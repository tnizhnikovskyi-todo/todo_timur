from odoo import api, fields, models


class StockPickingBatch(models.Model):
    _name = 'stock.picking.batch'
    _inherit = ['stock.picking.batch', 'f3d.scene.mixin']
    _f3d_kind = 'vehicle'
    _rec_names_search = ['name', 'f3d_code', 'f3d_truck']

    f3d_truck = fields.Char(
        string='Фура', size=64,
        help="Опис або назва фури з макета (не держномер і не код сцени). Код фури в 3D — "
             "«Код фури в 3D» (f3d_code); держномер веде модуль двору (рейс, f3d_plate).")
    f3d_vehicle_id = fields.Many2one(
        'maintenance.equipment', string='Техніка', ondelete='set null',
        domain="[('f3d_code', '!=', False)]",
        help='Навантажувач або тягач, що виконує пакет (FL-2, FL-6, TUGGER-1)')
    f3d_dock_code = fields.Char(related='dock_id.f3d_code', string='Код воріт', readonly=True)
    f3d_dock_warning = fields.Char(string='Попередження про ворота', compute='_compute_f3d_dock_warning')

    @api.depends('dock_id', 'dock_id.f3d_accepts', 'picking_ids.move_ids.product_id')
    def _compute_f3d_dock_warning(self):
        for batch in self:
            allowed = batch.dock_id.f3d_accepts
            if not allowed:
                batch.f3d_dock_warning = False
                continue
            bad = self.env['product.category']
            for move in batch.picking_ids.move_ids:
                categ = move.product_id.categ_id
                if categ and not any((categ.parent_path or '').startswith(a.parent_path or '\0')
                                     for a in allowed):
                    bad |= categ
            batch.f3d_dock_warning = bool(bad) and "Ворота %s приймають: %s. У пакеті є: %s." % (
                batch.dock_id.f3d_code, ', '.join(allowed.mapped('name')), ', '.join(bad.mapped('name')))
