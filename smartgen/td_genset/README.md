# td_genset — «Генератори» (Odoo 18.0)

Моніторинг і керування генератором SmartGen HGM6120N через ретранслятор: показання, події, тривоги з
ескалацією, пульт з підтвердженням команд, розклад/таймер/тест, паливо і ТО. Залежності — лише Community
(`base`, `mail`, `bus`, `web`, `maintenance`). Джерела: `../SPEC.md`, `../ТР_SmartGen_генератор.md`,
`../relay_api.md`, `../BUILD_PLAN.md`.

- Встановлення/тести: `smartgen/tools/odoo/run_tests.sh td_<потік>` (unit, `RelayMock`), стенд —
  `run_stand_tests.sh` (емулятор `smartgen/tools/fake_relay.py`, тег `td_genset_stand`).
- Адреса/токен — лише Налаштування → Генератори (`ir.config_parameter`, `base.group_system`).
- Стоп-крани: «Опитувати ретранслятор» (`relay_enabled`), «Дозволити команди» (`commands_allowed`).
- Каркас W0: поля `td.genset` — лише `models/genset.py`; методи — у файлах потоків; заглушки позначені
  «Заглушка W0» у докстрингу (прибрати позначку під час реалізації). Повний README — W5.
