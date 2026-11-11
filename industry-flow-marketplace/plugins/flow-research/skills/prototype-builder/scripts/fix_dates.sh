#!/usr/bin/env bash
# Нові записи зйомки мають робочий час показу (8:00-17:00 за часовим поясом показу), а не нічний час запуску зйомки.
# Записи розкладаються циклічно: 14 слотів на добу (08:05 + слот*37 хв, останній ~16:06), далі — попередні доби (дні тижня не пропускаються).
# Значення пишеться як naive UTC (так зберігає Odoo), тож у Києві (FIX_TZ, типово Europe/Kyiv) воно виглядає як 08:05-16:06.
# Використання: fix_dates.sh <demo-база> <таблиця> <колонка_дати> [<колонка_створення=create_date>]   (напр. sale_order date_order)
# Лише для демо-баз (demo-*); виконує psql від імені PG-користувача середовища (PGUSER/PGHOST).
set -euo pipefail
DB="${1:?потрібна база}"; TBL="${2:?таблиця}"; COL="${3:?колонка дати}"; CRE="${4:-create_date}"; TZ_SHOW="${FIX_TZ:-Europe/Kyiv}"
[[ "$DB" =~ ^demo-[A-Za-z0-9_-]+$ ]] || { echo "FLOW_STOP: база '$DB' не demo-<суфікс>" >&2; exit 2; }
[[ "$TBL" =~ ^[a-z_]+$ && "$COL" =~ ^[a-z_]+$ && "$CRE" =~ ^[a-z_]+$ ]] || { echo "FLOW_STOP: недопустимі ідентифікатори" >&2; exit 2; }
[[ "$TZ_SHOW" =~ ^[A-Za-z_]+(/[A-Za-z_+-]+)*$ ]] || { echo "FLOW_STOP: недопустимий часовий пояс '$TZ_SHOW'" >&2; exit 2; }
psql -q -d "$DB" <<SQL
WITH n AS (SELECT id, row_number() OVER (ORDER BY id) - 1 AS rn FROM $TBL WHERE $CRE > now() - interval '2 days' AND $COL > now() - interval '1 day'),
     base AS (SELECT date_trunc('day', now() AT TIME ZONE '$TZ_SHOW') - (CASE WHEN extract(hour from now() AT TIME ZONE '$TZ_SHOW') < 18 THEN interval '1 day' ELSE interval '0' END) AS d)
UPDATE $TBL s SET $COL = ((base.d - (n.rn / 14) * interval '1 day') + interval '8 hours 5 minutes' + (n.rn % 14) * interval '37 minutes') AT TIME ZONE '$TZ_SHOW' AT TIME ZONE 'UTC'
FROM n, base WHERE s.id = n.id;
SQL
