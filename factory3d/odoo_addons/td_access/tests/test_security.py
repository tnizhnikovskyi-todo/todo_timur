import re

from lxml import etree

from odoo.exceptions import AccessError
from odoo.tests import Form, HttpCase, new_test_user, tagged
from odoo.tests.common import JsonRpcException

from ..tools import params as P
from .common import AccessCase, FakeBioStar

# Матриця SPEC §13.3: модель -> {користувач: операції (R, W, C, D)}
MATRIX = {
    'td.access.server': {'user_admin': 'R', 'user_f3d_admin': 'RWCD'},
    'td.access.device': {'user_f3d': 'R', 'user_security': 'R', 'user_admin': 'RWCD', 'user_f3d_admin': 'RWCD'},
    'td.access.door': {'user_f3d': 'R', 'user_security': 'RW', 'user_admin': 'RWCD', 'user_f3d_admin': 'RWCD'},
    'td.access.user.link': {'user_security': 'R', 'user_hr': 'R', 'user_admin': 'RWCD', 'user_f3d_admin': 'RWCD'},
    'td.access.event': {'user_security': 'R', 'user_hr': 'R', 'user_admin': 'R', 'user_f3d_admin': 'RWCD'},
    'td.access.card': {'user_security': 'RWC', 'user_admin': 'RWCD', 'user_f3d_admin': 'RWCD'},
    'td.access.visitor': {'user_security': 'RWCD', 'user_hr': 'R', 'user_admin': 'RWCD', 'user_f3d_admin': 'RWCD'},
    'td.access.presence': {'user_security': 'R', 'user_hr': 'R', 'user_admin': 'R', 'user_f3d_admin': 'R'},
}
USERS = ('user_plain', 'user_f3d', 'user_security', 'user_hr', 'user_admin', 'user_f3d_admin')
OPS = {'R': 'read', 'W': 'write', 'C': 'create', 'D': 'unlink'}
SEC, ADM, FADM = ('td_access.group_td_access_security', 'td_access.group_td_access_admin',
                  'td_factory3d.group_td_admin')
HR = 'hr_attendance.group_hr_attendance_user'
MENUS = [  # xml-id, батько, sequence, групи
    ('menu_td_access', 'td_factory3d.menu_td_root', 70, {SEC}),
    ('menu_td_access_presence', 'menu_td_access', 10, {SEC}),
    ('menu_td_access_event', 'menu_td_access', 20, {SEC}),
    ('menu_td_access_visitor', 'menu_td_access', 30, {SEC}),
    ('menu_td_access_door', 'menu_td_access', 40, {SEC}),
    ('menu_td_access_device', 'menu_td_access', 50, {SEC}),
    ('menu_td_access_card', 'menu_td_access', 60, {SEC}),
    ('menu_td_access_user_link', 'menu_td_access', 70, {ADM}),
    ('menu_td_access_reprocess', 'menu_td_access', 80, {ADM}),
    ('menu_td_access_server', 'menu_td_access', 90, {FADM}),
    ('menu_td_access_att_report', 'hr_attendance.menu_hr_attendance_reporting', 20, {HR, SEC}),
    ('menu_td_access_att_server', 'hr_attendance.menu_hr_attendance_configuration', 50, {FADM}),
    ('menu_td_access_settings', 'td_factory3d.menu_td_config', 70, {FADM}),
]


@tagged('post_install', '-at_install', 'f3d', 'f3d_access')
class TestSecurity(AccessCase):

    def _ref(self, xmlid):
        return self.env.ref(xmlid if '.' in xmlid else 'td_access.' + xmlid)

    def test_acl_matrix(self):  # AC-62, ТБ-01
        for model, rules in MATRIX.items():
            for user_name in USERS:
                allowed = rules.get(user_name, '')
                user = getattr(self, user_name)
                for letter, op in OPS.items():
                    with self.subTest(model=model, user=user_name, op=op):
                        self.assertEqual(self.env[model].with_user(user).has_access(op), letter in allowed)

    def test_buttons_rights(self):  # ТБ-01
        server = self.server
        with self.assertRaises(AccessError):
            server.with_user(self.user_security).action_poll_now()
        with self.assertRaises(AccessError):
            server.with_user(self.user_admin).action_test_connection()
        with self.assertRaises(AccessError):
            server.with_user(self.user_admin).action_reset_cursor()
        server.with_user(self.user_f3d_admin).action_reset_cursor()
        with self.patch_client(FakeBioStar()):
            P.set_param(self.env, 'read_enabled', 'True')
            server.with_user(self.user_admin).action_poll_now()

    def test_public_presence_fields(self):  # AC-62, ТБ-07
        public = self.env['hr.employee.public'].with_user(self.user_security).browse(self.emp_a.id)
        data = public.read(['td_access_present', 'td_access_zone_id'])
        self.assertEqual(data[0]['td_access_present'], False)
        with self.assertRaises(AccessError):
            self.emp_a.with_user(self.user_security).read(['td_access_last_event_id'])
        with self.assertRaises(AccessError):
            self.emp_a.with_user(self.user_security).read(['td_access_card_ids'])
        pres = self.env['hr.employee']._f3d_access_public_presence(['OP-TST-A'])
        self.assertEqual(set(pres['OP-TST-A']), {'present', 'zone', 'zone_since', 'last_event'})

    def test_card_rules(self):  # AC-63
        Card = self.env['td.access.card']
        vals = {'server_id': self.server.id, 'holder_type': 'employee', 'employee_id': self.emp_a.id}
        with self.assertRaises(AccessError):
            Card.with_user(self.user_security).create(dict(vals, number='1001'))
        pool = Card.with_user(self.user_security).create(
            {'server_id': self.server.id, 'holder_type': 'pool', 'number': '1002'})
        self.assertTrue(pool.exists())
        owned = Card.with_user(self.user_admin).create(dict(vals, number='1003'))
        with self.assertRaises(AccessError):
            owned.with_user(self.user_security).write({'block_reason': 'x'})
        owned.with_user(self.user_admin).write({'block_reason': 'x'})
        self.assertEqual(owned.sudo().block_reason, 'x')

    def test_company_rules(self):  # AC-63
        company_b = self.env['res.company'].create({'name': 'Компанія B (тест СКУД)'})
        server_b = self.env['td.access.server'].create({
            'name': 'BioStar B', 'url': 'https://other-sim:8443', 'company_id': company_b.id})
        user = self.user_admin
        self.assertTrue(company_b not in user.company_ids)
        visible = self.env['td.access.server'].with_user(user).search([])
        self.assertNotIn(server_b, visible)
        self.assertIn(self.server, self.env['td.access.server'].with_user(self.user_f3d_admin).search([]))

    def test_no_biometric_fields(self):  # AC-64
        forbidden = re.compile(r'photo|image|template|document|fingerprint_data')
        allowed = {'document_checked'}  # прапорець перевірки документа відвідувача (V-08), без даних документа
        names = [m for m in self.env.registry.models
                 if m.startswith('td.access.') or m == 'td.viewer.provider.access']
        self.assertTrue(len(names) >= 8)
        for model in names:
            for name in self.env[model]._fields:
                if name not in allowed:
                    self.assertIsNone(forbidden.search(name), '%s.%s' % (model, name))
        for model in ('hr.employee', 'hr.attendance'):
            for name in self.env[model]._fields:
                if name.startswith('td_access') or name.startswith('td_in') or name.startswith('td_out'):
                    self.assertIsNone(forbidden.search(name), '%s.%s' % (model, name))

    def test_keep_raw(self):  # AC-64
        def row(i, minute):
            data = self.prow(i, '2026-10-12T03:%02d:00.00Z' % minute, 4102, 'TSTA1', tna='1')
            data['user_id'].update({'name': 'Тест А', 'photo_exists': 'true'})
            return data
        self.assertFalse(self.feed(row(1, 52)).sudo().raw)
        P.set_param(self.env, 'keep_raw', 'True')
        raw = self.feed(row(2, 53)).sudo().raw
        self.assertTrue(raw)
        self.assertNotIn('name', raw['user_id'])
        self.assertNotIn('photo_exists', raw['user_id'])
        self.assertNotIn('hint', raw)

    def test_menus(self):  # AC-65
        for xmlid, parent, seq, groups in MENUS:
            with self.subTest(menu=xmlid):
                menu = self._ref(xmlid)
                self.assertEqual(menu.parent_id, self._ref(parent))
                self.assertEqual(menu.sequence, seq)
                self.assertEqual(set(menu.group_ids.get_external_id().values()), groups)
        self.assertEqual(self._ref('menu_td_access').sequence, 70)

    def test_views_arch(self):  # AC-66
        admin = self.env.ref('base.user_admin')

        def arch(model, view_type, **kw):
            return etree.fromstring(self.env[model].with_user(admin).get_view(view_type=view_type, **kw)['arch'])
        self.assertTrue(arch('hr.employee', 'form').xpath("//page[@name='f3d_access']"))
        self.assertTrue(arch('hr.attendance', 'form').xpath("//field[@name='td_in_event_id']"))
        self.assertTrue(arch('res.config.settings', 'form').xpath("//block[@name='f3d_access_block']"))
        self.assertTrue(arch('td.zone', 'form').xpath("//button[@name='action_view_people']"))
        self.assertEqual(arch('td.access.presence', 'kanban').get('default_group_by'), 'zone_id')

    def test_settings_menu(self):  # AC-69
        menu = self._ref('menu_td_access_settings')
        action = self._ref('action_td_access_settings')
        self.assertEqual((menu.parent_id, menu.sequence), (self._ref('td_factory3d.menu_td_config'), 70))
        self.assertEqual(menu.group_ids, self._ref(FADM))
        self.assertEqual(menu.action, action)
        self.assertEqual((action.res_model, action.view_mode, action.target),
                         ('res.config.settings', 'form', 'current'))
        self.assertIn("'hr_attendance'", action.context)
        views = self.env['res.config.settings'].with_user(self.env.ref('base.user_admin')).get_views([[False, 'form']])
        self.assertIn('f3d_access_block', views['views']['form']['arch'])
        visible_security = self.env['ir.ui.menu'].with_user(self.user_security)._visible_menu_ids()
        self.assertNotIn(menu.id, visible_security)
        self.assertIn(menu.id, self.env['ir.ui.menu'].with_user(self.env.ref('base.user_admin'))._visible_menu_ids())


@tagged('post_install', '-at_install', 'f3d', 'f3d_access')
class TestGuardLogin(HttpCase):
    """A-1, ТБ-01: під реальним логіном охорони двері змінюються лише зняттям тривоги (SPEC §4.1, §13.3)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.login = 'f3d_guard_login'
        new_test_user(cls.env, cls.login, groups='base.group_user,td_access.group_td_access_security',
                      password=cls.login)
        cls.door = cls.env.ref('td_access.door_turn_1')

    def _call(self, method, *args):
        model = 'td.access.door'
        return self.make_jsonrpc_request(
            '/web/dataset/call_kw/%s/%s' % (model, method),
            {'model': model, 'method': method, 'args': list(args), 'kwargs': {}})

    def test_guard_only_acks_alarm(self):
        name, dwell = self.door.name, self.door.dwell_min
        self.door.sudo().write({'alarm': True, 'alarm_reason': 'fire'})
        self.authenticate(self.login, self.login)
        attempts = [
            ('write', [self.door.id], {'name': 'Зламано'}),
            ('write', [self.door.id], {'dwell_min': 5}),
            ('write', [self.door.id], {'active': False}),
            ('write', [self.door.id], {'alarm': True, 'alarm_reason': 'forced'}),  # тривогу не виставляють
            ('write', [self.door.id], {'name': 'Зламано', 'alarm': False}),
            ('unlink', [self.door.id]),
            ('create', {'name': 'Нові', 'code': 'TURN-X', 'server_id': self.door.server_id.id}),
        ]
        for method, *args in attempts:
            with self.subTest(method=method, args=args):
                with self.assertRaises(JsonRpcException) as cm:
                    self._call(method, *args)
                self.assertIn('AccessError', str(cm.exception))
        self.env.invalidate_all()
        self.assertEqual((self.door.name, self.door.dwell_min, self.door.active), (name, dwell, True))
        self.assertEqual((self.door.alarm, self.door.alarm_reason), (True, 'fire'))
        # підтвердження тривоги працює і кнопкою, і прямим записом alarm*
        self.assertTrue(self._call('action_ack_alarm', [self.door.id]))
        self.env.invalidate_all()
        self.assertEqual((self.door.alarm, self.door.alarm_reason), (False, False))
        self.door.sudo().write({'alarm': True, 'alarm_reason': 'held'})
        self.assertTrue(self._call('write', [self.door.id], {'alarm': False, 'alarm_reason': False}))
        self.env.invalidate_all()
        self.assertFalse(self.door.alarm)


@tagged('post_install', '-at_install', 'f3d', 'f3d_access')
class TestDoorFormReadonly(AccessCase):
    """SPEC §4.1: поля дверей у формі readonly для охорони (не лише відмова при збереженні); адміністратор редагує."""

    VIEW = 'td_access.view_td_access_door_form'

    def test_fields_readonly_for_guard_editable_for_admin(self):
        door = self.env.ref('td_access.door_turn_1')
        with Form(door.with_user(self.user_security), view=self.VIEW) as form:
            for fname, value in (('name', 'Зламано'), ('code', 'TURN-X'), ('dwell_min', 5), ('is_perimeter', True),
                                 ('active', False), ('kind', 'door')):
                with self.subTest(field=fname), self.assertRaises(AssertionError):
                    setattr(form, fname, value)
        with Form(door.with_user(self.user_admin), view=self.VIEW) as form:
            form.dwell_min = 7
        self.assertEqual(door.dwell_min, 7)
