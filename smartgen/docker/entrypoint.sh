#!/bin/bash
# Docker-стенд td_genset: точка входа контейнера odoo (docker-compose.yml: entrypoint bash /opt/stand/entrypoint.sh).
#
# Каждый старт: дождаться Postgres и проверить базу genset.
#   * базы нет / модуль не установлен → odoo -i base,td_genset --load-language=uk_UA --without-demo=all
#     --stop-after-init (первый старт, обычно 3–5 мин);
#   * стенд ещё не настроен → odoo shell < seed.py (ретранслятор, «Стенд», пользователи). Seed выполняется один
#     раз: после него в базе есть системный параметр td_genset_stand.seeded_at, и при перезапусках настройки,
#     изменённые вручную (например, адрес ретранслятора), не перезаписываются;
#   * затем exec odoo -c … -d genset: HTTP 8069, /websocket и cron (max_cron_threads = 1) в одном процессе.
#
# Переменные (для проверки вне Docker): STAND_CONF, STAND_DB, STAND_SEED; odoo должен быть в PATH.
set -euo pipefail

CONF="${STAND_CONF:-/etc/odoo/odoo.conf}"
DB="${STAND_DB:-genset}"
SEED="${STAND_SEED:-/opt/stand/seed.py}"

log() { printf '[stand] %s\n' "$*"; }

# Состояние базы: missing | empty | not_installed | not_seeded | ready. Ждёт Postgres до 120 с.
# Параметры подключения — из [options] конфига Odoo (db_host, db_port, db_user, db_password).
db_state() {
    python3 - "$CONF" "$DB" <<'PY'
import configparser
import sys
import time

import psycopg2

conf_path, dbname = sys.argv[1], sys.argv[2]
parser = configparser.RawConfigParser()
if not parser.read(conf_path) or not parser.has_section('options'):
    sys.exit('[stand] не прочитан конфиг Odoo: %s' % conf_path)
options = dict(parser.items('options'))


def option(key, default):
    value = (options.get(key) or '').strip()
    return default if value in ('', 'False', 'None') else value


params = {'host': option('db_host', 'db'), 'port': int(option('db_port', '5432')),
          'user': option('db_user', 'odoo'), 'connect_timeout': 5}
if option('db_password', ''):
    params['password'] = option('db_password', '')

deadline = time.time() + 120
while True:
    try:
        conn = psycopg2.connect(dbname='postgres', **params)
        break
    except psycopg2.OperationalError as exc:
        if time.time() > deadline:
            sys.exit('[stand] Postgres %s:%s не отвечает 120 с: %s' % (params['host'], params['port'], exc))
        time.sleep(2)
with conn.cursor() as cr:
    cr.execute('SELECT 1 FROM pg_database WHERE datname = %s', (dbname,))
    exists = cr.fetchone() is not None
conn.close()
if not exists:
    print('missing')
    sys.exit(0)

conn = psycopg2.connect(dbname=dbname, **params)
with conn.cursor() as cr:
    cr.execute("SELECT to_regclass('ir_module_module') IS NOT NULL AND to_regclass('ir_config_parameter') IS NOT NULL")
    if not cr.fetchone()[0]:
        state = 'empty'
    else:
        cr.execute("SELECT name, state FROM ir_module_module WHERE name IN ('base', 'td_genset')")
        modules = dict(cr.fetchall())
        if modules.get('base') != 'installed':
            state = 'empty'              # установка base прервалась — ставить заново base + td_genset
        elif modules.get('td_genset') != 'installed':
            state = 'not_installed'
        else:
            cr.execute("SELECT 1 FROM ir_config_parameter WHERE key = 'td_genset_stand.seeded_at'")
            state = 'ready' if cr.fetchone() else 'not_seeded'
conn.close()
print(state)
PY
}

state="$(db_state)"
log "база ${DB}: ${state}"

case "$state" in
    missing|empty)
        log "Первый старт: установка base + td_genset, язык uk_UA, без демо-данных (обычно 3–5 мин)…"
        odoo -c "$CONF" -d "$DB" -i base,td_genset --load-language=uk_UA --without-demo=all --stop-after-init
        state=not_seeded
        ;;
    not_installed)
        log "Модуль td_genset не установлен (прошлая установка прервалась?) — установка…"
        odoo -c "$CONF" -d "$DB" -i td_genset --load-language=uk_UA --without-demo=all --stop-after-init
        state=not_seeded
        ;;
esac

if [[ "$state" == "not_seeded" ]]; then
    log "Настройка стенда: seed.py…"
    odoo shell -c "$CONF" -d "$DB" < "$SEED"
fi

log "Запуск Odoo: http://localhost:8069 (admin / admin). Первые данные «Стенда» — примерно через минуту."
exec odoo -c "$CONF" -d "$DB"
