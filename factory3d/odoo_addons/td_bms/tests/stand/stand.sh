#!/usr/bin/env bash
# Стенд td_bms (SPEC §13.2) у процесному режимі без docker build: iot_sim і колектор — процеси з venv
# ($F3D_VENVS/{iot_sim,collector}; колектор з плагінами f3d-collector-bms/yard), MQTT-брокер — eclipse-mosquitto
# у docker, а якщо образ недоступний — amqtt з $F3D_VENVS/broker (pip install amqtt). Odoo — tools/odoo/serve.sh.
#   stand.sh up [db] | down [db] | collector-restart | seed [db] | token
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../../../../.." && pwd)"
SVC="$ROOT/factory3d/services"
T="$ROOT/factory3d/tools/odoo"
V="${F3D_VENVS:-/tmp/f3dvenv}"
D="${F3D_STAND_DIR:-/tmp/f3dstand}"
DB="${2:-f3d_factory3d_bms_w7}"
PORT="${F3D_STAND_ODOO_PORT:-18070}"
SIM_TOKEN="${SIM_API_TOKEN:-stand-token-0123456789abcdef0123456789}"
HTTP_SECRET=stand-lpr-secret-0123456789
cmd="${1:-}"

hosts() { grep -q "iot-sim mosquitto collector" /etc/hosts || echo "127.0.0.1 iot-sim mosquitto collector" >> /etc/hosts; }

mosquitto_up() {
    mkdir -p "$D"
    pkill -f "[a]mqtt" 2>/dev/null || true
    docker rm -f f3d-mosq >/dev/null 2>&1 || true
    if docker image inspect eclipse-mosquitto:2.0.20 >/dev/null 2>&1; then
        cp "$SVC/iot_sim/mosquitto/mosquitto.conf" "$D/m.conf"
        [ -s "$D/passwd" ] || { : > "$D/passwd"; docker run --rm -v "$D:/m" eclipse-mosquitto:2.0.20 sh -c \
            'mosquitto_passwd -b /m/passwd sim simpass && mosquitto_passwd -b /m/passwd collector collpass' >/dev/null 2>&1; chmod 644 "$D/passwd"; }
        docker run -d --name f3d-mosq --network host -v "$D/m.conf:/mosquitto/config/mosquitto.conf:ro" \
            -v "$D/passwd:/mosquitto/config/passwd:ro" eclipse-mosquitto:2.0.20 >/dev/null
    else   # запасний брокер: amqtt, анонімний доступ (лише для стенда)
        printf 'listeners:\n  default:\n    type: tcp\n    bind: 127.0.0.1:1883\nauth:\n  allow-anonymous: true\n' > "$D/amqtt.yaml"
        (nohup "$V/broker/bin/amqtt" -c "$D/amqtt.yaml" > "$D/broker.log" 2>&1 &) >/dev/null 2>&1 </dev/null
        sleep 3
    fi
}

sim_up() {
    pkill -f "[p]ython -m iot_sim" 2>/dev/null || true
    (cd "$SVC/iot_sim" && SIM_API_TOKEN="$SIM_TOKEN" SIM_MQTT_URL=mqtt://sim:simpass@mosquitto:1883 \
        SIM_MODE=scenario SIM_LOG_LEVEL=INFO SIM_LPR_PUSH_URL="http://collector:8080/f3d/lpr/$HTTP_SECRET" \
        SIM_BIOSTAR_PASS=bs-pass-stand SIM_WOODSTORE_APIKEY=ws-key-stand-0123456789 \
        SIM_JOBS_APIKEY=jobs-key-stand-0123456789 SIM_OPCUA_PASS=opcua-pass-stand \
        SIM_CATALOG_SOURCE=local SIM_OPCUA_CERT_DIR="$D/certs" \
        nohup "$V/iot_sim/bin/python" -m iot_sim run > "$D/sim.log" 2>&1 &) >/dev/null 2>&1 </dev/null
    for _ in $(seq 60); do curl -sf http://127.0.0.1:8090/sim/v1/health >/dev/null && return; sleep 1; done
    echo "iot_sim не піднявся" >&2; exit 1
}

oshell() {
    (cd "$ROOT" && source "$T/env.sh" && "$ODOO_PY" "$ODOO_BIN" shell -c "$ODOO_CONF" --addons-path="$ODOO_ADDONS_PATH" \
        -d "$DB" --no-http --log-level=warn 2>&1 | grep -E "STAND|Traceback|Error" | head -40) || true
}
seed() { oshell < "$HERE/seed_odoo.py"; }
rpc() { F3D_STAND_ODOO_URL="http://127.0.0.1:$PORT" F3D_STAND_ODOO_DB="$DB" "$V/collector/bin/python" "$SVC/collector/tests/stand/odoo_rpc.py" "$@"; }

collector_up() {
    pkill -f "[f]3d-collector" 2>/dev/null || true
    mkdir -p "$D/state"
    local token; token="$(rpc token)"
    (cd "$SVC/collector" && env -i PATH="$PATH" HOME="$HOME" F3D_ODOO_URL="http://127.0.0.1:$PORT" F3D_COLLECTOR_CODE=COL-MAIN \
        F3D_COLLECTOR_TOKEN="$token" F3D_ALLOW_HOSTS="${F3D_ALLOW_HOSTS:-iot-sim,mosquitto}" F3D_BUFFER_DIR="$D/state" \
        F3D_WRITE_ENABLED="${F3D_WRITE_ENABLED:-0}" F3D_BACNET_BIND=127.0.0.2:47808 \
        F3D_MQTT_PASSWORD=collpass F3D_HTTP_PUSH_SECRET_LPR="$HTTP_SECRET" F3D_LOG_LEVEL="${F3D_LOG_LEVEL:-INFO}" \
        F3D_CONFIG_POLL_S=30 F3D_PUSH_INTERVAL_S=5 ${F3D_EXTRA_ENV:-} \
        nohup "$V/collector/bin/f3d-collector" run > "$D/collector.log" 2>&1 &) >/dev/null 2>&1 </dev/null
    echo "$token" > "$D/token"; chmod 600 "$D/token"
}

case "$cmd" in
    up) hosts; mosquitto_up; sim_up; "$T/serve.sh" "$DB" "$PORT" | tail -n 1; seed; collector_up
        echo "стенд піднято: Odoo :$PORT, iot_sim :8090, колектор /metrics :9108" ;;
    seed) seed ;;
    shell) oshell ;;   # odoo shell: скрипт зі stdin, друкуються лише рядки STAND/Traceback/Error
    token) rpc token ;;
    collector-restart) collector_up ;;
    down) pkill -f "[f]3d-collector" 2>/dev/null || true; pkill -f "[p]ython -m iot_sim" 2>/dev/null || true
        pkill -f "[a]mqtt" 2>/dev/null || true; docker rm -f f3d-mosq >/dev/null 2>&1 || true
        "$T/serve.sh" stop "$DB" || true ;;
    *) echo "Використання: $0 up|down|seed|shell|token|collector-restart [db]" >&2; exit 2 ;;
esac
