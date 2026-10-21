# QA base
Статус: PARTIAL
Проверено: 51, провалено: 4, не проверено: 13 (2026-10-15, коммит 29a088e)
Дефекты: 4 (критичных: 0)
Мусор в базе: см. раздел «Мусор в базе» ниже (QA-записи, ничего не удалялось)

Объект: factory3d_base и мост factory3d_base_mrp_maintenance на базе `odoo` (https://timur-o19demo.todo.ltd, Odoo 19.0 Enterprise). Мост впервые проверен в Enterprise: он установлен, связи 35/35 верны, Enterprise-ветки кода base (workcenter_id, employee_ids) работают, найден один отказ ветки A-15 (D-2).

| # | AC / сценарий | Способ | Результат | Доказательство |
|---|---|---|---|---|
| 1 | Установка factory3d_base: state=installed, версия = манифест | ir.module.module | PASS | 19.0.1.0.0 = 19.0.1.0.0 |
| 2 | Установка моста factory3d_base_mrp_maintenance (auto_install; mrp_maintenance installed) | ir.module.module | PASS | installed, 19.0.1.0.0 = манифест; поле maintenance.equipment.workcenter_id есть |
| 3 | Меню (11) и действия (7): get_views, sequence/родитель/группы по §3 (AC-44) | get_views + ir.ui.menu | PASS | все 7 действий отдают views; menu_f3d_root=75, группы 82/83/84 как в таблице §3 |
| 4 | AC-46: 12 параметров factory3d.base.* | ir.config_parameter | PASS | 12 ключей, migration_state=done |
| 5 | МОСТ: workcenter_id заполнен у обладнання с f3d_code = f3d_code РЦ | search_read по 210 ед. и 35 РЦ | PASS | 35 из 35 совпадений заполнены верно, чужих связей 0, расхождений зон 0 |
| 6 | МОСТ/Enterprise: zones.bind наследует зону РЦ по workcenter_id (QA eq id 214) | f3d_run_migration | PASS | f3d_zone_id=55 (зона РЦ) проставлена |
| 7 | МОСТ/Enterprise: обладнання с f3d_code = f3d_code РЦ, но без workcenter_id (A-15; QA eq id 215, РЦ id 39 с зоной) | f3d_run_migration | FAIL | workcenter_id и зона остались пустыми, см. дефект D-2 |
| 8 | Enterprise: codes.employees через mrp.workcenter.employee_ids (mrp_workorder) | f3d_run_migration, QA-сотрудники 37-39 | PASS | QAEMP1 в РЦ QA-X-1 -> OP-QA-X-1; OPW99 -> OP-W99; QAZZ без РЦ -> без кода (AC-13, AC-40) |
| 9 | Формы/списки/поиск, унаследованные base, в Enterprise (stock.location, batch, picking, mrp.workcenter, maintenance.equipment, hr.employee, f3d.zone, passport) | get_views(form,list,search,kanban) | PASS | 9 моделей без ошибок |
| 10 | UI: 15 страниц в браузере (канбан/форма зон, ворота, оборудование SAW-1 вкладки «Завод 3D»/«Паспорт», паспорт, параметры, пакет с баннером, РЦ, сотрудник) | Playwright chromium | PASS | диалогов ошибок нет, console.error нет; баннер «Ворота QA-DW-93 приймають: Плитні матеріали. У пакеті є: Крайка.» виден |
| 11 | AC-10: 696 локаций с f3d_code | search_read | PASS | 696 |
| 12 | AC-11: 14 ворот DOCK-W1..7 (UNLOAD-1..7, x=0, y=5..65) и DOCK-E1..7 (x=150, без alias) | search_read | PASS | совпало |
| 13 | AC-12: 35 РЦ с кодом = code | search_read | PASS | 35/35 |
| 14 | AC-13/39: 35 кодов сотрудников = scene_employee_codes.csv | сверка с csv | PASS | 35, расхождений 0; Administrator без кода |
| 15 | AC-14: 210 ед. с кодом, 210 уникальных | search_read | PASS | 210/210, кол-во maintenance.equipment (до QA) 210 |
| 16 | AC-15: 45 зон, типы 7/7/5/1/1/7/4/2/11, is_roof только Z-ROOF | read_group | PASS | совпало |
| 17 | AC-17: zone_at на 8 точках и roof=True | zone_at | PASS | Z-CUT, пусто, Z-SHEETS, Z-OUT-7, Z-YARD-W, Z-GATE-E, Z-ENERGY, Z-CNC; roof=True -> Z-ROOF |
| 18 | AC-19: root_location_id у 21 зоны; счётчики мест/РЦ/оборудования зон | search_read | PASS | все счётчики совпали (Z-SHEETS 123, Z-HW 144, Z-FG 360, Z-ELEC 20 и др.) |
| 19 | AC-24/25/26/27: 24 пакета (6+18), TRUCK-IN/OUT, 15 с доком, 3 внутренних с техникой, статусы done | search_read batches | PASS | BATCH/IN/00001 -> 7 западных ворот, dock=Ворота 1, DOCK-W1; done: IN 7-11 и INT 23. Снимок stock.move не сверялся |
| 20 | AC-28/52: x_dock/x_truck/x_vehicle и демо-представления удалены; 21/6/3 документов с f3d_* | ir.model.fields, search_read picking | PASS | полей и представлений нет; 21/6/3 из 42 пикингов |
| 21 | AC-32/33: 93 паспорта, 999 параметров, 252 источника, beam_saw (HOMAG, 14 строк, 2 main + 2 connected), highbay lumen=20500 лм | search_read | PASS | совпало |
| 22 | AC-34/35/36: 207 с паспортом, 3 без; 63 связи; SAW-1 (роль, 11 кВт, '9957 × 6514 × —', 14/4/2) | search_read | PASS | совпало; единиц со складовыми 60, SPEC пишет 61 (известно, DEC-9) |
| 23 | AC-37: get_num / f3d_get_num | call_kw | PASS | 20500.0; 126.0; None; 11.0; None; 11.0 |
| 24 | AC-54: f3d_loc_kind 689 (360/144/123/24/20/18), capacity>0 у 654, контрольные значения | search_read | PASS | совпало; DOCK-E1 и WH/Stock без вида |
| 25 | AC-01: валидные коды (10 и 32 символа) и 5 невалидных на f3d.zone | create (QA-BASE-Z1, QA-BASE-X*24) | PASS | 5 ValidationError, 2 валидные создались |
| 26 | AC-01: код из 33 символов на f3d.zone -> ValidationError | create | FAIL | запись создана с обрезкой до 32 символов (zone id 53), см. D-1 |
| 27 | AC-01: код из 33 символов на stock.location и mrp.workcenter | create | PASS | ValidationError |
| 28 | AC-02: дубль кода зоны | create | PASS | ValidationError (UNIQUE) |
| 29 | AC-03: РЦ и обладнання с одним f3d_code | create | PASS | QA-T-1 в обеих моделях |
| 30 | AC-04: код/псевдоним локаций (3 запрета) | create/write | PASS | ValidationError во всех 4 негативных кейсах |
| 31 | AC-05: search_f3d по коду, псевдониму, пустой строке, архивной записи | call_kw | PASS | [732],[732],[], архивная зона найдена |
| 32 | AC-06: резолвер: зона раньше локации/РЦ; NOPE-0 -> None | f3d_resolve | PASS | зона 55; None |
| 33 | AC-06: архивированная зона -> резолвер отдаёт локацию | f3d_resolve после active=False | FAIL | вернул архивную зону 55, см. D-3 |
| 34 | AC-07: f3d_resolve_all | call_kw | PASS | ключи f3d.zone, stock.location, mrp.workcenter |
| 35 | AC-08: action_f3d_show на SAW-1 при установленном viewer | call_kw | PASS | dict равен эталону SPEC; f3d_viewer_available=True |
| 36 | AC-09: action_f3d_show без кода -> UserError | call_kw | PASS | UserError (ветка «viewer не установлен» не проверена, viewer на базе стоит) |
| 37 | AC-16: контур зоны: площадь/габарит и 4 невалидных контура | write polygon_text | PASS | area 63.8, x_min 110, y_max 71.4; 4 ValidationError |
| 38 | AC-18: счётчики зоны (2 локации, 1 док, 1 РЦ, 1 оборудование) | write + search_read | PASS | 2/1/1/1 |
| 39 | AC-20: ворота без стороны, дубль west/1, dock_no у location, f3d_kind=zone | create | PASS | 4 ValidationError |
| 40 | AC-21: f3d_register_dock: west -> in_type, east -> out_type, повтор без дублей (QA-склад QAB) | call_kw | PASS | in_type.dock_ids=[752], out_type=[753], после повтора без дублей; WH остаётся 7/7 |
| 41 | AC-22: f3d_dock_warning: «Крайка» -> предупреждение; дочерняя категория -> нет; сохранение не блокируется | create batch | PASS | текст предупреждения верен, batch сохранён |
| 42 | AC-23: ворота x=151 и y=-1 | create | PASS | 2 ValidationError |
| 43 | AC-51: поля пикинга из пакета (dock_code, truck_code, truck, vehicle) | search_read | PASS | QA-DW-93 / QA-TRUCK-T1 / «Фура плит (тест) QA-base» / QA-base-FL-T; кейс «пикинг без пакета» не проверен |
| 44 | AC-53: f3d_capacity=-1 и f3d_loc_kind='rack' | write | PASS | ValidationError (CHECK) и ValueError |
| 45 | AC-30: после 2 повторов миграции количества не меняются (локации 696, РЦ 35, сотр. 35, обор. 210, пакеты 24, ворота 14) | f3d_run_migration x2 | PASS | совпало |
| 46 | AC-30: отчёт повтора содержит batches_created=0, migration_state не ухудшается | f3d_run_migration | FAIL | state done -> skipped, отчёт перезаписан ({'skipped': true}), см. D-4 |
| 47 | AC-50: администратор запускает f3d_run_migration | call_kw (admin) | PASS | display_notification (ветка manager без admin не проверена) |
| 48 | AC-41: группы user/manager/admin и implied (stock_user, mrp_user, group_system), привилегия «Завод 3D» | res.groups | PASS | manager ∋ user, admin ∋ manager, system ∋ admin, stock_user и mrp_user ∋ user |
| 49 | AC-42: ACL f3d.zone/passport/spec/source (user r, manager rwcd) | ir.model.access (статически) | PASS | как в SPEC; динамика под пользователями не проверена |
| 50 | AC-45: record rule зон по компаниям | ir.rule (статически) | PASS | domain company_id in company_ids; вторая компания не создавалась |
| 51 | AC-55: hr.employee.public: поиск по коду, name_search, поля readonly (под администратором) | search_read/fields_get | PASS | OP-SAW-1 найден, f3d_kind=employee; случай пользователя без hr.group_hr_user не проверен |

## Дефекты

### D-1. f3d.zone.f3d_code: код длиннее 32 символов молча обрезается (AC-01), серьёзность средняя
- Шаги: `f3d.zone.create({'name': 'QA-base-bad', 'f3d_code': 'Q'*33, 'zone_type': 'technical', 'company_id': 1})`.
- Ожидание: ValidationError (AC-01, DEC-4: у кода нет size=32, длину проверяет `_check_f3d_codes`).
- Факт: запись создана, код обрезан до 32 символов (zone id 53). Constraint видит уже обрезанное значение и пропускает.
- Код: `models/f3d_zone.py:35` `f3d_code = fields.Char(required=True, size=32)` (то же для `name`, size=128, строка 36). На stock.location и mrp.workcenter 33 символа корректно дают ValidationError.
- Риск: два разных длинных кода склеятся в один и упрутся в UNIQUE с невнятной ошибкой, либо тихо запишутся неверно.

### D-2. Enterprise: ветка A-15 (связь по f3d_code) отключена, а мост не восстанавливает зону оборудования, серьёзность средняя
- Шаги: РЦ с `f3d_code='QA-BR-1'` и зоной (id 39), `maintenance.equipment` с тем же `f3d_code` без workcenter_id (id 215); запуск `f3d.scene.mixin.f3d_run_migration()` администратором.
- Ожидание (ENV-1, A-15): оборудование связано с РЦ по f3d_code и наследует зону РЦ.
- Факт: workcenter_id пуст, f3d_zone_id пуст. Рядом оборудование с уже заданным workcenter_id (id 214) зону наследует.
- Причина: `hooks/zones.py:75-86` `_equipment_from_workcenter`: fallback по f3d_code стоит в `elif` и работает только когда поля workcenter_id нет (CE). В Enterprise поле есть всегда, поэтому fallback выключен. Мост (`factory3d_base_mrp_maintenance/__init__.py`) заполняет workcenter_id один раз в post_init_hook и после него `zones.bind` не вызывает. Порядок установки: хук base, затем хук моста.
- Следствие: при чистой установке в Enterprise на базу, где workcenter_id ещё пуст, оборудование РЦ не получит зону через РЦ до ручного «Повторить міграцію». Новые пары оборудование/РЦ после установки сами не связываются. На этой базе не воспроизводится из-за уже заполненных связей.
- Предложение для менеджера: в `_equipment_from_workcenter` выполнять fallback и при наличии поля для оборудования без workcenter_id, либо вызывать `zones.bind` в хуке моста.

### D-3. f3d_resolve отдаёт архивированную зону (AC-06), серьёзность низкая
- Шаги: зона, локация и РЦ с одним кодом; `zone.active=False`; `f3d_resolve(code)`.
- Ожидание AC-06: локация. Факт: архивная зона (id 55).
- Причина: `f3d_resolve` использует `search_f3d`, а тот по AC-05 ищет и среди архивных (`models/f3d_scene_mixin.py:103-117`). SPEC противоречит себе (AC-05 против AC-06 и §5, алгоритм резолвера). Юнит-тест `tests/test_scene_mixin.py:75-83` проверяет только unlink и другой набор моделей, поэтому не ловит.
- Решение за менеджером: поправить текст AC-06 или добавить в резолвер приоритет активных записей.

### D-4. Повтор миграции портит migration_state и отчёт (AC-30), серьёзность низкая
- Шаги: после установки (x_* уже удалены) администратор запускает «Повторити міграцію демо-даних» (`f3d_run_migration`).
- Ожидание AC-30: отчёт с `batches_created=0`, состояние не ухудшается.
- Факт: `batches.migrate` возвращает `{'skipped': True}`, `migration_state` становится `skipped` вместо `done`, `migration_report` перезаписан, исходный отчёт установки (18 созданных пакетов и др.) теряется.
- Код: `hooks/__init__.py:21-43` (`write_report`), `hooks/__init__.py:47-62` (`run_all`).
- Я вручную вернул оба параметра к исходным значениям (ir.config_parameter id 48 и 49).

### Замечания без дефекта
- SPEC AC-35 пишет «61 одиниця зі складовими», факт 60 (63 связи), известно как DEC-9.
- `factory3d.base.environment` по умолчанию `test` (так в SPEC §5.1), на боевой базе будет «test» без нейтрализации.
- У моста нет тестов (нет каталога tests), README честно говорит «не тестирован». Теперь есть ручная проверка из этого отчёта.
- `f3d_register_dock` не вызывается при `create` ворот, только при `write` с f3d_kind/f3d_side или по кнопке. Не дефект, наблюдение: ворота, созданные через форму «с нуля», попадают в dock_ids типа операции только после кнопки «Зареєструвати як док» или последующего write.

## Не проверено и почему
1. МОСТ: фактический запуск post_init_hook моста: хук срабатывает только при установке; переустановка/обновление запрещены. На базе все 35 связей уже стоят, кто их проставил (хук или демо-заливка), не определить.
2. AC-42/43/55, ветка AC-50 под ролями (user, manager, admin без system, stock manager, base.group_user): создание пользователей qa-base-<роль> заблокировано классификатором прав (Permission Grant). Нужна ваша явная выдача разрешения; статическая проверка ACL/групп сделана.
3. Видимость меню по ролям: то же: нужны пользователи с ролями.
4. AC-45 динамически (две компании): вторая компания на общей базе не создавалась.
5. AC-09, ветка «factory3d_viewer не установлен»: viewer на базе установлен, патч недоступен снаружи.
6. AC-29, AC-31 (keep_x_fields, деинсталляция): запрещено правилами: удаление/установка модулей.
7. AC-47, AC-48, AC-49 (чистая база, uninstall_hook, neutralize.sql): нужны чистая база/деинсталляция/прямой SQL, на общей базе не выполнять.
8. AC-38 (note 210 ед. побайтово) и снимок stock.move/quant из AC-27: снимков «до установки» нет.
9. AC-40 (_f3d_code_from_barcode) напрямую и AC-53 с подменой scene_locations.csv: приватный метод и файл недоступны через RPC; косвенно через f3d_run_migration (OPW99 -> OP-W99).
10. AC-51, случай «документ без пакета»: не создавал отдельный пикинг.
11. Производительность §13.4 (test_perf_resolve и др.): вне приоритета и таймбокса.
12. Журнал сервера (ошибки загрузки): доступа к логу нет, ir.logging пуст.
13. HTTP API и крон: по SPEC §6/§7 у модуля их нет.

## Мусор в базе (ничего не удалял)
- f3d.zone: 46 (QA-base-zone1, контур перенесён в угол территории 181..181.6 x 99..99.6), 47 (QA-base-zone32), 53 (QA-base-bad, код из 32 символов Q), 55 (QA-base-zx, код QA-X-1). Из-за них зон в базе 49, а не 45.
- stock.warehouse: 2 (QA-base-WH, код QAB), вместе с автосозданными типами операций, локациями QAB/*, маршрутами и последовательностями.
- stock.location: 732 (QA-D-1/QA-U-1), 736 (QA-X-1), 752 (ворота QA-DW-93), 753 (ворота QA-DE-93), 754 (QA-Z2-L1).
- stock.picking.batch: 25, 26 (BATCH/IN/00025, 00026). stock.picking: 51, 52.
- product.product: 60, 61 (QA-base-prod-*). product.category: 12 (QA-base-ХДФ).
- mrp.workcenter: 36 (QA-T-1), 37 (QA-base-wcX, f3d_code QA-X-1, в нём сотрудник 37), 39 (QA-BR-1), 40 (QA-base-wc-nocode).
- maintenance.equipment: 212 (QA-T-1), 213 (QA-FL-T), 214 (без кода, в РЦ 37), 215 (QA-BR-1). Всего оборудования 214, а не 210.
- hr.employee: 37 (код OP-QA-X-1), 38 (код OP-W99), 39. Кодов сотрудников теперь 37, а не 35.
- Пользователи qa-base-* не создавались.
- Временно менял ir.config_parameter factory3d.base.migration_state (id 48) и migration_report (id 49) двумя запусками миграции, значения возвращены исходные (done и отчёт установки). Состояние миграции на базе: done.
- Записи QA-base-* можно удалить: сначала пакеты, пикинги, ворота и склад QAB, потом остальное.
