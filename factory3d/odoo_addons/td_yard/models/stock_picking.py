from odoo import api, fields, models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    td_visit_id = fields.Many2one("td.yard.visit", string="Рейс двору", related="batch_id.td_visit_id")
    td_net_weight_kg = fields.Float(string="Нетто з автоваг, кг", digits=(12, 1), readonly=True, copy=False)
    td_expected_weight_kg = fields.Float(
        string="Маса за документом, кг", digits=(12, 1), compute="_compute_f3d_expected"
    )
    td_weight_check = fields.Selection(
        [("none", "Не зважено"), ("ok", "У допуску"), ("deviation", "Відхилення"), ("no_reference", "Немає еталона")],
        string="Звірка ваги",
        readonly=True,
        copy=False,
        default="none",
    )
    td_weight_deviation_pct = fields.Float(string="Відхилення, %", digits=(6, 2), readonly=True, copy=False)

    @api.depends("move_ids.product_qty", "move_ids.quantity", "move_ids.product_id.weight", "state")
    def _compute_f3d_expected(self):
        for picking in self:
            picking.td_expected_weight_kg = picking._f3d_expected_kg()[0]

    def _f3d_expected_kg(self):
        """(маса документа, кг; чи є еталон — усі рухи мають product.weight > 0) — R-12 п. 2."""
        self.ensure_one()
        kgm = self.env.ref("uom.product_uom_kgm")
        weight_uom = self.env["product.template"]._get_weight_uom_id_from_ir_config_parameter()
        moves = self.move_ids.filtered(lambda m: m.state != "cancel")
        total, has_ref = 0.0, bool(moves)
        for move in moves:
            product = move.product_id
            if product.weight <= 0:
                has_ref = False
            if self.state == "done":
                qty = move.product_uom._compute_quantity(move.quantity, product.uom_id)
            else:
                qty = move.product_qty
            total += qty * weight_uom._compute_quantity(product.weight, kgm)
        return total, has_ref

    def action_f3d_open_visit(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Рейс",
            "res_model": "td.yard.visit",
            "res_id": self.td_visit_id.id,
            "view_mode": "form",
        }

    def _action_done(self):
        batches = self.batch_id  # після super() готові документи можуть бути відчеплені від пакета
        res = super()._action_done()
        if not self.env.context.get("f3d_yard_no_auto"):
            for batch in batches:
                visit = batch.td_visit_id.sudo()
                if not visit or visit.state not in ("queued", "at_dock", "handling"):
                    continue
                if any(p.state not in ("done", "cancel") for p in batch.picking_ids):
                    continue
                if visit.state in ("queued", "at_dock"):
                    visit.action_start_handling(auto=True)
                if not visit.handling_end_at:
                    visit.write({"handling_end_at": fields.Datetime.now()})
                    visit.message_post(body="Документи проведено")
                visit.action_end_handling(auto=True)
        return res


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    def _f3d_yard_auto_start(self):
        if self.env.context.get("f3d_yard_no_auto"):
            return
        for line in self.filtered(lambda ml: ml.quantity > 0 and ml.picking_id.batch_id):
            visit = line.picking_id.batch_id.td_visit_id.sudo()
            if visit.state in ("queued", "at_dock"):
                visit.action_start_handling(auto=True)

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        if any((vals.get("quantity") or 0) > 0 for vals in vals_list):
            lines._f3d_yard_auto_start()
        return lines

    def write(self, vals):
        res = super().write(vals)
        if "quantity" in vals and (vals["quantity"] or 0) > 0:
            self._f3d_yard_auto_start()
        return res
