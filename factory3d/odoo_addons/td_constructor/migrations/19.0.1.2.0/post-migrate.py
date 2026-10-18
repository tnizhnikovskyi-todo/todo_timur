"""19.0.1.2.0 (S1): тип місця `floor_spot` («Місце на підлозі») з'являється у шарів «Склади» наявних площадок.

Нова площадка отримує `floor_spot` у дозволених типах шару складів (`td.site._f3d_init_blank`); наявні шари, створені
раніше, мають старий список (pallet_rack, cantilever, shelf, floor_stack) — додаємо термін, інакше нове місце на
підлозі було б недоступне в цих шарах. Шари з порожнім списком (дозволено всі типи) і шари інших видів не змінюються.
Ідемпотентно: термін, що вже є в списку, не додається вдруге. Чернетка площадки не позначається зміненою."""

import logging

from odoo import SUPERUSER_ID, Command, api

_logger = logging.getLogger('odoo.addons.td_constructor.migrations')

TERM_KEY = 'floor_spot'


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    term = env['td.term'].search([('term_type', '=', 'slot_type'), ('key', '=', TERM_KEY)], limit=1)
    if not term:
        _logger.warning("td_constructor 19.0.1.2.0: довідник типів місць не містить «%s»; шари не змінено", TERM_KEY)
        return
    layers = (
        env['td.layer']
        .with_context(active_test=False, f3d_no_touch=True)
        .search([('kind', '=', 'storage'), ('allowed_slot_type_ids', '!=', False)])
        .filtered(lambda layer: term not in layer.allowed_slot_type_ids)
    )
    for layer in layers:
        layer.allowed_slot_type_ids = [Command.link(term.id)]
    _logger.info("td_constructor 19.0.1.2.0: «%s» додано в дозволені типи %d шарів складів", TERM_KEY, len(layers))
