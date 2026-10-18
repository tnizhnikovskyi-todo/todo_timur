"""AC-64…AC-67, AC-73: протокол HelvarNet і схеми (чисті функції)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from f3d_collector_bms import protocol as pr
from f3d_collector_bms.helvarnet import HelvarNetPlugin, faulty_text, sample_positions


def test_build_query():
    assert pr.build_query(2, 152, address="@1.2.1.5") == ">V:2,C:152,@1.2.1.5#"
    assert pr.build_query(2, 161, group=12) == ">V:2,C:161,G:12#"
    assert pr.build_query(2, 102, address="@1") == ">V:2,C:102,@1#"
    assert pr.build_query(2, 109, group=12, extra={"B": 2}) == ">V:2,C:109,G:12,B:2#"


def test_build_command():
    assert pr.build_command(2, 13, 12, level=60, fade_cs=100) == ">V:2,C:13,G:12,L:60,F:100,A:1#"
    assert pr.build_command(2, 11, 12, scene=3, block=1, fade_cs=200) == ">V:2,C:11,G:12,B:1,S:3,F:200,A:1#"
    assert pr.build_command(1, 13, 12, level=0, fade_cs=0, ack=False) == ">V:1,C:13,G:12,L:0,F:0#"


def test_build_invalid():
    with pytest.raises(ValueError):
        pr.build_query(2, 161, group=0)
    with pytest.raises(ValueError):
        pr.build_query(2, 152, address="@1.2.1")
    with pytest.raises(ValueError):
        pr.build_query(3, 152, address="@1.2.1.5")
    with pytest.raises(ValueError):
        pr.build_query(2, 19, group=1)
    with pytest.raises(ValueError):
        pr.build_command(2, 13, 12, level=101)
    with pytest.raises(ValueError):
        pr.build_command(2, 11, 12, scene=17)
    with pytest.raises(ValueError):
        pr.build_command(2, 152, 12, level=5)


def test_parse_reply_error_push_partial():
    f = pr.parse_frame("?V:2,C:152,@1.2.1.5=75#")
    assert (f.kind, f.cmd, f.address, f.answer, f.version) == ("reply", 152, "@1.2.1.5", "75", 2)
    f = pr.parse_frame("!V:2,C:104,@2.2.1.1=11#")
    assert (f.kind, f.answer) == ("error", "11")
    f = pr.parse_frame(">V:2,C:13,G:12,L:60,F:100#")
    assert f.kind == "push" and f.params == {"G": "12", "L": "60", "F": "100"}
    f = pr.parse_frame("?V:2,C:164,G:16=@1.2.3.1,@1.2.3.2$")
    assert f.kind == "partial" and f.answer == "@1.2.3.1,@1.2.3.2"
    assert pr.key_of(f) == (164, 16)
    assert pr.key_of(pr.parse_frame("?V:2,C:152,@1.2.1.5=75#")) == (152, "@1.2.1.5")
    for bad in ("hello#", "?V:2,C:152", "?V:2,V:2=1#"):
        with pytest.raises(pr.ProtocolError):
            pr.parse_frame(bad)


def test_split_stream():
    frames, rest = pr.split_stream(b"xx?V:2,C:191=2#>V:2,C:13,G:1,L:5#?V:2")
    assert frames == ["?V:2,C:191=2#", ">V:2,C:13,G:1,L:5#"]
    assert rest == b"?V:2"
    frames, rest = pr.split_stream(rest + b",C:164,G:1=@1.1.1.1$?V:2,C:164,G:1=@1.1.1.2#")
    assert len(frames) == 2 and rest == b""


def test_frame_too_long():
    with pytest.raises(pr.ProtocolError):
        pr.split_stream(b"?V:2,C:164,G:1=" + b"a" * 1600 + b"#")
    with pytest.raises(pr.ProtocolError):
        pr.split_stream(b"?V:2,C:164,G:1=" + b"a" * 1600)


def test_decode_level():
    assert [pr.decode_level(x) for x in ("75", "2147483649", "100", "127", "0")] == [75, 0, 100, 100, 0]
    with pytest.raises(pr.ProtocolError):
        pr.decode_level("abc")


def test_expand_devices():
    assert pr.expand_devices(["@1.2.1.1-3"]) == ["@1.2.1.1", "@1.2.1.2", "@1.2.1.3"]
    assert pr.expand_devices(["@1.2.1.5", "@1.2.1.5"]) == ["@1.2.1.5"]
    with pytest.raises(ValueError):
        pr.expand_devices(["@1.2.1.5-3"])
    with pytest.raises(ValueError):
        pr.expand_devices(["@1.2.1.1-200", "@1.2.2.1-200"])
    with pytest.raises(ValueError):
        pr.expand_devices(["1.2.1.1"])


def test_helpers():
    assert sample_positions(27, 3) == [0, 13, 26]
    assert sample_positions(2, 3) == [0, 1]
    assert sample_positions(1, 3) == [0]
    assert sample_positions(0, 3) == []
    assert faulty_text([]) == "—"
    assert faulty_text(["1.2.1.5", "1.2.1.9"]) == "1.2.1.5,1.2.1.9"
    text = faulty_text([f"1.2.1.{d}" for d in range(1, 13)])
    assert len(text) <= 64 and text.endswith(tuple(f"+{n}" for n in range(1, 13)))


def _errors(schema, instance):
    return list(Draft202012Validator(schema).iter_errors(instance))


def _telemetry_validate():
    path = Path(__file__).resolve().parents[3].parent / "odoo_addons/td_telemetry/tools/address.py"
    if not path.exists():
        return None
    spec = importlib.util.spec_from_file_location("f3d_tel_address", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.validate_address


def test_schemas():
    addr = HelvarNetPlugin.address_schema
    params = HelvarNetPlugin.params_schema
    good = [
        {"group": 12, "query": "level"},
        {"query": "router", "device": "@1.2.0.0"},
        {"group": 12},
        {"group": 12, "query": "faulty", "devices": ["@1.2.1.1-27"], "mask": 0x0800000E},
        {"group": 12, "query": "power", "scale": 0.001},
    ]
    for a in good:
        assert _errors(addr, a) == [], a
    bad = [
        {"query": "level"},
        {"group": 12, "query": "bogus"},
        {"group": 12, "sample": 0},
        {"group": 12, "fade_s": 100},
        {"query": "router"},
        {"group": 20000},
    ]
    for a in bad:
        assert _errors(addr, a), a
    assert _errors(params, {"host": "10.0.0.1", "router": 2}) == []
    assert _errors(params, {"host": "10.0.0.1", "router": 2, "protocol": "udp"}) == []
    assert _errors(params, {"host": "10.0.0.1"})
    assert _errors(params, {"host": "10.0.0.1", "router": 2, "rate_per_s": 0})
    validate = _telemetry_validate()
    if validate is not None:
        for a in good:
            assert validate("helvarnet", a) == [], a


def test_allowed_commands():
    assert pr.ALLOWED_COMMANDS == {11, 13, 102, 104, 109, 110, 152, 161, 164, 191}
    for cmd in (19, 20, 21, 22, 23, 24, 100, 111):
        with pytest.raises(ValueError):
            pr.build_query(2, cmd, group=1)
