# factory3d_telemetry
Статус: IN_PROGRESS
Тесты: Odoo 198/198, collector 100/100 (2026-10-15), ТК: —
Решений без заказчика: 9 (ниже)
Упирался в лимит: 0
Требует внимания человека: нет

| Воркер | Статус | Коммит | Тест |
|---|---|---|---|
| W0 | принят | 9f4c7d0 | TestInstall 3/3 |
| W1 | принят | 892f58f | /factory3d_telemetry 118/118 |
| W5 | принят | 3c6830c | pytest unit 100/100, ruff, mypy |
| W2 | принят | ef075c1 | /factory3d_telemetry 140/140 |
| W6 | в работе | | |
| W3 | принят | 33244f2 | telemetry+viewer 198/198 (2 skip AC-70) |
| W4 | в работе | | |
| W7 | | | |

## Решения без заказчика
- DEC-1: модуль должен ставиться до появления моделей — в `__manifest__` `data` только существующие файлы, хуки не подключены;
  полные тексты §4.1/§4.3/§6/§3 лежат в `*.full` (access.csv, security_rules.xml, ir_cron.xml, menus.xml), лидер переносит при приёмке W1–W4.
- DEC-2: `NotSupported` временно определён в `collector/plugins/base.py`, W5 переносит в ядро. — `collector/plugins/base.py`
- DEC-3: `f3d.collector/source/signal.code` без `size` — длину проверяет constraint (AC-02/AC-08 ждут ValidationError). — `models/f3d_*.py`
- DEC-4: `maintenance.equipment.f3d_meter_signal_id` — заглушка в конце `models/f3d_signal.py` (W2 переопределяет); `_open_request`/`_on_request_closed` (R-05/R-06) реализованы в `f3d.signal`. CT-11 (`_f3d_import_sim_*`) — за W4.
- DEC-5: показания `kind='event'` сохраняются всегда, без учёта `store_period_s`. — `tools/ingest.py`
- DEC-6: `SourcePlugin` без `@abstractmethod`; ошибка инициализации плагина → Health `plugin init failed` (Registry). `load_plugins` — в `core/registry.py`; entry points плагинов — за W6. — `collector/core/registry.py`
- DEC-7: «Запустити міграцію» в настройках вызывает `hooks.run_level0_migration(env)`; до W4 — UserError. — `models/res_config_settings.py`
- DEC-8: `factory3d_viewer` ещё не собран, абстракции `f3d.viewer.provider` нет — провайдер M-10 сделан AbstractModel (duck typing, ARCH §6.7); мост `factory3d_telemetry_viewer` depends base+telemetry, auto_install. Добавить `factory3d_viewer` в depends после его сборки. AC-70 (bus `f3d.viewer.event`) — skip до viewer. — `factory3d_telemetry_viewer/__manifest__.py`
- DEC-9: API-05 — поле `collector` в теле необязательно (проверяется при наличии); API-07 — неизвестный `state` → `rejected`, `reason=bad_state`. — `controllers/telemetry.py`
