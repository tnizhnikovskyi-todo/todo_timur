# factory3d_base
Статус: IN_PROGRESS
Тесты: —, ТК: ждут эмулятор
Решений без заказчика: 8 (ниже)
Упирался в лимит: 0
Требует внимания человека: мост factory3d_base_mrp_maintenance не тестирован — нет Enterprise (ENV-1)

| Воркер | Статус | Коммит | Тест |
|---|---|---|---|
| W0 | принят | 86ce45e | TestInstall OK |
| W1 | принят | 0ee48e8 | /factory3d_base 26/26 |
| W2 | принят | 0766b01 | /factory3d_base 42/42 (2 skip до W3/W4) |
| W4 | в работе | | |
| W3 | | | |
| W5 | | | |

## Решения без заказчика
- DEC-1 (ENV-1): `mrp_maintenance` недоступен — убран из `depends`; связь оборудование↔РЦ по `f3d_code` (A-15);
  заполнение `maintenance.equipment.workcenter_id` — мост `factory3d_base_mrp_maintenance` (auto_install). Шаги хука,
  читающие `workcenter_id`, выполняются только при наличии поля. — `__manifest__.py`, `hooks/zones.py`
- DEC-2: `data/f3d_actions.xml` (§0 SPEC) не распределён в §6 ARCHITECTURE — отдан W5 (ссылается на модель домішки
  и `f3d_run_migration`).
- DEC-3: в `__manifest__.py` → `data` W0 перечисляет только существующие файлы; файлы воркеров добавляет лидер при приёмке.
- DEC-4: `f3d_code`/`f3d_alias` без `size=32` — длину проверяет `_check_f3d_codes` (AC-01 ждёт ValidationError, а не DataError). — `models/f3d_scene_mixin.py`
- DEC-5: `hr.employee.public._rec_names_search = ['name','f3d_code']` — иначе поиск по коду без прав HR пуст (AC-55); в M-10a отсутствует. — `models/hr_employee.py`
- DEC-6: `f3d_resolve` пропускает модели без `search_f3d`. Кнопка «Показати в 3D» в форме сотрудника — в `<header groups=hr.group_hr_user>`. — `models/f3d_scene_mixin.py`, `views/hr_employee_views.xml`
- DEC-7: описания надворных зон — краткие тексты воркера, не `desc` из `site2.py`; генератор зон не в репо (данные из `plant/layout.py`, `dist/odoo_demo.json`). — `data/f3d_zone_data.xml`
- DEC-8: ENV-1 в `zones.bind`: без `workcenter_id` зона оборудования берётся у РЦ с тем же `f3d_code` (A-15); шаги для моделей без `f3d_code` пропускаются. Вызов `zones.bind` из `post_init_hook` — у W5. — `hooks/zones.py`
- TODO W3/W4: в V-01 (форма зоны) дописать поля локаций/обладнання/ворот; `f3d_zone_id` в форму РЦ.
