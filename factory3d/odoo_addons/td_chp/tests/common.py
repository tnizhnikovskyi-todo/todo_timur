"""Спільна база тестів td_chp (SPEC §13.1): користувачі user/operator/operator2/chief, показання, прапори запису."""

from datetime import datetime, timedelta, timezone

from odoo.tests import HttpCase, TransactionCase, new_test_user

from ..tools import bus

TAGS = ("post_install", "-at_install", "f3d", "td_chp")

# `chp/…` без префікса: значення, за яких виконуються всі 14 умов пуску (резерв, мережа є, дозвіл є)
IDLE = {
    "ctl/state": 0,
    "ctl/permit": 1,
    "ctl/remote": 1,
    "ctl/mode": 0,
    "ctl/ack": 0,
    "ctl/ack_reason": 0,
    "gas/p_in": 2.10,
    "safe/grid_ok": 1,
    "safe/rocof": 0,
    "safe/lel": 0.6,
    "safe/fire": 0,
    "safe/ext_state": 0,
    "safe/estop_loop": 1,
    "ht/t_ret": 58.0,
    "ht/t_sup": 88.0,
    "eng/t_jacket_out": 40.0,
    "eng/bat_v": 27.2,
    "eng/rpm": 0,
    "eng/hours": 18400.0,
    "oil/level": 66.8,
    "alarm/code": 0,
    "alarm/trip": 0,
}


def utc_now():
    """naive UTC з мікросекундами (показання мають зростати строго, а `fields.Datetime.now()` їх відкидає)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class ChpBase:
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True, mail_notrack=True))
        bus.reset()
        cls.Pult = cls.env["td.chp.pult"]
        cls.Event = cls.env["td.chp.event"]
        cls.Command = cls.env["td.chp.command"]
        cls.Rule = cls.env["td.chp.maintenance.rule"]
        cls.Signal = cls.env["td.signal"]
        cls.unit = cls.env.ref("td_chp.unit_chp")
        cls.source = cls.env.ref("td_chp.source_chp_u72")
        cls.u_user = cls._mk_user("chp_user", ["td_chp.group_td_chp_user"])
        cls.u_op1 = cls._mk_user("chp_op1", ["td_chp.group_td_chp_operator"])
        cls.u_op2 = cls._mk_user("chp_op2", ["td_chp.group_td_chp_operator"])
        cls.u_chief = cls._mk_user("chp_chief", ["td_chp.group_td_chp_chief"])
        cls.u_chief2 = cls._mk_user("chp_chief2", ["td_chp.group_td_chp_chief"])
        cls.u_mgr = cls._mk_user("chp_mgr", ["td_chp.group_td_chp_user", "td_factory3d.group_td_manager"])
        cls.u_admin = cls._mk_user("chp_admin", ["td_factory3d.group_td_admin"])
        cls.u_plain = cls._mk_user("chp_plain", [])
        cls.enable_write()

    @classmethod
    def _mk_user(cls, login, groups):
        return new_test_user(cls.env, login=login, groups=",".join(["base.group_user"] + groups))

    @classmethod
    def enable_write(cls, on=True, remote=True):
        """Усі запобіжники запису: параметри, джерело й записувані сигнали."""
        icp = cls.env["ir.config_parameter"].sudo()
        flag = "True" if on else "False"
        icp.set_param("td.telemetry.write_enabled", flag)
        icp.set_param("td.chp.write_enabled", flag)
        icp.set_param("td.chp.remote_switching_enabled", "True" if remote else "False")
        cls.source.sudo().write({"write_enabled": on})
        cls.Signal.sudo().search([("module", "=", "chp"), ("code", "like", "chp/ctl/")]).filtered(
            lambda s: "write" in (s.address or {})
        ).write({"write_enabled": on})

    @classmethod
    def put(cls, values, ts=None, env=None):
        """Прийняти показання `{код без chp/: число}` через `td.signal._td_ingest` (хуки td_chp спрацьовують)."""
        ts = ts or utc_now()
        readings = [{"code": "chp/" + k, "ts": ts, "value": float(v)} for k, v in values.items()]
        return (env or cls.env)["td.signal"]._td_ingest(readings, src="module")

    @classmethod
    def idle(cls, **over):
        cls.put({**IDLE, **over})

    def pult(self, user):
        return self.Pult.with_user(user)

    def events(self, **domain):
        return self.Event.search([("unit_id", "=", self.unit.id)] + [(k, "=", v) for k, v in domain.items()])

    def later(self, seconds):
        """Env з «поточним часом» `td_chp_now` на `seconds` попереду (для застарівання, прострочення)."""
        return self.env(
            context=dict(self.env.context, td_chp_now=utc_now().replace(microsecond=0) + timedelta(seconds=seconds))
        )

    def ack_flow(self, rec, result, reason=0):
        """Імітація колектора й контролера: `td.command` → done, далі показання `chp/ctl/ack`."""
        cmd = rec.command_id
        cmd.write({"state": "sent"})
        cmd.write({"state": "done", "done_at": utc_now().replace(microsecond=0) - timedelta(seconds=1)})
        self.put({"ctl/ack_reason": reason, "ctl/ack": result})


class ChpCase(ChpBase, TransactionCase):
    pass


class ChpHttpCase(ChpBase, HttpCase):
    pass
