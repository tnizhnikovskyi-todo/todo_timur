"""DEC-20: блокування рядків без очікування для кронів, що пишуть спільні рядки (сигнали, джерела, колектори).

Паралельна транзакція (push колектора, інший крон) — не помилка коду. Рядок, зайнятий нею, або змінений нею після знімка
REPEATABLE READ поточної транзакції, пропускається; його опрацює наступний запуск крону (через хвилину).
"""

import logging

from psycopg2 import errors as pg_errors

from odoo.tools import SQL

_logger = logging.getLogger(__name__)

# зайнятий рядок (`NOWAIT`), змінений після знімка (`SerializationFailure`), взаємне блокування
CONTENTION_ERRORS = (pg_errors.SerializationFailure, pg_errors.LockNotAvailable, pg_errors.DeadlockDetected)


def lock_skip_locked(records):
    """`SELECT … FOR UPDATE SKIP LOCKED` за зростанням id; повертає підмножину `records`, яку вдалося заблокувати.

    Стан повернених записів свіжий з бази (кеш скинуто). У REPEATABLE READ `FOR UPDATE` кидає `SerializationFailure`
    і на вільному рядку, який інша транзакція встигла змінити й закомітити після знімка поточної, — тоді пачка
    блокується по одному рядку (кожен у власному savepoint без flush), а змінені пропускаються.
    SQL блокування виконується з `log_exceptions=False`: конкуренція обробляється тут, «bad query» в лог не потрібен.
    """
    if not records.ids:
        return records
    cr = records.env.cr
    table = SQL.identifier(records._table)

    def query(ids):
        return SQL("SELECT id FROM %s WHERE id IN %s ORDER BY id FOR UPDATE SKIP LOCKED", table, tuple(ids))

    try:
        with cr.savepoint(flush=False):
            cr.execute(query(records.ids), log_exceptions=False)
            locked = [row[0] for row in cr.fetchall()]
    except CONTENTION_ERRORS:
        locked = []
        for rec_id in sorted(records.ids):
            try:
                with cr.savepoint(flush=False):
                    cr.execute(query([rec_id]), log_exceptions=False)
                    locked.extend(row[0] for row in cr.fetchall())
            except CONTENTION_ERRORS:
                _logger.debug("%s #%s: змінено паралельно, блокування пропущено", records._name, rec_id)
    records.invalidate_recordset()
    return records.browse(locked)
