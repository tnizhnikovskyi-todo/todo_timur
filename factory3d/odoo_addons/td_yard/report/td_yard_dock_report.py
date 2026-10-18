"""M-15 td.yard.dock.report: SQL-вид зайнятості воріт (R-19 п. 4)."""

from odoo import fields, models, tools


class F3dYardDockReport(models.Model):
    _name = "td.yard.dock.report"
    _description = "Двір: зайнятість воріт"
    _auto = False
    _order = "day desc, dock_id"
    _rec_name = "dock_id"

    day = fields.Date(string="День", readonly=True)
    dock_id = fields.Many2one("stock.location", string="Ворота", readonly=True)
    side = fields.Selection([("west", "Захід"), ("east", "Схід")], string="Сторона", readonly=True)
    company_id = fields.Many2one("res.company", string="Компанія", readonly=True)
    visit_count = fields.Integer(string="Рейсів", readonly=True)
    busy_min = fields.Float(string="Зайнято, хв", digits=(10, 1), readonly=True)
    idle_min = fields.Float(string="Простій, хв", digits=(10, 1), readonly=True)
    occupancy_pct = fields.Float(string="Зайнятість, %", digits=(6, 1), readonly=True, aggregator="avg")
    avg_dock_min = fields.Float(string="Середня операція, хв", digits=(10, 1), readonly=True, aggregator="avg")

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(
            """
            CREATE OR REPLACE VIEW td_yard_dock_report AS (
              WITH p AS (
                SELECT COALESCE((SELECT NULLIF(value, '')::numeric FROM ir_config_parameter
                                 WHERE key = 'td.yard.dock_shift_min'), 480) AS shift_min),
              v AS (
                SELECT v.dock_id, v.company_id,
                       (v.at_dock_at AT TIME ZONE 'UTC' AT TIME ZONE 'Europe/Kyiv')::date AS day,
                       EXTRACT(EPOCH FROM (COALESCE(v.handling_end_at, v.weighed_out_at, v.left_at)
                                           - v.at_dock_at)) / 60.0 AS busy
                FROM td_yard_visit v
                WHERE v.dock_id IS NOT NULL AND v.at_dock_at IS NOT NULL
                  AND COALESCE(v.handling_end_at, v.weighed_out_at, v.left_at) IS NOT NULL)
              SELECT row_number() OVER (ORDER BY v.day, v.dock_id) AS id, v.day, v.dock_id,
                     l.td_side AS side, v.company_id,
                     count(*) AS visit_count, round(sum(v.busy)::numeric, 1) AS busy_min,
                     round(GREATEST(p.shift_min - sum(v.busy), 0)::numeric, 1) AS idle_min,
                     round((sum(v.busy) / NULLIF(p.shift_min, 0) * 100)::numeric, 1) AS occupancy_pct,
                     round((sum(v.busy) / count(*))::numeric, 1) AS avg_dock_min
              FROM v JOIN stock_location l ON l.id = v.dock_id CROSS JOIN p
              GROUP BY v.day, v.dock_id, l.td_side, v.company_id, p.shift_min)
            """
        )
