import shutil

import pytest
from iot_sim.core.registry import Registry, driver_for, parse_spec
from iot_sim.models.base import PassiveModel

MODBUS_RE = r"u\d+ fc\d+ pdu\d+(\+\d+)?"


def _row(**kw):
    base = {
        "n": "1",
        "code": "a/b/c",
        "device": "B",
        "protocol": "P-05",
        "address": "",
        "dtype": "F32",
        "unit": "кВт",
        "scale": "×1",
        "nominal": "",
        "thresholds": "—",
        "model": "noise (R-01)",
        "status": "макет",
    }
    base.update(kw)
    return base


def test_catalog_load_1215(registry):
    assert len(registry.signals) == 1215
    assert (
        len(registry.served()) == 1064
    )  # без protocol=none (X-35); 1017 + 9 регістрів SWB-CTRL (W1) + 28 вікна керування (W2) + 10 ресурсів (W3)
    assert sum(1 for s in registry.signals if not s.emulated) == 151
    # ASSUMPTION: devices.yaml W0 — 184 пристрої (повні 276 генерує tools/gen_devices.py пізніше)
    assert len(registry.devices) >= 276


def test_computed_rows(registry):
    comp = [s for s in registry.signals if s.computed]
    assert len(comp) >= 150
    assert all(not s.emulated for s in comp if s.model.startswith("обчислює"))
    assert registry.by_code["energy/consumers/SAW-1/kwh_shift"].computed


def test_owner_rows_x76(registry):
    rows = {s.n: s for s in registry.signals}
    assert rows[334].protocol == "—" and rows[1166].protocol == "—"
    assert rows[1166].device == "CUTOPT" and not rows[1166].emulated
    assert registry.devices["CUTOPT"].driver == "passive"


def test_modbus_pdu_form(registry):
    import re

    for s in registry.served():
        if "Modbus" in s.address:
            assert re.search(MODBUS_RE, s.address), s.code
            assert s.modbus is not None
    unit, fc, pdu, count = registry.by_code["energy/consumers/SAW-1/p_now"].modbus
    assert (unit, fc, pdu, count) == (11, 3, 3059, 2)


def test_devices_yaml_fallback(tmp_path, registry):
    d = tmp_path / "cat"
    d.mkdir()
    shutil.copy("catalog/signals.csv", d / "signals.csv")  # без devices.yaml
    reg = Registry.load(d)
    assert len(reg.devices) >= 184
    assert reg.devices["SAW-1"].unit_id == 11
    assert reg.devices["SAW-1"].driver == "machine"


def test_catalog_hash(tmp_path, registry):
    assert Registry.load("catalog").catalog_hash == registry.catalog_hash
    d = tmp_path / "c"
    d.mkdir()
    shutil.copy("catalog/signals.csv", d / "signals.csv")
    h1 = Registry.load(d).catalog_hash
    assert h1 != registry.catalog_hash  # без devices.yaml
    (d / "signals.csv").write_text((d / "signals.csv").read_text() + "\n")
    assert Registry.load(d).catalog_hash != h1


def test_parse_numbers():
    s = parse_spec(_row(nominal="12.18 (шум 0.08, швидк. 1.92/хв)", thresholds="< 6.0"))
    assert (s.nominal, s.noise, s.rate, s.alarm, s.threshold) == (12.18, 0.08, 1.92, "below", 6.0)
    s = parse_spec(_row(nominal="18,0", thresholds="> -60"))
    assert (s.nominal, s.alarm, s.threshold) == (18.0, "above", -60.0)
    s = parse_spec(_row(nominal="READY/WORKING", thresholds="межа 20"))
    assert s.nominal is None and s.limit == 20.0 and s.initial_value() == 0
    assert parse_spec(_row(dtype="text", nominal="x")).initial_value() == ""
    assert parse_spec(_row(protocol="—", address="Modbus u1 fc3 pdu1")).modbus is None


def test_kinds_and_rule(registry):
    assert registry.by_code["equipment/FL-2/hours"].kind == "counter"
    assert registry.by_code["workcenters/SAW-1/state"].kind == "state"
    assert registry.by_code["equipment/COMPRESSOR/pressure_bar"].kind == "gauge"
    assert registry.by_code["equipment/COMPRESSOR/pressure_bar"].rule == "noise"
    assert registry.by_code["workcenters/SAW-1/state"].group == "workcenters"


def test_driver_rules_and_unknown_is_passive(registry, world):
    assert driver_for(["something/else"]) == "passive"
    assert driver_for(["infra/pv/PV-INV-1/p_kw"]) == "pv"
    assert registry.devices["COMPRESSOR"].driver == "compressor"
    # драйвер без зареєстрованого класу -> пасивна модель, що тримає номінал
    dev = world.devices["OFFICE"]
    assert isinstance(dev.model, PassiveModel)
    assert dev.signals["p_now"].value == pytest.approx(dev.signals["p_now"].params["nominal"])


def test_relative_nominal_threshold_is_not_absolute(registry):
    """«> 0,9·номінал» без номіналу — порога немає (інакше постійна хибна тривога QF-* i_now при 100 А)."""
    s = next(x for x in registry.signals if x.code == "energy/lines/BW-1/i_now")
    assert s.threshold is None and s.alarm is None
