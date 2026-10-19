from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError

MANAGER_XMLID = 'td_constructor.group_td_constructor_manager'
# Цифри порівняння рахує ядро (JS) за станом активного варіанта й надсилає разом із перемиканням: лише числа (§2.7)
METRIC_KEYS = ('cells', 'places', 'area', 'volume', 'max_weight')


class TdLayoutVariant(models.Model):
    """Варіант планування (F12, O-04): гілка чернетки як знімок; історія публікацій лишається в `td.layout.version`.

    Чернетка площадки — «живі» записи шарів/місць/розміщень. Активний варіант (`site.active_variant_id`) — той, що
    зараз у
    чернетці; його знімок оновлюється, коли з нього йдуть. Решта варіантів — лише знімки (формат R-14). Перемикання =
    знімок поточної гілки → `apply_snapshot` вибраної: чернетка не втрачається."""

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
    origin_id = fields.Many2one(
        'td.layout.variant',
        string="Створено з",
        ondelete='set null',
        copy=False,
        help="Варіант, до якого повертає «Скасувати» навчальної копії (F19-04)",
    )
    metrics = fields.Json(string="Цифри для порівняння", copy=False)
    company_id = fields.Many2one('res.company', related='site_id.company_id', store=True, index=True)
    active = fields.Boolean(default=True)
    is_current = fields.Boolean(string="Активний", compute='_compute_is_current')

    @api.depends('site_id.active_variant_id')
    def _compute_is_current(self):
        for variant in self:
            variant.is_current = bool(variant.id) and variant.site_id.active_variant_id == variant

    # --- параметри й права -------------------------------------------------------------------------------
    @api.model
    def _f3d_max(self):
        try:
            return max(1, int(self.env['ir.config_parameter'].sudo().get_param('td.constructor.variants_max', 12)))
        except (TypeError, ValueError):
            return 12

    @api.model
    def _f3d_assert_manager(self):
        """Варіантами керує менеджер (MERGE.md §3.5): чернетка спільна, перемикання підмінює її для всіх."""
        if not (self.env.su or self.env.user.has_group(MANAGER_XMLID)):
            raise AccessError("Варіантами планування керує лише менеджер конструктора.")

    @api.model
    def _f3d_clean_metrics(self, metrics):
        out = {}
        for key in METRIC_KEYS:
            value = (metrics or {}).get(key)
            if isinstance(value, int | float) and not isinstance(value, bool):
                out[key] = round(float(value), 3)
        return out

    # --- знімки ---------------------------------------------------------------------------------------------
    def _f3d_write_snapshot(self, metrics=None):
        """Записує знімок ПОТОЧНОЇ чернетки площадки у варіанти (R-14) і базову версію; `metrics` — цифри ядра."""
        from ..services import snapshot

        Attachment = self.env['ir.attachment'].sudo()
        for variant in self.sudo():
            site = variant.site_id
            raw, _sha1 = snapshot.dump_snapshot(snapshot.build_snapshot(site))
            if variant.snapshot_id:
                variant.snapshot_id.write({'raw': raw})
            else:
                variant.snapshot_id = Attachment.create(
                    {
                        'name': 'f3d_variant_%s_%d.json' % (site.code, variant.id),
                        'raw': raw,
                        'mimetype': 'application/json',
                        'res_model': 'td.layout.variant',
                        'res_id': variant.id,
                        'type': 'binary',
                    }
                )
            vals = {'base_version_id': site.draft_base_version_id.id or False}
            if metrics is not None:
                vals['metrics'] = dict(variant.metrics or {}, **self._f3d_clean_metrics(metrics))
            variant.write(vals)
        return True

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        # створений без знімка (наприклад, у списку Odoo): «з поточного» — знімок чернетки
        records.filtered(lambda v: not v.snapshot_id)._f3d_write_snapshot()
        return records

    def unlink(self):
        """Видалення активного варіанта очищає посилання на нього (ondelete=set null); `f3d_ensure` потім бере перший
        робочий. Заборона «активний не видаляється» діє в API-21 (редактор), а не тут: так працює й список Odoo."""
        return super().unlink()  # вкладення знімка (res_model/res_id) Odoo видаляє разом із записом

    # --- API-21: операції (викликає контролер; права — менеджер) ---------------------------------------
    @api.model
    def f3d_ensure(self, site):
        """«Як є»: перший варіант площадки (знімок поточної чернетки), якщо варіантів ще немає."""
        site = site.sudo()
        if site.active_variant_id and site.active_variant_id.exists():
            return site.active_variant_id
        existing = self.sudo().search([('site_id', '=', site.id), ('is_training', '=', False)], limit=1)
        if existing:
            site.active_variant_id = existing
            return existing
        variant = self.sudo().create({'site_id': site.id, 'name': "Як є", 'sequence': 10})
        site.active_variant_id = variant
        return variant

    @api.model
    def f3d_make(self, site, name, training=False, activate=True, metrics=None):
        """«Створити з поточного»: новий варіант = копія чернетки; за `activate` робота триває в ньому."""
        self._f3d_assert_manager()
        site = site.sudo()
        name = (name or '').strip()
        if not name:
            raise UserError("Вкажіть назву варіанта.")
        current = self.f3d_ensure(site)
        Variant = self.sudo()
        if training:
            if Variant.search_count([('site_id', '=', site.id), ('is_training', '=', True)]):
                raise UserError("Навчальна копія вже існує: завершіть або скасуйте її.")
        else:
            if Variant.search_count([('site_id', '=', site.id), ('is_training', '=', False)]) >= self._f3d_max():
                raise UserError("Не більше %d варіантів на площадку." % self._f3d_max())
            if Variant.search_count([('site_id', '=', site.id), ('is_training', '=', False), ('name', '=ilike', name)]):
                raise UserError("Варіант «%s» уже існує." % name)
        last = Variant.search([('site_id', '=', site.id)], order='sequence desc, id desc', limit=1)
        variant = Variant.create(
            {
                'site_id': site.id,
                'name': name,
                'sequence': (last.sequence or 0) + 10,
                'is_training': bool(training),
                'origin_id': current.id if training else False,
            }
        )
        if metrics is not None:
            variant.metrics = self._f3d_clean_metrics(metrics)
        if activate:
            current._f3d_write_snapshot(metrics)  # поточна гілка лишається знімком у попередньому варіанті
            site.active_variant_id = variant
            variant._f3d_write_snapshot(metrics)
        return variant

    def f3d_activate(self, metrics=None):
        """Зробити варіант активним: знімок поточної гілки → відновлення вибраної (чернетка не втрачається)."""
        from ..services import snapshot

        self._f3d_assert_manager()
        self.ensure_one()
        site = self.site_id.sudo()
        current = self.f3d_ensure(site)
        if current == self:
            return self
        if not self.snapshot_id:
            raise UserError("У варіанта «%s» немає знімка." % self.name)
        target = snapshot.load_snapshot(self)
        with self.env.cr.savepoint():
            current._f3d_write_snapshot(metrics)
            snapshot.apply_snapshot(site, target)
            active = site.active_version_id
            base = self.base_version_id if self.base_version_id.exists() else active
            changes = (
                snapshot.count_differences(target, snapshot.load_snapshot(active))
                if active and active.snapshot_id
                else 0
            )
            site.write(
                {
                    'active_variant_id': self.id,
                    'draft_base_version_id': base.id or False,
                    'draft_rev': site.draft_rev + 1,
                    'draft_changes': changes,
                }
            )
        return self

    def f3d_end_training(self, keep=False):
        """Кінець навчальної копії (F19-04): «Залишити зміни» робить її звичайним варіантом, «Скасувати» повертає
        роботу у варіант-джерело й видаляє копію."""
        self._f3d_assert_manager()
        self.ensure_one()
        if not self.is_training:
            raise UserError("Це не навчальна копія.")
        site = self.site_id.sudo()
        if keep:
            self.sudo().write({'is_training': False})
            self.sudo()._f3d_write_snapshot()
            return self
        origin = self.origin_id if self.origin_id.exists() else self.browse()
        if not origin:
            origin = self.sudo().search(
                [('site_id', '=', site.id), ('is_training', '=', False)], order='sequence, id', limit=1
            )
        if site.active_variant_id == self:
            if not origin:
                raise UserError("Немає варіанта, до якого повернутися.")
            origin.f3d_activate()
        self.sudo().unlink()
        return origin

    # --- подання ----------------------------------------------------------------------------------------------
    def f3d_dict(self, ops=None):
        self.ensure_one()
        return {
            'id': self.id,
            'name': self.name,
            'is_training': self.is_training,
            'active': self.site_id.active_variant_id == self,
            'origin_id': self.origin_id.id or None,
            'base_version': self.base_version_id.n if self.base_version_id else None,
            'metrics': dict(self.metrics or {}, ops=ops),
            'by': self.create_uid.name or '',
            'at': str(self.create_date) if self.create_date else '',
        }


class TdLayoutVersionVariant(models.Model):
    """Публікація пише `variant_id` у версію (O-04); навчальна копія не публікується (F19-04)."""

    _inherit = 'td.layout.version'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            site = self.env['td.site'].sudo().browse(vals.get('site_id'))
            variant = site.active_variant_id if site else False
            if variant and (vals.get('kind') or 'publish') == 'publish':
                if variant.is_training:
                    raise UserError("Навчальна копія не публікується в Odoo: перемкніться на робочий варіант.")
                vals.setdefault('variant_id', variant.id)
        return super().create(vals_list)
