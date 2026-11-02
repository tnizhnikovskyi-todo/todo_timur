#!/usr/bin/env bash
# Постоянный «стенд» на тестовом сервере (решение E-11): эмулятор оборудования iot_sim + сборщик сигналов
# (collector и плагины) + имитатор ретранслятора SmartGen (fake_relay, профиль D700) как службы systemd. Эмулятор отдаёт
# данные по протоколам, сборщик читает их и шлёт в Odoo; Odoo (td_genset) сам опрашивает имитатор ретранслятора.
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
#   6. имитатор ретранслятора td_genset/relay/fake_relay.py (профиль D700): venv-relay, код в /opt/td-stand/genset-relay,
#      /etc/td-stand/genset-relay.env (токены API и /sim/v1 генерируются один раз), порт TD_SIM_PORT_GENSET_RELAY
#      (по умолчанию 8087; НЕ 8081: там настоящий ретранслятор SmartGen). iot_sim получает его URL и токен для сценариев
#      blackout и genset_test (--no-relay — пропустить);
#   7. службы td-iot-sim.service, td-collector.service и td-genset-relay.service: Restart=always, пользователь td-stand,
#      журнал в journald, лимиты памяти/CPU/процессов, доступ в сеть только к loopback (и к TD_IP_ALLOW);
#   8. enable --now и печать состояния.
#
# Секреты, которые выдаёт менеджер (stand_odoo_setup.py печатает их один раз), в порядке приоритета:
#   переменная окружения TD_COLLECTOR_TOKEN / TD_SIM_API_TOKEN / TD_RELAY_API_TOKEN / TD_RELAY_SIM_TOKEN;
#   файл TD_COLLECTOR_TOKEN_FILE / TD_SIM_API_TOKEN_FILE / TD_RELAY_API_TOKEN_FILE / TD_RELAY_SIM_TOKEN_FILE (только значение);
#   файл TD_SECRETS_FILE (строки KEY=VALUE, по умолчанию /etc/td-stand/secrets.env, если есть);
#   значение, уже записанное в /etc/td-stand/*.env прошлым запуском.
#
# Переменные TD_* (TD_REPO — по умолчанию клон, в котором лежит этот скрипт): TD_ODOO_URL, TD_ODOO_SERVICE, TD_PYTHON,
#   TD_USER, TD_COLLECTOR_CODE, TD_PUSH_PORT, TD_SIM_PORT_BIOSTAR_HTTP (HTTP-порт эмулятора BioStar; пишется в iot-sim.env
#   как SIM_PORT_BIOSTAR_HTTP), TD_IP_FILTER (0 — не ограничивать сеть служб), TD_IP_ALLOW (доп. сети в фильтр служб,
#   например 172.16.0.0/12 — чтобы Odoo из контейнера Docker достучался до эмулятора и имитатора ретранслятора; через
#   пробел), TD_SIM_PORT_GENSET_RELAY (порт имитатора ретранслятора), TD_GENSET_RELAY_HOSTID (hostid имитатора), TD_HARDEN
#   (0 — без песочницы systemd), TD_ROOT (всё в подкаталог, для проверки без системы).
# ЗНАЧЕНИЯ ПОВТОРНОГО ЗАПУСКА. Для каждого TD_* порядок такой: 1) задано в команде; 2) уже установлено (читается из
#   /etc/td-stand/collector.env, iot-sim.env, genset-relay.env и unit-файлов); 3) по умолчанию (только для первой установки:
#   TD_ODOO_URL=http://127.0.0.1:8069, TD_SIM_PORT_BIOSTAR_HTTP=8081, TD_SIM_PORT_GENSET_RELAY=8087, TD_PUSH_PORT=8080,
#   TD_IP_FILTER=1, TD_IP_ALLOW пусто). Поэтому «голый» повторный запуск (только TD_SECRETS_FILE) НИЧЕГО не меняет: порт
#   BioStar, адрес Odoo и сети TD_IP_ALLOW остаются прежними. Если заданное значение ОТЛИЧАЕТСЯ от установленного, скрипт
#   остановится с препятствием, пока не добавлен флаг --confirm-change (или TD_CONFIRM_CHANGE=1). TD_SIM_PORT_BIOSTAR_HTTP
#   по умолчанию 8081 только если порт свободен; занятый чужим процессом 8081 (на timur-o19demo — настоящий ретранслятор
#   SmartGen) всегда препятствие. --check печатает каждое эффективное TD_* значение и его источник (задан / установлен /
#   по умолчанию); секреты не печатаются.
# Пример (Odoo в Docker на 8094, порт 8081 занят ретранслятором SmartGen) — первая установка:
#   sudo TD_SECRETS_FILE=/root/td-stand.secrets TD_ODOO_URL=http://127.0.0.1:8094 TD_SIM_PORT_BIOSTAR_HTTP=8181 \
#       TD_IP_ALLOW=172.16.0.0/12 bash /opt/timur-o19/timur-o19e/git/todo_timur/factory3d/tools/server/install_stand.sh --check
# Токены имитатора ретранслятора (TD_RELAY_API_TOKEN для Odoo, TD_RELAY_SIM_TOKEN для /sim/v1) обычно выдаёт менеджер:
#   stand_odoo_setup.py genset --token-file td-stand.secrets (дописывает строки KEY=VALUE); без них скрипт генерирует свои.
# Odoo для людей СКУД в режиме scenario (SIM_ODOO_*, необязательно): в файле секретов (или TD_SIM_ODOO_URL/DB/USER/APIKEY)
#   строки SIM_ODOO_DB, SIM_ODOO_USER, SIM_ODOO_APIKEY (и SIM_ODOO_URL; по умолчанию = TD_ODOO_URL) — скрипт переносит их в
#   iot-sim.env, значения не печатаются. Ключи SIM_ODOO_*, уже заданные вручную в iot-sim.local.env (служба читает его поверх
#   iot-sim.env), --check и установка тоже видят: они перекрывают остальные источники и в iot-sim.env не копируются. Права
#   пользователя Odoo — в STAND.md.
# Режимы проверки: --no-system — не трогать пользователей, apt, systemd, mosquitto (файлы пишутся под TD_ROOT).
set -euo pipefail
umask 022

# ---------------------------------------------------------------- аргументы
CHECK=0 UNINSTALL=0 PURGE=0 STATUS_ONLY=0 NO_MQTT=0 NO_SYSTEM=0 NO_RELAY=0 CONFIRM_CHANGE="${TD_CONFIRM_CHANGE:-0}"
usage() { sed -n '2,/^set -euo/p' "${BASH_SOURCE[0]}" | sed '$d; s/^# \{0,1\}//'; }
for arg in "$@"; do
    case "$arg" in
        --check | --dry-run) CHECK=1 ;;
        --uninstall) UNINSTALL=1 ;;
        --purge) PURGE=1 ;;
        --status) STATUS_ONLY=1 ;;
        --no-mqtt) NO_MQTT=1 ;;
        --no-system) NO_SYSTEM=1 ;;
        --no-relay) NO_RELAY=1 ;;
        --confirm-change) CONFIRM_CHANGE=1 ;;
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
# Значения TD_* (SVC_USER, ODOO_URL, ODOO_SERVICE, COLLECTOR_CODE, IP_FILTER, IP_ALLOW_EXTRA, HARDEN, BIOSTAR_HTTP_PORT,
# GENSET_RELAY_PORT, GENSET_RELAY_HOSTID, PUSH_PORT, PORTS_*) определяет resolve_params: задано > установлено > по умолчанию.
SECRETS_FILE="${TD_SECRETS_FILE:-/etc/td-stand/secrets.env}"
HOSTS_NAMES="iot-sim mosquitto collector"
MQ_CONF="${TD_MOSQUITTO_CONF:-/etc/mosquitto/conf.d/td-stand.conf}"
MQ_PASSWD="${TD_MOSQUITTO_PASSWD:-/etc/mosquitto/td-stand.passwd}"
PORTS_SIM_FIXED="502 4001 4840 8082 8083 8090 8443 50000"   # фиксированные порты эмулятора (порт BioStar HTTP — отдельно)
RECIPE=3                                             # версия способа установки: меняется — venv пересобираются
COL_PLUGINS="f3d_collector_bms f3d_collector_yard machine_connect td_collector_energy"   # плагины сборщика (W2: energy_ctl)
SIM_ENV="$ETC/iot-sim.env"
SIM_LOCAL_ENV="$ETC/iot-sim.local.env"   # ручные правки оператора: служба читает его поверх iot-sim.env, скрипт не пишет
COL_LOCAL_ENV="$ETC/collector.local.env"
COL_ENV="$ETC/collector.env"
RELAY_ENV="$ETC/genset-relay.env"
RELAY_SRC="$TD_REPO/factory3d/odoo_addons/td_genset/relay"   # fake_relay.py, genset_model.py, profiles/ (только stdlib + tzdata)
R_API_TOKEN="" R_SIM_TOKEN=""

WARNS=0 BLOCKERS=0
log() { printf '%s  %s\n' "$(date +%H:%M:%S)" "$*"; }
ok() { printf '   ok       %s\n' "$*"; }
plan() { printf '   БУДЕТ    %s\n' "$*"; }
warn() { printf '   ВНИМАНИЕ %s\n' "$*" >&2; WARNS=$((WARNS + 1)); }
block() { printf '   ПРЕПЯТСТВИЕ %s\n' "$*" >&2; BLOCKERS=$((BLOCKERS + 1)); }
die() { printf '%s  ОШИБКА: %s\n' "$(date +%H:%M:%S)" "$*" >&2; exit 1; }
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

# eff_env_get ЛОКАЛЬНЫЙ_ФАЙЛ ОСНОВНОЙ_ФАЙЛ КЛЮЧ — значение, которое увидит служба: *.local.env читается последним и перекрывает основной.
eff_env_get() {
    local v; v="$(kv_get "$1" "$3")"
    [[ -n "$v" ]] || v="$(env_get "$2" "$3")"
    printf '%s' "$v"
}

# ---------------------------------------------------------------- значения TD_*: задано > установлено > по умолчанию
PARAM_ROWS=""        # строки для show_params: ИМЯ|значение|источник|установлено|изменение(0/1)
CHANGES=""           # заданные значения, отличные от установленных (нужен --confirm-change)
SYS_ACTIVE=0         # td-iot-sim.service работает (заполняет resolve_params)

norm_plain() { printf '%s' "$1"; }
norm_url() { printf '%s' "${1%/}"; }
norm_nets() { local a; read -ra a <<<"$1"; [[ ${#a[@]} -gt 0 ]] || return 0; printf '%s\n' "${a[@]}" | LC_ALL=C sort -u | tr '\n' ' ' | sed 's/ $//'; }

# unit_val ФАЙЛ ШАБЛОН_sed — значение из unit-файла (последнее совпадение)
unit_val() { [[ -r "$1" ]] && sed -n "$2" "$1" | tail -1 || true; }

# resolve ИМЯ_TD ПЕРЕМЕННАЯ УСТАНОВЛЕНО ИЗВЕСТНО(0/1) ПО_УМОЛЧАНИЮ [НОРМАЛИЗАТОР] [ПУСТОЕ_ЗАДАНО_ОК]
# Результат — в ПЕРЕМЕННАЯ. ИЗВЕСТНО=1 — источник установленного значения существует (даже если значение пустое).
resolve() {
    local td=$1 var=$2 inst=$3 known=$4 def=$5 norm=${6:-norm_plain} empty_ok=${7:-0} val src chg=0
    if [[ -n "${!td:-}" || ( "$empty_ok" == 1 && -n "${!td+x}" ) ]]; then
        val="${!td:-}" src="задан"
        if [[ "$known" == 1 ]] && [[ "$("$norm" "$val")" != "$("$norm" "$inst")" ]]; then
            chg=1
            CHANGES="$CHANGES$td: установлено «${inst:-пусто}», задано «${val:-пусто}»"$'\n'
        fi
    elif [[ "$known" == 1 && ( -n "$inst" || "$empty_ok" == 1 ) ]]; then
        val="$inst" src="установлен"
    else
        val="$def" src="по умолчанию"
    fi
    printf -v "$var" '%s' "$val"
    PARAM_ROWS="$PARAM_ROWS$td|${val:-(пусто)}|$src|${inst:-}|$chg"$'\n'
}

net_re4='^[0-9]{1,3}(\.[0-9]{1,3}){3}(/[0-9]{1,2})?$'
net_re6='^[0-9a-fA-F]*:[0-9a-fA-F:]*(/[0-9]{1,3})?$'

resolve_params() {
    local i_sim_unit="$UNIT_DIR/td-iot-sim.service" i_col_unit="$UNIT_DIR/td-collector.service" f net
    local sim_unit_known=0 col_env_known=0 sim_env_known=0 rel_env_known=0
    [[ -e "$i_sim_unit" ]] && sim_unit_known=1
    [[ -e "$COL_ENV" ]] && col_env_known=1
    [[ -e "$SIM_ENV" ]] && sim_env_known=1
    [[ -e "$RELAY_ENV" ]] && rel_env_known=1
    for f in "$i_sim_unit" "$i_col_unit" "$COL_ENV" "$SIM_ENV" "$RELAY_ENV"; do
        if [[ -e "$f" && ! -r "$f" ]]; then
            warn "$f не читается (нужен root): установленные значения не учтены, «установлено» может показаться значением по умолчанию — запустите через sudo"
        fi
    done
    local i_ip_allow="" i_filter="" i_harden="" i_user="" i_svc=""
    if [[ $sim_unit_known -eq 1 ]]; then
        i_ip_allow="$(sed -n 's/^IPAddressAllow=//p' "$i_sim_unit" 2>/dev/null | grep -vx 'localhost' | tr '\n' ' ' | sed 's/ $//' || true)"
        if grep -qx 'IPAddressDeny=any' "$i_sim_unit" 2>/dev/null; then i_filter=1; else i_filter=0; fi
        if grep -qx 'ProtectSystem=strict' "$i_sim_unit" 2>/dev/null; then i_harden=1; else i_harden=0; fi
        i_user="$(unit_val "$i_sim_unit" 's/^User=//p')"
    fi
    [[ ! -e "$i_col_unit" ]] || i_svc="$(unit_val "$i_col_unit" 's/^After=network\.target td-iot-sim\.service mosquitto\.service \(.*\)\.service$/\1/p')"

    resolve TD_USER SVC_USER "$i_user" "$sim_unit_known" td-stand
    resolve TD_ODOO_URL ODOO_URL "$(env_get "$COL_ENV" F3D_ODOO_URL)" "$col_env_known" http://127.0.0.1:8069 norm_url
    ODOO_URL="${ODOO_URL%/}"
    resolve TD_ODOO_SERVICE ODOO_SERVICE "$i_svc" "$([[ -n "$i_svc" ]] && echo 1 || echo 0)" odoo
    resolve TD_COLLECTOR_CODE COLLECTOR_CODE "$(env_get "$COL_ENV" F3D_COLLECTOR_CODE)" "$col_env_known" COL-MAIN
    resolve TD_PUSH_PORT PUSH_PORT "$(env_get "$COL_ENV" F3D_HTTP_PUSH_PORT)" "$col_env_known" 8080
    resolve TD_IP_FILTER IP_FILTER "$i_filter" "$sim_unit_known" 1
    resolve TD_IP_ALLOW IP_ALLOW_EXTRA "$i_ip_allow" "$sim_unit_known" "" norm_nets 1
    resolve TD_HARDEN HARDEN "$i_harden" "$sim_unit_known" 1
    resolve TD_SIM_PORT_BIOSTAR_HTTP BIOSTAR_HTTP_PORT "$(env_get "$SIM_ENV" SIM_PORT_BIOSTAR_HTTP)" "$sim_env_known" 8081
    if [[ $NO_RELAY -eq 0 ]]; then
        resolve TD_SIM_PORT_GENSET_RELAY GENSET_RELAY_PORT "$(env_get "$RELAY_ENV" RELAY_PORT)" "$rel_env_known" 8087
        # hostid имитатора намеренно не равен hostid настоящего модуля: при ошибочном адресе Odoo получит 404 «unknown hostid»
        resolve TD_GENSET_RELAY_HOSTID GENSET_RELAY_HOSTID "$(env_get "$RELAY_ENV" RELAY_HOSTID)" "$rel_env_known" 53494D47454E534554443730
    else
        GENSET_RELAY_PORT="${TD_SIM_PORT_GENSET_RELAY:-8087}" GENSET_RELAY_HOSTID="${TD_GENSET_RELAY_HOSTID:-53494D47454E534554443730}"
    fi
    PORTS_SIM_TCP="$PORTS_SIM_FIXED $BIOSTAR_HTTP_PORT"
    PORTS_COL_TCP="$PUSH_PORT 9108"
    sysctl_on && systemctl is-active -q td-iot-sim.service 2>/dev/null && SYS_ACTIVE=1 || true

    for net in $IP_ALLOW_EXTRA; do
        [[ "$net" =~ $net_re4 || "$net" =~ $net_re6 ]] ||
            die "TD_IP_ALLOW: «$net» — нужна сеть вида 172.16.0.0/12 (несколько — через пробел)"
    done
    [[ "$IP_FILTER" =~ ^[01]$ && "$HARDEN" =~ ^[01]$ ]] || die "TD_IP_FILTER и TD_HARDEN: 0 или 1"
    [[ "$BIOSTAR_HTTP_PORT" =~ ^[0-9]+$ ]] && ((BIOSTAR_HTTP_PORT >= 1 && BIOSTAR_HTTP_PORT <= 65535)) ||
        die "TD_SIM_PORT_BIOSTAR_HTTP=$BIOSTAR_HTTP_PORT: нужен номер порта 1…65535"
    [[ "$PUSH_PORT" =~ ^[0-9]+$ ]] && ((PUSH_PORT >= 1 && PUSH_PORT <= 65535)) || die "TD_PUSH_PORT=$PUSH_PORT: нужен номер порта 1…65535"
    case " $PORTS_SIM_FIXED $PUSH_PORT 9108 " in
        *" $BIOSTAR_HTTP_PORT "*) die "TD_SIM_PORT_BIOSTAR_HTTP=$BIOSTAR_HTTP_PORT совпадает с другим портом стенда" ;;
    esac
    [[ "$GENSET_RELAY_PORT" =~ ^[0-9]+$ ]] && ((GENSET_RELAY_PORT >= 1 && GENSET_RELAY_PORT <= 65535)) ||
        die "TD_SIM_PORT_GENSET_RELAY=$GENSET_RELAY_PORT: нужен номер порта 1…65535"
    case " $PORTS_SIM_FIXED $PUSH_PORT 9108 $BIOSTAR_HTTP_PORT " in
        *" $GENSET_RELAY_PORT "*) die "TD_SIM_PORT_GENSET_RELAY=$GENSET_RELAY_PORT совпадает с другим портом стенда" ;;
    esac
    [[ "$GENSET_RELAY_PORT" != 8081 ]] ||
        die "TD_SIM_PORT_GENSET_RELAY=8081: на timur-o19demo этот порт занят настоящим ретранслятором SmartGen, возьмите другой (по умолчанию 8087)"
    [[ "$GENSET_RELAY_HOSTID" =~ ^[0-9A-Za-z]{1,24}$ ]] || die "TD_GENSET_RELAY_HOSTID: до 24 символов A-Z a-z 0-9"
}

# show_params — эффективные значения TD_* и источник (задан / установлен / по умолчанию); секреты не печатаются.
show_params() {
    local td val src inst chg
    log "параметры стенда (значение · источник: задан / установлен / по умолчанию)"
    while IFS='|' read -r td val src inst chg; do
        [[ -n "$td" ]] || continue
        if [[ "$chg" == 1 ]]; then
            printf '   %-28s %-34s %s, ИЗМЕНЕНИЕ установленного «%s»\n' "$td" "$val" "$src" "${inst:-пусто}"
        else
            printf '   %-28s %-34s %s\n' "$td" "$val" "$src"
        fi
    done <<<"$PARAM_ROWS"
    printf '   %-28s %s\n' "TD_CONFIRM_CHANGE" "$([[ "$CONFIRM_CHANGE" == 1 ]] && echo 1 || echo 0)"
    printf '   %-28s %s\n' "TD_SECRETS_FILE" "$SECRETS_FILE ($([[ -r "$SECRETS_FILE" ]] && echo найден || echo нет))"
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
    local sim_active="" col_active="" rel_active="" lines
    if ! have ss; then warn "нет утилиты ss (пакет iproute2): занятость портов не проверена"; return 0; fi
    if sysctl_on; then
        if systemctl is-active -q td-iot-sim.service 2>/dev/null; then sim_active=1; fi
        if systemctl is-active -q td-collector.service 2>/dev/null; then col_active=1; fi
        if systemctl is-active -q td-genset-relay.service 2>/dev/null; then rel_active=1; fi
    fi
    [[ $NO_RELAY -eq 0 ]] || rel_active=1               # имитатор не нужен: его порт не проверяем
    if [[ -n "$sim_active" && -n "$col_active" && -n "$rel_active" ]]; then ok "порты стенда заняты нашими службами (они уже работают)"; return 0; fi
    lines=""
    # shellcheck disable=SC2086  # списки портов разбиваются по словам намеренно
    if [[ -z "$sim_active" ]]; then lines="$(busy_ports tcp $PORTS_SIM_TCP; busy_ports udp 47808 50001)"; fi
    # shellcheck disable=SC2086
    if [[ -z "$col_active" ]]; then lines="$lines$(busy_ports tcp $PORTS_COL_TCP)"; fi
    if [[ -z "$rel_active" ]]; then lines="$lines$(busy_ports tcp "$GENSET_RELAY_PORT")"; fi
    if [[ -n "$lines" ]]; then
        block "порты стенда заняты другими процессами: $(printf '%s' "$lines" | tr '\n' ' ')"
    else
        ok "порты стенда свободны (TCP $PORTS_SIM_TCP $PORTS_COL_TCP$([[ $NO_RELAY -eq 1 ]] || printf ' %s' "$GENSET_RELAY_PORT"), UDP 47808 50001)"
    fi
}

# port_pid ПОРТ — pid слушающего TCP-порт процесса (пусто: порт свободен или pid не виден без root)
port_pid() { port_lines | awk -v p="$1" '$1 == "tcp" && $5 ~ (":" p "$") { if (match($7, /pid=[0-9]+/)) { print substr($7, RSTART + 4, RLENGTH - 4); exit } }'; }

# check_biostar_port — порт HTTP BioStar не должен оказаться портом чужого процесса (на timur-o19demo 8081 — настоящий
# ретранслятор SmartGen). check_ports пропускает порты эмулятора, пока служба работает, поэтому здесь отдельно:
# работающая служба владеет только тем портом, что уже установлен; новый или чужой занятый порт — препятствие.
check_biostar_port() {
    local busy pid main inst
    have ss || return 0
    inst="$(env_get "$SIM_ENV" SIM_PORT_BIOSTAR_HTTP)"
    busy="$(busy_ports tcp "$BIOSTAR_HTTP_PORT")"
    if [[ "$BIOSTAR_HTTP_PORT" == 8081 && "$PARAM_ROWS" == *"TD_SIM_PORT_BIOSTAR_HTTP|8081|по умолчанию|"* && -n "$busy" ]]; then
        block "TD_SIM_PORT_BIOSTAR_HTTP не задан и не установлен, а порт 8081 занят ($busy): на timur-o19demo это настоящий ретранслятор SmartGen. Задайте порт явно, например TD_SIM_PORT_BIOSTAR_HTTP=8181"
        return 0
    fi
    [[ $SYS_ACTIVE -eq 1 ]] || return 0                 # без работающей службы порт уже проверил check_ports
    [[ -n "$busy" ]] || return 0
    if [[ "$inst" == "$BIOSTAR_HTTP_PORT" ]]; then
        pid="$(port_pid "$BIOSTAR_HTTP_PORT")"
        main="$(systemctl show -p MainPID --value td-iot-sim.service 2>/dev/null || true)"
        if [[ -n "$pid" && "$pid" == "$main" ]]; then ok "порт BioStar $BIOSTAR_HTTP_PORT занят нашим td-iot-sim (pid $pid)"; return 0; fi
        if [[ -z "$pid" ]]; then warn "порт BioStar $BIOSTAR_HTTP_PORT занят ($busy), владельца не видно (нужен root): проверьте, что это td-iot-sim"; return 0; fi
    fi
    block "порт BioStar HTTP $BIOSTAR_HTTP_PORT занят не td-iot-sim: $busy"
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

# relay_tokens — токены имитатора ретранслятора: API (Bearer для Odoo, relay_api.md) и SIM (Bearer для /sim/v1, его же
# получает iot_sim). Приоритет как у остальных секретов; иначе генерируются один раз.
relay_tokens() {
    local name key var val
    for name in TD_RELAY_API_TOKEN:RELAY_API_TOKEN:R_API_TOKEN TD_RELAY_SIM_TOKEN:RELAY_SIM_TOKEN:R_SIM_TOKEN; do
        IFS=: read -r name key var <<<"$name"
        val="$(secret_in "$name" "$RELAY_ENV" "$key")"
        if [[ -z "$val" ]]; then
            warn "$name не задан: будет сгенерирован локально (Odoo получит токен командой stand_odoo_setup.py genset --token-file с копией $RELAY_ENV)"
            val="$(real && rand || echo '<будет сгенерирован>')"
        elif ! valid_secret "$val"; then
            block "$name некорректен (32-256 символов A-Z a-z 0-9 . _ ~ + / = -)"
        fi
        printf -v "$var" '%s' "$val"
    done
}

# params_conflicts — заданное значение отличается от установленного: без --confirm-change это препятствие.
params_conflicts() {
    local line
    [[ -n "$CHANGES" ]] || return 0
    while IFS= read -r line; do
        [[ -n "$line" ]] || continue
        if [[ "$CONFIRM_CHANGE" == 1 ]]; then warn "будет изменено (--confirm-change): $line"
        else block "$line. Это изменит уже установленный стенд и перезапустит службы: уберите TD_* из команды (останется установленное) или добавьте --confirm-change"; fi
    done <<<"$CHANGES"
}

preflight() {
    log "проверка окружения"
    show_params
    params_conflicts
    [[ $EUID -eq 0 ]] || if real; then die "запустите через sudo"; else warn "запущено не от root: часть проверок (секреты, порты процессов) неполная"; fi
    if [[ -r /etc/os-release ]] && ! grep -qiE '^ID(_LIKE)?=.*(debian|ubuntu)' /etc/os-release; then
        warn "ОС не Debian/Ubuntu: установка пакетов (apt) не будет работать"
    fi
    if [[ $NO_SYSTEM -eq 1 ]]; then ok "режим --no-system: systemd, пользователи, apt и mosquitto не трогаются"
    elif ! sysctl_on; then block "systemd не найден (/run/systemd/system)"; fi
    [[ -d "$SERVICES/iot_sim" && -d "$SERVICES/collector" && -d "$SERVICES/collector_plugins" ]] ||
        block "нет $SERVICES/{iot_sim,collector,collector_plugins}: задайте TD_REPO (git-клон репозитория)"
    [[ $NO_RELAY -eq 1 || ( -f "$RELAY_SRC/fake_relay.py" && -f "$RELAY_SRC/genset_model.py" && -f "$RELAY_SRC/profiles/d700.json" ) ]] ||
        block "нет $RELAY_SRC/{fake_relay.py,genset_model.py,profiles/d700.json}: задайте TD_REPO или --no-relay"
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
    [[ $NO_RELAY -eq 1 ]] || relay_tokens
    local url_re='^https?://[][A-Za-z0-9._:-]+(/[^[:space:]]*)?$'
    [[ "$ODOO_URL" =~ $url_re ]] || block "TD_ODOO_URL «$ODOO_URL» некорректен"
    check_ports
    check_biostar_port
    resolve_sim_odoo
    odoo_probe
    check_hosts_conflicts
}

# ---------------------------------------------------------------- SIM_ODOO_*: люди СКУД из Odoo в режиме scenario
# sim_odoo_val ИМЯ (URL|DB|USER|APIKEY) — приоритет как у секретов: TD_SIM_ODOO_<ИМЯ> (окружение, ..._FILE, файл секретов),
# строка SIM_ODOO_<ИМЯ> файла секретов, значение, уже записанное в iot-sim.env. Значения не печатаются.
# iot-sim.local.env учитывает resolve_sim_odoo: служба читает его последним, поэтому его значения перекрывают всё остальное.
sim_odoo_val() {
    local k=$1 v
    v="$(secret_in "TD_SIM_ODOO_$k" /dev/null x)"        # /dev/null: без чтения iot-sim.env на этом шаге
    [[ -n "$v" ]] || v="$(kv_get "$SECRETS_FILE" "SIM_ODOO_$k")"
    [[ -n "$v" ]] || v="$(env_get "$SIM_ENV" "SIM_ODOO_$k")"
    printf '%s' "$v"
}

SIM_ODOO_URL="" SIM_ODOO_DB="" SIM_ODOO_USER="" SIM_ODOO_APIKEY=""
SIM_ODOO_LOCAL=""   # какие из URL DB USER APIKEY заданы в iot-sim.local.env: их в iot-sim.env не копируем (не дублируем секрет)
resolve_sim_odoo() {
    local host k v hint=""
    SIM_ODOO_LOCAL=""
    for k in URL DB USER APIKEY; do
        v="$(kv_get "$SIM_LOCAL_ENV" "SIM_ODOO_$k")"
        if [[ -n "$v" ]]; then SIM_ODOO_LOCAL="$SIM_ODOO_LOCAL $k"; else v="$(sim_odoo_val "$k")"; fi
        printf -v "SIM_ODOO_$k" '%s' "$v"
    done
    SIM_ODOO_LOCAL="${SIM_ODOO_LOCAL# }"
    if [[ -z "$SIM_ODOO_DB$SIM_ODOO_USER$SIM_ODOO_APIKEY" ]]; then
        [[ ! -e "$SIM_LOCAL_ENV" || -r "$SIM_LOCAL_ENV" ]] || hint=" ($SIM_LOCAL_ENV не читается: запустите от root)"
        warn "SIM_ODOO_* не заданы: в режиме scenario эмулятор не читает людей из Odoo, СКУД останется без людей. Добавьте SIM_ODOO_DB/SIM_ODOO_USER/SIM_ODOO_APIKEY в файл секретов или в iot-sim.local.env (STAND.md, «Люди СКУД из Odoo»)$hint"
        SIM_ODOO_URL=""
        return 0
    fi
    [[ -n "$SIM_ODOO_URL" ]] || SIM_ODOO_URL="$ODOO_URL"
    SIM_ODOO_URL="${SIM_ODOO_URL%/}"
    if [[ -z "$SIM_ODOO_DB" || -z "$SIM_ODOO_USER" || -z "$SIM_ODOO_APIKEY" ]]; then
        block "SIM_ODOO_*: нужны все три — SIM_ODOO_DB, SIM_ODOO_USER, SIM_ODOO_APIKEY (SIM_ODOO_URL по умолчанию = TD_ODOO_URL)"
        return 0
    fi
    [[ "$SIM_ODOO_DB" =~ ^[A-Za-z0-9._-]{1,63}$ ]] || block "SIM_ODOO_DB некорректен (A-Z a-z 0-9 . _ -, до 63 символов)"
    [[ "$SIM_ODOO_USER" =~ ^[A-Za-z0-9._@+-]{1,128}$ ]] || block "SIM_ODOO_USER некорректен (A-Z a-z 0-9 . _ @ + -, до 128 символов)"
    valid_secret "$SIM_ODOO_APIKEY" || block "SIM_ODOO_APIKEY некорректен (32-256 символов A-Z a-z 0-9 . _ ~ + / = -)"
    [[ "$SIM_ODOO_URL" =~ ^https?://[][A-Za-z0-9._:-]+(/[^[:space:]]*)?$ ]] || block "SIM_ODOO_URL «$SIM_ODOO_URL» некорректен"
    host="$(printf '%s' "$SIM_ODOO_URL" | sed -E 's#^https?://\[?([^]/:]+)\]?.*#\1#')"
    case ",mosquitto,odoo19,collector,genset_relay,127.0.0.1," in
        *",$host,"*) ;;
        *) warn "SIM_ODOO_URL: хост $host вне SIM_ALLOW_OUTBOUND по умолчанию (mosquitto,odoo19,collector,genset_relay,127.0.0.1): добавьте его в SIM_ALLOW_OUTBOUND в iot-sim.local.env" ;;
    esac
    ok "SIM_ODOO_*: url=$SIM_ODOO_URL db=$SIM_ODOO_DB user=$SIM_ODOO_USER apikey=задан (${#SIM_ODOO_APIKEY} симв., не печатается)${SIM_ODOO_LOCAL:+; из iot-sim.local.env: $SIM_ODOO_LOCAL}"
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

# Имитатор ретранслятора: код лежит в td_genset/relay (stdlib; из pip нужен только tzdata для RELAY_TZ), venv отдельный,
# чтобы не смешивать с зависимостями эмулятора и сборщика.
relay_install() {
    local v=$1 tmp=$2
    filtered_reqs "$RELAY_SRC/requirements.txt" >"$tmp/req-relay.txt"
    "$v/bin/pip" install -q --disable-pip-version-check -r "$tmp/req-relay.txt"
    rm -rf "$PREFIX/genset-relay"
    mkdir -p "$PREFIX/genset-relay"
    cp -a "$RELAY_SRC/fake_relay.py" "$RELAY_SRC/genset_model.py" "$RELAY_SRC/profiles" "$PREFIX/genset-relay/"
    find "$PREFIX/genset-relay" -name __pycache__ -prune -exec rm -rf {} +
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

build_one() { # build_one КЛЮЧ(sim|collector|relay) ВЕНВ ХЭШ-ПАПКИ... (пути — от $SERVICES)
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
    chmod -R go+rX "$v" "$PREFIX/iot-sim" "$PREFIX/genset-relay" 2>/dev/null || true
    printf '%s\n' "$want" >"$stamp"
    ok "$v готов ($want)"
    case "$key" in sim) CHANGED_SIM=1 ;; collector) CHANGED_COL=1 ;; relay) CHANGED_RELAY=1 ;; esac
}

ensure_venvs() {
    CHANGED_SIM=${CHANGED_SIM:-0} CHANGED_COL=${CHANGED_COL:-0} CHANGED_RELAY=${CHANGED_RELAY:-0}
    [[ -n "${PY:-}" ]] || return 0
    real && mkdir -p "$PREFIX"
    build_one sim "$PREFIX/venv-sim" iot_sim
    build_one collector "$PREFIX/venv-collector" collector collector_plugins
    [[ $NO_RELAY -eq 1 ]] || build_one relay "$PREFIX/venv-relay" ../odoo_addons/td_genset/relay
    if real && [[ $NO_SYSTEM -eq 0 ]]; then chown -R root:root "$PREFIX"; fi
    if real; then printf '%s\n' "$(git_ rev-parse --short HEAD 2>/dev/null || echo unknown) $(date -u +%FT%TZ)" >"$PREFIX/VERSION"; fi
}

# ---------------------------------------------------------------- env-файлы
# relay_sim_lines — адрес и токен имитатора ретранслятора для iot_sim (сценарии blackout и genset_test ходят в /sim/v1).
# Без --no-relay эмулятор говорит с ним по loopback (127.0.0.1 есть в SIM_ALLOW_OUTBOUND по умолчанию).
relay_sim_lines() {
    [[ $NO_RELAY -eq 0 ]] || return 0
    printf 'SIM_GENSET_RELAY_URL=http://127.0.0.1:%s\nSIM_GENSET_RELAY_TOKEN=%s\n' "$GENSET_RELAY_PORT" "$R_SIM_TOKEN"
}

# sim_odoo_lines — SIM_ODOO_* для iot_sim (people из hr.employee в scenario); пусто, если не заданы.
# Ключи, заданные в iot-sim.local.env, пропускаются: служба и так читает их оттуда (SIM_ODOO_LOCAL).
sim_odoo_lines() {
    local k var
    [[ -n "$SIM_ODOO_APIKEY" && -n "$SIM_ODOO_DB" && -n "$SIM_ODOO_USER" && -n "$SIM_ODOO_URL" ]] || return 0
    for k in URL DB USER APIKEY; do
        [[ " $SIM_ODOO_LOCAL " != *" $k "* ]] || continue
        var="SIM_ODOO_$k"
        printf '%s=%s\n' "$var" "${!var}"
    done
}

# sim_extra_lines — хвост iot-sim.env: ретранслятор и SIM_ODOO_*; без пустых строк, чтобы файл не менялся зря (рестарт службы).
sim_extra_lines() {
    local a b
    a="$(relay_sim_lines)" b="$(sim_odoo_lines)"
    printf '%s' "$a"
    [[ -z "$a" || -z "$b" ]] || printf '\n'
    printf '%s' "$b"
}

# lpr_wiring_problems URL ТОКЕН_ЭМУЛЯТОРА СЕКРЕТ_СБОРЩИКА ТОКЕН_СБОРЩИКА ПОРТ — по одной строке на несогласованность пути
# «эмулятор → сборщик» (SIM_LPR_PUSH_* и F3D_HTTP_PUSH_*_LPR с учётом *.local.env). Сборщик отвечает 404, если маршрут не lpr,
# секретного сегмента нет/чужой (или у него нет секрета, а в URL он есть), есть лишние сегменты; 401 — если не совпал токен.
# Эмулятор пишет об этом только «LPR push failed (HTTP 404)». Значения секретов не печатаются.
lpr_wiring_problems() {
    local url=$1 tok=$2 csec=$3 ctok=$4 port=$5 rest hostport path f3d route seg extra
    rest="${url#*://}"; hostport="${rest%%/*}"; path="${rest#"$hostport"}"; path="${path%%\?*}"
    IFS=/ read -r _ f3d route seg extra <<<"$path"
    [[ "$f3d" == f3d && "$route" == lpr ]] || echo "путь SIM_LPR_PUSH_URL должен быть /f3d/lpr/<секрет>, а не «${path:-пусто}» (маршрут сборщика — lpr, params.routes источника HTTP-PUSH): 404"
    [[ -z "$extra" ]] || echo "в SIM_LPR_PUSH_URL после секрета лишние сегменты пути: 404"
    if [[ -n "$csec" && -z "$seg" ]]; then
        echo "в SIM_LPR_PUSH_URL нет сегмента секрета, а у сборщика задан F3D_HTTP_PUSH_SECRET_LPR (путь должен оканчиваться /f3d/lpr/<секрет>): 404"
    elif [[ -n "$csec" && "$seg" != "$csec" ]]; then
        echo "сегмент секрета в SIM_LPR_PUSH_URL не совпадает с F3D_HTTP_PUSH_SECRET_LPR сборщика: 404"
    elif [[ -z "$csec" && -n "$seg" ]]; then
        echo "в SIM_LPR_PUSH_URL есть сегмент секрета, а F3D_HTTP_PUSH_SECRET_LPR сборщика не задан: 404"
    fi
    [[ "$hostport" != *:* || "${hostport##*:}" == "$port" ]] || echo "порт в SIM_LPR_PUSH_URL (${hostport##*:}) не равен F3D_HTTP_PUSH_PORT=$port: соединение не пройдёт"
    [[ "$tok" == "$ctok" ]] || echo "SIM_LPR_PUSH_TOKEN эмулятора не совпадает с F3D_HTTP_PUSH_TOKEN_LPR сборщика: 401"
}

check_lpr_wiring() {
    local line bad=0
    while IFS= read -r line; do
        [[ -n "$line" ]] || continue
        warn "LPR: $line"; bad=1
    done < <(lpr_wiring_problems "$1" "$2" "$3" "$4" "$PUSH_PORT")
    [[ $bad -eq 1 ]] || ok "LPR: путь эмулятор → сборщик согласован (маршрут lpr, секретный сегмент, токен${SIM_LPR_OVERRIDE:+; из *.local.env: $SIM_LPR_OVERRIDE})"
}

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
$(sim_extra_lines)
EOF
    [[ "$PUT" == same ]] || CHANGED_SIM=1
    if [[ $NO_RELAY -eq 0 ]]; then
        put_file "$RELAY_ENV" 640 root "$SVC_USER" <<EOF
# Создано install_stand.sh: ИМИТАТОР ретранслятора SmartGen HGM6120N (td_genset/relay/fake_relay.py, профиль D700), не настоящий.
# Токены сгенерированы один раз (или выданы менеджером). Свои переопределения — в genset-relay.local.env (не трогается).
RELAY_HOST=0.0.0.0
RELAY_PORT=$GENSET_RELAY_PORT
RELAY_PROFILE=d700
RELAY_API_TOKEN=$R_API_TOKEN
RELAY_SIM_TOKEN=$R_SIM_TOKEN
RELAY_HOSTID=$GENSET_RELAY_HOSTID
RELAY_ID_BASE=epoch
RELAY_TIME_FACTOR=1
RELAY_TZ=Europe/Kyiv
RELAY_LOG_LEVEL=INFO
EOF
        [[ "$PUT" == same ]] || CHANGED_RELAY=1
    fi
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
    # согласованность LPR с учётом ручных *.local.env (служба читает их поверх основных env)
    local l_url l_tok l_sec l_ctok
    l_url="$(kv_get "$SIM_LOCAL_ENV" SIM_LPR_PUSH_URL)" l_tok="$(kv_get "$SIM_LOCAL_ENV" SIM_LPR_PUSH_TOKEN)"
    l_sec="$(kv_get "$COL_LOCAL_ENV" F3D_HTTP_PUSH_SECRET_LPR)" l_ctok="$(kv_get "$COL_LOCAL_ENV" F3D_HTTP_PUSH_TOKEN_LPR)"
    SIM_LPR_OVERRIDE="${l_url:+SIM_LPR_PUSH_URL }${l_tok:+SIM_LPR_PUSH_TOKEN }${l_sec:+F3D_HTTP_PUSH_SECRET_LPR }${l_ctok:+F3D_HTTP_PUSH_TOKEN_LPR}"
    SIM_LPR_OVERRIDE="${SIM_LPR_OVERRIDE% }"
    check_lpr_wiring "${l_url:-http://collector:$PUSH_PORT/f3d/lpr/$s_lpr_sec}" "${l_tok:-$s_lpr_tok}" \
        "${l_sec:-$s_lpr_sec}" "${l_ctok:-$s_lpr_tok}"
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

unit_relay() {
    cat <<EOF
# Создано install_stand.sh. Править через drop-in: systemctl edit td-genset-relay
[Unit]
StartLimitIntervalSec=0
Description=TD stand: имитатор ретранслятора SmartGen HGM6120N (fake_relay, профиль D700)
Documentation=file://$TD_REPO/factory3d/tools/server/STAND.md
After=network.target

[Service]
Type=simple
$(unit_common)
EnvironmentFile=$RELAY_ENV
EnvironmentFile=-$ETC/genset-relay.local.env
WorkingDirectory=$PREFIX/genset-relay
ExecStart=$PREFIX/venv-relay/bin/python $PREFIX/genset-relay/fake_relay.py --quiet --hostid \${RELAY_HOSTID}
SyslogIdentifier=td-genset-relay
CapabilityBoundingSet=
MemoryHigh=128M
MemoryMax=256M
CPUQuota=50%
TasksMax=64
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
    if [[ $NO_RELAY -eq 0 ]]; then
        put_file "$UNIT_DIR/td-genset-relay.service" 644 root root < <(unit_relay)
        [[ "$PUT" == same ]] || { reload=1; CHANGED_RELAY=1; }
        [[ "$IP_FILTER" == 1 ]] ||
            warn "TD_IP_FILTER=0: имитатор ретранслятора слушает 0.0.0.0:$GENSET_RELAY_PORT без сетевого фильтра (защищают только токены)"
    fi
    is_loopback_url || warn "Odoo не на loopback ($ODOO_URL): сетевой фильтр сборщика отключён, у эмулятора остаётся только loopback"
    if sysctl_on && real && [[ $reload -eq 1 ]]; then systemctl daemon-reload; fi
}

start_units() {
    local relay_unit=""; [[ $NO_RELAY -eq 1 ]] || relay_unit="td-genset-relay.service"
    if ! sysctl_on; then plan "enable --now td-iot-sim td-collector ${relay_unit%.service} (systemd недоступен/--no-system: пропущено)"; return 0; fi
    if ! real; then plan "systemctl enable --now td-iot-sim td-collector ${relay_unit%.service} (restart, если изменились код/env/unit)"; return 0; fi
    systemctl enable td-iot-sim.service td-collector.service $relay_unit >/dev/null 2>&1
    if [[ ${CHANGED_SIM:-0} -eq 1 ]] && systemctl is-active -q td-iot-sim.service; then systemctl restart td-iot-sim.service; else systemctl start td-iot-sim.service; fi
    if [[ ${CHANGED_COL:-0} -eq 1 ]] && systemctl is-active -q td-collector.service; then systemctl restart td-collector.service; else systemctl start td-collector.service; fi
    if [[ -n "$relay_unit" ]]; then
        # перезапуск имитатора обнуляет его журнал показаний (id с 1): рестартуем только при изменении кода, env или unit
        if [[ ${CHANGED_RELAY:-0} -eq 1 ]] && systemctl is-active -q "$relay_unit"; then systemctl restart "$relay_unit"; else systemctl start "$relay_unit"; fi
    fi
    ok "службы включены и запущены"
}

# relay_get ПУТЬ — GET к имитатору ретранслятора с Bearer SIM-токеном из его env-файла (токен не попадает в аргументы curl).
relay_get() {
    local tok; tok="$(env_get "$RELAY_ENV" RELAY_SIM_TOKEN)"
    [[ -n "$tok" ]] || return 1
    curl -fsS --max-time 4 -K - "http://127.0.0.1:$GENSET_RELAY_PORT$1" <<<"header = \"Authorization: Bearer $tok\"" 2>/dev/null
}

relay_up() { local b; b="$(relay_get /sim/v1/state || true)"; [[ "$b" == *'"profile"'*'"D700"'* ]]; }

# lpr_probe — тот же путь и токен, что у эмулятора (с учётом iot-sim.local.env), но с телом «[]» на локальный :$PUSH_PORT.
# Сборщик отвечает 400 «json object expected», только если маршрут, секрет и токен приняты; событие при этом не создаётся.
# Печатает код HTTP (000 — нет ответа). Секреты в аргументы curl не попадают.
lpr_probe() {
    local url tok path
    url="$(eff_env_get "$SIM_LOCAL_ENV" "$SIM_ENV" SIM_LPR_PUSH_URL)" tok="$(eff_env_get "$SIM_LOCAL_ENV" "$SIM_ENV" SIM_LPR_PUSH_TOKEN)"
    [[ -n "$url" ]] || { echo none; return 0; }
    path="${url#*://}"; path="/${path#*/}"
    curl -sS --max-time 4 -o /dev/null -w '%{http_code}' -X POST -H 'Content-Type: application/json' -d '[]' -K - \
        "http://127.0.0.1:$PUSH_PORT$path" <<<"header = \"X-F3D-Token: $tok\"" 2>/dev/null || true
}

# lpr_diagnose КОД — 0, если сборщик принял путь эмулятора; иначе печатает причину и возвращает 1.
lpr_diagnose() {
    local health
    case "$1" in
        400 | 200) return 0 ;;
        none) echo "в iot-sim.env нет SIM_LPR_PUSH_URL"; return 1 ;;
        401) echo "токен не принят (401): SIM_LPR_PUSH_TOKEN эмулятора ≠ F3D_HTTP_PUSH_TOKEN_LPR сборщика (или ≠ значению по token_ref источника HTTP-PUSH)" ;;
        403) echo "IP отправителя не входит в allow_ips источника HTTP-PUSH (403): нужны iot-sim и 127.0.0.1 — stand_odoo_setup.py setup" ;;
        404)
            health="$(curl -fsS --max-time 3 "http://127.0.0.1:$PUSH_PORT/f3d/health" 2>/dev/null || true)"
            if [[ "$health" == *'"lpr"'* ]]; then
                echo "маршрут lpr у сборщика есть, но путь не принят (404): у источника HTTP-PUSH в Odoo нет params.secret_ref (тогда секретного сегмента в URL быть не должно) или секрет в URL ≠ F3D_HTTP_PUSH_SECRET_LPR; сверьте URL в iot-sim(.local).env и params источника — stand_odoo_setup.py status/params"
            else
                echo "сборщик не знает маршрута lpr (404; /f3d/health: ${health:-нет ответа}): источник HTTP-PUSH не дошёл до сборщика (не active, не привязан к коллектору, params.routes без lpr, в Odoo нет токена сборщика) или в error (нет F3D_HTTP_PUSH_*_LPR в env): stand_odoo_setup.py setup; journalctl -u td-collector | grep HTTP-PUSH"
            fi ;;
        000 | "") echo "сборщик не отвечает на :$PUSH_PORT (journalctl -u td-collector -n 50)" ;;
        *) echo "неожиданный ответ сборщика HTTP $1" ;;
    esac
    return 1
}

# check_lpr_route [ПОПЫТОК] — зонд пути LPR; с повторами по 5 с (сборщик берёт конфигурацию из Odoo при старте).
check_lpr_route() {
    local tries=${1:-1} i code msg=""
    for ((i = 1; i <= tries; i++)); do
        code="$(lpr_probe)"
        if msg="$(lpr_diagnose "$code")"; then ok "LPR: сборщик принял путь эмулятора (HTTP $code на пустое тело — маршрут, секрет и токен верны)"; return 0; fi
        [[ $i -ge $tries ]] || sleep 5
    done
    warn "LPR эмулятор → сборщик: $msg"
}

wait_health() {
    if ! sysctl_on || ! real; then return 0; fi
    local sim=0 col=0 rel=0
    [[ $NO_RELAY -eq 0 ]] || rel=1
    log "жду готовности служб (до 90 с)"
    for _ in $(seq 1 45); do
        if [[ $sim -eq 0 ]] && curl -fsS --max-time 3 http://127.0.0.1:8090/sim/v1/health >/dev/null 2>&1; then sim=1; fi
        if [[ $col -eq 0 ]] && curl -fsS --max-time 3 http://127.0.0.1:9108/health >/dev/null 2>&1; then col=1; fi
        if [[ $rel -eq 0 ]] && relay_up; then rel=1; fi
        if [[ $sim -eq 1 && $col -eq 1 && $rel -eq 1 ]]; then break; fi
        sleep 2
    done
    [[ $sim -eq 1 ]] || warn "эмулятор не ответил на :8090 (journalctl -u td-iot-sim -n 50; при status=226/NAMESPACE — TD_HARDEN=0)"
    [[ $col -eq 1 ]] || warn "сборщик не ответил на :9108 (journalctl -u td-collector -n 50; при status=226/NAMESPACE — TD_HARDEN=0)"
    [[ $rel -eq 1 ]] || warn "имитатор ретранслятора не ответил на :$GENSET_RELAY_PORT/sim/v1/state (journalctl -u td-genset-relay -n 50; при status=226/NAMESPACE — TD_HARDEN=0)"
    if [[ $col -eq 1 ]]; then check_lpr_route 4; fi
}

# ---------------------------------------------------------------- состояние
show_status() {
    local u v tok body
    log "состояние стенда"
    if sysctl_on; then
        for u in td-iot-sim td-collector td-genset-relay mosquitto; do
            printf '   %-16s active=%-10s enabled=%-9s перезапусков=%s память=%s\n' "$u" \
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
    if [[ $NO_RELAY -eq 0 ]]; then
        v="$(relay_get /sim/v1/state | cut -c1-160 || true)"
        printf '   ретранслятор (имитатор) :%s/sim/v1/state  %s\n' "$GENSET_RELAY_PORT" "${v:-не отвечает (или нет прав на $RELAY_ENV)}"
    fi
    v="$(lpr_probe)"
    if body="$(lpr_diagnose "$v")"; then body="принят"; fi
    printf '   LPR эмулятор → сборщик (зонд с пустым телом, ждём 400)  HTTP %s  %s\n' "$v" "$body"
    printf '   Odoo      %s/web/health      %s\n' "$ODOO_URL" "$(curl -sS -o /dev/null -w '%{http_code}' --max-time 4 "$ODOO_URL/web/health" 2>/dev/null || echo нет)"
    tok="$(env_get "$COL_ENV" F3D_COLLECTOR_TOKEN)"
    if [[ -n "$tok" ]]; then
        body="$(curl -sS --max-time 8 -K - "$ODOO_URL/f3d/telemetry/health" <<<"header = \"Authorization: Bearer $tok\"" 2>/dev/null | cut -c1-300 || true)"
        printf '   Odoo /f3d/telemetry/health (с токеном): %s\n' "${body:-нет ответа}"
    fi
    if sysctl_on; then
        for u in td-iot-sim td-collector td-genset-relay; do
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
        for u in td-collector.service td-iot-sim.service td-genset-relay.service; do
            if systemctl cat "$u" >/dev/null 2>&1; then
                if real; then systemctl disable --now "$u" >/dev/null 2>&1 || true; ok "остановлена и отключена $u"; else plan "остановить и отключить $u"; fi
            fi
        done
    fi
    local f
    for f in "$UNIT_DIR/td-iot-sim.service" "$UNIT_DIR/td-collector.service" "$UNIT_DIR/td-genset-relay.service"; do
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
    resolve_params
    if [[ $STATUS_ONLY -eq 1 ]]; then show_status; return 0; fi
    if [[ $UNINSTALL -eq 1 ]]; then
        [[ $EUID -eq 0 || $CHECK -eq 1 ]] || die "запустите через sudo"
        do_uninstall
        return 0
    fi
    preflight
    if [[ $BLOCKERS -gt 0 ]] && real; then die "есть препятствия ($BLOCKERS), установка не начата. Исправьте и запустите снова."; fi
    CHANGED_SIM=0 CHANGED_COL=0 CHANGED_RELAY=0
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
