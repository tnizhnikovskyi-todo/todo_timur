"""ensure_http_push (stand_odoo_setup.py) на фиктивном Odoo: источник HTTP-PUSH приводится к виду, при котором сборщик
принимает POST /f3d/lpr/<секрет> (иначе 404). Без сети и Odoo. Запуск из этого каталога:
python3 -m unittest test_stand_odoo_setup"""

import contextlib
import io
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import stand_odoo_setup as setup


class FakeOdoo:
    """Минимум API Odoo, который нужен ensure_http_push: search_read и call(write)."""

    def __init__(self, source=None, collector_id=7, collector_code="COL-MAIN"):
        self.source = source
        self.collectors = [{"id": collector_id, "code": collector_code}] if collector_id else []
        self.writes = []

    def search_read(self, model, domain, fields, **kw):
        if model == "td.source":
            return [dict(self.source)] if self.source else []
        code = domain[0][2]
        return [{"id": c["id"]} for c in self.collectors if c["code"] == code]

    def call(self, model, method, ids, vals):
        assert (model, method) == ("td.source", "write")
        self.writes.append(vals)
        self.source.update(vals)
        if "collector_id" in vals:
            self.source["collector_id"] = [vals["collector_id"], "COL"]
        return True


def old_source(**kw):
    base = {
        "id": 3,
        "params": {"routes": ["lpr"], "allow_ips": ["iot-sim"]},  # ни secret_ref, ни token_ref
        "active": False,
        "read_enabled": False,
        "collector_id": False,
    }
    base.update(kw)
    return base


def run(odoo):
    with contextlib.redirect_stderr(io.StringIO()) as err:
        setup.ensure_http_push(odoo)
    return err.getvalue()


class EnsureHttpPushTest(unittest.TestCase):
    def test_brings_source_to_working_state(self):
        odoo = FakeOdoo(old_source())
        run(odoo)
        src = odoo.source
        self.assertEqual(src["params"]["secret_ref"], "F3D_HTTP_PUSH_SECRET_LPR")
        self.assertEqual(src["params"]["token_ref"], "F3D_HTTP_PUSH_TOKEN_LPR")
        self.assertEqual(src["params"]["routes"], ["lpr"])
        self.assertEqual(src["params"]["allow_ips"], ["iot-sim", "127.0.0.1"])
        self.assertTrue(src["active"] and src["read_enabled"])
        self.assertEqual(src["collector_id"][0], 7)

    def test_idempotent_and_keeps_foreign_values(self):
        odoo = FakeOdoo(old_source(params={"routes": ["lpr", "alarm"], "allow_ips": ["10.0.0.5"], "max_body_kb": 64}))
        run(odoo)
        self.assertEqual(odoo.source["params"]["routes"], ["lpr", "alarm"])
        self.assertEqual(odoo.source["params"]["allow_ips"], ["10.0.0.5", "iot-sim", "127.0.0.1"])
        self.assertEqual(odoo.source["params"]["max_body_kb"], 64)
        self.assertEqual(len(odoo.writes), 1)
        out = run(odoo)
        self.assertEqual(len(odoo.writes), 1, "повторный запуск ничего не пишет")
        self.assertIn("уже в нужном состоянии", out)

    def test_other_collector_is_relinked_and_secrets_are_names_only(self):
        odoo = FakeOdoo(old_source(collector_id=[99, "чужой"], active=True, read_enabled=True), collector_id=7)
        run(odoo)
        self.assertEqual(odoo.source["collector_id"][0], 7)
        self.assertEqual(set(odoo.writes[0]), {"params", "collector_id"})
        for value in odoo.source["params"].values():
            self.assertNotRegex(str(value), r"^[0-9a-f]{32,}$")

    def test_collector_code_from_env_and_missing_collector(self):
        os.environ["TD_COLLECTOR_CODE"] = "COL-X"
        try:
            odoo = FakeOdoo(old_source(), collector_id=5, collector_code="COL-X")
            run(odoo)
            self.assertEqual(odoo.source["collector_id"][0], 5)
            no_col = FakeOdoo(old_source(), collector_id=0)
            run(no_col)
            self.assertFalse(no_col.source["collector_id"])  # коллектора нет: привязку не придумываем
            self.assertTrue(no_col.source["active"])
        finally:
            del os.environ["TD_COLLECTOR_CODE"]

    def test_missing_source_is_not_an_error(self):
        odoo = FakeOdoo(None)
        self.assertIn("не найден", run(odoo))
        self.assertEqual(odoo.writes, [])


if __name__ == "__main__":
    unittest.main()
