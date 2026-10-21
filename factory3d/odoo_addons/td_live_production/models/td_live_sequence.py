"""Послідовності «попереду імен»: демо створювало документи з явними іменами (WH/MO/00231…00262, S00087…), а
послідовність Odoo про це не знає. Перші згенеровані документи дістали б зайняті номери й упали б на «Референс повинен
бути унікальний на компанію». Помічник підсуває `number_next` за найбільший числовий суфікс наявних імен.
"""

import logging
import re

from odoo import api, models
from odoo.tools import SQL

_logger = logging.getLogger(__name__)

# код типу операції складу → таблиця документів, що носять її номери
PICKING_TABLE = {"mrp_operation": "mrp_production"}
DEFAULT_TABLE = "stock_picking"


class TdLiveEngine(models.AbstractModel):
    _inherit = "td.live.engine"

    @api.model
    def _td_sequence_targets(self):
        """`[(ir.sequence, таблиця)]` для документів модуля: замовлення продажу, МО й переміщення компанії."""
        env = self.sudo().env
        company = env.company
        targets = {}
        sale = env["ir.sequence"].search(
            [("code", "=", "sale.order"), ("company_id", "in", [company.id, False])], order="company_id", limit=1
        )
        if sale:
            targets[sale.id] = (sale, "sale_order")
        for ptype in env["stock.picking.type"].search([("company_id", "=", company.id)]):
            seq = ptype.sequence_id
            if seq and seq.id not in targets:
                targets[seq.id] = (seq, PICKING_TABLE.get(ptype.code, DEFAULT_TABLE))
        return list(targets.values())

    @api.model
    def _td_max_suffix(self, table, seq):
        """Найбільший числовий суфікс імен таблиці з префіксом і суфіксом послідовності (0 — таких імен немає)."""
        prefix, suffix = seq._get_prefix_suffix()
        pattern = re.compile("^%s(\\d+)%s$" % (re.escape(prefix or ""), re.escape(suffix or "")))
        like = (prefix or "").replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        self.env.cr.execute(
            SQL(
                "SELECT name FROM %s WHERE name LIKE %s AND company_id = %s",
                SQL.identifier(table),
                like,
                self.env.company.id,
            )
        )
        top = 0
        for (name,) in self.env.cr.fetchall():
            match = pattern.match(name or "")
            if match:
                top = max(top, int(match.group(1)))
        return top

    @api.model
    def td_sequences_ahead(self):
        """Ідемпотентно підсунути послідовності вперед за наявні імена. Повертає `[(назва, було, стало)]` змінених."""
        fixed = []
        for seq, table in self._td_sequence_targets():
            top = self._td_max_suffix(table, seq)
            current = seq.sudo()._get_current_sequence()
            nxt = current.number_next_actual
            if top and nxt <= top:
                current.number_next_actual = top + 1
                fixed.append((seq.name, nxt, top + 1))
                _logger.info(
                    "td_live_production: послідовність «%s» %s → %s (є імена до %s)", seq.name, nxt, top + 1, top
                )
        return fixed
