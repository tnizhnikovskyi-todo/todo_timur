"""post_init_hook моста (W3-B): `env["td.energy.point"]._td_bind_extra()` (R-B1) — теплові точки й лічильники з BMS."""

import logging

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    env = env(su=True, context=dict(env.context, tracking_disable=True))
    report = env["td.energy.point"]._td_bind_extra()
    _logger.info("td_energy_resources_bms: прив'язка тепла: %s", report)
