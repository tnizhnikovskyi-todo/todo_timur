from odoo import fields
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
                {**common, "code": code, "name": "Дахова установка " + code, "kind": "roofvent", "mode_design": "AQ",
                 "airflow_nom": 8000.0, "heat_nom_kw": 116.8, "p_inst_kw": 8.6}
            )
        cls.ahu = Unit.create(
            {**common, "code": "AHU-1", "name": "Припливна установка", "kind": "ahu", "mode_design": "VE",
             "airflow_nom": 20000.0, "p_inst_kw": 15.0, "t_supply_design": 21.0}
        )
        cls.ef_elec = Unit.create(
            {**common, "code": "EF-ELEC", "name": "Витяжка електрощитової", "kind": "fan", "fan_count": 2,
             "mode_design": "thermostat", "required_in_work": False, "airflow_nom": 14120.0, "p_inst_kw": 0.84}
        )
        cls.ef_cmp = Unit.create(
            {**common, "code": "EF-CMP", "name": "Витяжка компресорної", "kind": "fan", "mode_design": "thermostat",
             "required_in_work": False, "airflow_nom": 7060.0, "p_inst_kw": 0.42}
        )
        cls.ef_chg = Unit.create(
            {**common, "code": "EF-CHG", "name": "Витяжка зарядної (Ex)", "kind": "exfan", "mode_design": "charging",
             "required_in_work": False, "airflow_nom": 644.0, "p_inst_kw": 0.178, "required_m3h": 158.4}
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
