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

    _f3d_version_n_uniq = models.Constraint('UNIQUE(site_id, n)', "Номер версії має бути унікальним на площадці.")

    @api.depends('state', 'site_id.draft_base_version_id')
    def _compute_is_draft_base(self):
        for ver in self:
            ver.is_draft_base = ver.state == 'active' and ver.site_id.draft_base_version_id == ver

    @api.depends('n', 'site_id.name')
    def _compute_display_name(self):
        for ver in self:
            ver.display_name = "v%d · %s" % (ver.n, ver.site_id.name or '')

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
