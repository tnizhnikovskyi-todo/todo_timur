from odoo.tests import TransactionCase, new_test_user


class YardCase(TransactionCase):
    """Спільна база тестів двору: користувачі за ролями."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user_reader = new_test_user(cls.env, "yard_reader", groups="factory3d_base.group_f3d_user")
        cls.user_guard = new_test_user(cls.env, "yard_guard", groups="factory3d_yard.group_f3d_yard_security")
        cls.user_dispatcher = new_test_user(cls.env, "yard_disp", groups="factory3d_yard.group_f3d_yard_dispatcher")
        cls.user_manager = new_test_user(cls.env, "yard_mgr", groups="factory3d_yard.group_f3d_yard_manager")
