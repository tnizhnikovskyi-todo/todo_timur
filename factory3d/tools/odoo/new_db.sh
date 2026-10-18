#!/usr/bin/env bash
# Створити базу <name> копією шаблона f3d_template (однойменна база видаляється) разом із filestore.
#
#   new_db.sh <name>
#
# Копія займає секунди; у базі стоять стандартні залежності factory3d (див. setup.sh, ENV.md) без
# демо-даних. Модулі td_* не встановлюються — для цього update.sh <name> (сам обере -i чи -u)
# або run_tests.sh <name>.
set -euo pipefail
# shellcheck source=env.sh
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"

[[ $# -eq 1 ]] || { echo "Використання: $0 <ім'я_бази>" >&2; exit 2; }
db="$1"
f3d_require_db_name "$db"
f3d_require_pg
f3d_lock_db "$db"
t0=$(date +%s%N)
f3d_clone_db "$db"
f3d_log "база $db створена з $F3D_TEMPLATE_DB за $(( ($(date +%s%N) - t0) / 1000000 )) мс"
