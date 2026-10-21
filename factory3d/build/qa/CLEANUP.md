# Мусор QA в базе timur-o19demo (удалять только с подтверждением пользователя)

Собрано из отчётов агентов. Все записи с префиксами QA-/qa-; ничего не удалялось.

## base
Мусор в базе: см. раздел «Мусор в базе» ниже (QA-записи, ничего не удалялось)
- f3d.zone: 46 (QA-base-zone1, контур перенесён в угол территории 181..181.6 x 99..99.6), 47 (QA-base-zone32), 53 (QA-base-bad, код из 32 символов Q), 55 (QA-base-zx, код QA-X-1). Из-за них зон в базе 49, а не 45.
- stock.warehouse: 2 (QA-base-WH, код QAB), вместе с автосозданными типами операций, локациями QAB/*, маршрутами и последовательностями.
- stock.location: 732 (QA-D-1/QA-U-1), 736 (QA-X-1), 752 (ворота QA-DW-93), 753 (ворота QA-DE-93), 754 (QA-Z2-L1).
- stock.picking.batch: 25, 26 (BATCH/IN/00025, 00026). stock.picking: 51, 52.
- product.product: 60, 61 (QA-base-prod-*). product.category: 12 (QA-base-ХДФ).
- mrp.workcenter: 36 (QA-T-1), 37 (QA-base-wcX, f3d_code QA-X-1, в нём сотрудник 37), 39 (QA-BR-1), 40 (QA-base-wc-nocode).
- maintenance.equipment: 212 (QA-T-1), 213 (QA-FL-T), 214 (без кода, в РЦ 37), 215 (QA-BR-1). Всего оборудования 214, а не 210.
- hr.employee: 37 (код OP-QA-X-1), 38 (код OP-W99), 39. Кодов сотрудников теперь 37, а не 35.
- Пользователи qa-base-* не создавались.
- Временно менял ir.config_parameter factory3d.base.migration_state (id 48) и migration_report (id 49) двумя запусками миграции, значения возвращены исходные (done и отчёт установки). Состояние миграции на базе: done.
- Записи QA-base-* можно удалить: сначала пакеты, пикинги, ворота и склад QAB, потом остальное.

## iot_sim
Мусор в базе: f3d.sim.run: id 1–4 (RUN/2026/0001 running, 0002 done, 0003 и 0004 failed; у 0001–0002 sim_run_id `QA-iot_sim-run-1`, у 0003–0004 параметры device=NOPE-1 / RV-05, создал run-wizard); f3d.sim.event: id 1–2 (сообщения `QA-iot_sim-ev1`, `QA-iot_sim-ev2 done`). Пользователей qa-iot_sim-* не создавал (см. «Не проверено»). Run №1 в состоянии `running` виден на пульте в «Активные запуски», удалить вручную.

## telemetry
Мусор в базе: см. раздел «Мусор в базе» ниже (QA-записи, ничего не удалялось)

- `f3d.collector` id 2 `QA-TELE-C1` (токен отозван, `state=online/offline` по времени); `f3d.source` id 137 `QA-TELE-S1`.
- `f3d.signal` id 1214–1218 `equipment/QA-TELE/*`; `maintenance.equipment` id 211 `QA-telemetry-equipment` (настроен счётчик на сигнал 1216).
- `maintenance.request` id 44 (закрыта), 45 (открыта, «QA-telemetry- стан 2»), 46 (закрыта, ТО по счётчику).
- `f3d.reading` около 20 строк `src=collector` по QA-сигналам, `f3d.reading.hour` несколько строк, `f3d.push.event` 2 записи (`route=qa_none`), сообщения в чаттере QA-записей.
- `res.users` id 7 `qa-telemetry-user`, id 8 `qa-telemetry-manager` (пароли затёрты, пользователей лучше заархивировать).
- `ir.config_parameter` `factory3d.telemetry.level0_migrated` перезаписан повторным запуском миграции (21:02:31); `ir.cron` 45–48 имеют обновлённый `lastcall`.
- Примечания «QA-telemetry- by manager» в `f3d.signal` 1218 и `f3d.source` 137.


## machine_connect
Мусор в базе: f3d.collector id 14 «QA-mc-collector (тест API-01)» (код QA-MC-C1), id 15 «QA-mc-collector-2 (тест чужого коллектора)» (код QA-MC-C2); f3d.cut.map id 2 «QA-mc-CM-1» (состояние draft, режим manual, в export_token_hash и export_token_expires остались хеш тестового токена и срок 2030; вложение «QA-mc-CM-1_parts.csv»; f3d.cut.map.line id 1 «QA-mc-P1»; две записи в чатере карты о забранном списке). Удалить вручную.

## access
Мусор в базе: res.users id 9 (`qa-access-plain`, пароль задан, группы не назначались); hr.employee id 40 («QA-access-Співробітник A»); f3d.access.user.link id 36 (`QA-access-1`); f3d.access.event id 1, 2 (`QA-access-ev-1`, `QA-access-ev-2`, process_state=done); hr.attendance id 36 (создана событиями, 2026-10-14 06:00–14:00); f3d.access.card id 2 (номер 90010001, state=active, pending_op=issue, sync_state=local). Удалено: ничего.
Мусор: см. шапку. Пароль тестового пользователя `qa-access-plain` записан в скрипт в scratchpad (`/tmp/claude-0/-home-user-todo-timur/c00ab7e6-c2ea-5355-9cae-b7d9087feae4/scratchpad/qa_access/plain_check.py`) и в отчёт не вынесен. HTTP-запросов к серверу: 5.

## energy
Мусор в базе: res.users id 10 (qa-energy-master), 11 (qa-energy-manager), 12 (qa-energy-accountant); тестовый пароль лежит в scratchpad, в скрипте qa_energy_roles.py. f3d.energy.balance: 192 строки создал крон при запуске (state=skipped, не QA-записи). Три попытки создать пользователей без `group_ids` вернули ошибку; id 10–12 идут подряд, но проверить, что лишних записей нет.

## yard
Мусор в базе: f3d.yard.visit id 7 «YV/2026/00007» (note «QA-yard-visit-1», state left); f3d.yard.visit id 8 (note «QA-yard-visit-2», state draft); f3d.yard.booking id 7 («QA-yard-booking-1», confirmed, DOCK-W2, 2026-10-20 10:00–11:00 UTC, visit 7); f3d.yard.booking id 8 («QA-yard-booking-overlap», requested, DOCK-W2, 2026-10-20 10:30–11:30 UTC). Побочный эффект: крон `day_reset` сбросил дневные счётчики ворот (штатно, не удаление). Удалений не было, пользователей не создавалось, LPR-событий не создавалось.

## bms
Мусор в базе: res.users id 13 (login `qa-bms-user`, группа «Завод 3D / Користувач»), res.users id 14 (login `qa-bms-operator`, группа «Будівля: оператор»), f3d.bms.light.norm id 16 (key `qa_bms_norm_1`, name «QA-bms-test norm (upd)», lux 260). Чужие тестовые зоны f3d.zone id 46, 47, 55 (`QA-BASE-Z1`, `QA-BASE-XXXXXXXXXXXXXXXXXXXXXXXX`, `QA-X-1`) созданы не QA bms, но попадают в огляд. Ничего не удалялось; удалить может пользователь.

## fire_safety
Мусор в базе: f3d.collector id 17 (code QA-FIRE-COL, токен отозван, запись активна, не удалялась);

## viewer
Мусор в базе: res.users id 15 `qa-viewer-mrp`, id 16 `qa-viewer-nomrp`, id 17 `qa-viewer-none` (имена `QA-viewer-…`). Записей f3d.* не создавал. Удалить пользователей вручную, если не нужны.

## td_genset
Мусор в базе: td.genset id 1; maintenance.equipment id 216; f3d.genset.link id 3; maintenance.request id 48 и 49; f3d.source id 136 (подробно ниже)
- td.genset id 1 «QA-genset-GEN-01». В ней записаны run_hours = 260 и run_hours_total = 260 вручную (симуляция).
- maintenance.equipment id 216 «Генератор · QA-genset-GEN-01». Установлены f3d_code = QA-GENSET-01 и f3d_passport_id = 37 (паспорт KOHLER-SDMO D700, роль genset). Создано автоматически при создании генератора.
- f3d.genset.link id 3 «Генератор · QA-genset-GEN-01 (QA-GENSET-01)». Записано 26 сигналов, публикация идет каждую минуту.
- maintenance.request id 48 «ТО-1 після обкатки (250 мотогодин)». Без префикса QA, создано кроном 78.
- maintenance.request id 49 «Генератор QA-GENSET-01: втрачено зв'язок з контролером…». Создано кроном 82.
- f3d.source id 136 «Ретранслятор SmartGen (td_genset)». Создано кроном 81 (возможно, из установки; проверить).
- Записей td.genset.reading, td.genset.event, td.genset.command не создавалось (отказ доступа).


## stand

## regress_1

- Створено res.users id 18 `QA-reg-guard` (login `qa-reg-guard`). Випадковий пароль, у звіт не записано.
- Двері id 3: alarm False → True → False (відновлено).
- Нові токени колекторів (зберігаються лише хеші; сирі токени не фіксувались): COL-MAIN (id 1; попередній токен уже був відкликаний), QA-MC-C2 (id 15), QA-TELE-C1 (id 2).
- QA-TELE-C1 (id 2): state offline→online, last_seen/last_push_at 2026-10-16 01:04:10.
- Запущено ir.cron id 60 «Верстати: OEE змін» (method_direct_trigger); нових смін за сьогодні не створив.
- Створено параметр `factory3d.base.migration_rerun_report`.
- Спроби create f3d.zone не залишили записів.


## regress_2

