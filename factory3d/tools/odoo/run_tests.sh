#!/usr/bin/env bash
# Прогнати тести модулів factory3d на свіжій копії шаблона.
#
#   run_tests.sh <dbname> [test-tags] [-- <додаткові аргументи odoo-bin>]
#
#   Що ставити: змінна F3D_TEST_INSTALL (модулі через кому, для `-i`); за замовчуванням — усі модулі
#   з factory3d/odoo_addons (каталоги з __manifest__.py).
#   test-tags за замовчуванням — /<модуль> для кожного модуля з F3D_TEST_INSTALL, наприклад
#   /factory3d_iot_sim; приклади: /factory3d_iot_sim:TestX, /factory3d_iot_sim:TestX.test_y,
#   my_tour_tag (за тегом), -at_install (виключити).
#
# Що робить: видаляє базу <dbname>, якщо є → createdb -T f3d_template (+ копія filestore) →
#   odoo-bin -c $ODOO_CONF --addons-path=<odoo>/addons,<worktree>/factory3d/odoo_addons -d <dbname>
#            -i $F3D_TEST_INSTALL --test-enable --test-tags <теги> --stop-after-init --log-level=test
#            --http-port=<порт з імені бази>
# Повний лог: $ODOO_LOG_DIR/test-<dbname>.log (перезаписується наступним прогоном з тим самим іменем).
# Друкує: підсумок тестів, записи ERROR/CRITICAL з трейсбеками, короткий хвіст логу (при провалі
# або якщо тести не запускались) і останній рядок «OK» / «ПРОВАЛ».
#
# Паралельні прогони безпечні, якщо в них різні <dbname>: своя база, filestore, лог, lock-файл і
# HTTP-порт. Порт виводиться з імені бази (F3D_PORT_BASE + cksum % F3D_PORT_SPAN; якщо він
# зайнятий — наступний вільний; порт блокується flock-ом на час прогону), lock — $ODOO_RUN_DIR/<db>.lock:
# те саме ім'я двічі зайняти не можна (другий прогон одразу завершиться з помилкою).
# Модулі беруться з factory3d/odoo_addons того worktree, де лежить скрипт (--addons-path).
#
# Код виходу: код Odoo (0 — усе пройшло); 1 — Odoo повернув 0, але в логу є ERROR/CRITICAL
# (F3D_TEST_STRICT=0 вимикає); 4 — модуль не знайдено або не встановився; 124 — таймаут.
#
# Змінні: F3D_TEST_INSTALL, F3D_TEST_TIMEOUT (с, за замовчуванням 3600), F3D_TEST_TEE=1 — дублювати лог
#   у консоль, F3D_TEST_KEEP_DB=0 — видалити базу після прогону (за замовчуванням лишається: її можна
#   відкрити через serve.sh).
set -euo pipefail
# shellcheck source=env.sh
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"

usage() { echo "Використання: [F3D_TEST_INSTALL=mod1,mod2] $0 <dbname> [test-tags] [-- <аргументи odoo-bin>]" >&2; exit 2; }
[[ $# -ge 1 ]] || usage
db="$1"; shift
tags=""
if [[ $# -gt 0 && "$1" != "--" ]]; then tags="$1"; shift; fi
if [[ $# -gt 0 ]]; then [[ "$1" == "--" ]] || usage; shift; fi
extra=("$@")

install="${F3D_TEST_INSTALL:-$(f3d_local_modules)}"
[[ -n "$install" ]] || f3d_die "нема що ставити: F3D_TEST_INSTALL не заданий і в $F3D_ADDONS_DIR немає модулів"
if [[ -z "$tags" ]]; then
    tags="/${install//,/,/}"
fi
timeout_s="${F3D_TEST_TIMEOUT:-3600}"
f3d_require_db_name "$db"
f3d_check_env
f3d_require_pg

f3d_lock_db "$db"
f3d_pick_port "$db"
port="$F3D_PORT"
t0=$(date +%s%N)
f3d_clone_db "$db"
t_clone=$(( ($(date +%s%N) - t0) / 1000000 ))
log="$ODOO_LOG_DIR/test-$db.log"
f3d_log "база $db з $F3D_TEMPLATE_DB за ${t_clone} мс; -i $install --test-tags $tags; http-port $port"
f3d_log "addons-path: $ODOO_ADDONS_PATH"
f3d_log "лог: $log"

cmd=(timeout --kill-after=30 "$timeout_s" "$ODOO_PY" "$ODOO_BIN" -c "$ODOO_CONF"
     --addons-path="$ODOO_ADDONS_PATH" -d "$db"
     -i "$install" --test-enable --test-tags "$tags" --stop-after-init --log-level=test
     --http-port="$port" "${extra[@]}")
t1=$(date +%s)
set +e
if [[ "${F3D_TEST_TEE:-0}" == "1" ]]; then
    "${cmd[@]}" 2>&1 | tee "$log"
    rc=${PIPESTATUS[0]}
else
    "${cmd[@]}" > "$log" 2>&1
    rc=$?
fi
set -e
elapsed=$(( $(date +%s) - t1 ))

final_rc=$rc
note=""
not_installed=""
if [[ $rc -eq 0 ]]; then
    for m in ${install//,/ }; do
        st="$(f3d_module_state "$db" "$m")"
        [[ "$st" == "installed" ]] || not_installed+=" $m(${st:-немає запису})"
    done
fi
if [[ $rc -eq 124 || $rc -eq 137 ]]; then
    final_rc=124; note="таймаут ${timeout_s} с (F3D_TEST_TIMEOUT)"
elif grep -qE "invalid module names, ignored: .*\b(${install//,/|})\b" "$log"; then
    final_rc=4; note="модуль не знайдено в addons_path ($F3D_ADDONS_DIR): немає каталогу з __manifest__.py"
elif [[ $rc -eq 0 && -n "$not_installed" ]]; then
    final_rc=4; note="не встановились:$not_installed"
elif [[ $rc -eq 0 ]] && f3d_log_has_errors "$log" && [[ "${F3D_TEST_STRICT:-1}" == "1" ]]; then
    final_rc=1; note="Odoo повернув 0, але в логу є ERROR/CRITICAL (F3D_TEST_STRICT=0 — не вважати помилкою)"
fi

echo "---- підсумок ($db, ${elapsed} с, код Odoo $rc)"
summary="$(grep -E 'odoo\.tests\.(result|stats)|Ran [0-9]+ tests|Starting post tests|[0-9]+ (failed|error)' "$log" \
           | sed -E 's/^[0-9-]+ [0-9:,]+ [0-9]+ //' | tail -n 15 || true)"
if [[ -n "$summary" ]]; then echo "$summary"; else echo "(рядків з підсумком тестів немає — тести не запускались?)"; fi

if f3d_log_has_errors "$log"; then
    echo "---- ERROR/CRITICAL (до 300 рядків)"
    f3d_log_errors "$log" 300
fi
if [[ $final_rc -ne 0 || -z "$summary" ]]; then
    echo "---- хвіст логу"
    tail -n 15 "$log"
fi
[[ -z "$note" ]] || echo "---- $note"

if [[ "${F3D_TEST_KEEP_DB:-1}" == "0" ]]; then
    f3d_drop_db "$db"
fi
if [[ $final_rc -eq 0 ]]; then
    echo "---- OK ($db). Відкрити в браузері: $F3D_TOOLS_DIR/serve.sh $db"
else
    echo "---- ПРОВАЛ, код $final_rc. Повний лог: $log"
fi
exit "$final_rc"
