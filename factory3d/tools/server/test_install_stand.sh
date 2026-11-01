#!/usr/bin/env bash
# Проверка install_stand.sh БЕЗ системы: всё во временном TD_ROOT, systemd/apt/mosquitto не трогаются (--no-system),
# сеть не используется (адреса и порты вымышленные: 18094/18181/18087, 10.99.0.0/16), на реальный стенд (127.0.0.1:8081,
# /etc/td-stand) скрипт не смотрит. Запуск:  bash factory3d/tools/server/test_install_stand.sh
# Проверяет: «голый» повторный запуск сохраняет установленные значения (Odoo, порт BioStar, TD_IP_ALLOW, порт ретранслятора,
# SIM_ODOO_*) и не переписывает файлы; заданное отличающееся значение требует --confirm-change; порт 8081 не берётся по
# умолчанию, когда он занят; секреты не печатаются.
set -euo pipefail
for v in $(compgen -e | grep '^TD_' || true); do unset "$v"; done   # чужие TD_* (TD_ETC, TD_ODOO_URL…) не должны влиять на тест
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
SCRIPT="$HERE/install_stand.sh"
T="$(mktemp -d)"
trap 'rm -rf "$T"' EXIT
FAILS=0 TESTS=0
pass() { TESTS=$((TESTS + 1)); printf '  ok    %s\n' "$1"; }
fail() { TESTS=$((TESTS + 1)); FAILS=$((FAILS + 1)); printf '  FAIL  %s\n' "$1"; }
expect() { if eval "$2"; then pass "$1"; else fail "$1  [$2]"; fi; }

COL_TOK="colTOKENcolTOKENcolTOKENcolTOKEN0001"
SIM_TOK="simTOKENsimTOKENsimTOKENsimTOKEN0002"
REL_API="relAPIrelAPIrelAPIrelAPIrelAPI000003"
REL_SIM="relSIMrelSIMrelSIMrelSIMrelSIM000004"
APIKEY="odooKEYodooKEYodooKEYodooKEYodoo0005"

# мир: свой TD_ROOT на каждый сценарий; secrets-файл только с токенами (+ по требованию SIM_ODOO_*)
new_root() { # new_root ИМЯ [с_odoo]
    ROOT_D="$T/$1"; mkdir -p "$ROOT_D"
    SECRETS="$ROOT_D/secrets"
    printf 'TD_COLLECTOR_TOKEN=%s\nTD_SIM_API_TOKEN=%s\nTD_RELAY_API_TOKEN=%s\nTD_RELAY_SIM_TOKEN=%s\n' \
        "$COL_TOK" "$SIM_TOK" "$REL_API" "$REL_SIM" >"$SECRETS"
    if [[ "${2:-}" == odoo ]]; then
        printf 'SIM_ODOO_DB=odoo\nSIM_ODOO_USER=simreader\nSIM_ODOO_APIKEY=%s\n' "$APIKEY" >>"$SECRETS"
    fi
    chmod 600 "$SECRETS"
}

# run_fn КОД: исполняет код bash с подключённым (source) install_stand.sh в подоболочке с TD_ROOT
run_fn() {
    local code=$1
    ( set -euo pipefail
      set --                    # source не должен разбирать аргументы функции как флаги скрипта
      export TD_ROOT="$ROOT_D" TD_SECRETS_FILE="$SECRETS"
      # shellcheck disable=SC1090
      source "$SCRIPT"
      NO_SYSTEM=1 CHECK=0 NO_RELAY=0
      eval "$code" )
}

# «установленный» стенд (как после первой установки с явными значениями)
install_fixture() {
    run_fn 'TD_ODOO_URL=http://127.0.0.1:18094 TD_SIM_PORT_BIOSTAR_HTTP=18181 TD_IP_ALLOW=10.99.0.0/16 TD_SIM_PORT_GENSET_RELAY=18087 TD_PUSH_PORT=18080 TD_COLLECTOR_CODE=COL-T
           resolve_params; COL_TOKEN=$(secret_in TD_COLLECTOR_TOKEN "$COL_ENV" F3D_COLLECTOR_TOKEN); SIM_TOKEN=$(secret_in TD_SIM_API_TOKEN "$SIM_ENV" SIM_API_TOKEN)
           relay_tokens; resolve_sim_odoo; ensure_dirs; CHANGED_SIM=0 CHANGED_COL=0 CHANGED_RELAY=0; write_envs; install_units' >"$T/fixture.log" 2>&1 || { echo "fixture failed:"; tail -15 "$T/fixture.log"; exit 1; }
}

snap() { (cd "$ROOT_D" && find etc -type f ! -name secrets | LC_ALL=C sort | xargs sha256sum); }

echo "1. голый повторный запуск сохраняет установленное (реальная запись файлов)"
new_root bare odoo
install_fixture
before="$(snap)"
OUT="$(run_fn 'resolve_params
    COL_TOKEN=$(secret_in TD_COLLECTOR_TOKEN "$COL_ENV" F3D_COLLECTOR_TOKEN); SIM_TOKEN=$(secret_in TD_SIM_API_TOKEN "$SIM_ENV" SIM_API_TOKEN)
    relay_tokens; resolve_sim_odoo; CHANGED_SIM=0 CHANGED_COL=0 CHANGED_RELAY=0; write_envs; install_units
    echo "CH=$CHANGED_SIM$CHANGED_COL$CHANGED_RELAY"; echo "CHANGES=[$CHANGES]"; show_params' 2>&1)"
after="$(snap)"
expect "файлы env и unit не изменились" '[[ "$before" == "$after" ]]'
expect "службы не перезапускаются (CHANGED_*=000)" '[[ "$OUT" == *CH=000* ]]'
expect "нет конфликтов" '[[ "$OUT" == *"CHANGES=[]"* ]]'
expect "порт BioStar остался 18181, а не 8081" 'grep -qx "SIM_PORT_BIOSTAR_HTTP=18181" "$ROOT_D/etc/td-stand/iot-sim.env"'
expect "F3D_ODOO_URL остался :18094" 'grep -qx "F3D_ODOO_URL=http://127.0.0.1:18094" "$ROOT_D/etc/td-stand/collector.env"'
expect "IPAddressAllow=10.99.0.0/16 сохранён в unit" 'grep -qx "IPAddressAllow=10.99.0.0/16" "$ROOT_D/etc/systemd/system/td-iot-sim.service"'
expect "SIM_ODOO_* сохранены в iot-sim.env" 'grep -qx "SIM_ODOO_DB=odoo" "$ROOT_D/etc/td-stand/iot-sim.env" && grep -qx "SIM_ODOO_URL=http://127.0.0.1:18094" "$ROOT_D/etc/td-stand/iot-sim.env"'
expect "порт ретранслятора 18087 и push 18080 сохранены" 'grep -qx "RELAY_PORT=18087" "$ROOT_D/etc/td-stand/genset-relay.env" && grep -qx "F3D_HTTP_PUSH_PORT=18080" "$ROOT_D/etc/td-stand/collector.env"'
expect "show_params: источник «установлен»" '[[ "$OUT" == *"TD_SIM_PORT_BIOSTAR_HTTP"*"18181"*"установлен"* && "$OUT" == *"TD_IP_ALLOW"*"10.99.0.0/16"*"установлен"* ]]'

echo "2. --check (скрипт целиком): значения и источники, секреты не печатаются"
new_root check odoo
install_fixture
CHK() { TD_ROOT="$ROOT_D" TD_SECRETS_FILE="$SECRETS" bash "$SCRIPT" --check --no-system --no-mqtt "$@" 2>&1 || true; }
OUT="$(CHK)"
expect "--check печатает таблицу параметров" '[[ "$OUT" == *"параметры стенда"* && "$OUT" == *TD_ODOO_URL*http://127.0.0.1:18094*установлен* ]]'
expect "голый --check: BioStar 18181 установлен" '[[ "$OUT" == *TD_SIM_PORT_BIOSTAR_HTTP*18181*установлен* ]]'
expect "голый --check: без «ИЗМЕНЕНИЕ» и без препятствия-изменения" '[[ "$OUT" != *ИЗМЕНЕНИЕ* && "$OUT" != *confirm-change* ]]'
expect "секреты не печатаются" '[[ "$OUT" != *"$COL_TOK"* && "$OUT" != *"$SIM_TOK"* && "$OUT" != *"$REL_API"* && "$OUT" != *"$REL_SIM"* && "$OUT" != *"$APIKEY"* ]]'
expect "--check ничего не пишет" '[[ "$(snap)" == "$(snap)" ]]'

echo "3. заданное отличающееся значение требует --confirm-change"
before="$(snap)"
OUT="$(TD_SIM_PORT_BIOSTAR_HTTP=8081 CHK)"
expect "порт 8081 вместо 18181 — препятствие" '[[ "$OUT" == *ПРЕПЯТСТВИЕ*TD_SIM_PORT_BIOSTAR_HTTP*18181*8081*confirm-change* ]]'
expect "таблица помечает ИЗМЕНЕНИЕ" '[[ "$OUT" == *TD_SIM_PORT_BIOSTAR_HTTP*8081*задан*ИЗМЕНЕНИЕ* ]]'
OUT="$(TD_ODOO_URL=http://127.0.0.1:8069 TD_IP_ALLOW= CHK)"
expect "другой URL Odoo и пустой TD_IP_ALLOW — тоже изменения" '[[ "$OUT" == *"TD_ODOO_URL: установлено"* && "$OUT" == *"TD_IP_ALLOW: установлено «10.99.0.0/16»"* ]]'
OUT="$(TD_SIM_PORT_BIOSTAR_HTTP=18182 CHK --confirm-change)"
expect "--confirm-change: только предупреждение, не препятствие" '[[ "$OUT" == *"будет изменено (--confirm-change)"* && "$OUT" != *"ПРЕПЯТСТВИЕ TD_SIM"* && "$OUT" != *"ПРЕПЯТСТВИЕ TD_ODOO"* ]]'
OUT="$(TD_IP_ALLOW=10.99.0.0/16 TD_ODOO_URL=http://127.0.0.1:18094/ CHK)"
expect "то же значение (URL со слэшем) — не изменение" '[[ "$OUT" != *confirm-change* ]]'
expect "файлы не тронуты --check" '[[ "$before" == "$(snap)" ]]'

echo "4. первая установка: значения по умолчанию, 8081 не берётся, если занят"
new_root fresh
OUT="$(CHK)"
expect "по умолчанию: Odoo 8069, BioStar 8081, relay 8087, push 8080" '[[ "$OUT" == *TD_ODOO_URL*8069*"по умолчанию"* && "$OUT" == *TD_SIM_PORT_BIOSTAR_HTTP*8081*"по умолчанию"* && "$OUT" == *TD_SIM_PORT_GENSET_RELAY*8087* && "$OUT" == *TD_PUSH_PORT*8080* ]]'
expect "без SIM_ODOO_* — предупреждение" '[[ "$OUT" == *"SIM_ODOO_* не заданы"* ]]'
OUT="$(run_fn 'port_lines() { printf "%s\n" "tcp LISTEN 0 128 127.0.0.1:8081 0.0.0.0:* users:((\"relay\",pid=4242,fd=3))"; }
    have() { [[ $1 == ss ]] || command -v "$1" >/dev/null 2>&1; }
    resolve_params; check_biostar_port; echo "BLOCKERS=$BLOCKERS"' 2>&1)"
expect "8081 занят, значение не задано и не установлено — препятствие" '[[ "$OUT" == *ПРЕПЯТСТВИЕ*8081*TD_SIM_PORT_BIOSTAR_HTTP=8181* && "$OUT" == *BLOCKERS=1* ]]'
OUT="$(run_fn 'port_lines() { printf "%s\n" "tcp LISTEN 0 128 127.0.0.1:8081 0.0.0.0:* users:((\"relay\",pid=4242,fd=3))"; }
    have() { [[ $1 == ss ]] || command -v "$1" >/dev/null 2>&1; }
    TD_SIM_PORT_BIOSTAR_HTTP=8181; resolve_params; check_biostar_port; echo "BLOCKERS=$BLOCKERS"' 2>&1)"
expect "TD_SIM_PORT_BIOSTAR_HTTP=8181 при занятом 8081 — без препятствия" '[[ "$OUT" == *BLOCKERS=0* ]]'
OUT="$(run_fn 'port_lines() { printf "%s\n" "tcp LISTEN 0 128 127.0.0.1:18181 0.0.0.0:* users:((\"python3\",pid=4242,fd=3))"; }
    have() { [[ $1 == ss ]] || command -v "$1" >/dev/null 2>&1; }
    TD_SIM_PORT_BIOSTAR_HTTP=18181; resolve_params; SYS_ACTIVE=1; systemctl() { echo 777; }; check_biostar_port; echo "BLOCKERS=$BLOCKERS"' 2>&1)"
expect "работающая служба + занят новый порт чужим pid — препятствие" '[[ "$OUT" == *ПРЕПЯТСТВИЕ*18181* && "$OUT" == *BLOCKERS=1* ]]'

echo "5. SIM_ODOO_* из файла секретов попадают в iot-sim.env, apikey не печатается"
new_root simodoo odoo
OUT="$(CHK)"
expect "--check: SIM_ODOO_* приняты без вывода apikey" '[[ "$OUT" == *"SIM_ODOO_*: url="* && "$OUT" != *"$APIKEY"* && "$OUT" != *"SIM_ODOO_* не заданы"* ]]'
OUT="$(run_fn 'resolve_params; COL_TOKEN=x; SIM_TOKEN=y; R_API_TOKEN=a; R_SIM_TOKEN=b; resolve_sim_odoo; sim_extra_lines' 2>&1)"
expect "sim_extra_lines содержит SIM_ODOO_* и SIM_GENSET_RELAY_*, без пустых строк" '[[ "$OUT" == *SIM_GENSET_RELAY_URL* && "$OUT" == *SIM_ODOO_APIKEY=* && "$OUT" != *$'"'"'\n\n'"'"'* ]]'
new_root badodoo
printf 'SIM_ODOO_DB=odoo\n' >>"$SECRETS"
OUT="$(CHK)"
expect "неполный набор SIM_ODOO_* — препятствие" '[[ "$OUT" == *ПРЕПЯТСТВИЕ*SIM_ODOO_*нужны*все*три* ]]'

echo
echo "итого: $((TESTS - FAILS)) из $TESTS пройдено"
[[ $FAILS -eq 0 ]]
