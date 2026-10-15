"""AC-15…AC-19, AC-87: безперервний лічильник `Ec(t)` (R-03) і ряд з показань / інтервалів."""

from datetime import datetime, timedelta

from odoo import fields
from odoo.tests import tagged

from ..tools.counter import Series, worst
from ..tools.dates import to_local
from .common import TAGS, F3DEnergyCase


class EnergyMixin:
    """Синтетичні сигнали, лічильники, показання й інтервали (SPEC §13.0). Не TestCase."""

    def base_day(self):
        """Початок доби UTC три доби тому: показання не старші за `keep_days` телеметрії."""
        return (fields.Datetime.now() - timedelta(days=3)).replace(hour=0, minute=0, second=0, microsecond=0)

    def mk_signal(self, code, kind="gauge", unit="кВт", **kw):
        vals = {"code": code, "name": code, "kind": kind, "unit": unit, "module": "energy"}
        vals.update(kw)
        return self.env["f3d.signal"].create(vals)

    def mk_meter(self, code, role="consumer", export=False, max_kw=48.0, with_power=False):
        """Вузол-споживач `<code без PM->` під SEC-1 і лічильник `code` з сигналами енергії."""
        node_code = code[3:] if code.startswith("PM-") else code
        parent = self.env["f3d.energy.node"].search([("code", "=", "SEC-1")])
        node = self.env["f3d.energy.node"].create(
            {"code": node_code, "name": node_code, "kind": "consumer", "parent_id": parent.id, "section": 1}
        )
        base = "energy/consumers/%s/" % node_code
        vals = {
            "code": code,
            "name": code,
            "node_id": node.id,
            "role": role,
            "max_kw": max_kw,
            "e_import_signal_id": self.mk_signal(base + "kwh_total", "counter", "кВт·год", period_s=60).id,
        }
        if export:
            vals["e_export_signal_id"] = self.mk_signal(base + "kwh_export", "counter", "кВт·год", period_s=60).id
        if with_power:
            vals["p_signal_id"] = self.mk_signal(base + "p_now").id
        return self.env["f3d.energy.meter"].create(vals)

    def bind_equipment(self, signal_code, equipment_code):
        """Обладнання сцени з кодом `equipment_code` (створюється, якщо немає) — на сигнал: потрібне для заявок."""
        Equipment = self.env["maintenance.equipment"]
        equipment = Equipment.search([("f3d_code", "=", equipment_code)], limit=1) or Equipment.create(
            {"name": equipment_code, "f3d_code": equipment_code}
        )
        self.env["f3d.signal"].search([("code", "=", signal_code)]).write({"equipment_id": equipment.id})
        return equipment

    def feed(self, signal, points, quality="good"):
        """Показання `f3d.reading` + `last_*` сигналу (без телеметрійного інгесту)."""
        self.env["f3d.reading"].create(
            [{"signal_id": signal.id, "ts": t, "value": v, "quality": quality, "src": "module"} for t, v in points]
        )
        t, v = max(points)
        signal.write({"last_ts": t, "last_value": v, "last_quality": "good", "status": "ok"})

    def mk_interval(self, meter, ts_start, kwh, kwh_export=0.0, quality="measured", e_start=0.0, price=8.4):
        local = to_local(ts_start)
        return self.env["f3d.energy.interval"].create(
            {
                "meter_id": meter.id, "ts_start": ts_start, "ts_end": ts_start + timedelta(minutes=15),
                "day": local.date(), "hour_local": local.hour, "e_start": e_start, "e_end": e_start + kwh,
                "kwh": kwh, "kwh_export": kwh_export, "kw_avg": kwh * 4, "price": price,
                "cost": round(kwh * price, 2), "quality": quality, "built_at": fields.Datetime.now(),
            }
        )  # fmt: skip


def ts(h, m=0, s=0):
    return datetime(2026, 10, 12, h, m, s)


@tagged(*TAGS)
class TestCounterPure(F3DEnergyCase):
    def test_continuous_series(self):  # AC-15
        points = [(ts(1, 35, 30) + timedelta(seconds=60 * k), 999.89 + 0.22 * k) for k in range(80)]
        ser = Series.build(points, max_kw=48)
        self.assertAlmostEqual(ser.value_at(ts(1, 36)), 1000.0, places=6)
        self.assertAlmostEqual(ser.value_at(ts(2, 54)), 1017.16, places=6)
        delta, quality = ser.delta(ts(1, 36), ts(2, 54))
        self.assertAlmostEqual(delta, 17.16, places=6)
        self.assertEqual(quality, "measured")
        self.assertIsNone(ser.value_at(ts(1, 35)))

    def test_interpolated_gap(self):  # AC-16
        points = [(ts(10), 500.0), (ts(10, 40), 520.0)]
        ser = Series.build(points, max_kw=48)
        self.assertAlmostEqual(ser.value_at(ts(10, 15)), 507.5, places=6)
        self.assertEqual(ser.delta(ts(10), ts(10, 15)), (7.5, "interpolated"))
        self.assertEqual(Series.build(points, max_kw=48, gap_max_s=3600).delta(ts(10), ts(10, 15))[1], "measured")

    def test_resets(self):  # AC-17
        ser = Series.build([(ts(10), 12345.678), (ts(10, 1), 0.512)], max_kw=48)
        self.assertAlmostEqual(ser.cs[-1], 12346.190, places=6)
        self.assertEqual(ser.seg, ["reset"])
        self.assertAlmostEqual(ser.resets[0][3] - ser.resets[0][2], 12345.678, places=6)
        swap = Series.build([(ts(10), 12345.678), (ts(10, 1), 2000.0)], max_kw=48)
        self.assertAlmostEqual(swap.cs[-1], 12345.678, places=6)
        self.assertEqual(swap.seg, ["reset"])
        noise = Series.build([(ts(10), 100.0), (ts(10, 1), 99.6)], max_kw=48)
        self.assertEqual((noise.cs[-1], noise.seg), (100.0, ["measured"]))
        self.assertEqual(noise.resets, [])
        based = Series.build([(ts(10), 5.0)], base=100.0)
        self.assertEqual(based.cs, [105.0])

    def test_delta_missing_and_order(self):  # AC-18
        ser = Series.build([(ts(10), 1.0), (ts(10, 1), 2.0)])
        self.assertEqual(ser.delta(ts(9), ts(10, 1)), (None, "missing"))
        self.assertEqual(ser.delta(ts(10), ts(11)), (None, "missing"))
        self.assertEqual(Series([], [], []).delta(ts(10), ts(11)), (None, "missing"))
        self.assertEqual(worst("measured", "interpolated"), "interpolated")
        self.assertEqual(worst("interpolated", "reset", "measured"), "reset")
        self.assertEqual(worst("reset", "missing", "interpolated"), "missing")
        self.assertEqual(worst(), "measured")


@tagged(*TAGS)
class TestCounterMeter(EnergyMixin, F3DEnergyCase):
    def test_series_from_intervals(self):  # AC-19
        meter = self.mk_meter("PM-SAW-T")
        day = self.base_day()
        energy = 1000.0
        for k in range(4):
            self.mk_interval(meter, day + timedelta(hours=1, minutes=15 * k), 2.0, e_start=energy)
            energy += 2.0
        a, b = day + timedelta(hours=1, minutes=15), day + timedelta(hours=1, minutes=45)
        ser = meter._f3d_counter_series(a, b)
        self.assertEqual(ser.delta(a, b), (4.0, "measured"))
        inner = ser.delta(a + timedelta(minutes=5), b)
        self.assertAlmostEqual(inner[0], 3.3333, places=3)
        self.assertEqual(inner[1], "interpolated")

    def test_kwh_api(self):  # AC-87
        meter = self.mk_meter("PM-SAW-T")
        day = self.base_day()
        start = day + timedelta(hours=1, minutes=35, seconds=30)
        self.feed(meter.e_import_signal_id, [(start + timedelta(seconds=60 * k), 999.89 + 0.22 * k) for k in range(80)])
        a, b = day + timedelta(hours=1, minutes=36), day + timedelta(hours=2, minutes=54)
        self.assertEqual(meter._f3d_kwh(a, b), (17.16, "measured"))
        self.assertEqual(self.env["f3d.energy.node"]._f3d_kwh_by_code("NOPE", a, b), (0.0, "missing"))
        self.assertEqual(self.env["f3d.energy.node"]._f3d_kwh_by_code("SAW-T", a, b), (17.16, "measured"))
        with self.assertRaises(ValueError):
            meter._f3d_kwh(b, a)
        with self.assertRaises(ValueError):
            meter._f3d_kwh(a, a)
