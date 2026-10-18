import json
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

PAYLOAD_MAX = 65536


def _default_expires_at(self):
    return fields.Datetime.now() + timedelta(minutes=10)


class F3dCommand(models.Model):
    _name = "td.command"
    _description = "Телеметрія: команда на пристрій"
    _order = "requested_at desc"
    _inherit = ["mail.thread"]

    signal_id = fields.Many2one(
        "td.signal",
        string="Сигнал",
        required=True,
        ondelete="cascade",
        index=True,
        domain="[('write_enabled', '=', True)]",
    )
    source_id = fields.Many2one("td.source", related="signal_id.source_id", store=True, index=True)
    collector_id = fields.Many2one("td.collector", related="signal_id.collector_id", store=True, index=True)
    signal_kind = fields.Selection(related="signal_id.kind")
    value = fields.Float(string="Значення")
    text = fields.Char(string="Текст/стан")
    payload = fields.Json(string="Дані команди", copy=False)
    payload_text = fields.Text(
        string="Дані команди (JSON)", compute="_compute_payload_text", inverse="_inverse_payload_text"
    )
    result_data = fields.Json(string="Дані результату", readonly=True, copy=False)
    state = fields.Selection(
        [
            ("queued", "У черзі"),
            ("sent", "Передано колектору"),
            ("done", "Виконано"),
            ("failed", "Помилка"),
            ("expired", "Прострочено"),
            ("cancelled", "Скасовано"),
        ],
        default="queued",
        index=True,
        tracking=True,
    )
    requested_by = fields.Many2one("res.users", string="Замовник", default=lambda self: self.env.user, readonly=True)
    requested_at = fields.Datetime(string="Запитано", default=fields.Datetime.now, readonly=True)
    expires_at = fields.Datetime(string="Дійсна до", default=_default_expires_at)
    sent_at = fields.Datetime(string="Передано", readonly=True)
    done_at = fields.Datetime(string="Виконано", readonly=True)
    result = fields.Char(string="Результат", readonly=True)
    error = fields.Char(string="Помилка", readonly=True)
    origin = fields.Char(string="Ініціатор")
    note = fields.Char(string="Примітка")

    @api.depends("payload")
    def _compute_payload_text(self):
        for rec in self:
            rec.payload_text = json.dumps(rec.payload, ensure_ascii=False, indent=2) if rec.payload else ""

    def _inverse_payload_text(self):
        for rec in self:
            text = (rec.payload_text or "").strip()
            try:
                rec.payload = json.loads(text) if text else None
            except ValueError as e:
                raise ValidationError(_("Дані команди (JSON): %s", e)) from e

    @api.constrains("payload")
    def _check_payload(self):
        for rec in self:
            p = rec.payload
            if p is None or p is False:
                continue
            if not isinstance(p, dict) or len(json.dumps(p, ensure_ascii=False).encode()) > PAYLOAD_MAX:
                raise ValidationError(_("Дані команди мають бути об'єктом JSON ≤ 64 КБ."))

    @api.model_create_multi
    def create(self, vals_list):
        icp = self.env["ir.config_parameter"].sudo()
        module_on = icp.get_param("td.telemetry.write_enabled", "False") in ("True", "true", "1")
        for vals in vals_list:
            sig = self.env["td.signal"].sudo().browse(vals.get("signal_id"))
            if not self.env.su and not self.env.user.has_group("td_factory3d.group_td_manager"):
                raise AccessError(_("Команди на пристрої створює лише менеджер телеметрії."))
            src = sig.source_id
            if not module_on:
                raise UserError(_("Запис у пристрій вимкнено: параметр модуля."))
            if src and not src.write_enabled:
                raise UserError(_("Запис у пристрій вимкнено: джерело %s.", src.code))
            if not sig.write_enabled:
                raise UserError(_("Запис у пристрій вимкнено: сигнал %s.", sig.code))
            if src and isinstance(src.params, dict) and src.params.get("read_only"):
                raise UserError(_("Джерело лише для читання."))
            if src and src.type in self.env["td.source"]._f3d_local_types():
                raise UserError(_("Джерело %s без колектора: запис у пристрій неможливий.", src.code))
            if sig.kind == "state" and vals.get("text") and "value" not in vals:
                states = sig.states or []
                vals["value"] = float(states.index(vals["text"])) if vals["text"] in states else -1.0
        return super().create(vals_list)

    def action_cancel(self):
        for rec in self:
            if rec.state != "queued":
                raise UserError(_("Скасувати можна лише команду в черзі."))
        self.write({"state": "cancelled"})
        return True

    @api.model
    def _cron_expire(self):
        """R-18 п. 4: `queued/sent` з `expires_at < now` → `expired`."""
        expired = self.sudo().search([("state", "in", ("queued", "sent")), ("expires_at", "<", fields.Datetime.now())])
        for cmd in expired:
            cmd.write({"state": "expired"})
            cmd.message_post(body=_("Колектор не забрав команду"), subtype_xmlid="mail.mt_note")
        return len(expired)
