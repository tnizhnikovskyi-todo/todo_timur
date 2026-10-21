"""База тестів моста td_chp_factory3d: користувачі й показання td_chp (ChpBase) + фікстури td_energy_control."""

from datetime import timedelta

from odoo.addons.td_chp.tests.common import IDLE, ChpBase, utc_now
from odoo.addons.td_energy_control.tests.common import TestControlCommon

__all__ = ["BridgeCase", "IDLE", "TAGS", "utc_now"]

TAGS = ("post_install", "-at_install", "f3d", "td_chp_factory3d")
RUNNING = {"ctl/state": 2, "ctl/mode": 3, "eng/rpm": 1500}  # агрегат у роботі, ручний режим (для stop/set_setpoint)


class BridgeCase(ChpBase, TestControlCommon):
    """Користувачі td_energy_control (`u_en1`, `u_en2`, `u_view`), `e_chief` і td_chp (`u_op1`, `u_user`: лише КГУ)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # `u_chief` у ChpBase — головний енергетик лише КГУ (без td_energy_control); енергетик-chief моста — `e_chief`
        cls.e_chief = cls._mk_user("br_chief", ["td_energy.group_td_energy_chief"])
        cls.e_chief2 = cls._mk_user("br_chief2", ["td_energy.group_td_energy_chief"])

    @classmethod
    def enable_write(cls, on=True, remote=True):
        """Усі стоп-крани: td_chp, td_energy_control, джерело (після злиття — `MB-U72-CHP`) і записувані сигнали."""
        icp = cls.env["ir.config_parameter"].sudo()
        flag = "True" if on else "False"
        icp.set_param("td.chp.write_enabled", flag)
        icp.set_param("td.chp.remote_switching_enabled", "True" if remote else "False")
        cls._enable_control(write=on, remote=remote)
        cls.source = cls.unit.source_id
        cls.source.sudo().write({"write_enabled": on})
        cls.Signal.sudo().search([("module", "=", "chp"), ("code", "like", "chp/ctl/")]).filtered(
            lambda s: "write" in (s.address or {})
        ).write({"write_enabled": on})

    def actions(self, *kinds):
        domain = [("kind_code", "in", list(kinds))] if kinds else [("kind_code", "like", "chp\\_%")]
        return self.Action.sudo().search(domain)

    def prepare(self, kind, params=None, user=None):
        return self.pult(user or self.u_en1).command("prepare", kind=kind, params=params)

    def confirm(self, prep, user=None):
        return self.pult(user or self.u_en1).command("confirm", ref=prep["ref"], token=prep["token"])

    def act(self, kind, params=None, user=None):
        """prepare → confirm одним користувачем; повертає запис дії."""
        prep = self.prepare(kind, params, user)
        self.confirm(prep, user)
        return self.Action.sudo().browse(prep["action_id"])

    def command_done(self, action, ack=None, reason=0, values=None):
        """Імітація колектора: `td.command` → sent → done, далі показання (`ack` або значення цілі)."""
        cmd = action.command_id
        cmd.write({"state": "sent"})
        cmd.write({"state": "done", "done_at": utc_now().replace(microsecond=0) - timedelta(seconds=1)})
        readings = dict(values or {})
        if ack is not None:
            readings.update({"ctl/ack_reason": reason, "ctl/ack": ack})
        if readings:
            self.put(readings)
