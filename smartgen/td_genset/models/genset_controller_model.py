# Part of td_genset (ToDo). Власник файлу: W0 «Каркас».
"""Довідник моделей контролера ``td.genset.controller.model`` — ТР 2.4.1; SPEC 5.11."""
from odoo import fields, models


class TdGensetControllerModel(models.Model):
    _name = 'td.genset.controller.model'
    _description = 'Генератори: модель контролера'
    _order = 'name'

    name = fields.Char(
        string='Назва', required=True,
        help='Назва моделі контролера: «HGM6120N», «HGM6110N».')
    code = fields.Char(
        string='Код', required=True,
        help='Технічний код моделі: hgm6120n, hgm6110n.')
    has_mains_breaker = fields.Boolean(
        string='Є автомат мережі', default=True,
        help='HGM6120N керує автоматами генератора і мережі (05H 0005/0006); у HGM6110N автомата мережі немає — '
             'кнопка «Автомат мережі» прихована (1.5-29).')
    active = fields.Boolean(
        string='Активна', default=True,
        help='Архівна модель не пропонується для нових генераторів.')

    _sql_constraints = [
        ('code_uniq', 'unique(code)', 'Модель контролера з таким кодом уже є.'),
    ]
