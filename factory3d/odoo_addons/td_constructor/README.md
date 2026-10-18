# Завод 3D: конструктор (`td_constructor`)

Конструктор розкладки заводу для Odoo 19: площадки, шари з висотними відмітками, місця зі стелажів-шаблонів (комірки
обчислюються), каталог варіантів обладнання з 3D-моделлю, перевірки розстановки, чернетка → публікація з підтвердженням
і історією версій. Документація: `factory3d/docs/modules/td_constructor/` (SPEC, ARCHITECTURE).

## Склад

| Шар | Що |
|---|---|
| Моделі | `td.site`, `td.layer`, `td.slot`, `td.placement`, `td.equipment.variant`, `td.check.config`, `td.layout.version`, `td.term`, майстер `td.publish.wizard` (+ рядки, зауваження); розширення `td.equipment.passport` (категорія, варіанти), `stock.location` / `maintenance.equipment` / `mrp.workcenter` (`td_site_id`, службові uid) |
| Сервіси (чистий Python) | `services/geometry` (OBB, SAT), `cells` (шаблони стелажів → комірки), `checks` (7 перевірок), `schemas` (JSON-поля), `glb_meta`, `convert` (STEP/IFC, необов'язково), `state`, `snapshot`, `publish` |
| API | `/f3d/constructor/*`: JSON-RPC (API-01…API-08), multipart `model/upload` (API-09), GET `model/<id>/<glb|original>` (API-10) |
| Клієнт | клієнтська дія `f3d_constructor`, віджети варіанта — окремі воркери (W2/W3) |
| Дані | `data/td_term_data.xml` (довідники), `td_generic_catalog.xml` (4 типові паспорти й варіанти), `params.xml`, `seed_site.json` («Меблеве підприємство») |

## Встановлення

Залежності: `td_factory3d`, `td_viewer3d`, `stock`, `maintenance`, `mrp`. Необов'язково `mrp_maintenance`
(`maintenance.equipment.workcenter_id` ставиться, лише якщо поле існує). Пакети Python на сервері не потрібні.

```bash
odoo-bin -d <db> -i td_constructor
```

`post_init_hook` виконує за порядком (кожен крок ідемпотентний): параметри (`publish_enabled` за `td.base.environment`:
`True` на `test`, `False` на `prod`) → категорії паспортів base → seed «Меблеве підприємство» (за `seed_key='main_demo'`) →
**зв'язування з наявними записами за кодом** (`td_code`, потім `barcode`; нічого не створюється й не змінюється, крім
службових полів) → базова версія v1 «Імпорт із макета» → `td.constructor.seed_report`.
Повторне встановлення/запуск хука дублікатів не створює. Перша публікація створює лише те, чого бракує (на копії демо-бази
сервера — нічого, окрім зони для трьох навантажувачів).

Деінсталяція (`uninstall_hook`) видаляє лише параметри `td.constructor.*`; `stock.location`, `maintenance.equipment`,
`mrp.workcenter` і знімки версій лишаються. `neutralize.sql` не потрібен: крони, джерела й токени відсутні.

## Права

Привілей «Конструктор» і 4 групи: технолог, комірник, інженер, менеджер (менеджер включає решту й менеджера `td_factory3d`;
адміністратор `td_factory3d` отримує менеджера конструктора). Хто редагує місця й розміщення шару, визначає
`layer.edit_group_ids` (порожньо — лише менеджер): `ir.rule` + серверна перевірка зі зрозумілим повідомленням. Публікація, версії,
налаштування перевірок і шарів — лише менеджер. Користувач лише з `group_td_user` читає.

## Параметри (`td.constructor.*`)

`max_model_mb` (20), `max_triangles` (50000), `autosave_ms` (1500), `eps_mm` (1), `reach_default_m` (15),
`convert_server_enabled` (True), `publish_enabled` — **стоп-кран публікації** (тест `True`, прод `False` до дозволу),
`seed_report` — звіт хука.

## Публікація

Майстер показує, що буде створено/оновлено, і пропозиції архівації (за замовчуванням не відмічені; лише записи з
`td_site_id`; записи із залишками/відкритими заявками заблоковані). Нічого не видаляється. Перед застосуванням сервер ще раз
перевіряє розкладку (всі 7 перевірок, режим `block` забороняє). Одна транзакція; знімок версії — JSON-вкладення (шаблони місць).

## 3D-моделі

GLB/OBJ/STL/FBX/3MF/DAE нормалізуються **у браузері** (DEC-03), сервер зберігає оригінал і легкий GLB, перераховує
трикутники й габарит. STEP/IGES/IFC зберігаються зі статусом `pending_conversion`; серверне перетворення вмикається
автоматично, якщо на сервері є `cascadio` (STEP) або `IfcConvert` (IFC). Відхилення від рішення замовника CD-16
(перетворення на сервері) **очікує підтвердження замовником** (Q-01).

## Тести

```bash
T=factory3d/tools/odoo
F3D_TEST_INSTALL=td_constructor $T/run_tests.sh f3d_c /td_constructor
# золоті фікстури паритету Python ↔ JS (static/tests/fixtures/*_golden.json): F3D_UPDATE_GOLDEN=1 оновлює їх
F3D_UPDATE_GOLDEN=1 F3D_TEST_INSTALL=td_constructor $T/run_tests.sh f3d_c /td_constructor:TestChecks
python3 factory3d/odoo_addons/td_constructor/tools/extract_seed.py   # перегенерувати data/seed_site.json
```

## Запити до каркаса

DEC-19: у CB-09 каркаса зарезервувати `sequence` 12 («Конструктор») і 14 («Планування», «Довідники конструктора»).
