from odoo import fields, models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    f3d_dock_id = fields.Many2one(
        'stock.location', related='batch_id.dock_id', string='Ворота', readonly=True)
    f3d_dock_code = fields.Char(
        related='batch_id.dock_id.f3d_code', string='Код воріт', readonly=True)
    f3d_truck = fields.Char(related='batch_id.f3d_truck', string='Фура', readonly=True)
    f3d_truck_code = fields.Char(related='batch_id.f3d_code', string='Код фури в 3D', readonly=True)
    f3d_vehicle_id = fields.Many2one(
        'maintenance.equipment', related='batch_id.f3d_vehicle_id', string='Техніка', readonly=True)
