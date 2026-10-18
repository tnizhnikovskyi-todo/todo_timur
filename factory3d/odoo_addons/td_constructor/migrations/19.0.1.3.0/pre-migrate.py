"""19.0.1.3.0 (S2): довідники зони (10 функцій, 4 атрибути) тепер у `data/td_term_data.xml`.

До цієї версії терміни створювала лише перша відповідь API-12 (без xmlid). У наявних базах вони можуть уже бути:
прив'язуємо їх до xmlid до завантаження даних модуля, інакше запис із файлу порушив би унікальність (тип, ключ).
Нічого не створює й не змінює в самих термінах (назви й кольори, змінені користувачем, лишаються). Ідемпотентно."""

import logging

_logger = logging.getLogger('odoo.addons.td_constructor.migrations')

ZONE_TERMS = {
    'zone_function': (
        'receiving',
        'quality',
        'quarantine',
        'storage',
        'picking',
        'packing',
        'shipping',
        'scrap',
        'returns',
        'wip',
    ),
    'zone_attr': ('temp', 'hazmat', 'valuable', 'long'),
}


def migrate(cr, version):
    bound = 0
    for term_type, keys in ZONE_TERMS.items():
        cr.execute("SELECT id, key FROM td_term WHERE term_type = %s AND key = ANY(%s)", (term_type, list(keys)))
        for res_id, key in cr.fetchall():
            cr.execute(
                """
                INSERT INTO ir_model_data (module, name, model, res_id, noupdate)
                VALUES ('td_constructor', %s, 'td.term', %s, TRUE)
                ON CONFLICT (module, name) DO NOTHING
                """,
                ('term_%s_%s' % (term_type, key), res_id),
            )
            bound += cr.rowcount
    _logger.info("td_constructor 19.0.1.3.0: до xmlid прив'язано %d наявних термінів зони", bound)
