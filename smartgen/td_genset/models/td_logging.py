# Part of td_genset (ToDo). Підготовка до проду (08.10).
"""Логи без спаму для кроків cron, що працюють щохвилини.

Повторювана помилка з тим самим ключем (ретранслятор недоступний, збій кроку планувальника, ескалації …) пишеться
в лог як WARNING один раз, далі — DEBUG, з нагадуванням WARNING не частіше ніж раз на годину («триває N хв,
повторів: M»); відновлення — один запис INFO. Нормальна робота (знімок без змін) у лог нічого не пише.

Стан — у пам'яті процесу, окремо для кожної бази й ключа: після перезапуску сервера перша помилка знову WARNING;
кілька процесів cron (``workers`` > 0) дають не більше одного WARNING на процес. Час — ``fields.Datetime.now()``
(у тестах діє ``freezegun``).
"""
import logging
import threading
from datetime import timedelta

from odoo import fields

REMIND_EVERY = timedelta(hours=1)
_LOCK = threading.Lock()
_STATE = {}          # (dbname, key) → {'signature', 'since', 'logged_at', 'count'}


def log_failure(logger, env, key, signature, msg, *args, exc_info=False):
    """Помилка з ключем ``key``: WARNING уперше (або коли змінився ``signature`` — інший код/тип помилки), далі DEBUG,
    нагадування WARNING раз на ``REMIND_EVERY``. ``exc_info`` — лише для записів WARNING.

    :return: рівень, з яким записано повідомлення (``logging.WARNING`` або ``logging.DEBUG``).
    """
    now = fields.Datetime.now()
    slot = (env.cr.dbname, key)
    suffix, extra = '', ()
    with _LOCK:
        state = _STATE.get(slot)
        if state is None or state['signature'] != signature:
            since = state['since'] if state else now
            _STATE[slot] = {'signature': signature, 'since': since, 'logged_at': now, 'count': 1}
            level = logging.WARNING
        else:
            state['count'] += 1
            if now - state['logged_at'] >= REMIND_EVERY:
                state['logged_at'] = now
                level = logging.WARNING
                suffix = ' (триває %d хв, повторів: %d)'
                extra = (int((now - state['since']).total_seconds() // 60), state['count'])
            else:
                level = logging.DEBUG
    logger.log(level, msg + suffix, *(args + extra), exc_info=exc_info if level >= logging.WARNING else False)
    return level


def log_recovered(logger, env, key, msg, *args):
    """Успіх після помилок з ключем ``key``: один запис INFO «… — після N хв помилок (повторів: M)»; без попередніх
    помилок — нічого (нормальна робота лог не засмічує).

    :return: True, якщо до цього були помилки.
    """
    slot = (env.cr.dbname, key)
    with _LOCK:
        state = _STATE.pop(slot, None)
    if state is None:
        return False
    minutes = int((fields.Datetime.now() - state['since']).total_seconds() // 60)
    logger.info(msg + ' — після %d хв помилок (повторів: %d)', *(args + (minutes, state['count'])))
    return True


def reset_log_state(dbname=None):
    """Забути стан помилок (усіх баз або однієї) — для тестів."""
    with _LOCK:
        if dbname is None:
            _STATE.clear()
        else:
            for slot in [slot for slot in _STATE if slot[0] == dbname]:
                del _STATE[slot]
