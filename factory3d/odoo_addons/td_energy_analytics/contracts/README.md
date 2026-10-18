# Заморожені контракти W4: `td_energy_analytics` (C-01…C-05, API-01)

Джерело — `build/energy/W4_SPEC.md` (розд. 7, 9) і `W4_ARCH.md` §2.1; копії — `docs/modules/td_energy_analytics/`.
Зміни — **лише через менеджера**. Файли — приклади-еталони структури (ключі й типи); тест
`tests/test_w4_contracts.py` звіряє моделі й поля з реєстром Odoo, а відповідь `get_dashboard` — з `api01_get_dashboard.json`
(після появи методу, воркер A).

| Файл | Контракт | Напрям |
|---|---|---|
| `api01_get_dashboard.json`, `api01_rules.json` | API-01 `td.energy.analytics.get_dashboard` (форма відповіді; правила, періоди, розрізи, ключі ₴) | A → B (екран, звіти) |
| `c01_w3_resources.json` | C-01: `td.energy.usage`, прапорці ресурсу, `_td_price_at`, `td.energy.opportunity` (API-02…06 W3), `tools/shifts` | W3 → W4 |
| `c02_report_hook.json` | C-02: хук `td.energy.dashboard._td_report_action` (правка W1 менеджером), `meta.report_action` | analytics → `td_energy` |
| `c03_energy_w1.json` | C-03: `td.energy.interval/alloc/node/tariff/event/outage.plan`, `mrp.production.td_energy_cost`, `tools/dates`, `day.mixin` | W1…W3 → W4 |
| `c04_mrp_stock.json` | C-04: `stock.move`, `mrp.*`, `product.template.td_plate_area_m2` (власне поле) | MRP/склад → W4 |
| `c05_telemetry.json` | C-05: `td.reading.hour` (температура для HDD) | `td_telemetry` → W4 |

C-06, C-07, API-H1 і C-08 (`td.energy.round` для звіту зміни; читач — `report/report_data.py` W4-B через
`env.get("td.energy.round")`) зафіксовано в `td_energy_mobile/contracts/` (провайдер — модуль обходів).

Формат файлів `c0*.json`: `models` (модель → обов'язкові поля), `methods` (`модель.метод(...)`), `tools` (модуль → імена),
`params` (ключі `ir.config_parameter`).
