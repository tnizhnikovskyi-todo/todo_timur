from odoo import api, fields, models

from ..models.f3d_check_config import CHECK_KEY_SELECTION


class F3dPublishWizard(models.TransientModel):
    _name = 'f3d.publish.wizard'
    _description = "Публікація розкладки"

    site_id = fields.Many2one('f3d.site', string="Площадка", required=True, readonly=True, ondelete='cascade')
    note = fields.Text(string="Нотатка до версії")
    draft_rev = fields.Integer(string="Лічильник чернетки", readonly=True)
    state = fields.Selection(
        [('preview', "Попередній перегляд"), ('done', "Опубліковано")], default='preview', required=True)
    line_ids = fields.One2many('f3d.publish.wizard.line', 'wizard_id', string="План")
    change_line_ids = fields.One2many(
        'f3d.publish.wizard.line', 'wizard_id', string="Буде створено / оновлено", domain=[('kind', '!=', 'archive')])
    archive_line_ids = fields.One2many(
        'f3d.publish.wizard.line', 'wizard_id', string="Пропонуємо архівувати", domain=[('kind', '=', 'archive')])
    issue_ids = fields.One2many('f3d.publish.wizard.issue', 'wizard_id', string="Зауваження перевірок")
    n_create = fields.Integer(string="Буде створено", compute='_compute_counts')
    n_update = fields.Integer(string="Буде оновлено", compute='_compute_counts')
    n_archive = fields.Integer(string="Буде архівовано", compute='_compute_counts')
    n_archive_offer = fields.Integer(string="Пропонуємо архівувати", compute='_compute_counts')
    n_unchanged = fields.Integer(string="Без змін", default=0)
    n_warn = fields.Integer(string="Попереджень", compute='_compute_counts')
    n_block = fields.Integer(string="Заборон", compute='_compute_counts')
    can_publish = fields.Boolean(compute='_compute_counts')
    version_id = fields.Many2one('f3d.layout.version', string="Версія", readonly=True)

    @api.depends('line_ids.kind', 'line_ids.selected', 'issue_ids.severity', 'site_id.has_changes')
    def _compute_counts(self):
        enabled = self.env['ir.config_parameter'].sudo().get_param('factory3d.constructor.publish_enabled') == 'True'
        for wiz in self:
            lines, issues = wiz.line_ids, wiz.issue_ids
            wiz.n_create = len(lines.filtered(lambda r: r.kind == 'create'))
            wiz.n_update = len(lines.filtered(lambda r: r.kind == 'update'))
            wiz.n_archive_offer = len(lines.filtered(lambda r: r.kind == 'archive'))
            wiz.n_archive = len(lines.filtered(lambda r: r.kind == 'archive' and r.selected))
            wiz.n_warn = len(issues.filtered(lambda r: r.severity == 'warn'))
            wiz.n_block = len(issues.filtered(lambda r: r.severity == 'block'))
            wiz.can_publish = wiz.state == 'preview' and not wiz.n_block and wiz.site_id.has_changes and enabled

    def _f3d_rebuild(self):
        """Побудувати план публікації (R-12). Реалізація — у наступному коміті (services.publish)."""
        return True

    def _f3d_action(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': "Публікація розкладки", 'res_model': self._name,
            'res_id': self.id, 'view_mode': 'form', 'target': 'new',
        }

    def action_confirm(self):
        """Підтвердити й опублікувати (R-12). Реалізація — у наступному коміті."""
        self.ensure_one()
        return self._f3d_action()

    def action_cancel(self):
        return {'type': 'ir.actions.act_window_close'}


class F3dPublishWizardLine(models.TransientModel):
    _name = 'f3d.publish.wizard.line'
    _description = "Рядок плану публікації"
    _order = 'kind, res_model, code'

    wizard_id = fields.Many2one('f3d.publish.wizard', required=True, ondelete='cascade', index=True)
    kind = fields.Selection(
        [('create', "Буде створено"), ('update', "Буде оновлено"), ('archive', "Пропонуємо архівувати")],
        string="Дія", required=True)
    res_model = fields.Selection(
        [('stock.location', "Локація"), ('maintenance.equipment', "Обладнання"), ('mrp.workcenter', "Робочий центр")],
        string="Модель", required=True)
    code = fields.Char(string="Код")
    name = fields.Char(string="Назва")
    res_id = fields.Integer(string="ID запису", default=0)
    source_uid = fields.Char(string="UID джерела", default='')
    changes = fields.Text(string="Зміни")
    selected = fields.Boolean(string="Застосувати", default=True)
    blocked = fields.Boolean(string="Заблоковано", default=False)
    blocked_reason = fields.Char(string="Причина блокування")


class F3dPublishWizardIssue(models.TransientModel):
    _name = 'f3d.publish.wizard.issue'
    _description = "Зауваження перевірок публікації"
    _order = 'severity desc, check_key, id'

    wizard_id = fields.Many2one('f3d.publish.wizard', required=True, ondelete='cascade', index=True)
    check_key = fields.Selection(
        CHECK_KEY_SELECTION + [('conflict', "Конфлікт кодів"), ('data', "Дані")], string="Перевірка")
    severity = fields.Selection([('warn', "Попередження"), ('block', "Заборона")], string="Серйозність")
    layer_id = fields.Many2one('f3d.layer', string="Шар", ondelete='set null')
    codes = fields.Char(string="Коди")
    message = fields.Char(string="Повідомлення")
