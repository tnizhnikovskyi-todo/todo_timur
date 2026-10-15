# Changelog — iot_sim

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
