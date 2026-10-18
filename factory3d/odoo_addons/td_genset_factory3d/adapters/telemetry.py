"""Адаптер td_telemetry: TEL-01…TEL-04 (SPEC §2.0.2, §2.0.3). Єдине місце імен telemetry у мості."""

from odoo import fields

SOURCE_CODE = "GENSET-RELAY"
SOURCE_TYPE = "td_genset"
SOURCE_MODULE = "genset"

# Додаток A: (leaf, назва, одиниця, kind, stale при не-fresh). 4 сигнали зі stale=False публікуються завжди (R-12).
SIGNALS = [
    ("state", "стан (код 0–10)", "", "gauge", False),
    ("mode", "режим (0 стоп, 1 ручний, 2 авто, 3 тест)", "", "gauge", True),
    ("breaker", "вимикач (0 жодного, 1 мережа, 2 генератор)", "", "gauge", True),
    ("mains_ok", "мережа в нормі", "", "gauge", True),
    ("alarm_level", "рівень тривоги (0/1/2)", "", "gauge", True),
    ("alarm_count", "кількість активних тривог", "", "gauge", True),
    ("online", "зв'язок з контролером", "", "gauge", False),
    ("p_kw", "активна потужність", "кВт", "gauge", True),
    ("load_pct", "навантаження від PRP", "%", "gauge", True),
    ("u_v", "лінійна напруга", "В", "gauge", True),
    ("f_hz", "частота", "Гц", "gauge", True),
    ("i_a", "струм (найбільша фаза)", "А", "gauge", True),
    ("pf", "коефіцієнт потужності", "", "gauge", True),
    ("kwh", "вироблена енергія", "кВт·год", "counter", True),
    ("fuel_pct", "рівень палива", "%", "gauge", True),
    ("fuel_l", "паливо в баку", "л", "gauge", True),
    ("fuel_lph", "витрата палива", "л/год", "gauge", False),
    ("autonomy_h", "автономність", "год", "gauge", False),
    ("hours", "мотогодини", "год", "counter", True),
    ("starts", "кількість пусків", "шт", "counter", True),
    ("service_h_left", "до ТО", "год", "gauge", True),
    ("coolant_c", "температура ОЖ", "°C", "gauge", True),
    ("oil_bar", "тиск оливи", "бар", "gauge", True),
    ("batt_v", "напруга АКБ", "В", "gauge", True),
    ("charger_v", "напруга зарядного", "В", "gauge", True),
    ("rpm", "оберти", "об/хв", "gauge", True),
]
LEAFS = [row[0] for row in SIGNALS]
ALWAYS_LEAFS = [row[0] for row in SIGNALS if not row[4]]
STALE_LEAFS = [row[0] for row in SIGNALS if row[4]]


def prefix(td_code):
    return "infra/genset/%s/" % td_code


def signal_period_s(env):
    """T-6: period_s = max(60, offline_min·20)."""
    raw = env["ir.config_parameter"].sudo().get_param("td.genset.offline_min", "5")
    try:
        offline_min = int(raw)
    except (TypeError, ValueError):
        offline_min = 5
    return max(60, offline_min * 20)


def ensure_source(env, link):
    """TEL-01: джерело GENSET-RELAY (локальний тип td_genset, без колектора)."""
    Source = env["td.source"].sudo()
    source = Source.search([("code", "=", SOURCE_CODE)], limit=1)
    if not source:
        source = Source.create(
            {
                "code": SOURCE_CODE,
                "name": "Ретранслятор SmartGen (td_genset)",
                "type": SOURCE_TYPE,
                "module": SOURCE_MODULE,
                "equipment_id": link.equipment_id.id,
                "params": {},
                "read_enabled": True,
                "period_s_default": 60,
            }
        )
    if link and link.source_id != source:
        link.sudo().source_id = source
    return source


def ensure_signals(env, link):
    """TEL-02: 26 сигналів Додатка A; повертає {code: signal}. Наявні не змінює."""
    Signal = env["td.signal"].sudo()
    td_code = link.equipment_id.td_code
    pfx = prefix(td_code)
    codes = [pfx + leaf for leaf in LEAFS]
    existing = {s.code: s for s in Signal.with_context(active_test=False).search([("code", "in", codes)])}
    period = signal_period_s(env)
    source = link.source_id or ensure_source(env, link)
    for leaf, title, unit, kind, _stale in SIGNALS:
        code = pfx + leaf
        if code in existing:
            continue
        vals = {
            "code": code,
            "name": "Генератор %s: %s" % (td_code, title),
            "equipment_id": link.equipment_id.id,
            "source_id": source.id,
            "module": SOURCE_MODULE,
            "unit": unit or False,
            "kind": kind,
            "period_s": period,
            "store_period_s": 0,
            "scale": 1.0,
            "viewer_visible": True,
            "create_request": False,
            "alarm_states": [],
            "address": {"leaf": leaf},
        }
        if leaf == "alarm_level":
            vals.update(alarm_high_on=True, alarm_high=0.5)
        existing[code] = Signal.create(vals)
    return existing


def ingest(env, batch):
    """TEL-03: пакет [{code, ts, value[, q]}] через CT-10 `_f3d_ingest(src="module")`."""
    readings = [
        {
            "code": item["code"],
            "ts": item["ts"],
            "value": item["value"],
            "q": item.get("q", "good") if isinstance(item.get("q", "good"), str) else ("good" if item["q"] else "bad"),
        }
        for item in batch
    ]
    res = env["td.signal"].sudo()._f3d_ingest(readings, src="module")
    return {"accepted": res["accepted"], "stored": res["stored"], "skipped": res["accepted"] - res["stored"]}


def mark_stale(env, codes, reason):
    """T-3: сигнали без свіжих даних -> stale (ідемпотентно, чаттер раз на перехід)."""
    env["td.signal"].sudo().search([("code", "in", list(codes))])._mark_stale(reason)


def read_values(env, codes):
    """TEL-04: {code: (value, ts, status)}; відсутній код — відсутній ключ."""
    rows = (
        env["td.signal"].sudo().search_read([("code", "in", list(codes))], ["code", "last_value", "last_ts", "status"])
    )
    return {r["code"]: (r["last_value"], r["last_ts"] or None, r["status"]) for r in rows}


def now():
    return fields.Datetime.now()


def signal_periods(env, codes):
    """period_s сигналів {code: period_s} (для перевірки свіжості ATS, R-05)."""
    rows = env["td.signal"].sudo().search_read([("code", "in", list(codes))], ["code", "period_s"])
    return {r["code"]: r["period_s"] for r in rows}
