#!/usr/bin/env bash
# Стенд телеметрії без docker build (процесний режим, DEPLOY_TEST «Середовище»): емулятор і колектор — процеси з їхніх .venv,
# MQTT-брокер — контейнер eclipse-mosquitto (--network host), Odoo — tools/odoo/serve.sh.
#   stand.sh up [db] | down [db] | collector-restart | seed [db]
# Імена iot-sim / mosquitto / collector додаються в /etc/hosts як 127.0.0.1 (колектор у BACnet слухає 127.0.0.2:47808,
# емулятор — 127.0.0.1:47808; інакше два UDP-сокети на одному порту не ужились би).
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COL="$(cd "$HERE/../.." && pwd)"
SVC="$(cd "$COL/.." && pwd)"
ROOT="$(cd "$SVC/../.." && pwd)"
T="$ROOT/factory3d/tools/odoo"
D="${F3D_STAND_DIR:-/tmp/f3dstand}"
DB="${2:-f3d_telemetry_w7}"
PORT="${F3D_STAND_ODOO_PORT:-18069}"
SIM_TOKEN="${SIM_API_TOKEN:-stand-token-0123456789abcdef0123456789}"
HTTP_SECRET=stand-lpr-secret-0123456789
cmd="${1:-}"

hosts() { grep -q "iot-sim mosquitto collector" /etc/hosts || echo "127.0.0.1 iot-sim mosquitto collector" >> /etc/hosts; }

mosquitto_up() {
    mkdir -p "$D"
    cp "$SVC/iot_sim/mosquitto/mosquitto.conf" "$D/m.conf"
    if [ ! -s "$D/passwd" ]; then
        : > "$D/passwd"
        docker run --rm -v "$D:/m" eclipse-mosquitto:2.0.20 sh -c \
          'mosquitto_passwd -b /m/passwd sim simpass && mosquitto_passwd -b /m/passwd collector collpass' >/dev/null 2>&1
        chmod 644 "$D/passwd"
    fi
    docker rm -f f3d-mosq >/dev/null 2>&1 || true
    docker run -d --name f3d-mosq --network host -v "$D/m.conf:/mosquitto/config/mosquitto.conf:ro" \
        -v "$D/passwd:/mosquitto/config/passwd:ro" eclipse-mosquitto:2.0.20 >/dev/null
}

sim_up() {
    pkill -f "python -m iot_sim" 2>/dev/null || true
    (cd "$SVC/iot_sim" && SIM_API_TOKEN="$SIM_TOKEN" SIM_MQTT_URL=mqtt://sim:simpass@mosquitto:1883 \
        SIM_MODE=scenario SIM_LOG_LEVEL=INFO SIM_LPR_PUSH_URL="http://collector:8080/f3d/lpr/$HTTP_SECRET" \
        SIM_BIOSTAR_PASS=bs-pass-stand SIM_WOODSTORE_APIKEY=ws-key-stand-0123456789 \
        SIM_JOBS_APIKEY=jobs-key-stand-0123456789 SIM_OPCUA_PASS=opcua-pass-stand \
        SIM_CATALOG_SOURCE=local SIM_OPCUA_CERT_DIR="$D/certs" \
        nohup .venv/bin/python -m iot_sim run > "$D/sim.log" 2>&1 &) >/dev/null 2>&1 </dev/null
    for _ in $(seq 40); do curl -sf http://127.0.0.1:8090/sim/v1/health >/dev/null && return; sleep 1; done
    echo "iot_sim не піднявся" >&2; exit 1
}

oshell() {      # Odoo shell: скрипт — зі stdin; друкуються лише рядки STAND / Traceback / Error
    (cd "$ROOT" && source "$T/env.sh" && "$ODOO_PY" "$ODOO_BIN" shell -c "$ODOO_CONF" --addons-path="$ODOO_ADDONS_PATH" \
        -d "$DB" --no-http --log-level=warn 2>&1 | grep -E "STAND|Traceback|Error" | head -40) || true
}

seed() { oshell < "$HERE/seed_odoo.py"; }

collector_up() {
    pkill -f "f3d-collector" 2>/dev/null || true
    mkdir -p "$D/state"
    local token
    token="$("$COL/.venv/bin/python" "$HERE/odoo_rpc.py" token)"
    (cd "$COL" && env -i PATH="$PATH" HOME="$HOME" F3D_ODOO_URL="http://127.0.0.1:$PORT" F3D_COLLECTOR_CODE=COL-MAIN \
        F3D_COLLECTOR_TOKEN="$token" F3D_ALLOW_HOSTS="${F3D_ALLOW_HOSTS:-iot-sim,mosquitto}" F3D_BUFFER_DIR="$D/state" \
        F3D_WRITE_ENABLED="${F3D_WRITE_ENABLED:-0}" F3D_BACNET_BIND=127.0.0.2:47808 \
        F3D_MQTT_PASSWORD=collpass F3D_HTTP_PUSH_SECRET_LPR="$HTTP_SECRET" F3D_LOG_LEVEL=INFO F3D_CONFIG_POLL_S=30 F3D_PUSH_INTERVAL_S=5 \
        ${F3D_EXTRA_ENV:-} nohup .venv/bin/f3d-collector run > "$D/collector.log" 2>&1 &) >/dev/null 2>&1 </dev/null
    echo "$token" > "$D/token"; chmod 600 "$D/token"
}

# одноразова команда CLI колектора (dump-config, test-source …) з тим самим середовищем, BACnet — з іншої адреси
cli() {
    (cd "$COL" && env -i PATH="$PATH" HOME="$HOME" F3D_ODOO_URL="http://127.0.0.1:$PORT" F3D_COLLECTOR_CODE=COL-MAIN \
        F3D_COLLECTOR_TOKEN="$(cat "$D/token")" F3D_ALLOW_HOSTS="${F3D_ALLOW_HOSTS:-iot-sim,mosquitto}" \
        F3D_BUFFER_DIR="$D/state-cli" F3D_BACNET_BIND=127.0.0.4:47808 F3D_MQTT_PASSWORD=collpass \
        F3D_HTTP_PUSH_SECRET_LPR="$HTTP_SECRET" F3D_LOG_LEVEL=DEBUG ./.venv/bin/f3d-collector "$@")
}

case "$cmd" in
    up)
        hosts; mosquitto_up; sim_up
        "$T/serve.sh" "$DB" "$PORT" | tail -n 1
        seed; collector_up
        echo "стенд піднято: Odoo :$PORT, iot_sim :8090, колектор /metrics :9108" ;;
    seed) seed ;;
    shell) DB="${F3D_SHELL_DB:-f3d_telemetry_w7}"; oshell ;;
    cli) shift; cli "$@" ;;
    collector-restart) collector_up ;;
    down)
        pkill -f "f3d-collector" 2>/dev/null || true
        pkill -f "python -m iot_sim" 2>/dev/null || true
        docker rm -f f3d-mosq >/dev/null 2>&1 || true
        "$T/serve.sh" stop "$DB" || true ;;
    *) echo "Використання: $0 up|down|seed|collector-restart [db]" >&2; exit 2 ;;
esac
