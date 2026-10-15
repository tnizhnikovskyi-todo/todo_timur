from odoo.tests import TransactionCase, new_test_user, tagged


@tagged("post_install", "-at_install", "f3d", "f3d_bms")
class F3DBmsCase(TransactionCase):
    """Спільна база тестів будівлі: користувачі за ролями (W0). Фікстури об'єктів додають W1…W5 (SPEC §13.0)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user_reader = new_test_user(cls.env, "bms_reader", groups="base.group_user,factory3d_base.group_f3d_user")
        cls.user_operator = new_test_user(cls.env, "bms_oper", groups="base.group_user,factory3d_bms.group_f3d_bms_operator")
        cls.user_manager = new_test_user(cls.env, "bms_mgr", groups="base.group_user,factory3d_base.group_f3d_manager")
        cls.user_admin = new_test_user(cls.env, "bms_admin", groups="base.group_user,factory3d_base.group_f3d_admin")


class F3DBmsLightCase(F3DBmsCase):
    """Фікстури освітлення (W1): зони, норми, щити LP-1/LP-2, група з підмножини Додатка A.1 (Φ=20 500, W=126)."""

    ZONES = {  # код -> площа, м² (прямокутник 10 м × A/10)
        "Z-CUT": 609.3, "Z-EB": 564.5, "Z-FAC": 1235.0, "Z-SHEETS": 1200.6, "Z-HW": 350.5,
        "Z-RCV-7": 144.0, "Z-T1": 100.0,
    }
    NORMS = {
        "woodworking_machine": 500, "spraying": 750, "storage_floor": 100, "storage_racks": 150,
        "packing_dispatch": 300, "t_300": 300,
    }

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.zones = {}
        for code, area in cls.ZONES.items():
            zone = env["f3d.zone"].search([("f3d_code", "=", code)], limit=1)  # зони base могли бути встановлені
            if not zone:
                zone = env["f3d.zone"].create({
                    "f3d_code": code, "name": code, "zone_type": "production",
                    "polygon": [[0, 0], [round(area / 10, 2), 0], [round(area / 10, 2), 10], [0, 10]],
                })
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
            "code": code, "name": "Освітлення: " + zone, "zone_id": cls.zones[zone].id, "norm_id": cls.norms[norm].id,
            "panel_id": panel.id, "n_fixtures": n, "fixture_kind": "highbay", "passport_id": cls.pass_hb.id,
            "level_design": 1.0, "control_mode": "shift", "dali_group": cls.next_dali, **kw,
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
