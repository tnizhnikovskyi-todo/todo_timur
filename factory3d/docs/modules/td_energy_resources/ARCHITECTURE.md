# td_energy_resources — ARCHITECTURE (за посиланням)

Технічне рішення W3 підключено за посиланням: `factory3d/build/energy/W3_ARCH.md` (розд. 2 — структура й контракти C-01…C-06, розд. 6 — план збирання: воркери A «дані», B «резерви й міст», C «екран», D «емулятор», E «API екрана»).

Каркас (комміт «scaffold:» гілки `claude/td-energy-w3`): маніфести, `__init__.py`, заглушки файлів усіх воркерів, `security/ir.model.access.csv` + `ir.model.access-opportunity.csv`, контракти JSON. Воркери не змінюють `__manifest__.py`, `__init__.py`, `models/__init__.py`, `tools/__init__.py`, `tools/detectors/__init__.py`, `controllers/__init__.py`, `tests/__init__.py` без погодження.
