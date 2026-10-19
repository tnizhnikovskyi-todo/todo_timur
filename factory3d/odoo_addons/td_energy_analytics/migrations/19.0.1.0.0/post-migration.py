"""Міграція 19.0.1.0.0 (W4_SPEC 5.4): ті самі кроки, що й `post_init_hook` (ідемпотентні).

Увесь код — у `hooks`: ділянки, карта вузлів, `alloc.product_id`.
"""

from odoo import SUPERUSER_ID, api

from odoo.addons.td_energy_analytics import hooks


def migrate(cr, version):
    hooks._run(api.Environment(cr, SUPERUSER_ID, {}))
