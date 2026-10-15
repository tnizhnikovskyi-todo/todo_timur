# wh_constructor — тонкий модуль Odoo для «Конструктора складу» (D-22)

Відає застосунок `warehouse3d/app` з адреси бази, зберігає проєкти, версії та блокування зон; права — групи Odoo.
Читає дані складів для застосунку (адаптер W-11) і застосовує до локацій план змін (W-13): одна транзакція, перевірки на сервері, журнал і відкат. Odoo 18 і 19 Community, залежності: `stock`, `web`.

## Склад модуля

- Моделі: `wh.project` (ключ у застосунку, компанія, склади, `data` — JSON проєкту v2, схема, ревізія `rev`),
  `wh.project.version` (знімок при кожному «Зберегти», зберігаються останні 50; параметр `wh_constructor.max_versions`),
  `wh.zone.lock` (проєкт, склад, ключ зони, користувач, термін; 5 хв, параметр `wh_constructor.lock_ttl`),
  `wh.library` (спільний довідник компанії: типи місць і шаблони, JSON `{types, templates}`, ревізія `rev`; читає «перегляд», пише «проєктування»),
  `wh.reader` (абстрактна, без таблиці: читання складів, локацій, залишків, категорій зберігання, правил розміщення й поповнення; W-11),
  `wh.apply.log` (журнал застосувань плану змін: хто, коли, проєкт, склад, операції з прежніми значеннями, стан `applied` / `rolled_back`; методи `api_apply`, `api_rollback`, `api_list`; W-13).
- Групи: «Конструктор: перегляд» ⊂ «проєктування» ⊂ «застосування в Odoo» (кожна наступна включає попередню; перегляд включає
  «Склад: користувач», щоб було видно меню). Правило записів за компанією. Адміністратор отримує «застосування» при встановленні.
- Меню: Склад → Конфігурація → Конструктор складу (група «перегляд»; видимість меню «Конфігурація» розширює `post_init_hook`).

## HTTP (усі `auth="user"`, JSON-RPC; префікс `/wh_constructor`)

| Маршрут | Дія |
|---|---|
| `/app` | сторінка застосунку (`static/app/index.html` + `<base>` і `window.__WH_ODOO__`); 404 з підказкою, якщо немає збірки |
| `/api/me` | користувач і права `{view, design, apply}` |
| `/api/projects`, `/project/load`, `/project/delete` | список, завантаження, видалення |
| `/api/project/save` | `{key, data, base_rev, commit, comment}` → `ok` + нова `rev`, або `stale` (в базі новіше) |
| `/api/project/versions`, `/project/restore` | історія; відновлення створює нову ревізію й версію |
| `/api/lock/acquire`, `/lock/release`, `/lock/list` | захоплення/продовження, звільнення, чинні блокування; зайнята — `{ok:false, owner, expires}` |
| `/api/apply/run`, `/apply/log`, `/apply/rollback` | застосування плану змін, журнал, відкат (див. «Застосування плану»); `run` `{warehouse_id, ops, key, comment}` → `ok` + `log_id`, `refs`, `counts` |
| `/api/library/load`, `/library/save` | довідник типів і шаблонів; `save` `{data, base_rev}` → `ok` + `rev`, або `stale` + поточні `data` (клієнт зливає й повторює) |

Відмова за правами — `{status:"denied"}`, помилка перевірки — `{status:"error"}`.

### Читання даних складу (W-11, `controllers/odoo_read.py`, модель `wh.reader`)

Потрібна група «Конструктор: перегляд»; читання йде від імені користувача (права й правила записів Odoo), у межах **усіх компаній, доступних
користувачу** (не лише поточної): чужа компанія не видна, склад із неї — `status:"error"`. Без групи — `denied`.
Вибірки — постранично: параметри `offset` (0) і `limit` (за замовчуванням 2000, не більше 5000); відповідь містить `total`, `offset`, `limit`, `next`
(зсув наступної сторінки або `null`), порядок стабільний (`id`; правила розміщення — `sequence, id`). Клієнт тягне сторінки, поки `next` не стане `null`.

| Маршрут (`/api/read/…`) | Параметри | Відповідь |
|---|---|---|
| `warehouses` | — | `version {series, major}`, `db`, `now`, `warehouses [{id, code, name, company_id, company, view_location_id, places}]` (`places` — внутрішні локації) |
| `locations` | `warehouse_id` | внутрішні та view-локації під view-локацією складу, разом із нею: `id, name, complete_name, location_id, usage, barcode, company_id, storage_category_id, removal_strategy_id, removal_strategy`, `replenish_location`, а також `posx/posy/posz` і `scrap_location`, якщо поле є у версії |
| `quants` | `warehouse_id` | `quants [{id, location_id, product_id, quantity, reserved_quantity, lot, package}]` (кількість ≠ 0) і `products {id: {id, default_code, name, uom, categ}}` для товарів сторінки |
| `storage_categories` | `warehouse_id` | категорії, призначені локаціям складу або його правилам розміщення, і всі категорії компанії складу (або без компанії; W-14): `id, name, max_weight, allow_new_product, company_id, capacities [{id, product_id, package_type_id, package_type, quantity}]` + `products` |
| `putaway_rules` | `warehouse_id` | `id, sequence, product_id, category_id, category, location_in_id, location_out_id, storage_category_id, package_types, sublocation, company_id` + `products` |
| `orderpoints` | `warehouse_id` | правила поповнення по місцях: `id, name, location_id, product_id, min, max, trigger, warehouse_id` + `products` |
| `removal_strategies` | — | стратегії списання бази (`product.removal`): `id, name, method` (W-14) |
| `package_types` | — | типи пакування (`stock.package.type`): `id, name` (W-14) |

Архівні записи не читаються (`active_test`). Приклад споживача — `warehouse3d/app/src/adapters/odoo-api.js`.

### Відмінності Odoo 18 і 19 (R-02, перевірено за вихідниками `addons/stock/models/`)

| Що | 18 | 19 | Як закрито |
|---|---|---|---|
| `stock.location`: `posx / posy / posz` | є | немає | віддаються лише якщо поле є (`_fields`) |
| `stock.location`: `scrap_location` | Boolean | немає (брак — `usage = inventory`) | так само |
| `stock.location`: `replenish_location`, `removal_strategy_id` (`product.removal`), `storage_category_id`, `barcode` | є | є | однаково |
| `stock.storage.category` (+ `.capacity`: товар / тип упаковки, кількість), `stock.putaway.rule` (у `product_strategy.py`), `stock.quant` | ті самі моделі й поля | ті самі | однаково |
| `stock.warehouse.orderpoint`: min / max | `product_min_qty`, `product_max_qty` | ті самі | однаково |
| `stock.warehouse.orderpoint`: кратність | `qty_multiple` | `replenishment_uom_id` | не читається (потрібні лише min/max) |
| тип JSON-маршруту | `json` | `jsonrpc` | константа `JSON` у `controllers/main.py` |
| поле груп користувача | `groups_id` | `group_ids` | `tests/common.py` |

Правило `replenish_location` у Odoo не дозволяє ставити прапор на вкладену локацію, якщо він уже стоїть на батьківській (в обох версіях).

## Застосування плану (W-13, `models/wh_apply.py`)

Право — група «Конструктор: застосування в Odoo» (`group_wh_apply`; журнал читає «проєктування»). Без групи — `{status:"denied"}`, помилка перевірки — `{status:"error", message}`. Запис у локації йде з правами сервера (`sudo`)
після перевірки групи, у межах компаній користувача; склад мусить бути доступний користувачу, усі локації — всередині складу.

`ops` — список `{kind, name, …}` (клієнт формує `plan.js` → `wireOps`):

| `kind` | Поля | Що робить |
|---|---|---|
| `create` | `ref`, `name` (коротке ім'я рівня), `usage` (`internal` / `view`), `parent` `{id}` або `{ref}`, `vals` | створює локацію (компанія складу); `vals` — `barcode` (повний код місця: за ним застосунок читає ключ місця, D-14), `posx / posy / posz`, `storage_category_id`, `replenish_location`, `scrap_location` — лише ті поля, що є у версії Odoo (решта пропускаються й записуються в журнал як `skipped`) |
| `move` | `id`, `to` `{id}` або `{ref}` | змінює батьківську локацію (не в саму себе) |
| `rename` | `id`, `name` | змінює назву |
| `attrs` | `id`, `vals` | пише атрибути (прежні значення — у журнал) |
| `archive` | `id` | архівує (`active = False`) |
| `category`, `orderpoint` | див. «Ємність і атрибути (W-14)» нижче | категорії зберігання та правила поповнення min / max |

- **Одна транзакція.** Порядок: категорії зберігання (W-14) → створення (батьки раніше за дітей, незалежно від порядку в запиті) → переноси → перейменування → атрибути → правила поповнення (W-14) → архівація (діти раніше за батьків). Усе в `cr.savepoint()`: помилка в будь-якому місці —
  у базі нічого не змінено й журналу немає. Штрихкод, що вже є в компанії, — помилка (до запису).
- **Архівація лише порожнього (F4).** До першої зміни сервер перевіряє локацію й усі підлеглі: немає `stock.quant` з кількістю ≠ 0 і немає незавершених `stock.move` (не `done` / `cancel`); корінь складу й `lot_stock_id` архівувати не можна.
- **Журнал** `wh.apply.log`: `ops` — застосовані операції з прежніми значеннями (`create` — id, `move` — `from`, `rename` — `old`, `attrs` — `old`, `archive` — id і раніше архівні підлеглі). Лічильники `n_created … n_archived`.
- **Відкат** (`api_rollback`): зворотні операції в зворотному порядку — розархівувати (батьки раніше; раніше архівні підлеглі лишаються в архіві), повернути атрибути, назви, батьків, заархівувати створене (діти раніше). Відмова, якщо створені
  локації вже використані (залишок або незавершене переміщення), запис уже відкочено або є пізніше застосування, яке чіпало ті самі локації: **старе застосування відкочується лише по порядку** — спершу відкочують пізніші.
- **Версії Odoo.** `posx / posy / posz` і `scrap_location` є лише у 18 (у 19 їх немає — поля пропускаються); `replenish_location` і `storage_category_id` — в обох. Створені контейнери (зона, ряд, секція) — внутрішні локації, а не `view`:
  у `view`-локації `complete_name` в Odoo починається заново, і шлях вузла в застосунку перестав би збігатися з шляхом в Odoo.

### Ёмкость и атрибуты (W-14)

`ops` расширены двумя видами, а `attrs` / `create` — полями (все проверяются сервером, лишнее пропускается и попадает в журнал как `skipped`):

| `kind` | Поля | Что делает |
|---|---|---|
| `category` | `ref` (новая) или `id` (правка), `name`, `vals { max_weight, allow_new_product (empty / same / mixed), capacities [{ product (код) \| package_type_id, quantity }] }` | создаёт `stock.storage.category` (компания склада) либо правит; ёмкости при правке заменяются целиком; товар — по `default_code` (запасной вариант `ID<id>`), повтор товара или типа упаковки, количество ≤ 0 и «и товар, и упаковка» — ошибка. Выполняется **раньше локаций** |
| `orderpoint` | `location_id`, `product` (код) или `product_id`, `min`, `max`, `id` (правка) | создаёт или правит `stock.warehouse.orderpoint` (`product_min_qty`, `product_max_qty`) на локации склада; повтор товара на локации, `min > max`, чужая локация — ошибка. Выполняется после атрибутов, перед архивацией |
| `attrs` / `create` (`vals`) | `storage_category_id` (id или `{ ref }` категории этого же плана), `removal_strategy_id`, `replenish_location`, `scrap_location` (18), `usage` (`internal` / `view`) | `usage = view` — только для локации без остатка; несуществующая категория или стратегия — ошибка |

Журнал хранит прежние значения (`category_update.old`, `orderpoint_update.old`) и счётчики `n_categories`, `n_orderpoints`; ответ `run` — `counts` `{ category, create, move, rename, attrs, orderpoint, archive }`, `refs` включает `c:<ключ>` созданных категорий.
Откат: правила возвращают min / max (созданные — в архив), категории — прежние значения (созданные удаляются, если ими не пользуются другие локации — иначе остаются); ключи затронутых записей разделены по виду (`loc` / `category` / `orderpoint`),
поэтому совпадение числовых id не мешает проверке «сначала откатите более позднее применение». Читатель добавляет `GET`-маршруты `read/removal_strategies` (`product.removal`: `id, name, method`) и `read/package_types` (`stock.package.type`),
а `read/storage_categories` отдаёт не только назначенные категории, но и все категории компании склада (или без компании) — иначе созданная и ещё не назначенная категория создавалась бы повторно.
Правила версий: `replenish_location` нельзя ставить на вложенную в «место пополнения» локацию и на ту, у которой такая вложена (в Odoo уже стоит на `lot_stock_id` склада) — ошибка Odoo приходит как `status: "error"`.

## Збірка і тести

**Перед встановленням модуля потрібна збірка застосунку** (I-02): `static/app/` модуля не в git, без неї `/wh_constructor/app` відповідає підказкою 404.

```bash
warehouse3d/tools/odoo/prepare_module.sh        # npm ci + npm run build:odoo → static/app модуля; збирає лише якщо вихідники новіші (--force — завжди)
WH_ODOO=19 warehouse3d/tools/odoo/update.sh <db>   # сам викликає prepare_module.sh для wh_constructor (WH_APP_BUILD=skip — пропустити)
warehouse3d/tools/odoo/setup.sh app             # те саме окремим кроком; повний setup.sh збирає застосунок без зупинки при помилці
cd warehouse3d/app && npm run build:odoo        # ручний варіант (Node 20+, спершу npm install)
warehouse3d/tools/odoo/run_tests.sh wh_t        # WH_ODOO=18|19; середовище — warehouse3d/tools/odoo/ENV.md (тестам збірка не потрібна)
```

Без Node (сервер): зберіть застосунок деінде й покладіть вміст `dist` у `odoo_addons/wh_constructor/static/app/`, а `WH_APP_BUILD=skip` не дасть скриптам його перезаписувати.

Тести ємності й атрибутів (W-14) — `tests/test_capacity.py` (нова категорія та її призначення, правка категорії, прапорці й стратегія, створення й зміна правила min / max, порядок «категорії → локації → правила», відмови, транзакційність, відкат, довідники читача, відмова без групи; Odoo 19 і 18).
Тести застосування — `tests/test_apply.py` (створення з ієрархією, перенос, перейменування, атрибути, архівація порожнього, відмова з залишком і з незавершеним переміщенням, відмова без групи, транзакційність, журнал і відкат, HTTP).
Тести читання — `tests/test_reader.py` (демо-дані: 2 склади по 10 локацій, залишки з партією й резервом, категорія зберігання, правило розміщення,
min/max, чужа компанія, користувач із двома компаніями, відмова без групи, постранично).
