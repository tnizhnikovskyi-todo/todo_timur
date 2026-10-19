# ruff: noqa
"""Знімок payload energy/infra всередині Odoo (``odoo-bin shell``, stdin): CE-03 ``infra.totals``, ``island`` живого
знімка, ключі ``energy.totals``. Не імпортується pytest і не потрапляє в Odoo test-tags. Друкує ``PAYLOAD {json}``.
Змінні: PAYLOAD_LOGIN — виконати від імені користувача (ТБ-06: без sudo), PAYLOAD_KIOSK=1 — ``ctx.kiosk`` (AC-65).
Працює без модуля viewer: ``build_infra``/``build_energy`` — чисті функції (env, ctx, payload)."""

import json
import os

from odoo.addons.td_energy.tools import payload as pl

login = os.environ.get("PAYLOAD_LOGIN")
if login:
    env = env(user=env["res.users"].search([("login", "=", login)], limit=1).id)  # noqa: F821
ctx = {"kiosk": True} if os.environ.get("PAYLOAD_KIOSK") == "1" else {}
out, energy = {}, {}
res = {"login": login or "admin"}
try:
    pl.build_infra(env, ctx, out)
    pl.build_energy(env, ctx, energy)
    res["error"] = None
except Exception as e:  # ТБ-06: виняток недопустимий — повідомити в результаті
    res["error"] = repr(e)
res["infra_totals"] = (out.get("infra") or {}).get("totals", {})
res["energy_present"] = "energy" in energy
etot = (energy.get("energy") or {}).get("totals", {})
res["energy_totals_keys"] = sorted(etot.keys())
res["productions_cost"] = [("energy_cost" in p) for p in (energy.get("productions") or [])]
try:
    snap = env["td.energy.node"]._td_live_snapshot()
    res["island"], res["bess_mode"] = snap.get("island"), snap.get("bess_mode")
except Exception as e:
    res["island"] = res["bess_mode"] = None
print("PAYLOAD " + json.dumps(res, default=str))
