# factory3d_yard
Статус: IN_PROGRESS
Тесты: 69/69 /factory3d_yard (W0–W3, 2026-10-15), плагин sics 34/34; ТК: ждут стенда (W5)
Решений без заказчика: 3 (ниже)
Упирался в лимит: 0
Требует внимания человека: нет

| Воркер | Статус | Коммит | Тест |
|---|---|---|---|
| W0 | принят | d01ddbd | TestYardInstall 10/10 |
| W1 | принят | 5748331 | /factory3d_yard 34/34; AC-17, часть AC-18/19 — после W3 |
| W2 | принят | 52d45e2 | /factory3d_yard 57/57 |
| W3 | принят | ea242c5 (+e901a87 слияние) | /factory3d_yard 69/69, sics 34/34 |
| W4 | в работе | — | — |

## Решения без заказчика
- DEC-1 (ENV): `web_gantt` (Enterprise) недоступен — убран из `depends`; gantt-представление рейсов/бронирований —
  в мосте `factory3d_yard_gantt` (depends yard+web_gantt, auto_install), как `factory3d_base_mrp_maintenance`. — `__manifest__.py`
- DEC-2 (ENV): run_tests.sh без `F3D_TEST_INSTALL` ставит все модули и падает на `factory3d_base_mrp_maintenance` —
  тесты yard запускаются с `F3D_TEST_INSTALL=factory3d_base,factory3d_telemetry,factory3d_yard`. Меню W0 — каркас без
  action; воркеры добавляют `action=` повторным `menuitem` с тем же id. — `views/f3d_yard_menus.xml`
- DEC-3: W2 ∥ W3 в worktree; запись весов — в `data/f3d_yard_scale_data.xml` (W3), а не в `f3d_yard_gate_data.xml` (W2),
  чтобы не конфликтовать; `f3d_yard_signals.csv` сливает лидер. — `data/`
