"""ТП-10 (R-64): `get_control` ≤ 40 SQL, `prepare`/`confirm` без лавини запитів."""

import logging

from odoo.tests import tagged

from .common import TAGS, TestControlCommon

_logger = logging.getLogger(__name__)


@tagged(*TAGS)
class TestPerformance(TestControlCommon):
    def count(self, fn):
        before = self.cr.sql_log_count
        fn()
        return self.cr.sql_log_count - before

    def test_get_control_queries(self):
        self.ctl(self.u_en1).get_control()  # прогрів кешів ORM
        n = self.count(lambda: self.ctl(self.u_en1).get_control())
        _logger.info("TP-10 get_control: %d SQL", n)
        self.assertLessEqual(n, 40, "get_control: %d запитів" % n)

    def test_prepare_confirm_queries(self):
        self.ctl(self.u_en1).prepare("bess_charge")
        prep = {}
        n1 = self.count(lambda: prep.update(self.ctl(self.u_en1).prepare("bess_charge", {"power_kw": 40})))
        n2 = self.count(lambda: self.ctl(self.u_en1).confirm(prep["token"]))
        _logger.info("TP-10 prepare: %d SQL, confirm: %d SQL", n1, n2)
        self.assertLessEqual(n1, 80)
        self.assertLessEqual(n2, 120)
