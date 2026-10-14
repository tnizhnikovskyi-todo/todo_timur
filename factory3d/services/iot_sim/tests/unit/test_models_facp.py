"""R-25, R-09 (запиленість FA-FAC), R-26/R-27 (spark, smoke); SPEC §13.1, AC-15, AC-50, AC-56, AC-61, AC-66."""
import pytest

from iot_sim.models.facp import (
    ALARM,
    FAULT,
    QUIET,
    TEST_ALARM,
    UNRELIABLE,
    drill_view,
    lsp_id,
    zone_of_machine,
)

pytestmark = pytest.mark.unit

ZONE = "fire/groups/FA-CUT/state"


def v(world, code):
    return world.signals[code].value


def start_drill(world, zone="FA-CNC", real=False, detector=""):
    world.set_flag("fire_drill", {"zone": zone, "detector": detector, "real": real,
                                  "t0": world.now().isoformat(), "phase": "active"})


def at(world, seconds):
    """Крок sim-годинника по 1 с до ``seconds`` від старту каскаду."""
    for _ in range(int(seconds)):
        world.step(1)


def test_drill_timeline(world):
    world.advance(10)
    assert v(world, "fire/totals/system_state") == 1
    start_drill(world, "FA-CUT", detector="2.CUT.01")
    world.step(0)
    assert v(world, ZONE) == TEST_ALARM and v(world, "fire/totals/state") == TEST_ALARM  # t = 0
    assert v(world, "fire/totals/system_state") == 4 and v(world, "fire/totals/alarms") == 1
    assert v(world, "fire/totals/sounders_active") == 0
    zone = world.devices["FA-CUT"].model
    assert zone.lsp["2.CUT.01"]["present_value"] == TEST_ALARM
    at(world, 3)  # +3 с: сирени; навчання не передається на пульт
    assert v(world, "fire/totals/sounders_active") == 1 and v(world, "fire/totals/brigade") == 0
    at(world, 3)  # +6 с: стоп вентиляції (читають RV/AHU)
    assert drill_view(world)["steps"]["vent_stop"] and not drill_view(world)["steps"]["dampers"]
    assert v(world, "fire/smoke/SMOKE-VENTS/state") == 0
    at(world, 3)  # +9 с: димовидалення u85 DI4
    assert v(world, "fire/smoke/SMOKE-VENTS/state") == 1
    assert v(world, "yard/gates/GATE-W/cmd_hold") == 0
    at(world, 3)  # +12 с: u86 DO4 і DO5, двері BioStar 20480
    assert v(world, "yard/gates/GATE-W/cmd_hold") == 1 and v(world, "yard/gates/GATE-E/cmd_hold") == 1
    ctl = world.devices["ACCESS"].model.ctl
    doors = {e["door_id"] for e in ctl.events if e["code"] == 20480}
    assert doors == {1, 2, 3, 4, 5} and any(e["code"] == 26368 for e in ctl.events)
    assert world.devices["SAW-1"].model.current_state == 3  # ще працює
    at(world, 8)  # +20 с: РЦ зони -> ExternalEmergency
    assert world.devices["SAW-1"].model.flags["ExternalEmergency"]
    assert world.devices["SAW-1"].model.current_state == 4
    assert not world.devices["CNC-1"].model.flags["ExternalEmergency"]
    assert [e for e in world.events.ring if e.kind == "fire" and "Навчальна тривога" in e.message]


def test_drill_real_and_restore(world):
    world.advance(10)
    start_drill(world, "FA-CUT", real=True)
    at(world, 4)
    assert v(world, ZONE) == ALARM and v(world, "fire/totals/system_state") == 2
    assert v(world, "fire/totals/brigade") == 1  # BV:11 — реальна тривога
    at(world, 20)
    world.flags["fire_drill"]["phase"] = "restoring"  # S-07: відкат у зворотному порядку за 30 с
    world.step(0)
    view = drill_view(world)
    assert view["restoring"] and view["steps"]["alarm"] and view["steps"]["doors"]
    order = []
    for _ in range(31):
        world.step(1)
        view = drill_view(world)
        now_on = None if view is None else {k for k, on in view["steps"].items() if on}
        order.append(now_on)
    first_off = {}
    for i, on in enumerate(order):
        names = set() if on is None else on
        for k in ("machines", "doors", "dampers", "vent_stop", "sounders", "alarm"):
            if k not in names and k not in first_off:
                first_off[k] = i
    assert sorted(first_off, key=first_off.get) == ["machines", "doors", "dampers", "vent_stop",
                                                         "sounders", "alarm"]
    world.step(5)
    assert drill_view(world) is None
    assert v(world, ZONE) == QUIET and v(world, "fire/totals/system_state") == 1
    assert v(world, "fire/totals/alarms") == 0 and v(world, "yard/gates/GATE-W/cmd_hold") == 0
    assert v(world, "fire/smoke/SMOKE-VENTS/state") == 0
    assert world.devices["SAW-1"].model.current_state == 3


def test_drill_flag_removed_triggers_restore(world):
    world.advance(10)
    start_drill(world, "FA-CNC")
    at(world, 15)
    world.clear_flag("fire_drill")  # stop/cleanup сценарію
    world.step(1)
    assert drill_view(world)["restoring"]
    at(world, 31)
    assert drill_view(world) is None


def test_zone_of_machine():
    assert zone_of_machine("Z-CUT") == "FA-CUT" and zone_of_machine(None) is None
    assert zone_of_machine("FA-X") == "FA-X"


def test_contamination_reliability(world):
    zone = world.devices["FA-FAC"].model
    assert v(world, "fire/groups/FA-FAC/dust") == 82 and zone.piv("2.FAC.07") == 82
    world.advance(10)
    assert zone.lsp["2.FAC.07"]["reliability"] == 0
    world.force("fire/groups/FA-FAC/dust", 91.0, hold_s=120)  # AC-50
    world.advance(10)
    assert zone.piv("2.FAC.07") == 91 and zone.lsp["2.FAC.07"]["reliability"] == UNRELIABLE
    assert zone.lsp["2.FAC.01"]["reliability"] == 0
    msgs = [e.message for e in world.events.ring if e.kind == "alarm"]
    assert "Очистити сповіщувач 2.FAC.07 (запиленість 91 %)" in msgs
    assert any("FA-FAC dust: 91" in m and "при нормі до 90" in m for m in msgs)
    world.advance(10)  # одна подія на перевищення
    assert sum(1 for e in world.events.ring if e.message.startswith("Очистити")) == 1
    for a in zone.detectors:  # інші сповіщувачі: 5…30 %
        if a != "2.FAC.07":
            assert 5 <= zone.piv(a) <= 31


def test_dust_drift_and_maintenance(world):
    world.r = lambda code: 0.0
    zone = world.devices["FA-FAC"].model
    world.advance(600)  # rate 0,01/хв · 10 хв
    assert v(world, "fire/groups/FA-FAC/dust") == pytest.approx(82.1, abs=1e-6)
    world.force("fire/groups/FA-FAC/dust", 95.0, hold_s=0)
    world.advance(10)
    assert zone.dust_alerted
    world.maintenance_closed.add("FA-FAC")  # заявку ТО закрито -> nominal
    world.advance(10)
    assert v(world, "fire/groups/FA-FAC/dust") == pytest.approx(10.0, abs=0.01)
    assert "FA-FAC" not in world.maintenance_closed and not zone.dust_alerted
    assert zone.lsp["2.FAC.07"]["reliability"] == 0
    world.advance(300)
    zone2 = world.devices["FA-FAC"].model
    d = zone2.get_state()
    zone2.contamination["2.FAC.01"] = 99
    zone2.set_state(d)
    assert zone2.contamination["2.FAC.01"] != 99


def test_zone_fault_sensor(world):
    world.advance(10)
    world.fault("FA-CUT", "sensor")
    world.advance(10)
    assert v(world, ZONE) == FAULT == 3 and v(world, "fire/totals/state") == FAULT
    assert v(world, "fire/totals/system_state") == 3 and v(world, "fire/totals/faults") == 1
    assert [v(world, f"fire/loops/{n}/state") for n in (1, 2, 3, 4)] == [0, 0, 0, 0]  # BV шлейфу не змінюється
    zone = world.devices["FA-CUT"].model
    assert zone.lsp[zone.first_detector]["reliability"] == UNRELIABLE
    evs = [e for e in world.events.ring if e.kind == "fault" and e.payload.get("detector")]
    assert evs and evs[0].message.startswith("Несправність сповіщувача 2.CUT.01 (зона FA-CUT, шлейф 2)")
    world.clear("FA-CUT")
    world.advance(10)
    assert v(world, ZONE) == QUIET and v(world, "fire/totals/faults") == 0
    assert v(world, "fire/totals/system_state") == 1


def test_zone_fault_loop(world):
    world.advance(10)
    world.fault("FA-CUT", "loop")
    world.advance(10)
    zone = world.devices["FA-CUT"].model
    loop = zone.detector_loop()
    assert v(world, f"fire/loops/{loop}/state") == 1 and sum(v(world, f"fire/loops/{n}/state") for n in (1, 2, 3, 4)) == 1
    assert any(e.message == f"Несправність шлейфу {loop}" for e in world.events.ring)
    assert zone.lsp[zone.first_detector]["reliability"] == 0  # лінія, а не сповіщувач
    world.clear("FA-CUT")
    world.advance(10)
    assert v(world, f"fire/loops/{loop}/state") == 0


def test_alarm_overrides_fault_and_comm(world):
    world.advance(10)
    world.fault("FA-CUT", "generic")
    start_drill(world, "FA-CUT")
    world.advance(5)
    assert v(world, ZONE) == TEST_ALARM  # тривога важливіша за несправність
    world.fault("FA-CNC", "comm")
    world.advance(5)
    assert world.signals["fire/groups/FA-CNC/state"].status == "stale"


def test_object_types(world):
    facp = world.devices["FACP-1"].model
    dtypes = {s.dtype for s in world.devices["FACP-1"].signals.values()}
    assert dtypes <= {"BV", "PIV", "MSV", "enum"}  # жодного AI/AV/BI (X-37)
    kinds = {}
    for o in facp.lsp_catalog():
        kinds[o["kind"]] = kinds.get(o["kind"], 0) + 1
    assert kinds == {"detector": 222, "mcp": 36, "flame": 3, "sounder": 41}
    assert sum(1 for o in facp.lsp_catalog() if o["piv"]) == 222  # PIV — лише сповіщувачі (X-79)
    assert len(facp.zones()) == 35
    assert all(o["address"].split(".")[1] not in ("SPK", "NOZ", "SV") for o in facp.lsp_catalog())


def test_lsp_ids_fire_r23(world):
    cat = {o["address"]: o["id"] for o in world.devices["FACP-1"].model.lsp_catalog()}
    assert len(cat) == 302 and len(set(cat.values())) == 302
    expect = {"1.MCP.01": 19001, "4.MCP.09": 49009, "2.SND.13": 29113, "2.FLM.01": 29201, "2.FAC.07": 21607,
              "1.RCV-1.01": 10101, "2.CNC.05": 21405, "2.BOILER.02": 23302, "3.SOC.01": 33401,
              "3.OFFICE.08": 33508}
    for addr, i in expect.items():
        assert cat[addr] == i, addr
    assert lsp_id(2, 16, 7) == 21607
    for bad in ((0, 1, 1), (9, 1, 1), (1, 0, 1), (1, 1, 100)):
        with pytest.raises(ValueError):
            lsp_id(*bad)
    assert world.devices["FA-CNC"].model.lsz == 14 and world.devices["FA-CUT"].model.lsz == 12


# --- SPARK-1 (R-26) і SMOKE-CTRL (R-27) -------------------------------------------------------
def test_spark_pulses(world):
    world.advance(10)
    spark = world.devices["SPARK-1"].model
    c0 = v(world, "fire/spark/SPARK-1/count_today")
    world.post("spark", {"fault": False, "index": 0})
    world.step(1)
    assert v(world, "fire/spark/SPARK-1/state") == 1 and v(world, "fire/spark/SPARK-1/extinguishing") == 1
    world.step(1)
    assert v(world, "fire/spark/SPARK-1/state") == 0 and v(world, "fire/spark/SPARK-1/extinguishing") == 1  # DI1 2 с
    world.step(1)
    assert v(world, "fire/spark/SPARK-1/extinguishing") == 0
    assert v(world, "fire/spark/SPARK-1/count_today") == c0 + 1 and v(world, "fire/spark/SPARK-1/fault") == 0
    assert v(world, "fire/spark/SPARK-1/water_ok") == 1
    ev = world.events.last("fire")
    assert ev.message.startswith("Іскрогасіння: іскру виявлено на магістралі аспірації над лінією")
    assert spark.count_total == 1


def test_spark_fault_latch_and_snapshot(world):
    world.post("spark", {"fault": True})
    world.step(1)
    assert v(world, "fire/spark/SPARK-1/fault") == 1
    world.advance(605)
    assert v(world, "fire/spark/SPARK-1/fault") == 0
    spark = world.devices["SPARK-1"].model
    d = spark.get_state()
    spark.count_total = 77
    spark.set_state(d)
    assert spark.count_total == 1
    world.fault("SPARK-1", "sensor")
    world.step(1)
    assert v(world, "fire/spark/SPARK-1/fault") == 1 and v(world, "fire/spark/SPARK-1/water_ok") == 0


def test_spark_background_and_day_reset(world):
    from datetime import datetime

    world.r = lambda code: -1.0  # (r+1)/2 = 0 < 1/480 -> іскра кожну sim-хвилину, поки працюють SAW
    world.advance(130)
    assert world.devices["SPARK-1"].model.count_total >= 2
    world.clock.set(datetime(2026, 10, 12, 19, 0))  # поза зміною — тиша
    n = world.devices["SPARK-1"].model.count_total
    world.advance(300)
    assert world.devices["SPARK-1"].model.count_total == n
    world.clock.set(datetime(2026, 10, 13, 19, 0))
    world.advance(10)
    assert v(world, "fire/spark/SPARK-1/count_today") == 0


def test_smoke_commands_and_battery(world):
    sig = "fire/smoke/SMOKE-VENTS/state"
    world.advance(10)
    assert v(world, sig) == 0 and v(world, "fire/smoke/SMOKE-CTRL/battery") == 0
    world.post("smoke", {"cmd": "open"})  # DO0
    world.advance(50)
    assert v(world, sig) == 0
    world.advance(20)  # 60 с
    assert v(world, sig) == 1
    world.post("smoke", {"cmd": "close"})
    world.advance(60)
    assert v(world, sig) == 1
    world.advance(40)  # 90 с
    assert v(world, sig) == 0
    world.set_flag("blackout", {"phase": "outage"})
    world.advance(10)
    assert v(world, "fire/smoke/SMOKE-CTRL/battery") == 1 and v(world, "fire/smoke/SMOKE-CTRL/fault") == 0
    world.devices["SMOKE-CTRL"].model.battery_s = 72 * 3600 - 5
    world.advance(10)
    assert v(world, "fire/smoke/SMOKE-CTRL/fault") == 1  # через 72 год DI5
    world.flags["blackout"]["phase"] = "restoring"
    world.advance(10)
    assert v(world, "fire/smoke/SMOKE-CTRL/battery") == 0
    m = world.devices["SMOKE-CTRL"].model
    d = m.get_state()
    m.set_state(d)
    world.fault("SMOKE-CTRL", "generic")
    world.advance(10)
    assert v(world, "fire/smoke/SMOKE-CTRL/fault") == 1
