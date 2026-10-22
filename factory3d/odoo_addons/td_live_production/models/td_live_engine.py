"""Двигун живого виробництва: параметри, «зараз», планувальник доби (LP-02), запуск/зупинка (LP-06).

Диспетчер (LP-03/04) — у `td_live_dispatch.py`, підготовка компанії (LP-07) — у `td_live_prepare.py`: усі три
розширюють одну абстрактну модель `td.live.engine`. Розрахунки — у `tools/` (чисті функції), тут лише ORM.
"""

import logging
from collections import defaultdict
from datetime import datetime, timedelta

from odoo import _, api, fields, models

from ..tools import clock, planner, pricing

_logger = logging.getLogger(__name__)

PREFIX = "td.live_production."
DEMO_CLOCK = "td.viewer.demo_clock"
CLOCK_BACKUP = PREFIX + "demo_clock_backup"
NOW_KEY = "td_live_now"  # ключ контексту: «зараз» (naive UTC `datetime` або рядок) для тестів і «віртуального» часу
HOT_DEFAULT = "Присадка"
BACKLOG_FREE_DAYS = 1.5  # доба-черга на верстатах, до якої замовлень не зменшуємо
BACKLOG_SPAN_DAYS = 3.0  # на скільки діб понад це кількість замовлень падає до чверті
TICK_BUDGET_S = 40.0  # секунд на такт: ліміт крона на сервері ~120 с, подія закриття МО — кілька секунд
TICK_EVENTS = 150  # подій на такт крона: довга пауза доганяється за кілька тактів
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
    "no_task": ("td_live_production.loss_no_task", "Немає завдання"),
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
            "hot_section": self._td_hot_name(icp.get_param(PREFIX + "hot_section")),
            "hot_factor": max(1.0, get("hot_factor", 3.5)),
            "downtime_share": min(max(get("downtime_pct", 6.0), 0.0), 60.0) / 100.0,
        }

    @api.model
    def _td_hot_name(self, raw):
        """Перевантажена ділянка: порожньо — «Присадка» за замовчуванням, «-» — вимкнено."""
        raw = (raw or "").strip()
        return "" if raw == "-" else (raw or HOT_DEFAULT)

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
    def _td_line_cost(self, bom, qty, hot=(), factor=1.0):
        """Планова собівартість `qty` одиниць виробу: компоненти × `standard_price` + тривалість операцій
        (налагодження РЦ + штуки × хвилини на штуку, для гарячих РЦ × `factor`) × ставка РЦ — як plan у td_sale_cost."""
        company = self.env.company
        base = bom.product_qty or 1.0
        cost = 0.0
        for line in bom.bom_line_ids:
            price = line.product_id.with_company(company).standard_price
            per_unit = line.product_qty / base * line.product_uom_id._compute_quantity(1.0, line.product_id.uom_id)
            cost += qty * per_unit * price
        for op in bom.operation_ids:
            wc = op.workcenter_id
            minutes = (wc.time_start + wc.time_stop + qty * op.time_cycle) * (factor if wc.id in hot else 1.0)
            cost += minutes / 60.0 * wc.costs_hour
        return cost

    # --- генерація доби (LP-02) -------------------------------------------------------------------------
    @api.model
    def _td_throttle(self, orders, release):
        """Запобіжник: якщо верстати вже завантажені на понад 1,5 доби вперед, замовлень на добу менше (до чверті).

        Інакше перевантажена ділянка накопичувала б чергу без кінця. Повертає `(замовлень, доби черги)`.
        """
        free = self._td_wc_free(self.env["mrp.production"])
        backlog = max(((t - release).total_seconds() / 86400.0 for t in free.values()), default=0.0)
        if orders <= 1 or backlog <= BACKLOG_FREE_DAYS:
            return orders, backlog
        share = max(0.25, 1.0 - (backlog - BACKLOG_FREE_DAYS) / BACKLOG_SPAN_DAYS * 0.75)
        return max(1, int(round(orders * share))), backlog

    @api.model
    def _td_create_order(self, day_rec, order, n, release, hot=(), hot_factor=1.0):
        """Замовлення продажу `order` із МО по рядках. Повертає `(замовлення, МО, виручка, собівартість)`."""
        env = self.env
        Bom = env["mrp.bom"]
        lines, costs = [], []
        for i, ln in enumerate(order["lines"]):
            bom = Bom.browse(ln["bom_id"])
            product = env["product.product"].browse(ln["product_id"])
            unit_cost = self._td_line_cost(bom, ln["qty"], hot, hot_factor) / ln["qty"]
            price = pricing.order_price(product.lst_price, unit_cost, "%s:%s:%s" % (day_rec.date, n, i))
            lines.append((0, 0, {"product_id": product.id, "product_uom_qty": ln["qty"], "price_unit": price}))
            costs.append((ln["qty"] * unit_cost, ln["qty"] * price))
        vals = {
            "partner_id": order["partner_id"],
            "date_order": release - timedelta(hours=2 + n % 4),
            "commitment_date": release + timedelta(days=1),
            "order_line": lines,
            "td_live_day_id": day_rec.id,
        }
        pricelist = self._td_company_pricelist(env.company)
        if pricelist:  # прайс у валюті компанії (₴), а не USD-прайс партнера за замовчуванням
            vals["pricelist_id"] = pricelist.id
        so = env["sale.order"].create(vals)
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
            self._td_cover_mo(mo, release)  # компоненти доступні одразу, а не лише при закритті МО
            mos |= mo
        return so, mos, sum(c[1] for c in costs), sum(c[0] for c in costs)

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
        """«Запустити живе виробництво». Є готовий план на сьогодні — вмикає одразу; немає — ставить у фон «догнати
        минуле» (якщо є старі відкриті МО) і генерацію доби, а запуск (вимикач, крони, демо-годинник) відбувається
        сам після їх завершення: без плану диспетчеру нічого вести, а застиглі МО минулих діб показувалися б наживо."""
        env = self.sudo().env
        today = self._td_today()
        ready = env["td.live.day"].search_count(
            [("date", "=", today), ("company_id", "=", env.company.id), ("generated", "=", True)]
        )
        if ready:
            return self.td_activate()
        Job = env["td.live.job"]
        steps = []
        today_start = clock.shift_window(today, (0.0, 24.0))[0]
        past, _skipped = self._td_catch_up_candidates(today_start)
        if past:
            Job.td_enqueue("catch_up")
            steps.append(_("догнати минуле (%s МО)", len(past)))
        Job.td_enqueue("generate_day", day=today, then_start=True)
        steps.append(_("згенерувати план на %s", today))
        return _(
            "Плану на сьогодні ще немає. У фоні: %s. Живе виробництво запуститься саме після їх завершення; прогрес у "
            "блоці «Фонові задачі» цього екрана. Диспетчер і демо-годинник поки не чіпаю.",
            " → ".join(steps),
        )

    @api.model
    def td_activate(self):
        """Власне запуск: вимикач, обидва крони, демо-годинник вимкнено (реальний «зараз»)."""
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
        env["td.live.job"].search([("state", "in", ("queued", "running")), ("then_start", "=", True)]).write(
            {"then_start": False}
        )
        backup = icp.get_param(CLOCK_BACKUP)
        note = ""
        if backup:
            icp.set_param(DEMO_CLOCK, backup)
            icp.set_param(CLOCK_BACKUP, False)
            note = _(" Демо-годинник повернуто: %s.", backup)
        return _("Живе виробництво зупинено: крони вимкнено.%s", note)

    @api.model
    def td_queue_catch_up(self):
        """Кнопка «Догнати минуле»: лише ставить задачу у фон."""
        job, status = self.env["td.live.job"].td_enqueue("catch_up")
        if status == "active":
            return _("Догнати минуле вже виконується у фоні: %s", job.progress_text)
        return _("Догнати минуле запущено у фоні. Прогрес і підсумок — у блоці «Фонові задачі» цього екрана.")

    @api.model
    def td_queue_generate(self, offset=0):
        """Кнопки «Згенерувати сьогодні» (`offset = 0`) і «Згенерувати завтра» (`1`): лише ставлять задачу у фон."""
        day = self._td_today() + timedelta(days=offset)
        job, status = self.env["td.live.job"].td_enqueue("generate_day", day=day)
        if status == "exists":
            return _("План на %s вже є.", day)
        if status == "active":
            return _("Генерація доби %(day)s вже виконується у фоні: %(progress)s", day=day, progress=job.progress_text)
        return _("Генерацію доби %s запущено у фоні. Прогрес і підсумок — у блоці «Фонові задачі» цього екрана.", day)

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
        """Крон 02:00: ставить у фон генерацію доби на сьогодні (якщо стенд стояв) і на завтра, переставляє себе."""
        try:
            if self._td_params()["enabled"]:
                today = self._td_today()
                Job = self.env["td.live.job"]
                Job.td_enqueue("generate_day", day=today)
                Job.td_enqueue("generate_day", day=today + timedelta(days=1))
        finally:
            self._td_schedule_night()

    @api.model
    def _cron_td_live_tick(self):
        """Крон щохвилини: такт диспетчера в межах часу й кількості подій."""
        if self._td_params()["enabled"]:
            self.td_dispatch(limit=TICK_EVENTS, budget_s=TICK_BUDGET_S)
