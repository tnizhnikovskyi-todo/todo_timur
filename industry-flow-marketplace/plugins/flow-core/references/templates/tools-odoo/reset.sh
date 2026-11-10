#!/usr/bin/env bash
# Скидання демо/тест-бази до чистого стану. Використання:
#   [PKG_REPO=<репо>] reset.sh <db> --yes [--modules m1,m2] [--tag <тег>] [--demo]
# Пересоздає базу (clean_db.sh) і, якщо задано --modules, встановлює модулі (install.sh).
# Без --yes нічого не робить. Знімки/restore цей шаблон не реалізує (рішення C-00).
source "$(dirname "$0")/_common.sh"
HERE="$(dirname "$0")"
DB="${1:-}"; shift || true
YES=0; MODS=""; PASS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --yes) YES=1; shift ;;
    --modules) MODS="${2:?}"; shift 2 ;;
    --tag) PASS+=(--tag "${2:?}"); shift 2 ;;
    --demo) PASS+=(--demo); shift ;;
    *) echo "Невідомий параметр: $1" >&2; exit 2 ;;
  esac
done
guard_db "$DB"
[[ $YES -eq 1 ]] || { echo "Потрібен --yes (база $DB буде видалена й створена знову)" >&2; exit 2; }
"$HERE/clean_db.sh" "$DB" ${PASS[@]+"${PASS[@]}"}
[[ -z "$MODS" ]] || "$HERE/install.sh" "$DB" "$MODS"
echo "OK reset: $DB"
