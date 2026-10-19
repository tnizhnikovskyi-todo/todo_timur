#!/usr/bin/env bash
# Постоянный «стенд» на тестовом сервере (решение E-11): эмулятор оборудования iot_sim + сборщик сигналов
# (collector и плагины) как службы systemd. Эмулятор отдаёт данные по протоколам, сборщик читает их и шлёт в Odoo.
#
#   sudo TD_SECRETS_FILE=/root/td-stand.secrets bash install_stand.sh            # установить / обновить
#   sudo bash install_stand.sh --check                                           # только показать план, ничего не менять
#   sudo bash install_stand.sh --status                                          # состояние служб и данных
#   sudo bash install_stand.sh --uninstall [--purge]                             # снять службы и venv (Odoo и БД не трогает)
#
# Что делает (идемпотентно; повторный запуск = обновление кода из репозитория):
#   1. пользователь td-stand, каталоги /opt/td-stand, /etc/td-stand, /var/lib/td-stand;
#   2. venv: /opt/td-stand/venv-sim (эмулятор) и /opt/td-stand/venv-collector (сборщик + плагины bms, yard,
#      machine_connect, td_collector_energy) из factory3d/services вашего git-клона (по умолчанию /mnt/f3d-addons);
#   3. /etc/td-stand/iot-sim.env и collector.env (0640 root:td-stand); токен сборщика берётся из TD_COLLECTOR_TOKEN
#      (или файла), остальные секреты стенда генерируются один раз и дальше не меняются; в репозитории секретов нет;
#   4. псевдонимы iot-sim, mosquitto, collector -> 127.0.0.1 в /etc/hosts (блок «# BEGIN td-stand»);
#   5. брокер MQTT: пакет mosquitto, слушает только 127.0.0.1:1883, пользователи sim и collector (--no-mqtt — пропустить);
#   6. службы td-iot-sim.service и td-collector.service: Restart=always, пользователь td-stand, журнал в journald,
#      лимиты памяти/CPU/процессов, доступ в сеть только к loopback (если Odoo на этой машине);
#   7. enable --now и печать состояния.
#
# Секреты, которые выдаёт менеджер (stand_odoo_setup.py печатает их один раз), в порядке приоритета:
#   переменная окружения TD_COLLECTOR_TOKEN / TD_SIM_API_TOKEN;
#   файл TD_COLLECTOR_TOKEN_FILE / TD_SIM_API_TOKEN_FILE (в файле только значение);
#   файл TD_SECRETS_FILE (строки KEY=VALUE, по умолчанию /etc/td-stand/secrets.env, если есть);
#   значение, уже записанное в /etc/td-stand/*.env прошлым запуском.
#
# Переменные (значения по умолчанию подходят для timur-o19demo): TD_REPO (по умолчанию — клон, в котором лежит этот
#   скрипт), TD_ODOO_URL, TD_ODOO_SERVICE, TD_PYTHON, TD_USER, TD_PUSH_PORT, TD_SIM_PORT_BIOSTAR_HTTP (HTTP-порт
#   эмулятора BioStar, по умолчанию 8081; пишется в iot-sim.env как SIM_PORT_BIOSTAR_HTTP), TD_IP_FILTER (0 — не
#   ограничивать сеть служб), TD_IP_ALLOW (доп. сети в фильтр служб, например 172.16.0.0/12 — чтобы Odoo из
#   контейнера Docker достучался до эмулятора; через пробел), TD_HARDEN (0 — без песочницы systemd), TD_ROOT (всё в подкаталог, для проверки без системы).
# Пример (Odoo в Docker на 8094, порт 8081 занят ретранслятором SmartGen):
#   sudo TD_SECRETS_FILE=/root/td-stand.secrets TD_ODOO_URL=http://127.0.0.1:8094 TD_SIM_PORT_BIOSTAR_HTTP=8181 \
#       bash /opt/timur-o19/timur-o19e/git/todo_timur/factory3d/tools/server/install_stand.sh --check
# Режимы проверки: --no-system — не трогать пользователей, apt, systemd, mosquitto (файлы пишутся под TD_ROOT).
set -euo pipefail
umask 022

# ---------------------------------------------------------------- аргументы
CHECK=0 UNINSTALL=0 PURGE=0 STATUS_ONLY=0 NO_MQTT=0 NO_SYSTEM=0
usage() { sed -n '2,/^set -euo/p' "${BASH_SOURCE[0]}" | sed '$d; s/^# \{0,1\}//'; }
for arg in "$@"; do
    case "$arg" in
        --check | --dry-run) CHECK=1 ;;
        --uninstall) UNINSTALL=1 ;;
        --purge) PURGE=1 ;;
        --status) STATUS_ONLY=1 ;;
        --no-mqtt) NO_MQTT=1 ;;
        --no-system) NO_SYSTEM=1 ;;
        -h | --help) usage; exit 0 ;;
        *) echo "Неизвестный аргумент: $arg (см. --help)" >&2; exit 2 ;;
    esac
done

# ---------------------------------------------------------------- параметры
SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
TD_REPO="${TD_REPO:-$(cd "$SELF_DIR/../../.." && pwd -P)}"
[[ -d "$TD_REPO/factory3d/services" ]] || TD_REPO=/mnt/f3d-addons
SERVICES="$TD_REPO/factory3d/services"
ROOT="${TD_ROOT:-}"                                  # префикс для проверки без системы; на сервере пустой
PREFIX="${TD_PREFIX:-$ROOT/opt/td-stand}"
ETC="${TD_ETC:-$ROOT/etc/td-stand}"
STATE="${TD_STATE:-$ROOT/var/lib/td-stand}"
UNIT_DIR="${TD_UNIT_DIR:-$ROOT/etc/systemd/system}"
HOSTS_FILE="${TD_HOSTS_FILE:-$ROOT/etc/hosts}"
SVC_USER="${TD_USER:-td-stand}"
ODOO_URL="${TD_ODOO_URL:-http://127.0.0.1:8069}"
ODOO_URL="${ODOO_URL%/}"
ODOO_SERVICE="${TD_ODOO_SERVICE:-odoo}"
COLLECTOR_CODE="${TD_COLLECTOR_CODE:-COL-MAIN}"
IP_FILTER="${TD_IP_FILTER:-1}"
IP_ALLOW_EXTRA="${TD_IP_ALLOW:-}"                      # доп. сети для фильтра служб, напр. 172.16.0.0/12 (Odoo в Docker → эмулятор)
HARDEN="${TD_HARDEN:-1}"                             # 0 — без песочницы mount-namespace (LXC и т. п., status=226/NAMESPACE)
SECRETS_FILE="${TD_SECRETS_FILE:-/etc/td-stand/secrets.env}"
HOSTS_NAMES="iot-sim mosquitto collector"
MQ_CONF="${TD_MOSQUITTO_CONF:-/etc/mosquitto/conf.d/td-stand.conf}"
MQ_PASSWD="${TD_MOSQUITTO_PASSWD:-/etc/mosquitto/td-stand.passwd}"
BIOSTAR_HTTP_PORT="${TD_SIM_PORT_BIOSTAR_HTTP:-8081}"   # 8081 на timur-o19demo занят ретранслятором SmartGen → 8181
PORTS_SIM_TCP="502 4001 4840 $BIOSTAR_HTTP_PORT 8082 8083 8090 8443 50000"
PUSH_PORT="${TD_PUSH_PORT:-8080}"
PORTS_COL_TCP="$PUSH_PORT 9108"
RECIPE=3                                             # версия способа установки: меняется — venv пересобираются
COL_PLUGINS="f3d_collector_bms f3d_collector_yard machine_connect td_collector_energy"   # плагины сборщика (W2: energy_ctl)
SIM_ENV="$ETC/iot-sim.env"
COL_ENV="$ETC/collector.env"

WARNS=0 BLOCKERS=0
log() { printf '%s  %s\n' "$(date +%H:%M:%S)" "$*"; }
ok() { printf '   ok       %s\n' "$*"; }
plan() { printf '   БУДЕТ    %s\n' "$*"; }
warn() { printf '   ВНИМАНИЕ %s\n' "$*" >&2; WARNS=$((WARNS + 1)); }
block() { printf '   ПРЕПЯТСТВИЕ %s\n' "$*" >&2; BLOCKERS=$((BLOCKERS + 1)); }
die() { printf '%s  ОШИБКА: %s\n' "$(date +%H:%M:%S)" "$*" >&2; exit 1; }
for net in $IP_ALLOW_EXTRA; do
    [[ "$net" =~ ^[0-9]{1,3}(\.[0-9]{1,3}){3}(/[0-9]{1,2})?$ || "$net" =~ ^[0-9a-fA-F]*:[0-9a-fA-F:]*(/[0-9]{1,3})?$ ]] \
        || die "TD_IP_ALLOW: «$net» — нужна сеть вида 172.16.0.0/12 (несколько — через пробел)"
done
[[ "$BIOSTAR_HTTP_PORT" =~ ^[0-9]+$ ]] && ((BIOSTAR_HTTP_PORT >= 1 && BIOSTAR_HTTP_PORT <= 65535)) \
    || die "TD_SIM_PORT_BIOSTAR_HTTP=$BIOSTAR_HTTP_PORT: нужен номер порта 1…65535"
case " 502 4001 4840 8082 8083 8090 8443 50000 $PUSH_PORT 9108 " in
    *" $BIOSTAR_HTTP_PORT "*) die "TD_SIM_PORT_BIOSTAR_HTTP=$BIOSTAR_HTTP_PORT совпадает с другим портом стенда" ;;
esac
have() { command -v "$1" >/dev/null 2>&1; }
real() { [[ $CHECK -eq 0 ]]; }                       # true, когда реально меняем систему
sysctl_on() { [[ $NO_SYSTEM -eq 0 ]] && have systemctl && [[ -d /run/systemd/system ]]; }
git_() { git -c safe.directory='*' -C "$TD_REPO" "$@"; }
rand() { head -c 24 /dev/urandom | od -An -tx1 | tr -d ' \n'; }
valid_secret() { [[ "$1" =~ ^[A-Za-z0-9._~+/=-]{32,256}$ ]]; }

# ---------------------------------------------------------------- утилиты файлов и секретов
# env_get ФАЙЛ КЛЮЧ — значение из env-файла (пусто, если нет или нет прав).
env_get() { [[ -r "$1" ]] && sed -n "s/^$2=//p" "$1" | tail -1 || true; }

# kv_get ФАЙЛ КЛЮЧ — то же для файла секретов от менеджера (KEY=VALUE, кавычки и пробелы по краям срезаются).
kv_get() {
    [[ -r "$1" ]] || return 0
    sed -n "s/^[[:space:]]*$2[[:space:]]*=[[:space:]]*//p" "$1" | tail -1 | sed -E "s/[[:space:]]+\$//; s/^(['\"])(.*)\1\$/\2/"
}

# secret_in NAME ТЕКУЩИЙ_ENV_ФАЙЛ ТЕКУЩИЙ_КЛЮЧ — найти значение секрета по приоритету (см. шапку).
secret_in() {
    local name=$1 envf=$2 key=$3 v="" f
    v="${!name:-}"
    if [[ -z "$v" ]]; then
        f="${name}_FILE"; f="${!f:-}"
        if [[ -n "$f" ]]; then [[ -r "$f" ]] || die "файл $f (${name}_FILE) не читается"; v="$(tr -d ' \t\r\n' <"$f")"; fi
    fi
    [[ -n "$v" ]] || v="$(kv_get "$SECRETS_FILE" "$name")"
    [[ -n "$v" ]] || v="$(env_get "$envf" "$key")"
    printf '%s' "$v"
}

# put_file ПУТЬ РЕЖИМ ВЛАДЕЛЕЦ ГРУППА — содержимое из stdin. Результат: PUT=same|new|changed. В режиме --check не пишет.
put_file() {
    local path=$1 mode=$2 owner=$3 group=$4 new tmp
    new="$(cat; printf x)"; new="${new%x}"
    if [[ -e "$path" ]] && printf '%s' "$new" | cmp -s - "$path" 2>/dev/null; then
        PUT=same; ok "$path"; return 0
    fi
    if [[ -e "$path" ]] || [[ -r "$path" ]]; then PUT=changed; else PUT=new; fi
    if ! real; then plan "$([[ $PUT == new ]] && echo создать || echo обновить) $path"; return 0; fi
    mkdir -p "$(dirname "$path")"
    tmp="$path.new.$$"
    (umask 077; printf '%s' "$new" >"$tmp")
    chmod "$mode" "$tmp"
    if [[ $NO_SYSTEM -eq 0 ]]; then chown "$owner:$group" "$tmp"; fi
    mv -f "$tmp" "$path"
    ok "$([[ $PUT == new ]] && echo создан || echo обновлён) $path"
}

# safe_rm ПУТЬ — rm -rf только для каталогов td-stand (защита от опечаток в TD_PREFIX и т. п.).
safe_rm() {
    local p=$1
    [[ -n "$p" && "$p" != / && "$(basename "$p")" == td-stand* ]] || die "отказываюсь удалять «$p»"
    [[ -e "$p" ]] || return 0
    if real; then rm -rf -- "$p"; ok "удалён $p"; else plan "удалить $p"; fi
}

# ---------------------------------------------------------------- проверки окружения
find_python() {
    local c
    for c in "${TD_PYTHON:-}" python3.12 python3.13 python3 python3.14; do
        if [[ -z "$c" ]] || ! have "$c"; then continue; fi
        if "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)' 2>/dev/null; then command -v "$c"; return 0; fi
    done
    return 1
}

port_lines() { have ss && ss -H -ltnup 2>/dev/null || true; }

# busy_ports ПРОТОКОЛ ПОРТЫ... — занятые порты с владельцем («502 (python3,pid=123)»)
busy_ports() {
    local proto=$1 p out; shift
    out="$(port_lines)"
    for p in "$@"; do
        printf '%s\n' "$out" | awk -v pr="$proto" -v p="$p" '$1 == pr && $5 ~ (":" p "$") {
            u = $7; gsub(/users:\(\(|\)\)|"/, "", u); print pr "/" p " (" (u == "" ? "?" : u) ")" }'
    done
}

check_ports() {
    local sim_active="" col_active="" lines
    if ! have ss; then warn "нет утилиты ss (пакет iproute2): занятость портов не проверена"; return 0; fi
    if sysctl_on; then
        if systemctl is-active -q td-iot-sim.service 2>/dev/null; then sim_active=1; fi
        if systemctl is-active -q td-collector.service 2>/dev/null; then col_active=1; fi
    fi
    if [[ -n "$sim_active" && -n "$col_active" ]]; then ok "порты стенда заняты нашими службами (они уже работают)"; return 0; fi
    lines=""
    # shellcheck disable=SC2086  # списки портов разбиваются по словам намеренно
    if [[ -z "$sim_active" ]]; then lines="$(busy_ports tcp $PORTS_SIM_TCP; busy_ports udp 47808 50001)"; fi
    # shellcheck disable=SC2086
    if [[ -z "$col_active" ]]; then lines="$lines$(busy_ports tcp $PORTS_COL_TCP)"; fi
    if [[ -n "$lines" ]]; then
        block "порты стенда заняты другими процессами: $(printf '%s' "$lines" | tr '\n' ' ')"
    else
        ok "порты стенда свободны (TCP $PORTS_SIM_TCP $PORTS_COL_TCP, UDP 47808 50001)"
    fi
}

odoo_probe() {
    local code tok
    code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 8 "$ODOO_URL/web/health" 2>/dev/null || true)"
    if [[ "$code" != 200 ]]; then
        warn "Odoo $ODOO_URL/web/health отвечает «${code:-нет ответа}»: сборщик будет копить данные в буфере до его запуска"
        return 0
    fi
    ok "Odoo отвечает: $ODOO_URL"
    if ! curl -sS --max-time 8 "$ODOO_URL/f3d/telemetry/health" 2>/dev/null | grep -q '"ok": *true'; then
        warn "маршрут /f3d/telemetry/health не отвечает ok=true: модуль td_telemetry не установлен в БД или Odoo не выбрал БД " \
            "(при нескольких БД задайте в odoo.conf db_name = odoo или dbfilter = ^odoo\$)"
        return 0
    fi
    ok "td_telemetry в Odoo доступен"
    tok="$(secret_in TD_COLLECTOR_TOKEN "$COL_ENV" F3D_COLLECTOR_TOKEN)"
    if [[ -n "$tok" ]] && valid_secret "$tok"; then
        if curl -sS --max-time 8 -K - "$ODOO_URL/f3d/telemetry/health" <<<"header = \"Authorization: Bearer $tok\"" 2>/dev/null |
            grep -q '"collector"'; then
            ok "токен сборщика принят Odoo"
        else
            warn "Odoo не принял токен сборщика (нет блока collector в /f3d/telemetry/health): проверьте TD_COLLECTOR_TOKEN"
        fi
    fi
}

preflight() {
    log "проверка окружения"
    [[ $EUID -eq 0 ]] || if real; then die "запустите через sudo"; else warn "запущено не от root: часть проверок (секреты, порты процессов) неполная"; fi
    if [[ -r /etc/os-release ]] && ! grep -qiE '^ID(_LIKE)?=.*(debian|ubuntu)' /etc/os-release; then
        warn "ОС не Debian/Ubuntu: установка пакетов (apt) не будет работать"
    fi
    if [[ $NO_SYSTEM -eq 1 ]]; then ok "режим --no-system: systemd, пользователи, apt и mosquitto не трогаются"
    elif ! sysctl_on; then block "systemd не найден (/run/systemd/system)"; fi
    [[ -d "$SERVICES/iot_sim" && -d "$SERVICES/collector" && -d "$SERVICES/collector_plugins" ]] ||
        block "нет $SERVICES/{iot_sim,collector,collector_plugins}: задайте TD_REPO (git-клон репозитория)"
    PY="$(find_python)" || { PY=""; block "нужен Python >= 3.12 (python3.12/3.13): задайте TD_PYTHON=/путь/к/python3.12"; }
    [[ -z "$PY" ]] || ok "Python: $PY ($("$PY" -c 'import sys; print(sys.version.split()[0])'))"
    have curl || block "нет curl"
    local free_kb
    free_kb="$(df -Pk "$(dirname "$PREFIX")" 2>/dev/null | awk 'NR == 2 { print $4 }' || true)"
    if [[ -n "$free_kb" ]] && ((free_kb < 1500000)); then block "мало места под $(dirname "$PREFIX"): $((free_kb / 1024)) МБ, нужно ≥ 1500 МБ"; fi

    COL_TOKEN="$(secret_in TD_COLLECTOR_TOKEN "$COL_ENV" F3D_COLLECTOR_TOKEN)"
    if [[ -z "$COL_TOKEN" ]]; then
        block "нет токена сборщика: передайте TD_COLLECTOR_TOKEN или TD_SECRETS_FILE (его печатает stand_odoo_setup.py)"
    elif ! valid_secret "$COL_TOKEN"; then
        block "токен сборщика некорректен (32-256 символов A-Z a-z 0-9 . _ ~ + / = -)"
    else
        ok "токен сборщика получен (${#COL_TOKEN} симв., не печатается)"
    fi
    SIM_TOKEN="$(secret_in TD_SIM_API_TOKEN "$SIM_ENV" SIM_API_TOKEN)"
    if [[ -z "$SIM_TOKEN" ]]; then
        warn "TD_SIM_API_TOKEN не задан: будет сгенерирован локально; тогда панель эмулятора в Odoo нужно настроить вручную (td.iot_sim.token = SIM_API_TOKEN из $SIM_ENV)"
        SIM_TOKEN="$(real && rand || echo '<будет сгенерирован>')"
    elif [[ "$SIM_TOKEN" != "<"* ]] && ! valid_secret "$SIM_TOKEN"; then
        block "TD_SIM_API_TOKEN некорректен (32-256 символов A-Z a-z 0-9 . _ ~ + / = -)"
    fi
    local url_re='^https?://[][A-Za-z0-9._:-]+(/[^[:space:]]*)?$'
    [[ "$ODOO_URL" =~ $url_re ]] || block "TD_ODOO_URL «$ODOO_URL» некорректен"
    check_ports
    odoo_probe
    check_hosts_conflicts
}

# ---------------------------------------------------------------- пользователь и каталоги
ensure_user() {
    if [[ $NO_SYSTEM -eq 1 ]]; then return 0; fi
    if id -u "$SVC_USER" >/dev/null 2>&1; then ok "пользователь $SVC_USER"; return 0; fi
    if real; then
        useradd --system --user-group --home-dir "$STATE" --no-create-home --shell /usr/sbin/nologin "$SVC_USER"
        ok "создан пользователь $SVC_USER"
    else plan "создать системного пользователя $SVC_USER (nologin)"; fi
}

ensure_dirs() {
    local d
    if ! real; then plan "каталоги $PREFIX, $ETC, $STATE/{sim/state,sim/certs,collector/state}"; return 0; fi
    mkdir -p "$PREFIX" "$ETC" "$STATE/sim/state" "$STATE/sim/certs" "$STATE/collector/state"
    chmod 755 "$PREFIX"
    chmod 750 "$ETC"
    if [[ $NO_SYSTEM -eq 0 ]]; then
        chown root:"$SVC_USER" "$ETC"
        for d in "$STATE" "$STATE/sim" "$STATE/sim/state" "$STATE/sim/certs" "$STATE/collector" "$STATE/collector/state"; do
            chown "$SVC_USER:$SVC_USER" "$d"
        done
    fi
    chmod 750 "$STATE"
    ok "каталоги $PREFIX, $ETC, $STATE"
}

# ---------------------------------------------------------------- venv
# src_hash КАТАЛОГ... — хэш исходников (без тестов), чтобы переустанавливать пакеты только при изменениях.
src_hash() {
    (cd "$SERVICES" && find "$@" -type f \( -name '*.py' -o -name '*.json' -o -name '*.csv' -o -name '*.yaml' -o -name '*.txt' -o -name '*.toml' \) \
        -not -path '*/tests/*' -not -path '*/__pycache__/*' -not -path '*/build/*' -not -path '*.egg-info/*' -print0 |
        LC_ALL=C sort -z | xargs -0 sha256sum | sha256sum | cut -c1-16)
}

ensure_venv() { # ensure_venv ПУТЬ
    local v=$1
    if [[ -x "$v/bin/python" ]] && "$v/bin/python" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)' 2>/dev/null; then return 0; fi
    rm -rf "$v"
    if ! "$PY" -m venv "$v" 2>/dev/null; then
        rm -rf "$v"
        if [[ $NO_SYSTEM -eq 0 ]] && have apt-get; then
            log "ставлю python3-venv (apt)"
            DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3-venv >/dev/null ||
                DEBIAN_FRONTEND=noninteractive apt-get install -y -qq "$(basename "$PY")-venv" >/dev/null || true
            "$PY" -m venv "$v" || die "не удалось создать venv $v (нужен пакет python3-venv / $(basename "$PY")-venv)"
        else
            die "не удалось создать venv $v (нужен пакет python3-venv)"
        fi
    fi
}

filtered_reqs() { grep -vE '^[[:space:]]*(#|$)' "$1" | grep -viE '^(pytest|ruff|mypy)' || true; }

# build_venv ИМЯ ХЭШ СТАТУС_ИМЯ... — общий каркас; установку пакетов делает вызывающий через pip_install_<имя>
sim_install() {
    local v=$1 tmp=$2
    filtered_reqs "$SERVICES/iot_sim/requirements.txt" >"$tmp/req-sim.txt"
    "$v/bin/pip" install -q --disable-pip-version-check -r "$tmp/req-sim.txt"
    # Эмулятор ищет catalog/ рядом с пакетом (Path(__file__).parents[2]), как в образе Docker: пакет iot_sim и catalog
    # лежат одним каталогом $PREFIX/iot-sim, который подключается через PYTHONPATH (pip-пакетом он не ставится).
    rm -rf "$PREFIX/iot-sim"
    mkdir -p "$PREFIX/iot-sim"
    cp -a "$SERVICES/iot_sim/iot_sim" "$PREFIX/iot-sim/iot_sim"
    cp -a "$SERVICES/iot_sim/catalog" "$PREFIX/iot-sim/catalog"
    find "$PREFIX/iot-sim" -name __pycache__ -prune -exec rm -rf {} +
}

collector_install() {
    local v=$1 tmp=$2 p
    {
        filtered_reqs "$SERVICES/collector/requirements.txt"
        filtered_reqs "$SERVICES/collector_plugins/machine_connect/requirements.txt"
    } | sort -u >"$tmp/req-col.txt"
    "$v/bin/pip" install -q --disable-pip-version-check -r "$tmp/req-col.txt"
    mkdir -p "$tmp/src"
    cp -a "$SERVICES/collector" "$tmp/src/collector"
    for p in $COL_PLUGINS; do cp -a "$SERVICES/collector_plugins/$p" "$tmp/src/$p"; done
    rm -rf "$tmp"/src/*/tests "$tmp"/src/collector/build
    "$v/bin/pip" install -q --disable-pip-version-check --no-deps --force-reinstall "$tmp/src/collector"
    for p in $COL_PLUGINS; do
        "$v/bin/pip" install -q --disable-pip-version-check --no-deps --force-reinstall "$tmp/src/$p"
    done
}

build_one() { # build_one КЛЮЧ(sim|collector) ВЕНВ ХЭШ-ПАПКИ...
    local key=$1 v=$2 stamp want have_ tmp; shift 2
    stamp="$PREFIX/.stamp-$key"
    want="$("$PY" -c 'import sys; print("%d.%d" % sys.version_info[:2])')-r$RECIPE-$(src_hash "$@")"
    have_="$(cat "$stamp" 2>/dev/null || true)"
    if [[ "$want" == "$have_" && -x "$v/bin/python" ]]; then ok "$v актуален ($want)"; return 0; fi
    if ! real; then plan "собрать/обновить $v из $SERVICES (pip, нужен доступ к PyPI)"; return 0; fi
    log "собираю $v (несколько минут)"
    tmp="$(mktemp -d)"
    ensure_venv "$v"
    if ! "${key}_install" "$v" "$tmp"; then rm -rf "$tmp"; die "pip не смог установить пакеты в $v (нет доступа к PyPI?)"; fi
    rm -rf "$tmp"
    chmod -R go+rX "$v" "$PREFIX/iot-sim" 2>/dev/null || true
    printf '%s\n' "$want" >"$stamp"
    ok "$v готов ($want)"
    case "$key" in sim) CHANGED_SIM=1 ;; collector) CHANGED_COL=1 ;; esac
}

ensure_venvs() {
    CHANGED_SIM=${CHANGED_SIM:-0} CHANGED_COL=${CHANGED_COL:-0}
    [[ -n "${PY:-}" ]] || return 0
    real && mkdir -p "$PREFIX"
    build_one sim "$PREFIX/venv-sim" iot_sim
    build_one collector "$PREFIX/venv-collector" collector collector_plugins
    if real && [[ $NO_SYSTEM -eq 0 ]]; then chown -R root:root "$PREFIX"; fi
    if real; then printf '%s\n' "$(git_ rev-parse --short HEAD 2>/dev/null || echo unknown) $(date -u +%FT%TZ)" >"$PREFIX/VERSION"; fi
}

# ---------------------------------------------------------------- env-файлы
write_envs() {
    local s_opcua s_wood s_jobs s_bio s_mq_sim s_mq_col s_lpr_sec s_lpr_tok
    g() {
        local v; v="$(env_get "$1" "$2")"
        if [[ -n "$v" ]]; then printf '%s' "$v"; elif real; then rand; else printf '<сгенерируется>'; fi
    }
    # общие секреты эмулятора и сборщика: берём прошлые значения из env, иначе генерируем
    s_opcua="$(g "$SIM_ENV" SIM_OPCUA_PASS)"
    s_wood="$(g "$SIM_ENV" SIM_WOODSTORE_APIKEY)"
    s_jobs="$(g "$SIM_ENV" SIM_JOBS_APIKEY)"
    s_bio="$(g "$SIM_ENV" SIM_BIOSTAR_PASS)"
    s_lpr_tok="$(g "$SIM_ENV" SIM_LPR_PUSH_TOKEN)"
    s_lpr_sec="$(env_get "$COL_ENV" F3D_HTTP_PUSH_SECRET_LPR)"; [[ -n "$s_lpr_sec" ]] || s_lpr_sec="$(real && rand || printf '<сгенерируется>')"
    s_mq_sim="$(sed -n 's#^SIM_MQTT_URL=mqtt://sim:\([^@]*\)@.*#\1#p' "$SIM_ENV" 2>/dev/null | tail -1 || true)"
    [[ -n "$s_mq_sim" ]] || s_mq_sim="$(real && rand || printf '<сгенерируется>')"
    s_mq_col="$(env_get "$COL_ENV" F3D_MQTT_PASSWORD)"; [[ -n "$s_mq_col" ]] || s_mq_col="$(real && rand || printf '<сгенерируется>')"
    MQ_SIM_PW="$s_mq_sim" MQ_COL_PW="$s_mq_col"

    put_file "$SIM_ENV" 640 root "$SVC_USER" <<EOF
# Создано install_stand.sh. Секреты сгенерированы один раз. Свои переопределения — в iot-sim.local.env (не трогается).
SIM_API_TOKEN=$SIM_TOKEN
SIM_MODE=scenario
SIM_LOG_LEVEL=INFO
SIM_CATALOG_SOURCE=local
SIM_PORT_BIOSTAR_HTTP=$BIOSTAR_HTTP_PORT
SIM_CATALOG_DIR=$PREFIX/iot-sim/catalog
SIM_STATE_DIR=$STATE/sim/state
SIM_OPCUA_CERT_DIR=$STATE/sim/certs
SIM_BIOSTAR_PASS=$s_bio
SIM_WOODSTORE_APIKEY=$s_wood
SIM_JOBS_APIKEY=$s_jobs
SIM_OPCUA_PASS=$s_opcua
SIM_MQTT_URL=mqtt://sim:$s_mq_sim@mosquitto:1883
SIM_LPR_PUSH_URL=http://collector:$PUSH_PORT/f3d/lpr/$s_lpr_sec
SIM_LPR_PUSH_TOKEN=$s_lpr_tok
EOF
    [[ "$PUT" == same ]] || CHANGED_SIM=1
    put_file "$COL_ENV" 640 root "$SVC_USER" <<EOF
# Создано install_stand.sh. Токен выдаёт Odoo (stand_odoo_setup.py). Свои переопределения — в collector.local.env.
F3D_ODOO_URL=$ODOO_URL
F3D_COLLECTOR_CODE=$COLLECTOR_CODE
F3D_COLLECTOR_TOKEN=$COL_TOKEN
F3D_ALLOW_HOSTS=iot-sim,mosquitto,127.0.0.1
F3D_BUFFER_DIR=$STATE/collector/state
F3D_MC_STATE_DIR=$STATE/collector/state
F3D_WRITE_ENABLED=0
F3D_BACNET_BIND=127.0.0.2:47808
F3D_HTTP_PUSH_PORT=$PUSH_PORT
F3D_METRICS_PORT=9108
F3D_LOG_LEVEL=INFO
F3D_CONFIG_POLL_S=30
F3D_PUSH_INTERVAL_S=5
F3D_MQTT_PASSWORD=$s_mq_col
F3D_HTTP_PUSH_SECRET_LPR=$s_lpr_sec
F3D_HTTP_PUSH_TOKEN_LPR=$s_lpr_tok
F3D_OPCUA_PASSWORD=$s_opcua
F3D_WOODSTORE_KEY=$s_wood
F3D_CUTOPT_KEY=$s_jobs
EOF
    [[ "$PUT" == same ]] || CHANGED_COL=1
}

# ---------------------------------------------------------------- /etc/hosts
hosts_block() { printf '# BEGIN td-stand\n127.0.0.1 %s\n# END td-stand\n' "$HOSTS_NAMES"; }

check_hosts_conflicts() {
    local n out=""
    [[ -r "$HOSTS_FILE" ]] || return 0
    for n in $HOSTS_NAMES; do
        if sed '/^# BEGIN td-stand$/,/^# END td-stand$/d' "$HOSTS_FILE" | grep -v '^[[:space:]]*#' |
            awk -v n="$n" '{ for (i = 2; i <= NF; i++) if ($i == n) f = 1 } END { exit !f }'; then out="$out $n"; fi
    done
    [[ -z "$out" ]] || warn "в $HOSTS_FILE имена$out уже заданы вне блока td-stand: используется первая запись, проверьте, что они указывают на 127.0.0.1"
}

ensure_hosts() {
    local cur new
    if [[ ! -e "$HOSTS_FILE" ]] && real; then mkdir -p "$(dirname "$HOSTS_FILE")"; : >"$HOSTS_FILE"; fi
    cur="$(sed -n '/^# BEGIN td-stand$/,/^# END td-stand$/p' "$HOSTS_FILE" 2>/dev/null || true)"
    if [[ "$cur" == "$(hosts_block)" ]]; then ok "$HOSTS_FILE: псевдонимы $HOSTS_NAMES"; return 0; fi
    if ! real; then plan "добавить в $HOSTS_FILE: 127.0.0.1 $HOSTS_NAMES"; return 0; fi
    if [[ ! -e "$ETC/hosts.before" && -e "$HOSTS_FILE" ]]; then cp -a "$HOSTS_FILE" "$ETC/hosts.before"; fi
    new="$(sed '/^# BEGIN td-stand$/,/^# END td-stand$/d' "$HOSTS_FILE"; hosts_block)"
    printf '%s\n' "$new" >"$HOSTS_FILE"      # перезапись на месте: /etc/hosts может быть bind-mount
    ok "$HOSTS_FILE: 127.0.0.1 $HOSTS_NAMES"
}

remove_hosts() {
    if [[ ! -e "$HOSTS_FILE" ]] || ! grep -q '^# BEGIN td-stand$' "$HOSTS_FILE"; then ok "блока td-stand в $HOSTS_FILE нет"; return 0; fi
    if ! real; then plan "убрать блок td-stand из $HOSTS_FILE"; return 0; fi
    local new; new="$(sed '/^# BEGIN td-stand$/,/^# END td-stand$/d' "$HOSTS_FILE")"
    printf '%s\n' "$new" >"$HOSTS_FILE"
    ok "блок td-stand убран из $HOSTS_FILE"
}

# ---------------------------------------------------------------- MQTT-брокер (пакет mosquitto)
setup_mosquitto() {
    local marker want have_ conf_changed=0 other
    if [[ $NO_MQTT -eq 1 ]]; then ok "MQTT пропущен (--no-mqtt): источник MQTT-MOBILE и телематика техники работать не будут"; return 0; fi
    if [[ $NO_SYSTEM -eq 1 ]]; then plan "(--no-system) mosquitto не настраивается"; return 0; fi
    if ! have mosquitto; then
        if ! real; then plan "apt-get install mosquitto mosquitto-clients"; elif have apt-get; then
            log "ставлю mosquitto (apt)"
            DEBIAN_FRONTEND=noninteractive apt-get install -y -qq mosquitto >/dev/null || { warn "не удалось поставить mosquitto: MQTT пропущен"; return 1; }
        else warn "нет apt-get и mosquitto: MQTT пропущен"; return 1; fi
    fi
    other="$(grep -rhE '^[[:space:]]*(listener|per_listener_settings)' /etc/mosquitto --include='*.conf' \
        --exclude="$(basename "$MQ_CONF")" 2>/dev/null || true)"
    if [[ -n "$other" ]]; then
        warn "в /etc/mosquitto уже есть свои listener: брокер не изменён. Настройте вручную: пользователи sim и collector, порт 1883 (пароли — в $SIM_ENV и $COL_ENV)"
        return 1
    fi
    want="$(printf 'sim:%s\ncollector:%s\n' "$MQ_SIM_PW" "$MQ_COL_PW" | sha256sum | cut -c1-32)"
    marker="$ETC/.mqtt-passwd"
    have_="$(cat "$marker" 2>/dev/null || true)"
    if [[ "$want" == "$have_" && -s "$MQ_PASSWD" ]]; then ok "$MQ_PASSWD"; elif ! real; then plan "записать $MQ_PASSWD (пользователи sim, collector)"; else
        if [[ "$MQ_SIM_PW" == "<"* ]]; then return 1; fi
        printf 'sim:%s\ncollector:%s\n' "$MQ_SIM_PW" "$MQ_COL_PW" | (umask 077; cat >"$MQ_PASSWD.new")
        mosquitto_passwd -U "$MQ_PASSWD.new" || { rm -f "$MQ_PASSWD.new"; warn "mosquitto_passwd не сработал: MQTT пропущен"; return 1; }
        chown mosquitto:mosquitto "$MQ_PASSWD.new" 2>/dev/null || true
        chmod 640 "$MQ_PASSWD.new"
        mv -f "$MQ_PASSWD.new" "$MQ_PASSWD"
        printf '%s\n' "$want" >"$marker"
        conf_changed=1
        ok "записан $MQ_PASSWD"
    fi
    put_file "$MQ_CONF" 644 root root <<EOF
# Создано install_stand.sh: брокер стенда только на loopback, вход по паролю (sim, collector).
listener 1883 127.0.0.1
allow_anonymous false
password_file $MQ_PASSWD
EOF
    [[ "$PUT" == same ]] || conf_changed=1
    if real; then
        if [[ $conf_changed -eq 1 ]]; then systemctl enable mosquitto >/dev/null 2>&1 || true; systemctl restart mosquitto || { warn "mosquitto не перезапустился: journalctl -u mosquitto"; return 1; }
        else systemctl enable --now mosquitto >/dev/null 2>&1 || true; fi
    else plan "enable + restart mosquitto при изменении конфигурации"; fi
}

remove_mosquitto() {
    [[ $NO_SYSTEM -eq 1 ]] && return 0
    if [[ -e "$MQ_CONF" ]] && grep -qs td-stand "$MQ_CONF"; then
        if real; then
            rm -f "$MQ_CONF" "$MQ_PASSWD"
            systemctl restart mosquitto 2>/dev/null || true
            ok "убрана конфигурация брокера стенда (пакет mosquitto оставлен)"
        else plan "убрать $MQ_CONF и $MQ_PASSWD, перезапустить mosquitto (пакет остаётся)"; fi
    fi
}

# ---------------------------------------------------------------- unit-файлы
ip_filter_lines() { # ip_filter_lines loopback_only
    [[ "$IP_FILTER" == 1 && "$1" == 1 ]] || return 0
    printf 'IPAddressDeny=any\nIPAddressAllow=localhost\n'
    [[ -z "$IP_ALLOW_EXTRA" ]] || printf 'IPAddressAllow=%s\n' "$IP_ALLOW_EXTRA"
}

is_loopback_url() { [[ "$ODOO_URL" =~ ^https?://(127\.[0-9.]+|localhost|\[::1\])([:/]|$) ]]; }

unit_common() {
    cat <<EOF
User=$SVC_USER
Group=$SVC_USER
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1
Environment=PYTHONDONTWRITEBYTECODE=1
StandardOutput=journal
StandardError=journal
LogRateLimitIntervalSec=30s
LogRateLimitBurst=5000
UMask=0027
NoNewPrivileges=yes
RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX AF_NETLINK
RestrictNamespaces=yes
RestrictSUIDSGID=yes
LockPersonality=yes
SystemCallArchitectures=native
LimitNOFILE=16384
EOF
    if [[ "$HARDEN" == 1 ]]; then
        cat <<EOF
PrivateTmp=yes
PrivateDevices=yes
ProtectSystem=strict
ProtectHome=yes
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectControlGroups=yes
ReadWritePaths=$STATE
EOF
    fi
}

unit_sim() {
    cat <<EOF
# Создано install_stand.sh (E-11). Править через drop-in: systemctl edit td-iot-sim
[Unit]
StartLimitIntervalSec=0
Description=TD stand: эмулятор оборудования iot_sim
Documentation=file://$TD_REPO/factory3d/tools/server/STAND.md
After=network.target mosquitto.service
Wants=mosquitto.service

[Service]
Type=simple
$(unit_common)
EnvironmentFile=$SIM_ENV
EnvironmentFile=-$ETC/iot-sim.local.env
Environment=PYTHONPATH=$PREFIX/iot-sim
WorkingDirectory=$STATE/sim
ExecStart=$PREFIX/venv-sim/bin/python -m iot_sim run
SyslogIdentifier=td-iot-sim
AmbientCapabilities=CAP_NET_BIND_SERVICE
CapabilityBoundingSet=CAP_NET_BIND_SERVICE
MemoryHigh=640M
MemoryMax=1G
CPUQuota=100%
TasksMax=256
$(ip_filter_lines 1)

[Install]
WantedBy=multi-user.target
EOF
}

unit_collector() {
    local lo=0; is_loopback_url && lo=1
    cat <<EOF
# Создано install_stand.sh (E-11). Править через drop-in: systemctl edit td-collector
[Unit]
StartLimitIntervalSec=0
Description=TD stand: сборщик сигналов (collector и плагины) -> Odoo
Documentation=file://$TD_REPO/factory3d/tools/server/STAND.md
After=network.target td-iot-sim.service mosquitto.service $ODOO_SERVICE.service
Wants=td-iot-sim.service mosquitto.service

[Service]
Type=simple
$(unit_common)
EnvironmentFile=$COL_ENV
EnvironmentFile=-$ETC/collector.local.env
WorkingDirectory=$STATE/collector
ExecStart=$PREFIX/venv-collector/bin/f3d-collector run
SyslogIdentifier=td-collector
CapabilityBoundingSet=
MemoryHigh=400M
MemoryMax=640M
CPUQuota=100%
TasksMax=256
$(ip_filter_lines "$lo")

[Install]
WantedBy=multi-user.target
EOF
}

install_units() {
    local reload=0
    put_file "$UNIT_DIR/td-iot-sim.service" 644 root root < <(unit_sim)
    [[ "$PUT" == same ]] || { reload=1; CHANGED_SIM=1; }
    put_file "$UNIT_DIR/td-collector.service" 644 root root < <(unit_collector)
    [[ "$PUT" == same ]] || { reload=1; CHANGED_COL=1; }
    is_loopback_url || warn "Odoo не на loopback ($ODOO_URL): сетевой фильтр сборщика отключён, у эмулятора остаётся только loopback"
    if sysctl_on && real && [[ $reload -eq 1 ]]; then systemctl daemon-reload; fi
}

start_units() {
    if ! sysctl_on; then plan "enable --now td-iot-sim td-collector (systemd недоступен/--no-system: пропущено)"; return 0; fi
    if ! real; then plan "systemctl enable --now td-iot-sim td-collector (restart, если изменились код/env/unit)"; return 0; fi
    systemctl enable td-iot-sim.service td-collector.service >/dev/null 2>&1
    if [[ ${CHANGED_SIM:-0} -eq 1 ]] && systemctl is-active -q td-iot-sim.service; then systemctl restart td-iot-sim.service; else systemctl start td-iot-sim.service; fi
    if [[ ${CHANGED_COL:-0} -eq 1 ]] && systemctl is-active -q td-collector.service; then systemctl restart td-collector.service; else systemctl start td-collector.service; fi
    ok "службы включены и запущены"
}

wait_health() {
    if ! sysctl_on || ! real; then return 0; fi
    local sim=0 col=0
    log "жду готовности служб (до 90 с)"
    for _ in $(seq 1 45); do
        if [[ $sim -eq 0 ]] && curl -fsS --max-time 3 http://127.0.0.1:8090/sim/v1/health >/dev/null 2>&1; then sim=1; fi
        if [[ $col -eq 0 ]] && curl -fsS --max-time 3 http://127.0.0.1:9108/health >/dev/null 2>&1; then col=1; fi
        if [[ $sim -eq 1 && $col -eq 1 ]]; then break; fi
        sleep 2
    done
    [[ $sim -eq 1 ]] || warn "эмулятор не ответил на :8090 (journalctl -u td-iot-sim -n 50; при status=226/NAMESPACE — TD_HARDEN=0)"
    [[ $col -eq 1 ]] || warn "сборщик не ответил на :9108 (journalctl -u td-collector -n 50; при status=226/NAMESPACE — TD_HARDEN=0)"
}

# ---------------------------------------------------------------- состояние
show_status() {
    local u v tok body
    log "состояние стенда"
    if sysctl_on; then
        for u in td-iot-sim td-collector mosquitto; do
            printf '   %-14s active=%-10s enabled=%-9s перезапусков=%s память=%s\n' "$u" \
                "$(systemctl is-active "$u" 2>/dev/null || true)" "$(systemctl is-enabled "$u" 2>/dev/null || true)" \
                "$(systemctl show -p NRestarts --value "$u" 2>/dev/null || echo ?)" \
                "$(systemctl show -p MemoryCurrent --value "$u" 2>/dev/null | awk '{ if ($1 ~ /^[0-9]+$/) printf "%d МБ", $1 / 1048576; else print "?" }')"
        done
    else
        printf '   systemd недоступен (--no-system)\n'
    fi
    v="$(curl -fsS --max-time 4 http://127.0.0.1:8090/sim/v1/health 2>/dev/null | cut -c1-160 || true)"
    printf '   эмулятор  :8090/sim/v1/health  %s\n' "${v:-не отвечает}"
    v="$(curl -fsS --max-time 4 http://127.0.0.1:9108/health 2>/dev/null | cut -c1-160 || true)"
    printf '   сборщик   :9108/health         %s\n' "${v:-не отвечает}"
    printf '   Odoo      %s/web/health      %s\n' "$ODOO_URL" "$(curl -sS -o /dev/null -w '%{http_code}' --max-time 4 "$ODOO_URL/web/health" 2>/dev/null || echo нет)"
    tok="$(env_get "$COL_ENV" F3D_COLLECTOR_TOKEN)"
    if [[ -n "$tok" ]]; then
        body="$(curl -sS --max-time 8 -K - "$ODOO_URL/f3d/telemetry/health" <<<"header = \"Authorization: Bearer $tok\"" 2>/dev/null | cut -c1-300 || true)"
        printf '   Odoo /f3d/telemetry/health (с токеном): %s\n' "${body:-нет ответа}"
    fi
    if sysctl_on; then
        for u in td-iot-sim td-collector; do
            printf '   --- journalctl -u %s (последние 3)\n' "$u"
            journalctl -u "$u" -n 3 --no-pager -o cat 2>/dev/null | cut -c1-200 | sed 's/^/   /' || true
        done
    fi
    printf '   версия кода: %s\n' "$(cat "$PREFIX/VERSION" 2>/dev/null || echo 'не установлен')"
}

# ---------------------------------------------------------------- удаление
do_uninstall() {
    log "удаление стенда (Odoo и БД не затрагиваются)"
    if sysctl_on; then
        local u
        for u in td-collector.service td-iot-sim.service; do
            if systemctl cat "$u" >/dev/null 2>&1; then
                if real; then systemctl disable --now "$u" >/dev/null 2>&1 || true; ok "остановлена и отключена $u"; else plan "остановить и отключить $u"; fi
            fi
        done
    fi
    local f
    for f in "$UNIT_DIR/td-iot-sim.service" "$UNIT_DIR/td-collector.service"; do
        [[ -e "$f" ]] || continue
        if real; then rm -f "$f"; ok "удалён $f"; else plan "удалить $f"; fi
    done
    if sysctl_on && real; then systemctl daemon-reload; fi
    safe_rm "$PREFIX"
    remove_hosts
    remove_mosquitto
    if [[ $PURGE -eq 1 ]]; then
        safe_rm "$ETC"
        safe_rm "$STATE"
        if [[ $NO_SYSTEM -eq 0 ]] && id -u "$SVC_USER" >/dev/null 2>&1; then
            if real; then userdel "$SVC_USER" 2>/dev/null || true; ok "удалён пользователь $SVC_USER"; else plan "удалить пользователя $SVC_USER"; fi
        fi
    else
        ok "оставлены $ETC (env и секреты) и $STATE (буфер, состояние); --purge удалит и их"
    fi
}

# ---------------------------------------------------------------- main
main() {
    [[ $CHECK -eq 0 ]] || log "РЕЖИМ ПРОВЕРКИ: ничего не меняю, только показываю план"
    if [[ $STATUS_ONLY -eq 1 ]]; then show_status; return 0; fi
    if [[ $UNINSTALL -eq 1 ]]; then
        [[ $EUID -eq 0 || $CHECK -eq 1 ]] || die "запустите через sudo"
        do_uninstall
        return 0
    fi
    preflight
    if [[ $BLOCKERS -gt 0 ]] && real; then die "есть препятствия ($BLOCKERS), установка не начата. Исправьте и запустите снова."; fi
    CHANGED_SIM=0 CHANGED_COL=0
    log "пользователь и каталоги"; ensure_user; ensure_dirs
    log "venv и код из $SERVICES (ревизия $(git_ rev-parse --short HEAD 2>/dev/null || echo '?'))"; ensure_venvs
    log "env-файлы"; MQ_SIM_PW="" MQ_COL_PW=""; write_envs
    log "псевдонимы хостов"; ensure_hosts
    log "MQTT-брокер"; setup_mosquitto || warn "MQTT не настроен (см. выше): телематика техники работать не будет"
    log "службы systemd"; install_units; start_units
    wait_health
    if real; then show_status; fi
    if [[ $CHECK -eq 1 ]]; then log "проверка завершена, ничего не изменено; препятствий: $BLOCKERS, предупреждений: $WARNS"; fi
    [[ $WARNS -eq 0 || $CHECK -eq 1 ]] || log "предупреждений: $WARNS"
    [[ $BLOCKERS -eq 0 ]] || return 3
}

# при `source` (тесты функций) main не запускается
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then main; fi
