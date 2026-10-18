import re
from datetime import timezone
from string import Formatter

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import html_escape

from .genset_link import KYIV, _to_utc_naive

ALLOWED_FIELDS = frozenset({"code", "name", "value", "unit", "threshold", "ts", "text", "td_link"})
TEXT_LIMIT = 2000
REGEX_NAME_LIMIT = 500


class SafeDict(dict):
    """Невідомий ключ у шаблоні → «—» (SPEC §11 п. 9)."""

    def __missing__(self, key):
        return "—"


def _num(value):
    """%.1f з комою як десятковим роздільником; None → «—»."""
    if value is None or value == "":
        return "—"
    try:
        return ("%.1f" % float(value)).replace(".", ",")
    except (TypeError, ValueError):
        return "—"


class F3dGensetEventMap(models.Model):
    _name = "f3d.genset.event.map"
    _description = "Генератор: мапа подій → заявки ТО"
    _order = "sequence, key"

    key = fields.Char(string="Ключ", size=64, required=True, index=True)
    sequence = fields.Integer(string="Послідовність", default=10)
    hgm_name = fields.Char(string="Назва за мануалом HGM6120N")
    hgm_table = fields.Selection(
        [("warning", "Table 4 — попередження"), ("shutdown", "Table 5 — аварійна зупинка"), ("other", "Інше")],
        string="Таблиця мануала",
        default="other",
    )
    severity = fields.Selection(
        [
            ("warning", "Попередження"),
            ("shutdown", "Аварійна зупинка"),
            ("comm", "Зв'язок"),
            ("service", "ТО"),
            ("info", "Інформація"),
        ],
        string="Важливість",
        required=True,
    )
    td_code = fields.Char(string="Код у td_genset", size=64, index=True)
    action = fields.Selection(
        [
            ("request_corrective", "Заявка ТО (ремонт)"),
            ("request_preventive", "Заявка ТО (планова)"),
            ("bus_only", "Лише подія в 3D"),
            ("ignore", "Ігнорувати"),
        ],
        string="Дія",
        required=True,
        default="bus_only",
    )
    priority = fields.Selection(
        [("0", "Дуже низький"), ("1", "Низький"), ("2", "Звичайний"), ("3", "Високий")], string="Пріоритет", default="2"
    )
    name_tpl = fields.Char(string="Шаблон назви заявки", required=True)
    description_tpl = fields.Text(string="Шаблон опису")
    match_regex = fields.Char(string="Регулярний вираз за назвою події")
    active = fields.Boolean(string="Активний", default=True)

    _key_uniq = models.Constraint("UNIQUE(key)", "Ключ мапи має бути унікальним.")

    @api.constrains("name_tpl", "description_tpl")
    def _check_templates(self):
        message = _("Шаблон: дозволені лише поля {code} {name} {value} {unit} {threshold} {ts} {text} {td_link}.")
        for rec in self:
            for tpl in (rec.name_tpl, rec.description_tpl):
                if not tpl:
                    continue
                try:
                    parsed = list(Formatter().parse(tpl))
                except ValueError:
                    raise ValidationError(message) from None
                for _lit, field_name, spec, conv in parsed:
                    if field_name is None:
                        continue
                    if (
                        field_name not in ALLOWED_FIELDS
                        or "." in field_name
                        or "[" in field_name
                        or "{" in (spec or "")
                        or conv
                    ):
                        raise ValidationError(message)

    @api.model
    def _match(self, ev):
        """R-07 крок 1: td_code → hgm_name+severity → match_regex → DEFAULT_<severity>; перший збіг за sequence, key."""
        rows = self.search([("active", "=", True)])  # _order = sequence, key
        code = ev.get("code") or ""
        name = (ev.get("name") or "").strip()
        severity = ev.get("severity") or ""
        if code:
            for row in rows:
                if row.td_code and row.td_code == code:
                    return row
        if name:
            for row in rows:
                if row.hgm_name and row.hgm_name.strip().lower() == name.lower() and row.severity == severity:
                    return row
            for row in rows:
                if row.match_regex:
                    try:
                        if re.search(row.match_regex, name[:REGEX_NAME_LIMIT], re.I):
                            return row
                    except re.error:
                        continue
        default = "DEFAULT_" + severity.upper()
        for row in rows:
            if row.key == default:
                return row
        return self.browse()

    def _render(self, ev, link):
        """R-07 крок 3: (name ≤ 120, description HTML) з екрануванням значень події."""
        self.ensure_one()
        ts = _to_utc_naive(ev.get("ts"))
        ts_txt = ts.replace(tzinfo=timezone.utc).astimezone(KYIV).strftime("%d.%m %H:%M") if ts else "—"
        ref = link.td_genset_ref
        raw = {
            "code": link.f3d_code or "—",
            "name": ev.get("name") or "—",
            "value": _num(ev.get("value")),
            "unit": ev.get("unit") or "",
            "threshold": _num(ev.get("threshold")),
            "ts": ts_txt,
            "text": (ev.get("text") or "—")[:TEXT_LIMIT],
            "td_link": "%s,%d" % (ref._name, ref.id) if ref else "—",
        }
        name = self.name_tpl.format_map(SafeDict(raw))[:120]
        escaped = {k: str(html_escape(str(v))) for k, v in raw.items()}
        tpl = str(html_escape(self.description_tpl or ""))
        description = tpl.format_map(SafeDict(escaped)).replace("\n", "<br/>")
        return name, description
