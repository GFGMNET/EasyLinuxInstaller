"""HTTP server for the menu (kiosk on the PC itself) and the remote UI.

Requests from the PC itself (localhost) need no token. Requests from other PCs
must send the token that is shown on the PC's screen (?token=… or X-Token).
"""

from __future__ import annotations

import hmac
import json
import mimetypes
import secrets
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import settings as settings_mod
from .job import Installer

UI_DIR = Path(__file__).resolve().parent / "ui"
I18N_DIR = Path(__file__).resolve().parent / "i18n"


def local_ips() -> list[str]:
    ips = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.add(info[4][0])
    except OSError:
        pass
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.0.2.1", 9))   # no packet is sent; picks the outgoing interface
            ips.add(s.getsockname()[0])
    except OSError:
        pass
    return sorted(ip for ip in ips if not ip.startswith("127."))


def make_handler(installer: Installer, token: str, port: int):
    class Handler(BaseHTTPRequestHandler):
        server_version = "EasyLinux"

        def log_message(self, fmt, *args):  # keep the journal quiet
            pass

        # ----- helpers -----
        def _is_local(self) -> bool:
            return self.client_address[0] in ("127.0.0.1", "::1", "::ffff:127.0.0.1")

        def _authorized(self) -> bool:
            if self._is_local():
                return True
            q = parse_qs(urlparse(self.path).query)
            given = self.headers.get("X-Token") or (q.get("token") or [""])[0]
            return hmac.compare_digest(given, token)

        def _send(self, code: int, body: bytes, ctype: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, code: int, data) -> None:
            self._send(code, json.dumps(data).encode(), "application/json")

        # ----- routes -----
        def do_GET(self):
            path = urlparse(self.path).path
            if path.startswith("/api/"):
                if not self._authorized():
                    return self._json(403, {"error": "token"})
                if path == "/api/state":
                    state = installer.state()
                    if self._is_local():   # only the PC's own screen shows the token
                        state["remote"] = {"token": token, "port": port, "ips": local_ips()}
                    return self._json(200, state)
                return self._json(404, {"error": "not found"})
            if path in ("/", "/index.html"):
                file = UI_DIR / "index.html"
            elif path.startswith("/i18n/"):
                file = I18N_DIR / Path(path).name
            else:
                file = UI_DIR / Path(path).name
            if not file.is_file():
                return self._send(404, b"not found", "text/plain")
            ctype = mimetypes.guess_type(file.name)[0] or "application/octet-stream"
            if ctype.startswith("text/") or ctype.endswith(("json", "javascript")):
                ctype += "; charset=utf-8"
            self._send(200, file.read_bytes(), ctype)

        def do_POST(self):
            path = urlparse(self.path).path
            if not self._authorized():
                return self._json(403, {"error": "token"})
            length = int(self.headers.get("Content-Length") or 0)
            try:
                body = json.loads(self.rfile.read(length) or b"{}")
            except json.JSONDecodeError:
                return self._json(400, {"error": "json"})
            if path == "/api/install":
                ok = installer.start(str(body.get("profile", "")), str(body.get("lang", "")))
                return self._json(200 if ok else 409, {"ok": ok})
            if path == "/api/retry":
                if installer.phase in ("error", "failed"):
                    threading.Thread(target=installer.load, daemon=True).start()
                return self._json(200, {"ok": True})
            return self._json(404, {"error": "not found"})

    return Handler


def main() -> None:
    s = settings_mod.load()
    s.workdir.mkdir(parents=True, exist_ok=True)
    token = s.token or secrets.token_hex(4).upper()   # 8 characters, shown on screen
    installer = Installer(s)
    threading.Thread(target=installer.load, daemon=True).start()
    server = ThreadingHTTPServer(("0.0.0.0", s.port), make_handler(installer, token, s.port))
    installer.log(f"Menu server on port {s.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
