"""R-26: плановий час. Чисті функції над списками пар `(start, end)` (naive UTC) + `ppt_intervals` (потребує `env`)."""

from datetime import timezone


def _naive_utc(dt):
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def union(intervals):
    """Об'єднання: відсортований список без перекриттів і порожніх пар."""
    res = []
    for a, b in sorted(i for i in intervals if i[1] > i[0]):
        if res and a <= res[-1][1]:
            if b > res[-1][1]:
                res[-1] = (res[-1][0], b)
        else:
            res.append((a, b))
    return res


def clip(intervals, a, b):
    """Обрізати інтервали до `[a, b)`."""
    return [(max(s, a), min(e, b)) for s, e in union(intervals) if min(e, b) > max(s, a)]


def minus(a, b):
    """Різниця `a − b` (обидва — списки інтервалів)."""
    res = union(a)
    for bs, be in union(b):
        nxt = []
        for s, e in res:
            if be <= s or bs >= e:
                nxt.append((s, e))
                continue
            if bs > s:
                nxt.append((s, bs))
            if be < e:
                nxt.append((be, e))
        res = nxt
    return res


def total_min(intervals):
    """Сума тривалостей у хвилинах."""
    return sum((e - s).total_seconds() for s, e in union(intervals)) / 60.0


def ppt_intervals(env, wc, dt_from, dt_to):
    """Інтервали планового часу РЦ у `[dt_from, dt_to)` (naive UTC): календар РЦ, інакше календар компанії;
    відсутності ресурсу (`time_type='leave'`) стандарт віднімає, слоти завдань — ні."""
    if not dt_from or not dt_to or dt_to <= dt_from:
        return []
    calendar = wc.resource_calendar_id or wc.company_id.resource_calendar_id
    if not calendar:
        return []
    res = calendar._work_intervals_batch(
        dt_from.replace(tzinfo=timezone.utc), dt_to.replace(tzinfo=timezone.utc), resources=wc.resource_id
    )[wc.resource_id.id]
    return union((_naive_utc(s), _naive_utc(e)) for s, e, _meta in res)
