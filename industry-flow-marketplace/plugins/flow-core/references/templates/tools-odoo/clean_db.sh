#!/usr/bin/env bash
# Чиста база Odoo для перевірки пакета. Використання:
#   PKG_REPO=<шлях до репо пакета> clean_db.sh <db> [--tag <git-тег-пакета>] [--demo]
# Створює базу з нуля (dropdb + createdb), ініціалізує base (-i base).
# --tag: лише перевіряє, що HEAD репо $PKG_REPO збігається з тегом (перемикання робить C-00/CI); без репо/тегу — FLOW_STOP.
# ДЕМО-ДАНІ — ВІДКРИТЕ ПИТАННЯ C-00: у Odoo 19 опції демо-даних (`--with-demo`/`--without-demo`, їх форма й значення
# за замовчуванням) не звірені з `odoo-bin --help`. Тому скрипт сам нічого не вигадує: опції беруться зі змінних
# ODOO_DEMO_OPT (для --demo) і ODOO_NODEMO_OPT (без --demo), які задає C-00; якщо порожні — друкується WARN.
# Передумови: PostgreSQL-клієнти (createdb/dropdb), ODOO_BIN, ODOO_ADDONS_PATH, bash >= 4.4; див. README.md.
source "$(dirname "$0")/_common.sh"
DB="${1:-}"; shift || true
TAG=""; DEMO=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --tag) TAG="${2:?--tag потребує значення}"; shift 2 ;;
    --demo) DEMO=1; shift ;;
    *) echo "Невідомий параметр: $1" >&2; exit 2 ;;
  esac
done
guard_db "$DB"
if [[ -n "$TAG" ]]; then
  [[ -n "${PKG_REPO:-}" ]] || { echo "FLOW_STOP: для --tag задайте PKG_REPO (шлях до репо пакета)" >&2; exit 2; }
  REPO="$PKG_REPO"
  HEAD_SHA="$(git -C "$REPO" rev-parse HEAD)" || { echo "FLOW_STOP: git rev-parse HEAD у $REPO не вдався" >&2; exit 2; }
  TAG_SHA="$(git -C "$REPO" rev-parse "$TAG^{commit}")" || { echo "FLOW_STOP: тег $TAG не знайдено в $REPO" >&2; exit 2; }
  [[ -n "$HEAD_SHA" && "$HEAD_SHA" == "$TAG_SHA" ]] || { echo "FLOW_STOP: HEAD не збігається з тегом $TAG" >&2; exit 2; }
fi
DEMO_ARGS=()
if [[ $DEMO -eq 1 ]]; then
  [[ -n "${ODOO_DEMO_OPT:-}" ]] && read -ra DEMO_ARGS <<<"$ODOO_DEMO_OPT" || echo "WARN: ODOO_DEMO_OPT не задано; демо-дані не гарантовані (відкрите питання C-00)" >&2
else
  [[ -n "${ODOO_NODEMO_OPT:-}" ]] && read -ra DEMO_ARGS <<<"$ODOO_NODEMO_OPT" || echo "WARN: ODOO_NODEMO_OPT не задано; наявність демо-даних залежить від умовчань Odoo (відкрите питання C-00)" >&2
fi
dropdb --if-exists "$DB"
createdb "$DB"
odoo_args
LOG="$(mktemp)"; trap 'rm -f "$LOG"' EXIT
set +e
"$ODOO_BIN" ${ODOO_ARGS[@]+"${ODOO_ARGS[@]}"} -d "$DB" -i base ${DEMO_ARGS[@]+"${DEMO_ARGS[@]}"} --stop-after-init --log-level=warn >"$LOG" 2>&1
RC=$?
set -e
grep -E " (ERROR|CRITICAL) |Traceback" -A 15 "$LOG" | head -40 || true
if [[ $RC -ne 0 ]] || grep -qE " (ERROR|CRITICAL) " "$LOG"; then echo "FAIL clean_db: $DB"; exit 1; fi
echo "OK clean_db: $DB"
