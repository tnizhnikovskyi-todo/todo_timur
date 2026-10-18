"""Міграція 19.0.1.0.0 (W3_SPEC 5.5, воркер A): `resource_id = el`, `mode = 'counter'` у наявних лічильників, сигнали й
джерела, демо-точки й лічильники, реактивні сигнали вводів. Увесь код — у `hooks` (ідемпотентний).
"""

from odoo import SUPERUSER_ID, api

from odoo.addons.td_energy_resources import hooks


def migrate(cr, version):
    hooks._run(api.Environment(cr, SUPERUSER_ID, {}))
