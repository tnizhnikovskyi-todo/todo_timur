"""R-22 п. 1: резолв `nodeid` (`ns=<n>;<s|i|g|b>=<ident>`) у ua.NodeId за URI простору імен."""

from __future__ import annotations

import base64
import binascii
import re
import uuid

from asyncua import ua
from collector.core.errors import ConnectError

NODEID_RE = re.compile(r"^ns=(\d+);([sigb])=(.{1,240})$")


def validate(nodeid: str) -> tuple[int, str, str]:
    """(ns, тип, ідентифікатор) або ValueError."""
    m = NODEID_RE.match(nodeid) if isinstance(nodeid, str) else None
    if m is None:
        raise ValueError(f"nodeid: недопустимий формат {nodeid!r}")
    ns, kind, ident = int(m.group(1)), m.group(2), m.group(3)
    try:
        _identifier(kind, ident)
    except ValueError as exc:
        raise ValueError(f"nodeid: {exc}") from exc
    return ns, kind, ident


def _identifier(kind: str, ident: str):
    if kind == "s":
        return ident
    if kind == "i":
        return int(ident)
    if kind == "g":
        return uuid.UUID(ident)
    try:
        return base64.b64decode(ident, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("недопустимий base64") from exc


def resolve(nodeid: str, ns_uri: str | None, ns_array: list[str]) -> ua.NodeId:
    """Індекс простору — позиція `ns_uri` у NamespaceArray (немає URI — індекс із рядка `ns=`)."""
    ns, kind, ident = validate(nodeid)
    if ns_uri:
        try:
            ns = ns_array.index(ns_uri)
        except ValueError:
            raise ConnectError(f"namespace {ns_uri} not found") from None
    value = _identifier(kind, ident)
    if kind == "s":
        return ua.NodeId(value, ns, ua.NodeIdType.String)
    if kind == "i":
        return ua.NodeId(value, ns)
    if kind == "g":
        return ua.NodeId(value, ns, ua.NodeIdType.Guid)
    return ua.NodeId(value, ns, ua.NodeIdType.ByteString)
