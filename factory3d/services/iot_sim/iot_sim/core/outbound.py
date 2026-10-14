"""Allow-list вихідних з'єднань (SPEC §8.2.1 ``SIM_ALLOW_OUTBOUND``, §11, AC-23).

``OutboundGuard.install()`` обгортає ``socket.create_connection``: перевірка hostname перед
кожним connect; поза списком — ``OutboundDenied``, лічильник ``denied_total``
(``iot_sim_outbound_denied_total``) і WARNING. Для HTTP-клієнтів — ``check_url()``/``httpx_hook``.
ASSUMPTION: «сирий» ``socket.connect`` на IP не перехоплюється (hostname там уже втрачено);
усі клієнти сервісу створюються через ``create_connection``/httpx.
"""
from __future__ import annotations

import ipaddress
import logging
import socket
from collections.abc import Callable
from urllib.parse import urlsplit

log = logging.getLogger("iot_sim.outbound")


class OutboundDenied(Exception):
    """Вихідне з'єднання поза allow-list."""

    def __init__(self, host: str) -> None:
        super().__init__(f"outbound connection to {host!r} is not allowed")
        self.host = host


class OutboundGuard:
    def __init__(self, allow: str | list[str] = "",
                 on_denied: Callable[[str], None] | None = None) -> None:
        if isinstance(allow, str):
            allow = [h for h in (x.strip() for x in allow.split(",")) if h]
        self.allow = [h.lower() for h in allow]
        self.denied_total = 0
        self.on_denied = on_denied
        self._orig = None

    def is_allowed(self, host: str) -> bool:
        h = (host or "").strip().lower().strip("[]")
        for rule in self.allow:
            if rule == h:
                return True
            if rule.startswith("*.") and h.endswith(rule[1:]):
                return True
            if "/" in rule:
                try:
                    if ipaddress.ip_address(h) in ipaddress.ip_network(rule, strict=False):
                        return True
                except ValueError:
                    continue
        return False

    def check(self, host: str) -> None:
        if self.is_allowed(host):
            return
        self.denied_total += 1
        log.warning("outbound denied: %s", host)
        if self.on_denied:
            self.on_denied(host)
        raise OutboundDenied(host)

    def check_url(self, url: str) -> None:
        self.check(urlsplit(url).hostname or "")

    async def httpx_hook(self, request) -> None:
        """``httpx.AsyncClient(event_hooks={"request": [guard.httpx_hook]})``."""
        self.check(request.url.host)

    def install(self) -> None:
        if self._orig is not None:
            return
        orig = socket.create_connection
        guard = self

        def guarded(address, *args, **kwargs):
            guard.check(address[0])
            return orig(address, *args, **kwargs)

        self._orig = orig
        socket.create_connection = guarded

    def uninstall(self) -> None:
        if self._orig is not None:
            socket.create_connection = self._orig
            self._orig = None
