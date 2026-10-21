# QA fire_safety

Статус: PARTIAL
Проверено: 18, провалено: 0, не проверено: 8 (2026-10-15, коммит 29a088e)
Дефекты: 0 подтверждённых (критичных: 0); вопрос к проверке: 1; наблюдения: 3
Мусор в базе: f3d.collector id 17 (code QA-FIRE-COL, токен отозван, запись активна, не удалялась);
f3d.fire.event id 5, 6, 7; показания f3d.signal `fire/groups/FA-CUT/state` (3 тестовых);
вероятно 1 запись f3d.push.event (event_id QA-fire-alarm-LSZ14…)

Сервер: https://timur-o19demo.todo.ltd, db `odoo` (проверено в ответах коннектора), подключение `AxI--dg8QCmJAxW_`.
Лидер-отчёт: `/home/user/f3d-build/factory3d/build/modules/factory3d_fire_safety.md` (в задании имя `fire_safety.md`, фактическое — с префиксом).
SPEC: `/home/user/f3d-build/factory3d/docs/modules/factory3d_fire_safety/SPEC.md`.

| # | AC / сценарий | Способ | Результат | Доказательство |
|---|---|---|---|---|
| 1 | Установка fire_safety | ir.module.module | PASS: installed, 19.0.1.0.0 совпадает с манифестом | id 1488 |
| 2 | Установка viewer-моста | ir.module.module | PASS: installed, 19.0.1.0.0 | id 1489 |
| 3 | Меню и действия | ir.model.data, ir.ui.menu, get_views f3d.fire.zone | PASS: 18 записей меню (корень + 17), 15 action_f3d_fire_*; list и form зон загружаются. Построчно с таблицей AC-63 не сверялось | ir.model.data 85232–85317 |
| 4 | AC-01 количества | search_count, read_group | PASS: норм 27; зон 35 (smoke 25, multi 9, heat 1); устройств 353; маршрутов 32; панель 1 | read_group f3d.fire.zone |
| 5 | Связи зон с оборудованием и зонами | search_count | PASS: у 35 зон заполнены equipment_id, zone_id, signal_id. Устройств без зоны 131: только flame 3, mcp 36, smoke_vent 44, sounder 41, spark_detector 4, spark_nozzle 3. Все дымовые, multi и heat привязаны | read_group f3d.fire.device по type |
| 6 | AC-62 сохранённые показатели соответствия | read f3d.fire.panel | PASS: зоны 35/35, mcp max 26.9, маршруты 32/32, выходы True, дымовые 8/8, missing_zones False. Пересчёт action_recompute_compliance не запускался | panel id 1 |
| 7 | AC-17 тривога зоны через API приёма телеметрии | POST /f3d/telemetry/push | PASS: FA-CUT → alarm; событие id 6, etype alarm, level alarm, ack_required True, текст «ТРИВОГА: зона FA-CUT (Розкрій)». Понадобилась временная привязка источника (см. раздел «Изменения»). | HTTP 200, changed [fire/groups/FA-CUT/state]; event 6 |
| 8 | AC-15 квитирование | action_ack на событии 6 | PASS: ack True, ack_user Administrator, ack_ts 21:27:38 | event 6 |
| 9 | AC-15 снятие подтверждения запрещено | write ack=False на событии 6 | PASS (условно): коннектор вернул ошибку, запись отклонена. Текст UserError не виден, доказательство неполное | — |
| 10 | AC-17 сброс alarm → normal, событие reset | push «normal», затем «quiet» | NOT CHECKED: «normal» не LS-текст, зона ушла в unknown (по R-11 ожидаемо). Затем «quiet» → normal, но переход из alarm в normal не выполнен, событие reset не проверено. Ошибка в последовательности теста | push-ответы 2 и 3 |
| 11 | Эвакуация: старт и стоп навчання | f3d.fire.drill action_start/action_stop | NOT CHECKED: не хватило времени | — |
| 12 | Крон sync (ir.cron 73) | method_direct_trigger | PASS: True, исключения нет | ir.cron 73 |
| 13 | Крон drill tick (ir.cron 74) | method_direct_trigger | PASS: True, исключения нет. Навчання не запущено, тик пустой | ir.cron 74 |
| 14 | Крон compliance (ir.cron 75) | method_direct_trigger | PASS: True, исключения нет | ir.cron 75 |
| 15 | Вогнегасники и инспекции | — | NOT CHECKED: модели в модуле нет. SPEC Q-12: вне v1, далее стандартный maintenance | SPEC строка 2255 |
| 16 | Активность на FACP-1 при тривоге (AC-17) | mail.activity | NOT CHECKED: после тривоги активности нет. Вопрос к проверке, см. ниже | mail.activity для f3d.fire.panel id 1: пусто |
| 17 | HTTP GET /f3d/telemetry/health | curl | PASS: 200, module factory3d_telemetry 19.0.1.1.0 | HTTP 1 |
| 18 | HTTP push без токена | curl | PASS: 401 unauthorized | HTTP 2 |
| 19 | HTTP push с неверным токеном | curl | PASS: 401 unauthorized | HTTP 3 |
| 20 | HTTP push с источником чужого коллектора | curl | PASS: 200, reading отклонён reason foreign_signal. Владелец источника соблюдён | HTTP 4 |
| 21 | HTTP event bacnet_event, валидный токен | curl | PASS: 200, accepted 1, handled f3d.push.handler.fire. Тип события bacnet, см. наблюдение 2 | HTTP 8; event 5 |
| 22 | HTTP event без токена и с неверным payload | curl | NOT CHECKED: не хватило времени | — |
| 23 | Права ролей AC-13, AC-14, AC-50, AC-64 | — | NOT CHECKED: пользователи qa-fire-<роль> не создавались | — |
| 24 | Enterprise-мосты: factory3d_access, factory3d_iot_sim, factory3d_machine_connect, maintenance | ir.module.module | PASS (только установка): все четыре installed. Их функции не проверялись | ids 1484, 1481, 1491, 896 |
| 25 | Интерфейс в браузере | — | NOT CHECKED: проверено только через ORM и get_views | — |
| 26 | AC-02/03 копия демо; ТК/ТБ/ТП, DEPLOY_TEST на стенде | — | NOT CHECKED: копии демо нет; стенд эмулятора не работает (как и указано в лидер-отчёте) | — |

Итого: проверено 18 (из них условно: 9), провалено 0, не проверено 8 (строки 10, 11, 15, 16, 22, 23, 25, 26).

## Дефекты

Подтверждённых дефектов нет. Ниже вопрос и наблюдения, которые стоит проверить.

**Вопрос 1 (не подтверждено): тривога без активности на FACP-1.** AC-17 требует по одной активности на FACP-1 при тривоге.
После тривоги mail.activity для f3d.fire.panel id 1 пусто. Возможная причина: в группе оповещения нет пользователей,
тогда `_schedule_activity` ничего не создаёт (`factory3d_fire_safety/models/f3d_fire_panel.py`, `_notify_alarm`, строки ~352–364).
Нужно проверить состав группы и повторить тривогу. Шаги: push alarm FA-CUT → mail.activity для панели.

**Наблюдение 1: события source='demo' на сервере без демо-данных.** На базе есть 4 события `source='demo'`
(id 1–4, даты 11–12.10.2026). Задание говорит «без демо-данных». Источник не выяснен: возможно, это результат post_init
`run_all` (AC-03, «подій демо 4»). Проверить, нужны ли они на тестовом сервере.

**Наблюдение 2: bacnet_event с to_state=alarm не даёт тревожного события.** Если события зоны ещё нет, обработчик создаёт
событие `etype='bacnet'`, level info, и не переводит зону в тревогу (`models/push_handler.py`, ветка `if etype:` без
существующего события → `_log("bacnet", …)`). Это соответствует тесту SPEC `test_new_bacnet_event` (etype='bacnet'),
поэтому дефектом не считаю. Для оператора такое событие выглядит как «информация», а не тревога. Решение за менеджером.

**Наблюдение 3: текст ошибки при снятии подтверждения.** Коннектор вернул ошибку без текста. Надо подтвердить,
что это UserError из AC-15, а не другой сбой.

**Замечание по входным данным.** Лидер пишет, что Enterprise-мосты в среде сборки не ставили. На тестовом сервере
установлены factory3d_access, factory3d_iot_sim, factory3d_machine_connect и maintenance. Поэтому AC-49
(«без iot_sim: sim_available=False») на этой базе как написано не проверяется.

## Изменения в базе (для учёта и отката)

- f3d.source id 134 (BAC-200-FACP-1): collector_id сначала 1, затем временно 17 (QA-коллектор), затем возвращён на 1.
  Проверено: сейчас 1.
- f3d.fire.zone FA-CUT (id 12): было unknown. Стало normal (raw_state quiet). Тревоги нет.
- f3d.fire.event id 6: ack = True (Administrator, 21:27:38).
- f3d.collector id 17 (QA-FIRE-COL): создан, токен выдан и отозван (action_revoke_token вернул true). Запись не удалялась и не архивировалась.
  Токен в отчёт не вынесен.
- Кроны 73, 74, 75: однократный запуск method_direct_trigger.
- Пользователи не создавались. Записи не удалялись. Модули не трогались.
- HTTP-запросов: 8 из 50.

## Не проверено и почему

- Строка 10 (сброс тревоги, событие reset): последовательность теста была неверной, см. таблицу.
- Строка 11 (эвакуация, навчання start/stop): не хватило времени (таймбокс 40 минут).
- Строка 15 (вогнегасники, инспекции): в модуле нет модели. Вне v1 по SPEC Q-12.
- Строка 16 (активность на FACP-1): нужна проверка состава группы оповещения.
- Строка 22 (HTTP event без токена и с неверным payload): не хватило времени.
- Строка 23 (права ролей): пользователи не создавались, время.
- Строка 25 (браузер): не делалось.
- Строка 26 (копия демо, ТК/ТБ/ТП на стенде): вне среды, как указано в лидер-отчёте.
