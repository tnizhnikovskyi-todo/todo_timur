import logging
from datetime import timedelta

import pytz

from odoo import fields, models

from ..tools import params as P
from ..tools.dates import local_date, schedule_end_utc

_logger = logging.getLogger(__name__)

SCOPE = 'td_access.group_td_access_security,hr_attendance.group_hr_attendance_user'


class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    in_mode = fields.Selection(selection_add=[('biostar', 'СКУД BioStar 2')], ondelete={'biostar': 'set default'})
    out_mode = fields.Selection(selection_add=[('biostar', 'СКУД BioStar 2')], ondelete={'biostar': 'set default'})
    td_in_event_id = fields.Many2one('td.access.event', string='Подія входу', readonly=True,
                                      ondelete='set null', groups=SCOPE)
    td_out_event_id = fields.Many2one('td.access.event', string='Подія виходу', readonly=True,
                                       ondelete='set null', groups=SCOPE)
    td_in_device_id = fields.Many2one('td.access.device', string='Пристрій входу', readonly=True,
                                       ondelete='set null', groups=SCOPE)
    td_out_device_id = fields.Many2one('td.access.device', string='Пристрій виходу', readonly=True,
                                        ondelete='set null', groups=SCOPE)
    td_closed_by_rule = fields.Boolean(string='Закрито правилом (без виходу)', readonly=True, default=False,
                                        index=True)

    def _f3d_rule_end(self):
        """R-07 кроки 1–4: (час виходу, пояснення) для відкритої відмітки."""
        self.ensure_one()
        emp = self.employee_id.sudo()
        tz = emp._get_tz()
        day = local_date(self.check_in, tz)
        cal = emp.resource_calendar_id
        lines = cal.attendance_ids.filtered(
            lambda ln: ln.dayofweek == str(day.weekday()) and ln.display_type != 'line_section'
            and ln.day_period != 'lunch')
        if cal.two_weeks_calendar:
            week = str(self.env['resource.calendar.attendance'].get_week_type(day))
            lines = lines.filtered(lambda ln: ln.week_type == week)
        if lines:
            hour_to = max(lines.mapped('hour_to'))
            end = schedule_end_utc(day, hour_to, tz)
            if end > self.check_in:
                local_end = pytz.utc.localize(end).astimezone(pytz.timezone(tz))
                return end, 'кінець графіка %s' % local_end.strftime('%H:%M')
        fallback = P.get_int(self.env, 'stale_close_fallback_min', 60, 1, 1440)
        return self.check_in + timedelta(minutes=fallback), 'вхід + %s хв' % fallback

    def _f3d_close_by_rule(self):
        """R-07: закрити відкриті відмітки без виходу; оновити присутність (крок 6)."""
        for att in self.sudo():
            if att.check_out:
                continue
            check_out, why = att._f3d_rule_end()
            att.write({'check_out': check_out, 'out_mode': 'technical', 'td_closed_by_rule': True})
            att.message_post(body="Закрито правилом СКУД: немає проходу на вихід; вихід = %s." % why)
            emp = att.employee_id
            if emp.td_access_present and (not emp.td_access_last_in or emp.td_access_last_in <= check_out):
                emp._f3d_access_set({'td_access_present': False, 'td_access_zone_id': False,
                                     'td_access_zone_since': False, 'td_access_zone_door_id': False})
        return True


