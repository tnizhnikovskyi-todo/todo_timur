#!/usr/bin/env bash
# Обновить (или установить) модуль td_genset в существующей базе.
#
#   update.sh <dbname> [-- <доп. аргументы odoo-bin>]
#
# Если модуль в базе уже установлен — odoo-bin -u td_genset, иначе — -i td_genset
# (-u на неустановленном модуле молча ничего не делает). Затем --stop-after-init.
# Запущенный serve.sh для этой базы перезагрузит реестр сам; если интерфейс «залип» — перезапустите его.
# Полный лог: $ODOO_LOG_DIR/update-<dbname>.log. Код выхода — как у run_tests.sh (0 / код Odoo / 1 при ERROR в логе).
set -euo pipefail
# shellcheck source=env.sh
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"

usage() { echo "Использование: $0 <dbname> [-- <аргументы odoo-bin>]" >&2; exit 2; }
[[ $# -ge 1 ]] || usage
db="$1"; shift
if [[ $# -gt 0 ]]; then [[ "$1" == "--" ]] || usage; shift; fi
extra=("$@")

td_require_db_name "$db"
td_check_env
td_require_pg
td_db_exists "$db" || td_die "базы $db нет (создайте: $TD_TOOLS_DIR/new_db.sh $db)"

state="$(td_module_state "$db" "$TD_MODULE")"
if [[ "$state" == "installed" || "$state" == "to upgrade" ]]; then mode=-u; else mode=-i; fi
log="$ODOO_LOG_DIR/update-$db.log"
td_log "$db: $mode $TD_MODULE (сейчас: ${state:-нет записи}); лог: $log"

t0=$(date +%s)
set +e
td_odoo -d "$db" "$mode" "$TD_MODULE" --stop-after-init --http-port="$(td_free_port)" "${extra[@]}" > "$log" 2>&1
rc=$?
set -e

final_rc=$rc
if [[ $rc -eq 0 ]] && td_log_has_errors "$log" && [[ "${TD_TEST_STRICT:-1}" == "1" ]]; then
    final_rc=1
fi
new_state="$(td_module_state "$db" "$TD_MODULE")"
echo "---- $db: $TD_MODULE → ${new_state:-нет записи}, $(( $(date +%s) - t0 )) с, код Odoo $rc"
if td_log_has_errors "$log"; then
    echo "---- ERROR/CRITICAL (до 300 строк)"
    td_log_errors "$log" 300
fi
if [[ $final_rc -ne 0 || "$new_state" != "installed" ]]; then
    echo "---- хвост лога"
    tail -n 25 "$log"
    [[ "$new_state" == "installed" ]] || final_rc=$(( final_rc == 0 ? 4 : final_rc ))
fi
exit "$final_rc"
