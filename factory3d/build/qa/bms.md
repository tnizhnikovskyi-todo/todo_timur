# QA bms

Статус: FAIL
Проверено: 15, провалено: 2, не проверено: 8 (2026-10-15, коммит 29a088e)
Дефекты: 2 (критичных: 1)
Мусор в базе: res.users id 13 (login `qa-bms-user`, группа «Завод 3D / Користувач»), res.users id 14 (login `qa-bms-operator`, группа «Будівля: оператор»), f3d.bms.light.norm id 16 (key `qa_bms_norm_1`, name «QA-bms-test norm (upd)», lux 260). Чужие тестовые зоны f3d.zone id 46, 47, 55 (`QA-BASE-Z1`, `QA-BASE-XXXXXXXXXXXXXXXXXXXXXXXX`, `QA-X-1`) созданы не QA bms, но попадают в огляд. Ничего не удалялось; удалить может пользователь.

Коннектор: `AxI--dg8QCmJAxW_`, в каждом ответе `connection.db == "odoo"`, сервер https://timur-o19demo.todo.ltd. «Проверено» = выполнено, включая провалы.

| # | AC / сценарий | Способ | Результат | Доказательство |
|---|---|---|---|---|
| 1 | Установка | `ir.module.module` | PASS: `factory3d_bms` installed, 19.0.1.0.0 = манифест | read id 1486 |
| 2 | Меню и действия | `ir.model.data` + `ir.ui.menu` | PASS: 14 меню под «Завод 3D / Будівля» и «Налаштування / Будівля», 10 действий (act_window, server, client) связаны | ir.model.data module=factory3d_bms; menu ids 582–595 |
| 3 | AC-47 открытие формы | `f3d.bms.overview.action_open('f3d.bms.light.group', 12, 'form')` | PASS: `ir.actions.act_window`, res_model=f3d.bms.light.group, view form | результат метода |
| 4 | AC-01, AC-02, AC-13, AC-48 количества | `search_count` | PASS: норм 13, групп 32, установок 29, щитов 3, баланс 1 с total_kw 753 (ожидание AC-48) | count |
| 5 | Связи объектов | `search_read` | PASS: 32/32 групп с zone, norm, panel, equipment; 29/29 установок с zone, equipment, source, airflow_signal (у EF-* нет теплових сигналів); 3/3 щитів с equipment, state_signal, source | read |
| 6 | Сигнали модуля, DEC-7 (origin catalog), AC-49 | `search_count` по code и origin, сверка с bms_signals.csv | FAIL: освітлення 195 (67 catalog, 128 module), вентиляція 351 (107 catalog, 163 module, 81 sim_data), без source 0. 81 сигнал `ventilation/*` остался `origin=sim_data`, не catalog | D-2 |
| 7 | AC-03 расчёт освітлення | `search_read` area_m2, e_norm, n_fixtures, n_required, e_calc; формула локально | PASS: LT-CUT (area 609.3, 500 лк): n_required 27, e_calc 509; LT-EB (564.5): 25 / 549; LT-RCV-1 (118.4, 300 лк): 4 / 388; LT-FAC (1235, 750 лк): 81 / 846. Все совпадают с формулами AC-03 | read |
| 8 | AC-07, AC-08, AC-09 без живых данных | `search_read` | PASS: LT-CUT level_pct 100, level_source design, e_now 509, stale True; щити LP-1/2/3 p_now 5.6 / 23.2 / 9.5, p_source design, state unknown | read |
| 9 | AC-14 пересчёт (метод) | `f3d.bms.heat.balance.action_recompute` id 1 | PASS: метод отработал, `true`, total_kw остался 753 | результат метода |
| 10 | AC-46, FR-14 огляд | `f3d.bms.overview.get_overview_data` ×3 | FAIL: три из трёх попыток — «Error executing tool odoo_execute» | D-1 |
| 11 | Создание, запись, чтение (QA-) | `odoo_create` / `odoo_write` / `odoo_search_read` f3d.bms.light.norm | PASS: создана норма id 16, записаны name и lux, прочитано. Первая попытка с ключом `QA-bms-norm-1` отклонена валидацией KEY_RE (латиница в нижнем регистре, без дефисов). Это ожидаемо, не дефект | id 16 |
| 12 | Крон `cron_f3d_bms_check` (AC-26…) | ir.cron id 72, `method_direct_trigger` | PASS: вернул `true`; lastcall 21:24:12 → 21:24:51; отклонений 0 (живых данных нет) | ir.cron 72 |
| 13 | Журнал ошибок после крона | `ir.logging` с 2026-10-15 | PASS с оговоркой: записей ERROR/CRITICAL нет, но `ir.logging` не записывает трейсбеки get_overview_data, признак ненадёжен | пустой результат |
| 14 | Права на f3d.bms.light.group, статически (AC-61) | `ir.model.access` | PASS (статически): group_f3d_user (82) только read; group_f3d_manager (83) полный доступ. Оператор (94) своего правила не имеет | access ids 1165, 1166 |
| 15 | Роли: создание пользователей и назначение групп | `res.users` create + write `group_ids` | PASS: qa-bms-user (id 13) в группе 82, qa-bms-operator (id 14) в группе 94; запись `group_ids` работает | write → true |
| 16 | AC-26, 27, 34, 37, 38, 40 алармы по порогам | — | NOT CHECKED: эмулятор не запущен, живых показаний нет; `_f3d_ingest` не вызывался, чтобы не создавать заявки ТО | — |
| 17 | HTTP-эндпоинты модуля | grep по `http.route`, `controllers` | NOT CHECKED: своих маршрутов в модуле нет (SPEC §7 подтверждает); проверка ORM через `/web/dataset/call_kw` не прошла, см. ниже | — |
| 18 | Runtime-права AC-57…AC-61 (AccessError под user и operator, write_enabled, команды) | — | NOT CHECKED: вход под QA-пользователями по HTTP возвращает 403; коннектор действует от admin | — |
| 19 | Браузер: формы, списки, 3D, Hoot | — | NOT CHECKED: Playwright не запускался (таймбокс) | — |
| 20 | AC-46 число зон 34, AC-43 | — | NOT CHECKED: блокируется D-1. В выборке зон видны чужие тестовые зоны id 46, 47, 55, они попадут в огляд | — |
| 21 | AC-49, AC-50, AC-52 (демо-копия, пункт «требует человека» у лидера) | — | NOT CHECKED: демо-установки на этой базе нет | — |
| 22 | AC-62 цепочка implied-групп | — | NOT CHECKED: не успел | — |
| 23 | AC-14 значение u_wall = 0.5 → total 772 | — | NOT CHECKED: запись баланса не менял, чтобы не трогать глобальные данные | — |

## Дефекты

### D-1 (критичный): `get_overview_data` возвращает ошибку сервера

- Шаги: `odoo_execute` с model=`f3d.bms.overview`, method=`get_overview_data`, args=[], connection_id=`AxI--dg8QCmJAxW_`. Повторено три раза.
- Ожидание: словарь с ts, work_time, plan, zones, groups, panels, units, kpi, heat, deviations (AC-46, R-28).
- Факт: во всех трёх попытках «Error executing tool odoo_execute», трейсбек недоступен. Другие методы модуля (`action_open`, `action_recompute`, крон) работают. Это ошибка сервера, по регламенту — дефект.
- Место в коде: `factory3d_bms/models/f3d_bms_overview.py:54–129` (сборка данных), `:141–154` (`_heat`), `:45–51` (`_work_time`), `:41–43` (`_search`, вспомогательный ACL-хелпер, не причина). Живой баланс: `models/f3d_bms_heat_balance.py:247` (`_f3d_bms_live`).
- Что уже исключено: computed-поля групп, установок и щитов читаются без ошибок (`plan_state`, `deviation_text`, `mode_label`, `e_now` и др.); `factory3d.bms.calendar_id` пуст, но company-календарь задан (id 2); `HEAT_KEYS` совпадают с ключами `_f3d_bms_live` (статическая сверка, 15 ключей).
- Нужно: серверный лог на тесте в момент вызова. HTTP-трейсбек не получен (см. примечания). Причина не установлена.
- Влияние: экран «Огляд» модуля не может получить данные; AC-46 и AC-47 (для огляда) не проходят.

### D-2 (средний): 81 сигнал `ventilation/*` сохранил `origin=sim_data`

- Шаги: `f3d.signal` `search_count` с `code like 'ventilation/%'`, `origin='sim_data'` → 81.
- Ожидание по DEC-7: сигналы из CSV с origin sim_data создаются как catalog, иначе миграция telemetry остаётся partial.
- Факт: существующие 81 сигнал не переписаны, origin остался sim_data (связаны с BAC-источниками, source не пуст). Для новых строк хук ставит catalog. Противоречие SPEC: AC-49 описывает sim_data как знімок, а DEC-7 требует catalog.
- Гипотеза, не проверена: эти 81 строки могут быть причиной того, что миграция telemetry стоит в partial. Это отдельный дефект, здесь не чиним.
- Место: `factory3d_bms/hooks.py:324` (маппинг origin), `:392–393` (умолчание для существующих сигналов), DEC-7 в build/modules/factory3d_bms.md.

## Не проверено и почему

- Алармы по порогам (AC-26…AC-40): эмулятор не запущен, живых показаний нет.
- HTTP и runtime-права: вход под QA-пользователями по HTTP даёт 403 (см. примечания), поэтому AC-57…AC-61 не проверены.
- Браузер и 3D: не запускался (таймбокс).
- AC-46 число зон, AC-43: блокируется D-1.
- AC-49, AC-50, AC-52: демо-копия не разворачивалась.
- AC-62: не успел.
- AC-14 со значением u_wall: запись баланса не менял.

## Примечания

- Пути из задания не совпали с фактическими: отчёт лидера — `/home/user/f3d-build/factory3d/build/modules/factory3d_bms.md`, SPEC — `/home/user/f3d-build/factory3d/docs/modules/factory3d_bms/SPEC.md`. Использованы они.
- HTTP: `GET /web/login` вернул 200. `POST /web/session/authenticate` вернул 403 дважды. Регламент прокси: 403 означает запрет политики, повторно не пробовал. Всего HTTP-запросов около 4 из 50.
- Пароль из cred-файла не выводился. Тестовым пользователям задан отдельный пароль при создании, в отчёт не вынесен.
- На базе в названии компании стоит «Меблева фабрика (демо)» (res.company id 1). Задание говорило «без демо-данных»; сверить с владельцем.
- Таймбокс 40 минут почти исчерпан.

> Примечание менеджера (21:32 UTC): D-1 не подтверждён — `f3d.bms.overview.get_overview_data` через JSON-RPC под admin отвечает OK; ошибка была в коннекторе. Итоговый статус модуля — PARTIAL.
