from odoo import fields, models

CHECK_KEY_SELECTION = [
    ('fits', "Вміщується"), ('collide', "Перетини"), ('service_free', "Зона обслуговування вільна"),
    ('aisles_free', "Проходи вільні"), ('load', "Навантаження"), ('utility_reach', "Досяжність підключення"),
    ('fire', "Пожежні проходи й виходи"),
]
CHECK_MODE_SELECTION = [('warn', "Попередження"), ('block', "Заборона")]


class F3dCheckConfig(models.Model):
    _name = 'f3d.check.config'
    _description = "Перевірка розкладки"
    _order = 'site_id, sequence'

    site_id = fields.Many2one('f3d.site', string="Площадка", required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one('res.company', related='site_id.company_id', store=True, index=True)
    check_key = fields.Selection(CHECK_KEY_SELECTION, string="Перевірка", required=True)
    sequence = fields.Integer(default=10)
    enabled = fields.Boolean(string="Увімкнено", default=True)
    mode = fields.Selection(CHECK_MODE_SELECTION, string="Режим", required=True, default='warn')
    params = fields.Json(string="Параметри", default=dict)

    _f3d_check_uniq = models.Constraint(
        'UNIQUE(site_id, check_key)', "Перевірка вже налаштована для площадки.")
