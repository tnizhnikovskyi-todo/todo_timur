"""Наповнення реєстру при `-u` з прототипу 19.0.1.0.0 → 19.0.2.0.0 (SPEC §5.3).

Odoo викликає `post_init_hook` лише при першому встановленні (`loading.py`: `update_operation == 'install'`),
тож на базі з прототипом `-u` лишав порожні реєстр пристроїв і каталог сигналів. Тут виконуються ті самі кроки 1–7;
вони ідемпотентні (ключі `code`), тому повторний запуск на базі, де реєстр уже наповнено, дублікатів не створює.
"""
import logging

from odoo import SUPERUSER_ID, api

from odoo.addons.factory3d_iot_sim.hooks import post_init_hook

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    devices = env['f3d.sim.device'].sudo().search_count([])
    signals = env['f3d.sim.signal'].sudo().search_count([])
    post_init_hook(env)
    _logger.info(
        "factory3d_iot_sim: post-migrate з %s: пристроїв %d → %d, сигналів %d → %d",
        version, devices, env['f3d.sim.device'].sudo().search_count([]),
        signals, env['f3d.sim.signal'].sudo().search_count([]))
