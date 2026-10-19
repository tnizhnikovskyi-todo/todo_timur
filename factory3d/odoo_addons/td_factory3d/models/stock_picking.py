from odoo import fields, models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    td_dock_id = fields.Many2one("stock.location", related="batch_id.dock_id", string="Ворота", readonly=True)
    td_dock_code = fields.Char(related="batch_id.dock_id.td_code", string="Код воріт", readonly=True)
    td_truck = fields.Char(related="batch_id.td_truck", string="Фура", readonly=True)
    td_truck_code = fields.Char(related="batch_id.td_code", string="Код фури в 3D", readonly=True)
    td_vehicle_id = fields.Many2one(
        "maintenance.equipment", related="batch_id.td_vehicle_id", string="Техніка", readonly=True
    )
