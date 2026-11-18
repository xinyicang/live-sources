# 我的直播源仓库

自动抓取多个公开直播源 → 逐个实测可播性 → 按分类输出一份 TVBox 能直接用的 TXT。
GitHub Actions 每 6 小时自动跑一次并提交结果，不需要服务器。

## 产物

- `tv/live.txt` —— 主文件，`频道名,地址` + `#genre#` 分类头，共 7 组：儿童 / 央视 / 卫视 / 地方 / 港澳 / 国际 / 其他
- `tv/live.m3u` —— 同样的内容转成 M3U，给不认 TXT 的播放器
- `stats.json` —— 每次运行的可播率统计

## 订阅地址

Raw 地址在国内通常打不开，用加速前缀：

```
https://gh-proxy.com/https://raw.githubusercontent.com/xinyicang/live-sources/main/tv/live.txt
https://cdn.jsdelivr.net/gh/xinyicang/live-sources@main/tv/live.txt
```

TVBox：设置 → 配置地址 → 填上面任意一条（或本地文件）。

## 上游源怎么加

编辑 `sources.txt`，一行一个，格式 `备注|地址`，支持上游 TXT（`频道名,地址` + `#genre#`）和 M3U：

```
vbskycn|https://raw.githubusercontent.com/vbskycn/iptv/master/tv/iptv4.txt
```

每加一个上游，覆盖面就大一圈，但跑得也更慢（1000 条以内约 3 分钟）。

## 手动跑一次

```bash
pip install requests
python scripts/build.py
```

## 判定口径

- `m3u8_ok`：playlist 能取到 `#EXTM3U`，且第一个分片真能下到数据
- `stream`：直连流，HTTP 200 且 Content-Type 为视频/音频/octet-stream
- 其余（401/403/404、空 body、分片挂掉的 m3u8）一律丢弃

## 免责与边界

- 仓库只存**链接**，不转存、不代理任何节目内容；链接均来自公开渠道。
- 原站失效时脚本会自动剔除。
- 公开聚合直播链接在国内的合规性存在争议，请勿用于商业分发。
