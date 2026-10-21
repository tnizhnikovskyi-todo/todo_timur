"""M-04 `td.chp.maintenance.rule` — інтервал ТО за наробітком (R-10)."""

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from ..tools import bus
from ..tools.signals import cparam_bool, now


class TdChpMaintenanceRule(models.Model):
    _name = "td.chp.maintenance.rule"
    _description = "КГУ: правило ТО за наробітком"
    _order = "sequence, id"

    unit_id = fields.Many2one("td.chp.unit", string="Агрегат", required=True, index=True, ondelete="cascade")
    name = fields.Char(string="Назва", required=True)
    every_h = fields.Float(string="Через, год", required=True, default=1000.0)
    last_h = fields.Float(string="Остання відмітка, мотогод")
    lead_pct = fields.Float(string="Попередити за, % інтервалу", default=15.0)
    request_id = fields.Many2one("maintenance.request", string="Заявка ТО", readonly=True, ondelete="set null")
    left_h = fields.Float(string="Залишок, год", compute="_compute_left", digits=(16, 1))
    hours = fields.Float(string="Наробіток, мотогод", compute="_compute_left", digits=(16, 1))
    progress = fields.Float(string="Вироблено, %", compute="_compute_left")
    state = fields.Selection(
        [("ok", "Норма"), ("soon", "Скоро"), ("overdue", "Прострочено")], string="Стан", compute="_compute_left"
    )
    sequence = fields.Integer(default=10)

    @api.constrains("every_h")
    def _check_every(self):
        for rec in self:
            if rec.every_h <= 0:
                raise ValidationError(_("Інтервал ТО має бути більшим за нуль."))

    @api.depends("unit_id", "every_h", "last_h", "lead_pct")
    def _compute_left(self):
        hours_of = {}
        for rec in self:
            unit = rec.unit_id
            if unit.id not in hours_of:
                hours_of[unit.id] = unit._td_value("eng/hours") if unit else None
            hours = hours_of[unit.id]
            if hours is None:
                rec.hours = rec.left_h = rec.progress = 0.0
                rec.state = False
                continue
            left = rec.last_h + rec.every_h - hours
            rec.hours = hours
            rec.left_h = left
            rec.progress = min(max((1 - left / rec.every_h) * 100, 0.0), 100.0)
            rec.state = "overdue" if left < 0 else "soon" if left <= rec.every_h * rec.lead_pct / 100 else "ok"

    def _td_refresh(self):
        """Обчислювані поля залежать від свіжих показань (не від полів правила): скинути кеш перед читанням."""
        self.invalidate_recordset(["hours", "left_h", "progress", "state"])
        return self

    def _td_dto(self):
        self.ensure_one()
        self._td_refresh()
        req = self.request_id
        known = bool(self.state)
        return {
            "id": self.id,
            "name": self.name,
            "every_h": self.every_h,
            "last_h": self.last_h,
            "left_h": round(self.left_h, 1) if known else None,
            "state": self.state or None,
            "request": {"id": req.id, "name": req.name} if req else None,
        }

    # --- R-10 ---------------------------------------------------------------------------------------------------
    @api.model
    def _cron_check(self):
        """Закрита заявка → `last_h = hours`; правило `soon/overdue` без відкритої заявки → нова заявка ТО."""
        if not cparam_bool(self.env, "read_enabled"):
            return 0
        created = 0
        for rule in self.sudo().search([])._td_refresh():
            if not rule.state:
                continue  # немає свіжих мотогодин
            if rule.request_id and rule.request_id.stage_id.done:
                rule.write({"last_h": rule.hours, "request_id": False})
                bus.tick(self.env, "maintenance")
            if not rule.request_id and rule.state in ("soon", "overdue") and rule.unit_id.equipment_id:
                rule._td_open_request()
                created += 1
        return created

    def _td_open_request(self):
        self.ensure_one()
        eq = self.unit_id.equipment_id
        left = self.left_h
        title = (
            _("ТО КГУ: %(name)s — через %(n)s год", name=self.name, n=f"{left:.0f}")
            if left >= 0
            else _("ТО КГУ: %(name)s — прострочено на %(n)s год", name=self.name, n=f"{-left:.0f}")
        )
        desc = _(
            "Наробіток: %(h).1f мотогод, інтервал: %(e).0f год, остання відмітка: %(l).1f мотогод.",
            h=self.hours,
            e=self.every_h,
            l=self.last_h,
        )
        vals = {
            "name": title,
            "equipment_id": eq.id,
            "maintenance_type": "preventive",
            "description": desc,
            "request_date": fields.Date.today(),
            "schedule_date": now(self.env),
        }
        team = eq.maintenance_team_id
        if team:
            vals["maintenance_team_id"] = team.id
        request = self.env["maintenance.request"].sudo().create(vals)
        self.sudo().write({"request_id": request.id})
        self.env["td.chp.event"]._td_log(
            self.unit_id,
            "info",
            "maintenance",
            title,
            code=f"to/{self.id}",
            request_id=request.id,
            dedup_s=0,
        )
        bus.tick(self.env, "maintenance")
        return request

    def action_td_done(self):
        """«ТО виконано»: `last_h = hours`, заявка (якщо є) → стадія `done`."""
        if not self.env.su and not self.env.user.has_group("td_chp.group_td_chp_operator"):
            raise AccessError(_("Відмітити ТО може лише енергетик КГУ."))
        for rule in self.sudo()._td_refresh():
            if not rule.state:
                raise UserError(_("Немає свіжих даних про мотогодини (chp/eng/hours)."))
            hours = rule.hours
            if rule.request_id:
                stage = self.env["maintenance.stage"].sudo().search([("done", "=", True)], order="sequence", limit=1)
                if stage and not rule.request_id.stage_id.done:
                    rule.request_id.write({"stage_id": stage.id})
            rule.write({"last_h": hours, "request_id": False})
        bus.tick(self.env, "maintenance")
        return True
