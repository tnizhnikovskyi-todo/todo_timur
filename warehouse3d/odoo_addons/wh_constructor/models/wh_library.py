from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .wh_project import iso


class WhLibrary(models.Model):
    """Общий справочник конструктора (D-12, C10): каталог типов мест и шаблоны секций/рядов, общие для всех проектов компании.
    Одна запись на компанию; JSON {"types": [...], "templates": [...]} собирает и читает приложение."""
    _name = "wh.library"
    _description = "Довідник конструктора складу (типи й шаблони)"
    _order = "company_id, id"

    name = fields.Char(required=True, default="library")
    company_id = fields.Many2one("res.company", string="Компанія", default=lambda self: self.env.company, required=True, index=True)
    data = fields.Json(string="Довідник (JSON)")
    rev = fields.Integer(string="Номер ревізії", default=1, readonly=True, copy=False,
                         help="Збільшується при кожному записі; за ним виявляється конфлікт збереження.")

    @api.constrains("company_id")
    def _check_one_per_company(self):
        for r in self:
            if self.sudo().search_count([("company_id", "=", r.company_id.id), ("id", "!=", r.id)]):
                raise ValidationError(_("Довідник конструктора для цієї компанії вже існує."))

    def _mine(self):
        return self.search([("company_id", "=", self.env.company.id)], limit=1)

    def _lock_row(self):
        self.env.cr.execute("SELECT id FROM wh_library WHERE id = %s FOR UPDATE", [self.id])
        self.invalidate_recordset(["rev"])

    def _payload(self):
        self.ensure_one()
        return {"found": True, "data": self.data, "rev": self.rev, "by": self.write_uid.name, "at": iso(self.write_date)}

    # ------------------------------------------------------------ API для контроллеров
    @api.model
    def api_load(self):
        r = self._mine()
        return r._payload() if r else {"found": False, "data": None, "rev": 0}

    @api.model
    def api_save(self, data, base_rev=None):
        """Записать справочник. base_rev — ревизия, на которой основаны правки (None/0 — справочника ещё не было).
        В базе новее — {"status": "stale", "rev", "data"}: клиент объединяет данные и повторяет запись."""
        if not isinstance(data, dict):
            raise ValidationError(_("Потрібні дані довідника."))
        clean = {k: v for k, v in data.items() if k in ("types", "templates") and isinstance(v, list)}
        r = self._mine()
        if r:
            r._lock_row()
            if (base_rev or 0) != r.rev:
                return {"status": "stale", "rev": r.rev, "data": r.data}
            r.write({"data": clean, "rev": r.rev + 1})
        else:
            r = self.create({"data": clean, "rev": 1})
        return {"status": "ok", "rev": r.rev}
