# td_energy_resources_bms — специфікація (міст «Енергоресурси — Будівля»)

Версія 0.2 · 19.10.2026 (v0.1 — 18.10.2026, Частина II `W3_SPEC.md`) · стандарт `docs/DOC_STANDARD.md` · технічне рішення: [ARCHITECTURE.md](ARCHITECTURE.md) · статус: збудовано (гілка `claude/td-energy-w4`).
Ядро — [../td_energy_resources/SPEC.md](../td_energy_resources/SPEC.md) (Частина I: M-01…M-11, V-01…V-13, API-01…API-10, R-01…R-25, AC-01…AC-64, A-01…A-16, Q-01…Q-08); хуки ядра, які перекриває міст: `td.energy.point._td_bind_extra`, `td.energy.res.dashboard._td_heat_kpis|_td_heat_list|_td_heat_chart_note`, `td.energy.res.interval._td_backfill_extra`, методи детекторів `td.energy.opportunity.rule._td_detect_<code>`. Нумерація мосту має префікс `B` (M-B1, UI-B1, R-B1…R-B5, AC-B01…AC-B10, A-B1…A-B2, Q-B1); поза таблицями ID пишеться з модулем: `td_energy_resources_bms R-B2`.
Мова: проза — українською, рядки інтерфейсу — українські.

Міст (`auto_install`: `td_energy_resources` + `td_bms`) додає вкладці «Тепло» дані BMS: точки й лічильники тепла, KPI температури й рекуперації, список «Куди йде тепло», три детектори. Відсутність `td_bms` — ядро працює без тепла (AC-64).

## B.0 Дерево файлів

```
odoo_addons/td_energy_resources_bms/              B
├── __manifest__.py                               (менеджер) version 19.0.1.0.0; depends [td_energy_resources, td_bms]; auto_install True
├── __init__.py                                   (менеджер)
├── hooks.py                                      B  post_init_hook → env["td.energy.point"]._td_bind_extra()
├── models/
│   ├── __init__.py                               (менеджер)
│   ├── td_energy_point.py                        B  M-B1 (_inherit: hvac_ref → зв'язки, `_td_bind_extra`)
│   ├── td_energy_res_dashboard.py                B  M-B2 (_inherit: гаки тепла)
│   ├── td_energy_res_interval.py                 B  `_td_backfill_extra` (R-B5)
│   └── td_energy_opportunity_rule.py             B  `_td_detect_preheat_early`, `_td_detect_ahu_recuperation`, `_td_detect_dock_gates`
├── tools/heat.py                                 B  R-B2, R-B3 (η, індикатори), R-B5 (генератори)
├── data/opportunity_rules.xml                    B  3 правила (noupdate=1)
├── data/neutralize.sql                           B  (порожній, коментар)
├── static/src/heat_note.xml                      B  UI-B1 (підпис «оцінка» в KPI «Рекуперація»; шаблон-спадкоємець `ResKpis`)
└── tests/test_wb_bridge.py, tests/stand/test_wb_tk.py   B
```

## B.1 Маніфест

`depends: ["td_energy_resources", "td_bms"]`, `auto_install: True`, `data`: `data/opportunity_rules.xml`; `assets`: `web.assets_backend`: `td_energy_resources_bms/static/src/**`; `post_init_hook`: `hooks.post_init_hook`.

## B.2 Моделі

### M-B1 `td.energy.point` — розширення

Поле `hvac_unit_id` — Many2one `td.bms.hvac.unit` (ondelete=set null, «Установка BMS»); `hvac_ref` ядра лишається текстовим кодом (джерело для `_td_bind_extra`). Метод `_td_bind_extra()` (R-B1): ідемпотентно створює точки й лічильники тепла.

### M-B2 `td.energy.res.dashboard` — розширення

Реалізація гаків ядра: `_td_heat_kpis(ctx)` (R-B2), `_td_heat_list(ctx)` (R-B2 п. 4), `_td_heat_chart_note(ctx)` → `capacity_kw` з `td.bms.heat.balance` (активний запис компанії).

### UI-B1 Бейдж «оцінка» у KPI «Рекуперація»

Шаблон-спадкоємець `td_energy_resources.ResKpis` (`static/src/heat_note.xml`, `t-inherit`): у картки з `quality='estimated'` показується крапка й підпис «оцінка» (підказка «Розрахунок за тепловим балансом установки»); ядро показує лише крапку. Гаків і стану JS немає.

## B.3 Дані

`data/opportunity_rules.xml` (`noupdate="1"`): правила `preheat_early` (`resource=gas`), `ahu_recuperation` (`resource=heat`), `dock_gates` (`resource=heat`) з `params`, `params_schema`, `actions`, `control_intent` (`heat_schedule_shift` для першого; в решти порожньо).
Точки й лічильники тепла створює `_td_bind_extra()` (не XML), бо залежать від встановлених сигналів BMS.

## B.4 Алгоритми

### R-B1 Прив'язка BMS (FR-B1)

`_td_bind_extra()`:
1. `balance = env["td.bms.heat.balance"].search([("company_id", "=", env.company.id)], limit=1)`; немає — вихід (`{}`).
2. Точки `heat`: `HEAT-BOILER` (`source`; сигнал `balance.boiler_heat_signal_id`), `HEAT-CHP` (`source`; `balance.chp_heat_signal_id`), споживачі `RV-ALL` (`hvac_ref='RV-*'`), `AHU-1` (`hvac_unit_id` за `code='AHU-1'`), `OFFICE` (залишок), `DOCK` — лише якщо знайдено сигнал відкриття воріт: `env.get("td.yard.gate")` → перший шлагбаум/ворота зі `state_signal_id` і `direction` відвантаження (`side='east'`), інакше точка не створюється (Q-08).
3. Лічильники: `HM-BOILER`, `HM-CHP` (`flow_integrate`, один сигнал); `HM-RV` (`flow_integrate`, `flow_signal_ids` = `heat_signal_id` усіх `td.bms.hvac.unit` із `code like 'RV-%'`); `HM-AHU1` (`heat_signal_id` установки `AHU-1`); `HM-DOCK` (`estimate`, `gate_loss`: `loss_kw_per_k=3,5`, `t_out_signal=ventilation/totals/outdoor_c`, `t_in` = `balance.t_in_set`); `HM-OFFICE` (`estimate`, `residual` `{"from": ["HEAT-BOILER","HEAT-CHP"]}`).
4. Ідемпотентність за `(resource, code)`; змінені вручну поля наявних записів не перезаписуються.
Очікувані кількості на демо-БД: точок тепла 5 (без `DOCK`) або 6; лічильників 5 або 6; `HM-RV` — 25 сигналів.

### R-B2 Теплові KPI й список (FR-B2)

1. `_td_heat_kpis(ctx)`: 
   - `power.note` = «подача {boiler_supply_signal.last_value} °C · зворот {boiler_return_signal.last_value} °C»;
   - `indoor` = середнє `indoor_c` установок із `required_in_work` (RV + AHU-1), значення 1 знак, `unit="°C"`, note «уставка {t_in_set} °C · зовні {outdoor_c} °C» (`outdoor_c` — `ventilation/totals/outdoor_c`), `good` при `|indoor − t_in_set| ≤ 1`;
   - `recovery` — R-B3 (AHU-1), note «норма ≥ {recovery_norm_pct} %» + « · фільтр брудний», якщо `filter_dp_pa > filter_dp_limit_pa`; `bad` при `η < recovery_norm`; `quality='estimated'`.
2. Параметри (`ir.config_parameter`, міст): `td.energy_resources_bms.recovery_norm_pct = 70`, `td.energy_resources_bms.filter_dp_limit_pa = 250`.
3. `power.value` — `Σ` швидкості `source`-точок (ядро), `today` — `Σ qty` джерел.
4. `_td_heat_list(ctx)`: споживачі `RV-ALL`, `AHU-1`, `DOCK`, `OFFICE` (значення — швидкість зараз, кВт; `OFFICE` = max(0, Σ джерел − решта)).
5. Приклад (14:20, макет): джерела 390 кВт; `RV-ALL 228`, `AHU-1 74`, `DOCK 46`, `OFFICE = 390 − 228 − 74 − 46 = 42`.

### R-B3 Рекуперація AHU-1 (оцінка; D-36)

`T_after = T_supply − Q_heat × 1000 / (air_wh_m3k × airflow_m3h)`; `η = (T_after − T_out)/(T_in − T_out)`, де `T_supply = supply_c`, `Q_heat = heat_kw`, `airflow_m3h` — сигнал `airflow_m3h` установки, `air_wh_m3k` — `td.bms.heat.balance.air_wh_m3k` (0,34), `T_in = indoor_c` (заміна температури витяжки; якщо з'явиться сигнал `ventilation/units/AHU-1/extract_c` — використовується він), `T_out = ventilation/totals/outdoor_c`. Захист: `T_in − T_out < 5 К`, `airflow < 10 %` від `airflow_nom` або `η ∉ [0, 1]` → `η = null`.
Приклад: `airflow 32 000 м³/год`, `Q_heat 74 кВт`, `T_supply 21,0`, `T_in 18,4`, `T_out 7,0` → `ΔT = 74 000/(0,34·32 000) = 6,80`; `T_after = 14,2`; `η = (14,2 − 7)/(18,4 − 7) = 0,632` (63 %).

### R-B4 Детектори моста (FR-B3)

**`preheat_early`** (газ): параметри `t_ready` = `balance.t_in_set` (18 °C), `margin_min=30`, `lookback_days=7`, `min_saving_uah=1000`, `control_intent="heat_schedule_shift"`.
1. Для кожного робочого дня вікна: `ready_time` = перший момент до початку першої зміни, коли середнє `indoor_c` за установками `required_in_work` ≥ `t_ready` (сирі показання, крок 5 хв); `margin = shift_start − ready_time` (хв, R-21).
2. `margin_med` = медіана за днями (≥ 3 днів); `margin_med − margin_min ≤ 0` → `[]`.
3. Газ розігріву: `preheat_rate` = середня швидкість `GM-BOILER` у вікні `[shift_start − margin_med − 60 хв, ready_time]` (м³/год); `extra_h = (margin_med − margin_min)/60`; `qty_window = preheat_rate × extra_h × (кількість робочих днів вікна)`; `est_qty_month = qty_window × K_month`; `est_saving = est_qty_month × price_gas`.
4. Текст: «Цех досягає {t_ready} °C о {ready_time}, а зміна о {shift_start}. Пізніший старт на {margin_med − margin_min} хв.»
Фікстура: `margin_med = 55`, `margin_min = 30`, `preheat_rate = 46`, 5 робочих днів, `price_gas = 19,80`, `L=7` → `extra_h = 0,4167`; `qty_window = 46 × 0,4167 × 5 = 95,83 м³`; `est_qty_month = 95,83 × 4,33 = 415,0 м³`; `est_saving = 8 216 ₴`.

**`ahu_recuperation`** (тепло): параметри `eta_norm = recovery_norm_pct/100`, `dp_limit = filter_dp_limit_pa`, `lookback_days=7`, `min_saving_uah=500`; дія `ticket` (`node_code="AHU-1"`, «AHU-1: заміна фільтра [OPP-<id>]»).
1. За вікно: `η_mean` — середнє R-B3 у робочі години (не `null`), `dp_mean` — середнє `filter_dp_pa`; знахідка при `η_mean < eta_norm` **або** `dp_mean > dp_limit`.
2. Втрати: `loss_kw = (eta_norm − η_mean) × air_wh_m3k × airflow_m3h × (T_in − T_out)/1000` (кВт; `max(0, …)`), `run_hours = кількість робочих годин вікна`; `qty_window = loss_kw × run_hours` (кВт·год тепла); `est_qty_month = qty_window × K_month`; `price_heat` — R-02 п. 3.
3. Якщо знахідка лише через `dp` (η у нормі) — `est_saving = 0` → відкидається за `min_saving`, лишається попередження в `evidence` (не створюється).
Фікстура: `η_mean = 0,632`, `eta_norm = 0,70`, `airflow 32 000`, `T_in − T_out = 11,4`, `run_hours = 80`, `price_heat = 2,0722` → `loss_kw = 0,068 × 0,34 × 32 000 × 11,4/1 000 = 8,43`; `qty_window = 674,7`; `est_qty_month = 2 921,6 кВт·год`; `est_saving = 6 054 ₴`.

**`dock_gates`** (тепло; потребує точку `DOCK`): параметри `long_open_min=10`, `min_events_day=3`, `open_norm_min_day=20`, `lookback_days=7`, `min_saving_uah=500`; дія `link` на `td_yard.action_td_yard_gate` («Показати у «Дворі»»), якщо `td_yard` встановлено, інакше запасна.
1. За сирими показаннями `state_signal` точки: «відкриття» — безперервні інтервали `≥ 0,5`; `long` — тривалістю `≥ long_open_min`; середня кількість `long` на добу `< min_events_day` → `[]`.
2. `open_min_day` = середній сумарний час відкриття на добу; `excess_h = max(0, open_min_day − open_norm_min_day)/60` на добу.
3. `loss_kw_per_k × ΔT_mean = loss_kw` (середня різниця температур вікна); `qty_window = loss_kw × excess_h × L`; `est_qty_month = qty_window × K_month`; `price_heat` — R-02 п. 3.
Фікстура: `long = 4/доба`, `open_min_day = 52`, `norm 20`, `loss_kw_per_k = 3,5`, `ΔT = 11`, `L = 7`, `price_heat = 2,0722` → `excess_h = 0,5333`; `loss_kw = 38,5`; `qty_window = 38,5 × 0,5333 × 7 = 143,7`; `est_qty_month = 622,3 кВт·год`; `est_saving = 1 290 ₴`.

### R-B5 Backfill тепла (гак `_td_backfill_extra`)

Генератори (доповнюють R-22): `HM-BOILER = heat_boiler` (R-22 п. 2, «газ»); `HM-CHP = 497 кВт`, коли КГУ працює; `HM-RV = 0,585 × heat_need`; `HM-AHU1 = 0,19 × heat_need`; оцінки `HM-DOCK`, `HM-OFFICE` — R-04 (для `DOCK` без сирих показань слоти `missing`, тому в backfill `HM-DOCK` генерується напряму: `open_frac = 0,05` у зміну, 0 поза змінами, `rate_kw = 3,5 × ΔT × open_frac`). Потрібна температура: `t_out(d, h) = 7,0 + 8·cos(2π(doy − 200)/365) + 3·sin(π(h − 9)/12)` (демо-наближення; якість `estimated`).

## B.5 Acceptance Criteria — AC-B01…AC-B10

| AC | FR | Given / When / Then | Тип |
|---|---|---|---|
| AC-B01 | FR-B1 | Given `td_bms` із `td.bms.heat.balance` і 26 установками (RV + AHU-1); When встановлення моста; Then точки `HEAT-BOILER`, `HEAT-CHP`, `RV-ALL`, `AHU-1`, `OFFICE` (+ `DOCK` за наявності сигналу воріт) і лічильники `HM-*` створено; `HM-RV.flow_signal_ids` = 25 сигналів; повторний `_td_bind_extra` — без дублів і без перезапису ручних правок | UT |
| AC-B02 | FR-B1 | Given міст установлено до/після `td_bms` (порядок встановлення обох модулів); Then результат однаковий (`auto_install` спрацьовує при появі другого) | UT + DEPLOY_TEST |
| AC-B03 | FR-B2 | Given фікстура (`boiler_heat 390`, `RV 228`, `AHU 74`, `DOCK 46`); Then `power.value=390`, note «подача 70 °C · зворот 52 °C»; список: `RV-ALL 228`, `AHU-1 74`, `DOCK 46`, `OFFICE 42` | UT |
| AC-B04 | FR-B2 | Given фікстура R-B3 (32 000 м³/год, 74 кВт, 21,0/18,4/7,0); Then `recovery.value=63` (63,2), tone `bad`, `quality='estimated'`, note «норма ≥ 70 %» (+ « · фільтр брудний» при ΔP 280 Па); `T_in − T_out < 5` → `null`, `η ∉ [0,1]` → `null` | UT |
| AC-B05 | FR-B2 | Given `indoor_c` установок і `t_in_set=18`; Then `indoor.value` = середнє, note «уставка 18 °C · зовні 7 °C», tone `good` при відхиленні ≤ 1 К; `_td_heat_chart_note` підставляє `{capacity}` з балансу | UT |
| AC-B06 | FR-B3 | Given фікстура `preheat_early` (`margin_med 55`, `margin_min 30`, 46 м³/год, 5 днів, 19,80); Then `est_qty_month = 415,0 м³`, `est_saving = 8 216`; `margin_med ≤ margin_min` → `[]`; днів < 3 → `[]` | UT |
| AC-B07 | FR-B3 | Given фікстура `ahu_recuperation` (η 0,632; норма 0,70; 32 000; ΔT 11,4; 80 год; 2,0722); Then `est_saving = 6 054`; знахідка лише за ΔP → не створюється | UT |
| AC-B08 | FR-B3 | Given фікстура `dock_gates` (4/доба; 52 хв; норма 20; 3,5 кВт/К; ΔT 11); Then `est_saving = 1 290`; `long < 3/доба` → `[]`; немає точки `DOCK` → правило пропущено без помилки | UT |
| AC-B09 | FR-B1 | Given backfill тепла; Then `HM-BOILER ≈ gas·10,5·0,914` ± 3 %; `Σ гілок` ≈ джерел ± 5 %; ідемпотентність і `purge` як AC-47 | UT |
| AC-B10 | FR-B2 | Given стенд, міст установлено; When відкрити «Тепло»; Then 4 KPI, список «Куди йде тепло», підпис «оцінка» в «Рекуперація AHU-1»; графік без лінії ліміту, `chart_note` містить «котли {capacity} кВт» | TC (ТК-B1) |

**Разом міст: AC-B01…AC-B10 = 10 критеріїв (UT 8, UT+DEPLOY_TEST 1 (AC-B02), TC 1 (AC-B10)).**

Тести моста: `tests/test_wb_bridge.py::TestWbBridge` (AC-B01…AC-B09), `tests/stand/test_wb_tk.py` (ТК-B1 = AC-B10). Команда: `F3D_TEST_INSTALL=td_energy,td_bms,td_energy_resources,td_energy_resources_bms $T/run_tests.sh td_w3b /td_energy_resources_bms`.

### Рішення автора й питання моста

| ID | Рішення | Обґрунтування |
|---|---|---|
| A-B1 | Теплові точки створюються кодом (`_td_bind_extra`), а не XML | залежать від сигналів і установок BMS конкретної бази |
| A-B2 | `η` рекуперації — оцінка за тепловим балансом установки; сигнал витяжки зарезервований (`extract_c`) | датчика витяжки в BMS немає (GAP §4.4 п. 5) |
| Q-B1 | Додати датчик температури витяжки AHU-1 в BMS (для вимірюваної рекуперації) | рекомендація: так; поки оцінка |

## Журнал змін документа

| Дата | Версія | Зміна |
|---|---|---|
| 18.10.2026 | 0.1 | Перша редакція — Частина II `build/energy/W3_SPEC.md` (хвиля W3, воркер B) |
| 19.10.2026 | 0.2 | Виокремлено в самостійний SPEC, переклад українською; у збірці міст містить також `models/td_energy_res_interval.py` (гак `_td_backfill_extra`, R-B5) і `hooks.py` (`post_init_hook` → `_td_bind_extra`); `neutralize.sql` порожній; відхилення збірки W3, що стосуються ядра (AI:7 для `equipment/BOILER/gas_m3h`, n 1206…1215, сценарії S-21…S-23, `limit_kind`, `meter_ids` у V-04, серверна дія «Запустити зараз», V-11, `refresh_registry`), — у [../td_energy_resources/SPEC.md](../td_energy_resources/SPEC.md), «Журнал змін документа» |

