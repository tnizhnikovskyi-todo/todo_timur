#!/usr/bin/env bash
# Перестворює базу зрізу ПЕРЕД кожною зйомкою (повторні зйомки лишають дублікати записів). Узагальнено з еталона A-21-real.
# Використання: build_db.sh <demo-база> <модулі через кому> <seed.py> [--lang uk_UA]
#   <демо-база> — ім'я за шаблоном demo-<суфікс> (guard_db tools/odoo); <seed.py> — скрипт `odoo-bin shell` (демо-дані з калібруванням, demo-data-rules.md).
# Середовище: TOOLS (каталог tools/odoo репо пакета; типово ./tools/odoo), ODOO_EDITION=ce|ee, ODOO_BIN, ODOO_ADDONS_PATH, ODOO_ALLOWED_HOSTS, ODOO_DELIVERY_DIR (C-00).
# Код 2 = FLOW_STOP (немає середовища/не та база/seed не залишив записів); 3 = EE недоступна (WARN, «не перевірено»).
# Seed-скрипт ОБОВ'ЯЗКОВО завершується явним env.cr.commit() (відкрите питання C-00: чи комітить odoo-bin shell сам) — після seed перевіряється кількість записів.
set -euo pipefail
DB="${1:?потрібна база demo-<суфікс>}"; MODS="${2:?потрібні модулі}"; SEED="${3:?потрібен seed.py}"; LANG_CODE="uk_UA"; CHK_TBL=""; MIN_ROWS=1; shift 3
while [[ $# -gt 0 ]]; do case "$1" in
  --lang) LANG_CODE="${2:?--lang потребує значення}"; shift 2;;
  --check-table) CHK_TBL="${2:?--check-table потребує таблицю}"; shift 2;;
  --min-rows) MIN_ROWS="${2:?--min-rows потребує число}"; shift 2;;
  *) echo "FLOW_STOP: невідомий аргумент $1" >&2; exit 2;; esac; done
[[ "$CHK_TBL" =~ ^[a-z_]+$ ]] || { echo "FLOW_STOP: потрібен --check-table <таблиця з демо-даними, напр. sale_order>" >&2; exit 2; }
[[ "$MIN_ROWS" =~ ^[0-9]+$ ]] || { echo "FLOW_STOP: --min-rows має бути числом" >&2; exit 2; }
T="${TOOLS:-./tools/odoo}"
[[ -x "$T/clean_db.sh" && -x "$T/install.sh" ]] || { echo "FLOW_STOP: немає $T/clean_db.sh або install.sh (C-00/preflight)" >&2; exit 2; }
"$T/clean_db.sh" "$DB"
"$T/install.sh" "$DB" "$MODS" --addons-src "${ADDONS_SRC:-package/addons}" --lang "$LANG_CODE"
# повторне оновлення з перезаписом перекладів: терміни нових view потрапляють у мову показу (інакше на екрані англійські підписи)
"$T/install.sh" "$DB" "$MODS" --update --i18n-overwrite --lang "$LANG_CODE"
# демо-дані: shell-скрипт із env; apply.py лише передає seed у `odoo-bin shell` через stdin (guard бази — у C-00), коміт — явний env.cr.commit() у seed
python3 -I "$T/apply.py" shell --db "$DB" --script "$SEED" | tail -15
ROWS="$(psql -qtA -d "$DB" -c "SELECT count(*) FROM $CHK_TBL" 2>/dev/null || echo -1)"
[[ "$ROWS" =~ ^[0-9]+$ && "$ROWS" -ge "$MIN_ROWS" ]] || { echo "FLOW_STOP: після seed у $CHK_TBL записів: $ROWS (треба >= $MIN_ROWS) — seed не закомітив дані (env.cr.commit()?)" >&2; exit 2; }
echo "build_db: $DB готова ($CHK_TBL: $ROWS записів; модулі: $MODS, мова: $LANG_CODE)"
