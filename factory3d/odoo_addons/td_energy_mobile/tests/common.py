"""W4-C: `TestWHCommon` — фікстури мобільного модуля (W4_SPEC H.13). Каркас: фікстури додає воркер C.

Воркер C зберігає ім'я `TAGS` і `TestWHCommon` (їх імпортує контрактний тест менеджера).
"""

from odoo.addons.td_energy.tests.common import TestW1Common

TAGS = ("post_install", "-at_install", "td", "td_wh")


class TestWHCommon(TestW1Common):
    """Каркас: базові фікстури W1 (користувачі `u_view/u_cost/u_eng/…`, час `f3d_now`)."""
