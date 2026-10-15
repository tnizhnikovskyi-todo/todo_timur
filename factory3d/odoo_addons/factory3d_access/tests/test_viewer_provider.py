import inspect
import re
import sys
import types
from datetime import datetime
from unittest.mock import patch

from odoo.tests import tagged

from ..models.f3d_access_event import F3dAccessEvent
from .common import AccessCase, FakeBioStar

CTX = {'now': datetime(2026, 10, 12, 7, 30), 'now_local': '2026-10-12 10:30', 'today': '2026-10-12'}
ACCESS_KEYS = {'updated', 'server', 'on_site', 'today', 'zones', 'people', 'visitors', 'readers', 'doors', 'cards',
               'last_events'}


def _deep_merge(dst, src):
    """Запасний deep_merge (viewer M-01), коли factory3d_viewer немає в addons_path."""
    for key, value in src.items():
        if isinstance(value, dict) and isinstance(dst.get(key), dict):
            _deep_merge(dst[key], value)
        else:
            dst[key] = value
    return dst


def viewer_payload_stub():
    """Підміна `odoo.addons.factory3d_viewer.tools.payload` лише якщо справжнього модуля немає."""
    try:
        from odoo.addons.factory3d_viewer.tools import payload  # noqa: F401
        return patch.dict(sys.modules, {})
    except ImportError:
        mods = {}
        for name in ('odoo.addons.factory3d_viewer', 'odoo.addons.factory3d_viewer.tools'):
            mods[name] = types.ModuleType(name)
            mods[name].__path__ = []
        leaf = types.ModuleType('odoo.addons.factory3d_viewer.tools.payload')
        leaf.deep_merge = _deep_merge
        mods['odoo.addons.factory3d_viewer.tools.payload'] = leaf
        return patch.dict(sys.modules, mods)


@tagged('post_install', '-at_install', 'f3d', 'f3d_access')
class TestProvider(AccessCase):

    def setUp(self):
        super().setUp()
        self.provider = self.env['f3d.viewer.provider.access']
        self.payload = {
            'employees': {'OP-TST-A': {'name': 'А', 'present': False}, 'OP-TST-B': {'name': 'Б', 'present': True}},
            'zones': {'Z-CUT': {'name': 'Розкрій'}}}

    def _enter_a(self):
        """emp_a входить через TURN-1 о 06:52 (Київ) і лишається в Z-CUT."""
        self.feed(self.prow(1, '2026-10-12T03:52:00.00Z', 4102, 'TSTA1', tna='1'))

    def _visitor(self):
        visitor = self.env['f3d.access.visitor'].create({
            'name': 'Іван Петренко', 'host_employee_id': self.emp_a.id,
            'date_from': datetime(2026, 10, 12, 5, 0), 'date_to': datetime(2026, 10, 12, 15, 0)})
        visitor.write({'state': 'on_site', 'present': True, 'zone_id': self.z['Z-OFFICE'].id,
                       'zone_since': datetime(2026, 10, 12, 6, 10), 'arrived_at': datetime(2026, 10, 12, 6, 10)})
        return visitor

    def test_employee_keys(self):  # AC-49
        self._enter_a()
        out = self.provider.with_user(self.user_f3d)._f3d_viewer_collect(self.payload, dict(CTX))
        a, b = out['employees']['OP-TST-A'], out['employees']['OP-TST-B']
        self.assertEqual((a['present'], a['zone'], a['zone_since']), (True, 'Z-CUT', '2026-10-12 06:52'))
        self.assertEqual(set(a['last_event']), {'ts', 'door', 'direction', 'type'})
        self.assertEqual((b['present'], b['zone']), (False, None))
        self.assertEqual(set(out['employees']), {'OP-TST-A', 'OP-TST-B'})

    def test_zone_people_now(self):  # AC-49
        self._enter_a()
        out = self.provider.with_user(self.user_f3d)._f3d_viewer_collect(self.payload, dict(CTX))
        self.assertEqual(out['zones']['Z-CUT']['people_now'], 1)
        out = self.provider.with_user(self.user_f3d)._f3d_viewer_collect(
            {'zones': {'Z-ASM': {}}}, dict(CTX))
        self.assertEqual(out['zones']['Z-ASM']['people_now'], 0)

    def _paint_pass(self):
        self.feed(self.prow(1, '2026-10-12T03:52:00.00Z', 4102, 'TSTA1', tna='1'),
                  self.prow(2, '2026-10-12T07:20:00.00Z', 4102, 'TSTB2', where='paint'))

    def test_access_schema_user(self):  # AC-50
        self._paint_pass()
        self._visitor()
        out = self.provider.with_user(self.user_f3d)._f3d_viewer_collect(self.payload, dict(CTX))
        access = out['access']
        self.assertEqual(set(access), ACCESS_KEYS)
        self.assertEqual(access['last_events'], [])
        self.assertEqual(len(access['visitors']), 1)
        self.assertNotIn('name', access['visitors'][0])
        self.assertEqual(access['on_site']['visitors'], 1)
        self.assertEqual(access['on_site']['total'], access['on_site']['employees'] + 1)
        row = dict(access['cards']['ACCESS']['rows'])['Останній доступ']
        self.assertNotIn(' — ', row)
        self.assertTrue(row.startswith('склад ЛФМ, 10:20'), row)
        self.assertEqual(access['server']['name'], self.server.name)
        self.assertIn('ACR-PAINT', access['readers'])
        self.assertIn('TURN-1', access['doors'])
        self.assertEqual(access['today']['passes'], 2)

    def test_access_schema_security(self):  # AC-50
        self._paint_pass()
        self._visitor()
        access = self.provider.with_user(self.user_security)._f3d_viewer_collect({}, dict(CTX))['access']
        self.assertTrue(access['last_events'])
        self.assertTrue(all('person' in e for e in access['last_events']))
        self.assertIn('OP-TST-B', {e['person'] for e in access['last_events']})
        self.assertEqual(access['visitors'][0]['name'], 'Іван Петренко')
        row = dict(access['cards']['ACCESS']['rows'])['Останній доступ']
        self.assertEqual(row, 'склад ЛФМ, 10:20 — Тест Б')

    def test_infra_cards_replaced(self):  # AC-50
        payload = {'infra': {'cards': {'TURNSTILES': {'rows': [['На території', '146 працівників · 3 відвідувачі']]},
                                       'ACCESS': {'rows': [['Дверей', '312']]}, 'OTHER': {'rows': [['x', 'y']]}}}}
        out = self.provider.with_user(self.user_f3d)._f3d_viewer_collect(payload, dict(CTX))
        cards = out['infra']['cards']
        self.assertEqual(cards['TURNSTILES']['rows'], out['access']['cards']['TURNSTILES']['rows'])
        self.assertNotIn('146', str(cards['TURNSTILES']['rows']))
        self.assertEqual(cards['ACCESS']['rows'][0], ['Дверей з рідерами', '5'])
        self.assertEqual(cards['OTHER'], {'rows': [['x', 'y']]})

    def test_plural_forms(self):
        rows = self.provider._f3d_cards(
            {'employees_on_site': 21, 'visitors': [{}, {}, {}], 'today': {'passes': 0}, 'doors_with_readers': 5,
             'last_pass': None}, None, False)['TURNSTILES']['rows']
        self.assertEqual(rows[0][1], '21 працівник · 3 відвідувачі')

    def _delta_ctx(self, **changes):
        return dict(CTX, changes=changes)

    def test_delta_deep_merge(self):  # AC-51, AC-67
        self._enter_a()
        patch_ = {'infra': {'cards': {'PV-INV': {'rows': [['Зараз', '468 кВт']]}}, 'totals': {'pv_now': 468}},
                  'employees': {'OP-TST-A': {'name': 'А', 'workcenter': 'SAW-1'}}}
        inf = patch_['infra']
        ctx = self._delta_ctx(**{'hr.employee': {'OP-TST-A'}})
        with viewer_payload_stub():
            self.provider.with_user(self.user_f3d)._f3d_viewer_delta(patch_, ctx)
        self.assertIs(patch_['infra'], inf)
        self.assertEqual(set(inf['cards']), {'PV-INV', 'TURNSTILES', 'ACCESS'})
        self.assertEqual(inf['cards']['PV-INV'], {'rows': [['Зараз', '468 кВт']]})
        self.assertEqual(inf['totals'], {'pv_now': 468})
        emp = patch_['employees']['OP-TST-A']
        self.assertEqual((emp['name'], emp['workcenter'], emp['present'], emp['zone']), ('А', 'SAW-1', True, 'Z-CUT'))
        self.assertEqual(set(emp), {'name', 'workcenter', 'present', 'zone', 'zone_since', 'last_event'})
        self.assertEqual(set(patch_), {'access', 'employees', 'zones', 'infra'})
        self.assertEqual(set(ACCESS_KEYS) - set(patch_['access']), set())
        self.assertEqual(inf['cards']['TURNSTILES']['rows'], patch_['access']['cards']['TURNSTILES']['rows'])

    def test_delta_zones_and_employees(self):  # AC-51
        self._enter_a()
        patch_ = {}
        ctx = self._delta_ctx(**{'hr.employee': {'OP-TST-A'}, 'f3d.access.door': {'TURN-1'}})
        with viewer_payload_stub():
            self.provider.with_user(self.user_f3d)._f3d_viewer_delta(patch_, ctx)
        self.assertEqual(set(patch_), {'access', 'employees', 'zones', 'infra'})
        self.assertEqual(set(patch_['employees']), {'OP-TST-A'})
        self.assertEqual(set(patch_['employees']['OP-TST-A']), {'present', 'zone', 'zone_since', 'last_event'})
        zones = self.env['f3d.zone'].search([]).mapped('f3d_code')
        self.assertEqual(set(patch_['zones']), set(zones))
        self.assertEqual(patch_['zones']['Z-CUT']['people_now'], 1)
        self.assertEqual(sum(v['people_now'] for k, v in patch_['zones'].items() if k != 'Z-CUT'), 0)
        self.assertEqual(set(patch_['infra']['cards']), {'TURNSTILES', 'ACCESS'})

    def test_delta_no_changes(self):  # AC-51
        patch_ = {}
        self.provider._f3d_viewer_delta(patch_, self._delta_ctx(**{'mrp.production': {'WH/MO/00231'}}))
        self.assertEqual(patch_, {})
        self.provider._f3d_viewer_delta(patch_, dict(CTX))
        self.assertEqual(patch_, {})

    def test_delta_keeps_foreign_keys(self):  # AC-67
        patch_ = {'zones': {'Z-CUT': {'name': 'Розкрій', 'wip': 3}}}
        ctx = self._delta_ctx(**{'f3d.access.visitor': {'V-1'}})
        with viewer_payload_stub():
            self.provider._f3d_viewer_delta(patch_, ctx)
        self.assertEqual((patch_['zones']['Z-CUT']['name'], patch_['zones']['Z-CUT']['wip']), ('Розкрій', 3))
        self.assertIn('people_now', patch_['zones']['Z-CUT'])

    def test_bus_calls(self):  # AC-51
        rows = [self.prow(1, '2026-10-12T03:52:00.00Z', 4102, 'TSTA1', tna='1'),
                self.prow(2, '2026-10-12T03:52:00.00Z', 4102, 'TSTB2', tna='1'),
                self.prow(3, '2026-10-12T03:52:01.00Z', 20480, None)]
        with patch.object(F3dAccessEvent, '_f3d_bus') as bus:
            self.poll('2026-10-12 04:00:00', FakeBioStar(events=rows))
        calls = {call.args[0]: set(call.args[1]) for call in bus.call_args_list}
        self.assertEqual(calls['hr.employee'], {'OP-TST-A', 'OP-TST-B'})
        self.assertEqual(calls['f3d.access.door'], {'TURN-1'})
        self.assertEqual(bus.call_count, len(calls))

    def test_visitor_bus(self):
        visitor = self._visitor()
        with patch.object(F3dAccessEvent, '_f3d_bus') as bus:
            self.assertTrue(visitor._f3d_presence_set({'zone_id': self.z['Z-ASM'].id}))
            self.assertFalse(visitor._f3d_presence_set({'zone_id': self.z['Z-ASM'].id}))
        bus.assert_called_once_with('f3d.access.visitor', {'V-%d' % visitor.id})

    def test_no_viewer_ok(self):  # AC-52
        self.assertNotIn('f3d.viewer.event', self.env)
        self.assertIsNone(self.env['f3d.access.event']._f3d_bus('hr.employee', {'OP-TST-A'}))
        events = self.feed(self.prow(1, '2026-10-12T03:52:00.00Z', 4102, 'TSTA1', tna='1'))
        self.assertEqual(events.process_state, 'done')

    def test_registry_attrs(self):  # AC-52
        provider = self.env['f3d.viewer.provider.access']
        self.assertEqual((provider._f3d_sequence, provider._f3d_sections, provider._f3d_group),
                         (170, ('access',), 'factory3d_base.group_f3d_user'))
        self.assertEqual(provider._f3d_viewer_bus_models(), ['hr.employee', 'f3d.access.door', 'f3d.access.visitor'])

    def test_sudo_only_in_public_presence(self):  # A-21
        import odoo.addons.factory3d_access.models.viewer_provider as module
        self.assertIsNone(re.search(r'\.sudo\(', inspect.getsource(module)))
        employee = inspect.getsource(type(self.env['hr.employee'])._f3d_access_public_presence)
        self.assertIn('.sudo()', employee)
