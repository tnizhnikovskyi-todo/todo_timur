from odoo import _, fields, models
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    td_has_3d = fields.Boolean(string="Є що показати в 3D", compute="_compute_f3d_has_3d")

    def _td_productions(self):
        """МО: origin = name або (якщо є sale_stock) група забезпечення замовлення."""
        self.ensure_one()
        domain = [("origin", "=", self.name)]
        group = self.procurement_group_id if "procurement_group_id" in self._fields else False
        if group:
            domain = ["|", ("procurement_group_id", "=", group.id)] + domain
        return self.env["mrp.production"].search(domain, order="date_start asc, id asc")

    def _td_pickings(self):
        self.ensure_one()
        domain = [("origin", "=", self.name), ("state", "!=", "cancel")]
        group = self.procurement_group_id if "procurement_group_id" in self._fields else False
        if group:
            domain = ["&", ("state", "!=", "cancel"), "|", ("group_id", "=", group.id), ("origin", "=", self.name)]
        return self.env["stock.picking"].search(domain, order="id asc")

    def _compute_f3d_has_3d(self):
        for rec in self:
            rec.td_has_3d = bool(rec.id and (rec._td_productions() or rec._td_pickings()))

    def action_f3d_show(self):
        """M-08: МО замовлення (перше за date_start) -> params.mo; інакше відвантаження -> params.picking."""
        self.ensure_one()
        productions = self._td_productions()
        if productions:
            params = {"mo": productions[0].name, "so": self.name}
        else:
            pickings = self._td_pickings()
            if not pickings:
                raise UserError(_("Для замовлення ще немає виробничих замовлень чи відвантажень"))
            params = {"picking": pickings[0].name, "so": self.name}
        return {"type": "ir.actions.client", "tag": "f3d_viewer.action", "name": "3D: " + self.name, "params": params}
