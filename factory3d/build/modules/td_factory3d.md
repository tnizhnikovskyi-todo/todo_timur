# td_factory3d
Статус: DONE (юнит-DoD); ТК-01…05 не прогнаны — нет копии демо-базы `odoo`
Тесты: 150/150 (/td_factory3d, 2026-10-14), ruff чисто; ТК-01 частично: установка на базе `odoo` timur-o19demo (Enterprise, 2026-10-15) — migration_state=done, коды 682/14/35/35/210, пакетов +18, mismatches 0, x_* удалены; ТК-02…05 не прогнаны
Решений без заказчика: 15 (ниже)
Упирался в лимит: 0
Требует внимания человека: ТК-01…05 по DEPLOY_TEST.md на копии базы `odoo`; мост td_factory3d_mrp_maintenance не тестирован — нет Enterprise (ENV-1); правки SPEC: DEC-5, DEC-11, DEC-15

| Воркер | Статус | Коммит | Тест |
|---|---|---|---|
| W0 | принят | 86ce45e | TestInstall OK |
| W1 | принят | 0ee48e8 | /td_factory3d 26/26 |
| W2 | принят | 0766b01 | /td_factory3d 42/42 (2 skip до W3/W4) |
| W4 | принят | 36a0877 | /td_factory3d 62/62 |
| W3 | принят | f50bbfa | /td_factory3d 84/84 |
| W5 | принят | 4140379 | /td_factory3d 150/150 |

## Решения без заказчика
- DEC-1 (ENV-1): `mrp_maintenance` недоступен — убран из `depends`; связь оборудование↔РЦ по `td_code` (A-15);
  заполнение `maintenance.equipment.workcenter_id` — мост `td_factory3d_mrp_maintenance` (auto_install). Шаги хука,
  читающие `workcenter_id`, выполняются только при наличии поля. — `__manifest__.py`, `hooks/zones.py`
- DEC-2: `data/td_actions.xml` (§0 SPEC) не распределён в §6 ARCHITECTURE — отдан W5 (ссылается на модель домішки
  и `f3d_run_migration`).
- DEC-3: в `__manifest__.py` → `data` W0 перечисляет только существующие файлы; файлы воркеров добавляет лидер при приёмке.
- DEC-4: `td_code`/`td_alias` без `size=32` — длину проверяет `_check_f3d_codes` (AC-01 ждёт ValidationError, а не DataError). — `models/td_scene_mixin.py`
- DEC-5: `hr.employee.public._rec_names_search = ['name','td_code']` — иначе поиск по коду без прав HR пуст (AC-55); в M-10a отсутствует. — `models/hr_employee.py`
- DEC-6: `f3d_resolve` пропускает модели без `search_f3d`. Кнопка «Показати в 3D» в форме сотрудника — в `<header groups=hr.group_hr_user>`. — `models/td_scene_mixin.py`, `views/hr_employee_views.xml`
- DEC-7: описания надворных зон — краткие тексты воркера, не `desc` из `site2.py`; генератор зон не в репо (данные из `plant/layout.py`, `dist/odoo_demo.json`). — `data/td_zone_data.xml`
- DEC-8: ENV-1 в `zones.bind`: без `workcenter_id` зона оборудования берётся у РЦ с тем же `td_code` (A-15); шаги для моделей без `td_code` пропускаются. Вызов `zones.bind` из `post_init_hook` — у W5. — `hooks/zones.py`
- TODO W3/W4: в V-01 (форма зоны) дописать поля локаций/обладнання/ворот; `td_zone_id` в форму РЦ.
- DEC-9: `mrp.workcenter.employee_ids` нет в CE — `codes.employees` не учитывает РЦ; данные макета: 60 единиц со складовыми (63 связи, не 61), зона в `scene_equipment_codes.csv` у 135 строк (не 121), FA-BOILER → Z-BOILER. — `hooks/codes.py`, `data/scene_equipment_codes.csv`
- DEC-10: значение параметра паспорта «пусто» = `not value_text and not value_num` (Float без NULL в CE); `codes.locations` пропускается без домішки на `stock.location`. — `models/td_equipment_passport.py`, `hooks/codes.py`
- DEC-11: синтетика TestBatchMigration — 4 пакета на 4 документа, а не 3 как в §13.1: по R-11(б)/Q-02 «один пакет на документ», противоречие внутри SPEC, приоритет у правила. — `tests/test_migration.py`
- DEC-12: `f3d_register_dock` пишет `dock_ids`/`dispatch_management` типа операции через `sudo()` (пользователь склада может не иметь прав на тип); черновики при миграции — `in_progress` напрямую, без `action_confirm`. — `models/stock_location.py:80`, `hooks/batches.py`
- DEC-13: нет ворот на чистой базе — INFO, а не WARNING (чистый лог установки); колонка `zone` в `scene_docks.csv` игнорируется (зоны — `zones.bind`). — `hooks/docks.py`
- DEC-14: `f3d_run_migration` проверяет `group_td_admin`, затем выполняет оркестратор под `sudo()` (админ без прав склада получал AccessError); `verify` вызывается только если `migrate` не skipped. — `models/td_scene_mixin.py:172`, `hooks/__init__.py`
- DEC-15: `td.zone.company_id` обязательное (M-02), поэтому ветка `company_id=False` record rule (§4.3) и случай AC-45 «зона без компании» недостижимы — противоречие в SPEC. — `models/td_zone.py:56`
- AC только синтетикой, кратности — через ТК: AC-10…12, 14, 19, 24…31, 34, 35.
