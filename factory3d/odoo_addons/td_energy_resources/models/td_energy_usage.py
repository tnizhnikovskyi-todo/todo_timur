"""M-07 `td.energy.usage` — зведення використання (FR-06): SQL-view над електричними й ресурсними інтервалами.

Семантика потоків — R-07: `import`/`export`/`generation`/`load` (електрика), `supply`/`branch` (ресурси); `consumer`,
`storage`, `metric='react'` у view не входять (A-03). Ідентифікатор рядка без `row_number()` (фільтри проштовхуються
в гілки UNION): `i.id * 4` (+1 для `export`) для електричних, `r.id * 4 + 2` для ресурсних.
"""

from odoo import fields, models, tools

COST_GROUP = "td_energy.group_td_energy_cost"

VIEW_SQL = """
CREATE VIEW td_energy_usage AS
WITH el AS (SELECT id, co2_kg_per_unit FROM td_energy_resource WHERE code = 'el' ORDER BY id LIMIT 1),
     src AS (SELECT DISTINCT resource_id FROM td_energy_point WHERE kind = 'source' AND active)
SELECT i.id * 4 AS id, el.id AS resource_id,
       CASE i.role WHEN 'incomer' THEN 'import' WHEN 'feeder' THEN 'load' ELSE 'generation' END AS flow,
       i.ts_start, i.day, i.hour_local, i.node_id, NULL::int AS point_id, i.meter_id,
       i.kwh AS qty, i.kwh AS kwh_eq,
       CASE WHEN i.role IN ('incomer', 'feeder') THEN COALESCE(i.cost, 0) ELSE 0 END AS cost,
       CASE WHEN i.role = 'incomer' THEN i.kwh * el.co2_kg_per_unit ELSE 0 END AS co2_kg,
       i.quality::varchar AS quality, i.is_backfill
  FROM td_energy_interval i CROSS JOIN el
 WHERE i.role IN ('incomer', 'feeder', 'generation')
UNION ALL
SELECT i.id * 4 + 1, el.id, 'export', i.ts_start, i.day, i.hour_local, i.node_id, NULL::int, i.meter_id,
       i.kwh_export, i.kwh_export, 0, 0, i.quality::varchar, i.is_backfill
  FROM td_energy_interval i CROSS JOIN el
 WHERE i.role = 'incomer' AND i.kwh_export > 0
UNION ALL
SELECT r.id * 4 + 2, r.resource_id,
       CASE WHEN p.kind = 'source' OR (p.kind = 'consumer' AND src.resource_id IS NULL)
            THEN 'supply' ELSE 'branch' END,
       r.ts_start, r.day, r.hour_local, NULL::int, r.point_id, r.meter_id,
       r.qty, r.kwh_eq, COALESCE(r.cost, 0),
       CASE WHEN p.kind = 'source' OR (p.kind = 'consumer' AND src.resource_id IS NULL)
            THEN r.qty * res.co2_kg_per_unit ELSE 0 END,
       r.quality::varchar, r.is_backfill
  FROM td_energy_res_interval r
  JOIN td_energy_point p ON p.id = r.point_id
  JOIN td_energy_resource res ON res.id = r.resource_id
  LEFT JOIN src ON src.resource_id = r.resource_id
 WHERE r.metric = 'main'
"""


class TdEnergyUsage(models.Model):
    _name = "td.energy.usage"
    _description = "Енергетика: зведення використання"
    _auto = False
    _order = "ts_start desc"
    _rec_name = "ts_start"

    resource_id = fields.Many2one("td.energy.resource", string="Ресурс", readonly=True)
    flow = fields.Selection(
        [
            ("import", "Імпорт"),
            ("export", "Експорт"),
            ("generation", "Генерація"),
            ("load", "Навантаження"),
            ("supply", "Надходження"),
            ("branch", "Гілка"),
        ],
        string="Потік",
        readonly=True,
    )
    ts_start = fields.Datetime(string="Початок (UTC)", readonly=True)
    day = fields.Date(string="Дата (Київ)", readonly=True)
    hour_local = fields.Integer(string="Година (Київ)", readonly=True)
    node_id = fields.Many2one("td.energy.node", string="Вузол", readonly=True)
    point_id = fields.Many2one("td.energy.point", string="Точка обліку", readonly=True)
    meter_id = fields.Many2one("td.energy.meter", string="Лічильник", readonly=True)
    qty = fields.Float(string="Кількість (од. ресурсу)", digits=(14, 3), readonly=True)
    kwh_eq = fields.Float(string="кВт·год-еквівалент", digits=(14, 3), readonly=True)
    cost = fields.Float(string="Вартість, ₴", digits=(14, 2), readonly=True, groups=COST_GROUP)
    co2_kg = fields.Float(string="CO₂, кг", digits=(14, 3), readonly=True)
    quality = fields.Char(string="Якість", readonly=True)
    is_backfill = fields.Boolean(string="Синтетичні дані", readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(VIEW_SQL)
