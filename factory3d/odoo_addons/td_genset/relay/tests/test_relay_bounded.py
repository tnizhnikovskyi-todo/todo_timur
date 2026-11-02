"""Имитатор ретранслятора не «залипает» на стенде: журналы ограничены, замки короткие, обрывы клиентов тихие.

Разбор инцидента стенда: через время порт 8087 не отвечал ~6 с, RSS 217 МБ (unit: MemoryHigh=128M), в журнале —
BrokenPipeError в RelayHandler._dispatch → end_headers. Причины и проверки:
* журналы снимков/сырых сообщений/команд/событий были списками (команды и события — без предела, снимки — до 50 000
  по ≈ 14 КБ) → deque(maxlen) и компактная запись снимка;
* O(n)-обходы журналов и сборка ответа под общим замком → обход с конца, JSON вне замка;
* поток на соединение без таймаута, listen(5), socket.getfqdn() при старте → таймаут простоя, потолок потоков
  (быстрый 503), очередь accept 128, без getfqdn;
* обрыв клиента (RST/EPIPE) печатал трассировку на каждый запрос → тихо закрываем соединение.

Без Odoo. Запуск: cd relay && python -m pytest -q tests   (или python -m unittest discover -s tests)
"""

import contextlib
import gc
import http.client
import io
import json
import os
import socket
import struct
import sys
import threading
import time
import unittest
from unittest import mock

RELAY_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RELAY_DIR)

import fake_relay  # noqa: E402
import genset_model  # noqa: E402

TOKEN = "api-token-0123456789abcdefghij"
SIM_TOKEN = "sim-token-secret-0123456789"
AUTH = {"Authorization": "Bearer " + TOKEN}
CAPS = {"KEEP_READINGS": 300, "KEEP_RAW": 200, "KEEP_COMMANDS": 50}


def make_relay(**kwargs):
    """Relay с урезанными журналами: границы достигаются за доли секунды."""
    with mock.patch.multiple(fake_relay, **CAPS), mock.patch.object(genset_model, "KEEP_EVENTS", 20):
        return fake_relay.Relay(
            TOKEN,
            [fake_relay.DEFAULT_HOSTID],
            snapshot_sec=1.0,
            noise=False,
            profile="d700",
            sim_token=SIM_TOKEN,
            **kwargs,
        )


class Served:
    """Сервер в потоке + мини-клиент."""

    def __init__(self, relay, **kwargs):
        self.relay = relay
        self.server = fake_relay.make_server(relay, "127.0.0.1", 0, quiet=True, **kwargs)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.relay.stop_event.set()
        self.server.shutdown()
        self.server.server_close()

    def conn(self, timeout=15):
        return http.client.HTTPConnection("127.0.0.1", self.port, timeout=timeout)

    def request(self, conn, method, path, body=None, headers=None):
        started = time.monotonic()
        conn.request(method, path, body=body, headers=headers or AUTH)
        resp = conn.getresponse()
        data = resp.read()
        return resp.status, data, time.monotonic() - started

    def sock(self):
        return socket.create_connection(("127.0.0.1", self.port), timeout=5)


def abort(sock):
    """Закрыть соединение с RST (не дожидаясь ответа): сервер потом пишет в мёртвый сокет."""
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
    sock.close()


class BoundedJournalsTest(unittest.TestCase):
    def test_journals_are_bounded(self):
        relay = make_relay()
        dev = next(iter(relay.devices.values()))
        relay._advance(3600)  # ≈ 3600 снимков (раз в секунду) и сырых сообщений при пределе 300 / 200
        self.assertEqual(len(relay.readings), CAPS["KEEP_READINGS"])
        self.assertEqual(len(relay.raw), CAPS["KEEP_RAW"])
        ids = [r["id"] for r in relay.readings]
        self.assertEqual(ids, sorted(ids))
        self.assertEqual(ids[-1], relay.reading_id)  # id не откатываются, хотя старые снимки вытеснены
        self.assertGreater(ids[0], 1000)

        for _ in range(200):
            relay._new_command(dev, "start", "test", "test")
        self.assertEqual(len(relay.commands), CAPS["KEEP_COMMANDS"])

        model = relay.sim_model()
        code = next(
            c for c in genset_model.FAULT_CODES if c != "start_fail" and genset_model.ALARM_DEFS[c][1] != "info"
        )
        for _ in range(100):
            model.fault(code)
            model.clear()
        self.assertEqual(len(model.events), 20)
        self.assertEqual(model.events[-1]["id"], model.event_seq)

        for _ in range(100):
            relay.sim_apply({"cloud_press": "start"})
        self.assertEqual(len(dev.cloud_seen), fake_relay.KEEP_CLOUD_SEEN)
        self.assertLessEqual(len(dev.pending_effects), fake_relay.KEEP_EFFECTS)
        self.assertEqual(len(relay.status_json()["devices"][0]["cloud_commands_seen"]), fake_relay.KEEP_CLOUD_SEEN)

    def test_pagination_and_raw_image_survive_compact_storage(self):
        relay = make_relay()
        relay._advance(600)
        first = relay.readings[10]["id"]
        _, body = relay.api("GET", "/api/v1/readings", {"since": [str(first)], "limit": ["5"], "raw": ["1"]}, None)
        self.assertEqual([r["id"] for r in body["readings"]], list(range(first + 1, first + 6)))
        self.assertEqual(body["next_since"], first + 5)
        one = body["readings"][0]
        self.assertEqual(list(one["regs"]), [str(a) for a in fake_relay.REG_ADDRS])
        self.assertEqual(list(one["coils"]), [str(a) for a in fake_relay.COIL_ADDRS])
        self.assertTrue(all(isinstance(v, int) for v in one["regs"].values()))
        self.assertTrue(set(one["coils"].values()) <= {0, 1})
        self.assertNotIn("regs", relay.api("GET", "/api/v1/latest", {}, None)[1])
        self.assertEqual(
            relay.api("GET", "/api/v1/readings", {"since": [str(relay.reading_id)]}, None)[1]["readings"], []
        )
        _, raw = relay.api("GET", "/api/v1/raw", {"since": [str(relay.raw_id - 3)]}, None)
        self.assertEqual([r["id"] for r in raw["raw"]], [relay.raw_id - 2, relay.raw_id - 1, relay.raw_id])
        cmd = relay._new_command(next(iter(relay.devices.values())), "start", None, None)
        self.assertEqual(relay.api("GET", "/api/v1/commands/%d" % cmd["id"], {}, None)[1]["id"], cmd["id"])
        with self.assertRaises(fake_relay.ApiError):
            relay.api("GET", "/api/v1/commands/%d" % (cmd["id"] + 100), {}, None)  # нет такой → 404


class ServerResilienceTest(unittest.TestCase):
    def test_server_start_does_not_resolve_hostname(self):
        with mock.patch("socket.getfqdn", side_effect=AssertionError("getfqdn при старте")):
            served = Served(make_relay())
        served.close()

    def test_many_requests_and_aborted_connections_stay_bounded(self):
        relay = make_relay()
        relay._advance(1800)  # журнал снимков уже полон (300), ответы raw=1 по 1,5 МБ
        served = Served(relay, idle_timeout=2.0)
        self.addCleanup(served.close)
        base_threads = threading.active_count()
        errors, latencies = [], []
        stderr = io.StringIO()
        gc.collect()
        blocks_before = sys.getallocatedblocks()  # журналы уже заполнены: дальше число живых объектов расти не должно

        with contextlib.redirect_stderr(stderr):
            # 1) клиенты уходят (RST), пока обработчики ждут замок: ответ пишется в закрытый сокет
            request = (
                "GET /api/v1/readings?since=0&limit=2000&raw=1 HTTP/1.1\r\nHost: x\r\nAuthorization: Bearer %s\r\n\r\n"
                % TOKEN
            ).encode()
            for _ in range(4):
                with relay.lock:
                    socks = [served.sock() for _ in range(30)]
                    for sock in socks:
                        sock.sendall(request)
                    time.sleep(0.3)  # обработчики разобрали запрос и стоят на замке
                    for sock in socks:
                        abort(sock)
                time.sleep(0.1)

            # 2) параллельная нагрузка: keep-alive клиенты + клиенты, рвущие соединение сразу после запроса
            paths = [
                ("GET", "/api/v1/status", None),
                ("GET", "/api/v1/latest?raw=1", None),
                ("GET", "/api/v1/readings?since=0&limit=2000&raw=1", None),
                ("GET", "/api/v1/readings?since=0&limit=50&raw=1", None),
                ("GET", "/api/v1/raw?since=0&limit=2000", None),
                ("GET", "/api/v1/commands?since=0", None),
                ("POST", "/api/v1/commands", json.dumps({"command": "start", "requested_by": "load"})),
                ("GET", "/api/v1/commands/1", None),
            ]

            def worker(seed):
                conn = served.conn()
                try:
                    for i in range(25):
                        method, path, body = paths[(seed + i) % len(paths)]
                        status, _, elapsed = served.request(conn, method, path, body)
                        latencies.append(elapsed)
                        if status not in (200, 201, 404, 409):
                            errors.append((path, status))
                    status, _, elapsed = served.request(
                        conn, "GET", "/sim/v1/state", headers={"Authorization": "Bearer " + SIM_TOKEN}
                    )
                    if status != 200:
                        errors.append(("/sim/v1/state", status))
                except Exception as exc:  # noqa: BLE001
                    errors.append(repr(exc))
                finally:
                    conn.close()

            def aborter():
                for _ in range(40):
                    try:
                        sock = served.sock()
                        sock.sendall(request)
                        abort(sock)
                    except OSError:
                        pass

            threads = [threading.Thread(target=worker, args=(n,)) for n in range(6)]
            threads += [threading.Thread(target=aborter) for _ in range(2)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(60)
            self.assertFalse(any(t.is_alive() for t in threads), "нагрузка не завершилась за 60 с")

            # 3) «полуоткрытые» соединения без единого байта: сервер обязан закрыть их по таймауту простоя
            idle = [served.sock() for _ in range(20)]
            for sock in idle:
                sock.settimeout(5)
                self.assertEqual(sock.recv(1), b"", "простаивающее соединение не закрыто сервером")
                sock.close()

            # 4) после всего порт отвечает быстро, потоки вернулись к исходному числу
            probe_conn = served.conn(timeout=5)
            status, _, probe = served.request(probe_conn, "GET", "/api/v1/status")
            probe_conn.close()
            deadline = time.monotonic() + 10
            while threading.active_count() > base_threads + 1 and time.monotonic() < deadline:
                time.sleep(0.1)

        self.assertEqual(errors, [])
        self.assertEqual(status, 200)
        self.assertLess(probe, 1.0)
        self.assertLess(max(latencies), 8.0)
        self.assertLessEqual(threading.active_count(), base_threads + 1, "потоки обработчиков не освободились")
        self.assertNotIn("Traceback", stderr.getvalue())
        self.assertNotIn("BrokenPipe", stderr.getvalue())
        self.assertNotIn("ConnectionReset", stderr.getvalue())
        self.assertLessEqual(len(relay.readings), CAPS["KEEP_READINGS"])
        self.assertLessEqual(len(relay.commands), CAPS["KEEP_COMMANDS"])
        gc.collect()
        growth = sys.getallocatedblocks() - blocks_before
        self.assertLess(growth, 40000, "число живых объектов выросло на %d" % growth)

    def test_connection_cap_gives_fast_503_and_recovers(self):
        served = Served(make_relay(), idle_timeout=1.0, max_connections=3)
        self.addCleanup(served.close)
        idle = [served.sock() for _ in range(3)]
        time.sleep(0.3)  # три обработчика заняли все слоты
        conn = served.conn(timeout=5)
        status, body, elapsed = served.request(conn, "GET", "/api/v1/status")
        conn.close()
        self.assertEqual(status, 503)
        self.assertIn("too many connections", body.decode())
        self.assertLess(elapsed, 1.0)
        for sock in idle:  # таймаут простоя освобождает слоты
            sock.settimeout(5)
            self.assertEqual(sock.recv(1), b"")
            sock.close()
        conn = served.conn(timeout=5)
        self.assertEqual(served.request(conn, "GET", "/api/v1/status")[0], 200)
        conn.close()


if __name__ == "__main__":
    unittest.main()
