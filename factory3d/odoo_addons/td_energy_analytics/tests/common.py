"""W4-A: `TestW4Common` — фікстури W4 (W4_SPEC 13.0).

Зберігайте імена `TAGS` і `TestW4Common`: їх імпортують тести B і контрактний тест менеджера.
Час — ключ контексту `f3d_now` (`TestW1Common`: 2026-10-17 14:20 Київ, субота); користувачі W1:
`u_view` (user), `u_cost`, `u_eng` (manager), `u_chief`, `u_plain` (без груп енергетики).
"""

from datetime import date, datetime, timedelta

from odoo.addons.td_energy.tests.common import TestW1Common
from odoo.addons.td_energy.tools import dates

TAGS = ("post_install", "-at_install", "td", "td_w4")
TODAY = date(2026, 10, 17)
SLOT = timedelta(minutes=15)


class TestW4Common(TestW1Common):
    """Базові фікстури W1 + допоміжні методи W4: ділянки, інтервали, значення драйверів, факти, бази, бюджети."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Area = cls.env["td.energy.area"]
        cls.Driver = cls.env["td.energy.driver"]
        cls.DriverValue = cls.env["td.energy.driver.value"]
        cls.Daily = cls.env["td.energy.daily"]
        cls.Baseline = cls.env["td.energy.baseline"]
        cls.Enpi = cls.env["td.energy.enpi"]
        cls.Budget = cls.env["td.energy.budget"]
        cls.Api = cls.env["td.energy.analytics"]
        cls.today = TODAY
        cls.plate = cls.Driver.search([("code", "=", "plate_m2")], limit=1)
        cls.hdd = cls.Driver.search([("code", "=", "hdd")], limit=1)
        cls.res_el = cls.env.ref("td_energy_resources.resource_el")
        cls.res_gas = cls.env.ref("td_energy_resources.resource_gas")
        cls.res_heat = cls.env.ref("td_energy_resources.resource_heat")

    # --- довідники ------------------------------------------------------------------------------------
    def _area(self, code):
        return self.Area.search([("code", "=", code)], limit=1)

    def _node(self, code, area=None):
        node = self.env["td.energy.node"].search([("code", "=", code)], limit=1)
        if area is not None:
            node.area_id = self._area(area) if isinstance(area, str) else area
        return node

    def _user(self, groups, login=None):
        login = login or "w4_%s" % abs(hash(tuple(groups)))
        return self._mk_user(login, list(groups))

    def _calendar_two_shifts(self):
        """Дві зміни макета (пн–пт 07:00–16:00 і 16:00–23:00): порожній `shift_calendar_id` = умовчання W3."""
        self.env["ir.config_parameter"].sudo().set_param("td.energy.shift_calendar_id", "")

    def _param(self, name, value):
        self.env["ir.config_parameter"].sudo().set_param("td.energy_analytics." + name, str(value))

    # --- інтервали ------------------------------------------------------------------------------------
    def _direct(self, code):
        """Вузол-споживач як «прямий» (потрібен робочий центр)."""
        node = self.env["td.energy.node"].search([("code", "=", code)], limit=1)
        wc = self.env["mrp.workcenter"].search([("name", "=", "WC-%s" % code)], limit=1) or self.env[
            "mrp.workcenter"
        ].create({"name": "WC-%s" % code})
        node.write({"workcenter_id": wc.id, "alloc_role": "direct"})
        return node

    def _day0(self, day):
        """Початок київської доби `day` (UTC naive)."""
        return dates.local_day_bounds(day)[0]

    def _interval(self, meter_code, ts_start, kwh, kwh_export=0.0, price=8.4, quality="measured"):
        return self.interval(meter_code, ts_start, kwh, kwh_export=kwh_export, price=price, quality=quality)

    def _fill(self, meter_code, day, kwh, slots=range(96), kwh_export=0.0, price=8.4, quality="measured"):
        """Інтервали `meter_code` у слотах `slots` (0…95) доби `day`; `kwh` — число або `{слот: кВт·год}`."""
        meter = self.Meter.search([("code", "=", meter_code)])
        d0 = self._day0(day)
        rows = []
        for slot in slots:
            value = kwh.get(slot, 0.0) if isinstance(kwh, dict) else kwh
            ts = d0 + SLOT * slot
            local = dates.to_local(ts)
            rows.append(
                {
                    "meter_id": meter.id, "ts_start": ts, "ts_end": ts + SLOT, "day": local.date(),
                    "hour_local": local.hour, "e_start": 0.0, "e_end": value, "kwh": value, "kwh_export": kwh_export,
                    "kw_avg": value * 4, "price": price, "cost": round(value * price, 2), "quality": quality,
                    "built_at": self.now,
                }
            )  # fmt: skip
        return self.env["td.energy.interval"].create(rows)

    def _driver(self, code):
        return self.Driver.search([("code", "=", code)], limit=1)

    def _driver_value(self, code, day, value, quality="estimated"):
        driver = self.Driver.search([("code", "=", code)], limit=1)
        rec = self.DriverValue.search([("driver_id", "=", driver.id), ("day", "=", day)])
        if rec:
            rec.write({"value": value, "quality": quality})
            return rec
        return self.DriverValue.create({"driver_id": driver.id, "day": day, "value": value, "quality": quality})

    def _daily(self, day, scope="plant", resource="el", node=None, area=None, **vals):
        """Пряма вставка факту (без побудови)."""
        resource = self.env["td.energy.resource"].get_by_code(resource) if isinstance(resource, str) else resource
        node = self._node(node) if isinstance(node, str) else node
        area = self._area(area) if isinstance(area, str) else area
        data = {
            "day": day, "scope": scope, "resource_id": resource.id if resource else False,
            "node_id": node.id if node else False, "area_id": area.id if area else (node.area_id.id if node else False),
            "built_at": self.now,
        }  # fmt: skip
        data.update(vals)
        return self.Daily.create(data)

    def _days(self, first, count):
        return [first + timedelta(days=i) for i in range(count)]

    # --- бази й бюджети -------------------------------------------------------------------------------
    def _baseline(self, period, coefs, resource="el", scope="plant", area=None, **vals):
        """Чернетка моделі бази: `period` — `(date_from, date_to)`, `coefs` — `{код драйвера: коефіцієнт}`."""
        lines = [
            (0, 0, {"driver_id": self._driver(code).id, "coef": coef, "sequence": 10 + i})
            for i, (code, coef) in enumerate(coefs.items())
        ]  # fmt: skip
        data = {
            "resource_id": self.env["td.energy.resource"].get_by_code(resource).id, "scope": scope,
            "area_id": self._area(area).id if area else False, "period_from": period[0], "period_to": period[1],
            "line_ids": lines,
        }  # fmt: skip
        data.update(vals)
        return self.Baseline.create(data)

    def _approved_baseline(self, period, coefs, const, resource="el", r2=0.93, **vals):
        """Затверджена база з готовими коефіцієнтами (метод `manual`; затверджує головний енергетик)."""
        base = self._baseline(period, coefs, resource=resource, const_per_day=const, method="manual", **vals)
        base.write({"r2": r2})
        base.with_user(self.u_chief).action_approve()
        return base

    def _budget(self, month, amount, resource=None, approve=True, **vals):
        data = {"month": month, "amount_uah": amount, "resource_id": resource.id if resource else False}
        data.update(vals)
        budget = self.Budget.create(data)
        if approve:
            budget.with_user(self.u_chief).action_approve()
        return budget

    # --- МО й розподіл --------------------------------------------------------------------------------
    def _product(self, code, area_m2=0.0):
        product = self.env["product.product"].search([("default_code", "=", code)], limit=1)
        if product:
            product.td_plate_area_m2 = area_m2
            return product
        return self.env["product.product"].create(
            {"name": code, "default_code": code, "type": "consu", "td_plate_area_m2": area_m2}
        )

    def _mo(self, product, qty, name=None, finished=None, state="done"):
        """МО без складських проводок; завершення — SQL (як у демо-сиді)."""
        mo = self.env["mrp.production"].create({"product_id": product.id, "product_qty": qty})
        sets, params = ["state = %s"], [state]
        if finished is not None:
            sets.append("date_finished = %s")
            params.append(finished)
        if name:
            sets.append("name = %s")
            params.append(name)
        self.env.cr.execute("UPDATE mrp_production SET %s WHERE id = %%s" % ", ".join(sets), params + [mo.id])
        mo.invalidate_recordset()
        return mo

    def _alloc(self, production, node, day, kwh, minutes=0.0, kind="direct", cost=None):
        """Рядок розподілу; для МО (`production`) створюється наряд, для `None` (простій) — без наряду."""
        wo = self.env["mrp.workorder"]
        wc = node.workcenter_id or self.env["mrp.workcenter"].search([("name", "=", "WC-%s" % node.code)], limit=1)
        wc = wc or self.env["mrp.workcenter"].create({"name": "WC-%s" % node.code})
        if production:
            wo = production.workorder_ids.filtered(lambda w: w.workcenter_id == wc)[:1] or wo.create(
                {
                    "name": "WO", "production_id": production.id, "workcenter_id": wc.id,
                    "product_uom_id": production.product_uom_id.id,
                }
            )  # fmt: skip
        return self.env["td.energy.alloc"].create(
            {
                "day": day, "kind": kind, "workorder_id": wo.id or False, "workcenter_id": wc.id,
                "node_id": node.id, "kwh": kwh, "minutes": minutes, "cost": kwh * 8.4 if cost is None else cost,
                "quality": "measured",
            }
        )  # fmt: skip

    def _res_interval(self, resource_code, ts_start, qty, cost=0.0, kind="source"):
        """Ресурсний інтервал (W3) точки `W4-<РЕСУРС>-<вид>`; точка й лічильник створюються за потреби."""
        resource = self.env["td.energy.resource"].get_by_code(resource_code)
        code = "W4-%s-%s" % (resource_code.upper(), kind.upper())
        point = self.env["td.energy.point"].search([("code", "=", code)], limit=1) or self.env[
            "td.energy.point"
        ].create({"resource_id": resource.id, "code": code, "name": code, "kind": kind})
        meter = self.env["td.energy.meter"].search([("code", "=", code)], limit=1)
        if not meter:
            signal = self.env["td.signal"].create(
                {"code": "energy/w4/%s" % code, "name": code, "kind": "counter", "unit": "м³",
                 "period_s": 60, "module": "energy"}
            )  # fmt: skip
            meter = self.env["td.energy.meter"].create(
                {
                    "code": code, "name": code, "resource_id": resource.id, "point_id": point.id, "mode": "counter",
                    "role": "resource", "model": "other", "qty_signal_id": signal.id,
                }
            )  # fmt: skip
        local = dates.to_local(ts_start)
        return self.env["td.energy.res.interval"].create(
            {
                "meter_id": meter.id, "metric": "main", "ts_start": ts_start, "ts_end": ts_start + SLOT,
                "day": local.date(), "hour_local": local.hour, "qty": qty, "rate_avg": qty * 4.0, "kwh_eq": 0.0,
                "price": 0.0, "cost": cost, "quality": "measured", "built_at": self.now,
            }
        )  # fmt: skip

    # --- допоміжні перевірки --------------------------------------------------------------------------
    def _rows(self, table, where="TRUE", params=(), cols="*"):
        self.env.flush_all()
        self.env.cr.execute("SELECT %s FROM %s WHERE %s" % (cols, table, where), params)
        return self.env.cr.fetchall()

    def _local(self, day, hour, minute=0):
        """Київський момент → UTC naive."""
        return dates.to_utc(datetime(day.year, day.month, day.day, hour, minute))
