#!/usr/bin/env bash
# Імпорт CSV майстер-даних у тестову/демо-базу. Використання:
#   import.sh <db> <model> <file.csv>
# РЕАЛІЗУЄ C-00: канал імпорту (base_import через XML-RPC/JSON-2 або шлях з odoo shell) не зафіксовано
# в цьому пакеті; вигадувати API не дозволено. Скрипт лише перевіряє вхід і зупиняється.
source "$(dirname "$0")/_common.sh"
DB="${1:-}"; MODEL="${2:-}"; FILE="${3:-}"
guard_db "$DB"
[[ -n "$MODEL" && -f "$FILE" ]] || { echo "Потрібні <model> і існуючий <file.csv>" >&2; exit 2; }
echo "FLOW_STOP: import.sh не реалізовано (C-00 обирає канал імпорту; див. README.md). db=$DB model=$MODEL file=$FILE" >&2
exit 4   # 4 = «не реалізовано»; код 3 зарезервовано за WARN ee-unavailable (check_edition)
