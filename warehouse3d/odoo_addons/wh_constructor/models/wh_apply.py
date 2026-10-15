from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from .wh_project import iso

G_DESIGN = "wh_constructor.group_wh_design"
G_APPLY = "wh_constructor.group_wh_apply"

KINDS = ("category", "create", "move", "rename", "attrs", "orderpoint", "archive")
USAGES = ("internal", "view")
POLICIES = ("empty", "same", "mixed")
# поля локации, которые план может писать (W-13, W-14); posx / posy / posz есть только в Odoo 18, остальные поля — по наличию в версии (R-02)
ATTR_FIELDS = ("barcode", "posx", "posy", "posz", "storage_category_id", "replenish_location", "scrap_location", "removal_strategy_id", "usage")
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
    n_categories = fields.Integer(string="Категорії зберігання")
    n_orderpoints = fields.Integer(string="Правила поповнення")
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
            if c["kind"] == "category":
                out.append(self._clean_category(o, c))
                continue
            if c["kind"] == "orderpoint":
                out.append(self._clean_orderpoint(o, c))
                continue
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
    def _clean_category(self, o, c):
        """Операция над категорией хранения: create (ref, имя) или update (id); vals — max_weight, allow_new_product, capacities [{product | product_id, package_type_id, quantity}]."""
        v = c["vals"]
        if not c["name"].strip():
            raise UserError(_("Порожня назва категорії зберігання."))
        if o.get("id") is not None:
            c["id"] = int(o["id"])
        elif o.get("ref"):
            c["ref"] = str(o["ref"])
        else:
            raise UserError(_("Категорія «%s»: немає ні id, ні ref.", c["name"]))
        try:
            c["max_weight"] = float(v.get("max_weight") or 0)
        except (TypeError, ValueError):
            raise UserError(_("Категорія «%s»: некоректна максимальна вага.", c["name"]))
        if c["max_weight"] < 0:
            raise UserError(_("Категорія «%s»: максимальна вага не може бути від'ємною.", c["name"]))
        c["policy"] = v.get("allow_new_product") if v.get("allow_new_product") in POLICIES else "mixed"
        caps, seen = [], set()
        for k in v.get("capacities") or []:
            if not isinstance(k, dict):
                raise UserError(_("Категорія «%s»: некоректна ємність.", c["name"]))
            prod, pkg = k.get("product") or k.get("product_id") or None, k.get("package_type_id") or None
            try:
                qty = float(k.get("quantity"))
            except (TypeError, ValueError):
                qty = 0.0
            if bool(prod) == bool(pkg) or qty <= 0:
                raise UserError(_("Категорія «%s»: ємність — це або товар, або тип упаковки, і кількість більша за нуль.", c["name"]))
            key = ("p", str(prod)) if prod else ("k", int(pkg))
            if key in seen:
                raise UserError(_("Категорія «%s»: ємність задано двічі (%s).", c["name"], prod or pkg))
            seen.add(key)
            caps.append({"product": prod, "package_type_id": int(pkg) if pkg else None, "quantity": qty})
        c["capacities"] = caps
        return c

    @api.model
    def _clean_orderpoint(self, o, c):
        """Правило пополнения места: create (без id) или update (id); location_id, product (код) или product_id, min, max."""
        try:
            c.update({"min": float(o.get("min")), "max": float(o.get("max"))})
        except (TypeError, ValueError):
            raise UserError(_("Правило поповнення «%s»: некоректні min / max.", c["name"]))
        if c["min"] < 0 or c["max"] < c["min"]:
            raise UserError(_("Правило поповнення «%s»: min не може бути від'ємним і більшим за max.", c["name"]))
        if o.get("id") is not None:
            c["id"] = int(o["id"])
        if o.get("location_id") is None:
            raise UserError(_("Правило поповнення «%s» без локації.", c["name"]))
        c["location_id"] = int(o["location_id"])
        c["product"] = str(o.get("product") or "") or None
        c["product_id"] = int(o["product_id"]) if o.get("product_id") else None
        if c.get("id") is None and not (c["product"] or c["product_id"]):
            raise UserError(_("Правило поповнення «%s»: потрібен товар.", c["name"]))
        return c

    @api.model
    def _write_vals(self, Loc, vals, refs=None):
        """Значения полей атрибутов, которые есть в этой версии Odoo; остальные пропускаются. storage_category_id может быть { ref } категории, созданной этим же планом."""
        out, skipped = {}, []
        for k, v in (vals or {}).items():
            if k not in ATTR_FIELDS or k not in Loc._fields:
                skipped.append(k)
                continue
            if k == "usage" and v not in USAGES:
                raise UserError(_("Невідомий тип локації «%s».", v))
            if k in ("storage_category_id", "removal_strategy_id"):
                v = (refs or {}).get(v.get("ref")) if isinstance(v, dict) else v
                if v in ("", None, False):
                    v = False
                elif not self.env[Loc._fields[k].comodel_name].sudo().browse(int(v)).exists():
                    raise UserError(_("Запис %s (%s) не знайдено.", k, v))
                else:
                    v = int(v)
            out[k] = v if v not in ("", None) or Loc._fields[k].type not in ("many2one", "char") else False
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
            self._do_categories(wh, [o for o in ops if o["kind"] == "category"], refs, journal)
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
                vals, skipped = self._write_vals(Loc, o["vals"], refs)
                if "barcode" in vals:
                    self._check_barcode(Loc, loc.company_id or wh.company_id, vals["barcode"], exclude=loc.id)
                if vals.get("usage") == "view" and loc.usage != "view":
                    self._check_empty(Loc, loc)  # внутреннее место с остатком видом не станет
                old = {k: (loc[k].id if Loc._fields[k].type == "many2one" else loc[k]) for k in vals}
                journal.append({"op": "attrs", "id": loc.id, "name": loc.name, "old": old, "new": vals, "skipped": skipped})
                loc.write(vals)
            self._do_orderpoints(wh, Loc, inside, [o for o in ops if o["kind"] == "orderpoint"], refs, journal)
            self._do_archive(wh, Loc, inside, [o for o in ops if o["kind"] == "archive"], journal)
            log = self.sudo().create({
                "name": "%s · %s" % (wh.code, fields.Datetime.now().strftime("%Y-%m-%d %H:%M")), "project_key": project_key or False,
                "project_id": self.env["wh.project"].sudo().search([("key", "=", project_key)], limit=1).id if project_key else False,
                "warehouse_id": wh.id, "warehouse_code": wh.code, "company_id": wh.company_id.id, "user_id": self.env.user.id, "ops": journal, "comment": (comment or "")[:200] or False,
                "n_created": sum(1 for j in journal if j["op"] == "create"), "n_moved": sum(1 for j in journal if j["op"] == "move"),
                "n_renamed": sum(1 for j in journal if j["op"] == "rename"), "n_attrs": sum(1 for j in journal if j["op"] == "attrs"),
                "n_archived": sum(1 for j in journal if j["op"] == "archive"),
                "n_categories": sum(1 for j in journal if j["op"] in ("category_create", "category_update")),
                "n_orderpoints": sum(1 for j in journal if j["op"] in ("orderpoint_create", "orderpoint_update")),
            })
        return {"status": "ok", "log_id": log.id, "refs": refs, "counts": self._counts(log)}

    @api.model
    def _counts(self, log):
        return {"category": log.n_categories, "create": log.n_created, "move": log.n_moved, "rename": log.n_renamed, "attrs": log.n_attrs, "orderpoint": log.n_orderpoints, "archive": log.n_archived}

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
                vals, skipped = self._write_vals(Loc, o["vals"], refs)
                self._check_barcode(Loc, wh.company_id, vals.get("barcode"))
                loc = Loc.create({"name": o["name"], "location_id": pid, "company_id": wh.company_id.id, **{"usage": o["usage"], **vals}})
                refs[o["ref"]] = loc.id
                inside.add(loc.id)
                journal.append({"op": "create", "id": loc.id, "name": loc.name, "parent": pid, "usage": o["usage"], "ref": o["ref"], "skipped": skipped})
                todo.remove(o)
                placed = True
            guard += 1
            if not placed or guard > MAX_OPS:
                raise UserError(_("Для частини нових локацій немає батьківської (%s).", ", ".join(o["name"] for o in todo[:5])))

    # ------------------------------------------------------------ категории хранения и правила пополнения (W-14)
    @api.model
    def _caps_commands(self, caps):
        """Команды ёмкостей категории: товар — по коду (default_code, запасной вариант «ID<id>»), тип упаковки — по id."""
        Prod, Pkg, cmds = self.env["product.product"].sudo(), self.env["stock.package.type"].sudo(), []
        for k in caps:
            vals = {"quantity": k["quantity"]}
            if k.get("product"):
                vals["product_id"] = self._product(Prod, k["product"]).id
            else:
                pkg = Pkg.browse(k["package_type_id"]).exists()
                if not pkg:
                    raise UserError(_("Тип упаковки %s не знайдено.", k["package_type_id"]))
                vals["package_type_id"] = pkg.id
            cmds.append(fields.Command.create(vals))
        return cmds

    @api.model
    def _product(self, Prod, code):
        found = Prod.search([("default_code", "=", code)])
        if not found and str(code).startswith("ID") and str(code)[2:].isdigit():
            found = Prod.browse(int(str(code)[2:])).exists()
        if not found:
            raise UserError(_("Товар з кодом «%s» не знайдено.", code))
        if len(found) > 1:
            raise UserError(_("Код товару «%s» збігається у кількох товарів.", code))
        return found

    @api.model
    def _cat_state(self, cat):
        return {"name": cat.name, "max_weight": cat.max_weight, "allow_new_product": cat.allow_new_product,
                "capacities": [{"product_id": k.product_id.id or None, "package_type_id": k.package_type_id.id or None, "quantity": k.quantity} for k in cat.capacity_ids]}

    @api.model
    def _do_categories(self, wh, cats, refs, journal):
        Cat = self.env["stock.storage.category"].sudo()
        for o in cats:
            vals = {"name": o["name"], "max_weight": o["max_weight"], "allow_new_product": o["policy"]}
            if o.get("id") is not None:
                cat = Cat.browse(o["id"]).exists()
                if not cat or cat.company_id.id not in (False, wh.company_id.id):
                    raise UserError(_("Категорію зберігання %s не знайдено або вона належить іншій компанії.", o["id"]))
                journal.append({"op": "category_update", "id": cat.id, "name": cat.name, "old": self._cat_state(cat)})
                cat.write({**vals, "capacity_ids": [fields.Command.clear()] + self._caps_commands(o["capacities"])})
            else:
                cat = Cat.create({**vals, "company_id": wh.company_id.id, "capacity_ids": self._caps_commands(o["capacities"])})
                refs[o["ref"]] = cat.id
                journal.append({"op": "category_create", "id": cat.id, "name": cat.name, "ref": o["ref"]})

    @api.model
    def _do_orderpoints(self, wh, Loc, inside, ops, refs, journal):
        OP = self.with_context(allowed_company_ids=self.env.user.company_ids.ids).env["stock.warehouse.orderpoint"].sudo()
        Prod = self.env["product.product"].sudo()
        for o in ops:
            loc = self._existing(Loc, inside, o["location_id"])
            if o.get("id") is not None:
                rule = OP.browse(o["id"]).exists()
                if not rule or rule.location_id.id not in inside:
                    raise UserError(_("Правило поповнення %s не належить цьому складу.", o["id"]))
                journal.append({"op": "orderpoint_update", "id": rule.id, "name": rule.display_name, "location": rule.location_id.id,
                                "old": {"product_min_qty": rule.product_min_qty, "product_max_qty": rule.product_max_qty}})
                rule.write({"product_min_qty": o["min"], "product_max_qty": o["max"]})
            else:
                prod = Prod.browse(o["product_id"]).exists() if o.get("product_id") else self._product(Prod, o["product"])
                if not prod:
                    raise UserError(_("Товар правила поповнення «%s» не знайдено.", o["name"]))
                if OP.search_count([("location_id", "=", loc.id), ("product_id", "=", prod.id)]):
                    raise UserError(_("Для товару «%s» на локації «%s» правило поповнення вже є.", prod.display_name, loc.complete_name))
                rule = OP.create({"location_id": loc.id, "product_id": prod.id, "warehouse_id": wh.id, "company_id": wh.company_id.id,
                                  "product_min_qty": o["min"], "product_max_qty": o["max"]})
                journal.append({"op": "orderpoint_create", "id": rule.id, "name": rule.display_name, "location": loc.id})

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
        mine = self._touched(ops)
        for later in self.sudo().search([("warehouse_id", "=", log.warehouse_id.id), ("state", "=", "applied"), ("id", ">", log.id)]):
            if mine & self._touched(later.ops or []):
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
            self._rollback_rules(Loc, ops)
            log.sudo().write({"state": "rolled_back", "rolled_back_by": self.env.user.id, "rolled_back_at": fields.Datetime.now()})
        return {"status": "ok", "log_id": log.id}

    @api.model
    def _touched(self, ops):
        """Ключи затронутых записей: id локаций, категорий и правил пополнения не смешиваются."""
        return {(j["op"].split("_")[0] if j["op"].startswith(("category", "orderpoint")) else "loc", j["id"]) for j in ops}

    @api.model
    def _rollback_rules(self, Loc, ops):
        """Откат правил пополнения (вернуть min / max, созданные — в архив) и категорий хранения (вернуть значения, созданные — удалить, если ими не пользуются другие локации)."""
        OP = self.env["stock.warehouse.orderpoint"].sudo().with_context(active_test=False)
        for j in reversed(ops):
            rule = OP.browse(j["id"]).exists() if j["op"].startswith("orderpoint") else None
            if rule and j["op"] == "orderpoint_update":
                rule.write(j["old"])
            elif rule:
                rule.write({"active": False})
        Cat = self.env["stock.storage.category"].sudo()
        made = [x["id"] for x in ops if x["op"] == "create"]
        for j in reversed(ops):
            cat = Cat.browse(j["id"]).exists() if j["op"].startswith("category") else None
            if not cat:
                continue
            if j["op"] == "category_update":
                old = j["old"]
                cat.write({"name": old["name"], "max_weight": old["max_weight"], "allow_new_product": old["allow_new_product"],
                           "capacity_ids": [fields.Command.clear()] + [fields.Command.create({k: v for k, v in c.items() if v}) for c in old["capacities"]]})
            elif not Loc.search_count([("storage_category_id", "=", cat.id), ("id", "not in", made)]):
                Loc.search([("storage_category_id", "=", cat.id)]).write({"storage_category_id": False})  # только созданные этим применением (и архивные)
                cat.unlink()  # категория, которой пользуются другие локации, остаётся

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
                        "counts": self._counts(r),
                        "ops": ops[:LOG_OPS_SHOWN], "more": max(len(ops) - LOG_OPS_SHOWN, 0),
                        "rolled_back_by": r.rolled_back_by.name or None, "rolled_back_at": iso(r.rolled_back_at)})
        return out
