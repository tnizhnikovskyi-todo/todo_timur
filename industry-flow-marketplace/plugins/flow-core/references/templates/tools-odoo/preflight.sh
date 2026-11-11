#!/usr/bin/env bash
# Передпольотна перевірка середовища C-00 (К-19, К-22).
# Використання: preflight.sh [--edition ce|ee|both] [--profile <access_profile>] [--needs odoo,browser,video,sources-push] [--step A-21]
# --profile = access_profile наряду (усі 8 з naryad-format.md: base|mail|research|research-internal|content|outreach|drive|repo):
#   research, outreach, drive, mail: лише bash і MANUAL-рядки, решта SKIP (Odoo/браузер/відео не потрібні).
#   base: група odoo (postgres, Odoo 19, addons-path, allow-list, редакція) без браузера й відео.
#   repo: група odoo (браузер і відео профілем НЕ вимагаються: ci-pipeline-builder, gates-aggregator, package-release-builder, skill-retro).
#   content: browser + video (шрифт, бренд-кіт); Odoo SKIP.
#   research-internal (A-03b, A-04): sources-push без FLOW_SOURCES_PUSH_ALLOWED=yes = FAIL; решта SKIP.
#   невідомий профіль: WARN і повна перевірка (не FAIL).
# --needs <групи через кому> замінює набір груп профілю (runner бере групи з картки кроку); групи: odoo, browser, video, sources-push.
# --step <код> -- основний спосіб для runner'а (мапа груп кроку), --needs -- ручне перевизначення. A-21 = odoo,browser,video; A-21c = browser,video; A-22 = odoo; A-03b/A-04 = sources-push; A-03c/A-01/A-05 = sources-push лише з --profile research-internal (збір internal-raw);
#   невідомий крок = лише набір профілю.
# Без --profile/--needs/--step -- повна перевірка (sources-push WARN).
# Вивід: JSON-список [{"id","status","msg"}] (status: PASS|FAIL|WARN|SKIP|MANUAL), код 1 при будь-якому FAIL, інакше 0.
# Без середовища скрипт НЕ падає: кожна відсутня річ — FAIL або WARN у JSON. Нічого не змінює й нікуди не підключається.
# FAIL => runner ставить наряд у waiting_human ДО витрати бюджету; WARN => крок можливий із застереженням у звіті (memo).
# Параметри — змінні середовища: ODOO_BIN, ODOO_ADDONS_PATH, ODOO_EDITION, ODOO_EE_ADDONS_PATH, ODOO_ALLOWED_HOSTS, PGHOST,
#   BRAND_KIT_DIR (каталог brand-todo/ для A-21c), FLOW_SOURCES_PUSH_ALLOWED=yes|no (рішення людини C-00: чи дозволено середовищу пушити research/sources/).
# Свідомо без `set -e`/`set -u`: збій однієї перевірки не обриває решту.
EDITION="${ODOO_EDITION:-ce}"
PROFILE=""; NEEDS=""; HAVE_NEEDS=0; UNKNOWN_PROFILE=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --edition) EDITION="${2:-ce}"; shift 2 || shift ;;
    --profile) PROFILE="${2:-}"; shift 2 || shift ;;
    --needs) NEEDS="${2:-}"; HAVE_NEEDS=1; shift 2 || shift ;;
    --step)
      case "${2:-}" in
        A-21) NEEDS="odoo,browser,video"; HAVE_NEEDS=1 ;;
        A-21c) NEEDS="browser,video"; HAVE_NEEDS=1 ;;
        A-22) NEEDS="odoo"; HAVE_NEEDS=1 ;;
        A-03b|A-04) NEEDS="sources-push"; HAVE_NEEDS=1 ;;
        A-03c|A-01|A-05) [[ "$PROFILE" == "research-internal" ]] && { NEEDS="sources-push"; HAVE_NEEDS=1; } ;;
      esac
      shift 2 || shift ;;
    *) shift ;;
  esac
done
OUT=(); BAD=0
jesc() { printf '%s' "$1" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g' | tr '\n\t' '  '; }
add() { # id status msg
  OUT+=("{\"id\":\"$(jesc "$1")\",\"status\":\"$2\",\"msg\":\"$(jesc "$3")\"}")
  [[ "$2" == "FAIL" ]] && BAD=1
  return 0
}
# need <група>: чи потрібна група перевірок (без профілю й без --needs -- усі, sources-push лише WARN)
need() {
  if (( HAVE_NEEDS )); then case ",$NEEDS," in *",$1,"*) return 0 ;; *) return 1 ;; esac; fi
  case "$PROFILE" in
    "") return 0 ;;
    research-internal) [[ "$1" == "sources-push" ]] ;;
    base|repo) [[ "$1" == "odoo" ]] ;;
    content) [[ "$1" == "browser" || "$1" == "video" ]] ;;
    research|outreach|drive|mail) return 1 ;;
    *) return 0 ;;
  esac
}
have() { command -v "$1" >/dev/null 2>&1; }

case "$PROFILE" in
  "") ;;
  base|mail|research|research-internal|content|outreach|drive|repo) add profile PASS "профіль наряду: $PROFILE${NEEDS:+; групи: $NEEDS}" ;;
  *) add profile WARN "профіль '$PROFILE' невідомий (очікується base|mail|research|research-internal|content|outreach|drive|repo): повна перевірка"; PROFILE=""; UNKNOWN_PROFILE=1 ;;
esac
# bash
if (( BASH_VERSINFO[0] > 4 || (BASH_VERSINFO[0] == 4 && BASH_VERSINFO[1] >= 4) )); then add bash PASS "bash ${BASH_VERSION}"
else add bash FAIL "потрібен bash >= 4.4 (є ${BASH_VERSION})"; fi
# PostgreSQL
if ! need odoo; then add postgres-clients SKIP "не потрібно профілю $PROFILE"; else
miss=""; for t in createdb dropdb psql; do have "$t" || miss="$miss $t"; done
[[ -z "$miss" ]] && add postgres-clients PASS "createdb, dropdb, psql" || add postgres-clients FAIL "немає:$miss"
fi
# Odoo 19 (редакція CE за замовчуванням)
ob="${ODOO_BIN:-odoo-bin}"
if ! need odoo; then add odoo19 SKIP "не потрібно профілю $PROFILE"; add addons-path SKIP "не потрібно профілю $PROFILE"
else
if have "$ob" || [[ -x "$ob" ]]; then
  if have timeout; then ver="$(timeout 20 "$ob" --version 2>/dev/null | head -1)"; else ver="$("$ob" --version 2>/dev/null | head -1)"; fi
  if [[ "$ver" =~ (^|[^0-9])19\.[0-9] ]]; then add odoo19 PASS "ODOO_BIN: $ver"
  else add odoo19 WARN "ODOO_BIN знайдено, але версія 19 не підтверджена виводом --version ('${ver:-порожньо}'); звірити вручну"; fi
else add odoo19 FAIL "ODOO_BIN ('$ob') не знайдено: потрібен локальний Odoo 19 CE (tools/odoo)"; fi
[[ -n "${ODOO_ADDONS_PATH:-}" ]] && add addons-path PASS "ODOO_ADDONS_PATH задано" || add addons-path FAIL "ODOO_ADDONS_PATH не задано"
fi
# Allow-list серверів БД
if ! need odoo; then add allowed-hosts SKIP "не потрібно профілю $PROFILE"
elif [[ -z "${ODOO_ALLOWED_HOSTS:-}" ]]; then add allowed-hosts FAIL "ODOO_ALLOWED_HOSTS не задано (guard_db відмовить)"
else
  ok=0; h="${PGHOST:-localhost}"; for a in ${ODOO_ALLOWED_HOSTS//,/ }; do [[ "$h" == "$a" ]] && ok=1; done
  (( ok )) && add allowed-hosts PASS "PGHOST '$h' у allow-list" || add allowed-hosts FAIL "PGHOST '$h' не в ODOO_ALLOWED_HOSTS"
fi
# Опції odoo-bin для мови показу (reset.sh --lang / install.sh --lang): звірка з --help
if need odoo && { have "$ob" || [[ -x "$ob" ]]; }; then
  oh="$("$ob" --help 2>/dev/null)"
  if [[ -z "$oh" ]]; then add odoo-lang-opts WARN "odoo-bin --help порожній: --load-language/--i18n-overwrite не звірено"
  elif grep -q -- '--load-language' <<<"$oh" && grep -q -- '--i18n-overwrite' <<<"$oh"; then add odoo-lang-opts PASS "odoo-bin підтримує --load-language і --i18n-overwrite"
  else add odoo-lang-opts WARN "у odoo-bin --help немає --load-language або --i18n-overwrite: install.sh/reset.sh --lang не працюватимуть, адаптувати (C-00)"; fi
fi
# Копія check_core_deps.py (C-03, К-06): кладе C-00
if need odoo; then
  if [[ -f "$(dirname "${BASH_SOURCE[0]}")/check_core_deps.py" ]]; then add core-deps-script PASS "tools/odoo/check_core_deps.py є"
  else add core-deps-script WARN "немає tools/odoo/check_core_deps.py: C-00 копіює його зі складу ci-pipeline-builder (інакше C-03 -> escalated)"; fi
fi
# Редакції (both = ce + ee: типове значення анкети та входу CI)
edition_ee() {
  if [[ -n "${ODOO_EE_ADDONS_PATH:-}" && -d "${ODOO_EE_ADDONS_PATH}" ]]; then add edition-ee PASS "ODOO_EE_ADDONS_PATH доступний"
  else add edition-ee WARN "ee-unavailable: доступу до EE немає; EE-твердження лише з документації («не перевірено»)"; fi
}
if ! need odoo; then add edition SKIP "не потрібно профілю $PROFILE"; else
case "$EDITION" in
  ce) add edition-ce PASS "редакція ce (ядро пакета)" ;;
  ee) edition_ee ;;
  both) add edition-ce PASS "редакція ce (ядро пакета)"; edition_ee ;;
  *) add edition FAIL "edition='$EDITION' (очікується ce|ee|both)" ;;
esac
fi
# Браузер, відео, шрифт, бренд (A-21, A-21c)
if ! need browser; then add playwright SKIP "не потрібно профілю $PROFILE"; add chromium SKIP "не потрібно профілю $PROFILE"
else
if have node && node -e "require.resolve('playwright')" >/dev/null 2>&1; then add playwright PASS "node + playwright"
elif have python3 && python3 -I -c "import playwright" >/dev/null 2>&1; then add playwright PASS "python playwright"
else add playwright FAIL "Playwright не знайдено (node або python)"; fi
if have chromium || have chromium-browser || have google-chrome || ls "${PLAYWRIGHT_BROWSERS_PATH:-$HOME/.cache/ms-playwright}"/chromium* >/dev/null 2>&1; then add chromium PASS "Chromium знайдено"
else add chromium FAIL "Chromium не знайдено"; fi
fi
if ! need video; then add ffmpeg SKIP "не потрібно профілю $PROFILE"; add font-open-sans SKIP "не потрібно профілю $PROFILE"; add brand-kit SKIP "не потрібно профілю $PROFILE"
else
if have ffmpeg && have ffprobe; then add ffmpeg PASS "ffmpeg, ffprobe"; else add ffmpeg FAIL "потрібні ffmpeg і ffprobe (A-21, A-21c)"; fi
if have fc-list && fc-list 2>/dev/null | grep -qi "open sans"; then add font-open-sans PASS "Open Sans"; else add font-open-sans WARN "шрифт Open Sans не знайдено (бренд ToDo); fc-list недоступний або шрифту немає"; fi
if [[ -n "${BRAND_KIT_DIR:-}" && -d "$BRAND_KIT_DIR" ]]; then add brand-kit PASS "brand-todo: $BRAND_KIT_DIR"; else add brand-kit WARN "BRAND_KIT_DIR не задано або каталогу немає"; fi
fi
# Дозвіл на push research/sources/ (К-07, К-19): рішення людини, скрипт його не вгадує
if [[ "${FLOW_SOURCES_PUSH_ALLOWED:-}" == "yes" ]]; then add sources-push PASS "C-00 підтвердив дозвіл середовища на push research/sources/"
elif need sources-push && (( HAVE_NEEDS || ${#PROFILE} )); then add sources-push FAIL "дозвіл на push research/sources/ не підтверджено (FLOW_SOURCES_PUSH_ALLOWED=yes задає C-00): internal-raw не можна буде запушити, у хмарному контейнері він зникне; наряд -> waiting_human до витрати бюджету"
elif [[ -n "$PROFILE" || $HAVE_NEEDS -eq 1 ]]; then add sources-push SKIP "не потрібно профілю $PROFILE"
else add sources-push WARN "дозвіл на push research/sources/ не підтверджено (FLOW_SOURCES_PUSH_ALLOWED=yes задає C-00): sources/ лишити локально, не пушити"; fi
# Те, що скрипт перевірити не може
if [[ -z "$PROFILE" || "$PROFILE" == "research-internal" ]]; then
add own-erp MANUAL "alias own-erp у odoo-mcp (лише читання) — звірити list_odoo_connections у профілі research-internal"
add fathom-unitalk-read MANUAL "Fathom, Unitalk (лише наявні транскрипти) — підключення за профілем research-internal"
fi
add artifact-publish MANUAL "публікація Artifact доступна середовищу (A-20c)"

printf '[%s]\n' "$(IFS=,; echo "${OUT[*]}")"
exit $BAD
