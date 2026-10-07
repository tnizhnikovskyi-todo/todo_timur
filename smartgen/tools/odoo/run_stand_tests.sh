#!/usr/bin/env bash
# Стендовые тесты td_genset со своим эмулятором ретранслятора (smartgen/tools/fake_relay.py).
#
#   run_stand_tests.sh <dbname> [test-tags] [-- <доп. аргументы odoo-bin>]
#
# test-tags по умолчанию td_genset_stand (SPEC: @tagged('post_install', '-at_install', '-standard',
# 'td_genset_stand')). Для каждого прогона поднимается СВОЙ fake_relay на свободном порту со случайным
# токеном (состояние /_sim у каждого своё — параллельные прогоны не мешают друг другу), затем
# run_tests.sh <dbname> <tags> с переменными окружения:
#   TD_GENSET_STAND_URL   = http://127.0.0.1:<port>/api/v1
#   TD_GENSET_STAND_TOKEN = <токен>
#   TD_GENSET_STAND_SIM   = http://127.0.0.1:<port>/_sim   (то же доступно как $TD_GENSET_STAND_URL/_sim)
# Эмулятор останавливается по завершении. Его лог: $ODOO_LOG_DIR/relay-<dbname>.log.
# Переменные: TD_STAND_SNAPSHOT_SEC (по умолчанию 2), TD_STAND_TIME_SCALE (1), TD_STAND_RELAY_ARGS (доп. аргументы).
set -euo pipefail
# shellcheck source=env.sh
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"

[[ $# -ge 1 ]] || { echo "Использование: $0 <dbname> [test-tags] [-- <аргументы odoo-bin>]" >&2; exit 2; }
db="$1"; shift
tags="td_genset_stand"
if [[ $# -gt 0 && "$1" != "--" ]]; then tags="$1"; shift; fi
td_require_db_name "$db"
td_check_env

relay_py="$TD_REPO_DIR/smartgen/tools/fake_relay.py"
[[ -f "$relay_py" ]] || td_die "нет эмулятора $relay_py"
port="$(td_free_port)"
token="stand-$(python3 -c 'import secrets; print(secrets.token_hex(12))')"
relay_log="$ODOO_LOG_DIR/relay-$db.log"
# shellcheck disable=SC2086
python3 "$relay_py" --port "$port" --token "$token" --snapshot-sec "${TD_STAND_SNAPSHOT_SEC:-2}" \
    --time-scale "${TD_STAND_TIME_SCALE:-1}" ${TD_STAND_RELAY_ARGS:-} > "$relay_log" 2>&1 &
relay_pid=$!
trap 'kill "$relay_pid" 2>/dev/null || true' EXIT
for _ in $(seq 1 50); do
    curl -s --noproxy '*' -o /dev/null --max-time 1 "http://127.0.0.1:$port/_sim" && break
    kill -0 "$relay_pid" 2>/dev/null || { cat "$relay_log" >&2; td_die "эмулятор не запустился"; }
    sleep 0.1
done
export TD_GENSET_STAND_URL="http://127.0.0.1:$port/api/v1"
export TD_GENSET_STAND_TOKEN="$token"
export TD_GENSET_STAND_SIM="http://127.0.0.1:$port/_sim"
td_log "эмулятор ретранслятора: $TD_GENSET_STAND_URL (pid $relay_pid, лог $relay_log)"
rc=0
"$TD_TOOLS_DIR/run_tests.sh" "$db" "$tags" "$@" || rc=$?
exit "$rc"
