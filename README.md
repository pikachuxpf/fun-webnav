# fun-webnav

个人导航站 — Anthropic 风格的通用服务入口，部署于 `www.funpx.cn`。卡片内容由服务端 JSON 驱动，带密钥保护的管理后台，可随时增删改分组与链接。

## 功能

- **前台**（`/`）：按分组展示卡片，实时在线状态探测（60 秒刷新），状态汇总显示在页头
- **管理后台**（`/admin.html`）：输入管理密钥解锁后可编辑分组（名称/说明/删除）、链接（名称/网址/描述/域名标签），保存后立即对所有访客生效
- 管理密钥从环境变量 `FUNWEBNAV_ADMIN_KEY` 读取，不出现在任何源码或前端

## 结构

- `index.html` — 前台页面（数据来自 `/api/links`）
- `admin.html` — 管理后台
- `style.css` — 主题样式（Fraunces + Inter，骨白底 / 墨色标题 / 陶土强调色）
- `webnav-server.py` — 轻量后端：静态托管 + `/api/links` 读写（PUT 需 `X-Admin-Key`），数据持久化在 `/opt/directlink/data/funwebnav-links.json`

## 部署

```bash
# 服务器目录
/opt/fun-webnav/site/        # 静态文件
/opt/fun-webnav/webnav-server.py

# systemd: funwebnav.service（监听 127.0.0.1:8085，EnvironmentFile 提供 FUNWEBNAV_ADMIN_KEY）

# Caddy
www.funpx.cn {
    encode gzip
    handle /api/* {
        reverse_proxy 127.0.0.1:8085
    }
    root * /opt/fun-webnav/site
    file_server
}
```
