#!/usr/bin/env bash
# Керування кластером PostgreSQL для Odoo.
#
#   pg.sh start     — запустити кластер (якщо кластера немає — створити й налаштувати, див. init)
#   pg.sh stop      — зупинити (fast)
#   pg.sh restart   — перезапустити
#   pg.sh status    — стан кластера, бази ролі odoo, підключення
#   pg.sh init      — ідемпотентно: пакет Postgres (apt, якщо його немає), кластер, налаштування для тестів,
#                     роль odoo/odoo (CREATEDB), ~/.pgpass
#
# Postgres не запускається під root, тому всі операції йдуть через pg_ctlcluster
# (сам перемикається на власника кластера) або від користувача postgres (runuser).
set -euo pipefail
# shellcheck source=env.sh
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"

PG_CONF_DIR="/etc/postgresql/$PG_VERSION/$PG_CLUSTER"
TUNING_FILE="$PG_CONF_DIR/conf.d/90-f3d-odoo-dev.conf"
PGPASS_FILE="${PGPASSFILE:-$HOME/.pgpass}"

# Налаштування лише для розробки/тестів: fsync вимкнено — при падінні контейнера кластер
# може пошкодитись (тоді: pg_dropcluster + pg.sh init + setup.sh template).
TUNING_CONTENT="# Створено factory3d/tools/odoo/pg.sh — ЛИШЕ для розробки і тестів Odoo.
listen_addresses = 'localhost'
max_connections = 300
shared_buffers = 1GB
work_mem = 32MB
maintenance_work_mem = 256MB
fsync = off
synchronous_commit = off
full_page_writes = off
checkpoint_timeout = 30min
max_wal_size = 4GB
"

# Команда від користувача postgres через unix-сокет (peer), без наших PGHOST/PGUSER.
as_postgres() {
    if [[ "$(id -u)" -eq 0 ]]; then
        (cd / && env -u PGHOST -u PGUSER -u PGPASSWORD -u PGDATABASE runuser -u postgres -- "$@")
    else
        (cd / && sudo -n -u postgres -- env -u PGHOST -u PGUSER -u PGPASSWORD -u PGDATABASE "$@")
    fi
}

cluster_field() {   # $1 = номер колонки pg_lsclusters (4 = статус)
    pg_lsclusters -h 2>/dev/null | awk -v v="$PG_VERSION" -v c="$PG_CLUSTER" -v f="$1" '$1 == v && $2 == c { print $f }'
}
cluster_exists() { [[ -n "$(cluster_field 1)" ]]; }
cluster_online() { [[ "$(cluster_field 4)" == online* ]]; }

wait_ready() {
    local i
    for i in $(seq 1 30); do
        f3d_pg_ready && return 0
        sleep 1
    done
    f3d_die "Postgres не відповів за 30 с; лог: /var/log/postgresql/postgresql-$PG_VERSION-$PG_CLUSTER.log"
}

# Свіжий контейнер: ставимо пакети Postgres, якщо їх ще немає (потрібен root і apt-get).
ensure_packages() {
    if [[ -x "$PG_BINDIR/postgres" ]] && command -v pg_lsclusters >/dev/null; then
        return 0
    fi
    if ! command -v apt-get >/dev/null || [[ "$(id -u)" -ne 0 ]]; then
        f3d_die "Postgres $PG_VERSION не встановлено ($PG_BINDIR/postgres), а apt-get недоступний — встановіть postgresql-$PG_VERSION вручну"
    fi
    f3d_log "встановлюю postgresql-$PG_VERSION (apt-get)"
    export DEBIAN_FRONTEND=noninteractive
    f3d_retry apt-get update -qq
    f3d_retry apt-get install -y -qq "postgresql-$PG_VERSION" "postgresql-client-$PG_VERSION" >/dev/null
}

ensure_cluster() {
    ensure_packages
    command -v pg_lsclusters >/dev/null || f3d_die "немає postgresql-common (pg_lsclusters); створіть кластер вручну: initdb, див. ENV.md"
    if ! cluster_exists; then
        f3d_log "кластера $PG_VERSION/$PG_CLUSTER немає — створюю"
        pg_createcluster "$PG_VERSION" "$PG_CLUSTER" --port "$PGPORT" --locale C.UTF-8 --encoding UTF8
    fi
}

# Записати налаштування; повернути 0, якщо файл змінився (потрібен рестарт).
write_tuning() {
    if [[ -f "$TUNING_FILE" ]] && [[ "$(cat "$TUNING_FILE")" == "$(printf '%s' "$TUNING_CONTENT")" ]]; then
        return 1
    fi
    mkdir -p "$(dirname "$TUNING_FILE")"
    printf '%s' "$TUNING_CONTENT" > "$TUNING_FILE"
    chown postgres:postgres "$TUNING_FILE" 2>/dev/null || true
    return 0
}

cmd_start() {
    ensure_cluster
    if cluster_online; then
        f3d_log "Postgres $PG_VERSION/$PG_CLUSTER уже запущений"
    else
        f3d_log "запускаю Postgres $PG_VERSION/$PG_CLUSTER"
        pg_ctlcluster "$PG_VERSION" "$PG_CLUSTER" start
    fi
    wait_ready
}

cmd_stop() {
    if cluster_exists && cluster_online; then
        if compgen -G "$ODOO_RUN_DIR/*.pid" >/dev/null; then
            f3d_warn "запущені сервери Odoo (serve.sh status) — вони втратять з'єднання з базою"
        fi
        f3d_log "зупиняю Postgres $PG_VERSION/$PG_CLUSTER"
        pg_ctlcluster "$PG_VERSION" "$PG_CLUSTER" stop -m fast
    else
        f3d_log "Postgres $PG_VERSION/$PG_CLUSTER не запущений"
    fi
}

cmd_status() {
    pg_lsclusters
    if f3d_pg_ready; then
        echo
        f3d_psql -c "
            select d.datname as база,
                   pg_size_pretty(pg_database_size(d.datname)) as розмір,
                   (select count(*) from pg_stat_activity a where a.datname = d.datname) as підключень,
                   case when d.datistemplate then 'так' else '' end as шаблон,
                   case when d.datallowconn then '' else 'заборонені' end as \"нові підключення\"
              from pg_database d join pg_roles r on r.oid = d.datdba
             where r.rolname = current_user
             order by 1"
        f3d_psql -At -c "select 'підключень усього: ' || count(*) || ' з ' || current_setting('max_connections') from pg_stat_activity"
    else
        echo "Postgres не відповідає на $PGHOST:$PGPORT як роль $PGUSER (немає ролі/пароля? — pg.sh init)"
        return 1
    fi
}

# Пароль ролі — стандартний для локальної розробки `odoo` (кластер слухає лише localhost).
# Інший — через F3D_PG_PASSWORD. Пишеться в ~/.pgpass, щоб psql/createdb і Odoo (db_password
# у конфігу немає) працювали без запиту.
pgpass_password() {
    local pw="${F3D_PG_PASSWORD:-odoo}" tmp
    touch "$PGPASS_FILE"
    chmod 600 "$PGPASS_FILE"
    tmp="$(mktemp "$PGPASS_FILE.XXXXXX")"
    awk -F: -v p="$PGPORT" -v u="$PGUSER" '!(($1 == "127.0.0.1" || $1 == "localhost") && $2 == p && $4 == u)' \
        "$PGPASS_FILE" > "$tmp"
    printf '%s\n' "127.0.0.1:$PGPORT:*:$PGUSER:$pw" "localhost:$PGPORT:*:$PGUSER:$pw" >> "$tmp"
    chmod 600 "$tmp"
    mv "$tmp" "$PGPASS_FILE"
    printf '%s' "$pw"
}

cmd_init() {
    ensure_cluster
    local changed=0
    if write_tuning; then
        changed=1
        f3d_log "записані налаштування для тестів: $TUNING_FILE"
    fi
    if cluster_online && [[ $changed -eq 1 ]]; then
        f3d_log "перезапуск Postgres, щоб застосувати налаштування"
        pg_ctlcluster "$PG_VERSION" "$PG_CLUSTER" restart
    fi
    cmd_start
    local pw
    pw="$(pgpass_password)"
    # пароль передаємо через змінну psql (stdin), а не в командному рядку
    printf '%s\n' \
        "select format('create role %I login createdb', :'role') where not exists (select 1 from pg_roles where rolname = :'role') \gexec" \
        "alter role :\"role\" with login createdb nosuperuser password :'pw';" \
        | as_postgres psql -X -q -v ON_ERROR_STOP=1 -v role="$PGUSER" -v pw="$pw" -d postgres
    f3d_psql -At -c "select 'роль ' || current_user || ' підключається, Postgres ' || current_setting('server_version')" >&2
}

case "${1:-}" in
    start)   cmd_start ;;
    stop)    cmd_stop ;;
    restart) cmd_stop; cmd_start ;;
    status)  cmd_status ;;
    init)    cmd_init ;;
    *) echo "Використання: $0 start|stop|restart|status|init" >&2; exit 2 ;;
esac
