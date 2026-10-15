from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

MAX_VERSIONS = 50  # сколько последних версий хранится; переопределяется параметром wh_constructor.max_versions


def iso(dt):
    """Datetime Odoo (UTC, наивный) → строка ISO 8601 для JSON."""
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ") if dt else None


class WhProject(models.Model):
    _name = "wh.project"
    _description = "Проєкт конструктора складу"
    _order = "name, id"

    name = fields.Char(required=True)
    key = fields.Char(string="Ідентифікатор у застосунку", required=True, index=True, copy=False,
                      help="Поле id проєкту v2 у застосунку; за ним застосунок знаходить проєкт.")
    company_id = fields.Many2one("res.company", string="Компанія", default=lambda self: self.env.company, index=True)
    warehouse_ids = fields.Many2many("stock.warehouse", "wh_project_warehouse_rel", "project_id", "warehouse_id", string="Склади")
    data = fields.Json(string="Проєкт (JSON v2)")
    schema = fields.Integer(string="Схема даних")
    rev = fields.Integer(string="Номер ревізії", default=1, readonly=True, copy=False,
                         help="Збільшується при кожному записі; за ним виявляється конфлікт збереження.")
    version_ids = fields.One2many("wh.project.version", "project_id", string="Версії")
    lock_ids = fields.One2many("wh.zone.lock", "project_id", string="Блокування зон")

    @api.constrains("key", "company_id")
    def _check_key_unique(self):
        for p in self:
            if self.sudo().search_count([("key", "=", p.key), ("company_id", "=", p.company_id.id), ("id", "!=", p.id)]):
                raise ValidationError(_("Проєкт з ідентифікатором «%s» уже існує в цій компанії.", p.key))

    # ------------------------------------------------------------ служебное
    @api.model
    def _max_versions(self):
        try:
            n = int(self.env["ir.config_parameter"].sudo().get_param("wh_constructor.max_versions", MAX_VERSIONS))
        except (TypeError, ValueError):
            n = MAX_VERSIONS
        return max(n, 1)

    def _lock_row(self):
        """Блокировка строки проекта до конца транзакции: сохранения одного проекта идут по очереди."""
        self.env.cr.execute("SELECT id FROM wh_project WHERE id = %s FOR UPDATE", [self.id])
        self.invalidate_recordset(["rev"])

    def _find(self, key):
        return self.search([("key", "=", key)], limit=1)

    def _summary(self):
        self.ensure_one()
        d = self.data if isinstance(self.data, dict) else {}
        return {
            "id": self.key, "name": self.name, "source": d.get("source"), "loaded_at": d.get("loaded_at"),
            "warehouses": len(d.get("warehouses") or []), "rev": self.rev,
            "by": self.write_uid.name, "at": iso(self.write_date),
        }

    def _stale(self):
        self.ensure_one()
        return {"status": "stale", "rev": self.rev, "by": self.write_uid.name, "at": iso(self.write_date)}

    def _link_warehouses(self, data):
        """Склады Odoo по кодам складов проекта (best effort: проект может содержать склады без записи в Odoo)."""
        codes = [w.get("code") for w in (data.get("warehouses") or []) if isinstance(w, dict) and w.get("code")]
        found = self.env["stock.warehouse"].search([("code", "in", codes)]) if codes else self.env["stock.warehouse"]
        return [(6, 0, found.ids)]

    # ------------------------------------------------------------ API для контроллеров
    @api.model
    def api_list(self):
        return [p._summary() for p in self.search([])]

    @api.model
    def api_load(self, key):
        p = self._find(key)
        if not p:
            return {"found": False}
        return {"found": True, "data": p.data, "rev": p.rev, "name": p.name, "by": p.write_uid.name, "at": iso(p.write_date)}

    @api.model
    def api_save(self, key, data, name=None, base_rev=None, commit=True, comment=None):
        """Записать проект. base_rev — ревизия, на которой основаны правки (None — новый проект).
        Если проект в базе уже новее — {"status": "stale", ...}, ничего не меняется.
        commit=True — создаётся версия (хранятся последние N); черновик (commit=False) версий не плодит."""
        if not key or not isinstance(data, dict):
            raise ValidationError(_("Потрібні ідентифікатор і дані проєкту."))
        vals = {"data": data, "schema": data.get("schema") or 0, "name": name or data.get("name") or key}
        p = self._find(key)
        if p:
            p._lock_row()
            if base_rev != p.rev:
                return p._stale()
            vals.update(rev=p.rev + 1, warehouse_ids=p._link_warehouses(data))
            p.write(vals)
        else:
            p = self.create({**vals, "key": key, "rev": 1, "warehouse_ids": self._link_warehouses(data)})
        version = self.env["wh.project.version"]
        if commit:
            version = version.create({"project_id": p.id, "rev": p.rev, "data": data, "comment": comment or False})
            version._prune(p)
        return {"status": "ok", "rev": p.rev, "version_id": version.id or None}

    @api.model
    def api_delete(self, key):
        p = self._find(key)
        if p:
            p.unlink()
        return {"status": "ok", "deleted": bool(p)}

    @api.model
    def api_versions(self, key):
        p = self._find(key)
        if not p:
            return []
        return [v._summary() for v in self.env["wh.project.version"].search([("project_id", "=", p.id)], order="rev desc, id desc")]

    @api.model
    def api_restore(self, key, version_id, base_rev=None):
        """Вернуть данные версии как новую ревизию проекта (история не переписывается: появляется ещё одна версия)."""
        p = self._find(key)
        v = self.env["wh.project.version"].browse(int(version_id)).exists()
        if not p or not v or v.project_id != p:
            return {"status": "missing"}
        p._lock_row()
        if base_rev != p.rev:
            return p._stale()
        p.write({"data": v.data, "schema": (v.data or {}).get("schema") or 0, "rev": p.rev + 1, "warehouse_ids": p._link_warehouses(v.data or {})})
        new = self.env["wh.project.version"].create({
            "project_id": p.id, "rev": p.rev, "data": v.data, "comment": _("Відновлено версію №%s", v.rev)})
        new._prune(p)
        return {"status": "ok", "rev": p.rev, "data": p.data, "version_id": new.id}
