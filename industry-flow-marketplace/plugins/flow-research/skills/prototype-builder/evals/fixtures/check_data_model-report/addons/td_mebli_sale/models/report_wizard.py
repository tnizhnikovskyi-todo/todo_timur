from odoo import models, fields


class ReportDoc(models.AbstractModel):
    _name = 'report.td_mebli_sale.report_doc'
    _description = 'Парсер QWeb-звіту'


class SqlReport(models.Model):
    _name = 'td.sale.sql.report'
    _description = 'SQL-звіт'
    _auto = False
    name = fields.Char()


class Wizard(models.TransientModel):
    _name = 'td.sale.wizard'
    _description = 'Майстер'
    note = fields.Char()
