from odoo import _, fields, models
from odoo.exceptions import ValidationError

P = "td.genset."


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    td_genset_read_enabled = fields.Boolean(string="Читати з td_genset", config_parameter=P + "read_enabled")
    td_genset_requests_enabled = fields.Boolean(
        string="Створювати заявки ТО з подій", config_parameter=P + "requests_enabled"
    )
    td_genset_write_enabled = fields.Boolean(
        string="Команди на генератор",
        config_parameter=P + "write_enabled",
        readonly=True,
        help="Зарезервовано: міст команд на генератор не надсилає",
    )
    td_genset_amf_master = fields.Selection(
        [("hgm", "HGM6120N веде AMF"), ("ats", "ATyS p головний")],
        string="Логіка AMF",
        config_parameter=P + "amf_master",
    )
    td_genset_offline_min = fields.Integer(string="Офлайн після, хв", config_parameter=P + "offline_min")
    td_genset_ats_position_code = fields.Char(string="Сигнал положення АВР", config_parameter=P + "ats_position_code")
    td_genset_ats_src1_code = fields.Char(string="Сигнал джерела 1 АВР", config_parameter=P + "ats_src1_code")
    td_genset_ats_src2_code = fields.Char(string="Сигнал джерела 2 АВР", config_parameter=P + "ats_src2_code")
    td_genset_ats_position_i_value = fields.Integer(
        string="Положення I (мережа): значення сигналу",
        default=2,
        config_parameter=P + "ats_position_i_value",
        help="Значення сигналу положення АВР для положення I «мережа» (Socomec ATyS p, Annexe III: 2)",
    )
    td_genset_ats_position_ii_value = fields.Integer(
        string="Положення II (генератор): значення сигналу",
        default=3,
        config_parameter=P + "ats_position_ii_value",
        help="Значення сигналу положення АВР для положення II «генератор» (Socomec ATyS p, Annexe III: 3)",
    )
    td_genset_critical_codes = fields.Char(
        string="Критичні споживачі (запасний список)", config_parameter=P + "critical_codes"
    )
    td_genset_publish_period_s = fields.Integer(string="Період публікації, с", config_parameter=P + "publish_period_s")

    def set_values(self):
        icp = self.env["ir.config_parameter"].sudo()
        for rec in self:
            if rec.td_genset_ats_position_i_value == rec.td_genset_ats_position_ii_value:
                raise ValidationError(_("Значення положень I і II АВР мають відрізнятися."))
        old_period = icp.get_param(P + "publish_period_s")
        old_offline = icp.get_param(P + "offline_min")
        super().set_values()
        period = icp.get_param(P + "publish_period_s")
        if period != old_period:
            seconds = int(period or 0)
            cron = self.env.ref("td_genset_factory3d.cron_td_genset_publish", raise_if_not_found=False)
            if cron:
                cron.sudo().write(
                    {"interval_number": max(1, seconds // 60) if seconds >= 60 else 1, "interval_type": "minutes"}
                )
        offline = icp.get_param(P + "offline_min")
        if offline != old_offline:
            offline_min = int(offline or 5)
            for link in self.env["td.genset.link"].sudo().search([]):
                signals = (
                    self.env["td.signal"].sudo().search([("code", "=like", "infra/genset/%s/%%" % link.td_code)])
                )
                signals.write({"period_s": max(60, offline_min * 20)})
