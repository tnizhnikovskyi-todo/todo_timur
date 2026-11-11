#!/usr/bin/env bash
# Мінімальний smoke: база існує, модулі завантажуються без ERROR. Використання:
#   smoke.sh <db> <module1,module2,...>
# Бізнес-сценарії (створення документів тощо) реалізує C-00 під конкретний пакет.
source "$(dirname "$0")/_common.sh"
DB="${1:-}"; MODS="${2:-}"
guard_db "$DB"
check_edition
[[ -n "$MODS" ]] || { echo "Не задано модулі" >&2; exit 2; }
psql -d "$DB" -Atc "select 1" >/dev/null || { echo "FAIL smoke: немає доступу до бази $DB"; exit 1; }
require_installed "$DB" "$MODS" || { echo "FAIL smoke: модулі не installed у $DB"; exit 1; }
odoo_args
LOG="$(mktemp)"; trap 'rm -f "$LOG"' EXIT
set +e
"$ODOO_BIN" ${ODOO_ARGS[@]+"${ODOO_ARGS[@]}"} -d "$DB" -u "$MODS" --stop-after-init --log-level=warn >"$LOG" 2>&1
RC=$?
set -e
grep -E " (ERROR|CRITICAL) |Traceback" -A 15 "$LOG" | head -60 || true
if [[ $RC -ne 0 ]] || grep -qE " (ERROR|CRITICAL) " "$LOG"; then echo "FAIL smoke: $DB"; exit 1; fi
require_installed "$DB" "$MODS" || { echo "FAIL smoke: $DB (не installed)"; exit 1; }
echo "OK smoke: $DB ($MODS)"
