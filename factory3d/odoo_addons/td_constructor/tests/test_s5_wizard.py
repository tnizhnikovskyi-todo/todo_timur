from odoo import Command
from odoo.tests import tagged

from .common import PASSWORD, F3DConstructorHttpCase

STATE = {
    'v': 1,
    'step': 2,
    'reached': 3,
    'form': {
        'building': {'length': 60, 'width': 30, 'height': 8},
        'zones': [{'id': 'wz1', 'name': "Зона 1", 'x0': 1, 'x1': 29}],
    },
    'created': {'items': ['bi_1'], 'zones': ['s_1'], 'rows': []},
}


@tagged("post_install", "-at_install", "f3d", "f3d_constructor", "f3d_s5")
class TestS5Wizard(F3DConstructorHttpCase):
    """S5, F16-04: маршрут `/site/wizard` — стан майстра «З нуля» за правилами API-01…10."""

    def call(self, user, **kw):
        self.authenticate(user.login, PASSWORD)
        return self.rpc('/f3d/constructor/site/wizard', **kw)

    def test_manager_writes_and_reads_state(self):
        draft = (self.site.draft_rev, self.site.draft_changes)
        res = self.call(self.u_manager, site_id=self.site.id, state=STATE)
        self.assertTrue(res['ok'], res)
        self.site.invalidate_recordset()
        self.assertEqual(self.site.wizard_state, STATE)
        self.assertEqual(
            (self.site.draft_rev, self.site.draft_changes), draft, "стан майстра не лічиться змінами чернетки"
        )
        res = self.call(self.u_manager, site_id=self.site.id)
        self.assertEqual(res['wizard_state'], STATE)
        load = self.rpc('/f3d/constructor/load', site_id=self.site.id)
        self.assertEqual(load['site']['wizard_state'], STATE, "load віддає стан майстра")

    def test_designer_with_layer_rights(self):
        self.assertTrue(
            self.call(self.u_store, site_id=self.site.id, state=STATE)['ok'], "комірник редагує шар «Склади»"
        )
        self.assertTrue(self.call(self.u_tech, site_id=self.site.id, state=STATE)['ok'], "технолог — шар «Виробництво»")
        res = self.call(self.u_plain, site_id=self.site.id, state=STATE)
        self.assertEqual((res['ok'], res['code']), (False, 'rights'), "без ролі й прав на шар майстер не пише")
        for layer in self.layers.values():
            layer.edit_group_ids = [Command.clear()]
        res = self.call(self.u_store, site_id=self.site.id, state=STATE)
        self.assertEqual((res['ok'], res['code']), (False, 'rights'), "права йдуть за групами шарів")

    def test_validation(self):
        for state in ([1, 2], "x", 5):
            res = self.call(self.u_manager, site_id=self.site.id, state=state)
            self.assertEqual((res['ok'], res['code']), (False, 'validation'), repr(state))
        deep = cur = {}
        for _ in range(12):
            cur['x'] = {}
            cur = cur['x']
        self.assertEqual(self.call(self.u_manager, site_id=self.site.id, state=deep)['code'], 'validation')
        big = {'blob': 'я' * 200000}
        self.assertEqual(self.call(self.u_manager, site_id=self.site.id, state=big)['code'], 'validation')
        self.assertEqual(self.call(self.u_manager, site_id=0, state=STATE)['code'], 'not_found')
        self.assertEqual(self.site.wizard_state or {}, {}, "хибні значення не записано")
