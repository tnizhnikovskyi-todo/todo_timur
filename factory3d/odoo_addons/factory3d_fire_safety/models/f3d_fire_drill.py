from odoo import fields, models


class F3dFireDrill(models.Model):
    # скелет, полностью — W4 (SPEC M-11)
    _name = "f3d.fire.drill"
    _description = "Навчальна пожежна тривога"

    name = fields.Char(string="Назва", required=True)
    zone_id = fields.Many2one("f3d.zone", string="Зона", ondelete="set null")
    state = fields.Selection(
        [("draft", "Чернетка"), ("planned", "Заплановано"), ("running", "Триває"),
         ("evaluating", "Оцінювання"), ("done", "Завершено"), ("cancelled", "Скасовано")],
        string="Стан", default="draft", required=True, index=True)
