from datetime import datetime, timedelta

from odoo.tests import TransactionCase, new_test_user

from ..tools.tariff import to_local

PARAMS = {
    "read_enabled": "True",
    "write_enabled": "False",
    "costing_enabled": "True",
    "analytic_enabled": "True",
    "balance_tol_pct": "3",
    "balance_tol_kwh": "2.0",
    "gap_max_s": "900",
    "gap_alarm_min": "60",
    "max_wait_h": "6",
    "settle_s": "120",
    "reset_tol_kwh": "1.0",
    "keep_interval_days": "400",
    "keep_event_days": "90",
    "typical_days": "20",
    "ats_fail_start_s": "35",
    "ats_fresh_factor": "3",
    "peak_shave_kw": "600",
    "alloc_close_h": "2",
}

TAGS = ("post_install", "-at_install", "f3d", "f3d_energy")


class F3DEnergyCase(TransactionCase):
    """SPEC §13.0. W0: параметри й користувачі (групи). Синтетичну мережу, сигнали, тариф, МО додають W1…W3
    (моделі `td.energy.*` на момент W0 відсутні)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        icp = cls.env["ir.config_parameter"].sudo()
        for key, val in PARAMS.items():
            icp.set_param("td.energy." + key, val)
        cls._setup_users()

    @classmethod
    def _setup_users(cls):
        def user(login, groups):
            return new_test_user(cls.env, login=login, groups=",".join(groups))

        cls.u_master = user("en_master", ["base.group_user", "mrp.group_mrp_user"])
        cls.u_account = user("en_account", ["base.group_user", "account.group_account_readonly"])
        cls.u_energy = user("en_energy", ["base.group_user", "td_energy.group_td_energy_manager"])
        cls.u_viewer = user("en_viewer", ["base.group_user", "td_factory3d.group_td_user"])
        cls.u_admin = user("en_admin", ["base.group_user", "td_factory3d.group_td_admin"])


NOW = datetime(2026, 10, 17, 11, 20, 0)  # 14:20 Київ (макет W1): субота


class TestW1Common(F3DEnergyCase):
    """W1 (SPEC 13.0): час через контекст `f3d_now`, свіжі сигнали, інтервали, користувачі груп."""

    now = NOW

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, f3d_now=cls.now, tracking_disable=True))
        cls.Node = cls.env["td.energy.node"]
        cls.Meter = cls.env["td.energy.meter"]
        cls.Event = cls.env["td.energy.event"]
        # демо-шаблон: хук прив'язує вузли до обладнання/РЦ демо-бази — W1-тести задають прив'язки самі
        cls.env.cr.execute("UPDATE td_energy_node SET workcenter_id = NULL, equipment_id = NULL")
        cls.Node.invalidate_model(["workcenter_id", "equipment_id"])
        cls.u_view = cls._mk_user("w1_view", ["td_energy.group_td_energy_user"])
        cls.u_cost = cls._mk_user("w1_cost", ["td_energy.group_td_energy_cost"])
        cls.u_eng = cls._mk_user("w1_eng", ["td_energy.group_td_energy_manager"])
        cls.u_eng2 = cls._mk_user("w1_eng2", ["td_energy.group_td_energy_manager"])
        cls.u_chief = cls._mk_user("w1_chief", ["td_energy.group_td_energy_chief"])
        cls.u_mrp = cls._mk_user("w1_mrp", ["mrp.group_mrp_manager"])
        cls.u_stock = cls._mk_user("w1_stock", ["stock.group_stock_manager"])
        cls.u_plain = new_test_user(cls.env, login="w1_plain", groups="base.group_user")

    @classmethod
    def _mk_user(cls, login, groups):
        return new_test_user(cls.env, login=login, groups=",".join(["base.group_user"] + groups))

    # --- фікстури ---------------------------------------------------------------------------------------
    def fresh(self, code, value=None, text=None, status="ok"):
        """Свіжий сигнал: `last_value`/`last_text`/`last_ts = now`, `status` (SQL, без телеметрійного інгесту)."""
        self.env.cr.execute(
            "UPDATE td_signal SET last_value=%s, last_text=%s, last_ts=%s, status=%s, last_quality='good'"
            " WHERE code=%s",
            (value, text, self.now, status, code),
        )
        self.assertEqual(self.env.cr.rowcount, 1, code)
        self.env["td.signal"].invalidate_model()

    def stale(self, code, minutes=33):
        self.env.cr.execute(
            "UPDATE td_signal SET last_ts=%s, status='stale' WHERE code=%s",
            (self.now - timedelta(minutes=minutes), code),
        )
        self.env["td.signal"].invalidate_model()

    def clear_signals(self):
        """Усі сигнали `energy/%` і `infra/%` — «без свіжих даних»."""
        self.env.cr.execute(
            "UPDATE td_signal SET last_value=NULL, last_text=NULL, last_ts=NULL, status='unknown'"
            " WHERE code LIKE 'energy/%' OR code LIKE 'infra/%'"
        )
        self.env["td.signal"].invalidate_model()

    def interval(self, meter_code, ts_start, kwh, kwh_export=0.0, price=8.4, quality="measured"):
        meter = self.Meter.search([("code", "=", meter_code)])
        local = to_local(ts_start)
        return self.env["td.energy.interval"].create(
            {
                "meter_id": meter.id, "ts_start": ts_start, "ts_end": ts_start + timedelta(minutes=15),
                "day": local.date(), "hour_local": local.hour, "e_start": 0.0, "e_end": kwh, "kwh": kwh,
                "kwh_export": kwh_export, "kw_avg": kwh * 4, "price": price, "cost": round(kwh * price, 2),
                "quality": quality, "built_at": self.now,
            }
        )  # fmt: skip

    def typical(self, meter_code, days=3, kwh=25.0, slots=range(96)):
        """Однакові інтервали `meter_code` у `days` попередніх суботах (NOW — субота): типовий день для R-28."""
        meter = self.Meter.search([("code", "=", meter_code)])
        rows = []
        for k in range(1, days + 1):
            day0 = datetime(2026, 10, 16, 21, 0) - timedelta(days=7 * k)  # 00:00 Київ суботи
            for s in slots:
                ts = day0 + timedelta(minutes=15 * s)
                local = to_local(ts)
                rows.append(
                    {
                        "meter_id": meter.id,
                        "ts_start": ts,
                        "ts_end": ts + timedelta(minutes=15),
                        "day": local.date(),
                        "hour_local": local.hour,
                        "e_start": 0.0,
                        "e_end": kwh,
                        "kwh": kwh,
                        "kwh_export": 0.0,
                        "kw_avg": kwh * 4,
                        "price": 8.4,
                        "cost": 0.0,
                        "quality": "measured",
                        "built_at": self.now,
                    }  # fmt: skip
                )
        self.env["td.energy.interval"].create(rows)

    def fixture_grid(self):
        """Макет 14:20 (R-26/R-27): вводи, лінії, трансформатори, генерація, АВР; усі лічильники на зв'язку."""
        self.env.cr.execute("UPDATE td_energy_meter SET data_state = 'ok'")
        self.env["td.energy.meter"].invalidate_model(["data_state"])
        for code, value, text in (
            ("energy/totals/p_now", 667.0, None), ("energy/totals/cos_phi", 0.93, None),
            ("infra/totals/grid_kw", 358.0, None), ("infra/totals/export_kw", 0.0, None),
            ("infra/totals/pv_now", 309.0, None), ("infra/totals/bess_soc", 82.0, None),
            ("infra/totals/bess_kw", 0.0, None), ("infra/chp/state", 0.0, "stop"), ("infra/bess/state", 1.0, "standby"),
            ("infra/ats/position", 2.0, "pos_I"), ("energy/cells/Q1/p_now", 384.0, None),
            ("energy/cells/Q2/p_now", -26.0, None), ("energy/cells/QS/state", 0.0, "open"),
            ("energy/sections/S1/cos_phi", 0.95, None), ("energy/sections/S2/cos_phi", 0.88, None),
            ("energy/cells/PFC-2/fault_step", 3.0, None), ("energy/transformers/T1/s_kva", 500.0, None),
            ("energy/transformers/T2/s_kva", 300.0, None),
        ):  # fmt: skip
            self.fresh(code, value, text)
        for line, p, i in (("BW-1", 70, 120), ("BW-2", 124, 192), ("BW-3", 70, 88), ("BW-4", 26, 61), ("C1", 184, 280)):
            self.fresh("energy/lines/%s/p_now" % line, p)
            self.fresh("energy/lines/%s/i_now" % line, i)
            self.fresh("energy/lines/%s/cos_phi" % line, 0.91)

    def user_env(self, user):
        return self.env(user=user.id)
