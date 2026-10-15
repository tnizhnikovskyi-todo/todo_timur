#!/usr/bin/env bash
# Підготувати модуль wh_constructor до встановлення: зібрати застосунок warehouse3d/app у static/app модуля (I-02: збірка не в git).
#
#   prepare_module.sh [--force]
#
# Збирає лише якщо static/app/index.html немає або він старіший за вихідники застосунку (src, index.html, package.json, vite.config.js,
# ../prototype/data.json); --force (або WH_APP_BUILD=force) — збирає завжди. WH_APP_BUILD=skip — пропустити (наприклад, на сервері без Node:
# збірку тоді треба покласти в static/app самому, а без неї сторінка модуля покаже підказку).
# Потрібні Node 20+ і npm; node_modules ставляться (`npm ci`, а без lock-файлу `npm install`), якщо їх ще немає.
# Викликається з setup.sh (крок app) і update.sh; код виходу 0 — збірка свіжа, інакше — помилка з поясненням.
set -euo pipefail
# shellcheck source=env.sh
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"

APP_DIR="$WH_REPO_DIR/warehouse3d/app"
OUT_DIR="$WH_ADDONS_DIR/wh_constructor/static/app"
mode="${WH_APP_BUILD:-auto}"
[[ "${1:-}" == "--force" ]] && mode=force

[[ "$mode" != "skip" ]] || { wh_log "збірку застосунку пропущено (WH_APP_BUILD=skip)"; exit 0; }
[[ -f "$APP_DIR/package.json" ]] || wh_die "немає $APP_DIR/package.json"

stale() {
    [[ -f "$OUT_DIR/index.html" ]] || return 0
    [[ -n "$(find "$APP_DIR/src" "$APP_DIR/index.html" "$APP_DIR/package.json" "$APP_DIR/vite.config.js" "$WH_REPO_DIR/warehouse3d/prototype/data.json" -newer "$OUT_DIR/index.html" -print -quit 2>/dev/null)" ]]
}

if [[ "$mode" != "force" ]] && ! stale; then
    wh_log "static/app модуля свіжий: $OUT_DIR"
    exit 0
fi
command -v node >/dev/null && command -v npm >/dev/null || wh_die "для збірки застосунку потрібні node і npm (або WH_APP_BUILD=skip і готова збірка в $OUT_DIR)"
node_major="$(node -p 'process.versions.node.split(".")[0]')"
[[ "$node_major" -ge 20 ]] || wh_die "потрібен Node 20+ (зараз $(node --version))"

cd "$APP_DIR"
if [[ ! -d node_modules ]]; then
    wh_log "ставлю залежності застосунку (npm)"
    if [[ -f package-lock.json ]]; then wh_retry npm ci --no-audit --no-fund --loglevel=error; else wh_retry npm install --no-audit --no-fund --loglevel=error; fi
fi
wh_log "збираю застосунок у $OUT_DIR"
npm run build:odoo --silent > "${TMPDIR:-/tmp}/wh-app-build.$$.log" 2>&1 || { tail -n 20 "${TMPDIR:-/tmp}/wh-app-build.$$.log" >&2; rm -f "${TMPDIR:-/tmp}/wh-app-build.$$.log"; wh_die "npm run build:odoo завершився з помилкою"; }
rm -f "${TMPDIR:-/tmp}/wh-app-build.$$.log"
[[ -f "$OUT_DIR/index.html" ]] || wh_die "після збірки немає $OUT_DIR/index.html"
wh_log "готово: $OUT_DIR"
