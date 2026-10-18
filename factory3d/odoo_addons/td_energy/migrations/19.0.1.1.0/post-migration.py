"""W1-A: міграція 19.0.1.1.0 (W1_SPEC 5.4): сигнали й джерело SWB-CTRL, пороги cos φ, геометрія схеми, R-24 для подій.

Увесь код — у `hooks._migrate_w1` (ідемпотентний; ті самі функції викликає `post_init_hook`).
"""

from odoo import SUPERUSER_ID, api

from odoo.addons.td_energy import hooks


def migrate(cr, version):
    hooks._migrate_w1(api.Environment(cr, SUPERUSER_ID, {}))
