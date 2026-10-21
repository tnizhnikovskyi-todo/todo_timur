"""R-31: портальний склад плит у 3D — чисті функції (без ORM): секунди доби, середньозважені відходи розкрою.

Збір даних з ORM — `td.portal` (`models/td_portal.py`). Арифметику залишку стосу за часом `t` (показання порталу
+ листи з журналів завдань) виконує клієнт (`td_machine_connect_viewer3d/static/src/layer/portal_layer.js`).
"""

from datetime import timezone

from ..models.td_machine import KYIV

CYCLE_S = 27  # цикл листа порталу (td_iot_sim R-18): 10 с до стосу, 4 с захоплення, 10 с до верстата, 3 с кладемо
LOG_MAX = 30  # записів журналу листів на завдання в payload (останні)
JOBS_MAX = 60  # завдань порталу в payload за добу (активні й у черзі — завжди)


def day_start(now):
    """Початок київської доби, що містить `now` (naive UTC) → naive UTC."""
    local = now.replace(tzinfo=timezone.utc).astimezone(KYIV)
    return local.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc).replace(tzinfo=None)


def to_sec(dt, day0):
    """Секунди від початку доби `day0` (обидва naive UTC); порожнє → `None`. Може бути від'ємним (учора)."""
    if not dt:
        return None
    return int(round((dt - day0).total_seconds()))


def waste_weighted(rows):
    """Середньозважений відхід, %: `rows` — `(відхід %, листів)`; рядки без відходу (`None`) чи листів не рахуються.

    Нічого рахувати → `None` (на плитці «—»), а не 0: відсутність даних не дорівнює нульовим відходам.
    """
    num = den = 0.0
    for waste, sheets in rows:
        if waste is None or not sheets or sheets <= 0:
            continue
        num += float(waste) * sheets
        den += sheets
    return round(num / den, 1) if den else None
