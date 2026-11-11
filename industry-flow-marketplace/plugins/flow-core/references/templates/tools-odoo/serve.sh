#!/usr/bin/env bash
# Старт HTTP-сервера Odoo для зйомки A-21 (prototype-builder/run_all.sh). Використання:
#   [ODOO_EDITION=ce|ee] serve.sh <db> <port>      напр.: serve.sh demo-mebli 8069
# Працює у фоні викликача (run_all.sh запускає через nohup); лог пише викликач. Зупинка — kill процесу.
# Захист імені бази — guard_db (_common.sh). Параметри odoo-bin (--http-port, --addons-path, -c) — як в інших скриптах;
# C-00 звіряє з `odoo-bin --help` на реальному Odoo 19 (шаблон перевірявся лише на stub). --workers=0 і --no-database-list не змінювати
# без рішення C-00: зйомці потрібен один процес і прив'язка до однієї бази.
source "$(dirname "$0")/_common.sh"
DB="${1:-}"; PORT="${2:-}"
guard_db "$DB"
[[ "$PORT" =~ ^[0-9]{2,5}$ ]] || { echo "FLOW_STOP: потрібен <port> (число), отримано '$PORT'" >&2; exit 2; }
check_edition
odoo_args
exec "$ODOO_BIN" ${ODOO_ARGS[@]+"${ODOO_ARGS[@]}"} -d "$DB" --http-port="$PORT" --workers=0 --no-database-list
