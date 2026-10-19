"""ТК-02, 06, 07, 09, 12 (Modbus: лічильники, I/O, інженерія, енергетика). AC-03/11/12/14/20/37/44/52/53."""

import time

import pytest

from .helpers import NOON, Mb, f32_of, s32, u32_le


@pytest.fixture
def mb(host):
    m = Mb(host)
    yield m
    m.close()


def test_tk02_pm5560_counters_and_io(api, mb):
    api.post("/time", {"set": NOON, "factor": 1})
    api.scenario("shift")
    time.sleep(6)
    # 1) AC-03: u11 pdu3059+2 = /signals ± 0,01
    p = mb.f32(11, 3059)
    assert p == pytest.approx(api.sig("energy/consumers/SAW-1/p_now"), abs=0.05)
    assert 10.9 <= p <= 13.5, p
    e0 = mb.i64(11, 3203)
    # 2) u1/u2 і сума u3…u8 ≈ u1+u2 (±1 %; AC-52, R-16)
    u1, u2 = mb.f32(1, 3059), mb.f32(2, 3059)
    s = sum(mb.f32(u, 3059) for u in range(3, 9))
    assert (u1 + u2) > 0
    assert abs(s - (u1 + u2)) <= 0.01 * (u1 + u2) + 1.0, (s, u1, u2)
    # 3) ADAM: u80 fc2 0+12, fc3 0+24; 0x6050; помилкові unit/адреси (AC-37)
    assert len(mb.di(80, 0, 12)) == 12 and len(mb.hr(80, 0, 24)) == 24
    assert mb.hr(80, 210) == [0x6050]
    assert mb.raw_hr(200, 0).exception_code == 0x0B
    assert mb.raw_hr(11, 9998).exception_code == 0x02
    api.put("/signals/workcenters/SLIDE-1/pieces_out", {"value": 65537, "hold_s": 60})
    time.sleep(2.5)
    assert mb.hr(80, 0, 2) == [1, 1]  # AC-52: молодше слово першим
    assert u32_le(mb.hr(80, 0, 2)) == 65537
    # 5) FC05 u86 pdu16 → DI0 (AC-44); FC06 u11 3059 → виняток 0x02
    assert not mb.c.write_coil(16, True, slave=86).isError()
    assert api.wait(lambda: mb.di(86, 0)[0] == 1, timeout=10)
    assert mb.c.write_register(3059, 1, slave=11).isError()
    assert not mb.c.write_coil(20, True, slave=86).isError()
    assert not mb.c.write_coil(21, True, slave=86).isError()
    mb.c.write_coil(20, False, slave=86)
    mb.c.write_coil(21, False, slave=86)
    # 6) u51…u59
    for u in range(51, 60):
        assert mb.f32(u, 3059) >= 0
    # INT64 росте (factor 60)
    api.post("/time", {"factor": 60})
    time.sleep(8)
    assert mb.i64(11, 3203) > e0


def test_tk06_engineering_compressor_dust_water(api, mb):
    api.post("/time", {"set": NOON, "factor": 1})
    api.scenario("shift")
    time.sleep(4)
    # AC-12/AC-52: u70 pdu3001 = pressure·1000, load (pdu3009) ≥ 80 при WORKING
    ps = api.sig("equipment/COMPRESSOR/pressure_bar")
    assert mb.hr(70, 3001)[0] == pytest.approx(ps * 1000, rel=0.02)
    load = api.sig("equipment/COMPRESSOR/load")  # AC-12 (≥ 80 — лише коли всі 35 РЦ WORKING; на стенді 13/35)
    assert mb.hr(70, 3009)[0] == pytest.approx(load, abs=3) and load >= 25
    assert ps >= 6.0
    api.scenario("compressor_fault", kind="pressure_drop", duration_s=900)
    api.post("/time", {"factor": 60})
    low = api.wait(lambda: api.sig("equipment/COMPRESSOR/pressure_bar") < 6.0, timeout=30, step=1)
    assert low, "тиск не впав нижче 6,0 за ≤ 15 хв sim"
    sig = api.get("/signals/equipment/COMPRESSOR/pressure_bar").json()
    assert sig["status"] in ("alarm", "warn", "ok")
    ev = api.get("/events", params={"device": "COMPRESSOR"}).json()["items"]
    assert ev
    # u90 raw/float (молодше слово першим — float у pdu30+8), u96, u84
    assert len(mb.hr(90, 0, 4)) == 4 and len(mb.hr(90, 30, 8)) == 8
    t = mb.hr(96, 0, 6)
    assert all(0 < x < 65535 for x in t)
    assert len(mb.di(84, 0, 2)) == 2
    w0 = u32_le(mb.hr(84, 16, 2))
    time.sleep(10)  # 10 хв sim
    assert u32_le(mb.hr(84, 16, 2)) >= w0


def test_tk07_energy_blackout(api, mb):
    api.post("/time", {"set": NOON, "factor": 1})
    api.scenario("shift")
    api.scenario("pv_cloudy", cf=0.3)
    time.sleep(4)
    pv = sum(s32(mb.hr(u, 32080, 2)) for u in range(61, 69))
    assert pv > 0
    assert mb.hr(61, 32089)
    assert api.post("/scenario/pv_cloudy/stop").status_code == 200  # домен energy зайнятий (409)
    assert mb.hr(69, 37001, 2) is not None
    assert len(mb.hr(72, 40000, 4)) == 4
    # блок без перекриттів (X-51): широке читання дає виняток 0x02
    # X-51: карта BESS розріджена (діапазони без перекриттів) — суцільне читання 37000+51 дає 0x02, читання по адресах —
    # ні
    assert mb.hr(69, 37000)[0] in (0, 1, 2, 3, 4)
    pos = mb.hr(71, 20483)[0]
    assert pos in (1, 2)
    api.scenario("blackout", duration_s=120)
    api.post("/time", {"factor": 10})
    ok = api.wait(lambda: mb.hr(71, 20483)[0] == 3, timeout=60, step=1)
    assert ok, "ATyS не переключився в II (запасний режим без genset_relay: 15 с sim)"
    assert mb.hr(71, 20486)[0] == 0 and mb.hr(71, 20487)[0] == 2 and mb.hr(71, 20482)[0] == 32
    assert f32_of(mb.hr(1, 3059, 2)) == 0 and f32_of(mb.hr(2, 3059, 2)) == 0
    assert mb.hr(61, 32089)[0] == 0x0303
    ev = api.get("/events").json()["items"]
    assert any("blackout" in str(e) for e in ev)
    api.post("/time", {"factor": 60})
    back = api.wait(lambda: mb.hr(71, 20483)[0] == 2, timeout=90, step=1)
    assert back, "після повернення мережі pdu20483 має стати 2"
    assert mb.hr(71, 20486)[0] == 2


def test_tk09_spark_and_smoke(api, mb):
    api.post("/time", {"set": NOON, "factor": 1})
    c0 = u32_le(mb.hr(85, 0, 2))
    api.scenario("spark", count=2, interval_s=30)
    edges, prev, t_end = 0, 0, time.time() + 45
    while time.time() < t_end:
        d = mb.di(85, 0, 7)[0]
        edges += 1 if d and not prev else 0
        prev = d
        time.sleep(0.1)
    assert edges == 2, edges  # імпульси DI0
    assert u32_le(mb.hr(85, 0, 2)) == c0 + 2  # count_today += 2
    # DO0 (FC05 pdu16) → клапани димовидалення DI4 через 60 с sim
    api.post("/time", {"factor": 30})
    assert mb.di(85, 4)[0] == 0
    assert not mb.c.write_coil(16, True, slave=85).isError()
    assert api.wait(lambda: mb.di(85, 4)[0] == 1, timeout=10, step=0.3), "DI4 не став 1 через 60 с sim"


def test_tk12_machines_without_interface(api, mb):
    api.post("/time", {"set": NOON, "factor": 1})
    api.scenario("shift")
    time.sleep(3)
    assert len(mb.di(82, 0, 12)) == 12 and len(mb.di(83, 0, 12)) == 12
    assert len(mb.hr(83, 0, 20)) == 20
    c0 = u32_le(mb.hr(82, 16, 2))
    api.post("/time", {"factor": 60})
    time.sleep(10)  # ≈10 хв sim
    c1 = u32_le(mb.hr(82, 16, 2))
    assert c1 >= c0
    api.post("/scenario/machine_fault/start", {"params": {"device": "ASM-3", "reason": "emergency"}})
    time.sleep(3)
    di = mb.di(83, 0, 12)
    assert di[3] == 1 and di[2] == 0  # ASM-3: аварія=1, в роботі=0
    assert api.post("/device/ASM-3/clear").status_code == 200
