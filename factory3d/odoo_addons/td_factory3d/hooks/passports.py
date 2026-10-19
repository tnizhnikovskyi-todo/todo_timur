"""Крок 6 post_init_hook: паспорти й складові на одиниці обладнання (SPEC §5.3, R-17)."""

import logging

from odoo import Command

from .codes import read_rows

_logger = logging.getLogger("odoo.addons.td_factory3d.hooks")


def link(env):
    """Роздати паспорти й складові за scene_equipment_codes.csv (код сцени → роль, components)."""
    Eq = env["maintenance.equipment"]
    passports = {p.role: p for p in env["td.equipment.passport"].with_context(active_test=False).search([])}
    res = {"linked": 0, "components": 0, "no_passport": 0}
    for row in read_rows("scene_equipment_codes.csv"):
        eq = Eq.search_f3d(row["code"])
        if not eq:
            continue
        role = row.get("role")
        if role:
            passport = passports.get(role)
            if not passport:
                _logger.warning("Паспорт для ролі %s (%s) не знайдено", role, row["code"])
            else:
                if eq.td_passport_id != passport:
                    eq.td_passport_id = passport
                res["linked"] += 1
        else:
            res["no_passport"] += 1
        roles = [r for r in (row.get("components") or "").split(";") if r]
        if roles:
            ids = [passports[r].id for r in roles if r in passports]
            if set(eq.td_component_passport_ids.ids) != set(ids):
                eq.td_component_passport_ids = [Command.set(ids)]
            res["components"] += len(ids)
    return res
