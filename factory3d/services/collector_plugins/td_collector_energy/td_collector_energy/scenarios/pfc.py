"""Сценарій «Компенсація реактивної потужності (PFC)» (R-47, CT-06): рушій лише задає режим і ціль контролера."""

from __future__ import annotations

from ..model import Env, Output, Request, W
from . import common as c


def step(env: Env) -> Output:
    cfg, inp = env.cfg, env.inp
    sc = cfg.scenario("pfc")
    out = Output()
    if inp.v("remote") is None and sc.enabled:  # R-44 п.3: `remote` — критичний вхід PFC
        out.state, out.facts = "warn", {"reason": "немає даних: " + ", ".join(inp.code_list(["remote"]))}
        return out
    faults = [(k, inp.v(f"pfc{k}_fault")) for k in (1, 2)]
    bad = next(((k, v) for k, v in faults if v is not None and v > 0), None)
    cos = {f"cos{k}": inp.v(f"s{k}_cos") for k in (1, 2) if inp.v(f"s{k}_cos") is not None}
    out.facts = dict(cos)
    if bad is not None:  # заявку ТО й події створює W1 (R-35), рушій їх не дублює
        out.state = "warn"
        out.facts["fault"] = f"PFC-{bad[0]} ступінь {int(bad[1])}"
    if sc.enabled:
        target = float(cfg.params("pfc")["cos_target"])
        out.requests.append(Request("pfc", [W("pfc_mode", 1), W("pfc_cos", round(target, 4))], "pfc"))
        if bad is None:
            out.state = "active"
            out.facts["cos_target"] = target
        if c.once(env, "pfc:enabled", True):
            out.events.append(
                c.ev(
                    "pfc",
                    "auto_step",
                    f"PFC: автоматичний режим, ціль cos φ {target:g}",
                    signal=cfg.sig("pfc_cos"),
                    value=target,
                )
            )
    else:
        out.requests.append(Request("pfc", [W("pfc_mode", 0)], "pfc"))
        if bad is None:
            out.state = "off"
        if c.once(env, "pfc:enabled", False):
            out.events.append(
                c.ev("pfc", "auto_release", "PFC: ручний режим (ступені вимкнені)", signal=cfg.sig("pfc_mode"), value=0)
            )
    return out
