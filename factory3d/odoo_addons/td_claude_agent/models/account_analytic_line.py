import math
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError

HOURS_STEP = 0.25
HOURS_MAX = 8.0
DESC_MIN = 20
DESC_MAX = 250
DESC_MIN_LETTERS = 10
GENERIC_WORDS = {
    "розробка",
    "розробив",
    "тестування",
    "тест",
    "аналіз",
    "зустріч",
    "робота",
    "працював",
    "налаштування",
    "доробка",
    "правки",
    "виправлення",
    "перевірка",
    "задача",
    "task",
    "work",
    "dev",
    "test",
}


class AccountAnalyticLine(models.Model):
    _inherit = "account.analytic.line"

    td_claude_is_ai = fields.Boolean(string="Рядок агента Claude", copy=False, index=True)
    td_claude_actual_minutes = fields.Integer(
        string="Реальний час агента, хв",
        copy=False,
        help="Скільки реально працював агент; «Години» — людський еквівалент.",
    )
    td_claude_request_id = fields.Many2one(
        "td.claude.request", string="Запит Claude", copy=False, ondelete="set null", index=True
    )

    @api.model
    def _td_claude_standard_text(self):
        return _(
            "Стандарт опису табеля: від %(min)s до %(max)s символів; один рядок на окрему дію; дієслово результату "
            "в минулому часі; що + об'єкт + результат; посилання (#задачі, AC-xx, модуль/гілка/PR, коди пунктів). "
            "Не можна «/», «-», «.» і окремі загальні слова («Розробка», «Тестування», «Аналіз», «Зустріч»).",
            min=DESC_MIN,
            max=DESC_MAX,
        )

    @api.model
    def _td_claude_clean_description(self, description):
        text = re.sub(r"\s+", " ", description or "").strip()
        standard = self._td_claude_standard_text()
        if not text:
            raise UserError(_("Порожній опис табеля. %s", standard))
        if len(text) < DESC_MIN:
            raise UserError(
                _(
                    "Опис табеля «%(text)s» закороткий (менше %(n)s символів). %(std)s",
                    text=text,
                    n=DESC_MIN,
                    std=standard,
                )
            )
        if len(text) > DESC_MAX:
            raise UserError(_("Опис табеля задовгий (%(n)s символів). %(std)s", n=len(text), std=standard))
        words = re.findall(r"[^\W\d_]+", text.lower())
        if (len(words) == 1 and words[0] in GENERIC_WORDS) or sum(len(w) for w in words) < DESC_MIN_LETTERS:
            raise UserError(_("Опис табеля занадто загальний. %s", standard))
        if len(words) == 1:
            raise UserError(_("Опис табеля не може бути одним словом. %s", standard))
        return text

    @api.model
    def _td_claude_round_hours(self, hours):
        try:
            hours = float(hours)
        except (TypeError, ValueError) as exc:
            raise UserError(_("Години мають бути числом.")) from exc
        if hours <= 0:
            raise UserError(_("Години мають бути більшими за нуль (мінімум %s).", HOURS_STEP))
        rounded = max(HOURS_STEP, math.ceil(round(hours / HOURS_STEP, 6)) * HOURS_STEP)
        if rounded > HOURS_MAX:
            raise UserError(
                _(
                    "Максимум %(max)s год на рядок: розбийте роботу на окремі дії й спишіть кількома рядками.",
                    max=HOURS_MAX,
                )
            )
        return rounded
