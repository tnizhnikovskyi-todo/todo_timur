#!/usr/bin/env bash
# Прогнать тесты модуля на свежей копии шаблона.
#
#   run_tests.sh <dbname> [test-tags] [-- <доп. аргументы odoo-bin>]
#
#   test-tags по умолчанию /td_genset; примеры: /td_genset:TestRelayClient, /td_genset:TestX.test_y,
#   td_genset_tour (по тегу), -at_install (исключить).
#
# Что делает: удаляет базу <dbname>, если есть, → createdb -T td_template (+ копия filestore) →
#   odoo-bin -c $ODOO_CONF -d <dbname> -i td_genset --test-enable --test-tags <tags>
#            --stop-after-init --log-level=test --http-port=<свободный порт>
# Полный лог: $ODOO_LOG_DIR/test-<dbname>.log (перезаписывается при следующем прогоне с тем же именем).
# Печатает итог тестов, записи ERROR/CRITICAL с трейсбеками и хвост лога.
#
# Параллельные прогоны безопасны, если у них разные <dbname>: своя база, свой лог,
# свой HTTP-порт (HttpCase ходит на http_port — общий 8069 смешал бы прогоны).
#
# Код выхода: код Odoo (0 — всё прошло); 1 — Odoo вернул 0, но в логе есть ERROR/CRITICAL
# (TD_TEST_STRICT=0 отключает); 4 — модуль не найден или не установился; 124 — таймаут.
#
# Переменные: TD_TEST_TIMEOUT (с, по умолчанию 3600), TD_TEST_TEE=1 — дублировать лог в консоль,
#   TD_TEST_KEEP_DB=0 — удалить базу после прогона (по умолчанию остаётся: её можно открыть
#   через serve.sh), TD_TEST_INSTALL — что ставить через -i (по умолчанию td_genset).
set -euo pipefail
# shellcheck source=env.sh
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"

usage() { echo "Использование: $0 <dbname> [test-tags] [-- <аргументы odoo-bin>]" >&2; exit 2; }
[[ $# -ge 1 ]] || usage
db="$1"; shift
tags="/$TD_MODULE"
if [[ $# -gt 0 && "$1" != "--" ]]; then tags="$1"; shift; fi
if [[ $# -gt 0 ]]; then [[ "$1" == "--" ]] || usage; shift; fi
extra=("$@")

install="${TD_TEST_INSTALL:-$TD_MODULE}"
timeout_s="${TD_TEST_TIMEOUT:-3600}"
td_require_db_name "$db"
td_check_env
td_require_pg

t0=$(date +%s%N)
td_clone_db "$db"
t_clone=$(( ($(date +%s%N) - t0) / 1000000 ))
port="$(td_free_port)"
log="$ODOO_LOG_DIR/test-$db.log"
td_log "база $db из $TD_TEMPLATE_DB за ${t_clone} мс; -i $install --test-tags $tags; http-port $port"
td_log "лог: $log"

cmd=(timeout --kill-after=30 "$timeout_s" "$ODOO_PY" "$ODOO_BIN" -c "$ODOO_CONF" -d "$db"
     -i "$install" --test-enable --test-tags "$tags" --stop-after-init --log-level=test
     --http-port="$port" "${extra[@]}")
t1=$(date +%s)
set +e
if [[ "${TD_TEST_TEE:-0}" == "1" ]]; then
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
if [[ $rc -eq 124 || $rc -eq 137 ]]; then
    final_rc=124; note="таймаут ${timeout_s} с (TD_TEST_TIMEOUT)"
elif grep -qE "invalid module names, ignored: .*\b(${install//,/|})\b" "$log"; then
    final_rc=4; note="модуль не найден в addons_path ($TD_ADDONS_DIR): нет каталога с __manifest__.py"
elif [[ $rc -eq 0 && "$install" == "$TD_MODULE" && "$(td_module_state "$db" "$TD_MODULE")" != "installed" ]]; then
    final_rc=4; note="модуль $TD_MODULE не установился (state: $(td_module_state "$db" "$TD_MODULE"))"
elif [[ $rc -eq 0 ]] && td_log_has_errors "$log" && [[ "${TD_TEST_STRICT:-1}" == "1" ]]; then
    final_rc=1; note="Odoo вернул 0, но в логе есть ERROR/CRITICAL (TD_TEST_STRICT=0 — не считать ошибкой)"
fi

echo "---- итог ($db, ${elapsed} с, код Odoo $rc)"
summary="$(grep -E 'odoo\.tests\.(result|stats)|Ran [0-9]+ tests|Starting post tests|[0-9]+ (failed|error)' "$log" \
           | sed -E 's/^[0-9-]+ [0-9:,]+ [0-9]+ //' | tail -n 15 || true)"
if [[ -n "$summary" ]]; then echo "$summary"; else echo "(строк с итогом тестов нет — тесты не запускались?)"; fi

if td_log_has_errors "$log"; then
    echo "---- ERROR/CRITICAL (до 300 строк)"
    td_log_errors "$log" 300
fi
if [[ $final_rc -ne 0 ]]; then
    echo "---- хвост лога"
    tail -n 25 "$log"
fi
[[ -z "$note" ]] || echo "---- $note"

if [[ "${TD_TEST_KEEP_DB:-1}" == "0" ]]; then
    td_drop_db "$db"
fi
if [[ $final_rc -eq 0 ]]; then
    echo "---- OK ($db). Открыть в браузере: $TD_TOOLS_DIR/serve.sh $db"
else
    echo "---- ПРОВАЛ, код $final_rc. Полный лог: $log"
fi
exit "$final_rc"
