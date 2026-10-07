#!/usr/bin/env bash
# Создать базу <name> копией шаблона td_template (одноимённая база удаляется) вместе с filestore.
#
#   new_db.sh <name>
#
# Копия занимает секунды; в базе стоят base, web, mail, contacts, maintenance без демо-данных.
# Модуль td_genset не устанавливается — для этого update.sh <name> (сам выберет -i или -u)
# или run_tests.sh <name>.
set -euo pipefail
# shellcheck source=env.sh
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"

[[ $# -eq 1 ]] || { echo "Использование: $0 <имя_базы>" >&2; exit 2; }
db="$1"
td_require_db_name "$db"
td_require_pg
td_lock_db "$db"
t0=$(date +%s%N)
td_clone_db "$db"
td_log "база $db создана из $TD_TEMPLATE_DB за $(( ($(date +%s%N) - t0) / 1000000 )) мс"
