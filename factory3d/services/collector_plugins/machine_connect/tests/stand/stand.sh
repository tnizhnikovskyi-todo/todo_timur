#!/usr/bin/env bash
# Стенд machine_connect без Docker (DEC-15 telemetry): iot_sim і колектор — процеси на localhost, Odoo — tools/odoo/serve.sh.
#   stand.sh build              — бази: f3d_mc_pre (чиста + seed) → установка модуля (ТК-01 крок 2) → шаблон f3d_mc_t0
#   stand.sh up [db]            — копія шаблона f3d_mc_tk (або db), emulator, Odoo, колектор
#   stand.sh sim-restart | collector-restart | down | seed-pre | cli <args>
# Змінні: F3D_VENV_SIM (venv iot_sim), F3D_VENV_MC (venv колектора з пакетом, asyncua), F3D_STAND_DIR, F3D_WRITE_ENABLED.
# Імена iot-sim/odoo19 додаються в /etc/hosts як 127.0.0.1.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../../../../../.." && pwd)"
SVC="$ROOT/factory3d/services"
T="$ROOT/factory3d/tools/odoo"
D="${F3D_STAND_DIR:-/tmp/f3dmc}"
VSIM="${F3D_VENV_SIM:-/tmp/claude-0/venv_sim}"
VMC="${F3D_VENV_MC:-/tmp/claude-0/venv_mc}"
SEED=f3d_mc_seed   # чиста база + telemetry + seed_pre (DEPLOY_TEST п. 1–2), модуль ще не встановлено
PRE=f3d_mc_pre
T0=f3d_mc_t0
PORT="${F3D_STAND_ODOO_PORT:-18070}"
SIM_TOKEN="${SIM_API_TOKEN:-stand-token-0123456789abcdef0123456789}"
cmd="${1:-}"
DB="${2:-f3d_mc_tk}"

hosts() { grep -q "iot-sim" /etc/hosts || echo "127.0.0.1 iot-sim" >> /etc/hosts; }

sim_up() {
    pkill -f "python -m iot_sim" 2>/dev/null || true
    mkdir -p "$D"
    (cd "$SVC/iot_sim" && SIM_API_TOKEN="$SIM_TOKEN" SIM_MODE=scenario SIM_LOG_LEVEL=INFO SIM_BIOSTAR_PASS=bs-pass-stand \
        SIM_WOODSTORE_APIKEY=ws-key-stand-0123456789 SIM_JOBS_APIKEY=jobs-key-stand-0123456789 \
        SIM_OPCUA_PASS=opcua-pass-stand SIM_CATALOG_SOURCE=local SIM_OPCUA_CERT_DIR="$D/certs" \
        nohup "$VSIM/bin/python" -m iot_sim run > "$D/sim.log" 2>&1 &) >/dev/null 2>&1 </dev/null
    for _ in $(seq 40); do curl -sf http://127.0.0.1:8090/sim/v1/health >/dev/null && return; sleep 1; done
    echo "iot_sim не піднявся" >&2; exit 1
}

oshell() {      # Odoo shell: скрипт — зі stdin; друкуються лише рядки STAND / Traceback / Error
    (cd "$ROOT" && source "$T/env.sh" && "$ODOO_PY" "$ODOO_BIN" shell -c "$ODOO_CONF" --addons-path="$ODOO_ADDONS_PATH" \
        -d "$1" --no-http --log-level=warn 2>&1 | grep -E "STAND|Traceback|Error" | head -40) || true
}

collector_down() {   # дочекатись звільнення порту метрик (інакше новий процес падає: address already in use)
    pkill -f "f3d-collector" 2>/dev/null || true
    for _ in $(seq 20); do pgrep -f "bin/f3d-collector run" >/dev/null || return 0; sleep 0.5; done
    pkill -9 -f "bin/f3d-collector run" 2>/dev/null || true; sleep 1
}

collector_up() {
    collector_down
    mkdir -p "$D/state"
    local token
    token="$("$VMC/bin/python" "$HERE/odoo_rpc.py" token)"
    local -a E=(PATH="$PATH" HOME="$HOME" F3D_ODOO_URL="http://127.0.0.1:$PORT" F3D_COLLECTOR_CODE=COL-MAIN
        F3D_COLLECTOR_TOKEN="$token" F3D_ALLOW_HOSTS="${F3D_ALLOW_HOSTS:-iot-sim,odoo19}" F3D_BUFFER_DIR="$D/state"
        F3D_MC_STATE_DIR="$D/state" F3D_OPCUA_PASSWORD=opcua-pass-stand F3D_WOODSTORE_KEY=ws-key-stand-0123456789
        F3D_CUTOPT_KEY=jobs-key-stand-0123456789 F3D_WRITE_ENABLED="${F3D_WRITE_ENABLED:-0}"
        F3D_LOG_LEVEL="${F3D_LOG_LEVEL:-INFO}" F3D_CONFIG_POLL_S=30 F3D_PUSH_INTERVAL_S=5)
    local -a F=()
    for kv in "${E[@]}"; do [ "${kv%%=*}" = "${F3D_STAND_UNSET:-}" ] || F+=("$kv"); done   # F3D_STAND_UNSET — змінна, яку не задавати (ТБ-08)
    (cd "$SVC/collector" && env -i "${F[@]}" ${F3D_EXTRA_ENV:-} nohup "$VMC/bin/f3d-collector" run > "$D/collector.log" 2>&1 &) >/dev/null 2>&1 </dev/null
    echo "$token" > "$D/token"; chmod 600 "$D/token"
}

case "$cmd" in
    build)
        hosts; "$T/pg.sh" start >/dev/null 2>&1 || true
        sim_up
        "$T/serve.sh" stop all >/dev/null 2>&1 || true
        "$T/new_db.sh" "$SEED" >/dev/null
        F3D_TEST_INSTALL=td_telemetry "$T/update.sh" "$SEED" | tail -n 2
        oshell "$SEED" < "$HERE/seed_pre.py"
        source "$T/env.sh"
        "$T/drop_db.sh" "$PRE" >/dev/null 2>&1 || true
        createdb -h localhost -U odoo -T "$SEED" "$PRE"
        # установка модуля в копію (ТК-01 повторює її з знімками S0–S5 на свіжій копії $SEED)
        F3D_TEST_INSTALL=td_machine_connect "$T/update.sh" "$PRE" | tail -n 2
        echo "база $PRE готова (установлено); шаблон $T0 — stand.sh template" ;;
    template)
        source "$T/env.sh"
        "$T/drop_db.sh" "$T0" >/dev/null 2>&1 || true
        createdb -h localhost -U odoo -T "$PRE" "$T0" && echo "шаблон $T0 створено" ;;
    fresh)          # fresh [seed|t0] [db]: свіжа копія шаблона (DEPLOY_TEST п. 3), без запуску серверів
        source "$T/env.sh"
        src="$T0"; [ "${2:-t0}" = seed ] && src="$SEED"
        DB="${3:-f3d_mc_tk}"
        collector_down
        "$T/serve.sh" stop "$DB" >/dev/null 2>&1 || true
        "$T/drop_db.sh" --force "$DB" >/dev/null 2>&1 || true
        createdb -h localhost -U odoo -T "$src" "$DB" && echo "база $DB ← $src" ;;
    install)        # установка модуля в базу (ТК-01 крок 2)
        F3D_TEST_INSTALL=td_machine_connect "$T/update.sh" "${2:-f3d_mc_tk}" | tail -n 2 ;;
    serve)          # Odoo + колектор на базі db (емулятор — якщо не піднятий)
        hosts
        DB="${2:-f3d_mc_tk}"
        curl -sf http://127.0.0.1:8090/sim/v1/health >/dev/null || sim_up
        "$0" odoo-start "$DB"
        collector_up
        echo "стенд піднято: Odoo :$PORT ($DB), iot_sim :8090, колектор /metrics :9108" ;;
    up) "$0" fresh t0 "$DB" && "$0" serve "$DB" ;;
    seed-pre) oshell "$SEED" < "$HERE/seed_pre.py" ;;
    sim-restart) sim_up ;;
    collector-stop) collector_down ;;
    collector-restart) collector_up ;;
    odoo-stop) "$T/serve.sh" stop "$DB" ;;
    odoo-start)     # порт після зупинки Odoo ще до хвилини в TIME_WAIT (serve.sh перевіряє bind без SO_REUSEADDR) — повторюємо
        for _ in $(seq 40); do
            out="$("$T/serve.sh" "$DB" "$PORT" 2>&1 | tail -n 1)" || true
            case "$out" in *зайнят*) sleep 3 ;; *) echo "$out"; break ;; esac
        done ;;
    down)
        pkill -f "f3d-collector" 2>/dev/null || true
        pkill -f "python -m iot_sim" 2>/dev/null || true
        "$T/serve.sh" stop "$DB" || true ;;
    *) echo "Використання: $0 build|template|fresh|install|serve|up|down|collector-stop|seed-pre|collector-restart|sim-restart|odoo-stop|odoo-start" >&2; exit 2 ;;
esac
