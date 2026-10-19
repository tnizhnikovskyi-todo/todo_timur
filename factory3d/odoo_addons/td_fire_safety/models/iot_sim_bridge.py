"""Міст до td_iot_sim (FR-23, A-34): без залежності від модуля, лише виклики self.env[...] за наявності."""
from odoo import models
from odoo.exceptions import AccessError, UserError


class F3dFireDrillSimBridge(models.Model):
    _inherit = "td.fire.drill"

    def _td_sim_start(self):
        self.ensure_one()
        if not self.env.su and not self.env.user.has_group("td_fire_safety.group_td_fire_drill"):
            raise AccessError("Запускати емулятор навчання можуть лише користувачі групи «Навчальні тривоги».")
        if "td.sim.run" not in self.env:
            raise UserError("Модуль емулятора не встановлено.")
        scenario = self.env["td.sim.scenario"].sudo().search([("code", "=", "fire_drill")], limit=1)
        if not scenario:
            raise UserError("У пульті емулятора немає сценарію fire_drill.")
        detector = self.device_id.address or self.zone_id.device_ids.filtered("is_detector")[:1].address
        params = {"zone": self.zone_id.code, "detector": detector, "real": False,
                  "duration_s": self._param("drill_sim_duration_s", 300)}
        return self._td_sim_create_run(scenario, params)

    def _td_sim_create_run(self, scenario, params):
        return self.env["td.sim.run"].sudo()._create_and_start(scenario, params)

    def _td_sim_stop(self):
        self.ensure_one()
        run = self.env["td.sim.run"].sudo().search([("name", "=", self.sim_run_ref)], limit=1)
        try:
            if run.state in ("queued", "running"):
                run.action_stop()
        except Exception as exc:
            self.message_post(body="Емулятор: не вдалося зупинити сценарій: %s" % exc)
