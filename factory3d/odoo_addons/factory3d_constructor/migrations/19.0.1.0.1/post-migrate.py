"""19.0.1.0.1: публікація незміненого сіда має давати порожній план.

Старий сід (19.0.1.0.0) давав на незміненій площадці «Меблеве підприємство» план із десятками змін: створення
maintenance.equipment для об'єктів сцени, зведені паспорти замість справжніх, вид локацій, майданчик WASTE.
Тут посіяна площадка виправляється на місці (ідемпотентно) — лише поки вона в стані сіда (чернетка не змінена
відносно версії v1 «Імпорт із макета»): варіанти, параметри місць, знімок v1. Записи Odoo (обладнання, локації,
паспорти) не видаляються й не змінюються, крім службових полів зв'язку."""

import logging

from odoo import SUPERUSER_ID, api

from odoo.addons.factory3d_constructor.hooks import seed
from odoo.addons.factory3d_constructor.services.schemas import SCENE_ROLE_PREFIX

_logger = logging.getLogger('odoo.addons.factory3d_constructor.migrations')


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    # нове поле: усі наявні варіанти отримали умовчання «створювати», зведені варіанти сцени — вимикаємо
    scene = (
        env['f3d.equipment.variant']
        .with_context(active_test=False)
        .search([('create_equipment', '=', True)])
        .filtered(lambda v: (v.passport_id.role or '').startswith(SCENE_ROLE_PREFIX))
    )
    scene.write({'create_equipment': False})
    try:
        with cr.savepoint():
            report = seed.resync_site(env)
    except Exception:
        _logger.exception("Виправлення посіяної площадки не виконано; публікацію перевірте вручну")
        return
    _logger.info("factory3d_constructor 19.0.1.0.1: прапорців %d, %s", len(scene), report)
