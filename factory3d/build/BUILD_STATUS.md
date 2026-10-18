# Состояние сборки factory3d

Правит только менеджер (`factory3d/build/MANAGER.md`). Лидеры модулей пишут в `factory3d/build/modules/<m>.md`.

Шаг 0: не начат
Ветка интеграции: `claude/factory3d-build` (ещё не создана)
Документация заморожена на коммите: —

## Модули

Статусы: `TODO` → `IN_PROGRESS` → `DONE`; `BLOCKED` (причина в отчёте модуля); `BLOCKED-ENV` (зависимость не ставится в среде).

| # | Модуль | Фаза | Зависит от (factory3d) | Статус | Сессия | Старт | Готов | Тесты | DEC |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `td_factory3d` | 1 | — | TODO | | | | | |
| 2 | `td_iot_sim` | 1 | base | TODO | | | | | |
| 3 | `td_telemetry` | 2 | base | TODO | | | | | |
| 4 | `td_viewer3d` | 1 | base | TODO | | | | | |
| 5 | `td_access` | 4 | base | TODO | | | | | |
| 6 | `td_machine_connect` | 2 | telemetry | TODO | | | | | |
| 7 | `td_energy` | 3 | telemetry | TODO | | | | | |
| 8 | `td_yard` | 4 | base, telemetry | TODO | | | | | |
| 9 | `td_bms` | 5 | telemetry | TODO | | | | | |
| 10 | `td_fire_safety` | 5 | telemetry | TODO | | | | | |
| 11 | `td_genset` + мост `td_genset_factory3d` | 3 | base, telemetry, energy | TODO | | | | | |

Порядок строк — приоритет запуска. Эмулятор (`iot_sim`) и телеметрия идут раньше: от них зависят стендовые тесты.
Мостики auto_install (`td_viewer3d_sale`, `td_telemetry_viewer3d`, `td_fire_safety_viewer3d`,
`td_access_telemetry`) делают лидеры модулей, в чьих §6 они описаны.

## Среда

Зависимости Odoo по модулям (из `docs/ARCHITECTURE.md` §3). Колонку «Ставится» заполняет шаг 0.

| Модуль | Зависимости Odoo | Ставится |
|---|---|---|
| base | stock, mrp, maintenance, mrp_maintenance, hr, stock_picking_batch, stock_fleet, fleet, web | |
| viewer | bus, web | |
| iot_sim | — | |
| telemetry | maintenance, mail, web | |
| machine_connect | mrp_workorder | |
| energy | mrp_account, mrp_workorder, analytic, web_hierarchy | |
| genset (мост) | td_genset | |
| yard | stock_picking_batch, stock_fleet, delivery, stock_delivery, web_gantt, mail, bus | |
| access | hr_attendance, mail | |
| bms | web | |
| fire_safety | hr_attendance | |

## Журнал менеджера

Коротко, одна строка на событие: дата, модуль, что произошло.
