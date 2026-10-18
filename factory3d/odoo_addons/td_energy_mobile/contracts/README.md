# Заморожені контракти W4: `td_energy_mobile` (C-06, C-07, C-08, API-H1)

Джерело — `build/energy/W4_SPEC.md` (H.3.4, H.7, H.9) і `W4_ARCH.md` §2.1; копії — `docs/modules/td_energy_mobile/`.
Зміни — **лише через менеджера**. Файли — приклади-еталони структури (ключі й типи); тест
`tests/test_wh_contracts.py` звіряє моделі, поля й файли `td_energy` з контрактами, а відповідь `get_mobile` — з
`api_h1_get_mobile.json` (після появи методу, воркер C).

| Файл | Контракт | Напрям |
|---|---|---|
| `api_h1_get_mobile.json`, `api_h1_rules.json` | API-H1 `td.energy.round.get_mobile`; правила форми, API-H2…H6 (сигнатури) | C → клієнт вкладки |
| `c06_mobile_tabs.json` | C-06: запис реєстру `td_energy.mobile_tabs`, props вкладки, тік шини `state`, `useEnergyActions()` | `td_energy_mobile` → `td_energy` (W1 C-33) |
| `c07_energy_core.json` | C-07: `td.energy.event._td_log`, `td.energy.dashboard.get_pult`, `td.signal`, `td.energy.node`, `tools/dates` | `td_energy` → mobile |
| `c08_round_optional.json` | C-08: `td.energy.round` для блоку «Обходи» звіту зміни (опційно, `env.get`) | mobile → `td_energy_analytics` |

C-01…C-05, C-02 і API-01 — у `td_energy_analytics/contracts/`.

Формат файлів `c0*.json`: `models` (модель → обов'язкові поля), `methods` (`модель.метод(...)`), `tools` (модуль → імена),
`params` (ключі `ir.config_parameter`), `td_energy_files_must_contain` (C-06: файли клієнта й рядки в них).
