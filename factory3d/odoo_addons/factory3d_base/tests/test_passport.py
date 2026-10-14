from psycopg2 import IntegrityError

from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger

from odoo.addons.factory3d_base.hooks import codes, passports

from .common import F3DCase


@tagged('post_install', '-at_install', 'f3d', 'f3d_base')
class TestPassportData(F3DCase):

    def passport(self, role):
        return self.env.ref('factory3d_base.passport_' + role)

    def test_93_passports(self):
        self.assertEqual(self.env['f3d.equipment.passport'].search_count([]), 93)

    def test_beam_saw_fields(self):
        p = self.passport('beam_saw')
        self.assertEqual(p.manufacturer, 'HOMAG')
        self.assertEqual(p.model, 'SAWTEQ S-310 з підйомним столом (S-310/43/22)')
        self.assertEqual((p.dim_l_mm, p.dim_w_mm, p.dim_h_mm), (9957, 6514, 0))
        self.assertEqual(p.power_kw, 11)
        self.assertEqual(p.connected_kw, 0)
        self.assertTrue(p.connected_note)
        self.assertEqual(p.dimensions, '9957 × 6514 × —')
        self.assertEqual(p.name, 'HOMAG ' + p.model)

    def test_spec_counts(self):
        Spec = self.env['f3d.equipment.spec']
        self.assertEqual(Spec.search_count([]), 999)
        specs = self.passport('beam_saw').spec_ids
        self.assertEqual(len(specs), 14)
        self.assertEqual(specs[0].name, 'Довжина різу')
        self.assertEqual(specs[0].value_text, '4300 мм (ряд 3200 / 3800 / 4300 / 5600)')
        lumen = self.passport('highbay').spec_ids.filtered(lambda s: s.key == 'lumen')
        self.assertEqual((lumen.value_num, lumen.uom), (20500, 'лм'))

    def test_sources(self):
        self.assertEqual(self.env['f3d.equipment.source'].search_count([]), 252)
        sources = self.passport('beam_saw').source_ids
        self.assertEqual(len(sources.filtered(lambda s: s.kind == 'main')), 2)
        self.assertEqual(len(sources.filtered(lambda s: s.kind == 'connected')), 2)
        self.assertEqual(sources[0].name, 'www.homag.com')

    def test_extra_numeric_keys(self):
        keyed = self.env['f3d.equipment.spec'].search([('key', '!=', False)])
        self.assertEqual(len(keyed), 48)
        self.assertEqual(self.passport('highbay').get_num('watt'), 126.0)
        self.assertEqual(self.passport('genset').get_num('kva') > 0, True)


@tagged('post_install', '-at_install', 'f3d', 'f3d_base')
class TestPassportApi(F3DCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.beam_saw = cls.env.ref('factory3d_base.passport_beam_saw')
        cls.eq.write({'f3d_passport_id': cls.beam_saw.id})

    def test_get_num(self):
        highbay = self.env.ref('factory3d_base.passport_highbay')
        self.assertEqual(highbay.get_num('lumen'), 20500.0)
        self.assertEqual(highbay.get_num('watt'), 126.0)
        self.assertIsNone(self.beam_saw.get_num('connected_kw'))
        self.assertEqual(self.beam_saw.get_num('power_kw'), 11.0)
        self.assertIsNone(self.beam_saw.get_num('nope'))
        controller = self.env['f3d.equipment.spec'].search([('key', '=', 'controller')], limit=1)
        self.assertIsNone(controller.passport_id.get_num('controller'))  # текстовий ключ
        self.assertEqual(self.eq.f3d_get_num('power_kw'), 11.0)
        self.assertIsNone(self.env['maintenance.equipment'].create({'name': 'X'}).f3d_get_num('lumen'))

    def test_equipment_related(self):
        eq = self.eq
        self.assertEqual(eq.f3d_role, 'beam_saw')
        self.assertEqual(eq.f3d_manufacturer, 'HOMAG')
        self.assertEqual(eq.f3d_power_kw, 11)
        self.assertEqual(eq.f3d_dimensions, '9957 × 6514 × —')
        self.assertEqual(len(eq.f3d_spec_ids), 14)
        self.assertEqual(len(eq.f3d_source_ids), 4)
        self.assertEqual(eq.f3d_units, 1)

    def test_unit_count(self):
        second = self.env['maintenance.equipment'].create(
            {'name': 'Пила-Т2', 'f3d_passport_id': self.beam_saw.id})
        self.assertEqual(self.beam_saw.unit_count, 2)
        self.assertEqual(second.f3d_units, 2)
        self.assertEqual(self.beam_saw.action_view_equipment()['domain'],
                         [('f3d_passport_id', '=', self.beam_saw.id)])

    def test_role_unique(self):
        Passport = self.env['f3d.equipment.passport']
        vals = {'role': 'beam_saw', 'manufacturer': 'X', 'model': 'Y'}
        with self.assertRaises(IntegrityError), mute_logger('odoo.sql_db'), self.cr.savepoint():
            Passport.create(vals)
        with self.assertRaises(ValidationError):
            Passport.create(dict(vals, role='Bad-Role'))

    def test_spec_key_unique(self):
        Spec = self.env['f3d.equipment.spec']
        vals = {'passport_id': self.beam_saw.id, 'name': 'T', 'value_text': '1', 'key': 'zz'}
        Spec.create(vals)
        with self.assertRaises(IntegrityError), mute_logger('odoo.sql_db'), self.cr.savepoint():
            Spec.create(vals)
        Spec.create(dict(vals, key=False))  # порожні ключі без обмеження
        Spec.create(dict(vals, key=False))
        with self.assertRaises(ValidationError):
            Spec.create({'passport_id': self.beam_saw.id, 'name': 'Порожній', 'value_text': False})

    def test_source_url_check(self):
        Source = self.env['f3d.equipment.source']
        src = Source.create({'passport_id': self.beam_saw.id, 'url': 'https://example.com/a.pdf'})
        self.assertEqual(src.name, 'example.com')
        with self.assertRaises(ValidationError):
            Source.create({'passport_id': self.beam_saw.id, 'url': 'ftp://example.com'})


@tagged('post_install', '-at_install', 'f3d', 'f3d_base')
class TestPassportLink(F3DCase):

    def test_link_from_table_synthetic(self):
        Eq = self.env['maintenance.equipment']
        edge, swb, charging = (Eq.create({'name': c, 'f3d_code': c}) for c in ('EDGE-1', 'SWB-1', 'CHARGING'))
        res = passports.link(self.env)
        self.assertEqual(res, {'linked': 2, 'components': 3, 'no_passport': 1})
        self.assertEqual(edge.f3d_passport_id.role, 'edgebander_laser')
        self.assertEqual(edge.f3d_component_passport_ids.mapped('role'), ['robot_return'])
        self.assertEqual(swb.f3d_passport_id.role, 'main_switchboard')
        self.assertEqual(set(swb.f3d_component_passport_ids.mapped('role')), {'acb', 'power_meter'})
        self.assertFalse(charging.f3d_passport_id)
        self.assertEqual(passports.link(self.env), res)  # повтор
        self.assertEqual(self.env.ref('factory3d_base.passport_robot_return').component_count, 1)


@tagged('post_install', '-at_install', 'f3d', 'f3d_base')
class TestCodesHooks(F3DCase):

    def test_locations(self):  # AC-10
        Loc = self.env['stock.location']
        if 'f3d_code' not in Loc._fields:
            self.skipTest("stock.location без домішки — W3")
        stock = self.wh.lot_stock_id
        stock.barcode = 'WHSTOCK'
        loc_a = Loc.create({'name': 'A', 'usage': 'internal', 'location_id': stock.id, 'barcode': 'A-1'})
        loc_b = Loc.create({'name': 'B', 'usage': 'internal', 'location_id': stock.id, 'barcode': 'b-1'})
        res = codes.locations(self.env)
        self.assertEqual(loc_a.f3d_code, 'A-1')
        self.assertFalse(loc_b.f3d_code)
        self.assertFalse(stock.f3d_code)
        self.assertGreaterEqual(res['locations'], 1)
        self.assertEqual(codes.locations(self.env)['locations'], 0)

    def test_workcenters(self):  # AC-12
        wc = self.env['mrp.workcenter'].create({'name': 'T', 'code': 'T-9'})
        self.assertEqual(codes.workcenters(self.env)['workcenters'], 2)  # + SAW-T з F3DCase
        self.assertEqual(wc.f3d_code, 'T-9')
        self.assertEqual(codes.workcenters(self.env)['workcenters'], 0)

    def test_employees(self):  # AC-13
        Emp = self.env['hr.employee']
        emps = {b: Emp.create({'name': b, 'barcode': b}) for b in ('OPSAW1', 'OPW3', 'OPNEW7', 'ZZ')}
        if 'employee_ids' in self.env['mrp.workcenter']._fields:
            wc = self.env['mrp.workcenter'].create({'name': 'N7', 'f3d_code': 'NEW-7'})
            wc.employee_ids = [(4, emps['OPNEW7'].id)]
            expected_new7 = 'OP-NEW-7'
        else:  # у CE немає mrp.workcenter.employee_ids — код із РЦ недосяжний
            expected_new7 = False
        res = codes.employees(self.env)
        self.assertEqual(emps['OPSAW1'].f3d_code, 'OP-SAW-1')
        self.assertEqual(emps['OPW3'].f3d_code, 'OP-W3')
        self.assertEqual(emps['OPNEW7'].f3d_code, expected_new7)
        self.assertFalse(emps['ZZ'].f3d_code)
        self.assertEqual(res['employees'], 2 + bool(expected_new7))
        self.assertEqual(codes.employees(self.env)['employees'], 0)

    def test_equipment_resolution(self):  # AC-14, R-07
        Eq = self.env['maintenance.equipment']
        saw, fl1, fl2, zz = (Eq.create({'name': s, 'serial_no': s})
                             for s in ('SAW-1', 'FL-4369', 'FL-4912', 'ZZ-1'))
        self.env['ir.model.data'].create({
            'module': 'factory3d', 'name': 'eq_fl_1', 'model': 'maintenance.equipment', 'res_id': fl1.id})
        res = codes.equipment(self.env)
        self.assertEqual((saw.f3d_code, fl1.f3d_code, fl2.f3d_code), ('SAW-1', 'FL-1', 'FL-2'))
        self.assertFalse(zz.f3d_code)
        self.assertEqual((res['by_serial'], res['by_xmlid_or_legacy'], res['equipment']), (1, 2, 3))
        # unmatched: ZZ-1 і SAW-T з F3DCase
        self.assertEqual(res['unmatched'], Eq.search_count([('f3d_code', '=', False)]))
        self.assertEqual(codes.equipment(self.env)['equipment'], 0)


@tagged('post_install', '-at_install', 'f3d', 'f3d_base')
class TestLocationKinds(F3DCase):

    def setUp(self):
        super().setUp()
        Loc = self.env['stock.location']
        if 'f3d_loc_kind' not in Loc._fields:
            self.skipTest("stock.location.f3d_loc_kind відсутнє (файл W3)")
        parent = self.wh.view_location_id
        self.plt, self.fur = (Loc.create({'name': c, 'usage': 'internal', 'location_id': parent.id,
                                          'f3d_code': c}) for c in ('PLT-T1', 'FUR-T1'))
        self.dock = Loc.create({'name': 'Док-Т1', 'usage': 'internal', 'location_id': parent.id,
                                'f3d_code': 'DOCK-T1', 'f3d_alias': 'UNLOAD-T1'})
        self.rows = [{'code': 'PLT-T1', 'kind': 'stack', 'capacity': '60'},
                     {'code': 'FUR-T1', 'kind': 'bin', 'capacity': '66'},
                     {'code': 'UNLOAD-T1', 'kind': 'area', 'capacity': ''}]

    def test_kind_capacity_from_table(self):  # AC-53
        with self.with_data_file('scene_locations.csv', self.rows):
            res = codes.locations(self.env)
        self.assertEqual((self.plt.f3d_loc_kind, self.plt.f3d_capacity), ('stack', 60))
        self.assertEqual((self.fur.f3d_loc_kind, self.fur.f3d_capacity), ('bin', 66))
        self.assertEqual((self.dock.f3d_loc_kind, self.dock.f3d_capacity), ('area', 0))  # через псевдонім
        self.assertEqual((res['kinds'], res['capacities']), (3, 2))

    def test_rerun(self):
        with self.with_data_file('scene_locations.csv', self.rows):
            first = codes.locations(self.env)
            second = codes.locations(self.env)
        self.assertEqual({k: first[k] for k in ('kinds', 'capacities')}, {k: second[k] for k in ('kinds', 'capacities')})
        self.assertEqual(second['locations'], 0)
        self.assertEqual(self.plt.f3d_capacity, 60)

    def test_capacity_nonneg(self):
        with self.assertRaises(IntegrityError), mute_logger('odoo.sql_db'), self.cr.savepoint():
            self.plt.f3d_capacity = -1
            self.plt.flush_recordset()

    def test_kind_selection(self):
        with self.assertRaises(ValueError):
            self.plt.f3d_loc_kind = 'rack'
