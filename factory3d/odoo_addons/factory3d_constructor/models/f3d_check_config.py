from odoo import api, fields, models
from odoo.exceptions import ValidationError

from ..services import schemas

CHECK_KEY_SELECTION = [
    ('fits', "Вміщується"), ('collide', "Перетини"), ('service_free', "Зона обслуговування вільна"),
    ('aisles_free', "Проходи вільні"), ('load', "Навантаження"), ('utility_reach', "Досяжність підключення"),
    ('fire', "Пожежні проходи й виходи"),
]
CHECK_MODE_SELECTION = [('warn', "Попередження"), ('block', "Заборона")]


class F3dCheckConfig(models.Model):
    _name = 'f3d.check.config'
    _description = "Перевірка розкладки"
    _inherit = ['f3d.draft.mixin']
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

    def _f3d_normalize_vals(self, vals):
        if 'params' in vals:
            key = vals.get('check_key') or (self[:1].check_key if self else None)
            vals['params'] = schemas.normalize_check_params(key, vals['params'])
        return vals

    @api.model
    def _f3d_check_create(self, vals_list):
        self._f3d_assert_manager("Налаштовувати перевірки")

    def _f3d_check_write(self, vals):
        self._f3d_assert_manager("Налаштовувати перевірки")

    def _f3d_check_unlink(self):
        self._f3d_assert_manager("Налаштовувати перевірки")

    @api.constrains('params', 'check_key')
    def _check_params(self):
        for cfg in self:
            try:
                schemas.normalize_check_params(cfg.check_key, cfg.params)
            except schemas.SchemaError as exc:
                raise ValidationError(str(exc)) from None
