#!/usr/bin/env bash
# Ідемпотентна збірка середовища Odoo 19.0 CE для розробки і тестів модулів factory3d.
#
#   setup.sh                 — усе по порядку: pg odoo venv conf template (що вже готове — пропускається)
#   setup.sh <крок> [<крок>…] — окремі кроки:
#       pg        Postgres: пакет (apt, якщо немає), кластер, налаштування, роль odoo, ~/.pgpass   (= pg.sh init)
#       odoo      клон odoo/odoo гілки 19.0 (--depth 1) у $ODOO_HOME, якщо його ще немає
#       venv      venv на Python 3.12 + залежності з requirements.txt
#                 (psycopg2 → psycopg2-binary: немає libpq-dev; python-ldap пропущено: немає libldap-dev)
#       conf      конфіг $ODOO_CONF (не перезаписує наявний; FORCE=1 — перезаписати)
#       template  (пере)зібрати шаблонну базу $F3D_TEMPLATE_DB без демо-даних. У повному запуску
#                 пропускається, якщо шаблон уже зібраний з тим самим комітом Odoo і списком модулів;
#                 явний `setup.sh template` перезбирає завжди.
#       check     прогнати post_install-тести /maintenance (вкл. тур у Chrome) на копії шаблона (перевірка тестової інфраструктури)
#
# Усі шляхи — в env.sh. Мережа потрібна кроками pg (apt, лише якщо Postgres не встановлений),
# odoo і venv (GitHub, PyPI); мережеві команди повторюються 2/4/8/16 с.
# Наприкінці друкується час роботи і список стандартних модулів, яких немає в Community
# (звіт також у $ODOO_DATA_DIR/template-report.txt).
set -euo pipefail
# shellcheck source=env.sh
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"

T_START=$(date +%s)
REPORT_FILE="$ODOO_DATA_DIR/template-report.txt"
STAMP_FILE="$ODOO_DATA_DIR/template.stamp"

step_pg() { "$F3D_TOOLS_DIR/pg.sh" init; }

clone_odoo() {
    # недокачаний клон з минулої спроби — прибираємо (каталог без odoo-bin, але з .git)
    if [[ -e "$ODOO_HOME" && ! -f "$ODOO_BIN" ]]; then
        [[ -d "$ODOO_HOME/.git" || -z "$(ls -A "$ODOO_HOME" 2>/dev/null)" ]] \
            || f3d_die "$ODOO_HOME існує, але це не клон Odoo (немає odoo-bin і .git) — приберіть його або задайте ODOO_HOME"
        rm -rf -- "${ODOO_HOME:?}"
    fi
    git clone --quiet --depth 1 --branch "$ODOO_BRANCH" --single-branch "$ODOO_REPO_URL" "$ODOO_HOME"
}

step_odoo() {
    if [[ -f "$ODOO_BIN" ]]; then
        f3d_log "Odoo вже на місці: $ODOO_HOME ($(git -C "$ODOO_HOME" log -1 --format='%h %cd' --date=short 2>/dev/null || echo '?'))"
        return
    fi
    f3d_log "клоную $ODOO_REPO_URL ($ODOO_BRANCH, --depth 1) у $ODOO_HOME (~1.4 ГБ)"
    f3d_retry clone_odoo
}

# Інтерпретатор для venv: заданий → системні 3.12/3.13/3.11/3.10 → uv python install 3.12.
pick_python() {
    local c
    if [[ -x "$ODOO_PYTHON_BIN" ]]; then return 0; fi
    for c in python3.12 python3.13 python3.11 python3.10; do
        if command -v "$c" >/dev/null; then ODOO_PYTHON_BIN="$(command -v "$c")"; return 0; fi
    done
    if command -v uv >/dev/null; then
        f3d_log "системного Python 3.10+ немає — ставлю 3.12 через uv"
        f3d_retry uv python install 3.12
        ODOO_PYTHON_BIN="$(uv python find 3.12)"
        return 0
    fi
    f3d_die "немає Python 3.10+; встановіть Python 3.12 (наприклад, 'uv python install 3.12') і задайте ODOO_PYTHON_BIN"
}

step_venv() {
    [[ -f "$ODOO_HOME/requirements.txt" ]] || f3d_die "немає $ODOO_HOME/requirements.txt (спершу крок odoo)"
    pick_python
    if [[ ! -x "$ODOO_PY" ]]; then
        f3d_log "створюю venv $ODOO_VENV на $("$ODOO_PYTHON_BIN" --version)"
        if command -v uv >/dev/null; then
            uv venv --quiet --python "$ODOO_PYTHON_BIN" "$ODOO_VENV"
        else
            "$ODOO_PYTHON_BIN" -m venv "$ODOO_VENV"
        fi
    fi
    local req="$ODOO_VENV/requirements-odoo.txt"
    sed -E -e 's/^psycopg2==/psycopg2-binary==/' -e '/^python-ldap/d' "$ODOO_HOME/requirements.txt" > "$req"
    # websocket-client — для HttpCase/турів (Chrome DevTools), pdfminer.six — індексація вкладень
    local extra=(websocket-client pdfminer.six)
    f3d_log "ставлю залежності ($req + ${extra[*]})"
    if command -v uv >/dev/null; then
        f3d_retry uv pip install --quiet --python "$ODOO_PY" -r "$req" "${extra[@]}"
    else
        "$ODOO_PY" -m pip install --quiet --upgrade pip
        f3d_retry "$ODOO_PY" -m pip install --quiet -r "$req" "${extra[@]}"
    fi
    "$ODOO_PY" -c 'import psycopg2, lxml, gevent, PIL, reportlab, werkzeug, websocket; print("venv OK:", __import__("sys").version.split()[0])'
}

step_conf() {
    if [[ -f "$ODOO_CONF" && "${FORCE:-0}" != "1" ]]; then
        f3d_log "конфіг уже є: $ODOO_CONF (FORCE=1 — перезаписати)"
        return
    fi
    local admin_pw
    admin_pw="$(python3 -c 'import secrets; print(secrets.token_hex(16))')"
    mkdir -p "$ODOO_DATA_DIR" "$ODOO_LOG_DIR" "$ODOO_RUN_DIR"
    (umask 077; cat > "$ODOO_CONF") <<EOF
; Створено factory3d/tools/odoo/setup.sh — Odoo 19.0 CE для розробки і тестів factory3d.
; addons_path тут довідковий: скрипти передають --addons-path свого worktree явно.
[options]
addons_path = $ODOO_HOME/addons,$F3D_ADDONS_DIR
data_dir = $ODOO_DATA_DIR
db_host = $PGHOST
db_port = $PGPORT
db_user = $PGUSER
db_password = ${F3D_PG_PASSWORD:-odoo}
db_maxconn = 32
http_interface = $ODOO_HTTP_INTERFACE
http_port = 8069
limit_time_real = 600
limit_time_real_cron = 600
limit_time_cpu = 600
max_cron_threads = 1
without_demo = True
admin_passwd = $admin_pw
EOF
    f3d_log "записано конфіг $ODOO_CONF"
}

# Розкласти $F3D_TEMPLATE_MODULES на доступні (є в Community і installable) та недоступні.
# Заповнює масиви TPL_AVAILABLE і TPL_MISSING (рядки "модуль — причина").
classify_template_modules() {
    local m dir
    TPL_AVAILABLE=(); TPL_MISSING=()
    for m in ${F3D_TEMPLATE_MODULES//,/ }; do
        if ! dir="$(f3d_odoo_module_dir "$m")"; then
            TPL_MISSING+=("$m — немає в Odoo $ODOO_BRANCH Community (каталог із __manifest__.py відсутній; Enterprise?)")
        elif grep -qE "['\"]installable['\"]\s*:\s*False" "$dir/__manifest__.py"; then
            TPL_MISSING+=("$m — каталог є, але installable=False")
        else
            TPL_AVAILABLE+=("$m")
        fi
    done
}

template_stamp() {
    printf 'odoo=%s\nmodules=%s\npython=%s\n' \
        "$(git -C "$ODOO_HOME" rev-parse HEAD 2>/dev/null || echo '?')" \
        "$F3D_TEMPLATE_MODULES" "$("$ODOO_PY" -c 'import sys; print(sys.version.split()[0])')"
}

template_is_current() {
    f3d_db_exists "$F3D_TEMPLATE_DB" && [[ -f "$STAMP_FILE" ]] && [[ "$(cat "$STAMP_FILE")" == "$(template_stamp)" ]]
}

print_report() {
    [[ -f "$REPORT_FILE" ]] && cat "$REPORT_FILE" >&2
    return 0
}

step_template() {
    f3d_check_env
    f3d_require_pg
    classify_template_modules
    local log="$ODOO_LOG_DIR/template-$(date +%Y%m%d-%H%M%S).log" t0 rc m state
    local modules
    modules="$(IFS=,; echo "${TPL_AVAILABLE[*]}")"
    [[ -n "$modules" ]] || f3d_die "ні один зі стандартних модулів не доступний — перевірте ODOO_HOME ($ODOO_HOME)"
    if f3d_db_exists "$F3D_TEMPLATE_DB"; then
        f3d_log "видаляю стару $F3D_TEMPLATE_DB"
        f3d_psql -c "alter database \"$F3D_TEMPLATE_DB\" with is_template false allow_connections true"
        "$PG_BINDIR/dropdb" --force "$F3D_TEMPLATE_DB"
    fi
    rm -rf -- "${ODOO_DATA_DIR:?}/filestore/$F3D_TEMPLATE_DB" "$STAMP_FILE"
    f3d_log "збираю $F3D_TEMPLATE_DB: -i $modules, без демо (лог: $log)"
    t0=$(date +%s)
    set +e
    f3d_odoo -d "$F3D_TEMPLATE_DB" -i "$modules" --without-demo=True --stop-after-init \
        --http-port="$(f3d_free_port)" > "$log" 2>&1
    rc=$?
    set -e
    if [[ $rc -ne 0 ]] || f3d_log_has_errors "$log"; then
        f3d_log_errors "$log" 100 >&2
        tail -n 20 "$log" >&2
        f3d_die "збірка шаблона не вдалась (код $rc), лог: $log"
    fi
    # Звіт: реальні стани модулів у щойно зібраній базі (до того, як її закрито для підключень).
    {
        echo "Шаблон $F3D_TEMPLATE_DB, Odoo $ODOO_BRANCH ($(git -C "$ODOO_HOME" log -1 --format='%h %cd' --date=short 2>/dev/null || echo '?')):"
        for m in "${TPL_AVAILABLE[@]}"; do
            state="$(f3d_module_state "$F3D_TEMPLATE_DB" "$m")"
            echo "  ${state:-немає запису}: $m"
        done
        echo "Недоступні стандартні модулі (пропущені):"
        if [[ ${#TPL_MISSING[@]} -gt 0 ]]; then printf '  %s\n' "${TPL_MISSING[@]}"; else echo "  (немає)"; fi
    } > "$REPORT_FILE"
    for m in "${TPL_AVAILABLE[@]}"; do
        state="$(f3d_module_state "$F3D_TEMPLATE_DB" "$m")"
        [[ "$state" == "installed" ]] || { print_report; f3d_die "модуль $m не встановився в шаблон (стан: ${state:-немає запису}), лог: $log"; }
    done
    # Шаблон: лише для CREATE DATABASE … TEMPLATE; підключатися до нього не можна, тому
    # клонування не впреться в «source database is being accessed by other users».
    f3d_psql -c "alter database \"$F3D_TEMPLATE_DB\" with is_template true allow_connections false"
    template_stamp > "$STAMP_FILE"
    f3d_log "шаблон $F3D_TEMPLATE_DB готовий за $(( $(date +%s) - t0 )) с"
}

# Повний запуск: перезбирати шаблон лише коли він застарів або його немає.
step_template_if_needed() {
    f3d_check_env
    f3d_require_pg
    if template_is_current; then
        f3d_log "шаблон $F3D_TEMPLATE_DB актуальний (той самий коміт Odoo і список модулів) — пропускаю (setup.sh template — перезібрати)"
        return
    fi
    step_template
}

step_check() {
    local db=f3d_check log port rc t0 tags="${F3D_CHECK_TAGS:-/maintenance,-at_install}"
    f3d_check_env
    f3d_require_pg
    t0=$(date +%s)
    f3d_clone_db "$db"
    f3d_log "копія шаблона $db створена за $(( $(date +%s) - t0 )) с; запускаю тести $tags"
    log="$ODOO_LOG_DIR/check-$(date +%Y%m%d-%H%M%S).log"
    f3d_pick_port "$db"; port="$F3D_PORT"
    set +e
    f3d_odoo -d "$db" --test-enable --test-tags "$tags" --stop-after-init --log-level=test \
        --http-port="$port" > "$log" 2>&1
    rc=$?
    set -e
    grep -E 'odoo\.tests\.(result|stats)' "$log" | sed -E 's/^[^ ]+ [^ ]+ [0-9]+ //' | tail -n 8 >&2 || true
    if [[ $rc -ne 0 ]] || f3d_log_has_errors "$log"; then
        f3d_log_errors "$log" 100 >&2
        f3d_die "перевірка не пройшла (код $rc), лог: $log"
    fi
    f3d_drop_db "$db"
    f3d_log "перевірка OK за $(( $(date +%s) - t0 )) с (лог: $log)"
}

steps=("$@")
full=0
if [[ ${#steps[@]} -eq 0 ]]; then steps=(pg odoo venv conf template_if_needed); full=1; fi
for s in "${steps[@]}"; do
    case "$s" in
        pg|odoo|venv|conf|template|check) "step_$s" ;;
        template_if_needed) [[ $full -eq 1 ]] && step_template_if_needed ;;
        *) f3d_die "невідомий крок '$s' (pg odoo venv conf template check)" 2 ;;
    esac
done

f3d_log "готово за $(( $(date +%s) - T_START )) с"
[[ " ${steps[*]} " == *" template "* || $full -eq 1 ]] && print_report || true
