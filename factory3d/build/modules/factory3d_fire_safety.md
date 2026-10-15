# factory3d_fire_safety
Статус: IN_PROGRESS
Тесты: /factory3d_fire_safety 114/114 (2026-10-15), ТК: ждут стенда
Решений без заказчика: 12 (ниже)
Упирался в лимит: 0
Требует внимания человека: AC-77 «signal_count=45» против Додатка B (46+запиленість) — тест ≥45

| Воркер | Статус | Коммит | Тест |
|---|---|---|---|
| W0 | принят | 8c85402 | TestW0Skeleton 4/4, test_data_sync 2/2 |
| W1 | принят | 48d3d27 (+f2c4b48 слияние) | модуль 50/50 вместе с W3 |
| W3 | принят | b652677 (+f717785 слияние) | модуль 50/50 |
| W2 | принят | 3e5cce3 | модуль 84/84; AC-22 (totals), AC-31 — на W4/W5 |
| W4 | принят | 9cad410 | модуль 114/114 (с test-модулем и без); +iot_sim/access 30/30 |
| W5 | в работе | — | — |
| W6 | — | — | — |

## Решения без заказчика
- DEC-1: W0 не может поставить data-файлы и access.csv для моделей, которых ещё нет. W0 генерирует все data-файлы,
  но в `data` манифеста и в access.csv — только то, что ставится без моделей; остальное лидер включает по мере
  приёмки W1/W3/W2/W4 (порядок списка — как SPEC §1). — `__manifest__.py`
- DEC-2 (ENV): pytest `tests/test_data_sync.py` (AC-71) запускается только с Odoo в PYTHONPATH
  (пакет tests импортирует odoo); фактически гоняется `python3 -m unittest discover -s tests -t tests -p test_data_sync.py`, 2/2 OK. — `tests/test_data_sync.py`
- DEC-3: `f3d_fire_norm.csv` грузится CSV без noupdate (SPEC §0 помечает noupdate=1; CSV его не поддерживает) — оставлено как в
  манифесте SPEC §1. Для 7 авторских норм ref/note из Додатка D, формулировка примечаний — W0. — `data/f3d_fire_norm.csv`
- DEC-4: SPEC §1 называет CSV `f3d_fire_norm.csv` и т. п., но Odoo берёт модель из имени CSV — переименованы в
  `f3d.fire.<model>.csv` (norm, zone, smoke.zone, device, exit); манифест и gen_data.py поправлены. — `data/`
- DEC-5: регэксп ключа нормы `^[A-Za-z0-9_]+$` вместо `[a-z0-9_]`: в данных макета есть `evac_distance_prod_B`. — `models/f3d_fire_norm.py`
- DEC-6: скелет `f3d.fire.drill` (name, zone_id, state) до W4 — на него ссылается журнал событий W1. — `models/f3d_fire_drill.py`
- DEC-7: `target="inline"` недопустим в Odoo 19 — у `action_f3d_fire_settings` target не задан. — `views/res_config_settings_views.xml`
- DEC-8: булевы настройки пишутся явно 'True'/'False' (стандарт удаляет параметр при False → умолчание True). — `models/res_config_settings.py`
- DEC-9: команда ТО из `team_id` ставится на заявки telemetry (threshold/stale); явную команду других вызывающих не трогаем;
  событие журнала привязывается к заявке в конце FireSync.run. — `models/maintenance_request.py`, `tools/sync.py`
- DEC-10: прошлое состояние DI2/3/4/6 систем — из последнего события системы; `sprinkler_low` пишется при любом входе в
  `low_pressure`. Строки access для моделей W4 — в `security/ir.model.access_w4_pending.csv` до W4. — `tools/sync.py`
- DEC-11: `_cron_tick` в одном запуске крона делает 5 тиков с шагом 10 с (commit между ними), в тестах — 1 тик
  (`odoo.modules.module.current_test`; `registry.in_test_mode()` в Odoo 19 нет). — `models/f3d_fire_drill.py`
- DEC-12: при установленном access его источник (приоритет 10) перекрывает hr_attendance; R-18 пишет `device_id`, только
  если сповіщувач в зоне навчання; тесты AC-49/access — skipUnless модулей. — `models/passage_source.py`, `models/f3d_fire_drill.py`
