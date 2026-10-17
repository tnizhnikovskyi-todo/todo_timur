from odoo import api, fields, models

F3D_CATEGORY_SELECTION = [
    ('machine', "Верстат"), ('rack', "Стелаж"), ('forklift', "Навантажувач"), ('conveyor', "Конвеєр"),
    ('panel', "Шафа/щит"), ('robot', "Робот"), ('other', "Інше"),
]


class F3dEquipmentPassport(models.Model):
    _inherit = 'f3d.equipment.passport'

    f3d_category = fields.Selection(
        F3D_CATEGORY_SELECTION, string="Категорія (конструктор)", default='other', index=True,
        help="Від категорії залежить умовна 3D-модель варіанта без файла (CD-18)")
    variant_ids = fields.One2many('f3d.equipment.variant', 'passport_id', string="Варіанти")
    variant_count = fields.Integer(string="Варіантів", compute='_compute_variant_count')

    @api.depends('variant_ids')
    def _compute_variant_count(self):
        data = dict(self.env['f3d.equipment.variant'].with_context(active_test=False)._read_group(
            [('passport_id', 'in', self.ids)], ['passport_id'], ['__count']))
        for rec in self:
            rec.variant_count = data.get(rec, 0)

    def action_view_variants(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': "Варіанти: %s" % self.name,
            'res_model': 'f3d.equipment.variant',
            'view_mode': 'kanban,list,form',
            'domain': [('passport_id', '=', self.id)],
            'context': {'default_passport_id': self.id},
        }
