"""Наповнення бази стенда до установки модуля (DEPLOY_TEST п. 1–2 у середовищі без копії демо-бази timur-o19demo).

Запуск: ``odoo-bin shell -d <db> < seed_pre.py`` (через ``stand.sh seed-pre``). Створює те, що в демо дає міграція
td_factory3d: 35 РЦ і обладнання з ``td_code`` (коди з ``data/mc_machines.csv`` модуля), операторів ``OP-*``,
календар (стенд: цілодобово 7 днів, щоб ТК не залежали від часу доби), служби, товари/партії/стоси ``PLT-*`` за
станом woodStore емулятора й дві специфікації для ТК-04/05/06. Ідемпотентний.
"""

import csv
import json
import os
import urllib.request

ROOT = os.environ.get("F3D_STAND_REPO", "/home/user/todo_timur")
CSV = f"{ROOT}/factory3d/odoo_addons/td_machine_connect/data/mc_machines.csv"
WS_KEY = os.environ.get("SIM_WOODSTORE_APIKEY", "ws-key-stand-0123456789")

Cal = env["resource.calendar"]  # noqa: F821
cal = Cal.search([("name", "=", "Стенд 24/7")], limit=1)
if not cal:
    att = [
        (0, 0, {"name": "Доба", "dayofweek": str(d), "hour_from": 0.0, "hour_to": 23.99, "day_period": "morning"})
        for d in range(7)
    ]
    cal = Cal.create(
        {"name": "Стенд 24/7", "tz": "Europe/Kyiv", "hours_per_day": 24, "attendance_ids": [(5, 0, 0)] + att}
    )

team = env["maintenance.team"].search([("name", "=", "Служба головного механіка")], limit=1)  # noqa: F821
team = team or env["maintenance.team"].create({"name": "Служба головного механіка"})  # noqa: F821
env["ir.config_parameter"].sudo().set_param("td.telemetry.default_team_id", str(team.id))  # noqa: F821

Eq, WC, Emp = env["maintenance.equipment"], env["mrp.workcenter"], env["hr.employee"]  # noqa: F821
rows = list(csv.DictReader(open(CSV, encoding="utf-8")))
for r in rows:
    code = r["code"]
    if not Eq.search_f3d(code):
        Eq.create({"name": "Верстат " + code, "td_code": code, "maintenance_team_id": team.id})
    if not WC.search_f3d(code):
        WC.create({"name": "Верстат " + code, "td_code": code, "resource_calendar_id": cal.id, "time_efficiency": 100})
    oc = r["operator_code"]
    if oc and not Emp.search_f3d(oc):
        Emp.create({"name": "Оператор " + oc, "td_code": oc, "barcode": oc.replace("-", "")})
if not Eq.search_f3d("GANTRY-1"):
    Eq.create({"name": "Портал woodStore", "td_code": "GANTRY-1", "maintenance_team_id": team.id})

# --- користувачі стенда: оператор (SAW-2), майстер, начальник складу ----------------------------------------------------
Users = env["res.users"].with_context(no_reset_password=True)  # noqa: F821


def user(login, xmlids):
    u = Users.search([("login", "=", login)], limit=1)
    if not u:
        gids = [env.ref(x).id for x in xmlids.split(",")]  # noqa: F821
        u = Users.create(
            {"name": login, "login": login, "password": login, "tz": "Europe/Kyiv", "group_ids": [(6, 0, gids)]}
        )
    return u


u_op = user("stand_op", "base.group_user,mrp.group_mrp_user,td_factory3d.group_td_user")
u_master = user("stand_master", "base.group_user,mrp.group_mrp_manager,td_factory3d.group_td_manager")
u_stock = user("stand_stock", "base.group_user,stock.group_stock_manager,td_factory3d.group_td_user")
if not Emp.search([("user_id", "=", u_op.id)]):
    saw2 = Emp.search_f3d("OP-SAW-2")
    if saw2:
        saw2.user_id = u_op
    else:
        Emp.create({"name": "stand_op", "user_id": u_op.id})
if not Emp.search([("user_id", "=", u_master.id)]):
    Emp.create({"name": "Майстер стенда", "user_id": u_master.id})

# --- товари, партії, стоси за станом woodStore -----------------------------------------------------------------------
req = urllib.request.Request("http://127.0.0.1:8082/api/v1/stacks", headers={"X-Api-Key": WS_KEY})
stacks = json.load(urllib.request.urlopen(req, timeout=10))
Product, Lot, Loc = env["product.product"], env["stock.lot"], env["stock.location"]  # noqa: F821
wh = env["stock.warehouse"].search([], limit=1)  # noqa: F821
company = env.company.id  # noqa: F821
prods = {}
cat = env["product.category"].search([("name", "=", "Плитні матеріали")], limit=1) or env["product.category"].create(  # noqa: F821
    {"name": "Плитні матеріали"}
)
for s in stacks:
    pc = s["product"]
    if not pc or pc in prods:
        continue
    thick = int("".join(ch for ch in pc.split("-")[0] if ch.isdigit()) or 16)
    p = Product.search([("default_code", "=", pc)], limit=1) or Product.create(
        {
            "name": f"{pc.split('-')[0][:3]} {thick} мм 2800×2070 ({pc})", "default_code": pc, "is_storable": True,
            "tracking": "lot", "categ_id": cat.id,
        }
    )  # fmt: skip
    prods[pc] = p
for s in stacks:
    loc = Loc.search([("td_code", "=", s["id"])], limit=1) or Loc.create(
        {
            "name": s["id"], "location_id": wh.lot_stock_id.id, "td_code": s["id"],
            "td_loc_kind": "stack", "td_capacity": s["max"],
        }
    )  # fmt: skip
    if s["product"] and not env["stock.quant"].search_count([("location_id", "=", loc.id)]):  # noqa: F821
        lot = Lot.search([("name", "=", s["lot"]), ("product_id", "=", prods[s["product"]].id)], limit=1) or Lot.create(
            {"name": s["lot"], "product_id": prods[s["product"]].id, "company_id": company}
        )
        env["stock.quant"]._update_available_quantity(prods[s["product"]], loc, s["qty"], lot_id=lot)  # noqa: F821

# --- специфікації для ТК-04/05/06 ---------------------------------------------------------------------------------------
board = prods.get("DSP18-ANT") or next(iter(prods.values()))


def finished(name, code, ops, comps):
    fg = Product.search([("default_code", "=", code)], limit=1) or Product.create(
        {"name": name, "default_code": code, "is_storable": True}
    )
    if not env["mrp.bom"].search_count([("product_tmpl_id", "=", fg.product_tmpl_id.id)]):  # noqa: F821
        env["mrp.bom"].create(  # noqa: F821
            {
                "product_tmpl_id": fg.product_tmpl_id.id, "product_qty": 1,
                "bom_line_ids": [(0, 0, {"product_id": p.id, "product_qty": q}) for p, q in comps],
                "operation_ids": [
                    (0, 0, {"name": "Операція " + c, "workcenter_id": WC.search_f3d(c).id, "time_mode": "manual",
                            "time_cycle_manual": cyc})
                    for c, cyc in ops
                ],
            }
        )  # fmt: skip


finished("Комод 4 шухляди", "BR-K4", [("SAW-1", 2.2)], [(board, 0.3)])
finished("Шухляда (складання)", "SLIDE-FG", [("SLIDE-1", 1.0)], [])
env.cr.commit()  # noqa: F821
print("STAND seed-pre: workcenters", WC.search_count([]), "equipment", Eq.search_count([]), "stacks", len(stacks))  # noqa: F821
