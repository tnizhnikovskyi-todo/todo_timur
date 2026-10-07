#!/usr/bin/env bash
# Удалить базы (с разрывом подключений) и их filestore.
#
#   drop_db.sh <name> [<name>…]
#   drop_db.sh --pattern '<LIKE-шаблон>'   например: drop_db.sh --pattern 'td_test_%'
#
# Шаблон td_template и служебные базы удалить нельзя (для шаблона — setup.sh template).
set -euo pipefail
# shellcheck source=env.sh
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"

[[ $# -ge 1 ]] || { echo "Использование: $0 <имя_базы>… | --pattern '<LIKE>'" >&2; exit 2; }
td_require_pg
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
    if [[ -f "$ODOO_RUN_DIR/$db.pid" ]]; then
        td_warn "для $db запущен serve.sh — останавливаю"
        "$TD_TOOLS_DIR/serve.sh" stop "$db" || true
    fi
    td_drop_db "$db"
    td_log "удалена $db"
done
