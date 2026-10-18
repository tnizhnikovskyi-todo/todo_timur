"""W3-A: `TestW3Common` — фікстури W3 (W3_SPEC 13.0). Час — ключ контексту `f3d_now` (`dates.now_utc`)."""

from datetime import datetime, timedelta

from odoo.addons.td_energy.tests.common import TestW1Common
from odoo.addons.td_energy.tools.dates import to_local

TAGS = ("post_install", "-at_install", "td", "td_w3")
NOW = datetime(2026, 10, 17, 11, 20, 0)  # 14:20 Київ, субота (макет)
SLOT = timedelta(minutes=15)
T0 = datetime(2026, 10, 17, 6, 0, 0)  # 09:00 Київ — початок слота фікстур


class TestW3Common(TestW1Common):
    """Користувачі груп, ресурси, сигнали, показання, точки, лічильники й інтервали ресурсів."""

    now = NOW

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Resource = cls.env["td.energy.resource"]
        cls.Price = cls.env["td.energy.price"]
        cls.Point = cls.env["td.energy.point"]
        cls.ResInterval = cls.env["td.energy.res.interval"]
        cls.Signal = cls.env["td.signal"]
        cls.Reading = cls.env["td.reading"]

    # --- довідники --------------------------------------------------------------------------------------
    def resource(self, code):
        return self.Resource.get_by_code(code)

    def signal(self, code, kind="gauge", unit="м³/год", period_s=60, **kw):
        vals = {"code": code, "name": code, "kind": kind, "unit": unit, "period_s": period_s, "module": "energy"}
        vals.update(kw)
        # Сигнал може вже існувати (напр. `energy_control/air/setpoint_bar` створює W2 td_energy_control).
        existing = self.Signal.with_context(active_test=False).search([("code", "=", code)], limit=1)
        if existing:
            existing.write({k: v for k, v in vals.items() if k not in ("code", "name", "module")})
            return existing
        return self.Signal.create(vals)

    def feed(self, signal, points, quality="good"):
        """`points` — `[(ts, value)]` → `td.reading`."""
        return self.Reading.create(
            [{"signal_id": signal.id, "ts": ts, "value": v, "quality": quality} for ts, v in points]
        )

    def point(self, code, resource="gas", kind="consumer", **vals):
        vals.update(resource_id=self.resource(resource).id, code=code, name=vals.pop("name", code), kind=kind)
        return self.Point.create(vals)

    def meter(self, code, point, mode="counter", qty=None, flow=None, **vals):
        vals.update(
            code=code, name=code, resource_id=point.resource_id.id, point_id=point.id, mode=mode,
            role="resource", model="other",
        )  # fmt: skip
        if qty:
            vals["qty_signal_id"] = qty.id
        if flow:
            vals["flow_signal_ids"] = [(6, 0, [s.id for s in flow])]
        return self.env["td.energy.meter"].create(vals)

    def res_interval(self, meter, ts, qty, quality="measured", metric="main", rate=None, cost=0.0, is_backfill=False):
        local = to_local(ts)
        factor = meter.resource_id.rate_hour_factor or 1.0
        return self.ResInterval.create(
            {
                "meter_id": meter.id, "metric": metric, "ts_start": ts, "ts_end": ts + SLOT, "day": local.date(),
                "hour_local": local.hour, "qty": qty, "rate_avg": qty * 4.0 / factor if rate is None else rate,
                "kwh_eq": 0.0, "price": 0.0, "cost": cost, "quality": quality, "built_at": self.now,
                "is_backfill": is_backfill,
            }
        )  # fmt: skip

    def rows(self, meter, metric="main"):
        """Рядки лічильника за зростанням часу (SQL, без груп доступу)."""
        self.env.flush_all()
        self.env.cr.execute(
            "SELECT ts_start, qty, rate_avg, kwh_eq, price, cost, quality, is_backfill FROM td_energy_res_interval"
            " WHERE meter_id = %s AND metric = %s ORDER BY ts_start",
            (meter.id, metric),
        )
        return self.env.cr.fetchall()

    def builder(self, now=None):
        from ..tools.build import SlotBuilder

        return SlotBuilder(self.env, now or self.now)

    def build(self, meters, now=None, **kw):
        return self.builder(now).build_all(meters, **kw)

    def el_interval(self, meter_code, ts, kwh, **kw):
        """Електричний інтервал наявного (демо) лічильника: `td.energy.interval` через W1-фікстуру."""
        return self.interval(meter_code, ts, kwh, **kw)

    def ref_user(self, login, *groups):
        return self._mk_user(login, list(groups))
