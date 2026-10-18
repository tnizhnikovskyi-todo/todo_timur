"""Хуки модуля (SPEC §5.3): початкове наповнення реєстру пристроїв і каталогу сигналів."""
import csv
import logging
import re

from odoo.exceptions import ValidationError
from odoo.tools import file_path

_logger = logging.getLogger(__name__)
CATALOG = 'factory3d_iot_sim/data/f3d_sim_signal.csv'

# §5.2: f3d_role → (protocol, driver)
ROLE_MAP = {}
for _roles, _proto, _driver in (
    (('beam_saw', 'beam_saw_book', 'nesting_cnc', 'edgebander_laser', 'edgebander', 'ptp_cnc',
      'throughfeed_drilling', 'dowel_inserting', 'sorting_cell', 'case_clamp_auto'), 'P-01', 'opcua_ww'),
    (('board_storage',), 'P-03', 'rest_woodstore'),
    (('sliding_table_saw', 'vertical_panel_saw', 'wide_belt_sander', 'membrane_press', 'glue_spray_booth',
      'manual_spray_booth', 'automatic_spraying', 'drying', 'uv_line', 'hinge_insertion', 'box_machine',
      'stretch_wrapper', 'shrink_line', 'case_clamp_manual'), 'P-02', 'modbus_adam6050'),
    (('power_meter', 'acb', 'main_switchboard'), 'P-05', 'modbus_pm5560'),
    (('forklift', 'board_forklift', 'tugger'), 'P-06', 'mqtt_mobile'),
    (('compressor',), 'P-07', 'modbus_elektronikon'),
    (('dust_extraction',), 'P-07', 'modbus_adam6017'),
    (('biomass_boiler', 'briquetting_press'), 'P-08', 'bacnet_boiler'),
    (('pv_inverter',), 'P-07', 'modbus_sun2000'),
    (('pv_module',), 'P-07', 'passive'),
    (('bess',), 'P-07', 'modbus_luna2000'),
    (('chp',), 'P-07', 'modbus_tedom'),
    (('ats',), 'P-07', 'modbus_atys'),
    (('transformer',), 'P-07', 'modbus_adam6015'),
    (('water_meter',), 'P-07', 'modbus_adam6050'),
    (('roofvent',), 'P-08', 'bacnet_roofvent'),
    (('make_up_ahu',), 'P-08', 'bacnet_ahu'),
    (('wall_fan', 'ex_fan'), 'P-08', 'bacnet_fan'),
    (('lighting_control',), 'P-08', 'helvarnet_router'),
    (('highbay', 'highbay_rack'), 'P-08', 'passive'),
    (('facp',), 'P-09', 'bacnet_facp'),
    (('smoke_detector', 'multi_detector', 'heat_detector', 'mcp', 'sounder_beacon', 'flame_detector'),
     'P-09', 'passive'),
    (('spark_detection', 'smoke_control', 'smoke_vent'), 'P-09', 'modbus_adam6050'),
    (('access_reader', 'turnstile'), 'P-10', 'rest_biostar'),
    (('barrier',), 'P-11', 'modbus_adam6060'),
    (('cctv_camera',), 'P-11', 'http_lpr'),
    (('truck_scale',), 'P-11', 'sics_scale'),
    (('genset',), 'P-12', 'genset_relay'),
):
    for _role in _roles:
        ROLE_MAP[_role] = (_proto, _driver)
CODE_MAP = {'SPRINKLERS': ('P-07', 'modbus_adam6017'), 'AIR-RING': ('P-07', 'modbus_adam6017'),
            # §5.2: «FL-6 … у демо без сигналів, пасивний», «SMOKE-VENTS — пасивний»
            'FL-6': ('P-06', 'passive'), 'SMOKE-VENTS': ('P-09', 'passive')}
PASSIVE_CODES = ('FL-6', 'SMOKE-VENTS')
_SMOKE = {'di_open': 4, 'di_fault': 5, 'do_open': 0}
# §5.2: (unit_id, params) пристроїв з фіксованою розкладкою каналів ADAM; unit — за таблицею §8.4.1
FIXED_LAYOUT = {
    'T1': (96, {'rtd': [0, 1, 2]}), 'T2': (96, {'rtd': [3, 4, 5]}),
    'SPRINKLERS': (90, {'ai': 2}), 'AIR-RING': (90, {'ai': 3}),
    'DUST-1': (90, {'ai_airflow': 0, 'ai_dp': 1, 'di_run': 0, 'di_fault': 1}),
    'WATER': (84, {'counter': 8}),
    'SPARK-1': (85, {'di_spark': 0, 'di_ext': 1, 'di_fault': 2}),
    'SMOKE-CTRL': (85, dict(_SMOKE)), 'SMOKE-VENTS': (None, dict(_SMOKE)),
    'GATE-W': (86, {'di_open': 0, 'di_loop': 1, 'di_photo': 4, 'do_open': 0, 'do_close': 2, 'do_hold': 4}),
    'GATE-E': (86, {'di_open': 2, 'di_loop': 3, 'di_photo': 5, 'do_open': 1, 'do_close': 3, 'do_hold': 5}),
}
# T1/T2: `_fill_addresses` раніше брав unit першого сигналу (PM5560 на вводі Q1/Q2) замість 96 (S-3)
LEGACY_UNITS = {'T1': 1, 'T2': 2}
FIXED_ADDRESS = {
    'rest_woodstore': 'http://iot-sim:8082/api/v1', 'sics_scale': 'iot-sim:4001', 'http_lpr': 'SIM_LPR_PUSH_URL'}
UNIT_RE = re.compile(r'\bu(\d+)\b')
INSTANCE_RE = re.compile(r'\bdev (\d+)\b')
CONSUMER_RE = re.compile(r'^energy/consumers/([^/]+)/')
P02_STATE_RE = re.compile(r'^workcenters/([^/]+)/state$')
DI_RE = re.compile(r'\bfc2 pdu(\d+)\b')
LSZ_CODE_RE = re.compile(r'^fire/groups/([^/]+)/state$')
LSZ_RE = re.compile(r'\bLSZ:(\d+)\b')
DALI_CODE_RE = re.compile(r'^lighting/groups/([^/]+)/level$')
DALI_RE = re.compile(r'router (@[\d.]+)\) група G:(\d+)')


def _read_catalog_rows():
    with open(file_path(CATALOG), encoding='utf-8', newline='') as fh:
        return list(csv.DictReader(fh))


def _default_address(code, driver):
    if driver == 'opcua_ww':
        return 'ns=2;s=%s' % code
    if driver == 'mqtt_mobile':
        return 'f3d/mobile/%s' % code
    return FIXED_ADDRESS.get(driver, False)


def _ensure_devices(env):
    """Крок 2: пристрої з обладнання з f3d_code + похідні + CUTOPT."""
    Device = env['f3d.sim.device'].sudo()
    Workcenter = env['mrp.workcenter'].sudo()
    existing = {d.code: d for d in Device.search([])}
    equipment = env['maintenance.equipment'].sudo().search([('f3d_code', '!=', False)])
    wcs = {w.f3d_code: w for w in Workcenter.search([('f3d_code', '!=', False)])}
    by_code = {e.f3d_code: e for e in equipment}
    to_create = []

    def add(code, name, proto, driver, eq=None, **extra):
        if code in existing or any(v['code'] == code for v in to_create):
            return
        vals = {'code': code, 'name': name or code, 'protocol': proto, 'driver': driver,
                'equipment_id': eq.id if eq else False, 'workcenter_id': wcs[code].id if code in wcs else False,
                'zone_id': eq.f3d_zone_id.id if eq and 'f3d_zone_id' in eq._fields and eq.f3d_zone_id else False,
                'address': _default_address(code, driver),
                'state': 'passive' if driver == 'passive' else 'unknown'}
        vals.update(extra)
        to_create.append(vals)

    for eq in equipment:
        proto, driver = CODE_MAP.get(eq.f3d_code) or ROLE_MAP.get(eq.f3d_role or '') or ('none', 'passive')
        add(eq.f3d_code, eq.name, proto, driver, eq)
    if 'ACCESS' in by_code:
        for n, code in enumerate(('ACR-IN', 'ACR-ELEC', 'ACR-CHG', 'ACR-PAINT', 'ACR-SRV')):
            add(code, 'Зчитувач %s' % code, 'P-10', 'rest_biostar', by_code['ACCESS'],
                params={'biostar_device_id': 5390001 + n})
    if 'TURNSTILES' in by_code:
        add('TURN-1', 'Турнікет 1', 'P-10', 'rest_biostar', by_code['TURNSTILES'],
            params={'biostar_device_id': 5390006})
    if 'CCTV' in by_code:
        add('CAM-05', 'Камера LPR 05', 'P-11', 'http_lpr', by_code['CCTV'], params={'gate': 'GATE-W'})
        add('CAM-06', 'Камера LPR 06', 'P-11', 'http_lpr', by_code['CCTV'], params={'gate': 'GATE-E'})
    if 'PV-INV' in by_code:
        for n in range(1, 9):
            add('PV-INV-%d' % n, 'Інвертор PV-INV-%d' % n, 'P-07', 'modbus_sun2000', by_code['PV-INV'],
                unit_id=60 + n)
    for row in _read_catalog_rows():
        match = CONSUMER_RE.match(row['code'])
        if match:
            src = match.group(1)
            add(src + '-PM', 'Лічильник %s' % src, 'P-05', 'modbus_pm5560', by_code.get(src))
    add('CUTOPT', 'Оптимізатор розкрою (P-04)', 'none', 'passive')
    if to_create:
        Device.create(to_create)


def _fill_addresses(env):
    """Крок 3а: unit id / instance з адрес першого сигналу пристрою (каталог = джерело правди)."""
    Device = env['f3d.sim.device'].sudo()
    first = {}
    for sig in env['f3d.sim.signal'].sudo().search([('protocol', '!=', 'none')], order='id'):
        first.setdefault(sig.device_id.id, sig.address or '')
    for dev in Device.search([('driver', '!=', 'passive')]):
        addr = first.get(dev.id, '')
        vals = {}
        if dev.code in FIXED_LAYOUT:  # unit за таблицею §8.4.1 — `_fill_params`, а не адреса першого сигналу
            continue
        if dev.driver.startswith('modbus') and not dev.unit_id:
            match = UNIT_RE.search(addr)
            if match:
                vals['unit_id'] = int(match.group(1))
        elif dev.driver.startswith('bacnet') and not dev.instance:
            match = INSTANCE_RE.search(addr)
            if match:
                vals['instance'] = int(match.group(1))
        if vals:
            try:
                with env.cr.savepoint():
                    dev.write(vals)
            except ValidationError as exc:
                _logger.warning("f3d_iot_sim: адресу %s пристрою %s не призначено: %s", vals, dev.code, exc)


def _catalog_params(rows):
    """Params з адрес каталогу (§5.2): P-02 `{di_run, di_fault, counter}`, FA-* `{lsz}`, LT-* `{group, router}`."""
    out = {}
    for row in rows:
        code, address = row['code'], row.get('address') or ''
        match = P02_STATE_RE.match(code)
        if match and row['protocol'] == 'P-02' and DI_RE.search(address):
            n = int(DI_RE.search(address).group(1))  # DI(2m) = «в роботі», DI(2m+1) = «аварія», лічильник на DI(2m)
            out[match.group(1)] = {'di_run': n, 'di_fault': n + 1, 'counter': n}
            continue
        match = LSZ_CODE_RE.match(code)
        if match and LSZ_RE.search(address):
            out[match.group(1)] = {'lsz': int(LSZ_RE.search(address).group(1))}
            continue
        match = DALI_CODE_RE.match(code)
        if match and DALI_RE.search(address):
            router, group = DALI_RE.search(address).groups()
            out[match.group(1)] = {'group': int(group), 'router': router}
    return out


def _fill_params(env):
    """Крок 3б (S-2, S-3): `params` і unit id за §5.2, пасивні FL-6/SMOKE-VENTS.

    Ідемпотентно й без перезапису ручних правок: `params` — лише порожні; `unit_id` — порожній або хибний
    (PM5560 вводу замість 96 у T1/T2); драйвер стає `passive` лише для пристрою без сигналів.
    """
    Device = env['f3d.sim.device'].sudo()
    wanted = {code: (None, params) for code, params in _catalog_params(_read_catalog_rows()).items()}
    wanted.update(FIXED_LAYOUT)
    for dev in Device.search([('code', 'in', list(wanted) + list(PASSIVE_CODES))]):
        unit, params = wanted.get(dev.code, (None, None))
        vals = {}
        if params and not dev.params:
            vals['params'] = params
        if dev.code in PASSIVE_CODES and dev.driver != 'passive' and not dev.signal_ids:
            vals.update({'driver': 'passive', 'state': 'passive'})
        if (unit and dev.driver.startswith('modbus') and dev.unit_id != unit
                and (not dev.unit_id or dev.unit_id == LEGACY_UNITS.get(dev.code))):
            vals['unit_id'] = unit
        if vals:
            try:
                with env.cr.savepoint():
                    dev.write(vals)
            except ValidationError as exc:
                _logger.warning("f3d_iot_sim: params/unit %s пристрою %s не призначено: %s", vals, dev.code, exc)


def _check_level0(env):
    """Крок 4: origin=mock ↔ x_f3d_signal.x_code."""
    if 'x_f3d_signal' not in env:
        _logger.warning("f3d_iot_sim: модель x_f3d_signal відсутня (рівень 0 не встановлено)")
        return
    codes = {s.x_code for s in env['x_f3d_signal'].sudo().search([])}
    mock = env['f3d.sim.signal'].sudo().search([('origin', '=', 'mock')])
    missing = [s.code for s in mock if s.level0_code not in codes]
    if missing and codes:
        _logger.warning("f3d_iot_sim: %d сигналів «макет» без x_f3d_signal: %s", len(missing), missing[:30])


def apply_read_enabled(env):
    """Крок 1а (CB-10, X-56): read_enabled за середовищем factory3d.base.environment."""
    ICP = env['ir.config_parameter'].sudo()
    environment = ICP.get_param('factory3d.base.environment', 'prod')
    ICP.set_param('factory3d.iot_sim.read_enabled', 'True' if environment == 'test' else 'False')


def refresh_registry(env):
    """Кроки 2–4 + 3б: пристрої, каталог, адреси, params (ідемпотентно; також post-migrate 19.0.2.0.1)."""
    _ensure_devices(env)
    env['f3d.sim.signal']._load_catalog(file_path(CATALOG))
    _fill_addresses(env)
    _fill_params(env)
    _check_level0(env)


def post_init_hook(env):
    Panel = env['f3d.sim.panel']
    panel = Panel.get_panel()
    apply_read_enabled(env)
    refresh_registry(env)
    if not (env['ir.config_parameter'].sudo().get_param('factory3d.iot_sim.url') or '').strip() \
            and panel.state != 'unconfigured':  # без зайвого запису: хук також виконує post-migrate (ідемпотентно)
        panel.sudo().state = 'unconfigured'
    env['f3d.sim.device'].sudo().search([('driver', '=', 'passive'), ('state', '=', 'unknown')]).write(
        {'state': 'passive'})


def uninstall_hook(env):
    """A-11: прибрати запуски/події й параметри, крони вимкнути; x_-дані й обладнання не чіпати."""
    _logger.warning("f3d_iot_sim: деінсталяція видалить і дані рівня 0 (x_f3d_*), бо їх файли належать "
                    "модулю — робіть лише на копії (SPEC §5.3)")
    panel = env['f3d.sim.panel'].sudo().search([], limit=1)
    if panel:
        panel.message_post(body="Деінсталяція модуля: запуски й події емулятора видаляються.")
    env['f3d.sim.event'].sudo().search([]).unlink()
    env['f3d.sim.run'].sudo().search([]).unlink()
    xmlids = env['ir.model.data'].sudo().search([('module', '=', 'factory3d_iot_sim'), ('model', '=', 'ir.cron')])
    env['ir.cron'].sudo().browse(xmlids.mapped('res_id')).exists().write({'active': False})
    env['ir.config_parameter'].sudo().search([('key', '=like', 'factory3d.iot_sim.%')]).unlink()
