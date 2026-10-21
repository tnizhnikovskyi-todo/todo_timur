"""M-17 `td.energy.whatif` — сценарій «Що якщо» (вау №6): перенос ділянки чи вузлів на інший тарифний період. R-23."""

import json
import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from odoo.addons.td_energy.tools import dates

from ..tools import whatif as whatif_tools

_logger = logging.getLogger(__name__)

COST = "td_energy.group_td_energy_cost"
DEMO_NOTE = "демо-сид"  # як у `tools/seed.py`: purge видаляє сидоване за цією приміткою
# Поля-входи: їхня зміна скидає результат (щоб у списку порівняння не лишалися застарілі цифри)
INPUTS = (
    "scope", "area_id", "node_ids", "hour_from", "hour_to", "move_mode", "shift_hours", "share_pct", "days_mode",
    "respect_rating", "base_days",
)  # fmt: skip
RESULT_RESET = {
    "state": "draft", "date_from": False, "date_to": False, "days_used": 0, "computed_at": False, "cost_before": 0.0,
    "cost_after": 0.0, "saving_month": 0.0, "peak_before_kw": 0.0, "peak_after_kw": 0.0, "peak_delta_kw": 0.0,
    "limit_kw": 0.0, "moved_kwh_month": 0.0, "limit_exceeded": False, "warning_count": 0, "result_json": False,
}  # fmt: skip
INTERVAL_SQL = """
SELECT meter_id, node_id, day, hour_local, ts_start, kwh, kwh_export, quality
  FROM td_energy_interval
 WHERE role = %s AND day BETWEEN %s AND %s AND (%s OR node_id = ANY(%s))
"""


def _hhmm(hour):
    """Година дробом → «08:00»; 24 → «24:00»."""
    minutes = int(round(hour * 60))
    return "%02d:%02d" % divmod(minutes, 60)


class TdEnergyWhatif(models.Model):
    _name = "td.energy.whatif"
    _description = "Енергетика: сценарій «Що якщо»"
    _order = "id desc"

    name = fields.Char(string="Назва", required=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one("res.company", string="Компанія", required=True, default=lambda self: self.env.company)
    note = fields.Char(string="Примітка", size=256)
    state = fields.Selection(
        [("draft", "Чернетка"), ("done", "Розраховано")], string="Стан", default="draft", readonly=True, copy=False
    )

    # --- що, коли, куди -------------------------------------------------------------------------------
    scope = fields.Selection(
        [("area", "Ділянка"), ("nodes", "Вибрані вузли")], string="Що переносимо", required=True, default="area"
    )
    area_id = fields.Many2one("td.energy.area", string="Ділянка", ondelete="restrict")
    node_ids = fields.Many2many(
        "td.energy.node", "td_energy_whatif_node_rel", "whatif_id", "node_id", string="Вузли",
        domain="[('kind', '=', 'consumer')]",
    )  # fmt: skip
    hour_from = fields.Float(
        string="Вікно з (год)", default=8.0, help="Місцевий час (Київ); 22:00–06:00 — вікно через північ."
    )
    hour_to = fields.Float(string="Вікно по (год)", default=16.0)
    move_mode = fields.Selection(
        [("shift", "Зсув на N годин"), ("night", "У нічну зону тарифу")], string="Куди", required=True, default="shift"
    )
    shift_hours = fields.Float(
        string="Зсув, год", digits=(4, 2), default=2.0, help="Додатний — на потім, від'ємний — на раніше."
    )
    share_pct = fields.Float(string="Частка навантаження, %", digits=(5, 1), default=100.0)
    days_mode = fields.Selection(
        [("work", "Лише робочі дні (пн–пт)"), ("all", "Усі дні")], string="Дні", required=True, default="work"
    )
    respect_rating = fields.Boolean(
        string="Не перевищувати номінал вузла", default=True, help="Встановлена потужність вузла (кВт) — стеля слота."
    )
    base_days = fields.Integer(string="Базовий період, діб", default=30, help="Останні повні доби до вчора.")

    # --- результат ------------------------------------------------------------------------------------
    date_from = fields.Date(string="База з", readonly=True, copy=False)
    date_to = fields.Date(string="База по", readonly=True, copy=False)
    days_used = fields.Integer(string="Діб у розрахунку", readonly=True, copy=False)
    computed_at = fields.Datetime(string="Розраховано", readonly=True, copy=False)
    cost_before = fields.Float(string="Вартість було, ₴/міс", digits=(14, 2), readonly=True, copy=False, groups=COST)
    cost_after = fields.Float(string="Вартість стало, ₴/міс", digits=(14, 2), readonly=True, copy=False, groups=COST)
    saving_month = fields.Float(string="Економія, ₴/міс", digits=(14, 2), readonly=True, copy=False, groups=COST)
    peak_before_kw = fields.Float(string="Пік було, кВт", digits=(10, 1), readonly=True, copy=False)
    peak_after_kw = fields.Float(string="Пік стало, кВт", digits=(10, 1), readonly=True, copy=False)
    peak_delta_kw = fields.Float(string="Зміна піку, кВт", digits=(10, 1), readonly=True, copy=False)
    limit_kw = fields.Float(string="Ліміт договору, кВт", digits=(10, 1), readonly=True, copy=False)
    moved_kwh_month = fields.Float(string="Перенесено, кВт·год/міс", digits=(12, 1), readonly=True, copy=False)
    limit_exceeded = fields.Boolean(string="Пік понад ліміт", readonly=True, copy=False)
    warning_count = fields.Integer(string="Попереджень", readonly=True, copy=False)
    result_json = fields.Text(string="Результат (JSON)", readonly=True, copy=False, groups=COST)

    target_text = fields.Char(string="Що переносимо", compute="_compute_texts")
    window_text = fields.Char(string="Вікно", compute="_compute_texts")
    move_text = fields.Char(string="Куди", compute="_compute_texts")

    # --- перевірки ------------------------------------------------------------------------------------
    @api.constrains("hour_from", "hour_to", "shift_hours", "share_pct", "base_days", "move_mode")
    def _check_inputs(self):
        for rec in self:
            for hour in (rec.hour_from, rec.hour_to):
                if not 0 <= hour <= 24 or abs(hour * 4 - round(hour * 4)) > 1e-9:
                    raise ValidationError(_("Години вікна — від 0 до 24 з кроком 15 хв."))
            if abs(rec.hour_from - rec.hour_to) < 1e-9:
                raise ValidationError(_("Вікно має ненульову тривалість: «з» і «по» не можуть збігатися."))
            if not 0 < rec.share_pct <= 100:
                raise ValidationError(_("Частка навантаження — від 0 (не включно) до 100 %."))
            if not 7 <= rec.base_days <= 90:
                raise ValidationError(_("Базовий період — від 7 до 90 діб."))
            if rec.move_mode == "shift" and not (
                0 < abs(rec.shift_hours) <= 12 and abs(rec.shift_hours * 4 - round(rec.shift_hours * 4)) < 1e-9
            ):
                raise ValidationError(_("Зсув — від 15 хв до 12 годин (крок 15 хв), додатний або від'ємний."))

    @api.depends("scope", "area_id", "node_ids", "hour_from", "hour_to", "move_mode", "shift_hours")
    def _compute_texts(self):
        for rec in self:
            if rec.scope == "area":
                rec.target_text = _("Ділянка «%s»", rec.area_id.name) if rec.area_id else ""
            else:
                codes = rec.node_ids.mapped("code")
                rec.target_text = _("Вузли: %s", ", ".join(codes[:3]) + (" …" if len(codes) > 3 else ""))
            rec.window_text = "%s–%s" % (_hhmm(rec.hour_from), _hhmm(rec.hour_to))
            if rec.move_mode == "night":
                rec.move_text = _("у нічну зону")
            else:
                hours = ("%+g" % rec.shift_hours).replace("-", "−").replace(".", ",")
                rec.move_text = _("%s год", hours)

    # --- запис: зміна входів скидає результат ----------------------------------------------------------
    def write(self, vals):
        if set(vals) & set(INPUTS) and not set(vals) & set(RESULT_RESET):
            vals = dict(vals, **RESULT_RESET)
        return super().write(vals)

    # --- розрахунок -----------------------------------------------------------------------------------
    def action_compute(self):
        for rec in self:
            rec._td_compute()
        return True

    def _td_nodes(self):
        self.ensure_one()
        if self.scope == "area":
            if not self.area_id:
                raise UserError(_("Оберіть ділянку."))
            nodes = self.area_id.sudo().node_ids
        else:
            nodes = self.node_ids.sudo()
        nodes = nodes.filtered(lambda n: n.kind == "consumer" and n.active)
        if not nodes:
            raise UserError(_("Немає вузлів-споживачів для перенесення."))
        return nodes

    def _td_scope_text(self, nodes):
        if self.scope == "area":
            return _("ділянці «%s»", self.area_id.name)
        codes = nodes.mapped("code")
        return _("вузлах: %s", ", ".join(codes[:4]) + (" …" if len(codes) > 4 else ""))

    def _td_rows(self, role, node_ids, first, last):
        """Інтервали `role` за `[first, last]`: `(node_id, індекс слота, кВт·год, віддано, якість)`; дублі слотів
        одного лічильника (повторна година при переході на зимовий час) відкидаються."""
        cr = self.env.cr
        cr.execute(INTERVAL_SQL, (role, first, last, node_ids is None, node_ids or []))
        seen = set()
        for meter_id, node_id, day, hour_local, ts_start, kwh, kwh_export, quality in cr.fetchall():
            idx = (day - first).days * whatif_tools.SLOTS + hour_local * 4 + ts_start.minute // 15
            if (meter_id, idx) not in seen:
                seen.add((meter_id, idx))
                yield meter_id, node_id, idx, kwh or 0.0, kwh_export or 0.0, quality

    def _td_grid(self, first, last):
        """Імпорт із мережі за вводами мінус віддача (кВт·год за слот) і прапорці повних діб: ≥ 90 % слотів
        усіх лічильників вводів не `missing`."""
        n_days = (last - first).days + 1
        net, per_day, meters = [0.0] * (n_days * whatif_tools.SLOTS), [0] * n_days, set()
        for meter_id, _node, idx, kwh, kwh_export, quality in self._td_rows("incomer", None, first, last):
            net[idx] += kwh - kwh_export
            meters.add(meter_id)
            if quality != "missing":
                per_day[idx // whatif_tools.SLOTS] += 1
        need = 0.9 * whatif_tools.SLOTS * max(1, len(meters))
        return net, [count >= need for count in per_day]

    def _td_loads(self, node_ids, first, last):
        """Споживання вузлів: `{node_id: список кВт·год за слот}`."""
        total = ((last - first).days + 1) * whatif_tools.SLOTS
        loads = {}
        for _meter, node_id, idx, kwh, _export, _quality in self._td_rows("consumer", node_ids, first, last):
            loads.setdefault(node_id, [0.0] * total)[idx] += kwh
        return loads

    def _td_compute(self):
        """R-23: збирає ряди (SQL), викликає чисту `tools/whatif.run`, зберігає підсумки й JSON результату."""
        self.ensure_one()
        env = self.env
        env.flush_all()
        now = dates.now_utc(env)
        last = dates.local_day(now) - timedelta(days=1)
        first = last - timedelta(days=self.base_days - 1)
        nodes = self._td_nodes()
        tariff = env["td.energy.tariff"].sudo()._td_tariff_at(dates.local_day_bounds(last)[0], self.company_id)
        if not tariff:
            raise UserError(_("Немає чинного тарифу на %s.", last.strftime("%d.%m.%Y")))
        net, data_ok = self._td_grid(first, last)
        if not any(data_ok):
            raise UserError(
                _("Немає повних діб даних вводів за %s–%s.", first.strftime("%d.%m"), last.strftime("%d.%m"))
            )
        loads = self._td_loads(nodes.ids, first, last)
        if not loads:
            raise UserError(_("Немає даних споживання вибраних вузлів за базовий період."))
        zeros = [0.0] * (self.base_days * whatif_tools.SLOTS)
        params = {
            "first_day": first, "n_days": self.base_days, "net": net, "data_ok": data_ok,
            "nodes": [
                {"code": n.code, "name": n.name, "kwh": loads.get(n.id, zeros), "cap_kw": n.p_inst_kw or None}
                for n in nodes
            ],
            "zones": [
                whatif_tools.Zone(z.name, z.code, z.price, z.weekdays, z.hour_from, z.hour_to, z.sequence)
                for z in tariff.zone_ids
            ],
            "export_price": tariff.export_price, "capacity_price": tariff.capacity_price,
            "contract_kw": tariff.contract_kw, "warn_pct": tariff.peak_warn_pct,
            "window": (self.hour_from, self.hour_to), "mode": self.move_mode, "shift_h": self.shift_hours,
            "share": self.share_pct / 100, "days": self.days_mode, "respect_rating": self.respect_rating,
            "scope_text": self._td_scope_text(nodes),
        }  # fmt: skip
        try:
            res = whatif_tools.run(params)
        except whatif_tools.WhatIfError as exc:
            raise UserError(str(exc)) from exc
        t, warnings = res["tiles"], res["warnings"]
        res["meta"].update(
            {
                "date_from": first.isoformat(), "date_to": last.isoformat(), "tariff": tariff.name,
                "nodes": nodes.mapped("code"),
            }
        )  # fmt: skip
        self.write(
            {
                "state": "done", "date_from": first, "date_to": last, "days_used": res["meta"]["days_used"],
                "computed_at": now, "cost_before": t["cost_before"], "cost_after": t["cost_after"],
                "saving_month": t["saving_month"], "peak_before_kw": t["peak_before_kw"],
                "peak_after_kw": t["peak_after_kw"], "peak_delta_kw": t["peak_delta_kw"], "limit_kw": t["limit_kw"],
                "moved_kwh_month": t["moved_kwh_month"],
                "limit_exceeded": any(w["code"] == "peak_over_limit" for w in warnings),
                "warning_count": sum(1 for w in warnings if w["level"] != "info"),
                "result_json": json.dumps(res, ensure_ascii=False),
            }
        )  # fmt: skip
        return res

    # --- демо (R-23 п. 9) -----------------------------------------------------------------------------
    @api.model
    def _td_seed_demo(self):
        """Демо-сценарії «Розкрій на ніч» і «Компресори зміщення на 2 год». Створюються лише коли чинний тариф має
        зони з різними цінами (інакше економії немає — сценарії були б беззмістовні) і вистачає даних; повтор не
        дублює. Повертає кількість створених."""
        model = self.sudo().with_context(tracking_disable=True)
        env = model.env
        now = dates.now_utc(env)
        tariff = env["td.energy.tariff"]._td_tariff_at(now)
        if not tariff or len({z.price for z in tariff.zone_ids}) < 2:
            _logger.info("td_energy_analytics: демо «Що якщо» пропущено — у чинному тарифі немає зон з різними цінами")
            return 0
        area = env["td.energy.area"].search([("code", "=", "CUT")], limit=1)
        compressor = env["td.energy.node"].search([("code", "=", "COMPRESSOR")], limit=1)
        defs = [
            {
                "name": "Розкрій на ніч", "scope": "area", "area_id": area.id, "hour_from": 16.0, "hour_to": 23.0,
                "move_mode": "night", "share_pct": 100.0, "days_mode": "work",
            },
            {
                "name": "Компресори зміщення на 2 год", "scope": "nodes", "node_ids": [(6, 0, compressor.ids)],
                "hour_from": 8.0, "hour_to": 11.0, "move_mode": "shift", "shift_hours": 2.0, "share_pct": 100.0,
                "days_mode": "work",
            },
        ]  # fmt: skip
        created = 0
        for vals in defs:
            if (vals["scope"] == "area" and not area) or (vals["scope"] == "nodes" and not compressor):
                continue
            if model.search_count([("name", "=", vals["name"]), ("note", "=", DEMO_NOTE)]):
                continue
            try:
                with env.cr.savepoint():
                    rec = model.create(dict(vals, note=DEMO_NOTE))
                    rec._td_compute()
                created += 1
            except UserError as exc:
                _logger.info("td_energy_analytics: демо «%s» пропущено: %s", vals["name"], exc)
        return created
