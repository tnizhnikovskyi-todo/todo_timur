from odoo.tests import tagged
from odoo.tests.common import BaseCase

from ..tools import sim_catalog as sc
from .common import F3DTelemetryCase

p = sc.parse_sim_address


@tagged("post_install", "-at_install", "f3d", "f3d_telemetry")
class TestParse(BaseCase):
    """AC-51: парсер адрес каталогу емулятора (R-24)."""

    def test_r24_examples(self):
        self.assertEqual(
            p("modbus", "Modbus u70 (Elektronikon Mk5, ПРИПУЩЕННЯ) HR 3002 (Outlet pressure)", "U16", "×0,001"),
            {"unit": 70, "fc": 3, "addr": 3001, "type": "u16", "scale": 0.001, "doc": "HR 3002 (Outlet pressure)"},
        )
        got = p("modbus", "Modbus u90 (ADAM-6017) HR 40001 (AI0, 4–20 мА = 0…32 000 м³/год)", "U16", "R-20")
        self.assertEqual(
            {k: got[k] for k in ("unit", "fc", "addr", "type", "offset", "range")},
            {"unit": 90, "fc": 3, "addr": 0, "type": "u16", "offset": 0, "range": [0, 32000]},
        )
        self.assertAlmostEqual(got["scale"], 32000 / 65535, places=6)
        got = p("modbus", "Modbus u84 (ADAM-6050) HR 40017–40018 (лічильник DI8, 1 імп = 10 л)", "U32", "×0,01")
        self.assertEqual(
            {k: v for k, v in got.items() if k != "doc"},
            {"unit": 84, "fc": 3, "addr": 16, "count": 2, "type": "u32", "wordorder": "little", "scale": 0.01},
        )
        self.assertEqual(
            p("mqtt", "MQTT f3d/mobile/FL-1/telemetry → $.battery_pct"),
            {"topic": "f3d/mobile/FL-1/telemetry", "path": "$.battery_pct"},
        )
        self.assertEqual(
            p("bacnet", "BACnet dev 140 AI:1 Present_Value (подача)"),
            {"device": 140, "object": "analog-input", "instance": 1, "property": "present-value"},
        )
        self.assertEqual(
            p("modbus", "Modbus u84 (ADAM-6050) DI0 coil 00001 (вентилятори в роботі), DI1 coil 00002 (аварія)"),
            {
                "unit": 84,
                "fc": 2,
                "states": [
                    {"addr": 1, "eq": 1, "text": "fault"},
                    {"addr": 0, "eq": 1, "text": "running"},
                    {"addr": 0, "eq": 0, "text": "stopped"},
                ],
            },
        )

    def test_vendor_pdu_rule(self):
        """X-42: Huawei/TEDOM — номер як є; PM5560/Elektronikon — N−1; ADAM — за діапазоном."""
        self.assertEqual(
            p("modbus", "Modbus u61 HR 32080–32081", "I32", "×0,001"),
            {"unit": 61, "fc": 3, "addr": 32080, "count": 2, "type": "i32", "scale": 0.001, "doc": "HR 32080–32081"},
        )
        self.assertEqual(p("modbus", "Modbus u72 (TEDOM) HR 40000", "U16")["addr"], 40000)
        self.assertEqual(p("modbus", "Modbus u1 (PM5560) HR 3060–3061", "F32")["addr"], 3059)
        self.assertEqual(p("modbus", "Modbus u71 (ATyS p) HR 20483", "U16")["addr"], 20483)
        self.assertEqual(p("modbus", "Modbus u84 HR 40001", "U16")["addr"], 0)
        ai = p("modbus", "Modbus u84 HR 30005", "U16")
        self.assertEqual((ai["fc"], ai["addr"]), (4, 4))

    def test_pdu_notation(self):
        self.assertEqual(
            {k: v for k, v in p("modbus", "Modbus u61 fc3 pdu32080+2", "I32").items() if k != "doc"},
            {"unit": 61, "fc": 3, "addr": 32080, "count": 2, "type": "i32"},
        )
        got = p(
            "modbus", "Modbus u96 fc3 pdu0+3 u16 max · ADAM-6015 40001–40003 RTD", "U16", "0–65535 → −50…+150 °C (R-20)"
        )
        self.assertEqual((got["count"], got["agg"], got["offset"], got["range"]), (3, "max", -50, [-50, 150]))
        self.assertAlmostEqual(got["scale"], 200 / 65535, places=7)
        enum = p("modbus", "Modbus u70 fc3 pdu3000 u16 · Elektronikon", "U16", "—", "0 stop/1 load/2 unload/3 fault")
        self.assertEqual(enum["map"], {"0": "stop", "1": "load", "2": "unload", "3": "fault"})

    def test_opcua_http_sics(self):
        self.assertEqual(
            p("opcua", "ns=2;s=SAW-1.State.Machine.Flags.Alarm (+ Error, Warning)"),
            {"nodeid": "ns=2;s=SAW-1.State.Machine.Flags.Alarm"},
        )
        self.assertEqual(
            p("http", "HTTP POST <collector>/f3d/lpr → plateText, plateCountry, carState, datetime (камера GATE-W)"),
            {"route": "lpr", "path": "$.plateText"},
        )
        self.assertEqual(
            p("sics", "SICS TCP :4001 «SI» → «S S  21380 kg» / «SIR» потік"), {"cmd": "SI", "field": "weight"}
        )
        self.assertEqual(p("sics", "SICS TCP :4001 «SI» → stable (S S / S D)"), {"cmd": "SI", "field": "stable"})
        self.assertIsNone(p("sics", "SICS TCP :4001 «Z» → ok"))
        self.assertEqual(
            p("rest", "GET /api/v1/status → $.vacuum_kpa"),
            {"method": "GET", "path": "/api/v1/status", "json_path": "$.vacuum_kpa"},
        )

    def test_piv(self):
        self.assertEqual(
            p("bacnet", "BACnet dev 200 PIV:3 Present_Value (запиленість)"),
            {"device": 200, "object": "positive-integer-value", "instance": 3, "property": "present-value"},
        )

    def test_unparsed(self):
        for text in (
            "Σ Modbus u61…u68 HR 32080–32081",
            "похідна m3_total за 5 хв",
            "Modbus u99 HR 100",
            "GET /api/v1/jobs?state=active → $[0].id",
            "обчислює energy (R-11) — без адреси",
            "",
        ):
            with self.subTest(text=text):
                self.assertIsNone(p("x", text))

    def test_helpers(self):
        self.assertEqual(sc.source_key("Modbus u70 HR 3002"), "u70")
        self.assertEqual(sc.source_key("BACnet dev 140 AI:1"), "dev140")
        self.assertEqual(sc.source_key("MQTT f3d/x → $.a"), "mqtt")
        self.assertEqual(sc.source_key("HTTP POST <collector>/f3d/lpr → a"), "http:lpr")
        self.assertEqual(sc.module_for_code("infra/water/m3_total"), "telemetry")
        self.assertEqual(sc.module_for_code("infra/totals/pv_now"), "energy")
        self.assertEqual(sc.module_for_code("ventilation/units/RV-05/filter_dp_pa"), "bms")
        self.assertEqual(sc.parse_nominal("12.18 (шум 0.08)"), 12.18)


@tagged("post_install", "-at_install", "f3d", "f3d_telemetry")
class TestImportRows(F3DTelemetryCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_telemetry_fixtures()

    def test_import_rows(self):
        """AC-52."""
        rows = [
            {
                "code": "equipment/COMPRESSOR-T/temp_c",
                "name": "Компресор-T: температура",
                "protocol": "P-07",
                "address": "Modbus u70 HR 3003",
                "dtype": "U16",
                "unit": "°C",
                "scale": "×0,1",
                "nominal": "60 (шум 1)",
                "thresholds": "—",
                "kind": "gauge",
            },
            {
                "code": self.sig_press.code,
                "name": "x",
                "protocol": "P-07",
                "address": "Modbus u70 HR 3002",
                "dtype": "U16",
                "unit": "бар",
                "scale": "×0,001",
                "nominal": "7",
                "thresholds": "—",
                "kind": "gauge",
            },
            {
                "code": "energy/consumers/SIGMA-T/p_now",
                "name": "Σ",
                "protocol": "P-05",
                "address": "Σ Modbus u61…u68 HR 32080–32081",
                "dtype": "F32",
                "unit": "кВт",
                "scale": "×1",
                "nominal": "1",
                "thresholds": "—",
                "kind": "gauge",
            },
            {
                "code": "Bad/Code",
                "name": "bad",
                "protocol": "P-07",
                "address": "Modbus u70 HR 3002",
                "dtype": "U16",
                "unit": "",
                "scale": "",
                "nominal": "",
                "thresholds": "",
                "kind": "gauge",
            },
        ]
        last_before = self.sig_press.last_value
        self.set_sql(self.sig_press, last_value=6.8)
        res = self.env["td.signal"]._f3d_import_sim_rows(rows, {"u70": "MB-T-U70"}, {})
        self.assertEqual(
            res, {"created": 1, "updated": 1, "unparsed": ["energy/consumers/SIGMA-T/p_now"], "skipped": ["Bad/Code"]}
        )
        new = self.env["td.signal"].search([("code", "=", "equipment/COMPRESSOR-T/temp_c")])
        self.assertEqual((new.origin, new.source_id, new.equipment_id), ("catalog", self.src_mb, self.eq_comp))
        self.assertEqual(
            {k: new.address[k] for k in ("unit", "fc", "addr", "type", "scale")},
            {"unit": 70, "fc": 3, "addr": 3002, "type": "u16", "scale": 0.1},
        )
        self.assertEqual(new.nominal, 60.0)
        self.assertEqual(self.sig_press.source_id, self.src_mb)
        self.assertEqual(self.sig_press.last_value, 6.8)
        self.assertEqual(self.sig_press.address["addr"], 3001)  # наявна адреса не змінена
        self.assertNotEqual(last_before, 6.8)

    def test_no_sim_model(self):
        if "td.sim.signal" in self.env:
            self.skipTest("встановлено td_iot_sim: модель td.sim.signal є")
        self.assertEqual(
            self.env["td.signal"]._f3d_import_sim_catalog(),
            {"created": 0, "updated": 0, "unparsed": [], "skipped": [], "state": "skipped"},
        )
