import hashlib
import hmac
import json
import logging
import math
import secrets
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from ..tools import commands as cmd_tools
from ..tools import cutcsv
from .f3d_cut_part import GRAINS, MATERIAL_ROLES
from .f3d_machine import param, param_bool

CUT_CODES = ("SAW-1", "SAW-2", "SAW-3", "NEST-1", "SLIDE-1", "VSAW-1")
CUTOPT_CMD_CODE = "equipment/CUTOPT/cmd"
THIN_MM = 8
OPTIMIZE_TIMEOUT_MIN = 30
STATUS_MIN_INTERVAL_S = 60
MPR_MAX_BYTES = 200 * 1024
CRON_LIMIT = 20
MAX_EXPORT_LINES = 5000
STATE_LABELS = {
    "draft": "Чернетка",
    "exported": "Експортовано",
    "optimizing": "Оптимізується",
    "planned": "Сплановано",
    "released": "Випущено",
    "running": "Ріжеться",
    "done": "Виконано",
    "error": "Помилка",
    "cancel": "Скасовано",
}


class CutExportError(Exception):
    """Відмова API-01: HTTP-статус, код і текст."""

    def __init__(self, status, code, message):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


_logger = logging.getLogger(__name__)


class F3dCutMap(models.Model):
    _name = "f3d.cut.map"
    _description = "Розкрій: карта розкрою"
    _inherit = ["mail.thread"]
    _order = "id desc"

    name = fields.Char(
        string="Номер",
        required=True,
        copy=False,
        default=lambda s: s.env["ir.sequence"].next_by_code("f3d.cut.map"),
    )
    production_id = fields.Many2one(
        "mrp.production", string="Виробниче замовлення", required=True, index=True, ondelete="restrict"
    )
    product_id = fields.Many2one("product.product", related="production_id.product_id")
    workorder_id = fields.Many2one(
        "mrp.workorder",
        string="Завдання розкрою",
        ondelete="set null",
        domain="[('production_id', '=', production_id)]",
    )
    workcenter_id = fields.Many2one("mrp.workcenter", related="workorder_id.workcenter_id", store=True)
    machine_code = fields.Char(related="workcenter_id.f3d_code")
    material_role = fields.Selection(MATERIAL_ROLES, required=True, default="main")
    material_product_id = fields.Many2one(
        "product.product", string="Плита", required=True, domain="[('f3d_sheet_length_mm', '>', 0)]"
    )
    sheet_length_mm = fields.Integer(string="Лист: довжина, мм")
    sheet_width_mm = fields.Integer(string="Лист: ширина, мм")
    thickness_mm = fields.Integer(string="Лист: товщина, мм")
    qty = fields.Float(string="Виробів", required=True, digits=(12, 2))
    line_ids = fields.One2many("f3d.cut.map.line", "map_id", string="Деталі")
    parts_count = fields.Integer(compute="_compute_parts", store=True, string="Деталей")
    mode = fields.Selection(
        [("collector", "Через колектор"), ("manual", "Вручну")],
        required=True,
        default=lambda s: param(s.env, "cutting_mode", "manual"),
    )
    state = fields.Selection(
        [
            ("draft", "Чернетка"),
            ("exported", "Експортовано"),
            ("optimizing", "Оптимізується"),
            ("planned", "Сплановано"),
            ("released", "Випущено"),
            ("running", "Ріжеться"),
            ("done", "Виконано"),
            ("error", "Помилка"),
            ("cancel", "Скасовано"),
        ],
        required=True,
        index=True,
        default="draft",
        tracking=True,
    )
    ext_job_id = fields.Char(string="Номер в оптимізаторі", size=32, index=True, copy=False)
    job_order_id = fields.Char(string="JobOrder верстата", size=64, copy=False)
    plan_sheets = fields.Integer(string="Аркушів за планом", tracking=True)
    plan_waste_pct = fields.Float(string="Відхід, %", digits=(5, 1))
    plan_cut_length_m = fields.Float(string="Довжина різу, м", digits=(10, 1))
    plan_est_min = fields.Float(string="Оцінка часу, хв", digits=(8, 1))
    plan_json = fields.Json(string="План", copy=False)
    sheets_need = fields.Float(compute="_compute_need", string="Потреба МО, арк.")
    sheets_warning = fields.Char(compute="_compute_need")
    csv_attachment_id = fields.Many2one("ir.attachment", string="Список деталей (CSV)", ondelete="set null", copy=False)
    plan_attachment_id = fields.Many2one("ir.attachment", string="План (JSON)", ondelete="set null", copy=False)
    mpr_attachment_ids = fields.Many2many(
        "ir.attachment",
        relation="f3d_cut_map_mpr_rel",
        column1="map_id",
        column2="attachment_id",
        copy=False,
        string="Програми ЧПК",
    )
    export_token_hash = fields.Char(size=64, copy=False, groups="factory3d_base.group_f3d_admin")
    export_token_expires = fields.Datetime(copy=False, groups="factory3d_base.group_f3d_admin")
    command_ids = fields.One2many("f3d.command", "f3d_cut_map_id", string="Команди")
    gantry_job_id = fields.Many2one("f3d.gantry.job", ondelete="set null", copy=False)
    error = fields.Char(size=512, readonly=True)
    released_at = fields.Datetime(readonly=True)
    done_at = fields.Datetime(readonly=True)
    company_id = fields.Many2one("res.company", related="production_id.company_id", store=True)
    optimizing_since = fields.Datetime(readonly=True, copy=False)

    @api.depends("line_ids.qty")
    def _compute_parts(self):
        for rec in self:
            rec.parts_count = int(sum(rec.line_ids.mapped("qty")))

    @api.depends("material_product_id", "production_id.move_raw_ids.product_uom_qty", "plan_sheets")
    def _compute_need(self):
        for rec in self:
            product = rec.material_product_id
            moves = rec.production_id.move_raw_ids.filtered(
                lambda m, product=product: m.product_id == product and m.state not in ("done", "cancel")
            )
            need = sum(moves.mapped("product_uom_qty"))
            rec.sheets_need = need
            rec.sheets_warning = (
                _("За планом %d арк., у МО %g — оновіть потребу або візьміть із запасу.", rec.plan_sheets, need)
                if rec.plan_sheets > need
                else False
            )

    @api.constrains("sheet_length_mm", "sheet_width_mm", "thickness_mm", "material_product_id")
    def _check_sheet(self):
        for rec in self:
            if min(rec.sheet_length_mm, rec.sheet_width_mm, rec.thickness_mm) <= 0:
                raise ValidationError(_("Задайте розміри листа плити %s.", rec.material_product_id.display_name))

    @api.constrains("line_ids")
    def _check_fit(self):
        self.line_ids._check_fit_in_sheet()

    def write(self, vals):
        if vals.get("state") == "optimizing" and "optimizing_since" not in vals:
            vals = dict(vals, optimizing_since=fields.Datetime.now())
        return super().write(vals)

    # --- R-19: створення з МО ------------------------------------------------------------------------
    @api.model
    def _f3d_plate_move(self, production, role):
        """Сировинний рух плити МО для ролі `main` (≥ 8 мм) / `back` (< 8 мм); найбільша кількість."""
        moves = production.move_raw_ids.filtered(
            lambda m: m.state not in ("done", "cancel") and m.product_id.f3d_sheet_length_mm > 0
        )
        if role == "main":
            moves = moves.filtered(lambda m: m.product_id.f3d_thickness_mm >= THIN_MM)
        else:
            moves = moves.filtered(lambda m: m.product_id.f3d_thickness_mm < THIN_MM)
        return moves.sorted("product_uom_qty", reverse=True)[:1]

    @api.model
    def _f3d_create_for(self, production, material_role="main"):
        production = production.sudo()
        role_label = dict(MATERIAL_ROLES).get(material_role, material_role)
        if production.state in ("done", "cancel"):
            raise UserError(_("МО %s завершено або скасовано.", production.name))
        if material_role not in ("main", "back"):
            raise UserError(_("Роль «%s» не підтримується для створення карти.", role_label))
        move = self._f3d_plate_move(production, material_role)
        if not move:
            raise UserError(_("У МО %s немає плити для ролі «%s».", production.name, role_label))
        if not production.bom_id:
            raise UserError(_("У МО %s немає специфікації.", production.name))
        plate = move.product_id
        parts = self._f3d_parts_for(production.bom_id, material_role, plate)
        if not parts:
            raise UserError(
                _(
                    "Для специфікації «%s» немає деталей ролі «%s» — заповніть «Деталі виробів».",
                    production.bom_id.display_name,
                    role_label,
                )
            )
        qty = production.product_qty - production.qty_produced
        if qty <= 0:
            qty = production.product_qty
        codes = set(CUT_CODES) | set(self.env["f3d.gantry.stack"].GANTRY_TARGETS)
        workorder = production.workorder_ids.filtered(
            lambda w: w.state not in ("done", "cancel") and w.workcenter_id.f3d_code in codes
        )[:1]
        rec = self.create(
            {
                "production_id": production.id,
                "workorder_id": workorder.id,
                "material_role": material_role,
                "material_product_id": plate.id,
                "sheet_length_mm": plate.f3d_sheet_length_mm,
                "sheet_width_mm": plate.f3d_sheet_width_mm,
                "thickness_mm": plate.f3d_thickness_mm,
                "qty": qty,
            }
        )
        rec.action_build_lines()
        return rec

    @api.model
    def _f3d_parts_for(self, bom, role, plate):
        parts = self.env["f3d.cut.part"].sudo().search([("bom_id", "=", bom.id), ("active", "=", True)])
        return parts.filtered(
            lambda p: p.material_role == role or (p.material_role == "product" and p.material_product_id == plate)
        )

    def action_build_lines(self):
        for rec in self:
            if rec.state != "draft":
                raise UserError(_("Карта %s не в чернетці.", rec.name))
            production = rec.production_id.sudo()
            if not production.bom_id:
                raise UserError(_("У МО %s немає специфікації.", production.name))
            parts = self._f3d_parts_for(production.bom_id, rec.material_role, rec.material_product_id)
            if not parts:
                raise UserError(
                    _(
                        "Для специфікації «%s» немає деталей ролі «%s» — заповніть «Деталі виробів».",
                        production.bom_id.display_name,
                        dict(MATERIAL_ROLES).get(rec.material_role, rec.material_role),
                    )
                )
            cmds = [(5, 0, 0)]
            for part in parts:
                cmds.append(
                    (
                        0,
                        0,
                        {
                            "sequence": part.sequence,
                            "part_id": part.id,
                            "part_code": part.part_code,
                            "name": part.name,
                            "length_mm": part.length_mm,
                            "width_mm": part.width_mm,
                            "qty": max(1, math.ceil(part.qty * rec.qty - 1e-9)),
                            "grain": part.grain,
                            "edge_top": part.edge_top,
                            "edge_bottom": part.edge_bottom,
                            "edge_left": part.edge_left,
                            "edge_right": part.edge_right,
                            "program": part.program,
                        },
                    )
                )
            rec.write({"line_ids": cmds})
        return True

    # --- вкладення -----------------------------------------------------------------------------------
    def _f3d_attach(self, name, mimetype, data):
        self.ensure_one()
        return (
            self.env["ir.attachment"]
            .sudo()
            .create({"name": name, "mimetype": mimetype, "raw": data, "res_model": self._name, "res_id": self.id})
        )

    def _f3d_csv_text(self):
        self.ensure_one()
        code = self.material_product_id.default_code
        if not code:
            raise UserError(_("У товару %s немає внутрішнього коду.", self.material_product_id.display_name))
        lines = [
            {
                "part_code": ln.part_code,
                "name": ln.name,
                "length_mm": ln.length_mm,
                "width_mm": ln.width_mm,
                "qty": ln.qty,
                "grain": ln.grain,
                "edge_top": ln.edge_top,
                "edge_bottom": ln.edge_bottom,
                "edge_left": ln.edge_left,
                "edge_right": ln.edge_right,
                "program": ln.program,
            }
            for ln in self.line_ids
        ]
        return cutcsv.build_parts_csv(lines, code)

    def action_export(self):
        for rec in self:
            if rec.state != "draft":
                raise UserError(_("Карта %s не в чернетці.", rec.name))
            if not rec.line_ids:
                raise UserError(_("У карті %s немає деталей.", rec.name))
            data = rec._f3d_csv_text().encode("utf-8")
            old = rec.csv_attachment_id
            att = rec._f3d_attach("%s_parts.csv" % rec.name, "text/csv", data)
            rec.write({"csv_attachment_id": att.id, "state": "exported", "error": False})
            old.sudo().unlink()
            if rec.mode == "collector":
                rec.action_send_optimizer()
        return True

    def action_download_csv(self):
        self.ensure_one()
        if not self.csv_attachment_id:
            raise UserError(_("Список деталей ще не сформовано."))
        return {
            "type": "ir.actions.act_url",
            "url": "/web/content/%d?download=true" % self.csv_attachment_id.id,
            "target": "self",
        }

    def action_open_plan_import(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Імпорт плану"),
            "res_model": "f3d.cut.plan.import.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_map_id": self.id},
        }

    # --- токен API-01 --------------------------------------------------------------------------------
    def _f3d_new_export_token(self):
        self.ensure_one()
        token = secrets.token_hex(8)
        ttl = int(param(self.env, "export_token_ttl_s", "600"))
        self.sudo().write(
            {
                "export_token_hash": hashlib.sha256(token.encode()).hexdigest(),
                "export_token_expires": fields.Datetime.now() + timedelta(seconds=ttl),
            }
        )
        return token

    @api.model
    def _f3d_check_export_token(self, map_id, t):
        rec = self.sudo().browse(map_id).exists()
        if not rec:
            raise CutExportError(404, "not_found", "Карту розкрою не знайдено")
        digest = hashlib.sha256((t or "").encode()).hexdigest()
        if not rec.export_token_hash or not hmac.compare_digest(digest, rec.export_token_hash):
            raise CutExportError(403, "forbidden", "Невірний токен експорту")
        if rec.export_token_expires and rec.export_token_expires < fields.Datetime.now():
            raise CutExportError(410, "expired", "Токен експорту прострочено")
        if rec.state not in ("exported", "optimizing"):
            raise CutExportError(409, "bad_state", "Карта не очікує експорту")
        return rec

    # --- R-20: оптимізація, план, випуск -------------------------------------------------------------
    @api.model
    def _f3d_export_collector(self):
        """API-01 п. 1 / AC-67: колектор, якому дозволено забирати список деталей, — власник джерела сигналу
        команд CMD-03 (`equipment/CUTOPT/cmd`): саме йому йде команда `upload` з токеном експорту."""
        sig = self.env["f3d.signal"].sudo().search([("code", "=", CUTOPT_CMD_CODE)], limit=1)
        return sig.collector_id

    @api.model
    def _f3d_cutopt_signal(self):
        sig = self.env["f3d.signal"].sudo().search([("code", "=", CUTOPT_CMD_CODE)], limit=1)
        if not sig:
            raise UserError(_("Не знайдено сигнал %s.", CUTOPT_CMD_CODE))
        return sig

    def _f3d_command(self, op, cmd_fields):
        self.ensure_one()
        return self.env["f3d.command"]._f3d_mc_create_command(
            self._f3d_cutopt_signal(), op, cmd_fields, {"f3d_cut_map_id": self.id}
        )

    def action_send_optimizer(self):
        for rec in self:
            if rec.mode != "collector":
                raise UserError(_("Карта %s у ручному режимі.", rec.name))
            if rec.state not in ("exported", "error"):
                raise UserError(_("Карта %s не готова до оптимізації (стан «%s»).", rec.name, STATE_LABELS[rec.state]))
            if not rec.csv_attachment_id:
                raise UserError(_("Спочатку експортуйте карту %s.", rec.name))
            with self.env.cr.savepoint():
                token = rec._f3d_new_export_token()
                rec._f3d_command("upload", {"map": rec.id, "token": token})
                rec.sudo().write({"state": "optimizing", "error": False})
        return True

    def _f3d_set_error(self, text):
        self.ensure_one()
        self.sudo().write(
            {"state": "error", "error": (text or _("Помилка оптимізатора"))[:512], "export_token_hash": False}
        )

    def _f3d_on_command(self, cmd):
        """R-20 п. 2, 5: результат команди CMD-03."""
        self.ensure_one()
        rec = self.sudo()
        payload = cmd.payload if "payload" in cmd._fields and cmd.payload else None
        if not payload:
            try:
                payload = cmd_tools.parse_cmd("cutopt", cmd.text or "")
            except ValueError:
                payload = {}
        op = payload.get("op")
        data = cmd.result_data if isinstance(cmd.result_data, dict) else {}
        failed = cmd.state in ("failed", "expired", "cancelled")
        reason = cmd.error or (_("Колектор не забрав команду") if cmd.state == "expired" else _("Команда не виконана"))
        if op == "upload":
            if rec.state != "optimizing":
                return
            if cmd.state == "done":
                words = (cmd.result or "").split()
                job_id = data.get("job_id") or (words[0] if words else "")
                rec.write({"ext_job_id": job_id[:32] if job_id else rec.ext_job_id, "error": False})
            elif failed:
                rec._f3d_set_error(reason)
        elif op == "release":
            if cmd.state == "done":
                vals = {"job_order_id": data.get("job_order_id") or rec.ext_job_id}
                if rec.state in ("planned", "error"):
                    vals.update(state="released", released_at=fields.Datetime.now(), error=False)
                rec.write(vals)
            elif failed and rec.state == "planned":
                rec._f3d_set_error(reason)
        elif failed:
            rec.message_post(body=_("Команда %s: %s", cmd.text or op or "", reason), subtype_xmlid="mail.mt_note")

    @api.model
    def _f3d_find_for_event(self, map_name, job_id):
        """Карта для події EV-03: за номером `map`, інакше (колектор після рестарту) за `ext_job_id`."""
        if map_name:
            domain = [("name", "=", map_name)]
        elif job_id:
            domain = [("ext_job_id", "=", job_id)]
        else:
            return self.browse()
        return self.sudo().search(domain, limit=1)

    def _f3d_apply_job(self, job):
        """EV-03 `job` (R-20 п. 2)."""
        self.ensure_one()
        rec = self.sudo()
        if rec.state in ("done", "cancel"):
            return False
        state = job.get("state")
        vals = {}
        if job.get("job_id") and not rec.ext_job_id:
            vals["ext_job_id"] = str(job["job_id"])[:32]
        if state == "optimizing":
            if rec.state in ("exported", "error"):
                vals["state"] = "optimizing"
        elif state == "planned":
            plan = job.get("plan") or {}
            if plan.get("sheets") is not None:
                vals["plan_sheets"] = int(plan["sheets"])
            if plan.get("waste_pct") is not None:
                vals["plan_waste_pct"] = float(plan["waste_pct"])
            if plan.get("cut_length_m") is not None:
                vals["plan_cut_length_m"] = float(plan["cut_length_m"])
            if plan.get("est_min") is not None:
                vals["plan_est_min"] = float(plan["est_min"])
            if rec.state in ("exported", "optimizing", "error"):
                vals["state"] = "planned"
        elif state == "released":
            vals["job_order_id"] = str(job.get("job_order_id") or job.get("job_id") or rec.ext_job_id or "")[:64]
            if rec.state in ("exported", "optimizing", "planned", "error"):
                vals.update(state="released", released_at=fields.Datetime.now())
        elif state == "running":
            if rec.state in ("exported", "optimizing", "planned", "released", "error"):
                vals["state"] = "running"
        elif state == "done":
            vals.update(state="done", done_at=fields.Datetime.now())
        elif state == "error":
            vals.update(state="error", error=str(job.get("error") or _("Помилка оптимізатора"))[:512])
        if vals:
            rec.write(vals)
        return True

    def _f3d_apply_plan(self, plan):
        """EV-03 `plan` і M-25 (R-20 п. 3). Невалідний план -> `ValueError`, стан не змінюється."""
        self.ensure_one()
        plan = cutcsv.parse_plan(plan)
        rec = self.sudo()
        if rec.state not in ("exported", "optimizing", "planned"):
            _logger.warning("Карта %s не очікує плану (стан %s)", rec.name, rec.state)
            return False
        old = rec.plan_attachment_id
        data = json.dumps(plan, ensure_ascii=False, sort_keys=True).encode("utf-8")
        att = rec._f3d_attach("%s_plan.json" % rec.name, "application/json", data)
        vals = {
            "plan_json": plan,
            "plan_sheets": plan["total_sheets"],
            "plan_waste_pct": plan["waste_pct"],
            "plan_attachment_id": att.id,
            "state": "planned",
            "error": False,
        }
        if "cut_length_m" in plan:
            vals["plan_cut_length_m"] = plan["cut_length_m"]
        if "est_min" in plan:
            vals["plan_est_min"] = plan["est_min"]
        rec.write(vals)
        old.sudo().unlink()
        rec._f3d_check_plan_counts(plan)
        rec._f3d_request_mpr()
        return True

    def _f3d_check_plan_counts(self, plan):
        self.ensure_one()
        placed = cutcsv.plan_counts(plan)
        wanted = {ln.part_code: ln.qty for ln in self.line_ids}
        diff = [
            "%s %d → %d" % (code, wanted.get(code, 0), placed.get(code, 0))
            for code in sorted(set(wanted) | set(placed))
            if wanted.get(code, 0) != placed.get(code, 0)
        ]
        if diff:
            self.message_post(body=_("План не відповідає карті: %s", ", ".join(diff)), subtype_xmlid="mail.mt_note")

    def _f3d_request_mpr(self):
        """R-20 п. 3: для рядків із програмою на РЦ ЧПК (`NEST-1`) — CMD-03 `mpr`, по одному."""
        self.ensure_one()
        if self.mode != "collector" or not self.ext_job_id or self.workcenter_id.f3d_code != "NEST-1":
            return
        for line in self.line_ids.filtered("program"):
            try:
                with self.env.cr.savepoint():
                    self._f3d_command("mpr", {"job": self.ext_job_id, "part": line.part_code})
            except UserError as e:
                _logger.warning("Карта %s: команду mpr не створено: %s", self.name, e)
                self.message_post(
                    body=_("Програму %s не запрошено: %s", line.part_code, e), subtype_xmlid="mail.mt_note"
                )
                return

    def _f3d_apply_mpr(self, part, text):
        """EV-03 `mpr` (R-20 п. 3)."""
        self.ensure_one()
        rec = self.sudo()
        line = rec.line_ids.filtered(lambda ln: ln.part_code == part)[:1]
        if not line:
            raise ValueError("mpr: деталі %s немає в карті %s" % (part, rec.name))
        data = (text or "").encode("utf-8")
        if len(data) > MPR_MAX_BYTES:
            raise ValueError("mpr: текст більший за 200 КБ")
        old = line.mpr_attachment_id
        att = rec._f3d_attach("%s.mpr" % part, "text/plain", data)
        line.write({"mpr_attachment_id": att.id})
        rec.write({"mpr_attachment_ids": [(4, att.id)]})
        if old:
            rec.write({"mpr_attachment_ids": [(3, old.id)]})
            old.unlink()
        return True

    def action_update_mo_need(self):
        if not self.env.su and not self.env.user.has_group("mrp.group_mrp_manager"):
            raise AccessError(_("Оновлення потреби МО доступне менеджерам виробництва."))
        for rec in self:
            production = rec.production_id.sudo()
            moves = production.move_raw_ids.filtered(
                lambda m, rec=rec: m.product_id == rec.material_product_id and m.state not in ("done", "cancel")
            )
            if not moves:
                raise UserError(
                    _("У МО %s немає руху плити %s.", production.name, rec.material_product_id.display_name)
                )
            was = sum(moves.mapped("product_uom_qty"))
            others = sum(moves[1:].mapped("product_uom_qty"))
            moves[0].product_uom_qty = max(rec.plan_sheets - others, 0)
            production.message_post(
                body=_(
                    "Потреба в %s за картою %s: %g → %g арк.",
                    rec.material_product_id.display_name,
                    rec.name,
                    was,
                    rec.plan_sheets,
                ),
                subtype_xmlid="mail.mt_note",
            )
        return True

    def action_release(self):
        for rec in self:
            if rec.state != "planned":
                raise UserError(_("Карта %s не сплановано (стан «%s»).", rec.name, STATE_LABELS[rec.state]))
            if rec.mode == "manual":
                rec.sudo().write({"state": "released", "released_at": fields.Datetime.now()})
                continue
            if not rec.ext_job_id:
                raise UserError(_("Карта %s без номера в оптимізаторі.", rec.name))
            machine = rec.workcenter_id.f3d_code
            if not machine:
                raise UserError(_("У карти %s не визначено верстат (завдання розкрою).", rec.name))
            rec._f3d_command("release", {"job": rec.ext_job_id, "machine": machine, "priority": 5})
        return True

    def action_cancel(self):
        for rec in self:
            if rec.state == "done":
                raise UserError(_("Карта %s уже виконана.", rec.name))
            rec.sudo().write({"state": "cancel", "export_token_hash": False})
        return True

    def action_reset_draft(self):
        for rec in self:
            if rec.state not in ("error", "cancel"):
                raise UserError(_("Карта %s не в стані помилки чи скасування.", rec.name))
            rec.sudo().write(
                {
                    "state": "draft",
                    "ext_job_id": False,
                    "job_order_id": False,
                    "plan_json": False,
                    "plan_sheets": 0,
                    "plan_waste_pct": 0.0,
                    "plan_cut_length_m": 0.0,
                    "plan_est_min": 0.0,
                    "error": False,
                    "export_token_hash": False,
                    "export_token_expires": False,
                    "optimizing_since": False,
                }
            )
        return True

    # --- R-20 п. 6: крон ------------------------------------------------------------------------------
    @api.model
    def _cron_cutmap(self):
        self = self.sudo()
        now = fields.Datetime.now()
        self.search(
            [("export_token_hash", "!=", False), ("export_token_expires", "<", now)], limit=CRON_LIMIT * 5
        ).write({"export_token_hash": False, "export_token_expires": False})
        maps = self.search([("state", "in", ("optimizing", "released", "running"))], order="id", limit=CRON_LIMIT)
        for rec in maps:
            try:
                with self.env.cr.savepoint():
                    rec._f3d_cron_step(now)
            except Exception:
                _logger.exception("Карта %s: помилка кроку", rec.name)
        return True

    def _f3d_cron_step(self, now):
        self.ensure_one()
        if self.state == "optimizing":
            since = self.optimizing_since or self.write_date
            if since and since < now - timedelta(minutes=OPTIMIZE_TIMEOUT_MIN):
                self._f3d_set_error(_("Оптимізатор не відповів 30 хв"))
                return
            horizon = now - timedelta(seconds=STATUS_MIN_INTERVAL_S)
            fresh = self.command_ids.filtered(lambda c: c.state in ("queued", "sent") and c.create_date > horizon)
            if self.ext_job_id and not fresh and self.mode == "collector" and param_bool(self.env, "write_enabled"):
                try:
                    with self.env.cr.savepoint():
                        self._f3d_command("status", {"job": self.ext_job_id})
                except UserError as e:
                    _logger.info("Карта %s: статус не запрошено: %s", self.name, e)
        elif self.state in ("released", "running"):
            wo_state = self.workorder_id.state
            if wo_state == "done":
                self.write({"state": "done", "done_at": now})
            elif wo_state == "progress" and self.state == "released":
                self.write({"state": "running"})


class F3dCutMapLine(models.Model):
    _name = "f3d.cut.map.line"
    _description = "Розкрій: деталь у карті"
    _order = "map_id, sequence, id"

    map_id = fields.Many2one("f3d.cut.map", required=True, index=True, ondelete="cascade")
    sequence = fields.Integer(default=10)
    part_id = fields.Many2one("f3d.cut.part", ondelete="set null")
    part_code = fields.Char(size=16, required=True)
    name = fields.Char(size=64, required=True)
    length_mm = fields.Integer(required=True)
    width_mm = fields.Integer(required=True)
    qty = fields.Integer(required=True, default=1)
    grain = fields.Selection(GRAINS, default="0")
    edge_top = fields.Char(size=32)
    edge_bottom = fields.Char(size=32)
    edge_left = fields.Char(size=32)
    edge_right = fields.Char(size=32)
    program = fields.Char(size=64)
    mpr_attachment_id = fields.Many2one("ir.attachment", ondelete="set null")

    _f3d_line_numbers = models.Constraint(
        "CHECK(qty >= 1 AND length_mm > 0 AND width_mm > 0)", "Кількість ≥ 1, розміри > 0."
    )

    @api.constrains("length_mm", "width_mm", "grain", "map_id")
    def _check_line_fit(self):
        self._check_fit_in_sheet()

    def _check_fit_in_sheet(self):
        """R-19 п. 4: деталь вміщується в лист карти з урахуванням текстури."""
        for line in self:
            sheet = line.map_id
            if sheet.sheet_length_mm <= 0 or sheet.sheet_width_mm <= 0:
                continue
            if not cutcsv.fits(line.length_mm, line.width_mm, sheet.sheet_length_mm, sheet.sheet_width_mm, line.grain):
                raise ValidationError(
                    _(
                        "Деталь %s (%d × %d) не вміщується в лист %d × %d.",
                        line.part_code,
                        line.length_mm,
                        line.width_mm,
                        sheet.sheet_length_mm,
                        sheet.sheet_width_mm,
                    )
                )

    def write(self, vals):
        if set(vals) - {"mpr_attachment_id"}:
            for line in self:
                if line.map_id.state != "draft":
                    raise UserError(_("Карта %s уже експортована — поверніть у чернетку.", line.map_id.name))
        return super().write(vals)
