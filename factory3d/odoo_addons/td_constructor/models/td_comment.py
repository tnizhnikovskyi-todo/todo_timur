from odoo import fields, models

COMMENT_TARGET_SELECTION = [
    ('site', "Площадка"),
    ('layer', "Шар"),
    ('slot', "Місце"),
    ('cell', "Комірка"),
    ('placement', "Розміщення"),
]


class TdComment(models.Model):
    """Коментар або задача на об'єкті чернетки (F13); об'єкт — за `target_uid`, бо записів Odoo в чернетки немає."""

    _name = 'td.comment'
    _description = "Коментар конструктора"
    _order = 'site_id, state, id desc'

    site_id = fields.Many2one('td.site', string="Площадка", required=True, ondelete='cascade', index=True)
    target_kind = fields.Selection(COMMENT_TARGET_SELECTION, string="Об'єкт", required=True, default='slot')
    target_uid = fields.Char(
        string="UID об'єкта", size=64, index=True, help="UID шару/місця/розміщення або код комірки"
    )
    target_label = fields.Char(string="Підпис об'єкта")
    kind = fields.Selection([('note', "Коментар"), ('task', "Задача")], string="Вид", required=True, default='note')
    state = fields.Selection(
        [('open', "Відкрито"), ('resolved', "Вирішено")], string="Стан", required=True, default='open', index=True
    )
    text = fields.Text(string="Текст", required=True)
    author_id = fields.Many2one(
        'res.users', string="Автор", required=True, default=lambda self: self.env.user, ondelete='restrict'
    )
    resolved_by_id = fields.Many2one('res.users', string="Вирішив", readonly=True, copy=False, ondelete='set null')
    resolved_at = fields.Datetime(string="Вирішено", readonly=True, copy=False)
    company_id = fields.Many2one('res.company', related='site_id.company_id', store=True, index=True)
    active = fields.Boolean(default=True)
