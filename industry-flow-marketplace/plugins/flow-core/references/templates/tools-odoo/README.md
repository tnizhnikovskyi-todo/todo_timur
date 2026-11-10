# Шаблони tools/odoo (C-00)

Шаблони, не готові скрипти: C-00 (людина) копіює їх у `tools/odoo/` репо пакета й адаптує. Агенти не вигадують параметрів — лише викликають те, що є в `tools/odoo/`. Не перевірялись на реальному Odoo 19 (лише на stub `odoo-bin`): C-00 обов'язково проганяє їх на тестовій базі.

## Захист
Кожен bash-скрипт викликає `guard_db` (`_common.sh`); `apply.py`/`validate.py` мають власну копію того самого правила (`guard_db` в `apply.py`, `re.fullmatch`) -- зміни вносити в ОБОХ місцях: дозволені бази лише `test-<суфікс>`, `test-pkg-<суфікс>`, `demo-<суфікс>`, `emu-<суфікс>` (суфікс непорожній); інакше `FLOW_STOP`, код 2. Не послаблювати. Це перевірка лише ІМЕНІ бази, не сервера: C-00 гарантує, що `PGHOST` і `db_host` в `ODOO_CONF` вказують на один непродовий сервер (за бажанням — allowlist хостів у `guard_db`).

## Скрипти
| Скрипт | Виклик | Що робить |
|---|---|---|
| `clean_db.sh` | `<db> [--tag T] [--demo]` | dropdb/createdb, `-i base --stop-after-init`; `--tag` звіряє HEAD репо `$PKG_REPO` з тегом (немає репо/тегу — `FLOW_STOP`); опції демо — зі змінних `ODOO_DEMO_OPT`/`ODOO_NODEMO_OPT` (відкрите питання) |
| `install.sh` | `<db> <modules> [--update] [--addons-src DIR] [--tag T]` | `-i`/`-u` модулів, потім перевірка стану `installed` у `ir_module_module` (невідомий модуль Odoo лише попереджає); `--addons-src` копіює модулі (напр. `package/addons`) у `$ODOO_DELIVERY_DIR` (має бути в `ODOO_ADDONS_PATH`), `--tag` звіряє HEAD `$PKG_REPO` з тегом; з `--addons-src` ще вимагає SRC усередині `$PKG_REPO` без незакомічених/невідстежуваних змін і ігнорованих файлів (напр. `__pycache__`); доставка не затирає модуль, якого немає в маркері `.flow-delivery` каталогу, і відмовляє, якщо там є `base` |
| `apply.py` | `modules\|shell\|rpc --db <db> ...` | застосування конфіг-пакета: `-u` модулів з data-файлами в manifest; `odoo-bin shell` зі скриптом; upsert за xml-id із `plan.json` через XML-RPC (`--dry-run`). Підсумок JSON `{created,updated,unchanged,manual,errors}`; `modules` після `-u` перевіряє `installed` (інакше rc=1) |
| `validate.py` | `--db <db> --expect expect.json` | лише читання (XML-RPC): модулі `installed`, `ir.config_parameter`, записи за xml-id проти очікуваного; `PASS`/`FAIL`, код 1 при розбіжностях |
| `run_tests.sh` | `<db> <module> [test-tags]` | `-u <module> --test-enable --test-tags` (за замовч. `/<module>`); `RESULT: PASS` лише якщо в логу є підсумок і тестів > 0, інакше `FAIL ... (no tests ran)` |
| `import.sh` | `<db> <model> <csv>` | заглушка: канал імпорту реалізує C-00 (код 3) |
| `reset.sh` | `<db> --yes [--modules m] [--tag T] [--demo]` | clean_db + install; знімків немає (`PKG_REPO` для `--tag`) |
| `smoke.sh` | `<db> <modules>` | модулі `installed` + оновлення без ERROR |

## apply.py / validate.py (еталони, рішення q17)
`ODOO_ALLOWED_HOSTS` — список хостів через кому або пробіл (однаково для `_common.sh`, `apply.py`, `validate.py`).
Python 3, лише stdlib. Той самий захист імені бази (`test-*|test-pkg-*|demo-*|emu-*`, без `prod`) + для RPC обов'язковий allowlist хостів `ODOO_ALLOWED_HOSTS`; креденціали лише `ODOO_URL`/`ODOO_LOGIN`/`ODOO_API_KEY` зі змінних середовища. Використано лише XML-RPC `/xmlrpc/2` (`authenticate`, `execute_kw`: `search_read`/`read`/`create`/`write`) і `odoo-bin shell`/`-u`. JSON-2 і побічні дії `res.config.settings.execute()` НЕ реалізовано (C-00, див. нижче). Контракт `config-package-format.md` (`--answers`, `vp-map`, transform) цими еталонами НЕ реалізовано, а сигнатури РІЗНІ: контракт -- `install.sh --db <db> --answers <файл>` і `bin/validate.py --answers` (без бази), еталони -- `install.sh <db> <modules> ...` і `validate.py --db --expect` (з базою, XML-RPC). Фікстура `demo-base-builder` теж викликає `install.sh <instance> --answers`. Агент НЕ викликає еталон за сигнатурою контракту; `answers -> plan.json` готує C-00/A-12.
Обмеження `apply.py`: лічильники `created/updated/unchanged` у режимах `modules`/`shell` завжди 0 (ідемпотентність за ними не перевіряється; лише `rpc` їх рахує); `rpc` не атомарний (запис і `ir.model.data` -- два виклики; збій між ними лишає запис без xml-id, повтор створить дубль); у `plan.json` лише скалярні значення; `ODOO_URL` лише https (http -- localhost/127.0.0.1); `--tag` в `install.sh` гарантує код тегу лише для `--addons-src` усередині `$PKG_REPO` з чистим деревом; `ODOO_DELIVERY_DIR` -- окремий каталог доставки, не стандартні addons Odoo.

## Передумови
bash >= 4.4 (macOS: `brew install bash`), PostgreSQL-клієнти (`createdb`, `dropdb`, `psql`; доступ через `PGHOST/PGPORT/PGUSER/PGPASSWORD`), Odoo 19 (`ODOO_BIN`, `ODOO_ADDONS_PATH`, опційно `ODOO_CONF`), git і змінна `PKG_REPO` (шлях до репо пакета) для `--tag`.

## Що адаптує C-00
- Шляхи `ODOO_BIN`/addons, параметри підключення до PostgreSQL, версію Odoo: використані опції `-d -i -u --test-enable --test-tags --stop-after-init --log-level` і таблиця `ir_module_module` (стан `installed`) потребують звірки з Odoo 19; опції демо-даних скрипти не вгадують.
- Звірити з `odoo-bin --help` формат опцій і текст підсумку тестів у логу (`run_tests.sh` фільтрує за `ERROR|CRITICAL|FAIL:|Traceback`, а підсумок шукає за `TESTS_SUMMARY_RE` — припущення, виправити за реальним логом; лічильник skipped не рахується).
- Реалізувати `import.sh` (канал імпорту), за потреби `snapshot/restore`, бізнес-smoke.
- Аналогів у `factory3d/tools/odoo/` на момент створення немає (каталогу не існує).

## Відкриті питання C-00
- Чи перейменовувати еталони, чи змінювати контракт `config-package-format.md` (різні сигнатури `install.sh`/`validate.py`) -- питання до людини, не вирішено. Чи є в Odoo 19 підтримуваний одновикликовий upsert за xml-id (атомарність `rpc`) -- не з'ясовано.
- `apply.py`/`validate.py`: JSON-2 API Odoo 19 (замість XML-RPC); чи коммітить `odoo-bin shell` без явного `env.cr.commit()`; `res.config.settings` (`execute()`) і `transform` з `vp-map.yaml`; поведінка `-i` для щойно доставленого модуля (чи потрібен `update_list`); перевірка хоста в `install.sh` (`PGHOST`).
- Опції демо-даних Odoo 19 (`--with-demo`/`--without-demo`, форма, умовчання): скрипти їх не передають, доки C-00 не задасть `ODOO_DEMO_OPT`/`ODOO_NODEMO_OPT`; без цього `demo-*` стенд може бути порожнім.
- Текст підсумку тестів у логу 19 і skipped (`ci-pipeline-builder`, В-1); канал імпорту (`import.sh`); snapshot/restore. Якщо на реальному Odoo 19 завжди виходить `(no tests ran)`, C-00 звіряє рівень логу (`--log-level=test` чи `info`) разом із `TESTS_SUMMARY_RE`; опцію не вгадувати.
- Назва таблиці/станів `ir_module_module` для перевірки `installed`.

## Скіл -> шаблон
| Скіл | Що очікує | Шаблон |
|---|---|---|
| `ci-pipeline-builder` | підйом чистої бази за тегом; підсумок тестів | `clean_db.sh <db> --tag T` (+`PKG_REPO`), `run_tests.sh <db> <module> [tags]`, рядок `RESULT:` |
| `demo-base-builder` | `up.sh`, `reset.sh <instance>`, `snapshot.sh`/`restore.sh` у `package/demo` (`references/stand-scripts.md`) | частково: `tools/odoo/reset.sh <db> --yes` — ІНШИЙ скрипт з тим самим ім'ям і сигнатурою, не плутати з `package/demo/reset.sh`; snapshot/restore немає |
| `master-data-template-builder` | імпорт шаблонів | `import.sh` (заглушка); перевірка результату — `validate.py` (`records`) |
| `config-as-code` | `install.sh`/`apply.py`/`validate.py` (CLI-контракт у `config-package-format.md`) | еталони тут; контракт `--answers`/`bin/*` НЕ реалізовано, сигнатури різні (див. вище) |
| `package-release-builder`, `odoo-version-migrator` | чиста база, установка, smoke | `clean_db.sh`, `install.sh --addons-src --tag`, `smoke.sh`, `validate.py` |
