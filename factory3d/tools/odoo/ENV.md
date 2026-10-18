# Середовище розробки і тестів factory3d (Odoo 19.0 CE)

Усе, крім скриптів, лежить **поза репозиторієм** і при перестворенні контейнера відновлюється однією командою
`factory3d/tools/odoo/setup.sh` (≈ 2 хв 40 с: клон Odoo + venv + Postgres ≈ 50 с, шаблонна база ≈ 110 с).
Повторний запуск `setup.sh` ідемпотентний: те, що вже готове, пропускається (≈ 1 с).

Скрипти — порт середовища `smartgen/tools/odoo/` (Odoo 18, `td_genset`) на Odoo 19 для модулів `td_*`.

## Шпаргалка (один рядок — одна дія)

```bash
T=<корінь worktree>/factory3d/tools/odoo
$T/setup.sh                                      # свіжий контейнер: Postgres, Odoo 19, venv, конфіг, шаблонна база f3d_template
$T/pg.sh start                                   # підняти Postgres (після рестарту контейнера сам не стартує)
F3D_TEST_INSTALL=td_x $T/run_tests.sh f3d_<ім'я>   # свіжа копія шаблона + -i td_x + тести /td_x
$T/run_tests.sh f3d_<ім'я>                       # те саме, але ставляться й тестуються ВСІ модулі з odoo_addons
$T/run_tests.sh f3d_<ім'я> /td_x:TestY    # лише клас (або :TestY.test_z, або тег); теги — синтаксис Odoo --test-tags
$T/new_db.sh f3d_<ім'я>                          # порожня копія шаблона (без модулів factory3d)
$T/update.sh f3d_<ім'я>                          # -u/-i модулів factory3d у наявній базі
$T/serve.sh f3d_<ім'я> [порт]                    # сервер у фоні (Playwright, ручна перевірка), admin / admin
$T/serve.sh stop f3d_<ім'я>                      # зупинити (serve.sh status — що запущено)
$T/drop_db.sh f3d_<ім'я>                         # видалити базу і filestore (--pattern 'f3d_w1_%'; зайняті пропускає)
$T/setup.sh template                             # перезібрати шаблон f3d_template (≈ 105 с)
$T/setup.sh check                                # перевірка інфраструктури: post_install-тести /maintenance з туром у Chrome (≈ 55 с)
```

Імена баз — `[a-z0-9_-]`; для паралельної роботи в кожного потоку свій префікс (`f3d_w1_…`, `f3d_w2_…`).
`T` — каталог скриптів **свого** worktree (див. розділ «Git worktree»).

## `run_tests.sh <db> [test-tags]`

- Що ставити: змінна **`F3D_TEST_INSTALL`** — модулі через кому для `-i` (за замовчуванням усі каталоги
  з `__manifest__.py` у `factory3d/odoo_addons`). Теги за замовчуванням — `/<модуль>` для кожного з них.
- Створює `<db>` з `f3d_template` (≈ 1 с), запускає
  `odoo-bin -c $ODOO_CONF --addons-path=<odoo>/addons,<worktree>/factory3d/odoo_addons -d <db> -i $F3D_TEST_INSTALL
  --test-enable --test-tags <теги> --stop-after-init --log-level=test --http-port=<порт з імені бази>`.
- Друкує лише: підсумок тестів (`odoo.tests.result`/`stats`), усі записи ERROR/CRITICAL з трейсбеками, а при
  провалі (або якщо тести не запускались) — хвіст логу (15 рядків) і фінальний рядок `OK` / `ПРОВАЛ`.
  Повний лог — `/home/user/odoo19-data/logs/test-<db>.log`.
- **Паралельні прогони** з різними `<db>` не заважають одне одному: окрема база, filestore, лог і lock-файл
  (`run/<db>.lock`, `flock`: те саме ім'я двічі зайняти не можна), а **HTTP-порт виводиться з імені бази**
  (`20000 + cksum(db) % 20000`; якщо зайнятий — наступний вільний; порт на час прогону блокується
  `run/port-<N>.lock`, тож навіть збіг хешів двох імен не дасть однакового порту). `HttpCase` ходить на цей порт.
- Код виходу: `0` — усе пройшло; код Odoo (зазвичай `1`) — впали тести/встановлення; `1` — Odoo повернув 0,
  але в логу є ERROR/CRITICAL (`F3D_TEST_STRICT=0` — не вважати); `4` — модуль не знайдено в `addons_path` або не
  встановився (стан модуля перевіряється в базі); `124` — таймаут (`F3D_TEST_TIMEOUT`, за замовчуванням 3600 с).
- Інші змінні: `F3D_TEST_TEE=1` — дублювати лог у консоль; `F3D_TEST_KEEP_DB=0` — видалити базу після прогону
  (за замовчуванням лишається — її можна відкрити через `serve.sh`). Аргументи після `--` йдуть в `odoo-bin`
  (наприклад, `-- --screenshots=/tmp/shots`).

Перевірено на заглушці `f3d_smoke_stub` (залежності `mrp, maintenance, stock`, 2 тести, `F3D_TEST_INSTALL=f3d_smoke_stub
run_tests.sh f3d_smoke`): модуль ставиться на копію шаблона, тести проходять; ≈ 7 с, з яких копія бази ≈ 1 с.

## Шаблонна база `f3d_template`

Зібрана з `--without-demo=True`, `ALLOW_CONNECTIONS false`, `IS_TEMPLATE` (до неї не можна підключитись, тому
`createdb -T` ніколи не впирається в «source database is being accessed by other users»). Стандартні модулі
(список — `F3D_TEMPLATE_MODULES` в `env.sh`; стани й недоступні — у `/home/user/odoo19-data/template-report.txt`):

`stock, mrp, maintenance, mrp_maintenance, hr, stock_picking_batch, stock_fleet, fleet, web, bus, mail, mrp_workorder,
mrp_account, analytic, web_hierarchy, delivery, stock_delivery, web_gantt, hr_attendance` (+ їхні залежності, 86 модулів).

### Демо-шаблон `td_demo_tpl` (`make_demo_tpl.sh`)

`make_demo_tpl.sh [--force]` (≈ 6,5 хв): копія `f3d_template` + uk_UA + purchase_stock/sale_stock/… → `plant.odoo_push` по XML-RPC (сервер без cron) → `-i td_factory3d,td_iot_sim` (post_init_hook мігрує демо) → шаблон (`ALLOW_CONNECTIONS false`). Є: MO `WH/MO/00231`, 35 РЦ, 731 локація, `td_sim_signal` 1168. Тести на ній: `F3D_TEMPLATE_DB=td_demo_tpl F3D_TEST_INSTALL=… run_tests.sh f3d_<ім'я> …`.
Кроки push `modules` (iot — Enterprise), `iot_module`, `signals` пропускаються (`--skip`/`F3D_DEMO_SKIP`); у `plant/odoo_push.py` — правки для CE: без `employee_ids`/`start_employee` і з lot_name при підтвердженні приймань. Якщо база є — вихід без дій.

### Недоступні модулі (Odoo 19.0 Community)

Скрипт ставить лише ті зі списку, чий каталог з `__manifest__.py` є в `<odoo>/addons`; решту пропускає й
перелічує наприкінці `setup.sh`. На коміті `bc77fac7` (19.0, 14.10.2026) **немає каталогів** (це Enterprise):

| Модуль | Статус |
|---|---|
| `mrp_workorder` | немає в Community (Enterprise: розширення робочих операцій / Shop Floor; сама модель `mrp.workorder` є в `mrp`) |
| `web_gantt` | немає в Community (Enterprise: подання Ганта) |
| `mrp_maintenance` | немає в 19.0 Community (є лише `maintenance`, `hr_maintenance`, `stock_maintenance`) |

Усі інші 16 зі списку встановлюються й ставляться в шаблон без помилок (`web_hierarchy`, `stock_fleet`, `mrp_account`,
`hr_attendance`, `delivery`, `stock_delivery` тощо — у Community 19.0 є). Модулі `td_*` не повинні залежати
від трьох недоступних — інакше `-i` впаде на «module not found».

## Git worktree (паралельні потоки)

- Скрипти обчислюють корінь репозиторію від свого розташування (`factory3d/tools/odoo` → `../../..`) і передають
  `odoo-bin` `--addons-path=/home/user/odoo19/addons,<корінь worktree>/factory3d/odoo_addons` — аргумент командного
  рядка перекриває `addons_path` з конфігу. Тому працює з будь-якого worktree чи клону; запускайте скрипти **зі
  свого worktree**. `run_tests.sh` друкує фактичний `addons-path`; `serve.sh status` — з якого worktree піднятий сервер.
- Ручний запуск `odoo-bin -c /home/user/odoo19.conf …` без `--addons-path` візьме модулі з того шляху, що в конфігу
  (worktree, з якого запускали `setup.sh conf`).
- Спільні для всіх worktree: Postgres, `f3d_template`, venv, вихідники Odoo, `data_dir`. Не перетинаються: база,
  `filestore/<база>`, логи `logs/*-<база>.log`, lock/pid/порт `run/<база>.*` — усе за іменем бази.
- `run_tests.sh`, `update.sh`, `new_db.sh` беруть блокування `run/<база>.lock` (другий одразу завершується з помилкою).
  `drop_db.sh` пропускає бази, зайняті прогоном або `serve.sh` (`--force` — видалити все одно).
- Перевизначити шлях повністю: `ODOO_ADDONS_PATH=/home/user/odoo19/addons,/інший/odoo_addons $T/run_tests.sh …`.
- Співіснує зі скриптами `smartgen/tools/odoo/` (Odoo 18): інші каталоги (`odoo18*`), інша шаблонна база
  (`td_template`), але **спільні** кластер Postgres 16 і роль `odoo` / пароль `odoo`.

## Що де

| Що | Де |
|---|---|
| Odoo 19.0 CE | `/home/user/odoo19` — `git clone --depth 1 --branch 19.0` (повний набір addons, ≈ 1,4 ГБ) |
| venv | `/home/user/odoo19-venv` (Python 3.12.3), список пакетів — `requirements-odoo.txt` там же |
| Конфіг | `/home/user/odoo19.conf` (права 600): `addons_path`, `data_dir`, `db_*`, `http_port = 8069`, `http_interface = 127.0.0.1`, `limit_time_real(_cron) = 600`, `max_cron_threads = 1`, `without_demo = True` |
| Дані Odoo | `/home/user/odoo19-data`: `filestore/<база>`, `sessions`, `logs/` (логи скриптів), `run/` (lock/pid/порти), `template-report.txt`, `template.stamp` |
| Postgres | кластер `16/main`, TCP `127.0.0.1:5432`, роль `odoo` / пароль `odoo` (CREATEDB, не суперкористувач), пароль також у `~/.pgpass` |
| Налаштування Postgres для тестів | `/etc/postgresql/16/main/conf.d/90-f3d-odoo-dev.conf`: `fsync=off`, `synchronous_commit=off`, `full_page_writes=off`, `max_connections=300`, `shared_buffers=1GB` |
| Браузер для HttpCase/турів | `ODOO_BROWSER_BIN=/opt/pw-browsers/chromium` (Chromium від Playwright) — виставляє `env.sh` |

Усі шляхи і версії перевизначаються змінними оточення (перелік — на початку `env.sh`): `F3D_ENV_ROOT`, `ODOO_HOME`,
`ODOO_VENV`, `ODOO_CONF`, `ODOO_DATA_DIR`, `ODOO_BRANCH`, `F3D_TEMPLATE_DB`, `F3D_TEMPLATE_MODULES`, `PG_VERSION`, `PGPORT`…

## `setup.sh` — кроки

`setup.sh` без аргументів: `pg odoo venv conf template` (шаблон — лише якщо його немає або застарів). Окремі кроки:
`setup.sh pg|odoo|venv|conf|template|check`.

- `pg` — (`pg.sh init`) якщо Postgres не встановлений і ми root з `apt-get` — ставить `postgresql-16`; кластер,
  налаштування для тестів, роль `odoo`, `~/.pgpass`.
- `odoo` — `git clone --depth 1 --branch 19.0` (повтори 2/4/8/16 с при мережевих збоях; недокачаний клон прибирається).
- `venv` — Python 3.12 (`/usr/bin/python3.12`; інакше 3.13/3.11/3.10 з системи, інакше `uv python install 3.12`) +
  `requirements.txt` Odoo з правками: `psycopg2` → `psycopg2-binary` (немає `libpq-dev`), `python-ldap` пропущено (немає
  `libldap-dev`; потрібен лише `auth_ldap`), додано `websocket-client` (без нього Odoo пропускає браузерні тести) і
  `pdfminer.six`. Ставить `uv pip`, якщо `uv` є, інакше `pip`.
- `conf` — не перезаписує наявний (`FORCE=1` — перезаписати).
- `template` — `-i <доступні модулі з F3D_TEMPLATE_MODULES> --without-demo=True`; потім перевіряє, що кожен модуль у стані
  `installed`, пише звіт, ставить `IS_TEMPLATE`. Позначка `template.stamp` (коміт Odoo + список модулів + Python) дає
  ідемпотентність: у повному запуску шаблон не перезбирається, поки позначка актуальна; `setup.sh template` — завжди.
- `check` — на копії шаблона (`f3d_check`) запускає `F3D_CHECK_TAGS` (за замовчуванням `/maintenance,-at_install`).

## Особливості Odoo 19 і підводні камені

- `--without-demo` в Odoo 19 — булева опція (`--without-demo=True`); значення `all` (як у Odoo 18) дає WARNING
  «invalid boolean value» і лише випадково працює.
- **at_install-тести і порядок завантаження.** У шаблоні вже стоять ~86 модулів. При `-i` модуль завантажується в
  порядку глибини графа залежностей, і його at_install-тести (дефолтний тег) виконуються, коли модулі *глибші* за
  нього ще не завантажені, хоча їхні колонки в БД уже є. Наслідок: тест низькорівневого модуля, що створює
  `res.partner`, падає на `NOT NULL` для колонок `account` (`autopost_bills`). Модулі `td_*`, що залежать від
  `mrp`/`stock`/…, цього не чіпає (перевірено: заглушка з `depends = mrp, maintenance, stock` створює `res.partner` і
  `res.users` в at_install-тесті без помилок), але тести, що торкаються моделей з модулів поза `depends`, роблять
  `@tagged('post_install', '-at_install')`.
- Не імпортуйте `tests` з `__init__.py` модуля: Odoo підхоплює `tests/` сам у тестовому режимі, а імпорт
  `odoo.tests` поза тестами дає ERROR «Importing test framework…» (він ламає суворий режим `run_tests.sh`/`update.sh`).
- Без `-i`/`-u` Odoo все одно виконує at_install-тести модулів, названих у `--test-tags /<модуль>`, у момент їх завантаження.
- Рядок підсумку: `odoo.tests.result: N failed, M error(s) of K tests when loading database '<db>'`; при `K = 0` це
  WARNING (тести не знайшлись — перевірте теги/`F3D_TEST_INSTALL`).

## Замірювання (4 CPU, 15 ГБ)

| Операція | Час |
|---|---|
| Повний `setup.sh` «з нуля» (чисті `odoo19*`, холодний кеш uv; Postgres-кластер уже є — без apt) | 161 с |
| — клон `odoo/odoo` 19.0 `--depth 1` | ≈ 45 с (разом з venv і `pg.sh init` ≈ 50 с) |
| — venv + залежності (`uv pip`, у середовищі з теплим кешем) | ≈ 15 с |
| — шаблон `f3d_template` (16 модулів + залежності, без демо) | 105–110 с |
| Повторний `setup.sh` (все готове) | ≈ 1 с |
| Копія бази з шаблона (`createdb -T` + filestore) | 0,7–2,3 с |
| `run_tests.sh` з мінімальним модулем (2 тести) | ≈ 7 с |
| `setup.sh check` (post_install `/maintenance`, тур у Chrome) | ≈ 55 с |
| Два `run_tests.sh` паралельно (різні бази) | не заважають одне одному (різні порти/бази/логи) |

## Застереження

- `fsync=off` тощо — лише для тестів: при аварійному падінні контейнера кластер може пошкодитись
  (лікування: `pg_dropcluster 16 main --stop`, потім `setup.sh`).
- Postgres не стартує сам після рестарту контейнера — `pg.sh start`. `pg.sh init` ідемпотентний.
- Перезбирання шаблона під час чужих прогонів зламає їхній `createdb` — попереджайте інших.
- `Running as user 'root' is a security risk.` у логах — попередження, не помилка. `wkhtmltopdf` немає (PDF-звіти
  не рендеряться, у логу INFO). `auth_ldap` працювати не буде (немає `python-ldap`).
- Бази `f3d_*` накопичуються (≈ 30–60 МБ кожна): `drop_db.sh --pattern 'f3d_w1_%'` — свої; зайняті чужими прогонами
  й серверами пропускаються, шаблон не видаляється ніколи.
- Оновити Odoo: `git -C /home/user/odoo19 pull --depth 1`, потім `setup.sh venv` (шаблон перезбереться сам у
  повному `setup.sh`, бо зміниться коміт у `template.stamp`).
