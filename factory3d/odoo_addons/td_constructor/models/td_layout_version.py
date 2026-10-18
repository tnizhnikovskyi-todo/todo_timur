from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError


class F3dLayoutVersion(models.Model):
    _name = 'td.layout.version'
    _description = "Версія планування"
    _order = 'site_id, n desc'

    site_id = fields.Many2one('td.site', string="Площадка", required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one('res.company', related='site_id.company_id', store=True, index=True)
    n = fields.Integer(string="№", required=True, readonly=True)
    note = fields.Text(string="Нотатка")
    published_by_id = fields.Many2one('res.users', string="Опублікував", readonly=True)
    published_at = fields.Datetime(string="Опубліковано", readonly=True, default=fields.Datetime.now)
    state = fields.Selection(
        [('active', "Діюча"), ('superseded', "Замінена")], string="Стан", default='active', required=True
    )
    snapshot_id = fields.Many2one('ir.attachment', string="Знімок", ondelete='set null', copy=False)
    snapshot_sha1 = fields.Char(string="SHA-1 знімка", size=40, readonly=True)
    draft_rev = fields.Integer(string="Лічильник чернетки", readonly=True)
    slot_count = fields.Integer(string="Місць", readonly=True)
    cell_count = fields.Integer(string="Комірок", readonly=True)
    placement_count = fields.Integer(string="Розміщень", readonly=True)
    layer_count = fields.Integer(string="Шарів", readonly=True)
    created_count = fields.Integer(string="Створено", readonly=True)
    updated_count = fields.Integer(string="Оновлено", readonly=True)
    archived_count = fields.Integer(string="Архівовано", readonly=True)
    report = fields.Json(string="Звіт", readonly=True)
    is_seed = fields.Boolean(string="Імпорт із макета", readonly=True)
    is_draft_base = fields.Boolean(
        string="База чернетки",
        compute='_compute_is_draft_base',
        help="Діюча версія, на якій уже ґрунтується чернетка: відновлювати нічого",
    )
    # --- MERGE.md §3.3 (волни 1–2): поля без логіки; наповнюють слайси ---------------------------------
    kind = fields.Selection(
        [('publish', "Публікація"), ('checkpoint', "Контрольна точка")],
        string="Вид",
        required=True,
        default='publish',
        index=True,
        help="Контрольна точка — знімок чернетки без змін в Odoo (N-03)",
    )
    variant_id = fields.Many2one(
        'td.layout.variant', string="Варіант", readonly=True, copy=False, ondelete='set null', index=True
    )
    rolled_back_at = fields.Datetime(string="Відкочено", readonly=True, copy=False)
    rolled_back_by_id = fields.Many2one('res.users', string="Відкотив", readonly=True, copy=False)
    op_ids = fields.One2many('td.publish.op', 'version_id', string="Операції публікації", readonly=True)
    metrics = fields.Json(string="Цифри для порівняння", readonly=True, copy=False)
    op_count = fields.Integer(string="Операцій в Odoo", compute='_compute_rollback')
    can_rollback = fields.Boolean(string="Можна відкотити", compute='_compute_rollback')
    rollback_reason = fields.Char(string="Чому не можна відкотити", compute='_compute_rollback')

    _f3d_version_n_uniq = models.Constraint('UNIQUE(site_id, n)', "Номер версії має бути унікальним на площадці.")

    @api.depends('state', 'site_id.draft_base_version_id')
    def _compute_is_draft_base(self):
        for ver in self:
            ver.is_draft_base = ver.state == 'active' and ver.site_id.draft_base_version_id == ver

    @api.depends('n', 'site_id.name')
    def _compute_display_name(self):
        for ver in self:
            ver.display_name = "v%d · %s" % (ver.n, ver.site_id.name or '')

    def _compute_rollback(self):
        """F02-08: чи можна відкотити публікацію (створене не використано, немає пізнішої з тими самими кодами)."""
        from ..services import publish

        for ver in self:
            ver.op_count = len(ver.op_ids)
            problems = publish.rollback_problems(ver.sudo()) if ver.id and ver.op_ids and not ver.rolled_back_at else []
            ver.can_rollback = bool(ver.op_ids) and not ver.rolled_back_at and not problems
            ver.rollback_reason = (
                "Версію вже відкочено" if ver.rolled_back_at else problems[0]['reason'] if problems else False
            )

    def action_rollback(self):
        """F02-08: відкотити публікацію — обернені операції в Odoo (менеджер); чернетка не змінюється."""
        from ..services import publish

        self.ensure_one()
        self.site_id._f3d_check_rights_manager()
        result = publish.rollback_version(self.site_id, self)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'message': "Відкочено операцій: %d. Чернетка не змінена: наступний план запропонує зміни знову."
                % result['reverted'],
                'next': {
                    'type': 'ir.actions.act_window',
                    'res_model': self._name,
                    'res_id': self.id,
                    'view_mode': 'form',
                    'views': [(False, 'form')],
                },
            },
        }

    def write(self, vals):
        """Історію не переписуємо: користувач (менеджер) міняє лише `note`; решту пишуть публікація й хук (sudo)."""
        if not self.env.su and set(vals) - {'note'}:
            raise AccessError("Версію планування змінювати не можна: лише нотатку.")
        return super().write(vals)

    def action_restore_draft(self):
        """R-14: повернути чернетку до версії (менеджер)."""
        self.ensure_one()
        self.site_id._f3d_check_rights_manager()
        from ..services import snapshot

        snapshot.restore_draft(self)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'td.site',
            'res_id': self.site_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_download_snapshot(self):
        self.ensure_one()
        if not self.snapshot_id:
            raise UserError("У версії немає знімка.")
        return {
            'type': 'ir.actions.act_url',
            'target': 'self',
            'url': '/web/content/%d?download=true' % self.snapshot_id.id,
        }
