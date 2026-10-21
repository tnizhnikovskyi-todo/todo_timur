"""Машинний шар `td_machine_connect` і диспетчер: причина простою ставиться одразу, а не «Потребує причини».

Коли емулятор виконує ціль диспетчера, верстат змінює стан, і `td_machine_connect` сам відкриває простій (R-05).
Диспетчер позначає верстат тим, чому він стоїть (`td_live_loss_id`: «Немає завдання», налагодження, очікування,
поломка), або що це «Поза зміною» (`td_live_off`). Хук `_td_open_downtime` підставляє причину при відкритті
простою; для «Поза зміною» простій не відкривається зовсім: поза календарем зміни це не втрата, і ₴ та OEE він не
мусить роздувати. Мітки пише лише диспетчер і лише за зміни причини (раз на пару хвилин, не щотакту), а решта
лишається штатною: межа робочого дня закриває «очікування» о кінці календаря зміни й відкриває наступного дня.
"""

from odoo import fields, models

PARAM_ENABLED = "td.live_production.enabled"


class TdMachine(models.Model):
    _inherit = "td.machine"

    td_live_loss_id = fields.Many2one(
        "mrp.workcenter.productivity.loss",
        string="Причина простою (диспетчер)",
        ondelete="set null",
        help="Яку причину отримує простій, що відкриється зараз: її виставляє диспетчер «Живого виробництва».",
    )
    td_live_off = fields.Boolean(
        string="Поза зміною (диспетчер)",
        help="Ціль диспетчера «Поза зміною»: простій у цей час не відкривається.",
    )

    def _td_live_on(self):
        return self.env["ir.config_parameter"].sudo().get_param(PARAM_ENABLED) == "True"

    def _td_open_downtime(self, kind, ts):
        """Простій за ціллю диспетчера: з причиною одразу, а поза зміною — без запису."""
        self.ensure_one()
        live = self._td_live_on()
        if live and self.td_live_off and kind in ("idle", "off"):
            return self.env["td.downtime"]
        dt = super()._td_open_downtime(kind, ts)
        loss = self.td_live_loss_id
        if live and dt and loss and kind in ("idle", "setup", "fault"):
            dt._td_apply_reason(loss, "demo")
            dt.sudo().with_context(f3d_mc_internal=True, tracking_disable=True).write({"reason_state": "confirmed"})
        return dt
