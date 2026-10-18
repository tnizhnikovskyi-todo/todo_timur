"""W4-A: `TestW4Common` — фікстури W4 (W4_SPEC 13.0). Каркас: фікстури додає воркер A.

Воркер A зберігає ім'я `TAGS` і `TestW4Common` (їх імпортують тести B і контрактний тест менеджера).
"""

from odoo.addons.td_energy.tests.common import TestW1Common

TAGS = ("post_install", "-at_install", "td", "td_w4")


class TestW4Common(TestW1Common):
    """Каркас: базові фікстури W1 (користувачі `u_view/u_cost/u_eng/…`, час `f3d_now`)."""
