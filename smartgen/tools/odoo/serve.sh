#!/usr/bin/env bash
# Сервер Odoo в фоне для проверок интерфейса (Playwright) и ручной работы.
#
#   serve.sh <dbname> [port] [-- <доп. аргументы odoo-bin>]   запустить (порт: первый свободный от 8069)
#   serve.sh stop <dbname> | serve.sh <dbname> stop            остановить
#   serve.sh stop all                                          остановить все
#   serve.sh status                                            что запущено
#
# Сервер видит только свою базу (-d <dbname>, db-filter), вход: admin / admin.
# pid и порт: $ODOO_RUN_DIR/<dbname>.pid|.port, лог: $ODOO_LOG_DIR/serve-<dbname>.log.
# Скрипт ждёт, пока /web/health ответит 200 (до TD_SERVE_WAIT с, по умолчанию 120).
set -euo pipefail
# shellcheck source=env.sh
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"

usage() {
    echo "Использование: $0 <dbname> [port] [-- <аргументы odoo-bin>] | stop <dbname>|all | <dbname> stop | status" >&2
    exit 2
}

pid_alive() { [[ -n "${1:-}" ]] && kill -0 "$1" 2>/dev/null; }
read_pid()  { cat "$ODOO_RUN_DIR/$1.pid" 2>/dev/null || true; }
read_port() { cat "$ODOO_RUN_DIR/$1.port" 2>/dev/null || true; }

cmd_status() {
    local f db pid any=0
    for f in "$ODOO_RUN_DIR"/*.pid; do
        [[ -e "$f" ]] || continue
        any=1
        db="$(basename "$f" .pid)"; pid="$(read_pid "$db")"
        if pid_alive "$pid"; then
            echo "$db: работает, pid $pid, http://127.0.0.1:$(read_port "$db")/web/login?db=$db"
        else
            echo "$db: pid-файл есть, процесса $pid нет (лог: $ODOO_LOG_DIR/serve-$db.log)"
        fi
    done
    [[ $any -eq 1 ]] || echo "серверов serve.sh не запущено"
}

cmd_stop() {
    local db="$1" pid i
    if [[ "$db" == "all" ]]; then
        local f
        for f in "$ODOO_RUN_DIR"/*.pid; do
            [[ -e "$f" ]] && cmd_stop "$(basename "$f" .pid)"
        done
        return 0
    fi
    pid="$(read_pid "$db")"
    if ! pid_alive "$pid"; then
        rm -f "$ODOO_RUN_DIR/$db.pid" "$ODOO_RUN_DIR/$db.port"
        td_log "$db: сервер не запущен"
        return 0
    fi
    kill -TERM "$pid" 2>/dev/null || true
    for i in $(seq 1 40); do
        pid_alive "$pid" || break
        sleep 0.5
    done
    if pid_alive "$pid"; then
        td_warn "$db: не остановился за 20 с — SIGKILL"
        kill -KILL "$pid" 2>/dev/null || true
    fi
    rm -f "$ODOO_RUN_DIR/$db.pid" "$ODOO_RUN_DIR/$db.port"
    td_log "$db: сервер остановлен (pid $pid)"
}

cmd_start() {
    local db="$1" port="${2:-}"; shift 2 || shift $#
    local extra=("$@") pid log url wait_s i code
    td_require_db_name "$db"
    td_check_env
    td_require_pg
    td_db_exists "$db" || td_die "базы $db нет (создайте: $TD_TOOLS_DIR/new_db.sh $db или run_tests.sh $db)"

    pid="$(read_pid "$db")"
    if pid_alive "$pid"; then
        td_log "$db уже запущен: http://127.0.0.1:$(read_port "$db")/web/login?db=$db (pid $pid)"
        return 0
    fi
    if [[ -n "$port" ]]; then
        [[ "$port" =~ ^[0-9]+$ ]] || td_die "порт должен быть числом: '$port'"
        [[ "$(td_free_port "$port")" == "$port" ]] || td_die "порт $port занят"
    else
        port="$(td_free_port 8069)"
    fi
    log="$ODOO_LOG_DIR/serve-$db.log"
    # setsid: сервер не умирает вместе с вызвавшим shell; pid = pid самого odoo-bin
    setsid "$ODOO_PY" "$ODOO_BIN" -c "$ODOO_CONF" -d "$db" --db-filter="^${db}\$" \
        --http-port="$port" --http-interface="$ODOO_HTTP_INTERFACE" "${extra[@]}" \
        > "$log" 2>&1 < /dev/null &
    pid=$!
    echo "$pid" > "$ODOO_RUN_DIR/$db.pid"
    echo "$port" > "$ODOO_RUN_DIR/$db.port"

    url="http://127.0.0.1:$port"
    wait_s="${TD_SERVE_WAIT:-120}"
    for i in $(seq 1 $(( wait_s * 2 ))); do
        if ! pid_alive "$pid"; then
            tail -n 30 "$log" >&2
            rm -f "$ODOO_RUN_DIR/$db.pid" "$ODOO_RUN_DIR/$db.port"
            td_die "сервер завершился при запуске, лог: $log"
        fi
        code="$(curl -s -o /dev/null -w '%{http_code}' --noproxy '*' --max-time 2 "$url/web/health" || true)"
        [[ "$code" == "200" ]] && break
        sleep 0.5
    done
    [[ "$code" == "200" ]] || td_die "сервер не ответил за $wait_s с (pid $pid), лог: $log"
    td_log "$db: $url/web/login?db=$db (admin / admin), pid $pid, лог: $log"
    td_log "остановить: $TD_TOOLS_DIR/serve.sh stop $db"
}

mkdir -p "$ODOO_RUN_DIR" "$ODOO_LOG_DIR"
case "${1:-}" in
    ""|-h|--help) usage ;;
    status) cmd_status ;;
    stop)   [[ $# -eq 2 ]] || usage; cmd_stop "$2" ;;
    *)
        db="$1"; shift
        if [[ "${1:-}" == "stop" ]]; then cmd_stop "$db"; exit 0; fi
        port=""
        if [[ $# -gt 0 && "$1" != "--" ]]; then port="$1"; shift; fi
        if [[ $# -gt 0 ]]; then [[ "$1" == "--" ]] || usage; shift; fi
        cmd_start "$db" "$port" "$@"
        ;;
esac
