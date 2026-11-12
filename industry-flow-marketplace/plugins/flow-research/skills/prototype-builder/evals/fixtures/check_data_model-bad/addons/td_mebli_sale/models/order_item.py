from odoo import fields, models


class TdMebliOrderItem(models.Model):
    _name = 'td.mebli.order.item'

    order_id = fields.Many2one('sale.order.line')
    supplier_id = fields.Many2one('res.partner')
    delivery_date = fields.Date()


class TdMebliMarginReport(models.Model):
    _name = 'td.mebli.margin.report'

    name = fields.Char()


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    td_supplier_note = fields.Char()


class TdMebliOrder(models.Model):
    _name = 'td.mebli.order'

    name = fields.Char()


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    td_vendor_id = fields.Many2one('res.partner')
    td_vendor_date = fields.Date()
    td_ready: fields.Date = fields.Date(compute='_compute_td_ready')


class TdMebliMarginReportExt(models.Model):
    _inherit = 'td.mebli.margin.report'

    extra = fields.Char()


class MebliOrderItem(models.Model):
    _name = 'mebli.order.item'

    name = fields.Char()


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    td_carrier_date = Date()
