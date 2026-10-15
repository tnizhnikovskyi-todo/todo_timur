"""R-00: детермінований шум макета (SPEC §8.2.2, §9.1).

``s0 = fnv1a32(code) XOR seed``; кожен крок ``s = (s*1103515245 + 12345) mod 2**31``,
``r = s/2**30 - 1`` ∈ [-1, 1). Та сама послідовність, що в ``action_iot_tick`` макета.
"""
from __future__ import annotations

from typing import Any

FNV_OFFSET = 0x811C9DC5
FNV_PRIME = 0x01000193
LCG_A = 1103515245
LCG_C = 12345
LCG_M = 2**31
MAX_CATCHUP = 7 * 1440  # ASSUMPTION: після стрибка sim-часу > тижня ряд просто продовжується


def fnv1a32(text: str) -> int:
    """FNV-1a 32 біт по UTF-8 (так само, як ``plant/odoo_demo.py:det``)."""
    h = FNV_OFFSET
    for b in text.encode("utf-8"):
        h = ((h ^ b) * FNV_PRIME) & 0xFFFFFFFF
    return h


def det(code: str) -> int:
    """Детермінований хеш коду (``det`` макета) для ``det(code) % N`` у правилах R-23/R-28."""
    return fnv1a32(code)


class Rng:
    """Детермінований генератор шуму одного сигналу.

    ``next()`` — один крок LCG. ``at(minute)`` — «хвилинний» шум: новий ``r`` на кожну
    sim-хвилину (``minute`` — ціле, зазвичай ``epoch_s // 60``); між хвилинами ``r`` не змінюється,
    тож ряд не залежить від ``factor`` і кроку тіку.
    """

    def __init__(self, seed: int, code: str) -> None:
        self.seed = seed
        self.code = code
        self.state = (fnv1a32(code) ^ seed) & 0xFFFFFFFF
        self.r = 0.0
        self.minute: int | None = None

    def next(self) -> float:
        self.state = (self.state * LCG_A + LCG_C) % LCG_M
        self.r = self.state / 2**30 - 1.0
        return self.r

    def at(self, minute: int, origin: int | None = None) -> float:
        """``r`` для sim-хвилини ``minute``. ``origin`` — хвилина першого ``r`` (початок світу):
        ряд тоді не залежить від того, коли сигнал уперше запитали. Кроків LCG — стільки,
        скільки хвилин пройшло (стеля ``MAX_CATCHUP`` при великих стрибках часу)."""
        if self.minute is None:
            self.next()
            self.minute = min(minute, origin) if origin is not None else minute
        if minute > self.minute:
            for _ in range(min(minute - self.minute, MAX_CATCHUP)):
                self.next()
            self.minute = minute
        return self.r

    def to_dict(self) -> dict[str, Any]:
        return {"state": self.state, "r": self.r, "minute": self.minute}

    def from_dict(self, d: dict[str, Any]) -> None:
        self.state = int(d["state"])
        self.r = float(d["r"])
        self.minute = d["minute"]
