# Состояние сборки factory3d

Правит только менеджер (`factory3d/build/MANAGER.md`). Лидеры модулей пишут в `factory3d/build/modules/<m>.md`.

Шаг 0: в работе (0.1 готов)
Ветка интеграции: `claude/factory3d-build`
Документация заморожена на коммите: `9b5cbb5`
BUILD_STATUS ведётся в ветке менеджера `claude/funny-knuth-8tq7jy`; интеграция — в отдельном worktree `claude/factory3d-build`.

## Модули

Статусы: `TODO` → `IN_PROGRESS` → `DONE`; `BLOCKED` (причина в отчёте модуля); `BLOCKED-ENV` (зависимость не ставится в среде).

| # | Модуль | Фаза | Зависит от (factory3d) | Статус | Сессия | Старт | Готов | Тесты | DEC |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `factory3d_base` | 1 | — | TODO | | | | | |
| 2 | `factory3d_iot_sim` | 1 | base | TODO | | | | | |
| 3 | `factory3d_telemetry` | 2 | base | TODO | | | | | |
| 4 | `factory3d_viewer` | 1 | base | TODO | | | | | |
| 5 | `factory3d_access` | 4 | base | TODO | | | | | |
| 6 | `factory3d_machine_connect` | 2 | telemetry | TODO | | | | | |
| 7 | `factory3d_energy` | 3 | telemetry | TODO | | | | | |
| 8 | `factory3d_yard` | 4 | base, telemetry | TODO | | | | | |
| 9 | `factory3d_bms` | 5 | telemetry | TODO | | | | | |
| 10 | `factory3d_fire_safety` | 5 | telemetry | TODO | | | | | |
| 11 | `td_genset` + мост `factory3d_genset` | 3 | base, telemetry, energy | TODO | | | | | |

Порядок строк — приоритет запуска. Эмулятор (`iot_sim`) и телеметрия идут раньше: от них зависят стендовые тесты.
Мостики auto_install (`factory3d_viewer_sale`, `factory3d_telemetry_viewer`, `factory3d_fire_safety_viewer`,
`factory3d_access_telemetry`) делают лидеры модулей, в чьих §6 они описаны.

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

- 2026-10-14 менеджер: шаг 0.1 — создана `claude/factory3d-build` от `9b5cbb5`; решение: BUILD_STATUS живёт в ветке менеджера, чтобы продолжение после очистки контекста видело актуальное состояние.
