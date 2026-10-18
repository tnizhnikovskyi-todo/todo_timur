import itertools
import math
import re

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from .td_fire_smoke_zone import COMPLIANCE, plant_size

CODE_RE = re.compile(r'^EX-[A-Z0-9]{1,4}$')
SIDES = [('S', 'Південна стіна'), ('N', 'Північна стіна'), ('W', 'Західна стіна'), ('E', 'Східна стіна')]


class F3dFireExit(models.Model):
    _name = "td.fire.exit"
    _description = "Евакуація: вихід"
    _order = "code"
    _rec_name = "display"

    code = fields.Char(string="Код", size=8, required=True, index=True)
    name = fields.Char(string="Назва", size=128, required=True)
    display = fields.Char(compute='_compute_display', store=True)
    kind = fields.Selection(
        [('emergency', 'Аварійний вихід'), ('staff', 'Вхід персоналу')], string="Тип",
        required=True, default='emergency')
    x = fields.Float(digits=(8, 2), required=True)
    y = fields.Float(digits=(8, 2), required=True)
    side = fields.Selection(SIDES, string="Стіна", required=True)
    width_m = fields.Float(string="Ширина у просвіті, м", digits=(4, 2), default=1.2)
    equipment_id = fields.Many2one('maintenance.equipment', string="Обладнання", ondelete='set null')
    route_ids = fields.One2many('td.fire.route', 'exit_id', string="Маршрути")
    route_count = fields.Integer(string="Маршрутів", compute='_compute_route_count')
    nearest_exit_m = fields.Float(
        string="До найближчого іншого виходу, м", digits=(8, 1), readonly=True)
    width_ok = fields.Boolean(readonly=True)
    compliance = fields.Selection(COMPLIANCE, default='na', readonly=True, index=True)
    compliance_note = fields.Text(readonly=True)
    note = fields.Text(string="Примітка")
    active = fields.Boolean(default=True)

    _code_uniq = models.Constraint('UNIQUE(code)', 'Код виходу має бути унікальним.')

    @api.depends('code', 'side')
    def _compute_display(self):
        labels = dict(SIDES)
        for rec in self:
            rec.display = "%s · %s" % (rec.code, labels.get(rec.side, ''))

    @api.depends('route_ids')
    def _compute_route_count(self):
        for rec in self:
            rec.route_count = len(rec.route_ids)

    @api.constrains('code')
    def _check_code(self):
        for rec in self:
            if not CODE_RE.match(rec.code or ''):
                raise ValidationError("Код виходу: EX-<бік><n>")

    @api.constrains('x', 'y')
    def _check_wall(self):
        length, width = plant_size(self.env)
        for rec in self:
            inside = 0 <= rec.x <= length and 0 <= rec.y <= width
            on_wall = (abs(rec.y) <= 0.5 or abs(rec.y - width) <= 0.5
                       or abs(rec.x) <= 0.5 or abs(rec.x - length) <= 0.5)
            if not (inside and on_wall):
                raise ValidationError("Вихід %s має лежати на зовнішній стіні будівлі." % rec.code)

    @api.constrains('width_m')
    def _check_width(self):
        for rec in self:
            if rec.width_m <= 0:
                raise ValidationError("Ширина виходу %s має бути більшою за 0." % rec.code)

    @api.model
    def _dispersal_summary(self):
        """R-06 пп. 1–3, 5: підсумок по активних виходах (для панелі)."""
        norm = self.env['td.fire.norm']
        exits = self.search([('active', '=', True)])
        length, width = plant_size(self.env)
        perimeter = 2 * (length + width)
        k = norm.get('exit_dispersal_k')
        min_n = norm.get('evac_exits_min')
        l_m = round(k * math.sqrt(perimeter), 1) if k else 0.0
        pair = 0.0
        for a, b in itertools.combinations(exits, 2):
            pair = max(pair, math.hypot(a.x - b.x, a.y - b.y))
        pair = round(pair, 1)
        n_ok = bool(min_n) and len(exits) >= min_n
        return {
            'count': len(exits), 'n_ok': n_ok, 'pair_m': pair, 'l_m': l_m,
            'ok': bool(k and min_n and n_ok and pair >= l_m and all(e.width_ok for e in exits)),
        }

    def _recompute(self):
        """R-06 п. 4 (відстань до найближчого), R-07 (ширина дверей). Перераховує всі активні виходи."""
        norm = self.env['td.fire.norm']
        door_min = norm.get('door_width_min')
        ref = norm.get_ref('door_width_min')
        all_active = self.search([('active', '=', True)])
        for rec in (all_active | self):
            if not rec.active:
                rec.write({'compliance': 'na', 'width_ok': False, 'nearest_exit_m': 0.0,
                           'compliance_note': False})
                continue
            others = all_active - rec
            nearest = round(min((math.hypot(rec.x - o.x, rec.y - o.y) for o in others), default=0.0), 1)
            if door_min is None:
                rec.write({'nearest_exit_m': nearest, 'width_ok': False, 'compliance': 'na',
                           'compliance_note': "Норма не задана"})
                continue
            ok = rec.width_m >= door_min
            rec.write({
                'nearest_exit_m': nearest, 'width_ok': ok, 'compliance': 'ok' if ok else 'fail',
                'compliance_note': "Ширина %s м при нормі ≥ %s м (%s)" % (rec.width_m, door_min, ref),
            })
        # ширина виходу впливає на маршрути до нього
        self.env['td.fire.route'].search([('exit_id', 'in', (all_active | self).ids)])._recompute()

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        recs._recompute()
        return recs

    def write(self, vals):
        res = super().write(vals)
        if {'x', 'y', 'width_m', 'active'} & set(vals):
            self._recompute()
        return res

    def action_f3d_show(self):
        self.ensure_one()
        if not self.equipment_id:
            raise UserError("Вихід %s не пов'язано з 3D-об'єктом (обладнання EXITS)." % self.code)
        return self.equipment_id.action_f3d_show()
