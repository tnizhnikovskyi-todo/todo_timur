"""M-H1 `td.energy.round.template` (шаблон обходу), M-H2 `.slot` (слот розкладу), M-H3 `.template.item` (пункт)."""

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from ..tools import schedule, value


class TdEnergyRoundTemplate(models.Model):
    _name = "td.energy.round.template"
    _description = "Енергетика: шаблон обходу"
    _order = "sequence, id"

    name = fields.Char(string="Назва", size=64, required=True)
    code = fields.Char(string="Код", size=32, required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    slot_ids = fields.One2many("td.energy.round.slot", "template_id", string="Розклад")
    item_ids = fields.One2many("td.energy.round.template.item", "template_id", string="Пункти")
    note = fields.Text(string="Примітка")
    company_id = fields.Many2one("res.company", string="Компанія", required=True, default=lambda self: self.env.company)

    _td_energy_round_template_code_uniq = models.Constraint("UNIQUE(code)", "Код шаблону обходу має бути унікальним.")


class TdEnergyRoundSlot(models.Model):
    _name = "td.energy.round.slot"
    _description = "Енергетика: слот обходу"
    _order = "sequence, id"

    template_id = fields.Many2one(
        "td.energy.round.template", string="Шаблон", required=True, index=True, ondelete="cascade"
    )
    name = fields.Char(string="Назва", size=32, required=True)
    time_from = fields.Float(string="З (год)", required=True)
    time_to = fields.Float(string="До (год)", required=True)
    weekdays = fields.Char(string="Дні тижня", size=13, default=schedule.WEEKDAYS_DEFAULT)
    sequence = fields.Integer(default=10)

    @api.constrains("time_from", "time_to")
    def _check_times(self):
        for rec in self:
            if not (0 <= rec.time_from < rec.time_to <= 24):
                raise ValidationError(_("Слот не може перетинати північ."))

    @api.constrains("weekdays")
    def _check_weekdays(self):
        for rec in self:
            if schedule.parse_weekdays(rec.weekdays) is None:
                raise ValidationError(_("Дні тижня слота «%s»: цифри 0…6 через кому без повторів (пн = 0).", rec.name))


class TdEnergyRoundTemplateItem(models.Model):
    _name = "td.energy.round.template.item"
    _description = "Енергетика: пункт шаблону обходу"
    _order = "sequence, id"

    template_id = fields.Many2one(
        "td.energy.round.template", string="Шаблон", required=True, index=True, ondelete="cascade"
    )
    sequence = fields.Integer(default=10)
    code = fields.Char(string="Код", size=16, required=True)
    title = fields.Char(string="Назва", size=128, required=True)
    hint = fields.Char(string="Підказка (без норми)", size=128)
    source = fields.Char(
        string="Джерело значення",
        size=96,
        help="signal:<код сигналу> або pult:<шлях JSON у get_pult>, напр. pult:kpis.generation.genset.fuel_pct; "
        "порожньо — без значення.",
    )
    norm_kind = fields.Selection(
        [("none", "Без норми"), ("max", "до"), ("min", "від"), ("range", "діапазон")],
        string="Норма",
        required=True,
        default="none",
    )
    norm_min = fields.Float(string="Норма від")
    norm_max = fields.Float(string="Норма до")
    unit = fields.Char(string="Одиниця", size=16)
    precision = fields.Integer(string="Знаків після коми", default=0)
    node_id = fields.Many2one("td.energy.node", string="Вузол (3D)", ondelete="set null")
    required = fields.Boolean(string="Обов'язковий", default=True)

    _td_energy_round_template_item_code_uniq = models.Constraint(
        "UNIQUE(template_id, code)", "Код пункту має бути унікальним у шаблоні."
    )

    @api.constrains("source")
    def _check_source(self):
        for rec in self:
            if rec.source and not value.SOURCE_RE.match(rec.source):
                raise ValidationError(
                    _("Джерело значення пункту «%s» некоректне: signal:<код> або pult:<шлях>.", rec.title)
                )

    @api.constrains("norm_kind", "norm_min", "norm_max")
    def _check_norm(self):
        """`max` ⇒ задано `norm_max`, `min` ⇒ `norm_min` (0 для float = «не задано»), `range` ⇒ мін ≤ макс."""
        for rec in self:
            kind = rec.norm_kind
            bad = (
                (kind == "max" and not rec.norm_max)
                or (kind == "min" and not rec.norm_min)
                or (kind == "range" and rec.norm_min > rec.norm_max)
            )
            if bad:
                raise ValidationError(_("Норма пункту «%s» некоректна.", rec.title))
