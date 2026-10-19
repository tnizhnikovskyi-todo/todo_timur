import unittest

from odoo.modules import Manifest
from odoo.tests import tagged

from .common import F3DConstructorHttpCase

URL = "/odoo/action-td_constructor.action_td_constructor?debug=1"


def tours_registered():
    """Тури Odoo (static/src/tours/*) підключає в `web.assets_tests` маніфесту менеджер при зливанні S6."""
    manifest = Manifest.for_addon("td_constructor", display_warning=False)
    return any(
        "td_constructor/static/src/tours" in path for path in manifest.get("assets", {}).get("web.assets_tests", [])
    )


@tagged("post_install", "-at_install", "f3d", "f3d_constructor", "f3d_s6")
class TestS6Tours(F3DConstructorHttpCase):
    """F12/F13/F19 у браузері Odoo: тури web_tour з реальним редактором (нульовий рендерер, `?debug=1`)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tour_mgr = cls._f3d_user('tour_mgr', ['manager'])
        cls.tour_store = cls._f3d_user('tour_store', ['storekeeper'])
        for user in (cls.tour_mgr, cls.tour_store):
            user.password = user.login  # start_tour входить із паролем = логіну
        cls.rack = cls.make_slot(cls, prefix='TQ-TOUR')
        cls.env.ref('td_constructor.action_td_constructor').params = {'site_id': cls.site.id, 'f3d_test': 1}

    def setUp(self):
        super().setUp()
        if not tours_registered():
            raise unittest.SkipTest(
                "Тури не підключено: `web.assets_tests: td_constructor/static/src/tours/*.js` у маніфест"
            )

    def test_variants_tour(self):
        self.start_tour(URL, "td_constructor_variants_tour", login="tour_mgr", timeout=240)
        variants = self.env['td.layout.variant'].search([('site_id', '=', self.site.id)])
        self.assertEqual(sorted(variants.mapped('name')), ["Проєкт A", "Як є"])
        self.assertFalse(variants.filtered('is_training'), "навчальну копію скасовано")
        self.assertEqual(self.site.active_variant_id.name, "Проєкт A")
        self.assertTrue(
            self.env['td.slot'].search_count([('site_id', '=', self.site.id), ('code_prefix', '=', 'TOUR-V1')])
        )

    def test_collab_tour(self):
        self.start_tour(URL, "td_constructor_collab_tour", login="tour_mgr", timeout=240)
        comments = self.env['td.comment'].search([('site_id', '=', self.site.id)], order='id')
        self.assertEqual(len(comments), 2)
        self.assertEqual(comments.mapped('state'), ['resolved', 'resolved'])
        self.assertEqual(set(comments.mapped('target_uid')), {self.rack.uid}, "коментарі прив'язані до виділеного ряду")
        self.assertEqual(set(comments.mapped('target_kind')), {'slot'})
        task = comments.filtered(lambda c: c.kind == 'task')
        self.assertEqual((task.assignee_id, task.author_id), (self.tour_store, self.tour_mgr))
        self.assertFalse(task.activity_ids, "завдання виконавця закрито вирішенням")
        done = self.env['mail.message'].search_count(
            [
                ('model', '=', 'td.comment'),
                ('res_id', '=', task.id),
                ('subtype_id', '=', self.env.ref('mail.mt_activities').id),
            ]
        )
        self.assertGreaterEqual(done, 1, "виконане завдання лишилось у обговоренні")

    def test_guide_tour(self):
        self.start_tour(URL, "td_constructor_guide_tour", login="tour_mgr", timeout=240)
