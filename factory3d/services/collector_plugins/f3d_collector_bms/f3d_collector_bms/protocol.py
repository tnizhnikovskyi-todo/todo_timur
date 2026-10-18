"""Кадрування й розбір ASCII HelvarNet (SPEC td_bms §8.3, R-31). Чисті функції, без мережі."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

MAX_FRAME = 1500
ALLOWED_COMMANDS = frozenset({11, 13, 102, 104, 109, 110, 152, 161, 164, 191})
PARAM_ORDER = ("B", "S", "L", "F", "A")
ADDRESS_RE = re.compile(r"^@\d{1,3}(\.\d{1,3}\.\d{1,4}\.\d{1,3})?$")
DEVICE_RANGE_RE = re.compile(r"^@(\d{1,3})\.(\d{1,3})\.(\d{1,4})\.(\d{1,3})(?:-(\d{1,3}))?$")

ERROR_TEXTS = {
    1: "Invalid group index parameter",
    2: "Invalid cluster parameter",
    3: "Invalid router parameter",
    4: "Invalid subnet parameter",
    5: "Invalid device parameter",
    6: "Invalid sub device parameter",
    7: "Invalid block parameter",
    8: "Invalid scene parameter",
    9: "Cluster does not exist",
    10: "Router does not exist",
    11: "Device does not exist",
    12: "Property does not exist",
    13: "Invalid RAW message size",
    14: "Invalid messages type",
    15: "Invalid message command",
    16: "Missing ASCII terminator",
    17: "Missing ASCII parameter",
    18: "Incompatible version",
}


class ProtocolError(Exception):
    """Кадр не відповідає формату HelvarNet."""


class HelvarError(Exception):
    """Роутер відповів кадром `!…=<код>#`."""

    def __init__(self, code: int, text: str | None = None) -> None:
        self.code = code
        self.text = text or ERROR_TEXTS.get(code, "unknown error")
        super().__init__(f"HelvarNet error {code}: {self.text}")


@dataclass
class Frame:
    kind: str  # reply | error | push | partial
    version: int | None
    cmd: int
    params: dict = field(default_factory=dict)
    address: str | None = None
    answer: str | None = None


def _check_group(group: int) -> None:
    if isinstance(group, bool) or not isinstance(group, int) or not 1 <= group <= 16383:
        raise ValueError(f"group {group!r} out of range 1..16383")


def build_query(
    version: int, cmd: int, group: int | None = None, address: str | None = None, extra: dict | None = None
) -> str:
    """`>V:{v},C:{cmd}[,G:{g}][,B:…,S:…,L:…,F:…,A:…][,{address}]#`."""
    if version not in (1, 2):
        raise ValueError(f"version {version!r} not supported")
    if cmd not in ALLOWED_COMMANDS:
        raise ValueError(f"command {cmd!r} not allowed")
    parts = [f"V:{version}", f"C:{cmd}"]
    if group is not None:
        _check_group(group)
        parts.append(f"G:{group}")
    extra = dict(extra or {})
    for key in PARAM_ORDER:
        if key in extra:
            value = extra.pop(key)
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"parameter {key} must be int")
            parts.append(f"{key}:{value}")
    if extra:
        raise ValueError(f"unknown parameters {sorted(extra)}")
    if address is not None:
        if not ADDRESS_RE.match(address):
            raise ValueError(f"bad address {address!r}")
        parts.append(address)
    return ">" + ",".join(parts) + "#"


def build_command(
    version: int,
    cmd: int,
    group: int,
    level: int | None = None,
    scene: int | None = None,
    block: int = 1,
    fade_cs: int = 200,
    ack: bool = True,
) -> str:
    """Запис: C:13 (рівень групи) або C:11 (сцена); fade_cs — сотні секунди."""
    if not 0 <= fade_cs <= 9000:
        raise ValueError("fade_cs out of range 0..9000")
    extra: dict[str, int] = {}
    if cmd == 13:
        if level is None or isinstance(level, bool) or not 0 <= level <= 100:
            raise ValueError("level out of range 0..100")
        extra["L"] = level
    elif cmd == 11:
        if scene is None or isinstance(scene, bool) or not 1 <= scene <= 16:
            raise ValueError("scene out of range 1..16")
        if not 1 <= block <= 8:
            raise ValueError("block out of range 1..8")
        extra["B"] = block
        extra["S"] = scene
    else:
        raise ValueError(f"command {cmd!r} is not a write command")
    extra["F"] = fade_cs
    if ack:
        extra["A"] = 1
    return build_query(version, cmd, group=group, extra=extra)


def parse_frame(text: str) -> Frame:
    text = text.strip()
    if len(text) < 3 or text[0] not in "?!>" or text[-1] not in "#$":
        raise ProtocolError(f"bad frame {text[:60]!r}")
    kind = {"?": "reply", "!": "error", ">": "push"}[text[0]]
    if text[-1] == "$":
        if kind != "reply":
            raise ProtocolError("partial frame must be a reply")
        kind = "partial"
    head, sep, answer = text[1:-1].partition("=")
    if kind == "push" and sep:
        raise ProtocolError("push frame with answer")
    params: dict[str, str] = {}
    address = None
    for token in head.split(","):
        token = token.strip()
        if token.startswith("@"):
            address = token
        elif len(token) > 2 and token[1] == ":":
            params[token[0]] = token[2:]
        elif token:
            raise ProtocolError(f"bad token {token!r}")
    if "C" not in params:
        raise ProtocolError("missing C")
    try:
        cmd = int(params.pop("C"))
        version = int(params.pop("V")) if "V" in params else None
    except ValueError as exc:
        raise ProtocolError(str(exc)) from exc
    return Frame(kind, version, cmd, params, address, answer if sep else None)


def split_stream(buffer: bytes) -> tuple[list[str], bytes]:
    """Ділить потік на кадри за `#`/`$`; байти до першого `?`/`!`/`>` відкидаються; залишок — незавершений кадр."""
    text = buffer.decode("latin-1")
    frames: list[str] = []
    pos = 0
    n = len(text)
    while pos < n:
        start = next((i for i in range(pos, n) if text[i] in "?!>"), None)
        if start is None:
            return frames, b""
        ends = [i for i in (text.find("#", start), text.find("$", start)) if i >= 0]
        if not ends:
            if n - start > MAX_FRAME:
                raise ProtocolError("frame too long")
            return frames, text[start:].encode("latin-1")
        end = min(ends)
        if end - start + 1 > MAX_FRAME:
            raise ProtocolError("frame too long")
        frames.append(text[start : end + 1])
        pos = end + 1
    return frames, b""


def decode_level(answer: str) -> int:
    try:
        n = int(answer)
    except (TypeError, ValueError) as exc:
        raise ProtocolError(f"bad level {answer!r}") from exc
    if n & 0x80000000:
        return 0
    return min(100, n & 0x7F)


def expand_devices(items: list[str]) -> list[str]:
    """`["@1.2.1.1-3"]` -> `["@1.2.1.1", "@1.2.1.2", "@1.2.1.3"]`; > 255 пристроїв або d1 > d2 -> ValueError."""
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        m = DEVICE_RANGE_RE.match(item)
        if not m:
            raise ValueError(f"bad device {item!r}")
        c, r, s, d1, d2 = m.groups()
        first = int(d1)
        last = int(d2) if d2 is not None else first
        if first > last:
            raise ValueError(f"bad range {item!r}")
        for d in range(first, last + 1):
            addr = f"@{c}.{r}.{s}.{d}"
            if addr not in seen:
                seen.add(addr)
                out.append(addr)
            if len(out) > 255:
                raise ValueError("more than 255 devices")
    return out


def key_for(cmd: int, group: int | None = None, address: str | None = None) -> tuple:
    return (cmd, group if group is not None else address)


def key_of(frame: Frame) -> tuple:
    """Ключ кореляції `(cmd, G | адреса)`."""
    g = frame.params.get("G")
    try:
        group = int(g) if g is not None else None
    except ValueError:
        group = None
    return key_for(frame.cmd, group, frame.address)
