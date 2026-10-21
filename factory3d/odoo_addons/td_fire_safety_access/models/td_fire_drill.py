"""R-16b: зняття блокувань після навчання — двері, які каскад тривоги розблокував і поставив у «пожежну тривогу»."""

from datetime import timedelta

from odoo import fields, models

LEAD = timedelta(seconds=60)


class F3dFireDrillAccessBridge(models.Model):
    _inherit = "td.fire.drill"

    def _td_release_locks(self):
        """Двері СКУД, змінені під час навчання: `unlocked`/`open` -> `locked`, пожежна тривога дверей знімається.

        Справжня тривога під час навчання (`real_alarm`) не знімається: її підтверджує охорона (access R-10).
        Ідемпотентно; повертає кількість дверей, у яких щось змінилось.
        """
        released = super()._td_release_locks()
        self.ensure_one()
        if "td.access.door" not in self.env or not self.start_ts:
            return released
        Door = self.env["td.access.door"].sudo()
        now = fields.Datetime.now()
        since = self.start_ts - LEAD
        changed = Door.browse()
        for door in Door.search(["|", ("state", "in", ("unlocked", "open")), ("alarm", "=", True)]):
            vals = {}
            if door.state in ("unlocked", "open") and door.state_ts and door.state_ts >= since:
                vals.update(state="locked", state_ts=max(now, door.state_ts))
            if door.alarm and door.alarm_reason == "fire" and not self.real_alarm:
                vals.update(alarm=False, alarm_reason=False)
            if vals:
                door.write(vals)
                changed |= door
        if changed:
            changed._td_publish_change()
        return released + len(changed)
