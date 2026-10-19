import logging
import re
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from ..tools.states import parse_ts
from .td_machine import param, param_bool

_logger = logging.getLogger(__name__)

ROWCOL_RE = re.compile(r"^PLT-(\d{2})([A-C])")
STALE_MIN = 10  # R-15 п. 4: дані порталу старші за 10 хв -> `unknown`
GANTRY_CMD_CODE = "equipment/GANTRY-1/cmd"
GANTRY_STACKS_CODE = "equipment/GANTRY-1/stacks"


def gantry_cmd_signal(env):
    """Сигнал команд порталу (CMD-02)."""
    sig = env["td.signal"].sudo().search([("code", "=", GANTRY_CMD_CODE)], limit=1)
    if not sig:
        raise UserError(_("Не знайдено сигнал %s.", GANTRY_CMD_CODE))
    return sig


def activity_user(env):
    """Перший активний користувач `stock.group_stock_manager` (не OdooBot), інакше адміністратор (R-15 п. 4)."""
    root = env.ref("base.user_root")
    users = env.ref("stock.group_stock_manager").sudo().all_user_ids
    users = users.filtered(lambda u: u.active and not u.share and u.id != root.id).sorted("id")
    return users[:1] or env.ref("base.user_admin")


def check_stock_manager(env):
    if not env.su and not env.user.has_group("stock.group_stock_manager"):
        raise AccessError(_("Дія доступна лише керівнику складу."))


class F3dGantryStack(models.Model):
    _name = "td.gantry.stack"
    _description = "Портал: стос плит"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "code"
    _rec_name = "code"
    GANTRY_TARGETS = ("SAW-1", "SAW-2", "SAW-3", "NEST-1")  # iot_sim API-25 target

    location_id = fields.Many2one(
        "stock.location",
        string="Місце",
        required=True,
        index=True,
        ondelete="cascade",
        domain="[('td_loc_kind', '=', 'stack')]",
    )
    code = fields.Char(related="location_id.td_code", store=True, index=True, string="Стос")
    capacity = fields.Float(related="location_id.td_capacity", string="Місткість, арк.")
    row = fields.Integer(compute="_compute_rowcol", store=True, string="Ряд")
    col = fields.Char(compute="_compute_rowcol", store=True, size=1, string="Колонка")
    orderpoint_id = fields.Many2one("stock.warehouse.orderpoint", string="Правило поповнення", ondelete="set null")
    min_qty = fields.Float(related="orderpoint_id.product_min_qty")
    max_qty = fields.Float(related="orderpoint_id.product_max_qty")
    ws_qty = fields.Integer(string="Портал, арк.", tracking=True)
    ws_product = fields.Char(string="Товар у порталі", size=32)
    ws_product_id = fields.Many2one(
        "product.product", compute="_compute_ws_product", store=True, string="Товар у порталі (Odoo)"
    )
    ws_lot = fields.Char(string="Партія в порталі", size=64)
    ws_reserved = fields.Integer(string="Зарезервовано порталом")
    ws_locked = fields.Boolean(string="Заблоковано в порталі")
    ws_updated = fields.Datetime(string="Оновлено в порталі")
    ws_seen = fields.Datetime(string="Отримано")
    odoo_qty = fields.Float(digits=(12, 1), string="Odoo, арк.")
    odoo_product_id = fields.Many2one("product.product", string="Товар в Odoo")
    odoo_lot_id = fields.Many2one("stock.lot", string="Партія в Odoo")
    fed_unconsumed = fields.Float(digits=(12, 1), string="Подано, не списано")
    expected_qty = fields.Float(digits=(12, 1), string="Має бути в порталі")
    diff = fields.Float(digits=(12, 1), string="Розбіжність, арк.")
    state = fields.Selection(
        [("ok", "Збігається"), ("pending", "Перевіряється"), ("diff", "Розбіжність"), ("unknown", "Немає даних")],
        default="unknown",
        index=True,
        tracking=True,
    )
    diff_since = fields.Datetime()
    replenish_at = fields.Datetime(string="Останнє поповнення", copy=False)
    fill = fields.Float(compute="_compute_fill", string="Заповнення")
    below_min = fields.Boolean(
        compute="_compute_below_min",
        store=True,
        index=True,
        string="Нижче мінімуму",
        help="Є правило поповнення, і кількість у порталі менша за його мінімум (домен не вміє порівнювати поле з полем).",
    )
    job_ids = fields.One2many("td.gantry.job", "stack_id", string="Завдання")
    note = fields.Text()

    _f3d_stack_loc_uniq = models.Constraint("UNIQUE(location_id)", "Для місця вже є стос.")
    _f3d_stack_ws_qty = models.Constraint("CHECK(ws_qty >= 0)", "Кількість у порталі не може бути від'ємною.")

    @api.depends("code")
    def _compute_rowcol(self):
        for rec in self:
            m = ROWCOL_RE.match(rec.code or "")
            rec.row = int(m.group(1)) if m else 0
            rec.col = m.group(2) if m else False

    @api.depends("ws_product")
    def _compute_ws_product(self):
        for rec in self:
            rec.ws_product_id = (
                self.env["product.product"].search([("default_code", "=", rec.ws_product)], limit=1)
                if rec.ws_product
                else False
            )

    @api.depends("ws_qty", "capacity")
    def _compute_fill(self):
        for rec in self:
            rec.fill = rec.ws_qty / rec.capacity if rec.capacity > 0 else 0.0

    @api.depends("ws_qty", "orderpoint_id.product_min_qty")
    def _compute_below_min(self):
        for rec in self:
            rec.below_min = bool(rec.orderpoint_id) and rec.ws_qty < rec.orderpoint_id.product_min_qty

    # --- R-15: звірка стосу ---------------------------------------------------------------------------
    def _td_odoo_side(self):
        """Кванти локації: (qty, товар з найбільшою к-стю, його партія з найбільшою к-стю)."""
        self.ensure_one()
        quants = self.env["stock.quant"].sudo().search([("location_id", "=", self.location_id.id)])
        by_product, by_lot = {}, {}
        for q in quants:
            by_product[q.product_id] = by_product.get(q.product_id, 0.0) + q.quantity
        qty = sum(by_product.values())
        product = max(by_product, key=by_product.get) if by_product else self.env["product.product"]
        for q in quants.filtered(lambda q: q.product_id == product and q.lot_id):
            by_lot[q.lot_id] = by_lot.get(q.lot_id, 0.0) + q.quantity
        lot = max(by_lot, key=by_lot.get) if by_lot else self.env["stock.lot"]
        return qty, product, lot

    def _td_fed_unconsumed(self):
        self.ensure_one()
        jobs = (
            self.env["td.gantry.job"]
            .sudo()
            .search(
                [
                    ("stack_id", "=", self.id),
                    ("type", "=", "feed"),
                    ("state", "in", ("active", "done")),
                    ("production_id", "!=", False),
                    ("production_id.state", "not in", ("done", "cancel")),
                ]
            )
        )
        return float(sum(jobs.mapped("done")))

    def _td_activity_domain(self):
        self.ensure_one()
        return [
            ("res_model", "=", "td.gantry.stack"),
            ("res_id", "=", self.id),
            ("summary", "=like", "Стос %s:%%" % self.code),
        ]

    def _td_open_activity(self, text):
        """Одна відкрита діяльність на стос (R-15 п. 4)."""
        self.ensure_one()
        if not self.env["mail.activity"].sudo().search_count(self._td_activity_domain()):
            self.sudo().activity_schedule(
                "mail.mail_activity_data_todo", summary=text[:64], note=text, user_id=activity_user(self.env).id
            )

    def _td_refresh(self):
        """R-15 п. 1–5. Без `write`, якщо нічого не змінилось."""
        now = fields.Datetime.now()
        tol = float(param(self.env, "stack_diff_tolerance", "0") or 0)
        confirm = int(param(self.env, "stack_diff_confirm_min", "10") or 10)
        for rec in self:
            odoo_qty, product, lot = rec._td_odoo_side()
            fed = rec._td_fed_unconsumed()
            expected = odoo_qty - fed
            diff = rec.ws_qty - expected
            vals = {
                "odoo_qty": odoo_qty,
                "odoo_product_id": product.id,
                "odoo_lot_id": lot.id,
                "fed_unconsumed": fed,
                "expected_qty": expected,
                "diff": diff,
            }
            text = False
            diff_since = rec.diff_since
            if not rec.ws_seen or now - rec.ws_seen > timedelta(minutes=STALE_MIN):
                state, diff_since = "unknown", False
            elif rec.ws_product and product.default_code and rec.ws_product != product.default_code:
                state = "diff"
                diff_since = diff_since or now
                text = _("Стос %s: у порталі %s, в Odoo %s", rec.code, rec.ws_product, product.default_code)
            elif abs(diff) <= tol:
                state, diff_since = "ok", False
            else:
                diff_since = diff_since or now
                state = "diff" if now - diff_since >= timedelta(minutes=confirm) else "pending"
                if state == "diff":
                    text = _(
                        "Стос %s: портал %g, має бути %g (Odoo %g − подано %g)",
                        rec.code,
                        rec.ws_qty,
                        expected,
                        odoo_qty,
                        fed,
                    )
            vals.update(state=state, diff_since=diff_since)
            changed = {}
            for key, val in vals.items():
                cur = rec[key]
                cur = cur.id if hasattr(cur, "id") else cur
                if isinstance(val, float) and isinstance(cur, float):
                    if abs(val - cur) > 1e-6:
                        changed[key] = val
                elif (cur or False) != (val or False):
                    changed[key] = val
            if changed:
                rec.write(changed)
            if text:
                rec._td_open_activity(text)
            elif state == "ok":
                found = self.env["mail.activity"].sudo().search(rec._td_activity_domain())
                if found:
                    found.action_feedback(feedback=_("Збігається"))
        return True

    # --- R-23 п. 3: події woodStore -------------------------------------------------------------------
    @api.model
    def _td_apply_ws(self, items, ts=None):
        now = fields.Datetime.now()
        stacks = self.sudo().search([])
        by_code = {s.code: s for s in stacks}
        touched = self.browse()
        for item in items or []:
            rec = by_code.get(item.get("id"))
            if not rec:
                _logger.warning("woodStore: невідомий стос %s", item.get("id"))
                continue
            vals = {
                "ws_qty": int(item.get("qty") or 0),
                "ws_product": item.get("product") or False,
                "ws_lot": item.get("lot") or False,
                "ws_reserved": int(item.get("reserved") or 0),
                "ws_locked": bool(item.get("locked")),
                "ws_updated": parse_ts(item.get("updated")) or False,
            }
            changed = {k: v for k, v in vals.items() if (rec[k] or False) != (v or False)}
            changed["ws_seen"] = now
            rec.write(changed)
            touched |= rec
        touched._td_refresh()
        count = len(stacks.filtered(lambda s: s.ws_qty > 0))
        sig = self.env["td.signal"].sudo().search([("code", "=", GANTRY_STACKS_CODE)], limit=1)
        if sig:
            self.env["td.signal"].sudo().with_context(f3d_mc_internal=True)._td_ingest(
                [{"code": sig.code, "ts": now, "value": count, "q": "good"}], src="module"
            )
        if touched and "td.viewer.event" in self.env:
            self.env["td.viewer.event"]._notify("stock.location", touched.mapped("code"), "stock")
        return len(touched)

    # --- дії ------------------------------------------------------------------------------------------
    def action_accept_portal(self):
        """R-15 п. 6а: інвентаризація стосу до даних порталу."""
        check_stock_manager(self.env)
        for rec in self:
            product = rec.odoo_product_id or rec.ws_product_id
            if not product:
                raise UserError(_("Стос %s: невідомий товар.", rec.code))
            lot = rec.odoo_lot_id
            if not lot and product.tracking != "none" and rec.ws_lot:
                lot = (
                    self.env["stock.lot"]
                    .sudo()
                    .search([("name", "=", rec.ws_lot), ("product_id", "=", product.id)], limit=1)
                )
            Quant = self.env["stock.quant"].sudo().with_context(inventory_mode=True)
            quants = self.env["stock.quant"].sudo().search([("location_id", "=", rec.location_id.id)])
            target_quant = quants.filtered(
                lambda q, product=product, lot=lot: q.product_id == product and q.lot_id == lot
            )
            others = sum((quants - target_quant).mapped("quantity"))
            target = rec.ws_qty + rec.fed_unconsumed - others
            if target_quant:
                quant = Quant.browse(target_quant[:1].id)
                quant.inventory_quantity = target
            else:
                quant = Quant.create(
                    {
                        "product_id": product.id,
                        "location_id": rec.location_id.id,
                        "lot_id": lot.id if lot else False,
                        "inventory_quantity": target,
                    }
                )
            quant.action_apply_inventory()
            rec.message_post(
                body=_(
                    "Прийнято з порталу: залишок %g арк. (портал %d, подано не списано %g).",
                    target,
                    rec.ws_qty,
                    rec.fed_unconsumed,
                ),
                subtype_xmlid="mail.mt_note",
            )
            rec._td_refresh()
        return True

    def action_fix_portal(self):
        """R-15 п. 6б: CMD-02 `stack` (потребує запису)."""
        check_stock_manager(self.env)
        for rec in self:
            rec._td_push_stack_cmd()
        return True

    def _td_push_stack_cmd(self):
        self.ensure_one()
        product = self.odoo_product_id or self.ws_product_id
        if not product.default_code:
            raise UserError(_("Стос %s: у товару немає внутрішнього коду.", self.code))
        fields_ = {
            "stack": self.code,
            "qty": int(self.expected_qty),
            "product": product.default_code,
            "lot": self.odoo_lot_id.name or None,
        }
        return self.env["td.command"]._td_mc_create_command(gantry_cmd_signal(self.env), "stack", fields_)

    def _td_replenish(self):
        """R-18 п. 2: стандартне поповнення за правилом."""
        self.ensure_one()
        if not self.orderpoint_id:
            raise UserError(_("Для стосу %s немає правила поповнення.", self.code))
        res = self.orderpoint_id.sudo().action_replenish()
        self.sudo().replenish_at = fields.Datetime.now()
        return res

    def action_replenish(self):
        res = True
        for rec in self:
            res = rec._td_replenish()
        return res if isinstance(res, dict) else True

    @api.model
    def _td_cron_replenish(self):
        """R-18 п. 1 (лише при `gantry_auto_replenish`)."""
        if not param_bool(self.env, "gantry_auto_replenish"):
            return
        now = fields.Datetime.now()
        Move = self.env["stock.move"].sudo()
        for rec in self.sudo().search([("orderpoint_id", "!=", False)]):
            qty = rec.expected_qty if rec.state == "unknown" else rec.ws_qty
            if qty >= rec.min_qty:
                continue
            if rec.replenish_at and now - rec.replenish_at < timedelta(hours=1):
                continue
            if Move.search_count(
                [("location_dest_id", "=", rec.location_id.id), ("state", "not in", ("done", "cancel", "draft"))]
            ):
                continue
            try:
                with self.env.cr.savepoint():
                    rec._td_replenish()
            except Exception:
                _logger.exception("Поповнення стосу %s не вдалося", rec.code)
                rec.replenish_at = now

    def _td_after_arrival(self, picking=None):
        """R-18 п. 3: листи прийшли в стос — оновити стос у woodStore (команда або діяльність)."""
        for rec in self:
            rec._td_refresh()
            try:
                with self.env.cr.savepoint():
                    rec._td_push_stack_cmd()
            except UserError:
                product = rec.odoo_product_id.default_code or ""
                text = _("Оновіть стос %s у woodStore: %d арк. %s", rec.code, int(rec.expected_qty), product)
                user = (picking.user_id if picking else False) or activity_user(self.env)
                rec.sudo().activity_schedule(
                    "mail.mail_activity_data_todo", summary=text[:64], note=text, user_id=user.id
                )

    def action_view_quants(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Залишки %s", self.code),
            "res_model": "stock.quant",
            "view_mode": "list",
            "domain": [("location_id", "=", self.location_id.id)],
        }

    def action_view_jobs(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Завдання порталу %s", self.code),
            "res_model": "td.gantry.job",
            "view_mode": "list,form",
            "domain": [("stack_id", "=", self.id)],
            "context": {"default_stack_id": self.id},
        }

    def action_f3d_show(self):
        self.ensure_one()
        return self.location_id.action_f3d_show()
