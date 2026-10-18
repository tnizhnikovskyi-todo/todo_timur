from odoo.tests import tagged

from .common import PASSWORD, F3DConstructorHttpCase

# MERGE.md §3.5: API-11…API-24 -> маршрути; тіло порожнє, відповідь — заглушка W0-B
STUB_ROUTES = [
    ('API-11', '/f3d/constructor/library'),
    ('API-12', '/f3d/constructor/storage_categories'),
    ('API-12', '/f3d/constructor/removal_strategies'),
    ('API-13', '/f3d/constructor/stock/state'),
    ('API-14', '/f3d/constructor/stock/find'),
    ('API-15', '/f3d/constructor/putaway/where'),
    ('API-15', '/f3d/constructor/putaway/fit'),
    ('API-16', '/f3d/constructor/odoo/locations'),
    ('API-17', '/f3d/constructor/codes/check'),
    ('API-18', '/f3d/constructor/publish/log'),
    ('API-18', '/f3d/constructor/publish/rollback'),
    ('API-19', '/f3d/constructor/render/labels_pdf'),
    ('API-19', '/f3d/constructor/render/table_xlsx'),
    ('API-19', '/f3d/constructor/render/plan_pdf'),
    ('API-19', '/f3d/constructor/render/spec_pdf'),
    ('API-20', '/f3d/constructor/parse/table'),
    ('API-21', '/f3d/constructor/variants'),
    ('API-22', '/f3d/constructor/comments'),
    ('API-23', '/f3d/constructor/locks'),
    ('API-24', '/f3d/constructor/version/view'),
    ('API-24', '/f3d/constructor/version/checkpoint'),
]


@tagged("post_install", "-at_install", "f3d", "f3d_constructor")
class TestSkeletonApi(F3DConstructorHttpCase):
    """W0-B: заглушки API-11…API-24 відповідають `not_implemented` (HTTP 200, `ok: false`), як очікувана помилка."""

    def test_all_stub_routes_not_implemented(self):
        self.authenticate(self.u_plain.login, PASSWORD)
        for api, route in STUB_ROUTES:
            res = self.rpc(route, site_id=self.site.id)
            self.assertEqual(res['ok'], False, route)
            self.assertEqual(res['code'], 'not_implemented', route)
            self.assertIn(api, res['message'], route)

    def test_stub_routes_accept_empty_body_and_any_role(self):
        for user in (self.u_manager, self.u_tech, self.u_store, self.u_eng):
            self.authenticate(user.login, PASSWORD)
            res = self.rpc('/f3d/constructor/library')
            self.assertEqual((res['ok'], res['code']), (False, 'not_implemented'), user.login)

    def test_stub_routes_are_registered_once(self):
        """Кожен маршрут API-11…24 належить рівно одному методу контролера (дублі ламають слайси)."""
        mapping = self.env['ir.http'].routing_map()
        for _api, route in STUB_ROUTES:
            rules = [rule for rule in mapping.iter_rules() if rule.rule == route]
            self.assertEqual(len(rules), 1, route)
