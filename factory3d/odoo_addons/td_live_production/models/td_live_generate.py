"""Генерація доби частинами (LP-02): план → замовлення → розклад → запис дат → завершення.

Кожен крок — окрема коротка транзакція, тож фонова задача (`td.live.job`) вкладається в ліміт крона навіть на повільному
сервері. Стан кроку лежить у `td.live.day` (`gen_phase`, `gen_done`, `plan_json`) і переживає обрив: наступний виклик
продовжує з того самого місця. Диспетчер не чіпає МО доби, поки `generated = False`.
"""

import json
from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..tools import clock, planner, pricing
from .td_live_engine import LINES_RANGE, OVERLOAD

APPLY_CHUNK = 25  # нарядів за крок запису дат (кожен запис створює слот календаря РЦ)


def _iso(value):
    return fields.Datetime.to_string(value)


class TdLiveEngine(models.AbstractModel):
    _inherit = "td.live.engine"

    @api.model
    def td_generate_day(self, day=None):
        """План доби `day` повністю й синхронно (тести, консоль). Ідемпотентно: готову добу повертає без змін.

        Кнопки налаштувань викликають цю ж роботу частинами у фоні (`td.live.job`, `kind = generate_day`).
        """
        rec = self._td_gen_plan(day)
        while not rec.generated:
            self._td_gen_step(rec)
        return rec

    @api.model
    def _td_gen_plan(self, day=None):
        """Крок 1: розрахунок складу замовлень і створення доби (`generated = False`). Наявну добу повертає як є."""
        self = self.sudo()
        env = self.env
        company = env.company
        day = day or self._td_today()
        existing = env["td.live.day"].search([("date", "=", day), ("company_id", "=", company.id)], limit=1)
        if existing:
            return existing
        fixed = (
            self.td_sequences_ahead()
        )  # демо-імена попереду послідовностей: без цього «Референс має бути унікальним»
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
        wc_ids = {op["wc"] for p in templates["products"] for v in p["variants"] for op in v["ops"]}
        hot = self._td_hot_workcenters(wc_ids, params["hot_section"])
        factor = params["hot_factor"] if hot else 1.0
        release = planner.shift_release(day, shift)
        orders_n, backlog = self._td_throttle(params["orders"], release)
        plan = planner.plan_orders(
            templates,
            orders_n,
            int(day.strftime("%Y%m%d")),
            clock.shift_minutes(shift),
            hot,
            OVERLOAD,
            factor,
            LINES_RANGE,
        )
        data = {
            "orders": plan["orders"],
            "hot": sorted(hot),
            "hot_factor": factor,
            "hot_section": params["hot_section"] if hot else False,
            "release": _iso(release),
            "shift": list(shift),
            "workdays": params["workdays"],
            "share": params["downtime_share"],
            "seed": int(day.strftime("%Y%m%d")),
            "cfg_orders": params["orders"],
            "backlog": backlog,
            "fixed": fixed,
        }
        return env["td.live.day"].create(
            {
                "date": day,
                "company_id": company.id,
                "generated": False,
                "gen_phase": "orders" if plan["orders"] else "schedule",
                "gen_done": 0,
                "plan_json": json.dumps(data, ensure_ascii=False),
            }
        )

    @api.model
    def _td_gen_total(self, rec):
        """Скільки одиниць роботи у поточній фазі (для прогресу)."""
        data = json.loads(rec.plan_json or "{}")
        if rec.gen_phase == "orders":
            return len(data.get("orders", []))
        if rec.gen_phase == "apply":
            return len(data.get("sched", []))
        return 1

    @api.model
    def _td_gen_step(self, rec):
        """Один крок генерації доби. Повертає `(фаза після кроку, зроблено, всього)`; `generated` у кінці."""
        self = self.sudo()
        data = json.loads(rec.plan_json)
        phase = rec.gen_phase
        if phase == "orders":
            self._td_gen_order(rec, data)
        elif phase == "schedule":
            self._td_gen_schedule(rec, data)
        elif phase == "apply":
            self._td_gen_apply(rec, data)
        elif phase == "finalize":
            self._td_gen_finalize(rec, data)
        return rec.gen_phase, rec.gen_done, self._td_gen_total(rec)

    @api.model
    def _td_gen_order(self, rec, data):
        i = rec.gen_done
        release = fields.Datetime.to_datetime(data["release"])
        _so, _mos, rev, cost = self._td_create_order(
            rec, data["orders"][i], i, release, set(data["hot"]), data["hot_factor"]
        )
        vals = {"revenue": rec.revenue + rev, "cost_plan": rec.cost_plan + cost, "gen_done": i + 1}
        if i + 1 >= len(data["orders"]):
            vals.update(gen_phase="schedule", gen_done=0)
        rec.write(vals)

    @api.model
    def _td_gen_schedule(self, rec, data):
        """Чистий розрахунок розкладу (без запису): наряди МО дня, кінцева потужність РЦ, простої."""
        hot, factor = set(data["hot"]), data["hot_factor"]
        release = fields.Datetime.to_datetime(data["release"])
        shift = tuple(data["shift"])
        mos = rec.production_ids.sorted("id")
        wc_free = self._td_wc_free(mos)
        ops_wc, items, minutes_of = {}, [], {}
        for mo in mos:
            ops = []
            for wo in mo.workorder_ids.filtered(lambda w: w.state != "cancel").sorted("id"):
                base = wo.duration_expected or 1.0
                minutes = round(base * factor, 1) if wo.workcenter_id.id in hot else base
                ops.append({"id": wo.id, "wc": wo.workcenter_id.id, "minutes": minutes})
                ops_wc[wo.id] = wo.workcenter_id.id
                minutes_of[wo.id] = (minutes, base)
            items.append({"id": mo.id, "release": release, "ops": ops})
        plan = planner.schedule(items, shift, data["workdays"], wc_free)
        day_end = clock.shift_window(clock.local_date(release), shift)[1]
        downtimes = self._td_plan_downtimes({"plan": plan, "ops_wc": ops_wc}, data["share"], data["seed"])
        for item in downtimes:
            item["plan_start"] = _iso(item["plan_start"])
        data.update(
            {
                "sched": [
                    [wo_id, _iso(s), _iso(e), minutes_of[wo_id][0], minutes_of[wo_id][1]]
                    for wo_id, (s, e) in plan.items()
                ],
                "load": planner.utilisation(plan, ops_wc, 1.0),
                "spill": planner.spill_minutes(plan, day_end),
                "downtimes": downtimes,
                "mo_count": len(mos),
            }
        )
        rec.write({"plan_json": json.dumps(data, ensure_ascii=False), "gen_phase": "apply", "gen_done": 0})

    @api.model
    def _td_gen_apply(self, rec, data):
        """Запис дат нарядів порціями; тривалість гарячих нарядів — у `duration_expected`, видима всюди."""
        Wo = self.env["mrp.workorder"]
        start = rec.gen_done
        chunk = data["sched"][start : start + APPLY_CHUNK]
        for wo_id, s, e, minutes, base in chunk:
            wo = Wo.browse(wo_id)
            if minutes != base:
                wo.duration_expected = minutes
            self._td_wo_dates(wo, fields.Datetime.to_datetime(s), fields.Datetime.to_datetime(e))
        done = start + len(chunk)
        if done >= len(data["sched"]):
            rec.write({"gen_phase": "finalize", "gen_done": 0})
        else:
            rec.write({"gen_done": done})

    @api.model
    def _td_gen_finalize(self, rec, data):
        """Дати МО, простої, підсумки доби; `generated = True`."""
        shift = tuple(data["shift"])
        window = {w[0]: (fields.Datetime.to_datetime(w[1]), fields.Datetime.to_datetime(w[2])) for w in data["sched"]}
        for mo in rec.production_ids:
            spans = [window[w.id] for w in mo.workorder_ids if w.id in window]
            if spans:
                mo.with_context(force_date=True).write(
                    {"date_start": min(s for s, _e in spans), "date_finished": max(e for _s, e in spans)}
                )
        downtimes = [dict(d, plan_start=fields.Datetime.to_datetime(d["plan_start"])) for d in data["downtimes"]]
        rec.downtime_ids = [(0, 0, vals) for vals in downtimes]
        hot = set(data["hot"])
        hot_load = 0.0
        if hot:
            minutes = sum(m for wc, m in data["load"].items() if int(wc) in hot)
            hot_load = minutes / (len(hot) * clock.shift_minutes(shift)) * 100.0
        orders_n = len(data["orders"])
        fixed = data["fixed"]
        note = _(
            "План: %(n)s замовлень, %(m)s МО, %(d)s простоїв.%(throttle)s%(seq)s",
            n=orders_n,
            m=data["mo_count"],
            d=len(downtimes),
            throttle=(
                _(" Черга верстатів %(days).1f доби: замовлень менше, ніж у налаштуваннях (%(cfg)s).")
                % {"days": data["backlog"], "cfg": data["cfg_orders"]}
                if orders_n < data["cfg_orders"]
                else ""
            ),
            seq=_(" Послідовності підсунуто: %s.", ", ".join("%s %s→%s" % tuple(f) for f in fixed)) if fixed else "",
        )
        rec.write(
            {
                "margin_plan_pct": pricing.margin_pct(rec.revenue, rec.cost_plan),
                "hot_section": data["hot_section"],
                "hot_load_pct": hot_load,
                "spill_min": data["spill"],
                "note": note,
                "generated": True,
                "gen_phase": "done",
                "gen_done": 0,
            }
        )

    @api.model
    def td_generate_today(self):
        """Синхронний перший запуск (тести, консоль): план на поточну добу й одразу диспетчер."""
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
