# td_genset_factory3d — технічне рішення W1 (за посиланням)

Технічне рішення W1 — `factory3d/build/energy/W1_ARCH.md` (розд. 2.1: C-31, C-37; розд. 6.1: воркер W1-C «Міст і емулятор»). Попередні редакції — `docs/modules/td_genset/ARCHITECTURE.md` (розділ про міст).
**Рішення про розміщення:** за посиланням, не злито.
Файли W1-C: `hooks.py` (`_restore_td_genset_root`), `models/td_energy_dashboard.py` (хуки `td.energy.dashboard`), `adapters/td_genset.py` (ADP-11), `data/menu_hide.xml`, `security/td_genset_factory3d_security.xml`, `views/menus.xml`, `tests/test_w1_section.py`, `tests/test_w1_hooks.py`, `tests/stand/test_w1_tk_g.py`. Каркас (маніфест, порожні файли) створено комітом «scaffold:» гілки `claude/td-energy-w1`.
