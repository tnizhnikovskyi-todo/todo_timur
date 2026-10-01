"""Локальный TCP-туннель через HTTPS CONNECT-прокси облачной сессии Claude Code.

Нужен только в облачном контейнере, где наружу можно выйти лишь через прокси
из HTTPS_PROXY, а прокси сверяет заголовок Host с целью CONNECT.

    python3 ccr_tunnel.py 16333 167.233.49.46 6333 --http   # Qdrant REST
    python3 ccr_tunnel.py 15432 167.233.49.46 5432          # Postgres

--http подменяет заголовок Host на адрес назначения. Из офиса и VPN туннель не нужен.
"""
import os
import re
import socket
import sys
import threading

LPORT, RHOST, RPORT = int(sys.argv[1]), sys.argv[2], int(sys.argv[3])
HOSTFIX = "--http" in sys.argv
PROXY_PORT = int(os.environ["HTTPS_PROXY"].rstrip("/").rsplit(":", 1)[1])


def pipe(src, dst, fix=False):
    try:
        while data := src.recv(65536):
            if fix:
                data = re.sub(rb"(?im)^host:[^\r\n]*", f"Host: {RHOST}:{RPORT}".encode(), data)
            dst.sendall(data)
    except OSError:
        pass
    finally:
        for s in (src, dst):
            try:
                s.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass


def handle(conn):
    up = socket.create_connection(("127.0.0.1", PROXY_PORT))
    up.sendall(f"CONNECT {RHOST}:{RPORT} HTTP/1.1\r\nHost: {RHOST}:{RPORT}\r\n\r\n".encode())
    buf = b""
    while b"\r\n\r\n" not in buf:
        chunk = up.recv(4096)
        if not chunk:
            break
        buf += chunk
    if b" 200" not in buf.split(b"\r\n", 1)[0]:
        conn.close()
        up.close()
        return
    threading.Thread(target=pipe, args=(conn, up, HOSTFIX), daemon=True).start()
    pipe(up, conn)


srv = socket.socket()
srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
srv.bind(("127.0.0.1", LPORT))
srv.listen(16)
while True:
    c, _ = srv.accept()
    threading.Thread(target=handle, args=(c,), daemon=True).start()
