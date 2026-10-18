# td-collector-energy

Плагін збирача `energy_ctl` (джерело `ENERGY-CTL`): цикл автоматики енергетики (6 сценаріїв) і виконавець інтентів
оператора. Специфікація — `factory3d/build/energy/W2_SPEC.md` §8.1, правила R-41…R-53, R-60; контракти (заморожені) —
`factory3d/odoo_addons/td_energy_control/contracts/` (C-38…C-47).

## Склад

| Модуль | Що робить |
|---|---|
| `plugin.py` | `EnergyCtlPlugin`: `validate`/`connect`/`subscribe` (4 задачі)/`call`/`health`/`disconnect`; єдиний екземпляр |
| `config.py` | API-24: схема, значення за замовчуванням, межі коду (`limits.py`), `Config` |
| `inputs.py`, `interlocks.py` | свіжі входи з `ctx.live`; реєстр блокувань R-41 (золоті випадки — `tests/golden.py`) |
| `engine.py`, `scenarios/*` | рушій R-44 (режими off/hold/auto, арбітраж, перекриття) і чисті функції `step(env)` сценаріїв |
| `actuator.py` | `Writer` (allowlist, `DENY_PREFIXES`) і `Actuator` («лише за зміни», інтервал, сторожовий таймер, повтор) |
| `intents.py`, `executor.py` | види інтентів R-42, приймання/черга/верифікація/fail-safe R-52 |
| `reporter.py`, `store.py` | API-25 (пакети, буфер, throttle), атомарний стан `td_energy_ctl.json` |

## Вхід і запис

Плагін читає лише `ctx.live` (показання інших джерел після масштабу ядра) і пише лише через `ctx.write_signal`
(`CommandLoop.write_direct`: ті самі запобіжники, що в `_execute`). Коди сигналів не зашиті — тільки логічні імена з API-24
(`signals`, `inputs`, `shed[].signal`, `bms.*`). Стани `kind=state` із `map` приходять текстом (`running`, `pos_I`…) —
`inputs.TEXT_NUM` зводить їх до індексу.

**Увага (входи, що їх збирач не опитує).** `energy/totals/p_now`, `energy/sections/S{1,2}/p_kw`, `infra/ats/src1_ok` —
похідні `EN-DERIVED` (рахує Odoo, у збирача їх немає): без них `backup` дає `warn`, а `qs_close`, `bess_charge`, `chp_start`
блокуються fail-closed. Рішення — віддати збирачу опитувані джерела (наприклад, `inputs.src1_ok → infra/ats/src1_state`).

## Тести

```
cd factory3d/services/collector && .venv/bin/pip install -e ../collector_plugins/td_collector_energy --no-deps
.venv/bin/pytest ../collector_plugins/td_collector_energy -q
```
