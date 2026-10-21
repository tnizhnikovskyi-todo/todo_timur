"""Бренд «Завод 3D» → «3D Завод»: XML оновлює лише en_US, тож uk_UA-значення translatable-полів (назва клієнтської дії,
привілею й групи кіоска) лишилось би старим."""

from odoo import SUPERUSER_ID, api

NAMES = {
    "td_viewer3d.action_td_viewer": "3D Завод",
    "td_viewer3d.privilege_td_viewer": "3D Завод: переглядач",
    "td_viewer3d.group_td_kiosk": "3D Завод: кіоск",
}


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    langs = env["res.lang"].search([("active", "=", True)]).mapped("code")
    for xmlid, name in NAMES.items():
        record = env.ref(xmlid, raise_if_not_found=False)
        for lang in langs if record else ():
            record.with_context(lang=lang).write({"name": name})
