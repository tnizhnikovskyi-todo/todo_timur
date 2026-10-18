import json

from odoo import api, fields, models
from odoo.exceptions import ValidationError

ZONE_TYPES = [
    ('receiving', 'Приймання'),
    ('storage', 'Склад'),
    ('production', 'Виробництво'),
    ('assembly', 'Збирання'),
    ('packing', 'Пакування'),
    ('shipping', 'Відвантаження'),
    ('technical', 'Технічна'),
    ('office', 'Офіс і побут'),
    ('outdoor', 'Двір'),
]

# Територія за замовчуванням (plant/infra.py:SITE), якщо параметри CB-12 відсутні.
SITE_DEFAULTS = {'x0': -32.0, 'y0': -30.0, 'x1': 182.0, 'y1': 100.0}


def _is_num(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


class F3dZone(models.Model):
    _name = 'td.zone'
    _inherit = ['td.scene.mixin']
    _description = 'Зона цеху'
    _order = 'sequence, td_code'
    _rec_name = 'name'
    _rec_names_search = ['name', 'td_code']
    _f3d_kind = 'zone'

    td_code = fields.Char(required=True)  # довжину ≤ 32 перевіряє _check_f3d_codes (size=32 мовчки обрізало б, B-1)
    name = fields.Char(string='Назва', required=True, size=128)
    sequence = fields.Integer(default=10)
    zone_type = fields.Selection(ZONE_TYPES, string='Тип', required=True)
    is_roof = fields.Boolean(
        string='Дах', default=False,
        help='Контур лежить на рівні покрівлі (z = 9 м), а не на підлозі; лише для типу «Двір»')
    polygon = fields.Json(string='Контур, м')
    polygon_text = fields.Text(
        string='Контур (JSON)', compute='_compute_polygon_text', inverse='_inverse_polygon_text')
    area_m2 = fields.Float(
        string='Площа, м²', compute='_compute_geometry', store=True, digits=(12, 1))
    x_min = fields.Float(compute='_compute_geometry', store=True, digits=(8, 2))
    y_min = fields.Float(compute='_compute_geometry', store=True, digits=(8, 2))
    x_max = fields.Float(compute='_compute_geometry', store=True, digits=(8, 2))
    y_max = fields.Float(compute='_compute_geometry', store=True, digits=(8, 2))
    color = fields.Char(string='Колір', size=7, default='#d5d8dc')
    description = fields.Text(string='Опис')
    root_location_id = fields.Many2one(
        'stock.location', string='Місце в Odoo', ondelete='set null',
        help='Групова локація, що відповідає зоні (напр. WH/Stock/Сировина/Плити)')
    company_id = fields.Many2one(
        'res.company', required=True, index=True, default=lambda self: self.env.company)
    active = fields.Boolean(default=True)
    location_ids = fields.One2many('stock.location', 'td_zone_id', string='Місця зберігання')
    workcenter_ids = fields.One2many('mrp.workcenter', 'td_zone_id', string='Робочі центри')
    equipment_ids = fields.One2many('maintenance.equipment', 'td_zone_id', string='Обладнання')
    dock_location_ids = fields.Many2many(
        'stock.location', string='Ворота', compute='_compute_docks')
    location_count = fields.Integer(compute='_compute_counts')
    workcenter_count = fields.Integer(compute='_compute_counts')
    equipment_count = fields.Integer(compute='_compute_counts')
    dock_count = fields.Integer(compute='_compute_counts')

    _f3d_zone_color = models.Constraint(
        "CHECK(color ~ '^#[0-9a-fA-F]{6}$')", 'Колір зони — у форматі #rrggbb.')

    # --- compute ---
    @api.depends('polygon')
    def _compute_polygon_text(self):
        for zone in self:
            zone.polygon_text = json.dumps(zone.polygon) if zone.polygon else False

    def _inverse_polygon_text(self):
        for zone in self:
            text = (zone.polygon_text or '').strip()
            if not text:
                zone.polygon = False
                continue
            try:
                zone.polygon = json.loads(text)
            except ValueError:
                raise ValidationError(
                    'Контур: очікується JSON-список точок [[x, y], …]') from None

    @staticmethod
    def _polygon_area(points):
        total = 0.0
        for (x1, y1), (x2, y2) in zip(points, points[1:] + points[:1], strict=True):
            total += x1 * y2 - x2 * y1
        return abs(total) / 2.0

    @api.depends('polygon')
    def _compute_geometry(self):
        for zone in self:
            points = zone.polygon
            if not points:
                zone.area_m2 = zone.x_min = zone.y_min = zone.x_max = zone.y_max = 0.0
                continue
            try:
                xs = [p[0] for p in points]
                ys = [p[1] for p in points]
                zone.area_m2 = self._polygon_area([tuple(p[:2]) for p in points])
                zone.x_min, zone.x_max = min(xs), max(xs)
                zone.y_min, zone.y_max = min(ys), max(ys)
            except (TypeError, IndexError, ValueError):
                # некоректний контур відхилить _check_polygon
                zone.area_m2 = zone.x_min = zone.y_min = zone.x_max = zone.y_max = 0.0

    @api.depends('location_ids')
    def _compute_docks(self):
        # td_kind на stock.location з'являється з домішкою (W3); до того воріт немає
        has_kind = 'td_kind' in self.env['stock.location']._fields
        for zone in self:
            zone.dock_location_ids = zone.location_ids.filtered(
                lambda loc: has_kind and loc.td_kind == 'dock')

    def _compute_counts(self):
        for zone in self:
            zone.location_count = self.env['stock.location'].search_count(
                [('td_zone_id', '=', zone.id)])
            zone.workcenter_count = self.env['mrp.workcenter'].search_count(
                [('td_zone_id', '=', zone.id)])
            zone.equipment_count = self.env['maintenance.equipment'].search_count(
                [('td_zone_id', '=', zone.id)])
            zone.dock_count = len(zone.dock_location_ids)

    # --- constraints ---
    def _site_bounds(self):
        get = self.env['ir.config_parameter'].sudo().get_param

        def param(name, default):
            try:
                return float(get('td.base.site_%s_m' % name, default))
            except (TypeError, ValueError):
                return default
        return (param('x0', SITE_DEFAULTS['x0']), param('y0', SITE_DEFAULTS['y0']),
                param('x1', SITE_DEFAULTS['x1']), param('y1', SITE_DEFAULTS['y1']))

    @api.constrains('polygon', 'is_roof', 'zone_type')
    def _check_polygon(self):
        x0, y0, x1, y1 = self._site_bounds()
        for zone in self:
            if zone.is_roof and zone.zone_type != 'outdoor':
                raise ValidationError('Позначка «Дах» — лише для зон типу «Двір».')
            points = zone.polygon
            if not points:
                continue
            reason = None
            if not isinstance(points, (list, tuple)) or len(points) < 3:
                reason = 'потрібно щонайменше 3 точки'
            elif any(not isinstance(p, (list, tuple)) or len(p) != 2
                     or not _is_num(p[0]) or not _is_num(p[1]) for p in points):
                reason = 'кожна точка має бути парою чисел [x, y]'
            elif any(not (x0 <= p[0] <= x1 and y0 <= p[1] <= y1) for p in points):
                reason = 'точка поза територією (%s…%s × %s…%s)' % (x0, x1, y0, y1)
            elif self._polygon_area([tuple(p) for p in points]) <= 0:
                reason = 'площа контуру має бути більшою за нуль'
            if reason:
                raise ValidationError('Контур зони %s: %s' % (zone.td_code, reason))

    # --- API ---
    @staticmethod
    def _point_in_polygon(x, y, points):
        """Промінь; точка на ребрі вважається всередині."""
        eps = 1e-9
        inside = False
        for (x1, y1), (x2, y2) in zip(points, points[1:] + points[:1], strict=True):
            cross = (x - x1) * (y2 - y1) - (y - y1) * (x2 - x1)
            if (abs(cross) <= eps and min(x1, x2) - eps <= x <= max(x1, x2) + eps
                    and min(y1, y2) - eps <= y <= max(y1, y2) + eps):
                return True
            if (y1 > y) != (y2 > y):
                x_cross = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
                if x < x_cross:
                    inside = not inside
        return inside

    @api.model
    def zone_at(self, x, y, company=None, roof=False):
        domain = [('active', '=', True), ('is_roof', '=', bool(roof)),
                  ('x_min', '<=', x), ('x_max', '>=', x),
                  ('y_min', '<=', y), ('y_max', '>=', y)]
        if company:
            domain.append(('company_id', 'in', [company.id, False]))
        for zone in self.search(domain, order='sequence, id'):
            points = [tuple(p) for p in (zone.polygon or [])]
            if len(points) >= 3 and self._point_in_polygon(x, y, points):
                return zone
        return self.browse()

    def _action_view(self, res_model, name):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': name,
            'res_model': res_model,
            'view_mode': 'list,form',
            'domain': [('td_zone_id', '=', self.id)],
            'context': {'default_td_zone_id': self.id},
        }

    def action_view_locations(self):
        return self._action_view('stock.location', 'Місця зберігання')

    def action_view_workcenters(self):
        return self._action_view('mrp.workcenter', 'Робочі центри')

    def action_view_equipment(self):
        return self._action_view('maintenance.equipment', 'Обладнання')

    def action_view_docks(self):
        action = self._action_view('stock.location', 'Ворота')
        action['domain'] = [('id', 'in', self.dock_location_ids.ids)]
        return action


class StockLocation(models.Model):
    _inherit = 'stock.location'

    td_zone_id = fields.Many2one(
        'td.zone', string='Зона цеху', index=True, ondelete='set null')


class MrpWorkcenter(models.Model):
    _inherit = 'mrp.workcenter'

    td_zone_id = fields.Many2one(
        'td.zone', string='Зона цеху', index=True, ondelete='set null')


class MaintenanceEquipment(models.Model):
    _inherit = 'maintenance.equipment'

    td_zone_id = fields.Many2one(
        'td.zone', string='Зона цеху', index=True, ondelete='set null')
