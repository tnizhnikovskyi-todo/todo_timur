#!/usr/bin/env bash
# Спільні функції шаблонів tools/odoo (C-00 адаптує під інфраструктуру клієнта).
# Підключається через: source "$(dirname "$0")/_common.sh"
set -euo pipefail
if (( BASH_VERSINFO[0] < 4 || (BASH_VERSINFO[0] == 4 && BASH_VERSINFO[1] < 4) )); then
  echo "FLOW_STOP: потрібен bash >= 4.4 (macOS: встановити через brew)" >&2; exit 2
fi

# Захист від прод-баз (ім'я бази + PGHOST за ODOO_ALLOWED_HOSTS; C-00 гарантує, що db_host в ODOO_CONF — той самий непродовий сервер): дозволено лише test-*(без «prod» в імені), test-pkg-*, demo-*, emu-*.
guard_db() {
  local db="${1:-}"
  if [[ -z "$db" ]]; then echo "FLOW_STOP: не задано ім'я бази" >&2; exit 2; fi
  case "$db" in
    *[Pp][Rr][Oo][Dd]*) echo "FLOW_STOP: ім'я бази '$db' містить prod; відмова (двозначне ім'я)" >&2; exit 2 ;;
    test-?*|test-pkg-?*|demo-?*|emu-?*) ;;
    *) echo "FLOW_STOP: база '$db' не відповідає test-<суфікс>|demo-<суфікс>|emu-<суфікс>; відмова (прод не чіпаємо)" >&2; exit 2 ;;
  esac
  if [[ ! "$db" =~ ^[A-Za-z0-9_-]+$ ]]; then
    echo "FLOW_STOP: недопустимі символи в імені бази '$db'" >&2; exit 2
  fi
  # Сервер: PGHOST (за замовчуванням localhost) має входити в ODOO_ALLOWED_HOSTS (список через кому або пробіл; задає C-00); не задано — відмова.
  if [[ -z "${ODOO_ALLOWED_HOSTS:-}" ]]; then echo "FLOW_STOP: не задано ODOO_ALLOWED_HOSTS (allow-list серверів БД)" >&2; exit 2; fi
  local h="${PGHOST:-localhost}" ok=0 a
  for a in ${ODOO_ALLOWED_HOSTS//,/ }; do [[ "$h" == "$a" ]] && ok=1; done
  if (( ! ok )); then echo "FLOW_STOP: сервер БД '$h' не в ODOO_ALLOWED_HOSTS; відмова" >&2; exit 2; fi
}

# Параметри середовища (задає C-00): ODOO_BIN, ODOO_ADDONS_PATH, ODOO_CONF (необов'язково),
# PGHOST/PGPORT/PGUSER/PGPASSWORD (стандартні змінні PostgreSQL-клієнтів).
ODOO_BIN="${ODOO_BIN:-odoo-bin}"
odoo_args() {
  ODOO_ARGS=()
  [[ -n "${ODOO_CONF:-}" ]] && ODOO_ARGS+=(-c "$ODOO_CONF")
  [[ -n "${ODOO_ADDONS_PATH:-}" ]] && ODOO_ARGS+=(--addons-path="$ODOO_ADDONS_PATH")
  return 0
}

# Перевірка, що модулі справді встановлені (Odoo для невідомого модуля пише лише WARNING і виходить з кодом 0,
# `-u` невстановленого модуля — тихий no-op). Таблицю ir_module_module і стан 'installed' C-00 звіряє з Odoo 19.
# Використання: require_installed <db> <m1,m2,...>; повертає 0 або друкує FAIL і повертає 1.
validate_mods() {
  local m
  IFS=',' read -ra _VML <<<"$1"
  for m in "${_VML[@]}"; do
    [[ "$m" =~ ^[a-z0-9_]+$ ]] || { echo "FLOW_STOP: недопустиме ім'я модуля '$m'" >&2; exit 2; }
  done
}
require_installed() {
  local db="$1" mods="$2" m st bad=0
  validate_mods "$mods"
  IFS=',' read -ra _ML <<<"$mods"
  for m in "${_ML[@]}"; do
    st="$(psql -d "$db" -Atc "select state from ir_module_module where name='$m'" 2>/dev/null || true)"
    if [[ "$st" != "installed" ]]; then echo "FAIL module '$m': стан '${st:-немає в базі}', очікується installed" >&2; bad=1; fi
  done
  return $bad
}
