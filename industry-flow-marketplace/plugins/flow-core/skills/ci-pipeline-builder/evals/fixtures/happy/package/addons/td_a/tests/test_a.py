from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestA(TransactionCase):
    def test_ok(self):
        self.assertTrue(True)
