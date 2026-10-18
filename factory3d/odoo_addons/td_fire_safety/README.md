# Завод 3D: Пожежна безпека (`td_fire_safety`)

Пожежна сигналізація **лише для читання** (рішення D-07): модуль ніколи не пише в прилад і не створює `td.command`.
Додатково: іскрогасіння, димовидалення, спринклери, евакуація за нормами ДБН, навчальні тривоги.

Статус: W0-скелет — файли даних і генератор готові, моделі додають W1…W4. Специфікація —
`factory3d/docs/modules/td_fire_safety/SPEC.md`.

## Дані з макета

```bash
cd factory3d
python3 odoo_addons/td_fire_safety/tools/gen_data.py --root .   # перегенерувати data/td_fire_*.csv|xml
```

Генератор детермінований; `tests/test_data_sync.py` (AC-71) перевіряє побайтову рівність із `data/`:

```bash
cd factory3d && PYTHONPATH=<odoo> python -m pytest odoo_addons/td_fire_safety/tests/test_data_sync.py -q
```

(`odoo` має бути в `PYTHONPATH`, бо pytest імпортує пакет модуля разом із `tests/__init__.py`.)

## Тести Odoo

```bash
F3D_TEST_INSTALL=td_factory3d,td_telemetry,td_fire_safety \
  factory3d/tools/odoo/run_tests.sh f3d_fire_w0 /td_fire_safety
```

## Нейтралізація

`data/neutralize.sql` вимикає читання, крони, джерела, переклички й активності тривог у копії проду.
