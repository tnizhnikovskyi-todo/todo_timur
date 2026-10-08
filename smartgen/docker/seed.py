# Docker-стенд td_genset: начальная настройка базы после установки модуля.
#
# Запуск (entrypoint.sh делает это один раз, при первом старте):
#     odoo shell -c /etc/odoo/odoo.conf -d genset < seed.py
# Повторный запуск безопасен: записи ищутся по логину / hostid / ключу параметра и приводятся к описанию
# ниже, ничего не дублируется (в выводе — «создан» или «уже есть»).
#
# Что настраивается:
#   * язык uk_UA активен; валюта компании — UAH (суммы заправок в модуле подписаны «грн»);
#   * системные параметры td_genset.relay_url и td_genset.relay_token — эмулятор (сервис relay);
#   * пользователи qa_s / qa_a / qa_t (пароль = логин) с группами «Генератори: Співробітник / Адміністратор /
#     Тех. адміністратор»; admin / admin; у всех язык uk_UA, часовой пояс Europe/Kyiv, уведомления — в Odoo;
#   * ланцюжок ескалації: рівень 1 «Черговий» — qa_s, 2 «Відповідальний за об'єкт» — qa_a, 3 «Керівник» — qa_t;
#   * генератор «Стенд» (HGM6120N, 30 kW, бак 145 L) с hostid эмулятора, «Опитувати ретранслятор» и «Дозволити
#     команди» включены (это эмулятор), відповідальний — qa_a, розклад пн–пт 08:45–18:30.
#
# Параметры — переменные окружения (по умолчанию — значения Docker-стенда):
#   STAND_RELAY_URL    адрес API эмулятора     http://relay:8081/api/v1
#   STAND_RELAY_TOKEN  токен эмулятора          dev-токен из smartgen/relay_api.md §10
#   STAND_HOSTID       hostid модуля эмулятора  5354414E442D444F434B4552 («STAND-DOCKER» в hex)
import os
import sys
from datetime import datetime, timezone

RELAY_URL = os.environ.get('STAND_RELAY_URL', 'http://relay:8081/api/v1').rstrip('/')
RELAY_TOKEN = os.environ.get('STAND_RELAY_TOKEN', 'dev-token-0123456789abcdefghij')
HOSTID = os.environ.get('STAND_HOSTID', '5354414E442D444F434B4552')
LANG = 'uk_UA'
TZ = 'Europe/Kyiv'
SEEDED_KEY = 'td_genset_stand.seeded_at'
GENSET_NAME = 'Стенд'
USERS = (
    # логин (= пароль), имя, группа модуля, рівень ланцюжка ескалації
    ('qa_s', 'QA Співробітник', 'td_genset.group_user', 'td_genset.level_1'),
    ('qa_a', 'QA Адміністратор', 'td_genset.group_admin', 'td_genset.level_2'),
    ('qa_t', 'QA Тех. адміністратор', 'td_genset.group_tech', 'td_genset.level_3'),
)
WEEKDAYS = ('0', '1', '2', '3', '4')     # пн–пт
WINDOW = (8.75, 18.5)                   # 08:45 → Авто, 18:30 → Ручний + Стоп (київський час)


def say(text):
    print('[seed] %s' % text, flush=True)


def user_vals(users_model, **vals):
    """Общие поля пользователя стенда; уведомления — во «Входящие» Odoo (почтового сервера на стенде нет)."""
    vals.update(lang=LANG, tz=TZ)
    if 'notification_type' in users_model._fields:
        vals['notification_type'] = 'inbox'
    return vals


def ensure_language(env):
    lang = env['res.lang'].with_context(active_test=False).search([('code', '=', LANG)], limit=1)
    if not lang:
        sys.exit('[seed] ОШИБКА: язык %s не найден в res.lang' % LANG)
    if lang.active:
        say('язык %s: уже активен' % LANG)
        return
    env['base.language.install'].create({'lang_ids': [(6, 0, lang.ids)], 'overwrite': False}).lang_install()
    say('язык %s: активирован, переводы загружены' % LANG)


def ensure_currency(env):
    company = env.ref('base.main_company')
    uah = env.ref('base.UAH', raise_if_not_found=False)
    if not uah:
        say('валюта UAH не найдена — валюта компании не менялась')
    elif company.currency_id == uah:
        say('валюта компании: уже UAH')
    else:
        uah.active = True
        company.currency_id = uah
        say('валюта компании: UAH')


def ensure_relay_params(env):
    icp = env['ir.config_parameter'].sudo()
    for key, value, shown in (('td_genset.relay_url', RELAY_URL, RELAY_URL),
                              ('td_genset.relay_token', RELAY_TOKEN, 'токен эмулятора (dev)')):
        if icp.get_param(key) == value:
            say('%s: уже %s' % (key, shown))
        else:
            icp.set_param(key, value)
            say('%s: %s' % (key, shown))


def password_matches(user, password):
    """Пароль уже такой? Проверка без записи: запись пароля отправляет письмо «Пароль змінено», а почты на стенде нет."""
    user.env.cr.execute("SELECT COALESCE(password, '') FROM res_users WHERE id = %s", [user.id])
    hashed = user.env.cr.fetchone()[0]
    try:
        return bool(hashed) and user._crypt_context().verify(password, hashed)
    except ValueError:
        return False


def ensure_users(env):
    users_model = env['res.users'].with_context(active_test=False, no_reset_password=True)
    result = {}
    for login, name, group_xmlid, _level in USERS:
        group = env.ref(group_xmlid)
        user = users_model.search([('login', '=', login)], limit=1)
        if user:
            vals = user_vals(users_model, active=True, groups_id=[(4, group.id)])
            reset = not password_matches(user, login)
            if reset:
                vals['password'] = login
            user.write(vals)
            say('пользователь %s: уже есть — группа «%s», язык, часовой пояс%s'
                % (login, group.name, '; пароль снова %s' % login if reset else ''))
        else:
            user = users_model.create(user_vals(
                users_model, name=name, login=login, password=login, email='%s@example.com' % login,
                groups_id=[(6, 0, [group.id])]))
            say('пользователь %s / %s: создан, группа «%s»' % (login, login, group.name))
        result[login] = user
    admin = env.ref('base.user_admin')
    vals = user_vals(users_model)
    if not password_matches(admin, 'admin'):
        vals['password'] = 'admin'
    admin.write(vals)
    say('пользователь admin / admin: язык %s, часовой пояс %s%s'
        % (LANG, TZ, '; пароль снова admin' if 'password' in vals else ''))
    root = env.ref('base.user_root', raise_if_not_found=False)
    if root:   # OdooBot: от его имени работают задачи cron (тексты в чатере, даты)
        root.with_context(active_test=False).write({'lang': LANG, 'tz': TZ})
    return result


def ensure_escalation(env, users):
    for login, _name, _group, level_xmlid in USERS:
        level = env.ref(level_xmlid, raise_if_not_found=False)
        if not level:
            say('рівень %s не найден — пропущен' % level_xmlid)
            continue
        if level.user_id == users[login]:
            say('ланцюжок: «%s» (%s хв) — уже %s' % (level.name, level.delay_min, login))
        else:
            level.user_id = users[login]
            say('ланцюжок: «%s» (%s хв) — %s' % (level.name, level.delay_min, login))


def ensure_genset(env, users):
    gensets = env['td.genset'].with_context(active_test=False)
    genset = gensets.search([('relay_hostid', '=', HOSTID)], limit=1)
    if genset:
        genset.write({'active': True, 'relay_enabled': True, 'commands_allowed': True})
        say('генератор «%s» (hostid %s): уже есть — опрос и команды включены' % (genset.name, HOSTID))
    else:
        genset = gensets.create({
            'name': GENSET_NAME,
            'address': 'Docker-стенд: емулятор ретранслятора (сервіс relay)',
            'controller_model_id': env.ref('td_genset.controller_hgm6120n').id,
            'power_kw': 30.0,
            'tank_volume_l': 145.0,
            'user_id': users['qa_a'].id,
            'relay_hostid': HOSTID,
            'relay_note': 'Емулятор smartgen/tools/fake_relay.py у контейнері relay. hostid — лише для стенду: '
                          'у справжнього модуля CMM366B інший.',
            'relay_enabled': True,
            'commands_allowed': True,
        })
        say('генератор «%s»: создан (HGM6120N, 30 kW, бак 145 L, hostid %s, опрос и команды включены)'
            % (genset.name, HOSTID))
    schedule = env['td.genset.schedule']
    created = 0
    for day in WEEKDAYS:
        if not schedule.search_count([('genset_id', '=', genset.id), ('dayofweek', '=', day)]):
            schedule.create({'genset_id': genset.id, 'dayofweek': day,
                             'time_start': WINDOW[0], 'time_end': WINDOW[1], 'enabled': True})
            created += 1
    say('розклад пн–пт 08:45–18:30: %s' % ('создано окон: %d' % created if created else 'уже есть'))
    return genset


def check_environment(env):
    """Диагностика без изменений: часовой пояс в Postgres и ответ эмулятора."""
    env.cr.execute("SELECT name FROM pg_timezone_names WHERE name IN ('Europe/Kyiv', 'Europe/Kiev')")
    known = sorted(row[0] for row in env.cr.fetchall())
    if 'Europe/Kyiv' in known:
        say('PostgreSQL знает часовые пояса: %s' % ', '.join(known))
    else:
        say('ВНИМАНИЕ: PostgreSQL не знает Europe/Kyiv — аналитика по дням может падать')
    try:
        status = env['td.genset.relay.client'].status()
        device = env['td.genset.relay.client'].device_status(status, HOSTID)
        say('эмулятор отвечает: версия %s, модуль %s' % (
            (status.get('relay') or {}).get('version', '?'),
            'на связи' if device and device.get('online') else 'не найден или не на связи'))
    except Exception as exc:  # noqa: BLE001 — эмулятор может подняться позже: cron заберёт данные сам
        say('ВНИМАНИЕ: эмулятор пока не ответил (%s) — Odoo будет опрашивать его каждую минуту' % exc)


def main(env):
    if 'td.genset' not in env:
        sys.exit('[seed] ОШИБКА: модуль td_genset не установлен в базе %s' % env.cr.dbname)
    say('база %s: настройка стенда' % env.cr.dbname)
    ensure_language(env)
    ensure_currency(env)
    ensure_relay_params(env)
    users = ensure_users(env)
    ensure_escalation(env, users)
    ensure_genset(env, users)
    check_environment(env)
    env['ir.config_parameter'].sudo().set_param(
        SEEDED_KEY, datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC'))
    env.cr.commit()
    say('готово. Вход: admin / admin; qa_s / qa_s, qa_a / qa_a, qa_t / qa_t. '
        'Генератори → Генератор → «%s»' % GENSET_NAME)


main(env)  # noqa: F821 — env задаёт odoo shell
