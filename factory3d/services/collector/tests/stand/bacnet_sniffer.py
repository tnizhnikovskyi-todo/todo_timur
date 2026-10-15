"""Мінімальний сніфер BACnet/IP на loopback (AF_PACKET) для ТБ-06/ТБ-08: замість tcpdump/tshark, яких у середовищі немає.

Збирає UDP-кадри з портом 47808 від заданої адреси-джерела й розбирає BVLC/NPDU/APDU до типу PDU та сервісу.
Потрібен root (CAP_NET_RAW). Використання: ``with Sniffer(src="127.0.0.2") as sn: ...; sn.packets``.
"""

from __future__ import annotations

import socket
import struct
import threading
import time
from dataclasses import dataclass

ETH_P_ALL = 0x0003
UNCONFIRMED = {
    0: "i-am",
    1: "i-have",
    2: "unconfirmed-cov-notification",
    3: "unconfirmed-event-notification",
    4: "unconfirmed-private-transfer",
    5: "unconfirmed-text-message",
    6: "time-synchronization",
    7: "who-has",
    8: "who-is",
    9: "utc-time-synchronization",
}
CONFIRMED = {
    0: "acknowledge-alarm",
    1: "confirmed-cov-notification",
    2: "confirmed-event-notification",
    3: "get-alarm-summary",
    4: "get-enrollment-summary",
    5: "subscribe-cov",
    6: "atomic-read-file",
    7: "atomic-write-file",
    8: "add-list-element",
    9: "remove-list-element",
    10: "create-object",
    11: "delete-object",
    12: "read-property",
    13: "read-property-conditional",
    14: "read-property-multiple",
    15: "write-property",
    16: "write-property-multiple",
    17: "device-communication-control",
    18: "confirmed-private-transfer",
    19: "confirmed-text-message",
    20: "reinitialize-device",
    27: "life-safety-operation",
    28: "subscribe-cov-property",
}


@dataclass
class Packet:
    src: str
    dst: str
    sport: int
    dport: int
    kind: str  # confirmed | unconfirmed | network | ack | other
    service: str


def parse(frame: bytes) -> Packet | None:
    if len(frame) < 14 + 20 + 8 or frame[12:14] != b"\x08\x00":
        return None
    ip = frame[14:]
    ihl = (ip[0] & 0x0F) * 4
    if ip[9] != 17:
        return None
    src, dst = socket.inet_ntoa(ip[12:16]), socket.inet_ntoa(ip[16:20])
    sport, dport = struct.unpack("!HH", ip[ihl : ihl + 4])
    data = ip[ihl + 8 :]
    if len(data) < 4 or data[0] != 0x81:
        return None
    func = data[1]
    off = 4 + (6 if func == 0x04 else 0)  # forwarded-NPDU: адреса ініціатора
    if func not in (0x04, 0x09, 0x0A, 0x0B) or len(data) <= off + 2:
        return Packet(src, dst, sport, dport, "other", f"bvlc-{func:#x}")
    npdu = data[off:]
    ctrl = npdu[1]
    i = 2
    if ctrl & 0x20:  # DNET, DLEN, DADR
        dlen = npdu[i + 2]
        i += 3 + dlen
    if ctrl & 0x08:  # SNET, SLEN, SADR
        slen = npdu[i + 2]
        i += 3 + slen
    if ctrl & 0x20:
        i += 1  # hop count
    if ctrl & 0x80:
        return Packet(src, dst, sport, dport, "network", f"nl-{npdu[i]:#x}")
    apdu = npdu[i:]
    if not apdu:
        return None
    t = apdu[0] >> 4
    if t == 0:
        j = 4 + (2 if apdu[0] & 0x08 else 0)
        return Packet(src, dst, sport, dport, "confirmed", CONFIRMED.get(apdu[j], f"svc-{apdu[j]}"))
    if t == 1:
        return Packet(src, dst, sport, dport, "unconfirmed", UNCONFIRMED.get(apdu[1], f"svc-{apdu[1]}"))
    return Packet(src, dst, sport, dport, "ack", f"pdu-{t}")


class Sniffer:
    def __init__(self, src: str | None = None, ports: tuple[int, ...] = (47808,), tcp_dports: tuple[int, ...] = ()):
        self.src, self.ports, self.tcp_dports = src, ports, tcp_dports
        self.packets: list[Packet] = []
        self.tcp_syn: list[tuple[str, str, int]] = []
        self._stop = threading.Event()
        self._sock: socket.socket | None = None
        self._thr: threading.Thread | None = None

    def __enter__(self) -> Sniffer:
        self._sock = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.ntohs(ETH_P_ALL))
        self._sock.bind(("lo", 0))
        self._sock.settimeout(0.5)
        self._thr = threading.Thread(target=self._run, daemon=True)
        self._thr.start()
        time.sleep(0.3)
        return self

    def _run(self) -> None:
        assert self._sock is not None
        while not self._stop.is_set():
            try:
                frame = self._sock.recv(65535)
            except TimeoutError:
                continue
            except OSError:
                return
            if len(frame) >= 14 + 20 + 20 and frame[12:14] == b"\x08\x00" and frame[14 + 9] == 6 and self.tcp_dports:
                ihl = (frame[14] & 0x0F) * 4
                sport, dport = struct.unpack("!HH", frame[14 + ihl : 14 + ihl + 4])
                flags = frame[14 + ihl + 13]
                if dport in self.tcp_dports and flags & 0x02 and not flags & 0x10:
                    self.tcp_syn.append(
                        (socket.inet_ntoa(frame[14 + 12 : 14 + 16]), socket.inet_ntoa(frame[14 + 16 : 14 + 20]), dport)
                    )
                continue
            p = parse(frame)
            if p and (p.dport in self.ports or p.sport in self.ports) and (self.src is None or p.src == self.src):
                self.packets.append(p)

    def __exit__(self, *exc) -> None:
        self._stop.set()
        if self._thr:
            self._thr.join(2)
        if self._sock:
            self._sock.close()
