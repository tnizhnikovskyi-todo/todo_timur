# QA td_genset
Статус: PARTIAL
Проверено: 24, провалено: 2, не проверено: 7 (2026-10-15, коммит 29a088e)
Дефекты: 3 (критичных: 0)
Мусор в базе: td.genset id 1; maintenance.equipment id 216; f3d.genset.link id 3; maintenance.request id 48 и 49; f3d.source id 136 (подробно ниже)

Сервер: https://timur-o19demo.todo.ltd, БД `odoo`, Odoo 19.0 Enterprise. В каждом вызове коннектора `connection_id = AxI--dg8QCmJAxW_`, в ответах `connection.db == "odoo"`.
Модули: td_genset 19.0.1.0.0 и factory3d_genset 19.0.1.0.0, state = installed, версии совпадают с манифестами. Установка и обновление модулей не делались, код не менялся, ничего не удалено.

## Таблица

| # | AC / сценарий | Способ | Результат | Доказательство |
|---|---|---|---|---|
| 1 | Установка td_genset | connector, ir.module.module | PASS | id 1499, installed, 19.0.1.0.0 |
| 2 | Установка factory3d_genset | connector | PASS | id 1490, installed, 19.0.1.0.0 |
| 3 | Меню: 29 menuitem обоих модулей | connector, ir.model.data → ir.ui.menu | PASS | ids 614–642, включая menu_root, menu_f3d_genset_settings |
| 4 | 26 action windows (list, graph, kanban, мастера) открываются | браузер Chromium, /odoo/action-<id> | PASS | ошибок в DOM нет; graph x7, kanban x1 (Каністри); мастери 935, 936, 937, 939 открываются диалогом |
| 5 | Формы: td.genset/1, f3d.genset.link/3, f3d.genset.profile/1, f3d.genset.event.map/1, настройки (945) | браузер | PASS | ошибок нет |
| 6 | Создание генератора (td.genset) | connector create | PASS | id 1 «QA-genset-GEN-01», equipment 216 создано автоматически, maint_next_hours 250, maint_hours_left 250 |
| 7 | Мотогодини: наработка 260 ч | connector write (СИМУЛЯЦИЯ: поле readonly, запись реле недоступна) | PASS (симуляция) | run_hours_total 260, maint_hours_left -10 |
| 8 | ТО по мотогодинам: просрочка создает заявку | cron 78 «Генератори: розклад, таймер, тест, ескалація» (method_direct_trigger) | FAIL (D1) | maintenance.request 48 «ТО-1 після обкатки (250 мотогодин)», preventive, priority = false, schedule_date = сейчас |
| 9 | Повторный прогон не дублирует заявки | cron 83 повторно | PASS | на equipment 216 только заявки 48 и 49 |
| 10 | Мост: связка genset ↔ equipment (AC-03 и валидации) | connector create / RPC create | PASS | link 3 создан. Негатив: без роли паспорта — ValidationError «роль «—», потрібна «genset»»; код сцены в нижнем регистре — ValidationError про формат |
| 11 | Профиль телеметрии (AC-04, точка) | connector | PASS | профиль 1 «KOHLER-SDMO D700 · SmartGen HGM6120N» подставлен автоматически, fuel_lph_50 = 71.2, fuel_lph_75 = 103.8 |
| 12 | Публикация телеметрии (AC-07, AC-10, частично) | cron 81 «Генератор: публікація показань у телеметрію» | PASS | 26 сигналов у связки 3; f3d.source 136 «Ретранслятор SmartGen (td_genset)» создан; last_publish_ts 21:36:31; last_publish_error пусто |
| 13 | COMM_LOST (R-12): нет данных → заявка | cron 82 (запуск и автоматический) | PASS | заявка 49 «Генератор QA-GENSET-01: втрачено зв'язок з контролером (немає даних 5,3 хв)», priority 2 (см. замечание 1) |
| 14 | Контроллерные события → заявки ТО (AC-12…17, 20, 21) | попытка td.genset.event create | NOT CHECKED | AccessError: «Наразі жодна група не дозволяє цю операцію». События создаются только реле |
| 15 | Показания td.genset.reading (полный путь AC-07…09) | попытка create | NOT CHECKED | AccessError, как в п. 14. Только реле |
| 16 | Viewer: карточка генератора в payload (AC-22, AC-24, присутствие) | HTTP GET /f3d/viewer/data?sections=infra | PASS (присутствие) | infra.cards = {'QA-GENSET-01': …}, infra.genset есть. Строки карточки (14 рядков, AC-22, AC-25) не сверены. Методы провайдера приватные, RPC недоступен, проверено через публичный endpoint |
| 17 | Кроны: method_direct_trigger без ошибок | connector ir.cron | PASS | ids 76, 77, 78, 80, 81, 82, 83 вернули true. ir.logging: WARNING/ERROR с 20:45 нет. Серверный лог не смотрел |
| 18 | Крон 79 «Генератори: чистка» | — | NOT CHECKED | крон удаляет сырые знимки; по правилу «ничего не удалять» не запускался |
| 19 | Права: qa-genset-<роль>, AC-33, AC-59, AC-60 | — | NOT CHECKED | пользователи не создавались (лимит времени) |
| 20 | Настройки моста (AC-09, AC-34) | connector ir.config_parameter | PASS | read_enabled = True, requests_enabled = True, write_enabled = False, offline_min = 5, amf_master = hgm. Кроны 82, 83 active = True по флагу requests_enabled (hooks.py:107–114) |
| 21 | Мапа «Події → ТО» (AC-63, количество) | connector search_count | PASS | 48 строк |
| 22 | HTTP: без сессии и с битой сессией → редирект на вход | HTTP GET /f3d/viewer/data, /f3d/viewer/delta | PASS | 303 на /web/login (data anon, data bad-session, delta anon) |
| 23 | HTTP: JSON-RPC без сессии | HTTP POST /f3d/viewer/cycle_check | PASS | HTTP 200, error code 100 «Odoo Session Expired» |
| 24 | HTTP: валидные запросы с сессией | HTTP GET data, data?sections=infra, parts/manifest.json | PASS | 200 для всех трех (data 568 КБ) |
| 25 | HTTP: невалидные параметры | HTTP GET delta без since, data?codes=<script> | PASS | 400 bad_request для обоих |
| 26 | HTTP: киоск с неверным токеном | HTTP GET /f3d/kiosk/<токен>/data | PASS | 404 |
| 27 | HTTP: /f3d/viewer/snapshot/abc (ожидалось 404) | HTTP GET | FAIL (D3) | 303 на /uk/f3d/viewer/snapshot/abc |
| 28 | HTTP: codes=../../etc | HTTP GET data | PASS (наблюдение D2) | 200 вместо 400, CODE_RE допускает «/» и «.» |
| 29 | Relay /sim/v1/* (AC-06, AC-36…40, AC-47…55), ТК-01…14, ТК-F, ТК-G | — | NOT CHECKED | relay D700 и эмулятор не подключены к серверу |
| 30 | Q-13: td_code пуст в строках мапы | connector | NOT CHECKED | фильтр не прошел (Error в коннекторе), число строк проверено (п. 21) |
| 31 | 3D-просмотр генератора (кнопка «Показать 3D», сцена) | — | NOT CHECKED | в браузере проверены только формы и списки |

Итог: строк 31. Проверено 24 (PASS 22, FAIL 2: п. 8 и п. 27). Не проверено 7: п. 14, 15, 18, 19, 29, 30, 31.

## Дефекты

**D1 (средний, решение менеджера). Просроченное ТО создано без приоритета.**
- Шаги: td.genset id 1, run_hours_total = 260 (ТО-1 при 250 ч); cron 78 «Генератори: розклад, таймер, тест, ескалація».
- Ожидание (AC-19, FR-06, раздел factory3d_genset SPEC): при hours_left = -12 заявка с priority = '3', schedule_date ≈ now, название «…прострочено на 12 мотогодин…».
- Факт: при hours_left = -10 заявка 48 «ТО-1 після обкатки (250 мотогодин)», priority = false. Название не содержит величины просрочки.
- Код: td_genset/models/genset_fuel.py:1177 `_check_maintenance`; grep по `priority` в genset_fuel.py пуст.
- Замечание: по DEC-14 заявки ТО создает td_genset, мост только дописывает сигнал hours (R-09). AC-19 описан для моста. Ни один из путей его, похоже, не выполняет. Нужно решение: кто ставит приоритет и название просрочки.

**D2 (минор, наблюдение). Параметр codes принимает «../../etc».**
- Шаги: GET /f3d/viewer/data?codes=../../etc (с сессией).
- Ожидание: 400, как для codes=<script>.
- Факт: 200 с урезанным payload.
- Код: factory3d_viewer/controllers/viewer.py:18 CODE_RE = `^[A-Za-z0-9/_.\-]{1,64}$` (допускает «.» и «/»). Путь к файлу не используется, поэтому это только валидация шире задуманной.

**D3 (минор, чужой модуль на стыке). Неверный int в маршруте уходит в редирект.**
- Шаги: GET /f3d/viewer/snapshot/abc с сессией.
- Ожидание: 404.
- Факт: 303 на /uk/f3d/viewer/snapshot/abc.
- Код: factory3d_viewer/controllers/viewer.py:235, маршрут `<int:snapshot_id>`.

## Замечания (не дефекты)
1. Заявка 49 (COMM_LOST) создана для связки, которая ни разу не была online. Это R-12 по DEC-12, но при подключении связки до запуска реле будет лишний шум.
2. Ключ карточки в viewer = f3d_code оборудования (тут QA-GENSET-01). AC-22 и AC-24 пишут ключ GENSET. Для реального генератора код должен быть GENSET, это стоит проверить при настройке.
3. Крон 81 (публикация) и кроны 82, 83 активны на этой базе и работают по расписанию. Тестовая связка 3 будет публиковать сигналы каждую минуту и держать заявку 49 открытой. Рекомендация: отключить связку 3 (active = False) или удалить вручную после проверки.

## Мусор в базе (создано мной, ничего не удалено)
- td.genset id 1 «QA-genset-GEN-01». В ней записаны run_hours = 260 и run_hours_total = 260 вручную (симуляция).
- maintenance.equipment id 216 «Генератор · QA-genset-GEN-01». Установлены f3d_code = QA-GENSET-01 и f3d_passport_id = 37 (паспорт KOHLER-SDMO D700, роль genset). Создано автоматически при создании генератора.
- f3d.genset.link id 3 «Генератор · QA-genset-GEN-01 (QA-GENSET-01)». Записано 26 сигналов, публикация идет каждую минуту.
- maintenance.request id 48 «ТО-1 після обкатки (250 мотогодин)». Без префикса QA, создано кроном 78.
- maintenance.request id 49 «Генератор QA-GENSET-01: втрачено зв'язок з контролером…». Создано кроном 82.
- f3d.source id 136 «Ретранслятор SmartGen (td_genset)». Создано кроном 81 (возможно, из установки; проверить).
- Записей td.genset.reading, td.genset.event, td.genset.command не создавалось (отказ доступа).

## Не проверено и почему
- Контроллерные события, показания по реле, ТК-01…14, ТК-F, ТК-G, /sim/v1/*, AC-36…40, AC-47…55: нужны relay D700 и эмулятор, на сервере их нет. Событий и показаний через RPC создать нельзя (нет групп с правом создания).
- Права и роли (AC-33, AC-59, AC-60): пользователи qa-genset-<роль> не создавались, лимит времени 40 минут.
- Крон 79 «Чистка»: удаляет записи, по правилу не запускался.
- Q-13: фильтр по td_code не прошел (ошибка коннектора). Количество строк мапы (48) проверено.
- 3D-просмотр сцены: не проверен, в браузере только формы и списки.
- Копия прода, neutralize.sql, R2, DEPLOY_TEST, MAN-AC: на этом сервере не запускались (это тестовая база без демо-данных; лидер отметил их как «требует человека»).
- Серверный лог не просматривался. Проверка ошибок сделана по ir.logging (WARNING и ERROR с 20:45 нет).

## Объем проверки
- Коннектор: около 40 вызовов (в т.ч. пробы создания с ошибками доступа).
- HTTP API (Python requests, cookie-сессия): 32 запроса из лимита 50.
- Браузер (Chromium): 26 action и 5 форм, с отдельным трафиком страниц; в лимит 50 API-запросов не входит.
- Скрипты и логи: /tmp/claude-0/-home-user-todo-timur/c00ab7e6-c2ea-5355-9cae-b7d9087feae4/scratchpad/qa_genset/ (rpc.py, http_check.py, ui.js). Файлы с паролем не выводились.
