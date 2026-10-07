#!/usr/bin/env bash
# Удалить базы (с разрывом подключений) и их filestore.
#
#   drop_db.sh <name> [<name>…]
#   drop_db.sh --pattern '<LIKE-шаблон>'   например: drop_db.sh --pattern 'td_w1_%'
#   drop_db.sh --force …                   удалить и занятые (идущий прогон, serve.sh) — осторожно
#
# Базы, занятые прогоном (flock) или запущенным serve.sh, без --force пропускаются: при параллельной
# работе нескольких потоков/worktree чужие базы так не удалить. Шаблон и служебные базы — никогда.
set -euo pipefail
# shellcheck source=env.sh
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"

force=0
if [[ "${1:-}" == "--force" ]]; then force=1; shift; fi
[[ $# -ge 1 ]] || { echo "Использование: $0 [--force] <имя_базы>… | [--force] --pattern '<LIKE>'" >&2; exit 2; }
td_require_pg
mkdir -p "$ODOO_RUN_DIR"
dbs=()
if [[ "$1" == "--pattern" ]]; then
    [[ $# -eq 2 ]] || td_die "--pattern принимает один LIKE-шаблон"
    [[ "$2" =~ ^[a-z0-9_%-]+$ ]] || td_die "недопустимый шаблон '$2'"
    mapfile -t dbs < <(td_psql -At -c "select datname from pg_database where datname like '$2' and not datistemplate order by 1")
else
    dbs=("$@")
fi
[[ ${#dbs[@]} -gt 0 ]] || { td_log "нечего удалять"; exit 0; }
for db in "${dbs[@]}"; do
    td_require_db_name "$db"
    pid="$(cat "$ODOO_RUN_DIR/$db.pid" 2>/dev/null || true)"
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
        if [[ $force -eq 0 ]]; then
            td_warn "$db: запущен serve.sh (pid $pid) — пропускаю (--force — остановить и удалить)"
            continue
        fi
        "$TD_TOOLS_DIR/serve.sh" stop "$db" || true
    fi
    (
        exec 8>"$ODOO_RUN_DIR/$db.lock"
        if ! flock -n 8; then
            [[ $force -eq 1 ]] || { td_warn "$db: занята идущим прогоном — пропускаю"; exit 0; }
            td_warn "$db: занята прогоном, удаляю (--force)"
        fi
        td_drop_db "$db"
        td_log "удалена $db"
    )
done
