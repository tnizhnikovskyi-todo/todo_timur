#!/usr/bin/env bash
# Самопідписаний сертифікат OPC UA сервера (SPEC §8.3.1): certs/server.der + server.key.
set -euo pipefail
DIR="${1:-${SIM_OPCUA_CERT_DIR:-./certs}}"
mkdir -p "$DIR"
openssl req -x509 -newkey rsa:2048 -nodes -days 3650 -keyout "$DIR/server.key" \
  -out "$DIR/server.pem" -subj "/O=todo.ltd/CN=iot_sim" \
  -addext "subjectAltName=URI:urn:todo.ltd:f3d:iot_sim,DNS:iot-sim,DNS:localhost" \
  -addext "keyUsage=digitalSignature,keyEncipherment,dataEncipherment,keyCertSign" \
  -addext "extendedKeyUsage=serverAuth,clientAuth" 2>/dev/null
openssl x509 -in "$DIR/server.pem" -outform der -out "$DIR/server.der"
chmod 600 "$DIR/server.key"
echo "OK: $DIR/server.der, $DIR/server.key"
