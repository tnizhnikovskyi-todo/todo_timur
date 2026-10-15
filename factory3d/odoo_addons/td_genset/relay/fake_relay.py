#!/usr/bin/env python3
"""Эмулятор ретранслятора SmartGen (API v1 из smartgen/relay_api.md) для разработки и тестов td_genset.

Один файл, только стандартная библиотека (Python 3.9+): http.server.ThreadingHTTPServer, json, threading.
Повторяет ответы рабочего API 1:1 (ключи, типы, *_utc, next_since, коды и тексты ошибок, Cache-Control:
no-store) и моделирует генератор (HGM6120N): режимы, пуск/останов по состояниям 5.3, сеть, автоматы
(ATS), топливо, АКБ, накопительные счётчики, снимки (first / interval / change), очередь команд.
Ретранслятор ничего не шлёт в Odoo сам — Odoo опрашивает его, как рабочий API.

Запуск:
    python3 fake_relay.py --port 8081 --token dev-token-0123456789abcdefghij --snapshot-sec 10
    python3 fake_relay.py --port 8081 --token dev-token-0123456789abcdefghij --hostid 3130373031334717003D002E
    python3 fake_relay.py --port 8081 --clock-offset -3600   # часы эмулятора на час позади реальных
    python3 fake_relay.py --selftest          # прогон сценария на свободном порту → SELF-TEST PASSED

В Odoo (dev): smartgen.relay_url = http://127.0.0.1:8081/api/v1, smartgen.relay_token = <токен>.

Примеры (API — с токеном, служебный /_sim — без токена, только с 127.0.0.1):
    T=dev-token-0123456789abcdefghij; B=http://127.0.0.1:8081/api/v1
    curl -s -H "Authorization: Bearer $T" $B/status
    curl -s -H "Authorization: Bearer $T" "$B/latest?raw=1"
    curl -s -H "Authorization: Bearer $T" "$B/readings?since=0&limit=500"
    curl -s -H "Authorization: Bearer $T" -H 'Content-Type: application/json' \\
         -d '{"command": "manual", "requested_by": "Dev (res.users 2)", "source": "odoo:button"}' $B/commands
    curl -s -H "Authorization: Bearer $T" $B/commands/1
    curl -s -H "Authorization: Bearer $T" "$B/commands?since=0"
    curl -s http://127.0.0.1:8081/_sim                                     # состояние симуляции
    curl -s -d '{"time_scale": 30}' http://127.0.0.1:8081/_sim              # ускорить физику в 30 раз
    curl -s -d '{"mains_normal": false}' http://127.0.0.1:8081/_sim         # пропала сеть (auto → пуск)
    curl -s -d '{"link": false}' http://127.0.0.1:8081/_sim                 # модуль не на связи → 409, снимков нет
    curl -s -d '{"cloud_press": "manual"}' http://127.0.0.1:8081/_sim       # нажали «Ручной» в приложении SmartGen
    curl -s -d '{"set": {"battery_v": 23.5}}' http://127.0.0.1:8081/_sim    # подменить значение
    curl -s -d '{"reset": true}' http://127.0.0.1:8081/_sim                 # всё с нуля (id тоже)
    curl -s -d '{"link": false, "advance": 600}' http://127.0.0.1:8081/_sim # «прошло 10 минут» без связи
    curl -s -d '{"fail_next": {"status": 503, "count": 2}}' http://127.0.0.1:8081/_sim  # 2 ответа как от nginx

Ключи POST /_sim (можно несколько в одном запросе; "hostid" выбирает модуль, по умолчанию первый):
    reset, restart (перезапуск ретранслятора: queued/sent → failed "relay restarted", следующий снимок "first"),
    link (bool), link_blip (с: связь пропадёт на N с), seen_ago (с: «последний раз видели» N с назад, при link off),
    commands_enabled, no_exec (done, но контроллер не выполняет), reject (bool или число команд: failed,
    "controller rejected the command"), no_reply (sent → timeout "no reply in 30 s"), format_learned,
    remote_lock, mains_normal, fuel_level (%), crank_failure (следующий пуск неудачен), time_scale, snapshot_sec,
    noise (шум напряжений), version ("1.1.1" — без 5 полей 1.1.3), cloud_press (<команда>), registers_known / coils_known,
    set ({ключ: значение}; null = «нет данных»), unset ([ключи] — снять подмену), drop ([ключи] — убрать ключ
    из values), snapshot (сделать снимок сейчас),
    advance (с: «прожить» N секунд мгновенно — шагами ≤ 1 с, для сдвигов больше ~5,5 ч крупнее (≤ 20 000 шагов):
    пакеты модуля, плановые снимки с нужными ts, смены состояний, исполнение и таймауты команд,
    seconds_since_seen; до 31 суток),
    clock_advance (с: просто перевести часы вперёд, без промежуточных шагов — как обёртка стенда
    tests/stand/relay_harness.py: следующий тик увидит скачок), clock_offset (с: задать сдвиг часов),
    fail_next ({"status": 500|502|503|504|4xx, "count": N, "error": "…"} — следующие N запросов к API, кроме
    /_sim, ещё до проверки токена получают этот код: 500 → {"error": "internal error"}, 502/503/504 — HTML-страница
    nginx, прочие — {"error": <error или "injected failure">}; null — сбросить).
Часы эмулятора = time.time() + сдвиг (--clock-offset, clock_offset, advance, clock_advance): от них все ts/*_utc,
интервал снимков, окно «online» (90 с), seconds_since_seen, uptime, таймауты команд. reset не трогает часы
(время не идёт назад), но сбрасывает fail_next. GET /_sim показывает clock_offset и fail_next.
time_scale ускоряет физику: задержки последовательностей пуска/останова, счётчики, расход топлива, а также
~1 с исполнения команды, паузу 2 с между командами и таймаут 30 с. Интервал снимков (--snapshot-sec) и окно
«online» от time_scale не зависят.
"""

import argparse
import json
import random
import socket
import sys
import threading
import time
import traceback
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

API_PREFIX = "/api/v1"
DEFAULT_HOSTID = "3130373031334717003D002E"
MAX_BODY = 64 * 1024
MAX_LIMIT = 2000
ONLINE_WINDOW_S = 90          # devices[].online: модуль что-то присылал за последние 90 с
PACKET_SEC = 5                # как часто «модуль» шлёт данные, пока на связи
QUEUE_MAX = 5                 # не больше 5 команд в ожидании на модуль
CMD_EXEC_S = 1.0              # queued→sent→done ≈ 1 с (симуляционные секунды)
CMD_PAUSE_S = 2.0             # пауза между командами одного модуля
CMD_TIMEOUT_S = 30.0          # нет ответа модуля 30 с → timeout
TANK_L = 145.0                # объём бака «Садовой», л
KEEP_READINGS = 50000         # хранить в памяти не больше (id всё равно растут)
KEEP_RAW = 5000

# ------------------------------------------------------------------ команды (7.1)
COMMAND_ADDR = {"start": 0x0000, "stop": 0x0001, "test": 0x0002, "auto": 0x0003,
                "manual": 0x0004, "gen_close_open": 0x0005, "mains_close_open": 0x0006}
ALLOWED_COMMANDS = sorted(COMMAND_ADDR)
FRAME_TO_COMMAND = {}


def crc16_modbus(data):
    """CRC-16/MODBUS (полином 0xA001, начальное значение 0xFFFF)."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


def command_frame(command, slave=0):
    """Кадр Modbus RTU 05H «записать катушку = ON» для команды, hex: auto → 00050003FF007DEB."""
    addr = COMMAND_ADDR[command]
    body = bytes([slave, 0x05, addr >> 8, addr & 0xFF, 0xFF, 0x00])
    crc = crc16_modbus(body)
    return (body + bytes([crc & 0xFF, crc >> 8])).hex().upper()


for _cmd in COMMAND_ADDR:
    FRAME_TO_COMMAND[command_frame(_cmd)] = _cmd

# ------------------------------------------------------------------ значения (5.1–5.3)
GENSET_STATUS_TEXT = {
    0: "Standby", 1: "Preheat", 2: "Fuel Output", 3: "Crank", 4: "Crank Rest", 5: "Safety Run",
    6: "Start Idle", 7: "High Speed Warming Up", 8: "Wait for Load", 9: "Normal Running",
    10: "High Speed Cooling", 11: "Stop Idle", 12: "ETS", 13: "Wait for Stop", 14: "Stop Failure",
    15: "After Stop",
}
REMOTE_START_TEXT = {0: "No Delay", 1: "Start Delay", 2: "Stop Delay"}
MAINS_STATUS_TEXT = {0: "Normal", 1: "Abnormal", 2: "No Delay"}

# Пуск: 1→3→5→6→7→8→9, останов: 10→11→12→13→15→0 (длительности — симуляционные секунды).
START_SEQ = [(1, 3), (3, 5), (5, 8), (6, 8), (7, 15), (8, 2)]
CRANK_FAIL_SEQ = [(1, 3), (3, 5), (4, 5), (3, 5), (4, 5), (3, 5)]
STOP_SEQ = [(10, 20), (11, 8), (12, 8), (13, 4), (15, 4)]
ETS_SEQ = [(12, 8), (13, 4), (15, 4)]
RUNNING_AT_SPEED = {5, 6, 7, 8, 9, 10, 11}
REMOTE_DELAY_S = 5

# Сигналы 01H: адрес → ключ (5.2). Адресов 5, 54, 55, 62, 63, 70, 71, 79 в протоколе нет.
COIL_KEYS = {
    0: "common_alarm", 1: "common_warning", 2: "common_shutdown", 3: "remote_mode", 4: "remote_lock",
    6: "mains_on_load", 7: "gen_on_load", 8: "emergency_stop", 9: "overspeed_shutdown",
    10: "underspeed_shutdown", 11: "speed_signal_loss_shutdown", 12: "overfrequency_shutdown",
    13: "underfrequency_shutdown", 14: "overvoltage_shutdown", 15: "undervoltage_shutdown",
    16: "gen_overcurrent_shutdown", 17: "crank_failure", 18: "high_temp_shutdown",
    19: "low_oil_pressure_shutdown", 20: "frequency_loss_alarm", 21: "input_shutdown",
    22: "low_fuel_shutdown", 23: "low_coolant_shutdown", 24: "high_temp_warning",
    25: "low_oil_pressure_warning", 26: "gen_overcurrent_warning", 27: "stop_failure_warning",
    28: "low_fuel_warning", 29: "charging_failure_warning", 30: "battery_undervoltage_warning",
    31: "battery_overvoltage_warning", 32: "input_warning", 33: "speed_signal_loss_warning",
    34: "low_coolant_warning", 35: "temp_sensor_open_warning", 36: "oil_pressure_sensor_open_warning",
    37: "maintenance_due_warning", 38: "charger_fail_warning", 39: "overpower_warning",
    40: "test_mode", 41: "auto_mode", 42: "manual_mode", 43: "stop_mode",
    44: "temp_sensor_open_shutdown", 45: "oil_pressure_sensor_open_shutdown",
    46: "maintenance_due_shutdown", 47: "overpower_shutdown", 48: "emergency_stop_input",
    49: "aux_input_1", 50: "aux_input_2", 51: "aux_input_3", 52: "aux_input_4", 53: "aux_input_5",
    56: "crank_relay", 57: "fuel_relay", 58: "aux_output_1", 59: "aux_output_2", 60: "aux_output_3",
    61: "aux_output_4", 64: "mains_fault", 65: "mains_normal", 66: "mains_overvoltage",
    67: "mains_undervoltage", 68: "mains_loss_phase", 69: "mains_blackout", 72: "gen_normal",
    73: "gen_overvoltage", 74: "gen_undervoltage", 75: "gen_overfrequency", 76: "gen_underfrequency",
    77: "gen_overcurrent", 78: "scheduled_not_run",
}
COIL_ADDRS = list(range(80))                               # coils_known = 80
REG_ADDRS = [a for a in range(56) if a != 45]              # registers_known = 55
SHUTDOWN_KEYS = [COIL_KEYS[a] for a in (9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 21, 22, 23, 44, 45, 46, 47)]
WARNING_KEYS = [COIL_KEYS[a] for a in range(24, 40)]
# «Залипающие» сигналы: держатся, пока их не сбросят (stop сбрасывает аварии; /_sim set — любые).
STICKY_KEYS = set(SHUTDOWN_KEYS + WARNING_KEYS) | {
    "emergency_stop", "frequency_loss_alarm", "remote_mode", "remote_lock", "emergency_stop_input",
    "aux_input_1", "aux_input_2", "aux_input_3", "aux_input_4", "aux_input_5",
    "aux_output_1", "aux_output_2", "aux_output_3", "aux_output_4", "scheduled_not_run",
    "mains_overvoltage", "mains_undervoltage", "mains_loss_phase", "gen_overvoltage", "gen_overfrequency",
    "gen_overcurrent"}
# Изменение этих сигналов (адреса 0,1,2,6,7,8,40–43,56,57,64,65,69,72) или genset_status → снимок "change".
CHANGE_KEYS = ["genset_status"] + [COIL_KEYS[a] for a in (0, 1, 2, 6, 7, 8, 40, 41, 42, 43, 56, 57, 64, 65, 69, 72)]
V113_KEYS = ("water_temp_sensor_ohm", "oil_pressure_sensor_ohm", "fuel_level_sensor_ohm",
             "controller_sw", "controller_hw")
REGISTER_VALUE_KEYS = [
    "mains_ua", "mains_ub", "mains_uc", "mains_uab", "mains_ubc", "mains_uca", "mains_freq",
    "gen_ua", "gen_ub", "gen_uc", "gen_uab", "gen_ubc", "gen_uca", "gen_freq",
    "current_a", "current_b", "current_c", "water_temp", "water_temp_sensor_ohm", "oil_pressure",
    "oil_pressure_sensor_ohm", "fuel_level", "fuel_level_sensor_ohm", "speed", "battery_v", "dplus_v",
    "active_power", "reactive_power", "apparent_power", "power_factor", "maint_h", "maint_min",
    "genset_status", "genset_status_text", "genset_status_delay", "remote_start_status",
    "remote_start_status_text", "remote_start_delay", "ats_status", "ats_status_delay", "mains_status",
    "mains_status_text", "mains_status_delay", "run_hours", "run_minutes", "start_count", "energy_kwh",
    "controller_sw", "controller_hw", "power_a", "power_b", "power_c", "load_pct", "controller_mode",
]
ALL_VALUE_KEYS = set(REGISTER_VALUE_KEYS) | set(COIL_KEYS.values())
NO_DATA_RAW = 32766           # «###» на экране контроллера → null в values
_ABSENT = object()            # маркер «ключа нет в values» (drop)


def utc(ts):
    """Секунды Unix → '2026-10-07T15:57:22Z' (или None)."""
    return None if ts is None else time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))


class ApiError(Exception):
    """Ответ с ошибкой: {"error": "..."} + дополнительные поля."""

    def __init__(self, status, error, **extra):
        super().__init__(error)
        self.status = status
        self.payload = {"error": error, **extra}


# ================================================================== модель генератора
class Genset:
    """Контроллер HGM6120N с агрегатом, сетью и ATS. Время — симуляционные секунды (dt уже × time_scale)."""

    def __init__(self, noise=True, rng=None):
        self.rng = rng or random.Random(1)
        self.noise = noise
        self.mode = "auto"
        self.status = 0
        self.seq = []                  # оставшиеся шаги последовательности [(код, длительность)]
        self.state_left = 0.0          # сколько осталось в текущем состоянии
        self.seq_kind = None           # "start" / "crank_fail" / "stop"
        self.remote = None             # отложенное автоматическое действие: ("start"|"stop", осталось с)
        self.mains_ok = True
        self.mains_closed = True       # автомат сети замкнут
        self.gen_closed = False        # автомат генератора замкнут
        self.fuel_l = 0.95 * TANK_L
        self.battery_rest = 27.8
        self.water_temp = 35.0
        self.run_s = 34 * 3600 + 51 * 60
        self.start_count = 39
        self.energy = 253.0
        self.crank_fail_next = False
        self.flags = {k: False for k in STICKY_KEYS}
        self.flags.update(aux_input_2=True, aux_output_4=True)   # у «Садовой» горят постоянно
        self.overrides = {}            # ключ → значение (None = «нет данных», _ABSENT = ключа нет)

    # ---------------------------------------------------------- состояние
    @property
    def running(self):
        return self.status not in (0, 15)

    def has_shutdown(self):
        return any(self.flags[k] for k in SHUTDOWN_KEYS) or self.flags["emergency_stop"]

    def _begin(self, kind, seq):
        self.seq_kind = kind
        self.seq = list(seq)
        self._next_state()

    def _next_state(self):
        if self.seq:
            self.status, self.state_left = self.seq.pop(0)
            if self.status == 5 and self.seq_kind == "start":
                self.start_count += 1          # двигатель «схватил»
            if self.status in (10, 12):        # снимаем нагрузку в начале останова
                self._unload_gen()
            return
        # последовательность закончилась
        kind, self.seq_kind = self.seq_kind, None
        if kind == "start":
            self.status, self.state_left = 9, 0.0
            self._close_gen()
        elif kind == "crank_fail":
            self.status, self.state_left = 0, 0.0
            self.flags["crank_failure"] = True
        else:
            self.status, self.state_left = 0, 0.0

    def _close_gen(self):
        if self.status in (8, 9):
            self.mains_closed = False          # блокировка: два автомата не замкнуты одновременно
            self.gen_closed = True
            self.status = 9

    def _unload_gen(self, transfer=True):
        if self.gen_closed:
            self.gen_closed = False
            if self.status == 9:
                self.status = 8
            if transfer and self.mains_ok:
                self.mains_closed = True       # нагрузка обратно на сеть

    def start(self):
        if self.running or self.has_shutdown():
            return False
        if self.crank_fail_next:
            self.crank_fail_next = False
            self._begin("crank_fail", CRANK_FAIL_SEQ)
        else:
            self._begin("start", START_SEQ)
        return True

    def stop(self):
        self.remote = None
        if self.status in (1, 2, 3, 4):        # ещё не завёлся — прекратить пуск
            self._begin("stop", [(15, 2)])
        elif self.status in RUNNING_AT_SPEED:
            self._begin("stop", STOP_SEQ)

    def emergency_stop(self):
        self.remote = None
        if self.status in RUNNING_AT_SPEED or self.status in (1, 2, 3, 4):
            self._unload_gen()
            self._begin("stop", ETS_SEQ)

    # ---------------------------------------------------------- команды контроллеру
    def apply_command(self, command):
        """Эффект принятой контроллером команды (кадр 05H)."""
        if command in ("auto", "manual", "test"):
            self.mode = command
            if command == "test" and not self.running:
                self.start()
        elif command == "stop":
            self.mode = "stop"
            for key in SHUTDOWN_KEYS + ["emergency_stop"]:
                self.flags[key] = False        # «Стоп» на контроллере сбрасывает аварии
            if self.running:
                self.stop()
        elif command == "start":
            if self.mode == "manual":
                self.start()
        elif command == "gen_close_open":
            if self.gen_closed:
                self._unload_gen(transfer=False)   # только разомкнуть; сеть — отдельной командой
            elif self.status in (8, 9):
                self._close_gen()
        elif command == "mains_close_open":
            if self.mains_closed:
                self.mains_closed = False
            elif self.mains_ok:
                if self.gen_closed:
                    self.gen_closed = False
                    self.status = 8 if self.status == 9 else self.status
                self.mains_closed = True

    def set_mains(self, ok):
        ok = bool(ok)
        if ok == self.mains_ok:
            return
        self.mains_ok = ok
        if not ok:
            self.mains_closed = False          # контактор сети отпадает без напряжения
            self.remote = None
        elif not self.gen_closed:
            self.mains_closed = True           # сеть вернулась — нагрузка снова на сети
            self.remote = None

    # ---------------------------------------------------------- шаг физики
    def tick(self, dt):
        # 1. отложенные автоматические действия режима auto (задержка дистанционного пуска/останова)
        if self.remote:
            kind, left = self.remote
            left -= dt
            if left > 0:
                self.remote = (kind, left)
            else:
                self.remote = None
                if kind == "start":
                    self.start()
                elif kind == "stop" and self.running:
                    self.stop()
        # 2. логика режима
        if self.remote and self.mode != "auto":
            self.remote = None
        if self.mode != "manual" and self.mains_ok and not self.gen_closed and not self.mains_closed:
            self.mains_closed = True            # ATS: вне ручного режима нагрузка возвращается на сеть
        if self.mode == "auto" and not self.remote and not self.seq:
            if not self.mains_ok and self.status == 0 and not self.has_shutdown():
                self.remote = ("start", REMOTE_DELAY_S)
            elif self.mains_ok and self.status in (8, 9):
                self.remote = ("stop", REMOTE_DELAY_S)
        elif self.mode == "test" and self.status == 0 and not self.seq and not self.has_shutdown():
            self.start()
        elif self.mode == "stop" and self.status in RUNNING_AT_SPEED and self.seq_kind != "stop":
            self.stop()
        # аварийные остановы и пустой бак
        if self.fuel_l <= 0.05 * TANK_L:
            self.flags["low_fuel_shutdown"] = True
        if self.has_shutdown() and self.seq_kind not in ("stop",) and (
                self.status in RUNNING_AT_SPEED or self.status in (1, 2, 3, 4)):
            self.emergency_stop()
        # 3. смена состояния: не больше одной за тик, чтобы каждое состояние попало в снимок
        if self.seq_kind:
            self.state_left -= dt
            if self.state_left <= 0:
                self._next_state()
        # 4. накопительные величины
        if self.status in RUNNING_AT_SPEED or self.status in (3, 12, 13):
            self.run_s += dt
        if self.status in RUNNING_AT_SPEED:
            self.fuel_l = max(0.0, self.fuel_l - (3.5 if self.gen_closed else 1.2) * dt / 3600)
            target_t, tau = 82.0, 300.0
        else:
            target_t, tau = 35.0, 1200.0
        self.water_temp += (target_t - self.water_temp) * min(1.0, dt / tau)
        if self.gen_closed:
            self.energy += self._load_kw() * dt / 3600

    def _load_kw(self):
        return 12.0

    def _n(self, amplitude):
        return self.rng.uniform(-amplitude, amplitude) if self.noise else 0.0

    # ---------------------------------------------------------- образ контроллера
    def values(self):
        """Расшифрованные значения (5.1, 5.2) с учётом подмен /_sim."""
        at_speed = self.status in RUNNING_AT_SPEED
        v = {}
        if self.mains_ok:
            v.update(mains_ua=round(239 + self._n(1)), mains_ub=round(234 + self._n(1)),
                     mains_uc=round(240 + self._n(1)), mains_uab=409, mains_ubc=410, mains_uca=418,
                     mains_freq=50.0)
        else:
            v.update(mains_ua=0, mains_ub=0, mains_uc=0, mains_uab=0, mains_ubc=0, mains_uca=0, mains_freq=0.0)
        if at_speed:
            v.update(gen_ua=round(230 + self._n(1)), gen_ub=round(231 + self._n(1)), gen_uc=round(229 + self._n(1)),
                     gen_uab=398, gen_ubc=400, gen_uca=399, gen_freq=round(50.0 + self._n(0.1), 1),
                     speed=round(1500 + self._n(5)), oil_pressure=round(350 + self._n(5)))
        else:
            v.update(gen_ua=0, gen_ub=0, gen_uc=0, gen_uab=0, gen_ubc=0, gen_uca=0, gen_freq=0.0,
                     speed=250 if self.status == 3 else (300 if self.status in (12, 13) else 0),
                     oil_pressure=0)
        load = self._load_kw() if self.gen_closed else 0.0
        if load:
            cur = round(load * 1000 / (3 * 230 * 0.92), 1)
            v.update(current_a=cur, current_b=round(cur + 0.4, 1), current_c=round(cur - 0.3, 1),
                     active_power=round(load), reactive_power=5, apparent_power=13, power_factor=0.92,
                     power_a=4, power_b=4, power_c=4, load_pct=30)
        else:
            v.update(current_a=0.0, current_b=0.0, current_c=0.0, active_power=0, reactive_power=0,
                     apparent_power=0, power_factor=1.0, power_a=0, power_b=0, power_c=0, load_pct=0)
        if self.status == 3:
            battery, dplus = self.battery_rest - 3.8, 0.0
        elif at_speed:
            battery, dplus = max(self.battery_rest, 28.4), 28.0
        else:
            battery, dplus = self.battery_rest, 0.0
        fuel_pct = round(self.fuel_l / TANK_L * 100)
        if self.seq_kind:
            delay = max(0, int(self.state_left + 0.999))
        else:
            delay = 0
        if self.remote:
            rs_status, rs_delay = (1 if self.remote[0] == "start" else 2), max(0, int(self.remote[1] + 0.999))
        else:
            rs_status, rs_delay = (0 if self.running else 2), 0
        v.update(water_temp=round(self.water_temp), water_temp_sensor_ohm=515.4, oil_pressure_sensor_ohm=9.5,
                 fuel_level=fuel_pct, fuel_level_sensor_ohm=round(10 + fuel_pct * 1.89, 1),
                 battery_v=round(battery, 1), dplus_v=dplus, maint_h=0, maint_min=0,
                 genset_status=self.status, genset_status_text=GENSET_STATUS_TEXT[self.status],
                 genset_status_delay=delay, remote_start_status=rs_status,
                 remote_start_status_text=REMOTE_START_TEXT[rs_status], remote_start_delay=rs_delay,
                 ats_status=2 if self.mains_closed else 5, ats_status_delay=0,
                 mains_status=2 if self.mains_ok else 1,
                 mains_status_text=MAINS_STATUS_TEXT[2 if self.mains_ok else 1], mains_status_delay=0,
                 run_hours=int(self.run_s // 3600), run_minutes=int(self.run_s % 3600 // 60),
                 start_count=self.start_count, energy_kwh=int(self.energy), controller_sw=4.3, controller_hw=3.4)
        # сигналы
        s = dict(self.flags)
        s["low_fuel_warning"] = s["low_fuel_warning"] or fuel_pct < 20
        s["battery_undervoltage_warning"] = s["battery_undervoltage_warning"] or (
            self.status != 3 and battery < 24.0)
        s["battery_overvoltage_warning"] = s["battery_overvoltage_warning"] or battery > 30.5
        s["high_temp_warning"] = s["high_temp_warning"] or self.water_temp > 95
        s.update(test_mode=self.mode == "test", auto_mode=self.mode == "auto",
                 manual_mode=self.mode == "manual", stop_mode=self.mode == "stop",
                 mains_on_load=self.mains_closed and self.mains_ok, gen_on_load=self.gen_closed,
                 crank_relay=self.status == 3, fuel_relay=self.status in (2, 3, 5, 6, 7, 8, 9, 10, 11),
                 mains_normal=self.mains_ok, mains_blackout=not self.mains_ok, mains_fault=not self.mains_ok,
                 gen_normal=at_speed, gen_undervoltage=not at_speed, gen_underfrequency=not at_speed)
        s["common_shutdown"] = any(s[k] for k in SHUTDOWN_KEYS) or s["emergency_stop"]
        s["common_warning"] = any(s[k] for k in WARNING_KEYS)
        s["common_alarm"] = s["common_shutdown"] or s["common_warning"]
        for addr in sorted(COIL_KEYS):
            v[COIL_KEYS[addr]] = bool(s[COIL_KEYS[addr]])
        # подмены из /_sim
        for key, val in self.overrides.items():
            if val is _ABSENT:
                v.pop(key, None)
            else:
                v[key] = val
        modes = [m for m in ("test", "auto", "manual", "stop") if v.get(m + "_mode")]
        v["controller_mode"] = modes[0] if len(modes) == 1 else None
        if "controller_mode" in self.overrides and self.overrides["controller_mode"] is not _ABSENT:
            v["controller_mode"] = self.overrides["controller_mode"]
        return v

    def set_value(self, key, val):
        """/_sim set: модельные величины меняют состояние, остальные ключи — жёсткая подмена."""
        if key not in ALL_VALUE_KEYS:
            raise ApiError(400, "unknown value key: %s" % key)
        if val is not None:
            if key == "fuel_level":
                self.fuel_l = max(0.0, min(100.0, float(val))) * TANK_L / 100
                if float(val) > 5:
                    self.flags["low_fuel_shutdown"] = False
                self.overrides.pop(key, None)
                return
            if key == "battery_v":
                self.battery_rest = float(val)
                self.overrides.pop(key, None)
                return
            if key == "water_temp":
                self.water_temp = float(val)
                self.overrides.pop(key, None)
                return
            if key in ("run_hours", "run_minutes"):
                hours = int(val) if key == "run_hours" else int(self.run_s // 3600)
                minutes = int(val) if key == "run_minutes" else int(self.run_s % 3600 // 60)
                self.run_s = hours * 3600 + minutes * 60
                return
            if key == "start_count":
                self.start_count = int(val)
                return
            if key == "energy_kwh":
                self.energy = float(val)
                return
            if key == "mains_normal":
                self.set_mains(bool(val))
                return
            if key in STICKY_KEYS:
                self.flags[key] = bool(val)
                self.overrides.pop(key, None)
                return
        self.overrides[key] = val


def raw_image(values):
    """Сырой образ: регистры 0–44, 46–55 и катушки 0–79 (как `regs`/`coils` при raw=1)."""
    def num(key, scale=1, signed=False):
        val = values.get(key)
        if val is None:
            return NO_DATA_RAW
        raw = int(round(float(val) * scale))
        return raw & 0xFFFF if signed else max(0, min(raw, 0xFFFF))

    def u32(key):
        val = values.get(key)
        val = 0 if val is None else int(val)
        return (val >> 16) & 0xFFFF, val & 0xFFFF

    regs = {}
    simple = {0: "mains_ua", 1: "mains_ub", 2: "mains_uc", 3: "mains_uab", 4: "mains_ubc", 5: "mains_uca",
              7: "gen_ua", 8: "gen_ub", 9: "gen_uc", 10: "gen_uab", 11: "gen_ubc", 12: "gen_uca",
              17: "water_temp", 19: "oil_pressure", 21: "fuel_level", 23: "speed", 30: "maint_h",
              31: "maint_min", 34: "genset_status", 35: "genset_status_delay", 36: "remote_start_status",
              37: "remote_start_delay", 38: "ats_status", 39: "ats_status_delay", 40: "mains_status",
              41: "mains_status_delay", 44: "run_minutes", 55: "load_pct"}
    for addr, key in simple.items():
        regs[addr] = num(key)
    for addr, key, scale in ((6, "mains_freq", 100), (13, "gen_freq", 100), (14, "current_a", 10),
                             (15, "current_b", 10), (16, "current_c", 10), (18, "water_temp_sensor_ohm", 10),
                             (20, "oil_pressure_sensor_ohm", 10), (22, "fuel_level_sensor_ohm", 10),
                             (24, "battery_v", 10), (25, "dplus_v", 10), (50, "controller_sw", 10),
                             (51, "controller_hw", 10)):
        regs[addr] = num(key, scale)
    for addr, key, scale in ((26, "active_power", 1), (27, "reactive_power", 1), (28, "apparent_power", 1),
                             (29, "power_factor", 100), (52, "power_a", 1), (53, "power_b", 1), (54, "power_c", 1)):
        regs[addr] = num(key, scale, signed=True)
    regs[32] = regs[33] = 0
    regs[42], regs[43] = u32("run_hours")
    regs[46], regs[47] = u32("start_count")
    regs[48], regs[49] = u32("energy_kwh")
    coils = {addr: int(bool(values.get(COIL_KEYS[addr]))) if addr in COIL_KEYS else 0 for addr in COIL_ADDRS}
    return ({str(a): regs[a] for a in REG_ADDRS}, {str(a): coils[a] for a in COIL_ADDRS})


# ================================================================== модуль связи + очередь команд
class Device:
    """Один модуль CMM366B-4G (hostid) с контроллером, связью и очередью команд API."""

    def __init__(self, hostid, noise, seed):
        self.hostid = hostid
        self.genset = Genset(noise=noise, rng=random.Random(seed))
        self.link = True
        self.link_until = None            # link_blip: когда связь вернётся
        self.last_seen = None
        self.next_packet = 0.0
        self.packetnum = 0
        self.no_exec = False
        self.reject = False               # True или число команд, которые нужно отклонить
        self.no_reply = False
        self.format_learned = True
        self.registers_known = len(REG_ADDRS)
        self.coils_known = len(COIL_ADDRS)
        self.cloud_seen = []
        self.active = None                # команда в статусе sent
        self.active_left = 0.0
        self.pause_left = 0.0
        self.pending_effects = []         # [(осталось сим. с, команда)] — режим меняется чуть позже done
        self.last_values = None
        self.last_signature = None
        self.need_first = True
        self.next_interval = None
        self.last_reading = None


class Relay:
    """Состояние ретранслятора: модули, снимки, сырые сообщения, журнал команд. Всё — под self.lock."""

    def __init__(self, token, hostids, snapshot_sec=60.0, time_scale=1.0, commands_enabled=True,
                 version="1.1.3", noise=True, seed=1, clock_offset=0.0):
        self.lock = threading.RLock()
        self.token = token
        self.hostids = list(hostids)
        self.defaults = dict(snapshot_sec=float(snapshot_sec), time_scale=float(time_scale),
                             commands_enabled=bool(commands_enabled), version=version, noise=noise, seed=seed)
        self.stop_event = threading.Event()
        self.clock_offset = float(clock_offset)   # сдвиг часов эмулятора, с; reset его не трогает
        self._reset(full=True)

    def now(self):
        """Часы эмулятора: реальное время + сдвиг (--clock-offset, /_sim advance / clock_advance / clock_offset)."""
        return time.time() + self.clock_offset

    # ---------------------------------------------------------- сброс / перезапуск
    def _reset(self, full):
        d = self.defaults
        self.snapshot_sec = d["snapshot_sec"]
        self.time_scale = d["time_scale"]
        self.commands_enabled = d["commands_enabled"]
        self.version = d["version"]
        self.started = self.now()
        self.last_tick = self.started
        self.fail_next = None                     # инъекция ошибок API (/_sim fail_next)
        self.devices = {h: Device(h, d["noise"], d["seed"] + i) for i, h in enumerate(self.hostids)}
        self.readings, self.raw, self.commands = [], [], []
        self.reading_id = self.raw_id = self.command_id = 0
        self.conn_id = 7

    def _restart(self):
        """Перезапуск ретранслятора: данные и id сохраняются, незавершённые команды → failed."""
        now = self.now()
        for cmd in self.commands:
            if cmd["status"] in ("queued", "sent"):
                self._finish(cmd, "failed", now, error="relay restarted")
        for dev in self.devices.values():
            dev.active, dev.pending_effects, dev.pause_left = None, [], 0.0
            dev.need_first, dev.next_interval = True, None
        self.started = now
        self.conn_id += 1

    # ---------------------------------------------------------- фон
    def run_ticker(self, period=0.1):
        while not self.stop_event.wait(period):
            try:
                self.tick()
            except Exception:                       # pragma: no cover — не роняем фон
                traceback.print_exc()

    def tick(self):
        """Шаг симуляции по часам эмулятора: связь, пакеты модуля, физика, команды, снимки."""
        with self.lock:
            now = self.now()
            dt_real = max(0.0, now - self.last_tick)
            self.last_tick = now
            dt = dt_real * self.time_scale
            for dev in self.devices.values():
                if dev.link_until is not None and now >= dev.link_until:
                    dev.link, dev.link_until = True, None
                if dev.link and now >= dev.next_packet:
                    dev.last_seen = now
                    dev.next_packet = now + min(PACKET_SEC, self.snapshot_sec)
                    self._modem_packet(dev, now)
                dev.genset.tick(dt)
                self._process_commands(dev, now, dt)
                self._maybe_snapshot(dev, now)

    def _modem_packet(self, dev, now):
        dev.packetnum += 1
        values = dev.genset.values()
        regs, _ = raw_image(values)
        changed = [{"%04X" % int(a): "%04X" % v} for a, v in regs.items()][:12]
        self._add_raw(dev, now, "modem->cloud", {"method": "reqdatachange", "hostid": dev.hostid,
                                                "params": {"packetnum": dev.packetnum, "03": changed}})

    def _add_raw(self, dev, now, direction, msg):
        self.raw_id += 1
        self.raw.append({"id": self.raw_id, "ts": now, "time_utc": utc(now), "conn": self.conn_id,
                         "dir": direction, "hostid": dev.hostid, "msg": msg})
        del self.raw[:-KEEP_RAW]

    # ---------------------------------------------------------- снимки
    def _maybe_snapshot(self, dev, now, force=False):
        if not dev.link:
            return None                                     # модуль не на связи → снимков нет
        full = dev.genset.values()
        signature = tuple(full.get(k, "-") for k in CHANGE_KEYS)
        reason = None
        if dev.need_first:
            reason = "first"
        elif signature != dev.last_signature:
            reason = "change"
        elif force or (dev.next_interval is not None and now >= dev.next_interval):
            reason = "interval"
        if reason is None:
            return None
        if reason == "first" or dev.next_interval is None or now >= dev.next_interval or force:
            dev.next_interval = now + self.snapshot_sec
        dev.need_first = False
        dev.last_signature = signature
        values = dict(full)
        if self.version == "1.1.1":                         # в 1.1.1 этих 5 полей в values нет
            for key in V113_KEYS:
                values.pop(key, None)
        regs, coils = raw_image(full)
        self.reading_id += 1
        rd = {"id": self.reading_id, "ts": now, "time_utc": utc(now), "hostid": dev.hostid,
              "reason": reason, "values": values, "regs": regs, "coils": coils}
        self.readings.append(rd)
        del self.readings[:-KEEP_READINGS]
        dev.last_reading = rd
        return rd

    @staticmethod
    def reading_json(rd, raw):
        out = {k: rd[k] for k in ("id", "ts", "time_utc", "hostid", "reason", "values")}
        if raw:
            out["regs"], out["coils"] = rd["regs"], rd["coils"]
        return out

    # ---------------------------------------------------------- команды
    def _new_command(self, dev, command, requested_by, source):
        now = self.now()
        self.command_id += 1
        cmd = {"id": self.command_id, "created": now, "created_utc": utc(now), "hostid": dev.hostid,
               "command": command, "requested_by": requested_by, "source": source, "status": "queued",
               "frame": None, "uid": None, "sent": None, "sent_utc": None, "done": None, "done_utc": None,
               "response": None, "error": None}
        self.commands.append(cmd)
        return cmd

    @staticmethod
    def _finish(cmd, status, now, error=None, response=None):
        cmd["status"] = status
        cmd["done"], cmd["done_utc"] = now, utc(now)
        cmd["error"] = error
        if response is not None:
            cmd["response"] = response

    def _process_commands(self, dev, now, dt):
        # эффекты принятых команд: режим меняется в образе контроллера чуть позже done
        if dev.pending_effects:
            keep = []
            for left, command in dev.pending_effects:
                left -= dt
                if left <= 0:
                    dev.genset.apply_command(command)
                else:
                    keep.append((left, command))
            dev.pending_effects = keep
        if dev.active is not None:
            cmd = dev.active
            dev.active_left -= dt
            if not dev.link:
                self._finish(cmd, "failed", now, error="modem disconnected")
            elif dev.no_reply:
                if now - cmd["sent"] >= CMD_TIMEOUT_S / self.time_scale:
                    self._finish(cmd, "timeout", now, error="no reply in 30 s")
            elif dev.active_left <= 0:
                rejected = bool(dev.reject)
                if isinstance(dev.reject, int) and not isinstance(dev.reject, bool) and dev.reject > 0:
                    dev.reject -= 1
                response = {"method": "writeConfig", "hostid": dev.hostid, "uid": "action",
                            "params": "%s,%d" % (cmd["frame"], 0 if rejected else 1)}
                if rejected:
                    self._finish(cmd, "failed", now, error="controller rejected the command", response=response)
                else:
                    self._finish(cmd, "done", now, response=response)
                    locked = dev.genset.flags["remote_lock"]
                    if not dev.no_exec and not locked:
                        dev.pending_effects.append((0.5, cmd["command"]))
            if cmd["status"] not in ("queued", "sent"):
                dev.active = None
                dev.pause_left = CMD_PAUSE_S
            return
        if dev.pause_left > 0:
            dev.pause_left -= dt
            return
        if not dev.link:
            for cmd in self.commands:
                if cmd["hostid"] == dev.hostid and cmd["status"] == "queued":
                    self._finish(cmd, "failed", now, error="modem disconnected")
            return
        queued = [c for c in self.commands if c["hostid"] == dev.hostid and c["status"] == "queued"]
        if queued:
            cmd = queued[0]
            cmd["status"] = "sent"
            cmd["frame"] = command_frame(cmd["command"])
            cmd["uid"] = "action"
            cmd["sent"], cmd["sent_utc"] = now, utc(now)
            dev.active, dev.active_left = cmd, CMD_EXEC_S
            self._add_raw(dev, now, "relay->modem", {"method": "writeConfig", "hostid": dev.hostid,
                                                     "uid": "action", "params": cmd["frame"]})

    @staticmethod
    def command_json(cmd, order="get"):
        keys_post = ["id", "created", "created_utc", "hostid", "command", "requested_by", "source", "status",
                     "frame", "uid", "sent", "sent_utc", "done", "done_utc", "response", "error"]
        keys_get = ["id", "created", "hostid", "command", "requested_by", "source", "status", "frame", "uid",
                    "sent", "done", "response", "error", "created_utc", "sent_utc", "done_utc"]
        return {k: cmd[k] for k in (keys_post if order == "post" else keys_get)}

    # ---------------------------------------------------------- часы и инъекция ошибок
    def _advance(self, seconds):
        """«Прожить» seconds секунд часов эмулятора сразу, шагами ≤ 1 с (не больше 20 000 шагов)."""
        if not 0 <= seconds <= 31 * 86400:
            raise ApiError(400, "advance must be between 0 and 2678400 seconds")
        step = max(min(1.0, self.snapshot_sec / 2.0), seconds / 20000.0)
        self.tick()                               # сначала догнать реальное время
        left = seconds
        while left > 1e-9:
            delta = min(step, left)
            self.clock_offset += delta
            left -= delta
            self.tick()

    def take_failure(self):
        """Очередная инъекция ошибки (/_sim fail_next) для запроса к API или None."""
        with self.lock:
            fail = self.fail_next
            if not fail:
                return None
            fail["count"] -= 1
            if fail["count"] <= 0:
                self.fail_next = None
            return {"status": fail["status"], "error": fail.get("error")}

    # ---------------------------------------------------------- /status
    def _device(self, hostid, required=False):
        if hostid is None:
            if required and len(self.devices) > 1:
                raise ApiError(400, "hostid is required", known=self.hostids)
            return None
        if hostid not in self.devices:
            raise ApiError(404, "unknown hostid", known=self.hostids)
        return self.devices[hostid]

    def status_json(self):
        now = self.now()
        devices = []
        for dev in self.devices.values():
            seen_ago = None if dev.last_seen is None else int(now - dev.last_seen)
            long_conn = dev.link
            values = dev.genset.values()
            devices.append({
                "hostid": dev.hostid,
                "online": seen_ago is not None and seen_ago <= ONLINE_WINDOW_S,
                "last_seen_utc": utc(dev.last_seen), "seconds_since_seen": seen_ago,
                "last_data_utc": utc(dev.last_seen), "long_connection": long_conn, "modem_ip": "127.0.0.1",
                "controller_mode": values.get("controller_mode"),
                "command_slave": 0, "command_format": "rtu" if dev.format_learned else None,
                "commands_ready": self.commands_enabled and long_conn and dev.format_learned,
                "cloud_commands_seen": list(dev.cloud_seen[-10:]),
                "cloud_routes": {"livedata": "8.136.108.133:21318", "historic": "8.136.108.133:21318"},
                "last_reading": None if dev.last_reading is None else {
                    "id": dev.last_reading["id"], "time_utc": dev.last_reading["time_utc"]},
                "registers_known": dev.registers_known, "coils_known": dev.coils_known,
            })
        return {
            "relay": {"version": self.version, "uptime_s": int(now - self.started), "time_utc": utc(now),
                      "public": "127.0.0.1:21318", "upstream": "www.smartgencloudplus.com:21318",
                      "commands_enabled": self.commands_enabled,
                      "snapshot_sec": int(self.snapshot_sec) if float(self.snapshot_sec).is_integer()
                      else self.snapshot_sec},
            "config": {"allowed_hostids": list(self.hostids), "hist_port": 21318, "cmd_format_setting": "auto",
                       "wire_log": True, "wire_log_until_utc": utc(self.started + 7 * 86400),
                       "raw_days": 14.0, "readings_days": 180.0},
            "devices": devices,
            "counts": {"raw": len(self.raw), "readings": len(self.readings), "commands": len(self.commands)},
        }

    # ---------------------------------------------------------- API
    def api(self, method, path, query, body):
        """Маршрутизация /api/v1/*: (код, тело). Токен уже проверен."""
        sub = path[len(API_PREFIX):]
        routes = {"/status": ("GET",), "/latest": ("GET",), "/readings": ("GET",), "/raw": ("GET",),
                  "/commands": ("GET", "POST")}
        if sub.startswith("/commands/") and sub.count("/") == 2 and sub != "/commands/":
            allowed = ("GET",)
        elif sub in routes:
            allowed = routes[sub]
        else:
            raise ApiError(404, "not found")
        if method not in allowed:
            raise ApiError(405, "method not allowed")
        if body is not None and len(body) > MAX_BODY:
            raise ApiError(413, "body too large")
        with self.lock:
            if sub == "/status":
                return 200, self.status_json()
            if sub == "/latest":
                dev = self._device(qstr(query, "hostid"))
                pool = [r for r in self.readings if dev is None or r["hostid"] == dev.hostid]
                if not pool:
                    raise ApiError(404, "no readings yet")
                return 200, self.reading_json(pool[-1], qflag(query, "raw"))
            if sub == "/readings":
                since, limit = qint(query, "since", 0), min(qint(query, "limit", 500), MAX_LIMIT)
                dev = self._device(qstr(query, "hostid"))
                raw = qflag(query, "raw")
                page = [r for r in self.readings if r["id"] > since and (dev is None or r["hostid"] == dev.hostid)]
                page = page[:limit]
                return 200, {"readings": [self.reading_json(r, raw) for r in page],
                             "next_since": page[-1]["id"] if page else since}
            if sub == "/raw":
                since, limit = qint(query, "since", 0), min(qint(query, "limit", 200), MAX_LIMIT)
                page = [r for r in self.raw if r["id"] > since][:limit]
                return 200, {"raw": page, "next_since": page[-1]["id"] if page else since}
            if sub == "/commands" and method == "GET":
                since, limit = qint(query, "since", 0), min(qint(query, "limit", 200), MAX_LIMIT)
                page = [c for c in self.commands if c["id"] > since][:limit]
                return 200, {"commands": [self.command_json(c) for c in page]}
            if sub.startswith("/commands/"):
                try:
                    cid = int(sub.rsplit("/", 1)[1])
                except ValueError:
                    raise ApiError(404, "no such command") from None
                for cmd in self.commands:
                    if cmd["id"] == cid:
                        return 200, self.command_json(cmd)
                raise ApiError(404, "no such command")
            return self._post_command(body)

    def _post_command(self, body):
        try:
            data = json.loads((body or b"").decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            raise ApiError(400, "body must be JSON") from None
        if not isinstance(data, dict):
            raise ApiError(400, "body must be JSON")
        command = data.get("command")
        if command not in COMMAND_ADDR:
            raise ApiError(400, "unknown command, allowed: %r" % (ALLOWED_COMMANDS,))
        hostid = data.get("hostid")
        dev = self._device(hostid if hostid not in ("", None) else None, required=True) \
            or next(iter(self.devices.values()))
        if not self.commands_enabled:
            raise ApiError(403, "commands are disabled on the relay (RELAY_COMMANDS_ENABLED=0)")
        if not dev.link:
            raise ApiError(409, "modem is not connected right now")
        if not dev.format_learned:
            raise ApiError(409, "command format not learned yet: waiting for a command from the SmartGen cloud "
                                "(or set RELAY_CMD_FORMAT)")
        waiting = [c for c in self.commands if c["hostid"] == dev.hostid and c["status"] in ("queued", "sent")]
        if len(waiting) >= QUEUE_MAX:
            raise ApiError(409, "%d commands already waiting for this modem" % len(waiting))

        def text(key, size):
            val = data.get(key)
            return None if val is None else str(val)[:size]

        cmd = self._new_command(dev, command, text("requested_by", 120), text("source", 60))
        return 201, self.command_json(cmd, order="post")

    # ---------------------------------------------------------- /_sim
    def sim_state(self):
        with self.lock:
            devs = []
            for dev in self.devices.values():
                g = dev.genset
                devs.append({
                    "hostid": dev.hostid, "link": dev.link, "link_until_utc": utc(dev.link_until),
                    "last_seen_utc": utc(dev.last_seen), "no_exec": dev.no_exec, "reject": dev.reject,
                    "no_reply": dev.no_reply, "format_learned": dev.format_learned,
                    "remote_lock": g.flags["remote_lock"], "mode": g.mode, "genset_status": g.status,
                    "genset_status_text": GENSET_STATUS_TEXT[g.status], "sequence": g.seq_kind,
                    "remote_delay": None if g.remote is None else {"action": g.remote[0], "left_s": round(g.remote[1], 1)},
                    "mains_normal": g.mains_ok, "mains_breaker_closed": g.mains_closed,
                    "gen_breaker_closed": g.gen_closed, "fuel_l": round(g.fuel_l, 2),
                    "crank_failure_next": g.crank_fail_next, "noise": g.noise,
                    "overrides": {k: ("<absent>" if v is _ABSENT else v) for k, v in g.overrides.items()},
                    "active_command": None if dev.active is None else dev.active["id"],
                    "queued_commands": [c["id"] for c in self.commands
                                        if c["hostid"] == dev.hostid and c["status"] == "queued"],
                    "values": g.values(),
                })
            return {"time_utc": utc(self.now()), "clock_offset": round(self.clock_offset, 3),
                    "fail_next": dict(self.fail_next) if self.fail_next else None,
                    "version": self.version, "time_scale": self.time_scale,
                    "snapshot_sec": self.snapshot_sec, "commands_enabled": self.commands_enabled,
                    "counts": {"raw": len(self.raw), "readings": len(self.readings), "commands": len(self.commands)},
                    "last_ids": {"reading": self.reading_id, "raw": self.raw_id, "command": self.command_id},
                    "devices": devs}

    def sim_apply(self, data):
        """POST /_sim: применить ключи в фиксированном порядке и вернуть состояние."""
        if not isinstance(data, dict):
            raise ApiError(400, "body must be a JSON object")
        known = {"hostid", "reset", "restart", "link", "link_blip", "seen_ago", "commands_enabled", "no_exec",
                 "reject", "no_reply", "format_learned", "remote_lock", "mains_normal", "fuel_level",
                 "crank_failure", "time_scale", "snapshot_sec", "noise", "cloud_press", "registers_known",
                 "coils_known", "set", "unset", "drop", "snapshot", "version", "advance", "clock_advance",
                 "clock_offset", "fail_next"}
        unknown = sorted(set(data) - known)
        if unknown:
            raise ApiError(400, "unknown _sim keys: %s" % ", ".join(unknown), known=sorted(known))
        with self.lock:
            if data.get("reset"):
                self._reset(full=True)
            if data.get("restart"):
                self._restart()
            if "fail_next" in data:
                self.fail_next = parse_fail_next(data["fail_next"])
            dev = self._device(data.get("hostid")) or next(iter(self.devices.values()))
            g = dev.genset
            now = self.now()
            if "time_scale" in data:
                scale = float(data["time_scale"])
                if not 0 < scale <= 10000:
                    raise ApiError(400, "time_scale must be in (0, 10000]")
                self.time_scale = scale
            if "snapshot_sec" in data:
                sec = float(data["snapshot_sec"])
                if sec <= 0:
                    raise ApiError(400, "snapshot_sec must be > 0")
                self.snapshot_sec = sec
                for d in self.devices.values():
                    d.next_interval = None if d.need_first else min(d.next_interval or now + sec, now + sec)
            if "version" in data:
                if data["version"] not in ("1.1.1", "1.1.3"):
                    raise ApiError(400, "version must be 1.1.1 or 1.1.3")
                self.version = data["version"]
            if "commands_enabled" in data:
                self.commands_enabled = bool(data["commands_enabled"])
            if "link" in data:
                dev.link = bool(data["link"])
                dev.link_until = None
                if dev.link:
                    dev.next_packet = 0.0
            if "link_blip" in data:
                dev.link, dev.link_until = False, now + float(data["link_blip"])
            if "seen_ago" in data:
                if dev.link:
                    raise ApiError(409, "seen_ago works only with link off")
                dev.last_seen = now - float(data["seen_ago"])
            for key in ("no_exec", "no_reply", "format_learned"):
                if key in data:
                    setattr(dev, key, bool(data[key]))
            if "reject" in data:
                rej = data["reject"]
                dev.reject = rej if isinstance(rej, int) and not isinstance(rej, bool) else bool(rej)
            if "remote_lock" in data:
                g.flags["remote_lock"] = bool(data["remote_lock"])
            if "mains_normal" in data:
                g.set_mains(data["mains_normal"])
            if "fuel_level" in data:
                g.set_value("fuel_level", data["fuel_level"])
            if "crank_failure" in data:
                g.crank_fail_next = bool(data["crank_failure"])
            if "noise" in data:
                for d in self.devices.values():
                    d.genset.noise = bool(data["noise"])
            for key in ("registers_known", "coils_known"):
                if key in data:
                    setattr(dev, key, int(data[key]))
            if "set" in data:
                if not isinstance(data["set"], dict):
                    raise ApiError(400, "set must be an object")
                for key, val in data["set"].items():
                    g.set_value(key, val)
            for key in data.get("unset") or []:
                g.overrides.pop(key, None)
            for key in data.get("drop") or []:
                if key not in ALL_VALUE_KEYS:
                    raise ApiError(400, "unknown value key: %s" % key)
                g.overrides[key] = _ABSENT
            if "cloud_press" in data:
                command = data["cloud_press"]
                if command not in COMMAND_ADDR:
                    raise ApiError(400, "unknown command, allowed: %r" % (ALLOWED_COMMANDS,))
                if not dev.link:
                    raise ApiError(409, "modem is not connected right now")
                frame = command_frame(command)
                dev.cloud_seen.append({"time_utc": utc(now), "frame": frame, "format": "rtu", "slave": 0,
                                       "command": command})
                dev.cloud_seen = dev.cloud_seen[-10:]
                dev.format_learned = True              # ретранслятор учится формату по командам хмары
                self._add_raw(dev, now, "cloud->modem", {"method": "writeConfig", "hostid": dev.hostid,
                                                         "uid": "action", "params": frame})
                if not g.flags["remote_lock"]:
                    dev.pending_effects.append((0.5, command))
            if "clock_offset" in data:
                self.clock_offset = number(data, "clock_offset")
            if "clock_advance" in data:
                jump = number(data, "clock_advance")
                if jump < 0:
                    raise ApiError(400, "clock_advance must be >= 0")
                self.clock_offset += jump                 # без шагов: следующий тик увидит скачок
            if "advance" in data:
                self._advance(number(data, "advance"))
                now = self.now()
            if data.get("snapshot"):
                if not dev.link:
                    raise ApiError(409, "modem is not connected right now: no snapshots without link")
                self._maybe_snapshot(dev, now, force=True)
        return self.sim_state()


# ------------------------------------------------------------------ разбор параметров запроса
def qstr(query, name):
    vals = query.get(name)
    return vals[-1] if vals else None


def qint(query, name, default):
    """since/limit: целое ≥ 0, иначе 400 {"error": "bad request: ValueError"}."""
    val = qstr(query, name)
    if val is None or val == "":
        return default
    try:
        num = int(val)
        if num < 0:
            raise ValueError(val)
    except ValueError:
        raise ApiError(400, "bad request: ValueError") from None
    return num


def qflag(query, name):
    return (qstr(query, name) or "").lower() in ("1", "true", "yes", "on")


def number(data, key):
    """Число из тела /_sim (секунды) или 400."""
    val = data.get(key)
    if isinstance(val, bool) or not isinstance(val, (int, float)):
        raise ApiError(400, "%s must be a number of seconds" % key)
    return float(val)


def parse_fail_next(spec):
    """/_sim fail_next: {"status": 400..599, "count": N ≥ 1 (1), "error": текст} или null."""
    if spec is None:
        return None
    if not isinstance(spec, dict):
        raise ApiError(400, "fail_next must be an object or null")
    status, count, error = spec.get("status"), spec.get("count", 1), spec.get("error")
    if isinstance(status, bool) or not isinstance(status, int) or not 400 <= status <= 599:
        raise ApiError(400, "fail_next.status must be an HTTP code 400..599")
    if isinstance(count, bool) or not isinstance(count, int) or count < 1:
        raise ApiError(400, "fail_next.count must be an integer >= 1")
    if error is not None and not isinstance(error, str):
        raise ApiError(400, "fail_next.error must be a string")
    return {"status": status, "count": count, "error": error}


NGINX_REASON = {502: "Bad Gateway", 503: "Service Temporarily Unavailable", 504: "Gateway Time-out"}


def nginx_page(status):
    """Страница ошибки nginx по умолчанию (так отвечает прокси, когда ретранслятор недоступен)."""
    title = "%d %s" % (status, NGINX_REASON[status])
    return ("<html>\r\n<head><title>%s</title></head>\r\n<body>\r\n<center><h1>%s</h1></center>\r\n"
            "<hr><center>nginx</center>\r\n</body>\r\n</html>\r\n" % (title, title)).encode("ascii")


# ================================================================== HTTP
class RelayHandler(BaseHTTPRequestHandler):
    """HTTP-обработчик: Bearer-токен первым, затем маршрут, метод, размер тела, JSON."""

    protocol_version = "HTTP/1.1"
    server_version = "fake-smartgen-relay/1.0"
    relay = None          # подставляется в make_server
    quiet = False

    def do_GET(self):
        self._dispatch("GET")

    def do_POST(self):
        self._dispatch("POST")

    def do_PUT(self):
        self._dispatch("PUT")

    def do_DELETE(self):
        self._dispatch("DELETE")

    def do_PATCH(self):
        self._dispatch("PATCH")

    def do_HEAD(self):
        self._dispatch("HEAD")

    def _read_body(self):
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if length > MAX_BODY:
            if length <= 1024 * 1024:          # дочитать, чтобы клиент успел получить 413
                self.rfile.read(length)
            self.close_connection = True
            return b"x" * (MAX_BODY + 1)
        return self.rfile.read(length) if length > 0 else b""

    def _is_loopback(self):
        return self.client_address[0] in ("127.0.0.1", "::1", "::ffff:127.0.0.1")

    def _token_ok(self):
        header = self.headers.get("Authorization") or ""
        return header.startswith("Bearer ") and header[7:].strip() == self.relay.token

    def _dispatch(self, method):
        try:
            body = self._read_body()
            url = urlsplit(self.path)
            path = url.path
            query = parse_qs(url.query, keep_blank_values=True)
            is_sim = path in ("/_sim", API_PREFIX + "/_sim")
            injected = None if is_sim else self.relay.take_failure()
            if injected:                          # /_sim fail_next: ответ до проверки токена и маршрута
                status = injected["status"]
                if status in NGINX_REASON:
                    self._send(status, None, method, html=nginx_page(status))
                    return
                raise ApiError(status, injected["error"] or ("internal error" if status == 500
                                                             else "injected failure"))
            if not self._token_ok() and not (is_sim and self._is_loopback()):
                raise ApiError(401, "missing or wrong token")
            if is_sim:
                status, payload = self._sim(method, body)
            elif path == API_PREFIX or path.startswith(API_PREFIX + "/"):
                status, payload = self.relay.api(method, path, query, body)
            else:
                raise ApiError(404, "not found")
        except ApiError as exc:
            status, payload = exc.status, exc.payload
        except Exception:
            traceback.print_exc()
            status, payload = 500, {"error": "internal error"}
        self._send(status, payload, method)

    def _sim(self, method, body):
        if method == "GET":
            return 200, self.relay.sim_state()
        if method != "POST":
            raise ApiError(405, "method not allowed")
        if len(body) > MAX_BODY:
            raise ApiError(413, "body too large")
        try:
            data = json.loads(body.decode("utf-8") or "{}")
        except (ValueError, UnicodeDecodeError):
            raise ApiError(400, "body must be JSON") from None
        return 200, self.relay.sim_apply(data)

    def _send(self, status, payload, method, html=None):
        if html is not None:
            data, ctype = html, "text/html"
        else:
            data, ctype = json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8"
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        if status == 405:
            self.send_header("Allow", "GET, POST")
        if self.close_connection:
            self.send_header("Connection", "close")
        self.end_headers()
        if method != "HEAD":
            self.wfile.write(data)

    def log_message(self, fmt, *args):
        if not self.quiet:
            sys.stderr.write("%s %s\n" % (time.strftime("%H:%M:%S"), fmt % args))


def make_server(relay, host, port, quiet=False):
    """Создать ThreadingHTTPServer и запустить фоновый тикер ретранслятора."""
    handler = type("BoundRelayHandler", (RelayHandler,), {"relay": relay, "quiet": quiet})
    server = ThreadingHTTPServer((host, port), handler)
    server.daemon_threads = True
    threading.Thread(target=relay.run_ticker, name="relay-ticker", daemon=True).start()
    return server


# ================================================================== самопроверка
def selftest():
    """Поднять сервер на свободном порту и прогнать сценарий через urllib. Код выхода 0 — всё прошло."""
    token = "selftest-token-0123456789abcdef"
    relay = Relay(token, [DEFAULT_HOSTID], snapshot_sec=1, time_scale=1.0, noise=False)
    server = make_server(relay, "127.0.0.1", 0, quiet=True)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base, root = "http://127.0.0.1:%d/api/v1" % port, "http://127.0.0.1:%d" % port
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))   # мимо HTTPS_PROXY

    def call(method, url, body=None, tok=token, raw_body=None):
        data = raw_body if raw_body is not None else (None if body is None else json.dumps(body).encode())
        req = urllib.request.Request(url, data=data, method=method)
        if tok:
            req.add_header("Authorization", "Bearer " + tok)
        if data is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with opener.open(req, timeout=10) as resp:
                return resp.status, json.loads(resp.read().decode()), resp.headers
        except urllib.error.HTTPError as err:
            raw = err.read().decode()
            try:
                payload = json.loads(raw or "null")
            except ValueError:
                payload = raw                       # не JSON (страница nginx)
            return err.code, payload, err.headers

    def check(cond, what):
        if not cond:
            raise AssertionError(what)
        print("  ok  " + what)

    def sim(**kw):
        st, js, _ = call("POST", root + "/_sim", kw, tok=None)
        check(st == 200, "_sim %s → 200" % json.dumps(kw, ensure_ascii=False))
        return js

    def wait(pred, what, timeout=15.0):
        t_end = time.time() + timeout
        while time.time() < t_end:
            res = pred()
            if res:
                return res
            time.sleep(0.05)
        raise AssertionError("timeout: " + what)

    def latest():
        return call("GET", base + "/latest")[1]

    def cmd_final(cid):
        return wait(lambda: (lambda c: c if c["status"] not in ("queued", "sent") else None)(
            call("GET", base + "/commands/%d" % cid)[1]), "command %d final" % cid)

    try:
        print("fake_relay self-test on port %d" % port)
        st, js, _ = call("GET", base + "/status", tok=None)
        check(st == 401 and js == {"error": "missing or wrong token"}, "401 без токена")
        check(call("GET", base + "/status", tok="wrong")[0] == 401, "401 с чужим токеном")
        check(call("GET", base + "/no/such/path", tok=None)[0] == 401, "401 раньше 404 на неизвестном пути")
        check(call("GET", root + "/_sim", tok=None)[0] == 200, "/_sim без токена с 127.0.0.1")
        st, js, hdr = call("GET", base + "/status")
        check(st == 200 and hdr.get("Cache-Control") == "no-store", "status 200 + Cache-Control: no-store")
        dev = js["devices"][0]
        check(set(js) == {"relay", "config", "devices", "counts"} and dev["hostid"] == DEFAULT_HOSTID
              and dev["registers_known"] == 55 and dev["coils_known"] == 80, "структура /status")
        first = wait(lambda: call("GET", base + "/latest")[0] == 200 and latest(), "первый снимок")
        check(first["reason"] == "first" and first["values"]["genset_status_text"] == "Standby"
              and first["values"]["controller_mode"] == "auto" and first["values"]["mains_on_load"] is True
              and first["values"]["gen_on_load"] is False, "первый снимок: Standby, auto, сеть на нагрузке")
        check(first["time_utc"].endswith("Z") and isinstance(first["ts"], float), "ts/time_utc")
        st, js, _ = call("GET", base + "/latest?raw=1")
        check(len(js["regs"]) == 55 and len(js["coils"]) == 80 and js["regs"]["24"] == 278, "latest?raw=1")
        check(call("GET", base + "/status")[1]["devices"][0]["online"], "devices[0].online")
        wait(lambda: len(call("GET", base + "/readings?since=0")[1]["readings"]) >= 2, "interval-снимок", 5)
        st, js, _ = call("GET", base + "/readings?since=0&limit=1")
        check(len(js["readings"]) == 1 and js["next_since"] == js["readings"][0]["id"], "readings limit/next_since")
        cursor = js["next_since"]
        js = call("GET", base + "/readings?since=%d" % cursor)[1]
        check(all(r["id"] > cursor for r in js["readings"]) and "interval" in {r["reason"] for r in js["readings"]},
              "readings с курсора, reason interval")
        big = 10 ** 9
        check(call("GET", base + "/readings?since=%d" % big)[1] == {"readings": [], "next_since": big},
              "пустая страница: next_since = since")
        check(call("GET", base + "/readings?since=abc")[1] == {"error": "bad request: ValueError"},
              "400 bad request: ValueError")
        check(call("GET", base + "/readings?hostid=XYZ")[0] == 404, "404 unknown hostid")
        check(call("PUT", base + "/status")[1] == {"error": "method not allowed"}, "405")
        check(call("GET", base + "/nope")[1] == {"error": "not found"}, "404 not found")
        check(call("GET", base + "/commands/999")[1] == {"error": "no such command"}, "404 no such command")
        check(call("POST", base + "/commands", raw_body=b"{oops")[1] == {"error": "body must be JSON"}, "400 не JSON")
        check(call("POST", base + "/commands", {"command": "fly"})[1]["error"].startswith(
            "unknown command, allowed: ['auto', 'gen_close_open'"), "400 unknown command")
        check(call("POST", base + "/commands", raw_body=b"x" * (MAX_BODY + 10))[0] == 413, "413 body too large")

        sim(time_scale=20)
        st, c1, _ = call("POST", base + "/commands", {"command": "manual", "requested_by": "Тест (res.users 2)",
                                                      "source": "odoo:button"})
        check(st == 201 and c1["status"] == "queued" and c1["frame"] is None, "POST manual → 201 queued")
        c1 = cmd_final(c1["id"])
        check(c1["status"] == "done" and c1["frame"] == "00050004FF00" + c1["frame"][-4:]
              and c1["response"]["params"] == c1["frame"] + ",1" and c1["done_utc"], "manual → done")
        wait(lambda: latest()["values"]["controller_mode"] == "manual", "режим manual в снимке")
        c2 = cmd_final(call("POST", base + "/commands", {"command": "auto"})[1]["id"])
        check(c2["frame"] == "00050003FF007DEB", "кадр auto = 00050003FF007DEB")
        lt = wait(lambda: (lambda x: x if x["values"]["controller_mode"] == "auto" else None)(latest()), "auto")
        check(lt["reason"] == "change" and lt["time_utc"] >= c2["done_utc"], "смена режима → снимок change")

        sim(link=False)
        st, js, _ = call("POST", base + "/commands", {"command": "manual"})
        check(st == 409 and js == {"error": "modem is not connected right now"}, "409 modem is not connected")
        check(not call("GET", base + "/status")[1]["devices"][0]["commands_ready"], "commands_ready false")
        n_before = len(call("GET", base + "/readings?since=0&limit=2000")[1]["readings"])
        time.sleep(1.5)
        check(len(call("GET", base + "/readings?since=0&limit=2000")[1]["readings"]) == n_before, "без связи снимков нет")
        sim(seen_ago=600)
        dev = call("GET", base + "/status")[1]["devices"][0]
        check(dev["online"] is False and dev["seconds_since_seen"] >= 600, "online false после seen_ago")
        sim(link=True)

        sim(commands_enabled=False)
        st, js, _ = call("POST", base + "/commands", {"command": "auto"})
        check(st == 403 and "RELAY_COMMANDS_ENABLED=0" in js["error"], "403 commands disabled")
        sim(commands_enabled=True)

        ids = [call("POST", base + "/commands", {"command": "auto"})[1]["id"] for _ in range(5)]
        st, js, _ = call("POST", base + "/commands", {"command": "auto"})
        check(st == 409 and js == {"error": "5 commands already waiting for this modem"}, "6-я команда → 409")
        lst = call("GET", base + "/commands?since=%d" % (ids[0] - 1))[1]["commands"]
        check([c["id"] for c in lst][:5] == ids and "next_since" not in lst, "GET /commands?since")
        for cid in ids:
            cmd_final(cid)
        done = [call("GET", base + "/commands/%d" % cid)[1] for cid in ids]
        check(all(b["sent"] - a["done"] >= 2.0 / 20 * 0.9 for a, b in zip(done, done[1:])), "пауза между командами")

        sim(no_exec=True)
        c = cmd_final(call("POST", base + "/commands", {"command": "manual"})[1]["id"])
        time.sleep(0.3)
        check(c["status"] == "done" and latest()["values"]["controller_mode"] == "auto", "no_exec: done, режим тот же")
        sim(no_exec=False, reject=True)
        c = cmd_final(call("POST", base + "/commands", {"command": "manual"})[1]["id"])
        check(c["status"] == "failed" and c["error"] == "controller rejected the command"
              and c["response"]["params"].endswith(",0"), "reject → failed")
        sim(reject=False)

        sim(time_scale=200)
        cmd_final(call("POST", base + "/commands", {"command": "manual"})[1]["id"])
        wait(lambda: latest()["values"]["controller_mode"] == "manual", "manual")
        start_id = latest()["id"]
        cmd_final(call("POST", base + "/commands", {"command": "start"})[1]["id"])
        lt = wait(lambda: (lambda x: x if x["values"]["genset_status"] == 9 else None)(latest()), "Normal Running")
        check(lt["values"]["gen_on_load"] and not lt["values"]["mains_on_load"] and lt["values"]["speed"] > 0,
              "start → 9, gen_on_load, speed > 0")
        seq = [r["values"]["genset_status"] for r in call("GET", base + "/readings?since=%d" % start_id)[1]["readings"]]
        check([s for i, s in enumerate(seq) if i == 0 or s != seq[i - 1]] == [0, 1, 3, 5, 6, 7, 8, 9]
              or [s for i, s in enumerate(seq) if i == 0 or s != seq[i - 1]][-7:] == [1, 3, 5, 6, 7, 8, 9],
              "последовательность пуска 1→3→5→6→7→8→9 в снимках")
        stop_id = latest()["id"]
        cmd_final(call("POST", base + "/commands", {"command": "stop"})[1]["id"])
        lt = wait(lambda: (lambda x: x if x["values"]["genset_status"] == 0 else None)(latest()), "Standby")
        seq = [r["values"]["genset_status"] for r in call("GET", base + "/readings?since=%d" % stop_id)[1]["readings"]]
        dedup = [s for i, s in enumerate(seq) if i == 0 or s != seq[i - 1]]
        check(dedup[-6:] == [10, 11, 12, 13, 15, 0] and lt["values"]["mains_on_load"]
              and not lt["values"]["gen_on_load"] and lt["values"]["controller_mode"] == "stop",
              "stop → 10→11→12→13→15→0, нагрузка на сети")
        check(lt["values"]["start_count"] == 40, "start_count вырос")

        cmd_final(call("POST", base + "/commands", {"command": "auto"})[1]["id"])
        wait(lambda: latest()["values"]["controller_mode"] == "auto", "auto")
        sim(mains_normal=False)
        lt = wait(lambda: (lambda x: x if x["values"]["genset_status"] == 9 else None)(latest()), "автопуск")
        check(lt["values"]["gen_on_load"] and lt["values"]["mains_blackout"] and not lt["values"]["mains_normal"],
              "auto + нет сети → автопуск на нагрузку")
        sim(mains_normal=True)
        lt = wait(lambda: (lambda x: x if x["values"]["genset_status"] == 0 else None)(latest()), "возврат")
        check(lt["values"]["mains_on_load"] and not lt["values"]["gen_on_load"], "сеть вернулась → останов")

        n_cmds = len(call("GET", base + "/commands?since=0&limit=2000")[1]["commands"])
        sim(cloud_press="manual")
        wait(lambda: latest()["values"]["controller_mode"] == "manual", "cloud manual")
        dev = call("GET", base + "/status")[1]["devices"][0]
        check(dev["cloud_commands_seen"][-1]["command"] == "manual"
              and dev["cloud_commands_seen"][-1]["frame"] == command_frame("manual"), "cloud_commands_seen")
        check(len(call("GET", base + "/commands?since=0&limit=2000")[1]["commands"]) == n_cmds,
              "команда из приложения не попала в /commands")
        sim(mains_normal=False)
        time.sleep(0.5)
        check(latest()["values"]["genset_status"] == 0 and not latest()["values"]["mains_on_load"],
              "manual + нет сети → не запускается, нагрузка обесточена")
        sim(mains_normal=True, crank_failure=True)
        cmd_final(call("POST", base + "/commands", {"command": "start"})[1]["id"])
        lt = wait(lambda: (lambda x: x if x["values"]["crank_failure"] else None)(latest()), "crank failure")
        check(lt["values"]["common_shutdown"] and lt["values"]["genset_status"] == 0, "неудачный пуск → авария")
        sim(set={"battery_v": 23.5, "oil_pressure": None}, fuel_level=40)
        v = latest()["values"] if sim(snapshot=True) else None
        check(v["battery_v"] == 23.5 and v["battery_undervoltage_warning"] and v["oil_pressure"] is None
              and v["fuel_level"] == 40, "_sim set / fuel_level / snapshot")

        # часы эмулятора: advance «проживает» время шагами, clock_advance — просто скачок
        st0 = call("GET", root + "/_sim", tok=None)[1]
        off0, rid0, ts0 = st0["clock_offset"], st0["last_ids"]["reading"], latest()["ts"]
        sim(advance=60)
        st1 = call("GET", root + "/_sim", tok=None)[1]
        check(abs(st1["clock_offset"] - off0 - 60) < 1e-6, "advance 60 → clock_offset +60 в GET /_sim")
        new = call("GET", base + "/readings?since=%d&limit=2000" % rid0)[1]["readings"]
        check(len(new) >= 50 and new[-1]["ts"] - ts0 >= 59 and all(b["ts"] >= a["ts"] for a, b in zip(new, new[1:]))
              and "interval" in {r["reason"] for r in new}, "advance: плановые снимки за прожитую минуту, ts по часам")
        check(call("GET", base + "/status")[1]["relay"]["time_utc"] >= utc(time.time() + off0 + 59),
              "relay.time_utc по часам эмулятора")
        sim(link=False)
        rid1 = call("GET", root + "/_sim", tok=None)[1]["last_ids"]["reading"]
        sim(advance=600)
        dev = call("GET", base + "/status")[1]["devices"][0]
        check(dev["online"] is False and dev["seconds_since_seen"] >= 600, "link off + advance 600 → online false")
        check(call("GET", root + "/_sim", tok=None)[1]["last_ids"]["reading"] == rid1, "без связи снимков нет и при advance")
        sim(link=True)
        off2 = call("GET", root + "/_sim", tok=None)[1]["clock_offset"]
        sim(clock_advance=5)
        check(abs(call("GET", root + "/_sim", tok=None)[1]["clock_offset"] - off2 - 5) < 1e-6, "clock_advance 5")
        check(abs(Relay("t", [DEFAULT_HOSTID], clock_offset=-3600).now() - (time.time() - 3600)) < 1,
              "--clock-offset: начальный сдвиг часов")
        sim(time_scale=1, no_reply=True)
        c = call("POST", base + "/commands", {"command": "auto"})[1]
        wait(lambda: call("GET", base + "/commands/%d" % c["id"])[1]["status"] == "sent", "sent")
        sim(advance=31)
        c = call("GET", base + "/commands/%d" % c["id"])[1]
        check(c["status"] == "timeout" and c["error"] == "no reply in 30 s" and c["done"] - c["sent"] >= 30,
              "no_reply + advance 31 → timeout")

        # инъекция ошибок API
        sim(fail_next={"status": 500, "count": 2})
        check(call("GET", base + "/status")[:2] == (500, {"error": "internal error"}), "fail_next 500 (1/2)")
        check(call("GET", root + "/_sim", tok=None)[0] == 200, "/_sim инъекцией не затронут")
        check(call("GET", base + "/latest", tok=None)[0] == 500, "fail_next 500 (2/2) — раньше проверки токена")
        check(call("GET", base + "/status")[0] == 200, "после count запросов — снова 200")
        sim(fail_next={"status": 503})
        st, body, hdr = call("GET", base + "/readings")
        check(st == 503 and "<center>nginx</center>" in body and hdr.get("Content-Type") == "text/html",
              "fail_next 503 → HTML-страница nginx")
        sim(fail_next={"status": 409, "count": 1, "error": "modem is not connected right now"})
        check(call("POST", base + "/commands", {"command": "auto"})[:2]
              == (409, {"error": "modem is not connected right now"}), "fail_next 409 со своим текстом")
        sim(fail_next={"status": 502, "count": 5})
        check(call("GET", root + "/_sim", tok=None)[1]["fail_next"] == {"status": 502, "count": 5, "error": None},
              "GET /_sim показывает fail_next")
        sim(fail_next=None)
        check(call("GET", base + "/status")[0] == 200, "fail_next null сбрасывает")
        check(call("POST", root + "/_sim", {"fail_next": {"status": 200}}, tok=None)[0] == 400, "fail_next: 400 на код вне 4xx/5xx")

        c = call("POST", base + "/commands", {"command": "auto"})[1]
        wait(lambda: call("GET", base + "/commands/%d" % c["id"])[1]["status"] == "sent", "sent")
        sim(restart=True, no_reply=False)
        c = call("GET", base + "/commands/%d" % c["id"])[1]
        check(c["status"] == "failed" and c["error"] == "relay restarted", "relay restarted")
        lt = wait(lambda: (lambda x: x if x["reason"] == "first" and x["id"] > lt["id"] else None)(latest()), "first")
        check(call("GET", base + "/status")[1]["relay"]["uptime_s"] <= 2, "uptime после перезапуска")

        off3 = call("GET", root + "/_sim", tok=None)[1]["clock_offset"]
        sim(fail_next={"status": 500, "count": 3})
        st = sim(reset=True, link=False)
        check(st["fail_next"] is None and st["clock_offset"] == off3, "reset: fail_next сброшен, часы не тронуты")
        check(call("GET", base + "/latest")[1] == {"error": "no readings yet"}, "404 no readings yet после reset")
        sim(link=True)
        lt = wait(lambda: call("GET", base + "/latest")[0] == 200 and latest(), "снимок после reset")
        check(lt["id"] == 1 and lt["reason"] == "first", "reset: id с 1")
    except AssertionError as exc:
        print("SELF-TEST FAILED: %s" % exc)
        return 1
    finally:
        relay.stop_event.set()
        server.shutdown()
    print("SELF-TEST PASSED")
    return 0


# ================================================================== main
def main(argv=None):
    ap = argparse.ArgumentParser(description="Эмулятор API ретранслятора SmartGen для разработки td_genset.")
    ap.add_argument("--host", default="127.0.0.1", help="адрес (по умолчанию 127.0.0.1)")
    ap.add_argument("--port", type=int, default=8081)
    ap.add_argument("--token", default="dev-token-0123456789abcdefghij", help="Bearer-токен API")
    ap.add_argument("--snapshot-sec", type=float, default=60.0, help="интервал плановых снимков, с (реальные)")
    ap.add_argument("--hostid", action="append", help="hostid модуля (можно несколько раз)")
    ap.add_argument("--time-scale", type=float, default=1.0, help="ускорение физики генератора")
    ap.add_argument("--clock-offset", type=float, default=0.0,
                    help="начальный сдвиг часов эмулятора относительно реального времени, с (может быть < 0)")
    ap.add_argument("--relay-version", default="1.1.3", choices=["1.1.1", "1.1.3"],
                    help="1.1.1 — без 5 полей из 5.1 (как сейчас на сервере), 1.1.3 — с ними")
    ap.add_argument("--commands-disabled", action="store_true", help="как RELAY_COMMANDS_ENABLED=0 → 403")
    ap.add_argument("--no-noise", action="store_true", help="без случайного шума напряжений")
    ap.add_argument("--quiet", action="store_true", help="не печатать журнал запросов")
    ap.add_argument("--selftest", action="store_true", help="самопроверка на свободном порту")
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    relay = Relay(args.token, args.hostid or [DEFAULT_HOSTID], snapshot_sec=args.snapshot_sec,
                  time_scale=args.time_scale, commands_enabled=not args.commands_disabled,
                  version=args.relay_version, noise=not args.no_noise, clock_offset=args.clock_offset)
    try:
        server = make_server(relay, args.host, args.port, quiet=args.quiet)
    except OSError as exc:
        print("не удалось открыть %s:%d: %s" % (args.host, args.port, exc), file=sys.stderr)
        return 1
    print("fake SmartGen relay: http://%s:%d%s (hostid %s, snapshot %ss, time_scale %s, clock_offset %ss); "
          "/_sim — служебный" % (args.host, server.server_address[1], API_PREFIX, ", ".join(relay.hostids),
                                 args.snapshot_sec, args.time_scale, args.clock_offset), file=sys.stderr, flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        relay.stop_event.set()
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
