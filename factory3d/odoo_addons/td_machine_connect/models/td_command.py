import json
import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Datetime

from ..tools import commands as cmd_tools
from .td_machine import param_bool

_logger = logging.getLogger(__name__)

TERMINAL_STATES = ("done", "failed", "expired", "cancelled")
EXPIRES_MIN = 10


class F3dCommand(models.Model):
    _inherit = "td.command"

    td_machine_id = fields.Many2one("td.machine", ondelete="set null", index=True)
    td_gantry_job_id = fields.Many2one("td.gantry.job", ondelete="set null", index=True)
    td_cut_map_id = fields.Many2one("td.cut.map", ondelete="set null", index=True)

    # --- створення команд модулем (X-93: не в tools/commands.py) -------------------------------------
    @api.model
    def _f3d_mc_payload_supported(self):
        """Чи є в telemetry поле `payload` (19.0.1.1.0, CR-01); без нього — запасна текстова граматика."""
        return "payload" in self._fields

    @api.model
    def _f3d_mc_create_command(self, signal, op, fields, links=None):
        """Створює команду на пристрій для сигналу `signal`: операція `op`, поля `fields` (R-21), зв'язки `links`."""
        if not param_bool(self.env, "write_enabled"):
            raise UserError(_("Запис на пристрої вимкнено: td.machine_connect.write_enabled."))
        address = signal.sudo().address or {}
        if address.get("call") == "job":
            kind = "job"
        elif address.get("cmd") in ("gantry", "cutopt"):
            kind = address["cmd"]
        else:
            raise UserError(_("Сигнал %s не є сигналом команд верстатів.", signal.code))
        try:
            payload = cmd_tools.build_payload(kind, op, **fields)
        except ValueError as e:
            raise UserError(_("Команда «%s» не відповідає формату: %s", op, e)) from e
        if self._f3d_mc_payload_supported():
            vals = {"payload": payload, "text": cmd_tools.cmd_label(kind, payload)}
        else:
            try:
                vals = {"text": cmd_tools.build_cmd(kind, op, **fields)}
            except ValueError as e:
                raise UserError(_("Команда «%s» не відповідає формату: %s", op, e)) from e
        # Запобіжники telemetry перевіряє R-18 у create(); тут — те саме з назвою запобіжника в тексті помилки.
        icp = self.env["ir.config_parameter"].sudo()
        if icp.get_param("td.telemetry.write_enabled", "False") not in ("True", "true", "1"):
            raise UserError(_("Запис на пристрої вимкнено: td.telemetry.write_enabled."))
        source = signal.sudo().source_id
        if source and not source.write_enabled:
            raise UserError(_("Запис на пристрої вимкнено: джерело %s.", source.code))
        if not signal.sudo().write_enabled:
            raise UserError(_("Запис на пристрої вимкнено: сигнал %s.", signal.code))
        return self.sudo().create(
            {
                "signal_id": signal.id,
                **vals,
                "origin": "machine_connect",
                "expires_at": Datetime.now() + timedelta(minutes=EXPIRES_MIN),
                **(links or {}),
            }
        )

    # --- реакція на результат ------------------------------------------------------------------------
    def write(self, vals):
        reacting = self.browse()
        if vals.get("state") in TERMINAL_STATES:
            reacting = self.filtered(lambda c: c.origin == "machine_connect" and c.state != vals["state"])
        res = super().write(vals)
        if reacting:
            reacting._f3d_mc_on_result()
        return res

    def _f3d_mc_result_text(self):
        self.ensure_one()
        if self.result_data:
            return json.dumps(self.result_data, ensure_ascii=False, sort_keys=True)
        return self.result or self.error or ""

    def _f3d_mc_on_result(self):
        """Команда завершилась (`done`/`failed`/`expired`/`cancelled`): повідомити власника (`_f3d_on_command`)."""
        for cmd in self:
            if cmd.td_gantry_job_id and hasattr(cmd.td_gantry_job_id, "_f3d_on_command"):
                cmd.td_gantry_job_id._f3d_on_command(cmd)  # R-16 п. 3
            if cmd.td_cut_map_id and hasattr(cmd.td_cut_map_id, "_f3d_on_command"):
                cmd.td_cut_map_id._f3d_on_command(cmd)  # R-20 п. 2
            if cmd.td_machine_id:
                cmd.td_machine_id.message_post(
                    body=_(
                        "Команда %s: %s %s",
                        cmd.text or "",
                        dict(cmd._fields["state"].selection).get(cmd.state, cmd.state),
                        cmd._f3d_mc_result_text() if cmd.state == "done" else (cmd.error or ""),
                    ),
                    subtype_xmlid="mail.mt_note",
                )
