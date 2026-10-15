import json
import logging
import re
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from ..tools.states import parse_ts
from .f3d_gantry_stack import gantry_cmd_signal
from .f3d_machine import param_bool

_logger = logging.getLogger(__name__)

SHEET_LOG_MAX = 200
IDLE_MIN = 30  # R-16 п. 5
CRON_JOBS_LIMIT = 20
CRON_STACKS_LIMIT = 27
OPEN_STATES = ("draft", "to_send", "sent", "queued", "active")
MO_LIVE = ("confirmed", "progress", "to_close")
WS_STATES = {"queued": "queued", "active": "active", "done": "done", "cancelled": "cancelled", "error": "error"}
TERMINAL = ("done", "cancelled")


class F3dGantryJob(models.Model):
    _name = "f3d.gantry.job"
    _description = "Портал: завдання"
    _inherit = ["mail.thread"]
    _order = "id desc"

    name = fields.Char(
        string="Номер",
        required=True,
        copy=False,
        default=lambda s: s.env["ir.sequence"].next_by_code("f3d.gantry.job"),
    )
    ws_id = fields.Char(string="Номер у woodStore", size=32, index=True, copy=False)
    type = fields.Selection(
        [
            ("feed", "Подача на верстат"),
            ("restack", "Перекладання"),
            ("return", "Повернення в стос"),
            ("count", "Перерахунок"),
        ],
        required=True,
        default="feed",
    )
    origin = fields.Selection(
        [("odoo", "Odoo"), ("machine", "Портал")], required=True, default="odoo", string="Створено в"
    )
    stack_id = fields.Many2one("f3d.gantry.stack", string="Стос", ondelete="set null")
    target_workcenter_id = fields.Many2one(
        "mrp.workcenter",
        string="На верстат",
        ondelete="set null",
        domain="[('f3d_code', 'in', ('SAW-1', 'SAW-2', 'SAW-3', 'NEST-1'))]",
    )
    target_code = fields.Char(related="target_workcenter_id.f3d_code")
    sheets = fields.Integer(string="Листів", required=True, default=1)
    done = fields.Integer(string="Подано", default=0, tracking=True)
    product_id = fields.Many2one("product.product", string="Плита")
    lot_id = fields.Many2one("stock.lot", string="Партія")
    priority = fields.Integer(string="Пріоритет", default=5, help="1…9")
    external_ref = fields.Char(string="Документ", size=64, help="Назва МО")
    production_id = fields.Many2one("mrp.production", ondelete="set null", index=True)
    workorder_id = fields.Many2one("mrp.workorder", ondelete="set null")
    cut_map_id = fields.Many2one("f3d.cut.map", ondelete="set null")
    state = fields.Selection(
        [
            ("draft", "Чернетка"),
            ("to_send", "До відправки"),
            ("sent", "Надіслано"),
            ("queued", "У черзі порталу"),
            ("active", "Виконується"),
            ("done", "Виконано"),
            ("cancelled", "Скасовано"),
            ("error", "Помилка"),
        ],
        required=True,
        index=True,
        default="draft",
        tracking=True,
    )
    command_id = fields.Many2one("f3d.command", string="Команда", ondelete="set null")
    cancel_command_id = fields.Many2one("f3d.command", ondelete="set null")
    error = fields.Char(size=512, readonly=True)
    ws_created = fields.Datetime(readonly=True)
    started = fields.Datetime(readonly=True)
    finished = fields.Datetime(readonly=True)
    sheet_log = fields.Json(string="Листи", default=lambda s: [], help="[{ts, stack, lot}], ≤ 200")
    consumed_qty = fields.Float(string="Списано в МО", readonly=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda s: s.env.company)

    _f3d_gjob_ws_uniq = models.Constraint("UNIQUE(ws_id)", "Завдання woodStore вже прив'язане.")
    _f3d_gjob_numbers = models.Constraint(
        "CHECK(sheets >= 1 AND done >= 0 AND priority BETWEEN 1 AND 9)",
        "Листів ≥ 1, подано ≥ 0, пріоритет 1…9.",
    )

    @api.constrains("type", "product_id", "target_workcenter_id", "state")
    def _check_feed(self):
        targets = self.env["f3d.gantry.stack"].GANTRY_TARGETS
        for rec in self:
            if rec.type != "feed" or rec.state in ("draft", "cancelled"):
                continue
            if not rec.product_id or not rec.target_workcenter_id:
                raise ValidationError(_("Для подачі задайте плиту і верстат."))
            if rec.target_code not in targets:
                raise ValidationError(_("Портал подає лише на SAW-1, SAW-2, SAW-3, NEST-1."))

    @api.constrains("stack_id", "product_id", "state", "origin")
    def _check_stack_product(self):
        """У стосі лежить інша плита (за квантами Odoo) -> помилка для завдань з Odoo до відправки."""
        Quant = self.env["stock.quant"].sudo()
        for rec in self:
            if (
                rec.origin != "odoo"
                or not rec.stack_id
                or not rec.product_id
                or rec.state not in ("draft", "to_send", "sent")
            ):
                continue
            quants = Quant.search([("location_id", "=", rec.stack_id.location_id.id), ("quantity", ">", 0)])
            products = quants.mapped("product_id")
            if products and rec.product_id not in products:
                raise ValidationError(
                    _("У стосі %s інша плита: %s.", rec.stack_id.code, ", ".join(products.mapped("display_name")))
                )

    # --- допоміжне ------------------------------------------------------------------------------------
    @api.model
    def _f3d_equipment(self):
        return self.env["maintenance.equipment"].sudo().search_f3d("GANTRY-1")

    @api.model
    def _f3d_post_equipment(self, text):
        eq = self._f3d_equipment()
        if eq:
            eq.message_post(body=text, subtype_xmlid="mail.mt_note")

    @api.model
    def _f3d_notify_equipment(self):
        if "f3d.viewer.event" in self.env:
            self.env["f3d.viewer.event"]._notify("maintenance.equipment", ["GANTRY-1"], "state")

    @api.model
    def _f3d_gantry_status(self):
        raw = self.env["ir.config_parameter"].sudo().get_param("factory3d.machine_connect.gantry_status", "{}")
        try:
            data = json.loads(raw or "{}")
        except ValueError:
            data = {}
        return data if isinstance(data, dict) else {}

    @api.model
    def _f3d_set_gantry_status(self, data):
        self.env["ir.config_parameter"].sudo().set_param(
            "factory3d.machine_connect.gantry_status", json.dumps(data, ensure_ascii=False, sort_keys=True)
        )

    def _check_group(self, xmlid):
        if not self.env.su and not self.env.user.has_group(xmlid):
            raise AccessError(_("Недостатньо прав для цієї дії."))

    # --- кнопки ---------------------------------------------------------------------------------------
    def action_send(self):
        self._check_group("mrp.group_mrp_user")
        for rec in self:
            if rec.state in ("draft", "error"):
                rec.sudo().write({"state": "to_send", "error": False})
        return True

    def action_retry(self):
        self._check_group("mrp.group_mrp_user")
        for rec in self.filtered(lambda r: r.state == "error"):
            rec.sudo().write({"state": "to_send", "error": False})
        return True

    def action_cancel(self):
        """R-16 п. 6."""
        for rec in self:
            if rec.state in TERMINAL:
                continue
            if rec.state in ("draft", "to_send", "error"):
                rec._check_group("mrp.group_mrp_user")
                rec.sudo().write({"state": "cancelled"})
                continue
            rec._check_group("mrp.group_mrp_manager")
            if not rec.ws_id:
                raise UserError(_("Завдання ще не прийняте порталом: скасування неможливе."))
            try:
                cmd = self.env["f3d.command"]._f3d_mc_create_command(
                    gantry_cmd_signal(self.env), "cancel", {"id": rec.ws_id}, {"f3d_gantry_job_id": rec.id}
                )
            except UserError as e:
                raise UserError(_("Скасування в порталі потребує дозволу запису.")) from e
            rec.sudo().cancel_command_id = cmd
        return True

    # --- R-16 п. 1: створення з МО --------------------------------------------------------------------
    @api.model
    def _f3d_from_production(self, production, workorder=None, cut_map=None, sheets=None):
        targets = self.env["f3d.gantry.stack"].GANTRY_TARGETS
        production = production.sudo()
        wo = (
            workorder
            or production.workorder_ids.filtered(
                lambda w: w.state not in ("done", "cancel") and w.workcenter_id.f3d_code in targets
            )[:1]
        )
        if not wo:
            raise UserError(_("У МО %s немає завдання розкрою на SAW-1…3 або NEST-1.", production.name))
        product = cut_map.material_product_id if cut_map else self.env["product.product"]
        moves = production.move_raw_ids.filtered(lambda m: m.state not in ("done", "cancel"))
        if not product:
            plates = moves.filtered(lambda m: m.product_id.f3d_thickness_mm >= 8).sorted(
                "product_uom_qty", reverse=True
            )
            product = plates[:1].product_id
        move = moves.filtered(lambda m: m.product_id == product)[:1]
        existing = self.sudo().search(
            [("production_id", "=", production.id), ("product_id", "=", product.id), ("state", "!=", "cancelled")]
        )
        live = existing.filtered(lambda j: j.state in OPEN_STATES)[:1]
        if live:
            return live
        qty = sheets or (cut_map.plan_sheets if cut_map else 0)
        if not qty:
            qty = int(move.product_uom_qty - sum(existing.mapped("sheets")))
        if qty <= 0:
            raise UserError(_("Плити для %s уже подано.", production.name))
        stack = self.env["f3d.gantry.stack"]
        lot = self.env["stock.lot"]
        lines = move.move_line_ids.filtered(lambda ml: ml.location_id.f3d_loc_kind == "stack").sorted(
            "quantity", reverse=True
        )
        if lines:
            stack = self.env["f3d.gantry.stack"].sudo().search([("location_id", "=", lines[0].location_id.id)], limit=1)
            lot = lines[0].lot_id
        return self.sudo().create(
            {
                "type": "feed",
                "origin": "odoo",
                "product_id": product.id,
                "sheets": qty,
                "stack_id": stack.id,
                "lot_id": lot.id,
                "target_workcenter_id": wo.workcenter_id.id,
                "production_id": production.id,
                "workorder_id": wo.id,
                "cut_map_id": cut_map.id if cut_map else False,
                "external_ref": production.name,
                "state": "draft",
            }
        )

    # --- R-16 п. 2: відправка -------------------------------------------------------------------------
    def _f3d_send(self):
        """`to_send` -> CMD-02 `feed`. Запис вимкнено: лишається `to_send` з текстом у `error`."""
        signal = gantry_cmd_signal(self.env)
        for rec in self.filtered(lambda r: r.state == "to_send"):
            fields_ = {
                "stack": rec.stack_id.code or None,
                "target": rec.target_code,
                "sheets": rec.sheets,
                "product": rec.product_id.default_code,
                "priority": rec.priority,
                "ref": rec.external_ref or rec.production_id.name,
            }
            try:
                with self.env.cr.savepoint():
                    cmd = self.env["f3d.command"]._f3d_mc_create_command(
                        signal, "feed", fields_, {"f3d_gantry_job_id": rec.id}
                    )
            except UserError as e:
                msg = str(e.args[0] if e.args else e)
                if "вимкнено" in msg:
                    text = ("Запис вимкнено: " + msg.split(": ", 1)[-1].rstrip("."))[:512]
                    if rec.error != text:
                        rec.sudo().error = text
                else:
                    rec.sudo().write({"state": "error", "error": msg[:512]})
                continue
            rec.sudo().write({"state": "sent", "command_id": cmd.id, "error": False})

    # --- R-16 п. 3: результат команди -----------------------------------------------------------------
    def _f3d_on_command(self, cmd):
        self.ensure_one()
        job = self.sudo()
        if cmd == job.cancel_command_id:
            if cmd.state == "done":
                job.write({"state": "cancelled", "finished": job.finished or fields.Datetime.now()})
            else:
                job.message_post(
                    body=_("Скасування в порталі не вдалося: %s", cmd.error or cmd.state), subtype_xmlid="mail.mt_note"
                )
            return
        if cmd != job.command_id or job.state in TERMINAL:
            return
        if cmd.state == "done":
            data = cmd.result_data
            ws_id = (data.get("id") if isinstance(data, dict) else None) or (cmd.result or "").strip()
            vals = {"error": False}
            if ws_id:
                other = self.sudo().search([("ws_id", "=", ws_id), ("id", "!=", job.id)])
                if other:  # подія встигла створити дубль з порталу: забираємо його стан
                    vals.update(state=other[0].state, done=other[0].done, sheet_log=other[0].sheet_log)
                    other.unlink()
                vals["ws_id"] = ws_id
            if job.state == "sent" and "state" not in vals:
                vals["state"] = "queued"
            job.write(vals)
        elif cmd.state == "failed":
            job.write({"state": "error", "error": (cmd.error or _("Команда не виконана"))[:512]})
        elif cmd.state == "expired":
            job.write({"state": "error", "error": _("Колектор не забрав команду")})
        else:
            job.write({"state": "error", "error": _("Команду скасовано")})
        if job.state == "done":
            job._f3d_consume()

    # --- R-23 п. 4 / R-16 п. 4: дзеркало woodStore ----------------------------------------------------
    @api.model
    def _f3d_ws_vals(self, item):
        """Значення завдання за об'єктом API-24."""
        env = self.env
        vals = {}
        if item.get("type") in ("feed", "restack", "return", "count"):
            vals["type"] = item["type"]
        stack = env["f3d.gantry.stack"].sudo().search([("code", "=", item.get("source"))], limit=1)
        if item.get("source") and not stack:
            _logger.warning("woodStore: невідомий стос %s", item["source"])
        if stack:
            vals["stack_id"] = stack.id
        if item.get("target"):
            wc = env["mrp.workcenter"].sudo().search_f3d(item["target"])
            if wc:
                vals["target_workcenter_id"] = wc.id
            else:
                _logger.warning("woodStore: невідомий верстат %s", item["target"])
        if item.get("product"):
            prod = env["product.product"].sudo().search([("default_code", "=", item["product"])], limit=1)
            if prod:
                vals["product_id"] = prod.id
            else:
                _logger.warning("woodStore: невідомий товар %s", item["product"])
        if item.get("sheets"):
            vals["sheets"] = max(int(item["sheets"]), 1)
        if item.get("priority"):
            vals["priority"] = min(max(int(item["priority"]), 1), 9)
        ref = item.get("external_ref")
        if ref:
            vals["external_ref"] = ref[:64]
            prod_order = env["mrp.production"].sudo().search([("name", "=", ref)], limit=1)
            if prod_order:
                vals["production_id"] = prod_order.id
        for key in ("created", "started", "finished"):
            ts = parse_ts(item.get(key))
            if ts:
                vals["ws_created" if key == "created" else key] = ts
        return vals

    @api.model
    def _f3d_apply_ws(self, items, ts=None):
        n = 0
        for item in items or []:
            ws_id = item.get("id")
            if not ws_id:
                continue
            job = self.sudo().search([("ws_id", "=", ws_id)], limit=1)
            vals = self._f3d_ws_vals(item)
            if not job:
                job = self._f3d_adopt(ws_id, item, vals)
            new_state = WS_STATES.get(item.get("state"))
            if new_state and not (job.state in TERMINAL and job.state != new_state):
                vals["state"] = new_state
            if item.get("done") is not None:
                vals["done"] = max(int(item["done"]), len(job.sheet_log or []))
            if not job:
                vals.update(ws_id=ws_id, origin="machine")
                vals.setdefault("type", "feed")
                vals.setdefault("sheets", 1)
                job = self.sudo().with_context(tracking_disable=True).create(vals)
            else:
                changed = {}
                for key, val in vals.items():
                    cur = job[key]
                    cur = cur.id if hasattr(cur, "id") else cur
                    if (cur or False) != (val or False):
                        changed[key] = val
                if changed:
                    job.write(changed)
            if job.production_id and not job.cut_map_id:
                job._f3d_link_cut_map()
            if job.state == "done":
                job._f3d_consume()
            n += 1
        return n

    @api.model
    def _f3d_adopt(self, ws_id, item, vals):
        """Подія з новим `ws_id`: це може бути наше `sent` завдання, чия команда ще не повернула результат."""
        ref = item.get("external_ref")
        if not ref:
            return self.browse()
        cand = self.sudo().search(
            [
                ("origin", "=", "odoo"),
                ("state", "=", "sent"),
                ("ws_id", "=", False),
                ("external_ref", "=", ref),
                ("product_id", "=", vals.get("product_id", False)),
            ],
            limit=1,
        )
        if cand:
            cand.ws_id = ws_id
        return cand

    def _f3d_link_cut_map(self):
        for rec in self:
            cut_map = (
                self.env["f3d.cut.map"]
                .sudo()
                .search(
                    [
                        ("production_id", "=", rec.production_id.id),
                        ("state", "=", "released"),
                        ("gantry_job_id", "=", False),
                    ],
                    limit=1,
                )
            )
            if cut_map:
                cut_map.gantry_job_id = rec
                rec.cut_map_id = cut_map

    @api.model
    def _f3d_apply_events(self, items):
        status = None
        for item in items or []:
            kind = item.get("type")
            ts = parse_ts(item.get("ts")) or fields.Datetime.now()
            job = self.sudo().search([("ws_id", "=", item.get("job"))], limit=1) if item.get("job") else self.browse()
            if kind == "sheet_placed" and job:
                job._f3d_on_sheet(item, ts)
            elif kind == "job_started" and job and job.state in ("sent", "queued"):
                job.write({"state": "active", "started": job.started or ts})
            elif kind == "job_finished" and job and job.state not in TERMINAL:
                job.write({"state": "done", "finished": ts, "done": max(job.done, len(job.sheet_log or []))})
                job._f3d_consume()
            elif kind == "stack_empty":
                stack = self.env["f3d.gantry.stack"].sudo().search([("code", "=", item.get("stack"))], limit=1)
                if stack:
                    stack._f3d_refresh()
                    stack.message_post(body=_("Стос порожній за даними порталу."), subtype_xmlid="mail.mt_note")
            elif kind == "alarm":
                self._f3d_post_equipment(_("Тривога порталу: %s", item.get("message") or ""))
            elif kind in ("aisle_opened", "aisle_closed"):
                status = status if status is not None else self._f3d_gantry_status()
                m = re.search(r"\d+", str(item.get("aisle") or item.get("message") or item.get("stack") or ""))
                if m:
                    aisles = set(status.get("aisles_open") or [])
                    (aisles.add if kind == "aisle_opened" else aisles.discard)(int(m.group()))
                    status["aisles_open"] = sorted(aisles)
        if status is not None:
            self._f3d_set_gantry_status(status)
        return len(items or [])

    def _f3d_on_sheet(self, item, ts):
        self.ensure_one()
        log = list(self.sheet_log or [])
        if any(e.get("id") == item.get("id") for e in log):
            return
        stack = self.env["f3d.gantry.stack"].sudo().search([("code", "=", item.get("stack"))], limit=1)
        log.append({"id": item.get("id"), "ts": ts.isoformat(), "stack": item.get("stack"), "lot": stack.ws_lot or ""})
        log = log[-SHEET_LOG_MAX:]
        vals = {"sheet_log": log, "done": max(self.done, len(log))}
        if self.state in ("sent", "queued"):
            vals.update(state="active", started=self.started or ts)
        self.write(vals)

    # --- R-23 п. 2: статус порталу --------------------------------------------------------------------
    @api.model
    def _f3d_apply_status(self, status, ts=None):
        old = self._f3d_gantry_status()
        aisles = status.get("aisles") or []
        opened = [a.get("no", i + 1) for i, a in enumerate(aisles) if a.get("gate_open")]
        alarms = [
            a if isinstance(a, str) else (a.get("text") or a.get("message") or str(a))
            for a in status.get("alarms") or []
        ]
        new = {
            "state": status.get("state"),
            "position": status.get("position"),
            "vacuum_kpa": status.get("vacuum_kpa"),
            "cycles_today": status.get("cycles_today"),
            "current_job": status.get("current_job"),
            "aisles_open": opened,
            "alarms": alarms,
        }
        if {k: v for k, v in old.items() if k != "ts"} == new:
            return False
        new["ts"] = status.get("ts") or (ts.isoformat() if hasattr(ts, "isoformat") else ts)
        self._f3d_set_gantry_status(new)
        for text in alarms:
            if text not in (old.get("alarms") or []):
                self._f3d_post_equipment(_("Тривога порталу: %s", text))
        self._f3d_notify_equipment()
        return True

    # --- R-17: списання плити в МО --------------------------------------------------------------------
    def _f3d_consume(self):
        tech = self.env["f3d.machine"]._f3d_tech_env()
        for rec in self:
            prod = rec.production_id
            if rec.type != "feed" or not rec.product_id or not prod or prod.state not in MO_LIVE:
                continue
            n = int(rec.done - rec.consumed_qty)
            if n <= 0:
                continue
            move = prod.move_raw_ids.filtered(
                lambda m, rec=rec: m.product_id == rec.product_id and m.state not in ("done", "cancel")
            )[:1]
            if not move:
                continue
            groups = {}
            log = (rec.sheet_log or [])[int(rec.consumed_qty) : int(rec.consumed_qty) + n]
            Stack = self.env["f3d.gantry.stack"].sudo()
            for entry in log:
                stack = Stack.search([("code", "=", entry.get("stack"))], limit=1)
                key = (stack.location_id.id, stack.odoo_lot_id.id or rec.lot_id.id)
                groups[key] = groups.get(key, 0) + 1
            rest = n - len(log)
            if rest > 0:
                loc = rec.stack_id.location_id or move.move_line_ids[:1].location_id
                if loc:
                    key = (loc.id, rec.stack_id.odoo_lot_id.id or rec.lot_id.id)
                    groups[key] = groups.get(key, 0) + rest
            if not groups:
                continue
            try:
                with self.env.cr.savepoint():
                    tmove = move.with_env(tech)
                    for (loc_id, lot_id), k in groups.items():
                        rec._f3d_consume_group(tmove, loc_id, lot_id, k)
                    if sum(tmove.move_line_ids.filtered("picked").mapped("quantity")) >= tmove.product_uom_qty:
                        tmove.picked = True
            except UserError as e:
                rec.message_post(
                    body=_("Не вдалося списати: %s", e.args[0] if e.args else e), subtype_xmlid="mail.mt_note"
                )
                continue
            rec.sudo().consumed_qty = rec.consumed_qty + sum(groups.values())

    def _f3d_consume_group(self, move, loc_id, lot_id, k):
        """Перенести `k` листів у рядок руху `(location, lot)`, зменшивши незібрані рядки інших локацій."""
        Line = move.move_line_ids
        same = Line.filtered(
            lambda ml: not ml.picked and ml.location_id.id == loc_id and ml.lot_id.id == (lot_id or False)
        )[:1]
        have = same.quantity if same else 0.0
        need = max(k - have, 0)
        others = Line.filtered(lambda ml: not ml.picked and ml.location_id.id != loc_id).sorted(
            "quantity", reverse=True
        )
        for line in others:
            if need <= 0:
                break
            take = min(line.quantity, need)
            if take >= line.quantity:
                line.unlink()
            else:
                line.quantity -= take
            need -= take
        if same:
            extra = same.quantity - k
            same.write({"quantity": k, "picked": True})
            if extra > 0:
                same.copy({"quantity": extra, "picked": False})
        else:
            self.env["stock.move.line"].with_env(move.env).create(
                {
                    "move_id": move.id,
                    "product_id": move.product_id.id,
                    "location_id": loc_id,
                    "location_dest_id": move.location_dest_id.id,
                    "lot_id": lot_id or False,
                    "quantity": k,
                    "picked": True,
                }
            )

    # --- крон -----------------------------------------------------------------------------------------
    @api.model
    def _cron_gantry(self):
        """R-15 п. 1–5, R-16 п. 2/5, R-18 п. 1 (SPEC §6). Кожен запис — у `savepoint`."""
        sudo = self.sudo()
        for stack in sudo.env["f3d.gantry.stack"].search([], limit=CRON_STACKS_LIMIT):
            try:
                with self.env.cr.savepoint():
                    stack._f3d_refresh()
            except Exception:
                _logger.exception("Звірка стосу %s не вдалася", stack.code)
        # команди, стан яких змінено не через ORM (A-14)
        for job in sudo.search(
            [("state", "=", "sent"), ("command_id.state", "in", ("done", "failed", "expired", "cancelled"))],
            limit=CRON_JOBS_LIMIT,
        ):
            try:
                with self.env.cr.savepoint():
                    job._f3d_on_command(job.command_id)
            except Exception:
                _logger.exception("Результат команди завдання %s не оброблено", job.name)
        if param_bool(self.env, "gantry_auto_feed"):
            sudo._f3d_auto_feed()
        for job in sudo.search([("state", "=", "to_send")], limit=CRON_JOBS_LIMIT):
            try:
                with self.env.cr.savepoint():
                    job._f3d_send()
            except Exception:
                _logger.exception("Відправка завдання %s не вдалася", job.name)
        sudo._f3d_check_idle()
        try:
            with self.env.cr.savepoint():
                sudo.env["f3d.gantry.stack"]._f3d_cron_replenish()
        except Exception:
            _logger.exception("Поповнення стосів не вдалося")
        return True

    @api.model
    def _f3d_auto_feed(self):
        """R-16 п. 1: перше завдання черги кожного верстата порталу -> завдання `to_send`."""
        targets = self.env["f3d.gantry.stack"].GANTRY_TARGETS
        for wc in self.env["mrp.workcenter"].search([("f3d_code", "in", list(targets))]):
            wo = self.env["mrp.workorder"].search([("workcenter_id", "=", wc.id), ("state", "=", "progress")], limit=1)
            if not wo:
                wos = self.env["mrp.workorder"].search([("workcenter_id", "=", wc.id), ("state", "=", "ready")])
                wo = wos.sorted(lambda w: w.production_id.name)[:1]
            if not wo or self.search_count([("production_id", "=", wo.production_id.id), ("state", "!=", "cancelled")]):
                continue
            try:
                with self.env.cr.savepoint():
                    job = self._f3d_from_production(wo.production_id, workorder=wo)
                    job.write({"state": "to_send"})
            except UserError as e:
                _logger.info("Автоподача %s пропущена: %s", wo.production_id.name, e)

    @api.model
    def _f3d_check_idle(self):
        """R-16 п. 5: `active` без змін > 30 хв -> один запис у чатері."""
        limit = fields.Datetime.now() - timedelta(minutes=IDLE_MIN)
        text = _("Завдання порталу без руху 30 хв")
        for job in self.search([("state", "=", "active"), ("write_date", "<", limit)]):
            posted = (
                self.env["mail.message"]
                .sudo()
                .search_count(
                    [
                        ("model", "=", self._name),
                        ("res_id", "=", job.id),
                        ("body", "ilike", "без руху 30 хв"),
                        ("date", ">=", job.write_date),
                    ]
                )
            )
            if not posted:
                job.message_post(body=text, subtype_xmlid="mail.mt_note")
