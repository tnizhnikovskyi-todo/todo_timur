#!/usr/bin/env bash
# Оновити (або встановити) модулі warehouse3d в існуючій базі.
#
#   update.sh <dbname> [-- <додаткові аргументи odoo-bin>]
#
# Модулі — WH_TEST_INSTALL (через кому) або всі з warehouse3d/odoo_addons. Ті, що вже встановлені в
# базі, оновлюються (-u), решта — ставляться (-i; -u на невстановленому модулі мовчки нічого не робить).
# Перед оновленням wh_constructor збирається застосунок у його static/app (prepare_module.sh; WH_APP_BUILD=skip — пропустити, I-02).
# Потім --stop-after-init. Запущений serve.sh для цієї бази перезавантажить реєстр сам; якщо
# інтерфейс «завис» — перезапустіть його. Повний лог: $ODOO_LOG_DIR/update-<dbname>.log.
# Код виходу — як у run_tests.sh (0 / код Odoo / 1 при ERROR у логу / 4 — модуль не встановився).
set -euo pipefail
# shellcheck source=env.sh
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"

usage() { echo "Використання: [WH_TEST_INSTALL=mod1,mod2] $0 <dbname> [-- <аргументи odoo-bin>]" >&2; exit 2; }
[[ $# -ge 1 ]] || usage
db="$1"; shift
if [[ $# -gt 0 ]]; then [[ "$1" == "--" ]] || usage; shift; fi
extra=("$@")

wh_require_db_name "$db"
wh_check_env
wh_require_pg
wh_db_exists "$db" || wh_die "бази $db немає (створіть: $WH_TOOLS_DIR/new_db.sh $db)"
wh_lock_db "$db"

modules="${WH_TEST_INSTALL:-$(wh_local_modules)}"
[[ -n "$modules" ]] || wh_die "нема що оновлювати: WH_TEST_INSTALL не заданий і в $WH_ADDONS_DIR немає модулів"
for m in ${modules//,/ }; do [[ "$m" == "wh_constructor" ]] && "$WH_TOOLS_DIR/prepare_module.sh"; done
upd=(); ins=()
for m in ${modules//,/ }; do
    state="$(wh_module_state "$db" "$m")"
    if [[ "$state" == "installed" || "$state" == "to upgrade" ]]; then upd+=("$m"); else ins+=("$m"); fi
done
args=()
[[ ${#upd[@]} -eq 0 ]] || args+=(-u "$(IFS=,; echo "${upd[*]}")")
[[ ${#ins[@]} -eq 0 ]] || args+=(-i "$(IFS=,; echo "${ins[*]}")")
log="$ODOO_LOG_DIR/update-$db.log"
wh_log "$db: ${args[*]} з $WH_ADDONS_DIR; лог: $log"
wh_pick_port "$db"

t0=$(date +%s)
set +e
wh_odoo -d "$db" "${args[@]}" --stop-after-init --http-port="$WH_PORT" "${extra[@]}" > "$log" 2>&1
rc=$?
set -e

final_rc=$rc
if [[ $rc -eq 0 ]] && wh_log_has_errors "$log" && [[ "${WH_TEST_STRICT:-1}" == "1" ]]; then
    final_rc=1
fi
bad=""
for m in ${modules//,/ }; do
    st="$(wh_module_state "$db" "$m")"
    [[ "$st" == "installed" ]] || bad+=" $m(${st:-немає запису})"
done
echo "---- $db: $modules → ${bad:+НЕ ВСТАНОВЛЕНІ:$bad}${bad:-installed}, $(( $(date +%s) - t0 )) с, код Odoo $rc"
if wh_log_has_errors "$log"; then
    echo "---- ERROR/CRITICAL (до 300 рядків)"
    wh_log_errors "$log" 300
fi
if [[ $final_rc -ne 0 || -n "$bad" ]]; then
    echo "---- хвіст логу"
    tail -n 15 "$log"
    [[ -z "$bad" ]] || final_rc=$(( final_rc == 0 ? 4 : final_rc ))
fi
exit "$final_rc"
