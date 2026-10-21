"""Бренд «Завод 3D» → «3D Завод»: назва клієнтської дії в uk_UA не оновилась би з XML (він пише лише en_US)."""

from odoo import SUPERUSER_ID, api

NEW_NAME = "3D Завод"


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    action = env.ref("td_viewer3d.action_td_viewer", raise_if_not_found=False)
    langs = env["res.lang"].search([("active", "=", True)]).mapped("code")
    for lang in langs if action else ():
        action.with_context(lang=lang).write({"name": NEW_NAME})
