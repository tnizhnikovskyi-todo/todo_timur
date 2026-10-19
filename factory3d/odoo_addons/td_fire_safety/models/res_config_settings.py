from odoo import api, fields, models
from odoo.exceptions import UserError

P = "td.fire_safety."


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    td_fire_read_enabled = fields.Boolean(
        string="Обробляти сигнали пожежної сигналізації",
        config_parameter=P + "read_enabled",
        groups="td_factory3d.group_td_admin",
    )
    td_fire_comm_stale_after_s = fields.Integer(
        string="Дані застарілі через, с", config_parameter=P + "comm_stale_after_s"
    )
    td_fire_comm_lost_after_s = fields.Integer(
        string="Зв'язок втрачено через, с", config_parameter=P + "comm_lost_after_s"
    )
    td_fire_dust_warn_pct = fields.Float(string="Поріг «Попередження», %", config_parameter=P + "dust_warn_pct")
    td_fire_dust_alarm_pct = fields.Float(string="Поріг «Очистити», %", config_parameter=P + "dust_alarm_pct")
    td_fire_polymer_panels = fields.Boolean(
        string="Стінові панелі з полімерним утеплювачем", config_parameter=P + "polymer_panels"
    )
    td_fire_cover_tol_m = fields.Float(string="Допуск покриття сповіщувачами, м", config_parameter=P + "cover_tol_m")
    td_fire_drill_time_limit_s = fields.Integer(
        string="Норма часу евакуації, с", config_parameter=P + "drill_time_limit_s"
    )
    td_fire_drill_auto_create = fields.Boolean(
        string="Створювати навчання за тестом приладу", config_parameter=P + "drill_auto_create"
    )
    td_fire_drill_match_window_min = fields.Integer(
        string="Вікно зіставлення з планом, хв", config_parameter=P + "drill_match_window_min"
    )
    td_fire_drill_auto_stop_s = fields.Integer(
        string="Автозавершення після тесту, с", config_parameter=P + "drill_auto_stop_s"
    )
    td_fire_drill_sim_duration_s = fields.Integer(
        string="Тривалість сценарію емулятора, с", config_parameter=P + "drill_sim_duration_s"
    )
    td_fire_alert_group_id = fields.Many2one("res.groups", string="Група сповіщення про тривогу")
    td_fire_team_id = fields.Many2one(
        "maintenance.team", string="Команда ТО пожежної безпеки", config_parameter=P + "team_id"
    )
    td_fire_viewer_devices = fields.Boolean(string="Показувати пристрої в 3D", config_parameter=P + "viewer_devices")
    td_fire_event_ack_required = fields.Boolean(
        string="Тривоги журналу потребують підтвердження", config_parameter=P + "event_ack_required"
    )

    # --- група сповіщення: xml-id, а не id --------------------------------------------------------------
    @api.model
    def get_values(self):
        res = super().get_values()
        xmlid = self.env["ir.config_parameter"].sudo().get_param(P + "alert_group_xmlid") or ""
        group = self.env.ref(xmlid, raise_if_not_found=False) if xmlid else None
        res["td_fire_alert_group_id"] = group.id if group and group._name == "res.groups" else False
        return res

    def _td_fire_validate(self):
        self.ensure_one()
        if self.td_fire_comm_stale_after_s < 30:
            raise UserError("Поріг «Дані застарілі» має бути не меншим за 30 с.")
        if self.td_fire_comm_lost_after_s <= self.td_fire_comm_stale_after_s:
            raise UserError("Поріг «Зв'язок втрачено» має бути більшим за поріг «Дані застарілі».")
        warn, alarm = self.td_fire_dust_warn_pct, self.td_fire_dust_alarm_pct
        if not (0 < warn < alarm <= 100):
            raise UserError("Поріг «Очистити» має бути більшим за поріг «Попередження» і не більшим за 100 %.")
        if not 0 <= self.td_fire_cover_tol_m <= 2:
            raise UserError("Допуск покриття має бути в межах 0…2 м.")
        if self.td_fire_drill_time_limit_s < 30:
            raise UserError("Норма часу евакуації має бути не меншою за 30 с.")
        if not 1 <= self.td_fire_drill_match_window_min <= 720:
            raise UserError("Вікно зіставлення має бути в межах 1…720 хв.")
        if self.td_fire_drill_auto_stop_s < 10:
            raise UserError("Автозавершення має бути не меншим за 10 с.")
        if not 30 <= self.td_fire_drill_sim_duration_s <= 3600:
            raise UserError("Тривалість сценарію емулятора має бути в межах 30…3600 с.")

    def set_values(self):
        icp = self.env["ir.config_parameter"].sudo()
        old = {
            key: icp.get_param(P + key)
            for key in ("read_enabled", "dust_warn_pct", "dust_alarm_pct", "polymer_panels", "cover_tol_m")
        }
        for rec in self:
            rec._td_fire_validate()
            if rec.td_fire_alert_group_id:
                ids = rec.td_fire_alert_group_id.get_external_id()
                if not ids.get(rec.td_fire_alert_group_id.id):
                    raise UserError("Оберіть групу з зовнішнім ідентифікатором.")
        super().set_values()
        for rec in self:
            group = rec.td_fire_alert_group_id
            if group:
                icp.set_param(P + "alert_group_xmlid", group.get_external_id()[group.id])
        rec = self[:1]
        if not rec:
            return
        # Boolean = False Odoo зберігає як видалення параметра, а модуль читає явні True/False (умовчання True)
        for key, fname in (
            ("read_enabled", "td_fire_read_enabled"),
            ("polymer_panels", "td_fire_polymer_panels"),
            ("drill_auto_create", "td_fire_drill_auto_create"),
            ("viewer_devices", "td_fire_viewer_devices"),
            ("event_ack_required", "td_fire_event_ack_required"),
        ):
            icp.set_param(P + key, str(bool(rec.sudo()[fname])))
        new = {key: icp.get_param(P + key) for key in old}
        if (old["dust_warn_pct"], old["dust_alarm_pct"]) != (new["dust_warn_pct"], new["dust_alarm_pct"]):
            self.env["td.signal"].sudo().with_context(active_test=False).search(
                [("module", "=", "fire_safety"), ("code", "like", "%/dust")]
            ).write(
                {
                    "warn_high": rec.td_fire_dust_warn_pct,
                    "warn_high_on": True,
                    "alarm_high": rec.td_fire_dust_alarm_pct,
                    "alarm_high_on": True,
                }
            )
        panel = self.env["td.fire.panel"].sudo()
        if (old["polymer_panels"], old["cover_tol_m"]) != (new["polymer_panels"], new["cover_tol_m"]):
            panel._schedule_compliance()
        if old["read_enabled"] != new["read_enabled"]:
            panel._td_fire_sync(full=True)
