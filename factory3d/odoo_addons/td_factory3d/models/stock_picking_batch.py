from odoo import api, fields, models


class StockPickingBatch(models.Model):
    _name = 'stock.picking.batch'
    _inherit = ['stock.picking.batch', 'td.scene.mixin']
    _f3d_kind = 'vehicle'
    _rec_names_search = ['name', 'td_code', 'td_truck']

    td_truck = fields.Char(
        string='Фура', size=64,
        help="Опис або назва фури з макета (не держномер і не код сцени). Код фури в 3D — "
             "«Код фури в 3D» (td_code); держномер веде модуль двору (рейс, td_plate).")
    td_vehicle_id = fields.Many2one(
        'maintenance.equipment', string='Техніка', ondelete='set null',
        domain="[('td_code', '!=', False)]",
        help='Навантажувач або тягач, що виконує пакет (FL-2, FL-6, TUGGER-1)')
    td_dock_code = fields.Char(related='dock_id.td_code', string='Код воріт', readonly=True)
    td_dock_warning = fields.Char(string='Попередження про ворота', compute='_compute_f3d_dock_warning')

    @api.depends('dock_id', 'dock_id.td_accepts', 'picking_ids.move_ids.product_id')
    def _compute_f3d_dock_warning(self):
        for batch in self:
            allowed = batch.dock_id.td_accepts
            if not allowed:
                batch.td_dock_warning = False
                continue
            bad = self.env['product.category']
            for move in batch.picking_ids.move_ids:
                categ = move.product_id.categ_id
                if categ and not any((categ.parent_path or '').startswith(a.parent_path or '\0')
                                     for a in allowed):
                    bad |= categ
            batch.td_dock_warning = bool(bad) and "Ворота %s приймають: %s. У пакеті є: %s." % (
                batch.dock_id.td_code, ', '.join(allowed.mapped('name')), ', '.join(bad.mapped('name')))
