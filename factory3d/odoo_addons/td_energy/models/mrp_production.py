from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError

from odoo.addons.factory3d_telemetry.tools.titles import fmt_num

from ..tools import dates

COST_GROUP = "factory3d_energy.group_f3d_energy_cost"
QUALITY_LABEL = {"none": "немає даних", "estimate": "оцінка", "partial": "частково виміряно", "measured": "виміряно"}


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    f3d_energy_alloc_ids = fields.One2many("f3d.energy.alloc", "production_id", string="Розподіл енергії")
    f3d_energy_direct_kwh = fields.Float(
        string="Енергія пряма, кВт·год", compute="_compute_f3d_energy", store=True, digits=(12, 3)
    )
    f3d_energy_shared_kwh = fields.Float(
        string="Енергія спільна, кВт·год", compute="_compute_f3d_energy", store=True, digits=(12, 3)
    )
    f3d_energy_kwh = fields.Float(string="Енергія, кВт·год", compute="_compute_f3d_energy", store=True, digits=(12, 3))
    f3d_energy_cost = fields.Float(
        string="Вартість енергії, грн", compute="_compute_f3d_energy", store=True, digits=(12, 2), groups=COST_GROUP
    )
    f3d_energy_unit_cost = fields.Float(
        string="Енергія на одиницю, грн", compute="_compute_f3d_energy_unit_cost", digits=(12, 4), groups=COST_GROUP
    )
    f3d_energy_state = fields.Selection(
        [
            ("none", "Немає даних"),
            ("estimate", "Оцінка"),
            ("partial", "Частково виміряно"),
            ("measured", "Виміряно"),
        ],
        string="Якість енергії",
        compute="_compute_f3d_energy",
        store=True,
    )
    f3d_energy_locked = fields.Boolean(string="Енергію зафіксовано", readonly=True, copy=False)
    f3d_energy_applied_unit = fields.Float(
        string="Енергія в Extra Unit Cost, грн/од.", readonly=True, copy=False, digits=(12, 4), groups=COST_GROUP
    )

    @api.depends(
        "workorder_ids.f3d_energy_direct_kwh",
        "workorder_ids.f3d_energy_shared_kwh",
        "workorder_ids.f3d_energy_cost",
        "workorder_ids.f3d_energy_quality",
    )
    def _compute_f3d_energy(self):
        for mo in self:
            wos = mo.sudo().workorder_ids
            mo.f3d_energy_direct_kwh = round(sum(wos.mapped("f3d_energy_direct_kwh")), 3)
            mo.f3d_energy_shared_kwh = round(sum(wos.mapped("f3d_energy_shared_kwh")), 3)
            mo.f3d_energy_kwh = round(mo.f3d_energy_direct_kwh + mo.f3d_energy_shared_kwh, 3)
            mo.f3d_energy_cost = round(sum(wos.mapped("f3d_energy_cost")), 2)
            quals = set(wos.mapped("f3d_energy_quality")) - {"none"}
            if not quals:
                mo.f3d_energy_state = "none"
            elif quals == {"measured"}:
                mo.f3d_energy_state = "measured"
            elif quals == {"estimate"}:
                mo.f3d_energy_state = "estimate"
            else:
                mo.f3d_energy_state = "partial"

    def _f3d_energy_qty(self):
        """Кількість у одиницях товару: `qty_producing` (або `product_qty`)."""
        self.ensure_one()
        return self.product_uom_id._compute_quantity(self.qty_producing or self.product_qty, self.product_id.uom_id)

    @api.depends("f3d_energy_cost", "qty_producing", "product_qty", "product_uom_id", "product_id")
    def _compute_f3d_energy_unit_cost(self):
        for mo in self:
            qty = mo._f3d_energy_qty() if mo.product_id else 0.0
            mo.f3d_energy_unit_cost = mo.sudo().f3d_energy_cost / qty if qty else 0.0

    # --- R-10 ------------------------------------------------------------------------------------------
    def _cal_price(self, consumed_moves):
        self.ensure_one()
        if not self.env.context.get("f3d_energy_skip"):
            self._f3d_energy_finalize()
            self._f3d_energy_apply_extra_cost()
        return super()._cal_price(consumed_moves)

    def _f3d_energy_days(self, now):
        """Місцеві дати від першої до останньої хвилини журналу часу завдань МО, обмежені `now`."""
        self.ensure_one()
        starts, ends = [], []
        for wo in self.sudo().workorder_ids:
            for p in wo.time_ids:
                if p.date_start:
                    starts.append(p.date_start)
                    ends.append(p.date_end or now)
        if not starts:
            return []
        lo = min(starts)
        hi = max(min(max(ends), now), lo)
        first, last = dates.local_day(lo), dates.local_day(hi)
        return [first + timedelta(days=i) for i in range((last - first).days + 1)]

    def _f3d_energy_finalize(self):
        """R-10 п. 2, 5: перерахунок діб, фіксація рядків, аналітика, чаттер."""
        self.ensure_one()
        if self.f3d_energy_locked:
            return
        now = dates.now_utc(self.env)
        Alloc = self.env["f3d.energy.alloc"].sudo()
        days = self._f3d_energy_days(now)
        if days:
            Alloc._f3d_alloc_days(days, now=now)
        rows = Alloc.search([("production_id", "=", self.id), ("kind", "in", ("direct", "shared"))])
        rows.write({"locked": True})
        mo = self.sudo()
        mo.f3d_energy_locked = True
        self._f3d_energy_analytic(rows)
        mo.message_post(
            body=_(
                "Енергію зафіксовано: %(kwh)s кВт·год (прямі %(direct)s, спільні %(shared)s), вартість %(cost)s грн, "
                "якість %(quality)s",
                kwh=fmt_num(mo.f3d_energy_kwh, 3),
                direct=fmt_num(mo.f3d_energy_direct_kwh, 3),
                shared=fmt_num(mo.f3d_energy_shared_kwh, 3),
                cost=fmt_num(mo.f3d_energy_cost, 2),
                quality=QUALITY_LABEL[mo.f3d_energy_state],
            )
        )

    def _f3d_energy_analytic(self, rows):
        if not dates.param_bool(self.env, "analytic_enabled"):
            return
        Account = self.env["account.analytic.account"].sudo()
        for row in rows.filtered(lambda r: not r.analytic_line_ids):
            distribution = row.workcenter_id.analytic_distribution
            if not distribution or not row.kwh:
                continue
            vals = Account._perform_analytic_distribution(distribution, -row.cost, row.kwh, row.analytic_line_ids, row)
            if vals:
                row.analytic_line_ids += self.env["account.analytic.line"].sudo().create(vals)

    def _f3d_energy_apply_extra_cost(self):
        """R-10 п. 3–4: енергія в `extra_cost` (FIFO/AVCO) або чаттер для `standard`."""
        self.ensure_one()
        if not dates.param_bool(self.env, "costing_enabled"):
            return
        mo = self.sudo()
        if mo.f3d_energy_applied_unit:
            return
        qty = self._f3d_energy_qty()
        if qty <= 0:
            return
        if mo.product_id.cost_method in ("fifo", "average"):
            unit = round(mo.f3d_energy_cost / qty, 4)
            mo.extra_cost += unit
            mo.f3d_energy_applied_unit = unit
            mo.message_post(
                body=_(
                    "До Extra Unit Cost додано енергію: %(unit)s грн/од. (%(cost)s грн / %(qty)s шт).",
                    unit=fmt_num(unit, 4),
                    cost=fmt_num(mo.f3d_energy_cost, 2),
                    qty=fmt_num(qty, 3),
                )
            )
        else:
            mo.message_post(
                body=_(
                    "Енергію не внесено у вартість: метод «Стандартна ціна» (Q-06). Енергія МО: %(kwh)s кВт·год, "
                    "%(cost)s грн.",
                    kwh=fmt_num(mo.f3d_energy_kwh, 1),
                    cost=fmt_num(mo.f3d_energy_cost, 2),
                )
            )

    def _get_backorder_mo_vals(self):
        res = super()._get_backorder_mo_vals()
        res["extra_cost"] = max(0.0, self.extra_cost - self.sudo().f3d_energy_applied_unit)
        return res

    def action_f3d_energy_recompute(self):
        if not self.env.user.has_group("factory3d_energy.group_f3d_energy_manager"):
            raise AccessError(_("Перерахунок енергії доступний енергетику."))
        total = 0.0
        now = dates.now_utc(self.env)
        for mo in self.filtered(lambda m: not m.f3d_energy_locked):
            days = mo._f3d_energy_days(now)
            if days:
                self.env["f3d.energy.alloc"].sudo()._f3d_alloc_days(days, now=now)
            total += mo.sudo().f3d_energy_kwh
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "success",
                "message": _("Перераховано: %s кВт·год", fmt_num(total, 3)),
                "sticky": False,
            },
        }

    def action_f3d_view_alloc(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Енергія на виробництво"),
            "res_model": "f3d.energy.alloc",
            "view_mode": "list,pivot",
            "domain": [("production_id", "=", self.id)],
        }
