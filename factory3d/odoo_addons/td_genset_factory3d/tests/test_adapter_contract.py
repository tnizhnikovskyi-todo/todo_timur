"""Контракт адаптера td_genset (SPEC §2.0.1): імена існують у td_genset 19, ADP-02…ADP-08 працюють."""

from datetime import timedelta

from odoo import fields
from odoo.tests import TransactionCase, tagged

from ..adapters import td_genset as td

SNAP_KEYS = {
    "ts",
    "online",
    "state_raw",
    "mode_raw",
    "mains_ok",
    "breaker_raw",
    "p_kw",
    "u_v",
    "f_hz",
    "i_a",
    "pf",
    "kwh",
    "fuel_pct",
    "fuel_l",
    "hours",
    "starts",
    "coolant_c",
    "oil_bar",
    "batt_v",
    "charger_v",
    "rpm",
    "alarms",
    "mains_u_v",
    "mains_f_hz",
}
EVENT_KEYS = {"id", "ts", "code", "severity", "name", "value", "unit", "threshold", "text"}
SERVICE_KEYS = {
    "hours_now",
    "interval_h",
    "next_service_hours",
    "last_service_hours",
    "last_service_date",
    "due",
    "hours_left",
}
GENSET_FIELDS = [
    "FIELD_TS",
    "FIELD_ONLINE",
    "FIELD_STATE_RAW",
    "FIELD_MODE_RAW",
    "FIELD_MAINS_OK",
    "FIELD_BREAKER_RAW",
    "FIELD_P_KW",
    "FIELD_U_V",
    "FIELD_F_HZ",
    "FIELD_I_A",
    "FIELD_PF",
    "FIELD_KWH",
    "FIELD_FUEL_PCT",
    "FIELD_FUEL_L",
    "FIELD_HOURS",
    "FIELD_STARTS",
    "FIELD_COOLANT_C",
    "FIELD_OIL_BAR",
    "FIELD_BATT_V",
    "FIELD_CHARGER_V",
    "FIELD_RPM",
    "FIELD_MAINS_U_V",
    "FIELD_MAINS_F_HZ",
    "FIELD_EQUIPMENT",
    "FIELD_SERVICE_INTERVAL_H",
    "FIELD_NEXT_SERVICE_H",
    "FIELD_SERVICE_DUE",
    "FIELD_SCHEDULE_LINES",
    "FIELD_TIMER_VS_SCHEDULE",
    "FIELD_NEXT_EVENT",
]


@tagged("post_install", "-at_install")
class TestAdapterContract(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.genset = cls.env["td.genset"].create(
            {
                "name": "Контракт",
                "controller_model_id": cls.env.ref("td_genset.controller_hgm6120n").id,
                "power_kw": 12.0,
                "tank_volume_l": 145.0,
            }
        )
        cls.reading = cls.env["td.genset.reading"].create(
            {"genset_id": cls.genset.id, "relay_id": 1, "ts": fields.Datetime.now()}
        )
        cls.genset.write(
            {
                "last_reading_id": cls.reading.id,
                "link_state": "online",
                "genset_status": "9",
                "controller_mode": "auto",
                "feed_source": "genset",
                "mains_ok": False,
                "active_power": 10.0,
                "gen_uab": 400.0,
                "gen_ubc": 401.0,
                "gen_uca": 402.0,
                "current_a": 1.0,
                "current_b": 3.0,
                "current_c": 2.0,
                "oil_pressure": 350.0,
                "run_hours_total": 12.5,
            }
        )

    def test_models_and_fields(self):
        env = self.env
        for model in (
            td.GENSET_MODEL,
            td.READING_MODEL,
            td.EVENT_MODEL,
            td.FIELD_ALARMS_MODEL,
            td.SCHEDULE_MODEL,
            td.LAST_TEST_MODEL,
            td.SERVICE_REQUEST_MODEL,
        ):
            self.assertIn(model, env, model)
        for const in GENSET_FIELDS:
            value = getattr(td, const)
            for name in value if isinstance(value, tuple) else (value,):
                self.assertIn(name, env[td.GENSET_MODEL]._fields, const)
        for name in (td.FIELD_LAST_SERVICE_H, td.FIELD_LAST_SERVICE_DATE):
            self.assertIn(name, env[td.SERVICE_REQUEST_MODEL]._fields, name)
        self.assertIn("active", env[td.GENSET_MODEL]._fields)

    def test_maps_cover_selections(self):
        fields_ = self.env[td.GENSET_MODEL]._fields
        sel = lambda name: {k for k, _v in fields_[name]._description_selection(self.env)}  # noqa: E731
        self.assertEqual(sel(td.FIELD_STATE_RAW), set(td.STATE_MAP))
        self.assertEqual(sel(td.FIELD_MODE_RAW) - {"unknown"}, set(td.MODE_MAP))
        self.assertEqual(sel(td.FIELD_BREAKER_RAW), set(td.BREAKER_MAP))
        self.assertTrue(set(td.STATE_MAP.values()) <= set(range(1, 11)))

    def test_adp02_generators(self):
        self.assertIn(self.genset, td.generators(self.env))
        self.assertEqual(td.generators(self.env).ids, sorted(td.generators(self.env).ids))

    def test_adp03_snapshot(self):
        snap = td.snapshot(self.genset)
        self.assertEqual(set(snap), SNAP_KEYS)
        self.assertTrue(snap["online"])
        self.assertEqual(snap["state_raw"], "9")
        self.assertEqual(snap["u_v"], 401.0)
        self.assertEqual(snap["i_a"], 3.0)
        self.assertEqual(snap["oil_bar"], 3.5)
        self.assertEqual(snap["hours"], 12.5)
        self.assertEqual(td.STATE_MAP[snap["state_raw"]], 6)
        self.assertEqual(td.BREAKER_MAP[snap["breaker_raw"]], 2)
        self.env["td.genset.alarm"].create(
            {"genset_id": self.genset.id, "code": "high_temp_warning", "name": "Висока температура ОР", "level": "warn"}
        )
        alarms = td.snapshot(self.genset)["alarms"]
        self.assertEqual([a["severity"] for a in alarms], ["warning"])
        self.assertEqual(set(alarms[0]), {"code", "name", "severity", "since"})

    def test_adp03_no_reading(self):
        other = self.env["td.genset"].create(
            {
                "name": "Порожній",
                "power_kw": 12.0,
                "tank_volume_l": 145.0,
                "controller_model_id": self.env.ref("td_genset.controller_hgm6120n").id,
            }
        )
        snap = td.snapshot(other)
        self.assertEqual(set(snap), SNAP_KEYS)
        self.assertIsNone(snap["ts"])
        self.assertEqual(snap["alarms"], [])

    def test_adp04_events(self):
        self.env["td.genset.event"].create(
            {"genset_id": self.genset.id, "event_type": "run", "date_start": fields.Datetime.now(), "summary": "Пуск"}
        )
        events = td.events_since(self.genset)
        self.assertTrue(events)
        self.assertEqual(set(events[0]), EVENT_KEYS)
        self.assertEqual(td.events_since(self.genset, since=fields.Datetime.now()), [])

    def test_adp05_service(self):
        info = td.service_info(self.genset)
        self.assertEqual(set(info), SERVICE_KEYS)
        self.assertEqual(info["hours_now"], 12.5)

    def test_adp06_schedule(self):
        info = td.schedule_info(self.genset)
        self.assertEqual(set(info), {"enabled", "windows", "timer_vs_schedule"})
        self.assertFalse(info["enabled"])
        for day in "01234":
            self.env["td.genset.schedule"].create(
                {"genset_id": self.genset.id, "dayofweek": day, "time_start": 8.75, "time_end": 18.75}
            )
        info = td.schedule_info(self.genset)
        self.assertTrue(info["enabled"])
        self.assertEqual(info["windows"], ["Пн–Пт 08:45–18:45"])

    def test_adp07_last_test(self):
        self.assertIsNone(td.last_test(self.genset))

    def test_adp08_open_action(self):
        action = td.open_action(self.genset)
        self.assertEqual(action["res_model"], td.GENSET_MODEL)
        self.assertEqual(action["res_id"], self.genset.id)

    def test_adp11_next_event(self):  # W1: ADP-11
        self.assertEqual(td.next_event(self.genset), self.genset.next_event_text)
        self.assertTrue(td.next_event(self.genset))
        self.genset.timer_end = fields.Datetime.now() + timedelta(hours=1)
        self.assertIn("кінець таймера", td.next_event(self.genset))
        self.assertIsNone(td.next_event(self.env["td.genset"].new({})))  # порожнє значення -> None

    def test_adp09_no_fuel_rate_field(self):
        self.assertFalse(td.set_fuel_rate(self.genset, 103.8))
