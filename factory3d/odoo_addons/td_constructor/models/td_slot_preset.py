from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError

from ..services import addr as addr_mod, cells as cells_mod
from ..services.schemas import SchemaError, check_json_limits

MANAGER_XMLID = 'td_constructor.group_td_constructor_manager'
PRESET_TEMPLATES = ('pallet_rack', 'cantilever', 'shelf', 'floor_stack', 'floor_spot', 'machine_spot')
COUNT_KEYS = {'pallet_rack': 'bays', 'cantilever': 'arms', 'shelf': 'sections', 'floor_stack': 'cols'}
MAX_GROUP = 200
SLOT_PRESET_KIND_SELECTION = [('row', "Ряд"), ('section', "Секція"), ('group', "Виділене")]


class TdSlotPreset(models.Model):
    """Пресет (F09-06/07): збережена настройка ряду, секції чи виділеного; бібліотека на компанію."""

    _name = 'td.slot.preset'
    _description = "Пресет місця"
    _order = 'name, id'

    name = fields.Char(string="Назва", required=True)
    type_id = fields.Many2one('td.slot.type', string="Тип місця", ondelete='set null', index=True)
    kind = fields.Selection(SLOT_PRESET_KIND_SELECTION, string="Вид", required=True, default='row')
    data = fields.Json(string="Дані пресету", default=dict)
    company_id = fields.Many2one(
        'res.company', string="Компанія", required=True, index=True, default=lambda self: self.env.company
    )
    active = fields.Boolean(default=True)

    # --- R-22: data пресету -----------------------------------------------------------------------------
    @api.model
    def _td_normalize_spec(self, spec):
        """Spec місця пресету: {template, params, rotation, type_code?, prefix?, dx?, dy?, addr?}."""
        if not isinstance(spec, dict) or spec.get('template') not in PRESET_TEMPLATES:
            raise ValidationError("Пресет: невідомий або непридатний генератор місця.")
        out = {'template': spec['template']}
        try:
            out['params'] = cells_mod.normalize_params(spec['template'], spec.get('params'))
        except cells_mod.CellsError as exc:
            raise ValidationError("Пресет: %s" % exc) from None
        rotation = spec.get('rotation') or 0
        if isinstance(rotation, bool) or not isinstance(rotation, (int, float)):
            raise ValidationError("Пресет: поворот має бути числом.")
        out['rotation'] = int(round(rotation)) % 360
        for key in ('type_code', 'prefix'):
            if spec.get(key):
                out[key] = str(spec[key])[:32]
        for key in ('dx', 'dy'):
            if spec.get(key) is not None:
                if isinstance(spec[key], bool) or not isinstance(spec[key], (int, float)):
                    raise ValidationError("Пресет: зсув має бути числом.")
                out[key] = float(spec[key])
        if spec.get('addr'):
            try:
                out['addr'] = addr_mod.normalize_addr(spec['addr'])
            except addr_mod.AddrError as exc:
                raise ValidationError("Пресет: %s" % exc) from None
        return out

    @api.model
    def _td_normalize_data(self, kind, data):
        if not isinstance(data, dict):
            raise ValidationError("Дані пресету мають бути об'єктом.")
        try:
            check_json_limits(data)
        except SchemaError as exc:
            raise ValidationError("Пресет: %s" % exc) from None
        if kind == 'group':
            slots = data.get('slots')
            if not isinstance(slots, list) or not 1 <= len(slots) <= MAX_GROUP:
                raise ValidationError("Пресет «Виділене»: від 1 до %d місць." % MAX_GROUP)
            return {'slots': [self._td_normalize_spec(spec) for spec in slots]}
        spec = self._td_normalize_spec(data.get('slot'))
        if kind == 'section' and spec['template'] not in COUNT_KEYS:
            raise ValidationError("Секцією може бути лише стелаж чи штабель.")
        return {'slot': spec}

    @api.constrains('kind', 'data')
    def _check_data(self):
        for rec in self:
            if rec.data is not None and rec.data != self._td_normalize_data(rec.kind, rec.data):
                raise ValidationError("Пресет «%s»: дані не в нормалізованому вигляді." % rec.name)

    @api.model_create_multi
    def create(self, vals_list):
        out = []
        for vals in vals_list:
            vals = dict(vals)
            vals['data'] = self._td_normalize_data(vals.get('kind') or 'row', vals.get('data') or {})
            out.append(vals)
        return super().create(out)

    def write(self, vals):
        if 'data' in vals or 'kind' in vals:
            for rec in self:
                vals = dict(
                    vals, data=self._td_normalize_data(vals.get('kind', rec.kind), vals.get('data', rec.data) or {})
                )
        return super().write(vals)

    def unlink(self):
        if not (self.env.su or self.env.user.has_group(MANAGER_XMLID)):
            raise AccessError("Видаляти пресети з бібліотеки може лише менеджер конструктора.")
        return super().unlink()
