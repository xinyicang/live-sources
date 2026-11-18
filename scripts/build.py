# -*- coding: utf-8 -*-
"""
抓取 sources.txt 里的所有上游源 -> 实测可播性 -> 按分类输出 tv/live.txt 与 tv/live.m3u

判定口径：
  m3u8_ok : playlist 能取到 #EXTM3U，且第一个分片真能下到数据
  stream  : 直连流，HTTP 200 且带 Content-Type 视频/音频/octet-stream
其余一律丢弃。
"""
import json
import os
import re
import sys
import collections
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_FILE = os.path.join(ROOT, "sources.txt")
OUT_DIR = os.path.join(ROOT, "tv")

TIMEOUT = 6
WORKERS = 100
MAX_PER_CHANNEL = 4

UA_LIST = [
    "Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Mobile Safari/537.36",
    "okhttp/3.15.0",
    "TVBox/20240101",
]

VIDEO_CT = ("video/", "audio/", "application/octet-stream", "application/vnd.apple.mpegurl",
            "application/x-mpegurl", "mp2t")


def http_get(url, ua=None, rng=True, timeout=TIMEOUT):
    headers = {"User-Agent": ua or UA_LIST[0]}
    if rng:
        headers["Range"] = "bytes=0-2047"
    return requests.get(url, headers=headers, timeout=timeout, allow_redirects=True, stream=False)


def fetch_text(url):
    for ua in UA_LIST:
        for u in (url, urllib.parse.quote(url, safe=":/?&=%#+,")):
            try:
                r = http_get(u, ua=ua, rng=False)
                if r.status_code == 200 and len(r.content) > 0:
                    for enc in ("utf-8-sig", "utf-8", "gb18030"):
                        try:
                            return r.content.decode(enc)
                        except UnicodeDecodeError:
                            continue
                    return r.content.decode("utf-8", "replace")
            except Exception:
                continue
    return None


def parse_txt(text):
    out, genre = [], ""
    if "#EXTM3U" in text:
        name = ""
        for ln in text.splitlines():
            s = ln.strip()
            if not s:
                continue
            if s.startswith("#EXTINF"):
                m = re.search(r",([^,]+)$", s)
                grp = re.search(r'group-title="([^"]*)"', s)
                name = (m.group(1) if m else "").strip()
                if grp and grp.group(1).strip():
                    genre = grp.group(1).strip()
            elif not s.startswith("#") and s.lower().startswith(("http://", "https://", "rtmp://", "rtsp://")):
                if name:
                    out.append((genre, name, s))
        return out
    for ln in text.splitlines():
        s = ln.strip()
        if not s:
            continue
        if "#genre#" in s.lower():
            genre = s.split(",")[0].strip()
            continue
        if s.startswith("#") or "," not in s:
            continue
        n, u = s.split(",", 1)
        u = u.strip()
        if not u.lower().startswith(("http://", "https://", "rtmp://", "rtsp://")):
            continue
        if "bdstatic" in u and u.endswith(".mp4"):
            continue
        out.append((genre, n.strip(), u))
    return out


def load_sources():
    entries = []
    if not os.path.exists(SRC_FILE):
        return entries
    for ln in open(SRC_FILE, encoding="utf-8"):
        s = ln.strip()
        if not s or s.startswith("#") or "|" not in s:
            continue
        tag, url = s.split("|", 1)
        text = fetch_text(url.strip())
        if not text:
            print("[skip] %s 抓取失败" % tag)
            continue
        parsed = parse_txt(text)
        print("[ok] %s: %d 条" % (tag, len(parsed)))
        entries.extend(parsed)
    return entries


def probe_segment(seg_url):
    try:
        r = http_get(seg_url)
        if r.status_code in (200, 206) and len(r.content) >= 188:
            return True
    except Exception:
        return False
    return False


def probe(url):
    if url.lower().startswith(("rtmp://", "rtsp://")):
        import socket
        try:
            p = urllib.parse.urlparse(url)
            port = p.port or (443 if "rtsp" in url[:5] else 1935)
            socket.create_connection((p.hostname, port), timeout=4).close()
            return "stream"
        except Exception:
            return "fail"

    for ua in UA_LIST:
        try:
            r = http_get(url, ua=ua)
            ct = r.headers.get("Content-Type", "").lower()
            body = r.content[:4096]
            if r.status_code in (401, 403, 429):
                continue
            if r.status_code not in (200, 206):
                return "fail"
            if b"#EXTM3U" in body:
                segs = [l.strip() for l in body.decode("utf-8", "ignore").splitlines()
                        if l.strip() and not l.strip().startswith("#")]
                if not segs:
                    return "fail"
                seg = urllib.parse.urljoin(url, segs[0])
                return "m3u8_ok" if probe_segment(seg) else "fail"
            if any(ct.startswith(p) for p in VIDEO_CT) and len(body) > 0:
                return "stream"
            if len(body) > 1024 and ct and "text/html" not in ct:
                return "stream"
            return "fail"
        except Exception:
            continue
    return "fail"


def probe_all(urls):
    res = {}
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        for u, r in zip(urls, ex.map(probe, urls)):
            res[u] = r
    return res


CCTV_CN = {1: "综合", 2: "财经", 3: "综艺", 4: "中文国际", 5: "体育", 6: "电影", 7: "国防军事",
           8: "电视剧", 9: "纪录", 10: "科教", 11: "戏曲", 12: "社会与法", 13: "新闻",
           14: "少儿", 15: "音乐", 16: "奥林匹克", 17: "农业农村"}
KID = ["少儿", "儿童", "动画", "卡通", "卡酷", "优漫", "嘉佳", "炫动", "哈哈", "金鹰卡通",
       "宝宝", "亲子", "幼教", "KIDS", "JUNIOR", "海绵宝宝", "猫和老鼠", "小猪佩奇",
       "汪汪队", "巴啦啦"]
HKMO = ["凤凰", "翡翠", "明珠", "无线", "VIUTV", "香港", "澳门", "TVB", "爆谷", "星影",
        "超视", "唯心", "中旺", "华藏", "台湾", "东森", "中天", "三立", "民视", "TVBS",
        "台视", "中视", "华视", "公视", "靖天", "寰宇", "纬来", "非凡", "高点", "年代",
        "龙祥", "壹电视"]
PROV = ["北京", "天津", "上海", "重庆", "河北", "山西", "辽宁", "吉林", "黑龙江", "江苏",
        "浙江", "安徽", "福建", "江西", "山东", "河南", "湖北", "湖南", "广东", "海南",
        "四川", "贵州", "云南", "陕西", "甘肃", "青海", "内蒙古", "广西", "西藏", "宁夏",
        "新疆", "广州", "深圳", "苏州", "烟台", "杭州", "南京", "成都", "武汉", "西安",
        "哈尔滨", "长春", "沈阳", "济南", "郑州", "长沙", "福州", "南昌", "合肥",
        "石家庄", "太原", "南宁", "海口", "贵阳", "昆明", "兰州", "西宁", "银川", "厦门",
        "青岛", "大连", "宁波", "无锡", "温州", "绍兴", "嘉兴", "金华", "台州", "泉州",
        "东莞", "佛山"]
GROUP_HINT = {"央视频道": "央视", "卫视频道": "卫视", "儿童频道": "儿童", "地方频道": "地方",
              "数字频道": "地方"}


def norm_name(n):
    s = n.strip().upper().replace(" ", "")
    m = re.match(r"CCTV[-_]?(\d+)(\+)?", s)
    if m:
        num, plus = int(m.group(1)), m.group(2)
        if num == 4 and "4K" in s:
            return "CCTV4K"
        return ("CCTV%d+体育赛事" % num) if plus else ("CCTV%d%s" % (num, CCTV_CN.get(num, "")))
    return n.strip()


def classify(name, group=""):
    up = name.upper()
    if re.match(r"CCTV[-_]?14", up):
        return "儿童"
    if any(k in name or k.upper() in up for k in KID):
        return "儿童"
    if re.match(r"CCTV", up) or up.startswith(("CGTN", "CETV")):
        return "央视"
    if "卫视" in name:
        return "卫视"
    if any(k.upper() in up for k in HKMO):
        return "港澳"
    if any(p in name for p in PROV):
        return "地方"
    if any(k in name for k in ["电影", "春晚", "剧场", "影院", "纪录", "纪实", "体育", "音乐", "解说"]):
        return GROUP_HINT.get(group, "其他")
    if re.search(r"[\u4e00-\u9fff]", name):
        return GROUP_HINT.get(group, "其他")
    return "国际"


ORDER = ["儿童", "央视", "卫视", "地方", "港澳", "国际", "其他"]


def sort_key(cat, name):
    if cat == "央视":
        m = re.match(r"CCTV(\d+)", name)
        if m:
            return (0, int(m.group(1)), name)
        return (1, 0, name)
    return (0, 0, name)


def ukey(u):
    return re.sub(r"^https?://", "", u.strip()).rstrip("?").lower()


def write_output(rows):
    os.makedirs(OUT_DIR, exist_ok=True)
    txt = []
    m3u = ["#EXTM3U"]
    total = 0
    for cat in ORDER:
        if not rows[cat]:
            continue
        txt.append("%s,#genre#" % cat)
        for n, u in sorted(rows[cat], key=lambda x: (sort_key(cat, x[0]), x[0])):
            txt.append("%s,%s" % (n, u))
            m3u.append('#EXTINF:-1 group-title="%s",%s\n%s' % (cat, n, u))
            total += 1
        txt.append("")
    open(os.path.join(OUT_DIR, "live.txt"), "w", encoding="utf-8").write("\n".join(txt) + "\n")
    open(os.path.join(OUT_DIR, "live.m3u"), "w", encoding="utf-8").write("\n".join(m3u) + "\n")
    return total


def main():
    raw = load_sources()
    print("上游合计 %d 条，去重中..." % len(raw))

    seen, cand = set(), []
    for g, n, u in raw:
        if ukey(u) in seen:
            continue
        seen.add(ukey(u))
        cand.append((g, norm_name(n), u))
    urls = [u for _, _, u in cand]
    print("唯一链接 %d 个，开始探测..." % len(urls))

    res = probe_all(urls)
    good = {u for u, r in res.items() if r in ("m3u8_ok", "stream")}
    print("可播 %d / %d = %.1f%%" % (len(good), len(urls), len(good) / max(len(urls), 1) * 100))

    chan = collections.defaultdict(list)
    group_of = {}
    for g, n, u in cand:
        group_of.setdefault(n, g)
        if u in good:
            chan[n].append(u)

    rows = collections.defaultdict(list)
    for n, us in chan.items():
        cat = classify(n, group_of.get(n, ""))
        k, cnt = set(), 0
        for u in us:
            if ukey(u) in k:
                continue
            k.add(ukey(u))
            rows[cat].append((n, u))
            cnt += 1
            if cnt >= MAX_PER_CHANNEL:
                break

    total = write_output(rows)
    stats = {cat: {"channels": len({n for n, _ in rows[cat]}), "sources": len(rows[cat])} for cat in ORDER}
    stats["_total"] = {"channels": len(chan), "sources": total, "probed": len(urls), "ok": len(good)}
    json.dump(stats, open(os.path.join(ROOT, "stats.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
