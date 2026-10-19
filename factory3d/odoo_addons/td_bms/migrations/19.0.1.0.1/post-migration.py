"""Міграція 19.0.1.0.1: сигнали КГУ (тепло `infra/chp/heat_kw`, електрична потужність), мережі й пожежі — у баланс.

У базах, де `td_energy` встановлено після `td_bms`, `post_init_hook` цих сигналів не бачив, і баланс рахував тепло КГУ
за проєктним значенням (50 %) навіть при зупиненій установці. Заповнюються лише порожні поля; ідемпотентно.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    written = env["td.bms.heat.balance"]._td_bms_link_optional()
    _logger.info("td_bms: міграція 19.0.1.0.1, сигнали балансу: %s", written)
