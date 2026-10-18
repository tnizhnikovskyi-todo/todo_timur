"""AC-63…AC-65: меню й дії (§3), матриця прав (§4.1), налаштування (§5.1)."""
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from .common import FireCase

U, M = 'factory3d_base.group_f3d_user', 'factory3d_base.group_f3d_manager'
ROOT = 'factory3d_fire_safety.menu_f3d_fire_root'
# (xml-id меню, батько, sequence, група, xml-id дії, модель)
MENUS = [
    ('menu_f3d_fire_overview', ROOT, 10, U, 'action_f3d_fire_overview', 'f3d.fire.panel'),
    ('menu_f3d_fire_zone', ROOT, 20, U, 'action_f3d_fire_zone', 'f3d.fire.zone'),
    ('menu_f3d_fire_device', ROOT, 30, U, 'action_f3d_fire_device', 'f3d.fire.device'),
    ('menu_f3d_fire_event', ROOT, 40, U, 'action_f3d_fire_event', 'f3d.fire.event'),
    ('menu_f3d_fire_system', ROOT, 50, U, 'action_f3d_fire_system', 'f3d.fire.system'),
    ('menu_f3d_fire_evac', ROOT, 60, U, None, None),
    ('menu_f3d_fire_exit', 'menu_f3d_fire_evac', 10, U, 'action_f3d_fire_exit', 'f3d.fire.exit'),
    ('menu_f3d_fire_route', 'menu_f3d_fire_evac', 20, U, 'action_f3d_fire_route', 'f3d.fire.route'),
    ('menu_f3d_fire_smoke_zone', 'menu_f3d_fire_evac', 30, U, 'action_f3d_fire_smoke_zone', 'f3d.fire.smoke.zone'),
    ('menu_f3d_fire_evac_report', 'menu_f3d_fire_evac', 40, U, 'action_f3d_fire_evac_report', None),
    ('menu_f3d_fire_drill', ROOT, 70, U, 'action_f3d_fire_drill', 'f3d.fire.drill'),
    ('menu_f3d_fire_norm', ROOT, 80, U, 'action_f3d_fire_norm', 'f3d.fire.norm'),
    ('menu_f3d_fire_config', ROOT, 90, M, None, None),
    ('menu_f3d_fire_template', 'menu_f3d_fire_config', 10, M, 'action_f3d_fire_drill_template',
     'f3d.fire.drill.template'),
    ('menu_f3d_fire_loop', 'menu_f3d_fire_config', 20, M, 'action_f3d_fire_loop', 'f3d.fire.loop'),
]
SETTINGS = {
    'f3d_fire_read_enabled': True, 'f3d_fire_comm_stale_after_s': 120, 'f3d_fire_comm_lost_after_s': 240,
    'f3d_fire_dust_warn_pct': 70.0, 'f3d_fire_dust_alarm_pct': 88.0, 'f3d_fire_polymer_panels': True,
    'f3d_fire_cover_tol_m': 0.4, 'f3d_fire_drill_time_limit_s': 280, 'f3d_fire_drill_auto_create': False,
    'f3d_fire_drill_match_window_min': 20, 'f3d_fire_drill_auto_stop_s': 100,
    'f3d_fire_drill_sim_duration_s': 200, 'f3d_fire_viewer_devices': True, 'f3d_fire_event_ack_required': False,
}


@tagged('post_install', '-at_install', 'f3d', 'f3d_fire')
class TestMenusRights(FireCase):

    def xid(self, name):
        return name if '.' in name else 'factory3d_fire_safety.' + name

    def test_menus(self):
        root = self.env.ref(ROOT)
        self.assertEqual((root.parent_id, root.sequence), (self.env.ref('factory3d_base.menu_f3d_root'), 85))
        self.assertEqual(root.group_ids, self.env.ref(U))
        for name, parent, seq, group, action, model in MENUS:
            menu = self.env.ref(self.xid(name))
            self.assertEqual(menu.parent_id, self.env.ref(self.xid(parent)), name)
            self.assertEqual(menu.sequence, seq, name)
            self.assertEqual(menu.group_ids, self.env.ref(group), name)
            if action:
                act = self.env.ref(self.xid(action))
                self.assertEqual(menu.action, act, name)
                if model:
                    self.assertEqual(act.res_model, model, name)
            else:
                self.assertFalse(menu.action, name)
        self.assertEqual(self.env.ref('factory3d_fire_safety.action_f3d_fire_evac_report')._name,
                         'ir.actions.server')
        settings = self.env.ref('factory3d_fire_safety.menu_f3d_fire_settings')
        self.assertEqual((settings.parent_id, settings.sequence, settings.group_ids),
                         (self.env.ref('factory3d_base.menu_f3d_config'), 85, self.env.ref(M)))
        action = self.env.ref('factory3d_fire_safety.action_f3d_fire_settings')
        self.assertEqual((settings.action, action.res_model, action.target), (action, 'res.config.settings', 'current'))  # 'inline' у Odoo 19 немає
        children = self.env['ir.ui.menu'].search([('parent_id', '=', root.id)]) | self.env['ir.ui.menu'].search(
            [('parent_id', 'in', (self.env.ref('factory3d_fire_safety.menu_f3d_fire_evac') |
                                  self.env.ref('factory3d_fire_safety.menu_f3d_fire_config')).ids)])
        self.assertEqual(len(children), 15)

    def test_acl_matrix(self):
        drill_group = 'factory3d_fire_safety.group_f3d_fire_drill'
        self.assertTrue(self.m.has_group(drill_group))
        # U: читає зони, не пише; не створює навчання
        self.assertTrue(self.z_cut.with_user(self.u).read(['name']))
        with self.assertRaises(AccessError):
            self.z_cut.with_user(self.u).write({'name': 'X'})
        with self.assertRaises(AccessError):
            self.env['f3d.fire.drill'].with_user(self.u).create(
                {'title': 'U', 'zone_id': self.z_cut.id, 'mode': 'tabletop'})
        # D: створює навчання й читає людей
        drill = self.new_drill(zone_id=self.z_cut.id, mode='tabletop')
        emp = self.make_employee('Тест Права', 'R-001')
        person = self.env['f3d.fire.drill.person'].sudo().create(
            {'drill_id': drill.id, 'employee_id': emp.id, 'seq': 1, 'source': 'manual'})
        self.assertEqual(person.with_user(self.d).seq, 1)
        self.assertEqual(len(drill.with_user(self.d).person_ids), 1)
        # H читає людей
        self.assertEqual(self.env['f3d.fire.drill.person'].with_user(self.hr).search_count([('id', '=', person.id)]), 1)
        # M пише норму, але не видаляє
        norm = self.env['f3d.fire.norm'].search([('key', '=', 'mcp_spacing')])
        norm.with_user(self.m).write({'note': 'M'})
        with self.assertRaises(AccessError):
            norm.with_user(self.m).unlink()
        # A — успіх
        spare = self.env['f3d.fire.norm'].with_user(self.a).create(
            {'key': 'tmp_norm', 'name': 'Тимчасова', 'ref': 'тест'})
        spare.unlink()
        # події не видаляються нікому
        event = self.env['f3d.fire.event']._log('info', 'FACP-1', self.T0, 'тест', source='manual')
        for user in (self.u, self.d, self.m, self.a):
            with self.assertRaises(UserError):  # AccessError ⊂ UserError
                event.with_user(user).unlink()

    def test_settings(self):
        Settings = self.env['res.config.settings']
        icp = self.env['ir.config_parameter'].sudo()
        self.assertFalse([n for n in Settings._fields if n.startswith('f3d_fire_') and 'write' in n])
        vals = dict(SETTINGS, f3d_fire_alert_group_id=self.g_alert.id, f3d_fire_team_id=self.team.id)
        Settings.create(vals).execute()
        P = 'factory3d.fire_safety.'
        self.assertEqual(icp.get_param(P + 'comm_stale_after_s'), '120')
        self.assertEqual(float(icp.get_param(P + 'dust_warn_pct')), 70.0)
        self.assertEqual(icp.get_param(P + 'event_ack_required'), 'False')
        self.assertEqual(icp.get_param(P + 'drill_auto_create'), 'False')
        self.assertEqual(icp.get_param(P + 'alert_group_xmlid'), 'test_fire.group_alert')
        self.assertEqual(icp.get_param(P + 'team_id'), str(self.team.id))
        values = Settings.default_get(list(vals))
        for name, value in vals.items():
            self.assertEqual(values[name], value, name)
        dust = self.env['f3d.signal'].search([('code', '=', 'fire/groups/FA-FAC/dust')])
        self.assertEqual((dust.warn_high, dust.alarm_high), (70.0, 88.0))
        with self.assertRaises(UserError):
            Settings.create(dict(vals, f3d_fire_dust_warn_pct=90.0, f3d_fire_dust_alarm_pct=80.0)).execute()
