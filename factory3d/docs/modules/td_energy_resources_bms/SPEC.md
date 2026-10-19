# ЧАСТЬ II. `td_energy_resources_bms` — мост «Енергоресурси — Будівля»

Мост (`auto_install`: `td_energy_resources` + `td_bms`) добавляет вкладке «Тепло» данные BMS: точки и счётчики тепла, KPI температуры и рекуперации, список «Куди йде тепло», три детектора. Отсутствие `td_bms` — ядро работает без тепла (AC-64).

## B.0 Дерево файлов

```
odoo_addons/td_energy_resources_bms/              B
├── __manifest__.py                               (менеджер) version 19.0.1.0.0; depends [td_energy_resources, td_bms]; auto_install True
├── __init__.py                                   (менеджер)
├── hooks.py                                      B  post_init_hook → env["td.energy.point"]._td_bind_extra()
├── models/
│   ├── __init__.py                               (менеджер)
│   ├── td_energy_point.py                        B  M-B1 (_inherit: hvac_ref → связи, `_td_bind_extra`)
│   ├── td_energy_res_dashboard.py                B  M-B2 (_inherit: хуки тепла)
│   ├── td_energy_res_interval.py                 B  `_td_backfill_extra` (R-B5)
│   └── td_energy_opportunity_rule.py             B  `_td_detect_preheat_early`, `_td_detect_ahu_recuperation`, `_td_detect_dock_gates`
├── tools/heat.py                                 B  R-B2, R-B3 (η, индикаторы), R-B5 (генераторы)
├── data/opportunity_rules.xml                    B  3 правила (noupdate=1)
├── data/neutralize.sql                           B  (пусто, комментарий)
├── static/src/heat_note.xml                      B  UI-B1 (подпись «оцінка» у KPI «Рекуперація»; шаблон-наследник `ResKpis`)
└── tests/test_wb_bridge.py, tests/stand/test_wb_tk.py   B
```

## B.1 Манифест

`depends: ["td_energy_resources", "td_bms"]`, `auto_install: True`, `data`: `data/opportunity_rules.xml`; `assets`: `web.assets_backend`: `td_energy_resources_bms/static/src/**`; `post_init_hook`: `hooks.post_init_hook`.

## B.2 Модели

### M-B1 `td.energy.point` — расширение

Поле `hvac_unit_id` — Many2one `td.bms.hvac.unit` (ondelete=set null, «Установка BMS»); `hvac_ref` ядра остаётся как текстовый код (источник для `_td_bind_extra`). Метод `_td_bind_extra()` (R-B1): идемпотентно создаёт точки и счётчики тепла.

### M-B2 `td.energy.res.dashboard` — расширение

Реализация хуков ядра: `_td_heat_kpis(ctx)` (R-B2), `_td_heat_list(ctx)` (R-B2 п. 4), `_td_heat_chart_note(ctx)` → `capacity_kw` из `td.bms.heat.balance` (активная запись компании).

### UI-B1 Бейдж «оцінка» у KPI «Рекуперація»

Шаблон-наследник `td_energy_resources.ResKpis` (`static/src/heat_note.xml`, `t-inherit`): у карточки с `quality='estimated'` показывается точка и подпись «оцінка» (подсказка «Розрахунок за тепловим балансом установки»); ядро показывает только точку. Хуков и состояния JS нет.

## B.3 Данные

`data/opportunity_rules.xml` (`noupdate="1"`): правила `preheat_early` (`resource=gas`), `ahu_recuperation` (`resource=heat`), `dock_gates` (`resource=heat`) с `params`, `params_schema`, `actions`, `control_intent` (`heat_schedule_shift` для первого; у остальных пусто).
Точки и счётчики тепла создаёт `_td_bind_extra()` (не XML), потому что зависят от установленных сигналов BMS.

## B.4 Алгоритмы

### R-B1 Привязка BMS (FR-B1)

`_td_bind_extra()`:
1. `balance = env["td.bms.heat.balance"].search([("company_id", "=", env.company.id)], limit=1)`; нет — выход (`{}`).
2. Точки `heat`: `HEAT-BOILER` (`source`; сигнал `balance.boiler_heat_signal_id`), `HEAT-CHP` (`source`; `balance.chp_heat_signal_id`), потребители `RV-ALL` (`hvac_ref='RV-*'`), `AHU-1` (`hvac_unit_id` по `code='AHU-1'`), `OFFICE` (остаток), `DOCK` — только если найден сигнал открытия ворот: `env.get("td.yard.gate")` → первый шлагбаум/ворота с `state_signal_id` и `direction` отгрузки (`side='east'`), иначе точка не создаётся (Q-08).
3. Счётчики: `HM-BOILER`, `HM-CHP` (`flow_integrate`, один сигнал); `HM-RV` (`flow_integrate`, `flow_signal_ids` = `heat_signal_id` всех `td.bms.hvac.unit` с `code like 'RV-%'`); `HM-AHU1` (`heat_signal_id` установки `AHU-1`); `HM-DOCK` (`estimate`, `gate_loss`: `loss_kw_per_k=3,5`, `t_out_signal=ventilation/totals/outdoor_c`, `t_in` = `balance.t_in_set`); `HM-OFFICE` (`estimate`, `residual` `{"from": ["HEAT-BOILER","HEAT-CHP"]}`).
4. Идемпотентность по `(resource, code)`; изменённые вручную поля существующих записей не перезаписываются.
Ожидаемые количества на демо-БД: точек тепла 5 (без `DOCK`) или 6; счётчиков 5 или 6; `HM-RV` — 25 сигналов.

### R-B2 Тепловые KPI и список (FR-B2)

1. `_td_heat_kpis(ctx)`: 
   - `power.note` = «подача {boiler_supply_signal.last_value} °C · зворот {boiler_return_signal.last_value} °C»;
   - `indoor` = среднее `indoor_c` установок с `required_in_work` (RV + AHU-1), значение 1 знак, `unit="°C"`, note «уставка {t_in_set} °C · зовні {outdoor_c} °C» (`outdoor_c` — `ventilation/totals/outdoor_c`), `good` при `|indoor − t_in_set| ≤ 1`;
   - `recovery` — R-B3 (AHU-1), note «норма ≥ {recovery_norm_pct} %» + « · фільтр брудний», если `filter_dp_pa > filter_dp_limit_pa`; `bad` при `η < recovery_norm`; `quality='estimated'`.
2. Параметры (`ir.config_parameter`, мост): `td.energy_resources_bms.recovery_norm_pct = 70`, `td.energy_resources_bms.filter_dp_limit_pa = 250`.
3. `power.value` — `Σ` скорости `source`-точек (ядро), `today` — `Σ qty` источников.
4. `_td_heat_list(ctx)`: потребители `RV-ALL`, `AHU-1`, `DOCK`, `OFFICE` (значение — скорость сейчас, кВт; `OFFICE` = max(0, Σ источников − остальные)).
5. Пример (14:20, макет): источники 390 кВт; `RV-ALL 228`, `AHU-1 74`, `DOCK 46`, `OFFICE = 390 − 228 − 74 − 46 = 42`.

### R-B3 Рекуперация AHU-1 (оценка; D-36)

`T_after = T_supply − Q_heat × 1000 / (air_wh_m3k × airflow_m3h)`; `η = (T_after − T_out)/(T_in − T_out)`, где `T_supply = supply_c`, `Q_heat = heat_kw`, `airflow_m3h` — сигнал `airflow_m3h` установки, `air_wh_m3k` — `td.bms.heat.balance.air_wh_m3k` (0,34), `T_in = indoor_c` (замена температуры вытяжки; если появится сигнал `ventilation/units/AHU-1/extract_c` — используется он), `T_out = ventilation/totals/outdoor_c`. Защита: `T_in − T_out < 5 К`, `airflow < 10 %` от `airflow_nom` или `η ∉ [0, 1]` → `η = null`.
Пример: `airflow 32 000 м³/ч`, `Q_heat 74 кВт`, `T_supply 21,0`, `T_in 18,4`, `T_out 7,0` → `ΔT = 74 000/(0,34·32 000) = 6,80`; `T_after = 14,2`; `η = (14,2 − 7)/(18,4 − 7) = 0,632` (63 %).

### R-B4 Детекторы моста (FR-B3)

**`preheat_early`** (газ): параметры `t_ready` = `balance.t_in_set` (18 °C), `margin_min=30`, `lookback_days=7`, `min_saving_uah=1000`, `control_intent="heat_schedule_shift"`.
1. Для каждого рабочего дня окна: `ready_time` = первый момент до начала первой смены, когда среднее `indoor_c` по установкам `required_in_work` ≥ `t_ready` (сырые показания, шаг 5 мин); `margin = shift_start − ready_time` (мин, R-21).
2. `margin_med` = медиана по дням (≥ 3 дней); `margin_med − margin_min ≤ 0` → `[]`.
3. Газ разогрева: `preheat_rate` = средняя скорость `GM-BOILER` в окне `[shift_start − margin_med − 60 мин, ready_time]` (м³/ч); `extra_h = (margin_med − margin_min)/60`; `qty_window = preheat_rate × extra_h × (число рабочих дней окна)`; `est_qty_month = qty_window × K_month`; `est_saving = est_qty_month × price_gas`.
4. Текст: «Цех досягає {t_ready} °C о {ready_time}, а зміна о {shift_start}. Пізніший старт на {margin_med − margin_min} хв.»
Фикстура: `margin_med = 55`, `margin_min = 30`, `preheat_rate = 46`, 5 рабочих дней, `price_gas = 19,80`, `L=7` → `extra_h = 0,4167`; `qty_window = 46 × 0,4167 × 5 = 95,83 м³`; `est_qty_month = 95,83 × 4,33 = 415,0 м³`; `est_saving = 8 216 ₴`.

**`ahu_recuperation`** (тепло): параметры `eta_norm = recovery_norm_pct/100`, `dp_limit = filter_dp_limit_pa`, `lookback_days=7`, `min_saving_uah=500`; действие `ticket` (`node_code="AHU-1"`, «AHU-1: заміна фільтра [OPP-<id>]»).
1. За окно: `η_mean` — среднее R-B3 в рабочие часы (не `null`), `dp_mean` — среднее `filter_dp_pa`; находка при `η_mean < eta_norm` **или** `dp_mean > dp_limit`.
2. Потери: `loss_kw = (eta_norm − η_mean) × air_wh_m3k × airflow_m3h × (T_in − T_out)/1000` (кВт; `max(0, …)`), `run_hours = число рабочих часов окна`; `qty_window = loss_kw × run_hours` (кВт·ч тепла); `est_qty_month = qty_window × K_month`; `price_heat` — R-02 п. 3.
3. Если находка только из-за `dp` (η в норме) — `est_saving = 0` → отбрасывается по `min_saving`, остаётся предупреждение в `evidence` (не создаётся).
Фикстура: `η_mean = 0,632`, `eta_norm = 0,70`, `airflow 32 000`, `T_in − T_out = 11,4`, `run_hours = 80`, `price_heat = 2,0722` → `loss_kw = 0,068 × 0,34 × 32 000 × 11,4/1 000 = 8,43`; `qty_window = 674,7`; `est_qty_month = 2 921,6 кВт·ч`; `est_saving = 6 054 ₴`.

**`dock_gates`** (тепло; требует точку `DOCK`): параметры `long_open_min=10`, `min_events_day=3`, `open_norm_min_day=20`, `lookback_days=7`, `min_saving_uah=500`; действие `link` на `td_yard.action_td_yard_gate` («Показати у «Дворі»»), если `td_yard` установлен, иначе запасное.
1. По сырым показаниям `state_signal` точки: «открытия» — непрерывные интервалы `≥ 0,5`; `long` — длительностью `≥ long_open_min`; среднее число `long` в сутки `< min_events_day` → `[]`.
2. `open_min_day` = среднее суммарное время открытия в сутки; `excess_h = max(0, open_min_day − open_norm_min_day)/60` в сутки.
3. `loss_kw_per_k × ΔT_mean = loss_kw` (средняя разница температур окна); `qty_window = loss_kw × excess_h × L`; `est_qty_month = qty_window × K_month`; `price_heat` — R-02 п. 3.
Фикстура: `long = 4/сут`, `open_min_day = 52`, `norm 20`, `loss_kw_per_k = 3,5`, `ΔT = 11`, `L = 7`, `price_heat = 2,0722` → `excess_h = 0,5333`; `loss_kw = 38,5`; `qty_window = 38,5 × 0,5333 × 7 = 143,7`; `est_qty_month = 622,3 кВт·ч`; `est_saving = 1 290 ₴`.

### R-B5 Backfill тепла (хук `_td_backfill_extra`)

Генераторы (дополняют R-22): `HM-BOILER = heat_boiler` (R-22 п. 2, «газ»); `HM-CHP = 497 кВт`, когда КГУ работает; `HM-RV = 0,585 × heat_need`; `HM-AHU1 = 0,19 × heat_need`; оценки `HM-DOCK`, `HM-OFFICE` — R-04 (для `DOCK` без сырых показаний слоты `missing`, поэтому в backfill `HM-DOCK` генерируется напрямую: `open_frac = 0,05` в смену, 0 вне смен, `rate_kw = 3,5 × ΔT × open_frac`). Нужна температура: `t_out(d, h) = 7,0 + 8·cos(2π(doy − 200)/365) + 3·sin(π(h − 9)/12)` (демо-приближение; квалитет `estimated`).

## B.5 Acceptance Criteria — AC-B01…AC-B10

| AC | FR | Given / When / Then | Тип |
|---|---|---|---|
| AC-B01 | FR-B1 | Given `td_bms` с `td.bms.heat.balance` и 26 установками (RV + AHU-1); When установка моста; Then точки `HEAT-BOILER`, `HEAT-CHP`, `RV-ALL`, `AHU-1`, `OFFICE` (+ `DOCK` при наличии сигнала ворот) и счётчики `HM-*` созданы; `HM-RV.flow_signal_ids` = 25 сигналов; повторный `_td_bind_extra` — без дублей и без перезаписи ручных правок | UT |
| AC-B02 | FR-B1 | Given мост установлен до/после `td_bms` (порядок установки обоих модулей); Then результат одинаков (`auto_install` срабатывает при появлении второго) | UT + DEPLOY_TEST |
| AC-B03 | FR-B2 | Given фикстура (`boiler_heat 390`, `RV 228`, `AHU 74`, `DOCK 46`); Then `power.value=390`, note «подача 70 °C · зворот 52 °C»; список: `RV-ALL 228`, `AHU-1 74`, `DOCK 46`, `OFFICE 42` | UT |
| AC-B04 | FR-B2 | Given фикстура R-B3 (32 000 м³/ч, 74 кВт, 21,0/18,4/7,0); Then `recovery.value=63` (63,2), tone `bad`, `quality='estimated'`, note «норма ≥ 70 %» (+ « · фільтр брудний» при ΔP 280 Па); `T_in − T_out < 5` → `null`, `η ∉ [0,1]` → `null` | UT |
| AC-B05 | FR-B2 | Given `indoor_c` установок и `t_in_set=18`; Then `indoor.value` = среднее, note «уставка 18 °C · зовні 7 °C», tone `good` при отклонении ≤ 1 К; `_td_heat_chart_note` подставляет `{capacity}` из баланса | UT |
| AC-B06 | FR-B3 | Given фикстура `preheat_early` (`margin_med 55`, `margin_min 30`, 46 м³/ч, 5 дней, 19,80); Then `est_qty_month = 415,0 м³`, `est_saving = 8 216`; `margin_med ≤ margin_min` → `[]`; дней < 3 → `[]` | UT |
| AC-B07 | FR-B3 | Given фикстура `ahu_recuperation` (η 0,632; норма 0,70; 32 000; ΔT 11,4; 80 ч; 2,0722); Then `est_saving = 6 054`; находка только по ΔP → не создаётся | UT |
| AC-B08 | FR-B3 | Given фикстура `dock_gates` (4/сут; 52 мин; норма 20; 3,5 кВт/К; ΔT 11); Then `est_saving = 1 290`; `long < 3/сут` → `[]`; нет точки `DOCK` → правило пропущено без ошибки | UT |
| AC-B09 | FR-B1 | Given backfill тепла; Then `HM-BOILER ≈ gas·10,5·0,914` ± 3 %; `Σ ветвей` ≈ источников ± 5 %; идемпотентность и `purge` как AC-47 | UT |
| AC-B10 | FR-B2 | Given стенд, мост установлен; When открыть «Тепло»; Then 4 KPI, список «Куди йде тепло», подпись «оцінка» у «Рекуперація AHU-1»; график без линии лимита, `chart_note` содержит «котли {capacity} кВт» | TC (ТК-B1) |

**Итого мост: AC-B01…AC-B10 = 10 критериев (UT 8, UT+DEPLOY_TEST 1 (AC-B02), TC 1 (AC-B10)).**

Тесты моста: `tests/test_wb_bridge.py::TestWbBridge` (AC-B01…AC-B09), `tests/stand/test_wb_tk.py` (ТК-B1 = AC-B10). Команда: `F3D_TEST_INSTALL=td_energy,td_bms,td_energy_resources,td_energy_resources_bms $T/run_tests.sh td_w3b /td_energy_resources_bms`.

### Решения автора и вопрос моста

| ID | Решение | Обоснование |
|---|---|---|
| A-B1 | Тепловые точки создаются кодом (`_td_bind_extra`), а не XML | зависят от сигналов и установок BMS конкретной базы |
| A-B2 | `η` рекуперации — оценка по тепловому балансу установки; сигнал вытяжки зарезервирован (`extract_c`) | датчика вытяжки в BMS нет (GAP §4.4 п. 5) |
| Q-B1 | Добавить датчик температуры вытяжки AHU-1 в BMS (для измеряемой рекуперации) | рекомендация: да; пока оценка |
