"""M-08 `td.energy.daily` — добові факти (W4-A). Каркас: поля — за SPEC; індекси `init()`, `_td_build_days`,
`action_rebuild`, `_cron_daily`, `_cron_rotate` — воркер A (замінює файл цілком)."""

from odoo import fields, models

COST = "td_energy.group_td_energy_cost"


class TdEnergyDaily(models.Model):
    _name = "td.energy.daily"
    _description = "Енергетика: добовий факт"
    _inherit = ["td.energy.day.mixin"]
    _log_access = False
    _order = "day desc, scope, node_id"

    day = fields.Date(string="Дата (Київ)", required=True, index=True)
    scope = fields.Selection(
        [("plant", "Завод"), ("node", "Вузол"), ("resource", "Ресурс")], string="Рівень", required=True, index=True
    )
    resource_id = fields.Many2one("td.energy.resource", string="Ресурс")
    node_id = fields.Many2one("td.energy.node", string="Вузол", index=True)
    area_id = fields.Many2one("td.energy.area", string="Ділянка", index=True)
    qty = fields.Float(string="Кількість", digits=(16, 3))
    cost = fields.Float(string="Вартість, ₴", digits=(14, 2), groups=COST)
    co2_kg = fields.Float(string="CO₂, кг", digits=(14, 2))
    import_qty = fields.Float(string="Імпорт, кВт·год")
    export_qty = fields.Float(string="Експорт, кВт·год")
    gen_pv_qty = fields.Float(string="СЕС, кВт·год")
    gen_chp_qty = fields.Float(string="КГУ, кВт·год")
    shift1_qty = fields.Float(string="Зміна 1, кВт·год")
    shift2_qty = fields.Float(string="Зміна 2, кВт·год")
    off_qty = fields.Float(string="Поза змінами, кВт·год")
    cost_s1 = fields.Float(string="Вартість, зміна 1", digits=(14, 2), groups=COST)
    cost_s2 = fields.Float(string="Вартість, зміна 2", digits=(14, 2), groups=COST)
    cost_off = fields.Float(string="Вартість поза змінами", digits=(14, 2), groups=COST)
    direct_s1 = fields.Float(string="Прямі, зміна 1")
    direct_s2 = fields.Float(string="Прямі, зміна 2")
    direct_off = fields.Float(string="Прямі поза змінами")
    plate_s1 = fields.Float(string="Плити, зміна 1")
    plate_s2 = fields.Float(string="Плити, зміна 2")
    plate_off = fields.Float(string="Плити поза змінами")
    minutes = fields.Float(string="Хвилин роботи")
    idle_qty = fields.Float(string="Простій, кВт·год")
    quality = fields.Selection([("ok", "Повні"), ("partial", "Неповні")], string="Якість", default="ok")
    built_at = fields.Datetime(string="Побудовано", required=True)
