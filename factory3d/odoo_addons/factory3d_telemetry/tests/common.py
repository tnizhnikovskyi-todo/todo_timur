import json
from contextlib import contextmanager
from datetime import datetime, timedelta
from unittest import mock
from zoneinfo import ZoneInfo

from odoo.tests import HttpCase, TransactionCase, new_test_user

PARAMS = {
    "read_enabled": "True",
    "write_enabled": "False",
    "keep_days": "30",
    "keep_hours_days": "400",
    "default_store_period_s": "300",
    "stale_periods": "3",
    "stale_min_s": "60",
    "bus_min_interval_s": "10",
    "realarm_cooldown_s": "3600",
    "push_max_readings": "2000",
    "push_rate_per_min": "60",
    "meter_lead_pct": "5",
}

EQUIPMENT = {  # атрибут -> (назва, f3d_code, з командою)
    "eq_comp": ("Компресорна станція", "COMPRESSOR-T", True),
    "eq_rv": ("Припливно-витяжна установка RV-05 (тест)", "RV-05-T", True),
    "eq_flc1": ("Навантажувач (резерв) (тест)", "FL-C1-T", True),
    "eq_fl2": ("Навантажувач приймання (тест)", "FL-2-T", True),
    "eq_water": ("Водомірний вузол (тест)", "WATER-T", True),
    "eq_other": ("Обладнання без команди", "OTHER-T", False),
}

MB_ADDR = {"host": "iot-sim", "port": 502}
MQTT_PARAMS = {
    "host": "mosquitto",
    "port": 1883,
    "username": "collector",
    "password_ref": "F3D_MQTT_PASSWORD",
    "client_id": "f3d-test",
    "topics": ["f3d/mobile/+/telemetry"],
}


class F3DTelemetryMixin:
    """SPEC §13.0.1. Базові фікстури (без моделей телеметрії) створює `_setup_base_fixtures`;
    колектори/джерела/сигнали — `_setup_telemetry_fixtures` (викликати з setUpClass класів, що їх потребують)."""

    T0 = datetime(2026, 10, 14, 6, 0, 0)
    KYIV = ZoneInfo("Europe/Kyiv")

    @classmethod
    def _setup_base_fixtures(cls):
        icp = cls.env["ir.config_parameter"].sudo()
        for key, val in PARAMS.items():
            icp.set_param("factory3d.telemetry." + key, val)
        cls.team_mech = cls.env["maintenance.team"].create({"name": "Служба головного механіка (тест)"})
        cls.team_default = cls.env["maintenance.team"].create({"name": "Команда за замовчуванням (тест)"})
        icp.set_param("factory3d.telemetry.default_team_id", str(cls.team_default.id))
        stages = cls.env["maintenance.stage"].search([], order="sequence, id")
        cls.stage_new = stages.filtered(lambda s: not s.done)[:1]
        cls.stage_done = stages.filtered("done")[:1]
        base = "factory3d_base."
        cls.user_plain = new_test_user(cls.env, "f3dt_plain", groups="base.group_user")
        cls.user_reader = new_test_user(cls.env, "f3dt_reader", groups="base.group_user," + base + "group_f3d_user")
        cls.user_mech = new_test_user(
            cls.env,
            "f3dt_mech",
            groups="base.group_user," + base + "group_f3d_user,maintenance.group_equipment_manager",
        )
        cls.user_manager = new_test_user(
            cls.env, "f3dt_manager", groups="base.group_user," + base + "group_f3d_manager"
        )
        cls.user_admin = new_test_user(cls.env, "f3dt_admin", groups="base.group_user," + base + "group_f3d_admin")
        for attr, (name, code, with_team) in EQUIPMENT.items():
            vals = {"name": name, "f3d_code": code}
            if with_team:
                vals["maintenance_team_id"] = cls.team_mech.id
            setattr(cls, attr, cls.env["maintenance.equipment"].create(vals))

    @classmethod
    def _setup_telemetry_fixtures(cls):
        """Колектори, джерела й сигнали (потребує моделей W1). Поля — за SPEC §2."""
        Col, Src, Sig = cls.env["f3d.collector"], cls.env["f3d.source"], cls.env["f3d.signal"]
        cls.col = Col.create({"code": "COL-T", "name": "Тестовий колектор"})
        cls.col2 = Col.create({"code": "COL-T2", "name": "Тестовий колектор 2"})
        cls.token = cls._gen_token(cls.col)
        cls.token2 = cls._gen_token(cls.col2)

        def src(code, typ, params, col=None, **kw):
            return Src.create(
                {"code": code, "name": code, "type": typ, "collector_id": (col or cls.col).id, "params": params, **kw}
            )

        cls.src_mb = src("MB-T-U70", "modbus_tcp", {**MB_ADDR, "unit": 70}, equipment_id=cls.eq_comp.id)
        cls.src_mb84 = src("MB-T-U84", "modbus_tcp", {**MB_ADDR, "unit": 84})
        cls.src_mqtt = src("MQTT-T", "mqtt", MQTT_PARAMS)
        cls.src_bac = src("BAC-T-105", "bacnet_ip", {"host": "iot-sim", "device": 105})
        cls.src_bac_ro = src("BAC-T-200", "bacnet_ip", {"host": "iot-sim", "device": 200, "read_only": True})
        cls.src_http = src("HTTP-T", "http_push", {"routes": ["lpr"], "allow_ips": ["iot-sim"]})
        cls.src_old = src("MB-T-OLD", "modbus_tcp", {**MB_ADDR, "unit": 70}, active=False)
        cls.src_other = src("MB-T2", "modbus_tcp", {**MB_ADDR, "unit": 71}, col=cls.col2)

        def sig(code, kind, unit, source, address, eq=None, **kw):
            vals = {
                "code": code,
                "name": kw.pop("name", code),
                "kind": kind,
                "unit": unit,
                "source_id": source.id if source else False,
                "address": address,
                "equipment_id": eq.id if eq else False,
                "origin": "manual",
                "store_period_s": 300,
                **kw,
            }
            return Sig.create(vals)

        cls.sig_press = sig(
            "equipment/COMPRESSOR-T/pressure_bar",
            "gauge",
            "бар",
            cls.src_mb,
            {"fc": 3, "addr": 3001, "type": "u16", "scale": 0.001},
            cls.eq_comp,
            name="Компресор: тиск",
            period_s=10,
            alarm_low_on=True,
            alarm_low=6.0,
            hysteresis=0.1,
            min_duration_s=30,
            decimals=2,
            alarm_title="{equipment}: тиск {value} бар при нормі від {threshold}",
        )
        cls.sig_hours = sig(
            "equipment/COMPRESSOR-T/hours",
            "counter",
            "год",
            cls.src_mb,
            {"fc": 3, "addr": 3019, "type": "u32"},
            cls.eq_comp,
            period_s=60,
            decimals=1,
        )
        cmap = {"0": "stopped", "1": "loaded", "2": "unloaded", "3": "fault", "4": "standby"}
        cls.sig_cstate = sig(
            "equipment/COMPRESSOR-T/state",
            "state",
            False,
            cls.src_mb,
            {"fc": 3, "addr": 3000, "type": "u16", "map": cmap},
            cls.eq_comp,
            name="Компресор",
            states_text=", ".join(cmap.values()),
            alarm_states_text="fault",
        )
        cls.sig_rv = sig(
            "ventilation/units/RV-05-T/filter_dp_pa",
            "gauge",
            "Па",
            cls.src_bac,
            {"object": "analog-input", "instance": 4, "mode": "poll"},
            cls.eq_rv,
            period_s=10,
            alarm_high_on=True,
            alarm_high=250,
            hysteresis=10,
            decimals=0,
            alarm_title="Заміна фільтрів: перепад тиску {value} Па при нормі до {threshold}",
        )
        cls.sig_valve = sig(
            "ventilation/units/RV-05-T/heating_valve",
            "gauge",
            "%",
            cls.src_bac,
            {"object": "analog-output", "instance": 1, "priority": 8},
            cls.eq_rv,
            write_enabled=False,
        )
        bat = {"topic": "f3d/mobile/FL-C1-T/telemetry"}
        cls.sig_bat = sig(
            "equipment/FL-C1-T/battery",
            "gauge",
            "%",
            cls.src_mqtt,
            {**bat, "path": "$.battery_pct"},
            cls.eq_flc1,
            period_s=5,
            warn_low_on=True,
            warn_low=25,
            alarm_low_on=True,
            alarm_low=15,
            hysteresis=0,
            decimals=1,
            alarm_title="Зарядити АКБ: заряд {value} % при нормі від {threshold}",
        )
        cls.sig_flstate = sig(
            "equipment/FL-C1-T/state",
            "state",
            False,
            cls.src_mqtt,
            {**bat, "path": "$.state", "map": {"to_charge": "busy"}},
            cls.eq_flc1,
            period_s=5,
            states_text="idle, busy, charging, offline, fault",
        )
        cls.sig_flx = sig(
            "equipment/FL-C1-T/x",
            "gauge",
            "м",
            cls.src_mqtt,
            {**bat, "path": "$.x"},
            viewer_visible=False,
            store_period_s=60,
        )
        cls.sig_fl2_hours = sig(
            "equipment/FL-2-T/hours", "counter", "год", cls.src_mqtt, {**bat, "path": "$.hours"}, cls.eq_fl2, decimals=1
        )
        cls.sig_water = sig(
            "infra/WATER-T/m3_total",
            "counter",
            "м³",
            cls.src_mb84,
            {"fc": 3, "addr": 16, "count": 2, "type": "u32", "wordorder": "little", "scale": 0.01},
            cls.eq_water,
            period_s=60,
            decimals=2,
        )
        cls.sig_flow = sig(
            "infra/WATER-T/flow_m3h",
            "gauge",
            "м³/год",
            None,
            {},
            cls.eq_water,
            derived_from_id=cls.sig_water.id,
            derive_rule="rate_h",
            period_s=60,
        )
        cls.sig_fire = sig(
            "fire/groups/FA-T/state", "state", False, cls.src_bac_ro, {"object": "life-safety-zone", "instance": 12}
        )
        cls.sig_plate = sig(
            "yard/lpr/CAM-T/plate",
            "event",
            False,
            cls.src_http,
            {
                "route": "lpr",
                "match": {"sensorProviderID": "CAM-05"},
                "path": "$.plateText",
                "ts_path": "$.capture_timestamp",
            },
        )
        cls.sig_free = sig("energy/consumers/SAW-T/p_now", "gauge", "кВт", None, {}, origin="sim_data")
        cls.set_sql(cls.sig_free, last_value=12.18, status="ok", last_ts=cls.T0 - timedelta(days=1))
        cls.sig_foreign = sig("equipment/OTHER-T/x", "gauge", False, cls.src_other, {"fc": 3, "addr": 0})
        cls.sig_old = sig("equipment/OTHER-T/old", "gauge", False, cls.src_mb, {"fc": 3, "addr": 1}, active=False)
        cls.sig_noaddr = sig("equipment/OTHER-T/noaddr", "gauge", False, cls.src_mb, {})

    @classmethod
    def _gen_token(cls, collector):
        res = collector.with_user(cls.user_admin).action_generate_token()
        return res["context"]["default_token"]

    # --- помічники ---
    def push(self, readings, collector=None, src="collector"):
        return self.env["f3d.signal"].sudo()._f3d_ingest(readings, src=src, collector=collector or self.col)

    def rd(self, sig, value=None, text=None, at=0, q="good"):
        res = {"code": sig.code, "ts": self.T0 + timedelta(seconds=at), "value": value, "text": text, "q": q}
        return {k: v for k, v in res.items() if v is not None}

    @classmethod
    def set_sql(cls, rec, **vals):
        cols = ", ".join(f"{k} = %s" for k in vals)
        cls.env.cr.execute(f"UPDATE {rec._table} SET {cols} WHERE id = %s", [*vals.values(), rec.id])
        rec.invalidate_recordset()

    def close(self, req):
        req.write({"stage_id": self.stage_done.id})

    def reopen(self, req):
        req.write({"stage_id": self.stage_new.id})

    @contextmanager
    def with_catalog_rows(self, rows):
        with mock.patch("odoo.addons.factory3d_telemetry.hooks._catalog_rows", return_value=rows):
            yield

    # --- рівень 0 (Додаток D) ---
    LEVEL0_SIGNALS = [  # (ключ, x_code, x_name, x_kind, x_unit, x_mode, x_value, x_alarm, x_threshold, x_state, eq)
        (
            "rv",
            "ventilation/units/RV-05-T/filter_dp_pa",
            "RV-05-T: перепад на фільтрі",
            "Перепад",
            "Па",
            "drift",
            320.594,
            "above",
            250.0,
            "тривога",
            "eq_rv",
        ),
        (
            "dust",
            "fire/groups/FA-T/dust",
            "FA-T: запиленість",
            "Запиленість",
            "%",
            "drift",
            89.304,
            "above",
            90.0,
            "норма",
            "eq_other",
        ),
        ("bat", "equipment/FL-T/battery", "FL-T: заряд", "Заряд", "%", "drain", 49.556, False, 0.0, "норма", None),
        (
            "hours",
            "equipment/FL-T/hours",
            "FL-T: мотогодини",
            "Мотогодини",
            "год",
            "hours",
            3222.1,
            False,
            0.0,
            "норма",
            None,
        ),
        (
            "press",
            "equipment/COMPRESSOR-T/pressure_bar",
            "Компресор: тиск",
            "Тиск",
            "бар",
            "noise",
            7.01,
            "below",
            6.0,
            "норма",
            "eq_comp",
        ),
        (
            "pnow",
            "energy/consumers/SAW-T/p_now",
            "SAW-T: потужність",
            "Потужність",
            "кВт",
            "machine",
            12.18,
            False,
            0.0,
            "норма",
            None,
        ),
        (
            "kwh",
            "energy/consumers/SAW-T/kwh_shift",
            "SAW-T: енергія за зміну",
            "Енергія",
            "кВт·год",
            "energy",
            50.5,
            False,
            0.0,
            "норма",
            None,
        ),
    ]
    LEVEL0_FIELDS = {
        "x_f3d_signal": [
            ("x_name", "char", None),
            ("x_code", "char", None),
            ("x_sequence", "integer", None),
            ("x_active", "boolean", None),
            ("x_equipment_id", "many2one", "maintenance.equipment"),
            ("x_workcenter_id", "many2one", "mrp.workcenter"),
            ("x_source_id", "many2one", "x_f3d_signal"),
            ("x_kind", "char", None),
            ("x_unit", "char", None),
            ("x_mode", "char", None),
            ("x_value", "float", None),
            ("x_nominal", "float", None),
            ("x_noise", "float", None),
            ("x_rate", "float", None),
            ("x_limit", "float", None),
            ("x_alarm", "char", None),
            ("x_threshold", "float", None),
            ("x_state", "char", None),
            ("x_charging", "boolean", None),
            ("x_seed", "integer", None),
            ("x_updated", "datetime", None),
            ("x_request_id", "many2one", "maintenance.request"),
        ],
        "x_f3d_reading": [
            ("x_name", "char", None),
            ("x_signal_id", "many2one", "x_f3d_signal"),
            ("x_equipment_id", "many2one", "maintenance.equipment"),
            ("x_value", "float", None),
            ("x_unit", "char", None),
            ("x_time", "datetime", None),
        ],
    }

    def _level0_xmlid(self, name, record):
        self.env["ir.model.data"].create(
            {"module": "factory3d_iot_sim", "name": name, "model": record._name, "res_id": record.id, "noupdate": True}
        )
        return record

    @classmethod
    def _level0_models(cls):
        env = cls.env
        for model, spec in cls.LEVEL0_FIELDS.items():
            if model in env:
                continue
            fields_ = []
            for name, ttype, rel in spec:
                vals = {"name": name, "field_description": name, "ttype": ttype, "state": "manual"}
                if rel:
                    vals["relation"] = rel
                fields_.append((0, 0, vals))
            env["ir.model"].create(
                {"name": "Рівень 0 (тест) " + model, "model": model, "state": "manual", "field_id": fields_}
            )
        if "x_f3d_signal_ids" not in env["maintenance.equipment"]._fields:
            env["ir.model.fields"].create(
                {
                    "model_id": env["ir.model"]._get_id("maintenance.equipment"),
                    "name": "x_f3d_signal_ids",
                    "field_description": "Сигнали рівня 0",
                    "ttype": "one2many",
                    "relation": "x_f3d_signal",
                    "relation_field": "x_equipment_id",
                    "state": "manual",
                }
            )

    def _level0_service(self):
        """Крон «IoT tick», меню й 7 представлень `factory3d_iot_sim.*` (створює, якщо iot_sim не встановлено)."""
        env = self.env
        ref = lambda name: env.ref("factory3d_iot_sim." + name, raise_if_not_found=False)  # noqa: E731
        cron = ref("cron_iot_sim")
        if not cron:
            cron = self._level0_xmlid(
                "cron_iot_sim",
                env["ir.cron"].create(
                    {
                        "name": "IoT tick (тест)",
                        "model_id": env["ir.model"]._get_id("x_f3d_signal"),
                        "state": "code",
                        "code": "pass",
                        "interval_number": 1,
                        "interval_type": "minutes",
                    }
                ),
            )
        cron.write({"active": True})
        menu = ref("menu_iot_root")
        if not menu:
            menu = self._level0_xmlid(
                "menu_iot_root",
                env["ir.ui.menu"].create(
                    {"name": "Імітація IoT", "parent_id": env.ref("maintenance.menu_maintenance_title").id}
                ),
            )
            self._level0_xmlid("menu_iot_signals", env["ir.ui.menu"].create({"name": "Сигнали", "parent_id": menu.id}))
        menu.write({"active": True})
        specs = {
            "view_signal_list": ("x_f3d_signal", '<list><field name="x_name"/></list>', None),
            "view_signal_form": ("x_f3d_signal", '<form><field name="x_name"/></form>', None),
            "view_signal_search": ("x_f3d_signal", '<search><field name="x_name"/></search>', None),
            "view_reading_list": ("x_f3d_reading", '<list><field name="x_name"/></list>', None),
            "view_reading_graph": (
                "x_f3d_reading",
                '<graph><field name="x_time"/><field name="x_value" type="measure"/></graph>',
                None,
            ),
            "view_reading_search": ("x_f3d_reading", '<search><field name="x_name"/></search>', None),
            "view_equipment_form_signals": (
                "maintenance.equipment",
                '<xpath expr="//notebook" position="inside"><page name="x_f3d_iot" string="IoT">'
                '<field name="x_f3d_signal_ids"/></page></xpath>',
                "maintenance.hr_equipment_view_form",
            ),
        }
        for name, (model, arch, inherit) in specs.items():
            view = ref(name)
            if not view:
                vals = {
                    "name": "f3d.level0.test." + name,
                    "model": model,
                    "arch": "<data>%s</data>" % arch if inherit else arch,
                }
                if inherit:
                    vals["inherit_id"] = env.ref(inherit).id
                view = self._level0_xmlid(name, env["ir.ui.view"].create(vals))
            view.write({"active": True})
        env["ir.config_parameter"].sudo().set_param("factory3d.iot_sim.level0_enabled", "True")

    def make_level0(self, signals=None, readings=None):
        """SPEC §13.0.1: рівень 0 — моделі `x_f3d_*`, 7 сигналів (AC-53), 30 показань + 1 з `x_time=NULL`,
        заявки A (`eq_rv`) і B (`eq_other`), крон/меню/представлення `factory3d_iot_sim.*`, параметр iot_sim."""
        env = self.env
        self._level0_models()
        Sig, Read = env["x_f3d_signal"], env["x_f3d_reading"]
        stage = self.stage_new
        req_a = env["maintenance.request"].create(
            {"name": "Заявка A (RV-05-T)", "equipment_id": self.eq_rv.id, "stage_id": stage.id}
        )
        req_b = env["maintenance.request"].create(
            {"name": "Заявка B (FA-T)", "equipment_id": self.eq_other.id, "stage_id": stage.id}
        )
        recs = {}
        for key, code, name, kind, unit, mode, value, alarm, thr, state, eq in signals or self.LEVEL0_SIGNALS:
            recs[key] = Sig.create(
                {
                    "x_code": code,
                    "x_name": name,
                    "x_sequence": len(recs) + 1,
                    "x_active": True,
                    "x_equipment_id": getattr(self, eq).id if eq else False,
                    "x_kind": kind,
                    "x_unit": unit,
                    "x_mode": mode,
                    "x_value": value,
                    "x_nominal": value,
                    "x_noise": 0.1,
                    "x_rate": 0.5,
                    "x_limit": 20.0,
                    "x_alarm": alarm,
                    "x_threshold": thr,
                    "x_state": state,
                    "x_charging": key == "bat",
                    "x_seed": 7,
                    "x_updated": self.T0,
                    "x_request_id": {"rv": req_a.id, "dust": req_b.id}.get(key, False),
                }
            )
        recs["kwh"].x_source_id = recs["pnow"]
        items = list(recs.values())
        reads = []
        for i in range(30 if readings is None else readings):
            sig = items[i % len(items)]
            reads.append(
                Read.create(
                    {
                        "x_name": sig.x_code,
                        "x_signal_id": sig.id,
                        "x_value": i + 0.5,
                        "x_unit": sig.x_unit,
                        "x_time": self.T0 + timedelta(minutes=i),
                    }
                )
            )
        null_read = Read.create({"x_name": "без часу", "x_signal_id": items[0].id, "x_value": 1.0})
        self._level0_service()
        return {"signals": recs, "readings": reads, "null_reading": null_read, "req_a": req_a, "req_b": req_b}


class F3DTelemetryCase(F3DTelemetryMixin, TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_base_fixtures()


class F3DTelemetryHttpCase(F3DTelemetryMixin, HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_base_fixtures()

    def api(self, method, path, body=None, token="default", headers=None, raw=None):
        if token == "default":
            token = getattr(self, "token", None)
        hdrs = {"Content-Type": "application/json", **(headers or {})}
        if token is not None:
            hdrs["Authorization"] = f"Bearer {token}"
        resp = self.url_open(path, data=raw if raw is not None else json.dumps(body), headers=hdrs, method=method)
        try:
            data = resp.json()
        except ValueError:
            data = None
        return resp.status_code, data, resp.headers
