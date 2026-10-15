# wh_constructor — тонкий модуль Odoo для «Конструктора складу» (D-22)

Відає застосунок `warehouse3d/app` з адреси бази, зберігає проєкти, версії та блокування зон; права — групи Odoo.
Читає дані складів для застосунку (адаптер W-11, лише читання). Odoo 18 і 19 Community, залежності: `stock`, `web`.
Застосування змін до локацій (W-13) тут ще немає.

## Склад модуля

- Моделі: `wh.project` (ключ у застосунку, компанія, склади, `data` — JSON проєкту v2, схема, ревізія `rev`),
  `wh.project.version` (знімок при кожному «Зберегти», зберігаються останні 50; параметр `wh_constructor.max_versions`),
  `wh.zone.lock` (проєкт, склад, ключ зони, користувач, термін; 5 хв, параметр `wh_constructor.lock_ttl`),
  `wh.reader` (абстрактна, без таблиці: читання складів, локацій, залишків, категорій зберігання, правил розміщення й поповнення; W-11).
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
| `storage_categories` | `warehouse_id` | категорії, призначені локаціям складу або його правилам розміщення: `id, name, max_weight, allow_new_product, company_id, capacities [{id, product_id, package_type_id, package_type, quantity}]` + `products` |
| `putaway_rules` | `warehouse_id` | `id, sequence, product_id, category_id, category, location_in_id, location_out_id, storage_category_id, package_types, sublocation, company_id` + `products` |
| `orderpoints` | `warehouse_id` | правила поповнення по місцях: `id, name, location_id, product_id, min, max, trigger, warehouse_id` + `products` |

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

## Збірка і тести

```bash
cd warehouse3d/app && npm run build:odoo        # збірка в static/app модуля (не в git)
warehouse3d/tools/odoo/run_tests.sh wh_t        # WH_ODOO=18|19; середовище — warehouse3d/tools/odoo/ENV.md
```

Тести читання — `tests/test_reader.py` (демо-дані: 2 склади по 10 локацій, залишки з партією й резервом, категорія зберігання, правило розміщення,
min/max, чужа компанія, користувач із двома компаніями, відмова без групи, постранично).
