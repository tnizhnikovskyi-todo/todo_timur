"""R-10…R-16: розрізи «Ділянки», «Обладнання», «Замовлення», «Продукти», «Зміни», «До бази», деталізація."""

from collections import defaultdict
from datetime import timedelta

from odoo import _
from odoo.exceptions import UserError

from odoo.addons.td_energy.tools import dates
from odoo.addons.td_energy_resources.tools import shifts

from . import periods
from .fmt import fmt_int, hhmm, r_int, round_half_up, spec_text, spec_value

OTHER = "OTHER"
NONE_KEY = "NONE"
HEAD = {
    "area": ("Ділянки", "Ділянка", "кВт·год/м²"),
    "eq": ("Обладнання", "Обладнання", "кВт·год/мотогод"),
    "mo": ("Замовлення", "Замовлення", "кВт·год/шт"),
    "prod": ("Продукти", "Продукт", "кВт·год/од."),
    "shift": ("Зміни", "Зміна", "кВт·год/м²"),
}
UNIT_NAMES = {"units", "unit(s)", "unit", "одиниці", "од.", "шт", "шт."}
AREA_SQL = """
SELECT a.code, SUM(d.qty), SUM(d.cost) FROM td_energy_daily d LEFT JOIN td_energy_area a ON a.id = d.area_id
 WHERE d.scope = 'node' AND d.day BETWEEN %s AND %s GROUP BY a.code
"""
DRIVER_SUM_SQL = """
SELECT d.code, SUM(v.value) FROM td_energy_driver_value v JOIN td_energy_driver d ON d.id = v.driver_id
 WHERE v.day BETWEEN %s AND %s GROUP BY d.code
"""
AREA_META_SQL = """
SELECT a.code, a.name, a.sequence, d.code FROM td_energy_area a LEFT JOIN td_energy_driver d ON d.id = a.spec_driver_id
 WHERE a.active
"""
EQ_SQL = """
SELECT n.code, n.name, SUM(d.qty), SUM(d.cost), SUM(d.minutes)
  FROM td_energy_daily d JOIN td_energy_node n ON n.id = d.node_id
 WHERE d.scope = 'node' AND d.day BETWEEN %s AND %s GROUP BY n.id
"""
ALLOC_SQL = """
SELECT a.production_id, SUM(a.kwh), SUM(a.cost) FROM td_energy_alloc a
 WHERE a.day BETWEEN %s AND %s AND a.production_id IS NOT NULL GROUP BY a.production_id
"""
MO_SQL = """
SELECT mp.id, mp.name, mp.product_id, mp.product_qty, mp.product_uom_id, COALESCE(pr.qty, 0)
  FROM mrp_production mp
  LEFT JOIN (SELECT sm.production_id, SUM(sm.quantity) AS qty FROM stock_move sm
               JOIN mrp_production p2 ON p2.id = sm.production_id
              WHERE sm.production_id = ANY(%(ids)s) AND sm.state != 'cancel' AND sm.picked
                AND sm.product_id = p2.product_id GROUP BY sm.production_id) pr ON pr.production_id = mp.id
 WHERE mp.id = ANY(%(ids)s)
"""
SHIFT_SQL = """
SELECT COALESCE(SUM(shift1_qty), 0), COALESCE(SUM(shift2_qty), 0), COALESCE(SUM(off_qty), 0),
       COALESCE(SUM(cost_s1), 0), COALESCE(SUM(cost_s2), 0), COALESCE(SUM(cost_off), 0),
       COALESCE(SUM(plate_s1), 0), COALESCE(SUM(plate_s2), 0), COALESCE(SUM(plate_off), 0)
  FROM td_energy_daily WHERE scope = 'plant' AND day BETWEEN %s AND %s
"""


# --- загальне ---------------------------------------------------------------------------------------------
def _div(a, b):
    return a / b if b else None


def _delta(now, base):
    """R-15: `(now/base − 1)·100`, ціле; немає даних — `None`."""
    if now is None or not base:
        return None
    return int(round_half_up((now / base - 1) * 100))


def _row(key, name, kwh, cost, spec=None, text=None, delta=None):
    return {
        "key": key, "name": name, "kwh": kwh, "cost_uah": cost, "spec_raw": spec, "text": text, "delta_pct": delta,
    }  # fmt: skip


def _finish(rows):
    """Частки, смуги, округлення: R-10. `rows` — `_row` у потрібному порядку."""
    total = sum(r["kwh"] for r in rows)
    peak = max((r["kwh"] for r in rows), default=0.0)
    out = []
    for r in rows:
        spec = r["spec_raw"]
        out.append(
            {
                "key": r["key"], "name": r["name"], "kwh": r_int(r["kwh"]), "cost_uah": r_int(r["cost_uah"]),
                "share_pct": int(round_half_up(r["kwh"] / total * 100)) if total > 0 else 0,
                "bar": round(r["kwh"] / peak, 3) if peak > 0 else 0.0,
                "spec": spec_value(spec), "spec_text": r["text"] or spec_text(spec), "delta_pct": r["delta_pct"],
            }
        )  # fmt: skip
    return out


def _limit(rows, limit):
    """Верхні `limit` рядків за `kwh` + підсумок «Інші» без питомого (R-10)."""
    rows = sorted(rows, key=lambda r: -r["kwh"])
    if limit <= 0 or len(rows) <= limit:
        return rows
    rest = rows[limit:]
    other = _row(OTHER, "Інші", sum(r["kwh"] for r in rest), sum(r["cost_uah"] for r in rest))
    return rows[:limit] + [other]


# --- «Ділянки» --------------------------------------------------------------------------------------------
def _area_data(cr, first, last):
    """`({code: (kwh, cost)}, {driver_code: Σ значень})` за вікном."""
    cr.execute(AREA_SQL, (first, last))
    kwh = {code or NONE_KEY: (float(q or 0.0), float(c or 0.0)) for code, q, c in cr.fetchall()}
    cr.execute(DRIVER_SUM_SQL, (first, last))
    return kwh, {code: float(v or 0.0) for code, v in cr.fetchall()}


def _area_cut(ctx):
    cr = ctx.cr
    now, drivers = _area_data(cr, ctx.f, ctx.t)
    window = ctx.baseline_window("el")
    base_kwh, base_drivers = _area_data(cr, *window) if window else ({}, {})
    cr.execute(AREA_META_SQL)
    meta = {code: (name, seq, driver) for code, name, seq, driver in cr.fetchall()}
    rows = []
    for code, (kwh, cost) in now.items():
        if code == NONE_KEY:
            rows.append(_row(NONE_KEY, "Без ділянки", kwh, cost))
            continue
        if code not in meta:
            continue
        name, _seq, driver = meta[code]
        spec = _div(kwh, drivers.get(driver)) if driver else None
        base = None
        if driver and code in base_kwh:
            base = _div(base_kwh[code][0], base_drivers.get(driver))
        rows.append(_row(code, name, kwh, cost, spec=spec, delta=_delta(spec, base)))
    return _limit(rows, 0)


# --- «Обладнання» -----------------------------------------------------------------------------------------
def _eq_data(cr, first, last):
    cr.execute(EQ_SQL, (first, last))
    return {
        code: (name, float(q or 0.0), float(c or 0.0), float(m or 0.0) / 60.0) for code, name, q, c, m in cr.fetchall()
    }


def _eq_cut(ctx, top):
    now = _eq_data(ctx.cr, ctx.f, ctx.t)
    window = ctx.baseline_window("el")
    base = _eq_data(ctx.cr, *window) if window else {}
    rows = []
    for code, (name, kwh, cost, hours) in now.items():
        spec = kwh / hours if hours >= 1 else None
        b = base.get(code)
        base_spec = b[1] / b[3] if b and b[3] >= 1 else None
        rows.append(_row(code, "%s · %s" % (code, name), kwh, cost, spec=spec, delta=_delta(spec, base_spec)))
    return _limit(rows, top)


# --- «Замовлення» й «Продукти» ----------------------------------------------------------------------------
def _alloc_data(env, first, last):
    """`{mo_id: {kwh, cost, name, product_id, qty, uom_id}}` за вікном (R-13)."""
    cr = env.cr
    cr.execute(ALLOC_SQL, (first, last))
    sums = {mo: (float(k or 0.0), float(c or 0.0)) for mo, k, c in cr.fetchall()}
    if not sums:
        return {}
    cr.execute(MO_SQL, {"ids": list(sums)})
    out = {}
    for mo_id, name, product_id, product_qty, uom_id, produced in cr.fetchall():
        kwh, cost = sums[mo_id]
        qty = float(produced) if produced and produced > 0 else float(product_qty or 0.0)
        out[mo_id] = {"kwh": kwh, "cost": cost, "name": name, "product_id": product_id, "qty": qty, "uom_id": uom_id}
    return out


def _product_spec(data):
    """`{product_id: Σ kwh / Σ qty}` по **різних** МО продукту (A-14)."""
    kwh, qty = defaultdict(float), defaultdict(float)
    for mo in data.values():
        kwh[mo["product_id"]] += mo["kwh"]
        qty[mo["product_id"]] += mo["qty"]
    return {pid: _div(kwh[pid], qty[pid]) for pid in kwh}


def _unit_label(env, uom_ids, default):
    """Підпис одиниці: єдина ЕІ всіх рядків (крім «штук») або `default`."""
    uoms = env["uom.uom"].browse(sorted(set(uom_ids)))
    if len(uoms) == 1:
        name = (uoms.name or "").strip()
        if name and name.lower() not in UNIT_NAMES:
            return name
    return default


def _mo_cut(ctx, top):
    env = ctx.env.sudo()
    now = _alloc_data(env, ctx.f, ctx.t)
    window = ctx.baseline_window("el")
    base = _product_spec(_alloc_data(env, *window)) if window else {}
    chosen = sorted(now.items(), key=lambda kv: -kv[1]["kwh"])
    head, tail = (chosen[:top], chosen[top:]) if top > 0 else (chosen, [])
    products = env["product.product"].browse(sorted({mo["product_id"] for _id, mo in head}))
    names = {p.id: p.name for p in products}
    rows = []
    for _mo_id, mo in head:
        spec = _div(mo["kwh"], mo["qty"])
        title = "%s · %s × %g" % (mo["name"], names.get(mo["product_id"], ""), mo["qty"])
        rows.append(
            _row(mo["name"], title, mo["kwh"], mo["cost"], spec=spec, delta=_delta(spec, base.get(mo["product_id"])))
        )
    if tail:
        rows.append(_row(OTHER, "Інші", sum(mo["kwh"] for _id, mo in tail), sum(mo["cost"] for _id, mo in tail)))
    unit = _unit_label(env, [mo["uom_id"] for _id, mo in now.items()], "шт")
    return rows, "кВт·год/%s" % unit


def _prod_cut(ctx):
    env = ctx.env.sudo()
    now = _alloc_data(env, ctx.f, ctx.t)
    window = ctx.baseline_window("el")
    base = _product_spec(_alloc_data(env, *window)) if window else {}
    kwh, cost, qty, uoms = defaultdict(float), defaultdict(float), defaultdict(float), []
    for mo in now.values():
        kwh[mo["product_id"]] += mo["kwh"]
        cost[mo["product_id"]] += mo["cost"]
        qty[mo["product_id"]] += mo["qty"]
        uoms.append(mo["uom_id"])
    names = {p.id: p.display_name for p in env["product.product"].browse(sorted(kwh))}
    rows = []
    for pid in kwh:
        spec = _div(kwh[pid], qty[pid])
        rows.append(
            _row(str(pid), names.get(pid, str(pid)), kwh[pid], cost[pid], spec=spec, delta=_delta(spec, base.get(pid)))
        )
    return _limit(rows, 0), "кВт·год/%s" % _unit_label(env, uoms, "од.")


# --- «Зміни» ----------------------------------------------------------------------------------------------
def _shift_labels(calendar):
    """Назви й межі першої та другої зміни: з першого дня тижня, що має зміни (R-14)."""
    by_day = defaultdict(list)
    for wd, name, h_from, h_to in calendar.windows:
        by_day[wd].append((h_from, h_to, name))
    for wd in sorted(by_day):
        wins = sorted(by_day[wd])
        return [(name, h_from, h_to) for h_from, h_to, name in wins[:2]]
    return []


def _off_hours(calendar, first, last):
    """Годин вікна поза змінами за календарем (з урахуванням довжини доби)."""
    total, day = 0.0, first
    while day <= last:
        d0, d1 = dates.local_day_bounds(day)
        hours = (d1 - d0).total_seconds() / 3600.0
        busy = sum((end - start).total_seconds() / 3600.0 for _name, start, end in calendar.windows_for(day))
        total += max(0.0, hours - busy)
        day += timedelta(days=1)
    return total


def _shift_data(cr, calendar, first, last):
    cr.execute(SHIFT_SQL, (first, last))
    q1, q2, qo, c1, c2, co, p1, p2, _po = (float(x) for x in cr.fetchone())
    hours = _off_hours(calendar, first, last)
    return {"q": (q1, q2, qo), "c": (c1, c2, co), "p": (p1, p2), "kw": _div(qo, hours)}


def _shift_cut(ctx):
    calendar = shifts.load_windows(ctx.env)
    now = _shift_data(ctx.cr, calendar, ctx.f, ctx.t)
    window = ctx.baseline_window("el")
    base = _shift_data(ctx.cr, calendar, *window) if window else None
    rows = []
    for i, (name, h_from, h_to) in enumerate(_shift_labels(calendar)):
        spec = _div(now["q"][i], now["p"][i])
        base_spec = _div(base["q"][i], base["p"][i]) if base else None
        title = "%s · %s–%s" % (name, hhmm(h_from), hhmm(h_to))
        rows.append(
            _row("shift%d" % (i + 1), title, now["q"][i], now["c"][i], spec=spec, delta=_delta(spec, base_spec))
        )
    kw = now["kw"]
    text = "база %s кВт" % fmt_int(kw) if kw is not None else "—"
    delta = _delta(kw, base["kw"]) if base else None
    rows.append(_row("off", "Ночі й вихідні · без виробництва", now["q"][2], now["c"][2], text=text, delta=delta))
    return rows


# --- вхід -------------------------------------------------------------------------------------------------
def build_cut(ctx, dim, top_equipment=15, top_mo=20):
    """`cut` (R-10…R-15): `{dim, dim_name, col_name, col_spec, rows}`; рядки відсортовані за `kwh` (крім «Інші»)."""
    dim_name, col_name, col_spec = HEAD[dim]
    if dim == "area":
        raw = _area_cut(ctx)
    elif dim == "eq":
        raw = _eq_cut(ctx, top_equipment)
    elif dim == "mo":
        raw, col_spec = _mo_cut(ctx, top_mo)
    elif dim == "prod":
        raw, col_spec = _prod_cut(ctx)
    else:
        raw = _shift_cut(ctx)
    if dim != "shift":
        head = sorted([r for r in raw if r["key"] != OTHER], key=lambda r: -r["kwh"])
        raw = head + [r for r in raw if r["key"] == OTHER]
    return {"dim": dim, "dim_name": dim_name, "col_name": col_name, "col_spec": col_spec, "rows": _finish(raw)}


# --- R-16: деталізація ------------------------------------------------------------------------------------
def open_cut(env, dim, key, period, today):
    """`ir.actions.act_window` зі списком/зведеною/графіком і доменом за вікном `[date_from, date_to]` (R-16)."""
    if dim not in HEAD:
        raise UserError(_("Невідомий розріз: %s.", dim))
    if key in (None, False, "", OTHER):
        raise UserError(_("Невідомий ключ: %s.", key or OTHER))
    first, last = periods.window(period, today)
    win = [("day", ">=", first), ("day", "<=", last)]
    name = "%s: %s" % (HEAD[dim][0], key)
    if dim in ("area", "eq", "shift"):
        model, ctx = "td.energy.interval", {"pivot_measures": ["kwh"], "pivot_row_groupby": ["day"]}
        if dim == "area":
            if key == NONE_KEY:
                domain = [("role", "=", "consumer"), ("node_id.area_id", "=", False)]
                exists = True
            else:
                domain = [("role", "=", "consumer"), ("node_id.area_id.code", "=", key)]
                exists = env["td.energy.area"].sudo().search_count([("code", "=", key)])
            ctx["pivot_row_groupby"] = ["node_id"]
        elif dim == "eq":
            domain = [("role", "=", "consumer"), ("node_id.code", "=", key)]
            exists = env["td.energy.node"].sudo().search_count([("code", "=", key), ("kind", "=", "consumer")])
        else:
            domain = [("role", "=", "feeder")]
            exists = key in ("shift1", "shift2", "off")
            ctx["pivot_row_groupby"] = ["hour_local"]
    elif dim == "mo":
        model, ctx = "td.energy.alloc", {"pivot_measures": ["kwh"], "pivot_row_groupby": ["workorder_id"]}
        domain = [("production_id.name", "=", key)]
        exists = env["mrp.production"].sudo().search_count([("name", "=", key)])
    else:
        model, ctx = "td.energy.alloc", {"pivot_measures": ["kwh"], "pivot_row_groupby": ["production_id"]}
        exists = str(key).isdigit() and env["product.product"].sudo().search_count([("id", "=", int(key))])
        domain = [("product_id", "=", int(key) if str(key).isdigit() else 0)]
    if not exists:
        raise UserError(_("Невідомий ключ: %s.", key))
    return {
        "type": "ir.actions.act_window", "name": name, "res_model": model,
        "view_mode": "list,pivot,graph", "views": [(False, "list"), (False, "pivot"), (False, "graph")],
        "domain": domain + win, "context": ctx, "target": "current",
    }  # fmt: skip
