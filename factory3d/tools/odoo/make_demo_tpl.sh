#!/usr/bin/env bash
# Зібрати шаблонну базу td_demo_tpl: f3d_template + демо меблевої фабрики (plant.odoo_push по XML-RPC)
# + td_factory3d і td_iot_sim (post_init_hook мігрує x_-поля демо, як на реальній базі).
#
#   make_demo_tpl.sh [--force] [--only <кроки push через кому>] [--skip <кроки через кому>]
#
# Ідемпотентний: якщо td_demo_tpl уже є — вихід (--force перезбирає). Далі тести беруть її як шаблон:
#   F3D_TEST_INSTALL=td_x F3D_TEMPLATE_DB=td_demo_tpl run_tests.sh td_<ім'я> /td_x:TestY
# Вихідна база — F3D_DEMO_SRC_DB (за замовчуванням f3d_template), результат — F3D_DEMO_TPL_DB.
# Повні логи: $ODOO_LOG_DIR/demo-push.log, update-<db>.log, serve-<db>.log.
set -euo pipefail
# shellcheck source=env.sh
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"

force=0; only=""; skip="${F3D_DEMO_SKIP:-modules,iot_module,signals}"   # iot — Enterprise; iot_module/signals — модуль ставимо з addons нижче
while [[ $# -gt 0 ]]; do
    case "$1" in
        --force) force=1 ;;
        --only) only="${2:?--only потребує значення}"; shift ;;
        --skip) skip="${2:?--skip потребує значення}"; shift ;;
        *) echo "Використання: $0 [--force] [--only кроки] [--skip кроки]" >&2; exit 2 ;;
    esac
    shift
done
F3D_DEMO_MODULES="${F3D_DEMO_MODULES:-purchase_stock,sale_stock,hr_attendance,stock_delivery,stock_picking_batch,stock_fleet}"
src="${F3D_DEMO_SRC_DB:-f3d_template}"
db="${F3D_DEMO_TPL_DB:-td_demo_tpl}"
f3d_require_db_name "$db"
f3d_check_env
f3d_require_pg
if f3d_db_exists "$db" && [[ $force -eq 0 ]]; then
    f3d_log "$db уже є (--force — перезібрати)"; exit 0
fi
f3d_lock_db "$db"
t0=$(date +%s)
log="$ODOO_LOG_DIR/demo-push.log"

f3d_psql -c "alter database \"$db\" with is_template false allow_connections true" 2>/dev/null || true
"$F3D_TOOLS_DIR/serve.sh" stop "$db" >/dev/null 2>&1 || true
F3D_TEMPLATE_DB="$src" f3d_clone_db "$db"
f3d_log "копія $src → $db за $(( $(date +%s) - t0 )) с"

# 1) мова демо (uk_UA) і модулі кроку "modules" — заздалегідь (через RPC ставити заважає cron); сервер без cron
f3d_pick_port "$db"
f3d_odoo -d "$db" -i "$F3D_DEMO_MODULES" --load-language=uk_UA --stop-after-init --http-port="$F3D_PORT" >"$ODOO_LOG_DIR/demo-lang.log" 2>&1 \
    || { tail -10 "$ODOO_LOG_DIR/demo-lang.log" >&2; f3d_die "не вдалося завантажити uk_UA"; }
"$F3D_TOOLS_DIR/serve.sh" "$db" -- --max-cron-threads=0 >/dev/null 2>&1
port="$(cat "$ODOO_RUN_DIR/$db.port")"
stop_srv() { "$F3D_TOOLS_DIR/serve.sh" stop "$db" >/dev/null 2>&1 || true; }
trap stop_srv EXIT
f3d_log "сервер на порту $port; заливаю демо (лог: $log)"
args=()
[[ -z "$only" ]] || args+=(--only "$only")
if [[ -n "$skip" ]]; then
    all="$(cd "$F3D_REPO_DIR/factory3d" && python3 - <<'PY'
from plant.odoo_push import STEPS
print(",".join(STEPS))
PY
)"
    keep=""
    for s in ${all//,/ }; do
        [[ ",$skip," == *",$s,"* ]] || keep+="${keep:+,}$s"
    done
    [[ -n "$only" ]] || args+=(--only "$keep")
fi
( cd "$F3D_REPO_DIR/factory3d" \
  && ODOO_URL="http://127.0.0.1:$port" ODOO_DB="$db" ODOO_USER=admin ODOO_PASSWORD=admin \
     python3 -m plant.odoo_push "${args[@]}" ) >"$log" 2>&1 \
    || { tail -15 "$log" >&2; f3d_die "odoo_push не вдався (повний лог $log)"; }
f3d_log "демо залито за $(( $(date +%s) - t0 )) с"
stop_srv
trap - EXIT

# 2) модулі factory3d: post_init_hook мігрує демо
exec 9>&-   # update.sh бере той самий lock
F3D_TEST_INSTALL=td_factory3d,td_iot_sim "$F3D_TOOLS_DIR/update.sh" "$db" | tail -5

# 3) зафіксувати як шаблон
f3d_psql -c "alter database \"$db\" with is_template true allow_connections false"
f3d_log "$db готова за $(( $(date +%s) - t0 )) с: F3D_TEMPLATE_DB=$db run_tests.sh …"
