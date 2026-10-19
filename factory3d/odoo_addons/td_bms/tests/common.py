from odoo import fields
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged("post_install", "-at_install", "f3d", "f3d_bms")
class F3DBmsCase(TransactionCase):
    """Спільна база тестів будівлі: користувачі за ролями (W0). Фікстури об'єктів додають W1…W5 (SPEC §13.0)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user_reader = new_test_user(cls.env, "bms_reader", groups="base.group_user,td_factory3d.group_td_user")
        cls.user_operator = new_test_user(
            cls.env, "bms_oper", groups="base.group_user,td_bms.group_td_bms_operator"
        )
        cls.user_manager = new_test_user(cls.env, "bms_mgr", groups="base.group_user,td_factory3d.group_td_manager")
        cls.user_admin = new_test_user(cls.env, "bms_admin", groups="base.group_user,td_factory3d.group_td_admin")

    @classmethod
    def fresh_signal(cls, vals):
        """Свіжий сигнал фікстури: сигнал з таким кодом із даних модуля (W3) видаляється — `UNIQUE(code)`."""
        cls.env["td.signal"].with_context(active_test=False).search([("code", "=", vals["code"])]).unlink()
        return cls.env["td.signal"].create(vals)


class F3DBmsLightCase(F3DBmsCase):
    """Фікстури освітлення (W1): зони, норми, щити LP-1/LP-2, група з підмножини Додатка A.1 (Φ=20 500, W=126)."""

    ZONES = {  # код -> площа, м² (прямокутник 10 м × A/10)
        "Z-CUT": 609.3,
        "Z-EB": 564.5,
        "Z-FAC": 1235.0,
        "Z-SHEETS": 1200.6,
        "Z-HW": 350.5,
        "Z-RCV-7": 144.0,
        "Z-T1": 100.0,
    }
    NORMS = {
        "woodworking_machine": 500,
        "spraying": 750,
        "storage_floor": 100,
        "storage_racks": 150,
        "packing_dispatch": 300,
        "t_300": 300,
    }

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        # дані модуля (W3) вже містять норми, щити й групи — фікстури створюють свої (UNIQUE за кодом)
        for model in ("td.bms.light.group", "td.bms.light.panel", "td.bms.light.norm"):
            env[model].with_context(active_test=False).search([]).unlink()
        cls.zones = {}
        for code, area in cls.ZONES.items():
            zone = env["td.zone"].search([("td_code", "=", code)], limit=1)  # зони base могли бути встановлені
            if not zone:
                zone = env["td.zone"].create(
                    {
                        "td_code": code,
                        "name": code,
                        "zone_type": "production",
                        "polygon": [[0, 0], [round(area / 10, 2), 0], [round(area / 10, 2), 10], [0, 10]],
                    }
                )
            cls.zones[code] = zone
        cls.zone_empty = env["td.zone"].create({"td_code": "Z-T0", "name": "Z-T0", "zone_type": "production"})
        cls.norms = {
            key: env["td.bms.light.norm"].create({"key": key, "name": key, "lux": lux})
            for key, lux in cls.NORMS.items()
        }
        Panel = env["td.bms.light.panel"]
        cls.lp1 = Panel.create({"code": "LP-1", "name": "ЩО-1", "router": 1})
        cls.lp2 = Panel.create({"code": "LP-2", "name": "ЩО-2", "router": 2})
        cls.pass_hb = env.ref("td_factory3d.passport_highbay")
        cls.pass_rack = env.ref("td_factory3d.passport_highbay_rack")
        cls.next_dali = 100

    @classmethod
    def mk_group(cls, code, zone, norm, panel, n, **kw):
        cls.next_dali += 1
        vals = {
            "code": code,
            "name": "Освітлення: " + zone,
            "zone_id": cls.zones[zone].id,
            "norm_id": cls.norms[norm].id,
            "panel_id": panel.id,
            "n_fixtures": n,
            "fixture_kind": "highbay",
            "passport_id": cls.pass_hb.id,
            "level_design": 1.0,
            "control_mode": "shift",
            "dali_group": cls.next_dali,
            **kw,
        }
        return cls.env["td.bms.light.group"].create(vals)

    @classmethod
    def mk_signal(cls, code, kind="gauge"):
        return cls.fresh_signal({"code": code, "name": code, "kind": kind, "origin": "manual"})

    @classmethod
    def ingest(cls, sig, value=None, text=None):
        from datetime import timedelta

        from odoo import fields

        cls._ingest_n = getattr(cls, "_ingest_n", 0) + 1  # ts строго зростає: повтор тієї ж секунди відкидається
        ts = fields.Datetime.now() - timedelta(minutes=10) + timedelta(seconds=cls._ingest_n)
        item = {"code": sig.code, "ts": ts, "value": value, "text": text, "q": "good"}
        res = cls.env["td.signal"].sudo()._td_ingest([{k: v for k, v in item.items() if v is not None}], src="module")
        cls.env.invalidate_all()
        return res


class F3DBmsHvacMixin:
    """Фікстури W2: установки вентиляції (25 RV, AHU-1, 3 вентилятори), тепловий баланс, сигнали з живими значеннями."""

    @classmethod
    def _setup_hvac_fixtures(cls):
        Unit = cls.env["td.bms.hvac.unit"]
        Unit.with_context(active_test=False).search([]).unlink()
        cls.env["td.bms.heat.balance"].sudo().search([]).unlink()
        cls.zone_hvac = cls.env["td.zone"].create(
            {"td_code": "Z-T-HVAC", "name": "Зона вентиляції (тест)", "zone_type": "production"}
        )
        common = {"zone_id": cls.zone_hvac.id}
        cls.rv = {}
        for i in range(1, 26):
            code = "RV-%02d" % i
            cls.rv[code] = Unit.create(
                {
                    **common,
                    "code": code,
                    "name": "Дахова установка " + code,
                    "kind": "roofvent",
                    "mode_design": "AQ",
                    "airflow_nom": 8000.0,
                    "heat_nom_kw": 116.8,
                    "p_inst_kw": 8.6,
                }
            )
        cls.ahu = Unit.create(
            {
                **common,
                "code": "AHU-1",
                "name": "Припливна установка",
                "kind": "ahu",
                "mode_design": "VE",
                "airflow_nom": 20000.0,
                "p_inst_kw": 15.0,
                "t_supply_design": 21.0,
            }
        )
        cls.ef_elec = Unit.create(
            {
                **common,
                "code": "EF-ELEC",
                "name": "Витяжка електрощитової",
                "kind": "fan",
                "fan_count": 2,
                "mode_design": "thermostat",
                "required_in_work": False,
                "airflow_nom": 14120.0,
                "p_inst_kw": 0.84,
            }
        )
        cls.ef_cmp = Unit.create(
            {
                **common,
                "code": "EF-CMP",
                "name": "Витяжка компресорної",
                "kind": "fan",
                "mode_design": "thermostat",
                "required_in_work": False,
                "airflow_nom": 7060.0,
                "p_inst_kw": 0.42,
            }
        )
        cls.ef_chg = Unit.create(
            {
                **common,
                "code": "EF-CHG",
                "name": "Витяжка зарядної (Ex)",
                "kind": "exfan",
                "mode_design": "charging",
                "required_in_work": False,
                "airflow_nom": 644.0,
                "p_inst_kw": 0.178,
                "required_m3h": 158.4,
            }
        )
        cls.balance = cls.env["td.bms.heat.balance"]._td_bms_get()
        cls.balance.action_recompute()

    @classmethod
    def make_signal(cls, code, value=None, text=None, kind="gauge", status="ok", unit=""):
        sig = cls.fresh_signal({"code": code, "name": code, "kind": kind, "unit": unit, "origin": "manual"})
        sig.sudo().write(
            {"last_value": value or 0.0, "last_text": text or False, "last_ts": fields.Datetime.now(), "status": status}
        )
        return sig


class F3DBmsRulesMixin:
    """Фікстури W4: календар «Зміна 1», параметри перевірок, обладнання, сигнали й керування часом (freezegun)."""

    @classmethod
    def _setup_rules(cls):
        env = cls.env
        cls.derived = env["td.source"].search([("code", "=", "BMS-DERIVED")], limit=1)
        if not cls.derived:
            cls.derived = env["td.source"].create(
                {"code": "BMS-DERIVED", "name": "Будівля: обчислені", "type": "f3d_bms", "module": "bms"}
            )
        cls.cal = env["resource.calendar"].create(
            {
                "name": "Зміна 1 (тест)",
                "tz": "Europe/Kyiv",
                "attendance_ids": [
                    (0, 0, {"name": "%s %s" % (d, p), "dayofweek": d, "hour_from": a, "hour_to": b, "day_period": p})
                    for d in "01234"
                    for a, b, p in ((7.0, 11.5, "morning"), (12.0, 15.5, "afternoon"))
                ],
            }
        )
        icp = env["ir.config_parameter"].sudo()
        for key, value in {
            "read_enabled": "True",
            "calendar_id": str(cls.cal.id),
            "light_check_delay_min": "10",
            "light_norm_tolerance_pct": "5",
            "hvac_check_delay_min": "10",
            "cold_delay_min": "30",
            "indoor_min_work_c": "16.0",
            "indoor_min_off_c": "10.0",
            "heat_deficit_kw": "20",
            "heat_deficit_delay_min": "30",
            "check_heartbeat_min": "10",
        }.items():
            icp.set_param("td.bms." + key, value)

    @classmethod
    def eq(cls, code):
        """Обладнання за назвою (створюється, якщо немає); перевірка — без кешу: тести відкочують транзакції."""
        Equipment = cls.env["maintenance.equipment"]
        return Equipment.search([("name", "=", code)], limit=1) or Equipment.create({"name": code})

    @classmethod
    def define(cls, code, equipment=None, **vals):
        """Сигнал модуля «Будівля»: `…/check` — стан на BMS-DERIVED з алертами за станами."""
        data = {"code": code, "name": code, "kind": "gauge", "origin": "module", "module": "bms"}
        if equipment:
            data["equipment_id"] = cls.eq(equipment).id
        if code.endswith("/check"):
            data.update(kind="state", source_id=cls.derived.id, alarm_title="{equipment}: {text}")
        data.update(vals)
        return cls.fresh_signal(data)

    @classmethod
    def push(cls, code, ts, value=None, text=None):
        item = {"code": code, "ts": ts, "q": "good"}
        if value is not None:
            item["value"] = value
        if text is not None:
            item["text"] = text
        res = cls.env["td.signal"].sudo()._td_ingest([item], src="module")
        cls.env.invalidate_all()
        return res

    @classmethod
    def run_check(cls):
        cls.env["td.bms.check"]._cron_check()
        cls.env.invalidate_all()

    @classmethod
    def requests(cls, sig):
        return cls.env["maintenance.request"].search([("td_signal_id", "=", sig.id)])
