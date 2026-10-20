import logging
from datetime import timezone

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from ..tools import ppt
from .td_machine import KYIV, local

_logger = logging.getLogger(__name__)


class F3dDowntime(models.Model):
    _name = "td.downtime"
    _description = "Верстати: простій"
    _inherit = ["mail.thread"]
    _order = "date_start desc, id desc"

    name = fields.Char(compute="_compute_name", store=True)
    machine_id = fields.Many2one("td.machine", string="Верстат", required=True, index=True, ondelete="cascade")
    workcenter_id = fields.Many2one("mrp.workcenter", related="machine_id.workcenter_id", store=True, index=True)
    code = fields.Char(related="machine_id.code", store=True)
    company_id = fields.Many2one("res.company", related="machine_id.company_id", store=True, index=True)
    date_start = fields.Datetime(string="Початок", required=True, index=True, tracking=True)
    date_end = fields.Datetime(string="Кінець", index=True, tracking=True)
    is_open = fields.Boolean(compute="_compute_open", store=True, index=True, string="Триває")
    duration_min = fields.Float(compute="_compute_duration", store=True, digits=(12, 1), string="Тривалість, хв")
    duration_live = fields.Float(compute="_compute_live", string="Тривалість (поточна), хв")
    ppt_min = fields.Float(digits=(12, 1), string="У плановому часі, хв")
    state_kind = fields.Selection(
        [("fault", "Аварія"), ("setup", "Налагодження"), ("idle", "Очікування"), ("off", "Вимкнено")],
        string="Стан верстата",
        required=True,
    )
    loss_id = fields.Many2one(
        "mrp.workcenter.productivity.loss",
        string="Причина",
        required=True,
        ondelete="restrict",
        tracking=True,
        domain="[('loss_type', 'in', ('availability', 'quality'))]",
        default=lambda s: s.env.ref("td_machine_connect.loss_unknown", raise_if_not_found=False),
    )
    loss_type = fields.Selection(related="loss_id.loss_type")
    planned = fields.Boolean(related="loss_id.td_planned", string="Плановий")
    reason_source = fields.Selection(
        [
            ("auto", "Автоматично"),
            ("hint", "Підказка верстата"),
            ("operator", "Оператор"),
            ("master", "Майстер"),
            ("demo", "Демо-дані"),
        ],
        string="Хто вказав",
        required=True,
        default="auto",
        tracking=True,
    )
    reason_state = fields.Selection(
        [
            ("to_classify", "Потребує причини"),
            ("to_confirm", "Потребує підтвердження"),
            ("confirmed", "Підтверджено"),
        ],
        string="Класифікація",
        required=True,
        index=True,
        default="to_classify",
        tracking=True,
    )
    hint_loss_id = fields.Many2one("mrp.workcenter.productivity.loss", string="Підказка", ondelete="set null")
    hint_text = fields.Char(string="Звідки підказка", size=256)
    event_id = fields.Many2one("td.machine.event", string="Подія верстата", ondelete="set null")
    workorder_id = fields.Many2one("mrp.workorder", string="Завдання", ondelete="set null")
    production_id = fields.Many2one("mrp.production", related="workorder_id.production_id", store=True)
    employee_id = fields.Many2one("hr.employee", string="Працівник (причина)", ondelete="set null")
    reason_user_id = fields.Many2one("res.users", string="Причину вказав", readonly=True)
    reason_at = fields.Datetime(readonly=True)
    confirmed_by = fields.Many2one("res.users", string="Підтвердив", readonly=True)
    confirmed_at = fields.Datetime(readonly=True)
    productivity_ids = fields.One2many("mrp.workcenter.productivity", "td_downtime_id", string="Записи журналу часу")
    maintenance_request_id = fields.Many2one("maintenance.request", string="Заявка ТО", ondelete="set null")
    note = fields.Text(string="Примітка")
    has_loss_tool = fields.Boolean(compute="_compute_has_loss_tool")
    # Простої в гривнях (DT-1): тривалість × ставка РЦ (`mrp.workcenter.costs_hour`) у валюті компанії верстата.
    currency_id = fields.Many2one("res.currency", related="company_id.currency_id", string="Валюта")
    cost = fields.Monetary(
        compute="_compute_cost",
        store=True,
        currency_field="currency_id",
        string="Вартість простою",
        help="Тривалість простою (год) × ставка робочого центра за годину. Відкритий простій — 0 до закриття.",
    )
    cost_live = fields.Monetary(compute="_compute_cost_live", currency_field="currency_id", string="Вартість (поточна)")
    shift_date = fields.Date(
        compute="_compute_shift_date",
        store=True,
        index=True,
        string="Зміна (дата)",
        help="Дата зміни за київським часом: та сама, що `Дата зміни` в OEE (одна зміна — одна доба).",
    )

    _f3d_downtime_dates = models.Constraint(
        "CHECK(date_end IS NULL OR date_end >= date_start)", "Кінець простою раніше за початок."
    )

    def init(self):
        self.env.cr.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS td_downtime_open_uniq ON td_downtime (machine_id) WHERE date_end IS NULL"
        )

    @api.depends("code", "date_start")
    def _compute_name(self):
        for rec in self:
            rec.name = "%s · %s" % (rec.code or "", local(rec.date_start, "%d.%m %H:%M"))

    @api.depends("date_end")
    def _compute_open(self):
        for rec in self:
            rec.is_open = not rec.date_end

    @api.depends("date_start", "date_end")
    def _compute_duration(self):
        for rec in self:
            rec.duration_min = (
                (rec.date_end - rec.date_start).total_seconds() / 60 if rec.date_end and rec.date_start else 0.0
            )

    @api.depends("date_start", "date_end", "duration_min")
    def _compute_live(self):
        now = fields.Datetime.now()
        for rec in self:
            if rec.date_end or not rec.date_start:
                rec.duration_live = rec.duration_min
            else:
                rec.duration_live = (now - rec.date_start).total_seconds() / 60

    @api.depends("duration_min", "workcenter_id.costs_hour", "currency_id")
    def _compute_cost(self):
        for rec in self:
            cost = rec.duration_min / 60.0 * rec.workcenter_id.sudo().costs_hour
            rec.cost = rec.currency_id.round(cost) if rec.currency_id else cost

    @api.depends("date_start", "date_end", "duration_min", "workcenter_id.costs_hour", "currency_id")
    def _compute_cost_live(self):
        now = fields.Datetime.now()
        for rec in self:
            if rec.date_end or not rec.date_start:
                rec.cost_live = rec.cost
                continue
            cost = (now - rec.date_start).total_seconds() / 3600.0 * rec.workcenter_id.sudo().costs_hour
            rec.cost_live = rec.currency_id.round(cost) if rec.currency_id else cost

    @api.depends("date_start")
    def _compute_shift_date(self):
        for rec in self:
            rec.shift_date = (
                rec.date_start.replace(tzinfo=timezone.utc).astimezone(KYIV).date() if rec.date_start else False
            )

    def _compute_has_loss_tool(self):
        has = bool(self.env.ref("factory3d.loss_tool", raise_if_not_found=False))
        for rec in self:
            rec.has_loss_tool = has

    # --- вартість простоїв (DT-1) ---------------------------------------------------------------------
    @api.model
    def _td_month_start(self):
        """Початок поточного місяця за київським часом як naive UTC (межа «за місяць» плитки й 3D)."""
        now = fields.Datetime.now().replace(tzinfo=timezone.utc).astimezone(KYIV)
        first = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return first.astimezone(timezone.utc).replace(tzinfo=None)

    @api.model
    def _td_cost_can_see(self):
        return bool(self.env.su or self.env.user.has_group("td_factory3d.group_td_manager"))

    @api.model
    def _td_cost_by_workcenter(self, since=None, company=None):
        """`{workcenter_id: сума}` простоїв з `since` (умовчання — місяць): закриті за `cost`, відкриті наживо."""
        domain = [
            ("date_start", ">=", since or self._td_month_start()),
            ("company_id", "=", (company or self.env.company).id),
        ]
        Downtime = self.sudo()
        res = {}
        for wc, total in Downtime._read_group(domain + [("date_end", "!=", False)], ["workcenter_id"], ["cost:sum"]):
            res[wc.id] = total or 0.0
        for rec in Downtime.search(domain + [("date_end", "=", False)]):
            res[rec.workcenter_id.id] = res.get(rec.workcenter_id.id, 0.0) + rec.cost_live
        return res

    @api.model
    def _td_cost_sum(self, domain):
        """Сума вартості за доменом: закриті простої — за `cost`, відкриті — наживо (`cost_live`)."""
        Downtime = self.sudo()
        closed = Downtime._read_group(domain + [("date_end", "!=", False)], [], ["cost:sum"])[0][0] or 0.0
        return closed + sum(Downtime.search(domain + [("date_end", "=", False)]).mapped("cost_live"))

    @api.model
    def td_cost_tile(self):
        """Плитка «Огляд верстатів» (DT-2): простої за поточний місяць у валюті компанії і з них — без причини.

        `False` без групи менеджера «Завод 3D» (вартість — управлінські дані): плитка не показується.
        """
        if not self._td_cost_can_see():
            return False
        company = self.env.company
        domain = [("date_start", ">=", self._td_month_start()), ("company_id", "=", company.id)]
        currency = company.currency_id
        return {
            "total": currency.round(self._td_cost_sum(domain)),
            "no_reason": currency.round(self._td_cost_sum(domain + [("reason_state", "=", "to_classify")])),
            "currency_id": currency.id,
            "symbol": currency.symbol,
            "position": currency.position,
            "decimals": currency.decimal_places,
        }

    # --- причина, підтвердження (M-03) ---------------------------------------------------------------
    def _td_reason_rights(self):
        """Права й `src` за замовчуванням: `(is_manager)`; `AccessError` без `mrp.group_mrp_user`."""
        user = self.env.user
        if not (self.env.su or user.has_group("mrp.group_mrp_user")):
            raise AccessError(_("Причину простою вказує користувач виробництва."))
        is_manager = user.has_group("mrp.group_mrp_manager")
        if any(rec.reason_state == "confirmed" for rec in self) and not (self.env.su or is_manager):
            raise UserError(_("Простій підтверджено — змінити причину може майстер."))
        return is_manager

    def action_set_reason(self, loss_id, employee_id=None, source=None):
        is_manager = self._td_reason_rights()
        loss = self.env["mrp.workcenter.productivity.loss"].browse(loss_id).exists()
        if not loss or loss.sudo().loss_type not in ("availability", "quality"):
            raise UserError(_("Причина має бути втратою доступності або якості."))
        src = source or ("master" if is_manager else "operator")
        employee = self.env["hr.employee"].browse(employee_id).exists() if employee_id else self.env["hr.employee"]
        for rec in self:
            rec._td_apply_reason(loss, src, employee)
            rec.sudo().with_context(f3d_mc_internal=True).write(
                {"reason_state": "confirmed" if src == "master" else "to_confirm"}
            )
        return True

    def action_confirm(self):
        if not (self.env.su or self.env.user.has_group("mrp.group_mrp_manager")):
            raise AccessError(_("Підтверджує простій майстер."))
        unknown = self.env.ref("td_machine_connect.loss_unknown")
        for rec in self:
            if rec.loss_id == unknown:
                raise UserError(_("Спершу вкажіть причину простою %s.", rec.display_name))
        self.sudo().with_context(f3d_mc_internal=True).write(
            {"reason_state": "confirmed", "confirmed_by": self.env.uid, "confirmed_at": fields.Datetime.now()}
        )
        return True

    def action_open_reason_wizard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Причина простою"),
            "res_model": "td.downtime.reason.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_downtime_id": self.id},
        }

    def action_quick_reason(self):
        """Кнопки kanban «Без причини»: причина за XML-id з контексту `f3d_loss_xmlid`."""
        loss = self.env.ref(self.env.context["f3d_loss_xmlid"])
        return self.action_set_reason(loss.id)

    def _td_apply_reason(self, loss, source, employee=None):
        """Записати причину простою; машинні записи журналу часу отримують ту саму причину."""
        who = dict(self._fields["reason_source"]._description_selection(self.env)).get(source, source)
        for rec in self:
            rec.sudo().with_context(f3d_mc_internal=True).write(
                {
                    "loss_id": loss.id,
                    "reason_source": source,
                    "employee_id": employee.id if employee else False,
                    "reason_user_id": self.env.uid,
                    "reason_at": fields.Datetime.now(),
                }
            )
            rec.sudo().productivity_ids.filtered("td_auto").write({"loss_id": loss.id})
            rec.sudo().message_post(body=_("Причина: %(loss)s (%(who)s)", loss=loss.sudo().name, who=who))

    def _td_set_hint(self, loss, text, event, apply):
        """R-07: підказка (і причина, якщо `apply` і причину ще не вказав оператор/майстер)."""
        self.ensure_one()
        self.sudo().with_context(f3d_mc_internal=True).write(
            {"hint_loss_id": loss.id, "hint_text": (text or "")[:256], "event_id": event.id if event else False}
        )
        if event:
            event.sudo().write({"downtime_id": self.id})
        if apply and self.reason_source in ("auto", "hint"):
            self._td_apply_reason(loss, "hint")
            self.sudo().with_context(f3d_mc_internal=True).write({"reason_state": "to_confirm"})

    def _td_close(self, ts):
        """R-05 п. 4: закрити простій переходом о `ts` (коротку не аварію — видалити)."""
        for dt in self.sudo():
            if dt.date_end:
                continue
            machine = dt.machine_id
            end = max(ts, dt.date_start)
            wc = dt.workcenter_id
            ppt_min = ppt.total_min(ppt.ppt_intervals(self.env, wc, dt.date_start, end))
            tech = machine._td_tech_env()
            recs = dt.productivity_ids
            operator = [(r.date_start, r.date_end or end) for r in recs if not r.td_auto]
            for rec in recs.filtered(lambda r: not r.date_end):
                rec.with_env(tech).write({"date_end": max(end, rec.date_start)})
            if dt.state_kind != "fault" and ppt_min * 60 < machine.micro_stop_s:
                dt.unlink()
                continue
            dt.write({"date_end": end, "ppt_min": ppt_min})
            if dt.state_kind == "fault":
                continue
            label = dict(self._fields["state_kind"]._description_selection(self.env)).get(dt.state_kind, "")
            desc = "%s: %s" % (label, dt.loss_id.name)
            if dt.hint_text:
                desc += "; %s" % dt.hint_text
            wo = dt.workorder_id if dt.state_kind == "setup" else False
            for start, stop in ppt.minus([(dt.date_start, end)], operator):
                if (stop - start).total_seconds() < 60 * 1.0:
                    continue
                machine._td_create_machine_record(dt, start, desc, date_end=stop, workorder=wo)
        return True

    def write(self, vals):
        if "loss_id" in vals and not self.env.context.get("f3d_mc_internal"):
            self._td_reason_rights()
        return super().write(vals)

    def unlink(self):
        if not (self.env.su or self.env.user.has_group("td_factory3d.group_td_admin")):
            raise AccessError(_("Простій видаляє лише адміністратор."))
        return super().unlink()
