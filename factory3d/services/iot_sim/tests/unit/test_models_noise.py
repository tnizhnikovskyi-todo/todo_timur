import pytest

from iot_sim.core.world import World
from iot_sim.models import MODELS, load_all, model_class, register_model
from iot_sim.models.base import (
    AGGREGATE,
    SOURCE,
    Model,
    NoiseModel,
    PassiveModel,
    noise_step,
)

CODE = "equipment/COMPRESSOR/pressure_bar"


def test_noise_formula_pure():
    # SPEC R-01: v=6,5, nominal=6,81, noise=0,05, r=0,4, dt=60 -> 6,613
    assert noise_step(6.5, 6.81, 0.05, 0.4, 1.0) == pytest.approx(6.613, abs=1e-9)
    assert noise_step(6.81, 6.81, 0.0, 0.7, 2.0) == 6.81


def test_noise_formula(world):
    dev = world.devices["COMPRESSOR"]
    dev.model = NoiseModel(dev, world)
    dev.model.attach()
    sig = world.signals[CODE]
    sig.value = 6.5
    world.step(60)
    r = world.r(CODE)
    assert sig.value == pytest.approx(6.5 + 0.3 * (6.81 - 6.5) + 0.05 * r, abs=1e-9)
    assert sig.ts == world.now()


def test_noise_threshold_alarm(world):
    dev = world.devices["COMPRESSOR"]
    sig = world.signals[CODE]
    assert (sig.params["alarm"], sig.params["threshold"]) == ("below", 6.0)
    sig.value = 5.99
    world.step(1)
    assert sig.status == "alarm"
    ev = world.events.since(0, device="COMPRESSOR", kind="alarm")[0][-1]
    assert "5.99" in ev.message and "від 6" in ev.message and ev.device == "COMPRESSOR"
    sig.value = 6.8
    world.step(1)
    assert sig.status == "ok"
    back = world.events.since(0, device="COMPRESSOR", kind="info")[0][-1]
    assert back.message.endswith("повернувся в норму")
    sig.value = 6.1  # у межах 10 % до порога
    assert sig.evaluate() == "warn"
    assert dev.state == "ok"


def test_registry_of_models():
    load_all()
    load_all()
    assert model_class("nope") is PassiveModel
    assert model_class("noise") is NoiseModel and MODELS["passive"] is PassiveModel

    @register_model("unit_test_driver")
    class _M(Model):
        phase = AGGREGATE

    assert model_class("unit_test_driver") is _M and _M.driver == "unit_test_driver"
    assert Model.phase == SOURCE
    MODELS.pop("unit_test_driver")


def test_model_helpers_and_fault(world: World):
    dev = world.devices["COMPRESSOR"]
    m = dev.model
    assert m.has("pressure_bar") and not m.has("zzz")
    assert m.val("zzz", 5) == 5 and m.val("pressure_bar") == pytest.approx(6.81)
    assert m.set("pressure_bar", 6.2) and not m.set("zzz", 1)
    assert 0 <= abs(m.r("pressure_bar")) < 1
    m.fault("comm", note="x")
    assert dev.fault == "comm" and dev.state == "offline"
    world.step(1)
    assert all(s.status == "stale" for s in dev.signals.values())
    assert world.events.last("fault").payload == {"reason": "comm", "note": "x"}
    m.clear()
    world.step(1)
    assert dev.fault is None and dev.state == "ok"
    assert world.events.last("info").message == "Збій COMPRESSOR усунено"
    assert all(s.status != "stale" for s in dev.signals.values())
    m.clear()  # повторний clear без збою — без події
    m.fault("generic")
    assert dev.state == "fault"
    d = m.to_dict()
    m.clear()
    m.from_dict(d)
    assert dev.fault == "generic" and d["extra"] == {}
