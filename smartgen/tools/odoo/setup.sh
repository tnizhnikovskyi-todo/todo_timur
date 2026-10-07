#!/usr/bin/env bash
# Идемпотентная сборка среды Odoo 18.0 CE для разработки и тестов td_genset.
#
#   setup.sh                 — всё по порядку: pg odoo venv conf template
#   setup.sh <шаг> [<шаг>…]  — отдельные шаги:
#       pg        Postgres: кластер, настройки, роль odoo, ~/.pgpass   (= pg.sh init)
#       odoo      клон odoo/odoo ветки 18.0 (--depth 1) в $ODOO_HOME, если его ещё нет
#       venv      venv на Python 3.12 + зависимости из requirements.txt
#                 (psycopg2 → psycopg2-binary: нет libpq-dev; python-ldap пропущен: нет libldap-dev)
#       conf      конфиг $ODOO_CONF (не перезаписывает существующий; FORCE=1 — перезаписать)
#       template  (пере)собрать шаблонную базу $TD_TEMPLATE_DB без демо-данных
#       check     прогнать тесты /maintenance на копии шаблона (проверка тестовой инфраструктуры)
#
# Все пути — в env.sh. Сеть нужна только шагам odoo и venv (GitHub, PyPI).
set -euo pipefail
# shellcheck source=env.sh
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"

step_pg() { "$TD_TOOLS_DIR/pg.sh" init; }

step_odoo() {
    if [[ -f "$ODOO_BIN" ]]; then
        td_log "Odoo уже на месте: $ODOO_HOME ($(git -C "$ODOO_HOME" log -1 --format='%h %cd' --date=short 2>/dev/null || echo '?'))"
        return
    fi
    td_log "клонирую $ODOO_REPO_URL ($ODOO_BRANCH, --depth 1) в $ODOO_HOME (~1.3 ГБ)"
    git clone --depth 1 --branch "$ODOO_BRANCH" --single-branch "$ODOO_REPO_URL" "$ODOO_HOME"
}

step_venv() {
    [[ -f "$ODOO_HOME/requirements.txt" ]] || td_die "нет $ODOO_HOME/requirements.txt (сначала шаг odoo)"
    [[ -x "$ODOO_PYTHON_BIN" ]] || td_die "нет $ODOO_PYTHON_BIN; поставьте Python 3.12 (например, 'uv python install 3.12') и задайте ODOO_PYTHON_BIN"
    if [[ ! -x "$ODOO_PY" ]]; then
        td_log "создаю venv $ODOO_VENV на $("$ODOO_PYTHON_BIN" --version)"
        "$ODOO_PYTHON_BIN" -m venv "$ODOO_VENV"
    fi
    local req="$ODOO_VENV/requirements-odoo.txt"
    sed -E -e 's/^psycopg2==/psycopg2-binary==/' -e '/^python-ldap/d' "$ODOO_HOME/requirements.txt" > "$req"
    # websocket-client — для HttpCase/туров (Chrome DevTools), pdfminer.six — индексация вложений
    local extra=(websocket-client pdfminer.six)
    td_log "ставлю зависимости ($req + ${extra[*]})"
    if command -v uv >/dev/null; then
        uv pip install --quiet --python "$ODOO_PY" -r "$req" "${extra[@]}"
    else
        "$ODOO_PY" -m pip install --quiet --upgrade pip
        "$ODOO_PY" -m pip install --quiet -r "$req" "${extra[@]}"
    fi
    "$ODOO_PY" -c 'import psycopg2, lxml, gevent, PIL, reportlab, werkzeug, websocket; print("venv OK:", __import__("sys").version.split()[0])'
}

step_conf() {
    if [[ -f "$ODOO_CONF" && "${FORCE:-0}" != "1" ]]; then
        td_log "конфиг уже есть: $ODOO_CONF (FORCE=1 — перезаписать)"
        return
    fi
    local admin_pw
    admin_pw="$(python3 -c 'import secrets; print(secrets.token_hex(16))')"
    mkdir -p "$ODOO_DATA_DIR" "$ODOO_LOG_DIR" "$ODOO_RUN_DIR"
    (umask 077; cat > "$ODOO_CONF") <<EOF
; Создано smartgen/tools/odoo/setup.sh — Odoo 18.0 CE для разработки и тестов td_genset.
[options]
addons_path = $ODOO_HOME/addons,$TD_ADDONS_DIR
data_dir = $ODOO_DATA_DIR
db_host = $PGHOST
db_port = $PGPORT
db_user = $PGUSER
db_password = ${TD_PG_PASSWORD:-odoo}
db_maxconn = 32
http_interface = $ODOO_HTTP_INTERFACE
http_port = 8069
limit_time_real = 600
limit_time_real_cron = 600
limit_time_cpu = 600
max_cron_threads = 1
without_demo = all
admin_passwd = $admin_pw
EOF
    td_log "записан конфиг $ODOO_CONF"
}

step_template() {
    td_check_env
    td_require_pg
    local log="$ODOO_LOG_DIR/template-$(date +%Y%m%d-%H%M%S).log" t0 rc
    if td_db_exists "$TD_TEMPLATE_DB"; then
        td_log "удаляю старую $TD_TEMPLATE_DB"
        td_psql -c "alter database \"$TD_TEMPLATE_DB\" with is_template false allow_connections true"
        "$PG_BINDIR/dropdb" --force "$TD_TEMPLATE_DB"
    fi
    rm -rf -- "${ODOO_DATA_DIR:?}/filestore/$TD_TEMPLATE_DB"
    td_log "собираю $TD_TEMPLATE_DB: -i $TD_TEMPLATE_MODULES, без демо (лог: $log)"
    t0=$(date +%s)
    set +e
    td_odoo -d "$TD_TEMPLATE_DB" -i "$TD_TEMPLATE_MODULES" --without-demo=all --stop-after-init \
        --http-port="$(td_free_port)" > "$log" 2>&1
    rc=$?
    set -e
    if [[ $rc -ne 0 ]] || td_log_has_errors "$log"; then
        td_log_errors "$log" 100 >&2
        tail -n 20 "$log" >&2
        td_die "сборка шаблона не удалась (код $rc), лог: $log"
    fi
    # Шаблон: только для CREATE DATABASE … TEMPLATE; подключаться к нему нельзя, поэтому
    # клонирование не упрётся в «source database is being accessed by other users».
    td_psql -c "alter database \"$TD_TEMPLATE_DB\" with is_template true allow_connections false"
    td_log "шаблон $TD_TEMPLATE_DB готов за $(( $(date +%s) - t0 )) с"
}

step_check() {
    local db=td_check_env log port rc t0
    td_check_env
    td_require_pg
    t0=$(date +%s)
    td_clone_db "$db"
    td_log "копия шаблона $db создана за $(( $(date +%s) - t0 )) с; запускаю тесты /maintenance"
    log="$ODOO_LOG_DIR/check-maintenance-$(date +%Y%m%d-%H%M%S).log"
    port="$(td_free_port)"
    set +e
    td_odoo -d "$db" --test-enable --test-tags /maintenance --stop-after-init --log-level=test \
        --http-port="$port" > "$log" 2>&1
    rc=$?
    set -e
    grep -E 'odoo\.tests\.(result|stats)' "$log" | sed -E 's/^[^ ]+ [^ ]+ [0-9]+ //' >&2 || true
    if [[ $rc -ne 0 ]] || td_log_has_errors "$log"; then
        td_log_errors "$log" 100 >&2
        td_die "проверка не прошла (код $rc), лог: $log"
    fi
    td_drop_db "$db"
    td_log "проверка OK за $(( $(date +%s) - t0 )) с (лог: $log)"
}

steps=("$@")
[[ ${#steps[@]} -gt 0 ]] || steps=(pg odoo venv conf template)
for s in "${steps[@]}"; do
    case "$s" in
        pg|odoo|venv|conf|template|check) "step_$s" ;;
        *) td_die "неизвестный шаг '$s' (pg odoo venv conf template check)" 2 ;;
    esac
done
