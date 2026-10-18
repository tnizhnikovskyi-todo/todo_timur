"""Генератор data-файлів td_factory3d з макета (SPEC §5.2).

Запуск з каталогу factory3d (корінь макета):
    python3 odoo_addons/td_factory3d/tools/gen_data.py [--root .] [--out odoo_addons/td_factory3d/data]

Читає dist/odoo_demo.json, plant/equipment_specs.json, plant/odoo_flows.py:NAMES.
Пише детерміновано (сортування, без часових міток). Файли зон, воріт і zone_links генеруються
окремо від цього модуля даних (див. SPEC §5.2) — тут лише паспорти, коди сцени й локації.
"""
import argparse
import csv
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
DEFAULT_OUT = os.path.abspath(os.path.join(HERE, '..', 'data'))

# додаткові числові ключі паспорта: ключ JSON -> (назва, одиниця); порядок = порядок рядків
EXTRA_KEYS = [
    ('lumen', 'Світловий потік', 'лм'),
    ('watt', 'Споживана потужність', 'Вт'),
    ('airflow_m3h', 'Витрата повітря', 'м³/год'),
    ('required_m3h', 'Потрібна витрата (розрахунок)', 'м³/год'),
    ('heat_kw', 'Теплова потужність', 'кВт'),
    ('heat_kw_75', 'Теплова потужність при 75 %', 'кВт'),
    ('heat_kw_50', 'Теплова потужність при 50 %', 'кВт'),
    ('kva', 'Потужність PRP', 'кВА'),
    ('kva_standby', 'Потужність ESP', 'кВА'),
    ('fuel_lph_75', 'Витрата палива при 75 %', 'л/год'),
    ('tank_l', 'Бак', 'л'),
    ('controller', 'Контролер', '—'),
    ('kwh', 'Ємність', 'кВт·год'),
    ('wp', 'Потужність модуля', 'Вт'),
    ('kw_ac', 'Потужність AC', 'кВт'),
    ('gas_m3h', 'Витрата газу при 100 %', 'м³/год'),
    ('gas_m3h_75', 'Витрата газу при 75 %', 'м³/год'),
    ('gas_m3h_50', 'Витрата газу при 50 %', 'м³/год'),
    ('eta_el', 'ККД електричний', '%'),
    ('eta_th', 'ККД тепловий', '%'),
    ('min_load', 'Мінімальне тривале навантаження', '%'),
    ('current_a', 'Струм', 'А'),
    ('exhaust_module_mm', 'Модуль вихлопу', 'мм'),
    ('silencer_mm', 'Глушник', 'мм'),
    ('beam_clear_mm', 'Просвіт балки', 'мм'),
    ('frame_depth_mm', 'Глибина рами', 'мм'),
    ('level_capacity_kg', 'Навантаження на ярус', 'кг'),
    ('upright_mm', 'Стійка', 'мм'),
    ('design_stack_max_kg', 'Макс. маса стосу (проєкт)', 'кг'),
    ('bay_pitch_mm', 'Крок прольоту', 'мм'),
    ('beam_height_mm', 'Висота балки', 'мм'),
    ('beam_levels_mm_full_stack', 'Рівні балок (повний стос)', 'мм'),
    ('beam_levels_mm_075_stack', 'Рівні балок (0,75 стосу)', 'мм'),
    ('capacity_kg', 'Вантажопідйомність', 'кг'),
    ('load_centre_mm', 'Центр ваги', 'мм'),
    ('capacity_at_1035mm_kg', 'Вантажопідйомність при c = 1035 мм', 'кг'),
    ('aisle_mm', 'Робочий прохід', 'мм'),
    ('lift_mm', 'Висота підйому', 'мм'),
    ('truck_w_mm', 'Ширина навантажувача', 'мм'),
    ('truck_l_mm', 'Довжина навантажувача', 'мм'),
    ('drive', 'Привод', '—'),
]
BASE_KEYS = {'role', 'manufacturer', 'model', 'reason', 'specs', 'dimensions_mm', 'power_kw',
             'sources', 'connected_kw', 'connected_note', 'connected_sources', 'note'}

# зони обладнання за README (A-06, додаток F) і за моделлю території (A-19)
EXTRA_ZONES = {}
for _codes, _zone in (
        (('RM6-1', 'T1', 'T2', 'SWB-1', 'Q1', 'Q2', 'QS', 'QF-1', 'QF-2', 'QF-3', 'QF-4', 'QF-C1',
          'QF-C2', 'PFC-1', 'PFC-2', 'EMS-1', 'ATS-1'), 'Z-ELEC'),
        (('COMPRESSOR',), 'Z-CMP'),
        (('CHARGING', 'EYE-CHG'), 'Z-CHG'),
        (('GANTRY-1', 'BOARD-RACKS'), 'Z-SHEETS'),
        (('FACP-1',), 'Z-OFFICE'),
        (('EYE-PAINT',), 'Z-FAC'),
        (('PRN-PACK1', 'PRN-PACK2', 'IOT-PACK'), 'Z-PACK'),
        (('GATE-W',), 'Z-GATE-W'),
        (('GATE-E', 'TRUCK-SCALE'), 'Z-GATE-E'),
        (('TURNSTILES',), 'Z-KPP'),
        (('GENSET', 'BESS', 'CHP', 'PV-INV'), 'Z-ENERGY'),
        (('BOILER',), 'Z-BOILER'),
        (('PV-ROOF', 'SMOKE-VENTS', 'LPS'), 'Z-ROOF')):
    for _c in _codes:
        EXTRA_ZONES[_c] = _zone


def _num(value):
    """Число для CSV: цілі без дробової частини; None -> 0."""
    if value is None:
        return '0'
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _key(*parts):
    """Копія plant/odoo_rpc.key (без імпорту, щоб не тягнути залежності)."""
    import hashlib
    raw = "_".join(str(p) for p in parts)
    k = re.sub(r"[^0-9A-Za-z]+", "_", raw).strip("_").lower()
    if not raw.isascii():
        k += "_" + hashlib.md5(raw.encode()).hexdigest()[:8]
    return k


def _csv(header, rows):
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator='\n')
    writer.writerow(header)
    writer.writerows(rows)
    return buf.getvalue()


def _host(url):
    from urllib.parse import urlparse
    return urlparse(url).netloc


def gen_passports(specs):
    rows = []
    for rec in sorted(specs, key=lambda r: r['role']):
        dims = rec.get('dimensions_mm') or {}
        rows.append([
            'passport_' + rec['role'], rec['role'], rec['manufacturer'], rec['model'],
            rec.get('reason') or '',
            int(dims.get('L') or 0), int(dims.get('W') or 0), int(dims.get('H') or 0),
            _num(rec.get('power_kw')), _num(rec.get('connected_kw')),
            rec.get('connected_note') or '', rec.get('note') or ''])
    return _csv(['id', 'role', 'manufacturer', 'model', 'reason', 'dim_l_mm', 'dim_w_mm', 'dim_h_mm',
                 'power_kw', 'connected_kw', 'connected_note', 'note'], rows)


def gen_specs(specs):
    known = {k for k, _n, _u in EXTRA_KEYS}
    rows = []
    for rec in sorted(specs, key=lambda r: r['role']):
        role = rec['role']
        unknown = set(rec) - BASE_KEYS - known
        if unknown:
            raise SystemExit("Невідомий ключ паспорта %s: %s" % (role, sorted(unknown)))
        counter = 0
        for n, (name, value) in enumerate(rec['specs'].items(), 1):
            counter += 1
            rows.append(['spec_%s_%03d' % (role, counter), 'passport_' + role, 10 * n, '', name,
                         str(value), '', '', 'published'])
        n = 0
        for key, name, uom in EXTRA_KEYS:
            value = rec.get(key)
            if value is None or value == []:
                continue
            n += 1
            counter += 1
            num, text = '', ''
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                num = text = _num(value)
            elif isinstance(value, str):
                text = value
            else:
                text = json.dumps(value, ensure_ascii=False)
            rows.append(['spec_%s_%03d' % (role, counter), 'passport_' + role, 1000 + 10 * n, key,
                         name, text, num, '' if uom == '—' else uom, 'published'])
    return _csv(['id', 'passport_id:id', 'sequence', 'key', 'name', 'value_text', 'value_num', 'uom',
                 'kind'], rows)


def gen_sources(specs):
    rows = []
    for rec in sorted(specs, key=lambda r: r['role']):
        role = rec['role']
        for kind, field in (('main', 'sources'), ('connected', 'connected_sources')):
            for n, url in enumerate(rec.get(field) or [], 1):
                rows.append(['source_%s_%s_%d' % (role, kind, n), 'passport_' + role, 10 * n, kind,
                             url, _host(url)])
    return _csv(['id', 'passport_id:id', 'sequence', 'kind', 'url', 'name'], rows)


def gen_employee_codes(demo):
    rows = [[code.replace('-', ''), code, emp['name']] for code, emp in sorted(demo['employees'].items())]
    return _csv(['barcode', 'td_code', 'name'], rows)


def gen_locations(demo):
    rows = []
    for code, loc in sorted(demo['locations'].items()):
        cap = loc.get('capacity')
        rows.append([code, loc['kind'], '' if cap is None else _num(cap)])
    return _csv(['code', 'kind', 'capacity'], rows)


def gen_equipment_codes(demo, names):
    ventilation, fire, lighting = (demo['ventilation']['units'], demo['fire']['groups'],
                                   demo['lighting']['groups'])
    codes = set(demo['passports']) | set(demo['workcenters']) | set(demo['equipment'])
    for group in (ventilation, fire, lighting):
        codes |= set(group)
    codes |= {'FA-FAC', 'RV-05'}
    all_names = dict(names)
    all_names.update({c: w['name'] for c, w in demo['workcenters'].items()})
    all_names.update({c: e['name'] for c, e in demo['equipment'].items()})
    all_names.update({c: u['name'] for c, u in ventilation.items()})
    all_names.update({c: "Пожежна сигналізація: %s (%s)" % (g['zone_name'], g['kind_name'])
                      for c, g in fire.items()})
    all_names.update({c: "Освітлення: %s" % g['zone_name'] for c, g in lighting.items()})
    zones = dict(EXTRA_ZONES)
    for group in (ventilation, fire, lighting):
        for code, g in group.items():
            zone = g.get('zone')
            if zone and not zone.startswith('Z-'):
                zone = 'Z-' + zone  # FA-BOILER: у макеті зона записана як «BOILER»
            if zone:
                zones[code] = zone
    rows = []
    for code in sorted(codes):
        passport = demo['passports'].get(code) or {}
        legacy = ''
        serial = (demo['equipment'].get(code) or {}).get('serial')
        if serial and serial != code:
            legacy = serial
        rows.append([code, _key('eq', code), legacy,
                     all_names.get(code, code), passport.get('role') or '',
                     ';'.join(u['role'] for u in passport.get('units') or []), zones.get(code, '')])
    return _csv(['code', 'xmlid', 'legacy_serial', 'name', 'role', 'components', 'zone'], rows)


def build(root=None):
    """Повертає {ім'я файлу: вміст}."""
    root = os.path.abspath(root or DEFAULT_ROOT)
    with open(os.path.join(root, 'dist', 'odoo_demo.json'), encoding='utf-8') as f:
        demo = json.load(f)
    with open(os.path.join(root, 'plant', 'equipment_specs.json'), encoding='utf-8') as f:
        specs = json.load(f)
    sys.path.insert(0, root)
    try:
        from plant.odoo_flows import NAMES
    finally:
        sys.path.remove(root)
    return {
        'td.equipment.passport.csv': gen_passports(specs),
        'td.equipment.spec.csv': gen_specs(specs),
        'td.equipment.source.csv': gen_sources(specs),
        'scene_equipment_codes.csv': gen_equipment_codes(demo, NAMES),
        'scene_employee_codes.csv': gen_employee_codes(demo),
        'scene_locations.csv': gen_locations(demo),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--root', default=DEFAULT_ROOT, help="каталог factory3d (де dist/ і plant/)")
    parser.add_argument('--out', default=DEFAULT_OUT, help="куди писати data-файли")
    args = parser.parse_args(argv)
    files = build(args.root)
    os.makedirs(args.out, exist_ok=True)
    for name, text in files.items():
        with open(os.path.join(args.out, name), 'w', encoding='utf-8', newline='') as f:
            f.write(text)
        print('%s: %d рядків' % (name, text.count('\n') - 1))


if __name__ == '__main__':
    main()
