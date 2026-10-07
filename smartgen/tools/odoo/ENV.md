# Среда разработки и тестов `td_genset` (Odoo 18.0 CE)

Всё, кроме скриптов и эмулятора, лежит **вне репозитория** и при пересоздании контейнера восстанавливается
одной командой `smartgen/tools/odoo/setup.sh` (≈2 мин: клон 40 с, venv 10 с, шаблонная база 45 с).

## Шпаргалка (одна строка — одно действие)

```bash
T=/home/user/todo_timur/smartgen/tools/odoo
$T/pg.sh start                                   # поднять Postgres (после рестарта контейнера сам не стартует)
$T/run_tests.sh td_<имя>                         # свежая копия шаблона + -i td_genset + тесты /td_genset
$T/run_tests.sh td_<имя> /td_genset:TestRelay    # только класс (или :TestRelay.test_x, или тег)
$T/run_stand_tests.sh td_<имя>                   # стендовые тесты (тег td_genset_stand) со своим fake_relay
$T/new_db.sh td_<имя>                            # пустая копия шаблона (без td_genset)
$T/update.sh td_<имя>                            # -u td_genset (или -i, если ещё не установлен)
$T/serve.sh td_<имя> [порт]                      # сервер в фоне для Playwright (порт по умолчанию случайный), admin / admin
$T/serve.sh stop td_<имя>                        # остановить (serve.sh status — что запущено)
$T/drop_db.sh td_<имя>                           # удалить базу и filestore (--pattern 'td_w1_%'; занятые пропускает)
$T/setup.sh template                             # пересобрать шаблон td_template (≈45 с)
$T/i18n_export.sh td_<имя> [--fill-same]         # обновить td_genset/i18n/uk_UA.po из базы с модулем (см. ниже)
python3 /home/user/todo_timur/smartgen/tools/fake_relay.py --port 8081 --token dev-token-0123456789abcdefghij --snapshot-sec 10
```

Имена баз — `[a-z0-9_-]`; для параллельной работы у каждого потока свой префикс (`td_w1_…`, `td_w2_…`).
`T` — каталог скриптов **своего** worktree (см. раздел «Git worktree»).

## Git worktree (параллельные потоки W1–W5)

- Скрипты вычисляют корень репозитория от своего расположения и передают odoo-bin
  `--addons-path=/home/user/odoo18/addons,<корень worktree>/smartgen` — аргумент командной строки перекрывает
  `addons_path` из `/home/user/odoo18.conf` (там прописана основная копия `/home/user/todo_timur`).
  Поэтому запускайте скрипты **из своего worktree**: `/путь/к/wt/smartgen/tools/odoo/run_tests.sh td_w1_x`.
  `run_tests.sh` печатает фактический `addons-path`; `serve.sh status` — из какого worktree поднят сервер.
- Ручной запуск `odoo-bin -c /home/user/odoo18.conf …` без `--addons-path` возьмёт модуль из основной копии.
- Общие для всех worktree: Postgres, `td_template`, venv, исходники Odoo, `data_dir`. Не пересекаются: база,
  `filestore/<база>`, логи `logs/*-<база>.log`, pid/порт `run/<база>.*` — всё по имени базы.
- Одно имя базы два прогона одновременно не займут: `run_tests.sh`, `run_stand_tests.sh`, `update.sh`,
  `new_db.sh` берут блокировку `run/<база>.lock` (второй сразу завершится с ошибкой).
- `drop_db.sh` пропускает базы, занятые прогоном или `serve.sh` (`--force` — удалить всё равно).
- `serve.sh` без порта берёт случайный свободный порт и проверяет, что порт занял именно его процесс.
- Переопределить путь целиком: `ODOO_ADDONS_PATH=/home/user/odoo18/addons,/другой/smartgen $T/run_tests.sh …`.

## Что где

| Что | Где |
|---|---|
| Odoo 18.0 CE | `/home/user/odoo18` — `git clone --depth 1 --branch 18.0` (полный набор addons, 1.3 ГБ) |
| venv | `/home/user/odoo18-venv` (Python 3.12.3), список пакетов — `requirements-odoo.txt` там же |
| Конфиг | `/home/user/odoo18.conf` (права 600): `addons_path = /home/user/odoo18/addons,/home/user/todo_timur/smartgen`, `data_dir`, `db_*`, `http_port = 8069`, `http_interface = 127.0.0.1`, `limit_time_real(_cron) = 600`, `max_cron_threads = 1`, `without_demo = all` |
| Данные Odoo | `/home/user/odoo18-data`: `filestore/<база>`, `sessions`, `logs/` (логи скриптов), `run/` (pid serve.sh) |
| Postgres | кластер `16/main` (`/var/lib/postgresql/16/main`), TCP `127.0.0.1:5432`, роль `odoo` / пароль `odoo` (CREATEDB, не суперпользователь), пароль также в `~/.pgpass` |
| Настройки Postgres для тестов | `/etc/postgresql/16/main/conf.d/90-td-odoo-dev.conf`: `fsync=off`, `synchronous_commit=off`, `full_page_writes=off`, `max_connections=300`, `shared_buffers=1GB` |
| Шаблон | база `td_template`: `base, web, mail, contacts, maintenance` (+ их зависимости, всего 26 модулей), **без демо-данных** |
| Браузер для HttpCase/туров | `ODOO_BROWSER_BIN=/opt/pw-browsers/chromium` (Chromium 141 от Playwright) — выставляет `env.sh` |
| Эмулятор ретранслятора | `smartgen/tools/fake_relay.py` (см. ниже) |

Модуль появится в `smartgen/td_genset/`; соседние каталоги без `__manifest__.py` Odoo игнорирует.

## Python: почему 3.12, а не 3.13

- Odoo 18 официально поддерживает Python 3.10–3.12; эталонная платформа `requirements.txt` — Ubuntu 24.04,
  а в контейнере есть её системный **Python 3.12.3** (`/usr/bin/python3.12`, с `venv` и заголовками).
  На нём и собран venv — ничего скачивать не пришлось.
- Проверено: под системным 3.13.16 зависимости тоже ставятся (в ветке 18.0 `requirements.txt` уже есть
  пины для 3.13), но это не официальная конфигурация Odoo 18 — не используем.
- Отличия от `requirements.txt` (и для 3.12, и для 3.13 одинаковы — нет `-dev` пакетов, `apt` недоступен):
  - `psycopg2==2.9.9` → **`psycopg2-binary==2.9.9`** (тот же модуль `psycopg2`, собран с libpq; для сборки
    из исходников нужен `libpq-dev`);
  - `python-ldap` **не ставится** (нужны заголовки `libldap2-dev`/`libsasl2-dev`); нужен только модулю `auth_ldap`;
  - добавлены `websocket-client` (без него Odoo пропускает браузерные тесты) и `pdfminer.six` (индексация PDF).
- Пакеты ставит `uv pip` (если есть; ~10 с), иначе `pip`. Другой интерпретатор: `ODOO_PYTHON_BIN=/путь/python3.12 setup.sh venv`.

## Как устроены тестовые базы

- `td_template` помечена `IS_TEMPLATE` и `ALLOW_CONNECTIONS false`: к ней нельзя подключиться (и Odoo её не
  показывает), поэтому `createdb -T td_template` никогда не упирается в «source database is being accessed by
  other users». Тесты и `serve.sh` к шаблону не применяются; для правок — `setup.sh template` (пересборка).
- `new_db.sh` / `run_tests.sh`: `dropdb --force` одноимённой базы → `createdb -T td_template` (до 5 попыток) →
  копия `filestore/td_template` жёсткими ссылками (файлы filestore неизменяемы; без filestore у копии
  «битые» вложения и ассеты).
- `run_tests.sh` запускает `odoo-bin -c /home/user/odoo18.conf --addons-path=… -d <db> -i td_genset --test-enable
  --test-tags <теги> --stop-after-init --log-level=test --http-port=<свободный порт>`. Свой порт важен:
  `HttpCase` ходит на `http_port`, и общий 8069 смешал бы параллельные прогоны.
- Полный лог: `/home/user/odoo18-data/logs/test-<db>.log` (перезаписывается при следующем прогоне с тем же
  именем); в консоль — итог тестов, все записи ERROR/CRITICAL с трейсбеками, при провале — хвост лога.
- База после прогона остаётся (её можно открыть `serve.sh`); `TD_TEST_KEEP_DB=0` — удалить.

**Коды выхода `run_tests.sh`:** `0` — всё прошло; код Odoo (обычно `1`) — упали тесты или установка;
`1` — Odoo вернул 0, но в логе есть ERROR/CRITICAL (`TD_TEST_STRICT=0` — не считать); `4` — модуль не найден
в `addons_path` или не установился; `124` — таймаут (`TD_TEST_TIMEOUT`, по умолчанию 3600 с).
Прочие переменные: `TD_TEST_TEE=1` — дублировать лог в консоль; `TD_TEST_INSTALL=td_genset,other` — что ставить.
Аргументы после `--` уходят в `odoo-bin` (например, `-- --screenshots=/tmp/shots`).

`update.sh` пишет лог в `logs/update-<db>.log`, коды выхода те же. `serve.sh` — `logs/serve-<db>.log`,
ждёт ответа `/web/health` от своего процесса (до 120 с), сервер видит только свою базу (`-d`, `--db-filter`).

## Замеры (4 CPU, 15 ГБ)

| Операция | Время |
|---|---|
| Сборка `td_template` (`setup.sh template`) | 42 с |
| Копия базы из шаблона (`createdb -T` + filestore) | 0,2–0,6 с |
| `run_tests.sh` без модуля (`-i td_genset` → «invalid module names», код 4) | ≈4 с |
| `run_tests.sh` с минимальным модулем (`depends: mail, maintenance`, 2 теста) | ≈4 с |
| Проверка инфраструктуры: тесты `/maintenance` (18 тестов, вкл. тур в Chrome) | 43 с, 0 ошибок |
| Два прогона параллельно | не мешают друг другу (разные базы, логи, порты) |

Полный модуль `td_genset` будет устанавливаться дольше (ассеты, данные) — ориентир 10–30 с плюс сами тесты.

## Эмулятор ретранслятора `smartgen/tools/fake_relay.py`

Только стандартная библиотека; API 1:1 с `smartgen/relay_api.md` (разделы 3–5, 7): `/api/v1/status`, `/latest`,
`/readings`, `/raw`, `POST /commands`, `/commands/<id>`, `/commands?since`; токен проверяется первым (401);
`Cache-Control: no-store`. Моделирует генератор (режимы, пуск 1→3→5→6→7→8→9, останов 10→11→12→13→15→0,
сеть и автоматы, топливо, АКБ, счётчики), снимки `first`/`interval`/`change`, очередь команд
(`queued → sent → done` ≈1 с, ≤5 в ожидании, пауза 2 с). Служебный `GET/POST /_sim` (без токена с 127.0.0.1;
также `/api/v1/_sim`) — управление сценарием; все ключи и примеры curl — в начале файла.

```bash
python3 smartgen/tools/fake_relay.py --port 8081 --token dev-token-0123456789abcdefghij --snapshot-sec 10
python3 smartgen/tools/fake_relay.py --selftest     # → SELF-TEST PASSED (≈12 с)
```

В Odoo (dev): `smartgen.relay_url = http://127.0.0.1:8081/api/v1`, `smartgen.relay_token = dev-token-0123456789abcdefghij`.
Для тестов удобно `{"time_scale": 30}` (пуск ≈1,5 с) и `--snapshot-sec 1..2`. По умолчанию отдаёт поля версии
1.1.3; `--relay-version 1.1.1` (или `/_sim {"version": "1.1.1"}`) — как сейчас на сервере, без 5 полей из 5.1.

`run_stand_tests.sh <db> [теги]` поднимает **свой** эмулятор на свободном порту со случайным токеном
(параллельные прогоны не делят состояние `/_sim`) и передаёт тестам `TD_GENSET_STAND_URL`,
`TD_GENSET_STAND_TOKEN`, `TD_GENSET_STAND_SIM`; лог эмулятора — `logs/relay-<db>.log`.

**Никаких запросов на `gen-relay.todo.ltd`**: это живой генератор. Разработка и тесты — только эмулятор.

### Стендовые тесты `td_genset/tests/stand/` (W5)

- `run_stand_tests.sh <db>` → тег `td_genset_stand` (≈45 тестов, ≈40 с): без `TD_GENSET_STAND_URL`/`TOKEN` они
  пропускаются, адрес — только loopback. Каждый тест сбрасывает эмулятор (`/_sim {"reset": true, "snapshot_sec": 10}`).
- Сценарии со временем (повторы команд, связь, догон, расписание) и режим ретранслятора 1.1.1 поднимают **свой**
  экземпляр `fake_relay.py` на свободном порту (`tests/stand/relay_harness.py`, гасится в `tearDown`) с управляемыми
  часами: файл эмулятора грузится как есть, его `time.time()` сдвигается (`--clock-offset`), а `/_sim` получает
  ключ `{"clock_advance": N}`; время Odoo сдвигается синхронно (`freezegun`, `tick=True`). Поэтому эти тесты
  стартуют, например, «в понедельник 08:44 Kyiv» независимо от реального времени.
- Переменные: `TD_GENSET_FAKE_RELAY` — другой путь к эмулятору; `TD_GENSET_STAND_KEEP_LOGS=1` — не удалять логи
  своих экземпляров (`/tmp/td_genset_stand_relay_*.log`).
- `test_w5_stand_harness.py` проверяет только стенд и зелёный всегда; остальные до слияния W1–W4 красные на первой
  проверке поведения модуля (заглушки W0).

## Переводы `i18n/uk_UA.po` — `i18n_export.sh`

`$T/i18n_export.sh <db> [--fill-same] [--dry-run]` — база должна быть с установленным `td_genset` (например, после
`run_tests.sh <db>`), сама база не меняется:

1. `odoo-bin --i18n-export=<tmp>/td_genset.pot --modules=td_genset` (шаблон без языка, `--addons-path` своего worktree);
2. слияние с текущим `td_genset/i18n/uk_UA.po`: `msgmerge --no-fuzzy-matching`, если есть gettext (в контейнере нет),
   иначе Python `polib` (зависимость Odoo 18, тот же `POFile.merge`, что Odoo использует при импорте). Переводы
   существующих строк сохраняются, новые добавляются с пустым `msgstr`, исчезнувшие удаляются, `fuzzy` не ставится;
3. `--fill-same` — пустые `msgstr` строк с кириллицей заполняются тем же текстом (исходные строки модуля уже
   по-украински, для `uk_UA` перевод = оригинал); `--dry-run` — только статистика.

Печатает статистику (строк / переведено / пустых / fuzzy); лог odoo-bin — `logs/i18n-<db>.log`. Перевод строк без
кириллицы и проверку «без fuzzy и пустых msgstr для видимых строк» делает интеграция (BUILD_PLAN §3 W5, §4).

## Оговорки

- `fsync=off` и т. п. — только для тестов: при аварийном падении контейнера кластер может повредиться
  (лечение: `pg_dropcluster 16 main --stop`, затем `pg.sh init` и `setup.sh template`).
- Postgres не стартует сам после рестарта контейнера — `pg.sh start`. `pg.sh init` идемпотентен
  (кластер, настройки, роль, `~/.pgpass`); если кластера нет — создаёт его `pg_createcluster`.
- Пересборка шаблона во время чужих прогонов сломает их `createdb` — предупреждайте остальных.
- `Running as user 'root' is a security risk.` в логах — предупреждение, не ошибка. Wkhtmltopdf нет
  (PDF-отчёты не рендерятся, в логе INFO). `auth_ldap` работать не будет (нет `python-ldap`).
- Базы `td_*` копятся (≈30 МБ каждая): `drop_db.sh --pattern 'td_w1_%'` — свои; занятые чужими прогонами
  и серверами пропускаются, шаблон не удаляется никогда.
- Ветка 18.0 клонирована на коммит `e0d3d4e` от 07.10.2026; обновить: `git -C /home/user/odoo18 pull --depth 1`,
  затем `setup.sh venv template`.
