from odoo.tests import TransactionCase, new_test_user, tagged


@tagged("post_install", "-at_install", "f3d", "f3d_bms")
class F3DBmsCase(TransactionCase):
    """Спільна база тестів будівлі: користувачі за ролями (W0). Фікстури об'єктів додають W1…W5 (SPEC §13.0)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user_reader = new_test_user(cls.env, "bms_reader", groups="base.group_user,factory3d_base.group_f3d_user")
        cls.user_operator = new_test_user(cls.env, "bms_oper", groups="base.group_user,factory3d_bms.group_f3d_bms_operator")
        cls.user_manager = new_test_user(cls.env, "bms_mgr", groups="base.group_user,factory3d_base.group_f3d_manager")
        cls.user_admin = new_test_user(cls.env, "bms_admin", groups="base.group_user,factory3d_base.group_f3d_admin")
