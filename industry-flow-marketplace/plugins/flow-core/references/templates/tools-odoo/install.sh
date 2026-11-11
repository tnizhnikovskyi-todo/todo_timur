#!/usr/bin/env bash
# Установка модулів у тестову базу. Використання:
#   [ODOO_EDITION=ce|ee] install.sh <db> <module1,module2,...> [--update] [--addons-src <dir>] [--tag <git-тег>] [--lang <uk_UA>] [--i18n-overwrite]
# --lang <код>: --load-language (мова показу); --i18n-overwrite: оновлення з перезаписом перекладів (виклик з --update після першої установки).
# Редакція: ODOO_EDITION=ce (за замовч.) | ee (потрібен ODOO_EE_ADDONS_PATH; немає — код 3 "WARN ee-unavailable"); див. _common.sh.
# За замовчуванням -i (install); з --update — -u (оновлення вже встановлених).
# --tag: HEAD репо $PKG_REPO має збігатися з тегом (як у clean_db.sh), інакше FLOW_STOP. З --addons-src додатково: SRC усередині $PKG_REPO
#   і без незакомічених/невідстежуваних змін та ігнорованих файлів (напр. __pycache__) (інакше доставили б не код тегу).
# --addons-src: доставка модулів (підкаталоги з __manifest__.py, напр. package/addons) у каталог
#   $ODOO_DELIVERY_DIR, який ОБОВ'ЯЗКОВО є одним із шляхів ODOO_ADDONS_PATH тестової бази. Без ODOO_DELIVERY_DIR — FLOW_STOP.
#   Каталог доставки має бути ОКРЕМИМ (не стандартні addons Odoo): модуль, що вже є в ньому й не в маркері .flow-delivery, не затирається.
#   Доставка потрібна ДО -i: інакше Odoo не бачить модуль (перевіряє require_installed нижче).
source "$(dirname "$0")/_common.sh"
DB="${1:-}"; MODS="${2:-}"; shift 2 || true
MODE="-i"; SRC=""; TAG=""; LANG_OPT=""; OVW=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --update) MODE="-u"; shift ;;
    --addons-src) SRC="${2:?--addons-src потребує значення}"; shift 2 ;;
    --tag) TAG="${2:?--tag потребує значення}"; shift 2 ;;
    --lang) LANG_OPT="${2:?--lang потребує значення}"; shift 2 ;;
    --i18n-overwrite) OVW=1; shift ;;
    *) echo "FLOW_STOP: невідомий аргумент '$1'" >&2; exit 2 ;;
  esac
done
[[ -z "$LANG_OPT" ]] || export ODOO_LANG="$LANG_OPT"
(( ! OVW )) || export ODOO_I18N_OVERWRITE=1
guard_db "$DB"
check_edition
if [[ -n "$TAG" ]]; then
  [[ -n "${PKG_REPO:-}" ]] || { echo "FLOW_STOP: для --tag задайте PKG_REPO" >&2; exit 2; }
  HEAD_SHA="$(git -C "$PKG_REPO" rev-parse HEAD)" || { echo "FLOW_STOP: git rev-parse HEAD не вдався" >&2; exit 2; }
  TAG_SHA="$(git -C "$PKG_REPO" rev-parse "$TAG^{commit}")" || { echo "FLOW_STOP: тег $TAG не знайдено" >&2; exit 2; }
  [[ "$HEAD_SHA" == "$TAG_SHA" ]] || { echo "FLOW_STOP: HEAD не збігається з тегом $TAG" >&2; exit 2; }
  if [[ -n "$SRC" ]]; then  # --tag гарантує код тегу лише якщо SRC у репо й без незакомічених змін
    [[ -d "$SRC" ]] || { echo "FLOW_STOP: немає каталогу --addons-src '$SRC'" >&2; exit 2; }
    REPO_R="$(cd "$PKG_REPO" && pwd -P)"; SRC_R="$(cd "$SRC" && pwd -P)"
    case "$SRC_R/" in
      "$REPO_R"/*) ;;
      *) echo "FLOW_STOP: --addons-src поза \$PKG_REPO: з --tag код тегу не гарантовано" >&2; exit 2 ;;
    esac
    DIRTY="$(git -C "$PKG_REPO" status --porcelain --untracked-files=all --ignored -- "$SRC_R")" || { echo "FLOW_STOP: git status не вдався" >&2; exit 2; }
    [[ -z "$DIRTY" ]] || { echo "FLOW_STOP: у --addons-src є незакомічені/невідстежувані зміни або ігноровані файли, напр. __pycache__ (код не збігається з тегом $TAG). Перші рядки git status:" >&2; echo "$DIRTY" | head -5 >&2; exit 2; }
  fi
fi
if [[ -n "$SRC" ]]; then
  DEST="${ODOO_DELIVERY_DIR:-}"
  [[ -d "$SRC" ]] || { echo "FLOW_STOP: немає каталогу --addons-src '$SRC'" >&2; exit 2; }
  [[ -n "$DEST" && "$DEST" != "/" && -d "$DEST" ]] || { echo "FLOW_STOP: задайте ODOO_DELIVERY_DIR (існуючий каталог тестової бази)" >&2; exit 2; }
  DEST="$(cd "$DEST" && pwd)"
  case ",${ODOO_ADDONS_PATH:-}," in
    *",$DEST,"*) ;;
    *) echo "FLOW_STOP: $DEST не входить до ODOO_ADDONS_PATH (повні шляхи через кому)" >&2; exit 2 ;;
  esac
  MARK="$DEST/.flow-delivery"  # список модулів, доставлених цим скриптом раніше
  [[ ! -f "$DEST/base/__manifest__.py" ]] || { echo "FLOW_STOP: $DEST схожий на каталог стандартних addons Odoo (є base); потрібен окремий каталог доставки" >&2; exit 2; }
  for d in "$SRC"/*/; do
    [[ -f "$d/__manifest__.py" ]] || continue
    n="$(basename "$d")"
    if [[ -e "$DEST/$n" ]] && ! grep -qxF -- "$n" "$MARK" 2>/dev/null; then
      echo "FLOW_STOP: $DEST/$n існує й не доставлявся цим скриптом (немає в .flow-delivery); не затираю" >&2; exit 2
    fi
  done
  for d in "$SRC"/*/; do
    [[ -f "$d/__manifest__.py" ]] || continue
    n="$(basename "$d")"
    [[ "$n" =~ ^[a-z0-9_]+$ ]] || { echo "FLOW_STOP: недопустиме ім'я модуля '$n'" >&2; exit 2; }
    rm -rf -- "${DEST:?}/$n"; cp -R "$d" "$DEST/$n"; grep -qxF -- "$n" "$MARK" 2>/dev/null || echo "$n" >> "$MARK"; echo "delivered: $n -> $DEST"
  done
fi
[[ -n "$MODS" ]] || { echo "Не задано модулі" >&2; exit 2; }
validate_mods "$MODS"
odoo_args
LOG="$(mktemp)"; trap 'rm -f "$LOG"' EXIT
set +e
"$ODOO_BIN" ${ODOO_ARGS[@]+"${ODOO_ARGS[@]}"} -d "$DB" "$MODE" "$MODS" --stop-after-init --log-level=warn >"$LOG" 2>&1
RC=$?
set -e
grep -E " (ERROR|CRITICAL) |Traceback" -A 15 "$LOG" | head -60 || true
if [[ $RC -ne 0 ]] || grep -qE " (ERROR|CRITICAL) " "$LOG"; then echo "FAIL install: $MODS у $DB"; exit 1; fi
require_installed "$DB" "$MODS" || { echo "FAIL install: $MODS у $DB (не installed)"; exit 1; }
echo "OK install: $MODS у $DB (edition=$ODOO_EDITION)"
