"""Детектор `react_section` — «Реактивна енергія на секції» (R-19, вкладка «Електрика»; W3-B).

Сигнатура (R-14): `detect(env, rule, now) -> list[dict]`. Вмикається лише за `tariff.tg_phi_limit > 0` і
`react_rate > 0` (Q-03). Секції `S1`, `S2`: години доби з `cos φ < cos_target` і надлишок реактивної енергії над
`tg_phi_limit × P` за добу (інтеграли `p_kw`, `q_kvar` після компенсації).
"""

from datetime import timedelta

from odoo.addons.td_energy.tools import dates

from .. import integrate
from ..build import rparam_float
from . import common

TITLE = "Реактивна енергія на секції"
NO_TARIFF = "Немає параметрів доплати в тарифі"
SECTIONS = (1, 2)
DAYS_MONTH = 30.0


def _open_request(env, node):
    """Відкрита заявка ТО по обладнанню вузла (`PFC-{s}`) або порожній набір."""
    Request = env["maintenance.request"].sudo()
    if not node.equipment_id:
        return Request
    return Request.search([("equipment_id", "=", node.equipment_id.id), ("stage_id.done", "=", False)], limit=1)


def _actions(env, section):
    node = env["td.energy.node"].sudo().search([("code", "=", "PFC-%d" % section)], limit=1)
    request = _open_request(env, node) if node else env["maintenance.request"]
    if request:
        return [
            {
                "code": "open_request", "label": "Відкрити заявку", "kind": "link", "class": None,
                "params": {"xmlid": "maintenance.hr_equipment_request_action", "res_id": request.id},
            }
        ]  # fmt: skip
    return [
        {
            "code": "ticket", "label": "Створити заявку", "kind": "ticket", "class": None,
            "params": {
                "node_code": "PFC-%d" % section, "title": "Компенсація PFC-%d: перевірка" % section,
                "description": "Секція %d: cos φ нижче цілі, компенсація не справляється. [OPP-{id}]" % section,
            },
        }
    ]  # fmt: skip


def detect(env, rule, now):
    params = common.rule_params(rule)
    tariff = env["td.energy.tariff"].sudo()._td_tariff_at(now)
    if not tariff or tariff.tg_phi_limit <= 0 or tariff.react_rate <= 0:
        raise common.DetectorNote(NO_TARIFF)
    win = common.Window(env, rule, now)
    gap = rparam_float(env, "gap_max_s")
    pad = timedelta(seconds=gap)
    out = []
    for section in SECTIONS:
        codes = {k: "energy/sections/S%d/%s" % (section, k) for k in ("cos_phi", "p_kw", "q_kvar")}
        ids = common.signal_ids(env, codes.values())
        if len(ids) < len(codes):
            continue
        series = common.readings(env, [ids[c] for c in codes.values()], win.lo - pad, win.hi + pad)
        cos_pts, p_pts, q_pts = (series[ids[codes[k]]] for k in ("cos_phi", "p_kw", "q_kvar"))
        low_hours, excess = [], []
        for day in win.days:
            d0, d1 = dates.local_day_bounds(day)
            below, covered = common.step_below(cos_pts, d0, d1, params["cos_target"], gap)
            p = integrate.flow_slot([p_pts], d0, d1, 1.0, gap, common.MIN_COVERAGE)
            q = integrate.flow_slot([q_pts], d0, d1, 1.0, gap, common.MIN_COVERAGE)
            if covered / ((d1 - d0).total_seconds() / 3600.0) < common.MIN_COVERAGE:
                continue
            if p["quality"] == "missing" or q["quality"] == "missing":
                continue
            low_hours.append(below)
            excess.append(max(0.0, q["qty"] - tariff.tg_phi_limit * p["qty"]))
        if len(excess) < common.MIN_DAYS or common.mean(low_hours) < params["min_hours_day"]:
            continue
        qty = common.mean(excess) * DAYS_MONTH
        saving = qty * tariff.react_rate
        cos_min = min((v for _t, v in cos_pts if win.lo <= _t < win.hi), default=None)
        text = "cos φ секції %d — %s. Компенсація PFC-%d не досягає цілі." % (
            section, common.fmt_dec(cos_min, 2) if cos_min is not None else "—", section,
        )  # fmt: skip
        evidence = {
            "section": section, "h_low_avg": round(common.mean(low_hours), 2),
            "excess_kvarh_day": round(common.mean(excess), 2), "tg_phi_limit": tariff.tg_phi_limit,
            "react_rate": tariff.react_rate, "days": len(excess), "cos_min": cos_min,
        }  # fmt: skip
        out.append(
            common.finding(
                "react_section:S%d" % section,
                TITLE,
                text,
                saving,
                qty,
                evidence,
                node_code="PFC-%d" % section,
                actions=_actions(env, section),
            )
        )
    return out
