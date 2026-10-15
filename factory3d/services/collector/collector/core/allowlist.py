"""Allow-list хостів пристроїв (F3D_ALLOW_HOSTS), SPEC §8.10."""

from __future__ import annotations

import ipaddress
import logging
import socket
from collections.abc import Iterable
from typing import Any
from urllib.parse import urlsplit

from collector.core.errors import AllowlistDenied

log = logging.getLogger("collector.allowlist")

_IPNet = ipaddress.IPv4Network | ipaddress.IPv6Network


def _resolve(host: str) -> set[str]:
    try:
        return {str(ai[4][0]) for ai in socket.getaddrinfo(host, None)}
    except (OSError, UnicodeError):
        return set()


class Allowlist:
    """`allowlist(host)` -> None або AllowlistDenied. Резолв hostname -> IP; IP ∈ (імена, IP, CIDR)."""

    def __init__(self, entries: Iterable[str], odoo_url: str = "", metrics: Any = None) -> None:
        self.names: set[str] = set()
        self.nets: list[_IPNet] = []
        self.metrics = metrics
        for entry in entries:
            self.add(entry)
        if odoo_url:
            self.add(urlsplit(odoo_url).hostname or "")

    def add(self, entry: str) -> None:
        entry = entry.strip().lower()
        if not entry:
            return
        try:
            self.nets.append(ipaddress.ip_network(entry, strict=False))
        except ValueError:
            self.names.add(entry)

    def _allowed_ip(self, ip: str) -> bool:
        try:
            addr = ipaddress.ip_address(ip.split("%", 1)[0])
        except ValueError:
            return False
        return any(addr in net for net in self.nets)

    def is_allowed(self, host: str) -> bool:
        host = host.strip().strip("[]").lower()
        if not host:
            return False
        if host in self.names or self._allowed_ip(host):
            return True
        if any(c.isalpha() for c in host):  # hostname: резолвимо його і дозволені імена
            ips = _resolve(host)
            if any(self._allowed_ip(ip) for ip in ips):
                return True
            for name in self.names:
                if ips & _resolve(name):
                    return True
        return False

    def check(self, host: str) -> None:
        if self.is_allowed(host):
            return
        if self.metrics is not None:
            self.metrics.allowlist_denied.inc()
        log.warning("host %s is not in F3D_ALLOW_HOSTS", host)
        raise AllowlistDenied(f"host {host} is not allowed (F3D_ALLOW_HOSTS)")

    __call__ = check
