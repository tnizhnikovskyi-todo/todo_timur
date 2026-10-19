"""Журналюючий TLS-проксі між Odoo і BioStar-емулятором (ТБ-08): пише ``METHOD path status`` кожного запиту у файл.

Емулятор не логує запити (uvicorn log_level=warning), тому лічильник записів (POST /api/cards, PUT/POST /api/users)
ведеться тут. Проксі завершує TLS тим самим самопідписаним сертифікатом емулятора і пересилає запити на його HTTP-порт
(A-07). Запуск: ``python logging_proxy.py <cert> <key> <лог> [listen_port=18443] [upstream=http://127.0.0.1:8081]``.
"""

from __future__ import annotations

import ssl
import sys
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

LOCK = threading.Lock()


def make_handler(upstream: str, log_path: str):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *args):  # тиша в консолі
            return

        def _forward(self):
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length) if length else None
            req = urllib.request.Request(upstream + self.path, data=body, method=self.command)
            for key, val in self.headers.items():
                if key.lower() not in ("host", "content-length", "connection"):
                    req.add_header(key, val)
            try:
                resp = urllib.request.urlopen(req, timeout=60)  # noqa: S310 - лише 127.0.0.1
            except urllib.error.HTTPError as err:
                resp = err
            data = resp.read()
            with LOCK, open(log_path, "a", encoding="utf-8") as fh:
                status = getattr(resp, "status", None) or resp.code
                fh.write(f"{self.command} {self.path.split('?')[0]} {status}\n")
            self.send_response(getattr(resp, "status", None) or resp.code)
            for key, val in resp.headers.items():
                if key.lower() not in ("transfer-encoding", "connection", "content-length"):
                    self.send_header(key, val)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        do_GET = do_POST = do_PUT = do_DELETE = do_PATCH = _forward  # noqa: N815

    return Handler


def main(argv: list[str]) -> None:
    cert, key, log_path = argv[1:4]
    port = int(argv[4]) if len(argv) > 4 else 18443
    upstream = argv[5] if len(argv) > 5 else "http://127.0.0.1:8081"
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(upstream, log_path))
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(cert, key)
    server.socket = ctx.wrap_socket(server.socket, server_side=True)
    server.serve_forever()


if __name__ == "__main__":
    main(sys.argv)
