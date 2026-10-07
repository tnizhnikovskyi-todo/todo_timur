# Part of td_genset (ToDo). Власник файлу: W1 «Моніторинг». Каркас (поля, READING_FIELD_MAP, індекси): W0.
"""Знімок показань ``td.genset.reading`` — ТР 2.3.2, А.4, А.8; SPEC 5.2, Додаток A.

Кожен ключ ``values`` знімка (регістри 03H і сигнали 01H, ``relay_api.md`` 5.1–5.2) → поле з тим самим
іменем (виняток: ``fuel_level_sensor_ohm`` → ``fuel_sensor_ohm``) — ``READING_FIELD_MAP``.
Ключі ``*_text`` не зберігаються; невідомі ключі → ``values_extra`` (Json).

Увага щодо NULL: ORM читає NULL у Float/Integer як 0, у Boolean як False. Щоб зберегти «немає даних»
(NULL у базі, SPEC 4), ``_create_from_payload`` НЕ передає ключ у ``create`` (а не передає ``None``);
показ «немає даних» — з ``last_values_json``/``values`` (null), агрегати SQL NULL ігнорують.
"""
import json
import logging

from odoo import api, fields, models
from odoo.tools import sql

from .genset import CONTROLLER_MODES, FEED_SOURCES, FUEL_SOURCES, GENSET_STATUS

_logger = logging.getLogger(__name__)

# Ключ API → (поле, тип) — SPEC Додаток A (51 регістр 03H + 72 сигнали 01H). Тип: float | integer |
# boolean | selection | char. selection: ``genset_status`` (число → '0'…'15'), ``controller_mode``
# (null → 'unknown'); char: версії контролера.
READING_FIELD_MAP = {
    'mains_ua': ('mains_ua', 'float'),
    'mains_ub': ('mains_ub', 'float'),
    'mains_uc': ('mains_uc', 'float'),
    'mains_uab': ('mains_uab', 'float'),
    'mains_ubc': ('mains_ubc', 'float'),
    'mains_uca': ('mains_uca', 'float'),
    'mains_freq': ('mains_freq', 'float'),
    'gen_ua': ('gen_ua', 'float'),
    'gen_ub': ('gen_ub', 'float'),
    'gen_uc': ('gen_uc', 'float'),
    'gen_uab': ('gen_uab', 'float'),
    'gen_ubc': ('gen_ubc', 'float'),
    'gen_uca': ('gen_uca', 'float'),
    'gen_freq': ('gen_freq', 'float'),
    'current_a': ('current_a', 'float'),
    'current_b': ('current_b', 'float'),
    'current_c': ('current_c', 'float'),
    'water_temp': ('water_temp', 'float'),
    'oil_pressure': ('oil_pressure', 'float'),
    'fuel_level': ('fuel_level', 'float'),
    'speed': ('speed', 'float'),
    'battery_v': ('battery_v', 'float'),
    'dplus_v': ('dplus_v', 'float'),
    'active_power': ('active_power', 'float'),
    'reactive_power': ('reactive_power', 'float'),
    'apparent_power': ('apparent_power', 'float'),
    'power_factor': ('power_factor', 'float'),
    'power_a': ('power_a', 'float'),
    'power_b': ('power_b', 'float'),
    'power_c': ('power_c', 'float'),
    'load_pct': ('load_pct', 'float'),
    'maint_h': ('maint_h', 'integer'),
    'maint_min': ('maint_min', 'integer'),
    'genset_status': ('genset_status', 'selection'),
    'genset_status_delay': ('genset_status_delay', 'integer'),
    'remote_start_status': ('remote_start_status', 'integer'),
    'remote_start_delay': ('remote_start_delay', 'integer'),
    'ats_status': ('ats_status', 'integer'),
    'ats_status_delay': ('ats_status_delay', 'integer'),
    'mains_status': ('mains_status', 'integer'),
    'mains_status_delay': ('mains_status_delay', 'integer'),
    'run_hours': ('run_hours', 'integer'),
    'run_minutes': ('run_minutes', 'integer'),
    'start_count': ('start_count', 'integer'),
    'energy_kwh': ('energy_kwh', 'float'),
    'water_temp_sensor_ohm': ('water_temp_sensor_ohm', 'float'),
    'oil_pressure_sensor_ohm': ('oil_pressure_sensor_ohm', 'float'),
    'fuel_level_sensor_ohm': ('fuel_sensor_ohm', 'float'),
    'controller_sw': ('controller_sw', 'char'),
    'controller_hw': ('controller_hw', 'char'),
    'controller_mode': ('controller_mode', 'selection'),
    'common_alarm': ('common_alarm', 'boolean'),
    'common_warning': ('common_warning', 'boolean'),
    'common_shutdown': ('common_shutdown', 'boolean'),
    'remote_mode': ('remote_mode', 'boolean'),
    'remote_lock': ('remote_lock', 'boolean'),
    'mains_on_load': ('mains_on_load', 'boolean'),
    'gen_on_load': ('gen_on_load', 'boolean'),
    'emergency_stop': ('emergency_stop', 'boolean'),
    'overspeed_shutdown': ('overspeed_shutdown', 'boolean'),
    'underspeed_shutdown': ('underspeed_shutdown', 'boolean'),
    'speed_signal_loss_shutdown': ('speed_signal_loss_shutdown', 'boolean'),
    'overfrequency_shutdown': ('overfrequency_shutdown', 'boolean'),
    'underfrequency_shutdown': ('underfrequency_shutdown', 'boolean'),
    'overvoltage_shutdown': ('overvoltage_shutdown', 'boolean'),
    'undervoltage_shutdown': ('undervoltage_shutdown', 'boolean'),
    'gen_overcurrent_shutdown': ('gen_overcurrent_shutdown', 'boolean'),
    'crank_failure': ('crank_failure', 'boolean'),
    'high_temp_shutdown': ('high_temp_shutdown', 'boolean'),
    'low_oil_pressure_shutdown': ('low_oil_pressure_shutdown', 'boolean'),
    'frequency_loss_alarm': ('frequency_loss_alarm', 'boolean'),
    'input_shutdown': ('input_shutdown', 'boolean'),
    'low_fuel_shutdown': ('low_fuel_shutdown', 'boolean'),
    'low_coolant_shutdown': ('low_coolant_shutdown', 'boolean'),
    'high_temp_warning': ('high_temp_warning', 'boolean'),
    'low_oil_pressure_warning': ('low_oil_pressure_warning', 'boolean'),
    'gen_overcurrent_warning': ('gen_overcurrent_warning', 'boolean'),
    'stop_failure_warning': ('stop_failure_warning', 'boolean'),
    'low_fuel_warning': ('low_fuel_warning', 'boolean'),
    'charging_failure_warning': ('charging_failure_warning', 'boolean'),
    'battery_undervoltage_warning': ('battery_undervoltage_warning', 'boolean'),
    'battery_overvoltage_warning': ('battery_overvoltage_warning', 'boolean'),
    'input_warning': ('input_warning', 'boolean'),
    'speed_signal_loss_warning': ('speed_signal_loss_warning', 'boolean'),
    'low_coolant_warning': ('low_coolant_warning', 'boolean'),
    'temp_sensor_open_warning': ('temp_sensor_open_warning', 'boolean'),
    'oil_pressure_sensor_open_warning': ('oil_pressure_sensor_open_warning', 'boolean'),
    'maintenance_due_warning': ('maintenance_due_warning', 'boolean'),
    'charger_fail_warning': ('charger_fail_warning', 'boolean'),
    'overpower_warning': ('overpower_warning', 'boolean'),
    'test_mode': ('test_mode', 'boolean'),
    'auto_mode': ('auto_mode', 'boolean'),
    'manual_mode': ('manual_mode', 'boolean'),
    'stop_mode': ('stop_mode', 'boolean'),
    'temp_sensor_open_shutdown': ('temp_sensor_open_shutdown', 'boolean'),
    'oil_pressure_sensor_open_shutdown': ('oil_pressure_sensor_open_shutdown', 'boolean'),
    'maintenance_due_shutdown': ('maintenance_due_shutdown', 'boolean'),
    'overpower_shutdown': ('overpower_shutdown', 'boolean'),
    'emergency_stop_input': ('emergency_stop_input', 'boolean'),
    'aux_input_1': ('aux_input_1', 'boolean'),
    'aux_input_2': ('aux_input_2', 'boolean'),
    'aux_input_3': ('aux_input_3', 'boolean'),
    'aux_input_4': ('aux_input_4', 'boolean'),
    'aux_input_5': ('aux_input_5', 'boolean'),
    'crank_relay': ('crank_relay', 'boolean'),
    'fuel_relay': ('fuel_relay', 'boolean'),
    'aux_output_1': ('aux_output_1', 'boolean'),
    'aux_output_2': ('aux_output_2', 'boolean'),
    'aux_output_3': ('aux_output_3', 'boolean'),
    'aux_output_4': ('aux_output_4', 'boolean'),
    'mains_fault': ('mains_fault', 'boolean'),
    'mains_normal': ('mains_normal', 'boolean'),
    'mains_overvoltage': ('mains_overvoltage', 'boolean'),
    'mains_undervoltage': ('mains_undervoltage', 'boolean'),
    'mains_loss_phase': ('mains_loss_phase', 'boolean'),
    'mains_blackout': ('mains_blackout', 'boolean'),
    'gen_normal': ('gen_normal', 'boolean'),
    'gen_overvoltage': ('gen_overvoltage', 'boolean'),
    'gen_undervoltage': ('gen_undervoltage', 'boolean'),
    'gen_overfrequency': ('gen_overfrequency', 'boolean'),
    'gen_underfrequency': ('gen_underfrequency', 'boolean'),
    'gen_overcurrent': ('gen_overcurrent', 'boolean'),
    'scheduled_not_run': ('scheduled_not_run', 'boolean'),
}
# Ключі values, які свідомо не зберігаються (похідні від selection, SPEC Додаток A)
READING_IGNORED_KEYS = frozenset({'genset_status_text', 'remote_start_status_text', 'mains_status_text'})
# Оми датчиків: поле → (ключ API ≥ 1.1.3, регістр сирого образу raw=1; значення регістра ÷ 10) — AC-68
SENSOR_OHM_SOURCES = {
    'fuel_sensor_ohm': ('fuel_level_sensor_ohm', '22'),
    'water_temp_sensor_ohm': ('water_temp_sensor_ohm', '18'),
    'oil_pressure_sensor_ohm': ('oil_pressure_sensor_ohm', '20'),
}
REASONS = [
    ('first', 'Перший'),
    ('change', 'Зміна стану'),
    ('interval', 'Плановий'),
]


class TdGensetReading(models.Model):
    _name = 'td.genset.reading'
    _description = 'Генератори: знімок показань'
    _order = 'ts desc, id desc'
    _rec_name = 'ts'

    READING_FIELD_MAP = READING_FIELD_MAP

    # ------------------------------------------------------------------ службові
    genset_id = fields.Many2one(
        'td.genset', string='Генератор', required=True, index=True, ondelete='cascade',
        help='Генератор, з модуля якого отримано знімок.')
    relay_id = fields.Integer(
        string='ID знімка', required=True, index=True, aggregator=None,
        help='id знімка ретранслятора (монотонний) — ключ ідемпотентності разом з генератором.')
    ts = fields.Datetime(
        string='Час', required=True, index=True,
        help='Коли ретранслятор зробив знімок (UTC у базі, показ — у часовому поясі користувача).')
    reason = fields.Selection(
        REASONS, string='Причина',
        help='first — перший знімок після запуску ретранслятора; change — змінився стан; interval — плановий.')
    slot_15 = fields.Datetime(
        string='Інтервал 15 хв', index=True,
        help='Початок 15-хвилинного інтервалу за київським часом (збережений в UTC) — журнал показань (ФВ-6).')
    is_journal = fields.Boolean(
        string='Журнальний',
        help='Останній знімок свого 15-хвилинного інтервалу — показується в журналі за замовчуванням.')
    is_hour = fields.Boolean(
        string='Погодинний',
        help='Інтервал починається на початку години — фільтр «Погодинно».')

    # ------------------------------------------------------------------ похідні (SPEC 4, ТР 1.2; _derive)
    feed_source = fields.Selection(
        FEED_SOURCES, string="Живлення об'єкта", readonly=True,
        help="З сигналів 01H 0006/0007: мережа під навантаженням → Мережа, генератор → Генератор, обидва ні → Немає.")
    is_running = fields.Boolean(
        string='Працює', readonly=True,
        help='genset_status ∉ {0, 15} або оберти > 0 (14 «Невдала зупинка» — теж працює). Фільтр «Генератор працював».')
    mains_ok = fields.Boolean(
        string='Є мережа', readonly=True,
        help='Сигнал 01H 0065 «Мережа в нормі» (не mains_status). Фільтр «Без мережі».')
    fuel_liters = fields.Float(
        string='Паливо, L', compute='_compute_fuel_liters', store=True, readonly=True, aggregator='avg',
        help="За калібруванням датчика (Ом → L), якщо воно заповнене і є опір датчика; інакше рівень % × об'єм бака. "
             "Історія перераховується кнопкою «Перерахувати літри» (AC-69).")
    fuel_source = fields.Selection(
        FUEL_SOURCES, string='Літри за', compute='_compute_fuel_liters', store=True, readonly=True,
        help='За % контролера чи за калібруванням датчика (Ом).')
    run_hours_total = fields.Float(
        string='Мотогодини всього', compute='_compute_run_hours_total', store=True, readonly=True,
        aggregator='max',
        help='Мотогодини + хвилини / 60.')
    alarm_flags = fields.Char(
        string='Тривоги', readonly=True,
        help='Активні сигнали тривог 01H на момент знімка (коди через кому).')
    values_extra = fields.Json(
        string='Інші значення', readonly=True,
        help='Ключі values, яких немає в таблиці відповідності (нові версії ретранслятора); зазвичай порожньо.')
    values_extra_text = fields.Text(
        string='Інші значення (JSON)', compute='_compute_values_extra_text',
        help='Інші значення як текст JSON — для експорту (AC-59).')

    # ------------------------------------------------------------------ значення знімка (Додаток A)
    mains_ua = fields.Float(
        string="Мережа, фазні напруги (UA), V", readonly=True, aggregator='avg',
        help="Мережа, фазні напруги (UA) (регістр 03H 0–2; ключ API «mains_ua»). NULL — немає даних.")
    mains_ub = fields.Float(
        string="Мережа, фазні напруги (UB), V", readonly=True, aggregator='avg',
        help="Мережа, фазні напруги (UB) (регістр 03H 0–2; ключ API «mains_ub»). NULL — немає даних.")
    mains_uc = fields.Float(
        string="Мережа, фазні напруги (UC), V", readonly=True, aggregator='avg',
        help="Мережа, фазні напруги (UC) (регістр 03H 0–2; ключ API «mains_uc»). NULL — немає даних.")
    mains_uab = fields.Float(
        string="Мережа, лінійні напруги (UAB), V", readonly=True, aggregator='avg',
        help="Мережа, лінійні напруги (UAB) (регістр 03H 3–5; ключ API «mains_uab»). NULL — немає даних.")
    mains_ubc = fields.Float(
        string="Мережа, лінійні напруги (UBC), V", readonly=True, aggregator='avg',
        help="Мережа, лінійні напруги (UBC) (регістр 03H 3–5; ключ API «mains_ubc»). NULL — немає даних.")
    mains_uca = fields.Float(
        string="Мережа, лінійні напруги (UCA), V", readonly=True, aggregator='avg',
        help="Мережа, лінійні напруги (UCA) (регістр 03H 3–5; ключ API «mains_uca»). NULL — немає даних.")
    mains_freq = fields.Float(
        string="Мережа, частота, Hz", readonly=True, aggregator='avg',
        help="Мережа, частота (регістр 03H 6; ключ API «mains_freq»). NULL — немає даних.")
    gen_ua = fields.Float(
        string="Генератор, фазні напруги (UA), V", readonly=True, aggregator='avg',
        help="Генератор, фазні напруги (UA) (регістр 03H 7–9; ключ API «gen_ua»). NULL — немає даних.")
    gen_ub = fields.Float(
        string="Генератор, фазні напруги (UB), V", readonly=True, aggregator='avg',
        help="Генератор, фазні напруги (UB) (регістр 03H 7–9; ключ API «gen_ub»). NULL — немає даних.")
    gen_uc = fields.Float(
        string="Генератор, фазні напруги (UC), V", readonly=True, aggregator='avg',
        help="Генератор, фазні напруги (UC) (регістр 03H 7–9; ключ API «gen_uc»). NULL — немає даних.")
    gen_uab = fields.Float(
        string="Генератор, лінійні напруги (UAB), V", readonly=True, aggregator='avg',
        help="Генератор, лінійні напруги (UAB) (регістр 03H 10–12; ключ API «gen_uab»). NULL — немає даних.")
    gen_ubc = fields.Float(
        string="Генератор, лінійні напруги (UBC), V", readonly=True, aggregator='avg',
        help="Генератор, лінійні напруги (UBC) (регістр 03H 10–12; ключ API «gen_ubc»). NULL — немає даних.")
    gen_uca = fields.Float(
        string="Генератор, лінійні напруги (UCA), V", readonly=True, aggregator='avg',
        help="Генератор, лінійні напруги (UCA) (регістр 03H 10–12; ключ API «gen_uca»). NULL — немає даних.")
    gen_freq = fields.Float(
        string="Генератор, частота, Hz", readonly=True, aggregator='avg',
        help="Генератор, частота (регістр 03H 13; ключ API «gen_freq»). NULL — немає даних.")
    current_a = fields.Float(
        string="Струм навантаження генератора по фазах (A), A", readonly=True, aggregator='avg',
        help="Струм навантаження генератора по фазах (A) (регістр 03H 14–16; ключ API «current_a»). NULL — немає даних.")
    current_b = fields.Float(
        string="Струм навантаження генератора по фазах (B), A", readonly=True, aggregator='avg',
        help="Струм навантаження генератора по фазах (B) (регістр 03H 14–16; ключ API «current_b»). NULL — немає даних.")
    current_c = fields.Float(
        string="Струм навантаження генератора по фазах (C), A", readonly=True, aggregator='avg',
        help="Струм навантаження генератора по фазах (C) (регістр 03H 14–16; ключ API «current_c»). NULL — немає даних.")
    water_temp = fields.Float(
        string="Температура охолоджувальної рідини, °C", readonly=True, aggregator='avg',
        help="Температура охолоджувальної рідини (регістр 03H 17; ключ API «water_temp»). NULL — немає даних.")
    oil_pressure = fields.Float(
        string="Тиск оливи, kPa", readonly=True, aggregator='avg',
        help="Тиск оливи (регістр 03H 19; ключ API «oil_pressure»). NULL — немає даних.")
    fuel_level = fields.Float(
        string="Рівень палива, %", readonly=True, aggregator='avg',
        help="Рівень палива (регістр 03H 21; ключ API «fuel_level»). NULL — немає даних.")
    speed = fields.Float(
        string="Оберти двигуна, RPM", readonly=True, aggregator='avg',
        help="Оберти двигуна (регістр 03H 23; ключ API «speed»). NULL — немає даних.")
    battery_v = fields.Float(
        string="Напруга АКБ, V", readonly=True, aggregator='avg',
        help="Напруга АКБ (регістр 03H 24; ключ API «battery_v»). NULL — немає даних.")
    dplus_v = fields.Float(
        string="Напруга D+ (зарядний генератор), V", readonly=True, aggregator='avg',
        help="Напруга D+ (зарядний генератор) (регістр 03H 25; ключ API «dplus_v»). NULL — немає даних.")
    active_power = fields.Float(
        string="Активна потужність (знакова), kW", readonly=True, aggregator='max',
        help="Активна потужність (знакова) (регістр 03H 26; ключ API «active_power»). NULL — немає даних.")
    reactive_power = fields.Float(
        string="Реактивна потужність (знакова), kvar", readonly=True, aggregator='avg',
        help="Реактивна потужність (знакова) (регістр 03H 27; ключ API «reactive_power»). NULL — немає даних.")
    apparent_power = fields.Float(
        string="Повна потужність (знакова), kVA", readonly=True, aggregator='avg',
        help="Повна потужність (знакова) (регістр 03H 28; ключ API «apparent_power»). NULL — немає даних.")
    power_factor = fields.Float(
        string="cos φ (знаковий)", readonly=True, aggregator='avg',
        help="cos φ (знаковий) (регістр 03H 29; ключ API «power_factor»). NULL — немає даних.")
    power_a = fields.Float(
        string="Активна потужність по фазах (A), kW", readonly=True, aggregator='avg',
        help="Активна потужність по фазах (A) (регістр 03H 52–54; ключ API «power_a»). NULL — немає даних.")
    power_b = fields.Float(
        string="Активна потужність по фазах (B), kW", readonly=True, aggregator='avg',
        help="Активна потужність по фазах (B) (регістр 03H 52–54; ключ API «power_b»). NULL — немає даних.")
    power_c = fields.Float(
        string="Активна потужність по фазах (C), kW", readonly=True, aggregator='avg',
        help="Активна потужність по фазах (C) (регістр 03H 52–54; ключ API «power_c»). NULL — немає даних.")
    load_pct = fields.Float(
        string="Навантаження генератора, %", readonly=True, aggregator='avg',
        help="Навантаження генератора (регістр 03H 55; ключ API «load_pct»). NULL — немає даних.")
    maint_h = fields.Integer(
        string="До ТО (год)", readonly=True, aggregator=None,
        help="До ТО (год) (регістр 03H 30–31; ключ API «maint_h»). NULL — немає даних.")
    maint_min = fields.Integer(
        string="До ТО (хв)", readonly=True, aggregator=None,
        help="До ТО (хв) (регістр 03H 30–31; ключ API «maint_min»). NULL — немає даних.")
    genset_status = fields.Selection(
        GENSET_STATUS, string="Стан агрегату", readonly=True,
        help="Стан агрегату (таблиця 5.3) (регістр 03H 34; ключ API «genset_status»). NULL — немає даних.")
    genset_status_delay = fields.Integer(
        string="Відлік поточного стану, с", readonly=True, aggregator=None,
        help="Відлік поточного стану (регістр 03H 35; ключ API «genset_status_delay»). NULL — немає даних.")
    remote_start_status = fields.Integer(
        string="Дистанційний пуск", readonly=True, aggregator=None,
        help="Дистанційний пуск: 0 «No Delay», 1 «Start Delay», 2 «Stop Delay» (регістр 03H 36; ключ API «remote_start_status»). NULL — немає даних.")
    remote_start_delay = fields.Integer(
        string="Відлік дистанційного пуску, с", readonly=True, aggregator=None,
        help="Відлік дистанційного пуску (регістр 03H 37; ключ API «remote_start_delay»). NULL — немає даних.")
    ats_status = fields.Integer(
        string="Стан ATS", readonly=True, aggregator=None,
        help="Стан ATS (перемикання навантаження), код. Таблиці значень у протоколі немає. Спостереження: 5 → 2 після замикання мережі (регістр 03H 38; ключ API «ats_status»). NULL — немає даних.")
    ats_status_delay = fields.Integer(
        string="Відлік ATS, с", readonly=True, aggregator=None,
        help="Відлік ATS (регістр 03H 39; ключ API «ats_status_delay»). NULL — немає даних.")
    mains_status = fields.Integer(
        string="Стан мережі (код)", readonly=True, aggregator=None,
        help="0 «Normal», 1 «Abnormal», 2 «No Delay». (регістр 03H 40; ключ API «mains_status»). NULL — немає даних.")
    mains_status_delay = fields.Integer(
        string="Відлік стану мережі, с", readonly=True, aggregator=None,
        help="Відлік стану мережі (регістр 03H 41; ключ API «mains_status_delay»). NULL — немає даних.")
    run_hours = fields.Integer(
        string="Мотогодини (год)", readonly=True, aggregator='max',
        help="Мотогодини (накопичувальні) (год) (регістр 03H 42–44; ключ API «run_hours»). NULL — немає даних.")
    run_minutes = fields.Integer(
        string="Мотогодини (хв)", readonly=True, aggregator='max',
        help="Мотогодини (накопичувальні) (хв) (регістр 03H 42–44; ключ API «run_minutes»). NULL — немає даних.")
    start_count = fields.Integer(
        string="Кількість пусків (накопичувальна)", readonly=True, aggregator='max',
        help="Кількість пусків (накопичувальна) (регістр 03H 46–47; ключ API «start_count»). NULL — немає даних.")
    energy_kwh = fields.Float(
        string="Вироблено енергії генератором (накопичувальна), kWh", readonly=True, aggregator='max',
        help="Вироблено енергії генератором (накопичувальна) (регістр 03H 48–49; ключ API «energy_kwh»). NULL — немає даних.")
    water_temp_sensor_ohm = fields.Float(
        string="Опір датчика температури, Ом", readonly=True, digits=(16, 1), aggregator='avg',
        help="Опір датчика температури — з версії 1.1.3 (регістр 03H 18; ключ API «water_temp_sensor_ohm»). NULL — немає даних. Крок 0,1 Ом; з ключа (ретранслятор ≥ 1.1.3) або з сирого образу raw=1 (регістр ÷ 10).")
    oil_pressure_sensor_ohm = fields.Float(
        string="Опір датчика тиску оливи, Ом", readonly=True, digits=(16, 1), aggregator='avg',
        help="Опір датчика тиску оливи — з 1.1.3 (регістр 03H 20; ключ API «oil_pressure_sensor_ohm»). NULL — немає даних. Крок 0,1 Ом; з ключа (ретранслятор ≥ 1.1.3) або з сирого образу raw=1 (регістр ÷ 10).")
    fuel_sensor_ohm = fields.Float(
        string="Опір датчика рівня палива, Ом", readonly=True, digits=(16, 1), aggregator='avg',
        help="Опір датчика рівня палива — з 1.1.3 (регістр 03H 22; ключ API «fuel_level_sensor_ohm»). NULL — немає даних. Крок 0,1 Ом; з ключа (ретранслятор ≥ 1.1.3) або з сирого образу raw=1 (регістр ÷ 10).")
    controller_sw = fields.Char(
        string="Версія ПЗ контролера", readonly=True,
        help="Версії ПЗ і апаратна контролера — з 1.1.3 (ПЗ) (регістр 03H 50, 51; ключ API «controller_sw»). NULL — немає даних.")
    controller_hw = fields.Char(
        string="Апаратна версія контролера", readonly=True,
        help="Версії ПЗ і апаратна контролера — з 1.1.3 (апаратна) (регістр 03H 50, 51; ключ API «controller_hw»). NULL — немає даних.")
    controller_mode = fields.Selection(
        CONTROLLER_MODES, string="Режим контролера", readonly=True,
        help="Режим контролера з сигналів 01H 0040–0043 (ключ API «controller_mode»): Авто / Ручний / Стоп / Тест; null — невідомо або горить кілька.")
    common_alarm = fields.Boolean(
        string="Загальна тривога", readonly=True,
        help="Загальна тривога (сигнал 01H 0000; ключ API «common_alarm»). NULL — невідомо (ключа немає у знімку).")
    common_warning = fields.Boolean(
        string="Загальне попередження", readonly=True,
        help="Загальне попередження (сигнал 01H 0001; ключ API «common_warning»). NULL — невідомо (ключа немає у знімку).")
    common_shutdown = fields.Boolean(
        string="Загальна аварійна зупинка", readonly=True,
        help="Загальна аварійна зупинка (сигнал 01H 0002; ключ API «common_shutdown»). NULL — невідомо (ключа немає у знімку).")
    remote_mode = fields.Boolean(
        string="Дистанційний режим", readonly=True,
        help="Дистанційний режим (сигнал 01H 0003; ключ API «remote_mode»). NULL — невідомо (ключа немає у знімку).")
    remote_lock = fields.Boolean(
        string="Дистанційне блокування", readonly=True,
        help="Дистанційне блокування (сигнал 01H 0004; ключ API «remote_lock»). NULL — невідомо (ключа немає у знімку).")
    mains_on_load = fields.Boolean(
        string="Мережа під навантаженням", readonly=True,
        help="Мережа під навантаженням (сигнал 01H 0006; ключ API «mains_on_load»). NULL — невідомо (ключа немає у знімку).")
    gen_on_load = fields.Boolean(
        string="Генератор під навантаженням", readonly=True,
        help="Генератор під навантаженням (сигнал 01H 0007; ключ API «gen_on_load»). NULL — невідомо (ключа немає у знімку).")
    emergency_stop = fields.Boolean(
        string="Аварійний стоп", readonly=True,
        help="Аварійний стоп (сигнал 01H 0008; ключ API «emergency_stop»). NULL — невідомо (ключа немає у знімку).")
    overspeed_shutdown = fields.Boolean(
        string="Аварія: перевищення обертів", readonly=True,
        help="Перевищення обертів (сигнал 01H 0009; ключ API «overspeed_shutdown»). NULL — невідомо (ключа немає у знімку).")
    underspeed_shutdown = fields.Boolean(
        string="Аварія: занижені оберти", readonly=True,
        help="Занижені оберти (сигнал 01H 0010; ключ API «underspeed_shutdown»). NULL — невідомо (ключа немає у знімку).")
    speed_signal_loss_shutdown = fields.Boolean(
        string="Аварія: втрата сигналу обертів", readonly=True,
        help="Втрата сигналу обертів (сигнал 01H 0011; ключ API «speed_signal_loss_shutdown»). NULL — невідомо (ключа немає у знімку).")
    overfrequency_shutdown = fields.Boolean(
        string="Аварія: висока частота", readonly=True,
        help="Висока частота (сигнал 01H 0012; ключ API «overfrequency_shutdown»). NULL — невідомо (ключа немає у знімку).")
    underfrequency_shutdown = fields.Boolean(
        string="Аварія: низька частота", readonly=True,
        help="Низька частота (сигнал 01H 0013; ключ API «underfrequency_shutdown»). NULL — невідомо (ключа немає у знімку).")
    overvoltage_shutdown = fields.Boolean(
        string="Аварія: висока напруга", readonly=True,
        help="Висока напруга (сигнал 01H 0014; ключ API «overvoltage_shutdown»). NULL — невідомо (ключа немає у знімку).")
    undervoltage_shutdown = fields.Boolean(
        string="Аварія: низька напруга", readonly=True,
        help="Низька напруга (сигнал 01H 0015; ключ API «undervoltage_shutdown»). NULL — невідомо (ключа немає у знімку).")
    gen_overcurrent_shutdown = fields.Boolean(
        string="Аварія: перевантаження за струмом", readonly=True,
        help="Перевантаження за струмом (сигнал 01H 0016; ключ API «gen_overcurrent_shutdown»). NULL — невідомо (ключа немає у знімку).")
    crank_failure = fields.Boolean(
        string="Аварія: невдалий пуск", readonly=True,
        help="Невдалий пуск (сигнал 01H 0017; ключ API «crank_failure»). NULL — невідомо (ключа немає у знімку).")
    high_temp_shutdown = fields.Boolean(
        string="Аварія: висока температура ОР", readonly=True,
        help="Висока температура ОР (сигнал 01H 0018; ключ API «high_temp_shutdown»). NULL — невідомо (ключа немає у знімку).")
    low_oil_pressure_shutdown = fields.Boolean(
        string="Аварія: низький тиск оливи", readonly=True,
        help="Низький тиск оливи (сигнал 01H 0019; ключ API «low_oil_pressure_shutdown»). NULL — невідомо (ключа немає у знімку).")
    frequency_loss_alarm = fields.Boolean(
        string="Аварія: втрата частоти", readonly=True,
        help="Втрата частоти (сигнал 01H 0020; ключ API «frequency_loss_alarm»). NULL — невідомо (ключа немає у знімку).")
    input_shutdown = fields.Boolean(
        string="Аварія: аварійний вхід", readonly=True,
        help="Аварійний вхід (сигнал 01H 0021; ключ API «input_shutdown»). NULL — невідомо (ключа немає у знімку).")
    low_fuel_shutdown = fields.Boolean(
        string="Аварія: низький рівень палива", readonly=True,
        help="Низький рівень палива (сигнал 01H 0022; ключ API «low_fuel_shutdown»). NULL — невідомо (ключа немає у знімку).")
    low_coolant_shutdown = fields.Boolean(
        string="Аварія: низький рівень ОР", readonly=True,
        help="Низький рівень ОР (сигнал 01H 0023; ключ API «low_coolant_shutdown»). NULL — невідомо (ключа немає у знімку).")
    high_temp_warning = fields.Boolean(
        string="Попередження: висока температура ОР", readonly=True,
        help="Висока температура ОР (сигнал 01H 0024; ключ API «high_temp_warning»). NULL — невідомо (ключа немає у знімку).")
    low_oil_pressure_warning = fields.Boolean(
        string="Попередження: низький тиск оливи", readonly=True,
        help="Низький тиск оливи (сигнал 01H 0025; ключ API «low_oil_pressure_warning»). NULL — невідомо (ключа немає у знімку).")
    gen_overcurrent_warning = fields.Boolean(
        string="Попередження: перевантаження за струмом", readonly=True,
        help="Перевантаження за струмом (сигнал 01H 0026; ключ API «gen_overcurrent_warning»). NULL — невідомо (ключа немає у знімку).")
    stop_failure_warning = fields.Boolean(
        string="Попередження: невдала зупинка", readonly=True,
        help="Невдала зупинка (сигнал 01H 0027; ключ API «stop_failure_warning»). NULL — невідомо (ключа немає у знімку).")
    low_fuel_warning = fields.Boolean(
        string="Попередження: низький рівень палива", readonly=True,
        help="Низький рівень палива (сигнал 01H 0028; ключ API «low_fuel_warning»). NULL — невідомо (ключа немає у знімку).")
    charging_failure_warning = fields.Boolean(
        string="Попередження: немає заряду D+", readonly=True,
        help="Немає заряду D+ (сигнал 01H 0029; ключ API «charging_failure_warning»). NULL — невідомо (ключа немає у знімку).")
    battery_undervoltage_warning = fields.Boolean(
        string="Попередження: низька напруга АКБ", readonly=True,
        help="Низька напруга АКБ (сигнал 01H 0030; ключ API «battery_undervoltage_warning»). NULL — невідомо (ключа немає у знімку).")
    battery_overvoltage_warning = fields.Boolean(
        string="Попередження: висока напруга АКБ", readonly=True,
        help="Висока напруга АКБ (сигнал 01H 0031; ключ API «battery_overvoltage_warning»). NULL — невідомо (ключа немає у знімку).")
    input_warning = fields.Boolean(
        string="Попередження: вхід попередження", readonly=True,
        help="Вхід попередження (сигнал 01H 0032; ключ API «input_warning»). NULL — невідомо (ключа немає у знімку).")
    speed_signal_loss_warning = fields.Boolean(
        string="Попередження: втрата сигналу обертів", readonly=True,
        help="Втрата сигналу обертів (сигнал 01H 0033; ключ API «speed_signal_loss_warning»). NULL — невідомо (ключа немає у знімку).")
    low_coolant_warning = fields.Boolean(
        string="Попередження: низький рівень ОР", readonly=True,
        help="Низький рівень ОР (сигнал 01H 0034; ключ API «low_coolant_warning»). NULL — невідомо (ключа немає у знімку).")
    temp_sensor_open_warning = fields.Boolean(
        string="Попередження: обрив датчика температури", readonly=True,
        help="Обрив датчика температури (сигнал 01H 0035; ключ API «temp_sensor_open_warning»). NULL — невідомо (ключа немає у знімку).")
    oil_pressure_sensor_open_warning = fields.Boolean(
        string="Попередження: обрив датчика тиску", readonly=True,
        help="Обрив датчика тиску (сигнал 01H 0036; ключ API «oil_pressure_sensor_open_warning»). NULL — невідомо (ключа немає у знімку).")
    maintenance_due_warning = fields.Boolean(
        string="Попередження: термін ТО", readonly=True,
        help="Термін ТО (сигнал 01H 0037; ключ API «maintenance_due_warning»). NULL — невідомо (ключа немає у знімку).")
    charger_fail_warning = fields.Boolean(
        string="Попередження: збій зарядного пристрою", readonly=True,
        help="Збій зарядного пристрою (сигнал 01H 0038; ключ API «charger_fail_warning»). NULL — невідомо (ключа немає у знімку).")
    overpower_warning = fields.Boolean(
        string="Попередження: перевантаження за потужністю", readonly=True,
        help="Перевантаження за потужністю (сигнал 01H 0039; ключ API «overpower_warning»). NULL — невідомо (ключа немає у знімку).")
    test_mode = fields.Boolean(
        string="Режим Тест", readonly=True,
        help="Режим Тест (сигнал 01H 0040; ключ API «test_mode»). NULL — невідомо (ключа немає у знімку).")
    auto_mode = fields.Boolean(
        string="Режим Авто", readonly=True,
        help="Режим Авто (сигнал 01H 0041; ключ API «auto_mode»). NULL — невідомо (ключа немає у знімку).")
    manual_mode = fields.Boolean(
        string="Режим Ручний", readonly=True,
        help="Режим Ручний (сигнал 01H 0042; ключ API «manual_mode»). NULL — невідомо (ключа немає у знімку).")
    stop_mode = fields.Boolean(
        string="Режим Стоп", readonly=True,
        help="Режим Стоп (сигнал 01H 0043; ключ API «stop_mode»). NULL — невідомо (ключа немає у знімку).")
    temp_sensor_open_shutdown = fields.Boolean(
        string="Аварія: обрив датчика температури", readonly=True,
        help="Обрив датчика температури (сигнал 01H 0044; ключ API «temp_sensor_open_shutdown»). NULL — невідомо (ключа немає у знімку).")
    oil_pressure_sensor_open_shutdown = fields.Boolean(
        string="Аварія: обрив датчика тиску", readonly=True,
        help="Обрив датчика тиску (сигнал 01H 0045; ключ API «oil_pressure_sensor_open_shutdown»). NULL — невідомо (ключа немає у знімку).")
    maintenance_due_shutdown = fields.Boolean(
        string="Аварія: прострочене ТО", readonly=True,
        help="Прострочене ТО (сигнал 01H 0046; ключ API «maintenance_due_shutdown»). NULL — невідомо (ключа немає у знімку).")
    overpower_shutdown = fields.Boolean(
        string="Аварія: перевантаження за потужністю", readonly=True,
        help="Перевантаження за потужністю (сигнал 01H 0047; ключ API «overpower_shutdown»). NULL — невідомо (ключа немає у знімку).")
    emergency_stop_input = fields.Boolean(
        string="Вхід аварійного стопу", readonly=True,
        help="Вхід аварійного стопу (сигнал 01H 0048; ключ API «emergency_stop_input»). NULL — невідомо (ключа немає у знімку).")
    aux_input_1 = fields.Boolean(
        string="Дод. вхід 1", readonly=True,
        help="Дод. вхід 1 (сигнал 01H 0049; ключ API «aux_input_1»). NULL — невідомо (ключа немає у знімку).")
    aux_input_2 = fields.Boolean(
        string="Дод. вхід 2", readonly=True,
        help="Дод. вхід 2 (сигнал 01H 0050; ключ API «aux_input_2»). NULL — невідомо (ключа немає у знімку).")
    aux_input_3 = fields.Boolean(
        string="Дод. вхід 3", readonly=True,
        help="Дод. вхід 3 (сигнал 01H 0051; ключ API «aux_input_3»). NULL — невідомо (ключа немає у знімку).")
    aux_input_4 = fields.Boolean(
        string="Дод. вхід 4", readonly=True,
        help="Дод. вхід 4 (сигнал 01H 0052; ключ API «aux_input_4»). NULL — невідомо (ключа немає у знімку).")
    aux_input_5 = fields.Boolean(
        string="Дод. вхід 5", readonly=True,
        help="Дод. вхід 5 (сигнал 01H 0053; ключ API «aux_input_5»). NULL — невідомо (ключа немає у знімку).")
    crank_relay = fields.Boolean(
        string="Реле стартера", readonly=True,
        help="Реле стартера (сигнал 01H 0056; ключ API «crank_relay»). NULL — невідомо (ключа немає у знімку).")
    fuel_relay = fields.Boolean(
        string="Реле палива", readonly=True,
        help="Реле палива (сигнал 01H 0057; ключ API «fuel_relay»). NULL — невідомо (ключа немає у знімку).")
    aux_output_1 = fields.Boolean(
        string="Дод. вихід 1", readonly=True,
        help="Дод. вихід 1 (сигнал 01H 0058; ключ API «aux_output_1»). NULL — невідомо (ключа немає у знімку).")
    aux_output_2 = fields.Boolean(
        string="Дод. вихід 2", readonly=True,
        help="Дод. вихід 2 (сигнал 01H 0059; ключ API «aux_output_2»). NULL — невідомо (ключа немає у знімку).")
    aux_output_3 = fields.Boolean(
        string="Дод. вихід 3", readonly=True,
        help="Дод. вихід 3 (сигнал 01H 0060; ключ API «aux_output_3»). NULL — невідомо (ключа немає у знімку).")
    aux_output_4 = fields.Boolean(
        string="Дод. вихід 4", readonly=True,
        help="Дод. вихід 4 (сигнал 01H 0061; ключ API «aux_output_4»). NULL — невідомо (ключа немає у знімку).")
    mains_fault = fields.Boolean(
        string="Аварія мережі", readonly=True,
        help="Аварія мережі (сигнал 01H 0064; ключ API «mains_fault»). NULL — невідомо (ключа немає у знімку).")
    mains_normal = fields.Boolean(
        string="Мережа в нормі", readonly=True,
        help="Мережа в нормі (сигнал 01H 0065; ключ API «mains_normal»). NULL — невідомо (ключа немає у знімку).")
    mains_overvoltage = fields.Boolean(
        string="Мережа: перенапруга", readonly=True,
        help="Перенапруга (сигнал 01H 0066; ключ API «mains_overvoltage»). NULL — невідомо (ключа немає у знімку).")
    mains_undervoltage = fields.Boolean(
        string="Мережа: недонапруга", readonly=True,
        help="Недонапруга (сигнал 01H 0067; ключ API «mains_undervoltage»). NULL — невідомо (ключа немає у знімку).")
    mains_loss_phase = fields.Boolean(
        string="Мережа: обрив фази", readonly=True,
        help="Обрив фази (сигнал 01H 0068; ключ API «mains_loss_phase»). NULL — невідомо (ключа немає у знімку).")
    mains_blackout = fields.Boolean(
        string="Відсутність мережі", readonly=True,
        help="Відсутність мережі (сигнал 01H 0069; ключ API «mains_blackout»). NULL — невідомо (ключа немає у знімку).")
    gen_normal = fields.Boolean(
        string="Генератор у нормі", readonly=True,
        help="Генератор у нормі (сигнал 01H 0072; ключ API «gen_normal»). NULL — невідомо (ключа немає у знімку).")
    gen_overvoltage = fields.Boolean(
        string="Генератор: перенапруга", readonly=True,
        help="Перенапруга (сигнал 01H 0073; ключ API «gen_overvoltage»). NULL — невідомо (ключа немає у знімку).")
    gen_undervoltage = fields.Boolean(
        string="Генератор: недонапруга", readonly=True,
        help="Недонапруга (сигнал 01H 0074; ключ API «gen_undervoltage»). NULL — невідомо (ключа немає у знімку).")
    gen_overfrequency = fields.Boolean(
        string="Генератор: висока частота", readonly=True,
        help="Висока частота (сигнал 01H 0075; ключ API «gen_overfrequency»). NULL — невідомо (ключа немає у знімку).")
    gen_underfrequency = fields.Boolean(
        string="Генератор: низька частота", readonly=True,
        help="Низька частота (сигнал 01H 0076; ключ API «gen_underfrequency»). NULL — невідомо (ключа немає у знімку).")
    gen_overcurrent = fields.Boolean(
        string="Генератор: перевантаження за струмом", readonly=True,
        help="Перевантаження за струмом (сигнал 01H 0077; ключ API «gen_overcurrent»). NULL — невідомо (ключа немає у знімку).")
    scheduled_not_run = fields.Boolean(
        string="Пропущено запуск за розкладом", readonly=True,
        help="Пропущено запуск за розкладом (сигнал 01H 0078; ключ API «scheduled_not_run»). NULL — невідомо (ключа немає у знімку).")

    _sql_constraints = [
        ('relay_id_uniq', 'unique(genset_id, relay_id)', 'Знімок з таким ID уже збережено для цього генератора.'),
    ]

    def init(self):
        """Індекси А.4: складений ``(genset_id, ts DESC)`` і частковий ``... WHERE is_journal``."""
        sql.create_index(self.env.cr, 'td_genset_reading_genset_ts_idx', self._table, ['genset_id', 'ts DESC'])
        sql.create_index(self.env.cr, 'td_genset_reading_journal_idx', self._table, ['genset_id', 'ts DESC'],
                         where='is_journal')

    # ------------------------------------------------------------------ compute (W0, працюють)
    @api.depends('fuel_level', 'fuel_sensor_ohm')
    def _compute_fuel_liters(self):
        """Літри: калібрування (``genset._liters_from_ohm``, W4) або ``round(fuel_level / 100 × tank_volume_l)``.

        Залежить лише від полів знімка: зміна об'єму бака/калібрування НЕ перераховує історію автоматично
        (ТР 2.16) — для цього ``td.genset.action_recompute_liters``. Значення, передане в ``create``
        (``_derive``), має пріоритет (поле захищене від перерахунку під час створення).
        """
        for reading in self:
            genset = reading.genset_id
            liters = None
            if genset.fuel_calibrated and reading.fuel_sensor_ohm:
                liters = genset._liters_from_ohm(reading.fuel_sensor_ohm)
            if liters is not None:
                reading.fuel_liters = liters
                reading.fuel_source = 'ohm'
            else:
                reading.fuel_liters = round((reading.fuel_level or 0.0) / 100.0 * (genset.tank_volume_l or 0.0))
                reading.fuel_source = 'pct'

    @api.depends('run_hours', 'run_minutes')
    def _compute_run_hours_total(self):
        for reading in self:
            reading.run_hours_total = (reading.run_hours or 0) + (reading.run_minutes or 0) / 60.0

    @api.depends('values_extra')
    def _compute_values_extra_text(self):
        for reading in self:
            reading.values_extra_text = json.dumps(reading.values_extra, ensure_ascii=False, sort_keys=True) \
                if reading.values_extra else False

    # ------------------------------------------------------------------ інтерфейси W1 (заглушки)
    @api.model
    def _create_from_payload(self, genset, payloads):
        """Ідемпотентно створює знімки сторінки (пропускає наявні ``relay_id``): ``ts``, ``slot_15``,
        ``is_hour``, ``READING_FIELD_MAP``, ``values_extra``, оми (``_extract_sensor_ohms``), похідні (``_derive``).

        :param genset: запис ``td.genset``.
        :param list[dict] payloads: знімки ``/readings`` (``{id, ts, time_utc, hostid, reason, values[, regs, coils]}``).
        :return: створені записи в порядку ``relay_id``.
        TODO: W1 — AC-03, AC-04, AC-06, AC-08, AC-68. Заглушка W0: порожній recordset.
        """
        return self.browse()

    @api.model
    def _derive(self, values, genset):
        """Семантика 1.2: ``controller_mode`` (null → ``unknown``), ``is_running``, ``mains_ok``, ``feed_source``,
        ``alarm_flags``, ``fuel_liters``/``fuel_source`` (калібрування або %).

        :param dict values: ``values`` знімка (вже з омами).
        :return: dict значень похідних полів.
        TODO: W1 — AC-06, AC-07, AC-69. Заглушка W0: ``{}``.
        """
        return {}

    @api.model
    def _extract_sensor_ohms(self, payload):
        """Оми з ключів ``fuel_level_sensor_ohm``/``water_temp_sensor_ohm``/``oil_pressure_sensor_ohm`` (≥ 1.1.3),
        інакше з ``payload["regs"]["22"|"18"|"20"] / 10`` (raw=1, 1.1.1); решта ``regs``/``coils`` відкидається.

        :return: ``{fuel_sensor_ohm, water_temp_sensor_ohm, oil_pressure_sensor_ohm}`` (None — немає даних).
        TODO: W1 — AC-68. Заглушка W0: усі ``None``.
        """
        return {name: None for name in SENSOR_OHM_SOURCES}

    @api.model
    def _mark_journal(self, genset, slots):
        """Один SQL ``UPDATE``: ``is_journal = True`` для останнього знімка кожного слота, ``False`` для решти.

        :param set slots: значення ``slot_15`` (datetime UTC), зачеплені сторінкою.
        TODO: W1 — AC-08. Заглушка W0: нічого не робить.
        """
        return None

    @api.model
    def _cron_cleanup(self):
        """Cron ``cron_cleanup`` (1 день, 03:30 Kyiv): видалення сирих знімків старших за ``reading_retention_days``
        (крім журнальних і ``reason='change'``) партіями по 10 000; архів винятків старших за 30 днів.

        TODO: W1 — AC-58. Заглушка W0: нічого не робить (успішно).
        """
        return None
