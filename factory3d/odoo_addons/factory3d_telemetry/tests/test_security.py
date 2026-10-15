import logging

from odoo.addons.factory3d_telemetry import hooks
from odoo.exceptions import AccessError
from odoo.tests import tagged
from odoo.tools import file_open

from .common import F3DTelemetryCase

TAGS = ('post_install', '-at_install', 'f3d', 'f3d_telemetry')
MODELS = ['f3d.collector', 'f3d.source', 'f3d.signal', 'f3d.reading', 'f3d.reading.hour', 'f3d.command',
          'f3d.push.event']
# §13.3 ТБ-03: модель -> {користувач: дозволені операції (R, W, C, D)}
MATRIX = {
    'f3d.collector': {'user_reader': 'R', 'user_manager': 'R', 'user_admin': 'RWCD'},
    'f3d.source': {'user_reader': 'R', 'user_manager': 'RWCD', 'user_admin': 'RWCD'},
    'f3d.signal': {'user_reader': 'R', 'user_manager': 'RWCD', 'user_admin': 'RWCD'},
    'f3d.reading': {'user_reader': 'R', 'user_manager': 'RC', 'user_admin': 'RWCD'},
    'f3d.reading.hour': {'user_reader': 'R', 'user_manager': 'R', 'user_admin': 'RWCD'},
    'f3d.command': {'user_reader': 'R', 'user_manager': 'RWC', 'user_admin': 'RWCD'},
    'f3d.push.event': {'user_reader': 'R', 'user_manager': 'R', 'user_admin': 'RWCD'},
}
OPS = {'R': 'read', 'W': 'write', 'C': 'create', 'D': 'unlink'}


@tagged(*TAGS)
class TestAcl(F3DTelemetryCase):
    def test_matrix(self):
        """AC-59: права за §13.3 ТБ-03 (за ACL моделі, підтест на клітинку)."""
        for model, users in MATRIX.items():
            for user_attr, allowed in users.items():
                for letter, op in OPS.items():
                    with self.subTest(model=model, user=user_attr, op=op):
                        env_model = self.env[model].with_user(getattr(self, user_attr))
                        if letter in allowed:
                            env_model.check_access(op)
                        else:
                            with self.assertRaises(AccessError):
                                env_model.check_access(op)
        wizard = self.env['f3d.collector.token.wizard']
        wizard.with_user(self.user_admin).check_access('create')
        for user in (self.user_reader, self.user_manager):
            with self.subTest(wizard=user.login), self.assertRaises(AccessError):
                wizard.with_user(user).check_access('read')

    def test_plain_user_denied(self):
        for model in MODELS:
            with self.subTest(model=model), self.assertRaises(AccessError):
                self.env[model].with_user(self.user_plain).search([])

    def test_mech_meter_fields(self):
        self.eq_comp.with_user(self.user_mech).write({'f3d_meter_interval': 500.0})
        self.assertEqual(self.eq_comp.f3d_meter_interval, 500.0)


@tagged(*TAGS)
class TestSecrets(F3DTelemetryCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_telemetry_fixtures()

    def test_token_fields_hidden(self):
        col = self.col.with_user(self.user_manager)
        for field in ('token_hash', 'token_hint'):
            with self.subTest(field=field):
                with self.assertRaises(AccessError):
                    col.read([field])
                with self.assertRaises(AccessError):
                    col.search_read([('id', '=', col.id)], [field])
                self.assertNotIn(field, col.fields_get())

    def test_token_not_logged(self):
        col = self.env['f3d.collector'].create({'code': 'COL-T3', 'name': 'Колектор 3'})
        with self.assertLogs('odoo', 'DEBUG') as logs:
            logging.getLogger('odoo.addons.factory3d_telemetry').debug('probe')
            token = self._gen_token(col)
            self.push([self.rd(self.sig_press, 7.0)], collector=col)
        self.assertTrue(token)
        for record in logs.records:
            self.assertNotIn(token, record.getMessage())

    def test_token_not_in_messages(self):
        col = self.env['f3d.collector'].create({'code': 'COL-T4', 'name': 'Колектор 4'})
        token = self._gen_token(col)
        self.assertTrue(col.message_ids)
        for message in col.message_ids:
            self.assertNotIn(token, message.body or '')
            self.assertNotIn(token, message.preview or '')


@tagged(*TAGS)
class TestStopCranes(F3DTelemetryCase):
    def _params(self, environment):
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param('factory3d.base.environment', environment)
        hooks.params(self.env)
        return icp.get_param('factory3d.telemetry.read_enabled'), icp.get_param('factory3d.telemetry.write_enabled')

    def test_test_env_defaults(self):
        self.assertEqual(self._params('test'), ('True', 'False'))

    def test_prod_env_defaults(self):
        self.assertEqual(self._params('prod'), ('False', 'False'))

    def test_settings_fields(self):
        self._params('test')
        settings = self.env['res.config.settings'].create({})
        self.assertTrue(settings.f3d_telemetry_read_enabled)
        self.assertFalse(settings.f3d_telemetry_write_enabled)
        self._params('prod')
        settings = self.env['res.config.settings'].create({})
        self.assertFalse(settings.f3d_telemetry_read_enabled)


@tagged(*TAGS)
class TestNeutralize(F3DTelemetryCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_telemetry_fixtures()

    def test_neutralize_sql(self):
        """AC-62."""
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param('factory3d.telemetry.read_enabled', 'True')
        icp.set_param('factory3d.telemetry.write_enabled', 'True')
        self.src_mb.write_enabled = True
        self.set_sql(self.src_mb, state='online')
        self.set_sql(self.src_bac, state='online', write_enabled=True)
        self.sig_valve.write_enabled = True
        first = self.env['f3d.command'].sudo().create({'signal_id': self.sig_valve.id, 'value': 1})
        second = self.env['f3d.command'].sudo().create({'signal_id': self.sig_valve.id, 'value': 2})
        self.set_sql(second, state='sent')
        done = self.env['f3d.command'].sudo().create({'signal_id': self.sig_valve.id, 'value': 3})
        self.set_sql(done, state='done')
        self.env.ref('factory3d_telemetry.cron_f3d_telemetry_stale').active = True
        self.assertTrue(self.col.token_hash)
        self.env.flush_all()
        self.cr.execute(file_open('factory3d_telemetry/data/neutralize.sql').read())
        self.env.invalidate_all()
        self.env.registry.clear_cache('stable')
        self.assertEqual(icp.get_param('factory3d.telemetry.read_enabled'), 'False')
        self.assertEqual(icp.get_param('factory3d.telemetry.write_enabled'), 'False')
        self.cr.execute("SELECT count(*) FROM ir_cron c JOIN ir_model_data d ON d.model = 'ir.cron' "
                        "AND d.res_id = c.id AND d.module = 'factory3d_telemetry' WHERE c.active")
        self.assertEqual(self.cr.fetchone()[0], 0)
        for source in self.env['f3d.source'].with_context(active_test=False).search([]):
            self.assertEqual((source.read_enabled, source.write_enabled, source.state), (False, False, 'disabled'))
        for collector in self.env['f3d.collector'].with_context(active_test=False).search([]):
            self.assertFalse(collector.token_hash)
            self.assertEqual(collector.state, 'never')
        self.assertEqual((first.state, second.state, done.state), ('expired', 'expired', 'done'))
        self.assertFalse(self.env['f3d.signal'].with_context(active_test=False).search([('write_enabled', '=', True)]))
