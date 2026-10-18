"""W1-A: M-28 `td.energy.ticket.wizard` — заявка ТО з картки вузла (API-14, FR-40)."""

from odoo import _, api, fields, models


class TdEnergyTicketWizard(models.TransientModel):
    _name = "td.energy.ticket.wizard"
    _description = "Енергетика: заявка ТО з картки вузла"

    node_id = fields.Many2one("td.energy.node", string="Вузол", required=True)
    equipment_id = fields.Many2one(
        "maintenance.equipment", string="Обладнання", compute="_compute_equipment_id", readonly=True
    )
    maintenance_type = fields.Selection(
        [("corrective", "Коригувальне"), ("preventive", "Планове")], string="Тип", default="corrective", required=True
    )
    description = fields.Text(
        string="Опис", required=True, default=lambda self: self.env.context.get("default_description")
    )
    team_id = fields.Many2one("maintenance.team", string="Команда", default=lambda self: self._default_team())
    priority = fields.Selection([("2", "Звичайний"), ("3", "Високий")], string="Пріоритет", default="2")

    @api.model
    def _default_team(self):
        Team = self.env["maintenance.team"]
        return Team.search([("name", "=", "Електрики")], limit=1) or Team.search([], order="id", limit=1)

    @api.depends("node_id")
    def _compute_equipment_id(self):
        for rec in self:
            rec.equipment_id = rec.node_id.equipment_id

    def action_create(self):
        """Створити `maintenance.request`, прив'язати до вузла й повернути форму заявки."""
        self.ensure_one()
        node = self.node_id
        first_line = (self.description or "").strip().splitlines()[0][:80] if (self.description or "").strip() else ""
        description = self.description or ""
        if not node.equipment_id:
            description += "\n" + _("Вузол мережі: %s", node.code)
        Request = self.env["maintenance.request"]
        vals = {
            "name": "%s: %s" % (node.sld_label or node.name, first_line),
            "description": description,
            "equipment_id": node.equipment_id.id,
            "maintenance_type": self.maintenance_type,
            "maintenance_team_id": self.team_id.id,
            "priority": self.priority,
            "user_id": False,
        }
        if "td_origin" in Request._fields:
            vals["td_origin"] = "manual"
        request = Request.sudo().create(vals)
        request.message_post(body=_("Створено з картки вузла %s", node.code))
        return {
            "type": "ir.actions.act_window",
            "name": request.name,
            "res_model": "maintenance.request",
            "view_mode": "form",
            "res_id": request.id,
            "target": "current",
        }
