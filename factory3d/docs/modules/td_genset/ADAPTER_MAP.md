# ADAPTER_MAP: td_genset_factory3d ↔ td_genset (Odoo 19)

Джерело правди — `odoo_addons/td_genset_factory3d/adapters/td_genset.py`; звірено з `odoo_addons/td_genset/models/*.py`.
Тест-контракт: `td_genset_factory3d/tests/test_adapter_contract.py`.

## Таблиця імен

| ADP / ключ | td_genset 19 (модель.поле) | Одиниці | Примітка |
|---|---|---|---|
| ADP-01 | `td.genset`, `td.genset.reading`, `td.genset.event` | — | `active` є |
| ADP-02 | `td.genset.search([active=True], order=id)` | — | |
| ts | `td.genset.last_reading_at` (related `last_reading_id.ts`) | UTC | |
| online | `td.genset.link_state == 'online'` | — | враховує `/status` ретранслятора і свіжість знімків (`link_lost_min`) |
| state_raw | `td.genset.genset_status` ('0'…'15') | — | STATE_MAP покриває усі 16 |
| mode_raw | `td.genset.controller_mode` (auto/manual/stop/test/unknown) | — | unknown -> None -> код 0 |
| mains_ok | `td.genset.mains_ok` | bool | |
| breaker_raw | `td.genset.feed_source` (mains/genset/none) | — | BREAKER_MAP: none 0, mains 1, genset 2 |
| p_kw | `td.genset.active_power` | kW | сумарна, знакова |
| u_v | середнє `gen_uab/gen_ubc/gen_uca` | V | розрахунок у `snapshot()` |
| f_hz | `td.genset.gen_freq` | Гц | |
| i_a | max(`current_a/b/c`) | A | розрахунок у `snapshot()` |
| pf | `td.genset.power_factor` | — | |
| kwh | `td.genset.energy_kwh` | kWh | накопичена |
| fuel_pct / fuel_l | `fuel_level` / `fuel_liters` | % / L | |
| hours | `td.genset.run_hours_total` | год | |
| starts | `td.genset.start_count` | шт | |
| coolant_c | `td.genset.water_temp` | °C | |
| oil_bar | `td.genset.oil_pressure` / 100 | kPa -> bar | |
| batt_v / charger_v | `battery_v` / `dplus_v` | V | |
| rpm | `td.genset.speed` | об/хв | |
| mains_u_v / mains_f_hz | середнє `mains_uab/ubc/uca` / `mains_freq` | V / Гц | |
| alarms | `td.genset.alarm` (genset_id, state != cleared): `code`, `name`, `level`, `date_raised` | — | `crit` -> shutdown, `warn` -> warning, `info` пропускається |
| ADP-04 | `td.genset.event`: `date_start`, `event_type`, `display_name`, `summary/reason`, `alarm_id` | UTC | див. нижче |
| ADP-05 | `maint_interval_hours`, `maint_next_hours`, `maint_state`; остання закрита заявка `maintenance.request.td_run_hours_at_close`, `close_date` (через `_maint_last_done()`) | год | `due` = `maint_state in (due, overdue)` |
| ADP-06 | `td.genset.schedule` (`schedule_line_ids`: `dayofweek`, `time_start`, `time_end`, `enabled`); `next_event_text` | Київ | вікна групуються «Пн–Пт 08:45–18:45» |
| ADP-07 | `td.genset.command` (source='test', command in test/start, state done/done_late); тривалість — наступна подія `run` | UTC | |
| ADP-08 | act_window на `td.genset` | — | |
| ADP-09 | немає | — | див. «Немає аналога» |
| ADP-10 | STATE_MAP / MODE_MAP / BREAKER_MAP | — | R-03 |

STATE_MAP (genset_status -> R-03): 0->1; 1,2,3,4->3; 5->4; 6,7->5; 8,9->6 (7 вирішує міст за breaker/p_kw); 10->8; 11,12,13->9; 14->10; 15->1.
MODE_MAP: stop 0, manual 1, auto 2, test 3.

## Немає аналога в td_genset — рішення

| Що | Рішення |
|---|---|
| Сталої витрати палива (ADP-09) | У `td.genset` є лише обчислювані `fuel_rate_lph_7d/30d`; `FIELD_FUEL_RATE_LPH=None`, `set_fuel_rate()` повертає `False` без запису (Q-11). |
| Стан R-03 код 2 «мережа втрачена, затримка» | `genset_status` його не має; міст виводить код 2 сам: STATE=1 і `mains_ok=False`. |
| Події: `value`, `unit`, `threshold` | `td.genset.event` їх не має -> `None`. `code` = `event_type` (для `alarm` — `alarm_id.code`); severity: alarm по `alarm_id.level`, link/gap -> comm, maintenance -> service, external_control -> command, outage/drain -> warning, run/refuel -> info. |
| `td.genset.alarm` не з контролера | Активні тривоги `link_lost`, `cmd_unconfirmed` тощо теж потрапляють у `alarms` (рівні crit/warn); `online`=0 їх перекриває. Ризик: завищений `alarm_level` при втраті зв'язку. |
| Тривалість останнього тесту | Окремої моделі тестів немає; береться з журналу команд і події `run`; `duration_min=None`, якщо запуск ще триває/не знайдено. |

## Q-10…Q-19

| Q | Статус | Рішення |
|---|---|---|
| Q-10 | закрито | імена звірені (таблиця вище) |
| Q-11 | закрито | у td_genset немає сталої витрати -> ADP-09 `False`, крива в мосту (R-01) |
| Q-12 | закрито | групи td_genset: `td_genset.group_user`, `group_admin`, `group_tech` (відповідність — SPEC §4.3) |
| Q-13 | частково | коди подій td_genset: `event_type` (run, outage, refuel, drain, external_control, alarm, link, gap, maintenance); для alarm — `td.genset.alarm.code` (ключі сигналів контролера, напр. `high_temp_warning`); `td_code` 41 рядка — за цими кодами (W2 data) |
| Q-14 | закрито | формат journal/relay — на боці td_genset (`relay_api`); міст читає ORM, не HTTP |
| Q-15 | закрито | `link_lost_min` у `td.genset.config` визначає online; мостове `offline_min=5` |
| Q-16 | закрито | стоп-кран команд: `td.genset.commands_allowed` (і `relay_enabled` — опитування); `data/neutralize.sql` td_genset обнуляє обидва і видаляє токен `td_genset.relay_token`; ім'я для AC-A15/ТБ-04: `td.genset.commands_allowed` |
| Q-17 | закрито | td_genset створює превентивні заявки ТО (`_create_maintenance_request`) -> `SERVICE_REQUESTS_BY_TD=True` |
| Q-18 | закрито | окремого «останнього тесту» немає; ADP-07 з журналу команд (source=test); немає -> `None` -> «—» |
| Q-19 | закрито | сервіси OWL-пульта td_genset не використовуються адаптером (`get_pult_state` у `genset_ui.py`, MG-20…MG-24 — на боці td_genset) |
