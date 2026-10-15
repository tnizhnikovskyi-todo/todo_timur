"""FireCase: спільна база тестів пожежної безпеки (SPEC §13.1).

Заробить після появи моделей W1…W4 і розкоментованих data-файлів (у tests/__init__.py не імпортується до цього).
"""
from contextlib import contextmanager
from datetime import datetime, timedelta
from unittest import mock

from freezegun import freeze_time

from odoo.tests import TransactionCase, new_test_user

EQUIPMENT_CODES = ('FACP-1', 'FA-CUT', 'FA-EB', 'FA-CNC', 'FA-FAC', 'SPARK-1', 'SMOKE-CTRL', 'SPRINKLERS')
T0 = datetime(2026, 10, 14, 7, 0, 0)  # UTC naive


class FireCase(TransactionCase):

    T0 = T0

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        ref = env.ref
        # записи data
        cls.panel = ref('factory3d_fire_safety.panel_facp_1')
        for attr, code in (('z_cut', 'cut'), ('z_eb', 'eb'), ('z_cnc', 'cnc'), ('z_fac', 'fac'), ('z_fg', 'fg'),
                           ('z_rcv1', 'rcv_1')):
            setattr(cls, attr, ref('factory3d_fire_safety.fire_zone_fa_' + code))
        cls.dev_fac07 = ref('factory3d_fire_safety.dev_2_fac_07')
        cls.dev_cnc05 = ref('factory3d_fire_safety.dev_2_cnc_05')
        cls.loop2 = ref('factory3d_fire_safety.loop_2')
        cls.src_bac = ref('factory3d_fire_safety.source_bacnet_facp_1', raise_if_not_found=False)
        cls.src_io = ref('factory3d_fire_safety.source_mb_u85_io6', raise_if_not_found=False)
        cls.sys_spark = ref('factory3d_fire_safety.system_spark_1')
        cls.sys_smoke = ref('factory3d_fire_safety.system_smoke_ctrl')
        cls.sys_spr = ref('factory3d_fire_safety.system_sprinklers')
        cls.tpl = ref('factory3d_fire_safety.drill_template_default', raise_if_not_found=False)  # W4
        # обладнання: чиста база не має демо
        cls.team = env['maintenance.team'].create({'name': 'Тестова команда ПБ'})
        cls.equipment = {
            code: env['maintenance.equipment'].create(
                {'name': code, 'f3d_code': code, 'maintenance_team_id': cls.team.id})
            for code in EQUIPMENT_CODES}
        from odoo.addons.factory3d_fire_safety import hooks
        hooks.equipment.link(env)
        # сигнал тиску спринклерів
        Signal = env['f3d.signal']
        if not Signal.search([('code', '=', 'equipment/SPRINKLERS/pressure_bar')]):
            Signal.create({
                'code': 'equipment/SPRINKLERS/pressure_bar', 'name': 'Тиск спринклерів', 'kind': 'gauge',
                'alarm_low': 6.5, 'alarm_low_on': True, 'module': 'telemetry',
                'equipment_id': cls.equipment['SPRINKLERS'].id})
        cls._ensure_dust_signal()
        hooks.equipment.link(env)
        # параметри й тестова група охорони
        icp = env['ir.config_parameter'].sudo()
        icp.set_param('factory3d.fire_safety.read_enabled', 'True')
        icp.set_param('factory3d.fire_safety.team_id', str(cls.team.id))
        cls.g_alert = env['res.groups'].create({'name': 'Тест: охорона ПБ'})
        env['ir.model.data'].create({'module': 'test_fire', 'name': 'group_alert', 'model': 'res.groups',
                                     'res_id': cls.g_alert.id})
        icp.set_param('factory3d.fire_safety.alert_group_xmlid', 'test_fire.group_alert')
        # користувачі
        cls.u = new_test_user(env, 'fire_u', groups='base.group_user,factory3d_base.group_f3d_user')
        cls.d = new_test_user(env, 'fire_d', groups='base.group_user,factory3d_fire_safety.group_f3d_fire_drill')
        cls.m = new_test_user(env, 'fire_m', groups='base.group_user,factory3d_base.group_f3d_manager')
        cls.a = new_test_user(env, 'fire_a', groups='base.group_user,factory3d_base.group_f3d_admin')
        cls.hr = new_test_user(env, 'fire_hr', groups='base.group_user,hr.group_hr_user,factory3d_base.group_f3d_user')
        cls.guard1 = new_test_user(env, 'fire_guard1', groups='base.group_user')
        cls.guard2 = new_test_user(env, 'fire_guard2', groups='base.group_user')
        cls.g_alert.user_ids = [(6, 0, (cls.guard1 | cls.guard2).ids)]

    @classmethod
    def _ensure_dust_signal(cls):
        """Сигнал запиленості 2.FAC.07 (хук §5.4 п. 3): створюється, якщо хук ще не створив."""
        env = cls.env
        sig = env['f3d.signal'].search([('code', '=', 'fire/groups/FA-FAC/dust')], limit=1)
        if not sig:
            sig = env['f3d.signal'].create({
                'code': 'fire/groups/FA-FAC/dust', 'name': 'Запиленість сповіщувача 2.FAC.07', 'kind': 'gauge',
                'unit': '%', 'source_id': cls.src_bac.id, 'address': {'object': 'PIV', 'instance': 21607, 'mode': 'poll'},
                'period_s': 600, 'store_period_s': 3600, 'module': 'fire_safety', 'origin': 'module',
                'warn_high': 80, 'warn_high_on': True, 'alarm_high': 90, 'alarm_high_on': True, 'hysteresis': 1.8,
                'decimals': 1, 'create_request': True, 'write_enabled': False,
                'alarm_title': 'Очистити сповіщувач 2.FAC.07 (Дільниця фасадів МДФ): запиленість {value} % при нормі до {threshold}'})
        cls.dust_signal = sig
        cls.z_fac.dust_signal_id = sig
        cls.dev_fac07.write({'dust_signal_id': sig.id, 'monitor': True})

    # --- час ---------------------------------------------------------------------------------------------
    @staticmethod
    def at(s):
        return T0 + timedelta(seconds=s)

    # --- сигнали -----------------------------------------------------------------------------------------
    def _push(self, readings, ts):
        with freeze_time(ts + timedelta(seconds=1)):  # щоб не спрацював ts_future
            return self.env['f3d.signal']._f3d_ingest(readings, src='module')

    def push_text(self, code, text, ts=None):
        return self._push([{'code': code, 'ts': ts or T0, 'text': text}], ts or T0)

    def push_value(self, code, value, ts=None):
        return self._push([{'code': code, 'ts': ts or T0, 'value': value}], ts or T0)

    def sync(self, s=None):
        """Повна звірка; `s` — секунди від T0 (час заморожується, інакше «зараз» далеко від T0)."""
        with freeze_time(self.at(s if s is not None else 5)):
            return self.panel._f3d_fire_sync(full=True)

    def ev(self, etype, **dom):
        domain = [('etype', '=', etype)] + [(k, '=', v) for k, v in dom.items()]
        return self.env['f3d.fire.event'].search(domain)

    # --- люди й навчання ---------------------------------------------------------------------------------
    def make_employee(self, name, code=None):
        vals = {'name': name}
        if code:
            vals['f3d_code'] = code
        return self.env['hr.employee'].create(vals)

    def make_att(self, emp, check_in, check_out=None):
        vals = {'employee_id': emp.id, 'check_in': check_in}
        if check_out:
            vals['check_out'] = check_out
        return self.env['hr.attendance'].create(vals)

    def new_drill(self, **vals):
        vals.setdefault('title', 'Тестове навчання')
        return self.env['f3d.fire.drill'].with_user(self.d).create(vals)

    @contextmanager
    def viewer_installed(self, flag):
        from odoo.addons.factory3d_base.models.f3d_scene_mixin import F3dSceneMixin
        with mock.patch.object(F3dSceneMixin, '_f3d_viewer_installed', return_value=flag):
            yield
