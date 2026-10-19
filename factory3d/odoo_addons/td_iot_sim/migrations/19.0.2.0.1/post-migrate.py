"""S-2/S-3: params пристроїв, unit 96 для T1/T2, сигнали PV-INV-n на похідних інверторах, пасивні FL-6/SMOKE-VENTS.

Ті самі кроки реєстру, що й `post_init_hook` (без перерахунку `read_enabled`); вони ідемпотентні: `params` пишуться лише
порожні, пристрої й сигнали за ключем `code` не дублюються.
"""
import logging

from odoo import SUPERUSER_ID, api
from odoo.addons.td_iot_sim.hooks import refresh_registry

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Device = env['td.sim.device'].sudo()
    before = Device.search_count([('params', '!=', False)])
    refresh_registry(env)
    _logger.info("td_iot_sim: post-migrate з %s: пристроїв із params %d → %d",
                 version, before, Device.search_count([('params', '!=', False)]))
