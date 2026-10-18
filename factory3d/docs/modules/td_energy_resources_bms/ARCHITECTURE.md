# td_energy_resources_bms — ARCHITECTURE (за посиланням)

Технічне рішення моста — `factory3d/build/energy/W3_ARCH.md` (розд. 2.1: рішення A-01, контракт C-04; розд. 6: воркер B). Мост лише розширює моделі ядра через `_inherit` (`td.energy.point`, `td.energy.res.dashboard`, `td.energy.res.interval`, `td.energy.opportunity.rule`) і не змінює `td_bms`.
