from odoo import api, models
from odoo.exceptions import AccessError, ValidationError

from ..services.schemas import SchemaError

MANAGER_XMLID = 'factory3d_constructor.group_f3d_constructor_manager'
ETAG_FORMAT = '%Y-%m-%d %H:%M:%S.%f'


class F3dDraftMixin(models.AbstractModel):
    """Спільна поведінка сутностей чернетки (layer, slot, placement, check.config).

    Лічильник R-21, права R-11, нормалізація JSON R-22."""

    _name = 'f3d.draft.mixin'
    _description = "Чернетка площадки: лічильник правок і права"

    # --- права (R-11) ---------------------------------------------------------------------------------
    @api.model
    def _f3d_is_manager(self):
        return self.env.su or self.env.user.has_group(MANAGER_XMLID)

    @api.model
    def _f3d_can_edit_layer(self, layer):
        if self._f3d_is_manager():
            return True
        return bool(layer.sudo().edit_group_ids & self.env.user.all_group_ids)

    @api.model
    def _f3d_assert_layers(self, layers):
        """Другий бар'єр поверх ir.rule (пропускається при sudo): зрозуміле повідомлення про те, хто редагує шар."""
        if self.env.su:
            return
        for layer in layers:
            if not self._f3d_can_edit_layer(layer):
                groups = layer.sudo().edit_group_ids
                raise AccessError(
                    "Шар «%s» редагує: %s." % (layer.name, ", ".join(groups.mapped('name')) or "менеджер")
                )

    @api.model
    def _f3d_assert_manager(self, what="Цю дію"):
        if not self._f3d_is_manager():
            raise AccessError("%s може виконати лише менеджер конструктора." % what)

    # --- R-22: нормалізація JSON ---------------------------------------------------------------------
    def _f3d_normalize_vals(self, vals):
        return vals

    @api.model
    def _f3d_normalized(self, vals):
        try:
            return self._f3d_normalize_vals(dict(vals))
        except SchemaError as exc:
            raise ValidationError(str(exc)) from None

    # --- R-21: лічильник чернетки --------------------------------------------------------------------
    def _f3d_touch_sites(self, counts=None):
        if self.env.context.get('f3d_no_touch'):
            return
        if counts is None:
            counts = {}
            for rec in self:
                counts[rec.site_id.id] = counts.get(rec.site_id.id, 0) + 1
        for site_id, n in counts.items():
            if site_id:
                self.env['f3d.site'].browse(site_id)._f3d_touch(n)

    def _f3d_etag(self):
        self.ensure_one()
        return self.write_date.strftime(ETAG_FORMAT) if self.write_date else ''

    # --- перевірки на create / write / unlink: перевизначаються в моделях -----------------------------
    @api.model
    def _f3d_check_create(self, vals_list):
        pass

    def _f3d_check_write(self, vals):
        pass

    def _f3d_check_unlink(self):
        pass

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [self._f3d_normalized(vals) for vals in vals_list]
        self._f3d_check_create(vals_list)
        records = super().create(vals_list)
        records._f3d_touch_sites()
        return records

    def write(self, vals):
        if not self:
            return True
        vals = self._f3d_normalized(vals)
        self._f3d_check_write(vals)
        res = super().write(vals)
        self._f3d_touch_sites()
        return res

    def unlink(self):
        self._f3d_check_unlink()
        counts = {}
        for rec in self:
            counts[rec.site_id.id] = counts.get(rec.site_id.id, 0) + 1
        res = super().unlink()
        self._f3d_touch_sites(counts)
        return res
