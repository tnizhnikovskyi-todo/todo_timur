#!/usr/bin/env bash
# Управление кластером PostgreSQL для Odoo.
#
#   pg.sh start     — запустить кластер (если кластера нет — создать и настроить, см. init)
#   pg.sh stop      — остановить (fast)
#   pg.sh restart   — перезапустить
#   pg.sh status    — состояние кластера, базы роли odoo, подключения
#   pg.sh init      — идемпотентно: кластер, настройки для тестов, роль odoo/odoo (CREATEDB), ~/.pgpass
#
# Postgres не запускается под root, поэтому все операции идут через pg_ctlcluster
# (сам переключается на владельца кластера) или от пользователя postgres (runuser).
set -euo pipefail
# shellcheck source=env.sh
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"

PG_CONF_DIR="/etc/postgresql/$PG_VERSION/$PG_CLUSTER"
TUNING_FILE="$PG_CONF_DIR/conf.d/90-td-odoo-dev.conf"
PGPASS_FILE="${PGPASSFILE:-$HOME/.pgpass}"

# Настройки только для разработки/тестов: fsync выключен — при падении контейнера кластер
# может повредиться (тогда: pg_dropcluster + pg.sh init + setup.sh template).
TUNING_CONTENT="# Создано smartgen/tools/odoo/pg.sh — ТОЛЬКО для разработки и тестов Odoo.
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

# Команда от пользователя postgres через unix-сокет (peer), без наших PGHOST/PGUSER.
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
        td_pg_ready && return 0
        sleep 1
    done
    td_die "Postgres не ответил за 30 с; лог: /var/log/postgresql/postgresql-$PG_VERSION-$PG_CLUSTER.log"
}

ensure_cluster() {
    command -v pg_lsclusters >/dev/null || td_die "нет postgresql-common (pg_lsclusters); создайте кластер вручную: initdb, см. ENV.md"
    if ! cluster_exists; then
        td_log "кластера $PG_VERSION/$PG_CLUSTER нет — создаю"
        pg_createcluster "$PG_VERSION" "$PG_CLUSTER" --port "$PGPORT" --locale C.UTF-8 --encoding UTF8
    fi
}

# Записать настройки; вернуть 0, если файл изменился (нужен рестарт).
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
        td_log "Postgres $PG_VERSION/$PG_CLUSTER уже запущен"
    else
        td_log "запускаю Postgres $PG_VERSION/$PG_CLUSTER"
        pg_ctlcluster "$PG_VERSION" "$PG_CLUSTER" start
    fi
    wait_ready
}

cmd_stop() {
    if cluster_exists && cluster_online; then
        if compgen -G "$ODOO_RUN_DIR/*.pid" >/dev/null; then
            td_warn "запущены серверы Odoo (serve.sh status) — они потеряют соединение с базой"
        fi
        td_log "останавливаю Postgres $PG_VERSION/$PG_CLUSTER"
        pg_ctlcluster "$PG_VERSION" "$PG_CLUSTER" stop -m fast
    else
        td_log "Postgres $PG_VERSION/$PG_CLUSTER не запущен"
    fi
}

cmd_status() {
    pg_lsclusters
    if td_pg_ready; then
        echo
        td_psql -c "
            select d.datname as база,
                   pg_size_pretty(pg_database_size(d.datname)) as размер,
                   (select count(*) from pg_stat_activity a where a.datname = d.datname) as подключений,
                   case when d.datistemplate then 'да' else '' end as шаблон,
                   case when d.datallowconn then '' else 'запрещены' end as \"новые подключения\"
              from pg_database d join pg_roles r on r.oid = d.datdba
             where r.rolname = current_user
             order by 1"
        td_psql -At -c "select 'подключений всего: ' || count(*) || ' из ' || current_setting('max_connections') from pg_stat_activity"
    else
        echo "Postgres не отвечает на $PGHOST:$PGPORT как роль $PGUSER (нет роли/пароля? — pg.sh init)"
        return 1
    fi
}

# Пароль роли — стандартный для локальной разработки `odoo` (кластер слушает только localhost;
# BUILD_PLAN запускает odoo-bin с --db_password=odoo). Другой — через TD_PG_PASSWORD.
# Пишется в ~/.pgpass, чтобы psql/createdb и Odoo (db_password в конфиге нет) работали без запроса.
pgpass_password() {
    local pw="${TD_PG_PASSWORD:-odoo}" tmp
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
        td_log "записаны настройки для тестов: $TUNING_FILE"
    fi
    if cluster_online && [[ $changed -eq 1 ]]; then
        td_log "перезапуск Postgres, чтобы применить настройки"
        pg_ctlcluster "$PG_VERSION" "$PG_CLUSTER" restart
    fi
    cmd_start
    local pw
    pw="$(pgpass_password)"
    # пароль передаём через переменную psql (stdin), а не в командной строке
    printf '%s\n' \
        "select format('create role %I login createdb', :'role') where not exists (select 1 from pg_roles where rolname = :'role') \gexec" \
        "alter role :\"role\" with login createdb nosuperuser password :'pw';" \
        | as_postgres psql -X -q -v ON_ERROR_STOP=1 -v role="$PGUSER" -v pw="$pw" -d postgres
    td_psql -At -c "select 'роль ' || current_user || ' подключается, Postgres ' || current_setting('server_version')" >&2
}

case "${1:-}" in
    start)   cmd_start ;;
    stop)    cmd_stop ;;
    restart) cmd_stop; cmd_start ;;
    status)  cmd_status ;;
    init)    cmd_init ;;
    *) echo "Использование: $0 start|stop|restart|status|init" >&2; exit 2 ;;
esac
