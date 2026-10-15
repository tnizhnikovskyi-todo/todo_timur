"""R-25: спільні кроки майстрів керування (перевірки, запобіжники, створення `f3d.command`)."""

from datetime import timedelta

from odoo import SUPERUSER_ID, fields
from odoo.exceptions import AccessError, UserError

OPERATOR = "factory3d_bms.group_f3d_bms_operator"


def check_operator(env):
    if not env.user.has_group(OPERATOR):
        raise AccessError("Керування доступне енергетику й головному механіку (група «Будівля: оператор»).")


def _flag(env, key):
    return env["ir.config_parameter"].sudo().get_param(key, "False") in ("True", "true", "1")


def check_switches(env):
    """R-25 п. 2–3: запобіжники модуля й телеметрії."""
    if not _flag(env, "factory3d.bms.write_enabled"):
        raise UserError("Керування вимкнено: модуль «Будівля» (factory3d.bms.write_enabled).")
    if not _flag(env, "factory3d.telemetry.write_enabled"):
        raise UserError("Керування вимкнено: телеметрія (factory3d.telemetry.write_enabled).")


def check_signals(items):
    """R-25 п. 4: `items` — [(код об'єкта, сигнал)]; сигнал і джерело мають дозволяти запис."""
    bad = []
    for code, sig in items:
        sig = sig.sudo()
        if not sig or not sig.write_enabled or not sig.source_id.write_enabled:
            bad.append("%s (джерело %s)" % (code, sig.source_id.code or "—") if sig else "%s (немає сигналу)" % code)
    if bad:
        raise UserError("Запис вимкнено на: %s" % ", ".join(bad))


def send(env, specs, expires_min, note, label):
    """R-25 п. 6–8. `specs` — [(об'єкт, сигнал, value, text)]; повертає `act_window` списку команд."""
    Command = env["f3d.command"].with_user(SUPERUSER_ID)
    expires = fields.Datetime.now() + timedelta(minutes=expires_min)
    ids = []
    for obj, sig, value, text in specs:
        cmd = Command.create(
            {
                "signal_id": sig.id,
                "value": value,
                "text": text,
                "expires_at": expires,
                "origin": "bms",
                "requested_by": env.uid,
                "note": note or False,
            }
        )
        ids.append(cmd.id)
        obj.sudo().message_post(
            body="Надіслано команду: %s (%s), команда #%d" % (label, env.user.name, cmd.id),
            subtype_xmlid="mail.mt_note",
        )
    return {
        "type": "ir.actions.act_window",
        "name": "Команди",
        "res_model": "f3d.command",
        "view_mode": "list,form",
        "domain": [("id", "in", ids)],
    }
