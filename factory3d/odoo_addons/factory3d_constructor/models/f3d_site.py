import re

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from ..services.checks import CHECK_DEFAULTS


class F3dSite(models.Model):
    _name = 'f3d.site'
    _description = "Площадка"
    _order = 'sequence, name'
    _rec_name = 'name'
    _rec_names_search = ['name', 'code']
    _check_company_auto = True

    name = fields.Char(string="Назва", required=True)
    code = fields.Char(
        string="Код", size=16, required=True, index=True,
        help="Префікс площадки для сторонніх кодів: латиниця великими літерами й цифри")
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one(
        'res.company', string="Компанія", required=True, index=True, default=lambda self: self.env.company)
    building_length_m = fields.Float(string="Довжина будівлі, м", digits=(10, 3), required=True, default=60.0)
    building_width_m = fields.Float(string="Ширина будівлі, м", digits=(10, 3), required=True, default=30.0)
    building_height_m = fields.Float(string="Висота будівлі, м", digits=(10, 3), required=True, default=8.0)
    column_step_x_m = fields.Float(string="Крок колон по X, м", digits=(10, 3), default=6.0)
    column_step_y_m = fields.Float(string="Крок колон по Y, м", digits=(10, 3), default=6.0)
    default_parent_location_id = fields.Many2one(
        'stock.location', string="Батьківська локація за замовчуванням", check_company=True,
        domain=[('usage', 'in', ('internal', 'view'))],
        help="Куди публікуються комірки, у яких не задано батьківську локацію місця")
    layer_ids = fields.One2many('f3d.layer', 'site_id', string="Шари")
    check_config_ids = fields.One2many('f3d.check.config', 'site_id', string="Перевірки")
    version_ids = fields.One2many('f3d.layout.version', 'site_id', string="Версії")
    active_version_id = fields.Many2one(
        'f3d.layout.version', string="Діюча версія", readonly=True, copy=False, ondelete='set null')
    draft_base_version_id = fields.Many2one(
        'f3d.layout.version', string="База чернетки", readonly=True, copy=False, ondelete='set null')
    draft_rev = fields.Integer(string="Лічильник правок", default=0, readonly=True, copy=False)
    draft_changes = fields.Integer(string="Змінено від діючої версії", default=0, readonly=True, copy=False)
    published_rev = fields.Integer(string="Лічильник на момент публікації", readonly=True, copy=False)
    has_changes = fields.Boolean(
        string="Є непубліковані зміни", compute='_compute_has_changes', search='_search_has_changes')
    seed_key = fields.Char(string="Ключ seed", size=32, copy=False, readonly=True)
    slot_count = fields.Integer(string="Місць", compute='_compute_counts')
    placement_count = fields.Integer(string="Розміщень", compute='_compute_counts')
    layer_count = fields.Integer(string="Шарів", compute='_compute_counts')
    version_count = fields.Integer(string="Версій", compute='_compute_counts')
    active = fields.Boolean(default=True)

    _f3d_site_code_uniq = models.Constraint(
        'UNIQUE(company_id, code)', "Код площадки має бути унікальним у компанії.")
    _f3d_site_seed_uniq = models.Constraint(
        'UNIQUE(seed_key)', "Seed-площадка вже існує.")

    @api.depends('draft_rev', 'published_rev')
    def _compute_has_changes(self):
        for site in self:
            site.has_changes = site.draft_rev != site.published_rev

    def _search_has_changes(self, operator, value):
        if operator not in ('=', '!='):
            raise UserError("Непідтримуваний оператор пошуку.")
        want = bool(value) == (operator == '=')
        self.env.cr.execute(
            "SELECT id FROM f3d_site WHERE (draft_rev IS DISTINCT FROM published_rev) = %s", (want,))
        return [('id', 'in', [row[0] for row in self.env.cr.fetchall()])]

    def _compute_counts(self):
        def counts(model):
            return dict(self.env[model].with_context(active_test=False)._read_group(
                [('site_id', 'in', self.ids)], ['site_id'], ['__count']))
        slots, placements = counts('f3d.slot'), counts('f3d.placement')
        layers, versions = counts('f3d.layer'), counts('f3d.layout.version')
        for site in self:
            site.slot_count = slots.get(site, 0)
            site.placement_count = placements.get(site, 0)
            site.layer_count = layers.get(site, 0)
            site.version_count = versions.get(site, 0)

    @api.constrains('building_length_m', 'building_width_m', 'building_height_m', 'column_step_x_m', 'column_step_y_m')
    def _check_dimensions(self):
        for site in self:
            if min(site.building_length_m, site.building_width_m, site.building_height_m) <= 0:
                raise ValidationError("Розміри будівлі мають бути додатними.")
            if site.column_step_x_m <= 0 or site.column_step_y_m <= 0:
                raise ValidationError("Крок колон має бути додатним.")

    @api.constrains('code')
    def _check_code(self):
        for site in self:
            if not re.match(r'^[A-Z0-9]+$', site.code or ''):
                raise ValidationError("Код площадки: лише великі латинські літери й цифри.")

    # --- create / службові -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        sites = super().create(vals_list)
        sites._f3d_init_checks()
        if self.env.context.get('f3d_blank'):
            sites._f3d_init_blank()
        return sites

    def _f3d_init_checks(self):
        """R-04: 7 рядків f3d.check.config (ідемпотентно)."""
        Config = self.env['f3d.check.config'].sudo()
        for site in self:
            have = set(Config.with_context(active_test=False).search([('site_id', '=', site.id)]).mapped('check_key'))
            vals = [{
                'site_id': site.id, 'check_key': key, 'sequence': (idx + 1) * 10,
                'enabled': enabled, 'mode': mode, 'params': dict(params),
            } for idx, (key, enabled, mode, params) in enumerate(CHECK_DEFAULTS) if key not in have]
            if vals:
                Config.create(vals)

    def _f3d_init_blank(self):
        """R-23: 5 базових шарів порожньої площадки (реалізація — у наступному коміті)."""
        return True

    def _f3d_touch(self, n=1):
        """R-21: лічильник чернетки без зміни write_date площадки."""
        ids = [rid for rid in self.ids if rid]
        if not ids:
            return
        self.env.cr.execute(
            "UPDATE f3d_site SET draft_rev = draft_rev + 1, draft_changes = draft_changes + %s WHERE id IN %s",
            (n, tuple(ids)))
        self.invalidate_recordset(['draft_rev', 'draft_changes', 'has_changes'])

    def _f3d_check_rights_manager(self):
        if not (self.env.su or self.env.user.has_group('factory3d_constructor.group_f3d_constructor_manager')):
            raise AccessError("Лише менеджер конструктора може виконати цю дію.")

    # --- дії -----------------------------------------------------------------------------------------
    def action_open_constructor(self):
        self.ensure_one()
        return {'type': 'ir.actions.client', 'tag': 'f3d_constructor', 'name': "Конструктор",
                'params': {'site_id': self.id}}

    def action_publish_wizard(self):
        """Створює майстер публікації (M-08); план будується в `wizard.f3d_publish_wizard`."""
        self.ensure_one()
        self._f3d_check_rights_manager()
        wizard = self.env['f3d.publish.wizard'].create({'site_id': self.id})
        wizard._f3d_rebuild()
        return wizard._f3d_action()

    def action_open_layers(self):
        return self._f3d_action_list('f3d.layer', "Шари")

    def action_open_slots(self):
        return self._f3d_action_list('f3d.slot', "Місця")

    def action_open_placements(self):
        return self._f3d_action_list('f3d.placement', "Розміщення")

    def action_open_versions(self):
        return self._f3d_action_list('f3d.layout.version', "Версії планування")

    def _f3d_action_list(self, model, name):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': name, 'res_model': model, 'view_mode': 'list,form',
            'domain': [('site_id', '=', self.id)], 'context': {'default_site_id': self.id},
        }
