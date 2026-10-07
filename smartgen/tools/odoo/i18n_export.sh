#!/usr/bin/env bash
# Оновити smartgen/td_genset/i18n/uk_UA.po з бази, де встановлено td_genset, зі збереженням наявних перекладів.
#
#   i18n_export.sh <dbname> [--fill-same] [--dry-run]
#
# 1. odoo-bin --i18n-export=<tmp>/td_genset.pot --modules=td_genset (шаблон без мови: усі рядки модуля —
#    поля, help, selection, подання, меню, _() у Python/JS — з цього worktree, --addons-path як у run_tests.sh);
# 2. злиття з наявним uk_UA.po: msgmerge --no-fuzzy-matching (якщо є gettext), інакше Python (polib — залежність
#    Odoo 18, той самий POFile.merge, яким Odoo зливає .po при імпорті); переклади наявних рядків зберігаються,
#    нові рядки додаються з порожнім msgstr, рядки, яких у модулі вже немає, прибираються; fuzzy не ставиться;
# 3. --fill-same — порожні msgstr рядків з кирилицею заповнити тим самим текстом (вихідні рядки модуля вже
#    українською: для uk_UA переклад = оригінал); --dry-run — лише статистика, файл не змінюється.
#
# Статистика: усього рядків, перекладено, порожніх, fuzzy. Лог odoo-bin: $ODOO_LOG_DIR/i18n-<dbname>.log.
# База має бути з модулем (наприклад, після run_tests.sh <db> або update.sh <db>); скрипт її не змінює.
set -euo pipefail
# shellcheck source=env.sh
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"

usage() { echo "Використання: $0 <dbname> [--fill-same] [--dry-run]" >&2; exit 2; }
[[ $# -ge 1 ]] || usage
db="$1"; shift
fill=0; dry=0
for arg in "$@"; do
    case "$arg" in
        --fill-same) fill=1 ;;
        --dry-run) dry=1 ;;
        *) usage ;;
    esac
done
td_require_db_name "$db"
td_check_env
td_require_pg
td_db_exists "$db" || td_die "немає бази $db (спершу $TD_TOOLS_DIR/run_tests.sh $db або update.sh $db)"
state="$(td_module_state "$db" "$TD_MODULE")"
[[ "$state" == "installed" ]] || td_die "у базі $db модуль $TD_MODULE не встановлено (state: ${state:-немає})"
td_lock_db "$db"

po="$TD_ADDONS_DIR/$TD_MODULE/i18n/uk_UA.po"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
pot="$tmp/$TD_MODULE.pot"
log="$ODOO_LOG_DIR/i18n-$db.log"
td_log "експорт рядків $TD_MODULE з бази $db (addons-path: $ODOO_ADDONS_PATH)"
if ! td_odoo -d "$db" --i18n-export="$pot" --modules="$TD_MODULE" --stop-after-init --log-level=warn > "$log" 2>&1; then
    tail -n 20 "$log" >&2
    td_die "odoo-bin --i18n-export не вдався (лог $log)"
fi
[[ -s "$pot" ]] || td_die "порожній експорт (лог $log)"

merged="$tmp/uk_UA.po"
if [[ -f "$po" ]] && command -v msgmerge > /dev/null 2>&1; then
    td_log "злиття: msgmerge --no-fuzzy-matching"
    msgmerge --quiet --no-fuzzy-matching -o "$merged" "$po" "$pot"
    merge_mode="msgmerge"
else
    cp "$pot" "$merged.pot"
    merge_mode="polib"
    td_log "злиття: Python (polib)"
fi

"$ODOO_PY" - "$po" "$pot" "$merged" "$merge_mode" "$fill" <<'PY'
import datetime
import os
import re
import sys

import polib

po_path, pot_path, out_path, mode, fill = sys.argv[1:6]
pot = polib.pofile(pot_path)
if mode == 'msgmerge':
    po = polib.pofile(out_path)
elif os.path.exists(po_path):
    po = polib.pofile(po_path)
    po.merge(pot)                         # як msgmerge: переклади наявних рядків лишаються, нові — порожні
else:
    po = pot
    po.metadata['Language'] = 'uk_UA'
obsolete = [entry for entry in po if entry.obsolete]
for entry in obsolete:
    po.remove(entry)                      # рядків уже немає в модулі
for entry in po:
    if 'fuzzy' in entry.flags:
        entry.flags.remove('fuzzy')
        entry.msgstr = ''                 # неточний переклад не лишаємо — краще порожній (видно в статистиці)
cyrillic = re.compile('[А-Яа-яІіЇїЄєҐґ]')
filled = 0
if fill == '1':
    for entry in po:
        if not entry.msgstr and cyrillic.search(entry.msgid):
            entry.msgstr = entry.msgid
            filled += 1
now = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M+0000')
po.metadata['POT-Creation-Date'] = pot.metadata.get('POT-Creation-Date', now)
po.metadata['PO-Revision-Date'] = now
po.save(out_path)
total = len([entry for entry in po if entry.msgid])
empty = len([entry for entry in po if entry.msgid and not entry.msgstr])
print('рядків: %d · перекладено: %d · порожніх msgstr: %d · fuzzy: 0 · прибрано застарілих: %d · заповнено '
      'оригіналом: %d' % (total, total - empty, empty, len(obsolete), filled))
PY

if [[ $dry -eq 1 ]]; then
    td_log "--dry-run: $po не змінено"
else
    cp "$merged" "$po"
    td_log "оновлено $po"
fi
