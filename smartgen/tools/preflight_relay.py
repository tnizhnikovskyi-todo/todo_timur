#!/usr/bin/env python3
"""Передпольотна перевірка ретранслятора SmartGen для модуля td_genset — ЛИШЕ ЧИТАННЯ (жодного POST).

Запускається на сервері Odoo (тестовому чи проді) перед увімкненням «Опитувати ретранслятор»: перевіряє той самий
мережевий шлях, яким ходитиме модуль (HTTPS із системними сертифікатами, проксі з оточення, таймаут 20 с), і що
ретранслятор віддає знімки потрібного модуля зв'язку. Лише стандартна бібліотека Python 3.8+.

Адреса й токен — ТІЛЬКИ з аргументів або змінних оточення (у коді їх немає):
    TD_GENSET_RELAY_URL     адреса API, напр. https://<relay-host>/api/v1  (або --url)
    TD_GENSET_RELAY_TOKEN   токен Bearer                                  (або --token-file; --token видно в ps)

Приклади:
    export TD_GENSET_RELAY_URL='https://<relay-host>/api/v1'
    read -rs TD_GENSET_RELAY_TOKEN && export TD_GENSET_RELAY_TOKEN       # токен не потрапляє в історію shell
    python3 preflight_relay.py --hostid 3130373031334717003D002E
    python3 preflight_relay.py --hostid 3130373031334717003D002E --psql 'host=127.0.0.1 dbname=<база> user=odoo'
    /opt/odoo/venv/bin/python3 preflight_relay.py ...    # тим самим Python, що й Odoo: перевірка pytz Europe/Kyiv

Що перевіряє:
    • TLS (для https): сертифікат дійсний для хоста, ланцюжок довіри системи, скільки днів до закінчення;
    • GET /status: версія, commands_enabled, snapshot_sec, годинник ретранслятора проти годинника сервера,
      devices[]: online, seconds_since_seen, commands_ready, controller_mode, registers_known/coils_known, last_reading;
    • GET /latest?hostid=: ключові значення знімка, наявність *_sensor_ohm (з 1.1.3) — інакше модуль читає raw=1;
    • GET /readings?since=<last-5>&limit=5: курсор (id зростають, next_since = останній id), свіжість знімків;
      GET /readings?since=<last-1>&limit=1&raw=1: регістри 18/20/22 для омів датчиків (ретранслятор < 1.1.3);
    • часові пояси: Python (zoneinfo, pytz — якщо є) і, з --psql, PostgreSQL (pg_timezone_names: Europe/Kyiv
      обов'язково; Europe/Kiev — попередження, ENV-1).
Переадресації не виконуються (токен не піде на інший хост). Токен у звіт і в лог не виводиться.

Код виходу: 0 — ГОТОВО до етапу 1 (лише читання); 1 — НЕ ГОТОВО (причини у звіті); 2 — помилка запуску.
Готовність до етапу 2 (команди) показується окремим рядком і на код виходу не впливає.
"""
import argparse
import datetime as dt
import json
import os
import socket
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import urlencode, urlsplit

URL_ENV = 'TD_GENSET_RELAY_URL'
TOKEN_ENV = 'TD_GENSET_RELAY_TOKEN'
DEFAULT_TIMEOUT = 20            # як td_genset.http_timeout у модулі
ONLINE_MAX_S = 90               # devices[].online — модуль щось надсилав за останні 90 с
LINK_LOST_S = 180               # модуль вважає зв'язок втраченим через 3 хв без даних
CLOCK_SKEW_WARN_S = 30
CLOCK_SKEW_FAIL_S = 90
CERT_DAYS_WARN = 14
OHM_KEYS = ('fuel_level_sensor_ohm', 'water_temp_sensor_ohm', 'oil_pressure_sensor_ohm')
OHM_REGS = (('22', 'паливо'), ('18', 'температура ОР'), ('20', 'тиск оливи'))
KEY_VALUES = (
    ('controller_mode', 'режим'), ('genset_status_text', 'стан агрегату'), ('mains_normal', 'мережа в нормі'),
    ('mains_on_load', 'автомат мережі'), ('gen_on_load', 'автомат генератора'), ('remote_lock', 'блокування'),
    ('common_alarm', 'загальна тривога'), ('fuel_level', 'паливо, %'), ('battery_v', 'АКБ, V'),
    ('run_hours', 'мотогодини'), ('start_count', 'пусків'),
)


class Report:
    """Рядки звіту: OK / WARN / FAIL / INFO; FAIL — причина «НЕ ГОТОВО»."""

    def __init__(self):
        self.lines = []
        self.failures = []
        self.warnings = []
        self.stage2 = []

    def add(self, level, text):
        self.lines.append((level, text))
        if level == 'FAIL':
            self.failures.append(text)
        elif level == 'WARN':
            self.warnings.append(text)
        print('[%-4s] %s' % (level, text), flush=True)

    def ok(self, text):
        self.add('OK', text)

    def warn(self, text):
        self.add('WARN', text)

    def fail(self, text):
        self.add('FAIL', text)

    def info(self, text):
        self.add('INFO', text)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """Без переадресацій: інакше urllib переніс би заголовок Authorization на іншу адресу."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url, code, 'redirect to %s refused' % newurl, headers, fp)


class Relay:
    """GET-клієнт API ретранслятора (POST у цьому скрипті немає взагалі)."""

    def __init__(self, base_url, token, timeout, cafile=None):
        self.base_url = base_url.rstrip('/')
        self.token = token
        self.timeout = timeout
        context = ssl.create_default_context(cafile=cafile)     # перевірка сертифіката й імені хоста — завжди
        self.opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=context), NoRedirect())

    def get(self, path, **params):
        """→ (status, body: dict|None, ms, error_text). Мережеві помилки — status None."""
        query = {key: value for key, value in params.items() if value is not None}
        url = self.base_url + path + ('?' + urlencode(query) if query else '')
        request = urllib.request.Request(url, method='GET', headers={
            'Authorization': 'Bearer %s' % self.token, 'Accept': 'application/json',
            'User-Agent': 'td_genset-preflight/1.0'})
        started = time.monotonic()
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                raw = response.read()
                status = response.status
        except urllib.error.HTTPError as exc:
            raw = exc.read() if exc.fp else b''
            status = exc.code
        except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError, ssl.SSLError) as exc:
            reason = getattr(exc, 'reason', exc)
            return None, None, int((time.monotonic() - started) * 1000), '%s: %s' % (type(reason).__name__, reason)
        ms = int((time.monotonic() - started) * 1000)
        try:
            body = json.loads(raw.decode('utf-8')) if raw else None
        except (UnicodeDecodeError, ValueError):
            body = None
        error = body.get('error') if isinstance(body, dict) else None
        if not (200 <= status < 300) and not error:
            error = 'HTTP %s' % status
        return status, body, ms, error


def parse_utc(text):
    if not text:
        return None
    try:
        return dt.datetime.strptime(str(text)[:19], '%Y-%m-%dT%H:%M:%S').replace(tzinfo=dt.timezone.utc)
    except ValueError:
        return None


def ago(seconds):
    seconds = int(seconds)
    if seconds < 120:
        return '%d с' % seconds
    if seconds < 7200:
        return '%d хв' % (seconds // 60)
    if seconds < 172800:
        return '%d год' % (seconds // 3600)
    return '%d дн' % (seconds // 86400)


def check_tls(report, url, timeout, cafile=None):
    """https: рукостискання з перевіркою сертифіката (як requests verify=True); http — лише для емулятора."""
    parts = urlsplit(url)
    if parts.scheme != 'https':
        return
    host, port = parts.hostname, parts.port or 443
    if urllib.request.getproxies().get('https'):
        report.info('TLS: HTTPS іде через проксі з оточення — сертифікат перевіряється разом із запитами нижче')
        return
    context = ssl.create_default_context(cafile=cafile)
    try:
        with socket.create_connection((host, port), timeout=min(timeout, 10)) as sock:
            with context.wrap_socket(sock, server_hostname=host) as tls:
                cert = tls.getpeercert()
                version = tls.version()
    except ssl.SSLCertVerificationError as exc:
        report.fail('TLS: сертифікат %s не пройшов перевірку: %s' % (host, exc.verify_message or exc))
        return
    except (OSError, ssl.SSLError) as exc:
        report.fail('TLS: немає з\'єднання з %s:%s (%s: %s) — перевірте вихідний HTTPS з цього сервера'
                    % (host, port, type(exc).__name__, exc))
        return
    subject = dict(item[0] for item in cert.get('subject', ()))
    issuer = dict(item[0] for item in cert.get('issuer', ()))
    not_after = dt.datetime.fromtimestamp(ssl.cert_time_to_seconds(cert['notAfter']), tz=dt.timezone.utc)
    days = (not_after - dt.datetime.now(dt.timezone.utc)).days
    text = 'TLS %s: сертифікат перевірено (CN=%s, видавець %s, дійсний до %s — %d дн)' % (
        version, subject.get('commonName', '?'), issuer.get('organizationName') or issuer.get('commonName', '?'),
        not_after.strftime('%Y-%m-%d'), days)
    (report.warn if days < CERT_DAYS_WARN else report.ok)(text)


def check_status(report, relay, hostid):
    """GET /status → (device, relay_info) або (None, None)."""
    status, body, ms, error = relay.get('/status')
    if status is None:
        report.fail('GET /status: ретранслятор недоступний (%s) — мережа/фаєрвол/DNS/проксі' % error)
        return None, None
    if status == 401:
        report.fail('GET /status → 401: токен не прийнято (%s)' % error)
        return None, None
    if status != 200 or not isinstance(body, dict):
        report.fail('GET /status → %s: %s' % (status, error or 'не JSON'))
        return None, None
    info = body.get('relay') or {}
    version = info.get('version') or '?'
    report.ok('GET /status — 200 за %d мс; ретранслятор %s, знімки кожні %s с, працює %s'
              % (ms, version, info.get('snapshot_sec', '?'), ago(info.get('uptime_s') or 0)))
    relay_time = parse_utc(info.get('time_utc'))
    if relay_time:
        skew = (relay_time - dt.datetime.now(dt.timezone.utc)).total_seconds()
        text = 'Годинник: ретранслятор %+d с відносно цього сервера' % skew
        if abs(skew) >= CLOCK_SKEW_FAIL_S:
            report.fail(text + ' — модуль рахує «зв\'язок втрачено» за часом сервера Odoo; синхронізуйте NTP')
        elif abs(skew) >= CLOCK_SKEW_WARN_S:
            report.warn(text + ' — перевірте NTP')
        else:
            report.ok(text)
    if info.get('commands_enabled'):
        report.info('Команди на ретрансляторі: дозволено (relay.commands_enabled = true) — у Odoo їх стримує '
                    'перемикач «Дозволити команди» (за замовчуванням вимкнено)')
    else:
        report.info('Команди на ретрансляторі: вимкнено (RELAY_COMMANDS_ENABLED=0) — етап 1 це не заважає')
        report.stage2.append('relay.commands_enabled = false')
    devices = body.get('devices') or []
    known = [item.get('hostid') for item in devices]
    if hostid:
        device = next((item for item in devices if item.get('hostid') == hostid), None)
        if not device:
            report.fail('Модуля hostid %s на ретрансляторі немає; відомі: %s' % (hostid, ', '.join(map(str, known))
                                                                                 or '—'))
            return None, info
    elif len(devices) == 1:
        device = devices[0]
        report.warn('hostid не задано (--hostid) — беру єдиний модуль %s; у картці генератора вкажіть саме його'
                    % device.get('hostid'))
    else:
        report.fail('hostid не задано, а модулів %d (%s) — вкажіть --hostid' % (len(devices), ', '.join(map(str,
                                                                                                    known))))
        return None, info
    seen = device.get('seconds_since_seen')
    online = bool(device.get('online'))
    text = 'Модуль %s: %s, бачили %s тому, режим контролера: %s' % (
        device.get('hostid'), 'онлайн' if online else 'НЕ на зв\'язку', ago(seen or 0),
        device.get('controller_mode') or 'невідомо')
    (report.ok if online and (seen or 0) <= ONLINE_MAX_S else report.fail)(text)
    regs, coils = device.get('registers_known') or 0, device.get('coils_known') or 0
    text = 'Образ контролера: регістрів %s, сигналів %s (норма 55 / 80)' % (regs, coils)
    if not regs or not coils:
        report.fail(text + ' — ретранслятор не розбирає дані')
    elif (regs, coils) != (55, 80):
        report.warn(text)
    else:
        report.ok(text)
    ready = bool(device.get('commands_ready'))
    report.info('Готовність до команд (commands_ready): %s; довге з\'єднання: %s; формат команд: %s' % (
        'так' if ready else 'ні', 'так' if device.get('long_connection') else 'ні',
        device.get('command_format') or 'не вивчено'))
    if not ready:
        report.stage2.append('commands_ready = false')
    cloud = device.get('cloud_commands_seen') or []
    if cloud:
        nulls = sum(1 for item in cloud if isinstance(item, dict) and item.get('command') is None)
        report.info('cloud_commands_seen: %d записів (без назви команди — %d; модуль обробляє і такі)'
                    % (len(cloud), nulls))
    return device, info


def check_latest(report, relay, hostid, version):
    status, body, ms, error = relay.get('/latest', hostid=hostid)
    if status == 404 and error and 'no readings' in error:
        report.fail('GET /latest → 404: знімків ще немає (модуль ще нічого не надсилав)')
        return None
    if status != 200 or not isinstance(body, dict):
        report.fail('GET /latest → %s: %s' % (status, error or 'не JSON'))
        return None
    values = body.get('values') or {}
    stamp = parse_utc(body.get('time_utc'))
    age = (dt.datetime.now(dt.timezone.utc) - stamp).total_seconds() if stamp else None
    text = 'GET /latest — 200 за %d мс; знімок id %s (%s), %s тому' % (
        ms, body.get('id'), body.get('reason'), ago(age) if age is not None else '?')
    (report.ok if age is not None and age <= LINK_LOST_S else report.fail)(
        text if age is not None and age <= LINK_LOST_S else text + ' — знімки не надходять')
    shown = []
    for key, label in KEY_VALUES:
        if key in values:
            value = values[key]
            shown.append('%s: %s' % (label, 'немає даних' if value is None else value))
    report.info('Знімок: ' + '; '.join(shown))
    missing = [key for key in ('controller_mode', 'genset_status', 'mains_normal', 'fuel_level') if key not in values]
    if missing:
        report.warn('У знімку немає ключів %s — модуль покаже «немає даних»' % ', '.join(missing))
    ohms = [key for key in OHM_KEYS if key in values]
    if ohms:
        report.ok('Оми датчиків у values (ретранслятор ≥ 1.1.3): %s' % ', '.join(
            '%s=%s' % (key, values[key]) for key in ohms))
    else:
        report.info('Ключів *_sensor_ohm немає (ретранслятор %s): модуль в режимі «Автоматично» читає raw=1 і '
                    'бере оми з регістрів 18/20/22' % version)
    return body


def check_readings(report, relay, hostid, last_id):
    since = max(int(last_id or 0) - 5, 0)
    status, body, ms, error = relay.get('/readings', since=since, limit=5, hostid=hostid)
    if status != 200 or not isinstance(body, dict):
        report.fail('GET /readings?since=%s&limit=5 → %s: %s' % (since, status, error or 'не JSON'))
        return
    readings = body.get('readings') or []
    ids = [item.get('id') for item in readings]
    problems = []
    if not readings:
        problems.append('порожньо')
    if ids != sorted(ids) or len(set(ids)) != len(ids):
        problems.append('id не зростають: %s' % ids)
    if any((item or 0) <= since for item in ids):
        problems.append('є id ≤ since')
    if readings and body.get('next_since') != ids[-1]:
        problems.append('next_since %s ≠ останній id %s' % (body.get('next_since'), ids[-1]))
    text = 'GET /readings?since=%s&limit=5 — 200 за %d мс; id %s, next_since %s' % (
        since, ms, ids, body.get('next_since'))
    if problems:
        report.fail(text + ' — ' + '; '.join(problems))
    else:
        report.ok(text + ' (курсор коректний)')
    status, body, ms, error = relay.get('/readings', since=max(int(last_id or 0) - 1, 0), limit=1, hostid=hostid,
                                        raw=1)
    page = (body or {}).get('readings') if status == 200 and isinstance(body, dict) else None
    if not page:
        report.warn('GET /readings …&raw=1 → %s: %s' % (status, error or 'порожньо'))
        return
    regs = page[0].get('regs') or {}
    found = ['%s %s Ом' % (label, regs[reg] / 10.0) for reg, label in OHM_REGS
             if isinstance(regs.get(reg), (int, float))]
    if found:
        report.ok('raw=1 — %d мс; оми з регістрів 18/20/22: %s' % (ms, ', '.join(found)))
    else:
        report.warn('raw=1: у сирому образі немає регістрів 18/20/22 — літри лише за % контролера')


def check_python_tz(report):
    try:
        import zoneinfo     # noqa: PLC0415 — Python 3.9+
        zoneinfo.ZoneInfo('Europe/Kyiv')
        report.ok('Python %s: zoneinfo знає Europe/Kyiv' % sys.version.split()[0])
    except ImportError:
        report.info('Python %s без zoneinfo — пропущено' % sys.version.split()[0])
    except Exception as exc:  # noqa: BLE001
        report.warn('zoneinfo не знає Europe/Kyiv (%s) — оновіть системний tzdata' % exc)
    try:
        import pytz         # noqa: PLC0415
    except ImportError:
        report.info('pytz у цьому Python немає — щоб перевірити Python Odoo, запустіть скрипт інтерпретатором Odoo')
        return
    try:
        pytz.timezone('Europe/Kyiv')
        report.ok('pytz %s знає Europe/Kyiv (модуль td_genset рахує розклад і журнал за ним)' % pytz.__version__)
    except Exception as exc:  # noqa: BLE001
        report.fail('pytz %s не знає Europe/Kyiv (%s) — модуль td_genset не завантажиться; оновіть pytz/tzdata'
                    % (getattr(pytz, '__version__', '?'), type(exc).__name__))


def check_pg_timezones(report, dsn):
    """``psql -X -A -t`` (PG* і ~/.pgpass з оточення). Europe/Kyiv — обов'язково; Europe/Kiev — ENV-1."""
    query = ("SELECT name FROM pg_timezone_names WHERE name IN ('Europe/Kyiv', 'Europe/Kiev') ORDER BY name")
    command = ['psql', '-X', '-A', '-t', '-v', 'ON_ERROR_STOP=1', '-c', query]
    if dsn:
        command.insert(1, dsn)
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
    except FileNotFoundError:
        report.warn('psql не знайдено — перевірте вручну: %s' % query)
        return
    except subprocess.TimeoutExpired:
        report.warn('psql не відповів за 30 с — перевірте вручну: %s' % query)
        return
    if result.returncode != 0:
        report.warn('psql завершився з кодом %s (%s) — перевірте вручну: %s' % (
            result.returncode, ' '.join((result.stderr or '').split())[:200], query))
        return
    names = set(line.strip() for line in result.stdout.splitlines() if line.strip())
    if 'Europe/Kyiv' in names:
        report.ok('PostgreSQL знає Europe/Kyiv')
    else:
        report.fail('PostgreSQL не знає Europe/Kyiv — аналітика з групуванням за днями впаде; оновіть tzdata '
                    'сервера БД')
    if 'Europe/Kiev' in names:
        report.ok('PostgreSQL знає й Europe/Kiev (стара назва)')
    else:
        report.warn('PostgreSQL не знає Europe/Kiev (немає tzdata-legacy, ENV-1): користувачам модуля — часовий '
                    'пояс Europe/Kyiv (Odoo при першому вході з браузера може записати Europe/Kiev)')


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='Передпольотна перевірка ретранслятора SmartGen для td_genset (лише GET, без POST).')
    parser.add_argument('--url', default=os.environ.get(URL_ENV),
                        help='адреса API, напр. https://<relay-host>/api/v1 (або змінна %s)' % URL_ENV)
    parser.add_argument('--token-file', help='файл з токеном (або змінна %s)' % TOKEN_ENV)
    parser.add_argument('--token', help='токен (НЕ рекомендовано: видно в списку процесів; краще %s)' % TOKEN_ENV)
    parser.add_argument('--hostid', help='hostid модуля зв\'язку (24 символи), як у картці генератора')
    parser.add_argument('--timeout', type=float, default=DEFAULT_TIMEOUT, help='таймаут запиту, с (20)')
    parser.add_argument('--cafile', help='додатковий файл CA (якщо вихід — через корпоративний проксі з TLS)')
    parser.add_argument('--allow-http', action='store_true', help='дозволити http:// (лише локальний емулятор)')
    parser.add_argument('--psql', nargs='?', const='', metavar='DSN',
                        help="перевірити pg_timezone_names через psql (DSN, напр. 'host=… dbname=… user=…'; "
                             "без значення — PG* з оточення)")
    args = parser.parse_args(argv)

    token = args.token or os.environ.get(TOKEN_ENV)
    if args.token_file:
        try:
            with open(args.token_file, encoding='utf-8') as handle:
                token = handle.read().strip()
        except OSError as exc:
            parser.error('не прочитано --token-file: %s' % exc)
    if not args.url:
        parser.error('не задано адресу: --url або %s' % URL_ENV)
    if not token:
        parser.error('не задано токен: %s або --token-file' % TOKEN_ENV)
    scheme = urlsplit(args.url).scheme
    if scheme not in ('https', 'http') or (scheme == 'http' and not args.allow_http):
        parser.error('адреса має бути https://… (http — лише з --allow-http для емулятора)')

    report = Report()
    now = dt.datetime.now(dt.timezone.utc)
    print('Передпольотна перевірка ретранслятора SmartGen (лише читання, без POST) — %s UTC, вузол %s'
          % (now.strftime('%Y-%m-%d %H:%M:%S'), socket.gethostname()))
    print('Адреса: %s; токен: задано (%d симв., у звіт не виводиться); таймаут %s с' % (
        args.url.rstrip('/'), len(token), args.timeout))
    proxies = {key: value.split('@')[-1] for key, value in urllib.request.getproxies().items()
               if key in ('http', 'https', 'no')}
    if proxies:
        print('Проксі з оточення (так само піде й Odoo, якщо в його оточенні ті самі змінні): %s' % proxies)
    print()

    check_tls(report, args.url, args.timeout, args.cafile)
    relay = Relay(args.url, token, args.timeout, args.cafile)
    device, info = check_status(report, relay, args.hostid)
    if device:
        hostid = device.get('hostid')
        version = (info or {}).get('version') or '?'
        latest = check_latest(report, relay, hostid, version)
        last_id = ((device.get('last_reading') or {}).get('id')) or (latest or {}).get('id')
        if last_id:
            check_readings(report, relay, hostid, last_id)
        if latest and (latest.get('values') or {}).get('remote_lock'):
            report.stage2.append('remote_lock = true (блокування на контролері)')
    check_python_tz(report)
    if args.psql is not None:
        check_pg_timezones(report, args.psql)

    print()
    if report.failures:
        print('ПІДСУМОК: НЕ ГОТОВО до етапу 1 — причини:')
        for text in report.failures:
            print('  • ' + text)
    else:
        print('ПІДСУМОК: ГОТОВО до етапу 1 (лише читання: «Опитувати ретранслятор»)%s'
              % (' — з попередженнями: %d' % len(report.warnings) if report.warnings else ''))
    if not report.failures and not report.stage2:
        print('Етап 2 (команди): з боку ретранслятора готово; у Odoo — лише після протоколу DEPLOY_TEST.md, розділ D')
    elif report.stage2:
        print('Етап 2 (команди): НЕ готово — %s' % '; '.join(report.stage2))
    return 1 if report.failures else 0


if __name__ == '__main__':
    sys.exit(main())
