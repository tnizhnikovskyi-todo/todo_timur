from datetime import timedelta

from odoo import api, fields, models

AGG_WINDOW_H = 48

AGGREGATE_SQL = """
WITH agg AS (
    SELECT r.signal_id, max(r.equipment_id) AS equipment_id, date_trunc('hour', r.ts) AS hour,
           min(r.value) AS v_min, avg(r.value) AS v_avg, max(r.value) AS v_max, sum(r.value) AS v_sum,
           count(*) AS v_count,
           (array_agg(r.value ORDER BY r.ts))[1] AS v_first,
           (array_agg(r.value ORDER BY r.ts DESC))[1] AS v_last
      FROM td_reading r
     WHERE r.quality <> 'bad' AND r.ts >= %(start)s AND r.ts < %(end)s
     GROUP BY r.signal_id, date_trunc('hour', r.ts)
), ranked AS (
    SELECT a.*, s.kind,
           COALESCE(
               lag(a.v_last) OVER (PARTITION BY a.signal_id ORDER BY a.hour),
               (SELECT p.v_last FROM td_reading_hour p
                 WHERE p.signal_id = a.signal_id AND p.hour < a.hour ORDER BY p.hour DESC LIMIT 1)
           ) AS v_prev
      FROM agg a JOIN td_signal s ON s.id = a.signal_id
)
INSERT INTO td_reading_hour
       (signal_id, equipment_id, hour, v_min, v_avg, v_max, v_sum, v_count, v_first, v_last, delta)
SELECT signal_id, equipment_id, hour, v_min, v_avg, v_max, v_sum, v_count, v_first, v_last,
       COALESCE(CASE WHEN kind <> 'counter' THEN 0
                     WHEN v_prev IS NULL OR v_last < v_prev THEN v_last - v_first
                     ELSE v_last - v_prev END, 0)
  FROM ranked
ON CONFLICT (signal_id, hour) DO UPDATE SET
       equipment_id = EXCLUDED.equipment_id, v_min = EXCLUDED.v_min, v_avg = EXCLUDED.v_avg,
       v_max = EXCLUDED.v_max, v_sum = EXCLUDED.v_sum, v_count = EXCLUDED.v_count,
       v_first = EXCLUDED.v_first, v_last = EXCLUDED.v_last, delta = EXCLUDED.delta
"""


class F3dReadingHour(models.Model):
    _name = "td.reading.hour"
    _description = "Телеметрія: годинний агрегат"
    _order = "hour desc"
    _log_access = False

    signal_id = fields.Many2one("td.signal", string="Сигнал", required=True, ondelete="cascade", index=True)
    equipment_id = fields.Many2one(
        "maintenance.equipment", string="Обладнання", related="signal_id.equipment_id", store=True, index=True
    )
    hour = fields.Datetime(string="Година (UTC)", required=True)
    v_min = fields.Float(string="Мін.")
    v_avg = fields.Float(string="Серед.")
    v_max = fields.Float(string="Макс.")
    v_sum = fields.Float(string="Сума")
    v_count = fields.Integer(string="Кількість")
    v_first = fields.Float(string="Перше")
    v_last = fields.Float(string="Останнє")
    delta = fields.Float(string="Приріст")

    _f3d_reading_hour_uniq = models.Constraint("UNIQUE(signal_id, hour)", "Агрегат за цю годину вже є.")

    @api.model
    def _cron_aggregate(self):
        """R-09: годинні агрегати закритих годин; перерахунок останньої години (показання з буфера)."""
        cr = self.env.cr
        now = fields.Datetime.now()
        end = now.replace(minute=0, second=0, microsecond=0)
        cr.execute("SELECT max(hour) FROM td_reading_hour")
        last_hour = cr.fetchone()[0]
        if last_hour:
            start = last_hour - timedelta(hours=1)
        else:
            cr.execute("SELECT min(ts) FROM td_reading")
            first = cr.fetchone()[0]
            if not first:
                return 0
            start = first.replace(minute=0, second=0, microsecond=0)
        end = min(end, start + timedelta(hours=AGG_WINDOW_H))
        if start >= end:
            return 0
        cr.execute(AGGREGATE_SQL, {"start": start, "end": end})
        self.env.invalidate_all()
        return cr.rowcount
