"""W1-A: M-25 `td.energy.outage.plan` — планове відключення (R-31, API-09/10, FR-39)."""

import logging

from odoo import Command, _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from ..tools import bus, dates

_logger = logging.getLogger(__name__)

AFFECTED_KINDS = ("tapoff", "consumer")
ACTIVE_STATES = ("pending", "approved")
STATE_LABELS = {
    "draft": "чернетка",
    "pending": "на узгодженні",
    "approved": "узгоджено",
    "rejected": "відхилено",
    "done": "виконано",
    "cancelled": "скасовано",
}


class TdEnergyOutagePlan(models.Model):
    _name = "td.energy.outage.plan"
    _description = "Енергетика: планове відключення"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "start desc, id desc"

    name = fields.Char(string="Назва", compute="_compute_name", store=True)
    node_id = fields.Many2one(
        "td.energy.node",
        string="Вузол",
        required=True,
        ondelete="restrict",
        index=True,
        tracking=True,
        domain="[('kind', 'in', ('line', 'cell', 'transformer', 'section', 'switchboard'))]",
    )
    reason = fields.Selection(
        [
            ("busway", "Протяжка з'єднань шинопроводу"),
            ("thermo", "Тепловізійний огляд і ремонт"),
            ("replace", "Заміна відгалуження"),
            ("other", "Інша"),
        ],
        string="Причина",
        required=True,
        default="busway",
    )
    reason_text = fields.Char(string="Причина (текст)", size=128)
    start = fields.Datetime(string="Початок", required=True, tracking=True)
    end = fields.Datetime(string="Кінець", required=True, tracking=True)
    state = fields.Selection(
        [
            ("draft", "Чернетка"),
            ("pending", "На узгодженні"),
            ("approved", "Узгоджено"),
            ("rejected", "Відхилено"),
            ("done", "Виконано"),
            ("cancelled", "Скасовано"),
        ],
        string="Стан",
        default="draft",
        index=True,
        tracking=True,
    )
    affected_node_ids = fields.Many2many(
        "td.energy.node",
        "td_energy_outage_plan_node_rel",
        "plan_id",
        "node_id",
        string="Зачеплені відгалуження",
        readonly=True,
    )
    affected_count = fields.Integer(string="Відгалужень", compute="_compute_counts", store=True)
    production_ids = fields.Many2many(
        "mrp.production",
        "td_energy_outage_plan_mo_rel",
        "plan_id",
        "production_id",
        string="Замовлення на виробництво",
        readonly=True,
    )
    production_count = fields.Integer(string="Замовлень", compute="_compute_counts", store=True)
    requested_by = fields.Many2one("res.users", string="Автор", default=lambda self: self.env.uid, readonly=True)
    approver_id = fields.Many2one("res.users", string="Узгодив", readonly=True)
    approved_at = fields.Datetime(string="Узгоджено", readonly=True)
    reject_reason = fields.Char(string="Причина відхилення", size=256, readonly=True)
    company_id = fields.Many2one("res.company", string="Компанія", required=True, default=lambda self: self.env.company)
    note = fields.Text(string="Примітка")

    # --- обчислювані й перевірки ---------------------------------------------------------------------
    @api.depends("node_id", "node_id.sld_label", "node_id.name", "start", "end")
    def _compute_name(self):
        for rec in self:
            if rec.node_id and rec.start and rec.end:
                start, end = dates.to_local(rec.start), dates.to_local(rec.end)
                rec.name = "%s · %s %s–%s" % (
                    rec.node_id.sld_label or rec.node_id.name,
                    start.strftime("%d.%m"),
                    start.strftime("%H:%M"),
                    end.strftime("%H:%M"),
                )
            else:
                rec.name = rec.node_id.sld_label or rec.node_id.name or ""

    @api.depends("affected_node_ids", "production_ids")
    def _compute_counts(self):
        for rec in self:
            rec.affected_count = len(rec.affected_node_ids)
            rec.production_count = len(rec.production_ids)

    @api.constrains("start", "end")
    def _check_period(self):
        for rec in self:
            if rec.start and rec.end and rec.end <= rec.start:
                raise ValidationError(_("Кінець має бути пізніше за початок."))

    @api.constrains("node_id", "start", "end", "state")
    def _check_overlap(self):
        for rec in self.filtered(lambda r: r.state in ACTIVE_STATES):
            other = self.sudo().search(
                [
                    ("id", "!=", rec.id),
                    ("node_id", "=", rec.node_id.id),
                    ("state", "in", ACTIVE_STATES),
                    ("start", "<", rec.end),
                    ("end", ">", rec.start),
                ],
                limit=1,
            )
            if other:
                label = rec.node_id.sld_label or rec.node_id.name
                raise ValidationError(_("Для %s вже є відключення в цей час.", label))

    @api.constrains("reason", "reason_text")
    def _check_reason(self):
        for rec in self:
            if rec.reason == "other" and not (rec.reason_text or "").strip():
                raise ValidationError(_("Вкажіть причину відключення."))

    # --- R-31 п. 1–2: зачеплені відгалуження й замовлення ---------------------------------------------
    @api.model
    def _td_affected(self, node, start, end):
        """(вузли `tapoff|consumer` піддерева, коди відгалужень, `mrp.workorder` у вікні)."""
        affected = self.env["td.energy.node"].search([("id", "child_of", node.id), ("kind", "in", AFFECTED_KINDS)])
        taps = affected.filtered(lambda n: n.kind == "tapoff")
        tap_codes = (taps or affected).mapped("code")
        orders = self.env["mrp.workorder"]
        workcenters = affected.workcenter_id
        if workcenters and start and end:
            orders = (
                self.env["mrp.workorder"]
                .sudo()
                .search(
                    [
                        ("workcenter_id", "in", workcenters.ids),
                        ("state", "not in", ("done", "cancel")),
                        ("date_start", "!=", False),
                        ("date_finished", "!=", False),
                        ("date_start", "<", end),
                        ("date_finished", ">", start),
                    ],
                    order="date_start, id",
                )
            )
        return affected, tap_codes, orders

    @api.model
    def preview(self, node_code, start, end):
        """API-09: попередній перегляд зачеплених відгалужень і замовлень, без запису."""
        node = self.env["td.energy.node"].search([("code", "=", node_code)], limit=1)
        if not node:
            raise UserError(_("Невідомий вузол: %s.", node_code))
        start, end = fields.Datetime.to_datetime(start), fields.Datetime.to_datetime(end)
        _affected, tap_codes, orders = self._td_affected(node, start, end)
        seen, rows = set(), []
        for wo in orders:  # одне МО — один рядок (за першою операцією)
            if wo.production_id.id in seen:
                continue
            seen.add(wo.production_id.id)
            rows.append(
                {
                    "name": wo.production_id.name,
                    "product": wo.production_id.product_id.display_name or "",
                    "date_start": fields.Datetime.to_string(wo.date_start),
                }
            )
        return {"tap_codes": tap_codes, "tap_count": len(tap_codes), "orders": rows, "order_count": len(rows)}

    # --- переходи -------------------------------------------------------------------------------------
    def _td_check_energetic(self):
        if not self.env.user.has_group("td_energy.group_td_energy_manager"):
            raise AccessError(_("Планувати відключення може лише енергетик."))

    def _td_users(self, xmlid):
        group = self.env.ref(xmlid, raise_if_not_found=False)
        if not group:
            return self.env["res.users"]
        return group.sudo().all_user_ids.filtered(lambda u: u.active and not u.share)

    def action_submit(self):
        """R-31 п. 3: перевірки, зачеплені, activity керівникам виробництва, сповіщення складу, `pending`."""
        self._td_check_energetic()
        now = dates.now_utc(self.env)
        for rec in self:
            if rec.state != "draft":
                raise UserError(_("На узгодження можна надіслати лише чернетку."))
            if rec.start < now:
                raise UserError(_("Початок має бути в майбутньому."))
            affected, _codes, orders = self._td_affected(rec.node_id, rec.start, rec.end)
            rec.sudo().write(
                {
                    "affected_node_ids": [Command.set(affected.ids)],
                    "production_ids": [Command.set(orders.production_id.ids)],
                    "state": "pending",
                }
            )
            rec._td_notify_submit()
        bus.tick(self.env, "state")
        return True

    def _td_notify_submit(self):
        """R-31 п. 4: activity керівникам виробництва; склад підписується й отримує повідомлення."""
        self.ensure_one()
        sudo = self.sudo()
        deadline = dates.to_local(self.start).date()
        for user in self._td_users("mrp.group_mrp_manager"):
            sudo.activity_schedule(
                "mail.mail_activity_data_todo",
                date_deadline=deadline,
                summary=_("Узгодити відключення %s", self.name),
                note=_(
                    "Планове відключення %(name)s: відгалужень — %(taps)s, замовлень — %(orders)s.",
                    name=self.name,
                    taps=self.affected_count,
                    orders=self.production_count,
                ),
                user_id=user.id,
            )
        subscribers = self._td_users("td_energy.group_td_energy_manager") | self.requested_by
        sudo.message_subscribe(partner_ids=subscribers.partner_id.ids)
        stock = self._td_users("stock.group_stock_manager")
        if stock:
            sudo.message_subscribe(partner_ids=stock.partner_id.ids)
            sudo.message_post(
                body=_(
                    "Планове відключення %(name)s надіслано на узгодження. Замовлень у вікні відключення: %(orders)s.",
                    name=self.name,
                    orders=self.production_count,
                ),
                subtype_xmlid="mail.mt_comment",
                partner_ids=stock.partner_id.ids,
            )

    def _td_check_mrp_manager(self):
        if not self.env.user.has_group("mrp.group_mrp_manager"):
            raise AccessError(_("Узгоджує керівник виробництва."))

    def action_approve(self):
        self._td_check_mrp_manager()
        now = dates.now_utc(self.env)
        for rec in self.sudo():
            if rec.state != "pending":
                raise UserError(_("Узгоджувати можна лише відключення на узгодженні."))
            rec.write({"state": "approved", "approver_id": self.env.uid, "approved_at": now})
            rec.activity_ids.unlink()
            rec.message_post(
                body=_("Узгоджено: %(name)s (%(user)s).", name=rec.name, user=self.env.user.name),
                subtype_xmlid="mail.mt_comment",
            )
        bus.tick(self.env, "state")
        return True

    def action_reject(self, reason=None):
        self._td_check_mrp_manager()
        reason = (reason or "").strip()
        if not reason:
            raise UserError(_("Вкажіть причину відхилення."))
        now = dates.now_utc(self.env)
        for rec in self.sudo():
            if rec.state != "pending":
                raise UserError(_("Відхиляти можна лише відключення на узгодженні."))
            rec.write(
                {"state": "rejected", "approver_id": self.env.uid, "approved_at": now, "reject_reason": reason[:256]}
            )
            rec.activity_ids.unlink()
            rec.message_post(
                body=_("Відхилено: %(name)s. Причина: %(reason)s", name=rec.name, reason=reason),
                subtype_xmlid="mail.mt_comment",
            )
        bus.tick(self.env, "state")
        return True

    def action_cancel(self):
        energetic = self.env.user.has_group("td_energy.group_td_energy_manager")
        for rec in self.sudo():
            if not energetic and rec.requested_by.id != self.env.uid:
                raise AccessError(_("Скасувати відключення може енергетик або його автор."))
            if rec.state not in ("draft", "pending", "approved"):
                raise UserError(_("Скасувати можна лише чернетку, відключення на узгодженні або узгоджене."))
            rec.write({"state": "cancelled"})
            rec.activity_ids.unlink()
        bus.tick(self.env, "state")
        return True

    @api.model
    def _cron_close(self):
        """R-31 п. 7: `approved` після кінця → `done`; `draft|pending` після кінця → `cancelled`."""
        try:
            with self.env.cr.savepoint():
                now = dates.now_utc(self.env)
                Plan = self.sudo()
                done = Plan.search([("state", "=", "approved"), ("end", "<", now)])
                stale = Plan.search([("state", "in", ("draft", "pending")), ("end", "<", now)])
                done.write({"state": "done"})
                stale.write({"state": "cancelled"})
                stale.activity_ids.unlink()
                if done or stale:
                    bus.tick(self.env, "state")
        except Exception:
            _logger.exception("td_energy: крон планових відключень")
        return True

    # --- допоміжне для API (картка вузла, Пульт) ------------------------------------------------------
    def _td_when(self):
        """«25.10 · 07:00–09:00» (Київ)."""
        self.ensure_one()
        start, end = dates.to_local(self.start), dates.to_local(self.end)
        return "%s · %s–%s" % (start.strftime("%d.%m"), start.strftime("%H:%M"), end.strftime("%H:%M"))

    def _td_reason_label(self):
        self.ensure_one()
        if self.reason == "other":
            return self.reason_text or ""
        label = dict(self._fields["reason"].selection).get(self.reason, "")
        return label[:1].lower() + label[1:]
