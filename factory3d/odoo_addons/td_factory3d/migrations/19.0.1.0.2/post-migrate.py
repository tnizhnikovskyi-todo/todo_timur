"""Бренд «Завод 3D» → «3D Завод»: XML оновлює лише en_US, тож uk_UA-значення translatable-полів лишилось би старим."""

from odoo import SUPERUSER_ID, api

NEW_NAME = "3D Завод"
XMLIDS = (
    "td_factory3d.menu_td_root",
    "td_factory3d.privilege_td",
    "td_factory3d.module_category_factory3d",
)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    langs = env["res.lang"].search([("active", "=", True)]).mapped("code")
    for xmlid in XMLIDS:
        record = env.ref(xmlid, raise_if_not_found=False)
        for lang in langs if record else ():
            record.with_context(lang=lang).write({"name": NEW_NAME})
