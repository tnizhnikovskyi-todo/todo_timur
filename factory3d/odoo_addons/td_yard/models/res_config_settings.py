"""M-11: параметри двору в налаштуваннях (FR-25, SPEC §5.1)."""

from odoo import api, fields, models

from ..tools import params as P

ADMIN = "td_factory3d.group_td_admin"
MGR = "td_yard.group_td_yard_manager"
POLICY = [("none", "Без зважування"), ("in_out", "На в'їзді й виїзді")]


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    td_yard_read_enabled = fields.Boolean(
        string="Обробляти показання й події двору", config_parameter="td.yard.read_enabled", groups=ADMIN
    )
    td_yard_write_enabled = fields.Boolean(
        string="Дозволяти команди на шлагбауми", config_parameter="td.yard.write_enabled", groups=ADMIN
    )
    td_yard_antipassback = fields.Boolean(
        string="Контроль проїзду без дозволу", config_parameter="td.yard.antipassback", groups=MGR
    )
    td_yard_walk_in_allowed = fields.Boolean(
        string="Охорона створює рейси без броні", config_parameter="td.yard.walk_in_allowed", groups=MGR
    )
    td_yard_walk_in_limit_per_day = fields.Integer(
        string="Ліміт рейсів без броні на добу", config_parameter="td.yard.walk_in_limit_per_day", groups=MGR
    )
    td_yard_lpr_min_confidence = fields.Float(
        string="Мінімальна довіра розпізнавання", config_parameter="td.yard.lpr_min_confidence", groups=MGR
    )
    td_yard_lpr_match_window_h = fields.Integer(
        string="Вікно пошуку рейсу за номером, год", config_parameter="td.yard.lpr_match_window_h", groups=MGR
    )
    td_yard_lpr_store_images = fields.Boolean(
        string="Зберігати знімки номерів", config_parameter="td.yard.lpr_store_images", groups=MGR
    )
    td_yard_lpr_image_max_kb = fields.Integer(
        string="Макс. розмір знімка, КБ", config_parameter="td.yard.lpr_image_max_kb", groups=MGR
    )
    td_yard_lpr_keep_days = fields.Integer(
        string="Зберігати події LPR, діб", config_parameter="td.yard.lpr_keep_days", groups=MGR
    )
    td_yard_kpp_refresh_s = fields.Integer(
        string="Оновлення екрана КПП, с", config_parameter="td.yard.kpp_refresh_s", groups=MGR
    )
    td_yard_slot_default_min = fields.Integer(
        string="Тривалість слоту за замовчуванням, хв", config_parameter="td.yard.slot_default_min", groups=MGR
    )
    td_yard_dock_turnaround_min = fields.Integer(
        string="Буфер між слотами, хв", config_parameter="td.yard.dock_turnaround_min", groups=MGR
    )
    td_yard_enforce_calendar = fields.Boolean(
        string="Забороняти слоти поза зміною", config_parameter="td.yard.enforce_calendar", groups=MGR
    )
    td_yard_early_min = fields.Integer(
        string="Авто-пропуск: раніше за слот, хв", config_parameter="td.yard.early_min", groups=MGR
    )
    td_yard_late_min = fields.Integer(
        string="Авто-пропуск: пізніше за початок слоту, хв", config_parameter="td.yard.late_min", groups=MGR
    )
    td_yard_auto_call_next = fields.Boolean(
        string="Викликати наступну фуру автоматично", config_parameter="td.yard.auto_call_next", groups=MGR
    )
    td_yard_queue_slot_window_min = fields.Integer(
        string="Слот «починається» протягом, хв", config_parameter="td.yard.queue_slot_window_min", groups=MGR
    )
    td_yard_arrival_timeout_min = fields.Integer(
        string="Незбіг LPR без рішення гасне через, хв",
        config_parameter="td.yard.arrival_timeout_min",
        groups=MGR,
    )
    td_yard_no_show_min = fields.Integer(
        string="«Не приїхала» через, хв після початку слоту", config_parameter="td.yard.no_show_min", groups=MGR
    )
    td_yard_dock_shift_min = fields.Integer(
        string="Робочий час воріт на добу, хв", config_parameter="td.yard.dock_shift_min", groups=MGR
    )
    td_yard_open_timeout_s = fields.Integer(
        string="Таймаут підтвердження відкриття, с", config_parameter="td.yard.open_timeout_s", groups=MGR
    )
    td_yard_cmd_cooldown_s = fields.Integer(
        string="Інтервал між командами, с", config_parameter="td.yard.cmd_cooldown_s", groups=MGR
    )
    td_yard_cmd_expire_s = fields.Integer(
        string="Строк дії команди, с", config_parameter="td.yard.cmd_expire_s", groups=MGR
    )
    td_yard_hold_max_min = fields.Integer(
        string="Макс. утримання відкритим, хв", config_parameter="td.yard.hold_max_min", groups=MGR
    )
    td_yard_signal_max_age_s = fields.Integer(
        string="Свіжість сигналів воріт, с", config_parameter="td.yard.signal_max_age_s", groups=MGR
    )
    td_yard_net_tolerance_pct = fields.Float(
        string="Допуск нетто, %", config_parameter="td.yard.net_tolerance_pct", groups=MGR
    )
    td_yard_net_tolerance_kg = fields.Float(
        string="Допуск нетто, кг (мінімум)", config_parameter="td.yard.net_tolerance_kg", groups=MGR
    )
    td_yard_weigh_max_age_s = fields.Integer(
        string="Свіжість показання ваг, с", config_parameter="td.yard.weigh_max_age_s", groups=MGR
    )
    td_yard_scale_auto_capture = fields.Boolean(
        string="Автозахоплення зважування", config_parameter="td.yard.scale_auto_capture", groups=MGR
    )
    td_yard_scale_dwell_s = fields.Integer(
        string="Фура «на вагах» у 3D після зважування, с", config_parameter="td.yard.scale_dwell_s", groups=MGR
    )
    td_yard_weighing_policy_west = fields.Selection(
        POLICY, string="Зважування рейсів приймання", config_parameter="td.yard.weighing_policy_west", groups=MGR
    )
    td_yard_weighing_policy_east = fields.Selection(
        POLICY,
        string="Зважування рейсів відвантаження",
        config_parameter="td.yard.weighing_policy_east",
        groups=MGR,
    )
    td_yard_visit_pii_keep_days = fields.Integer(
        string="Зберігати персональні дані водіїв, діб",
        config_parameter="td.yard.visit_pii_keep_days",
        groups=MGR,
    )
    td_yard_weighing_unassigned_keep_days = fields.Integer(
        string="Зберігати непризначені зважування, діб",
        config_parameter="td.yard.weighing_unassigned_keep_days",
        groups=MGR,
    )
    td_yard_seed_product_weights = fields.Boolean(
        string="Заповнити маси плит із моделі (лише нульові)",
        config_parameter="td.yard.seed_product_weights",
        groups=MGR,
    )
    td_yard_calendar_id = fields.Many2one("resource.calendar", string="Календар роботи воріт", groups=MGR)

    @api.model
    def get_values(self):
        res = super().get_values()
        res["td_yard_calendar_id"] = int(P.get_str(self.env, "calendar_id") or 0) or False
        return res

    def set_values(self):
        super().set_values()
        P.set_param(self.env, "calendar_id", self.td_yard_calendar_id.id or "")

    def action_td_yard_gate(self):
        return self.env["ir.actions.act_window"]._for_xml_id("td_yard.action_td_yard_gate")

    def action_td_yard_run_migration(self):
        return self.env["td.yard.visit"].f3d_yard_run_migration()
