#!/usr/bin/env bash
# Скидання демо/тест-бази до чистого стану. Використання:
#   [PKG_REPO=<репо>] [ODOO_EDITION=ce|ee] reset.sh <db> --yes [--modules m1,m2] [--tag <тег>] [--demo] [--lang uk_UA]
# --lang потребує --modules (інакше FLOW_STOP, код 2). --lang: після установки модулів повторне оновлення з --i18n-overwrite (переклади view-ів потрапляють у мову показу).
# Пересоздає базу (clean_db.sh) і, якщо задано --modules, встановлює модулі (install.sh).
# Без --yes нічого не робить. Знімки/restore цей шаблон не реалізує (рішення C-00).
source "$(dirname "$0")/_common.sh"
HERE="$(dirname "$0")"
DB="${1:-}"; shift || true
YES=0; MODS=""; PASS=(); LANGC=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --yes) YES=1; shift ;;
    --modules) MODS="${2:?}"; shift 2 ;;
    --tag) PASS+=(--tag "${2:?}"); shift 2 ;;
    --demo) PASS+=(--demo); shift ;;
    --lang) LANGC="${2:?}"; shift 2 ;;
    *) echo "Невідомий параметр: $1" >&2; exit 2 ;;
  esac
done
guard_db "$DB"
check_edition
if [[ -n "$LANGC" && -z "$MODS" ]]; then echo "FLOW_STOP: --lang $LANGC без --modules не має ефекту (мова застосовується лише при установці модулів); додайте --modules або приберіть --lang" >&2; exit 2; fi
[[ $YES -eq 1 ]] || { echo "Потрібен --yes (база $DB буде видалена й створена знову)" >&2; exit 2; }
"$HERE/clean_db.sh" "$DB" ${PASS[@]+"${PASS[@]}"}
if [[ -n "$MODS" ]]; then
  if [[ -n "$LANGC" ]]; then
    "$HERE/install.sh" "$DB" "$MODS" --lang "$LANGC"
    "$HERE/install.sh" "$DB" "$MODS" --update --lang "$LANGC" --i18n-overwrite
  else
    "$HERE/install.sh" "$DB" "$MODS"
  fi
fi
echo "OK reset: $DB"
