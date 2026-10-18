# shellcheck shell=bash
# Спільні змінні та функції для скриптів factory3d/tools/odoo/*.sh (Odoo 19.0 CE).
#
# Підключається через `source` (сам нічого не запускає і не змінює опції shell).
# Будь-яку змінну можна перевизначити оточенням перед викликом скрипта, наприклад:
#   ODOO_CONF=/tmp/other.conf factory3d/tools/odoo/run_tests.sh td_x
#
# Пароль ролі Postgres тут НЕ зберігається: він лежить у ~/.pgpass (створює pg.sh init) і в
# $ODOO_CONF (права 600, db_password); libpq-утиліти (createdb, psql…) беруть його з ~/.pgpass.

# ---------------------------------------------------------------- шляхи
F3D_TOOLS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
# Корінь worktree/клону визначається від розташування скриптів (factory3d/tools/odoo → ../../..),
# тому все працює з будь-якого worktree чи клону, а не лише з /home/user/todo_timur.
F3D_REPO_DIR="${F3D_REPO_DIR:-$(cd "$F3D_TOOLS_DIR/../../.." && pwd -P)}"
F3D_ADDONS_DIR="${F3D_ADDONS_DIR:-$F3D_REPO_DIR/factory3d/odoo_addons}"   # наші модулі td_*
F3D_TEMPLATE_DB="${F3D_TEMPLATE_DB:-f3d_template}"
# Стандартні залежності, які ставляться в шаблон (ті, що відсутні в Community, пропускаються
# і перелічуються при збиранні — див. ENV.md, «Недоступні модулі»).
F3D_TEMPLATE_MODULES="${F3D_TEMPLATE_MODULES:-stock,mrp,maintenance,mrp_maintenance,hr,stock_picking_batch,stock_fleet,fleet,web,bus,mail,mrp_workorder,mrp_account,analytic,web_hierarchy,delivery,stock_delivery,web_gantt,hr_attendance}"

F3D_ENV_ROOT="${F3D_ENV_ROOT:-/home/user}"                  # куди ставиться все, що поза репозиторієм
ODOO_BRANCH="${ODOO_BRANCH:-19.0}"
ODOO_REPO_URL="${ODOO_REPO_URL:-https://github.com/odoo/odoo.git}"
ODOO_HOME="${ODOO_HOME:-$F3D_ENV_ROOT/odoo19}"              # вихідники Odoo 19.0 CE (поза репозиторієм)
ODOO_VENV="${ODOO_VENV:-$F3D_ENV_ROOT/odoo19-venv}"
ODOO_PYTHON_BIN="${ODOO_PYTHON_BIN:-/usr/bin/python3.12}"   # з нього setup.sh створює venv
ODOO_PY="$ODOO_VENV/bin/python"
ODOO_BIN="$ODOO_HOME/odoo-bin"
ODOO_CONF="${ODOO_CONF:-$F3D_ENV_ROOT/odoo19.conf}"
ODOO_DATA_DIR="${ODOO_DATA_DIR:-$F3D_ENV_ROOT/odoo19-data}" # filestore, sessions
ODOO_LOG_DIR="${ODOO_LOG_DIR:-$ODOO_DATA_DIR/logs}"
ODOO_RUN_DIR="${ODOO_RUN_DIR:-$ODOO_DATA_DIR/run}"          # lock-файли, pid-файли serve.sh
ODOO_HTTP_INTERFACE="${ODOO_HTTP_INTERFACE:-127.0.0.1}"
# addons_path передається odoo-bin явно (--addons-path перекриває конфіг): модулі беруться з
# factory3d/odoo_addons САМЕ ЦЬОГО worktree, а не з копії, прописаної в $ODOO_CONF.
ODOO_ADDONS_PATH="${ODOO_ADDONS_PATH:-$ODOO_HOME/addons,$F3D_ADDONS_DIR}"
# Діапазон портів для HTTP-сервера Odoo (HttpCase ходить на http_port).
F3D_PORT_BASE="${F3D_PORT_BASE:-20000}"
F3D_PORT_SPAN="${F3D_PORT_SPAN:-20000}"

# ---------------------------------------------------------------- Postgres
PG_VERSION="${PG_VERSION:-16}"
PG_CLUSTER="${PG_CLUSTER:-main}"
PG_BINDIR="${PG_BINDIR:-/usr/lib/postgresql/$PG_VERSION/bin}"
export PGHOST="${PGHOST:-127.0.0.1}"
export PGPORT="${PGPORT:-5432}"
export PGUSER="${PGUSER:-odoo}"
export PGDATABASE="${PGDATABASE:-postgres}"
export PGCONNECT_TIMEOUT="${PGCONNECT_TIMEOUT:-10}"
export PGAPPNAME="${PGAPPNAME:-f3d-tools}"

# ---------------------------------------------------------------- браузер для HttpCase / тур-тестів
# Odoo шукає google-chrome/chromium у PATH або бере ODOO_BROWSER_BIN; беремо Chromium від Playwright.
if [[ -z "${ODOO_BROWSER_BIN:-}" && -x /opt/pw-browsers/chromium ]]; then
    export ODOO_BROWSER_BIN=/opt/pw-browsers/chromium
fi

# ---------------------------------------------------------------- функції
f3d_log()  { printf '==> %s\n' "$*" >&2; }
f3d_warn() { printf 'УВАГА: %s\n' "$*" >&2; }
f3d_die()  { printf 'ПОМИЛКА: %s\n' "$*" >&2; exit "${2:-1}"; }

# Команда з повторами при мережевих збоях: 2 / 4 / 8 / 16 с (усього до 5 спроб).
f3d_retry() {
    local attempt delay=2
    for attempt in 1 2 3 4 5; do
        "$@" && return 0
        [[ $attempt -lt 5 ]] || return 1
        f3d_warn "не вдалось: $* — повтор через ${delay} с (спроба $attempt з 5)"
        sleep "$delay"
        delay=$(( delay * 2 ))
    done
}

# Ім'я бази: лише [a-z0-9_-], не службові й не шаблон.
f3d_require_db_name() {
    local db="${1:-}"
    [[ -n "$db" ]] || f3d_die "не задано ім'я бази"
    [[ "$db" =~ ^[a-z0-9_][a-z0-9_-]{0,62}$ ]] || f3d_die "недопустиме ім'я бази '$db' (дозволено: a-z 0-9 _ -, до 63 символів)"
    case "$db" in
        postgres|template0|template1|"$F3D_TEMPLATE_DB")
            f3d_die "базу '$db' чіпати не можна (службова або шаблон)";;
    esac
}

# Перевірка, що Odoo, venv і конфіг на місці.
f3d_check_env() {
    [[ -x "$ODOO_PY" ]]   || f3d_die "немає venv: $ODOO_PY (запустіть $F3D_TOOLS_DIR/setup.sh)"
    [[ -f "$ODOO_BIN" ]]  || f3d_die "немає Odoo: $ODOO_BIN (запустіть $F3D_TOOLS_DIR/setup.sh)"
    [[ -f "$ODOO_CONF" ]] || f3d_die "немає конфігу: $ODOO_CONF (запустіть $F3D_TOOLS_DIR/setup.sh)"
    mkdir -p "$ODOO_LOG_DIR" "$ODOO_RUN_DIR"
}

# Postgres доступний?
f3d_pg_ready() { "$PG_BINDIR/pg_isready" -q -h "$PGHOST" -p "$PGPORT" >/dev/null 2>&1; }
f3d_require_pg() {
    f3d_pg_ready || f3d_die "Postgres не відповідає на $PGHOST:$PGPORT (запустіть $F3D_TOOLS_DIR/pg.sh start)"
}

# psql від ролі odoo до бази postgres; -At — «голий» вивід.
f3d_psql() { "$PG_BINDIR/psql" -X -q -v ON_ERROR_STOP=1 -d postgres "$@"; }

f3d_db_exists() {
    [[ "$(f3d_psql -At -c "select 1 from pg_database where datname = '$1'")" == "1" ]]
}

f3d_require_template() {
    f3d_db_exists "$F3D_TEMPLATE_DB" \
        || f3d_die "немає шаблонної бази $F3D_TEMPLATE_DB (зберіть: $F3D_TOOLS_DIR/setup.sh template)"
}

# Видалити базу (з розривом підключень) і її filestore.
f3d_drop_db() {
    local db="$1"
    PGOPTIONS='-c client_min_messages=warning' "$PG_BINDIR/dropdb" --if-exists --force "$db"
    rm -rf -- "${ODOO_DATA_DIR:?}/filestore/$db"
}

# Створити базу копією шаблона (спершу видаливши однойменну) і скопіювати filestore шаблона.
# CREATE DATABASE … TEMPLATE падає, якщо до шаблона хтось підключений; у f3d_template
# підключення заборонені (ALLOW_CONNECTIONS false), але про всяк випадок — кілька спроб.
f3d_clone_db() {
    local db="$1" attempt err
    f3d_require_template
    f3d_drop_db "$db"
    for attempt in 1 2 3 4 5; do
        if err="$("$PG_BINDIR/createdb" -T "$F3D_TEMPLATE_DB" -O "$PGUSER" "$db" 2>&1)"; then
            break
        fi
        [[ $attempt -lt 5 ]] || f3d_die "createdb -T $F3D_TEMPLATE_DB $db не вдався: $err"
        f3d_warn "createdb не вдався (спроба $attempt): $err — повтор через 2 с"
        sleep 2
    done
    local src="$ODOO_DATA_DIR/filestore/$F3D_TEMPLATE_DB" dst="$ODOO_DATA_DIR/filestore/$db"
    if [[ -d "$src" ]]; then
        mkdir -p "$ODOO_DATA_DIR/filestore"
        # жорсткі посилання: файли filestore незмінні (ім'я = хеш вмісту), копія миттєва
        cp -al "$src" "$dst" 2>/dev/null || cp -a "$src" "$dst"
    fi
}

# Вільний TCP-порт на 127.0.0.1, шукаючи від N (за замовчуванням — будь-який ефемерний).
f3d_free_port() {
    local py="$ODOO_PY"
    [[ -x "$py" ]] || py=python3
    "$py" - "${1:-0}" <<'PY'
import socket, sys
start = int(sys.argv[1])
for port in ([0] if start == 0 else range(start, start + 400)):
    with socket.socket() as s:
        try:
            s.bind(("127.0.0.1", port))
        except OSError:
            continue
        print(s.getsockname()[1])
        break
else:
    sys.exit("немає вільного порту")
PY
}

# Детермінований стартовий порт з імені бази: F3D_PORT_BASE + cksum(db) % F3D_PORT_SPAN.
f3d_port_for_db() {
    local sum
    sum="$(printf '%s' "$1" | cksum | cut -d' ' -f1)"
    echo $(( F3D_PORT_BASE + sum % F3D_PORT_SPAN ))
}

# Обрати HTTP-порт для бази: починаючи з детермінованого, перший вільний, на який вдалось взяти
# lock-файл (fd 8 — тримається, поки живе скрипт і його дочірні процеси). Розрахунок «від імені бази»
# дає стабільний порт для однієї бази, а lock порту виключає гонку двох паралельних прогонів, у яких
# хеші імен збіглись. Результат — у змінній F3D_PORT.
f3d_pick_port() {
    local db="$1" start port i
    mkdir -p "$ODOO_RUN_DIR"
    start="$(f3d_port_for_db "$db")"
    for i in $(seq 0 49); do
        port=$(( F3D_PORT_BASE + (start - F3D_PORT_BASE + i) % F3D_PORT_SPAN ))
        exec 8>"$ODOO_RUN_DIR/port-$port.lock"
        flock -n 8 || continue
        if [[ "$(f3d_free_port "$port")" == "$port" ]]; then
            F3D_PORT="$port"
            return 0
        fi
    done
    f3d_die "не знайшов вільного порту біля $start для бази $db"
}

# Запустити odoo-bin з нашим конфігом і addons_path цього worktree.
f3d_odoo() { "$ODOO_PY" "$ODOO_BIN" -c "$ODOO_CONF" --addons-path="$ODOO_ADDONS_PATH" "$@"; }

# Ексклюзивне блокування бази на час роботи скрипта (і запущеного ним odoo-bin): два прогони
# з однією назвою бази — зокрема з різних worktree — не затруть одне одному базу, filestore і лог.
f3d_lock_db() {
    mkdir -p "$ODOO_RUN_DIR"
    exec 9>"$ODOO_RUN_DIR/$1.lock"
    flock -n 9 || f3d_die "база $1 зайнята іншим прогоном (lock $ODOO_RUN_DIR/$1.lock) — візьміть іншу назву"
}

# Стан модуля в базі: installed / uninstalled / to upgrade / … або порожньо, якщо запису немає.
f3d_module_state() {
    "$PG_BINDIR/psql" -X -q -At -d "$1" -c "select state from ir_module_module where name = '$2'" 2>/dev/null || true
}

# Модулі з каталогу odoo_addons (каталоги з __manifest__.py), через кому.
f3d_local_modules() {
    local d out=()
    for d in "$F3D_ADDONS_DIR"/*/; do
        [[ -f "${d}__manifest__.py" ]] && out+=("$(basename "$d")")
    done
    local IFS=,
    echo "${out[*]:-}"
}

# Чи є модуль $1 у вихідниках Odoo (каталог з __manifest__.py в addons/ або odoo/addons/).
f3d_odoo_module_dir() {
    local m="$1" d
    for d in "$ODOO_HOME/addons/$m" "$ODOO_HOME/odoo/addons/$m"; do
        [[ -f "$d/__manifest__.py" ]] && { echo "$d"; return 0; }
    done
    return 1
}

# Надрукувати з логу Odoo записи рівня ERROR/CRITICAL разом із трейсбеками (не більше $2 рядків).
# Запис логу починається з дати; рядки без дати — продовження (трейсбек) попереднього запису.
f3d_log_errors() {
    local logfile="$1" max="${2:-300}"
    awk -v max="$max" '
        /^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9:,]+ [0-9]+ / {
            keep = ($4 == "ERROR" || $4 == "CRITICAL")
        }
        keep { if (++n > max) { print "… (обрізано, див. повний лог)"; exit } print }
    ' "$logfile"
}

f3d_log_has_errors() {
    grep -qE '^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9:,]+ [0-9]+ (ERROR|CRITICAL) ' "$1"
}
