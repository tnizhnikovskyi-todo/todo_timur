import math
import re

from odoo import api, fields, models
from odoo.exceptions import ValidationError

CODE_RE = re.compile(r'^SZ-[0-9]{1,2}$')

COMPLIANCE = [
    ('na', 'Не перевірено'), ('ok', 'Відповідає'), ('warn', 'Зауваження'), ('fail', 'Не відповідає'),
]


def plant_size(env):
    """Розміри будівлі (CB-12): (довжина, ширина), м."""
    icp = env['ir.config_parameter'].sudo()
    return (float(icp.get_param('td.base.plant_length_m', 150) or 150),
            float(icp.get_param('td.base.plant_width_m', 72) or 72))


class F3dFireSmokeZone(models.Model):
    _name = "td.fire.smoke.zone"
    _description = "Димовидалення: димова зона"
    _order = "code"
    _rec_name = "code"

    code = fields.Char(string="Код", size=8, required=True, index=True)
    name = fields.Char(string="Назва", size=128, required=True)
    system_id = fields.Many2one(
        'td.fire.system', string="Система", required=True, ondelete='cascade',
        domain=[('system_type', '=', 'smoke')])
    x0 = fields.Float(digits=(8, 2), required=True)
    y0 = fields.Float(digits=(8, 2), required=True)
    x1 = fields.Float(digits=(8, 2), required=True)
    y1 = fields.Float(digits=(8, 2), required=True)
    area_m2 = fields.Float(
        string="Площа, м²", compute='_compute_area', store=True, digits=(12, 0))
    vent_ids = fields.One2many('td.fire.device', 'smoke_zone_id', string="Люки")
    vent_count = fields.Integer(
        string="Люків", compute='_compute_vent_count', store=True)
    vent_area_m2 = fields.Float(
        string="Площа люків Aa, м²", compute='_compute_vent_area', digits=(8, 2))
    need_vents = fields.Integer(string="Потрібно люків", readonly=True)
    max_area_m2 = fields.Float(string="Найбільша площа за нормою, м²", readonly=True)
    area_ok = fields.Boolean(readonly=True)
    vents_ok = fields.Boolean(readonly=True)
    compliance = fields.Selection(COMPLIANCE, default='na', readonly=True, index=True)
    compliance_note = fields.Text(readonly=True)
    active = fields.Boolean(default=True)

    _code_uniq = models.Constraint('UNIQUE(code)', 'Код димової зони має бути унікальним.')

    @api.constrains('code')
    def _check_code(self):
        for rec in self:
            if not CODE_RE.match(rec.code or ''):
                raise ValidationError("Код димової зони: SZ-<n>")

    @api.constrains('x0', 'y0', 'x1', 'y1')
    def _check_rect(self):
        length, width = plant_size(self.env)
        for rec in self:
            if not (rec.x0 < rec.x1 and rec.y0 < rec.y1
                    and rec.x0 >= 0 and rec.y0 >= 0 and rec.x1 <= length and rec.y1 <= width):
                raise ValidationError("Контур димової зони %s поза будівлею." % rec.code)

    @api.depends('x0', 'y0', 'x1', 'y1')
    def _compute_area(self):
        for rec in self:
            rec.area_m2 = (rec.x1 - rec.x0) * (rec.y1 - rec.y0)

    @api.depends('vent_ids.active', 'vent_ids.type')
    def _compute_vent_count(self):
        for rec in self:
            rec.vent_count = len(rec.vent_ids.filtered(lambda d: d.active and d.type == 'smoke_vent'))

    @api.depends('vent_count')
    def _compute_vent_area(self):
        aa = self.env['td.fire.norm'].get('smoke_vent_aa') or 0.0
        for rec in self:
            rec.vent_area_m2 = rec.vent_count * aa

    def point_inside(self, x, y):
        self.ensure_one()
        return self.x0 <= x <= self.x1 and self.y0 <= y <= self.y1

    def _recompute(self):
        """R-09: площа, потрібна кількість люків, відповідність."""
        norm = self.env['td.fire.norm']
        max_area = norm.get('smoke_zone_max_area')
        per400 = norm.get('smoke_vent_area')
        aa = norm.get('smoke_vent_aa')
        ref = norm.get_ref('smoke_zone_max_area')
        for rec in self:
            area = (rec.x1 - rec.x0) * (rec.y1 - rec.y0)
            if not max_area or not per400 or not aa:
                rec.write({'compliance': 'na', 'area_ok': False, 'vents_ok': False,
                           'compliance_note': "Норма не задана"})
                continue
            need = math.ceil(area / 400.0 * per400 / aa - 1e-9)
            area_ok = area <= max_area
            vents_ok = rec.vent_count >= need
            if not area_ok:
                state = 'fail'
            elif not vents_ok:
                state = 'warn'
            else:
                state = 'ok'
            rec.write({
                'need_vents': need,
                'max_area_m2': max_area,
                'area_ok': area_ok,
                'vents_ok': vents_ok,
                'compliance': state,
                'compliance_note': "Площа %d м² (норма ≤ %d м², %s); люків %d з %d потрібних (орієнтир)" % (
                    round(area), round(max_area), ref, rec.vent_count, need),
            })

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        recs._recompute()
        return recs

    def write(self, vals):
        res = super().write(vals)
        if {'x0', 'y0', 'x1', 'y1', 'active'} & set(vals):
            self._recompute()
        return res
