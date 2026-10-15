"""AC-49: parse_line, одиниці й перетворення показань (SPEC §8.5)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from conftest import make_signal

from f3d_collector_yard.sics import SicsPlugin, frame_readings, parse_line, to_kg

TS = datetime(2026, 10, 14, 6, 0, tzinfo=UTC)


def _readings(line, **kw):
    frame = parse_line(line)
    sigs = [make_signal("weight", **kw), make_signal("stable")]
    return {r.code.rsplit("/", 1)[1]: r for r in frame_readings(frame, sigs, TS)}


@pytest.mark.parametrize(
    ("line", "kind", "fid", "status", "value", "unit"),
    [
        ("S S      21380 kg\r\n", "weight", "S", "S", 21380.0, "kg"),
        (b"S D      21360 kg\r\n", "weight", "S", "D", 21360.0, "kg"),
        ("S S       21.38 t", "weight", "S", "S", 21.38, "t"),
        ("S S        -20 kg", "weight", "S", "S", -20.0, "kg"),
        ("S S      21380", "weight", "S", "S", 21380.0, "kg"),
        ("T S      14000 kg", "weight", "T", "S", 14000.0, "kg"),
        ("S I", "status", "S", "I", None, ""),
        ("S +", "status", "S", "+", None, ""),
        ("Z A", "status", "Z", "A", None, ""),
        ('I4 A "AX2026-0001"', "status", "I4", "A", None, ""),
        ("ES", "error", "ES", "", None, ""),
        ("ET", "error", "ET", "", None, ""),
        ("EL\r\n", "error", "EL", "", None, ""),
        ("", "empty", "", "", None, ""),
        ("garbage here", "error", "?", "", None, ""),
    ],
)
def test_parse_line(line, kind, fid, status, value, unit):
    frame = parse_line(line)
    assert (frame.kind, frame.id, frame.status, frame.value) == (kind, fid, status, value)
    if kind == "weight":
        assert frame.unit == unit


def test_status_text_and_default_unit():
    assert parse_line('I4 A "AX2026-0001"').text == "AX2026-0001"
    assert parse_line("S S 100", default_unit="t").unit == "t"


@pytest.mark.parametrize(
    ("value", "unit", "kg"),
    [(21380, "kg", 21380.0), (21380, "g", 21.38), (21.38, "t", 21380.0), (100, "lb", 45.359237), (5, "oz", None)],
)
def test_to_kg(value, unit, kg):
    got = to_kg(value, unit)
    assert got == pytest.approx(kg) if kg is not None else got is None


def test_readings_table():
    r = _readings("S S      21380 kg")
    assert (r["weight"].value, r["weight"].q, r["stable"].value, r["stable"].q) == (21380.0, "good", 1.0, "good")
    r = _readings("S D      21360 kg")
    assert (r["weight"].value, r["stable"].value) == (21360.0, 0.0)
    r = _readings("S S       21.38 t")
    assert r["weight"].value == pytest.approx(21380.0)
    r = _readings("S S        -20 kg")
    assert (r["weight"].value, r["weight"].q) == (-20.0, "good")
    for line, text in (("S I", "busy"), ("S +", "overload"), ("S -", "underload")):
        r = _readings(line)
        assert (r["weight"].value, r["weight"].q, r["weight"].text) == (None, "bad", text)
        assert (r["stable"].value, r["stable"].q) == (None, "bad")
    r = _readings("S S      21380 oz")
    assert (r["weight"].value, r["weight"].q, r["weight"].text) == (None, "bad", "unit oz")
    assert (r["stable"].value, r["stable"].q) == (1.0, "good")


def test_scale_offset_applied_to_weight():
    assert _readings("S S 21380 kg", scale=0.001)["weight"].value == pytest.approx(21.38)
    assert _readings("S S 21380 kg", scale=1, offset=-20)["weight"].value == 21360.0
    assert all(r.ts == TS for r in _readings("S S 1 kg").values())


def test_signals_without_known_field_skipped():
    frame = parse_line("S S 100 kg")
    sig = make_signal("weight", address={"cmd": "SI"})
    assert frame_readings(frame, [sig], TS) == []
    assert SicsPlugin.type == "sics"
