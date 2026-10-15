# factory3d_energy — Завод 3D: енергетика

Схема електропостачання, лічильники PM5560, 15-хв профіль, баланс, кВт·год і вартість на завдання й МО, СЕС,
накопичувач, КГУ, АВР, тарифи. Специфікація — `docs/modules/factory3d_energy/SPEC.md`.

## Стан (W0)
Каркас: групи (`group_f3d_energy_user` / `_cost` / `_manager`), параметри `factory3d.energy.*`, меню «Енергетика»,
CSV-дані. Моделі, види, крони й хуки додають W1…W5 (поради в коментарях `__manifest__.py`, `models/__init__.py`,
`views/menus.xml`; рядки прав — `security/ir.model.access.full.csv`, копіюються в `ir.model.access.csv` разом із моделлю).

## Залежності
`factory3d_telemetry`, `mrp_account`, `analytic`, `web_hierarchy`. (`mrp_workorder` — Enterprise, не вимагається, ENV-2.)

## Дані
`data/energy_*.csv` генеруються з макета, Odoo їх не вантажить напряму (читає хук W1):
`python3 odoo_addons/factory3d_energy/tools/gen_energy_data.py --root .` (з каталогу `factory3d/`).

## Тести
`F3D_TEST_INSTALL=factory3d_energy tools/odoo/run_tests.sh <db> /factory3d_energy`
