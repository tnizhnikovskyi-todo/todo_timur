"""M-B1 `td.chp.unit` (розширення): зв'язок із вузлами енергетики `CHP`, `QF-CHP`; дозвіл дистанційних перемикань."""

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from odoo.addons.td_energy_control.tools import cparam_bool as energy_cparam_bool


class TdChpUnit(models.Model):
    _inherit = "td.chp.unit"

    def _default_energy_node(self):
        return self.env["td.energy.node"].sudo().search([("code", "=", "CHP")], limit=1).id

    def _default_energy_qf_node(self):
        return self.env["td.energy.node"].sudo().search([("code", "=", "QF-CHP")], limit=1).id

    energy_node_id = fields.Many2one(
        "td.energy.node", string="Вузол КГУ", default=_default_energy_node, ondelete="set null"
    )
    energy_qf_node_id = fields.Many2one(
        "td.energy.node", string="Вузол вводу QF-CHP", default=_default_energy_qf_node, ondelete="set null"
    )
    energy_node_state = fields.Selection(related="energy_node_id.sld_state", string="Стан вузла КГУ", readonly=True)
    energy_qf_state = fields.Selection(related="energy_qf_node_id.sld_state", string="Стан QF-CHP", readonly=True)
    energy_p_kw = fields.Float(related="energy_node_id.p_now", string="P ел., кВт", readonly=True)

    @api.constrains("energy_node_id", "energy_qf_node_id")
    def _check_energy_nodes(self):
        for rec in self:
            for node, kind in ((rec.energy_node_id, "generator"), (rec.energy_qf_node_id, "cell")):
                if node and node.kind != kind:
                    raise ValidationError(_("Вузол %s не є КГУ/вводом КГУ.", node.code))

    def action_open_energy_node(self):
        """Картка вузла КГУ в Пульті енергетика (`td_energy.node_card`)."""
        self.ensure_one()
        return {
            "type": "ir.actions.client",
            "tag": "td_energy.node_card",
            "name": _("Вузол КГУ"),
            "params": {"code": self.energy_node_id.code or "CHP"},
        }

    def _td_remote_switching(self):
        """D-15: дозвіл дистанційного пуску — `td.energy_control.remote_switching_enabled` (td_energy_control)."""
        self.ensure_one()
        return energy_cparam_bool(self.env, "remote_switching_enabled")
