from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    td_expected_date = fields.Datetime(compute='_compute_td_expected_date')


class TdMebliMarginReport(models.Model):
    _name = 'td.mebli.margin.report'

    name = fields.Char()
    order_id = fields.Many2one('sale.order')


class TdMebliCatalog(models.Model):
    _name = 'td.mebli.catalog'

    name = fields.Char()
