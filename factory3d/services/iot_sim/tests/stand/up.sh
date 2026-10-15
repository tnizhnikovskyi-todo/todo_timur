#!/usr/bin/env bash
# Підняти стенд (профіль dev, без genset_relay — запасний режим §8.14). Запуск: tests/stand/up.sh [extra env KEY=VAL...]
set -euo pipefail
cd "$(dirname "$0")/../.."
TOKEN=${SIM_API_TOKEN:-stand-token-0123456789abcdef0123456789}
[ -f .env ] || cat > .env <<EOT
SIM_API_TOKEN=$TOKEN
SIM_CATALOG_SOURCE=local
SIM_MODE=scenario
SIM_MQTT_URL=mqtt://sim:simpass@mosquitto:1883
SIM_BIOSTAR_PASS=bs-pass-stand
SIM_WOODSTORE_APIKEY=ws-key-stand-0123456789
SIM_JOBS_APIKEY=jobs-key-stand-0123456789
SIM_OPCUA_PASS=opcua-pass-stand
SIM_LOG_LEVEL=DEBUG
RELAY_SIM_TOKEN=relay-token-0123456789abcdef012345
EOT
[ -f mosquitto/passwd ] || docker run --rm -v "$PWD/mosquitto:/m" eclipse-mosquitto:2.0.20 sh -c 'touch /m/passwd && mosquitto_passwd -b /m/passwd sim simpass && chmod 644 /m/passwd'
docker network inspect odoo_default >/dev/null 2>&1 || docker network create odoo_default >/dev/null
docker compose -f docker-compose.sim.yml --profile dev up -d --build iot_sim mosquitto
