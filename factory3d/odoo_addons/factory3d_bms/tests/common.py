from odoo import fields
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged("post_install", "-at_install", "f3d", "f3d_bms")
class F3DBmsCase(TransactionCase):
    """Спільна база тестів будівлі: користувачі за ролями (W0). Фікстури об'єктів додають W1…W5 (SPEC §13.0)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user_reader = new_test_user(cls.env, "bms_reader", groups="base.group_user,factory3d_base.group_f3d_user")
        cls.user_operator = new_test_user(
            cls.env, "bms_oper", groups="base.group_user,factory3d_bms.group_f3d_bms_operator"
        )
        cls.user_manager = new_test_user(cls.env, "bms_mgr", groups="base.group_user,factory3d_base.group_f3d_manager")
        cls.user_admin = new_test_user(cls.env, "bms_admin", groups="base.group_user,factory3d_base.group_f3d_admin")


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
        cls.zones = {}
        for code, area in cls.ZONES.items():
            zone = env["f3d.zone"].search([("f3d_code", "=", code)], limit=1)  # зони base могли бути встановлені
            if not zone:
                zone = env["f3d.zone"].create(
                    {
                        "f3d_code": code,
                        "name": code,
                        "zone_type": "production",
                        "polygon": [[0, 0], [round(area / 10, 2), 0], [round(area / 10, 2), 10], [0, 10]],
                    }
                )
            cls.zones[code] = zone
        cls.zone_empty = env["f3d.zone"].create({"f3d_code": "Z-T0", "name": "Z-T0", "zone_type": "production"})
        cls.norms = {
            key: env["f3d.bms.light.norm"].create({"key": key, "name": key, "lux": lux})
            for key, lux in cls.NORMS.items()
        }
        Panel = env["f3d.bms.light.panel"]
        cls.lp1 = Panel.create({"code": "LP-1", "name": "ЩО-1", "router": 1})
        cls.lp2 = Panel.create({"code": "LP-2", "name": "ЩО-2", "router": 2})
        cls.pass_hb = env.ref("factory3d_base.passport_highbay")
        cls.pass_rack = env.ref("factory3d_base.passport_highbay_rack")
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
        return cls.env["f3d.bms.light.group"].create(vals)

    @classmethod
    def mk_signal(cls, code, kind="gauge"):
        return cls.env["f3d.signal"].create({"code": code, "name": code, "kind": kind, "origin": "manual"})

    @classmethod
    def ingest(cls, sig, value=None, text=None):
        from datetime import timedelta

        from odoo import fields

        cls._ingest_n = getattr(cls, "_ingest_n", 0) + 1  # ts строго зростає: повтор тієї ж секунди відкидається
        ts = fields.Datetime.now() - timedelta(minutes=10) + timedelta(seconds=cls._ingest_n)
        item = {"code": sig.code, "ts": ts, "value": value, "text": text, "q": "good"}
        res = cls.env["f3d.signal"].sudo()._f3d_ingest([{k: v for k, v in item.items() if v is not None}], src="module")
        cls.env.invalidate_all()
        return res


class F3DBmsHvacMixin:
    """Фікстури W2: установки вентиляції (25 RV + AHU-1 + 3 вентилятори), тепловий баланс, сигнали з живими значеннями."""

    @classmethod
    def _setup_hvac_fixtures(cls):
        Unit = cls.env["f3d.bms.hvac.unit"]
        Unit.with_context(active_test=False).search([]).unlink()
        cls.env["f3d.bms.heat.balance"].sudo().search([]).unlink()
        cls.zone_hvac = cls.env["f3d.zone"].create(
            {"f3d_code": "Z-T-HVAC", "name": "Зона вентиляції (тест)", "zone_type": "production"}
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
        cls.balance = cls.env["f3d.bms.heat.balance"]._f3d_bms_get()
        cls.balance.action_recompute()

    @classmethod
    def make_signal(cls, code, value=None, text=None, kind="gauge", status="ok", unit=""):
        sig = cls.env["f3d.signal"].create({"code": code, "name": code, "kind": kind, "unit": unit, "origin": "manual"})
        sig.sudo().write(
            {"last_value": value or 0.0, "last_text": text or False, "last_ts": fields.Datetime.now(), "status": status}
        )
        return sig
