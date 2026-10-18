# ruff: noqa
"""Вимірювання всередині Odoo (``odoo-bin shell``, stdin) для ТП-03/ТП-04: дані — 130 000 подій, генерація SQL.

Не імпортується pytest і не потрапляє в Odoo test-tags. Результат — один рядок ``PERF {json}`` у stdout.
Режим — змінна PERF_MODE: ``collect`` (ТП-03), ``gc`` (ТП-04).
"""
import json
import os
import sys
import time
import types
from datetime import datetime, timedelta
from unittest.mock import patch

MODE = os.environ["PERF_MODE"]
N = int(os.environ.get("PERF_N", "130000"))
cr = env.cr  # noqa: F821  (env надає odoo shell)
server = env["td.access.server"].search([], limit=1)
door = env["td.access.door"].search([("code", "=", "TURN-1")], limit=1)
device = env["td.access.device"].search([("code", "=", "ACR-IN")], limit=1)
emps = env["hr.employee"].search([("barcode", "!=", False)], limit=150)


def gen(prefix, start, step_s):
    """N подій від ``start`` з кроком ``step_s`` секунд (execute_values-еквівалент: INSERT ... generate_series)."""
    cr.execute("""
        INSERT INTO td_access_event (server_id, company_id, biostar_id, ts, server_ts, received_at, code, event_type,
            direction, process_state, attendance_action, device_id, door_id, employee_id)
        SELECT %(srv)s, %(co)s, %(pfx)s || g, %(start)s::timestamp + (g * %(step)s) * interval '1 second',
            %(start)s::timestamp + (g * %(step)s) * interval '1 second', now() at time zone 'utc',
            4102, 'pass', CASE WHEN g %% 2 = 0 THEN 'in' ELSE 'out' END, 'done', 'none', %(dev)s, %(door)s,
            (%(emps)s::int[])[1 + (g %% %(n_emp)s)]
        FROM generate_series(1, %(n)s) g
        ON CONFLICT DO NOTHING""", {
        "srv": server.id, "co": server.company_id.id, "pfx": prefix, "start": start, "step": step_s,
        "dev": device.id, "door": door.id, "emps": emps.ids, "n_emp": len(emps), "n": N})
    cr.commit()
    cr.execute("ANALYZE td_access_event")
    cr.commit()


out = {"events_before": env["td.access.event"].search_count([])}
now = datetime.utcnow()
if MODE == "collect":
    t0 = time.perf_counter()
    gen("PERF-", (now - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S"), 20)   # 30 діб по ~4 300 подій/добу ≈ 130 000
    out["gen_s"] = round(time.perf_counter() - t0, 2)
    out["events_total"] = env["td.access.event"].search_count([])
    # заглушка viewer.tools.payload, якщо модуля немає (як у test_viewer_provider)
    try:
        from odoo.addons.td_viewer3d.tools import payload  # noqa
        ctx_mgr = patch.dict(sys.modules, {})
    except ImportError:
        mods = {}
        for nm in ("odoo.addons.td_viewer3d", "odoo.addons.td_viewer3d.tools"):
            mods[nm] = types.ModuleType(nm)
            mods[nm].__path__ = []
        leaf = types.ModuleType("odoo.addons.td_viewer3d.tools.payload")
        def deep_merge(dst, src):
            for k, v in src.items():
                if isinstance(v, dict) and isinstance(dst.get(k), dict):
                    deep_merge(dst[k], v)
                else:
                    dst[k] = v
            return dst
        leaf.deep_merge = deep_merge
        mods["odoo.addons.td_viewer3d.tools.payload"] = leaf
        ctx_mgr = patch.dict(sys.modules, mods)
    user = env["res.users"].search([("login", "=", "stand_user_f3d")], limit=1) or env.user
    provider = env["td.viewer.provider.access"].with_user(user)
    payload_ = {"employees": {e.td_code: {"name": e.name, "present": False} for e in emps if e.td_code},
                "zones": {z.td_code: {"name": z.name} for z in env["td.zone"].search([])}}
    times = []
    with ctx_mgr:
        for _ in range(7):
            t0 = time.perf_counter()
            provider._f3d_viewer_collect(json.loads(json.dumps(payload_)), {"now": now, "today": now.strftime("%Y-%m-%d")})
            times.append((time.perf_counter() - t0) * 1000)
    out["collect_ms"] = [round(x, 1) for x in times]
    zones = env["td.zone"].search([])
    times = []
    for _ in range(7):
        zones.invalidate_recordset(["td_people_now"])
        t0 = time.perf_counter()
        zones.mapped("td_people_now")
        times.append((time.perf_counter() - t0) * 1000)
    out["zones"] = len(zones)
    out["people_now_ms"] = [round(x, 1) for x in times]
    cr.execute("EXPLAIN (FORMAT JSON) SELECT id FROM td_access_event WHERE ts >= %s ORDER BY ts DESC",
               [now.strftime("%Y-%m-%d") + " 00:00:00"])
    plan = json.dumps(cr.fetchone()[0])
    out["explain_today_index"] = "Index" in plan or "Bitmap" in plan
    out["explain_nodes"] = sorted({w for w in ("Index Scan", "Index Only Scan", "Bitmap Index Scan", "Seq Scan")
                                   if w in plan})
elif MODE == "gc":
    keep = int(env["ir.config_parameter"].get_param("td.access.keep_days") or 90)
    gen("OLD-", (now - timedelta(days=keep + 200)).strftime("%Y-%m-%d %H:%M:%S"), 100)  # усе старше keep_days
    cr.execute("SELECT count(*) FROM td_access_event WHERE ts < now() at time zone 'utc' - %s * interval '1 day'", [keep])
    out["old_before"] = cr.fetchone()[0]
    registry = env.registry
    if not hasattr(registry, "in_test_mode"):
        # ДЕФЕКТ модуля: Odoo 19 не має Registry.in_test_mode() (models/td_access_event.py:520, td_access_server.py:162),
        # ротація/крони падають з AttributeError. Спершу — як є (фіксуємо наслідок), далі — з тимчасовою підміною.
        out["defect_in_test_mode"] = True
        env["td.access.event"]._cron_housekeeping()
        cr.commit()
        cr.execute("SELECT count(*) FROM td_access_event WHERE ts < now() at time zone 'utc' - %s * interval '1 day'",
                   [keep])
        out["old_after_unpatched"] = cr.fetchone()[0]
        registry.in_test_mode = lambda: False
    t0 = time.perf_counter()
    env["td.access.event"]._cron_housekeeping()
    out["housekeeping_s"] = round(time.perf_counter() - t0, 2)
    cr.commit()
    cr.execute("SELECT count(*) FROM td_access_event WHERE ts < now() at time zone 'utc' - %s * interval '1 day'", [keep])
    out["old_after"] = cr.fetchone()[0]
    out["events_after"] = env["td.access.event"].search_count([])
print("PERF " + json.dumps(out))
