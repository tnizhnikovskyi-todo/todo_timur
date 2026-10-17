from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install", "f3d", "f3d_constructor")
class TestModelHoot(HttpCase):
    """ЗАГЛУШКА скелета (W1). W3 запускає тут HOOT suite `@factory3d_constructor/model`
    (патерн factory3d_viewer/tests/test_hoot.py) і покриває AC-34, 35, 37…42 (JS)."""
