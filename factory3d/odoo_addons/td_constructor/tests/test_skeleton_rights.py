from odoo.exceptions import AccessError
from odoo.tests import tagged

from .common import F3DConstructorCase

R = (1, 0, 0, 0)  # лише читання
OPS = ('read', 'write', 'create', 'unlink')
# MERGE.md §3.5: права за ролями; ключі — u_plain (лише group_td_user), u_tech/u_store/u_eng, u_manager
LIBRARY = {'plain': R, 'tech': (1, 1, 1, 0), 'store': (1, 1, 1, 0), 'eng': (1, 1, 1, 0), 'manager': (1, 1, 1, 1)}
DRAFT = {'plain': R, 'tech': (1, 1, 1, 1), 'store': (1, 1, 1, 1), 'eng': (1, 1, 1, 1), 'manager': (1, 1, 1, 1)}
MATRIX = {
    'td.slot.type': LIBRARY,
    'td.slot.preset': LIBRARY,
    'td.putaway.rule': DRAFT,
    'td.replenish.rule': DRAFT,
    'td.comment': DRAFT,
    'td.zone.lock': DRAFT,
    'td.publish.op': {'plain': R, 'tech': R, 'store': R, 'eng': R, 'manager': R},  # пише лише публікація (sudo)
    'td.layout.variant': {'plain': R, 'tech': R, 'store': R, 'eng': R, 'manager': (1, 1, 1, 1)},  # варіанти — менеджер
}


@tagged("post_install", "-at_install", "f3d", "f3d_constructor")
class TestSkeletonRights(F3DConstructorCase):
    """W0-B: ACL нових моделей за §3.5 MERGE.md і правила мультикомпанії.

    Читання — group_td_user; правка — проєктувальники; варіанти й видалення з бібліотеки — менеджер."""

    def users(self):
        return {
            'plain': self.u_plain,
            'tech': self.u_tech,
            'store': self.u_store,
            'eng': self.u_eng,
            'manager': self.u_manager,
        }

    def test_acl_matrix(self):
        for model, expected in MATRIX.items():
            for role, user in self.users().items():
                got = tuple(int(self.env[model].with_user(user).has_access(op)) for op in OPS)
                self.assertEqual(got, expected[role], "%s / %s" % (model, role))

    def test_outsider_has_no_access(self):
        outsider = self.env['res.users'].with_context(no_reset_password=True).create(
            {'name': "Без ролей", 'login': 'td_outsider', 'password': 'td_outsider_pw', 'group_ids': [(6, 0, [])]}
        )
        for model in MATRIX:
            self.assertFalse(self.env[model].with_user(outsider).has_access('read'), model)

    def test_every_new_model_has_company_rule(self):
        for model in MATRIX:
            rules = self.env['ir.rule'].sudo().search([('model_id.model', '=', model), ('global', '=', True)])
            self.assertEqual(len(rules), 1, model)

    def test_comment_company_isolation(self):
        company2 = self.env['res.company'].create({'name': "Друга компанія W0-B"})
        site2 = self.env['td.site'].create({'name': "Чужа площадка", 'code': 'OTH', 'company_id': company2.id})
        mine = self.env['td.comment'].create({'site_id': self.site.id, 'text': "Моє"})
        foreign = self.env['td.comment'].create({'site_id': site2.id, 'text': "Чуже"})
        seen = self.env['td.comment'].with_user(self.u_tech).search([('id', 'in', (mine | foreign).ids)])
        self.assertEqual(seen, mine)
        with self.assertRaises(AccessError):
            foreign.with_user(self.u_tech).read(['text'])

    def test_slot_type_global_and_company_visibility(self):
        company2 = self.env['res.company'].create({'name': "Друга компанія типів"})
        glob = self.env['td.slot.type'].create({'code': 'GLB', 'name': "Каталог"})
        mine = self.env['td.slot.type'].create({'code': 'MYT', 'name': "Мій", 'company_id': self.company.id})
        foreign = self.env['td.slot.type'].create({'code': 'FRN', 'name': "Чужий", 'company_id': company2.id})
        seen = self.env['td.slot.type'].with_user(self.u_plain).search([('id', 'in', (glob | mine | foreign).ids)])
        self.assertEqual(seen, glob | mine)

    def test_designer_edits_library_but_cannot_delete(self):
        Type = self.env['td.slot.type'].with_user(self.u_tech)
        rec = Type.create({'code': 'TCH', 'name': "Створено технологом", 'company_id': self.company.id})
        rec.write({'name': "Змінено"})
        with self.assertRaises(AccessError):
            rec.unlink()
        rec.with_user(self.u_manager).unlink()

    def test_publish_op_is_read_only_for_everyone_but_sudo(self):
        version = self.env['td.layout.version'].create({'site_id': self.site.id, 'n': 1})
        vals = {'version_id': version.id, 'seq': 1, 'op': 'create', 'res_model': 'stock.location', 'code': 'X'}
        with self.assertRaises(AccessError):
            self.env['td.publish.op'].with_user(self.u_manager).create(vals)
        op = self.env['td.publish.op'].sudo().create(vals)
        self.assertEqual(op.with_user(self.u_plain).code, 'X')
