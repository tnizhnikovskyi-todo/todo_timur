# Підготовка 27 модулів td_* до Odoo Apps Store (Odoo 19)

Гілка `claude/td-apps` (основа — `claude/td-integration` 208e617). Ціни й ліцензії **не змінювались**: усі модулі
LGPL-3 без ціни, `td_genset` — OPL-1. Це технічна готовність і перелік рішень для замовника.

## 1. Підсумок

- **Перевірка `check_apps.py`** (без `--ignore`): 27 модулів — **1 ok, 26 лише з попередженнями, 0 з помилками**.
  Попередження: відсутній `.pot` (26 модулів) і два ліцензійні (п. 5); з `--ignore i18n.pot` — 25 ok, 2 з попередженнями.
  Ті самі підсумки на результаті `export_apps.sh`.
- **Enterprise**: залежать від Enterprise лише 3 модулі-містки (`td_factory3d_mrp_maintenance` → `mrp_maintenance`,
  `td_machine_connect_mrp_workorder` → `mrp_workorder`, `td_yard_gantt` → `web_gantt`). Жоден інший td_* не залежить від
  них, тож решта 24 модулі працюють на Community (перевірено і прямо, і транзитивно, за джерелами CE в
  `/home/user/odoo19/addons`; `web_hierarchy`, `stock_fleet`, `stock_picking_batch`, `mrp_account` у 19.0 — CE).
- **Зроблено**: ключі маніфесту (`name`/`summary`/`description` англійською, `support`, `website`, `images`),
  `static/description/index.html`, `banner.png` (1120×560) і `icon.png` (140×140) для всіх 27 модулів;
  4 скриншоти енергетики (з репозиторію, зменшені); експорт у плоский каталог; перевірка + pytest.
- **Бізнес-код, дані, `depends`, `version`, `license`, ціна не змінювались.** Змінено лише відображувані
  `name`/`summary`/`description` (були українською, Apps вимагає англійську; оригінали — в історії git).

## 2. Вимоги Apps для v19 і як вони перевіряються

Джерела: <https://apps.odoo.com/apps/vendor-guidelines>, <https://apps.odoo.com/apps/faq>, довідник маніфесту 19.0
(отримано через curl, 3 запити). Окремого розміру іконки/обкладинки Odoo **не задає** — розміри нижче це стандарт проєкту.

| Вимога Apps | Перевірка (`code`) |
|---|---|
| Обов'язково: `name` (≤ 25 символів, без прикметників і назви компанії), `version` (19.0.x.y.z), `license`, `depends` | `manifest.name/version/license/key` |
| Рекомендовано (вимагаємо): `summary`, `description`, `author`, `website`, `support` (email), `category`, `images` | `manifest.key`, `manifest.support` |
| Опис і скриншоти **англійською** (без реклами й посилань на інші сховища) | `manifest.language`, `html.language` |
| Ліцензії: GPL-3, AGPL-3, LGPL-3, OPL-1, Other OSI approved licence, Other proprietary; таблиця сумісності з залежностями | `manifest.license`, `license.compat` |
| Платні: `price` ≥ 9, `currency` лише EUR або USD | `manifest.price/currency` |
| `static/description/icon.png` — справжній PNG (інакше «біла коробка»); проєктний стандарт 140×140 | `icon.missing/format/size` |
| `images` — обкладинка png/gif/jpeg; `banner.png` = 1120×560 (2:1, стандарт проєкту) | `images.missing/format/size` |
| `static/description/index.html`: без JavaScript, без `<style>`, лише дозволені теги/атрибути (набір санітайзера Odoo), зовнішні посилання лише youtube/teams, `mailto:`/`skype:`, локальні png/gif/jpeg | `html.script/tag/attr/style/url/local/image` |
| Залежність від неіснуючого модуля ламає скан репозиторію (усі модулі знімаються з публікації) | `dep.missing`, `files.missing` |
| Модуль «Community» не залежить (прямо чи через інші td_*) від Enterprise | `dep.enterprise`, `edition.*` |
| Переклади: бажано `.pot` | `i18n.pot` (попередження) |
| Правило Apps: зовнішні сервіси мають бути явно описані; дані користувача — лише з opt-in; без ключа активації | вручну: блок «Requirements» в `index.html` (п. 6) |

Запуск: `factory3d/tools/apps/check_apps.py [каталог] [--ignore i18n.pot] [--strict] [-q]`, код виходу ≠ 0 при помилках;
CE-джерела беруться з `$ODOO_CE_ADDONS` або `/home/user/odoo19/addons` (без них — вбудований список Enterprise-модулів).
Тест: `pytest factory3d/tools/apps` (42 тести, без Odoo і мережі, включно з `export_apps.sh`).

## 3. Модулі

Позначення готовності: **ok** — без помилок і попереджень; **W** — лише попередження (перелік у п. 5).
Усі: версія 19.0.x, автор «ToDo», `website` https://todo.ltd, `support` support@todo.ltd (плейсхолдер).

| Модуль | Назва в Apps | Призначення | CE / EE | Готовність | Публікація |
|---|---|---|---|---|---|
| `td_factory3d` | Factory 3D Core | Ядро: коди сцени, зони, ворота-доки, паспорти обладнання, групи прав | CE | W (i18n) | залежність (безкоштовна) |
| `td_viewer3d` | Factory 3D Viewer | 3D-переглядач заводу в Odoo, «Показати в 3D», журнал, кіоск | CE | W (i18n) | окремо (флагман) |
| `td_viewer3d_sale` | Factory 3D Viewer Sales | Кнопка «Показати в 3D» на замовленні клієнта | CE | W (i18n) | місток |
| `td_constructor` | Factory 3D Constructor | Конструктор розкладки: шари, стелажі → комірки, каталог обладнання, публікація версій | CE | ok | окремо |
| `td_constructor_viewer3d` | Constructor 3D Bridge | Показ опублікованої розкладки в переглядачі | CE | W (i18n) | місток |
| `td_telemetry` | Factory 3D Telemetry | Збір даних: джерела, сигнали, показання, пороги → заявки ТО, API колектора | CE | W (i18n) | залежність (безкоштовна) |
| `td_telemetry_viewer3d` | Telemetry 3D Bridge | Значення сигналів у payload переглядача | CE | W (i18n) | місток |
| `td_machine_connect` | Machine Connect | Верстати: стани → журнал часу, автостарт, простої, OEE, портал STORETEQ, карти розкрою | CE (`mrp_workorder` не потрібен, DEC-1) | W (i18n) | окремо |
| `td_machine_connect_mrp_workorder` | Machine Connect Workorder | Автостарт/стоп із працівниками Enterprise `mrp_workorder` | **EE** (`mrp_workorder`) | W (i18n) | лише EE |
| `td_iot_sim` | Equipment Simulator | Пульт емулятора обладнання (демо/тести) | CE | W (i18n) | не публікувати (п. 4) |
| `td_yard` | Yard Management | Двір: рейси, бронювання воріт, LPR, шлагбауми, автоваги | CE | W (i18n) | окремо |
| `td_yard_gantt` | Yard Gantt | Gantt бронювань воріт | **EE** (`web_gantt`) | W (i18n) | лише EE |
| `td_access` | Factory Access Control | СКУД Suprema BioStar 2: відмітки, картки, відвідувачі, зони | CE | W (i18n) | окремо |
| `td_access_telemetry` | Access Telemetry Bridge | 7 сигналів СКУД у телеметрії | CE | W (i18n) | місток |
| `td_bms` | Building Management | Освітлення, вентиляція, опалення (BACnet/DALI), тепловий баланс, відхилення | CE | W (i18n) | окремо |
| `td_energy` | Factory Energy | Схема електропостачання, лічильники, баланс, кВт·год і вартість на МО, тарифи | CE | W (i18n) | окремо (флагман енергетики) |
| `td_energy_analytics` | Energy Analytics | ISO 50001, EnPI, бюджет, розрізи, PDF-звіти | CE | W (i18n) | доповнення до Energy |
| `td_energy_control` | Energy Control | Сценарії автоматики, ручні команди з блокуваннями (залежить від `td_bms`) | CE | W (i18n) | доповнення до Energy |
| `td_energy_mobile` | Energy Rounds Mobile | Вкладка «Обхід» мобільного екрана чергового | CE | W (i18n) | доповнення до Energy |
| `td_energy_resources` | Energy Resources | Газ, тепло, повітря, вода, резерви економії, Excel | CE | W (i18n) | доповнення до Energy |
| `td_energy_resources_bms` | Energy Resources BMS | Міст ресурсів і BMS: теплові точки, KPI, детектори | CE | W (i18n) | місток |
| `td_energy_viewer3d` | Energy 3D Layer | Шар «Енергетика в 3D» | CE | W (i18n) | місток |
| `td_fire_safety` | Fire Safety | Пожежна сигналізація (лише читання), іскрогасіння, димовидалення, евакуація | CE | W (i18n) | окремо |
| `td_fire_safety_viewer3d` | Fire Safety 3D Bridge | Розділи fire і evacuation у переглядачі | CE | W (i18n) | місток |
| `td_genset` | Generators | Генератори SmartGen HGM6120N через ретранслятор (OPL-1, application) | CE | W (i18n, немає LICENSE) | окремо (незалежний від набору) |
| `td_genset_factory3d` | Generator Factory Bridge | Зв'язка генератора з моделлю заводу (телеметрія, ТО, 3D, блекаут) | CE | W (i18n, LGPL→OPL) | місток |
| `td_factory3d_mrp_maintenance` | MRP Maintenance Bridge | Заповнює `maintenance.equipment.workcenter_id` за `td_code` | **EE** (`mrp_maintenance`) | W (i18n) | лише EE |

`test_td_fire_safety`, `test_td_viewer3d` — тестові джерела/провайдери; не публікуються, не входять до експорту й до таблиці перевірки
(`--include-tests` перевіряє їх теж).

## 4. Пропонована група вітрини (рішення за замовником)

1. **Окремі продукти (9 + 1):** Factory 3D Viewer; Factory 3D Constructor (потребує `td_viewer3d`); Factory Energy
   (+ доповнення Analytics, Control, Resources, Rounds Mobile; Control потребує `td_bms`, Analytics — `td_energy_resources`);
   Machine Connect; Yard Management; Fire Safety; Building Management; Factory Access Control;
   Generators (`td_genset` — єдиний, що не залежить від решти набору).
2. **Лише як залежності, безкоштовні:** `td_factory3d`, `td_telemetry` (за FAQ Apps: залежність від неопублікованого
   додатку можлива, якщо базовий безкоштовний; ціна покупця = ціна додатку + ціни залежностей).
3. **Містки `auto_install` (8):** `td_viewer3d_sale`, `td_constructor_viewer3d`, `td_telemetry_viewer3d`,
   `td_energy_viewer3d`, `td_fire_safety_viewer3d`, `td_access_telemetry`, `td_energy_resources_bms`, `td_genset_factory3d`.
   Їх **треба публікувати** (безкоштовно, можна з категорією Hidden): вони не є залежністю основних модулів, тож покупець
   не отримає їх разом із ними, а без містка не з'являється шар/зв'язка.
4. **Лише для Enterprise (3):** `td_factory3d_mrp_maintenance`, `td_machine_connect_mrp_workorder`, `td_yard_gantt` —
   безкоштовні додатки з позначкою «Requires Odoo Enterprise» (у банері, іконці й `index.html` вже зазначено) або поки не
   публікувати. `export_apps.sh --skip-ee` їх виключає.
5. **Не публікувати:** `td_iot_sim` (інструмент демо/розробки: потребує зовнішнього сервісу емулятора, містить успадковані
   data-файли «рівня 0»; не залежність жодного модуля), `test_td_*`.

## 5. Попередження перевірки

- `i18n.pot` — у 26 з 27 модулів немає шаблону перекладу (є лише в `td_constructor`; `td_genset` має `uk_UA.po`, але не `.pot`).
- `td_genset`: `license.file` — для OPL-1 Apps показує файл `LICENSE` (модуль або корінь репозиторію); його немає.
  Текст OPL-1 додає власник після рішення про ліцензію.
- `td_genset_factory3d`: `license.proprietary_dep` — LGPL-3 модуль залежить від OPL-1 `td_genset`. Таблиця сумісності Apps це
  дозволяє, але відкритий модуль не працює без пропрієтарного.

## 6. Що лежить у репозиторії

- `factory3d/tools/apps/apps_catalog.json` — джерело англомовного контенту й декларації CE/EE для кожного модуля.
- `factory3d/tools/apps/gen_apps_content.py` — з каталогу генерує ключі маніфесту (текстовим редагуванням, решту не чіпає),
  `static/description/index.html`, `banner.png`, `icon.png` (лише якщо немає або це плоска заглушка; дизайнерські
  `td_factory3d`, `td_machine_connect`, `td_genset` збережено, `td_genset` зменшено/збільшено до 140×140), скриншоти. Ідемпотентний.
- `factory3d/tools/apps/check_apps.py` + `test_check_apps.py` — перевірка й тести.
- `factory3d/tools/apps/export_apps.sh <out_dir> [--force] [--skip-ee] [--modules a,b] [--with-docs] [--no-check]` — плоский каталог
  «модуль у корені» для гілки `19.0` (+ `README.md` зі списком); виключає `test_td_*`, Python `tests/` (разом з `tests/stand`),
  `ruff.toml`/`pytest.ini`, `*.pyc`/кеші, `td_genset/relay` (фейковий ретранслятор для тестів), внутрішні `*.md`
  (README/CHANGELOG — нотатки збирання українською; `--with-docs` залишає). `static/tests` лишається (на нього посилаються `assets`).
  Файли ядра копіювати не треба: бандл конструктора і three.js уже всередині модулів; `files.missing` перевіряє, що кожен
  файл з `data`/`demo`/`assets` є в результаті. Результат експорту: 27 модулів, ≈ 36 МБ, 0 помилок перевірки.
- Блок «Requirements» кожного `index.html` чесно вказує: Community/Enterprise, залежності, Python-пакети, зовнішні сервіси
  (колектор, ретранслятор, BioStar), мову інтерфейсу (українська; англійської немає — `i18n/en*.po`).

## 7. Регрес

`F3D_TEST_INSTALL=<24 td_* без трьох EE-містків> run_tests.sh td_apps /td_factory3d`: усі 24 CE-модулі встановились
з новими маніфестами (у логу немає ERROR і зауважень до ключів маніфесту), тести `td_factory3d` — 163 тести,
0 failed, 0 error, код 0 (≈ 2 хв). База `td_apps` видалена (`drop_db.sh --force td_apps`). Три EE-містки не
встановлювались (у CE немає `mrp_maintenance`, `mrp_workorder`, `web_gantt`) — їхні маніфести перевірені лише `check_apps.py`.

## 8. Відкриті рішення для замовника

1. **Ціни.** Зараз усі безкоштовні. Apps: мінімум 9 EUR/USD, валюта лише EUR або USD; комісія Odoo 30 %; ціна в Apps має бути
   не вищою, ніж на інших майданчиках; базові модулі, що лишаються неопублікованими, мають бути безкоштовними; ціна покупця
   складається з цін залежностей (Constructor → Viewer, Energy Control → BMS тощо). Потрібні: які продукти платні, ціни
   за модуль чи за набір, ціни додатків-доповнень.
2. **Ліцензії по модулях.** Поточний стан: 26 × LGPL-3, `td_genset` — OPL-1. Рекомендація Apps: LGPL-3 для відкритих,
   OPL-1 для пропрієтарних (платних). Потрібне рішення, які продукти OPL-1; тоді додати `LICENSE` з текстом OPL-1;
   LGPL-3 дозволяє покупцям вільно поширювати модуль. Окремо: `td_genset_factory3d` (LGPL-3) залежить від `td_genset`
   (OPL-1) — або обидва в одну ліцензію, або місток теж OPL-1.
3. **Назва видавця** (`author`): зараз «ToDo»; юридична назва/бренд для сторінки Apps. Назви додатків уже без назви компанії.
4. **Контактний email** (`support`): зараз плейсхолдер support@todo.ltd; для платних додатків Apps вимагає реальну підтримку
   і відповідальність за дефекти (політика повернення коштів). Бажано також посилання на політику приватності.
5. **Скриншоти англійською.** Скриншоти в `td_energy_analytics/control/mobile/resources` — з українським інтерфейсом
   (взято з `factory3d/build/energy/shots`), що суперечить вимозі Apps; в інших модулів скриншотів немає. Потрібна
   англомовна база й нові знімки (мінімум 1–3 на продукт).
6. **Мова інтерфейсу.** Вихідні рядки всіх модулів українські, англомовний переклад є лише в `td_constructor` (`en.po`).
   Рішення: чи робити `en_US` для всіх публічних модулів і `.pot` (26 попереджень).
7. **Склад вітрини** (п. 4): які модулі публікувати окремо, чи публікувати EE-містки, `td_iot_sim`; чи позначати частину модулів
   як beta (Apps: beta — версія нижча за 1.0, зараз усі 19.0.1.x і `td_iot_sim` 19.0.2.0.4).
8. **Торгові марки третіх сторін** в описах: HOMAG, STORETEQ, Suprema BioStar, SmartGen, Axis, CAME, Mettler Toledo, Helvar,
   Schneider (PM5560) — потрібна юридична оцінка або нейтральні формулювання.
9. **Зовнішні сервіси.** Телеметрійні модулі працюють лише з окремим колектором (`factory3d/services/collector`),
   `td_genset` — з окремим ретранслятором, `td_access` — із сервером BioStar. Apps вимагає явно описувати такі сервіси (зроблено)
   і не вимагати ключа активації; рішення: як клієнти отримують колектор (окремий репозиторій/інсталятор) і чи не суперечить це
   вимозі «модуль встановлюється копіюванням у addons».
10. **Репозиторій Apps:** приватний чи публічний (публічні — лише безкоштовні), назва, гілка `19.0`, ключ доступу для
    скану; процес оновлення (експорт → коміт у гілку 19.0). Перший скан зніме з публікації весь репозиторій при помилці
    маніфесту, тому експорт завжди проганяти через `check_apps.py`.
11. **Категорії:** `td_access_telemetry` має категорію `Hidden` (інші містки — видимі); єдине правило для містків.
