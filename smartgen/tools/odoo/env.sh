# shellcheck shell=bash
# Общие переменные и функции для скриптов smartgen/tools/odoo/*.sh.
#
# Подключается через `source` (сам ничего не запускает и не меняет опции shell).
# Любую переменную можно переопределить окружением до вызова скрипта, например:
#   ODOO_CONF=/tmp/other.conf smartgen/tools/odoo/run_tests.sh td_x
#
# Пароль роли Postgres здесь НЕ хранится: он лежит в ~/.pgpass (создаёт setup.sh / pg.sh init),
# его читают и libpq-утилиты (createdb, psql…), и Odoo (db_password в конфиге не задан).

# ---------------------------------------------------------------- пути
TD_TOOLS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
TD_REPO_DIR="${TD_REPO_DIR:-$(cd "$TD_TOOLS_DIR/../../.." && pwd -P)}"
TD_ADDONS_DIR="${TD_ADDONS_DIR:-$TD_REPO_DIR/smartgen}"     # здесь появится модуль td_genset
TD_MODULE="${TD_MODULE:-td_genset}"
TD_TEMPLATE_DB="${TD_TEMPLATE_DB:-td_template}"
TD_TEMPLATE_MODULES="${TD_TEMPLATE_MODULES:-base,web,mail,contacts,maintenance}"

ODOO_BRANCH="${ODOO_BRANCH:-18.0}"
ODOO_REPO_URL="${ODOO_REPO_URL:-https://github.com/odoo/odoo.git}"
ODOO_HOME="${ODOO_HOME:-/home/user/odoo18}"                 # исходники Odoo 18.0 CE (вне репозитория)
ODOO_VENV="${ODOO_VENV:-/home/user/odoo18-venv}"
ODOO_PYTHON_BIN="${ODOO_PYTHON_BIN:-/usr/bin/python3.12}"   # из него setup.sh создаёт venv
ODOO_PY="$ODOO_VENV/bin/python"
ODOO_BIN="$ODOO_HOME/odoo-bin"
ODOO_CONF="${ODOO_CONF:-/home/user/odoo18.conf}"
ODOO_DATA_DIR="${ODOO_DATA_DIR:-/home/user/odoo18-data}"    # filestore, sessions
ODOO_LOG_DIR="${ODOO_LOG_DIR:-$ODOO_DATA_DIR/logs}"
ODOO_RUN_DIR="${ODOO_RUN_DIR:-$ODOO_DATA_DIR/run}"          # pid-файлы serve.sh
ODOO_HTTP_INTERFACE="${ODOO_HTTP_INTERFACE:-127.0.0.1}"

# ---------------------------------------------------------------- Postgres
PG_VERSION="${PG_VERSION:-16}"
PG_CLUSTER="${PG_CLUSTER:-main}"
PG_BINDIR="${PG_BINDIR:-/usr/lib/postgresql/$PG_VERSION/bin}"
export PGHOST="${PGHOST:-127.0.0.1}"
export PGPORT="${PGPORT:-5432}"
export PGUSER="${PGUSER:-odoo}"
export PGDATABASE="${PGDATABASE:-postgres}"
export PGCONNECT_TIMEOUT="${PGCONNECT_TIMEOUT:-10}"
export PGAPPNAME="${PGAPPNAME:-td-tools}"

# ---------------------------------------------------------------- браузер для HttpCase / тур-тестов
# Odoo ищет google-chrome/chromium в PATH или берёт ODOO_BROWSER_BIN; используем Chromium от Playwright.
if [[ -z "${ODOO_BROWSER_BIN:-}" && -x /opt/pw-browsers/chromium ]]; then
    export ODOO_BROWSER_BIN=/opt/pw-browsers/chromium
fi

# ---------------------------------------------------------------- функции
td_log()  { printf '==> %s\n' "$*" >&2; }
td_warn() { printf 'ВНИМАНИЕ: %s\n' "$*" >&2; }
td_die()  { printf 'ОШИБКА: %s\n' "$*" >&2; exit "${2:-1}"; }

# Имя базы: только [a-z0-9_-], не служебные и не шаблон.
td_require_db_name() {
    local db="${1:-}"
    [[ -n "$db" ]] || td_die "не задано имя базы"
    [[ "$db" =~ ^[a-z0-9_][a-z0-9_-]{0,62}$ ]] || td_die "недопустимое имя базы '$db' (разрешено: a-z 0-9 _ -, до 63 символов)"
    case "$db" in
        postgres|template0|template1|"$TD_TEMPLATE_DB")
            td_die "базу '$db' трогать нельзя (служебная или шаблон)";;
    esac
}

# Проверка, что Odoo, venv и конфиг на месте.
td_check_env() {
    [[ -x "$ODOO_PY" ]]   || td_die "нет venv: $ODOO_PY (запустите $TD_TOOLS_DIR/setup.sh)"
    [[ -f "$ODOO_BIN" ]]  || td_die "нет Odoo: $ODOO_BIN (запустите $TD_TOOLS_DIR/setup.sh)"
    [[ -f "$ODOO_CONF" ]] || td_die "нет конфига: $ODOO_CONF (запустите $TD_TOOLS_DIR/setup.sh)"
    mkdir -p "$ODOO_LOG_DIR" "$ODOO_RUN_DIR"
}

# Postgres доступен под ролью odoo?
td_pg_ready() { "$PG_BINDIR/pg_isready" -q -h "$PGHOST" -p "$PGPORT" >/dev/null 2>&1; }
td_require_pg() {
    td_pg_ready || td_die "Postgres не отвечает на $PGHOST:$PGPORT (запустите $TD_TOOLS_DIR/pg.sh start)"
}

# psql от роли odoo к базе postgres; -At — «голый» вывод.
td_psql() { "$PG_BINDIR/psql" -X -q -v ON_ERROR_STOP=1 -d postgres "$@"; }

td_db_exists() {
    [[ "$(td_psql -At -c "select 1 from pg_database where datname = '$1'")" == "1" ]]
}

td_require_template() {
    td_db_exists "$TD_TEMPLATE_DB" \
        || td_die "нет шаблонной базы $TD_TEMPLATE_DB (соберите: $TD_TOOLS_DIR/setup.sh template)"
}

# Удалить базу (с разрывом подключений) и её filestore.
td_drop_db() {
    local db="$1"
    PGOPTIONS='-c client_min_messages=warning' "$PG_BINDIR/dropdb" --if-exists --force "$db"
    rm -rf -- "${ODOO_DATA_DIR:?}/filestore/$db"
}

# Создать базу копией шаблона (сначала удалив одноимённую) и скопировать filestore шаблона.
# CREATE DATABASE … TEMPLATE падает, если к шаблону кто-то подключён; у td_template
# подключения запрещены (ALLOW_CONNECTIONS false), но на всякий случай — несколько попыток.
td_clone_db() {
    local db="$1" attempt err
    td_require_template
    td_drop_db "$db"
    for attempt in 1 2 3 4 5; do
        if err="$("$PG_BINDIR/createdb" -T "$TD_TEMPLATE_DB" -O "$PGUSER" "$db" 2>&1)"; then
            break
        fi
        [[ $attempt -lt 5 ]] || td_die "createdb -T $TD_TEMPLATE_DB $db не удался: $err"
        td_warn "createdb не удался (попытка $attempt): $err — повтор через 2 с"
        sleep 2
    done
    local src="$ODOO_DATA_DIR/filestore/$TD_TEMPLATE_DB" dst="$ODOO_DATA_DIR/filestore/$db"
    if [[ -d "$src" ]]; then
        mkdir -p "$ODOO_DATA_DIR/filestore"
        # жёсткие ссылки: файлы filestore неизменяемы (имя = хеш содержимого), копия мгновенная
        cp -al "$src" "$dst" 2>/dev/null || cp -a "$src" "$dst"
    fi
}

# Свободный TCP-порт на 127.0.0.1 (по умолчанию — любой эфемерный; с аргументом — первый свободный от N).
td_free_port() {
    local py="$ODOO_PY"
    [[ -x "$py" ]] || py=python3
    "$py" - "${1:-0}" <<'PY'
import socket, sys
start = int(sys.argv[1])
for port in ([0] if start == 0 else range(start, start + 200)):
    with socket.socket() as s:
        try:
            s.bind(("127.0.0.1", port))
        except OSError:
            continue
        print(s.getsockname()[1])
        break
else:
    sys.exit("нет свободного порта")
PY
}

# Запустить odoo-bin с нашим конфигом.
td_odoo() { "$ODOO_PY" "$ODOO_BIN" -c "$ODOO_CONF" "$@"; }

# Состояние модуля в базе: installed / uninstalled / to upgrade / … или пусто, если записи нет.
td_module_state() {
    "$PG_BINDIR/psql" -X -q -At -d "$1" -c "select state from ir_module_module where name = '$2'" 2>/dev/null || true
}

# Напечатать из лога Odoo записи уровня ERROR/CRITICAL вместе с трейсбеками (не больше $2 строк).
# Запись лога начинается с даты; строки без даты — продолжение (трейсбек) предыдущей записи.
td_log_errors() {
    local logfile="$1" max="${2:-300}"
    awk -v max="$max" '
        /^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9:,]+ [0-9]+ / {
            keep = ($4 == "ERROR" || $4 == "CRITICAL")
        }
        keep { if (++n > max) { print "… (обрезано, см. полный лог)"; exit } print }
    ' "$logfile"
}

td_log_has_errors() {
    grep -qE '^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9:,]+ [0-9]+ (ERROR|CRITICAL) ' "$1"
}
