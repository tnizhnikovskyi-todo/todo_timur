"""ST-1: `store_period_s = 300` для сигналів стану верстатів, створених до виправлення CSV (SPEC Додаток C.2).

Записи сигналів `noupdate`, тож `-u` не підхоплює нове значення з `data/mc_signals.csv`. Оновлюються лише сигнали
зі значенням 0 (ручні правки лишаються); повторний запуск нічого не змінює.
"""

from odoo import SUPERUSER_ID, api

from odoo.addons.td_machine_connect.hooks import migrate_store_period


def migrate(cr, version):
    migrate_store_period(api.Environment(cr, SUPERUSER_ID, {}))
