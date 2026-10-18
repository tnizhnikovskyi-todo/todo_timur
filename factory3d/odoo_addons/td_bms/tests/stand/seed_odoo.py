# ruff: noqa: E501, F821  (env — глобальна змінна odoo shell)
"""Наповнення бази стенда bms (запуск через stand.sh seed: odoo-bin shell). Ідемпотентно: команда «Служба головного
механіка», календар «Цілодобово (ТК)» (7 × 00:00–24:00) і «Без робочого часу (ТК)» (calendar_id ставить сам тест), параметри затримок §13.2, realarm_cooldown_s=60."""

from odoo.addons.td_bms import hooks  # noqa: E402

ICP = env["ir.config_parameter"].sudo()  # noqa: F821
Team = env["maintenance.team"]  # noqa: F821
team = Team.search([("name", "=", "Служба головного механіка")], limit=1) or Team.create(
    {"name": "Служба головного механіка"}
)
ICP.set_param("td.telemetry.default_team_id", str(team.id))
Cal = env["resource.calendar"]  # noqa: F821


def calendar(name, intervals):
    cal = Cal.search([("name", "=", name)], limit=1)
    if not cal:
        cal = Cal.create({"name": name, "attendance_ids": [(5, 0, 0)] + intervals})
    return cal


full = calendar(
    "Цілодобово (ТК)",
    [(0, 0, {"name": f"d{d}", "dayofweek": str(d), "hour_from": 0.0, "hour_to": 24.0}) for d in range(7)],
)
none = calendar("Без робочого часу (ТК)", [])
for key in ("light_check_delay_min", "hvac_check_delay_min", "cold_delay_min", "heat_deficit_delay_min"):
    ICP.set_param(f"td.bms.{key}", "1")
ICP.set_param("td.telemetry.realarm_cooldown_s", "60")
# Обладнання з td_code (у демо-базі воно є після міграції td_factory3d; на чистій базі стенда — створюємо тут)
Equip = env["maintenance.equipment"]  # noqa: F821
codes = {"BOILER", "CHP"}
for model in ("td.bms.light.group", "td.bms.light.panel", "td.bms.hvac.unit"):
    codes |= set(env[model].with_context(active_test=False).search([]).mapped("code"))  # noqa: F821
for r in hooks._csv_rows():  # noqa: SLF001
    if r.get("equipment"):
        codes.add(r["equipment"])
for code in sorted(codes):
    if not Equip.search_f3d(code):
        Equip.create({"name": code, "td_code": code, "maintenance_team_id": team.id})
rep = hooks.run_install(env)  # повторна установка даних: прив'язка equipment_id (A-04, ідемпотентна)
print("STAND seed: equipment", len(codes), "install", rep.get("state"))
print("STAND seed: team", team.id, "calendars", full.id, none.id)  # noqa: F821
env.cr.commit()  # noqa: F821
