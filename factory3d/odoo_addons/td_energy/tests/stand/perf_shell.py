# ruff: noqa
"""Вимірювання ТП-01…ТП-06 (SPEC §13.4) всередині Odoo (``odoo-bin shell``, stdin) на базі стенду.

Не імпортується pytest і не потрапляє в Odoo test-tags. Режим — PERF_MODE: tp01…tp06. Результат — рядок
``PERF {json}``. Дані генеруються SQL (``generate_series``). Запускати на окремій базі (без колектора), порядок:
tp01, tp02, tp03, tp04, tp06, tp05 (tp06 і tp05 очищають f3d_energy_interval).
"""

import json
import os
import statistics
import time
from datetime import datetime, timedelta, timezone

import odoo.sql_db as sql_db

MODE = os.environ["PERF_MODE"]
cr = env.cr  # noqa: F821  (env надає odoo shell)
Meter = env["f3d.energy.meter"].sudo()  # noqa: F821
Interval = env["f3d.energy.interval"].sudo()  # noqa: F821
out = {"mode": MODE}
now = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)


class Counter:
    """Лічильник SQL-запитів (патч Cursor.execute)."""

    def __enter__(self):
        self.n, self.orig = 0, sql_db.Cursor.execute
        outer = self

        def counted(cur, *a, **kw):
            outer.n += 1
            return outer.orig(cur, *a, **kw)

        sql_db.Cursor.execute = counted
        return self

    def __exit__(self, *exc):
        sql_db.Cursor.execute = self.orig


def pct(vals, q):
    vals = sorted(vals)
    return vals[min(len(vals) - 1, int(len(vals) * q))]


if MODE == "tp01":
    meters = Meter.search([("active", "=", True), ("e_import_signal_id", "!=", False)])
    pm = meters.filtered(lambda m: m.model == "pm5560")[:57]
    other = meters - pm
    start = (now - timedelta(days=2)).replace(minute=0, second=0)
    cr.execute("DELETE FROM f3d_energy_interval")
    cr.execute("DELETE FROM f3d_reading WHERE signal_id = ANY(%s)", [meters.e_import_signal_id.ids])
    t0 = time.perf_counter()
    rows = 0
    for group, n, step in ((pm, 2880, 60), (other, 576, 300)):
        for m in group:
            cr.execute(
                """INSERT INTO f3d_reading (signal_id, quality, src, ts, received_at, value)
                SELECT %s, 'good', 'collector', %s::timestamp + g * %s * interval '1 second', now() at time zone 'utc',
                       1000 + g * 0.01 FROM generate_series(0, %s - 1) g""",
                [m.e_import_signal_id.id, start, step, n],
            )
            rows += n
    cr.execute("UPDATE f3d_energy_meter SET last_interval_start = NULL")
    cr.commit()
    cr.execute("ANALYZE f3d_reading")
    out.update(meters=len(meters), pm5560=len(pm), readings=rows, gen_s=round(time.perf_counter() - t0, 1))
    env.invalidate_all()  # noqa: F821
    t0 = time.perf_counter()
    with Counter() as q:
        built = Interval._cron_build()
    out.update(build_s=round(time.perf_counter() - t0, 2), sql_queries=q.n, slots=built)
    cr.commit()

elif MODE == "tp02":
    Node, WC = env["f3d.energy.node"].sudo(), env["mrp.workcenter"].sudo()  # noqa: F821
    nodes = Node.search([("kind", "=", "consumer"), ("alloc_role", "in", ("none", "direct"))], limit=35)
    for n in nodes:  # чиста база: прямі споживачі без РЦ мають alloc_role='none' — прив'язуємо 35 РЦ
        n.write({"workcenter_id": n.workcenter_id.id or WC.create({"name": "TP-" + n.code}).id, "alloc_role": "direct"})
    wcs = nodes.workcenter_id
    prod = env["product.product"].sudo().create({"name": "TP product", "is_storable": True})  # noqa: F821
    bom = (
        env["mrp.bom"]
        .sudo()
        .create(
            {  # noqa: F821
                "product_tmpl_id": prod.product_tmpl_id.id,
                "product_qty": 1,
                "operation_ids": [(0, 0, {"name": "op " + w.name, "workcenter_id": w.id}) for w in wcs],
            }
        )
    )
    mo = env["mrp.production"].sudo().create({"product_id": prod.id, "product_qty": 1, "bom_id": bom.id})  # noqa: F821
    mo.action_confirm()
    loss = env["mrp.workcenter.productivity.loss"].sudo().search([("loss_type", "=", "productive")], limit=1)  # noqa: F821
    day = (now - timedelta(days=1)).date()
    base = datetime.combine(day, datetime.min.time()) + timedelta(hours=4)  # 07:00 за Києвом
    made = 0
    for i, wo in enumerate(mo.workorder_ids):
        for k in range(6):
            if made >= 200:
                break
            s = base + timedelta(hours=2 * k, minutes=i % 7)
            env["mrp.workcenter.productivity"].sudo().create(
                {  # noqa: F821
                    "workorder_id": wo.id,
                    "workcenter_id": wo.workcenter_id.id,
                    "loss_id": loss.id,
                    "date_start": s,
                    "date_end": s + timedelta(minutes=25),
                }
            )
            made += 1
    cr.commit()
    env.invalidate_all()  # noqa: F821
    t0 = time.perf_counter()
    with Counter() as q:
        stats = env["f3d.energy.alloc"].sudo()._f3d_alloc_days([day], now=now)  # noqa: F821
    out.update(
        workcenters=len(wcs),
        workorders=len(mo.workorder_ids),
        intervals=made,
        alloc_s=round(time.perf_counter() - t0, 2),
        sql_queries=q.n,
        stats=stats,
    )
    cr.rollback()

elif MODE == "tp03":
    from odoo.addons.factory3d_energy.tools import payload as pl

    cr.execute("SELECT count(*) FROM f3d_signal WHERE code LIKE 'energy/%' OR code LIKE 'infra/%'")
    out["signals_fresh"] = cr.fetchone()[0]
    cr.execute("""UPDATE f3d_signal SET last_ts = now() at time zone 'utc', last_value = 1 + random() * 100,
                  last_quality = 'good' WHERE code LIKE 'energy/%' OR code LIKE 'infra/%'""")
    cr.commit()
    env.invalidate_all()  # noqa: F821
    times = []
    for _ in range(30):
        t0 = time.perf_counter()
        payload = {}
        pl.build_energy(env, {}, payload)  # noqa: F821
        pl.build_infra(env, {}, payload)  # noqa: F821
        times.append((time.perf_counter() - t0) * 1000)
        env.invalidate_all()  # noqa: F821
    out.update(
        first_ms=round(times[0]),
        median_ms=round(statistics.median(times)),
        p95_ms=round(pct(times, 0.95)),
        max_ms=round(max(times)),
    )

elif MODE == "tp04":
    Signal = env["f3d.signal"].sudo()  # noqa: F821
    energy = Signal.search(["|", ("code", "like", "energy/%"), ("code", "like", "infra/%")], limit=500)
    others = Signal.search([("code", "not like", "energy/%"), ("code", "not like", "infra/%")], limit=500)
    for i in range(500 - len(others)):
        others |= Signal.create({"code": "tp/test/%d" % i, "name": "tp %d" % i, "kind": "gauge", "module": "telemetry"})
    codes = (energy.mapped("code") + others.mapped("code"))[:1000]  # 500 енергетики (R-13 перевизначення) + решта
    out.update(energy=len(energy), other=len(others))

    def run(ctx, offset):
        base = datetime.utcnow() - timedelta(seconds=600) + timedelta(seconds=offset)
        readings = [
            {"code": c, "ts": base.strftime("%Y-%m-%dT%H:%M:%SZ"), "value": 1000.0 + i % 7 + offset}
            for i, c in enumerate(codes)
        ]
        t0 = time.perf_counter()
        Signal.with_context(**ctx)._f3d_ingest(readings, src="collector")
        dt = time.perf_counter() - t0
        cr.rollback()
        return dt

    plain, full = [], []
    for i in range(6):
        plain.append(run({"f3d_energy_internal": True}, i * 2))  # без перевизначення M-15
        full.append(run({}, i * 2 + 1))  # з перевизначенням M-15
    out.update(
        readings=len(codes),
        plain_ms=round(statistics.median(plain) * 1000),
        override_ms=round(statistics.median(full) * 1000),
        increase_pct=round((statistics.median(full) / statistics.median(plain) - 1) * 100, 1),
    )

elif MODE in ("tp05", "tp06"):
    cr.execute("DELETE FROM f3d_energy_interval")
    cr.commit()
    zones = env["f3d.energy.tariff.zone"].sudo().search([]).ids or [None]  # noqa: F821
    older = MODE == "tp05"
    d_to, d_from = (400 + 1, 800) if older else (1, 400)
    t0 = time.perf_counter()
    cr.execute(
        """
        INSERT INTO f3d_energy_interval (meter_id, node_id, role, ts_start, ts_end, day, hour_local, e_start, e_end,
                                         kwh, kw_avg, quality, built_at, zone_id, price, cost)
        SELECT m.id, m.node_id, m.role, ts, ts + interval '15 minutes', ts::date, extract(hour from ts)::int,
               0, 1, 1.5, 6, 'measured', now() at time zone 'utc', (%s::int[])[1 + (extract(hour from ts)::int %% %s)],
               4.2, 6.3
        FROM f3d_energy_meter m
        CROSS JOIN generate_series(date_trunc('day', now() at time zone 'utc') - %s * interval '1 day',
                                   date_trunc('day', now() at time zone 'utc') - %s * interval '1 day', interval '15 minutes') ts
        WHERE m.active AND m.e_import_signal_id IS NOT NULL""",
        [[z for z in zones if z] or [0], max(1, len([z for z in zones if z])), d_from, d_to],
    )
    out["rows"] = cr.rowcount
    cr.commit()
    cr.execute("ANALYZE f3d_energy_interval")
    cr.commit()
    out["gen_s"] = round(time.perf_counter() - t0, 1)
    if MODE == "tp05":
        # Усі 2,6 М рядків старші за межу: планувальник слушно обирає Seq Scan (LIMIT 50000 без вибірковості).
        # Index Scan за ts_start перевіряємо на вибірковому предикаті (найстаріші 7 діб ≈ 1 % таблиці).
        cr.execute(
            "EXPLAIN SELECT id FROM f3d_energy_interval WHERE ts_start < now() - interval '400 days' LIMIT 50000"
        )
        out["plan_full"] = " | ".join(r[0].strip() for r in cr.fetchall())[:160]
        cr.execute("""EXPLAIN SELECT id FROM f3d_energy_interval
                      WHERE ts_start < (SELECT min(ts_start) + interval '7 days' FROM f3d_energy_interval) LIMIT 50000""")
        plan = "\n".join(r[0] for r in cr.fetchall())
        out["index_scan"] = "Index Scan" in plan or "Index Only Scan" in plan or "Bitmap Index Scan" in plan
        out["plan"] = plan[:240]
        runs, run_s = 0, []
        while True:
            t0 = time.perf_counter()
            Interval._cron_rotate()
            cr.commit()
            run_s.append(round(time.perf_counter() - t0, 1))
            runs += 1
            cr.execute("SELECT count(*) FROM f3d_energy_interval")
            left = cr.fetchone()[0]
            if not left or runs >= 5:
                break
        out.update(runs=runs, run_s=run_s, left=left)
    else:
        out["days"] = 400
        env.invalidate_all()  # noqa: F821
        times = []
        for _ in range(3):
            t0 = time.perf_counter()
            res = Interval._read_group([], groupby=["day:month", "zone_id"], aggregates=["kwh:sum", "cost:sum"])
            res2 = Interval._read_group([], groupby=["hour_local", "zone_id"], aggregates=["kwh:sum", "cost:sum"])
            times.append(time.perf_counter() - t0)
        out.update(groups=len(res), groups_hour=len(res2), read_group_s=[round(t, 2) for t in times])
    cr.execute("DELETE FROM f3d_energy_interval")
    cr.commit()

print("PERF " + json.dumps(out, default=str))
