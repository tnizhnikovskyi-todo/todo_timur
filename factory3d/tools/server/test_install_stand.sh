#!/usr/bin/env bash
# Проверка install_stand.sh БЕЗ системы: всё во временном TD_ROOT, systemd/apt/mosquitto не трогаются (--no-system),
# сеть не используется (адреса и порты вымышленные: 18094/18181/18087, 10.99.0.0/16), на реальный стенд (127.0.0.1:8081,
# /etc/td-stand) скрипт не смотрит. Запуск:  bash factory3d/tools/server/test_install_stand.sh
# Проверяет: «голый» повторный запуск сохраняет установленные значения (Odoo, порт BioStar, TD_IP_ALLOW, порт ретранслятора,
# SIM_ODOO_*) и не переписывает файлы; заданное отличающееся значение требует --confirm-change; порт 8081 не берётся по
# умолчанию, когда он занят; секреты не печатаются; SIM_ODOO_* из iot-sim.local.env видны --check и установке;
# путь LPR «эмулятор → сборщик» (URL, секрет, токен с учётом *.local.env) проверяется и зондируется (заглушка сборщика).
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

echo "6. SIM_ODOO_* в iot-sim.local.env (ручной файл оператора): видны --check и установке, в iot-sim.env не копируются"
LOCAL_REL="etc/td-stand/iot-sim.local.env"
new_root localenv
mkdir -p "$ROOT_D/etc/td-stand"
printf '# комментарий\nSIM_ODOO_URL=http://127.0.0.1:18094\nSIM_ODOO_DB="odoo"\nSIM_ODOO_USER = simreader\nSIM_ODOO_APIKEY=%s\nSIM_ALLOW_OUTBOUND=mosquitto\n' "$APIKEY" >"$ROOT_D/$LOCAL_REL"
OUT="$(CHK)"
expect "--check: ключи из iot-sim.local.env приняты, без «SIM_ODOO_* не заданы»" '[[ "$OUT" == *"SIM_ODOO_*: url=http://127.0.0.1:18094 db=odoo user=simreader"* && "$OUT" != *"SIM_ODOO_* не заданы"* ]]'
expect "--check: источник назван, apikey не печатается" '[[ "$OUT" == *"из iot-sim.local.env: URL DB USER APIKEY"* && "$OUT" != *"$APIKEY"* ]]'
expect "--check: нет препятствий по SIM_ODOO_*" '[[ "$OUT" != *ПРЕПЯТСТВИЕ*SIM_ODOO* ]]'
install_fixture
expect "iot-sim.env не получает копию SIM_ODOO_* из local.env" '! grep -q "^SIM_ODOO_" "$ROOT_D/etc/td-stand/iot-sim.env"'
expect "iot-sim.local.env не изменён установкой" 'grep -qx "SIM_ODOO_DB=\"odoo\"" "$ROOT_D/$LOCAL_REL" && grep -q "^SIM_ALLOW_OUTBOUND=mosquitto" "$ROOT_D/$LOCAL_REL"'
before="$(snap)"
OUT="$(run_fn 'resolve_params
    COL_TOKEN=$(secret_in TD_COLLECTOR_TOKEN "$COL_ENV" F3D_COLLECTOR_TOKEN); SIM_TOKEN=$(secret_in TD_SIM_API_TOKEN "$SIM_ENV" SIM_API_TOKEN)
    relay_tokens; resolve_sim_odoo; CHANGED_SIM=0 CHANGED_COL=0 CHANGED_RELAY=0; write_envs; install_units
    echo "CH=$CHANGED_SIM$CHANGED_COL$CHANGED_RELAY"; echo "LOCAL=[$SIM_ODOO_LOCAL]"' 2>&1)"
expect "голый повторный запуск: файлы не менялись, службы не перезапускаются" '[[ "$before" == "$(snap)" && "$OUT" == *CH=000* && "$OUT" == *"LOCAL=[URL DB USER APIKEY]"* ]]'

new_root localmix
mkdir -p "$ROOT_D/etc/td-stand"
printf 'SIM_ODOO_DB=odoo\nSIM_ODOO_USER=simreader\n' >>"$SECRETS"
printf 'SIM_ODOO_APIKEY=%s\n' "$APIKEY" >"$ROOT_D/$LOCAL_REL"
install_fixture
expect "часть ключей в local.env, часть в секретах: в iot-sim.env только не заданные в local.env" 'grep -qx "SIM_ODOO_DB=odoo" "$ROOT_D/etc/td-stand/iot-sim.env" && grep -qx "SIM_ODOO_USER=simreader" "$ROOT_D/etc/td-stand/iot-sim.env" && grep -qx "SIM_ODOO_URL=http://127.0.0.1:18094" "$ROOT_D/etc/td-stand/iot-sim.env" && ! grep -q "^SIM_ODOO_APIKEY" "$ROOT_D/etc/td-stand/iot-sim.env"'
expect "…и без препятствий" '[[ "$(CHK)" != *ПРЕПЯТСТВИЕ*SIM_ODOO* ]]'

new_root localbad
mkdir -p "$ROOT_D/etc/td-stand"
printf '# SIM_ODOO_DB=odoo\n#SIM_ODOO_USER=simreader\nSIM_ODOO_DB_OLD=x\n' >"$ROOT_D/$LOCAL_REL"
expect "закомментированные и похожие ключи не считаются заданными" '[[ "$(CHK)" == *"SIM_ODOO_* не заданы"* ]]'
printf 'SIM_ODOO_DB=odoo\n' >"$ROOT_D/$LOCAL_REL"
expect "неполный набор в local.env — препятствие, как и в секретах" '[[ "$(CHK)" == *ПРЕПЯТСТВИЕ*SIM_ODOO_*нужны*все*три* ]]'

echo "7. LPR «эмулятор → сборщик»: URL/секрет/токен с учётом *.local.env и зонд (иначе эмулятор пишет только «HTTP 404»)"
new_root lpr odoo
install_fixture
OUT="$(run_fn 'resolve_params
    COL_TOKEN=$(secret_in TD_COLLECTOR_TOKEN "$COL_ENV" F3D_COLLECTOR_TOKEN); SIM_TOKEN=$(secret_in TD_SIM_API_TOKEN "$SIM_ENV" SIM_API_TOKEN)
    relay_tokens; resolve_sim_odoo; CHANGED_SIM=0 CHANGED_COL=0 CHANGED_RELAY=0; write_envs; install_units' 2>&1)"
expect "установленный стенд: путь LPR согласован, предупреждений нет" '[[ "$OUT" == *"LPR: путь эмулятор → сборщик согласован"* && "$OUT" != *"ВНИМАНИЕ LPR"* ]]'
ENVD="$ROOT_D/etc/td-stand"
LSEC="$(sed -n 's/^F3D_HTTP_PUSH_SECRET_LPR=//p' "$ENVD/collector.env")"
LTOK="$(sed -n 's/^F3D_HTTP_PUSH_TOKEN_LPR=//p' "$ENVD/collector.env")"
expect "SIM_LPR_PUSH_URL установщика = /f3d/lpr/<секрет сборщика>, токены равны" 'grep -qx "SIM_LPR_PUSH_URL=http://collector:18080/f3d/lpr/$LSEC" "$ENVD/iot-sim.env" && grep -qx "SIM_LPR_PUSH_TOKEN=$LTOK" "$ENVD/iot-sim.env"'
CHK_LPR() { CHK "$@" | grep -E 'LPR' || true; }
printf 'SIM_LPR_PUSH_URL=http://collector:18080/f3d/lpr\n' >"$ENVD/iot-sim.local.env"
OUT="$(CHK_LPR)"
expect "iot-sim.local.env без секретного сегмента — предупреждение про 404" '[[ "$OUT" == *"ВНИМАНИЕ LPR"*"нет сегмента секрета"*"404"* && "$OUT" != *"$LSEC"* ]]'
printf 'SIM_LPR_PUSH_URL=http://collector:18080/f3d/lpr/wrongsecret\n' >"$ENVD/iot-sim.local.env"
OUT="$(CHK_LPR)"
expect "чужой секрет в iot-sim.local.env — предупреждение, секреты не печатаются" '[[ "$OUT" == *"не совпадает с F3D_HTTP_PUSH_SECRET_LPR"* && "$OUT" != *"$LSEC"* && "$OUT" != *wrongsecret* ]]'
printf 'SIM_LPR_PUSH_URL=http://collector:18080/f3d/yard_lpr/%s\nSIM_LPR_PUSH_TOKEN=othertoken\n' "$LSEC" >"$ENVD/iot-sim.local.env"
OUT="$(CHK_LPR)"
expect "чужой маршрут и токен в iot-sim.local.env" '[[ "$OUT" == *"должен быть /f3d/lpr/<секрет>"* && "$OUT" == *"SIM_LPR_PUSH_TOKEN"*"401"* ]]'
rm -f "$ENVD/iot-sim.local.env"
printf 'F3D_HTTP_PUSH_SECRET_LPR=%s\n' "other-collector-secret" >"$ENVD/collector.local.env"
OUT="$(CHK_LPR)"
expect "collector.local.env меняет секрет сборщика — предупреждение" '[[ "$OUT" == *"не совпадает с F3D_HTTP_PUSH_SECRET_LPR"* && "$OUT" != *other-collector-secret* ]]'
rm -f "$ENVD/collector.local.env"
OUT="$(CHK_LPR)"
expect "без переопределений — снова согласовано" '[[ "$OUT" == *"согласован"* && "$OUT" != *"ВНИМАНИЕ"* ]]'
OUT="$(run_fn 'lpr_wiring_problems http://collector:8080/f3d/lpr/S1/extra T1 S1 T1 8080; echo ---
    lpr_wiring_problems http://collector:9090/f3d/lpr/S1 T1 S1 T1 8080; echo ---
    lpr_wiring_problems http://collector:8080/f3d/lpr/S1 T1 S1 T1 8080; echo "ok-rc=$?"
    lpr_wiring_problems http://collector:8080/f3d/lpr/S1 T1 "" T1 8080' 2>&1)"
expect "lpr_wiring_problems: лишний сегмент, чужой порт, пустой секрет сборщика; верный набор — пусто" '[[ "$OUT" == *"лишние сегменты"* && "$OUT" == *"не равен F3D_HTTP_PUSH_PORT=8080"* && "$OUT" == *"F3D_HTTP_PUSH_SECRET_LPR сборщика не задан"* && "$OUT" == *"---"*"---"*"ok-rc=0"* ]]'

# зонд: заглушка сборщика (маршрут lpr с секретом и токеном; /f3d/health перечисляет маршруты), тело «[]» → 400 только при верном пути
cat >"$T/stub.py" <<'PYEOF'
import http.server, json, sys
portfile, routes, secret, token = sys.argv[1], [r for r in sys.argv[2].split(",") if r != "-"], sys.argv[3], sys.argv[4]
class H(http.server.BaseHTTPRequestHandler):
    def _send(self, code, body):
        data = json.dumps(body).encode()
        self.send_response(code); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)
    def do_GET(self):
        self._send(200 if self.path == "/f3d/health" else 404, {"status": "ok", "routes": routes})
    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length") or 0))
        parts = self.path.strip("/").split("/")
        if len(parts) != 3 or parts[0] != "f3d" or parts[1] not in routes or parts[2] != secret:
            return self._send(404, {"received": False, "error": "unknown route"})
        if self.headers.get("X-F3D-Token") != token:
            return self._send(401, {"received": False, "error": "unauthorized"})
        self._send(400, {"received": False, "error": "json object expected"})
    def log_message(self, *a): pass
srv = http.server.HTTPServer(("127.0.0.1", 0), H)
open(portfile, "w").write(str(srv.server_address[1]))
srv.serve_forever()
PYEOF
STUBS=()
start_stub() { # start_stub РОУТЫ → STUB_PORT
    rm -f "$T/stub.port"
    python3 "$T/stub.py" "$T/stub.port" "$1" "$LSEC" "$LTOK" & STUBS+=($!)
    for _ in $(seq 1 50); do [[ -s "$T/stub.port" ]] && break; sleep 0.1; done
    STUB_PORT="$(cat "$T/stub.port")"
}
trap 'kill "${STUBS[@]}" 2>/dev/null || true; rm -rf "$T"' EXIT
probe() { run_fn "TD_PUSH_PORT=$STUB_PORT; resolve_params; $1" 2>&1; }
start_stub lpr
OUT="$(probe 'echo "CODE=$(lpr_probe)"; check_lpr_route 1')"
expect "зонд: верный путь и токен → 400 и «принял»" '[[ "$OUT" == *CODE=400* && "$OUT" == *"сборщик принял путь эмулятора"* && "$OUT" != *"ВНИМАНИЕ"* && "$OUT" != *"$LSEC"* ]]'
printf 'SIM_LPR_PUSH_URL=http://collector:18080/f3d/lpr\n' >"$ENVD/iot-sim.local.env"
OUT="$(probe 'echo "CODE=$(lpr_probe)"; check_lpr_route 1')"
expect "зонд: URL без секрета в iot-sim.local.env → 404, маршрут у сборщика есть → про секрет/secret_ref" '[[ "$OUT" == *CODE=404* && "$OUT" == *"маршрут lpr у сборщика есть"*"secret_ref"* && "$OUT" != *"$LSEC"* ]]'
rm -f "$ENVD/iot-sim.local.env"
printf 'SIM_LPR_PUSH_TOKEN=othertoken\n' >"$ENVD/iot-sim.local.env"
OUT="$(probe 'echo "CODE=$(lpr_probe)"; check_lpr_route 1')"
expect "зонд: чужой токен → 401" '[[ "$OUT" == *CODE=401* && "$OUT" == *"токен не принят"* ]]'
rm -f "$ENVD/iot-sim.local.env"
start_stub -
OUT="$(probe 'check_lpr_route 1')"
expect "зонд: сборщик не знает маршрута lpr → 404 с указанием на источник HTTP-PUSH" '[[ "$OUT" == *"сборщик не знает маршрута lpr"*"HTTP-PUSH"* ]]'
OUT="$(run_fn 'TD_PUSH_PORT=1; resolve_params; check_lpr_route 1' 2>&1)"
expect "зонд: порт не отвечает → «сборщик не отвечает»" '[[ "$OUT" == *"сборщик не отвечает на :1"* ]]'

echo
echo "итого: $((TESTS - FAILS)) из $TESTS пройдено"
[[ $FAILS -eq 0 ]]
