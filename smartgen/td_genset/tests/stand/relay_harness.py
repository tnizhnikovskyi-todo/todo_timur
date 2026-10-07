# Part of td_genset (ToDo). Власник файлу: W5 «Стенд і документація».
"""Обв'язка стендових тестів навколо емулятора ``smartgen/tools/fake_relay.py`` (без імпорту Odoo).

* ``SimClient`` — HTTP-клієнт емулятора: API ретранслятора (з токеном) і службовий ``/_sim`` (без токена,
  лише з 127.0.0.1). Іде напряму, повз проксі; таймаути короткі; очікування — опитуванням з ``time.sleep``
  і лічильником кроків (у тестах Odoo ``freezegun`` підміняє ``time.time``, тому годинник процесу тут не
  використовується).
* ``spawn_relay()`` — власний екземпляр емулятора на вільному порту (``subprocess``): версія 1.1.1 для AC-68
  і сценарії з керованим годинником; ``RelayProcess.stop()`` гасить процес (``tearDown``).
* Запуск цього файлу як скрипта (так його запускає ``spawn_relay``) — емулятор з годинником: модуль
  ``fake_relay.py`` завантажується як є, його ``time.time()`` зсувається на ``--clock-offset`` секунд, а
  ``POST /_sim`` приймає додатковий ключ ``{"clock_advance": N}`` — зсунути годинник емулятора вперед на N с
  (знімки, ``ts``/``*_utc``, ``seconds_since_seen``, тайм-аути команд і фізика генератора бачать «минулий»
  час). Файл емулятора не змінюється; ключ потрібен, доки в самому ``fake_relay.py`` немає керування часом.
"""
import argparse
import importlib.util
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

FAKE_RELAY_ENV = 'TD_GENSET_FAKE_RELAY'
KEEP_LOGS_ENV = 'TD_GENSET_STAND_KEEP_LOGS'
LOOPBACK_HOSTS = ('127.0.0.1', 'localhost', '::1')
POLL_STEP = 0.05


class StandError(Exception):
    """Стенд відповів не так, як очікувалося від емулятора (не 2xx у ``/_sim``, процес не стартував …)."""


class StandTimeout(AssertionError):
    """Не дочекалися стану стенду за відведений час — тест падає з поясненням (не «висне»)."""


def fake_relay_path():
    """Шлях до ``smartgen/tools/fake_relay.py`` (поруч із модулем у репозиторії) або ``$TD_GENSET_FAKE_RELAY``."""
    path = os.environ.get(FAKE_RELAY_ENV)
    if path:
        return path
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(here, '..', '..', '..', 'tools', 'fake_relay.py'))


def is_loopback_url(url):
    """Стенд — лише локальний емулятор (жодних звернень до реального ретранслятора)."""
    host = urllib.parse.urlsplit(url or '').hostname or ''
    return host in LOOPBACK_HOSTS or host.startswith('127.')


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def wait_until(predicate, timeout=5.0, message='стан стенду', step=POLL_STEP):
    """Опитувати ``predicate()`` до істинного результату (повертає його) або ``StandTimeout`` через ``timeout`` с."""
    for _ in range(max(1, int(timeout / step))):
        result = predicate()
        if result:
            return result
        time.sleep(step)
    result = predicate()
    if result:
        return result
    raise StandTimeout('Стенд: не дочекалися «%s» за %.1f с' % (message, timeout))


class SimClient:
    """Клієнт емулятора: ``api_url`` = ``http://127.0.0.1:<port>/api/v1``; ``/_sim`` — ``sim_url``."""

    def __init__(self, api_url, token, sim_url=None, timeout=10):
        self.api_url = api_url.rstrip('/')
        self.token = token
        self.sim_url = sim_url or (self.api_url + '/_sim')
        self.timeout = timeout
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    # ------------------------------------------------------------------ HTTP
    def _call(self, method, url, body=None, token=None):
        data = None if body is None else json.dumps(body).encode('utf-8')
        request = urllib.request.Request(url, data=data, method=method)
        if token:
            request.add_header('Authorization', 'Bearer ' + token)
        if data is not None:
            request.add_header('Content-Type', 'application/json')
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                raw = response.read().decode('utf-8')
                return response.status, (json.loads(raw) if raw else None)
        except urllib.error.HTTPError as err:
            raw = err.read().decode('utf-8', 'replace')
            try:
                payload = json.loads(raw) if raw else None
            except ValueError:
                payload = raw
            return err.code, payload

    def api(self, method, path, params=None, body=None, token=None):
        """Запит до API ретранслятора → ``(код, тіло)``; ``token=None`` — токен стенду."""
        url = self.api_url + path
        if params:
            url += '?' + urllib.parse.urlencode(params)
        return self._call(method, url, body, token=self.token if token is None else token)

    def api_ok(self, method, path, params=None, body=None):
        status, payload = self.api(method, path, params=params, body=body)
        if status not in (200, 201):
            raise StandError('%s %s → %s: %s' % (method, path, status, payload))
        return payload

    def sim(self, **keys):
        """``POST /_sim`` з ключами емулятора (``reset``, ``link``, ``set``, ``snapshot`` …) → стан симуляції."""
        status, payload = self._call('POST', self.sim_url, keys)
        if status != 200:
            raise StandError('POST /_sim %s → %s: %s' % (json.dumps(keys, ensure_ascii=False), status, payload))
        return payload

    def sim_state(self):
        status, payload = self._call('GET', self.sim_url)
        if status != 200:
            raise StandError('GET /_sim → %s: %s' % (status, payload))
        return payload

    def has_sim(self):
        """Чи це ``fake_relay.py`` (є службовий ``/_sim``)."""
        try:
            status, payload = self._call('GET', self.sim_url)
        except OSError:
            return False
        return status == 200 and isinstance(payload, dict) and 'devices' in payload

    # ------------------------------------------------------------------ API ретранслятора
    def status(self):
        return self.api_ok('GET', '/status')

    def device(self):
        return self.status()['devices'][0]

    def readings(self, since=0, raw=False):
        """Усі знімки з ``id > since`` (сторінками по 2000), як їх віддає ``GET /readings``."""
        result = []
        while True:
            params = {'since': since, 'limit': 2000}
            if raw:
                params['raw'] = 1
            page = self.api_ok('GET', '/readings', params=params)
            result.extend(page['readings'])
            if len(page['readings']) < 2000:
                return result
            since = page['next_since']

    def latest(self, raw=False):
        return self.api_ok('GET', '/latest', params={'raw': 1} if raw else None)

    def commands(self, since=0):
        return self.api_ok('GET', '/commands', params={'since': since, 'limit': 2000})['commands']

    def command(self, relay_cmd_id):
        return self.api_ok('GET', '/commands/%d' % relay_cmd_id)

    def post_command(self, command, requested_by='Стенд: підготовка', source='stand:setup'):
        """Команда в обхід Odoo (підготовка стенду, як оператор стенду)."""
        status, payload = self.api('POST', '/commands', body={
            'command': command, 'requested_by': requested_by, 'source': source})
        if status != 201:
            raise StandError('POST /commands %s → %s: %s' % (command, status, payload))
        return payload

    # ------------------------------------------------------------------ стан симуляції
    def device_state(self):
        return self.sim_state()['devices'][0]

    def values(self):
        """Поточний образ контролера (``values`` наступного знімка)."""
        return self.device_state()['values']

    def last_ids(self):
        return self.sim_state()['last_ids']

    def last_reading_id(self):
        return self.last_ids()['reading']

    def snapshot(self):
        """Знімок «зараз» (``{"snapshot": true}``) → його ``id``."""
        return self.sim(snapshot=True)['last_ids']['reading']

    def wait_first_reading(self, timeout=5.0):
        return wait_until(lambda: self.last_reading_id() > 0, timeout, 'перший знімок емулятора')

    def wait_values(self, predicate, timeout=5.0, message='стан контролера'):
        """Дочекатися образу контролера, для якого ``predicate(values)`` істинний; повертає ``values``."""
        def check():
            values = self.values()
            return values if predicate(values) else None
        return wait_until(check, timeout, message)

    def wait_mode(self, mode, timeout=5.0):
        return self.wait_values(lambda v: v.get('controller_mode') == mode, timeout, 'режим %s' % mode)

    def wait_command_final(self, relay_cmd_id, timeout=5.0, raise_on_timeout=True):
        """Дочекатися фінального статусу команди на ретрансляторі (``done``/``failed``/``timeout``)."""
        def check():
            cmd = self.command(relay_cmd_id)
            return cmd if cmd['status'] not in ('queued', 'sent') else None
        try:
            return wait_until(check, timeout, 'команда %s на ретрансляторі' % relay_cmd_id)
        except StandTimeout:
            if raise_on_timeout:
                raise
            return self.command(relay_cmd_id)

    def wait_tick(self, timeout=1.0):
        """Дочекатися наступного кроку емулятора: пакет модуля (``last_ids.raw`` росте; пакет — що 5 с часу
        емулятора, тож після зсуву годинника — одразу), інакше (немає зв'язку, малий зсув) — 0,25 с (≥ 2 цикли
        тікера по 0,1 с). Стан ``/_sim`` читається під замком емулятора — крок уже завершений."""
        state = self.sim_state()
        if state['devices'][0]['link']:
            before = state['last_ids']['raw']
            try:
                wait_until(lambda: self.last_ids()['raw'] > before, timeout, 'крок емулятора')
                return
            except StandTimeout:
                pass
        time.sleep(0.25)

    def advance(self, seconds):
        """Зсунути годинник емулятора вперед (лише екземпляр з ``spawn_relay``) і дочекатися його кроку."""
        state = self.sim(clock_advance=float(seconds))
        self.wait_tick()
        return state


class RelayProcess:
    """Власний процес емулятора (``spawn_relay``): ``client``, ``port``, ``token``, ``log_path``, ``stop()``."""

    def __init__(self, process, client, port, token, log_path, log_file):
        self.process = process
        self.client = client
        self.port = port
        self.token = token
        self.log_path = log_path
        self._log_file = log_file

    def log_tail(self, lines=20):
        try:
            with open(self.log_path, encoding='utf-8', errors='replace') as handle:
                return ''.join(handle.readlines()[-lines:])
        except OSError:
            return ''

    def stop(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        if not self._log_file.closed:
            self._log_file.close()
        if os.environ.get(KEEP_LOGS_ENV) != '1':
            try:
                os.unlink(self.log_path)
            except OSError:
                pass


def spawn_relay(token, version='1.1.3', snapshot_sec=10, time_scale=20, clock_offset=0.0, hostid=None,
                commands_disabled=False):
    """Підняти власний ``fake_relay.py`` (з годинником ``clock_offset``, с) на вільному порту → ``RelayProcess``.

    Параметри — як у CLI емулятора (``--relay-version``, ``--snapshot-sec``, ``--time-scale``, ``--hostid``,
    ``--commands-disabled``; шум напруг вимкнено). Без файлу емулятора — ``FileNotFoundError``.
    """
    path = fake_relay_path()
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    last_error = ''
    for _attempt in range(3):
        port = free_port()
        log_file = tempfile.NamedTemporaryFile(prefix='td_genset_stand_relay_', suffix='.log', delete=False)
        args = [sys.executable, '-B', os.path.abspath(__file__), '--fake-relay', path,
                '--clock-offset', repr(float(clock_offset)),
                '--', '--host', '127.0.0.1', '--port', str(port), '--token', token,
                '--snapshot-sec', str(snapshot_sec), '--time-scale', str(time_scale),
                '--relay-version', version, '--no-noise']
        if hostid:
            args += ['--hostid', hostid]
        if commands_disabled:
            args.append('--commands-disabled')
        process = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=log_file, stderr=subprocess.STDOUT,
                                   close_fds=True)
        client = SimClient('http://127.0.0.1:%d/api/v1' % port, token)
        relay = RelayProcess(process, client, port, token, log_file.name, log_file)
        for _ in range(200):
            if process.poll() is not None:
                break
            if client.has_sim():
                return relay
            time.sleep(POLL_STEP)
        last_error = relay.log_tail()
        relay.stop()
    raise StandError('Власний емулятор не запустився: %s' % last_error)


# ====================================================================== емулятор з годинником (скрипт)
class _OffsetClock:
    """Замінник модуля ``time`` для ``fake_relay``: ``time()`` + зсув; решта — справжній ``time``."""

    def __init__(self, real, offset):
        self._real = real
        self.offset = float(offset)

    def time(self):
        return self._real.time() + self.offset

    def __getattr__(self, name):
        return getattr(self._real, name)


def run_clocked_relay(argv):
    """``relay_harness.py --fake-relay <шлях> --clock-offset <с> -- <аргументи fake_relay.py>``."""
    own, relay_args = (argv[:argv.index('--')], argv[argv.index('--') + 1:]) if '--' in argv else (argv, [])
    parser = argparse.ArgumentParser(description='fake_relay.py з керованим годинником (стендові тести td_genset)')
    parser.add_argument('--fake-relay', required=True)
    parser.add_argument('--clock-offset', type=float, default=0.0)
    options = parser.parse_args(own)
    sys.dont_write_bytecode = True          # не залишати __pycache__ поруч із fake_relay.py у репозиторії
    spec = importlib.util.spec_from_file_location('td_genset_stand_fake_relay', options.fake_relay)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    clock = _OffsetClock(time, options.clock_offset)
    module.time = clock
    relay_cls = module.Relay
    original_apply, original_state = relay_cls.sim_apply, relay_cls.sim_state

    def sim_apply(self, data):
        if isinstance(data, dict) and 'clock_advance' in data:
            data = dict(data)
            try:
                step = float(data.pop('clock_advance'))
            except (TypeError, ValueError):
                raise module.ApiError(400, 'clock_advance must be a number of seconds') from None
            if step < 0:
                raise module.ApiError(400, 'clock_advance must be >= 0')
            with self.lock:
                clock.offset += step
        return original_apply(self, data)

    def sim_state(self):
        state = original_state(self)
        state['clock_offset'] = clock.offset
        return state

    relay_cls.sim_apply = sim_apply
    relay_cls.sim_state = sim_state
    return module.main(relay_args)


if __name__ == '__main__':
    sys.exit(run_clocked_relay(sys.argv[1:]))
