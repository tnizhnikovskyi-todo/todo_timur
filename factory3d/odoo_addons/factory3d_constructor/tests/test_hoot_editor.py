from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install", "f3d", "f3d_constructor")
class TestEditorHoot(HttpCase):
    """ЗАГЛУШКА скелета (W1). W2 запускає тут HOOT suite `@factory3d_constructor/editor`
    (патерн factory3d_viewer/tests/test_hoot.py) і покриває AC-10, 12, 14, 17, 18, 22, 31, 48, 49, 61, 63…66 (JS)."""
