import logging
from collections import defaultdict
from datetime import timedelta

from odoo import api, fields, models

from ..tools import alloc as alloc_tools
from ..tools import dates

_logger = logging.getLogger(__name__)

EPS = 5e-4  # половина одиниці останнього знака kwh (3 знаки)


class F3dEnergyAlloc(models.Model):
    _name = "td.energy.alloc"
    _inherit = ["td.energy.day.mixin"]
    _description = "Енергетика: розподіл на виробництво"
    _order = "day desc, production_id, workorder_id, kind"

    day = fields.Date(string="Дата (Київ)", required=True, index=True)
    kind = fields.Selection(
        [
            ("direct", "Пряма"),
            ("shared", "Спільна"),
            ("idle", "Простій РЦ"),
            ("unallocated", "Нерозподілена"),
            ("overhead", "Накладні"),
        ],
        required=True,
        index=True,
    )
    workorder_id = fields.Many2one("mrp.workorder", string="Завдання", ondelete="cascade", index=True)
    production_id = fields.Many2one(
        "mrp.production", related="workorder_id.production_id", store=True, index=True, string="МО"
    )
    workcenter_id = fields.Many2one("mrp.workcenter", string="Робочий центр", index=True)
    node_id = fields.Many2one("td.energy.node", string="Вузол")
    pool_id = fields.Many2one("td.energy.pool", string="Пул")
    kwh = fields.Float(string="кВт·год", digits=(12, 3))
    minutes = fields.Float(string="Хвилин роботи", digits=(10, 1))
    cost = fields.Float(string="Вартість, грн", digits=(12, 2), groups="td_energy.group_td_energy_cost")
    currency_id = fields.Many2one("res.currency", default=lambda self: self.env.company.currency_id)
    quality = fields.Selection(
        [
            ("measured", "Виміряно"),
            ("interpolated", "Інтерпольовано"),
            ("estimate", "Оцінка"),
            ("partial", "Частково"),
        ],
        required=True,
        default="measured",
    )
    locked = fields.Boolean(string="Зафіксовано", default=False, index=True)
    analytic_line_ids = fields.Many2many(
        "account.analytic.line", "td_energy_alloc_analytic_rel", "alloc_id", "line_id", copy=False
    )
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)

    # --- крон ----------------------------------------------------------------------------------------
    @api.model
    def _cron_alloc(self):
        """R-08, R-09: доба сьогодні (до `now`); учора — доки місцевий час < `alloc_close_h` або вона ще не
        перераховувалась після півночі."""
        if not dates.param_bool(self.env, "read_enabled"):
            return
        try:
            with self.env.cr.savepoint():
                now = dates.now_utc(self.env)
                local = dates.to_local(now)
                today = local.date()
                yesterday = today - timedelta(days=1)
                days = [today]
                close_h = dates.param_float(self.env, "alloc_close_h", 2.0)
                midnight = dates.local_day_bounds(today)[0]
                if local.hour + local.minute / 60 < close_h or not self.sudo().search_count(
                    [("day", "=", yesterday), ("write_date", ">=", midnight)]
                ):
                    days.insert(0, yesterday)
                self._td_alloc_days(days, now=now)
        except Exception:
            _logger.exception("Енергетика: помилка розподілу на виробництво")

    # --- допоміжні -----------------------------------------------------------------------------------
    @api.model
    def _td_machine_intervals(self, workorders, d0, end):
        """CM-03 (обгортка): `{wo_id: [(start, end, state), …]}` для завдань РЦ з активним `td.machine`;
        без `td_machine_connect` — порожній словник. Ключ є для кожного завдання такого РЦ."""
        if "td.machine" not in self.env or not workorders:
            return {}
        Machine = self.env["td.machine"].sudo()
        wcs = workorders.workcenter_id.filtered(
            lambda wc: Machine.search_count([("workcenter_id", "=", wc.id), ("active", "=", True)])
        )
        wos = workorders.filtered(lambda w: w.workcenter_id in wcs)
        if not wos:
            return {}
        res = Machine._td_wo_intervals(wos, d0, end)
        return {wo.id: list(res.get(wo.id, [])) for wo in wos}

    def _prepare_analytic_line_values(self, account_field_values, amount, unit_amount):
        """A-11: значення аналітичного рядка для рядка розподілу."""
        self.ensure_one()
        return {
            "name": "[EN] %s" % self.workorder_id.display_name,
            "amount": amount,
            **account_field_values,
            "unit_amount": unit_amount,
            "product_id": self.workorder_id.product_id.id,
            "product_uom_id": self.env.ref("uom.product_uom_kwh").id,
            "company_id": self.company_id.id,
            "ref": self.production_id.name,
            "category": "manufacturing_order",
        }

    @api.model
    def _td_candidates(self, d0, end):
        """R-08 п. 1: завдання з журналом часу в добі, у роботі, або завершені в/після доби."""
        Prod = self.env["mrp.workcenter.productivity"]
        ids = set(
            Prod.search(
                [
                    ("workorder_id", "!=", False),
                    ("date_start", "<", end),
                    "|",
                    ("date_end", "=", False),
                    ("date_end", ">=", d0),
                ]
            ).workorder_id.ids
        )
        WO = self.env["mrp.workorder"]
        wos = WO.browse(ids) | WO.search(
            ["|", ("state", "=", "progress"), "&", ("date_finished", ">=", d0), ("date_start", "<", end)]
        )
        return wos.filtered(lambda w: w.state != "cancel")

    @api.model
    def _td_intervals(self, wos, d0, end):
        """R-08 п. 2: `{wo_id: [(s, e), …]}` — інтервали роботи завдань у `[d0, end)`."""
        machine = self._td_machine_intervals(wos, d0, end) or {}
        machine_wcs = {w.workcenter_id.id for w in wos if w.id in machine}
        result = {}
        for wo in wos:
            if wo.id in machine or wo.workcenter_id.id in machine_wcs:
                raw = [(s, e) for s, e, _state in machine.get(wo.id, ())]
            else:
                raw = [(p.date_start, p.date_end or end) for p in wo.time_ids if p.date_start]
            ivs = alloc_tools.merge(piece for piece in (alloc_tools.clip(s, e, d0, end) for s, e in raw) if piece)
            if ivs:
                result[wo.id] = ivs
        return result

    # --- розподіл діб --------------------------------------------------------------------------------
    @api.model
    def _td_alloc_days(self, days, now=None):
        """R-09 п. 8: повний перерахунок діб; `locked` не змінюються. Повертає статистику."""
        now = now or dates.now_utc(self.env)
        stats = {"days": 0, "rows": 0, "skipped": 0, "kwh": 0.0}
        prices = {}
        for day in sorted(set(days)):
            d0, d1 = dates.local_day_bounds(day)
            if min(d1, now) <= d0:
                continue
            res = self.sudo()._td_alloc_day(day, now, prices)
            stats["days"] += 1
            for key in ("rows", "skipped", "kwh"):
                stats[key] += res[key]
        return stats

    def _td_price(self, prices, dt):
        a = alloc_tools.floor15(dt)
        if a not in prices:
            prices[a] = self.env["td.energy.tariff"]._td_price_at(a)[1]
        return prices[a]

    def _td_alloc_day(self, day, now, prices):
        Node = self.env["td.energy.node"]
        d0, d1 = dates.local_day_bounds(day)
        end = min(d1, now)
        series_memo = {}

        def series_of(node):
            if node.id not in series_memo:
                meter = node.meter_id.sudo()
                series = meter._td_counter_series(d0, end) if meter else None
                series_memo[node.id] = series or None
            return series_memo[node.id]

        def day_kwh_cost(series):
            """(кВт·год, вартість, якість) за добу; кошт — сума за слотами. Немає даних — None."""
            total, cost, quals = 0.0, 0.0, []
            for a, b in alloc_tools.slots(d0, end):
                kwh, q = series.delta(a, b)
                if kwh is None:
                    continue
                total += kwh
                cost += kwh * self._td_price(prices, a)
                quals.append(q)
            if not quals:
                return None
            return total, cost, alloc_tools.row_quality(quals)

        new = {}  # ключ → значення
        wos = self._td_candidates(d0, end)
        intervals = self._td_intervals(wos, d0, end)
        node_by_wc = {
            n.workcenter_id.id: n for n in Node.search([("alloc_role", "=", "direct"), ("workcenter_id", "!=", False)])
        }
        wo_by_id = {wo.id: wo for wo in wos}
        by_wc = defaultdict(dict)
        for wo_id, ivs in intervals.items():
            by_wc[wo_by_id[wo_id].workcenter_id.id][wo_id] = ivs

        # --- R-08: пряма енергія ---
        direct = {}
        direct_slot, minutes_slot = defaultdict(float), defaultdict(float)
        measured_kwh, measured_cost = defaultdict(float), defaultdict(float)
        for wc_id, wo_ivs in by_wc.items():
            node = node_by_wc.get(wc_id)
            if not node:
                continue
            series = series_of(node)
            for x, y, active in alloc_tools.segments(wo_ivs):
                seconds = (y - x).total_seconds()
                kwh, q = series.delta(x, y) if series else (None, "missing")
                if kwh is None:
                    kwh = alloc_tools.estimate_kwh(node.p_inst_kw, node.load_factor, seconds)
                    q = "estimate"
                else:
                    q = alloc_tools.norm_quality(q)
                price = self._td_price(prices, x)
                if q != "estimate":
                    measured_kwh[wc_id] += kwh
                    measured_cost[wc_id] += kwh * price
                part = kwh / len(active)
                for wo_id in active:
                    d = direct.setdefault(wo_id, {"kwh": 0.0, "minutes": 0.0, "cost": 0.0, "quals": []})
                    d["kwh"] += part
                    d["minutes"] += seconds / 60.0
                    d["cost"] += part * price
                    d["quals"].append(q)
                    slot = alloc_tools.floor15(x)
                    direct_slot[wo_id, slot] += part
                    minutes_slot[wo_id, slot] += seconds / 60.0
        for wo_id, d in direct.items():
            wo = wo_by_id[wo_id]
            node = node_by_wc[wo.workcenter_id.id]
            new[day, "direct", wo_id, wo.workcenter_id.id, node.id, False] = {
                "kwh": d["kwh"],
                "minutes": d["minutes"],
                "cost": d["cost"],
                "quality": alloc_tools.row_quality(d["quals"]),
                "company_id": wo.company_id.id or node.company_id.id or self.env.company.id,
            }

        # --- R-08 п. 5: простій РЦ ---
        for wc_id, node in node_by_wc.items():
            series = series_of(node)
            total = day_kwh_cost(series) if series else None
            if not total:
                continue
            idle_kwh = max(total[0] - measured_kwh[wc_id], 0.0)
            if idle_kwh >= EPS:
                new[day, "idle", False, wc_id, node.id, False] = {
                    "kwh": idle_kwh,
                    "cost": max(total[1] - measured_cost[wc_id], 0.0),
                    "quality": total[2],
                    "company_id": node.company_id.id or self.env.company.id,
                }

        existing = {}
        dups = self.browse()
        for rec in self.search([("day", "=", day)]):
            key = (rec.day, rec.kind, rec.workorder_id.id or False, rec.workcenter_id.id or False,
                   rec.node_id.id or False, rec.pool_id.id or False)  # fmt: skip
            if key in existing:
                dups |= rec
            else:
                existing[key] = rec

        # --- R-09: спільні пули ---
        slot_wos = defaultdict(list)
        for wo_id, slot in minutes_slot:
            slot_wos[slot].append(wo_id)
        wc_with_node = set(node_by_wc)
        for pool in self.env["td.energy.pool"].with_context(active_test=False).search([]):
            nodes = Node.search([("pool_id", "=", pool.id)])
            series_list = [s for s in (series_of(n) for n in nodes) if s]
            allowed = set(pool.workcenter_ids.ids) & wc_with_node if pool.workcenter_ids else wc_with_node
            pool_total, pool_cost, pool_quals = 0.0, 0.0, []
            shared = {}
            for a, b in alloc_tools.slots(d0, end):
                parts = [r for r in (s.delta(a, b) for s in series_list) if r[0] is not None]
                if not parts:
                    continue
                pk = sum(r[0] for r in parts)
                q = alloc_tools.row_quality([r[1] for r in parts])
                price = self._td_price(prices, a)
                pool_total += pk
                pool_cost += pk * price
                pool_quals.append(q)
                if not pool.active:
                    continue
                claim = [w for w in slot_wos.get(a, ()) if wo_by_id[w].workcenter_id.id in allowed]
                src = direct_slot if pool.driver == "kwh" else minutes_slot
                drivers = {w: src[w, a] for w in claim}
                for wo_id, share in alloc_tools.pool_shares(pk, drivers).items():
                    s = shared.setdefault(wo_id, {"kwh": 0.0, "cost": 0.0, "minutes": 0.0, "quals": []})
                    s["kwh"] += share
                    s["cost"] += share * price
                    s["minutes"] += minutes_slot[wo_id, a]
                    s["quals"].append(q)
            if not pool_quals:
                continue
            sum_kwh, sum_cost = 0.0, 0.0
            for wo_id, s in shared.items():
                wo = wo_by_id[wo_id]
                key = (day, "shared", wo_id, wo.workcenter_id.id, False, pool.id)
                old = existing.get(key)
                if old and old.locked:
                    sum_kwh += old.kwh
                    sum_cost += old.cost
                    continue
                sum_kwh += s["kwh"]
                sum_cost += s["cost"]
                new[key] = {
                    "kwh": s["kwh"],
                    "minutes": s["minutes"],
                    "cost": s["cost"],
                    "quality": alloc_tools.row_quality(s["quals"]),
                    "company_id": wo.company_id.id or self.env.company.id,
                }
            for key, old in existing.items():
                if key[1] == "shared" and key[5] == pool.id and old.locked and key[2] not in shared:
                    sum_kwh += old.kwh
                    sum_cost += old.cost
            rest = pool_total - sum_kwh
            if abs(rest) >= EPS:
                new[day, "unallocated", False, False, False, pool.id] = {
                    "kwh": rest,
                    "cost": pool_cost - sum_cost,
                    "quality": alloc_tools.row_quality(pool_quals),
                    "company_id": self.env.company.id,
                }

        # --- R-09 п. 7: накладні ---
        for node in Node.search([("alloc_role", "=", "overhead")]):
            series = series_of(node)
            total = day_kwh_cost(series) if series else None
            if total and total[0] >= EPS:
                new[day, "overhead", False, False, node.id, False] = {
                    "kwh": total[0],
                    "cost": total[1],
                    "quality": total[2],
                    "company_id": node.company_id.id or self.env.company.id,
                }

        return self._td_alloc_write(day, new, existing, dups)

    def _td_alloc_write(self, day, new, existing, dups):
        """R-09 п. 8: upsert за ключем; `locked` не чіпаємо; зайві незафіксовані — видаляємо."""
        res = {"rows": 0, "skipped": sum(1 for r in existing.values() if r.locked), "kwh": 0.0}
        to_create = []
        for key, vals in new.items():
            vals = dict(vals)
            vals["kwh"] = round(vals["kwh"], 3)
            vals["cost"] = round(vals.get("cost", 0.0), 2)
            vals["minutes"] = round(vals.get("minutes", 0.0), 1)
            rec = existing.get(key)
            if rec and rec.locked:
                continue
            res["rows"] += 1
            if key[1] in ("direct", "shared"):
                res["kwh"] += vals["kwh"]
            if rec:
                diff = {f: v for f, v in vals.items() if (rec[f].id if f == "company_id" else rec[f]) != v}
                if diff:
                    rec.write(diff)
            else:
                _day, kind, wo_id, wc_id, node_id, pool_id = key
                to_create.append(
                    {
                        **vals,
                        "day": day,
                        "kind": kind,
                        "workorder_id": wo_id or False,
                        "workcenter_id": wc_id or False,
                        "node_id": node_id or False,
                        "pool_id": pool_id or False,
                    }
                )
        if to_create:
            self.create(to_create)
        stale = self.browse()
        for key, rec in existing.items():
            if key not in new and not rec.locked:
                stale |= rec
        (stale | dups.filtered(lambda r: not r.locked)).unlink()
        return res
