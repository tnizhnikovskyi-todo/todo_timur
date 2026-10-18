#!/usr/bin/env bash
# Чистий стенд без docker: база f3d_access_stand (td_factory3d + td_access), Odoo на :18079, емулятор iot_sim
# (локальний запуск сервісу) на :8090/:8443/:8081. Секрети — лише в змінних середовища/тимчасовому каталозі.
#   reset_stand.sh up | down
# Потрібні: SIM_VENV (venv з requirements.txt сервісу), STAND_TMP (каталог для env/логів/стану емулятора).
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
T="$ROOT/factory3d/tools/odoo"
SVC="$ROOT/factory3d/services/iot_sim"
DB=${F3D_ODOO_DB:-f3d_access_stand}
PORT=${F3D_ODOO_PORT:-18079}
SIM_VENV=${SIM_VENV:?вкажіть SIM_VENV}
STAND_TMP=${STAND_TMP:?вкажіть STAND_TMP}
TOKEN=${SIM_API_TOKEN:?вкажіть SIM_API_TOKEN (>= 32 символи)}
BS_PASS=${SIM_BIOSTAR_PASS:?вкажіть SIM_BIOSTAR_PASS}

stop_pid() { [ -f "$STAND_TMP/$1.pid" ] && kill "$(cat "$STAND_TMP/$1.pid")" 2>/dev/null || true; rm -f "$STAND_TMP/$1.pid"; }
stop_sim() { stop_pid sim; stop_pid proxy; }

case "${1:-up}" in
down)
    stop_sim
    "$T/serve.sh" stop "$DB" || true
    ;;
up)
    mkdir -p "$STAND_TMP/state"
    stop_sim
    "$T/serve.sh" stop "$DB" || true
    "$T/drop_db.sh" "$DB" >/dev/null 2>&1 || true
    F3D_TEST_INSTALL=td_factory3d,td_access "$T/new_db.sh" "$DB"
    F3D_TEST_INSTALL=td_factory3d,td_access "$T/update.sh" "$DB"
    "$T/serve.sh" "$DB" "$PORT"
    rm -rf "$STAND_TMP/state"/* 2>/dev/null || true
    cd "$STAND_TMP"           # BioStar TLS-сертифікат (./certs) і знімок світу — поза репозиторієм
    (
        export SIM_API_TOKEN="$TOKEN" SIM_BIOSTAR_PASS="$BS_PASS" SIM_CATALOG_SOURCE=local SIM_MODE=follow_odoo
        export SIM_WOODSTORE_APIKEY=ws-key-stand-0123456789 SIM_JOBS_APIKEY=jobs-key-stand-0123456789
        export SIM_OPCUA_PASS=opcua-pass-stand SIM_LOG_LEVEL=DEBUG SIM_MQTT_URL= SIM_CATALOG_DIR="$SVC/catalog" SIM_STATE_DIR="$STAND_TMP/state"
        export SIM_ODOO_URL="http://127.0.0.1:$PORT" SIM_ODOO_DB="$DB" SIM_ODOO_USER=admin SIM_ODOO_APIKEY=admin
        PYTHONPATH="$SVC" nohup "$SIM_VENV/bin/python" -m iot_sim run > "$STAND_TMP/sim.log" 2>&1 &
        echo $! > "$STAND_TMP/sim.pid"
    )
    for _ in $(seq 60); do
        curl -fs "http://127.0.0.1:8090/sim/v1/health" >/dev/null 2>&1 && break
        sleep 1
    done
    # журналюючий TLS-проксі :18443 -> HTTP-порт емулятора (ТБ-08); Odoo ходить на https://127.0.0.1:18443
    for _ in $(seq 20); do [ -f "$STAND_TMP/certs/biostar.key" ] && break; sleep 1; done
    : > "$STAND_TMP/biostar-proxy.log"
    nohup "$SIM_VENV/bin/python" "$HERE/logging_proxy.py" "$STAND_TMP/certs/biostar.crt" "$STAND_TMP/certs/biostar.key" \
        "$STAND_TMP/biostar-proxy.log" 18443 > "$STAND_TMP/proxy.out" 2>&1 &
    echo $! > "$STAND_TMP/proxy.pid"
    echo "стенд піднято: Odoo :$PORT, емулятор :8090 (pid $(cat "$STAND_TMP/sim.pid")), лог $STAND_TMP/sim.log"
    ;;
esac
