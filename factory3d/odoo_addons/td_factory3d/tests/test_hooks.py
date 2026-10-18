import json

from odoo.tests import tagged
from odoo.tools import file_open

from odoo.addons.td_factory3d import hooks

from .common import F3DCase

DEFAULTS = {
    'td.base.plant_length_m': '150',
    'td.base.plant_width_m': '72',
    'td.base.plant_height_m': '9',
    'td.base.site_x0_m': '-32',
    'td.base.site_y0_m': '-30',
    'td.base.site_x1_m': '182',
    'td.base.site_y1_m': '100',
    'td.base.keep_x_fields': 'False',
    'td.base.uninstall_restore_x_fields': 'True',
}


@tagged('post_install', '-at_install', 'f3d', 'f3d_base')
class TestParams(F3DCase):

    def _param(self, key):
        return self.env['ir.config_parameter'].sudo().get_param(key)

    def test_params_defaults(self):  # AC-46
        for key, value in DEFAULTS.items():
            self.assertEqual(self._param(key), value, key)
        self.assertTrue(self._param('td.base.environment'))
        self.assertNotEqual(self._param('td.base.migration_state'), 'pending')
        self.assertTrue(self._param('td.base.migration_report'))

    def test_clean_db_skipped(self):  # AC-47
        report = hooks.run_all(self.env)
        self.assertTrue(report['batches.migrate'].get('skipped'))
        self.assertEqual(self._param('td.base.migration_state'), 'skipped')
        self.assertEqual(report['x_fields.drop_demo'], {'views_dropped': 0, 'fields_dropped': 0})

    def test_report_json(self):
        hooks.run_all(self.env)
        report = json.loads(self._param('td.base.migration_report'))
        self.assertIn('ts', report)
        for step in ('docks.register', 'codes.locations', 'codes.workcenters', 'codes.employees',
                     'codes.equipment', 'passports.link', 'zones.bind', 'batches.migrate'):
            self.assertIn(step, report)

    def test_state_partial_done(self):  # крок 11
        migrated = {'batches.migrate': {'batches_created': 1}}
        done = hooks.write_report(self.env, dict(migrated, **{'batches.verify': {'mismatches': []},
                                                              'x_fields.drop_demo': {'fields_dropped': 3}}))
        self.assertEqual(done, 'done')
        for extra in ({'batches.verify': {'mismatches': ['x']}},
                      {'x_fields.drop_demo': {'blocked_views': ['v']}}):
            self.assertEqual(hooks.write_report(self.env, dict(migrated, **extra)), 'partial')
        self.env['ir.config_parameter'].sudo().set_param('td.base.keep_x_fields', 'True')
        self.assertEqual(hooks.write_report(self.env, dict(migrated)), 'partial')

    def test_rerun_keeps_done_state(self):  # AC-30
        params = self.env['ir.config_parameter'].sudo()
        params.set_param('td.base.migration_state', 'done')
        params.set_param('td.base.migration_report', '{"orig": 1}')
        report = hooks.run_all(self.env)
        self.assertTrue(report['batches.migrate'].get('skipped'))
        self.assertEqual(self._param('td.base.migration_state'), 'done')
        self.assertEqual(self._param('td.base.migration_report'), '{"orig": 1}')
        rerun = json.loads(self._param('td.base.migration_rerun_report'))
        self.assertEqual((rerun['migration_state'], rerun['batches_created']), ('done', 0))

    def test_neutralize_sql(self):  # AC-49
        with file_open('td_factory3d/data/neutralize.sql') as f:
            sql = f.read()
        self.env['ir.config_parameter'].sudo().set_param('td.base.environment', 'prod')
        self.env.cr.execute(sql)
        self.env.cr.execute("SELECT value FROM ir_config_parameter WHERE key = 'td.base.environment'")
        self.assertEqual(self.env.cr.fetchone()[0], 'test')

    def test_uninstall_hook_clean(self):  # AC-48
        self.make_zone('UNI-1')
        hooks.uninstall_hook(self.env)
        keys = self.env['ir.config_parameter'].sudo().search([('key', '=like', 'td.base.%')])
        self.assertFalse(keys)
        self.assertTrue(self.loc_in.exists())
        self.env.cr.execute("SELECT count(*) FROM ir_model_fields WHERE model='stock.picking' "
                            "AND name IN ('x_dock','x_truck','x_vehicle')")
        self.assertEqual(self.env.cr.fetchone()[0], 3)
