import json
from pathlib import Path

from iot_sim.core.rng import Rng, det, fnv1a32

GOLDEN = json.loads((Path(__file__).parent / "data/golden_rng.json").read_text())["series"]


def test_golden_sequence():
    for key, expected in GOLDEN.items():
        seed, code = key.split(":", 1)
        rng = Rng(int(seed), code)
        assert [rng.next() for _ in range(10)] == expected


def test_fnv_known_values():
    assert fnv1a32("") == 0x811C9DC5
    assert fnv1a32("a") == 0xE40C292C
    assert det("a") == fnv1a32("a")


def test_range_and_determinism():
    a, b = Rng(1, "x"), Rng(1, "x")
    vals = [a.next() for _ in range(1000)]
    assert vals == [b.next() for _ in range(1000)]
    assert all(-1 <= v < 1 for v in vals)
    assert Rng(2, "x").next() != vals[0]


def test_minute_noise_constant_within_minute():
    rng = Rng(5, "sig")
    r0 = rng.at(100)
    assert rng.at(100) == r0
    assert rng.at(99) == r0  # час назад не крокує
    r1 = rng.at(101)
    assert r1 != r0
    ref = Rng(5, "sig")
    ref.next()
    assert r1 == ref.next()
    r3 = rng.at(103)  # пропущені хвилини крокують стільки ж разів
    ref.next(), ref.next()
    assert r3 == ref.r


def test_state_roundtrip():
    a = Rng(7, "k")
    a.at(10)
    a.at(11)
    b = Rng(7, "k")
    b.from_dict(a.to_dict())
    assert b.at(12) == a.at(12)
