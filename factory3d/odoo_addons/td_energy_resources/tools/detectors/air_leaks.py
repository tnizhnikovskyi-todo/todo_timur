"""Детектор `air_leaks` (R-17, W3-B). Каркас: тіло — воркер B.

Сигнатура (R-14): `detect(env, rule, now) -> list[dict]`; елемент `{"dedup_key", "title", "text",
"est_saving_month", "est_qty_month", "evidence", "node_code", "point_code"}`.
"""


def detect(env, rule, now):
    return []
