#!/usr/bin/env bash
# Чистий стенд без docker: база f3d_energy_stand (td_energy + залежності), Odoo на :18079, емулятор iot_sim
# (локальний запуск) :8090/:502, колектор telemetry (COL-MAIN). Секрети — лише в змінних середовища.
#   reset_stand.sh up | down
# Потрібні: SIM_VENV (venv: `pip install -r services/iot_sim/requirements.txt -r services/collector/requirements.txt`
# і `pip install -e services/collector --no-deps` — без нього плагіни колектора (modbus_tcp…) не знаходяться),
# STAND_TMP (каталог для стану/логів), SIM_API_TOKEN і F3D_COLLECTOR_TOKEN (>= 32 символи, лише в середовищі).
# Модбас-джерела енергетики мають host=iot-sim, порт 502: у /etc/hosts додається «127.0.0.1 iot-sim».
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
T="$ROOT/factory3d/tools/odoo"
SIMSVC="$ROOT/factory3d/services/iot_sim"
COLSVC="$ROOT/factory3d/services/collector"
DB=${F3D_ODOO_DB:-f3d_energy_stand}
PORT=${F3D_ODOO_PORT:-18079}
SIM_VENV=${SIM_VENV:?вкажіть SIM_VENV}
STAND_TMP=${STAND_TMP:?вкажіть STAND_TMP}
TOKEN=${SIM_API_TOKEN:?вкажіть SIM_API_TOKEN (>= 32 символи)}
COL_TOKEN=${F3D_COLLECTOR_TOKEN:?вкажіть F3D_COLLECTOR_TOKEN (>= 32 символи)}

stop_pid() { [ -f "$STAND_TMP/$1.pid" ] && kill "$(cat "$STAND_TMP/$1.pid")" 2>/dev/null || true; rm -f "$STAND_TMP/$1.pid"; }

case "${1:-up}" in
down)
    stop_pid collector; stop_pid sim
    "$T/serve.sh" stop "$DB" || true
    ;;
up)
    mkdir -p "$STAND_TMP/state" "$STAND_TMP/collector"
    stop_pid collector; stop_pid sim
    "$T/serve.sh" stop "$DB" || true
    "$T/drop_db.sh" "$DB" >/dev/null 2>&1 || true
    F3D_TEST_INSTALL=td_energy "$T/new_db.sh" "$DB"
    F3D_TEST_INSTALL=td_energy "$T/update.sh" "$DB"
    "$T/serve.sh" "$DB" "$PORT"
    grep -q ' iot-sim$' /etc/hosts || echo "127.0.0.1 iot-sim" >> /etc/hosts
    # токен колектора COL-MAIN: у Odoo зберігається лише SHA-256
    HASH=$(printf '%s' "$COL_TOKEN" | sha256sum | cut -d' ' -f1)
    PGHOST=${PGHOST:-127.0.0.1} psql -U "${PGUSER:-odoo}" "$DB" -qc \
        "UPDATE td_collector SET token_hash='$HASH', token_hint=right('$COL_TOKEN',4) WHERE code='COL-MAIN'"
    rm -rf "$STAND_TMP/state"/* "$STAND_TMP/collector"/* 2>/dev/null || true
    (
        cd "$STAND_TMP"
        export SIM_API_TOKEN="$TOKEN" SIM_CATALOG_SOURCE=local SIM_MODE=scenario SIM_LOG_LEVEL=INFO SIM_MQTT_URL=
        export SIM_BIOSTAR_PASS=stand-biostar-pass SIM_WOODSTORE_APIKEY=ws-key-stand-0123456789
        export SIM_JOBS_APIKEY=jobs-key-stand-0123456789 SIM_OPCUA_PASS=opcua-pass-stand
        export SIM_CATALOG_DIR="$SIMSVC/catalog" SIM_STATE_DIR="$STAND_TMP/state"
        export SIM_ODOO_URL="http://127.0.0.1:$PORT" SIM_ODOO_DB="$DB" SIM_ODOO_USER=admin SIM_ODOO_APIKEY=admin
        PYTHONPATH="$SIMSVC" nohup "$SIM_VENV/bin/python" -m iot_sim run > "$STAND_TMP/sim.log" 2>&1 &
        echo $! > "$STAND_TMP/sim.pid"
    )
    for _ in $(seq 60); do curl -fs "http://127.0.0.1:8090/sim/v1/health" >/dev/null 2>&1 && break; sleep 1; done
    (
        cd "$STAND_TMP/collector"
        export F3D_ODOO_URL="http://127.0.0.1:$PORT" F3D_COLLECTOR_CODE=COL-MAIN F3D_COLLECTOR_TOKEN="$COL_TOKEN"
        export F3D_ALLOW_HOSTS="iot-sim,127.0.0.1" F3D_BUFFER_DIR="$STAND_TMP/collector" F3D_LOG_JSON=0
        export F3D_CONFIG_POLL_S=30 F3D_METRICS_PORT=19108 F3D_HTTP_PUSH_PORT=18080
        PYTHONPATH="$COLSVC" nohup "$SIM_VENV/bin/python" -m collector run > "$STAND_TMP/collector.log" 2>&1 &
        echo $! > "$STAND_TMP/collector.pid"
    )
    echo "стенд піднято: Odoo :$PORT, емулятор :8090 (sim.log), колектор (collector.log) у $STAND_TMP"
    ;;
esac
