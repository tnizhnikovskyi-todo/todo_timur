import json

from odoo.tests import tagged

from ..services import publish
from .common import F3DConstructorCase


@tagged("post_install", "-at_install", "f3d", "f3d_constructor")
class TestVersions(F3DConstructorCase):
    """AC-58, AC-59, AC-60: R-14, §10."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['ir.config_parameter'].sudo().set_param('factory3d.constructor.publish_enabled', 'True')

    def publish(self, note=''):
        action = self.site.with_user(self.u_manager).action_publish_wizard()
        wizard = self.env['f3d.publish.wizard'].with_user(self.u_manager).browse(action['res_id'])
        wizard.note = note
        wizard.action_confirm()
        return wizard.version_id

    def test_ac58_snapshot_and_chain(self):
        self.make_slot(prefix='V-R1', bays=3, levels=2)
        self.make_placement(code='V-M1')
        v1 = self.publish("перша")
        self.assertEqual((v1.n, v1.state, v1.note), (1, 'active', "перша"))
        snap = json.loads(v1.snapshot_id.raw.decode())
        self.assertEqual(len(snap['slots']), 1)
        self.assertEqual(snap['counts']['cells'], 6)
        self.assertNotIn('cells', snap)
        self.assertEqual(len(snap['layers']), 5)
        self.assertEqual(snap['placements'][0]['variant_ref'], {'passport_role': 'test_machine', 'name': "Стандарт"})
        import hashlib
        self.assertEqual(v1.snapshot_sha1, hashlib.sha1(v1.snapshot_id.raw).hexdigest())
        self.assertEqual(v1.snapshot_id.mimetype, 'application/json')
        self.assertEqual(self.site.active_version_id, v1)
        self.assertFalse(self.site.has_changes)
        self.make_slot(kind='yard', prefix='V-Z1', template='zone', polygon=[[0, 0], [5, 0], [5, 5]])
        self.assertTrue(self.site.has_changes)
        v2 = self.publish()
        self.assertEqual((v2.n, v2.state, v1.state), (2, 'active', 'superseded'))
        self.assertEqual(self.site.active_version_id, v2)
        self.assertEqual(self.site.version_ids.filtered(lambda v: v.state == 'active'), v2)
        self.assertEqual(json.loads(v2.snapshot_id.raw.decode())['counts']['slots'], 2)

    def test_ac59_restore_draft(self):
        slot = self.make_slot(prefix='V-R1', bays=3, levels=2)
        v1 = self.publish()
        n_locations = self.env['stock.location'].search_count([])
        extra = self.make_slot(kind='yard', prefix='V-Z1', template='zone', polygon=[[0, 0], [5, 0], [5, 5]])
        slot.write({'x_m': 40.0})
        v2 = self.publish()
        slot_uid, extra_uid = slot.uid, extra.uid
        slot.unlink()  # у чернетці немає V-R1, у v1 вона є
        v1.with_user(self.u_manager).action_restore_draft()
        slots = self.env['f3d.slot'].search([('site_id', '=', self.site.id)])
        self.assertEqual(slots.mapped('code_prefix'), ['V-R1'])  # зайвий видалено, відсутній створено
        self.assertEqual(slots.x_m, 30.0)
        self.assertNotEqual(slots.uid, extra_uid)
        self.assertEqual(slots.uid, slot_uid)  # той самий uid, що й у знімку
        self.assertEqual(self.env['stock.location'].search_count([]), n_locations)  # Odoo не чіпали
        self.assertEqual(self.site.draft_base_version_id, v1)
        self.assertTrue(self.site.has_changes)
        self.assertGreater(self.site.draft_changes, 0)
        v2.with_user(self.u_manager).action_restore_draft()  # діюча версія → чистий стан
        self.assertFalse(self.site.has_changes)
        self.assertEqual(self.site.draft_changes, 0)
        self.assertEqual(self.site.draft_base_version_id, v2)
        self.assertEqual(len(self.env['f3d.slot'].search([('site_id', '=', self.site.id)])), 2)

    def test_ac60_no_changes(self):
        self.make_slot(prefix='V-R1', bays=2, levels=1)
        self.publish()
        count = self.env['f3d.layout.version'].search_count([])
        plan = publish.build_plan(self.site)
        with self.assertRaises(publish.PublishError) as ctx:
            publish.apply_plan(self.site.with_user(self.u_manager), plan, (), '')
        self.assertEqual(ctx.exception.code, 'no_changes')
        self.assertIn("Немає змін для публікації", str(ctx.exception))
        self.assertEqual(self.env['f3d.layout.version'].search_count([]), count)
        wizard = self.env['f3d.publish.wizard'].with_user(self.u_manager).browse(
            self.site.with_user(self.u_manager).action_publish_wizard()['res_id'])
        self.assertFalse(wizard.can_publish)

    def test_version_write_restrictions(self):
        from odoo.exceptions import AccessError
        self.make_slot(prefix='V-R1', bays=2, levels=1)
        version = self.publish()
        version.with_user(self.u_manager).write({'note': "оновлена нотатка"})
        with self.assertRaises(AccessError):
            version.with_user(self.u_manager).write({'n': 99})
        with self.assertRaises(AccessError):
            version.with_user(self.u_manager).unlink()
