from uuid import uuid4

from odoo import api, fields, models

SLOT_TEMPLATE_SELECTION = [
    ('pallet_rack', "Паллетний стелаж"), ('cantilever', "Консольний стелаж"),
    ('shelf', "Полицевий стелаж / комірки фурнітури"), ('floor_stack', "Підлогове штабелювання"),
    ('machine_spot', "Місце під верстат"), ('zone', "Зона-контур"),
]


class F3dSlot(models.Model):
    _name = 'f3d.slot'
    _description = "Місце (шаблон)"
    _order = 'layer_id, code_prefix'
    _rec_name = 'code_prefix'
    _check_company_auto = True

    uid = fields.Char(string="UID", size=32, default=lambda self: uuid4().hex, copy=False, index=True, readonly=True)
    layer_id = fields.Many2one('f3d.layer', string="Шар", required=True, ondelete='cascade', index=True)
    site_id = fields.Many2one('f3d.site', related='layer_id.site_id', store=True, index=True)
    company_id = fields.Many2one('res.company', related='site_id.company_id', store=True, index=True)
    template = fields.Selection(SLOT_TEMPLATE_SELECTION, string="Шаблон", required=True)
    code_prefix = fields.Char(
        string="Префікс коду", size=22, required=True,
        help="Префікс кодів комірок: FG-R1 → FG-R1-B01-L1; не більше 22 символів")
    x_m = fields.Float(string="X, м", digits=(10, 3))
    y_m = fields.Float(string="Y, м", digits=(10, 3))
    rotation = fields.Integer(string="Поворот, °", default=0)
    params = fields.Json(string="Параметри шаблону", default=dict)
    overrides = fields.Json(string="Перевизначення комірок", default=dict)
    parent_location_id = fields.Many2one(
        'stock.location', string="Батьківська локація", check_company=True,
        domain=[('usage', 'in', ('internal', 'view'))], help="Куди публікувати комірки місця")
    cell_count = fields.Integer(
        string="Комірок", compute='_compute_cells', store=True)
    footprint_l_m = fields.Float(string="Довжина габариту, м", digits=(10, 3), compute='_compute_cells', store=True)
    footprint_w_m = fields.Float(string="Ширина габариту, м", digits=(10, 3), compute='_compute_cells', store=True)
    cells_html = fields.Html(string="Комірки", compute='_compute_cells_html', sanitize=False)
    note = fields.Text(string="Примітка")
    active = fields.Boolean(default=True)

    _f3d_slot_uid_uniq = models.Constraint(
        'UNIQUE(site_id, uid)', "UID місця має бути унікальним на площадці.")
    _f3d_slot_prefix_uniq = models.Constraint(
        'UNIQUE(site_id, code_prefix)', "Префікс місця має бути унікальним на площадці.")

    @api.depends('template', 'params', 'overrides')
    def _compute_cells(self):
        # Реалізація R-01 — у наступному коміті (services.cells)
        for slot in self:
            slot.cell_count = 0
            slot.footprint_l_m = 0.0
            slot.footprint_w_m = 0.0

    def _compute_cells_html(self):
        for slot in self:
            slot.cells_html = False
