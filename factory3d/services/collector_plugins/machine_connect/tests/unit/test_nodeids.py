"""AC-69: резолв nodeid за URI простору імен."""

from __future__ import annotations

import pytest
from asyncua import ua
from collector.core.errors import ConnectError
from f3d_collector_mc import nodeids

NS = [
    "http://opcfoundation.org/UA/",
    "urn:test",
    "http://example.org/other/",
    "http://opcfoundation.org/UA/Woodworking/",
    "http://opcfoundation.org/UA/ISA95-JOBCONTROL_V2/",
    "http://todo.ltd/f3d/iot_sim/instances/",
]
URI = "http://todo.ltd/f3d/iot_sim/instances/"
NID = "ns=2;s=SAW-1.State.Machine.Overview.CurrentState"


def test_resolve_by_uri():
    assert nodeids.resolve(NID, URI, NS) == ua.NodeId("SAW-1.State.Machine.Overview.CurrentState", 5)


def test_fallback_index():
    assert nodeids.resolve(NID, None, NS) == ua.NodeId("SAW-1.State.Machine.Overview.CurrentState", 2)


def test_missing_uri():
    with pytest.raises(ConnectError, match="namespace http://nope/ not found"):
        nodeids.resolve(NID, "http://nope/", NS)


def test_other_identifier_types():
    assert nodeids.resolve("ns=3;i=1005", None, NS) == ua.NodeId(1005, 3)
    guid = nodeids.resolve("ns=3;g=0e5e5c24-8c1c-4d9c-9a35-7c2a0e1c6d11", None, NS)
    assert guid.NodeIdType == ua.NodeIdType.Guid
    raw = nodeids.resolve("ns=3;b=AQID", None, NS)
    assert raw.Identifier == b"\x01\x02\x03"


@pytest.mark.parametrize(
    "bad",
    ["ns=2;x=1", "ns=;s=a", "s=abc", "ns=2;s=", "ns=2;s=" + "a" * 241, "ns=2;i=abc", "ns=2;g=zzz", "ns=2;b=***"],
)
def test_validate_errors(bad):
    with pytest.raises(ValueError):
        nodeids.validate(bad)


def test_validate_ok():
    assert nodeids.validate("ns=2;s=" + "a" * 240) == (2, "s", "a" * 240)
