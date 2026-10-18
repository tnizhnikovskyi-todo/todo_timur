# Перейменування factory3d → стандарт компанії `td_*`

Замовник затвердив стандарт імен. Гілка `claude/td-rename` (від `claude/factory3d-build`). Для тестового сервера
буде **нова база** під нові модулі, тож міграції даних «на місці» немає: старі й нові імена в одній базі не співіснують
(див. розділ «Розгортання»).

Стандарт:

- технічне ім'я модуля — `td_<область>`; моделі — `td.*`; поля будь-якої моделі — `td_*`;
- короткі display-імена модулів без префікса «Завод 3D:»;
- назва продукту «Завод 3D» і каталог репозиторію `factory3d/` лишаються (це не технічні імена Odoo).

Заміну виконує `factory3d/build/rename_td.py` (явні регекси за категоріями + множини імен, зібрані з коду до заміни;
жодного `s/f3d/td/g`). Скрипт ідемпотентний і лишений як журнал: у ньому за призначенням згадуються старі імена.
Кроки в git: `95bf195` (git mv каталогів і файлів), `1cfeb14` (CSV, названі за моделлю), `36f06b5` (вміст).

## 1. Карта модулів

| Було | Стало | Display-ім'я (`name` у маніфесті) |
|---|---|---|
| factory3d_base | td_factory3d | Завод 3D |
| factory3d_viewer | td_viewer3d | Переглядач |
| factory3d_constructor | td_constructor | Конструктор |
| factory3d_constructor_viewer | td_constructor_viewer3d | Конструктор — Переглядач |
| factory3d_telemetry | td_telemetry | Телеметрія |
| factory3d_iot_sim | td_iot_sim | Емулятор обладнання |
| factory3d_machine_connect | td_machine_connect | Верстати |
| factory3d_energy | td_energy | Енергетика |
| factory3d_yard | td_yard | Двір |
| factory3d_access | td_access | Доступ |
| factory3d_bms | td_bms | Будівля |
| factory3d_fire_safety | td_fire_safety | Пожежна безпека |
| factory3d_genset | td_genset_factory3d | Генератори — Завод 3D |
| factory3d_viewer_sale | td_viewer3d_sale | Переглядач — Продажі |
| factory3d_yard_gantt | td_yard_gantt | Двір — Gantt |
| factory3d_telemetry_viewer | td_telemetry_viewer3d | Телеметрія — Переглядач |
| factory3d_fire_safety_viewer | td_fire_safety_viewer3d | Пожежна безпека — Переглядач |
| factory3d_access_telemetry | td_access_telemetry | Доступ — Телеметрія |
| factory3d_base_mrp_maintenance | td_factory3d_mrp_maintenance | Завод 3D — mrp_maintenance |
| factory3d_machine_connect_mrp_workorder | td_machine_connect_mrp_workorder | Верстати — mrp_workorder |
| test_factory3d_viewer | test_td_viewer3d | Переглядач — тестові провайдери |
| test_factory3d_fire_safety | test_td_fire_safety | Пожежна безпека — тестові джерела проходів |
| td_genset | td_genset | (без змін, «Генератори») |

Мости («—») названо за схемою «<A> — <B>». Три мости Enterprise (`td_factory3d_mrp_maintenance`,
`td_machine_connect_mrp_workorder`, `td_yard_gantt`) на CE не ставляться і не тестуються.
Каталоги `docs/modules/<m>` і файли `build/modules/<m>.md` перейменовано так само (13 каталогів документів, 10 файлів).
Лише в документації згадуються два незбудовані мости: `factory3d_energy_mrp_workorder` → `td_energy_mrp_workorder`,
`factory3d_genset_viewer` → `td_genset_viewer3d`.

## 2. Що замінено (категорії скрипта і лічильники)

Усього змінено 998 файлів скриптом (Python, XML, CSV, JS/OWL, SQL, shell, TOML, JSON, Markdown у `odoo_addons`,
`services`, `plant`, `tools`, `docs`, `build`, кореневі конфіги), далі вручну дрібні правки (розділ 4) і
git mv: 34 каталоги, 233 файли `f3d_*` → `td_*`, 8 файлів `f3d.<model>.csv` → `td.<model>.csv`
(Odoo визначає модель імпорту CSV за назвою файлу).

| Категорія | Правило | Замін |
|---|---|---|
| module | `factory3d_<m>` → `td_…` у `depends`, `odoo.addons.<m>`, `<m>.xmlid`, `/<m>/static/…`, `@<m>/…`, `--test-tags /<m>`, `name="<m>"` в `<app>` налаштувань | 4494 |
| config_param | `factory3d.<ns>.<param>` → `td.<ns>.<param>` (ns: base, telemetry, yard, access, machine_connect, viewer, energy, bms, iot_sim, genset, fire_safety, constructor), шаблони `'factory3d.%'`, `"factory3d." + key` | 1553 (+9 `factory3d_*`→`td_*` у шаблонах) |
| model | `f3d.<model>` (151 модель з `_name` + віртуальні ключі змін шини `f3d.energy`, `f3d.bms`) → `td.<model>`; `_name`, `_inherit`, comodel, `env[...]`, `model="…"`, RPC у JS і сервісах, коди послідовностей, імена `data/td.<model>.csv` | 8211 |
| field | точний токен `f3d_<field>` для 342 полів із `fields.X(...)` → `td_<field>` (+ `default_f3d_*` у контекстах, `startswith('f3d_fire_')`) | 5882 + 5 + 6 |
| genset3d | **особливий випадок** (рішення менеджера): моделі мосту `td_genset_factory3d` `f3d.genset.{link,profile,event.map}` → `td.genset3d.{link,profile,event.map}` (а не `td.genset.*`, бо цей простір належить окремому продукту td_genset); `model_td_genset3d_*`, `access_td_genset3d_*` в `ir.model.access.csv`, таблиці `td_genset3d_*` у `neutralize.sql` і документації | 178 + 27 + 2 |
| xmlid | 993 xml-id, оголошені в XML/CSV, сегмент `f3d` → `td` (`group_f3d_user` → `group_td_user`, `menu_f3d_*`, `action_f3d_*`, `cron_f3d_*`, `view_f3d_*`, `rule_f3d_*`, `access_f3d_*`, `seq_f3d_*`, `report_f3d_*`, `privilege_f3d_*`, `param_f3d_*`, `user_f3d_machine`) | 5020 |
| field_infix | єдине поле з `f3d` не на початку імені: `is_f3d_manager` (домішка `td.scene.mixin`, `td.signal`, bms) → `td_is_manager` | 96 |
| xmlid_model | `model_f3d_<m>` → `model_td_<m>` (ir.model.access.csv, `ref=`), `field_f3d_<m>__…` | 623 |
| xmlid_prefix | динамічні префікси `group_f3d_`, `menu_f3d_`, `privilege_f3d_` | 26 |
| table | таблиці моделей у сирому SQL (`f3d_signal` → `td_signal`), `neutralize.sql`, службова таблиця `f3d_collector_push` | 866 |
| file_stem | імена файлів `f3d_<x>.{py,xml,csv}` у імпортах, маніфестах, документації | 509 |
| ddl_name | таблиці many2many `f3d_*_rel`, індекси `f3d_*_idx`/`_uniq` | 69 |
| settings_block | `<block name="factory3d_bms_settings">` → `td_bms_settings` | 35 |
| view_name | назви успадкованих представлень `….form.f3d.access` → `….form.td.access` (XML) | 41 |
| wildcard | `f3d_*`, `f3d_fire_*`, `factory3d_*` у документації й docstring | 38 + 9 |
| doc_extra | лише документація: заплановані/вилучені поля й xml-id (`f3d_row`, `view_f3d_energy_dashboard`, …) | 25 |

Вручну (не підходять під регекс): `test_view_js_guards` (фільтр модулів тепер `startswith('td_')`, td_genset входить
сам), `startswith('f3d.access.')` у `td_access/tests/test_security.py`, ключ `factory3d.test.zz_fail` → `td.test.zz_fail`
(`test_td_viewer3d`), ключ-«двійник» `td.machine_connectX` у тесті деінсталяції, коментарі `f3d.*` → `td.*`,
display-імена (маніфести, `<app string>` у налаштуваннях, імена `res.groups.privilege`), текст розділу «Імена»
в `docs/ARCHITECTURE.md` §5, `CLAUDE.md`, `docs/README.md`, `tools/odoo/*` (шаблон демо `f3d_demo_tpl` → `td_demo_tpl`).

## 3. Що лишилося без змін (зовнішні контракти й значення даних)

| Що | Приклад | Чому |
|---|---|---|
| HTTP-маршрути | `/f3d/telemetry/push`, `/f3d/viewer/...`, заголовок `x-f3d-token` | зовнішній контракт: колектор, емулятор, переглядач, kiosk |
| Канал і типи повідомлень шини | `f3d_viewer`, `f3d_viewer.notify`, `f3d_yard.kpp`, клієнтські дії `f3d_viewer.action` | контракт сервер ↔ клієнт (канали шини за вимогою замовника) |
| Коди сигналів і шляхи | `energy/cells/Q1/p_now`, `equipment/FL-1/battery` | дані, ключ між Odoo і 3D |
| Коди об'єктів/сцени, назви вузлів GLB | `FG-R1-B01-L4`, `CNC-2`, `COL-MAIN` | дані |
| Карти регістрів емулятора, формати колектора | `services/iot_sim`, `services/collector*` (протоколи, JSON-схеми) | wire-формат |
| Python-пакети колектора й плагінів | `f3d_collector` (pip), `f3d_collector_mc`, `f3d_collector_bms`, `f3d_collector_yard`, entry points `factory3d_collector.plugins`, `…rest_vendors` | не Odoo-модулі; формат плагіна — внутрішній контракт колектора, обидва боки в репозиторії |
| Ключі Selection типів «локальних» джерел | `f3d_machine`, `f3d_bms`, `f3d_energy` (`td.source.type`) | значення даних (разом із `td_genset`, який уже `td_`) |
| Легасі-моделі рівня 0 | `x_f3d_signal`, `x_f3d_reading`, `model_x_f3d_*`, поля `x_*` | Odoo вимагає префікс `x_` для manual-моделей; контракт із демо-завантажувачем `plant/odoo_push.py` (`MOD = "factory3d"`) |
| Простір xml-id демо-завантажувача | `factory3d.loss_tool`, `factory3d.view_picking_form_dock`, `ir.model.data.module = 'factory3d'` | дані на демо-базі, які створює `plant/odoo_push.py` |
| CSS/JS-імена | `o_f3d_*`, `--f3d-*`, `.f3d-card`, `userData.f3dBase`, ключі localStorage `f3d.ui`, `f3d.lite`, `f3d.layers`, `f3d.static` | внутрішні (не охоплені стандартом) |
| Методи й атрибути Python | `_f3d_ingest`, `action_f3d_show`, `search_f3d`, `_compute_f3d_*` (зокрема `_compute_is_f3d_manager`), `_f3d_*_uniq = models.Constraint(...)` (імена SQL-обмежень у БД лишаються `f3d_*`) | стандарт називає модулі, моделі, поля, xml-id; методи — внутрішнє API (рішення узгодити, див. розділ 6) |
| Ключі контексту, теги тестів, імена тестових користувачів і баз | `f3d_bms_internal`, `f3d_now`, теги `f3d`, `f3d_base`, `f3d_telemetry`, `f3d_template`, `f3d_w1_*` | внутрішні ключі/значення; базу-шаблон `f3d_template` (лише стандартні модулі Odoo) не перебудовувано |
| Shell-функції й змінні середовища | `f3d_log`, `f3d_die`, `F3D_TEST_INSTALL`, `F3D_TEMPLATE_DB` | інструментарій `tools/odoo` (змінні названо в завданні) |
| Product name і каталог | `factory3d/`, «Завод 3D», `ir.module.category` `module_category_factory3d` | назва продукту/проєкту |
| Згенеровані артефакти | `factory3d/dist/*` (`odoo_demo.json`, `factory_viewer.html`), `viewer/index.html`, прототип `build/constructor/proto/*`, `static/lib/*`, `static/data/*` | знімки даних; перегенеруються з живого сервера, у них лише підпис «модуль factory3d_iot_sim» |

## 4. Колізії полів і моделей

Перевірка до заміни (AST усіх моделей, спадкування через `_inherit` і домішки, множина `td_*` з усього репозиторію):

- `td_genset` додає `td_genset_id` (maintenance.equipment, maintenance.request), `td_partner_id`, `td_run_hours_at_close`
  (maintenance.request) і поля `td_genset_*` у res.config.settings. Нові `td_*` міста factory3d на тих самих моделях:
  `td_genset_link_id`, `td_genset_link_ids`, `td_is_genset`, `td_genset_event_key`, `td_genset_*` у налаштуваннях
  (`amf_master`, `ats_*`, `critical_codes`, `offline_min`, `publish_period_s`, `read_enabled`, `requests_enabled`,
  `write_enabled`) — збігів **немає**.
- Три нові імена збігаються з рядками `td_*`, що вже є в репозиторії, але не на одній моделі: `td_code`
  (є поле `td_code` у `td.genset.event.map` з бриджа genset; домішка `td.scene.mixin` на цю модель не підмішується),
  `td_partner_id` (поле td_genset на `maintenance.request`; нове `td_partner_id` — на `delivery.carrier`),
  `td_x` (поле `stock.location`; у td_genset — лише приклад імені бази в README). Колізій немає, зливати нічого не довелося.
- Моделі: за рішенням менеджера моделі мосту `f3d.genset.link/profile/event.map` отримали імена `td.genset3d.link/profile/event.map`
  (`td.genset.*` — простір окремого продукту td_genset: `td.genset`, `td.genset.event`, `td.genset.reading`, …), таблиці —
  `td_genset3d_link/profile/event_map`, xml-id моделей — `model_td_genset3d_link/profile/event_map`, рядки доступу —
  `access_td_genset3d_*`. Назви полів (`td_genset_link_id`, `td_genset_ref`, `td_genset_*` у налаштуваннях), представлень, дій,
  меню й файлів даних бриджа лишилися за загальною схемою (`td_genset_*`, `view_td_genset_link_form`): вони в просторі модуля
  `td_genset_factory3d` і не перетинаються з td_genset. Ключі `td.genset.*` (ir.config_parameter) не збігаються з
  `td_genset.*` td_genset (там крапка після `td_genset`); `uninstall_hook` td_genset перевіряє `startswith('td_genset.')`,
  тож параметри бриджа не зачіпає.
- Підтвердження після встановлення: повний прогін Run A (усі модулі в одній базі, td_genset разом із бриджем); подвійних
  визначень полів немає.

## 5. Перевірка (на фінальному коді)

- **Run A** — усі модулі, крім трьох мостів Enterprise (`td_factory3d_mrp_maintenance`, `td_machine_connect_mrp_workorder`,
  `td_yard_gantt`): `F3D_TEST_INSTALL=<20 модулів> run_tests.sh td_runa` → **1875 тестів, 0 failed, 0 error**
  (базова лінія на старих іменах: 1860; різниця — +21 тест `td_constructor`, доданих merge-ом fix1 після зняття базової лінії;
  решта модулів збігається поштучно).
- **Run B** — демо-набір: шаблон `td_demo_tpl` перебудовано `make_demo_tpl.sh` на нових іменах (демо-завантажувач + `td_factory3d` +
  `td_iot_sim`), далі `F3D_TEMPLATE_DB=td_demo_tpl F3D_TEST_INSTALL=td_factory3d,td_viewer3d,test_td_viewer3d,td_constructor,
  td_constructor_viewer3d run_tests.sh td_runb /td_viewer3d,/test_td_viewer3d,/td_constructor,/td_constructor_viewer3d`
  → **394 тести, 0 failed** (базова лінія 394).
- **ruff** — нових зауважень немає: сумарно 1253 проти 1254 до перейменування (усі застарілі: E501/B905 тощо; по модулях
  кількості збігаються, `td_bms` на одне менше). У `services/iot_sim` (власний конфіг) 33 = 33.
- Після встановлення в базі: 0 моделей `f3d.*`, 0 полів `f3d_*`, 0 параметрів `factory3d.*`, 214 параметрів `td.*`.
- **Залишки (grep):** `factory3d_<…>` як посилання на модуль — 0; лишилося 28 входжень `factory3d_collector.*` (група entry points
  колектора, розділ 3). `f3d.<…>` як рядок моделі — 0; лишилося 25 входжень ключів localStorage/JS (`f3d.ui`, `f3d.lite`,
  `f3d.layers`, `f3d.static`, `f3d.tab`, `f3d.kiosk.reloaded.`) і тестової назви `f3d.level0.test.`.
  Усього змінено 1334 файли відносно `7626727` (1073 — перейменування файлів).


## 6. Рішення, які варто узгодити

- Методи `_f3d_*`, `action_f3d_*`, `search_f3d`, імена SQL-обмежень (`_f3d_*_uniq`), теги тестів `f3d*`, контекстні ключі лишено: стандарт їх не
  називає. Якщо потрібно — окремою категорією у `rename_td.py` (внутрішнє API, ~6000 входжень, тести покриють).
- Імена `ir.rule` («Завод 3D: знімки своєї компанії» тощо), заголовок kiosk-сторінки й слоган `static/description` лишають префікс
  «Завод 3D:» (це не display-імена модулів; ключ групи в налаштуваннях — `Завод 3D`).

## 7. Розгортання на тестовому сервері (робить менеджер; сервер цією гілкою не змінювався)

1. Створити **нову базу** (стара містить `factory3d_*`/`f3d.*`/`f3d_*` — оновити її «на місці» не можна).
2. `addons-path` — каталог `factory3d/odoo_addons` цієї гілки (і `td_genset` там же); інсталяція `-i td_factory3d,td_viewer3d,
   td_constructor,td_constructor_viewer3d,td_telemetry,td_iot_sim,td_machine_connect,td_energy,td_yard,td_access,td_bms,
   td_fire_safety,td_genset,td_genset_factory3d,td_viewer3d_sale,td_telemetry_viewer3d,td_fire_safety_viewer3d,
   td_access_telemetry` (+ мости Enterprise там, де є `mrp_workorder`, `mrp_maintenance`, `web_gantt`).
3. Демо-завантажувач: `plant/odoo_push.py` без змін по суті (xml-id демо — простір `factory3d.*`, `x_f3d_signal`),
   потім `td_factory3d` і `td_iot_sim` (post_init_hook мігрує демо-поля) — порядок `tools/odoo/make_demo_tpl.sh`;
   майстер «Демо» в `td_viewer3d` (меню `menu_td_demo`) — як раніше.
4. Скрипт оновлення на сервері: у списках модулів (`-i/-u`), cron/systemd/docker-compose і CI замінити `factory3d_*` на `td_*`
   за картою розділу 1; параметри нейтралізації/перевірки в базі — ключі `td.<область>.*` замість `factory3d.<область>.*`
   (`td.base.environment` тощо); SQL-перевірки — таблиці `td_*` замість `f3d_*`. Колектор, емулятор, маршрути `/f3d/...`,
   токени й канал шини — без змін.
5. Права: групи тепер `td_factory3d.group_td_user/manager/admin` та `group_td_<область>_*` — перепризначити користувачам
   у новій базі.

## 8. Повторити/перевірити

```
python3 factory3d/build/rename_td.py            # сухий прогін (на вже перейменованому дереві — 0 змін)
git grep -nE 'factory3d_|f3d\.' -- factory3d    # залишки: див. розділ 3
```
