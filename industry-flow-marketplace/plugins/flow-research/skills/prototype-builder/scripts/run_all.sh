#!/usr/bin/env bash
# Оркестрація повної зйомки зрізу A-21 (узагальнено з еталона run_all.sh). Порядок строгий:
#   build_db (перестворення) -> старт Odoo + перевірка BASE -> очищення cookie/dom/facts -> ПРОХІД 1 (кроки й кліпи, що ЗМІНЮЮТЬ дані)
#   -> fix_dates (робочі години показу) -> ПРОХІД 2 (лише читання: дашборд першим, звіти, мобільні) -> check_ui_text.
# Так цифри дашборда у скриншотах, відео й facts.json збігаються (DASH-drill). Списки проходів — експорти PASS1/PASS2 у
# shoot/scenario.steps.mjs (номери кроків), shoot/scenario-mobile.steps.mjs (PASS2: 'm1'...), shoot/clips.mjs (імена кліпів) за PLAN.md §6.
# Використання (з prototype-real/shoot або з PROTO_ROOT):
#   run_all.sh <demo-база> <модулі через кому> <seed.py> --check-table <таблиця> --fix-dates <таблиця:колонка> [--fix-dates ...]
#              [--lang uk_UA] [--zero-cols td_hours,...] [--allow-empty a,b] [--no-build]
# Env: BASE (з портом, типово http://127.0.0.1:8069), DEMO_EMAIL_DOMAIN, TOOLS (tools/odoo), PROTO_ROOT, ODOO_SERVE_CMD (команда старту Odoo; або $TOOLS/serve.sh <db> <port>).
# Код 2 = FLOW_STOP (немає середовища/сервера/кроків проходу); решта — код першого збійного етапу.
set -euo pipefail
DB="${1:?потрібна база demo-<суфікс>}"; MODS="${2:?потрібні модулі}"; SEED="${3:?потрібен seed.py}"; shift 3
CHK=""; LANG_CODE="uk_UA"; ZERO=""; ALLOWE=""; NOBUILD=0; FIXES=()
while [[ $# -gt 0 ]]; do case "$1" in
  --check-table) CHK="${2:?}"; shift 2;;
  --fix-dates) FIXES+=("${2:?потрібно <таблиця:колонка>}"); shift 2;;
  --lang) LANG_CODE="${2:?}"; shift 2;;
  --zero-cols) ZERO="${2:?}"; shift 2;;
  --allow-empty) ALLOWE="${2:?}"; shift 2;;
  --no-build) NOBUILD=1; shift;;
  *) echo "FLOW_STOP: невідомий аргумент $1" >&2; exit 2;; esac; done
[[ -n "$CHK" ]] || { echo "FLOW_STOP: потрібен --check-table" >&2; exit 2; }
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SHOOT="${PROTO_ROOT:+$PROTO_ROOT/shoot}"; SHOOT="${SHOOT:-$HERE}"; ROOT="$(cd "$SHOOT/.." && pwd)"
T="${TOOLS:-./tools/odoo}"; export BASE="${BASE:-http://127.0.0.1:8069}" DB PROTO_ROOT="$ROOT"
reachable() { curl -fsS -o /dev/null --max-time 5 "$BASE/web/login" 2>/dev/null; }

# 1. база (перестворення обов'язкове перед кожною зйомкою) + штамп: старі сесії недійсні
if [[ $NOBUILD -eq 0 ]]; then "$HERE/build_db.sh" "$DB" "$MODS" "$SEED" --lang "$LANG_CODE" --check-table "$CHK"; fi
mkdir -p "$SHOOT"; touch "$SHOOT/.db_stamp"
# 2. сервер Odoo на BASE: $TOOLS/serve.sh або ODOO_SERVE_CMD; іншого способу немає (шаблон serve.sh — flow-core/references/templates/tools-odoo/)
if ! reachable; then
  PORT="${BASE##*:}"; PORT="${PORT%%/*}"
  if [[ -n "${ODOO_SERVE_CMD:-}" ]]; then nohup bash -c "$ODOO_SERVE_CMD" >"$SHOOT/odoo-serve.log" 2>&1 &
  elif [[ -x "$T/serve.sh" ]]; then nohup "$T/serve.sh" "$DB" "$PORT" >"$SHOOT/odoo-serve.log" 2>&1 &
  else echo "FLOW_STOP: Odoo недоступний за $BASE, а команди старту немає (немає $T/serve.sh і ODOO_SERVE_CMD). шаблон serve.sh <db> <port> — у flow-core/references/templates/tools-odoo/; підніми сервер вручну і повтори з --no-build" >&2; exit 2; fi
  for _ in $(seq 1 60); do reachable && break; sleep 2; done
fi
reachable || { echo "FLOW_STOP: Odoo недоступний за $BASE після старту (хвіст $SHOOT/odoo-serve.log)" >&2; exit 2; }
# 3. очищення прогону: сесії, DOM-знімки, факти (інакше старі кроки дають хибні FAIL і застарілі факти)
rm -f "$SHOOT/.cookies.json"; rm -rf "$SHOOT/dom" "$SHOOT/fail"; rm -f "$ROOT/facts.json" "$SHOOT/console.log"
cd "$SHOOT"
# 4. ПРОХІД 1 — змінює дані
PASS=1 node scenario.mjs
PASS=1 node rec_clips.mjs
# 5. робочий час показу для нових записів (між проходами)
for f in "${FIXES[@]:-}"; do [[ -n "$f" ]] && "$HERE/fix_dates.sh" "$DB" "${f%%:*}" "${f##*:}"; done
# 6. ПРОХІД 2 — лише читання (кліпи дашборда першими за порядком PASS2 у clips.mjs)
PASS=2 node scenario.mjs
PASS=2 node scenario-mobile.mjs
PASS=2 node rec_clips.mjs
# 7. перевірка UI-тексту
ARGS=(--lang "${LANG_CODE%%_*}"); [[ -n "$ZERO" ]] && ARGS+=(--zero-cols "$ZERO"); [[ -n "$ALLOWE" ]] && ARGS+=(--allow-empty "$ALLOWE")
python3 -I "$HERE/check_ui_text.py" "$SHOOT/dom" "${ARGS[@]}" | tail -30
