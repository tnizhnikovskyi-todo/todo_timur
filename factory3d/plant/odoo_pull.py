"""Живі дані з Odoo 19 для 3D-переглядача (XML-RPC, лише читання).

Розкладка заводу (комірки, ворота, маршрути, енергетика, пожежна безпека) — як і раніше з моделі
(plant/odoo_demo.py), а стан документів береться з бази, куди демо залив plant/odoo_push.py:
приймання й відвантаження (стан, прийнято/зібрано по рядках, ворота), виробничі замовлення й робочі
завдання (стан, час роботи, зупинка робочого центру), залишки по комірках, замовлення клієнтів і
постачальникам, контроль якості, заявки на ТО. Ланцюги «від фури до клієнта» перераховуються вже з
живих даних, і на них проганяється plant/cycle_check.py.

Запуск (доступи — зі змінних середовища, див. plant/odoo_rpc.py):
    python3 -m plant.odoo_pull dist/odoo_demo.json
або збірка переглядача з живими даними:
    python3 build_scene.py --embed --live dist
"""
import json
import sys
from datetime import datetime
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from .odoo_demo import NOW, Demo, ts
from .odoo_rpc import Odoo, key

TZ = ZoneInfo("Europe/Kyiv")
PICK_STATE = {"confirmed": "waiting", "waiting": "waiting", "assigned": "assigned", "done": "done",
              "draft": "draft", "cancel": "cancel"}
MO_STATE = {"to_close": "progress"}
MR_STAGES = ["Новий", "В роботі", "Відремонтовано", "Брак"]


def local(s):
    """Рядок UTC з Odoo → '2026-10-12 10:30' за Києвом."""
    if not s:
        return None
    dt = datetime.strptime(s[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=ZoneInfo("UTC"))
    return dt.astimezone(TZ).strftime("%Y-%m-%d %H:%M")


def minutes_until(start, end, now):
    a = datetime.strptime(start[:19], "%Y-%m-%d %H:%M:%S")
    b = datetime.strptime(end[:19], "%Y-%m-%d %H:%M:%S") if end else now
    return max(0.0, (b - a).total_seconds() / 60)


class LiveDemo(Demo):
    """Той самий збирач даних, але після логістики стан документів підміняється живим з Odoo."""

    def __init__(self, o):
        super().__init__()
        self.o = o
        rows = o("ir.model.data", "search_read", [["module", "=", "factory3d"]], fields=["name", "res_id"])
        self.xid = {r["name"]: r["res_id"] for r in rows}
        prods = o("product.product", "search_read", [["default_code", "!=", False]], fields=["default_code"],
                  context={"active_test": False})
        self.code = {p["id"]: p["default_code"] for p in prods}
        self.stats = {}

    def build_logistics(self):
        super().build_logistics()
        self.sync_pickings()
        self.sync_production()
        self.sync_stock()
        self.sync_orders()

    # ------------------------------------------------------------ переміщення
    def sync_pickings(self):
        o = self.o
        rows = o("stock.picking", "search_read", [["state", "!=", "cancel"]],
                 fields=["name", "state", "scheduled_date", "date_done", "origin", "partner_id", "picking_type_id",
                         "picking_type_code", "x_dock", "x_vehicle", "x_truck", "location_dest_id"])
        moves = o("stock.move", "search_read", [["picking_id", "in", [r["id"] for r in rows]]],
                  fields=["picking_id", "product_id", "product_uom_qty", "quantity", "picked", "state"])
        lines = {}
        for m in moves:
            if m["state"] == "cancel":
                continue
            done = m["quantity"] if m["picked"] or m["state"] == "done" else 0
            lines.setdefault(m["picking_id"][0], []).append(dict(
                product=self.code.get(m["product_id"][0], m["product_id"][1]), qty=m["product_uom_qty"],
                qty_done=round(done, 2)))
        by_name = {p["name"]: p for p in self.pickings}
        added = 0
        for r in rows:
            ls = lines.get(r["id"], [])
            tot = sum(x["qty"] for x in ls) or 1
            vals = dict(state=PICK_STATE.get(r["state"], r["state"]),
                        scheduled_date=local(r["date_done"] if r["state"] == "done" else r["scheduled_date"]),
                        lines=ls, progress=round(sum(min(x["qty_done"], x["qty"]) for x in ls) / tot, 2))
            p = by_name.get(r["name"])
            if p:
                if p.get("state") == "waiting" and vals["state"] != "waiting" and p.get("note", "").startswith("Чекає"):
                    p["note"] = ""
                p.update(vals)
                continue
            if r["picking_type_code"] not in ("incoming", "outgoing"):
                continue  # нові внутрішні переміщення без місця в 3D не показуємо
            added += 1
            self.pickings.append(dict(
                name=r["name"], picking_type=r["picking_type_id"][1].split(": ")[-1], type=r["picking_type_code"],
                partner=r["partner_id"][1] if r["partner_id"] else "", origin=r["origin"] or "",
                dock=r["x_dock"] or None, truck=r["x_truck"] or None,
                location_dest=r["location_dest_id"][1] if r["location_dest_id"] else None, **vals))
        self.stats["pickings"] = len(rows)
        self.stats["pickings_new"] = added

    # ------------------------------------------------------------ виробництво
    def sync_production(self):
        o = self.o
        mos = {r["name"]: r for r in o("mrp.production", "search_read", [],
                                       fields=["name", "state", "reservation_state", "product_qty"])}
        wo_ids = {wid: self.xid.get(key("wo", wid)) for wid in self.workorders}
        rows = o("mrp.workorder", "search_read", [["id", "in", [i for i in wo_ids.values() if i]]],
                 fields=["state", "duration_expected", "date_start", "date_finished", "working_state",
                         "workcenter_id"])
        logs = o("mrp.workcenter.productivity", "search_read", [["workorder_id", "in", [r["id"] for r in rows]]],
                 fields=["workorder_id", "date_start", "date_end"])
        # демо-годинник: відкриті таймери рахуємо до демо-часу, а не до «зараз», інакше за ніч усе «добіжить»
        now_utc = NOW.replace(tzinfo=TZ).astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
        worked, first, last = {}, {}, {}
        for lg in logs:
            k = lg["workorder_id"][0]
            worked[k] = worked.get(k, 0) + minutes_until(lg["date_start"], lg["date_end"], now_utc)
            first[k] = min(first.get(k, lg["date_start"]), lg["date_start"])
            if lg["date_end"]:
                last[k] = max(last.get(k, lg["date_end"]), lg["date_end"])
        byid = {r["id"]: r for r in rows}
        for mo in self.productions:
            r = mos.get(mo["name"])
            if not r:
                continue
            mo["state"] = MO_STATE.get(r["state"], r["state"])
            mo["qty"] = r["product_qty"]
            if r["reservation_state"] == "confirmed" and mo["state"] == "confirmed":
                mo["reservation_state"] = "waiting"
            else:
                mo.pop("reservation_state", None)
            prev = "done"
            for i, wid in enumerate(mo["workorders"]):
                w = self.workorders[wid]
                ow = byid.get(wo_ids.get(wid))
                if not ow:
                    continue
                st = ow["state"]
                if st in ("ready", "blocked"):  # як у демо: наступне за поточним — «готове», далі — «очікує»
                    st = "waiting" if (i == 0 and mo.get("reservation_state")) else \
                        "ready" if prev in ("done", "progress") else "pending"
                prev = st
                mins = worked.get(ow["id"], 0)
                w.update(state=st, duration=round(mins),
                         duration_expected=round(ow["duration_expected"]))
                # час — з журналу роботи (mrp.workcenter.productivity), як його бачить майстер
                if st in ("done", "progress"):
                    w["date_start"] = local(first.get(ow["id"]) or ow["date_start"])
                if st == "done":
                    w.update(progress=1.0, date_finished=local(last.get(ow["id"]) or ow["date_finished"]))
                    w.pop("date_planned_finished", None)
                elif st == "progress":
                    prog = min(0.99, mins / max(1, ow["duration_expected"]))
                    w["progress"] = round(prog, 2)
                else:
                    w["progress"] = 0.0
                    for f in ("date_start", "date_finished", "duration", "date_planned_finished"):
                        w.pop(f, None)
                w["blocked"] = st == "progress" and ow["working_state"] == "blocked"
                if not w["blocked"]:
                    w.pop("blocked")
            ws = [self.workorders[x] for x in mo["workorders"]]
            mo["progress"] = round((sum(1 for x in ws if x["state"] == "done") +
                                    sum(x["progress"] for x in ws if x["state"] == "progress")) / len(ws), 2)
        wcs = {r["code"]: r for r in o("mrp.workcenter", "search_read", [], fields=["code", "working_state"])}
        for code, wc in self.workcenters.items():
            wos = [w for w in self.workorders.values() if w["workcenter"] == code]
            wc["current_workorder"] = next((w["id"] for w in wos if w["state"] == "progress"), None)
            wc["queue"] = [w["id"] for w in sorted(wos, key=lambda w: (w["state"] != "ready", w["production"]))
                           if w["state"] in ("ready", "waiting", "pending")][:8]
            live = wcs.get(code)
            if live:
                wc["working_state"] = live["working_state"]
                if live["working_state"] == "blocked":
                    wc["status"] = "stop"
                elif wc["status"] == "stop":
                    wc["status"] = "work" if wc["current_workorder"] else "idle"
        self.stats["productions"] = len(mos)

    # ------------------------------------------------------------ залишки
    def sync_stock(self):
        """Залишки по комірках (за штрихкодом = код у сцені) з партіями й палетами з бази."""
        o = self.o
        root = self.xid.get("loc_wh") or self.xid.get("loc_root")
        locs = o("stock.location", "search_read", [["id", "child_of", root], ["barcode", "!=", False]],
                 fields=["barcode"])
        code_of = {r["id"]: r["barcode"] for r in locs}
        quants = o("stock.quant", "search_read", [["location_id", "in", list(code_of)], ["quantity", "!=", 0]],
                   fields=["location_id", "product_id", "quantity", "reserved_quantity", "lot_id", "package_id"])
        live = {}
        for q in quants:
            p = self.code.get(q["product_id"][0])
            if p:
                live.setdefault(code_of[q["location_id"][0]], []).append(dict(
                    product=p, qty=round(q["quantity"], 2), reserved=round(q["reserved_quantity"], 2),
                    lot=q["lot_id"][1] if q["lot_id"] else None,
                    package=q["package_id"][1] if q["package_id"] else None))
        known = set(code_of.values())
        for code, loc in self.locations.items():
            if code not in known:
                continue
            extra = {}  # що знає лише модель: для якого документа стос, карантин, приймання
            for q in loc["quants"]:
                extra.setdefault(q["product"], {k: v for k, v in q.items()
                                                if k not in ("product", "qty", "reserved", "lot", "package")})
            new = []
            rows = live.get(code, [])
            for p in {q["product"] for q in rows}:  # без партій і палет, кількість та сама — розбивка з моделі
                mine = [q for q in rows if q["product"] == p]
                demo = [q for q in loc["quants"] if q["product"] == p]
                if len(demo) > 1 and not any(q["lot"] or q["package"] for q in mine) and \
                        abs(sum(q["qty"] for q in mine) - sum(q["qty"] for q in demo)) < 1e-6:
                    new += demo
                    rows = [q for q in rows if q["product"] != p]
            for q in sorted(rows, key=lambda x: (x["product"], x["package"] or "", x["lot"] or "")):
                item = {"product": q["product"], "qty": q["qty"], **extra.get(q["product"], {})}
                for f in ("lot", "package", "reserved"):
                    if q[f]:
                        item[f] = q[f]
                new.append(item)
            loc["quants"] = new
            if loc.get("kind") == "pallet_cell":
                loc["fill"] = min(1.0, len(new) / 2)
            elif loc.get("capacity"):
                loc["fill"] = min(1.0, sum(q["qty"] for q in new) / loc["capacity"])
            op = loc.get("orderpoint")
            if op:
                have = sum(q["qty"] for q in new if q["product"] == op["product"])
                loc["state"] = "out" if have <= 0 else "low" if have < op["min"] else "ok"
        self.stats["quants"] = len(quants)

    # ------------------------------------------------------------ замовлення, якість
    def sync_orders(self):
        o = self.o
        so = {r["name"]: r for r in o("sale.order", "search_read", [], fields=["name", "state", "amount_untaxed"])}
        for s in self.sale:
            if s["name"] in so:
                s["state"] = so[s["name"]]["state"]
                s["amount"] = so[s["name"]]["amount_untaxed"]
        po = {r["name"]: r for r in o("purchase.order", "search_read", [], fields=["name", "state"])}
        for p in self.purchase:
            if p["name"] in po:
                p["state"] = po[p["name"]]["state"]
        if o.has("quality.check"):
            qc = {r["name"]: r for r in o("quality.check", "search_read", [], fields=["name", "quality_state"])}
            for q in self.quality:
                if q["name"] in qc:
                    q["state"] = qc[q["name"]]["quality_state"]

    def sync_maintenance(self, data):
        o = self.o
        if not o.has("maintenance.request"):
            return
        stages = [s["id"] for s in o("maintenance.stage", "search_read", [], fields=["id"], order="sequence")]
        ids = {self.xid.get(key("mr", m["id"])): m for m in data["maintenance_requests"]}
        for r in o("maintenance.request", "search_read", [["id", "in", [i for i in ids if i]]],
                   fields=["stage_id", "priority", "schedule_date"]):
            m = ids[r["id"]]
            i = stages.index(r["stage_id"][0]) if r["stage_id"] and r["stage_id"][0] in stages else 0
            m["stage"] = MR_STAGES[min(i, len(MR_STAGES) - 1)]
            m["priority"] = r["priority"]
            if r["schedule_date"]:
                m["schedule_date"] = local(r["schedule_date"])

    def sync_signals(self, data):
        """Показники обладнання з модуля factory3d_iot_sim: x_code — шлях у даних переглядача
        (energy/consumers/SAW-1/p_now, equipment/FL-1/battery…); відсотки в моделі — частки."""
        o = self.o
        if not o.has("x_f3d_signal"):
            return
        rows = o("x_f3d_signal", "search_read", [["x_active", "=", True], ["x_code", "!=", False]],
                 fields=["x_code", "x_value", "x_unit", "x_mode", "x_charging", "x_updated", "x_state"])
        last = None
        for r in rows:
            *path, leaf = r["x_code"].split("/")
            node = data
            for k in path:
                node = node.get(k) if isinstance(node, dict) else None
                if node is None:
                    break
            if node is None:
                continue
            v = r["x_value"]
            node[leaf] = round(v / 100, 3) if r["x_unit"] == "%" else round(v, 2) if abs(v) < 20 else round(v, 1)
            if r["x_mode"] == "drain" and "state" in node:
                node["state"] = "charging" if r["x_charging"] else "busy"
            if r["x_updated"] and (last is None or r["x_updated"] > last):
                last = r["x_updated"]
        t = data["infra"]["totals"]
        data["energy"]["totals"].update(pv_kw=t["pv_now"], chp_kw=t["chp_kw"])
        data["meta"]["iot"] = {"source": "імітація датчиків (модуль factory3d_iot_sim)", "signals": len(rows),
                               "alarms": sum(r["x_state"] == "тривога" for r in rows), "updated": local(last)}

    def build(self):
        data = super().build()
        self.sync_maintenance(data)
        self.sync_signals(data)
        host = urlparse(self.o.url).hostname
        data["meta"].update(
            source=f"Odoo {self.o.version['server_serie']} · {host}", database=self.o.db, live=True,
            company=self.o("res.company", "read", [1], ["name"])[0]["name"],
            pulled_at=datetime.now(TZ).strftime("%Y-%m-%d %H:%M"),
            note=f"Живі дані з бази (XML-RPC, лише читання): {self.stats.get('pickings', 0)} переміщень, "
                 f"{self.stats.get('productions', 0)} виробничих замовлень, {self.stats.get('quants', 0)} залишків. "
                 f"Демо-годинник зупинено на {ts(NOW)} — від нього рахуються таймери робочих завдань."
                 + (f" Показники обладнання — {data['meta']['iot']['signals']} сигналів імітації IoT, оновлено "
                    f"{data['meta']['iot']['updated']}." if data["meta"].get("iot") else ""))
        return data


def generate():
    return LiveDemo(Odoo()).build()


if __name__ == "__main__":
    from .cycle_check import check
    out = sys.argv[1] if len(sys.argv) > 1 else "odoo_demo.json"
    data = generate()
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    issues = check(data)
    print(out, data["meta"]["note"])
    print("cycle_check:", "OK" if not issues else f"{len(issues)} проблем\n  " + "\n  ".join(issues))
