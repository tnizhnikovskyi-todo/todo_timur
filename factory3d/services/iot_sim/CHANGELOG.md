# Changelog — iot_sim

## Unreleased: портал STORETEQ (вау №19)
- Авто-завдання порталу: `protocols/woodstore_auto.py` — РЦ розкрою (SAW-1…3, NEST-1) у WORKING без завдання в черзі отримує `feed` на 2…5 листів із `external_ref` = МО активного завдання РЦ
  (REST woodStore раніше віддавав лише завдання від Odoo); `GET /status` показує фази `moving/picking/placing`. `SIM_WOODSTORE_AUTOFEED=0` вимикає. Тести: `tests/protocols/test_woodstore_auto.py`.
- Стоси woodStore стенда: `catalog/woodstore_stacks.json` — 27 стосів `PLT-01A…PLT-09C`, 23 з листами, як залишки демо-бази Odoo (раніше 36 синтетичних зі стосами `PLT-04E`, яких в Odoo немає;
  `SIM_WOODSTORE_STACKS` — інший файл). Тести `test_woodstore.py` перейшли на непорожній стос `PLT-01B`.

## Unreleased
- Штатний стан «Енергетики» як у макеті W1: КГУ **в резерві** (`state=0`, `chp_kw=0`); запуск — прапор світу `chp_run`
  або запис ненульового «Load setpoint» у HR 40007 (Modbus u72), 0 — зупинка. СЕС: сезонна амплітуда `season`
  (жовтень ≈ 0,75 літнього). BESS: розряд на дефіцит лише понад `bess_shave_kw` (600 кВт; 0 — R-13 макета).
  У робочу добу `Q1 + Q2 > 0` (імпорт +), невеликий експорт лише на T2 вдень. Тести: `test_models_energy`, `test_models_pv`.

## 0.1.0
- Перший випуск емулятора обладнання factory3d: ядро (World, сигнали, сценарії S-01…S-15, знімок), моделі (РЦ, енергетика,
  інженерія, пожежна панель, двір, СКУД, мобільна техніка), протоколи (OPC UA, Modbus TCP, BACnet/IP, HelvarNet, MQTT, BioStar 2,
  SICS, woodStore, jobs, LPR push), REST керування `/sim/v1`, режим `follow_odoo`.
- Стенд (W6): `tests/stand` (`pytest -m stand`, ТК/ТБ/ТП), compose `dev`/`demo`, `TEST_REPORT.md`, `DEPLOY_TEST.md`.
- Виправлено за результатами стенду: образ (макет BACnet), `read_only` ФС, compose (ports лише в dev), BACnet (інтерфейс
  `f3d_sim`, 302 LSP, сегментація `object-list` перевірена), OPC UA (26 прапорів, заборона клієнтського Write),
  знімок РЦ (`shift_key`), MQTT (`status` при зміні, `to_charge`), `battery_low`, `reset` моделей і двору, поріг `QF-*`,
  код 401 BioStar, метрика tick lag, `SIM_HELVAR_VERSION` з env.
- `fire_drill` без `detector` для `FA-CNC` піднімає `2.CNC.05` (AC-15); Modbus 2020 (Reset All Energies) обнуляє лічильники.
- `mypy --strict`, `ruff`, `pre-commit` (корінь репозиторію).
