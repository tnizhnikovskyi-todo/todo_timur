from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from .wh_project import iso

G_DESIGN = "wh_constructor.group_wh_design"
G_APPLY = "wh_constructor.group_wh_apply"

KINDS = ("create", "move", "rename", "attrs", "archive")
USAGES = ("internal", "view")
# поля локации, которые план может писать (W-13); posx / posy / posz есть только в Odoo 18, остальные поля — по наличию в версии (R-02)
ATTR_FIELDS = ("barcode", "posx", "posy", "posz", "storage_category_id", "replenish_location", "scrap_location")
MAX_OPS = 20000
LOG_OPS_SHOWN = 300


class WhApplyLog(models.Model):
    """Журнал применений плана изменений к локациям Odoo (W-13, G5, G8): кто, когда, проект, склад и список операций с прежними значениями.
    По записи журнала применение откатывается (api_rollback). Записи создаёт и меняет только сервер (sudo после проверки группы «застосування»)."""
    _name = "wh.apply.log"
    _description = "Журнал застосувань конструктора складу"
    _order = "date desc, id desc"

    name = fields.Char(required=True)
    project_key = fields.Char(string="Проєкт (ключ)", index=True)
    project_id = fields.Many2one("wh.project", string="Проєкт", ondelete="set null")
    warehouse_id = fields.Many2one("stock.warehouse", string="Склад", ondelete="set null", index=True)
    warehouse_code = fields.Char(string="Код складу")
    company_id = fields.Many2one("res.company", string="Компанія", index=True)
    user_id = fields.Many2one("res.users", string="Хто", required=True, default=lambda self: self.env.user, ondelete="restrict")
    date = fields.Datetime(string="Коли", required=True, default=fields.Datetime.now)
    state = fields.Selection([("applied", "Застосовано"), ("rolled_back", "Відкочено")], string="Стан", default="applied", required=True, index=True)
    ops = fields.Json(string="Операції (з прежніми значеннями)")
    n_created = fields.Integer(string="Створено")
    n_moved = fields.Integer(string="Перенесено")
    n_renamed = fields.Integer(string="Перейменовано")
    n_attrs = fields.Integer(string="Атрибути")
    n_archived = fields.Integer(string="Архівовано")
    comment = fields.Char(string="Коментар")
    rolled_back_by = fields.Many2one("res.users", string="Хто відкотив", ondelete="set null")
    rolled_back_at = fields.Datetime(string="Коли відкочено")

    # ------------------------------------------------------------ общее
    @api.model
    def _need(self, group):
        if not self.env.user.has_group(group):
            raise AccessError(_("Немає права «Конструктор: застосування в Odoo».") if group == G_APPLY else _("Немає права «Конструктор: проєктування»."))

    @api.model
    def _locations(self):
        """Локации с правами сервера (после проверки группы) в пределах компаний пользователя; архивные тоже видны."""
        return self.with_context(allowed_company_ids=self.env.user.company_ids.ids, active_test=False).env["stock.location"].sudo()

    @api.model
    def _warehouse(self, warehouse_id):
        env = self.with_context(allowed_company_ids=self.env.user.company_ids.ids).env
        wh = env["stock.warehouse"].search([("id", "=", int(warehouse_id or 0))], limit=1)  # права и правила компаний пользователя
        if not wh:
            raise UserError(_("Склад не знайдено або він недоступний."))
        return wh

    @api.model
    def _clean_ops(self, ops):
        if not isinstance(ops, list) or not ops:
            raise UserError(_("Немає операцій для застосування."))
        if len(ops) > MAX_OPS:
            raise UserError(_("Забагато операцій за раз (не більше %s).", MAX_OPS))
        out = []
        for i, o in enumerate(ops):
            if not isinstance(o, dict) or o.get("kind") not in KINDS:
                raise UserError(_("Невідома операція №%s.", i + 1))
            c = {"kind": o["kind"], "name": str(o.get("name") or "")[:200], "vals": o.get("vals") if isinstance(o.get("vals"), dict) else {}}
            for k in ("id", "ref"):
                if o.get(k) is not None:
                    c[k] = int(o[k]) if k == "id" else str(o[k])
            for k in ("parent", "to"):
                p = o.get(k)
                if isinstance(p, dict):
                    c[k] = {"id": int(p["id"])} if p.get("id") is not None else {"ref": str(p.get("ref") or "")}
            if c["kind"] == "create":
                if not c["name"].strip() or not c.get("ref") or "parent" not in c or o.get("usage") not in USAGES:
                    raise UserError(_("Некоректна операція створення: %s.", c["name"]))
                c["usage"] = o["usage"]
            elif c["kind"] == "move" and "to" not in c:
                raise UserError(_("Некоректна операція переносу: %s.", c["name"]))
            elif c["kind"] == "rename" and not c["name"].strip():
                raise UserError(_("Порожня нова назва."))
            if c["kind"] != "create" and c.get("id") is None:
                raise UserError(_("Операція без локації: %s.", c["name"]))
            out.append(c)
        return out

    @api.model
    def _write_vals(self, Loc, vals):
        """Значения полей атрибутов, которые есть в этой версии Odoo; остальные пропускаются."""
        out, skipped = {}, []
        for k, v in (vals or {}).items():
            if k in ATTR_FIELDS and k in Loc._fields:
                out[k] = v if v not in ("", None) or Loc._fields[k].type not in ("many2one", "char") else False
            else:
                skipped.append(k)
        return out, skipped

    @api.model
    def _check_barcode(self, Loc, company, barcode, exclude=None):
        if barcode and Loc.search_count([("barcode", "=", barcode), ("company_id", "in", [company.id, False]), ("id", "!=", exclude or 0)]):
            raise UserError(_("Штрихкод «%s» уже використовується іншою локацією.", barcode))

    @api.model
    def _check_empty(self, Loc, locs):
        """Архивировать можно только пустое (F4): нет остатков (количество ≠ 0) и незавершённых перемещений ни на локации, ни под ней."""
        ids = Loc.search([("id", "child_of", locs.ids)]).ids
        quant = self.env["stock.quant"].sudo().search([("location_id", "in", ids), ("quantity", "!=", 0)], limit=1)
        if quant:
            raise UserError(_("Локація «%s» не порожня: є залишок (%s).", quant.location_id.complete_name, quant.product_id.display_name))
        move = self.env["stock.move"].sudo().search([("state", "not in", ("done", "cancel")), "|", ("location_id", "in", ids), ("location_dest_id", "in", ids)], limit=1)
        if move:
            raise UserError(_("З локацією «%s» пов'язане незавершене переміщення %s.", (move.location_id | move.location_dest_id).filtered(lambda x: x.id in ids)[:1].complete_name, move.reference or move.display_name))

    # ------------------------------------------------------------ применение
    @api.model
    def api_apply(self, warehouse_id=None, ops=None, project_key=None, comment=None):
        """Применить план одной транзакцией: создание (родители раньше) → переносы → переименования → атрибуты → архивация.
        Архивируются только пустые локации (остаток и незавершённые перемещения проверяются здесь, а не на клиенте). Ошибка в любом месте — ничего не применено."""
        self._need(G_APPLY)
        ops = self._clean_ops(ops)
        wh = self._warehouse(warehouse_id)
        Loc = self._locations()
        inside = set(Loc.search([("id", "child_of", wh.view_location_id.id)]).ids)
        with self.env.cr.savepoint():
            refs, journal = {}, []
            self._do_create(wh, Loc, inside, [o for o in ops if o["kind"] == "create"], refs, journal)
            for o in (x for x in ops if x["kind"] == "move"):
                loc = self._existing(Loc, inside, o["id"])
                pid = self._parent_id(o["to"], refs, inside)
                if pid in Loc.search([("id", "child_of", loc.id)]).ids:
                    raise UserError(_("Не можна перенести «%s» всередину себе.", loc.complete_name))
                journal.append({"op": "move", "id": loc.id, "name": loc.name, "from": loc.location_id.id, "to": pid})
                loc.write({"location_id": pid})
            for o in (x for x in ops if x["kind"] == "rename"):
                loc = self._existing(Loc, inside, o["id"])
                journal.append({"op": "rename", "id": loc.id, "old": loc.name, "new": o["name"]})
                loc.write({"name": o["name"]})
            for o in (x for x in ops if x["kind"] == "attrs"):
                loc = self._existing(Loc, inside, o["id"])
                vals, skipped = self._write_vals(Loc, o["vals"])
                if "barcode" in vals:
                    self._check_barcode(Loc, loc.company_id or wh.company_id, vals["barcode"], exclude=loc.id)
                old = {k: (loc[k].id if Loc._fields[k].type == "many2one" else loc[k]) for k in vals}
                journal.append({"op": "attrs", "id": loc.id, "name": loc.name, "old": old, "new": vals, "skipped": skipped})
                loc.write(vals)
            self._do_archive(wh, Loc, inside, [o for o in ops if o["kind"] == "archive"], journal)
            log = self.sudo().create({
                "name": "%s · %s" % (wh.code, fields.Datetime.now().strftime("%Y-%m-%d %H:%M")), "project_key": project_key or False,
                "project_id": self.env["wh.project"].sudo().search([("key", "=", project_key)], limit=1).id if project_key else False,
                "warehouse_id": wh.id, "warehouse_code": wh.code, "company_id": wh.company_id.id, "user_id": self.env.user.id, "ops": journal, "comment": (comment or "")[:200] or False,
                "n_created": sum(1 for j in journal if j["op"] == "create"), "n_moved": sum(1 for j in journal if j["op"] == "move"),
                "n_renamed": sum(1 for j in journal if j["op"] == "rename"), "n_attrs": sum(1 for j in journal if j["op"] == "attrs"),
                "n_archived": sum(1 for j in journal if j["op"] == "archive"),
            })
        return {"status": "ok", "log_id": log.id, "refs": refs, "counts": {"create": log.n_created, "move": log.n_moved, "rename": log.n_renamed, "attrs": log.n_attrs, "archive": log.n_archived}}

    @api.model
    def _existing(self, Loc, inside, loc_id):
        if loc_id not in inside:
            raise UserError(_("Локація %s не належить цьому складу.", loc_id))
        return Loc.browse(loc_id)

    @api.model
    def _parent_id(self, p, refs, inside):
        pid = refs.get(p["ref"]) if p.get("ref") else p.get("id")
        if pid is None:
            raise UserError(_("Батьківську локацію не знайдено (%s).", p.get("ref") or p.get("id")))
        if pid not in inside and pid not in refs.values():
            raise UserError(_("Локація %s не належить цьому складу.", pid))
        return pid

    @api.model
    def _do_create(self, wh, Loc, inside, creates, refs, journal):
        todo, guard = list(creates), 0
        while todo:
            placed = False
            for o in list(todo):
                p = o["parent"]
                if p.get("ref") and p["ref"] not in refs:
                    continue
                pid = self._parent_id(p, refs, inside)
                if not Loc.browse(pid).active:
                    raise UserError(_("Батьківська локація «%s» в архіві.", Loc.browse(pid).complete_name))
                vals, skipped = self._write_vals(Loc, o["vals"])
                self._check_barcode(Loc, wh.company_id, vals.get("barcode"))
                loc = Loc.create({"name": o["name"], "location_id": pid, "usage": o["usage"], "company_id": wh.company_id.id, **vals})
                refs[o["ref"]] = loc.id
                inside.add(loc.id)
                journal.append({"op": "create", "id": loc.id, "name": loc.name, "parent": pid, "usage": o["usage"], "ref": o["ref"], "skipped": skipped})
                todo.remove(o)
                placed = True
            guard += 1
            if not placed or guard > MAX_OPS:
                raise UserError(_("Для частини нових локацій немає батьківської (%s).", ", ".join(o["name"] for o in todo[:5])))

    @api.model
    def _do_archive(self, wh, Loc, inside, archives, journal):
        locs = Loc.browse([self._existing(Loc, inside, o["id"]).id for o in archives])
        protect = wh.view_location_id | wh.lot_stock_id
        for loc in locs:
            if loc in protect:
                raise UserError(_("Локацію «%s» склад використовує — архівувати її не можна.", loc.complete_name))
            if not loc.active:
                raise UserError(_("Локація «%s» уже в архіві.", loc.complete_name))
        self._check_empty(Loc, locs)  # до першої зміни: перевірка на сервері, а не довіра клієнту
        for loc in locs.sorted(key=lambda x: -(x.parent_path or "").count("/")):  # діти раніше батьків
            kids = Loc.search([("id", "child_of", loc.id), ("id", "!=", loc.id), ("active", "=", False)]).ids  # вже архівні — при відкаті знову архівуються
            journal.append({"op": "archive", "id": loc.id, "name": loc.name, "was_archived_kids": kids})
            loc.write({"active": False})

    # ------------------------------------------------------------ откат
    @api.model
    def api_rollback(self, log_id=None):
        """Откатить применение по журналу: архивировать созданное, вернуть имена, родителей, атрибуты, разархивировать. Только если созданные локации
        не использовались (нет остатков и незавершённых перемещений) и нет более поздних применений, затронувших те же локации."""
        self._need(G_APPLY)
        log = self.search([("id", "=", int(log_id or 0))], limit=1)
        if not log:
            raise UserError(_("Запис журналу не знайдено."))
        if log.state != "applied":
            raise UserError(_("Це застосування вже відкочено."))
        Loc = self._locations()
        ops = log.ops or []
        mine = {j["id"] for j in ops}
        for later in self.sudo().search([("warehouse_id", "=", log.warehouse_id.id), ("state", "=", "applied"), ("id", ">", log.id)]):
            if mine & {j["id"] for j in (later.ops or [])}:
                raise UserError(_("Спершу відкотіть пізніше застосування «%s»: воно змінило ті самі локації.", later.name))
        created = Loc.browse([j["id"] for j in ops if j["op"] == "create" and Loc.browse(j["id"]).exists() and Loc.browse(j["id"]).active])
        if created:
            self._check_empty(Loc, created)
        with self.env.cr.savepoint():
            for j in reversed([j for j in ops if j["op"] == "archive"]):  # батьки раніше дітей
                loc = Loc.browse(j["id"]).exists()
                if loc:
                    loc.write({"active": True})
                    if j.get("was_archived_kids"):
                        Loc.browse(j["was_archived_kids"]).exists().write({"active": False})
            for j in ops:
                if j["op"] == "attrs":
                    Loc.browse(j["id"]).exists().write({k: v for k, v in (j.get("old") or {}).items() if k in Loc._fields})
            for j in ops:
                if j["op"] == "rename":
                    Loc.browse(j["id"]).exists().write({"name": j["old"]})
            for j in reversed([j for j in ops if j["op"] == "move"]):
                loc = Loc.browse(j["id"]).exists()
                if loc and j.get("from"):
                    loc.write({"location_id": j["from"]})
            for j in reversed([j for j in ops if j["op"] == "create"]):  # діти раніше батьків
                loc = Loc.browse(j["id"]).exists()
                if loc and loc.active:
                    loc.write({"active": False})
            log.sudo().write({"state": "rolled_back", "rolled_back_by": self.env.user.id, "rolled_back_at": fields.Datetime.now()})
        return {"status": "ok", "log_id": log.id}

    # ------------------------------------------------------------ журнал
    @api.model
    def api_list(self, project_key=None, warehouse_id=None, limit=50):
        self._need(G_DESIGN)
        domain = []
        if project_key:
            domain.append(("project_key", "=", project_key))
        if warehouse_id:
            domain.append(("warehouse_id", "=", int(warehouse_id)))
        out = []
        for r in self.search(domain, limit=min(max(int(limit or 50), 1), 200)):
            ops = r.ops or []
            out.append({"id": r.id, "name": r.name, "date": iso(r.date), "user": r.user_id.name, "state": r.state, "project": r.project_key, "warehouse_id": r.warehouse_id.id or None,
                        "warehouse": r.warehouse_code, "comment": r.comment or None,
                        "counts": {"create": r.n_created, "move": r.n_moved, "rename": r.n_renamed, "attrs": r.n_attrs, "archive": r.n_archived},
                        "ops": ops[:LOG_OPS_SHOWN], "more": max(len(ops) - LOG_OPS_SHOWN, 0),
                        "rolled_back_by": r.rolled_back_by.name or None, "rolled_back_at": iso(r.rolled_back_at)})
        return out
