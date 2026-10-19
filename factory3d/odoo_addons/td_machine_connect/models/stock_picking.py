import logging

from odoo import models

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    """M-27: поповнення під портал (`_action_done`, R-18)."""

    _inherit = "stock.picking"

    def _action_done(self):
        res = super()._action_done()
        Stack = self.env["td.gantry.stack"].sudo()
        for picking in self.filtered(lambda p: p.state == "done"):
            lines = picking.move_line_ids
            dest = Stack.search([("location_id", "in", lines.location_dest_id.ids)])
            src = Stack.search([("location_id", "in", lines.location_id.ids)]) - dest
            try:
                with self.env.cr.savepoint():
                    src._td_refresh()
                    dest._td_after_arrival(picking)
            except Exception:
                _logger.exception("Стоси порталу для %s не оновлено", picking.name)
        return res
