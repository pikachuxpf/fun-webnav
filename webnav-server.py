#!/usr/bin/env python3
"""fun-webnav backend: card registry with key-protected editing.

Serves the static site plus a small JSON API:

- GET  /api/links   -> {"groups": [...]}          public
- PUT  /api/links   -> replaces the registry      requires X-Admin-Key
- GET  /api/health  -> {"ok": true}

The admin key is read from the environment (FUNWEBNAV_ADMIN_KEY) and is
never hard-coded here. Data lives in a single JSON file under a fixed
trusted directory; no request input ever forms a filesystem path.
"""

import hmac
import http.client
import http.server
import json
import os
import pathlib
import socketserver
import urllib.parse

SITE_ROOT = pathlib.Path("/opt/fun-webnav/site").resolve()
DATA_FILE = pathlib.Path("/opt/directlink/data/funwebnav-links.json").resolve()
LISTEN_HOST = "127.0.0.1"
LISTEN_PORT = 8085
HOP_BY_HOP = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade", "content-length", "host",
}

DEFAULT_DATA = {
    "groups": [
        {"id": "ai", "name": "AI 模型接口", "desc": "OpenAI / Anthropic 兼容网关与管理台",
         "links": [
            {"name": "CPA 管理台", "url": "https://p.funpx.dpdns.org/management.html",
             "desc": "CLIProxyAPI 管理面板：账号代理接入与密钥管理", "host": "p.funpx.dpdns.org/management.html"},
            {"name": "Sub2API", "url": "https://api.funpx.cn/",
             "desc": "账号池聚合为 OpenAI 兼容 API：分组、渠道、令牌管理", "host": "api.funpx.cn"},
            {"name": "OpenCode2API", "url": "https://opencode2api.funpx.dpdns.org/",
             "desc": "OpenCode 源码版实例，每日同步上游模型列表", "host": "opencode2api.funpx.dpdns.org"},
         ]},
        {"id": "files", "name": "文件与网盘", "desc": "临时直链与对象存储",
         "links": [
            {"name": "DirectLink 传文件", "url": "https://pan.funpx.cn/",
             "desc": "拖入即得公网直链，历史云端同步", "host": "pan.funpx.cn"},
            {"name": "MinIO 控制台", "url": "https://console.funpx.cn/",
             "desc": "S3 对象存储控制台（已汉化）", "host": "console.funpx.cn"},
         ]},
        {"id": "mail", "name": "邮件", "desc": "临时邮箱",
         "links": [
            {"name": "MoeMail", "url": "https://moemail.funpx.cn/en",
             "desc": "自托管一次性邮箱，接注册验证码", "host": "moemail.funpx.cn"},
         ]},
        {"id": "misc", "name": "常用站点", "desc": "日常入口",
         "links": []},
    ]
}


def validated_data_file() -> pathlib.Path:
    resolved = DATA_FILE.resolve()
    if resolved.parent != DATA_FILE.parent:
        raise RuntimeError("data path left trusted directory")
    return resolved


def load_data() -> dict:
    try:
        raw = json.loads(validated_data_file().read_text(encoding="utf-8"))
        if isinstance(raw, dict) and isinstance(raw.get("groups"), list):
            return raw
    except Exception:
        pass
    return DEFAULT_DATA


def save_data(data: dict) -> None:
    path = validated_data_file()
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)


def sanitize(data: dict) -> dict:
    """Keep only known fields with sane lengths; drop anything unexpected."""
    groups_out = []
    for g in data.get("groups", [])[:20]:
        if not isinstance(g, dict):
            continue
        links_out = []
        for l in (g.get("links") or [])[:60]:
            if not isinstance(l, dict):
                continue
            url = str(l.get("url", "")).strip()
            if not url.startswith(("http://", "https://")):
                continue
            links_out.append({
                "name": str(l.get("name", ""))[:60] or url,
                "url": url[:500],
                "desc": str(l.get("desc", ""))[:160],
                "host": str(l.get("host", ""))[:160] or urllib.parse.urlsplit(url).hostname or "",
            })
        gid = str(g.get("id", ""))[:32] or ("g" + str(len(groups_out)))
        groups_out.append({
            "id": gid,
            "name": str(g.get("name", ""))[:40] or "未命名分组",
            "desc": str(g.get("desc", ""))[:120],
            "links": links_out,
        })
    return {"groups": groups_out}


class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "FpxWebNav/2"

    def log_message(self, fmt, *args):
        pass

    def _check_admin(self) -> bool:
        expected = os.environ.get("FUNWEBNAV_ADMIN_KEY", "")
        provided = self.headers.get("X-Admin-Key", "")
        if not expected or not provided:
            return False
        return hmac.compare_digest(provided, expected)

    def _send(self, status: int, body: bytes, ctype: str, cache: str = "no-store") -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", cache)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _send_json(self, status: int, payload) -> None:
        self._send(status, json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                   "application/json; charset=utf-8")

    def _serve_static(self, route: str) -> None:
        if route in ("/", "/index.html"):
            path = SITE_ROOT / "index.html"
            ctype = "text/html; charset=utf-8"
        elif route == "/style.css":
            path = SITE_ROOT / "style.css"
            ctype = "text/css; charset=utf-8"
        elif route == "/admin.html":
            path = SITE_ROOT / "admin.html"
            ctype = "text/html; charset=utf-8"
        else:
            self._send_json(404, {"error": "not found"})
            return
        try:
            resolved = path.resolve()
            if resolved.parent != SITE_ROOT:
                self._send_json(404, {"error": "not found"})
                return
            body = resolved.read_bytes()
        except Exception:
            self._send_json(404, {"error": "not found"})
            return
        self._send(200, body, ctype)

    def _handle_links_get(self) -> None:
        self._send_json(200, load_data())

    def _handle_links_put(self) -> None:
        if not self._check_admin():
            self._send_json(401, {"error": "unauthorized"})
            return
        length = int(self.headers.get("Content-Length") or 0)
        if length > 512 * 1024:
            self._send_json(413, {"error": "payload too large"})
            return
        raw = self.rfile.read(length) if length else b""
        try:
            data = json.loads(raw.decode("utf-8"))
        except Exception:
            self._send_json(400, {"error": "invalid json"})
            return
        clean = sanitize(data if isinstance(data, dict) else {})
        save_data(clean)
        self._send_json(200, {"saved": True, **clean})

    def do_GET(self):
        route = urllib.parse.urlsplit(self.path).path
        if route == "/api/links":
            self._handle_links_get()
        elif route == "/api/health":
            self._send_json(200, {"ok": True})
        else:
            self._serve_static(route)

    def do_HEAD(self):
        self.do_GET()

    def do_PUT(self):
        route = urllib.parse.urlsplit(self.path).path
        if route == "/api/links":
            self._handle_links_put()
        else:
            self._send_json(404, {"error": "not found"})

    def do_POST(self):
        self._send_json(404, {"error": "not found"})


class ThreadingServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


if __name__ == "__main__":
    ThreadingServer((LISTEN_HOST, LISTEN_PORT), Handler).serve_forever()
