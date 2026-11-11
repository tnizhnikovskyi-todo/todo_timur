#!/usr/bin/env bash
# Тести модуля. Використання:
#   [ODOO_EDITION=ce|ee] run_tests.sh <db> <module> [test-tags]     напр.: run_tests.sh test-pkg-x my_module /my_module:TestClass
# Редакція (К-06): ce за замовчуванням; ee — ODOO_EE_ADDONS_PATH; без доступу до EE — код 3 і "WARN ee-unavailable" (НЕ PASS, НЕ FAIL).
# Друкує рядок "EDITION: ce|ee" окремо від "RESULT:" (формат RESULT не змінено).
# <module> — ім'я модуля для `-u` (^[a-z0-9_]+$, має бути installed у базі). [test-tags] — значення --test-tags Odoo,
# за замовчуванням "/<module>". Інші форми тегів C-00 перевіряє на реальному Odoo 19.
# Друкує лише підсумок і помилки; повний лог у контекст не виводиться.
# Код виходу: 0 — PASS; 1 — FAIL (ERROR/FAIL/CRITICAL, ненульовий код Odoo АБО тести не запускались / їх 0).
# Формат для ci-pipeline-builder: рядок "RESULT: PASS|FAIL <db> <module> <tags>" (FAIL з "(no tests ran)", якщо тестів не було).
# ВІДКРИТЕ ПИТАННЯ C-00: точний текст рядка підсумку тестів в логу Odoo 19 і лічильник skipped не звірені;
# Якщо на реальному Odoo 19 завжди виходить "(no tests ran)", C-00 звіряє рівень логу (--log-level=test чи info) разом із TESTS_SUMMARY_RE; опцію не вгадувати.
# TESTS_SUMMARY_RE нижче — припущення (рядок з числом "N tests"), звірити й виправити за реальним логом.
source "$(dirname "$0")/_common.sh"
DB="${1:-}"; MOD="${2:-}"; TAGS="${3:-/$MOD}"
guard_db "$DB"
check_edition
echo "EDITION: $ODOO_EDITION"
[[ "$MOD" =~ ^[a-z0-9_]+$ ]] || { echo "FLOW_STOP: потрібен <module> (^[a-z0-9_]+\$), отримано '$MOD'" >&2; exit 2; }
[[ "$TAGS" =~ ^[-+A-Za-z0-9_:./,@]+$ ]] || { echo "FLOW_STOP: недопустимі test-tags '$TAGS'" >&2; exit 2; }
TESTS_SUMMARY_RE="${TESTS_SUMMARY_RE:-[0-9]+ tests}"
require_installed "$DB" "$MOD" || { echo "RESULT: FAIL $DB $MOD $TAGS (module not installed)"; exit 1; }
odoo_args
LOG="$(mktemp)"; trap 'rm -f "$LOG"' EXIT
set +e
"$ODOO_BIN" ${ODOO_ARGS[@]+"${ODOO_ARGS[@]}"} -d "$DB" -u "$MOD" --test-enable --test-tags "$TAGS" --stop-after-init --log-level=test >"$LOG" 2>&1
RC=$?
set -e
grep -E " (ERROR|CRITICAL) |FAIL:|Traceback" -A 15 "$LOG" | head -80 || true
SUMMARY="$(grep -E "$TESTS_SUMMARY_RE" "$LOG" | tail -3 || true)"
[[ -z "$SUMMARY" ]] || echo "$SUMMARY"
if [[ $RC -ne 0 ]] || grep -qE " (ERROR|CRITICAL) |FAIL:" "$LOG"; then echo "RESULT: FAIL $DB $MOD $TAGS"; exit 1; fi
N="$({ echo "$SUMMARY" | grep -oE '[0-9]+ tests' || true; } | awk '{s+=$1} END{print s+0}')"
if [[ -z "$SUMMARY" || "$N" -le 0 ]]; then echo "RESULT: FAIL $DB $MOD $TAGS (no tests ran)"; exit 1; fi
echo "RESULT: PASS $DB $MOD $TAGS"
