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

# Редакція Odoo (К-06): ODOO_EDITION=ce|ee, за замовчуванням ce. Ядро пакета працює на CE; ee — підсилення td_*_ee.
# ee: ODOO_EE_ADDONS_PATH — каталог із модулями Enterprise (повний шлях; задає C-00/CI, лише якщо доступ до EE є).
# Немає доступу до EE -> код 3 і рядок "WARN ee-unavailable" (це НЕ PASS і не помилка пакета: EE-перевірка «не перевірено»).
# ce: каталог EE у ODOO_ADDONS_PATH заборонений (інакше «CE-прогін» мовчки бачить EE-модулі).
ODOO_EDITION="${ODOO_EDITION:-ce}"
check_edition() {
  case "$ODOO_EDITION" in
    ce)
      if [[ -n "${ODOO_EE_ADDONS_PATH:-}" ]]; then
        local p
        for p in $(printf '%s' "${ODOO_ADDONS_PATH:-}" | tr ',' ' '); do
          if [[ "${p%/}" == "${ODOO_EE_ADDONS_PATH%/}" ]]; then
            echo "FLOW_STOP: ODOO_EDITION=ce, але ODOO_EE_ADDONS_PATH входить до ODOO_ADDONS_PATH" >&2; exit 2
          fi
        done
      fi ;;
    ee)
      if [[ -z "${ODOO_EE_ADDONS_PATH:-}" || ! -d "${ODOO_EE_ADDONS_PATH}" ]]; then
        echo "WARN ee-unavailable: ODOO_EE_ADDONS_PATH не задано або каталогу немає; EE-перевірка не виконана (не перевірено)" >&2; exit 3
      fi ;;
    *) echo "FLOW_STOP: ODOO_EDITION='$ODOO_EDITION' (очікується ce|ee)" >&2; exit 2 ;;
  esac
  return 0
}

# Параметри odoo-bin. ee: до addons-path додається ODOO_EE_ADDONS_PATH. Мова: ODOO_LANG (напр. uk_UA) -> --load-language;
# ODOO_I18N_OVERWRITE=1 -> --i18n-overwrite (повторне оновлення з перезаписом перекладів: терміни нових view потрапляють у мову показу).
# Обидві опції взято з робочого еталона build_db.sh (зріз «меблі», Odoo 19); C-00 звіряє з `odoo-bin --help` (відкрите питання).
odoo_args() {
  ODOO_ARGS=()
  check_edition
  local ap="${ODOO_ADDONS_PATH:-}"
  [[ "$ODOO_EDITION" == "ee" ]] && ap="${ap:+$ap,}${ODOO_EE_ADDONS_PATH}"
  [[ -n "${ODOO_CONF:-}" ]] && ODOO_ARGS+=(-c "$ODOO_CONF")
  [[ -n "$ap" ]] && ODOO_ARGS+=(--addons-path="$ap")
  if [[ -n "${ODOO_LANG:-}" ]]; then
    [[ "$ODOO_LANG" =~ ^[a-z]{2,3}(_[A-Z]{2,4})?$ ]] || { echo "FLOW_STOP: недопустимий код мови '$ODOO_LANG'" >&2; exit 2; }
    ODOO_ARGS+=(--load-language="$ODOO_LANG")
  fi
  [[ "${ODOO_I18N_OVERWRITE:-0}" == "1" ]] && ODOO_ARGS+=(--i18n-overwrite)
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
