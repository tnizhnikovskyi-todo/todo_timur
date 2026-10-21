# QA access
Статус: PARTIAL
Проверено: 12, провалено: 0, не проверено: 9 (2026-10-15, коммит 29a088e)
Дефекты: 5 (критичных: 1)
Мусор в базе: res.users id 9 (`qa-access-plain`, пароль задан, группы не назначались); hr.employee id 40 («QA-access-Співробітник A»); f3d.access.user.link id 36 (`QA-access-1`); f3d.access.event id 1, 2 (`QA-access-ev-1`, `QA-access-ev-2`, process_state=done); hr.attendance id 36 (создана событиями, 2026-10-14 06:00–14:00); f3d.access.card id 2 (номер 90010001, state=active, pending_op=issue, sync_state=local). Удалено: ничего.

| # | AC / сценарий | Способ | Результат | Доказательство |
|---|---|---|---|---|
| 1 | Установка: access и telemetry-мост | odoo_search_read ir.module.module | PASS: factory3d_access 19.0.1.0.0 = манифест; factory3d_access_telemetry 19.0.1.0.0 installed (см. дефект 2) | ir.module.module id 1484, 1485 |
| 2 | AC-65: меню §3 | ir.ui.menu + ir.model.data | PASS: 13 пунктов, родитель «Завод 3D/Доступ», «Доступ» sequence=70 | res id 511–523 |
| 3 | AC-66: вкладка в hr.employee | ir.ui.view | PASS: form (hr.employee.form.f3d.access, .cards), list, search. Вид hr.attendance не найден по маркеру f3d_access, не проверено | view id 2269, 2280, 2270, 2271 |
| 4 | AC-01: url `ftp://` в test-среде | odoo_create f3d.access.server | PASS: отклонено (текст ошибки коннектор не показывает) | запись не создана |
| 5 | AC-39: номер карты `AB12` (не цифры) | odoo_create f3d.access.card | PASS: отклонено (текст не виден) | запись не создана |
| 6 | AC-40: выдача карты при write_enabled=False | odoo_execute action_issue, card id 2 | PASS: state=active, sync_state=local, pending_op=issue | f3d.access.card id 2 |
| 7 | AC-48: date_to раньше date_from у визитора | odoo_create f3d.access.visitor | PASS: отклонено (текст не виден) | запись не создана |
| 8 | AC-15, AC-18: отметка из событий вход/выход | odoo_create f3d.access.event x2 + action_reprocess | PASS: событие 1 → checked_in, событие 2 → checked_out; hr.attendance 36: check_in 06:00, check_out 14:00, worked 8.0 ч; presence_changed=True | f3d.access.event 1, 2; hr.attendance 36 |
| 9 | AC-08: ошибка опроса BioStar, backoff | живое состояние f3d.access.server id 1 | PASS: state=error, error_count=6, last_error=NameResolutionError (iot-sim), next_try_at = +10 мин | f3d.access.server id 1 |
| 10 | AC-62: матрица ACL vs SPEC §13.3 | ir.model.access (статично) | PASS по строкам, кроме door write (дефект 3) | ir.model.access id 1054–1073 |
| 11 | AC-62: user_plain не видит модуль | XML-RPC, логин qa-access-plain (uid 9) | PASS: AccessError на f3d.access.event, card, door, server | вывод скрипта (4 вызова) |
| 12 | Крон: method_direct_trigger | ir.cron ids 49, 50, 51, 52, 53 по одному | PASS: все вернули true, без ошибки RPC. Крон 54 (ротация/закрытие) намеренно не запускался (дефект 1) | ir.cron 49–53 |
| 13 | HTTP-эндпоинты модуля | grep @http.route, controllers/ в обоих модулях | N/A: маршрутов нет, модуль только исходящий клиент BioStar | 0 совпадений |

## Дефекты

**1. КРИТИЧНО (риск данных, нужно решение человека до 2026-10-16 23:30).** Крон «СКУД: ротація і закриття відміток» (ir.cron id 54, nextcall 2026-10-16 23:30) вызывает `_f3d_close_stale_attendances`. Включены `stale_close_enabled=True`, fallback 60 мин, `max_shift_h=16`. В базе 35 открытых hr.attendance с check_in 2026-10-12 03:40–03:59 и пустым check_out. Крон их закроет. Ожидание: решение, закрывать ли эти отметки, до запуска. Код: `models/f3d_access_event.py:554–573`.
Шаги: `hr.attendance` с `check_out = False` → 35 записей. Не тестировал вживую, чтобы не менять данные.

**2. СРЕДНЕ (расхождение с отчётом).** Отчёт лидера `build/modules/factory3d_access.md` пишет «мост factory3d_access_telemetry не установлен/не тестирован». На сервере установлены `factory3d_access_telemetry` 19.0.1.0.0 и `factory3d_telemetry` 19.0.1.1.0. Нужна сверка. Стыковые AC-53, AC-68 при этом не проверены (см. ниже).

**3. СРЕДНЕ (не подтверждено вживую).** Группа «Охорона» имеет RW на `f3d.access.door` (`security/ir.model.access.csv`, строка `access_f3d_access_door_security`). SPEC §13.3 даёт RW только для `alarm*`. Ограничение есть только в коде: `models/f3d_access_door.py:79–80` (`write`). Проверить под пользователем Охорона: запись `name` должна давать AccessError.

**4. НИЗКО (конфигурация тестовой базы).** Сервер «BioStar 2 (емулятор)» активен, `factory3d.access.read_enabled=True`, `url=https://iot-sim:8443` не резолвится. Опрос идёт каждую минуту с backoff. AC-08 работает. `factory3d.access.migration_state=partial`, в отчёте миграции `home_zone_missing=1`, `attendances_touched=0` из 35.

**5. НИЗКО (косметика).** Два меню «Сервери BioStar»: id 520 в «Завод 3D/Доступ» (sequence 90) и id 521 в «Attendances/Configuration» (sequence 50). Одинаковые имена.

## Не проверено и почему

1. Роли «Охорона», «Адміністратор СКУД», «HR» (AC-62 по строкам, AC-63, AC-50, ТБ-07). Коннектор отклоняет запись `res.users.groups_id` и `res.groups.users` (ошибка без текста). Пользователи `qa-access-security`, `qa-access-admin`, `qa-access-hr` не созданы: их create падал. В обход коннектора не ходил. Нужно назначить группы вручную в UI или подтвердить способ.
2. Права Охраны на door: RW только `alarm*` (дефект 3). Требует логина под Охраной.
3. Браузер и UI: формы, списки, 3D-просмотр. Не делал из-за таймбокса.
4. Крон 54 «ротація і закриття відміток» не запускался: закроет 35 открытых отметок (дефект 1). Не запускался также `_f3d_process` напрямую: коннектор не пускает методы с подчёркиванием. Обработка идёт через публичный `action_reprocess`.
5. AC-41–47: блокировка, возврат карт, пул визитора, `action_expect`, синхронизация BioStar. Требуют `write_enabled=True` или не запускались (write_enabled=False, менять конфиг не стал).
6. AC-27–30, AC-45: домашняя зона, zone_dwell по сценариям, нарушение зоны визитора.
7. AC-53, AC-68: телеметрия, мост. Проверено только установка (дефект 2).
8. AC-64: отсутствие полей с биометрией в `fields_get`.
9. AC-69: `action_f3d_access_settings`, target=current. Проверено только меню (родитель и sequence).

Мусор: см. шапку. Пароль тестового пользователя `qa-access-plain` записан в скрипт в scratchpad (`/tmp/claude-0/-home-user-todo-timur/c00ab7e6-c2ea-5355-9cae-b7d9087feae4/scratchpad/qa_access/plain_check.py`) и в отчёт не вынесен. HTTP-запросов к серверу: 5.
