"""Міграція 19.0.1.0.2: джерело тепла «КГУ» (`HEAT-CHP` + лічильник `HM-CHP` за `infra/chp/heat_kw`) у W3.

У базах, де `td_energy` встановлено після `td_bms`, баланс BMS не мав сигналу тепла КГУ, тому `_td_bind_extra` пропускав
`HM-CHP`. Спершу довантажуємо сигнали КГУ в баланс (тільки порожні поля), далі — ідемпотентна прив'язка тепла (R-B1).
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    env = env(su=True, context=dict(env.context, tracking_disable=True))
    env["td.bms.heat.balance"]._td_bms_link_optional()
    report = env["td.energy.point"]._td_bind_extra()
    _logger.info("td_energy_resources_bms: міграція 19.0.1.0.2, прив'язка тепла: %s", report)
