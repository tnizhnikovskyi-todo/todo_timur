from odoo import fields, models


class TdLayoutVariant(models.Model):
    """Варіант планування (F12, O-04): гілка чернетки як знімок; історія публікацій лишається в `td.layout.version`."""

    _name = 'td.layout.variant'
    _description = "Варіант планування"
    _order = 'site_id, sequence, id'

    site_id = fields.Many2one('td.site', string="Площадка", required=True, ondelete='cascade', index=True)
    name = fields.Char(string="Назва", required=True)
    sequence = fields.Integer(default=10)
    snapshot_id = fields.Many2one('ir.attachment', string="Знімок", ondelete='set null', copy=False)
    base_version_id = fields.Many2one(
        'td.layout.version', string="Базова версія", ondelete='set null', copy=False, index=True
    )
    is_training = fields.Boolean(string="Навчальний", default=False, help="Навчальний варіант не публікується в Odoo")
    metrics = fields.Json(string="Цифри для порівняння", copy=False)
    company_id = fields.Many2one('res.company', related='site_id.company_id', store=True, index=True)
    active = fields.Boolean(default=True)
