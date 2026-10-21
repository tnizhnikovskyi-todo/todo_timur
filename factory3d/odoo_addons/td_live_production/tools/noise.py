"""Детермінований «шум»: ті самі ключі дають ті самі числа на будь-якому тику й після перезапуску. Без ORM.

Диспетчер на кожному тику перераховує стан із бази, тож фактична тривалість операції має бути функцією ключа
(`wo<id>`), а не `random()`: інакше операція завершувалась би в різний час на сусідніх тиках.
"""

import hashlib
import random

NOISE_PCT = 0.15


def rng(key):
    """`random.Random`, засіяний SHA-256 ключа (хеш `str` у Python випадковий, тому свій)."""
    digest = hashlib.sha256(str(key).encode("utf-8")).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


def unit(key):
    """Число з `[-1, 1]` за ключем."""
    return rng(key).uniform(-1.0, 1.0)


def noisy_minutes(planned, key, pct=NOISE_PCT):
    """Фактична тривалість: план ±`pct` (за замовчуванням ±15 %), не менше хвилини."""
    return max(1.0, planned * (1.0 + pct * unit(key)))
