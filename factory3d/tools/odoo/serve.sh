#!/usr/bin/env bash
# Сервер Odoo у фоні для перевірок інтерфейсу (Playwright) і ручної роботи.
#
#   serve.sh <dbname> [port] [-- <додаткові аргументи odoo-bin>]   запустити (без порту — порт з імені бази)
#   serve.sh stop <dbname> | serve.sh <dbname> stop                зупинити
#   serve.sh stop all                                              зупинити всі
#   serve.sh status                                                що запущено
#
# Сервер бачить лише свою базу (-d <dbname>, db-filter), вхід: admin / admin. Модулі — з
# factory3d/odoo_addons того worktree, де лежить скрипт (--addons-path). Порт за замовчуванням
# виводиться з імені бази (див. run_tests.sh), якщо зайнятий — наступний вільний; дізнатись:
# вивід скрипта, serve.sh status або $ODOO_RUN_DIR/<dbname>.port.
# pid і порт: $ODOO_RUN_DIR/<dbname>.pid|.port, лог: $ODOO_LOG_DIR/serve-<dbname>.log.
# Скрипт чекає, поки /web/health відповість 200 (до F3D_SERVE_WAIT с, за замовчуванням 120).
set -euo pipefail
# shellcheck source=env.sh
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"

usage() {
    echo "Використання: $0 <dbname> [port] [-- <аргументи odoo-bin>] | stop <dbname>|all | <dbname> stop | status" >&2
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
            echo "$db: працює, pid $pid, http://127.0.0.1:$(read_port "$db")/web/login?db=$db" \
                 "(addons: $(cat "$ODOO_RUN_DIR/$db.addons" 2>/dev/null || echo '?'))"
        else
            echo "$db: pid-файл є, процесу $pid немає (лог: $ODOO_LOG_DIR/serve-$db.log)"
        fi
    done
    [[ $any -eq 1 ]] || echo "серверів serve.sh не запущено"
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
        rm -f "$ODOO_RUN_DIR/$db.pid" "$ODOO_RUN_DIR/$db.port" "$ODOO_RUN_DIR/$db.addons"
        f3d_log "$db: сервер не запущений"
        return 0
    fi
    kill -TERM "$pid" 2>/dev/null || true
    for i in $(seq 1 40); do
        pid_alive "$pid" || break
        sleep 0.5
    done
    if pid_alive "$pid"; then
        f3d_warn "$db: не зупинився за 20 с — SIGKILL"
        kill -KILL "$pid" 2>/dev/null || true
    fi
    rm -f "$ODOO_RUN_DIR/$db.pid" "$ODOO_RUN_DIR/$db.port" "$ODOO_RUN_DIR/$db.addons"
    f3d_log "$db: сервер зупинений (pid $pid)"
}

cmd_start() {
    local db="$1" port="${2:-}"; shift 2 || shift $#
    local extra=("$@") pid log url wait_s i code=""
    f3d_require_db_name "$db"
    f3d_check_env
    f3d_require_pg
    f3d_db_exists "$db" || f3d_die "бази $db немає (створіть: $F3D_TOOLS_DIR/new_db.sh $db або run_tests.sh $db)"

    pid="$(read_pid "$db")"
    if pid_alive "$pid"; then
        f3d_log "$db уже запущений: http://127.0.0.1:$(read_port "$db")/web/login?db=$db (pid $pid)"
        return 0
    fi
    if [[ -n "$port" ]]; then
        [[ "$port" =~ ^[0-9]+$ ]] || f3d_die "порт має бути числом: '$port'"
        [[ "$(f3d_free_port "$port")" == "$port" ]] || f3d_die "порт $port зайнятий"
    else
        # fd 8 (lock порту) успадковує сервер і тримає його, поки сервер живий
        f3d_pick_port "$db"; port="$F3D_PORT"
    fi
    log="$ODOO_LOG_DIR/serve-$db.log"
    # setsid: сервер не вмирає разом з shell, що його запустив; pid = pid самого odoo-bin
    setsid "$ODOO_PY" "$ODOO_BIN" -c "$ODOO_CONF" --addons-path="$ODOO_ADDONS_PATH" -d "$db" --db-filter="^${db}\$" \
        --http-port="$port" --http-interface="$ODOO_HTTP_INTERFACE" "${extra[@]}" \
        > "$log" 2>&1 < /dev/null &
    pid=$!
    echo "$pid" > "$ODOO_RUN_DIR/$db.pid"
    echo "$port" > "$ODOO_RUN_DIR/$db.port"
    echo "$ODOO_ADDONS_PATH" > "$ODOO_RUN_DIR/$db.addons"

    url="http://127.0.0.1:$port"
    wait_s="${F3D_SERVE_WAIT:-120}"
    for i in $(seq 1 $(( wait_s * 2 ))); do
        if ! pid_alive "$pid"; then
            tail -n 30 "$log" >&2
            rm -f "$ODOO_RUN_DIR/$db.pid" "$ODOO_RUN_DIR/$db.port" "$ODOO_RUN_DIR/$db.addons"
            f3d_die "сервер завершився при запуску, лог: $log"
        fi
        # 200 має віддати саме наш процес: чекаємо в його логу рядок про зайнятий порт
        if grep -q "HTTP service (werkzeug) running on .*:$port" "$log" 2>/dev/null; then
            code="$(curl -s -o /dev/null -w '%{http_code}' --noproxy '*' --max-time 2 "$url/web/health" || true)"
            [[ "$code" == "200" ]] && break
        fi
        sleep 0.5
    done
    [[ "$code" == "200" ]] || f3d_die "сервер не відповів за $wait_s с (pid $pid), лог: $log"
    f3d_log "$db: $url/web/login?db=$db (admin / admin), pid $pid, лог: $log"
    f3d_log "зупинити: $F3D_TOOLS_DIR/serve.sh stop $db"
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
