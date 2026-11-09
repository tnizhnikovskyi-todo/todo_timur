#!/usr/bin/env python3
"""Детерміновані розрахунки SLA для support-desk. Лише stdlib, без мережі. Вихід — JSON.
Календар береться ЛИШЕ з договору й передається явно; значень за замовчуванням для робочих годин немає.

  due        --start "РРРР-ММ-ДД ГГ:ХХ" --hours N (--calendar 24x7 | --work-days 1-5 --work-start 09:00 --work-end 18:00) [--holidays д1,д2]
  breach     --due "РРРР-ММ-ДД ГГ:ХХ" --actual "РРРР-ММ-ДД ГГ:ХХ"|""   (порожньо -> «очікує Підтримку»)
  days-clean --golive РРРР-ММ-ДД [--last-critical РРРР-ММ-ДД] --today РРРР-ММ-ДД [--need 14]
Час — локальний у часовому поясі договору (приведення робить викликач)."""
import argparse, json, sys
from datetime import datetime, timedelta, date

FMT = "%Y-%m-%d %H:%M"


def parse_days(s):
    a, _, b = s.partition("-")
    lo, hi = int(a), int(b or a)
    return set(range(lo, hi + 1))


def due(a):
    start = datetime.strptime(a.start, FMT)
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
    d.add_argument("--start", required=True); d.add_argument("--hours", type=float, required=True)
    d.add_argument("--calendar"); d.add_argument("--work-days"); d.add_argument("--work-start")
    d.add_argument("--work-end"); d.add_argument("--holidays")
    b = sub.add_parser("breach")
    b.add_argument("--due", required=True); b.add_argument("--actual", default="")
    c = sub.add_parser("days-clean")
    c.add_argument("--golive", required=True); c.add_argument("--last-critical", default="")
    c.add_argument("--today", required=True); c.add_argument("--need", type=int, default=14)
    a = p.parse_args()
    if a.cmd == "due":
        print(json.dumps({"due": due(a).strftime(FMT)}))
    elif a.cmd == "breach":
        if not a.actual.strip():
            print(json.dumps({"status": "очікує Підтримку"}))
        else:
            ok = datetime.strptime(a.actual, FMT) <= datetime.strptime(a.due, FMT)
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
