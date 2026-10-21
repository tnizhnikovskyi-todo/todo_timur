"""Розрахунок собівартості замовлення за пов'язаними МО (R-01…R-07 SPEC): план за BOM і маршрутом, факт із журналів.

Усе читається від `sudo()` (права перевіряє точка входу). Нічого не зберігається: кожен виклик рахує заново.
Енергія (`td.energy.alloc`) і журнал станів верстатів (`td.machine.state.log`) — необов'язкові: без модуля стаття
«Енергія» порожня, час верстатів береться з журналу часу робочих операцій.
"""

import logging
import re
from collections import defaultdict
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from odoo import _, api, fields, models

from ..tools import cost

_logger = logging.getLogger(__name__)

PARAM = "td.sale_cost."
DEMO_CLOCK = "td.viewer.demo_clock"  # демо-годинник «Переглядача» (час за Києвом): на демо-базі він і є «зараз»
CLOCK_RE = re.compile(r"^\d{4}-\d\d-\d\d \d\d:\d\d$")
KYIV = ZoneInfo("Europe/Kyiv")
CUT_STATES = ("planned", "released", "running", "done")


class TdSaleCostCalc(models.AbstractModel):
    _name = "td.sale.cost.calc"
    _description = "Собівартість замовлення: розрахунок"

    # --- вхід ---------------------------------------------------------------------------------------
    @api.model
    def _td_thresholds(self):
        """R-06: пороги кольору відхилення, % (`td.sale_cost.warn_pct`, `td.sale_cost.alert_pct`)."""
        icp = self.env["ir.config_parameter"].sudo()

        def get(key, default):
            try:
                return float(icp.get_param(PARAM + key, default))
            except ValueError:
                return default

        return get("warn_pct", cost.WARN_PCT), get("alert_pct", cost.ALERT_PCT)

    @api.model
    def _td_now(self):
        """«Зараз»: демо-годинник `td.viewer.demo_clock` (лише демо-бази; так само в аналітиці вузького місця
        td_machine_connect R-30), інакше реальний час. Відкриті записи журналу рахуються до цього моменту."""
        clock = self.env["ir.config_parameter"].sudo().get_param(DEMO_CLOCK)
        if clock and CLOCK_RE.match(clock):
            try:
                naive = datetime.strptime(clock, "%Y-%m-%d %H:%M")
                return naive.replace(tzinfo=KYIV).astimezone(timezone.utc).replace(tzinfo=None)
            except ValueError:
                _logger.warning("%s невалідний (%r): ігнорується", DEMO_CLOCK, clock)
        return fields.Datetime.now()

    @api.model
    def _td_duration(self, wo, now):
        """Хвилини журналу часу операції — як `mrp.workorder.get_duration`, але відкриті записи рахуються до `now`
        (з перекриттями за типом втрат, як у стандарті)."""
        by_loss = defaultdict(list)
        for t in wo.time_ids:
            start = t.date_start or now
            by_loss[t.loss_id.loss_type].append((start, max(t.date_end or now, start), t))
        return sum(wo._intervals_duration(ivs) for ivs in by_loss.values())

    @api.model
    def _td_calc(self, orders):
        """`{order.id: результат}` для замовлень з МО (решта у словнику відсутня), один прохід даних на пакет."""
        orders = orders.sudo()
        warn, alert = self._td_thresholds()
        tree = self._td_trees(orders)
        mos = self.env["mrp.production"].sudo().browse(sorted({m.id for ms in tree["order_mos"].values() for m in ms}))
        data = self._td_mos_data(mos, tree, warn, alert) if mos else {}
        return {
            o.id: self._td_order(o, [data[m.id] for m in tree["order_mos"][o.id]], warn, alert)
            for o in orders
            if tree["order_mos"][o.id]
        }

    @api.model
    def _td_trees(self, orders):
        """R-01: МО замовлення — перший рівень (`sale_mrp`: `mrp_production_ids`, плюс МО з `origin` = номер
        замовлення) і підпорядковані МО напівфабрикатів (група виробництва або `origin` = номер МО), рекурсивно.
        `{"order_mos": {order.id: [МО в порядку обходу]}, "parent": {mo.id: МО-батько}, "children": {mo.id: МО}}`."""
        MO = self.env["mrp.production"].sudo()
        by_origin = MO.search([("origin", "in", orders.mapped("name")), ("state", "!=", "cancel")])
        roots = {}
        for o in orders:
            extra = by_origin.filtered(lambda m, o=o: m.origin == o.name and not m.production_group_id.parent_ids)
            roots[o.id] = (o.mrp_production_ids.filtered(lambda m: m.state != "cancel") | extra).sorted("id")
        parent, children = {}, defaultdict(lambda: MO)  # підМО — у порядку id, як і корені
        root_ids = {m.id for ms in roots.values() for m in ms}
        frontier = MO.browse(sorted(root_ids))
        while frontier:
            names = {m.name: m for m in frontier}
            found = MO.search([("origin", "in", list(names)), ("state", "!=", "cancel")])
            pairs = [(names[k.origin], k) for k in found]
            pairs += [(m, k) for m in frontier for k in m.production_group_id.child_ids.production_ids]
            new = MO
            for par, kid in pairs:
                if kid.state == "cancel" or kid.id in parent or kid.id in root_ids:
                    continue
                parent[kid.id] = par
                children[par.id] = (children[par.id] | kid).sorted("id")
                new |= kid
            frontier = new
        order_mos = {}
        for o in orders:
            out = []

            def walk(mo, out=out):
                out.append(mo)
                for kid in children[mo.id]:
                    walk(kid)

            for root in roots[o.id]:
                walk(root)
            order_mos[o.id] = out
        return {"order_mos": order_mos, "parent": parent, "children": children}

    # --- дані МО ------------------------------------------------------------------------------------
    @api.model
    def _td_mos_data(self, mos, tree, warn, alert):
        now = self._td_now()
        wos = mos.workorder_ids.filtered(lambda w: w.state != "cancel")
        state_min = self._td_state_minutes(wos, now)
        energy = self._td_energy(mos)
        rates = self._td_energy_rates(wos.workcenter_id)
        scrap = self._td_scrap(mos)
        cuts = self._td_cut_maps(mos)
        out = {}
        for mo in mos:
            mo_wos = wos.filtered(lambda w, mo=mo: w.production_id == mo)
            mach = self._td_machines(mo, mo_wos, state_min, now)
            kids = tree["children"].get(mo.id, mo.browse())
            parts = {
                "machine": mach,
                "energy": self._td_energy_mo(mo, mo_wos, energy, rates, mach["fractions"]),
                "material": self._td_materials(mo, kids.product_id),
                "waste": self._td_waste(mo, scrap, cuts),
            }
            plan = {a: parts[a]["plan"] for a in cost.ARTICLES}
            plan_now = {a: parts[a]["plan_now"] for a in cost.ARTICLES}
            fact = {a: parts[a]["fact"] for a in cost.ARTICLES}
            out[mo.id] = {
                "mo": mo,
                "parent": tree["parent"].get(mo.id),
                "progress": (1.0 if mo.state == "done" else cost.progress(mach["rows"])) or 0.0,
                "plan": plan,
                "plan_now": plan_now,
                "fact": fact,
                "stats": {a: parts[a]["stats"] for a in cost.ARTICLES},
                **self._td_sums(plan, plan_now, fact, warn, alert),
            }
        return out

    @api.model
    def _td_sums(self, plan, plan_now, fact, warn, alert):
        """Підсумки за статтями: план, план на поточний стан, факт, прогноз, відхилення, колір."""
        p, pn, f = (sum(cost.num(d[a]) for a in cost.ARTICLES) for d in (plan, plan_now, fact))
        return {
            "plan_cost": p,
            "plan_now_cost": pn,
            "fact_cost": f,
            "forecast_cost": cost.forecast(f, p, pn),
            "dev_pct": cost.deviation_pct(f, pn),
            "level": cost.level(f, pn, warn, alert),
        }

    @api.model
    def _td_state_minutes(self, wos, now):
        """Хвилини `working`/`setup` із журналу станів верстата за завданнями (відкритий інтервал — до `now`)."""
        if "td.machine.state.log" not in self.env or not wos:
            return {}
        logs = (
            self.env["td.machine.state.log"]
            .sudo()
            .search([("workorder_id", "in", wos.ids), ("state", "in", ("working", "setup"))])
        )
        res = defaultdict(float)
        for log in logs:
            res[log.workorder_id.id] += max(((log.date_end or now) - log.date_start).total_seconds(), 0.0) / 60.0
        return res

    @api.model
    def _td_machines(self, mo, wos, state_min, now):
        """R-02: станки. Факт = робочі хвилини операції × `costs_hour` РЦ; хвилини — з журналу станів верстата,
        якщо він має записи для операції, інакше з журналу часу (`mrp.workorder.duration`).
        План = `duration_expected`."""
        plan = plan_now = fact = 0.0
        rows, fractions = [], {}
        stats = {"state_min": 0.0, "time_min": 0.0, "no_rate": set(), "no_ops": 0 if wos else 1}
        done = mo.state == "done"
        for wo in wos:
            rate = wo.workcenter_id.costs_hour
            exp = wo.duration_expected or 0.0
            dur = self._td_duration(wo, now)
            frac = 1.0 if done else cost.fraction(wo.state, exp, dur)
            rows.append((exp, frac))
            fractions[wo.id] = frac
            plan += exp / 60.0 * rate
            plan_now += exp / 60.0 * rate * frac
            if state_min.get(wo.id):
                minutes = state_min[wo.id]
                stats["state_min"] += minutes
            else:
                minutes = dur
                stats["time_min"] += minutes
            fact += minutes / 60.0 * rate
            if minutes and not rate:
                stats["no_rate"].add(wo.workcenter_id.display_name)
        return {
            "plan": plan if wos else None,
            "plan_now": plan_now if wos else None,
            "fact": fact if wos else None,
            "rows": rows,
            "fractions": fractions,
            "stats": stats,
        }

    @api.model
    def _td_energy_kinds(self):
        """Які рядки `td.energy.alloc` входять у собівартість: прямі завжди; спільні (повітря, аспірація, світло,
        вентиляція) — лише з `td.sale_cost.energy_shared` = 1: пул доби ділиться між завданнями, що йшли в слоті, і на
        розрідженій добі кілька завдань забирають увесь цеховий пул (тисячі ₴ на завдання), тож це накладні."""
        shared = self.env["ir.config_parameter"].sudo().get_param(PARAM + "energy_shared", "0")
        return ("direct", "shared") if str(shared).strip().lower() in ("1", "true", "yes") else ("direct",)

    @api.model
    def _td_energy(self, mos):
        """`{mo.id: {"cost", "kwh", "shared_cost", "shared_kwh"}}` — Σ `td.energy.alloc` за МО (`cost`/`kwh` — лише
        враховані види, див. `_td_energy_kinds`; `shared_*` — спільна енергія, що не входить); `None`, якщо модуля
        енергії немає."""
        if "td.energy.alloc" not in self.env:
            return None
        kinds = self._td_energy_kinds()
        rows = (
            self.env["td.energy.alloc"]
            .sudo()
            ._read_group(
                [("production_id", "in", mos.ids), ("kind", "in", ("direct", "shared"))],
                ["production_id", "kind"],
                ["cost:sum", "kwh:sum"],
            )
        )
        res = {}
        for mo, kind, c, k in rows:
            d = res.setdefault(mo.id, {"cost": 0.0, "kwh": 0.0, "shared_cost": 0.0, "shared_kwh": 0.0})
            if kind in kinds:
                d["cost"] += c
                d["kwh"] += k
            if kind == "shared" and "shared" not in kinds:
                d["shared_cost"] += c
                d["shared_kwh"] += k
        return res

    @api.model
    def _td_energy_rates(self, workcenters):
        """`{wc.id: грн за годину роботи}` з історії розподілу енергії РЦ — база плану енергії. Вартість — врахованих
        видів рядків, час — лише хвилини прямих рядків: спільні рядки того самого завдання повторюють його хвилини,
        тож їхня сума в знаменнику занижувала б ставку в кілька разів."""
        if "td.energy.alloc" not in self.env or not workcenters:
            return {}
        Alloc = self.env["td.energy.alloc"].sudo()
        base = [("workcenter_id", "in", workcenters.ids), ("workorder_id", "!=", False)]
        costs = Alloc._read_group(base + [("kind", "in", self._td_energy_kinds())], ["workcenter_id"], ["cost:sum"])
        minutes = Alloc._read_group(base + [("kind", "=", "direct")], ["workcenter_id"], ["minutes:sum"])
        mins = {wc.id: m for wc, m in minutes}
        return {wc.id: c / mins[wc.id] * 60.0 for wc, c in costs if mins.get(wc.id, 0) > 0 and c > 0}

    @api.model
    def _td_energy_mo(self, mo, wos, energy, rates, fractions):
        """R-03: енергія. Факт — Σ `td.energy.alloc` за МО (нема рядків — «немає даних»); план — плановий час операцій ×
        ₴/год роботи РЦ за історією розподілу (немає історії — плану немає)."""
        if energy is None:
            return {"plan": None, "plan_now": None, "fact": None, "stats": {"module": False}}
        plan = plan_now = None
        for wo in wos:
            rate = rates.get(wo.workcenter_id.id)
            if rate:
                amount = (wo.duration_expected or 0.0) / 60.0 * rate
                plan = cost.num(plan) + amount
                plan_now = cost.num(plan_now) + amount * fractions.get(wo.id, 0.0)
        stats = {"module": True, "kwh": 0.0, "rows": 0, "shared_kwh": 0.0, "shared_cost": 0.0}
        fact = None
        if mo.id in energy:
            row = energy[mo.id]
            fact, stats["kwh"], stats["rows"] = row["cost"], row["kwh"], 1
            stats["shared_kwh"], stats["shared_cost"] = row["shared_kwh"], row["shared_cost"]
        return {"plan": plan, "plan_now": plan_now, "fact": fact, "stats": stats}

    @api.model
    def _td_materials(self, mo, semi_products):
        """R-04: матеріали. План — `product_qty` компонентів × `standard_price`. Факт — виконані рухи за
        `stock.move.value` (немає — кількість × `standard_price`, позначено як оцінка); рух «взято», але не
        виконаний — кількість × `standard_price` (оцінка). Не взяте й зарезервоване у факт не входить.
        Напівфабрикати з підпорядкованих МО пропускаються: їхня вартість — у рядках тих МО."""
        plan = plan_now = fact = 0.0
        keys = ("valued", "est_std", "est_picked", "pending", "semi", "no_price")
        stats = dict.fromkeys(keys, 0)
        moves = mo.move_raw_ids.filtered(lambda m: m.state != "cancel")
        for m in moves:
            if m.product_id in semi_products:
                stats["semi"] += 1
                continue
            product = m.product_id.with_company(mo.company_id)
            price = product.standard_price
            line_plan = m.product_qty * price
            plan += line_plan
            if not price and m.product_qty:
                stats["no_price"] += 1
            qty = m.product_uom._compute_quantity(m.quantity, product.uom_id)
            if m.state == "done":
                plan_now += line_plan
                if "value" in m._fields and m.value:
                    fact += abs(m.value)
                    stats["valued"] += 1
                else:
                    fact += qty * price
                    stats["est_std"] += 1
            elif m.picked and qty:
                plan_now += line_plan
                fact += qty * price
                stats["est_picked"] += 1
            else:
                stats["pending"] += 1
        stats["no_moves"] = 0 if moves else 1
        return {
            "plan": plan if moves else None,
            "plan_now": plan_now if moves else None,
            "fact": fact if moves else None,
            "stats": stats,
        }

    @api.model
    def _td_scrap(self, mos):
        """`{mo.id: [вартість, поз.]}` — виконані списання браку (`stock.scrap`) за МО."""
        scraps = self.env["stock.scrap"].sudo().search([("production_id", "in", mos.ids), ("state", "=", "done")])
        res = defaultdict(lambda: [0.0, 0])
        for s in scraps:
            value = sum(abs(v) for v in s.move_ids.mapped("value")) if "value" in s.move_ids._fields else 0.0
            if not value:
                value = s.scrap_qty * s.product_id.with_company(s.company_id).standard_price
            res[s.production_id.id][0] += value
            res[s.production_id.id][1] += 1
        return res

    @api.model
    def _td_cut_maps(self, mos):
        """`{mo.id: Σ(відхід за планом карт, грн)}` — карти розкроя МО (`td.cut.map`); `None`, якщо модуля немає."""
        if "td.cut.map" not in self.env:
            return None
        res = defaultdict(float)
        maps = self.env["td.cut.map"].sudo().search([("production_id", "in", mos.ids), ("state", "in", CUT_STATES)])
        for cm in maps:
            price = cm.material_product_id.with_company(cm.production_id.company_id).standard_price
            res[cm.production_id.id] += cm.plan_sheets * price * cm.plan_waste_pct / 100.0
        return res

    @api.model
    def _td_waste(self, mo, scrap, cuts):
        """R-05: відходи. Факт — виконані списання браку МО. Відхід розкроя (план карт) — лише довідка в нотатці, бо
        листи вже списані в матеріалах. Ні браку, ні карт — «немає даних» (`fact = None`)."""
        has_scrap = mo.id in scrap
        has_cut = cuts is not None and mo.id in cuts
        return {
            "plan": None,
            "plan_now": None,
            "fact": scrap[mo.id][0] if has_scrap else (0.0 if has_cut else None),
            "stats": {
                "scrap": scrap[mo.id][1] if has_scrap else 0,
                "cut_cost": cuts[mo.id] if has_cut else 0.0,
                "has_cut": has_cut,
            },
        }

    # --- нотатки про джерела даних ---------------------------------------------------------------------
    @api.model
    def _td_notes(self, article, stats, count):
        """Пояснення, звідки цифри й чого бракує: `stats` — підсумок лічильників статті, `count` — кількість МО."""
        n = []
        if article == "machine":
            if stats["no_ops"] >= count:
                return [_("немає даних: у МО немає операцій")]
            n.append(
                _(
                    "час: журнал станів верстата %(s).0f хв, журнал часу %(t).0f хв",
                    s=stats["state_min"],
                    t=stats["time_min"],
                )
            )
            if stats["no_rate"]:
                n.append(_("ставка РЦ 0 ₴/год, вартість занижена: %s", ", ".join(sorted(stats["no_rate"]))))
        elif article == "energy":
            if not stats["module"]:
                return [_("модуль td_energy не встановлено")]
            if not stats["rows"]:
                return [_("немає даних: розподілу td.energy.alloc по МО немає")]
            n.append(_("%.1f кВт·год за розподілом td.energy.alloc", stats["kwh"]))
            if stats["rows"] < count:
                n.append(_("МО без розподілу енергії: %s з %s", count - stats["rows"], count))
            if stats["shared_cost"]:
                n.append(
                    _(
                        "спільна енергія цеху (повітря, аспірація, світло, вентиляція) %(kwh).1f кВт·год ≈ "
                        "%(cost).0f ₴ у собівартість не входить (накладні; td.sale_cost.energy_shared = 1 — включити)",
                        kwh=stats["shared_kwh"],
                        cost=stats["shared_cost"],
                    )
                )
        elif article == "material":
            if stats["no_moves"] >= count:
                return [_("немає даних: у МО немає компонентів")]
            if stats["no_price"]:
                n.append(
                    _("увага: %s поз. без собівартості (standard_price = 0), матеріали занижені", stats["no_price"])
                )
            if stats["valued"]:
                n.append(_("оцінка руху складу (stock.move.value): %s поз.", stats["valued"]))
            if stats["est_std"]:
                n.append(_("оцінка за standard_price (рух без вартості): %s поз.", stats["est_std"]))
            if stats["est_picked"]:
                n.append(_("взято, не виконано — оцінка за standard_price: %s поз.", stats["est_picked"]))
            if stats["pending"]:
                n.append(_("ще не списано: %s поз.", stats["pending"]))
            if stats["semi"]:
                n.append(_("напівфабрикати з підпорядкованих МО: %s поз. (враховано в їхніх рядках)", stats["semi"]))
        elif article == "waste":
            if stats["scrap"]:
                n.append(_("брак: %s списань", stats["scrap"]))
            if stats["has_cut"]:
                n.append(_("відхід розкроя за картами ≈ %.2f ₴ (входить у матеріали)", stats["cut_cost"]))
            if not n:
                n.append(_("немає даних: карт розкроя й браку немає"))
        return n

    # --- замовлення ---------------------------------------------------------------------------------
    @api.model
    def _td_order(self, order, mo_data, warn, alert):
        company = order.company_id
        price = order.currency_id._convert(
            order.amount_untaxed, company.currency_id, company, (order.date_order or fields.Datetime.now()).date()
        )
        articles = {}
        for a in cost.ARTICLES:
            merged = {}
            for d in mo_data:
                for key, val in d["stats"][a].items():
                    merged[key] = (merged.get(key, set()) | val) if isinstance(val, set) else merged.get(key, 0) + val
            if a == "energy":
                merged["module"] = all(d["stats"][a]["module"] for d in mo_data)
            if a == "waste":
                merged["has_cut"] = bool(merged.get("has_cut"))
            articles[a] = {
                "plan": cost.total(d["plan"][a] for d in mo_data),
                "plan_now": cost.total(d["plan_now"][a] for d in mo_data),
                "fact": cost.total(d["fact"][a] for d in mo_data),
                "notes": self._td_notes(a, merged, len(mo_data)),
            }
        plan = {a: articles[a]["plan"] for a in cost.ARTICLES}
        plan_now = {a: articles[a]["plan_now"] for a in cost.ARTICLES}
        fact = {a: articles[a]["fact"] for a in cost.ARTICLES}
        res = {
            "order": order,
            "currency": company.currency_id,
            "price": price,
            "mos": mo_data,
            "articles": articles,
            **self._td_sums(plan, plan_now, fact, warn, alert),
        }
        weight = sum(d["plan_cost"] for d in mo_data)
        res["progress"] = (
            sum(d["progress"] * d["plan_cost"] for d in mo_data) / weight
            if weight
            else sum(d["progress"] for d in mo_data) / len(mo_data)
        )
        for key in ("plan", "plan_now", "fact", "forecast"):
            res["margin_" + key] = price - res[key + "_cost"]
            res["margin_%s_pct" % key] = cost.margin_pct(price, res[key + "_cost"])
        # Замовлення в роботі: маржа за фактом «поки що» завищена (витрати лише до зараз), тож головна — прогнозна
        # (ціна − факт − решта плану); виконане замовлення має повні витрати — головна маржа факту.
        res["is_done"] = all(d["mo"].state == "done" for d in mo_data)
        res["margin_main"] = "fact" if res["is_done"] else "forecast"
        return res
