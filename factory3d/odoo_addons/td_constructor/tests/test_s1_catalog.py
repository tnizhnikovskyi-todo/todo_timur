from psycopg2 import IntegrityError

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger

from ..services import cells
from .common import F3DConstructorCase

GROUPS = {'rack': 20, 'floor': 5, 'special': 8, 'zone': 12, 'mobile': 5}
TEMPLATES = {'pallet_rack': 8, 'shelf': 10, 'cantilever': 2, 'floor_stack': 4, 'floor_spot': 25, False: 1}


@tagged("post_install", "-at_install", "f3d", "f3d_constructor", "f3d_s1")
class TestCatalog(F3DConstructorCase):
    """F08: каталог із 50 типів на семи генераторах (Q9), floor_spot, нові параметри, права на типи."""

    def catalog(self):
        return self.env['td.slot.type'].search([('is_custom', '=', False)])

    def test_fifty_types_seeded(self):
        types = self.catalog()
        self.assertEqual(len(types), 50)
        self.assertFalse(types.mapped('company_id'))  # каталог спільний для всіх компаній
        groups = {}
        for t in types:
            groups[t.group] = groups.get(t.group, 0) + 1
        self.assertEqual(groups, GROUPS)
        by_template = {}
        for t in types:
            by_template[t.template] = by_template.get(t.template, 0) + 1
        self.assertEqual(by_template, TEMPLATES)
        self.assertEqual(len(set(types.mapped('ref'))), 50)
        self.assertEqual(types.filtered(lambda t: not t.template).mapped('ref'), ['BF03'])
        self.assertEqual({t.relevance for t in types}, {0, 1, 2})
        self.assertEqual(self.env['td.slot.type'].search([('code', '=', 'r02')]).params['deep'], 2)
        self.assertEqual(self.env['td.term'].search_count([('term_type', '=', 'slot_type')]), 7)  # + floor_spot

    def test_seven_generators_build_geometry(self):
        self.assertEqual(
            list(cells.SLOT_TEMPLATES),
            ['pallet_rack', 'cantilever', 'shelf', 'floor_stack', 'floor_spot', 'machine_spot', 'zone'],
        )
        self.assertEqual(
            set(self.env['td.term'].search([('term_type', '=', 'slot_type')]).mapped('key')), set(cells.SLOT_TEMPLATES)
        )
        self.assertEqual(set(dict(self.env['td.slot']._fields['template'].selection)), set(cells.SLOT_TEMPLATES))
        for t in self.catalog().filtered('template'):
            params = cells.normalize_params(t.template, t.params)
            length, width = cells.footprint(t.template, params)
            self.assertGreater(length * width, 0, t.ref)
            out = cells.generate_cells(t.template, t.ref, 0, 0, 0, params)
            self.assertTrue(out, "%s: комірок немає" % t.ref)
            self.assertEqual(len({c['code'] for c in out}), len(out), "%s: коди повторюються" % t.ref)
            self.assertTrue(all(len(c['code']) <= cells.CODE_MAX_LEN for c in out), t.ref)
            self.assertTrue(cells.slot_obb(t.template, params, 0, 0, 0))
        # генератори без комірок (верстат, зона) теж мають габарит
        self.assertEqual(cells.footprint('machine_spot', {'length': 3.0, 'width': 1.5}), (3.0, 1.5))
        self.assertEqual(cells.footprint('zone', {'polygon': [[0, 0], [4, 0], [4, 3], [0, 3]]}), (4.0, 3.0))

    def test_slot_from_type_and_consistency(self):
        r02 = self.env['td.slot.type'].search([('code', '=', 'r02')])
        slot = self.make_slot(prefix='CT-1', template='pallet_rack', **dict(r02.params, bays=2, levels=1))
        slot.type_id = r02
        self.assertEqual(slot.type_id.ref, 'R02')
        self.assertEqual(slot.footprint_w_m, 2.2)  # deep=2: глибина секції — дві палети
        self.assertEqual(slot._f3d_cells()[0]['capacity'], 6.0)
        with self.assertRaises(ValidationError):
            slot.type_id = self.env['td.slot.type'].search([('code', '=', 'r11')])  # інший генератор
        with self.assertRaises(ValidationError):
            slot.type_id = self.env['td.slot.type'].search([('code', '=', 'bf03')])  # об'єкт будівлі, не місце
        with self.assertRaises(IntegrityError), mute_logger('odoo.sql_db'):
            r02.unlink()  # тип, що використовується, видалити не можна (ondelete restrict)

    def test_floor_spot_generator(self):
        spot = self.make_slot(prefix='BF-IN', template='floor_spot', length=6.0, width=4.0, height=0.1, loc_kind='area')
        self.assertEqual((spot.cell_count, spot.footprint_l_m, spot.footprint_w_m), (1, 6.0, 4.0))
        cell = spot._f3d_cells()[0]
        self.assertEqual((cell['code'], cell['kind'], cell['l'], cell['w']), ('BF-IN', 'area', 6.0, 4.0))
        with self.assertRaises(ValidationError):
            self.make_slot(prefix='BF-X', template='floor_spot', length=0.0)
        with self.assertRaises(ValidationError):
            self.make_slot(prefix='BF-Y', template='floor_spot', loc_kind='nope')

    def test_new_params_validation_and_geometry(self):
        base = {'bays': 2, 'levels': 3}
        p = cells.normalize_params(
            'pallet_rack', dict(base, level_heights=[1.2], double_sided=1, beam_th=0.1, bottom_on_floor=False)
        )
        self.assertEqual(p['level_heights'], [1.2, 1.5, 1.5])  # бракуючі — базова висота
        self.assertIs(p['double_sided'], True)
        self.assertNotIn('deep', p)  # необов'язкові параметри з'являються лише коли задані
        out = cells.generate_cells(
            'pallet_rack', 'P', 0, 0, 0, dict(base, bottom_on_floor=False, level_heights=[1.0, 2.0, 1.0], beam_th=0.1)
        )
        self.assertEqual([round(c['z0'], 3) for c in out[:3]], [0.15, 1.15, 3.15])
        self.assertEqual([round(c['h'], 3) for c in out[:3]], [0.9, 1.9, 0.9])
        for bad in (
            {'deep': 7},
            {'gap_x': -1},
            {'cells_per_level': 13},
            {'shape': 'nope'},
            {'level_heights': 'x'},
            {'level_heights': [9]},
            {'double_sided': 5},
        ):
            with self.assertRaises(cells.CellsError, msg=str(bad)):
                cells.normalize_params('pallet_rack', dict(base, **bad))
        with self.assertRaises(cells.CellsError):
            cells.normalize_params('floor_stack', {'deep': 2, 'shape': 'zone', 'gap_x': 3})
        self.assertEqual(cells.normalize_params('floor_stack', {'gap_x': 0.5, 'shape': 'zone'})['shape'], 'zone')
        # зазори й двосторонній ряд збільшують габарит
        self.assertAlmostEqual(cells.footprint('pallet_rack', dict(base, gap_x=0.5))[0], 2 * 2.7 + 0.5)
        self.assertAlmostEqual(
            cells.footprint('shelf', {'sections': 2, 'double_sided': True, 'gap_y': 0.2})[1], 2 * 0.4 + 0.2
        )

    def test_type_validation(self):
        Type = self.env['td.slot.type']
        good = {'code': 'my_type', 'name': "Мій", 'group': 'rack', 'template': 'pallet_rack', 'params': {'bays': 3}}
        Type.create(good)
        with self.assertRaises(ValidationError):
            Type.create(dict(good, code='Bad Code'))
        with self.assertRaises(ValidationError):
            Type.create(dict(good, code='t2', params={'bays': 0}))
        with self.assertRaises(ValidationError):
            Type.create(dict(good, code='t3', shape='nope'))
        with self.assertRaises(ValidationError):
            Type.create(dict(good, code='t4', template='zone'))
        with self.assertRaises(IntegrityError), mute_logger('odoo.sql_db'):
            Type.create(dict(good, code='t5', relevance=3))
        Type.create(dict(good, code='t6', template=False, params={'width': 3.5}))  # об'єкт будівлі: параметри довільні

    def test_rights_catalog_and_custom(self):
        Type = self.env['td.slot.type']
        r01 = Type.search([('code', '=', 'r01')])
        tech = Type.with_user(self.u_tech)
        with self.assertRaises(AccessError):
            tech.browse(r01.id).write({'name': "Зламаний"})
        with self.assertRaises(AccessError):
            tech.create({'code': 'cat_x', 'name': "X", 'group': 'rack', 'template': 'shelf', 'is_custom': False})
        own = tech.create(
            {'code': 'tech_own', 'name': "Свій", 'group': 'rack', 'template': 'shelf', 'params': {'sections': 2}}
        )
        self.assertTrue(own.is_custom)
        self.assertEqual(own.company_id, self.company)  # власний тип — на компанію
        own.write({'name': "Свій 2"})
        with self.assertRaises(AccessError):
            own.write({'is_custom': False})
        with self.assertRaises(AccessError):
            own.unlink()  # видаляє менеджер
        view = Type.with_user(self.u_plain)
        self.assertTrue(view.search_count([]) >= 51)
        with self.assertRaises(AccessError):
            view.create({'code': 'v_x', 'name': "V", 'group': 'rack', 'template': 'shelf'})
        Type.with_user(self.u_manager).browse(own.id).unlink()
        self.assertFalse(own.exists())
