"""AC-66…AC-68: API-01 — одноразова видача списку деталей колектору."""

from datetime import timedelta

from odoo import fields
from odoo.tests import tagged

from .common import F3DMachineHttpCase

EXPECTED_CSV = (
    "PartId;Description;Material;Length;Width;Quantity;Grain;EdgeTop;EdgeBottom;EdgeLeft;EdgeRight;Program\r\n"
    "P001;Боковина;BOARD-T;720;560;28;1;EB-T;;EB-T;;\r\n"
)


@tagged("post_install", "-at_install", "f3d", "f3d_machine_connect")
class TestApiExport(F3DMachineHttpCase):
    def setUp(self):
        super().setUp()
        self.mo = self.make_mo(self.wc_saw, qty=14, comps=((self.board, 8 / 14),), name="WH/MO/T0233")
        self.env["f3d.cut.part"].create(
            {
                "bom_id": self.mo.bom_id.id,
                "part_code": "P001",
                "name": "Боковина",
                "length_mm": 720,
                "width_mm": 560,
                "qty": 2,
                "grain": "1",
                "edge_top": "EB-T",
                "edge_left": "EB-T",
            }
        )
        self.map = self.env["f3d.cut.map"]._f3d_create_for(self.mo, "main")
        self.map.mode = "manual"
        self.map.action_export()
        self.t = self.map.sudo()._f3d_new_export_token()

    def _get(self, map_id=None, t="default", token="default", query=""):
        """`t` — одноразовий токен у заголовку `X-F3D-Token` (DEC-20); `None` — без заголовка."""
        t = self.t if t == "default" else t
        token = self.token if token == "default" else token
        headers = {"Authorization": "Bearer %s" % token} if token else {}
        if t is not None:
            headers["X-F3D-Token"] = t
        return self.url_open("/f3d/machine/cutmap/%d/export%s" % (map_id or self.map.id, query), headers=headers)

    def test_export_ok_once(self):
        resp = self._get()
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers["Cache-Control"], "no-store")
        self.assertIn("application/json", resp.headers["Content-Type"])
        body = resp.json()
        self.assertEqual(body["parts_csv"], EXPECTED_CSV)
        self.assertEqual(
            (body["map"], body["external_ref"], body["machine"], body["material"], body["sheet"], body["priority"]),
            (self.map.name, "WH/MO/T0233", "SAW-T", "BOARD-T", "2800x2070x16", 5),
        )
        self.assertEqual(body["parts"], 28)
        self.assertEqual(self._get().status_code, 403)  # одноразовий
        self.assertTrue(self.map.message_ids.filtered(lambda m: "COL-T" in (m.body or "")))

    def test_token_header_only(self):
        """DEC-20: токен `t` — лише в заголовку; у query не приймається; без заголовка — 400."""
        resp = self._get(t=None, query="?t=%s" % self.t)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["error"]["code"], "bad_token")
        self.assertEqual(self._get(t=None).status_code, 400)
        self.assertEqual(self._get(t="XYZ").status_code, 400)
        self.assertTrue(self.map.sudo().export_token_hash)  # токен не витрачено
        self.assertEqual(self._get(query="?t=%s" % ("0" * 16)).status_code, 200)  # query ігнорується

    def test_token_not_in_access_log(self):
        """DEC-20 / ТБ-03: токен не потрапляє в рядок access-log (URL без query)."""
        with self.assertLogs("werkzeug", level="INFO") as cm:
            self.assertEqual(self._get().status_code, 200)
        self.assertTrue(cm.output)
        self.assertFalse([ln for ln in cm.output if self.t in ln], cm.output)

    def test_errors(self):
        cases = [
            ("no bearer", dict(token=None), 401),
            ("other token", dict(token="x" * 43), 401),
            ("bad format", dict(t="xyz"), 400),
            ("wrong t", dict(t="0" * 16), 403),
            ("missing map", dict(map_id=self.map.id + 10000), 404),
            ("no bearer wrong t", dict(token=None, t="xyz"), 401),
            ("no t header", dict(t=None), 400),
        ]
        for label, kw, status in cases:
            with self.subTest(case=label):
                self.assertEqual(self._get(**kw).status_code, status)
        self.map.sudo().export_token_expires = fields.Datetime.now() - timedelta(seconds=1)
        self.assertEqual(self._get().status_code, 410)
        self.map.sudo().export_token_expires = fields.Datetime.now() + timedelta(seconds=60)
        self.map.sudo().state = "draft"
        self.assertEqual(self._get().status_code, 409)
        self.assertEqual(self._get().json()["error"]["code"], "bad_state")

    def test_too_large(self):
        line = self.map.line_ids
        vals = [
            {
                "map_id": self.map.id,
                "part_code": "Q%04d" % i,
                "name": "Деталь",
                "length_mm": 100,
                "width_mm": 100,
                "qty": 1,
            }
            for i in range(6000)
        ]
        self.assertTrue(line)
        self.env["f3d.cut.map.line"].sudo().create(vals)
        resp = self._get()
        self.assertEqual(resp.status_code, 413)
        self.assertEqual(resp.json()["error"]["code"], "too_large")
        self.env.invalidate_all()
        self.assertEqual(self.map.state, "error")
