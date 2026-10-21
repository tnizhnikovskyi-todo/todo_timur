"""Заглушка W1: клас `TestChpHoot` (Hoot-набір `@td_chp`) заповнює W2. Тест пропускається."""

from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install", "td_chp")
class TestChpHoot(HttpCase):
    def test_hoot_suite(self):
        self.skipTest("Hoot-набір пульта КГУ додає W2")
