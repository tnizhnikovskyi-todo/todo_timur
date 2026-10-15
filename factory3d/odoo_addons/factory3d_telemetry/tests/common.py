import json
from contextlib import contextmanager
from datetime import datetime, timedelta
from unittest import mock
from zoneinfo import ZoneInfo

from odoo.tests import HttpCase, TransactionCase, new_test_user

PARAMS = {
    'read_enabled': 'True', 'write_enabled': 'False', 'keep_days': '30', 'keep_hours_days': '400',
    'default_store_period_s': '300', 'stale_periods': '3', 'stale_min_s': '60', 'bus_min_interval_s': '10',
    'realarm_cooldown_s': '3600', 'push_max_readings': '2000', 'push_rate_per_min': '60', 'meter_lead_pct': '5',
}

EQUIPMENT = {  # атрибут -> (назва, f3d_code, з командою)
    'eq_comp': ('Компресорна станція', 'COMPRESSOR-T', True),
    'eq_rv': ('Припливно-витяжна установка RV-05 (тест)', 'RV-05-T', True),
    'eq_flc1': ('Навантажувач (резерв) (тест)', 'FL-C1-T', True),
    'eq_fl2': ('Навантажувач приймання (тест)', 'FL-2-T', True),
    'eq_water': ('Водомірний вузол (тест)', 'WATER-T', True),
    'eq_other': ('Обладнання без команди', 'OTHER-T', False),
}

MB_ADDR = {"host": "iot-sim", "port": 502}
MQTT_PARAMS = {"host": "mosquitto", "port": 1883, "username": "collector", "password_ref": "F3D_MQTT_PASSWORD",
               "client_id": "f3d-test", "topics": ["f3d/mobile/+/telemetry"]}


class F3DTelemetryMixin:
    """SPEC §13.0.1. Базові фікстури (без моделей телеметрії) створює `_setup_base_fixtures`;
    колектори/джерела/сигнали — `_setup_telemetry_fixtures` (викликати з setUpClass класів, що їх потребують)."""

    T0 = datetime(2026, 10, 14, 6, 0, 0)
    KYIV = ZoneInfo('Europe/Kyiv')

    @classmethod
    def _setup_base_fixtures(cls):
        icp = cls.env['ir.config_parameter'].sudo()
        for key, val in PARAMS.items():
            icp.set_param('factory3d.telemetry.' + key, val)
        cls.team_mech = cls.env['maintenance.team'].create({'name': 'Служба головного механіка (тест)'})
        cls.team_default = cls.env['maintenance.team'].create({'name': 'Команда за замовчуванням (тест)'})
        icp.set_param('factory3d.telemetry.default_team_id', str(cls.team_default.id))
        stages = cls.env['maintenance.stage'].search([], order='sequence, id')
        cls.stage_new = stages.filtered(lambda s: not s.done)[:1]
        cls.stage_done = stages.filtered('done')[:1]
        base = 'factory3d_base.'
        cls.user_plain = new_test_user(cls.env, 'f3dt_plain', groups='base.group_user')
        cls.user_reader = new_test_user(cls.env, 'f3dt_reader', groups='base.group_user,' + base + 'group_f3d_user')
        cls.user_mech = new_test_user(
            cls.env, 'f3dt_mech',
            groups='base.group_user,' + base + 'group_f3d_user,maintenance.group_equipment_manager')
        cls.user_manager = new_test_user(
            cls.env, 'f3dt_manager', groups='base.group_user,' + base + 'group_f3d_manager')
        cls.user_admin = new_test_user(cls.env, 'f3dt_admin', groups='base.group_user,' + base + 'group_f3d_admin')
        for attr, (name, code, with_team) in EQUIPMENT.items():
            vals = {'name': name, 'f3d_code': code}
            if with_team:
                vals['maintenance_team_id'] = cls.team_mech.id
            setattr(cls, attr, cls.env['maintenance.equipment'].create(vals))

    @classmethod
    def _setup_telemetry_fixtures(cls):
        """Колектори, джерела й сигнали (потребує моделей W1). Поля — за SPEC §2."""
        Col, Src, Sig = cls.env['f3d.collector'], cls.env['f3d.source'], cls.env['f3d.signal']
        cls.col = Col.create({'code': 'COL-T', 'name': 'Тестовий колектор'})
        cls.col2 = Col.create({'code': 'COL-T2', 'name': 'Тестовий колектор 2'})
        cls.token = cls._gen_token(cls.col)
        cls.token2 = cls._gen_token(cls.col2)

        def src(code, typ, params, col=None, **kw):
            return Src.create({'code': code, 'name': code, 'type': typ, 'collector_id': (col or cls.col).id,
                               'params': params, **kw})

        cls.src_mb = src('MB-T-U70', 'modbus_tcp', {**MB_ADDR, "unit": 70}, equipment_id=cls.eq_comp.id)
        cls.src_mb84 = src('MB-T-U84', 'modbus_tcp', {**MB_ADDR, "unit": 84})
        cls.src_mqtt = src('MQTT-T', 'mqtt', MQTT_PARAMS)
        cls.src_bac = src('BAC-T-105', 'bacnet_ip', {"host": "iot-sim", "device": 105})
        cls.src_bac_ro = src('BAC-T-200', 'bacnet_ip', {"host": "iot-sim", "device": 200, "read_only": True})
        cls.src_http = src('HTTP-T', 'http_push', {"routes": ["lpr"], "allow_ips": ["iot-sim"]})
        cls.src_old = src('MB-T-OLD', 'modbus_tcp', {**MB_ADDR, "unit": 70}, active=False)
        cls.src_other = src('MB-T2', 'modbus_tcp', {**MB_ADDR, "unit": 71}, col=cls.col2)

        def sig(code, kind, unit, source, address, eq=None, **kw):
            vals = {'code': code, 'name': kw.pop('name', code), 'kind': kind, 'unit': unit,
                    'source_id': source.id if source else False, 'address': address,
                    'equipment_id': eq.id if eq else False, 'origin': 'manual', 'store_period_s': 300, **kw}
            return Sig.create(vals)

        cls.sig_press = sig(
            'equipment/COMPRESSOR-T/pressure_bar', 'gauge', 'бар', cls.src_mb,
            {"fc": 3, "addr": 3001, "type": "u16", "scale": 0.001}, cls.eq_comp, name='Компресор: тиск',
            period_s=10, alarm_low_on=True, alarm_low=6.0, hysteresis=0.1, min_duration_s=30, decimals=2,
            alarm_title="{equipment}: тиск {value} бар при нормі від {threshold}")
        cls.sig_hours = sig('equipment/COMPRESSOR-T/hours', 'counter', 'год', cls.src_mb,
                            {"fc": 3, "addr": 3019, "type": "u32"}, cls.eq_comp, period_s=60, decimals=1)
        cmap = {"0": "stopped", "1": "loaded", "2": "unloaded", "3": "fault", "4": "standby"}
        cls.sig_cstate = sig('equipment/COMPRESSOR-T/state', 'state', False, cls.src_mb,
                             {"fc": 3, "addr": 3000, "type": "u16", "map": cmap}, cls.eq_comp, name='Компресор',
                             states_text=', '.join(cmap.values()), alarm_states_text='fault')
        cls.sig_rv = sig(
            'ventilation/units/RV-05-T/filter_dp_pa', 'gauge', 'Па', cls.src_bac,
            {"object": "analog-input", "instance": 4, "mode": "poll"}, cls.eq_rv, period_s=10,
            alarm_high_on=True, alarm_high=250, hysteresis=10, decimals=0,
            alarm_title="Заміна фільтрів: перепад тиску {value} Па при нормі до {threshold}")
        cls.sig_valve = sig('ventilation/units/RV-05-T/heating_valve', 'gauge', '%', cls.src_bac,
                            {"object": "analog-output", "instance": 1, "priority": 8}, cls.eq_rv,
                            write_enabled=False)
        bat = {"topic": "f3d/mobile/FL-C1-T/telemetry"}
        cls.sig_bat = sig('equipment/FL-C1-T/battery', 'gauge', '%', cls.src_mqtt,
                          {**bat, "path": "$.battery_pct"}, cls.eq_flc1, period_s=5, warn_low_on=True, warn_low=25,
                          alarm_low_on=True, alarm_low=15, hysteresis=0, decimals=1,
                          alarm_title="Зарядити АКБ: заряд {value} % при нормі від {threshold}")
        cls.sig_flstate = sig('equipment/FL-C1-T/state', 'state', False, cls.src_mqtt,
                              {**bat, "path": "$.state", "map": {"to_charge": "busy"}}, cls.eq_flc1, period_s=5,
                              states_text='idle, busy, charging, offline, fault')
        cls.sig_flx = sig('equipment/FL-C1-T/x', 'gauge', 'м', cls.src_mqtt, {**bat, "path": "$.x"},
                          viewer_visible=False, store_period_s=60)
        cls.sig_fl2_hours = sig('equipment/FL-2-T/hours', 'counter', 'год', cls.src_mqtt,
                                {**bat, "path": "$.hours"}, cls.eq_fl2, decimals=1)
        cls.sig_water = sig('infra/WATER-T/m3_total', 'counter', 'м³', cls.src_mb84,
                            {"fc": 3, "addr": 16, "count": 2, "type": "u32", "wordorder": "little", "scale": 0.01},
                            cls.eq_water, period_s=60, decimals=2)
        cls.sig_flow = sig('infra/WATER-T/flow_m3h', 'gauge', 'м³/год', None, {}, cls.eq_water,
                           derived_from_id=cls.sig_water.id, derive_rule='rate_h', period_s=60)
        cls.sig_fire = sig('fire/groups/FA-T/state', 'state', False, cls.src_bac_ro,
                           {"object": "life-safety-zone", "instance": 12})
        cls.sig_plate = sig('yard/lpr/CAM-T/plate', 'event', False, cls.src_http,
                            {"route": "lpr", "match": {"sensorProviderID": "CAM-05"}, "path": "$.plateText",
                             "ts_path": "$.capture_timestamp"})
        cls.sig_free = sig('energy/consumers/SAW-T/p_now', 'gauge', 'кВт', None, {}, origin='sim_data')
        cls.set_sql(cls.sig_free, last_value=12.18, status='ok', last_ts=cls.T0 - timedelta(days=1))
        cls.sig_foreign = sig('equipment/OTHER-T/x', 'gauge', False, cls.src_other, {"fc": 3, "addr": 0})
        cls.sig_old = sig('equipment/OTHER-T/old', 'gauge', False, cls.src_mb, {"fc": 3, "addr": 1}, active=False)
        cls.sig_noaddr = sig('equipment/OTHER-T/noaddr', 'gauge', False, cls.src_mb, {})

    @classmethod
    def _gen_token(cls, collector):
        res = collector.with_user(cls.user_admin).action_generate_token()
        return res['context']['default_token']

    # --- помічники ---
    def push(self, readings, collector=None, src='collector'):
        return self.env['f3d.signal'].sudo()._f3d_ingest(readings, src=src, collector=collector or self.col)

    def rd(self, sig, value=None, text=None, at=0, q='good'):
        res = {"code": sig.code, "ts": self.T0 + timedelta(seconds=at), "value": value, "text": text, "q": q}
        return {k: v for k, v in res.items() if v is not None}

    @classmethod
    def set_sql(cls, rec, **vals):
        cols = ', '.join(f'{k} = %s' for k in vals)
        cls.env.cr.execute(f'UPDATE {rec._table} SET {cols} WHERE id = %s', [*vals.values(), rec.id])
        rec.invalidate_recordset()

    def close(self, req):
        req.write({'stage_id': self.stage_done.id})

    def reopen(self, req):
        req.write({'stage_id': self.stage_new.id})

    @contextmanager
    def with_catalog_rows(self, rows):
        with mock.patch('odoo.addons.factory3d_telemetry.hooks._catalog_rows', return_value=rows):
            yield

    # make_level0(signals, readings) — реалізує воркер міграції (W4): потребує Додатка D.


class F3DTelemetryCase(F3DTelemetryMixin, TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_base_fixtures()


class F3DTelemetryHttpCase(F3DTelemetryMixin, HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_base_fixtures()

    def api(self, method, path, body=None, token='default', headers=None, raw=None):
        if token == 'default':
            token = getattr(self, 'token', None)
        hdrs = {'Content-Type': 'application/json', **(headers or {})}
        if token is not None:
            hdrs['Authorization'] = f'Bearer {token}'
        resp = self.url_open(path, data=raw if raw is not None else json.dumps(body), headers=hdrs, method=method)
        try:
            data = resp.json()
        except ValueError:
            data = None
        return resp.status_code, data, resp.headers
