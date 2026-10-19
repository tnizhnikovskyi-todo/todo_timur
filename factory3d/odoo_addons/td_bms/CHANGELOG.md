# Changelog

## 19.0.1.0.1 — тепло КГУ в тепловому балансі
- Сигнали КГУ (`infra/chp/heat_kw`, `infra/totals/chp_kw`), мережі й пожежі привʼязуються до порожніх полів `td.bms.heat.balance`
  незалежно від порядку встановлення `td_bms` / `td_energy` (раніше лише в `post_init_hook`, тож у базах із `td_energy` після `td_bms`
  баланс рахував проєктні 497 кВт і при зупиненій КГУ): `td.bms.heat.balance._td_bms_link_optional`, `td.signal.create`.
- Міграція `19.0.1.0.1`: довантажує сигнали в баланс наявних баз (лише порожні поля, привʼязку вручну не чіпає). Тести `TestChpHeatSource`.

## Unreleased

- `static/description/icon.png` (копія td_factory3d): блок `<app name="td_bms">` на сторінках «Налаштування» давав 404.

## 19.0.1.0.0
- Каркас модуля «Будівля»: група «Будівля: оператор» (привілей `privilege_td_bms`), параметри `td.bms.*`,
  каркас меню, `neutralize.sql`, заготовка крону перевірки відхилень (`data/ir_cron.xml`, підключається після моделей).
