from datetime import timedelta

from odoo import _, api, fields, models

from ..tools import dates


class MrpWorkcenter(models.Model):
    _inherit = "mrp.workcenter"

    td_energy_node_id = fields.Many2one(
        "td.energy.node",
        string="Вузол енергетики",
        compute="_compute_f3d_energy_node",
        search="_search_f3d_energy_node",
    )
    td_energy_p_now = fields.Float(string="Потужність зараз, кВт", compute="_compute_f3d_energy_node")
    td_kwh_today = fields.Float(string="Енергія сьогодні, кВт·год", compute="_compute_f3d_energy_node")
    td_kwh_idle_today = fields.Float(string="Простій сьогодні, кВт·год", compute="_compute_f3d_energy_node")

    @api.depends_context("uid")
    def _compute_f3d_energy_node(self):
        Node = self.env["td.energy.node"]
        can_read = Node.has_access("read")
        nodes = Node.sudo().search([("workcenter_id", "in", self.ids)]) if can_read else Node.browse()
        by_wc = {n.workcenter_id.id: n for n in nodes}
        today = dates.local_day(dates.now_utc(self.env))
        idle = {}
        if nodes and self.env["td.energy.alloc"].has_access("read"):
            for wc, total in (
                self.env["td.energy.alloc"]
                .sudo()
                ._read_group(
                    [("kind", "=", "idle"), ("day", "=", today), ("workcenter_id", "in", self.ids)],
                    ["workcenter_id"],
                    ["kwh:sum"],
                )
            ):
                idle[wc.id] = total
        for wc in self:
            node = by_wc.get(wc.id)
            wc.td_energy_node_id = node
            wc.td_energy_p_now = node.p_now if node else 0.0
            wc.td_kwh_today = node.kwh_today if node else 0.0
            wc.td_kwh_idle_today = idle.get(wc.id, 0.0)

    def _search_f3d_energy_node(self, operator, value):
        if operator in ("in", "not in") and not value:
            return [("id", "!=", 0)] if operator == "not in" else [("id", "=", 0)]
        nodes = self.env["td.energy.node"].sudo().search([("workcenter_id", "!=", False)])
        if operator in ("=", "in"):
            ids = value if isinstance(value, list | tuple) else [value]
            nodes = nodes.filtered(lambda n: n.id in ids)
        elif operator in ("!=", "not in"):
            ids = value if isinstance(value, list | tuple) else [value]
            nodes = nodes.filtered(lambda n: n.id not in ids)
        return [("id", "in", nodes.workcenter_id.ids)]

    def action_f3d_energy_view(self):
        """Інтервали лічильника вузла РЦ за 2 доби (графік M-03)."""
        self.ensure_one()
        node = self.sudo().td_energy_node_id
        since = dates.now_utc(self.env) - timedelta(hours=48)
        return {
            "type": "ir.actions.act_window",
            "name": _("Енергія: %s", self.name),
            "res_model": "td.energy.interval",
            "view_mode": "graph,list",
            "domain": [("node_id", "=", node.id), ("ts_start", ">=", fields.Datetime.to_string(since))],
        }
