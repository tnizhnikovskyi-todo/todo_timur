from odoo import fields, models


class F3dBmsLightScene(models.Model):
    _name = "f3d.bms.light.scene"
    _description = "Будівля: сцена освітлення"
    _order = "number"

    number = fields.Integer(string="Номер", required=True)
    name = fields.Char(string="Назва", size=64, required=True)
    level_pct = fields.Integer(string="Рівень, %")
    block = fields.Integer(string="Блок сцен", default=1)
    note = fields.Char(size=256)

    _f3d_bms_scene_uniq = models.Constraint("UNIQUE(block, number)", "Сцена з таким номером уже є в блоці.")
    _f3d_bms_scene_range = models.Constraint(
        "CHECK(number BETWEEN 1 AND 16 AND block BETWEEN 1 AND 8 "
        "AND (level_pct IS NULL OR level_pct BETWEEN 0 AND 100))",
        "Сцена: номер 1…16, блок 1…8, рівень 0…100 %.",
    )
