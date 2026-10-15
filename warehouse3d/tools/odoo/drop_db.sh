#!/usr/bin/env bash
# Видалити бази (з розривом підключень) і їхні filestore.
#
#   drop_db.sh <name> [<name>…]
#   drop_db.sh --pattern '<LIKE-шаблон>'   наприклад: drop_db.sh --pattern 'wh_w1_%'
#   drop_db.sh --force …                   видалити й зайняті (прогін, що йде, serve.sh) — обережно
#
# Бази, зайняті прогоном (flock) або запущеним serve.sh, без --force пропускаються: при паралельній
# роботі кількох потоків/worktree чужі бази так не видалити. Шаблон і службові бази — ніколи.
set -euo pipefail
# shellcheck source=env.sh
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"

force=0
if [[ "${1:-}" == "--force" ]]; then force=1; shift; fi
[[ $# -ge 1 ]] || { echo "Використання: $0 [--force] <ім'я_бази>… | [--force] --pattern '<LIKE>'" >&2; exit 2; }
wh_require_pg
mkdir -p "$ODOO_RUN_DIR"
dbs=()
if [[ "$1" == "--pattern" ]]; then
    [[ $# -eq 2 ]] || wh_die "--pattern приймає один LIKE-шаблон"
    [[ "$2" =~ ^[a-z0-9_%-]+$ ]] || wh_die "недопустимий шаблон '$2'"
    mapfile -t dbs < <(wh_psql -At -c "select datname from pg_database where datname like '$2' and not datistemplate order by 1")
else
    dbs=("$@")
fi
[[ ${#dbs[@]} -gt 0 ]] || { wh_log "нічого видаляти"; exit 0; }
for db in "${dbs[@]}"; do
    wh_require_db_name "$db"
    pid="$(cat "$ODOO_RUN_DIR/$db.pid" 2>/dev/null || true)"
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
        if [[ $force -eq 0 ]]; then
            wh_warn "$db: запущений serve.sh (pid $pid) — пропускаю (--force — зупинити й видалити)"
            continue
        fi
        "$WH_TOOLS_DIR/serve.sh" stop "$db" || true
    fi
    (
        exec 8>"$ODOO_RUN_DIR/$db.lock"
        if ! flock -n 8; then
            [[ $force -eq 1 ]] || { wh_warn "$db: зайнята прогоном, що йде — пропускаю"; exit 0; }
            wh_warn "$db: зайнята прогоном, видаляю (--force)"
        fi
        wh_drop_db "$db"
        wh_log "видалена $db"
    )
done
