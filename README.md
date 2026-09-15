# fun-webnav

funpx.cn 自托管服务导航站 — Anthropic 风格的统一服务入口，部署于 `www.funpx.cn`。

收录范围：AI 模型接口（CPA / Sub2API / OpenCode2API）、文件与网盘（DirectLink / MinIO 控制台）、邮件（MoeMail）。每张卡片带实时在线状态探测（60 秒刷新，`no-cors` fetch）。

## 结构

- `index.html` — 单页导航，按用途分组
- `style.css` — 主题样式（Fraunces + Inter，骨白底 / 墨色标题 / 陶土强调色）

## 部署

静态站点，服务器上由 Caddy 托管：

```caddyfile
www.funpx.cn {
    encode gzip
    root * /opt/fun-webnav
    file_server
}
```

同步到服务器：

```bash
scp -r index.html style.css root@<server>:/opt/fun-webnav/
systemctl reload caddy
```
