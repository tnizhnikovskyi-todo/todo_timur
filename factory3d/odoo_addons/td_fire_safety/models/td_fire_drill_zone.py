"""M-11g: підсумок навчальної тривоги по зонах — запит над людьми навчання (`_table_query`, R-16d)."""

from odoo import fields, models


class F3dFireDrillZone(models.Model):
    _name = "td.fire.drill.zone"
    _description = "Навчальна тривога: підсумок по зоні"
    _auto = False
    _order = "drill_id, evac_time_s desc, zone_id"
    # поля, від яких залежить представлення: ORM скидає їх у БД перед читанням `td.fire.drill.zone`
    _depends = {
        "td.fire.drill": ["time_limit_s"],
        "td.fire.drill.person": [
            "drill_id",
            "zone_id",
            "status",
            "wrong_exit",
            "exit_s",
            "exit_ts",
            "assigned_exit_id",
            "exit_id",
        ],
        "td.fire.exit": ["code"],
    }

    drill_id = fields.Many2one("td.fire.drill", string="Навчання", readonly=True)
    zone_id = fields.Many2one("td.zone", string="Зона", readonly=True)
    people = fields.Integer(string="Було", readonly=True)
    evacuated = fields.Integer(string="Вийшли", readonly=True)
    present = fields.Integer(string="Є на перекличці", readonly=True)
    missing = fields.Integer(string="Не відмітились", readonly=True)
    wrong_exit = fields.Integer(string="Не своїм виходом", readonly=True)
    first_exit_s = fields.Integer(string="Перший вихід, с", readonly=True)
    evac_time_s = fields.Integer(string="Час евакуації зони, с", readonly=True)
    norm_s = fields.Integer(string="Норматив, с", readonly=True)
    in_norm = fields.Boolean(string="У нормативі", readonly=True)
    assigned_exits = fields.Char(string="Призначені виходи", readonly=True)
    actual_exits = fields.Char(string="Вийшли через", readonly=True)

    @property
    def _table_query(self):
        return """
                SELECT min(p.id) AS id,
                       p.drill_id AS drill_id,
                       p.zone_id AS zone_id,
                       count(*) AS people,
                       count(*) FILTER (WHERE p.status = 'evacuated') AS evacuated,
                       count(*) FILTER (WHERE p.status = 'present') AS present,
                       count(*) FILTER (WHERE p.status = 'missing') AS missing,
                       count(*) FILTER (WHERE p.wrong_exit) AS wrong_exit,
                       COALESCE(min(p.exit_s) FILTER (WHERE p.exit_ts IS NOT NULL), 0) AS first_exit_s,
                       COALESCE(max(p.exit_s) FILTER (WHERE p.exit_ts IS NOT NULL), 0) AS evac_time_s,
                       d.time_limit_s AS norm_s,
                       (COALESCE(max(p.exit_s) FILTER (WHERE p.exit_ts IS NOT NULL), 0) <= d.time_limit_s
                        AND count(*) FILTER (WHERE p.status = 'missing') = 0) AS in_norm,
                       string_agg(DISTINCT e1.code, ', ') AS assigned_exits,
                       string_agg(DISTINCT e2.code, ', ') AS actual_exits
                  FROM td_fire_drill_person p
                  JOIN td_fire_drill d ON d.id = p.drill_id
                  LEFT JOIN td_fire_exit e1 ON e1.id = p.assigned_exit_id
                  LEFT JOIN td_fire_exit e2 ON e2.id = p.exit_id
                 GROUP BY p.drill_id, p.zone_id, d.time_limit_s
        """
