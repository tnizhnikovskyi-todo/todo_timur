# Состояние сборки factory3d

Правит только менеджер (`factory3d/build/MANAGER.md`). Лидеры модулей пишут в `factory3d/build/modules/<m>.md`.

Шаг 0: готов
Ветка интеграции: `claude/factory3d-build`
Документация заморожена на коммите: `9b5cbb5`
BUILD_STATUS ведётся в ветке менеджера `claude/funny-knuth-8tq7jy`; интеграция — в отдельном worktree `claude/factory3d-build`.

## Модули

Статусы: `TODO` → `IN_PROGRESS` → `DONE`; `BLOCKED` (причина в отчёте модуля); `BLOCKED-ENV` (зависимость не ставится в среде).

| # | Модуль | Фаза | Зависит от (factory3d) | Статус | Сессия | Старт | Готов | Тесты | DEC |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `factory3d_base` | 1 | — | DONE | session_01QHzZ3cNyHZ2W6eBd43JJwn | 2026-10-14 22:04 UTC | 2026-10-14 23:17 UTC | 150/150 | 15 |
| 2 | `factory3d_iot_sim` | 1 | base | DONE | session_019MFyhB78Wd7hgrNLzgRGkP | 2026-10-14 23:18 UTC | 2026-10-15 04:30 UTC | Odoo 140/140, svc 451/451 | 18 |
| 3 | `factory3d_telemetry` | 2 | base | DONE | session_01NF5Tuhsrpzgd1SMkYaMG8N | 2026-10-15 06:47 UTC | 2026-10-15 11:43 UTC | Odoo 541/541 (6 модулей), collector 174+2 skip | 16 |
| 4 | `factory3d_viewer` | 1 | base | IN_PROGRESS | session_01HJS765EQsGKtWkA6ocokUP | 2026-10-15 08:33 UTC | | | |
| 5 | `factory3d_access` | 4 | base | DONE | session_01VWzBg1ho7GaJgftY7d5EgN | 2026-10-15 08:55 UTC | 2026-10-15 10:59 UTC | 156/156 (вместе с base+iot_sim 296/296) | 13 |
| 6 | `factory3d_machine_connect` | 2 | telemetry | IN_PROGRESS | session_015rKvjaStE6jPJzyWqGrcwf | 2026-10-15 11:44 UTC | | | |
| 7 | `factory3d_energy` | 3 | telemetry | TODO | | | | | |
| 8 | `factory3d_yard` | 4 | base, telemetry | TODO | | | | | |
| 9 | `factory3d_bms` | 5 | telemetry | TODO | | | | | |
| 10 | `factory3d_fire_safety` | 5 | telemetry | TODO | | | | | |
| 11 | `td_genset` + мост `factory3d_genset` | 3 | base, telemetry, energy | TODO | | | | | |

Порядок строк — приоритет запуска. Эмулятор (`iot_sim`) и телеметрия идут раньше: от них зависят стендовые тесты.
Мостики auto_install (`factory3d_viewer_sale`, `factory3d_telemetry_viewer`, `factory3d_fire_safety_viewer`,
`factory3d_access_telemetry`) делают лидеры модулей, в чьих §6 они описаны.

## Среда

Зависимости Odoo по модулям (из `docs/ARCHITECTURE.md` §3). Odoo 19.0 CE `bc77fac7`; скрипты `factory3d/tools/odoo/` (`setup.sh` с нуля ≈3 мин).
Нет в среде: `mrp_maintenance`, `mrp_workorder`, `web_gantt` → решения ENV-1..4 в `factory3d/build/ENV_DECISIONS.md` (ветка интеграции).

| Модуль | Зависимости Odoo | Ставится |
|---|---|---|
| base | stock, mrp, maintenance, mrp_maintenance, hr, stock_picking_batch, stock_fleet, fleet, web | кроме mrp_maintenance → ENV-1 |
| viewer | bus, web | да |
| iot_sim | — | да |
| telemetry | maintenance, mail, web | да |
| machine_connect | mrp_workorder | нет → ENV-3 |
| energy | mrp_account, mrp_workorder, analytic, web_hierarchy | кроме mrp_workorder → ENV-2 |
| genset (мост) | td_genset | свой модуль, переносит лидер |
| yard | stock_picking_batch, stock_fleet, delivery, stock_delivery, web_gantt, mail, bus | кроме web_gantt → ENV-4 |
| access | hr_attendance, mail | да |
| bms | web | да |
| fire_safety | hr_attendance | да |

## Журнал менеджера

Коротко, одна строка на событие: дата, модуль, что произошло.

- 2026-10-14 менеджер: шаг 0.1 — создана `claude/factory3d-build` от `9b5cbb5`; решение: BUILD_STATUS живёт в ветке менеджера, чтобы продолжение после очистки контекста видело актуальное состояние.
- 2026-10-14 менеджер: шаг 0.2–0.3 — скрипты Odoo 19 в `claude/factory3d-build` (`49decab`), смоук зелёный; нет mrp_maintenance, mrp_workorder, web_gantt.
- 2026-10-14 менеджер: решение ENV-1..4 (`f0fbe9f`) — ядро на CE, Enterprise-часть в мосты auto_install; вместо BLOCKED-ENV для base/energy/machine_connect/yard.
- 2026-10-14 22:04 UTC factory3d_base: запущена сессия session_01QHzZ3cNyHZ2W6eBd43JJwn (1/2 за 24 ч).
- 2026-10-14 23:17 UTC factory3d_base: DONE — смержен в `claude/factory3d-build` (`298871a`), тесты 150/150, DEC 15. Не проверено: ТК-01…05 (нужна копия базы `odoo`), мост `factory3d_base_mrp_maintenance` (нет Enterprise, ENV-1).
- 2026-10-14 23:18 UTC factory3d_iot_sim: запущена сессия session_019MFyhB78Wd7hgrNLzgRGkP (2/2 за 24 ч; следующий слот — 2026-10-15 22:04 UTC).
- 2026-10-15 04:30 UTC factory3d_iot_sim: DONE — смержен в `claude/factory3d-build` (`609a247`), Odoo 140/140 (base+iot_sim), сервис 451/451, DEC 18. Не проверено: ТК-01/15 на копии базы `odoo`, ТК-18 (нет genset_relay в td_genset, CI-02), ТП-06 24 ч; ТП-04 p95 1,39 с > 1 с (медиана в норме); подпись security-review — за человеком.
- 2026-10-15 04:30 UTC менеджер: лимит запусков 2/24 ч исчерпан; следующий запуск (`factory3d_telemetry`) — 2026-10-15 22:05 UTC.
- 2026-10-15 06:47 UTC factory3d_telemetry: запущена сессия session_01NF5Tuhsrpzgd1SMkYaMG8N по прямому указанию пользователя сверх лимита (3/2 за 24 ч). Пауза до 22:05 отменена. Дальше лимит «2 за 24 ч» снова действует: следующий запуск — когда в окне 24 ч останется меньше 2 сессий (после 2026-10-15 23:19 UTC).
- 2026-10-15 08:33 UTC factory3d_viewer: запущена сессия session_01HJS765EQsGKtWkA6ocokUP по прямому указанию пользователя сверх лимита (4 за 24 ч); одновременно 2 (telemetry, viewer).
- 2026-10-15 08:55 UTC factory3d_access: запущена сессия session_01VWzBg1ho7GaJgftY7d5EgN по прямому указанию пользователя сверх лимитов (5 за 24 ч; одновременно 3: telemetry, viewer, access).
- 2026-10-15 09:58 UTC менеджер: правки SPEC по DEC (base DEC-5/11/15, iot_sim DEC-4/11, telemetry DEC-10, access AC-69) — `fa69787` в `claude/factory3d-build`; отчёт base (ТК-01 частично на timur-o19demo) смержен — `c3c845b`.
- 2026-10-15 10:59 UTC factory3d_access: DONE — смержен в `claude/factory3d-build` (`9ab374a`), Odoo 296/296 (base+iot_sim+access), DEC 13. Не проверено: мост `factory3d_access_telemetry` (нет telemetry), ТК-09 (viewer), ТК-10 drill (fire_safety), копия базы `odoo`. Найдено: эмулятор iot_sim отдаёт 404 вместо 405 (D-2); ERROR FK `card.server_id` при деинсталляции (O-1); подпись security/pr-review — за человеком.
- 2026-10-15 11:36 UTC менеджер: исправлены D-2 (эмулятор iot_sim: 405 вместо 404, `d79c297`, svc 463/463) и O-1 (uninstall factory3d_access без FK ERROR, `e6ebb47`, Odoo 297/297) в `claude/factory3d-build`.
- 2026-10-15 11:43 UTC factory3d_telemetry: DONE — смержен в `claude/factory3d-build` (`d10cd6e`), Odoo 541/541 (base, iot_sim, access, telemetry + мосты access_telemetry, telemetry_viewer), collector unit 174 + 2 skip (MQTT без docker), DEC 16. Не проверено: стенд ТК-03/09/10 (красные в полном прогоне), ТК-12, ТП-06 — на сервере с Docker; ТП-04 объём таблиц выше оценки (DEC-16).
- 2026-10-15 11:44 UTC factory3d_machine_connect: запущена сессия session_015rKvjaStE6jPJzyWqGrcwf по указанию пользователя; одновременно 2 (viewer, machine_connect).
