"""R-31 п. 6: демо-історія порталу (завдання, карти розкрою, показання стосів) для вже встановлених демо-баз.

Лише демо-база без жодного завдання порталу; на бойовій базі нічого не робить."""

from odoo import SUPERUSER_ID, api

from odoo.addons.td_machine_connect.tools.demo_portal import demo_gantry


def migrate(cr, version):
    demo_gantry(api.Environment(cr, SUPERUSER_ID, {}))
