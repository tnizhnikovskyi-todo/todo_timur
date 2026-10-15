"""Генератор events_shift.json (SPEC §13.1): 152 рядки API-06 за 2026-10-12. Odoo цей файл не вантажить.

Запуск: python3 gen_events_shift.py  (перезаписує events_shift.json поруч).
"""
import csv
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
CODES_CSV = os.path.join(HERE, '..', '..', '..', 'factory3d_base', 'data', 'scene_employee_codes.csv')
DAY = '2026-10-12'
ACR = {'in': ('5390001', '1'), 'elec': ('5390002', '2'), 'paint': ('5390004', '4'), 'srv': ('5390005', '5')}


def det(*xs, mod=1000):
    """FNV-1a 32 як plant/odoo_demo.py:det."""
    h = 2166136261
    for x in xs:
        for ch in str(x):
            h = ((h ^ ord(ch)) * 16777619) & 0xFFFFFFFF
    return h % mod


def row(dt, code, user, where, tna=''):
    device, door = ACR[where]
    res = {'datetime': dt, 'server_datetime': dt, 'event_type_id': {'code': str(code)},
           'device_id': {'id': device}, 'door_id': [{'id': door}], 'tna_key': tna}
    if user:
        res['user_id'] = {'user_id': user}
    return res


def stamp(minute, second=0, hour=3):
    return '%sT%02d:%02d:%02d.00Z' % (DAY, hour, minute, second)


def build():
    rows = []
    with open(CODES_CSV, encoding='utf-8') as fh:
        people = list(csv.DictReader(fh))
    for person in people:
        minute = 40 + det(person['f3d_code'], mod=20)
        code = 4102 if det(person['f3d_code']) % 2 == 0 else 4867
        rows.append(row(stamp(minute), code, person['barcode'], 'in', tna='1'))
        for offset, door_code in ((0, 20480), (1, 20992), (6, 21248)):
            rows.append(row(stamp(minute, offset), door_code, None, 'in'))
    for dt, user, where, door_code in ((stamp(51, hour=6), 'OPW1', 'elec', 20480),
                                      (stamp(20, hour=7), 'OPW2', 'paint', 20480),
                                      (stamp(5, hour=8), '1', 'srv', 20480)):
        rows.append(row(dt, 4102, user, where))
        for offset, code in ((0, door_code), (1, 20992), (6, 21248)):
            rows.append(row(dt[:-5] + '%02d.00Z' % offset, code, None, where))
    rows.sort(key=lambda r: r['datetime'])
    for i, r in enumerate(rows, 1):
        r['id'] = str(i)
        r['hint'] = 'H%d' % i
    return rows


if __name__ == '__main__':
    out = build()
    with open(os.path.join(HERE, 'events_shift.json'), 'w', encoding='utf-8') as fh:
        json.dump({'EventCollection': {'rows': out, 'total': str(len(out))}}, fh, ensure_ascii=False, indent=1)
    print(len(out), 'rows')
