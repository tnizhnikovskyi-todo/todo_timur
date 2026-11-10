#!/usr/bin/env bash
# Установка модулів у тестову базу. Використання:
#   install.sh <db> <module1,module2,...> [--update]
# За замовчуванням -i (install); з --update — -u (оновлення вже встановлених).
source "$(dirname "$0")/_common.sh"
DB="${1:-}"; MODS="${2:-}"; shift 2 || true
MODE="-i"
[[ "${1:-}" == "--update" ]] && MODE="-u"
guard_db "$DB"
[[ -n "$MODS" ]] || { echo "Не задано модулі" >&2; exit 2; }
validate_mods "$MODS"
odoo_args
LOG="$(mktemp)"; trap 'rm -f "$LOG"' EXIT
set +e
"$ODOO_BIN" ${ODOO_ARGS[@]+"${ODOO_ARGS[@]}"} -d "$DB" "$MODE" "$MODS" --stop-after-init --log-level=warn >"$LOG" 2>&1
RC=$?
set -e
grep -E " (ERROR|CRITICAL) |Traceback" -A 15 "$LOG" | head -60 || true
if [[ $RC -ne 0 ]] || grep -qE " (ERROR|CRITICAL) " "$LOG"; then echo "FAIL install: $MODS у $DB"; exit 1; fi
require_installed "$DB" "$MODS" || { echo "FAIL install: $MODS у $DB (не installed)"; exit 1; }
echo "OK install: $MODS у $DB"
