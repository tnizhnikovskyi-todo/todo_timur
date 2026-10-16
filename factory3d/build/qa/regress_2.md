# Регрессионная QA: проверка исправлений на живом сервере (timur-o19demo)

- Дата проверки: 2026-10-16, около 01:00–01:06 UTC.
- База `odoo`, сервер https://timur-o19demo.todo.ltd, пользователь Administrator (uid 2).
- HTTP-запросов: 59 из 60 (включая авторизацию в каждом из четырёх скриптов).
- Код репозитория не менялся. Модули не ставились и не обновлялись. Ничего не удалялось.
- Все новые записи с префиксом QA-reg- (госномер визита `QA-reg-1`); коллекторы, источники и сценарии не создавались.

## Результаты

| defect | result | evidence |
|---|---|---|
| S-2 (params каталога iot_sim) | PASS | Модуль `factory3d_iot_sim` = 19.0.2.0.1. `f3d.sim.device`: всего 280, params непустые у 106 (было 8). Раскладка каналов 31 ADAM не проверялась (вне списка пунктов). |
| S-3 (данные каталога iot_sim) | PASS | T1 и T2: `unit_id` = 96 (ошибочные 1 и 2 исправлены). Сигналов `infra/pv/PV-INV-n/*` 32, все 32 на своём устройстве PV-INV-n, ни одного на родителе PV-INV. FL-6: driver=passive, state=passive. SMOKE-VENTS: driver=passive, state=passive. Под «unit» понимается поле `unit_id` (Modbus unit id). |
| ST-1 (store_period_s для state-шаблонов) | PASS | `f3d.signal` с module=machine_connect: 205 сигналов. Сигналы шаблонов state/alarm/mode/job (io_state, io_alarm, g_state, g_job, ua_state, ua_mode, ua_alarm, ua_job): 102, у всех `store_period_s` = 300, с 0 осталось 0. Остальные с 0 вне списка шаблонов: mc_state 35 (в CSV store 0 по замыслу, производный сигнал), event 15, job_cmd 15, cmd 2, stacks 1. |
| S-4 (Перевірити зв'язок при пустом url) | PASS | Панель «Пульт емулятора» (`f3d.sim.panel`). При недоступном url (`http://127.0.0.1:9`) action_check дал state=offline. После пустого url тот же action_check дал state=unconfigured, сообщение «Адресу сервісу емулятора не налаштовано». Параметр `factory3d.iot_sim.url` восстановлен: ключа нет, как до теста. |
| S-5 (сценарий с device=NOPE-1) | NOT CHECKED | Сценарий machine_fault, мастер запуска, params `{"device": "NOPE-1"}`. Отказ с UserError: «Команди на емулятор вимкнено стоп-краном factory3d.iot_sim.write_enabled». Это не ошибка устройства: `_sim_require_write()` в `sim_run.py` выполняется раньше `_check_device()` (строки 88–93), поэтому проверка NOPE-1 не достигнута. Run не создан. Для проверки нужен повтор с включённым write_enabled (около 4 HTTP-запросов). |
| V-1 (провайдеры quality, stock, logistics) | PASS | `GET /f3d/viewer/data?sections=quality_checks,products,locations,pickings,docks,sale_orders,purchase_orders` → 200, `meta.errors` = []. Секции с данными: quality_checks (около 1,1 КБ), products (8,2 КБ), pickings (19,6 КБ), sale_orders, locations, docks, purchase_orders. |
| V-2 (codes=../../etc) | PASS | `GET /f3d/viewer/data?codes=../../etc` в залогиненной сессии → 400, `{"error":{"code":"bad_request","message":"Невалідний параметр: codes"}}`. |
| V-3 (snapshot/abc) | PASS | `GET /f3d/viewer/snapshot/abc` → 404, редиректа нет (Location отсутствует). |
| T-5 (405 и icon.png) | PASS | `GET /f3d/telemetry/push` → 405, Content-Type application/json, заголовок `Allow: POST`, тело `{"error":{"code":"method_not_allowed","message":"Дозволено лише POST"}}`. `GET /factory3d_telemetry/static/description/icon.png` → 200, image/png. |
| Y-2 (фильтр «сегодня» КПП и смены) | PASS | Поле `is_today` есть у f3d.yard.visit и f3d.yard.booking, у f3d.energy.day.mixin, f3d.energy.interval, f3d.energy.balance, f3d.energy.alloc, f3d.oee.shift (machine_connect), f3d.viewer.snapshot. Создан визит id 10 (name YV/2026/00010, plate QA-REG-1, arrived_at 2026-10-16 01:05 UTC, день по Киеву 2026-10-16). Поиск `is_today=True` нашёл его. Поиск `is_today=True` по bookings работает без ошибки (0 записей). Проверка выполнена в 01:05 UTC, окно 21–24 UTC не воспроизводилось напрямую. |
| F-1 (группа оповещения и активность на FACP-1) | PASS (с оговоркой) | Группа `factory3d_base.group_f3d_user` (id 82): 6 участников, из них 5 активных. Тревога FA-CUT через `/f3d/telemetry/push` с токеном коллектора QA-FIRE-COL (id 17) и временно переназначенным источником BAC-200-FACP-1 (id 134): ответ 200, changed = fire/groups/FA-CUT/state. `mail.activity` на `f3d.fire.panel` id 1 (FACP-1): 3 шт., создано 01:05:48, «Пожежна тривога: FA-CUT · Розкрій», назначены QA-viewer-nomrp, QA-viewer-mrp, Administrator. Оговорка: активные QA-bms user (тест) и QA-telemetry-user активности не получили, причину не выяснял. Зона возвращена: state=normal, raw_state=quiet. Источник 134 возвращён на collector 1, токен collector 17 отозван. |

## Изменения в базе (для учёта и отката)

- `ir.config_parameter` `factory3d.iot_sim.url`: временно `http://127.0.0.1:9`, затем пусто. Восстановлено: ключа нет, как до теста.
- `f3d.source` id 134 (BAC-200-FACP-1), `collector_id`: 1, затем 17 (QA-FIRE-COL), затем 1. Сейчас 1.
- `f3d.collector` id 17 (QA-FIRE-COL): токен перевыпущен и отозван. Действие записано в чатер коллектора.
- Создан `f3d.yard.visit` id 10 (YV/2026/00010, plate QA-REG-1). Удалять по правилам не стал.
- Создан transient-запись `f3d.sim.run.wizard` (S-5). Запуска run нет, отказ произошёл до создания run.
- Тревога FA-CUT: создано событие тревоги (`f3d.fire.event`), оно не квитировано. Нужно квитирование владельцем.
- Открыты 3 `mail.activity` на FACP-1 (создано 01:05:48). Их нужно закрыть владельцем.

## Что нужно доделать

1. S-5: повторить при включённом `factory3d.iot_sim.write_enabled` (временно, с возвратом) и убедиться, что отказ именно «Невідомий пристрій «NOPE-1»». Этот шаг выходит за лимит 60 HTTP в текущем прогоне.
2. F-1: выяснить, почему QA-bms user и QA-telemetry-user не получили активность при активной группе.
3. S-2: раскладка каналов 31 ADAM на сервере не проверялась.
