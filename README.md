# 我的直播源仓库

自动抓取多个公开直播源 → 去重 → 按分类输出一份 TVBox 能直接用的 TXT。
GitHub Actions 每 6 小时自动跑一次并提交结果，不需要服务器。

## 产物

- `tv/live.txt` —— 主文件，`频道名,地址` + `#genre#` 分类头，共 7 组：儿童 / 央视 / 卫视 / 地方 / 港澳 / 国际 / 其他
- `tv/live.m3u` —— 同样的内容转成 M3U
- `stats.json` —— 每次运行的统计

## 订阅地址

Raw 地址在国内通常打不开，用加速前缀：

```
https://gh-proxy.com/https://raw.githubusercontent.com/xinyicang/live-sources/main/tv/live.txt
https://cdn.jsdelivr.net/gh/xinyicang/live-sources@main/tv/live.txt
```

TVBox：设置 → 配置地址 → 填上面任意一条。

## 工作模式：只聚合，不探测

GitHub 的 runner 在境外，国内 IPTV 面板大量对境外 IP 限流，线上实测会把还能用的源判死（同源本机测 98% 可播，runner 只有 80%）。
所以默认**直接相信上游**，只做抓取、去重、分类：

- 源码里 `PROBE = os.getenv("PROBE", "0") == "1"`
- 想恢复探测，在 workflow 里给 Build 步骤加 `env: PROBE: "1"`

## 上游源怎么加

编辑 `sources.txt`，一行一个，格式 `备注|地址`，支持上游 TXT（`频道名,地址` + `#genre#`）和 M3U：

```
vbskycn|https://raw.githubusercontent.com/vbskycn/iptv/master/tv/iptv4.txt
```

加源前先看上游自己是否持续刷新：三个月没更新的镜像，可播率会掉到 20% 以下。

## 判定口径（PROBE=1 时生效）

- `m3u8_ok`：playlist 能取到 `#EXTM3U`，且第一个分片真能下到数据
- `stream`：直连流，HTTP 200 且 Content-Type 为视频/音频/octet-stream
- 其余（401/403/404、空 body、分片挂掉的 m3u8）一律丢弃

## 免责与边界

- 仓库只存**链接**，不转存、不代理任何节目内容；链接均来自公开渠道。
- 公开聚合直播链接在国内的合规性存在争议，请勿用于商业分发。
