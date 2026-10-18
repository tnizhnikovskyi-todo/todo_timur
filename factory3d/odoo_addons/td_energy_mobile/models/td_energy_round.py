"""M-H4 `td.energy.round`, M-H5 `td.energy.round.item` (W4-C). Каркас: ключові поля — для ACL і record rules;
решта полів, `UNIQUE`, методи API-H1…API-H6, крони — воркер C (замінює файл цілком).
Контракт відповіді `get_mobile`: `contracts/api_h1_get_mobile.json`."""

from odoo import fields, models


class TdEnergyRound(models.Model):
    _name = "td.energy.round"
    _description = "Енергетика: обхід"
    _inherit = ["mail.thread"]
    _order = "date desc, starts_at desc, id desc"

    name = fields.Char(string="Назва")
    template_id = fields.Many2one(
        "td.energy.round.template", string="Шаблон", required=True, index=True, ondelete="restrict"
    )
    date = fields.Date(string="Дата (Київ)", required=True, index=True)
    starts_at = fields.Datetime(string="Початок слота", required=True)
    due_at = fields.Datetime(string="Кінець слота", required=True)
    state = fields.Selection(
        [
            ("open", "Відкритий"),
            ("in_progress", "У роботі"),
            ("done", "Завершено"),
            ("missed", "Не виконано"),
            ("cancelled", "Скасовано"),
        ],
        string="Стан",
        default="open",
        index=True,
        tracking=True,
    )
    item_ids = fields.One2many("td.energy.round.item", "round_id", string="Пункти")
    company_id = fields.Many2one("res.company", string="Компанія", required=True, default=lambda self: self.env.company)


class TdEnergyRoundItem(models.Model):
    _name = "td.energy.round.item"
    _description = "Енергетика: пункт обходу"
    _order = "sequence, id"

    round_id = fields.Many2one("td.energy.round", string="Обхід", required=True, index=True, ondelete="cascade")
    sequence = fields.Integer(default=10)
    code = fields.Char(string="Код", size=16)
    title = fields.Char(string="Назва", size=128)
    done = fields.Boolean(string="Виконано", default=False)
