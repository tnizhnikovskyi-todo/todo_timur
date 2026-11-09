#!/usr/bin/env python3
"""Детерміновані розрахунки SLA для support-desk. Лише stdlib, без мережі. Вихід — JSON.
Календар береться ЛИШЕ з договору й передається явно; значень за замовчуванням для робочих годин немає.

  due        --start "РРРР-ММ-ДД ГГ:ХХ" | ISO з зсувом ("2026-10-03T09:12:00+00:00", "...Z") --hours N | --amount N --unit hours|work-days|calendar-days
             (--calendar 24x7 | --work-days 1-5 --work-start 09:00 --work-end 18:00) [--holidays д1,д2] [--tz Europe/Kyiv]
  to-local   --start <дата> [--tz ..]   (лише приведення часу листа до поясу, без строку й календаря; працює до договору)
  breach     --due "РРРР-ММ-ДД ГГ:ХХ" --actual "РРРР-ММ-ДД ГГ:ХХ"|"" [--tz ..]   (порожньо -> «очікує Підтримку»)
  days-clean --golive РРРР-ММ-ДД [--last-critical РРРР-ММ-ДД] --today РРРР-ММ-ДД [--need 14]
Старт з зсувом UTC (поле date листа) приводиться до --tz (zoneinfo, за замовчуванням Europe/Kyiv); старт без зсуву
вважається вже локальним. Одиниці work-days / calendar-days: кінець того ж часу доби через N днів; work-days
пропускає неробочі дні й свята (потрібен календар з договору)."""
import argparse, json, sys
from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo

FMT = "%Y-%m-%d %H:%M"


def parse_days(s):
    a, _, b = s.partition("-")
    lo, hi = int(a), int(b or a)
    return set(range(lo, hi + 1))


def parse_dt(s, tz):
    """Локальний 'РРРР-ММ-ДД ГГ:ХХ' або ISO зі зсувом -> наївний локальний datetime у tz договору."""
    s = s.strip()
    try:
        return datetime.strptime(s, FMT)
    except ValueError:
        try:
            d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError:
            sys.exit(json.dumps({"error": f"нерозпізнаний формат дати: {s!r}; потрібен 'РРРР-ММ-ДД ГГ:ХХ' або ISO зі зсувом"}, ensure_ascii=False))
        if d.tzinfo is None:
            return d.replace(microsecond=0, second=0)
        return d.astimezone(ZoneInfo(tz)).replace(tzinfo=None, second=0, microsecond=0)


def due(a):
    start = parse_dt(a.start, a.tz)
    amount = a.amount if a.amount is not None else a.hours
    if amount is None:
        sys.exit(json.dumps({"error": "потрібен --hours або --amount"}))
    if a.unit == "calendar-days":
        return start + timedelta(days=amount)
    if a.unit == "work-days":
        if not a.work_days:
            sys.exit(json.dumps({"error": "для work-days потрібен --work-days з договору"}))
        days = parse_days(a.work_days)
        hol = {d.strip() for d in (a.holidays or "").split(",") if d.strip()}
        cur, left = start, int(amount)
        while left > 0:
            cur += timedelta(days=1)
            if cur.isoweekday() in days and cur.strftime("%Y-%m-%d") not in hol:
                left -= 1
        return cur
    a.hours = amount
    if a.calendar == "24x7":
        return start + timedelta(hours=a.hours)
    if not (a.work_days and a.work_start and a.work_end):
        sys.exit(json.dumps({"error": "потрібен календар з договору: --calendar 24x7 або --work-days/--work-start/--work-end"}))
    days = parse_days(a.work_days)
    hol = {d.strip() for d in (a.holidays or "").split(",") if d.strip()}
    ws = datetime.strptime(a.work_start, "%H:%M").time()
    we = datetime.strptime(a.work_end, "%H:%M").time()
    cur, left = start, timedelta(hours=a.hours)
    for _ in range(3650):
        if cur.isoweekday() in days and cur.strftime("%Y-%m-%d") not in hol:
            day_start = datetime.combine(cur.date(), ws)
            day_end = datetime.combine(cur.date(), we)
            cur = max(cur, day_start)
            if cur < day_end:
                avail = day_end - cur
                if left <= avail:
                    return cur + left
                left -= avail
        cur = datetime.combine(cur.date() + timedelta(days=1), datetime.min.time())
    sys.exit(json.dumps({"error": "календар не дав строку за 10 років"}))


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("due")
    d.add_argument("--start", required=True); d.add_argument("--hours", type=float); d.add_argument("--amount", type=float)
    d.add_argument("--unit", default="hours", choices=["hours", "work-days", "calendar-days"]); d.add_argument("--tz", default="Europe/Kyiv")
    d.add_argument("--calendar"); d.add_argument("--work-days"); d.add_argument("--work-start")
    d.add_argument("--work-end"); d.add_argument("--holidays")
    t = sub.add_parser("to-local")
    t.add_argument("--start", required=True); t.add_argument("--tz", default="Europe/Kyiv")
    b = sub.add_parser("breach")
    b.add_argument("--due", required=True); b.add_argument("--actual", default=""); b.add_argument("--tz", default="Europe/Kyiv")
    c = sub.add_parser("days-clean")
    c.add_argument("--golive", required=True); c.add_argument("--last-critical", default="")
    c.add_argument("--today", required=True); c.add_argument("--need", type=int, default=14)
    a = p.parse_args()
    if a.cmd == "to-local":
        print(json.dumps({"local": parse_dt(a.start, a.tz).strftime(FMT)}))
    elif a.cmd == "due":
        print(json.dumps({"due": due(a).strftime(FMT)}))
    elif a.cmd == "breach":
        if not a.actual.strip():
            print(json.dumps({"status": "очікує Підтримку"}))
        else:
            ok = parse_dt(a.actual, a.tz) <= parse_dt(a.due, a.tz)
            print(json.dumps({"status": "в межах" if ok else "прострочено"}))
    else:
        g = date.fromisoformat(a.golive)
        lc = date.fromisoformat(a.last_critical) if a.last_critical else None
        start = max(g, lc) if lc else g
        earliest = start + timedelta(days=a.need)
        today = date.fromisoformat(a.today)
        print(json.dumps({"start": start.isoformat(), "clean_days": max((today - start).days, 0),
                          "earliest_end": earliest.isoformat(), "enough": today >= earliest}))


if __name__ == "__main__":
    main()
