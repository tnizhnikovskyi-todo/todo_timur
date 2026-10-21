"""Фікстури td_energy_control (SPEC 13.0): користувачі, свіжі сигнали, стан макета 14:20, прапори запису."""

from datetime import datetime, timedelta

from odoo.tests import TransactionCase, new_test_user

NOW = datetime(2026, 10, 17, 11, 20, 0)  # 14:20 Київ (макет), субота
TAGS = ("post_install", "-at_install", "f3d", "f3d_energy_control")

SNAPSHOT_1420 = {  # код сигналу → (значення, текст)
    "infra/totals/grid_kw": (356.0, None),
    "infra/totals/export_kw": (26.0, None),
    "infra/totals/pv_now": (309.0, None),
    "infra/totals/bess_soc": (82.0, None),
    "infra/bess/state": (1.0, None),
    "infra/chp/state": (0.0, None),
    "infra/ats/position": (2.0, None),
    "infra/ats/src1_ok": (1.0, None),
    "energy/cells/QS/state": (0.0, "open"),
    "energy/sections/S1/p_kw": (150.0, None),
    "energy/sections/S2/p_kw": (100.0, None),
    "energy_control/ats/parallel_lock": (1.0, None),
    "energy_control/ctl/remote": (1.0, "remote"),
    "energy_control/chp/gas_bar": (2.1, None),
    "energy_control/chp/permit": (1.0, None),
    "energy_control/air/min_consumer_bar": (6.2, None),
    "energy_control/air/setpoint_bar": (7.0, None),
    "energy_control/bess/temp_c": (24.0, None),
    "energy_control/bess/reserve_pct": (30.0, None),
}


class TestControlCommon(TransactionCase):
    """Спільна база тестів керування: час через `f3d_now`, користувачі груп, прапори запису."""

    now = NOW

    bridge_executor = False  # True — тести моста td_chp_factory3d: `chp_start`/`chp_stop` лишаються з виконавцем `chp`

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, f3d_now=cls.now, tracking_disable=True))
        if not cls.bridge_executor:  # міст КГУ (auto_install) підміняє виконавця; ядро перевіряємо з інтентом збирача
            cls.env["td.energy.command.kind"].sudo().search(
                [("code", "in", ("chp_start", "chp_stop")), ("executor", "=", "chp")]
            ).write({"executor": "intent"})
        cls.Action = cls.env["td.energy.action"]
        cls.Kind = cls.env["td.energy.command.kind"]
        cls.Scenario = cls.env["td.energy.scenario"]
        cls.Shed = cls.env["td.energy.shed.item"]
        cls.Slot = cls.env["td.energy.schedule.slot"]
        cls.Control = cls.env["td.energy.control"]
        cls.State = cls.env["td.energy.control.state"]
        cls.u_view = cls._mk_user("c_view", ["td_energy.group_td_energy_user"])
        cls.u_en1 = cls._mk_user("c_en1", ["td_energy.group_td_energy_manager"])
        cls.u_en2 = cls._mk_user("c_en2", ["td_energy.group_td_energy_manager"])
        cls.u_chief = cls._mk_user("c_chief", ["td_energy.group_td_energy_chief"])
        cls.u_chief2 = cls._mk_user("c_chief2", ["td_energy.group_td_energy_chief"])
        cls.u_admin = cls._mk_user("c_admin", ["td_factory3d.group_td_admin", "td_energy.group_td_energy_chief"])
        cls.u_plain = new_test_user(cls.env, login="c_plain", groups="base.group_user")
        cls._enable_control()
        cls._snapshot_1420()

    @classmethod
    def _mk_user(cls, login, groups):
        return new_test_user(cls.env, login=login, groups=",".join(["base.group_user"] + groups))

    @classmethod
    def _enable_control(cls, write=True, remote=True, automation=True):
        icp = cls.env["ir.config_parameter"].sudo()
        icp.set_param("td.telemetry.write_enabled", "True" if write else "False")
        icp.set_param("td.energy_control.write_enabled", "True" if write else "False")
        icp.set_param("td.energy_control.automation_enabled", "True" if automation else "False")
        icp.set_param("td.energy_control.remote_switching_enabled", "True" if remote else "False")
        src = cls.env["td.source"].sudo().search([("code", "=", "ENERGY-CTL")])
        src.write({"write_enabled": write})
        cls.env["td.signal"].sudo().search([("code", "=", "energy_control/intent")]).write({"write_enabled": write})

    @classmethod
    def _fresh(cls, code, value, text=None, age_s=0, status="ok"):
        sig = cls.env["td.signal"].sudo().search([("code", "=", code)], limit=1)
        assert sig, "немає сигналу %s" % code
        sig.write(
            {
                "last_value": value,
                "last_text": text,
                "last_ts": cls.now - timedelta(seconds=age_s),
                "status": status,
            }
        )
        return sig

    @classmethod
    def _snapshot_1420(cls):
        for code, (value, text) in SNAPSHOT_1420.items():
            cls._fresh(code, value, text)

    @classmethod
    def _collector(cls):
        col = cls.env["td.collector"].create({"code": "COL-CTL", "name": "Тестовий збирач керування"})
        res = col.with_user(cls.u_admin).action_generate_token()
        return col, res["context"]["default_token"]

    # --- дії користувача ---------------------------------------------------------------------------------------
    def ctl(self, user=None):
        return self.Control.with_user(user or self.u_en1)

    def run_action(self, kind, params=None, user=None, second=None):
        """prepare → confirm (→ confirm_second); повертає запис дії."""
        user = user or self.u_chief
        prep = self.ctl(user).prepare(kind, params)
        self.ctl(user).confirm(prep["token"])
        action = self.Action.browse(prep["action_id"])
        if second and action.state == "awaiting_second":
            self.ctl(second).confirm_second(action.id)
        return action.sudo()

    def finish(self, action, state="done", result="виконано", error=None):
        """Імітація звіту збирача (API-25 `actions[]`)."""
        item = {"id": action.id, "idem": action.idem, "state": state, "result": result, "error": error}
        return self.Action.sudo()._td_on_engine(item)
