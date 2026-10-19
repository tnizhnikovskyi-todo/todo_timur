# td-collector-energy

Плагін збирача `energy_ctl` (джерело `ENERGY-CTL`): цикл автоматики енергетики (6 сценаріїв) і виконавець інтентів
оператора. Специфікація — [`td_energy_control/SPEC.md`](../../../docs/modules/td_energy_control/SPEC.md) §8.1, правила
R-41…R-53, R-60; технічне рішення — [`td_energy_control/ARCHITECTURE.md`](../../../docs/modules/td_energy_control/ARCHITECTURE.md);
контракти (заморожені) — `factory3d/odoo_addons/td_energy_control/contracts/` (C-38…C-47).

## Склад

| Модуль | Що робить |
|---|---|
| `plugin.py` | `EnergyCtlPlugin`: `validate`/`connect`/`subscribe` (4 задачі)/`call`/`health`/`disconnect`; єдиний екземпляр |
| `config.py` | API-24: схема, значення за замовчуванням, межі коду (`limits.py`), `Config` |
| `inputs.py`, `derived.py`, `interlocks.py` | свіжі входи з `ctx.live` і похідні входи D-47; реєстр блокувань R-41 (золоті випадки — `tests/golden.py`) |
| `engine.py`, `scenarios/*` | рушій R-44 (режими off/hold/auto, арбітраж, перекриття) і чисті функції `step(env)` сценаріїв |
| `actuator.py` | `Writer` (allowlist, `DENY_PREFIXES`) і `Actuator` («лише за зміни», інтервал, сторожовий таймер, повтор) |
| `intents.py`, `executor.py` | види інтентів R-42, приймання/черга/верифікація/fail-safe R-52 |
| `reporter.py`, `store.py` | API-25 (пакети, буфер, throttle), атомарний стан `td_energy_ctl.json` |

## Вхід і запис

Плагін читає лише `ctx.live` (показання інших джерел після масштабу ядра) і пише лише через `ctx.write_signal`
(`CommandLoop.write_direct`: ті самі запобіжники, що в `_execute`). Коди сигналів не зашиті — тільки логічні імена з API-24
(`signals`, `inputs`, `shed[].signal`, `bms.*`). Стани `kind=state` із `map` приходять текстом (`running`, `pos_I`…) —
`inputs.TEXT_NUM` зводить їх до індексу.

**Похідні входи (D-47).** `energy/totals/p_now`, `energy/sections/S{1,2}/p_kw`, `infra/ats/src1_ok`, `infra/totals/{grid_kw,
export_kw,pv_now}` збирач не опитує: їх рахує сам плагін за формулами блоку `derived` API-24 (`derived.py`: `sum` з `k`,
`min` терма, `clamp_min`, `zero_if`; `ge`) із `LiveCache`. Терм відсутній або старший за `max_age_s` → вхід відсутній
(fail-closed), невідома операція → вхід відсутній і попередження в журнал.

**Дистанційне перемикання (D-46).** Прапор `flags.remote_switching_enabled` з API-24 (параметр Odoo
`td.energy_control.remote_switching_enabled`, за замовчуванням `False`; на demo/стенді `True`) вмикає інтенти `qs_close`,
`qs_open`, `chp_start`, `bess_discharge` (`intents.REMOTE_GATED`). Поки прапор вимкнено, `executor` відмовляє зі станом
`rejected` і причиною «Дистанційне перемикання вимкнено: td.energy_control.remote_switching_enabled»; `genset_test` — не
інтент збирача, його блокує Odoo. Інші інтенти (заряд/зупинка BESS, `chp_stop`, сцени BMS, уставка повітря) не зачіпаються.

**Пожежна тривога й нічний режим (D-48, D-49).** `fire_state = alarm` не переводить рушій у `hold`: режим лишається `auto`,
блокується запис лише ресурсів `vent` і `light` (R-44 п.8; сценарій `night` повідомляє `warn`). Сценарій `night` не потребує
входу `remote` (цілі BMS ідуть не через контролер ГРЩ); критичний вхід `remote` лишився лише в `pfc`. Параметр
`verify_timeout_s` (30 с; Odoo `td.energy_control.verify_timeout_s`, `Config.verify_timeout_s`, також у відповіді API-17
`prepare`) — очікування підтвердження пристроєм читанням назад.

## Тести

```
cd factory3d/services/collector && .venv/bin/pip install -e ../collector_plugins/td_collector_energy --no-deps
.venv/bin/pytest ../collector_plugins/td_collector_energy -q
```
