# Part of td_genset (ToDo). Власник файлу: W0 «Каркас».
"""Генератор ``td.genset`` — УСІ поля моделі (SPEC 5.1, ТР 2.3.1 + А.4).

Правило нульових конфліктів (BUILD_PLAN 1.6): поля ``td.genset`` оголошуються лише тут;
методи — у файлах потоків-власників через ``_inherit = 'td.genset'``:

* ``genset_monitoring.py`` (W1) — забір показань, стан зв'язку, ``action_check_relay``, ``action_refresh``;
* ``genset_scheduler.py`` (W2) — планувальник, таймер, тест, кнопки пульта/таймера, ``next_event_text``;
* ``genset_ui.py`` (W3) — ``get_pult_state``, ``current_data_html``, ``timer_progress``, ``is_tech``/``is_admin``, KPI;
* ``genset_fuel.py`` (W4) — KPI палива, калібрування, ТО.

Тут — лише поля, базові обмеження, ``create``/``write`` з хуками, smart-кнопки і ``_notify_bus`` (А.9).
Нове поле, якщо знадобиться потоку, додається В КІНЕЦЬ класу з позначкою потоку.
"""
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError

# --------------------------------------------------------------------------- спільні selection
# Значення — контракт між потоками (SPEC 4, 5, 6; ТР 2.4). Імпортуються іншими файлами модуля.
CONTROLLER_MODES = [
    ('auto', 'Авто'),
    ('manual', 'Ручний'),
    ('stop', 'Стоп'),
    ('test', 'Тест'),
    ('unknown', 'Невідомо'),
]
GENSET_STATUS = [
    ('0', 'Очікування'),
    ('1', 'Передпусковий підігрів'),
    ('2', 'Подача палива'),
    ('3', 'Прокрутка стартером'),
    ('4', 'Пауза між спробами пуску'),
    ('5', 'Безпечний пуск'),
    ('6', 'Холостий хід'),
    ('7', 'Прогрів'),
    ('8', 'Очікування навантаження'),
    ('9', 'Нормальна робота'),
    ('10', 'Охолодження'),
    ('11', 'Холостий хід перед зупинкою'),
    ('12', 'Зупинка (ETS)'),
    ('13', 'Очікування зупинки'),
    ('14', 'Невдала зупинка'),
    ('15', 'Після зупинки'),
]
GENSET_STAGES = [
    ('standby', 'Очікування'),
    ('start', 'Пуск'),
    ('run', 'Робота'),
    ('stop', 'Зупинка'),
]
FEED_SOURCES = [
    ('mains', 'Мережа'),
    ('genset', 'Генератор'),
    ('none', 'Немає живлення'),
]
LINK_STATES = [
    ('online', 'Онлайн'),
    ('offline', "Немає зв'язку"),
    ('none', 'Не підключено'),
]
CONTROL_SOURCES = [
    ('schedule', 'Розклад'),
    ('timer', 'Таймер'),
    ('manual', 'Вручну'),
    ('test', 'Тест'),
    ('external', 'Не з Odoo'),
    ('none', 'Ніхто'),
]
TEST_MODES = [
    ('load', 'З навантаженням'),
    ('idle', 'Без навантаження (Ручний + Пуск)'),
]
FUEL_SOURCES = [
    ('pct', 'За % контролера'),
    ('ohm', 'За датчиком (Ом)'),
]
MAINT_STATES = [
    ('ok', 'У нормі'),
    ('due', 'Скоро ТО'),
    ('overdue', 'Прострочено'),
]
# genset_status → етап статусбару (SPEC 4: 0 → standby; 1–7 → start; 8–9 → run; 10–15 → stop)
STAGE_BY_STATUS = {str(code): ('standby' if code == 0 else 'start' if code <= 7 else 'run' if code <= 9 else 'stop')
                   for code in range(16)}
# Типи повідомлень bus (А.9)
BUS_KINDS = ('reading', 'link', 'command', 'alarm', 'timer', 'test', 'schedule', 'status')

FUEL_HINT = 'Точність датчика 1 % ≈ 1,45 L; з калібруванням за омами ≈ 0,1–0,2 L.'


class TdGenset(models.Model):
    _name = 'td.genset'
    _description = 'Генератор'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'bus.listener.mixin']
    _rec_name = 'name'
    _order = 'name'

    # ------------------------------------------------------------------ картка
    name = fields.Char(
        string='Назва', required=True, tracking=True,
        help="Назва генератора — зазвичай за адресою об'єкта («Садова вулиця»).")
    active = fields.Boolean(
        string='Активний', default=True,
        help='Архівація генератора архівує і його обладнання ТО (ТР 2.9).')
    address = fields.Char(
        string='Адреса',
        help="Адреса об'єкта, де стоїть генератор.")
    company_id = fields.Many2one(
        'res.company', string='Компанія', default=lambda self: self.env.company,
        help='Компанія генератора. Record rules немає: усі групи модуля бачать усі генератори.')
    user_id = fields.Many2one(
        'res.users', string='Відповідальний', tracking=True, domain=[('share', '=', False)],
        help="Відповідальний за об'єкт: виконавець заявок ТО за замовчуванням.")
    controller_model_id = fields.Many2one(
        'td.genset.controller.model', string='Модель контролера', required=True, ondelete='restrict',
        help="Модель контролера (довідник). Ознака «Є автомат мережі» ховає кнопку «Автомат мережі» (1.5-29).")
    power_kw = fields.Float(
        string='Номінальна потужність, kW', required=True,
        help='Номінальна потужність. Від неї рахується «% від номіналу» в аналітиці.')
    tank_volume_l = fields.Float(
        string="Об'єм бака, L", required=True, default=145.0,
        help="Об'єм бака, L. Контролер дає рівень у % (03H 0021): літри = рівень × об'єм бака, "
             "якщо калібрування датчика не заповнене.")
    fuel_type = fields.Selection(
        [('diesel', 'Дизель')], string='Паливо', default='diesel',
        help='Тип палива.')
    maint_first_hours = fields.Integer(
        string='Перше ТО, мотогодин',
        default=lambda self: self._default_from_config('maint_first_hours_default', 30),
        help='Перше ТО (обкатка) — через скільки мотогодин. За замовчуванням — з налаштувань модуля.')
    maint_interval_hours = fields.Integer(
        string='Далі кожні, мотогодин',
        default=lambda self: self._default_from_config('maint_interval_hours_default', 250),
        help='Інтервал ТО в мотогодинах; поруч — інтервал у місяцях: що настане раніше.')
    maint_interval_months = fields.Integer(
        string='або раз на, міс.',
        default=lambda self: self._default_from_config('maint_interval_months_default', 12),
        help='Інтервал ТО в місяцях; що настане раніше — мотогодини чи місяці.')
    commissioning_date = fields.Date(
        string='Введено в експлуатацію',
        help='Дата введення в експлуатацію: відлік ТО за місяцями до першого закриття заявки (ТР 2.9).')

    # ------------------------------------------------------------------ підключення до ретранслятора
    relay_hostid = fields.Char(
        string='ID модуля (hostid)', index='btree', size=24,
        help='ID модуля CMM366B (hostid, 24 символи). Передається в кожному запиті до ретранслятора; '
             'один генератор на модуль.')
    relay_note = fields.Text(
        string='Підключення модуля (примітка)',
        help='Довідково: як модуль підключено (USB, 4G …).')
    relay_enabled = fields.Boolean(
        string='Опитувати ретранслятор', default=False, tracking=True,
        help='Стоп-кран етапу 1: без нього cron забору й планувальник генератор пропускають.')
    commands_allowed = fields.Boolean(
        string='Дозволити команди', default=False, tracking=True, groups='td_genset.group_tech',
        help='Стоп-кран етапу 2: вмикається після перевірки на стенді. Вимкнено — POST /commands не '
             'надсилається (AC-66).')
    catchup_from_date = fields.Date(
        string='Починати історію з',
        default=lambda self: fields.Date.context_today(self) - timedelta(days=30),
        help='Глибина першого догону: курсор ставиться на перший знімок не старший за цю дату (А.7).')
    equipment_id = fields.Many2one(
        'maintenance.equipment', string='Обладнання ТО', readonly=True, ondelete='set null', copy=False,
        help='Обладнання «Обслуговування», створюється разом з генератором (ТР 2.9).')
    readings_cursor = fields.Integer(
        string='Курсор знімків', default=0, readonly=True, copy=False,
        help='since для GET /readings; зберігається в одній транзакції зі знімками сторінки (AC-04).')
    commands_cursor = fields.Integer(
        string='Курсор журналу команд', default=0, readonly=True, copy=False,
        help='since для звірки GET /commands (журнал ретранслятора).')
    cloud_cmd_last_utc = fields.Datetime(
        string='Остання команда з хмари', readonly=True, copy=False,
        help='Час останнього запису /status.cloud_commands_seen — детектор «керування не з Odoo».')
    last_reading_id = fields.Many2one(
        'td.genset.reading', string='Останній знімок', readonly=True, ondelete='set null', copy=False,
        help='Останній збережений знімок показань.')
    last_reading_at = fields.Datetime(
        string='Час останнього знімка', related='last_reading_id.ts', store=True, readonly=True,
        help='Час останнього знімка (UTC у базі). «N с тому» рахується на клієнті.')
    link_state = fields.Selection(
        LINK_STATES, string="Зв'язок", readonly=True, tracking=True, default='none', copy=False,
        help="Зв'язок з модулем CMM366B: «Онлайн», якщо модуль на зв'язку і знімки надходять не довше, "
             "ніж «Зв'язок втрачено через» у налаштуваннях (2.8.6).")
    link_changed_at = fields.Datetime(
        string="Зв'язок з", readonly=True, copy=False,
        help="Коли змінився стан зв'язку.")

    # ------------------------------------------------------------------ /status ретранслятора
    relay_online = fields.Boolean(
        string='Модуль онлайн (ретранслятор)', readonly=True, copy=False,
        help='/status devices[].online: модуль щось надсилав за останні 90 с.')
    relay_seconds_since_seen = fields.Integer(
        string='Модуль бачили, с тому', readonly=True, copy=False,
        help='/status devices[].seconds_since_seen.')
    relay_long_connection = fields.Boolean(
        string="Довге з'єднання модуля", readonly=True, copy=False,
        help="/status devices[].long_connection: без довгого з'єднання команди неможливі.")
    relay_commands_enabled = fields.Boolean(
        string='Команди дозволено на ретрансляторі', readonly=True, copy=False,
        help='/status relay.commands_enabled (RELAY_COMMANDS_ENABLED).')
    relay_commands_ready = fields.Boolean(
        string='Ретранслятор готовий до команд', readonly=True, copy=False,
        help="/status devices[].commands_ready: команди дозволено, є довге з'єднання і відомий формат.")
    relay_version = fields.Char(
        string='Версія ретранслятора', readonly=True, copy=False,
        help='/status relay.version (1.1.1; з 1.1.3 — оми датчиків і версії контролера в знімках).')
    relay_registers_known = fields.Integer(
        string='Регістрів в образі', readonly=True, copy=False,
        help='/status devices[].registers_known (норма 55; 0 — дані не розбираються).')
    relay_coils_known = fields.Integer(
        string='Сигналів в образі', readonly=True, copy=False,
        help='/status devices[].coils_known (норма 80; 0 — дані не розбираються).')
    relay_time_utc = fields.Datetime(
        string='Час ретранслятора', readonly=True, copy=False,
        help='/status relay.time_utc — для звірки годинника.')
    relay_snapshot_sec = fields.Integer(
        string='Інтервал знімків, с', readonly=True, copy=False,
        help='/status relay.snapshot_sec — плановий інтервал знімків.')

    # ------------------------------------------------------------------ стан з останнього знімка (2.16)
    controller_mode = fields.Selection(
        CONTROLLER_MODES, string='Режим', readonly=True, tracking=True, copy=False,
        help='Режим контролера з сигналів 01H 0040–0043; змінюється командами з пульта. '
             'null у знімку → «Невідомо» (команди не підтверджуються).')
    genset_status = fields.Selection(
        GENSET_STATUS, string='Стан агрегату', readonly=True, copy=False,
        help='Стан агрегату з контролера, 03H 0034 (таблиця 5.3 relay_api.md).')
    genset_stage = fields.Selection(
        GENSET_STAGES, string='Етап', compute='_compute_genset_stage', store=True, copy=False,
        help='Етап для статусбару: 0 → Очікування; 1–7 → Пуск; 8–9 → Робота; 10–15 → Зупинка '
             '(14 «Невдала зупинка» — червоним).')
    genset_status_delay = fields.Integer(
        string='Відлік стану, с', readonly=True, copy=False,
        help='Відлік поточного стану агрегату, 03H 0035.')
    is_running = fields.Boolean(
        string='Працює', readonly=True, copy=False,
        help='genset_status ∉ {0, 15} або оберти > 0; 14 «Невдала зупинка» — теж «працює» (1.2).')
    mains_ok = fields.Boolean(
        string='Є мережа', readonly=True, copy=False,
        help='Сигнал 01H 0065 «Мережа в нормі» (не mains_status: при нормальній мережі він = 2).')
    feed_source = fields.Selection(
        FEED_SOURCES, string="Живлення об'єкта", readonly=True, copy=False,
        help="Від чого живиться об'єкт: 01H 0006 «Мережа під навантаженням» → Мережа, "
             "0007 «Генератор під навантаженням» → Генератор, обидва вимкнені → Немає живлення.")
    gen_on_load = fields.Boolean(
        string='Автомат генератора замкнений', readonly=True, copy=False,
        help='Сигнал 01H 0007 «Генератор під навантаженням» — положення автомата генератора.')
    mains_on_load = fields.Boolean(
        string='Автомат мережі замкнений', readonly=True, copy=False,
        help='Сигнал 01H 0006 «Мережа під навантаженням» — положення автомата мережі.')
    remote_lock = fields.Boolean(
        string='Блокування на контролері', readonly=True, tracking=True, copy=False,
        help='Сигнал 01H 0004: дистанційне керування заблоковано на панелі — команди не надсилаються (ФВ-15).')
    common_alarm = fields.Boolean(
        string='Загальна тривога', readonly=True, copy=False,
        help='Сигнал 01H 0000.')
    common_warning = fields.Boolean(
        string='Загальне попередження', readonly=True, copy=False,
        help='Сигнал 01H 0001.')
    common_shutdown = fields.Boolean(
        string='Загальна аварійна зупинка', readonly=True, copy=False,
        help='Сигнал 01H 0002.')
    speed = fields.Float(
        string='Оберти, RPM', readonly=True, copy=False,
        help='Оберти двигуна, 03H 0023. 0 — немає даних або стоїть.')
    active_power = fields.Float(
        string='Активна потужність, kW', readonly=True, copy=False,
        help='Активна потужність (знакова), 03H 0026.')
    oil_pressure = fields.Float(
        string='Тиск оливи, kPa', readonly=True, copy=False,
        help='Тиск оливи, 03H 0019. 32766 на контролері — «немає даних».')
    water_temp = fields.Float(
        string='Температура ОР, °C', readonly=True, copy=False,
        help='Температура охолоджувальної рідини, 03H 0017.')
    battery_v = fields.Float(
        string='Напруга АКБ, V', readonly=True, copy=False,
        help='Напруга АКБ, 03H 0024.')
    dplus_v = fields.Float(
        string='Напруга D+, V', readonly=True, copy=False,
        help='Напруга D+ (зарядний генератор), 03H 0025.')
    fuel_level = fields.Float(
        string='Рівень палива, %', readonly=True, copy=False,
        help='Рівень палива з контролера, 03H 0021 (%). ' + FUEL_HINT)
    fuel_liters = fields.Float(
        string='Паливо в баку, L', readonly=True, copy=False,
        help="Паливо в баку з останнього знімка: за калібруванням датчика (Ом → L) або % × об'єм бака. " + FUEL_HINT)
    fuel_source = fields.Selection(
        FUEL_SOURCES, string='Літри за', readonly=True, copy=False,
        help='Звідки взято літри останнього знімка: за % контролера чи за калібруванням датчика (ФВ-31).')
    fuel_sensor_ohm = fields.Float(
        string='Опір датчика палива, Ом', readonly=True, digits=(16, 1), copy=False,
        help='Опір датчика рівня палива, 03H 0022 (ключ fuel_level_sensor_ohm з 1.1.3 або raw=1), крок 0,1 Ом.')
    water_temp_sensor_ohm = fields.Float(
        string='Опір датчика температури ОР, Ом', readonly=True, digits=(16, 1), copy=False,
        help='Опір датчика температури, 03H 0018 — показ і діагностика обриву датчика.')
    oil_pressure_sensor_ohm = fields.Float(
        string='Опір датчика тиску оливи, Ом', readonly=True, digits=(16, 1), copy=False,
        help='Опір датчика тиску оливи, 03H 0020 — показ і діагностика обриву датчика.')
    mains_uab = fields.Float(
        string='Мережа UAB, V', readonly=True, copy=False,
        help='Лінійна напруга мережі, 03H 0003.')
    mains_ubc = fields.Float(
        string='Мережа UBC, V', readonly=True, copy=False,
        help='Лінійна напруга мережі, 03H 0004.')
    mains_uca = fields.Float(
        string='Мережа UCA, V', readonly=True, copy=False,
        help='Лінійна напруга мережі, 03H 0005.')
    mains_freq = fields.Float(
        string='Частота мережі, Hz', readonly=True, copy=False,
        help='Частота мережі, 03H 0006.')
    gen_uab = fields.Float(
        string='Генератор UAB, V', readonly=True, copy=False,
        help='Лінійна напруга генератора, 03H 0010.')
    gen_ubc = fields.Float(
        string='Генератор UBC, V', readonly=True, copy=False,
        help='Лінійна напруга генератора, 03H 0011.')
    gen_uca = fields.Float(
        string='Генератор UCA, V', readonly=True, copy=False,
        help='Лінійна напруга генератора, 03H 0012.')
    gen_freq = fields.Float(
        string='Частота генератора, Hz', readonly=True, copy=False,
        help='Частота генератора, 03H 0013.')
    current_a = fields.Float(
        string='Струм фази A, A', readonly=True, copy=False,
        help='Струм навантаження генератора, фаза A, 03H 0014.')
    current_b = fields.Float(
        string='Струм фази B, A', readonly=True, copy=False,
        help='Струм навантаження генератора, фаза B, 03H 0015.')
    current_c = fields.Float(
        string='Струм фази C, A', readonly=True, copy=False,
        help='Струм навантаження генератора, фаза C, 03H 0016.')
    power_factor = fields.Float(
        string='cos φ', readonly=True, copy=False,
        help='Коефіцієнт потужності (знаковий), 03H 0029.')
    load_pct = fields.Float(
        string='Навантаження, %', readonly=True, copy=False,
        help='Завантаження генератора від номіналу, 03H 0055.')
    run_hours = fields.Integer(
        string='Мотогодини, год', readonly=True, copy=False,
        help='Мотогодини (накопичувальні), 03H 0042–0043.')
    run_minutes = fields.Integer(
        string='Мотогодини, хв', readonly=True, copy=False,
        help='Хвилини мотогодин (накопичувальні), 03H 0044.')
    run_hours_total = fields.Float(
        string='Мотогодини всього', readonly=True, copy=False,
        help='run_hours + run_minutes / 60 — основа відліку ТО.')
    start_count = fields.Integer(
        string='Кількість пусків', readonly=True, copy=False,
        help='Кількість пусків (накопичувальна), 03H 0046–0047.')
    energy_kwh = fields.Float(
        string='Вироблено всього, kWh', readonly=True, copy=False,
        help='Вироблено енергії генератором (накопичувальна), 03H 0048–0049.')
    last_values_json = fields.Json(
        string='Усі значення', readonly=True, copy=False,
        help='values останнього знімка як є (null = немає даних) — для вкладки «Поточні дані».')

    # ------------------------------------------------------------------ калібрування датчика палива (ФВ-31)
    fuel_calibration_ids = fields.One2many(
        'td.genset.fuel.calibration', 'genset_id', string='Калібрування датчика палива',
        help='Точки Ом → L. Заповніть за кривою датчика в налаштуваннях контролера (Ом → % × об\'єм бака) '
             'або за реальними заправками (Ом до/після відомого об\'єму).')
    fuel_calibrated = fields.Boolean(
        string='Калібрування заповнено', compute='_compute_fuel_calibrated', store=True,
        help='Є щонайменше 2 точки калібрування — літри рахуються за омами датчика.')

    # ------------------------------------------------------------------ керування і планувальник
    control_source = fields.Selection(
        CONTROL_SOURCES, string='Керує', readonly=True, tracking=True, copy=False,
        help='Хто зараз керує режимом: розклад, таймер роботи поза графіком, людина з пульта, тест '
             'або хтось не з Odoo (панель, застосунок SmartGen).')
    next_event_text = fields.Char(
        string='Наступна подія', compute='_compute_next_event_text',
        help='Наступна дія розкладу, кінець таймера або тесту. Обчислюється з розкладу, днів-винятків, '
             'таймера і тесту (ФВ-23).')
    sched_in_window = fields.Boolean(
        string='У вікні розкладу', readonly=True, copy=False,
        help='Останній обчислений стан розкладу — команди лише на переходах.')
    sched_last_eval_at = fields.Datetime(
        string='Остання оцінка розкладу', readonly=True, copy=False,
        help='Коли планувальник востаннє оцінив розклад — детектор пропущеного переходу (А.6).')
    timer_end = fields.Datetime(
        string='Таймер до', readonly=True, copy=False,
        help='Кінець роботи поза графіком. Порожньо — таймера немає.')
    timer_started_at = fields.Datetime(
        string='Таймер запущено о', readonly=True, copy=False,
        help='Коли запущено таймер.')
    timer_user_id = fields.Many2one(
        'res.users', string='Таймер запустив', readonly=True, copy=False, ondelete='set null',
        help='Хто запустив таймер.')
    test_end = fields.Datetime(
        string='Тест до', readonly=True, copy=False,
        help='Кінець тестового пуску.')
    test_mode = fields.Selection(
        TEST_MODES, string='Тест', readonly=True, copy=False,
        help='Варіант тесту: з навантаженням (режим Тест) або без навантаження (Ручний + Пуск).')
    test_timer_paused_left = fields.Integer(
        string='Пауза таймера під час тесту, с', readonly=True, copy=False,
        help='Скільки лишалось таймеру, коли почався тест; після тесту таймер продовжується (ФВ-22).')
    schedule_line_ids = fields.One2many(
        'td.genset.schedule', 'genset_id', string='Розклад',
        help='Вікна роботи в режимі Авто за днями тижня (київський час).')
    exception_ids = fields.One2many(
        'td.genset.schedule.exception', 'genset_id', string='Дні-винятки',
        help='Дати, коли розклад не діє або діє інший час.')
    command_ids = fields.One2many(
        'td.genset.command', 'genset_id', string='Команди',
        help='Журнал команд генератора.')
    alarm_ids = fields.One2many(
        'td.genset.alarm', 'genset_id', string='Тривоги', domain=[('state', '!=', 'cleared')],
        help='Активні та прийняті тривоги генератора.')
    event_ids = fields.One2many(
        'td.genset.event', 'genset_id', string='Події',
        help='Події генератора: робота, відключення мережі, заправки, тривоги, зв\'язок.')

    # ------------------------------------------------------------------ smart-кнопки, ТО
    reading_count = fields.Integer(
        string='Показань', compute='_compute_counts',
        help='Кількість знімків показань генератора.')
    alarm_count = fields.Integer(
        string='Тривог', compute='_compute_counts',
        help='Кількість активних і прийнятих (не знятих) тривог.')
    command_count = fields.Integer(
        string='Команд', compute='_compute_counts',
        help='Кількість команд у журналі.')
    canister_liters = fields.Float(
        string='Паливо в каністрах, L', compute='_compute_fuel_kpi',
        help='Скільки палива в активних каністрах (smart-кнопка «У каністрах»).')
    maint_hours_left = fields.Float(
        string='До ТО, мотогодин', compute='_compute_maint',
        help='Скільки мотогодин лишилось до наступного ТО за регламентом (ТР 2.9).')
    maint_due_date = fields.Date(
        string='ТО не пізніше', compute='_compute_maint',
        help='Дата наступного ТО за місяцями регламенту.')
    maint_state = fields.Selection(
        MAINT_STATES, string='Стан ТО', compute='_compute_maint',
        help='У нормі / Скоро ТО / Прострочено (мотогодини ≤ 0 або дата настала).')

    # ------------------------------------------------------------------ KPI палива (вкладка «Паливо», W4)
    fuel_in_canisters_l = fields.Float(
        string='У каністрах, L', compute='_compute_fuel_kpi',
        help='Σ літрів активних каністр.')
    fuel_total_l = fields.Float(
        string='Разом палива, L', compute='_compute_fuel_kpi',
        help='Паливо в баку + у каністрах.')
    fuel_hours_left = fields.Float(
        string='Вистачить на, год', compute='_compute_fuel_kpi',
        help='(бак + каністри) / витрата L/год за 30 днів, якщо витрата > 0.')
    fuel_min_stock_ok = fields.Boolean(
        string='Запас у нормі', compute='_compute_fuel_kpi',
        help='Запас у каністрах не менший за мінімальний з налаштувань.')
    fuel_used_7d_l = fields.Float(
        string='Витрачено за 7 днів, L', compute='_compute_fuel_kpi',
        help='−Σ зміни палива подій «Робота» за 7 днів.')
    fuel_used_30d_l = fields.Float(
        string='Витрачено за 30 днів, L', compute='_compute_fuel_kpi',
        help='−Σ зміни палива подій «Робота» за 30 днів.')
    fuel_rate_lph_7d = fields.Float(
        string='Витрата за 7 днів, L/год', compute='_compute_fuel_kpi',
        help='Витрачено / години роботи за 7 днів.')
    fuel_rate_lph_30d = fields.Float(
        string='Витрата за 30 днів, L/год', compute='_compute_fuel_kpi',
        help='Витрачено / години роботи за 30 днів.')
    fuel_rate_lpkwh_7d = fields.Float(
        string='Питома витрата за 7 днів, L/kWh', compute='_compute_fuel_kpi',
        help='Витрачено / вироблено kWh за 7 днів.')
    fuel_rate_lpkwh_30d = fields.Float(
        string='Питома витрата за 30 днів, L/kWh', compute='_compute_fuel_kpi',
        help='Витрачено / вироблено kWh за 30 днів.')
    fuel_per_day_7d = fields.Float(
        string='Витрата на добу (7 днів), L', compute='_compute_fuel_kpi',
        help='Витрачено за 7 днів / 7.')
    fuel_per_day_30d = fields.Float(
        string='Витрата на добу (30 днів), L', compute='_compute_fuel_kpi',
        help='Витрачено за 30 днів / 30.')
    fuel_cost_7d = fields.Float(
        string='Вартість палива за 7 днів', compute='_compute_fuel_kpi',
        help='Витрачено × остання ціна надходження за 7 днів.')
    fuel_cost_30d = fields.Float(
        string='Вартість палива за 30 днів', compute='_compute_fuel_kpi',
        help='Витрачено × остання ціна надходження за 30 днів.')

    # ------------------------------------------------------------------ KPI аналітики (вкладка «Аналітика»)
    kpi_run_hours_7d = fields.Float(
        string='Мотогодини за 7 днів', compute='_compute_kpi',
        help='Σ тривалості подій «Робота генератора» за 7 днів.')
    kpi_run_hours_30d = fields.Float(
        string='Мотогодини за 30 днів', compute='_compute_kpi',
        help='Σ тривалості подій «Робота генератора» за 30 днів.')
    kpi_starts_7d = fields.Integer(
        string='Пусків за 7 днів', compute='_compute_kpi',
        help='Кількість подій «Робота генератора» за 7 днів.')
    kpi_starts_30d = fields.Integer(
        string='Пусків за 30 днів', compute='_compute_kpi',
        help='Кількість подій «Робота генератора» за 30 днів.')
    kpi_energy_kwh_7d = fields.Float(
        string='Вироблено за 7 днів, kWh', compute='_compute_kpi',
        help='Σ енергії подій «Робота генератора» за 7 днів.')
    kpi_energy_kwh_30d = fields.Float(
        string='Вироблено за 30 днів, kWh', compute='_compute_kpi',
        help='Σ енергії подій «Робота генератора» за 30 днів.')
    kpi_outages_7d = fields.Integer(
        string='Відключень за 7 днів', compute='_compute_kpi',
        help='Кількість подій «Відключення мережі» за 7 днів.')
    kpi_outages_30d = fields.Integer(
        string='Відключень за 30 днів', compute='_compute_kpi',
        help='Кількість подій «Відключення мережі» за 30 днів.')
    kpi_covered_pct_7d = fields.Float(
        string='Покрито генератором за 7 днів, %', compute='_compute_kpi',
        help='Частка часу відключень, коли об\'єкт живився від генератора, за 7 днів.')
    kpi_covered_pct_30d = fields.Float(
        string='Покрито генератором за 30 днів, %', compute='_compute_kpi',
        help='Частка часу відключень, коли об\'єкт живився від генератора, за 30 днів.')
    kpi_avg_load_pct_7d = fields.Float(
        string='Середнє навантаження за 7 днів, %', compute='_compute_kpi',
        help='Середнє навантаження під час роботи за 7 днів.')
    kpi_avg_load_pct_30d = fields.Float(
        string='Середнє навантаження за 30 днів, %', compute='_compute_kpi',
        help='Середнє навантаження під час роботи за 30 днів.')
    kpi_first_try_pct_7d = fields.Float(
        string='Пуск з 1-ї спроби за 7 днів, %', compute='_compute_kpi',
        help='Частка пусків з першої спроби за 7 днів.')
    kpi_first_try_pct_30d = fields.Float(
        string='Пуск з 1-ї спроби за 30 днів, %', compute='_compute_kpi',
        help='Частка пусків з першої спроби за 30 днів.')
    kpi_crank_battery_min_7d = fields.Float(
        string='АКБ при прокрутці (мін.) за 7 днів, V', compute='_compute_kpi',
        help='Мінімальна напруга АКБ при прокрутці за 7 днів (точність обмежена інтервалом знімків).')
    kpi_crank_battery_min_30d = fields.Float(
        string='АКБ при прокрутці (мін.) за 30 днів, V', compute='_compute_kpi',
        help='Мінімальна напруга АКБ при прокрутці за 30 днів (точність обмежена інтервалом знімків).')

    # ------------------------------------------------------------------ службові поля движка подій (2.8.1, А.4)
    prev_reading_id = fields.Many2one(
        'td.genset.reading', string='Попередній оброблений знімок', readonly=True, ondelete='set null',
        copy=False, help='Службове: знімок P для правил подій.')
    open_run_event_id = fields.Many2one(
        'td.genset.event', string='Відкрита подія «Робота»', readonly=True, ondelete='set null', copy=False,
        help='Службове: відкрита подія роботи генератора.')
    open_outage_event_id = fields.Many2one(
        'td.genset.event', string='Відкрита подія «Відключення»', readonly=True, ondelete='set null',
        copy=False, help='Службове: відкрита подія відключення мережі.')
    open_alarm_codes = fields.Json(
        string='Відкриті коди тривог', readonly=True, copy=False,
        help='Службове: код → id тривоги/події для сигналів контролера.')
    catchup_mode = fields.Boolean(
        string='Режим догону', readonly=True, copy=False,
        help='Службове: забір історії — події створюються, тривоги й сповіщення ні (А.7).')

    # ------------------------------------------------------------------ UI (W3)
    timer_progress = fields.Float(
        string='Прогрес таймера', compute='_compute_timer_progress',
        help='Частка часу таймера, що минула (0–100).')
    current_data_html = fields.Html(
        string='Поточні дані', compute='_compute_current_data_html', sanitize=False,
        help='Таблиця всіх значень останнього знімка з підписами, омами датчиків і блоком «Ретранслятор».')
    is_tech = fields.Boolean(
        string='Я тех. адміністратор', compute='_compute_is_tech',
        help='Поточний користувач у групі «Генератори: Тех. адміністратор» — видимість кнопок.')
    is_admin = fields.Boolean(
        string='Я адміністратор', compute='_compute_is_admin',
        help='Поточний користувач у групі «Генератори: Адміністратор» — редагування розкладу.')

    _sql_constraints = [
        ('relay_hostid_uniq', 'unique(relay_hostid)', 'Такий hostid уже є в іншого генератора.'),
    ]

    # ================================================================== defaults, обмеження
    @api.model
    def _default_from_config(self, field_name, fallback):
        config = self.env.ref('td_genset.config_main', raise_if_not_found=False)
        value = config.sudo()[field_name] if config else False
        return value or fallback

    @api.constrains('tank_volume_l', 'power_kw')
    def _check_positive_volume_power(self):
        for genset in self:
            if genset.tank_volume_l <= 0:
                raise ValidationError(_("Об'єм бака має бути більшим за 0."))
            if genset.power_kw <= 0:
                raise ValidationError(_('Номінальна потужність має бути більшою за 0.'))

    def _td_check_group(self, group_xmlid):
        """Перевірка групи для кнопок і прямих RPC (SPEC 7, А.10): інакше ``AccessError``.

        Технічні записи після цієї перевірки пишуться через ``sudo()``. Суперкористувач (cron) проходить.
        """
        if self.env.su or self.env.user.has_group(group_xmlid):
            return True
        group = self.env.ref(group_xmlid, raise_if_not_found=False)
        raise AccessError(_('Ця дія доступна лише групі «%(group)s».', group=group.name if group else group_xmlid))

    # ================================================================== compute (W0, працюють)
    @api.depends('genset_status')
    def _compute_genset_stage(self):
        for genset in self:
            genset.genset_stage = STAGE_BY_STATUS.get(genset.genset_status) if genset.genset_status else False

    def _compute_counts(self):
        reading_data = dict(self.env['td.genset.reading']._read_group(
            [('genset_id', 'in', self.ids)], ['genset_id'], ['__count']))
        alarm_data = dict(self.env['td.genset.alarm']._read_group(
            [('genset_id', 'in', self.ids), ('state', '!=', 'cleared')], ['genset_id'], ['__count']))
        command_data = dict(self.env['td.genset.command']._read_group(
            [('genset_id', 'in', self.ids)], ['genset_id'], ['__count']))
        for genset in self:
            genset.reading_count = reading_data.get(genset, 0)
            genset.alarm_count = alarm_data.get(genset, 0)
            genset.command_count = command_data.get(genset, 0)

    # ================================================================== CRUD з хуками
    @api.model_create_multi
    def create(self, vals_list):
        gensets = super().create(vals_list)
        # TODO: W4 — _ensure_equipment створює maintenance.equipment (ТР 2.9, AC-53)
        gensets._ensure_equipment()
        return gensets

    def write(self, vals):
        res = super().write(vals)
        if {'name', 'user_id', 'active', 'company_id'} & set(vals):
            # TODO: W4 — синхронізація/архівація обладнання ТО (ТР 2.9)
            self._ensure_equipment()
        return res

    # ================================================================== bus (А.9) — працює з W0
    def _notify_bus(self, kind, payload=None):
        """Надіслати ``td_genset.update`` у канал запису генератора (А.9) — єдина точка надсилання.

        :param str kind: ``reading|link|command|alarm|timer|test|schedule|status``
        :param dict payload: додаткові ключі (``command_id``, ``state``, ``note`` …); без секретів.
        Повідомлення надсилається після коміту транзакції (``bus.bus._sendone`` — postcommit).
        """
        if kind not in BUS_KINDS:
            raise ValueError("Unknown td_genset bus kind: %r" % (kind,))
        at = fields.Datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')
        for genset in self:
            message = {'genset_id': genset.id, 'kind': kind, 'at': at}
            if payload:
                message.update(payload)
            genset._bus_send('td_genset.update', message)

    # ================================================================== меню і smart-кнопки (W0, працюють)
    @api.model
    def action_open_main(self):
        """Пункт меню «Генератор» (ТР 2.10): один генератор — його форма, інакше — список."""
        action = self.env['ir.actions.act_window']._for_xml_id('td_genset.action_td_genset')
        gensets = self.search([], limit=2)
        if len(gensets) == 1:
            action.update({
                'res_id': gensets.id,
                'view_mode': 'form',
                'views': [(False, 'form')],
            })
        return action

    def _action_open(self, xmlid, domain, context=None):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(xmlid)
        action['domain'] = domain
        action['context'] = dict(context or {}, default_genset_id=self.id)
        return action

    def action_open_readings(self):
        """Smart-кнопка «Показання»: знімки цього генератора (журнал 15 хв за замовчуванням)."""
        return self._action_open('td_genset.action_td_genset_reading', [('genset_id', '=', self.id)],
                                 {'search_default_journal': 1})

    def action_open_events(self):
        """Smart-кнопка «Події» генератора."""
        return self._action_open('td_genset.action_td_genset_event', [('genset_id', '=', self.id)])

    def action_open_alarms(self):
        """Smart-кнопка «Тривоги» генератора (активні й прийняті за замовчуванням)."""
        return self._action_open('td_genset.action_td_genset_alarm', [('genset_id', '=', self.id)],
                                 {'search_default_not_cleared': 1})

    def action_open_commands(self):
        """Smart-кнопка «Команди» — журнал команд генератора."""
        return self._action_open('td_genset.action_td_genset_command', [('genset_id', '=', self.id)])

    def action_open_maintenance(self):
        """Smart-кнопка «До ТО»: заявки ТО обладнання генератора (стандартний maintenance.request)."""
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('maintenance.hr_equipment_request_action')
        action['domain'] = [('equipment_id', '=', self.equipment_id.id)] if self.equipment_id else [('id', '=', 0)]
        action['context'] = {'default_equipment_id': self.equipment_id.id} if self.equipment_id else {}
        return action

    # ------------------------------------------------------------------ W1 «Моніторинг»: додані поля
    relay_last_reading_id = fields.Integer(
        string='Останній знімок на ретрансляторі (id)', readonly=True, copy=False, aggregator=None,
        help='/status devices[].last_reading.id — до цього знімка доганяється історія; верхня межа бінарного '
             'пошуку курсору для першого забору (А.7).')
    relay_last_reading_at = fields.Datetime(
        string='Останній знімок на ретрансляторі', readonly=True, copy=False,
        help="/status devices[].last_reading.time_utc — свіжість даних на ретрансляторі: під час догону історії "
             "зв'язок не вважається втраченим (2.8.6).")
    catchup_stats = fields.Json(
        string='Догон: підсумок', readonly=True, copy=False,
        help='Службове: скільки знімків і подій оброблено в поточному догоні — для підсумку «Догнано історію» (А.7).')

    # ------------------------------------------------------------------ W4 «Паливо і ТО»: додаткові поля
    # (BUILD_PLAN 1.6: нові поля — у кінець класу; обчислення — у genset_fuel.py)
    fuel_canisters_summary = fields.Char(
        string='Каністри за станом', compute='_compute_fuel_kpi',
        help='Скільки активних каністр повних, часткових і порожніх: «6 повних · 1 часткова · 5 порожніх».')
    fuel_min_stock_l = fields.Float(
        string='Мінімальний запас, L', compute='_compute_fuel_kpi',
        help='Мінімальний запас палива в каністрах (Генератори → Налаштування → Паливо).')
    fuel_stock_lack_l = fields.Float(
        string='Бракує до мінімального запасу, L', compute='_compute_fuel_kpi',
        help='Скільки літрів бракує в каністрах до мінімального запасу; 0 — запас у нормі.')
    fuel_recompute_next_id = fields.Integer(
        string='Перерахунок літрів: наступний знімок', readonly=True, copy=False, default=0,
        help='Службове: 0 — перерахунок не триває; інакше фонове завдання продовжить перерахунок літрів зі '
             'знімків з id, меншим за це значення (від свіжіших до старіших, партіями по 10 000; перша партія '
             '— одразу кнопкою «Перерахувати літри», AC-69).')
    maint_next_hours = fields.Float(
        string='Наступне ТО на, мотогодин', compute='_compute_maint',
        help='На яких мотогодинах наступне ТО: «Перше ТО» до першої закритої заявки, далі мотогодини закриття '
             'останньої заявки + «Далі кожні, мотогодин» (ТР 2.9).')
    maint_progress = fields.Float(
        string='Прогрес до ТО, %', compute='_compute_maint',
        help='Яку частку поточного інтервалу ТО вже відпрацьовано, 0–100 %.')
