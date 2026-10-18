"""M-11: параметри двору в налаштуваннях (FR-25, SPEC §5.1)."""

from odoo import api, fields, models

from ..tools import params as P

ADMIN = "factory3d_base.group_f3d_admin"
MGR = "factory3d_yard.group_f3d_yard_manager"
POLICY = [("none", "Без зважування"), ("in_out", "На в'їзді й виїзді")]


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    f3d_yard_read_enabled = fields.Boolean(
        string="Обробляти показання й події двору", config_parameter="factory3d.yard.read_enabled", groups=ADMIN
    )
    f3d_yard_write_enabled = fields.Boolean(
        string="Дозволяти команди на шлагбауми", config_parameter="factory3d.yard.write_enabled", groups=ADMIN
    )
    f3d_yard_antipassback = fields.Boolean(
        string="Контроль проїзду без дозволу", config_parameter="factory3d.yard.antipassback", groups=MGR
    )
    f3d_yard_walk_in_allowed = fields.Boolean(
        string="Охорона створює рейси без броні", config_parameter="factory3d.yard.walk_in_allowed", groups=MGR
    )
    f3d_yard_walk_in_limit_per_day = fields.Integer(
        string="Ліміт рейсів без броні на добу", config_parameter="factory3d.yard.walk_in_limit_per_day", groups=MGR
    )
    f3d_yard_lpr_min_confidence = fields.Float(
        string="Мінімальна довіра розпізнавання", config_parameter="factory3d.yard.lpr_min_confidence", groups=MGR
    )
    f3d_yard_lpr_match_window_h = fields.Integer(
        string="Вікно пошуку рейсу за номером, год", config_parameter="factory3d.yard.lpr_match_window_h", groups=MGR
    )
    f3d_yard_lpr_store_images = fields.Boolean(
        string="Зберігати знімки номерів", config_parameter="factory3d.yard.lpr_store_images", groups=MGR
    )
    f3d_yard_lpr_image_max_kb = fields.Integer(
        string="Макс. розмір знімка, КБ", config_parameter="factory3d.yard.lpr_image_max_kb", groups=MGR
    )
    f3d_yard_lpr_keep_days = fields.Integer(
        string="Зберігати події LPR, діб", config_parameter="factory3d.yard.lpr_keep_days", groups=MGR
    )
    f3d_yard_kpp_refresh_s = fields.Integer(
        string="Оновлення екрана КПП, с", config_parameter="factory3d.yard.kpp_refresh_s", groups=MGR
    )
    f3d_yard_slot_default_min = fields.Integer(
        string="Тривалість слоту за замовчуванням, хв", config_parameter="factory3d.yard.slot_default_min", groups=MGR
    )
    f3d_yard_dock_turnaround_min = fields.Integer(
        string="Буфер між слотами, хв", config_parameter="factory3d.yard.dock_turnaround_min", groups=MGR
    )
    f3d_yard_enforce_calendar = fields.Boolean(
        string="Забороняти слоти поза зміною", config_parameter="factory3d.yard.enforce_calendar", groups=MGR
    )
    f3d_yard_early_min = fields.Integer(
        string="Авто-пропуск: раніше за слот, хв", config_parameter="factory3d.yard.early_min", groups=MGR
    )
    f3d_yard_late_min = fields.Integer(
        string="Авто-пропуск: пізніше за початок слоту, хв", config_parameter="factory3d.yard.late_min", groups=MGR
    )
    f3d_yard_auto_call_next = fields.Boolean(
        string="Викликати наступну фуру автоматично", config_parameter="factory3d.yard.auto_call_next", groups=MGR
    )
    f3d_yard_queue_slot_window_min = fields.Integer(
        string="Слот «починається» протягом, хв", config_parameter="factory3d.yard.queue_slot_window_min", groups=MGR
    )
    f3d_yard_arrival_timeout_min = fields.Integer(
        string="Незбіг LPR без рішення гасне через, хв",
        config_parameter="factory3d.yard.arrival_timeout_min",
        groups=MGR,
    )
    f3d_yard_no_show_min = fields.Integer(
        string="«Не приїхала» через, хв після початку слоту", config_parameter="factory3d.yard.no_show_min", groups=MGR
    )
    f3d_yard_dock_shift_min = fields.Integer(
        string="Робочий час воріт на добу, хв", config_parameter="factory3d.yard.dock_shift_min", groups=MGR
    )
    f3d_yard_open_timeout_s = fields.Integer(
        string="Таймаут підтвердження відкриття, с", config_parameter="factory3d.yard.open_timeout_s", groups=MGR
    )
    f3d_yard_cmd_cooldown_s = fields.Integer(
        string="Інтервал між командами, с", config_parameter="factory3d.yard.cmd_cooldown_s", groups=MGR
    )
    f3d_yard_cmd_expire_s = fields.Integer(
        string="Строк дії команди, с", config_parameter="factory3d.yard.cmd_expire_s", groups=MGR
    )
    f3d_yard_hold_max_min = fields.Integer(
        string="Макс. утримання відкритим, хв", config_parameter="factory3d.yard.hold_max_min", groups=MGR
    )
    f3d_yard_signal_max_age_s = fields.Integer(
        string="Свіжість сигналів воріт, с", config_parameter="factory3d.yard.signal_max_age_s", groups=MGR
    )
    f3d_yard_net_tolerance_pct = fields.Float(
        string="Допуск нетто, %", config_parameter="factory3d.yard.net_tolerance_pct", groups=MGR
    )
    f3d_yard_net_tolerance_kg = fields.Float(
        string="Допуск нетто, кг (мінімум)", config_parameter="factory3d.yard.net_tolerance_kg", groups=MGR
    )
    f3d_yard_weigh_max_age_s = fields.Integer(
        string="Свіжість показання ваг, с", config_parameter="factory3d.yard.weigh_max_age_s", groups=MGR
    )
    f3d_yard_scale_auto_capture = fields.Boolean(
        string="Автозахоплення зважування", config_parameter="factory3d.yard.scale_auto_capture", groups=MGR
    )
    f3d_yard_scale_dwell_s = fields.Integer(
        string="Фура «на вагах» у 3D після зважування, с", config_parameter="factory3d.yard.scale_dwell_s", groups=MGR
    )
    f3d_yard_weighing_policy_west = fields.Selection(
        POLICY, string="Зважування рейсів приймання", config_parameter="factory3d.yard.weighing_policy_west", groups=MGR
    )
    f3d_yard_weighing_policy_east = fields.Selection(
        POLICY,
        string="Зважування рейсів відвантаження",
        config_parameter="factory3d.yard.weighing_policy_east",
        groups=MGR,
    )
    f3d_yard_visit_pii_keep_days = fields.Integer(
        string="Зберігати персональні дані водіїв, діб",
        config_parameter="factory3d.yard.visit_pii_keep_days",
        groups=MGR,
    )
    f3d_yard_weighing_unassigned_keep_days = fields.Integer(
        string="Зберігати непризначені зважування, діб",
        config_parameter="factory3d.yard.weighing_unassigned_keep_days",
        groups=MGR,
    )
    f3d_yard_seed_product_weights = fields.Boolean(
        string="Заповнити маси плит із моделі (лише нульові)",
        config_parameter="factory3d.yard.seed_product_weights",
        groups=MGR,
    )
    f3d_yard_calendar_id = fields.Many2one("resource.calendar", string="Календар роботи воріт", groups=MGR)

    @api.model
    def get_values(self):
        res = super().get_values()
        res["f3d_yard_calendar_id"] = int(P.get_str(self.env, "calendar_id") or 0) or False
        return res

    def set_values(self):
        super().set_values()
        P.set_param(self.env, "calendar_id", self.f3d_yard_calendar_id.id or "")

    def action_f3d_yard_gate(self):
        return self.env["ir.actions.act_window"]._for_xml_id("factory3d_yard.action_f3d_yard_gate")

    def action_f3d_yard_run_migration(self):
        return self.env["f3d.yard.visit"].f3d_yard_run_migration()
