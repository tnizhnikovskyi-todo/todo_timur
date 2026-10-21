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

    def _td_pickings(self, cancelled=False):
        self.ensure_one()
        domain = [("origin", "=", self.name)]
        group = self.procurement_group_id if "procurement_group_id" in self._fields else False
        if group:
            domain = ["|", ("group_id", "=", group.id)] + domain
        if not cancelled:
            domain = [("state", "!=", "cancel")] + domain
        return self.env["stock.picking"].search(domain, order="id asc")

    def _compute_f3d_has_3d(self):
        for rec in self:
            rec.td_has_3d = bool(rec.id and (rec._td_productions() or rec._td_pickings(cancelled=True)))

    def _td_pick_production(self):
        """МО для показу: перше «живе» (не виконане й не скасоване, за date_start), інакше найновіше (виконані
        перед скасованими). Виконане чи скасоване поза payload переглядача: клієнт бере його маршрут із сервера (API-13)."""
        productions = self._td_productions()
        live = productions.filtered(lambda m: m.state not in ("done", "cancel"))
        if live:
            return live[0]
        key = lambda m: (m.state != "cancel", m.date_finished or m.date_start or m.create_date, m.id)  # noqa: E731
        return productions.sorted(key)[-1:]

    def action_f3d_show(self):
        """M-08: МО замовлення -> params.mo (перше «живе», інакше найновіше); інакше відвантаження -> params.picking
        (перше непроскасоване, інакше найновіше скасоване)."""
        self.ensure_one()
        production = self._td_pick_production()
        if production:
            params = {"mo": production.name, "so": self.name}
        else:
            picking = self._td_pickings()[:1] or self._td_pickings(cancelled=True)[-1:]
            if not picking:
                raise UserError(_("Для замовлення ще немає виробничих замовлень чи відвантажень"))
            params = {"picking": picking.name, "so": self.name}
        return {"type": "ir.actions.client", "tag": "f3d_viewer.action", "name": "3D: " + self.name, "params": params}
