# td_yard
Статус: DONE (юнит-DoD); вне среды: ТК-01…08 и DEPLOY_TEST на копии демо-базы, мост td_yard_gantt (нет web_gantt)
Тесты: Odoo 152 (120 post + at_install) /td_yard, 0 fail (2026-10-15); плагин sics 34/34; collector unit 173 + 1 env-fail (пакет не установлен в venv, entry points пусты — не регресс); ruff/xmllint OK; ТК: ждут стенда (нет docker и копии демо)
Решений без заказчика: 8 (ниже)
Упирался в лимит: 0
Требует внимания человека: ТК-01…08/AC-75, AC-81…86 на стенде с копией демо; sudo() шире списка SPEC §4.4 (DEC-6, решение автора SPEC); миграция шаг 5 без ветки by_description (AC-76 частично); AC-58 порог 1 с вместо 50 мс; мост gantt не тестирован (DEC-1); подпись security-review менеджером

| Воркер | Статус | Коммит | Тест |
|---|---|---|---|
| W0 | принят | d01ddbd | TestYardInstall 10/10 |
| W1 | принят | 5748331 | /td_yard 34/34; AC-17, часть AC-18/19 — после W3 |
| W2 | принят | 52d45e2 | /td_yard 57/57 |
| W3 | принят | ea242c5 (+e901a87 слияние) | /td_yard 69/69, sics 34/34 |
| W4 | принят | 76ecd08 | /td_yard 89/89 (2 тура); AC-55, AC-59 — на W5 |
| W5 | принят | a561192 | /td_yard 152 (0 fail), sics 34, metrics 3 |

## Решения без заказчика
- DEC-1 (ENV): `web_gantt` (Enterprise) недоступен — убран из `depends`; gantt-представление рейсов/бронирований —
  в мосте `td_yard_gantt` (depends yard+web_gantt, auto_install), как `td_factory3d_mrp_maintenance`. — `__manifest__.py`
- DEC-2 (ENV): run_tests.sh без `F3D_TEST_INSTALL` ставит все модули и падает на `td_factory3d_mrp_maintenance` —
  тесты yard запускаются с `F3D_TEST_INSTALL=td_factory3d,td_telemetry,td_yard`. Меню W0 — каркас без
  action; воркеры добавляют `action=` повторным `menuitem` с тем же id. — `views/td_yard_menus.xml`
- DEC-3: W2 ∥ W3 в worktree; запись весов — в `data/td_yard_scale_data.xml` (W3), а не в `td_yard_gate_data.xml` (W2),
  чтобы не конфликтовать; `td_yard_signals.csv` сливает лидер. — `data/`
- DEC-4: W5 добавил record rules по компании для 6 моделей (§4.3; без них AC-69 падал). — `security/td_yard_security.xml`
- DEC-5: AC-48 проверяется моком (_f3d_yard_safe не вызывается для чужих кодов), а не счётчиком запросов. — `tests/test_migration.py`
- DEC-6: sudo() вне §4.4: sequence в visit.create, driver в onchange, action_leave/picking_ids (чтение), действия ворот, провайдер viewer, kpp_data, мастера walkin/reject — все после `_f3d_yard_require` или только чтение; нужна правка §4.4 SPEC. — models/*
- DEC-7: AC-60 — среднее длительностей только по рейсам с нужными метками (float пишет 0.0 вместо NULL). — `models/td_yard_visit_kpp.py`
- DEC-8: res.config.settings в Odoo 19 не принимает target='inline' — убран; отчёт миграции вложен по шагам. — `views/res_config_settings_views.xml`, `hooks/migrate.py`
