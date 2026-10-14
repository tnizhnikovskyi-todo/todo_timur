# factory3d_base
Статус: IN_PROGRESS
Тесты: —, ТК: ждут эмулятор
Решений без заказчика: 3 (ниже)
Упирался в лимит: 0
Требует внимания человека: мост factory3d_base_mrp_maintenance не тестирован — нет Enterprise (ENV-1)

| Воркер | Статус | Коммит | Тест |
|---|---|---|---|
| W0 | принят | 86ce45e | TestInstall OK |
| W1 | в работе | | |
| W2 | | | |
| W4 | | | |
| W3 | | | |
| W5 | | | |

## Решения без заказчика
- DEC-1 (ENV-1): `mrp_maintenance` недоступен — убран из `depends`; связь оборудование↔РЦ по `f3d_code` (A-15);
  заполнение `maintenance.equipment.workcenter_id` — мост `factory3d_base_mrp_maintenance` (auto_install). Шаги хука,
  читающие `workcenter_id`, выполняются только при наличии поля. — `__manifest__.py`, `hooks/zones.py`
- DEC-2: `data/f3d_actions.xml` (§0 SPEC) не распределён в §6 ARCHITECTURE — отдан W5 (ссылается на модель домішки
  и `f3d_run_migration`).
- DEC-3: в `__manifest__.py` → `data` W0 перечисляет только существующие файлы; файлы воркеров добавляет лидер при приёмке.
