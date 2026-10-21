"""Зонний тариф демо-компанії (LP-07): три зони від базової ціни. Без ORM."""

BASE_PRICE = 8.4  # ₴/кВт·год — ціна умовного плаского тарифу td_energy
# (код зони td.energy.tariff.zone, назва, множник, [(з, до) годин доби])
ZONES = (
    ("night", "Ніч", 0.5, ((0.0, 7.0), (23.0, 24.0))),
    ("half_peak", "Напівпік", 1.0, ((7.0, 8.0), (11.0, 20.0), (22.0, 23.0))),
    ("peak", "Пік", 1.5, ((8.0, 11.0), (20.0, 22.0))),
)


def zone_rows(base=BASE_PRICE):
    """Рядки зон для `td.energy.tariff.zone` без `tariff_id`: окремий рядок на кожен інтервал годин."""
    rows = []
    seq = 10
    for code, name, k, spans in ZONES:
        for hour_from, hour_to in spans:
            rows.append(
                {
                    "sequence": seq,
                    "name": name,
                    "code": code,
                    "price": round(base * k, 4),
                    "weekdays": "0123456",
                    "hour_from": hour_from,
                    "hour_to": hour_to,
                }
            )
            seq += 10
    return rows


def covers_day(rows):
    """Зони щільно покривають добу: без прогалин і перекриттів (для тесту; перевірка є й у td_energy)."""
    spans = sorted((r["hour_from"], r["hour_to"]) for r in rows)
    pos = 0.0
    for start, end in spans:
        if start != pos:
            return False
        pos = end
    return pos == 24.0
