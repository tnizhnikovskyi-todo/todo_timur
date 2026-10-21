"""Двигун живого виробництва: параметри, «зараз», планувальник доби (LP-02), запуск/зупинка (LP-06).

Диспетчер (LP-03/04) — у `td_live_dispatch.py`, підготовка компанії (LP-07) — у `td_live_prepare.py`: усі три
розширюють одну абстрактну модель `td.live.engine`. Розрахунки — у `tools/` (чисті функції), тут лише ORM.
"""

import logging
from collections import defaultdict
from datetime import datetime, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..tools import clock, planner, pricing

_logger = logging.getLogger(__name__)

PREFIX = "td.live_production."
DEMO_CLOCK = "td.viewer.demo_clock"
CLOCK_BACKUP = PREFIX + "demo_clock_backup"
NOW_KEY = "td_live_now"  # ключ контексту: «зараз» (naive UTC `datetime` або рядок) для тестів і «віртуального» часу
LINES_RANGE = (2, 3)  # рядків (МО) у замовленні
OVERLOAD = 1.5  # гарячі верстати вважаються «повними» на 150 % зміни (див. `planner.plan_orders`)
CRON_TICK = "td_live_production.cron_td_live_tick"
CRON_NIGHT = "td_live_production.cron_td_live_nightly"
DOWNTIME_LOSS = {  # ключ причини планувальника → (XML-id причини втрат, назва, якщо причини немає)
    "setup": ("mrp.block_reason2", "Налагодження"),
    "tool": ("factory3d.loss_tool", "Заміна інструменту"),
    "material": ("mrp.block_reason0", "Очікування матеріалу"),
    "break": ("factory3d.loss_break", "Перерва"),
    "fault": ("mrp.block_reason1", "Поломка"),
}


class TdLiveEngine(models.AbstractModel):
    _name = "td.live.engine"
    _description = "Живе виробництво: планувальник і диспетчер"

    # --- параметри, час --------------------------------------------------------------------------------
    @api.model
    def _td_params(self):
        icp = self.env["ir.config_parameter"].sudo()

        def get(key, default, cast=float):
            raw = icp.get_param(PREFIX + key)
            try:
                return cast(raw) if raw not in (None, False, "") else default
            except (TypeError, ValueError):
                return default

        shift = (get("shift_start", 7.0), get("shift_end", 15.5))
        if not 0 <= shift[0] < shift[1] <= 24:
            shift = (7.0, 15.5)
        return {
            "enabled": icp.get_param(PREFIX + "enabled") == "True",
            "orders": max(0, get("orders_per_day", 8, int)),
            "shift": shift,
            "workdays": icp.get_param(PREFIX + "workdays") or "0123456",
            "hot_section": icp.get_param(PREFIX + "hot_section") or "",
            "hot_factor": max(1.0, get("hot_factor", 2.5)),
            "downtime_share": min(max(get("downtime_pct", 6.0), 0.0), 60.0) / 100.0,
        }

    @api.model
    def _td_now(self):
        """«Зараз» (naive UTC): `context[td_live_now]`, інакше реальний час. Демо-годинник не враховується (LP-06)."""
        forced = self.env.context.get(NOW_KEY)
        if forced:
            forced = fields.Datetime.to_datetime(forced)
            return forced.replace(tzinfo=None)
        return fields.Datetime.now()

    @api.model
    def _td_today(self, now=None):
        return clock.local_date(now or self._td_now())

    # --- шаблони з бази ---------------------------------------------------------------------------------
    @api.model
    def _td_templates(self):
        """Шаблони дня з бази: клієнти підтверджених замовлень і вироби зі специфікаціями-маршрутами."""
        env = self.sudo().env
        company = env.company
        Order = env["sale.order"]
        orders = Order.search([("state", "=", "sale"), ("company_id", "=", company.id)], order="id")
        customers = sorted(set(orders.partner_id.ids))
        boms = env["mrp.bom"].search(
            [
                ("type", "=", "normal"),
                ("operation_ids", "!=", False),
                ("product_tmpl_id.sale_ok", "=", True),
                ("product_tmpl_id.list_price", ">", 0),
                ("company_id", "in", [False, company.id]),
            ],
            order="id",
        )
        hist = defaultdict(set)
        for line in env["sale.order.line"].search([("order_id", "in", orders.ids), ("product_id", "!=", False)]):
            if line.product_uom_qty > 0:
                hist[line.product_id.id].add(int(line.product_uom_qty))
        products = {}
        for bom in boms:
            product = bom.product_id or bom.product_tmpl_id.product_variant_id
            if not product:
                continue
            ops = [
                {
                    "wc": op.workcenter_id.id,
                    "setup": op.workcenter_id.time_start + op.workcenter_id.time_stop,
                    "cycle": op.time_cycle,
                }
                for op in bom.operation_ids.sorted(lambda o: (o.sequence, o.id))
            ]
            item = products.setdefault(
                product.id, {"id": product.id, "qtys": sorted(hist.get(product.id, ())), "variants": []}
            )
            item["variants"].append({"bom_id": bom.id, "ops": ops})
        return {"customers": customers, "products": list(products.values())}

    @api.model
    def _td_section_of(self, workcenter):
        """Ділянка РЦ — перша мітка (`tag_ids`): так її бачить аналітика «Вузьке місце» td_machine_connect."""
        tag = workcenter.tag_ids.sorted("id")[:1]
        return tag.name if tag else workcenter.name

    @api.model
    def _td_hot_workcenters(self, wc_ids, section):
        if not section:
            return set()
        wcs = self.sudo().env["mrp.workcenter"].browse(list(wc_ids))
        return {wc.id for wc in wcs if self._td_section_of(wc) == section}

    # --- ціни -------------------------------------------------------------------------------------------
    @api.model
    def _td_bom_unit_cost(self, bom):
        """Планова собівартість одиниці виробу: компоненти × `standard_price` + хвилини операцій × ставка РЦ."""
        company = self.env.company
        qty = bom.product_qty or 1.0
        cost = 0.0
        for line in bom.bom_line_ids:
            price = line.product_id.with_company(company).standard_price
            cost += line.product_qty / qty * line.product_uom_id._compute_quantity(1.0, line.product_id.uom_id) * price
        for op in bom.operation_ids:
            cost += op.time_cycle / 60.0 * op.workcenter_id.costs_hour / qty
        return cost

    # --- генерація доби (LP-02) -------------------------------------------------------------------------
    @api.model
    def td_generate_today(self):
        """Перший запуск: план на поточну добу й одразу доганяння: що за планом мало закінчитись — закрито."""
        now = self._td_now()
        day = self.td_generate_day(self._td_today(now))
        res = self.td_dispatch(now=now, force=True)
        return _(
            "%(day)s: замовлень %(so)s, МО %(mo)s. Диспетчер: стартувало нарядів %(started)s, завершено %(finished)s, "
            "закрито МО %(mos)s, відвантажено %(ship)s. %(note)s",
            day=day.date,
            so=day.order_count,
            mo=day.production_count,
            started=res["started"],
            finished=res["finished"],
            mos=res["closed"],
            ship=res["shipped"],
            note=day.note or "",
        )

    @api.model
    def td_generate_day(self, day=None):
        """План доби `day` (київська дата; за замовчуванням сьогодні): замовлення, МО, розклад нарядів, простої.

        Ідемпотентно: для доби, що вже має план, повертає його без змін.
        """
        self = self.sudo()
        env = self.env
        company = env.company
        now = self._td_now()
        day = day or self._td_today(now)
        Day = env["td.live.day"]
        existing = Day.search([("date", "=", day), ("company_id", "=", company.id)], limit=1)
        if existing:
            return existing
        params = self._td_params()
        templates = self._td_templates()
        if not templates["customers"] or not templates["products"]:
            raise UserError(
                _(
                    "Немає шаблонів: потрібні підтверджені замовлення клієнтів і вироби зі специфікаціями, що мають "
                    "операції (маршрут). Завантажте демо-набір factory3d."
                )
            )
        shift = params["shift"]
        shift_min = clock.shift_minutes(shift)
        wc_ids = {op["wc"] for p in templates["products"] for v in p["variants"] for op in v["ops"]}
        hot = self._td_hot_workcenters(wc_ids, params["hot_section"])
        seed = int(day.strftime("%Y%m%d"))
        plan = planner.plan_orders(
            templates,
            params["orders"],
            seed,
            shift_min,
            hot,
            OVERLOAD,
            params["hot_factor"] if hot else 1.0,
            LINES_RANGE,
        )
        release = planner.shift_release(day, shift)
        rec = Day.create({"date": day, "company_id": company.id})
        mos_for_plan = env["mrp.production"]
        revenue = cost_total = 0.0
        for n, order in enumerate(plan["orders"]):
            so, mos, rev, cost = self._td_create_order(rec, order, n, release)
            revenue += rev
            cost_total += cost
            mos_for_plan |= mos
        sched = self._td_schedule(mos_for_plan, release, shift, params["workdays"], hot, params["hot_factor"])
        rec.downtime_ids = [(0, 0, vals) for vals in self._td_plan_downtimes(sched, params["downtime_share"], seed)]
        hot_load = 0.0
        if hot:
            machines = len(hot)
            minutes = sum(m for wc, m in sched["load"].items() if wc in hot)
            hot_load = minutes / (machines * shift_min) * 100.0
        rec.write(
            {
                "revenue": revenue,
                "cost_plan": cost_total,
                "margin_plan_pct": pricing.margin_pct(revenue, cost_total),
                "hot_section": params["hot_section"] if hot else False,
                "hot_load_pct": hot_load,
                "spill_min": sched["spill"],
                "note": _(
                    "План: %(n)s замовлень, %(m)s МО, %(d)s простоїв.",
                    n=len(plan["orders"]),
                    m=len(mos_for_plan),
                    d=len(rec.downtime_ids),
                ),
            }
        )
        return rec

    @api.model
    def _td_create_order(self, day_rec, order, n, release):
        """Замовлення продажу `order` із МО по рядках. Повертає `(замовлення, МО, виручка, собівартість)`."""
        env = self.env
        Bom = env["mrp.bom"]
        lines, costs = [], []
        for i, ln in enumerate(order["lines"]):
            bom = Bom.browse(ln["bom_id"])
            product = env["product.product"].browse(ln["product_id"])
            unit_cost = self._td_bom_unit_cost(bom)
            price = pricing.order_price(product.lst_price, unit_cost, "%s:%s:%s" % (day_rec.date, n, i))
            lines.append((0, 0, {"product_id": product.id, "product_uom_qty": ln["qty"], "price_unit": price}))
            costs.append((ln["qty"] * unit_cost, ln["qty"] * price))
        so = env["sale.order"].create(
            {
                "partner_id": order["partner_id"],
                "date_order": release - timedelta(hours=2 + n % 4),
                "commitment_date": release + timedelta(days=1),
                "order_line": lines,
                "td_live_day_id": day_rec.id,
            }
        )
        so.action_confirm()
        mos = env["mrp.production"]
        for ln in order["lines"]:
            bom = Bom.browse(ln["bom_id"])
            product = bom.product_id or bom.product_tmpl_id.product_variant_id
            mo = env["mrp.production"].create(
                {
                    "product_id": product.id,
                    "product_qty": ln["qty"],
                    "product_uom_id": product.uom_id.id,
                    "bom_id": bom.id,
                    "origin": so.name,
                    "date_start": release,
                    "td_live_day_id": day_rec.id,
                }
            )
            mo.action_confirm()
            mos |= mo
        return so, mos, sum(c[1] for c in costs), sum(c[0] for c in costs)

    @api.model
    def _td_schedule(self, mos, release, shift, workdays, hot, hot_factor):
        """Розклад нарядів МО дня: хвилини (ділянка гарячих верстатів × складність), кінцева потужність РЦ."""
        env = self.env
        wc_free = self._td_wc_free(mos)
        ops_wc, items = {}, []
        for mo in mos:
            ops = []
            for wo in mo.workorder_ids.filtered(lambda w: w.state != "cancel").sorted("id"):
                minutes = wo.duration_expected or 1.0
                if wo.workcenter_id.id in hot:
                    minutes = round(minutes * hot_factor, 1)
                    wo.duration_expected = minutes
                ops.append({"id": wo.id, "wc": wo.workcenter_id.id, "minutes": minutes})
                ops_wc[wo.id] = wo.workcenter_id.id
            items.append({"id": mo.id, "release": release, "ops": ops})
        plan = planner.schedule(items, shift, workdays, wc_free)
        Wo = env["mrp.workorder"]
        for wo_id, (start, end) in plan.items():
            self._td_wo_dates(Wo.browse(wo_id), start, end)
        for mo in mos:
            starts = [plan[w.id][0] for w in mo.workorder_ids if w.id in plan]
            ends = [plan[w.id][1] for w in mo.workorder_ids if w.id in plan]
            if starts:
                mo.with_context(force_date=True).write({"date_start": min(starts), "date_finished": max(ends)})
        day_end = clock.shift_window(clock.local_date(release), shift)[1]
        return {
            "plan": plan,
            "ops_wc": ops_wc,
            "load": planner.utilisation(plan, ops_wc, 1.0),
            "spill": planner.spill_minutes(plan, day_end),
        }

    @api.model
    def _td_wc_free(self, new_mos):
        """Коли верстати вільні від попереднього завантаження: максимум планового кінця незавершених нарядів."""
        Wo = self.env["mrp.workorder"]
        open_wos = Wo.search(
            [
                ("state", "in", ("blocked", "ready", "progress")),
                ("production_id.td_live_day_id", "!=", False),
                ("production_id", "not in", new_mos.ids),
            ]
        )
        free = {}
        for wo in open_wos:
            if wo.date_finished:
                free[wo.workcenter_id.id] = max(free.get(wo.workcenter_id.id, wo.date_finished), wo.date_finished)
        return free

    @api.model
    def _td_plan_downtimes(self, sched, share, seed):
        """Значення `td.live.downtime` для доби: простої між нарядами верстатів із підключенням (`td.machine`)."""
        env = self.env
        by_wc = defaultdict(list)
        for op_id, (start, end) in sched["plan"].items():
            by_wc[sched["ops_wc"][op_id]].append((start, end))
        with_machine = set(env["td.machine"].search([("workcenter_id", "in", list(by_wc))]).workcenter_id.ids)
        wc_ops = {wc: ops for wc, ops in by_wc.items() if wc in with_machine}
        res = []
        for item in planner.plan_downtimes(wc_ops, share, seed):
            loss = self._td_loss(item["reason"])
            res.append(
                {
                    "workcenter_id": item["wc"],
                    "kind": item["kind"],
                    "reason": item["reason"],
                    "loss_id": loss.id,
                    "plan_start": item["start"],
                    "minutes": item["minutes"],
                }
            )
        return res

    @api.model
    def _td_loss(self, reason):
        """Причина втрат за ключем планувальника: за XML-id, інакше за назвою, інакше створюється (доступність)."""
        xmlid, name = DOWNTIME_LOSS[reason]
        loss = self.env.ref(xmlid, raise_if_not_found=False)
        if loss:
            return loss
        Loss = self.env["mrp.workcenter.productivity.loss"].sudo()
        loss = Loss.search([("name", "=", name)], limit=1)
        if loss:
            return loss
        return Loss.create({"name": name, "loss_id": self.env.ref("mrp.category_availability").id, "manual": True})

    # --- запуск / зупинка (LP-06) -----------------------------------------------------------------------
    @api.model
    def _td_crons(self):
        return [self.env.ref(x, raise_if_not_found=False) for x in (CRON_TICK, CRON_NIGHT)]

    @api.model
    def td_start(self):
        """«Запустити живе виробництво»: вимикач, обидва крони, демо-годинник вимкнено (реальний «зараз»)."""
        env = self.sudo().env
        icp = env["ir.config_parameter"]
        icp.set_param(PREFIX + "enabled", "True")
        clock_value = icp.get_param(DEMO_CLOCK)
        note = ""
        if clock_value:
            icp.set_param(CLOCK_BACKUP, clock_value)
            icp.set_param(DEMO_CLOCK, False)
            note = _(" Демо-годинник %s вимкнено.", clock_value)
        for cron in self._td_crons():
            if cron:
                cron.sudo().active = True
        self._td_schedule_night()
        return _("Живе виробництво запущено: диспетчер щохвилини, план на завтра о 02:00 (Київ).%s", note)

    @api.model
    def td_stop(self):
        env = self.sudo().env
        icp = env["ir.config_parameter"]
        icp.set_param(PREFIX + "enabled", "False")
        for cron in self._td_crons():
            if cron:
                cron.sudo().active = False
        backup = icp.get_param(CLOCK_BACKUP)
        note = ""
        if backup:
            icp.set_param(DEMO_CLOCK, backup)
            icp.set_param(CLOCK_BACKUP, False)
            note = _(" Демо-годинник повернуто: %s.", backup)
        return _("Живе виробництво зупинено: крони вимкнено.%s", note)

    @api.model
    def _td_schedule_night(self):
        """Наступний запуск нічного крона — найближчі 02:00 за Києвом (інтервал в UTC зсунувся б із літнім часом)."""
        cron = self.env.ref(CRON_NIGHT, raise_if_not_found=False)
        if not cron:
            return
        now = clock.to_local(fields.Datetime.now())
        target = datetime.combine(now.date(), datetime.min.time(), tzinfo=clock.KYIV).replace(hour=2)
        if target <= now:
            target = datetime.combine(now.date() + timedelta(days=1), datetime.min.time(), tzinfo=clock.KYIV).replace(
                hour=2
            )
        cron.sudo().nextcall = clock.to_utc(target)

    @api.model
    def _cron_td_live_nightly(self):
        """Крон 02:00: план на завтра (і на сьогодні, якщо стенд стояв), потім наступний запуск о 02:00."""
        params = self._td_params()
        try:
            if params["enabled"]:
                today = self._td_today()
                self.td_generate_day(today)
                self.td_generate_day(today + timedelta(days=1))
        finally:
            self._td_schedule_night()

    @api.model
    def _cron_td_live_tick(self):
        """Крон щохвилини: такт диспетчера."""
        if self._td_params()["enabled"]:
            self.td_dispatch()
