# QA factory3d_energy
Статус: PARTIAL
Проверено: 15, провалено: 1, не проверено: 11 (2026-10-15, коммит 29a088e; код на HEAD 6328313 его включает; тестировалась установленная версия 19.0.1.0.0)
Дефекты: 3 (критичных: 1)
Мусор в базе: res.users id 10 (qa-energy-master), 11 (qa-energy-manager), 12 (qa-energy-accountant); тестовый пароль лежит в scratchpad, в скрипте qa_energy_roles.py. f3d.energy.balance: 192 строки создал крон при запуске (state=skipped, не QA-записи). Три попытки создать пользователей без `group_ids` вернули ошибку; id 10–12 идут подряд, но проверить, что лишних записей нет.

Соединение: connection_id AxI--dg8QCmJAxW_, connection.db = "odoo" (проверено на каждом вызове). HTTP-запросов: около 47 из 50.

| # | AC / сценарий | Способ | Результат | Доказательство |
|---|---|---|---|---|
| 1 | Установка, версия | ir.module.module | PASS: installed, 19.0.1.0.0 = манифест | RPC, модуль id 1487 |
| 2 | Меню и действия | ir.model.data (menu_f3d_energy_*, action_f3d_energy_*), ir.actions.act_window | PASS: 16 меню, 13 действий, res_model и view_mode заданы | RPC |
| 3 | Представления f3d.energy.node | get_views (list, form, search, hierarchy) | PASS: все 4 загружаются. Остальные представления отдельно не запрашивались | RPC |
| 4 | Отчёт установки и состав данных (AC-12/13, AC-01/04/05) | ir.config_parameter factory3d.energy.install_report, search_count | PASS: state=done; nodes 123, meters 67, pools 5, signals 297, critical 10, equipment_linked 80, workcenter_linked 35, unmatched 0. Цифры совпадают с AC-13 (копия демо) | install_report |
| 5 | Лічильник ↔ сигнали ↔ вузол (AC-05) | f3d.energy.meter search_read, 4 лічильники: PM-Q1, PM-Q2, PM-QF-3, PM-SAW-1 | PASS: e_import/e_export/p_signal и node_id заполнены; коды сигналов по AC-05 | RPC |
| 6 | Прапори читання і запису (AC-80, AC-23 частково) | ir.config_parameter factory3d.energy.* | PASS: read_enabled=True, write_enabled=False | RPC |
| 7 | Крони (§6): 4 из 5 | ir.cron.method_direct_trigger, ids 64, 65, 66, 67 | PASS: каждый вернул true; lastcall обновлён 21:14:49–52, nextcall сохранён. cron_rotate не запускался (см. ниже) | RPC ir.cron |
| 8 | Баланс без даних (AC-31) | f3d.energy.balance search_read | PASS: 192 строки, state=skipped, reason «немає даних: PM-Q1 (немає інтервалів)…» | RPC |
| 9 | Живые тотали при stale-фидерах (AC-29, вторая часть) | f3d.signal energy/totals/p_now, grid15_kw | PASS (согласовано): last_ts пуст, тотали не пишутся, потому что фидеры без данных | RPC |
| 10 | HTTP-эндпоинты (§7) | grep http.route и controllers/ по модулю | PASS: эндпоинтов нет, как в SPEC §7; каталога controllers нет | grep, пусто |
| 11 | Роль master: кВт·год доступен, вартість закрыта (AC-54) | HTTP JSON-RPC check_field_access_rights (uid 10) | PASS: f3d_energy_kwh разрешено; f3d_energy_cost → AccessError | логин qa-energy-master |
| 12 | Роль master: запись вузла запрещена (AC-78) | check_access_rights('write') | PASS: False | HTTP, uid 10 |
| 13 | Роль енергетик: запись вузла и вартість (AC-77) | то же, uid 11 | PASS: write=True; f3d_energy_cost разрешено | HTTP, uid 11 |
| 14 | Роль бухгалтер: вартість есть, запись вузла запрещена (AC-77/78) | то же, uid 12 | PASS: cost разрешено; write=False | HTTP, uid 12 |
| 15 | Расход кВт·год из показаний (AC-15–22, AC-37) | крон интервалов + чтение counter-сигналов | NOT: сигналы kwh_total (id 438, 511, 525, 559) без показаний, last_value=0, last_ts пуст; интервалов 0 (см. Д-1) | f3d.reading, f3d.signal |
| 16 | Тарифы, зоны, цена (AC-07–11) | _f3d_price_at (приватный) | NOT: приватные методы не вызываются через RPC. Демо-тариф id 1 есть (contract 800 кВт, peak_warn 90 %) | — |
| 17 | API-01/02 кВт·год (AC-87) | _f3d_kwh, _f3d_kwh_by_code (приватные) | NOT: то же ограничение RPC; вызовы дали ошибку | — |
| 18 | Защита от записи (AC-81) | odoo_write write_enabled=True на сигнал id 438 | NOT: запись отклонена политикой прав, не повторялась. Нужно решение человека | ответ классификатора |
| 19 | Повторная привязка (AC-14) | action_f3d_energy_rebind | NOT: не запускалась, она перезаписывает install_report | — |
| 20 | Энергия WO на Enterprise (FR-08, AC-37–41, мост) | mrp_workorder установлен; моста нет | NOT: мост factory3d_energy_mrp_workorder не установлен и отсутствует в odoo_addons (см. Д-3) | ir.module.module |
| 21 | Распределение и МО (AC-37–52) | крон распределения | NOT: крон запущен (lastcall обновлён), но входных данных нет, расчёт не проверен | ir.cron 66 |
| 22 | Ротация (AC-84) | cron_rotate | NOT: не запускался, так как удаляет записи по дизайну | — |
| 23 | Журнал ошибок кронов | ir.logging | NOT: таблица ir.logging пуста за всё время, отсутствие ошибок не доказательство (см. ниже) | ir.logging count=0 |
| 24 | Веб-интерфейс (формы, списки, 3D) | браузер | NOT: таймбокс | — |
| 25 | Мультикомпания (AC-79) | — | NOT: не проверялась | — |
| 26 | Синхронизация сигнала и показаний | f3d.signal id 1 + f3d.reading | FAIL (подозрение): signal last_ts 20:36:22, значение 12.431; последнее показание 21:00:22, значение 12.822 (см. Д-2) | f3d.signal id 1, f3d.reading |

Счёт: строки 1–14 и 26 выполнены (15, из них 1 провал). Строки 15–25 не проверены (11).

## Дефекты

### Д-1 (критичный, блокер данных; не дефект кода модуля)
- Шаги: модуль установлен; запущен `cron_f3d_energy_intervals` через method_direct_trigger.
- Ожидание: 15-минутный профиль строится по показаниям счётчиков (R-04, AC-21, AC-22), затем распределение (AC-37).
- Факт: `f3d.energy.interval` = 0, `f3d.energy.alloc` = 0. У всех 67 лічильників `data_state = no_data`. Сигналы `kwh_total` (id 438, 511, 525, 559) имеют `last_value=0`, `last_ts` пуст, записей `f3d.reading` на них нет. Показания есть только у `p_now` (`src=sim_data`).
- Вероятная причина: partial-миграция telemetry, уже известна. Место в коде: `odoo_addons/factory3d_telemetry/hooks.py:663` (состояние `partial`).

### Д-2 (средний, подозрение, требует проверки)
- Сигнал `energy/consumers/SAW-1/p_now` (id 1): `last_value=12.431`, `last_ts=2026-10-15 20:36:22`. Последнее `f3d.reading` по этому сигналу: 21:00:22, значение 12.822, `src=sim_data`.
- Ожидание: состояние сигнала соответствует последнему показанию. Факт: отстаёт. Вероятно, миграция записала показания без обновления состояния сигнала. Проверить в telemetry.

### Д-3 (средний, пробел интеграции)
- На сервере установлен Enterprise `mrp_workorder` (19.0.1.0). Моста `factory3d_energy_mrp_workorder` нет ни на сервере, ни в `odoo_addons/`. В `__manifest__.py:12–13` `mrp_workorder` убран из depends (ENV-2, DEC-1 лидера).
- Следствие: FR-08 (журнал времени WO, AC-37–41, AC-88) на Enterprise не проверен и, вероятно, не работает.

## Что не проверено и почему
- AC-07–11, AC-15–22, AC-87 (тарифы, расчёт по показаниям, API-01/02): методы с `_` недоступны через RPC. Нужны Odoo shell или тесты модуля на стенде.
- AC-81: попытка записи `write_enabled=True` на сигнал id 438 отклонена политикой прав. Не повторялась. Решение за человеком.
- AC-14: не запускалась, так как перезаписывает `factory3d.energy.install_report`.
- `cron_f3d_energy_rotate`: не запускалась, так как удаляет записи по дизайну.
- Журнал ошибок: `ir.logging` пуст за всё время. Крон ловит исключения и пишет их только в лог, поэтому ошибки могли остаться невидимыми. Нужен доступ к серверному лог-файлу.
- Веб-интерфейс, мультикомпания (AC-79), стендовые ТК-02…ТК-12 (эмулятор), мост Enterprise (Д-3): не проверено.
- Из отчёта лидера: DEC-8 (расхождение AC-32 с SPEC) и DEC-15 (380 В против 400 В) на стенде не проверялись.

## Примечания
- `f3d.source` с `module=energy`: 69 записей. Это 68 телеметрических источников плюс `EN-DERIVED`, который создаёт хук (`derived_source.created=1`). Не дефект.
- Крон `live` не записал тотали, потому что фидеры без данных. Это согласуется с AC-29, вторая часть.
