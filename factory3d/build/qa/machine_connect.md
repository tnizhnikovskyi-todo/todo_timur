# QA machine_connect

Статус: PARTIAL
Проверено: 23, провалено: 2, не проверено: 6 (дата 2026-10-15, коммит 29a088e)
Дефекты: 2 (критичных: 0)
Мусор в базе: f3d.collector id 14 «QA-mc-collector (тест API-01)» (код QA-MC-C1), id 15 «QA-mc-collector-2 (тест чужого коллектора)» (код QA-MC-C2); f3d.cut.map id 2 «QA-mc-CM-1» (состояние draft, режим manual, в export_token_hash и export_token_expires остались хеш тестового токена и срок 2030; вложение «QA-mc-CM-1_parts.csv»; f3d.cut.map.line id 1 «QA-mc-P1»; две записи в чатере карты о забранном списке). Удалить вручную.

Что сделано сверх шаблона: изменено поле mode карты id 2 (collector → manual, чтобы выполнить экспорт; см. наблюдение 1). Глобальные параметры (ir.config_parameter, write_enabled=False) не менялись. Пароль Odoo не читался и не использовался: API-01 публичный (auth=public), коннектор работает по своим учётным данным. Модули не ставились, пользователи не создавались, ничего не удалялось.

Пути: отчёт лидера лежит в `/home/user/f3d-build/factory3d/build/modules/factory3d_machine_connect.md` (в задании указан machine_connect.md, файла нет); SPEC — `/home/user/f3d-build/factory3d/docs/modules/factory3d_machine_connect/SPEC.md` (103 строки AC, читались только строки AC и оглавление).

HTTP-запросов к API: 13 (лимит 50). Скрипт с тестами: `/tmp/claude-0/-home-user-todo-timur/c00ab7e6-c2ea-5355-9cae-b7d9087feae4/scratchpad/qa_mc_api.sh`; токены в `.../scratchpad/qa_mc_tokens.json` (не в отчёте).

| # | AC / сценарий | Способ | Результат | Доказательство |
|---|---|---|---|---|
| 1 | Установка machine_connect: installed, 19.0.1.0.0 | odoo_search_read ir.module.module (id 1491) | PASS | state=installed, latest_version=19.0.1.0.0 |
| 2 | Установка моста factory3d_machine_connect_mrp_workorder (auto_install) | ir.module.module (id 1492) | PASS | mrp_workorder (id 939) installed, мост installed, 19.0.1.0.0 |
| 3 | Меню (18) и действия (15) открываются: у моделей есть нужные виды | ir.ui.menu, ir.actions.act_window, ir.ui.view | PASS (по метаданным, браузер не запускался) | f3d.machine list/form/kanban/search; f3d.cut.map list/form; f3d.downtime list/kanban/form/graph/pivot; мастер импорта и res.config.settings с form |
| 4 | Машины: 35 f3d.machine, каждая на своём РЦ, связь 1:1 | search_read f3d.machine, mrp.workcenter | PASS | 35 активных машин; f3d_machine_ids у каждого РЦ = одна машина; коды ASM-1…PACKLINE-1 совпадают с f3d_code |
| 5 | Мост: связи машина ↔ РЦ ↔ заказ; поля Enterprise (duck typing переключится на Enterprise-путь) | ir.model.fields | PASS (наличие) | mrp.workcenter.employee_ids (7062), mrp.workorder.employee_ids (7056), mrp.workorder.f3d_employee_id (14452); f3d.machine.active_workorder_id = false у всех 35 |
| 6 | Мост: старт/стоп работника через start_employee/stop_employee | не проводилось | NOT CHECKED | см. «Не проверено» |
| 7 | API-01: без Bearer → 401; с неверным Bearer → 401 | HTTP GET /f3d/machine/cutmap/2/export | PASS | `{"error":{"code":"unauthorized"}}`, 401, Cache-Control: no-store |
| 8 | API-01: без X-F3D-Token → 400 | HTTP с валидным Bearer | PASS | 400, code bad_token |
| 9 | API-01: токен в ?t= без заголовка → 400 (DEC-20) | HTTP ?t=<валидный токен> | PASS | 400, code bad_token; query не принимается |
| 10 | API-01: мусорный X-F3D-Token («zz-not-hex», «xyz») → 400 | HTTP | PASS | 400, code bad_token (два запроса) |
| 11 | API-01: 16-hex, но неверный токен → 403 | HTTP | PASS | 403, code forbidden |
| 12 | API-01: несуществующая карта → 404 | HTTP, map 999999 | PASS | 404, code not_found |
| 13 | API-01: валидный Bearer + токен экспорта → 200, no-store, JSON с CSV | HTTP | PASS | 200; map «QA-mc-CM-1», external_ref WH/MO/00245, material DSP16-ANT, sheet 2800x2070x16, parts 2 |
| 14 | AC-61 (формат CSV): заголовок R-19, `;`, CRLF | тело ответа 13 | PASS | `PartId;Description;Material;Length;Width;Quantity;Grain;EdgeTop;EdgeBottom;EdgeLeft;EdgeRight;Program` + `QA-mc-P1;QA-mc-Боковина;DSP16-ANT;720;560;2;0;;;;;` + CRLF |
| 15 | AC-66: повтор того же токена → 403 (одноразовый) | HTTP | PASS | 403, code forbidden |
| 16 | AC-67: истёкший токен → 410 | odoo_write export_token_expires=2020-01-01 + HTTP | PASS | 410, code expired |
| 17 | AC-67: карта не в exported (draft) → 409 | odoo_write state=draft + HTTP | PASS | 409, code bad_state |
| 18 | AC-67: токен колектора іншого → 401 | второй активный коллектор QA-MC-C2 (id 15) + валидный экспортный токен | FAIL | HTTP 200 и полный CSV; см. дефект 1 |
| 19 | AC-68: >5 000 деталей → 413 | не проводилось | NOT CHECKED | см. «Не проверено» |
| 20 | Кроны: 5 шт. (ids 59–63) через method_direct_trigger без ошибок | odoo_execute ir.cron | PASS | все вызовы вернули true; ir.logging уровня ERROR/CRITICAL: 0 записей |
| 21 | Кроны реально выполнились | ir.cron.lastcall | PASS | lastcall 21:07:08–21:07:18 (до запуска кроны шли сами каждую минуту) |
| 22 | Состояния станков и OEE обновляются от данных | ir.cron, f3d.machine, f3d.oee.shift | NOT CHECKED | данных колектора на стенде нет, состояния не меняются (кроме CNC-2 из миграции, см. наблюдение 3); смены OEE созданы и закрыты (35 шт.) |
| 23 | OEE-смены 15.10 по журналу часа: открытые записи от 12.10 не считаются работой | f3d.oee.shift, mrp.workcenter.productivity | FAIL | см. дефект 2 |
| 24 | AC-59: деталь с length_mm=0 отклоняется, запись не создаётся | odoo_create f3d.cut.part | PASS | create вернул ошибку; поиск part_code QA-mc-P2 → пусто |
| 25 | AC-58 (частично): при write_enabled=False команда не создаётся | экспорт collector (откат) + f3d.command count | PASS (частично) | f3d.command: 0 записей (после неудачного экспорта, до запуска кронов); текст предупреждения через RPC не виден |
| 26 | Create/read/write через коннектор: f3d.collector, f3d.cut.map, f3d.cut.map.line | odoo_create, odoo_write, odoo_execute action_export | PASS | коллектор id 14/15; карта id 2 (draft → exported → draft); строка id 1 |
| 27 | AC-62: отправка оптимизатору при write_enabled=True | не проводилось | NOT CHECKED | см. «Не проверено» |
| 28 | Интерфейс в браузере: формы, списки, 3D | не проводилось | NOT CHECKED | см. «Не проверено» |
| 29 | Права ролей (логины qa-mc-<роль>) | не проводилось | NOT CHECKED | пользователи не создавались (правило задания) |

## Дефекты

### Дефект 1. API-01 принимает Bearer любого активного коллектора (средний)

- Шаги: (1) активный коллектор QA-MC-C2 (id 15) с токеном T2; (2) на карте id 2 в состоянии exported записан хеш экспортного токена t, срок в будущем; (3) GET /f3d/machine/cutmap/2/export с `Authorization: Bearer T2` и `X-F3D-Token: t`.
- Ожидание (AC-67): 401 («токен колектора іншого → 401»).
- Факт: 200 и полный JSON с parts_csv.
- Код: `factory3d_machine_connect/controllers/cutmap.py:31–33` проверяет только, что коллектор существует и активен (`f3d.collector._authenticate`). Карта не привязана к коллектору: в `models/f3d_cut_map.py` нет поля collector_id (поиск пуст).
- Риск ограничен: экспортный токен одноразовый и передаётся колектору только в команде. Но SPEC требует 401. Решение за человеком: привязать карту к коллектору при отправке или поправить SPEC.

### Дефект 2. OEE-смена по журналу часа считает открытые записи трёхдневной давности работой до конца смены (средний, вероятный)

- Шаги: открыть f3d.oee.shift за 15.10 для РЦ «Збирання 1/2/3» (ASM-1..3).
- Ожидание: открытая запись журнала часа старше смены (или без активности) не даёт рабочего времени; при выпуске 0 доступность не должна быть 1.0.
- Факт: смены id 30, 31, 32 (source=timelog): ppt_min=480, run_min=480, availability=1.0, performance=0, oee=0. Причина: записи mrp.workcenter.productivity без date_end с датой 12.10 («Fully Productive Time»): id 32 (Збирання 1, 12.10 06:36), id 37 (Збирання 2, 12.10 06:02), id 69 (Збирання 3, 12.10 06:32). Всего открытых записей, по данным поиска, не меньше пяти.
- Код: `factory3d_machine_connect/models/f3d_oee_shift.py:190` (`log.date_end or now`), `:254` (`dt.date_end or t1`), `:266` (`min(log.date_end or t1, t1)`). Открытая запись обрезается только концом смены.
- Не покрыто AC. Вероятная причина: записи после миграции (migration_report: timelog_marked 184) или не закрыты на производстве. Решение за человеком: логика расчёта или очистка данных.

## Наблюдения (не дефекты)

1. Экспорт карты в режиме «через колектор» при write_enabled=False откатывается целиком: карта остаётся в draft, CSV не создаётся. Причина: `action_export` (`models/f3d_cut_map.py:310–322`) вызывает `action_send_optimizer` (`:387–399`), который отказывает. Текст ошибки коннектор не возвращает. Вопрос проектирования: нужно ли блокировать формирование CSV, а не только отправку.
2. Код модулей в HEAD `/home/user/f3d-build` (6328313) совпадает с установленным коммитом 29a088e: git diff по обоим модулям пуст.
3. CNC-2 (f3d.machine id 9) в состоянии fault без сигналов: открытый простой id 74 «CNC-2 · 12.10 09:42», raw_state=False, raw_alarm=False, f3d.machine.state.log пуст (0 записей). Вероятно, перенесено миграцией (migration_report: downtimes_created 74, DEC-17). Лидеру проверить миграцию.
4. Лидер в отчёте пишет, что мост не тестировался (нет Enterprise). Enterprise mrp_workorder на этой базе установлен, поэтому частичная проверка моста возможна (пункты 5–6).
5. В расчётах кронов `_cron_rotate` (хранение журналов 400 дней) удалять было нечего: f3d.machine.state.log пуст.
6. Коннектор скрывает тексты ошибок (ответ «Error executing tool»), поэтому тексты сообщений оценивались по HTTP-ответам и коду.
7. Чужой мусор на базе (не трогал): mrp.workcenter id 36, 37, 39 (QA-T-1, QA-X-1, QA-BR-1, «QA-base-…»); f3d.collector id 2 «QA-telemetry-collector» (QA-TELE-C1).

## Не проверено и почему

- Мост: start_employee/stop_employee и автостарт работника (пункт 6). Нужна работающая WO на РЦ с машиной. Чтобы её получить, пришлось бы менять МО WH/MO/00245 (state progress), на что у QA нет права. Исходников Enterprise в среде нет, поэтому наличие методов проверить нельзя.
- AC-68 (413): нужно >5 000 строк карты или тело >1 МБ, через RPC не сформировать.
- AC-62 (отправка оптимизатору): требует write_enabled=True. Параметр на стенде выключен, включать не стал.
- Состояния станков от колектора (AC-03…AC-08 живьём): на стенде нет данных колектора.
- Браузер (формы, списки, 3D-просмотр): не запускал, проверено по метаданным (виды и действия). Причина: лимит 40 минут.
- Права ролей (пункт 6 QA.md): пользователи не создавались по правилу задания.
- Инактивный коллектор (ожидается 401 по коду): не проверял, в шаблон не вошёл.
- Нагрузочные ТП-01 (DEC-19, deadlock), ТК-03/15, ТП-04 (DEC-21): стендовые, вне 40 минут.
