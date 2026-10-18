"""Адаптер td_genset: ADP-01…ADP-11 (SPEC §2.0.1; ADP-11 — W1). Єдине місце імен td_genset.

Імена звірені з моделями td_genset 19 (``td.genset``, ``td.genset.reading``, ``td.genset.event``,
``td.genset.alarm``, ``td.genset.schedule``, ``td.genset.command``); таблиця — docs/modules/td_genset/ADAPTER_MAP.md.
Усі функції — чисте читання (крім ADP-09). Константа-кортеж означає «розрахунок у snapshot()».
"""

from datetime import timedelta
import re

from odoo import fields

# ADP-01
GENSET_MODEL = "td.genset"
READING_MODEL = "td.genset.reading"
EVENT_MODEL = "td.genset.event"

# ADP-03: поля знімка на td.genset (ключ знімка -> поле або кортеж полів для розрахунку)
FIELD_TS = "last_reading_at"  # Datetime UTC часу останнього знімка (related last_reading_id.ts)
FIELD_ONLINE = "link_state"  # 'online' = модуль на зв'язку і знімки свіжі (link_lost_min td_genset)
FIELD_STATE_RAW = "genset_status"  # selection '0'…'15'
FIELD_MODE_RAW = "controller_mode"  # auto/manual/stop/test/unknown
FIELD_MAINS_OK = "mains_ok"
FIELD_BREAKER_RAW = "feed_source"  # mains/genset/none
FIELD_P_KW = "active_power"  # сумарна активна, kW (знакова)
FIELD_U_V = ("gen_uab", "gen_ubc", "gen_uca")  # середнє лінійних, V
FIELD_F_HZ = "gen_freq"
FIELD_I_A = ("current_a", "current_b", "current_c")  # max фаз, A
FIELD_PF = "power_factor"
FIELD_KWH = "energy_kwh"
FIELD_FUEL_PCT = "fuel_level"
FIELD_FUEL_L = "fuel_liters"
FIELD_HOURS = "run_hours_total"
FIELD_STARTS = "start_count"
FIELD_COOLANT_C = "water_temp"
FIELD_OIL_BAR = "oil_pressure"  # kPa у td_genset -> /100 у snapshot()
FIELD_BATT_V = "battery_v"
FIELD_CHARGER_V = "dplus_v"
FIELD_RPM = "speed"
FIELD_MAINS_U_V = ("mains_uab", "mains_ubc", "mains_uca")  # середнє лінійних, V
FIELD_MAINS_F_HZ = "mains_freq"
FIELD_ALARMS_MODEL = "td.genset.alarm"  # genset_id, code, name, level (crit/warn/info), state, date_raised
FIELD_EQUIPMENT = "equipment_id"

# Рівні td.genset.alarm -> severity ADP-03 (info не береться)
ALARM_SEVERITY = {"crit": "shutdown", "warn": "warning"}

# ADP-05
FIELD_SERVICE_INTERVAL_H = "maint_interval_hours"
FIELD_NEXT_SERVICE_H = "maint_next_hours"  # мотогодини наступного ТО (computed)
SERVICE_REQUEST_MODEL = "maintenance.request"
FIELD_LAST_SERVICE_H = "td_run_hours_at_close"  # на maintenance.request (остання закрита заявка)
FIELD_LAST_SERVICE_DATE = "close_date"  # на maintenance.request
FIELD_SERVICE_DUE = "maint_state"  # ok / due / overdue; due=True для due та overdue
# Q-17: td_genset сам створює превентивні заявки ТО (td.genset._create_maintenance_request)
SERVICE_REQUESTS_BY_TD = True

# ADP-06 / ADP-07
SCHEDULE_MODEL = "td.genset.schedule"  # dayofweek '0'..'6', time_start/time_end (float, Київ), enabled
FIELD_SCHEDULE_LINES = "schedule_line_ids"
FIELD_TIMER_VS_SCHEDULE = "next_event_text"  # текст «Наступна подія» (розклад/таймер/тест)
LAST_TEST_MODEL = "td.genset.command"  # source='test', command in ('test','start'), state done/done_late

# ADP-11 (W1): текст найближчої події генератора (розклад/таймер/тест)
FIELD_NEXT_EVENT = "next_event_text"  # ЗВІРИТИ: computed Char td.genset (genset_scheduler.py), test_adapter_contract

# ADP-09: сталої витрати в td_genset немає (є лише обчислювані fuel_rate_lph_7d/30d) -> запису немає
FIELD_FUEL_RATE_LPH = None

# ADP-10: сирі значення td_genset (нижній регістр) -> коди R-03.
# state: td_genset не має станів «мережа втрачена, затримка» (код 2) — міст виводить його сам
# з mains_ok=False при state 1. «працює» (6) -> 7 за навантаженням вирішує міст (R-03).
STATE_MAP: dict = {
    "0": 1,  # Очікування
    "1": 3,  # Передпусковий підігрів -> пуск
    "2": 3,  # Подача палива -> пуск
    "3": 3,  # Прокрутка стартером
    "4": 3,  # Пауза між спробами пуску
    "5": 4,  # Безпечний пуск -> захисна затримка
    "6": 5,  # Холостий хід -> прогрів
    "7": 5,  # Прогрів
    "8": 6,  # Очікування навантаження -> працює без навантаження
    "9": 6,  # Нормальна робота (7, якщо breaker == 2 або p_kw ≥ 0,05·kw_prp — у мосту)
    "10": 8,  # Охолодження
    "11": 9,  # Холостий хід перед зупинкою
    "12": 9,  # Зупинка (ETS)
    "13": 9,  # Очікування зупинки
    "14": 10,  # Невдала зупинка -> аварійна
    "15": 1,  # Після зупинки -> очікування
}
MODE_MAP: dict = {"stop": 0, "manual": 1, "auto": 2, "test": 3}  # unknown -> None -> 0
BREAKER_MAP: dict = {"none": 0, "mains": 1, "genset": 2}

_CODE_RE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
# td.genset.event.event_type -> (code, severity)
_EVENT_SEVERITY = {
    "run": "info",
    "outage": "warning",
    "refuel": "info",
    "drain": "warning",
    "external_control": "command",
    "alarm": "warning",
    "link": "comm",
    "gap": "comm",
    "maintenance": "service",
}
_DAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"]


def _avg(gen, names):
    values = [gen[n] for n in names]
    return round(sum(values) / len(values), 1)


def _hhmm(value):
    minutes = int(round((value or 0.0) * 60))
    return "%02d:%02d" % divmod(minutes, 60)


def generators(env):
    """ADP-02: активні генератори, порядок за id."""
    return env[GENSET_MODEL].search([("active", "=", True)], order="id")


def snapshot(gen) -> dict:
    """ADP-03: останній знімок показань (немає знімка -> усі значення None, alarms [])."""
    gen = gen.sudo()
    keys = (
        "ts online state_raw mode_raw mains_ok breaker_raw p_kw u_v f_hz i_a pf kwh fuel_pct fuel_l hours "
        "starts coolant_c oil_bar batt_v charger_v rpm mains_u_v mains_f_hz"
    ).split()
    snap = dict.fromkeys(keys)
    snap["alarms"] = []
    if not gen.last_reading_id:
        return snap
    snap.update(
        ts=gen[FIELD_TS],
        online=gen[FIELD_ONLINE] == "online",
        state_raw=gen[FIELD_STATE_RAW] or None,
        mode_raw=gen[FIELD_MODE_RAW] or None,
        mains_ok=bool(gen[FIELD_MAINS_OK]),
        breaker_raw=gen[FIELD_BREAKER_RAW] or None,
        p_kw=gen[FIELD_P_KW],
        u_v=_avg(gen, FIELD_U_V),
        f_hz=gen[FIELD_F_HZ],
        i_a=max(gen[n] for n in FIELD_I_A),
        pf=gen[FIELD_PF],
        kwh=gen[FIELD_KWH],
        fuel_pct=gen[FIELD_FUEL_PCT],
        fuel_l=gen[FIELD_FUEL_L],
        hours=gen[FIELD_HOURS],
        starts=gen[FIELD_STARTS],
        coolant_c=gen[FIELD_COOLANT_C],
        oil_bar=round(gen[FIELD_OIL_BAR] / 100.0, 2),
        batt_v=gen[FIELD_BATT_V],
        charger_v=gen[FIELD_CHARGER_V],
        rpm=gen[FIELD_RPM],
        mains_u_v=_avg(gen, FIELD_MAINS_U_V),
        mains_f_hz=gen[FIELD_MAINS_F_HZ],
    )
    alarms = gen.env[FIELD_ALARMS_MODEL].search(
        [("genset_id", "=", gen.id), ("state", "!=", "cleared"), ("level", "in", list(ALARM_SEVERITY))],
        order="date_raised, id",
    )
    snap["alarms"] = [
        {
            "code": a.code or "",
            "name": a.name or "",
            "severity": ALARM_SEVERITY[a.level],
            "since": a.date_raised,
        }
        for a in alarms
    ]
    return snap


def events_since(gen, since=None, limit: int = 200) -> list:
    """ADP-04: події журналу td_genset новіші за since (за замовчуванням — останні 24 год)."""
    if since is None:
        since = fields.Datetime.now() - timedelta(hours=24)
    events = (
        gen.sudo()
        .env[EVENT_MODEL]
        .search([("genset_id", "=", gen.id), ("date_start", ">", since)], order="date_start, id", limit=limit)
    )
    result = []
    for ev in events:
        severity = _EVENT_SEVERITY.get(ev.event_type, "info")
        if ev.event_type == "alarm" and ev.alarm_id:
            severity = ALARM_SEVERITY.get(ev.alarm_id.level, "info" if ev.alarm_id.level == "info" else "warning")
        code = ev.event_type or ""
        if ev.event_type == "alarm" and ev.alarm_id.code:
            code = ev.alarm_id.code
        result.append(
            {
                "id": ev.id,
                "ts": ev.date_start,
                "code": code if _CODE_RE.match(code) else "",
                "severity": severity,
                "name": ev.display_name or "",
                "value": None,
                "unit": None,
                "threshold": None,
                "text": ev.summary or ev.reason or "",
            }
        )
    return result


def service_info(gen) -> dict:
    """ADP-05: ТО за мотогодинами."""
    gen = gen.sudo()
    hours_now = gen[FIELD_HOURS]
    next_h = gen[FIELD_NEXT_SERVICE_H]
    last = gen._maint_last_done()
    return {
        "hours_now": hours_now,
        "interval_h": gen[FIELD_SERVICE_INTERVAL_H],
        "next_service_hours": next_h,
        "last_service_hours": last[FIELD_LAST_SERVICE_H] if last else None,
        "last_service_date": last[FIELD_LAST_SERVICE_DATE] if last else None,
        "due": gen[FIELD_SERVICE_DUE] in ("due", "overdue"),
        "hours_left": round(next_h - hours_now, 2),
    }


def schedule_info(gen) -> dict:
    """ADP-06: розклад (вікна за днями, київський час)."""
    gen = gen.sudo()
    lines = gen[FIELD_SCHEDULE_LINES].filtered("enabled").sorted(lambda r: (r.dayofweek, r.time_start))
    groups: dict = {}
    for line in lines:
        groups.setdefault((_hhmm(line.time_start), _hhmm(line.time_end)), []).append(int(line.dayofweek))
    windows = []
    for (start, end), days in groups.items():
        days = sorted(days)
        if len(days) > 1 and days == list(range(days[0], days[-1] + 1)):
            label = "%s–%s" % (_DAYS[days[0]], _DAYS[days[-1]])
        else:
            label = ", ".join(_DAYS[d] for d in days)
        windows.append("%s %s–%s" % (label, start, end))
    return {
        "enabled": bool(lines),
        "windows": windows,
        "timer_vs_schedule": gen[FIELD_TIMER_VS_SCHEDULE] or None,
    }


def last_test(gen):
    """ADP-07: останній тестовий пуск (з журналу команд source='test') або None."""
    gen = gen.sudo()
    cmd = gen.env[LAST_TEST_MODEL].search(
        [
            ("genset_id", "=", gen.id),
            ("source", "=", "test"),
            ("command", "in", ["test", "start"]),
            ("state", "in", ["done", "done_late"]),
        ],
        order="id desc",
        limit=1,
    )
    if not cmd:
        return None
    ts = cmd.done_at or cmd.confirmed_at or cmd.sent_at
    run = (
        gen.env[EVENT_MODEL].search(
            [("genset_id", "=", gen.id), ("event_type", "=", "run"), ("date_start", ">=", ts)],
            order="date_start, id",
            limit=1,
        )
        if ts
        else gen.env[EVENT_MODEL]
    )
    return {
        "ts": ts,
        "duration_min": round(run.duration * 60.0, 1) if run and not run.is_open else None,
        "result": "норма",
    }


def next_event(gen) -> str | None:
    """ADP-11: текст найближчої події генератора (розклад/таймер/тест) або None, якщо порожній."""
    return gen.sudo()[FIELD_NEXT_EVENT] or None


def open_action(gen) -> dict:
    """ADP-08: act_window на запис генератора td_genset."""
    return {
        "type": "ir.actions.act_window",
        "res_model": GENSET_MODEL,
        "res_id": gen.id,
        "view_mode": "form",
        "target": "current",
    }


def set_fuel_rate(gen, lph: float) -> bool:
    """ADP-09: у td_genset немає поля сталої витрати (лише обчислювані KPI) -> False без запису."""
    if not FIELD_FUEL_RATE_LPH or FIELD_FUEL_RATE_LPH not in gen._fields:
        return False
    gen.sudo().write({FIELD_FUEL_RATE_LPH: lph})
    return True
