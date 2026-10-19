"""Наповнення бази стенда (DEPLOY_TEST п. 1–3 у середовищі без копії демо-бази).

Запуск (через stand.sh seed): ``odoo-bin shell -d <db> < seed_odoo.py``. Створює обладнання з кодами `td_code`
(у демо вони з'являються після міграції td_factory3d), команду «Служба головного механіка», 26 сигналів рівня 0,
яких немає без `x_f3d_signal` (з каталогу `td.sim.signal`), і повторює кроки 3–4 міграції (каталог + CT-11) та
лічильники ТО (крок 8). Ідемпотентний.
"""

from odoo.addons.td_telemetry import hooks

mech_name = "Служба головного механіка"
Team = env["maintenance.team"]  # noqa: F821
team = Team.search([("name", "=", mech_name)], limit=1) or Team.create({"name": mech_name})
env["ir.config_parameter"].sudo().set_param("td.telemetry.default_team_id", str(team.id))  # noqa: F821

rows = list(hooks._catalog_rows(env))  # noqa: F821, SLF001
codes_eq = {"COMPRESSOR", "BOILER", "WATER", "RV-05", "DUST-1"}
for r in rows:
    parts = r["code"].split("/")
    if parts[0] == "equipment":
        codes_eq.add(parts[1])
    if r.get("equipment"):
        codes_eq.add(r["equipment"])
NAMES = {
    "COMPRESSOR": "Компресорна станція",
    "AIR-RING": "Пневмомагістраль",
    "DUST-1": "Аспірація",
    "BOILER": "Котельня Kalvis",
    "SPRINKLERS": "Спринклерна станція",
    "WATER": "Водомірний вузол",
    "RV-05": "Припливно-витяжна установка RV-05",
    "FL-C1": "Навантажувач (резерв) FL-C1",
}
Equip = env["maintenance.equipment"]  # noqa: F821
for code in sorted(codes_eq):
    eq = Equip.search_f3d(code)
    if not eq:
        Equip.create({"name": NAMES.get(code, code), "td_code": code, "maintenance_team_id": team.id})
    elif eq.name == code and code in NAMES:
        eq.write({"name": NAMES[code]})

Signal = env["td.signal"].sudo().with_context(active_test=False)  # noqa: F821
missing = [r["code"] for r in rows if not Signal.search_count([("code", "=", r["code"])])]
rep = Signal._td_import_sim_catalog(codes=missing, source_map=hooks.SOURCE_MAP, defaults={"origin": "sim_data"})
print("STAND seed: імпорт з каталогу iot_sim:", {k: (len(v) if isinstance(v, list) else v) for k, v in rep.items()})
print("STAND seed: signals_catalog:", hooks.signals_catalog(env))  # noqa: F821

# Пороги рівня 0 (у демо-базі приходять з x_f3d_signal; тут — із колонки `thresholds` каталогу iot_sim, SPEC §13.2)
LEVEL0 = {
    "equipment/COMPRESSOR/pressure_bar": {
        "alarm_low": 6.0,
        "alarm_low_on": True,
        "decimals": 1,
        "alarm_title": "Компресорна станція: тиск {value} бар при нормі від {threshold}",
    },
    "equipment/AIR-RING/pressure_bar": {
        "alarm_low": 6.0,
        "alarm_low_on": True,
        "decimals": 1,
        "hysteresis": 0.1,
        "min_duration_s": 30,
        "alarm_title": "Пневмомагістраль: тиск {value} бар при нормі від {threshold}",
    },
    "equipment/SPRINKLERS/pressure_bar": {
        "alarm_low": 6.5,
        "alarm_low_on": True,
        "decimals": 1,
        "hysteresis": 0.1,
        "min_duration_s": 30,
        "alarm_title": "Спринклери: тиск {value} бар при нормі від {threshold}",
    },
    "equipment/DUST-1/filter_dp_kpa": {
        "alarm_high": 1.8,
        "alarm_high_on": True,
        "decimals": 1,
        "hysteresis": 0.036,
        "min_duration_s": 0,
        "alarm_title": "Заміна фільтрів: перепад тиску {value} кПа при нормі до {threshold}",
    },
    "energy/transformers/T1/temp_c": {"alarm_high": 140.0, "alarm_high_on": True, "decimals": 1, "hysteresis": 2.0},
    "energy/transformers/T2/temp_c": {"alarm_high": 140.0, "alarm_high_on": True, "decimals": 1, "hysteresis": 2.0},
}
for _code, _vals in LEVEL0.items():
    _sig = Signal.search([("code", "=", _code)], limit=1)
    if _sig and not _sig.alarm_low_on and not _sig.alarm_high_on:
        _sig.write(_vals)
        print("STAND seed: пороги рівня 0:", _code)
print("STAND seed: sim_catalog:", hooks.sim_catalog(env))  # noqa: F821
print("STAND seed: meters:", hooks.meters(env))  # noqa: F821
# Додаток C.4: відкрита планова заявка «ТО на 18 000 мотогодин» COMPRESSOR, прив'язана до лічильника (ТК-13)
comp = Equip.search_f3d("COMPRESSOR")
hsig = Signal.search([("code", "=", "equipment/COMPRESSOR/hours")], limit=1)
Req = env["maintenance.request"].sudo().with_context(mail_notrack=True, tracking_disable=True)  # noqa: F821
if comp and hsig and not comp.td_meter_request_id:
    req = Req.search([("equipment_id", "=", comp.id), ("name", "=", "ТО на 18 000 мотогодин")], limit=1) or Req.create(
        {
            "name": "ТО на 18 000 мотогодин",
            "equipment_id": comp.id,
            "maintenance_type": "preventive",
            "maintenance_team_id": team.id,
        }
    )
    req.write({"td_signal_id": hsig.id, "td_origin": "meter", "td_threshold": 18000.0})
    comp.with_context(mail_notrack=True).write({"td_meter_request_id": req.id})
    print("STAND seed: заявка ТО COMPRESSOR", req.id)

# Стенд: емулятор не вміє слати токен (лише секрет у URL), тому token_ref джерела HTTP-PUSH на стенді знімається
http = env["td.source"].sudo().search([("code", "=", "HTTP-PUSH")])  # noqa: F821
if http and "token_ref" in (http.params or {}):
    http.write({"params": {k: v for k, v in http.params.items() if k != "token_ref"}})
    print("STAND seed: HTTP-PUSH без token_ref")
env.cr.commit()  # noqa: F821
print("STAND seed: signals", Signal.search_count([]), "bound", Signal.search_count([("source_id", "!=", False)]))
