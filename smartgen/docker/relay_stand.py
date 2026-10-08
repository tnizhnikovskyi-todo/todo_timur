#!/usr/bin/env python3
"""Запуск эмулятора ретранслятора ``smartgen/tools/fake_relay.py`` для Docker-стенда td_genset.

Файл эмулятора не меняется: он подключается как модуль, и перед его ``main()`` стенд правит две вещи.

1. Номера (id) снимков, команд и сырых сообщений не начинаются с 1 ни после перезапуска контейнера
   ``relay``, ни после ``POST /_sim {"reset": true}``. Эмулятор держит всё в памяти, а Odoo забирает
   снимки по курсору (``GET /readings?since=<последний id>``) и пропускает уже сохранённые id: если бы
   нумерация начиналась заново, карточка «Стенд» не видела бы новых снимков, пока номера не перерастут
   старый курсор (часы и дни). Поэтому начальный id = секунды с 01.01.2026 × 4 (растёт быстрее, чем
   эмулятор выдаёт номера, и помещается в integer Postgres до 2043 года), а после ``reset`` номера
   продолжаются с уже выданных. Ограничение: ``/_sim {"advance": N}`` на много часов вперёд, а затем
   перезапуск контейнера могут дать номера меньше прежних — тогда ``docker compose down -v``.
2. В памяти хранится не больше 10 000 снимков (≈ 28 ч при снимке раз в 10 с, ≈ 150 МБ) вместо 50 000
   (≈ 750 МБ): Odoo забирает снимки раз в минуту, длинная история эмулятору не нужна.

Аргументы командной строки — как у ``fake_relay.py``, передаются ему без изменений, например:
    python3 relay_stand.py --host 0.0.0.0 --port 8081 --token dev-token-0123456789abcdefghij \\
        --snapshot-sec 10 --relay-version 1.1.1 --hostid 5354414E442D444F434B4552
``fake_relay.py`` ищется рядом с этим файлом (в контейнере оба лежат в ``/opt/relay``), затем в
``../tools`` (запуск из репозитория).
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.normpath(os.path.join(HERE, '..', 'tools'))]

import fake_relay  # noqa: E402

ID_EPOCH = 1767225600          # 2026-01-01T00:00:00Z
IDS_PER_SECOND = 4
KEEP_READINGS = 10000
ID_ATTRS = ('reading_id', 'raw_id', 'command_id')


def id_floor():
    """Наименьший id, с которого эмулятор продолжает нумерацию сейчас."""
    return max(1, int((time.time() - ID_EPOCH) * IDS_PER_SECOND))


def patch_relay():
    """Номера без повторов после перезапуска и reset; меньше снимков в памяти.

    :return: True — поправлено; False — внутренности fake_relay.py изменились, запуск как есть.
    """
    plain = fake_relay.Relay('probe', [fake_relay.DEFAULT_HOSTID], snapshot_sec=60)
    if not all(getattr(plain, attr, None) == 0 for attr in ID_ATTRS) \
            or not isinstance(getattr(fake_relay, 'KEEP_READINGS', None), int):
        return False
    original_reset = fake_relay.Relay._reset

    def reset_keeping_ids(self, full):
        issued = [getattr(self, attr, 0) for attr in ID_ATTRS]
        original_reset(self, full)
        floor = id_floor()
        for attr, last in zip(ID_ATTRS, issued):
            setattr(self, attr, max(floor, last))

    fake_relay.Relay._reset = reset_keeping_ids
    fake_relay.KEEP_READINGS = min(fake_relay.KEEP_READINGS, KEEP_READINGS)
    return True


def main(argv=None):
    if patch_relay():
        print('relay_stand: id продолжаются с %d, в памяти не больше %d снимков'
              % (id_floor(), fake_relay.KEEP_READINGS), file=sys.stderr, flush=True)
    else:
        print('relay_stand: ВНИМАНИЕ — fake_relay.py изменился, нумерация id после перезапуска начнётся с 1',
              file=sys.stderr, flush=True)
    return fake_relay.main(argv)


if __name__ == '__main__':
    sys.exit(main())
