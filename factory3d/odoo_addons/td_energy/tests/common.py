from odoo.tests import TransactionCase, new_test_user

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
