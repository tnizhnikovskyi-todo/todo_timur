# Шаблони tools/odoo (C-00)

Шаблони, не готові скрипти: C-00 (людина) копіює їх у `tools/odoo/` репо пакета й адаптує. Агенти не вигадують параметрів — лише викликають те, що є в `tools/odoo/`. Не перевірялись на реальному Odoo 19 (лише на stub `odoo-bin`): C-00 обов'язково проганяє їх на тестовій базі.

## Захист
Кожен скрипт викликає `guard_db` (`_common.sh`): дозволені бази лише `test-<суфікс>`, `test-pkg-<суфікс>`, `demo-<суфікс>`, `emu-<суфікс>` (суфікс непорожній); інакше `FLOW_STOP`, код 2. Не послаблювати. Це перевірка лише ІМЕНІ бази, не сервера: C-00 гарантує, що `PGHOST` і `db_host` в `ODOO_CONF` вказують на один непродовий сервер (за бажанням — allowlist хостів у `guard_db`).

## Скрипти
| Скрипт | Виклик | Що робить |
|---|---|---|
| `clean_db.sh` | `<db> [--tag T] [--demo]` | dropdb/createdb, `-i base --stop-after-init`; `--tag` звіряє HEAD репо `$PKG_REPO` з тегом (немає репо/тегу — `FLOW_STOP`); опції демо — зі змінних `ODOO_DEMO_OPT`/`ODOO_NODEMO_OPT` (відкрите питання) |
| `install.sh` | `<db> <modules> [--update]` | `-i`/`-u` модулів, потім перевірка стану `installed` у `ir_module_module` (невідомий модуль Odoo лише попереджає) |
| `run_tests.sh` | `<db> <module> [test-tags]` | `-u <module> --test-enable --test-tags` (за замовч. `/<module>`); `RESULT: PASS` лише якщо в логу є підсумок і тестів > 0, інакше `FAIL ... (no tests ran)` |
| `import.sh` | `<db> <model> <csv>` | заглушка: канал імпорту реалізує C-00 (код 3) |
| `reset.sh` | `<db> --yes [--modules m] [--tag T] [--demo]` | clean_db + install; знімків немає (`PKG_REPO` для `--tag`) |
| `smoke.sh` | `<db> <modules>` | модулі `installed` + оновлення без ERROR |

## Передумови
bash >= 4.4 (macOS: `brew install bash`), PostgreSQL-клієнти (`createdb`, `dropdb`, `psql`; доступ через `PGHOST/PGPORT/PGUSER/PGPASSWORD`), Odoo 19 (`ODOO_BIN`, `ODOO_ADDONS_PATH`, опційно `ODOO_CONF`), git і змінна `PKG_REPO` (шлях до репо пакета) для `--tag`.

## Що адаптує C-00
- Шляхи `ODOO_BIN`/addons, параметри підключення до PostgreSQL, версію Odoo: використані опції `-d -i -u --test-enable --test-tags --stop-after-init --log-level` і таблиця `ir_module_module` (стан `installed`) потребують звірки з Odoo 19; опції демо-даних скрипти не вгадують.
- Звірити з `odoo-bin --help` формат опцій і текст підсумку тестів у логу (`run_tests.sh` фільтрує за `ERROR|CRITICAL|FAIL:|Traceback`, а підсумок шукає за `TESTS_SUMMARY_RE` — припущення, виправити за реальним логом; лічильник skipped не рахується).
- Реалізувати `import.sh` (канал імпорту), за потреби `snapshot/restore`, бізнес-smoke.
- Аналогів у `factory3d/tools/odoo/` на момент створення немає (каталогу не існує).

## Відкриті питання C-00
- Опції демо-даних Odoo 19 (`--with-demo`/`--without-demo`, форма, умовчання): скрипти їх не передають, доки C-00 не задасть `ODOO_DEMO_OPT`/`ODOO_NODEMO_OPT`; без цього `demo-*` стенд може бути порожнім.
- Текст підсумку тестів у логу 19 і skipped (`ci-pipeline-builder`, В-1); канал імпорту (`import.sh`); snapshot/restore. Якщо на реальному Odoo 19 завжди виходить `(no tests ran)`, C-00 звіряє рівень логу (`--log-level=test` чи `info`) разом із `TESTS_SUMMARY_RE`; опцію не вгадувати.
- Назва таблиці/станів `ir_module_module` для перевірки `installed`.

## Скіл -> шаблон
| Скіл | Що очікує | Шаблон |
|---|---|---|
| `ci-pipeline-builder` | підйом чистої бази за тегом; підсумок тестів | `clean_db.sh <db> --tag T` (+`PKG_REPO`), `run_tests.sh <db> <module> [tags]`, рядок `RESULT:` |
| `demo-base-builder` | `up.sh`, `reset.sh <instance>`, `snapshot.sh`/`restore.sh` у `package/demo` (`references/stand-scripts.md`) | частково: `tools/odoo/reset.sh <db> --yes` — ІНШИЙ скрипт з тим самим ім'ям і сигнатурою, не плутати з `package/demo/reset.sh`; snapshot/restore немає |
| `master-data-template-builder` | імпорт шаблонів | `import.sh` (заглушка) |
| `package-release-builder`, `odoo-version-migrator` | чиста база, установка, smoke | `clean_db.sh`, `install.sh`, `smoke.sh` |
