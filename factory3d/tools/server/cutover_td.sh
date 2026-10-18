#!/usr/bin/env bash
# Перехід тестового сервера на модулі td_* (RENAME.md): нова база з тим самим іменем, стара лишається поруч.
#
#   sudo bash cutover_td.sh --check   # лише показати, що знайдено, нічого не змінювати
#   sudo bash cutover_td.sh           # виконати
#
# Що робить:
#   1. зупиняє таймер f3d-update і Odoo, знімає дамп старої бази в /var/backups;
#   2. перемикає /mnt/f3d-addons на гілку з перейменуванням;
#   3. перейменовує стару базу odoo → odoo_f3d_old (разом із filestore), нічого не видаляє;
#   4. створює нову базу odoo: base + uk_UA, пароль admin — той самий, що був у старій базі;
#   5. запускає Odoo. Модулі td_* і демо-дані ставить менеджер через RPC;
#   6. чекає, поки менеджер запушить ту саму ревізію в claude/factory3d-build, і лише тоді вмикає таймер
#      (інакше таймер повернув би старий код). Чекання — до 3 год; таймер можна ввімкнути й вручну.
#
# Змінні (за замовчуванням — як на timur-o19demo): ADDONS_REPO, BRANCH, DEPLOY_BRANCH, OLD_DB, KEEP_DB,
#   ODOO_CONF, ODOO_SERVICE, ODOO_OS_USER, ODOO_BIN, TIMER.
set -euo pipefail

CHECK=0
[[ "${1:-}" == "--check" ]] && CHECK=1

ADDONS_REPO="${ADDONS_REPO:-/mnt/f3d-addons}"
BRANCH="${BRANCH:-claude/td-rename}"
DEPLOY_BRANCH="${DEPLOY_BRANCH:-claude/factory3d-build}"
OLD_DB="${OLD_DB:-odoo}"
KEEP_DB="${KEEP_DB:-odoo_f3d_old}"
ODOO_SERVICE="${ODOO_SERVICE:-odoo}"
TIMER="${TIMER:-f3d-update.timer}"
ODOO_BIN="${ODOO_BIN:-$(command -v odoo || echo /usr/bin/odoo)}"
if [[ -z "${ODOO_CONF:-}" ]]; then
    ODOO_CONF="$(systemctl cat "$ODOO_SERVICE" 2>/dev/null | grep -oE -- '(-c|--config)[ =][^ ]+' | head -1 | sed -E 's/^(-c|--config)[ =]//' || true)"
    ODOO_CONF="${ODOO_CONF:-/etc/odoo/odoo.conf}"
fi
ODOO_OS_USER="${ODOO_OS_USER:-$(systemctl show -p User --value "$ODOO_SERVICE" 2>/dev/null || true)}"
ODOO_OS_USER="${ODOO_OS_USER:-odoo}"
conf() { grep -E "^\s*$1\s*=" "$ODOO_CONF" | tail -1 | sed -E 's/^[^=]*=\s*//; s/\s+$//'; }
DATA_DIR="$(conf data_dir || true)"
DATA_DIR="${DATA_DIR:-$(getent passwd "$ODOO_OS_USER" | cut -d: -f6)/.local/share/Odoo}"
FILESTORE="$DATA_DIR/filestore"
git_() { git -c safe.directory='*' -C "$ADDONS_REPO" "$@"; }
psql_() { sudo -u postgres psql -v ON_ERROR_STOP=1 -Atq "$@"; }
log() { printf '%s  %s\n' "$(date -u +%H:%M:%S)" "$*"; }
die() { log "ПОМИЛКА: $*"; exit 1; }

[[ $EUID -eq 0 ]] || die "запустіть через sudo"
[[ -f "$ODOO_CONF" ]] || die "немає конфігу Odoo $ODOO_CONF (задайте ODOO_CONF)"
[[ -x "$ODOO_BIN" ]] || die "немає odoo-bin $ODOO_BIN (задайте ODOO_BIN)"
git_ rev-parse --git-dir >/dev/null 2>&1 || die "$ADDONS_REPO — не git-клон (задайте ADDONS_REPO)"
git_ fetch -q origin "$BRANCH" "$DEPLOY_BRANCH" || die "git fetch $BRANCH не вдався"
TARGET="$(git_ rev-parse "origin/$BRANCH")"
[[ "$(psql_ -c "select 1 from pg_database where datname = '$OLD_DB'")" == 1 ]] || die "бази $OLD_DB немає"
[[ -z "$(psql_ -c "select 1 from pg_database where datname = '$KEEP_DB'")" ]] || die "база $KEEP_DB уже є — перехід, схоже, вже виконано"
ADMIN_HASH="$(psql_ -d "$OLD_DB" -c "select password from res_users where id = 2")"
[[ -n "$ADMIN_HASH" ]] || die "не знайдено пароль admin у $OLD_DB"

log "конфіг Odoo:      $ODOO_CONF (служба $ODOO_SERVICE, користувач $ODOO_OS_USER)"
log "odoo-bin:         $ODOO_BIN"
log "filestore:        $FILESTORE"
log "код:              $ADDONS_REPO → origin/$BRANCH ($TARGET)"
log "бази:             $OLD_DB → $KEEP_DB, нова $OLD_DB"
log "таймер:           $TIMER (увімкнеться, коли origin/$DEPLOY_BRANCH = $TARGET)"
DBF="$(conf dbfilter || true)"; DBN="$(conf db_name || true)"
log "dbfilter/db_name: ${DBF:-—} / ${DBN:-—} $([[ -z "$DBF$DBN" ]] && echo "(буде додано dbfilter = ^$OLD_DB\$: після переходу баз дві)")"
if [[ $CHECK -eq 1 ]]; then log "перевірка пройдена, нічого не змінено"; exit 0; fi

log "1/6 зупиняю таймер і Odoo, знімаю дамп"
systemctl stop "$TIMER" || true
while systemctl is-active -q "${TIMER%.timer}.service"; do sleep 5; done
mkdir -p /var/backups
DUMP="/var/backups/${OLD_DB}_before_td_$(date -u +%Y%m%d_%H%M).dump"
sudo -u postgres pg_dump -Fc "$OLD_DB" >"$DUMP"
log "    дамп: $DUMP"
systemctl stop "$ODOO_SERVICE"

log "2/6 код → $TARGET"
git_ checkout -q -f -B "$DEPLOY_BRANCH" "$TARGET"

log "3/6 $OLD_DB → $KEEP_DB"
psql_ -c "select pg_terminate_backend(pid) from pg_stat_activity where datname = '$OLD_DB' and pid <> pg_backend_pid()" >/dev/null
psql_ -c "alter database \"$OLD_DB\" rename to \"$KEEP_DB\""
if [[ -d "$FILESTORE/$OLD_DB" ]]; then mv "$FILESTORE/$OLD_DB" "$FILESTORE/$KEEP_DB"; fi

log "4/6 нова база $OLD_DB: base + uk_UA"
sudo -u "$ODOO_OS_USER" "$ODOO_BIN" -c "$ODOO_CONF" -d "$OLD_DB" -i base --load-language=uk_UA \
    --stop-after-init --no-http --log-level=warn
psql_ -d "$OLD_DB" -v h="$ADMIN_HASH" -c "update res_users set password = :'h', lang = 'uk_UA' where id = 2"
BASE_URL="$(psql_ -d "$KEEP_DB" -c "select value from ir_config_parameter where key = 'web.base.url'")"
if [[ -n "$BASE_URL" ]]; then
    psql_ -d "$OLD_DB" -v u="$BASE_URL" -c "update ir_config_parameter set value = :'u' where key = 'web.base.url'"
fi

if [[ -z "$DBF$DBN" ]]; then
    cp -a "$ODOO_CONF" "$ODOO_CONF.before_td"
    printf '\ndbfilter = ^%s$\n' "$OLD_DB" >>"$ODOO_CONF"
    log "    додано dbfilter = ^$OLD_DB\$ (копія конфігу: $ODOO_CONF.before_td)"
fi
log "5/6 запускаю Odoo"
systemctl start "$ODOO_SERVICE"
log "    нова база працює. Повідомте менеджеру: «база готова». Далі він ставить модулі td_* і демо-дані."

log "6/6 чекаю ревізію $TARGET в origin/$DEPLOY_BRANCH (до 3 год), потім вмикаю $TIMER"
for _ in $(seq 1 360); do
    git_ fetch -q origin "$DEPLOY_BRANCH" || true
    if [[ "$(git_ rev-parse "origin/$DEPLOY_BRANCH")" == "$TARGET" ]] || git_ merge-base --is-ancestor "$TARGET" "origin/$DEPLOY_BRANCH"; then
        systemctl start "$TIMER"
        log "готово: таймер увімкнено. Стара база лишилась як $KEEP_DB, дамп — $DUMP"
        exit 0
    fi
    sleep 30
done
log "ревізія так і не з’явилась; таймер вимкнений. Увімкніть вручну: systemctl start $TIMER"
exit 1
