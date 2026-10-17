import json
import os
import re

from odoo.tests import tagged

from .. import hooks
from ..hooks import seed
from .common import F3DConstructorCase


@tagged("post_install", "-at_install", "f3d", "f3d_constructor")
class TestSeedHook(F3DConstructorCase):
    """AC-02, AC-03, AC-05 (AC-06 — в test_publish): R-24, §5.2."""

    def _drop_seed_site(self):
        site = self.env['f3d.site'].with_context(active_test=False).search([('seed_key', '=', 'main_demo')])
        site.sudo().unlink()

    def _models_count(self):
        return {
            m: self.env[m].with_context(active_test=False).search_count([])
            for m in (
                'f3d.site',
                'f3d.layer',
                'f3d.slot',
                'f3d.placement',
                'f3d.equipment.variant',
                'f3d.layout.version',
                'f3d.check.config',
                'stock.location',
                'maintenance.equipment',
                'mrp.workcenter',
            )
        }

    def test_ac02_seed_created_and_idempotent(self):
        self._drop_seed_site()
        data = seed.normalize_seed(seed.read_seed())
        report1 = hooks.run_seed_hook(self.env)
        site = self.env['f3d.site'].search([('seed_key', '=', 'main_demo')])
        self.assertEqual(len(site), 1)
        self.assertEqual(
            (site.name, site.building_length_m, site.building_width_m, site.building_height_m),
            ("Меблеве підприємство", 150, 72, 9),
        )
        counts = data['meta']['counts']
        slots = self.env['f3d.slot'].search([('site_id', '=', site.id)])
        self.assertEqual(len(site.layer_ids), counts['layers'])
        self.assertEqual(len(slots), counts['slots'])
        self.assertEqual(sum(slots.mapped('cell_count')), counts['cells'])
        self.assertEqual(self.env['f3d.placement'].search_count([('site_id', '=', site.id)]), counts['placements'])
        self.assertEqual(report1['created'], counts)
        self.assertEqual(report1['skipped_variants'], [])
        self.assertEqual(len(site.version_ids), 1)
        self.assertTrue(site.version_ids.is_seed)
        self.assertFalse(site.has_changes)
        self.assertEqual(site.active_version_id, site.version_ids)
        self.assertEqual(len(site.check_config_ids), 7)
        before = self._models_count()
        report2 = hooks.run_seed_hook(self.env)
        self.assertEqual(before, self._models_count())
        self.assertEqual(report1, report2)
        self.assertEqual(
            self.env['ir.config_parameter'].sudo().get_param('factory3d.constructor.seed_report'),
            json.dumps(report2, ensure_ascii=False, sort_keys=True),
        )

    def test_ac19_categories_after_hook(self):
        hooks.step_categories(self.env)
        Passport = self.env['f3d.equipment.passport']
        for role, category in (('beam_saw', 'machine'), ('board_rack', 'rack'), ('forklift', 'forklift')):
            passport = Passport.search([('role', '=', role)])
            if passport:
                self.assertEqual(passport.f3d_category, category, role)

    def test_ac03_link_existing_records(self):
        """Наявні запис (barcode/f3d_code) зв'язуються, а не дублюються; незнайдені коди — у seed_report.unlinked."""
        self._drop_seed_site()
        Loc, Equipment = self.env['stock.location'], self.env['maintenance.equipment']
        loc = Loc.search([('f3d_code', '=', 'FG-R1-B01-L4')]) or Loc.create(
            {'name': 'FG-R1-B01-L4', 'barcode': 'FG-R1-B01-L4', 'usage': 'internal', 'location_id': self.wh_stock.id}
        )
        eq = Equipment.search([('f3d_code', '=', 'SAW-1')]) or Equipment.create(
            {'name': "Розкрій 1", 'f3d_code': 'SAW-1'}
        )
        demo = bool(Loc.search_count([('f3d_code', '=', 'FG-R1-B01-L1')]))  # копія демо-бази: усі коди макета вже є
        name, parent = loc.name, loc.location_id
        locations, equipment = Loc.search_count([]), Equipment.search_count([])
        workcenters = self.env['mrp.workcenter'].search_count([])
        report = hooks.run_seed_hook(self.env)
        site = self.env['f3d.site'].search([('seed_key', '=', 'main_demo')])
        self.assertEqual((loc.f3d_site_id, eq.f3d_site_id), (site, site))
        placement = self.env['f3d.placement'].search([('site_id', '=', site.id), ('code', '=', 'SAW-1')])
        self.assertEqual(placement.equipment_id, eq)
        self.assertEqual(eq.f3d_placement_uid, placement.uid)
        self.assertEqual(
            (Loc.search_count([]), Equipment.search_count([]), self.env['mrp.workcenter'].search_count([])),
            (locations, equipment, workcenters),
        )  # нічого не створено
        self.assertNotIn('FG-R1-B01-L4', report['unlinked']['locations'])
        self.assertNotIn('SAW-1', report['unlinked']['equipment'])
        self.assertGreaterEqual(report['linked']['locations'], 1)
        if demo:
            # демо-база має локації всіх комірок макета (майданчик відходів WASTE — контейнери, не склад: комірку
            # вимкнено) і обладнання верстатів; об'єкти сцени (будівлі, планшети, люди) окремого обладнання не мають
            scene = set(
                self.env['f3d.placement']
                .search([('site_id', '=', site.id), ('variant_id.passport_id.role', '=like', 'scene_%')])
                .mapped('code')
            )
            self.assertEqual(report['unlinked']['locations'], [])
            self.assertLessEqual(set(report['unlinked']['equipment']), scene)
            self.assertEqual(report['linked']['locations'], report['created']['cells'])
        else:
            self.assertIn('FG-R1-B01-L1', report['unlinked']['locations'])
            self.assertIn('SAW-2', report['unlinked']['equipment'])
        # зв'язок не змінює ім'я й батьківську локацію запису
        self.assertEqual((loc.name, loc.location_id), (name, parent))

    def test_ac05_no_hardcoded_codes_or_urls(self):
        """AC-05: у вихідниках модуля (крім seed, тестів і dev-скриптів tools/) немає меблевих кодів і зовнішніх URL."""
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        bad_codes = re.compile(r'\b(FG-R|SAW-|RCK-|CNC-)')
        bad_urls = re.compile(r'https?://(?!(www\.)?(todo\.ltd|odoo\.com))')
        found = []
        for base, dirs, files in os.walk(root):
            rel = os.path.relpath(base, root)
            if rel.split(os.sep)[0] in ('tests', 'tools', 'data', 'node_modules', '.git') and rel != '.':
                if rel.split(os.sep)[0] != 'data':
                    dirs[:] = []
                    continue
            for name in files:
                if not name.endswith(('.py', '.js', '.xml')) or name == 'seed_site.json':
                    continue
                path = os.path.join(base, name)
                text = open(path, encoding='utf-8', errors='ignore').read()
                if bad_codes.search(text):
                    found.append((path, 'код'))
                if bad_urls.search(text) and 'static/lib' not in path and '/lib/' not in path:
                    found.append((path, 'url'))
        self.assertEqual(found, [])
