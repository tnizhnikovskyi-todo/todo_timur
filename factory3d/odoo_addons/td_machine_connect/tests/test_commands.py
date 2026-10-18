import json
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import tagged

from ..tools import commands as C
from .common import F3DMachineCase

GANTRY_FEED = {
    "stack": "PLT-03C",
    "target": "SAW-1",
    "sheets": 4,
    "product": "DSP16-ANT",
    "priority": 5,
    "ref": "WH/MO/00233",
}
# (вид, операція, поля, запасний текст, результат call(), запасний result) — таблиця R-21
TABLE = [
    (
        "job",
        "Store",
        {"job": "WO00013", "qty": 14, "ref": "WH/MO/00233", "priority": 5},
        "Store;WO00013;14;WH/MO/00233;5",
        {"ReturnStatus": 0},
        "ok ReturnStatus=0",
    ),
    (
        "job",
        "StoreAndStart",
        {"job": "WO00013", "qty": 14, "ref": "WH/MO/00233", "priority": 5},
        "StoreAndStart;WO00013;14;WH/MO/00233;5",
        {"ReturnStatus": 0},
        "ok ReturnStatus=0",
    ),
    ("job", "Stop", {"job": "WO00013"}, "Stop;WO00013", {"ReturnStatus": 0}, "ok ReturnStatus=0"),
    ("job", "Clear", {"job": "WO00013"}, "Clear;WO00013", {"ReturnStatus": 0}, "ok ReturnStatus=0"),
    (
        "gantry",
        "feed",
        GANTRY_FEED,
        "feed;PLT-03C;SAW-1;4;DSP16-ANT;5;WH/MO/00233",
        {"id": "wj-00412", "state": "queued"},
        "wj-00412",
    ),
    (
        "gantry",
        "feed",
        {**GANTRY_FEED, "stack": None},
        "feed;*;SAW-1;4;DSP16-ANT;5;WH/MO/00233",
        {"id": "wj-00412", "state": "queued"},
        "wj-00412",
    ),
    ("gantry", "cancel", {"id": "wj-00412"}, "cancel;wj-00412", {"id": "wj-00412", "state": "cancelled"}, "cancelled"),
    (
        "gantry",
        "stack",
        {"stack": "PLT-07C", "qty": 55, "product": "DSP16-SON", "lot": "DSP16-SON-2610-321"},
        "stack;PLT-07C;55;DSP16-SON;DSP16-SON-2610-321",
        {"id": "PLT-07C", "qty": 55},
        "stack PLT-07C=55",
    ),
    (
        "gantry",
        "stack",
        {"stack": "PLT-07C", "qty": 55, "product": "DSP16-SON", "lot": None},
        "stack;PLT-07C;55;DSP16-SON;-",
        {"id": "PLT-07C", "qty": 55},
        "stack PLT-07C=55",
    ),
    (
        "cutopt",
        "upload",
        {"map": 12, "token": "9f2c41aa07b3e5d1"},
        "upload;12;9f2c41aa07b3e5d1",
        {"job_id": "cj-00077", "state": "optimizing", "eta_s": 5},
        "cj-00077 optimizing",
    ),
    (
        "cutopt",
        "status",
        {"job": "cj-00077"},
        "status;cj-00077",
        {"job_id": "cj-00077", "state": "planned", "sheets": 7, "waste_pct": 11.4},
        "planned 7 11.4",
    ),
    (
        "cutopt",
        "status",
        {"job": "cj-00077"},
        "status;cj-00077",
        {"job_id": "cj-00077", "state": "optimizing", "sheets": None, "waste_pct": None},
        "optimizing",
    ),
    (
        "cutopt",
        "release",
        {"job": "cj-00077", "machine": "SAW-1", "priority": 5},
        "release;cj-00077;SAW-1;5",
        {"job_id": "cj-00077", "state": "released", "job_order_id": "cj-00077"},
        "released cj-00077",
    ),
    (
        "cutopt",
        "mpr",
        {"job": "cj-00077", "part": "P001"},
        "mpr;cj-00077;P001",
        {"part": "P001", "size_kb": 4},
        "mpr P001 4 КБ",
    ),
    (
        "cutopt",
        "mpr",
        {"job": "cj-00077", "part": "P001"},
        "mpr;cj-00077;P001",
        {"part": "P001", "size_kb": None},
        "no mpr",
    ),
]
LONG_FEED = {
    "stack": "PLT-T1",
    "target": "SAW-T",
    "sheets": 4,
    "product": "B" * 32,
    "priority": 5,
    "ref": "WH/MO/T0001",
}


@tagged("post_install", "-at_install", "f3d", "f3d_machine_connect")
class TestCommands(F3DMachineCase):
    def test_build_parse_examples(self):
        """AC-57: приклади R-21 і таблиця (parse_cmd ∘ build_cmd == build_payload; result_text)."""
        self.assertEqual(C.build_payload("gantry", "feed", **GANTRY_FEED), {"op": "feed", **GANTRY_FEED})
        self.assertEqual(C.build_cmd("gantry", "feed", **GANTRY_FEED), "feed;PLT-03C;SAW-1;4;DSP16-ANT;5;WH/MO/00233")
        with self.assertRaisesRegex(ValueError, "^product: "):
            C.build_payload("gantry", "feed", **{**GANTRY_FEED, "product": "DSP16 ANT"})
        with self.assertRaisesRegex(ValueError, "^stack: відсутнє$"):
            C.check_payload("gantry", {"op": "feed", "sheets": 4})
        with self.assertRaisesRegex(ValueError, "^fields: очікується 5$"):
            C.parse_cmd("gantry", "stack;PLT-07C;55;DSP16-SON;L1;x")
        self.assertEqual(C.parse_cmd("job", "Stop;WO00013"), {"method": "Stop", "job": "WO00013"})
        self.assertEqual(
            C.result_text(
                "gantry",
                {"op": "stack", "stack": "PLT-07C", "qty": 55, "product": "DSP16-SON", "lot": None},
                {"id": "PLT-07C", "qty": 55},
            ),
            "stack PLT-07C=55",
        )
        for kind, op, fields, text, data, result in TABLE:
            with self.subTest(kind=kind, op=op, text=text):
                payload = C.build_payload(kind, op, **fields)
                self.assertEqual(C.check_payload(kind, payload), payload)
                self.assertEqual(C.build_cmd(kind, op, **fields), text)
                self.assertEqual(C.parse_cmd(kind, C.build_cmd(kind, op, **fields)), payload)
                self.assertEqual(C.result_text(kind, payload, data), result)

    def test_five_fuses(self):
        """AC-58: кожен із запобіжників зупиняє створення; формат і вид сигналу."""
        self.enable_write()
        Cmd = self.env["td.command"]
        fields = {"job": "WO00013", "qty": 14, "ref": "WH/MO/00233", "priority": 5}
        cmd = Cmd._f3d_mc_create_command(self.sig_ua_cmd, "Store", fields, {"td_machine_id": self.m_ua.id})
        self.assertEqual(cmd.origin, "machine_connect")
        self.assertEqual(cmd.td_machine_id, self.m_ua)
        self.assertEqual(cmd.payload, {"method": "Store", **fields})
        before = Cmd.search_count([])
        fuses = [
            (
                "td.machine_connect.write_enabled",
                lambda: self._icp().set_param("td.machine_connect.write_enabled", "False"),
            ),
            (
                "td.telemetry.write_enabled",
                lambda: self._icp().set_param("td.telemetry.write_enabled", "False"),
            ),
            (self.src_ua.code, lambda: self.src_ua.write({"write_enabled": False})),
            (self.sig_ua_cmd.code, lambda: self.sig_ua_cmd.write({"write_enabled": False})),
        ]
        for key, turn_off in fuses:
            with self.subTest(fuse=key):
                self.enable_write()
                turn_off()
                with self.assertRaises(UserError) as cm:
                    Cmd._f3d_mc_create_command(self.sig_ua_cmd, "Store", fields)
                self.assertIn(key, str(cm.exception))
        self.enable_write()
        self.assertEqual(Cmd.search_count([]), before)
        with self.assertRaisesRegex(UserError, "не відповідає формату"):
            Cmd._f3d_mc_create_command(self.sig_g_cmd, "feed", {**GANTRY_FEED, "product": "DSP16 ANT"})
        with self.assertRaisesRegex(UserError, "не є сигналом команд верстатів"):
            Cmd._f3d_mc_create_command(self.sig_ua_state, "Store", fields)
        self.assertEqual(Cmd.search_count([]), before)

    def test_payload_and_label(self):
        """AC-102: payload без змін, довідковий text — 63 символи + «…»."""
        self.enable_write()
        cmd = self.env["td.command"]._f3d_mc_create_command(self.sig_g_cmd, "feed", LONG_FEED)
        self.assertEqual(cmd.payload, {"op": "feed", **LONG_FEED})
        self.assertEqual(len(cmd.text), 64)
        self.assertTrue(cmd.text.endswith("…"))
        self.assertEqual(cmd.text[:-1], f"feed;PLT-T1;SAW-T;4;{'B' * 32};5;WH/MO/T0001"[:63])

    def test_fallback_text_mode(self):
        """AC-102: telemetry без payload → запасний текст; довгий текст — UserError; результат без result_data."""
        self.enable_write()
        Cmd = self.env["td.command"]
        with patch.object(type(Cmd), "_f3d_mc_payload_supported", return_value=False):
            with self.assertRaisesRegex(UserError, "length: 66 > 64"):
                Cmd._f3d_mc_create_command(self.sig_g_cmd, "feed", LONG_FEED)
            self.assertFalse(Cmd.search([("origin", "=", "machine_connect")]))
            fields = {**LONG_FEED, "product": "BOARD-T"}
            cmd = Cmd._f3d_mc_create_command(self.sig_g_cmd, "feed", fields)
        self.assertEqual(cmd.text, "feed;PLT-T1;SAW-T;4;BOARD-T;5;WH/MO/T0001")
        self.assertFalse(cmd.payload)
        self.cmd_done(cmd, "wj-00412")
        self.assertEqual(cmd.state, "done")
        self.assertEqual(cmd.result, "wj-00412")
        self.assertFalse(cmd.result_data)

    def test_result_reaction(self):
        """M-20: результат команди верстата — запис у чатері; без власників команда спокійно завершується."""
        self.enable_write()
        cmd = self.env["td.command"]._f3d_mc_create_command(
            self.sig_ua_cmd,
            "Store",
            {"job": "WO00013", "qty": 14, "ref": "WH/MO/00233", "priority": 5},
            {"td_machine_id": self.m_ua.id},
        )
        self.cmd_done(cmd, data={"ReturnStatus": 0})
        body = " ".join(self.m_ua.message_ids.mapped("body"))
        self.assertIn("ReturnStatus", body)
        self.assertEqual(json.loads(json.dumps(cmd.result_data)), {"ReturnStatus": 0})
