"""Міст: розширення `td.energy.point` (M-B1, R-B1): зв'язок з установкою BMS і `_td_bind_extra` — теплові точки й
лічильники з `td_bms` (ідемпотентно за `(ресурс, код)`; змінені вручну поля наявних записів не перезаписуються, окрім
`estimate_params["state_invert"]` точки `DOCK`, що стежить за `invert_di` воріт, поки точка привʼязана до їхнього
сигналу)."""

import logging

from odoo import api, fields, models

from ..tools import heat

_logger = logging.getLogger(__name__)

OUTDOOR_SIGNAL = heat.OUTDOOR_SIGNAL


class TdEnergyPoint(models.Model):
    _inherit = "td.energy.point"

    hvac_unit_id = fields.Many2one("td.bms.hvac.unit", string="Установка BMS", ondelete="set null")

    @api.model
    def _td_bind_extra(self):
        """R-B1: точки `heat` (`HEAT-BOILER`, `HEAT-CHP`, `RV-ALL`, `AHU-1`, `OFFICE`, `DOCK` — лише якщо знайдено
        сигнал воріт) і лічильники `HM-*`; без `td.bms.heat.balance` компанії — `{}`; інакше `{"points", "meters"}`
        (скільки створено). `DOCK`: `estimate_params["state_invert"]` = `invert_di` воріт (NC: 0 = відкрито); для
        наявної точки оновлюється лише цей ключ і лише якщо `state_signal_id` досі сигнал цих воріт."""
        stats = dict(super()._td_bind_extra() or {})
        env = self.env(su=True, context=dict(self.env.context, tracking_disable=True))
        balance = heat.balance(env)
        resource = env["td.energy.resource"].get_by_code("heat")
        if not balance or not resource:
            return stats
        units = env["td.bms.hvac.unit"].search([])
        rv_units = units.filtered(lambda u: u.code.startswith("RV-"))
        ahu = units.filtered(lambda u: u.code == "AHU-1")[:1]
        gate_signal, gate_invert = find_dock(env)
        points = [
            ("HEAT-BOILER", "Котли (тепло)", "source", 10, {}),
            ("HEAT-CHP", "КГУ (тепло)", "source", 20, {}),
            ("RV-ALL", "Дахові установки RoofVent", "consumer", 30, {"hvac_ref": "RV-*"}),
            ("AHU-1", "Припливна установка AHU-1", "consumer", 40,
             {"hvac_ref": "AHU-1", "hvac_unit_id": ahu.id or False}),
            ("OFFICE", "Офіс і побутові", "consumer", 60,
             {"estimate_method": "residual", "estimate_params": {"from": ["HEAT-BOILER", "HEAT-CHP"]}}),
        ]  # fmt: skip
        if gate_signal:
            points.insert(
                4,
                (
                    "DOCK", "Втрати через ворота", "consumer", 50,
                    {
                        "estimate_method": "gate_loss", "state_signal_id": gate_signal.id,
                        "estimate_params": {
                            "loss_kw_per_k": heat.DOCK_LOSS_K, "t_out_signal": OUTDOOR_SIGNAL,
                            "t_in": balance.t_in_set, "state_invert": gate_invert,
                        },
                    },
                ),
            )  # fmt: skip
        Point = env["td.energy.point"].with_context(active_test=False)
        by_code = {}
        created_points = 0
        for code, name, kind, sequence, vals in points:
            point = Point.search(
                [("resource_id", "=", resource.id), ("code", "=", code), ("company_id", "=", env.company.id)], limit=1
            )
            if not point:
                point = Point.create(
                    dict(vals, resource_id=resource.id, code=code, name=name, kind=kind, sequence=sequence)
                )
                created_points += 1
            elif code == "DOCK" and gate_signal:
                sync_state_invert(point, gate_signal, gate_invert)
            by_code[code] = point
        flows = {
            "HM-BOILER": ("HEAT-BOILER", "Тепло: котельня (BMS)", balance.boiler_heat_signal_id),
            "HM-CHP": ("HEAT-CHP", "Тепло: КГУ (BMS)", balance.chp_heat_signal_id),
            "HM-RV": ("RV-ALL", "Тепло: дахові установки (BMS)", rv_units.heat_signal_id),
            "HM-AHU1": ("AHU-1", "Тепло: AHU-1 (BMS)", ahu.heat_signal_id),
        }
        estimates = {
            "HM-DOCK": ("DOCK", "Тепло: втрати через ворота (оцінка)"),
            "HM-OFFICE": ("OFFICE", "Тепло: офіс і побутові (оцінка)"),
        }
        Meter = env["td.energy.meter"].with_context(active_test=False)
        created_meters = 0
        for code, (point_code, name, signals) in flows.items():
            if Meter.search_count([("code", "=", code)]):
                continue
            if not signals:
                _logger.warning("td_energy_resources_bms: лічильник %s пропущено — немає сигналів тепла в BMS", code)
                continue
            Meter.create(
                {
                    "code": code, "name": name, "resource_id": resource.id, "point_id": by_code[point_code].id,
                    "mode": "flow_integrate", "flow_signal_ids": [(6, 0, signals.ids)],
                }
            )  # fmt: skip
            created_meters += 1
        for code, (point_code, name) in estimates.items():
            point = by_code.get(point_code)
            if not point or Meter.search_count([("code", "=", code)]):
                continue
            Meter.create(
                {"code": code, "name": name, "resource_id": resource.id, "point_id": point.id, "mode": "estimate"}
            )
            created_meters += 1
        stats.update(points=created_points, meters=created_meters)
        return stats


def find_dock(env, company=None):
    """Q-08: ворота відвантаження компанії (`td.yard.gate`, схід, `out`/`both`, активні; `company` — за замовчуванням
    `env.company`, як у точок і балансу) → `(сигнал «стріла відкрита», invert_di)`. `(порожній набір, False)` —
    `td_yard` не встановлено або сигналу немає (точка `DOCK` не створюється)."""
    if "td.yard.gate" not in env:
        return env["td.signal"], False
    company = company or env.company
    gate = env["td.yard.gate"].search(
        [
            ("state_signal_id", "!=", False), ("side", "=", "east"), ("direction", "in", ("out", "both")),
            ("company_id", "=", company.id),
        ],
        order="sequence, id",
        limit=1,
    )  # fmt: skip
    return gate.state_signal_id, bool(gate.invert_di)


def find_dock_signal(env, company=None):
    """Q-08: сигнал відкриття воріт відвантаження компанії або порожній набір (див. `find_dock`)."""
    return find_dock(env, company)[0]


def sync_state_invert(point, signal, invert):
    """Привести `estimate_params["state_invert"]` точки до `invert_di` воріт. Лише якщо точка досі привʼязана до
    `signal` (інший сигнал — ручна зміна, не чіпаємо); решта параметрів не змінюється; відсутній ключ = `False`.
    Повертає `True`, якщо записано."""
    params = dict(point.estimate_params or {})
    if point.state_signal_id != signal or bool(params.get("state_invert")) == bool(invert):
        return False
    params["state_invert"] = bool(invert)
    point.estimate_params = params
    return True
