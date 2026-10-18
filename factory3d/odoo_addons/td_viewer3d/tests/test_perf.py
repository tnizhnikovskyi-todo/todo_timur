import gzip
import json
import logging
import time
from datetime import timedelta

from odoo import fields
from odoo.tests import HttpCase, tagged

from odoo.addons.td_viewer3d.tools.payload import DeltaBuilder, PayloadBuilder

from .common import F3dViewerCase

_logger = logging.getLogger(__name__)

LIMIT_DATA_S = 1.5
LIMIT_DATA_SQL = 80
LIMIT_FULL_S = 2.0
LIMIT_GZIP_KB = 250
LIMIT_STATIC_FIRST_S = 0.3
LIMIT_STATIC_SECOND_S = 0.1
LIMIT_DELTA_S = 0.3
LIMIT_DELTA_SQL = 30


@tagged("post_install", "-at_install", "f3d", "f3d_viewer", "f3d_perf")
class TestPerf(HttpCase, F3dViewerCase):
    """AC-52, SPEC §13.4 / ARCHITECTURE §2.7: пороги на демо-базі (в ORM, без мережі)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.admin = cls.env.ref("base.user_admin")
        cls.admin.password = "admin"

    def setUp(self):
        super().setUp()
        self.env = self.env(user=self.admin)  # assertQueryCount ключується за логіном env.user
        self.demo_clock()

    def _build(self, **kw):
        return PayloadBuilder(self.env(user=self.admin), **kw).build()

    def test_data_time_and_queries(self):
        self._build()  # прогрів кешів реєстру/статики
        self.env.invalidate_all()
        n0 = self.env.cr.sql_log_count
        t0 = time.perf_counter()
        data = self._build()
        elapsed = time.perf_counter() - t0
        _logger.info("PERF /data: %.3f с, %d SQL", elapsed, self.env.cr.sql_log_count - n0)
        self.assertTrue(data["meta"])
        self.assertLess(elapsed, LIMIT_DATA_S, f"/data {elapsed:.2f} с")

    def test_data_query_count(self):
        self._build()
        self.env.invalidate_all()
        with self.assertQueryCount(admin=LIMIT_DATA_SQL):
            self._build()

    def test_data_full_and_gzip_size(self):
        self._build(full=True)
        t0 = time.perf_counter()
        data = self._build(full=True)
        elapsed = time.perf_counter() - t0
        _logger.info("PERF /data?full=1: %.3f с", elapsed)
        self.assertLess(elapsed, LIMIT_FULL_S, f"/data?full=1 {elapsed:.2f} с")
        self.assertIn("passports", data)

    def test_payload_gzip_size(self):
        raw = json.dumps(self._build(full=True), ensure_ascii=False, separators=(",", ":")).encode()
        size_kb = len(gzip.compress(raw)) / 1024
        _logger.info("PERF full gzip: %.0f КБ (raw %.0f КБ)", size_kb, len(raw) / 1024)
        self.assertLess(size_kb, LIMIT_GZIP_KB, f"gzip {size_kb:.0f} КБ")

    def test_static_cached(self):
        self.authenticate("admin", "admin")
        t0 = time.perf_counter()
        res = self.url_open("/f3d/viewer/static")
        first = time.perf_counter() - t0
        self.assertEqual(res.status_code, 200)
        t0 = time.perf_counter()
        res = self.url_open("/f3d/viewer/static")
        second = time.perf_counter() - t0
        self.assertEqual(res.status_code, 200)
        _logger.info("PERF /static: перший %.0f мс, другий %.0f мс", first * 1000, second * 1000)
        self.assertLess(first, LIMIT_STATIC_FIRST_S, f"/static перший {first * 1000:.0f} мс")
        self.assertLess(second, LIMIT_STATIC_SECOND_S, f"/static другий {second * 1000:.0f} мс")

    def test_delta_50_codes(self):
        codes = []
        for loc in self.env["stock.location"].search([("td_code", "!=", False)], limit=50):
            codes.append(loc.td_code)
        self.assertEqual(len(codes), 50)
        since = fields.Datetime.now() - timedelta(minutes=5)
        DeltaBuilder(self.env(user=self.admin), since, codes=codes).build()  # прогрів
        n0 = self.env.cr.sql_log_count
        t0 = time.perf_counter()
        DeltaBuilder(self.env(user=self.admin), since, codes=codes).build()
        elapsed = time.perf_counter() - t0
        _logger.info("PERF /delta 50: %.3f с, %d SQL", elapsed, self.env.cr.sql_log_count - n0)
        self.assertLess(elapsed, LIMIT_DELTA_S, f"/delta {elapsed * 1000:.0f} мс")

    def test_delta_query_count(self):
        since = fields.Datetime.now() - timedelta(minutes=5)
        codes = self.env["stock.location"].search([("td_code", "!=", False)], limit=50).mapped("td_code")
        DeltaBuilder(self.env(user=self.admin), since, codes=codes).build()
        with self.assertQueryCount(admin=LIMIT_DELTA_SQL):
            DeltaBuilder(self.env(user=self.admin), since, codes=codes).build()
