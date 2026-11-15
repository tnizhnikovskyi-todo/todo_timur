from odoo import api, fields, models
from odoo.models import AbstractModel


class ReportOrder(models.AbstractModel):
    _name = 'report.td_mebli_sale.report_order'
    _description = 'Order report parser'

    @api.model
    def _get_report_values(self, docids, data=None):
        return {}


class ReportOrder2(AbstractModel):
    _name = "report.td_mebli_sale.report_order2"
    _inherit = "report.report_xlsx.abstract"
    x = fields.Char()


class ReportExtend(models.AbstractModel):
    _inherit = "report.sale.report_saleorder"
    y = fields.Char()
