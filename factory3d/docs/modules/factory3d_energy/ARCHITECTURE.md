# factory3d_energy — технічне рішення

Версія 0.1 · 14.10.2026 · автор: агент-архітектор модуля (хвиля 2) · статус: **чернетка на погодження**.
Каркас: `docs/ARCHITECTURE.md` (далі «каркас»: §3 `factory3d_energy ← factory3d_telemetry, mrp_account`, §5 конвенції,
§6.4–§6.5 телеметрія й колектор, §6.6 P-05/P-07, §6.7 контракт переглядача, §6.8 заявки ТО, D-04, D-06, D-11, §9 п. 1, 6,
8). Специфікація: `docs/modules/factory3d_energy/SPEC.md`. Спирається на: `factory3d_base` CB-01, CB-03, CB-07…CB-10;
`factory3d_telemetry` CT-01…CT-12 (прийнята SPEC 2 219 рядків: моделі, `_f3d_ingest`, локальні джерела R-26, схеми
`address` Додаток A); `factory3d_iot_sim` §8.4.1 (unit id), §8.7 (P-05 PM5560), §8.9.1–§8.9.5 (Huawei, LUNA2000, ATyS p,
TEDOM), Додаток A (№ 1–80, 190–196, 366–428), S-01 `shift`, S-03 `blackout`, S-12 `pv_cloudy`, API-16; `factory3d_viewer`
M-01 (хук провайдера), M-03 (шина), R-01, R-07, R-14, Додаток A.12/A.13; `factory3d_machine_connect` CM-02…CM-04
(інтервали роботи завдань); `td_genset` / міст `factory3d_genset` (запити CE-01…CE-03, R-05, R-06, варіант AMF «A»).
Рішення автора — **A-xx** (§7), відкриті питання — **Q-xx** (§5.1), контракти модуля — **CE-xx** (§2.1).

## Загальна інформація

| Етап ToDo | Що здається | Люд./год (оцінка автора; `docs/оцінки` в репозиторії ще немає) |
|---|---|---|
| ТР | цей документ + SPEC.md | 28 |
| Архітектура | погодження A-xx/Q-xx з менеджером, енергетиком і бухгалтером; узгодження CE-xx з авторами td_genset, viewer, iot_sim | 10 |
| Розробка | Odoo-модуль `odoo_addons/factory3d_energy` (W0–W5: мережа, лічильники й прив'язка 68 джерел/297 сигналів, 15-хв профіль, баланс, розподіл на завдання/МО, собівартість, АВР і блекаут, провайдери переглядача) + генератор даних `tools/gen_energy_data.py`; власного плагіна колектора немає | 124 |
| Тестування | юніт-тести формул (лічильник, інтервали, тариф, баланс, розподіл, собівартість), ТК на емуляторі (`shift`, `blackout`, `pv_cloudy`, експорт СЕС), безпека, продуктивність, DEPLOY_TEST | 58 |
| Інструкція | §4 цього документа + README модуля + CHANGELOG | 8 |
| **Разом** | | **228** |

Факти тестового сервера timur-o19demo, база `odoo` (перевірено 14.10.2026, лише читання): Odoo 19.0+e; встановлені
`mrp_account`, `mrp_account_enterprise`, `stock_account`, `account_accountant`, `analytic`, `hr_hourly_cost`,
`mrp_workorder_hr_account`, `spreadsheet_dashboard`, `spreadsheet_dashboard_mrp_account`, `web_hierarchy`, `web_gantt`;
`board` не встановлений. Моделі **`stock.valuation.layer` в Odoo 19 немає** (вартість — `stock.move.value`,
`product.value`). `mrp.production.extra_cost` («Extra Unit Cost», Float, на одиницю) є; аналітики на МО немає — є
`mrp.workcenter.analytic_distribution`, `costs_hour`, `expense_account_id`, `mrp.workorder.wc_analytic_account_line_ids`,
`mrp.workcenter.productivity.account_move_line_id`/`total_cost`. Усі 11 категорій товарів — `property_cost_method='standard'`,
`property_valuation='periodic'`. 35 робочих центрів, `costs_hour = 0`, календар «Зміна 1 (07:00–15:30)», `tz=Europe/Kyiv`.
Журнал часу: 184 рядки `mrp.workcenter.productivity`; для `WH/MO/00231` — SAW-1 01:36–02:54 UTC (78 хв), EDGE-1 02:48–03:51
(63), CNC-1 03:45–04:59 (74), SORT-1 04:52–05:21 (29), ASMLINE-1 з 05:55 відкритий. Обладнання енергетики (26 кодів
`RM6-1`…`CHP`, категорія «Електропостачання»), споживачі `GANTRY-1`, `COMPRESSOR`, `DUST-1`, `BOILER`, `CHARGING`, `LP-1…3`,
`AHU-1`, `EF-*` є; `OFFICE` і `RV-ALL` як обладнання немає. Рівень 0: 84 сигнали `energy/*` + 3 `infra/*`
(`energy/consumers/SAW-1/kwh_shift` = 195,17, `infra/totals/pv_now` = 429,6). Валюта компанії — UAH;
`uom.product_uom_kwh` існує; команди ТО: «Служба головного механіка» (id 2), «Internal Maintenance».

## 1. Опис процесу і функціональні вимоги

### 1.1 Контекст: що є в макеті

| Джерело | Що саме | Як використовується |
|---|---|---|
| `plant/energy.py` (458 рядків) | `SWB_CELLS` — 11 шаф ГРЩ (`PFC-1, Q1, QF-3, QF-2, QF-C1, QS, QF-1, QF-4, QF-C2, Q2, PFC-2`) з типами `pfc/incomer/feeder/cable/coupler`; `SECTION` (QS ділить секції 1/2); `BUSWAYS` BW-1…4 (630 А, траси), `CABLE_FEEDERS` C1 (630 А), C2 (400 А); `taps()` — 36 відгалужень; `consumers()` — 49 споживачів з `p_inst`, `p_now`, `cos_phi`, `source` (`passport/estimate/mixed`), `status`; `ESTIMATE_KW`, `PROFILE` (коефіцієнт завантаження `kf` і cos φ за типом), `IDLE_K`, `STOP_K`; `lines()` (P, Q, cos φ, I, `load`); `energy_data()` — секції, компенсація до `COS_TARGET=0.97`, `PFC_KVAR=350` (ступені 50 + 3 × 100), трансформатори `TRAFO_KVA=1000`, `temp_c = 38 + 60·S/Sн`; `TARIFF=8.4` грн/кВт·год (умовний, **одна зона**); `day_profile()` (дві зміни, пік 15 хв); `events()`; `ENERGY_ROLES` | ієрархія вузлів (SPEC Додаток B), номінали й оцінки для запасного розрахунку R-08, формули секцій/компенсації R-06, тариф демо R-05 |
| `plant/odoo_demo.py:build_energy` (рядки 680–705) | `kwh_shift` верстата = `p_inst·(kf·prod + idle·(shift − prod))/60`; **кВт·год МО = Σ `p_inst × kf × duration/60`** по завданнях `done|progress`, вартість = `round(kWh × 8.4)` | розрахунок «оцінка» (R-08 п. 4) відтворює ці числа: `WH/MO/00231` = 17,160 + 46,069 + 13,567 + 4,350 + 5,067 = **86,2 кВт·год, 724 грн** |
| `plant/infra.py` (рядки 226–391) | `INFRA_ROLES`; `CRITICAL` (9 споживачів + `BW-1-LINE`); `infra_data()`: СЕС `pv_now = min(kWp·0,52; 8·115) = 468`, КГУ 800 × 0,5 = 400, баланс `surplus = pv + chp − load` → BESS ≤ 200, решта експорт; картки `PV-ROOF`, `PV-INV`, `CHP`, `GENSET`, `ATS-1`, `BESS`, `WATER`…; `totals` (18 ключів) | картки й тотали провайдера `infra` (R-17), баланс R-06, критичні R-06 п. 9 (347,8 ≈ 348 кВт) |
| `plant/site2.py` (рядки 127–247) | об'єкти `GENSET`, `ATS-1`, `BESS`, `PV-ROOF`, `PV-INV` (один об'єкт на 8 інверторів), `CHP`, `CHP-GAS`, `CHP-HEAT`; вид «Когенерація» | коди вузлів генерації (Додаток B) |
| `plant/equipment_specs.json` | ролі `substation`, `transformer`, `main_switchboard`, `acb`, `busbar_main`, `busbar_dist`, `tapoff`, `power_meter` (PM5560), `pfc`, `pv_module` (`wp=580`), `pv_inverter` (`kw_ac=115`), `bess` (`kwh=193.5`, `power_kw=100`), `chp` (`power_kw=800`, `heat_kw=856`, `heat_kw_50=497`, `gas_m3h=199/154/109`, `eta_el=0.425`, `eta_th=0.455`, `min_load=0.5`), `ats` | номінали через `f3d_get_num(key)` (CB-08) у картках R-17 |
| `dist/odoo_demo.json` | `energy` (`meta`, `totals` 16 ключів, `transformers`, `cells` 11, `lines` 6, `consumers` 49, `profile`, `typical`, `events` 6); `infra` (`cards` 30, `totals` 18); `productions[].energy_kwh/energy_cost` (32 МО) | структура провайдерів (viewer A.12/A.13), очікувані числа AC |
| `viewer/index.html` | вкладка «Енергія» `renderEnergy()` (рядки 2028–2058: KPI, трансформатори, профіль доби `chartHtml`, лінії, «Власна генерація й резерв» `backupSummary()`, найбільші споживачі, журнал подій); режим «Споживання електроенергії» (легенда 1507–1510); картки `energyHtml()` (2093–2150: споживач, лінія `lineBody`, трансформатор, шафа, `SWB-1`/`EMS-1`, `RM6-1`); `infraHtml()` (2608); картка МО «Електроенергія … (виконані операції)» (1587); `energyTick()` — «дихання» лише без `meta.live` | ключі, які провайдери мають віддати; що видно користувачу |
| README «Електропостачання», «Резервне живлення, сонячна станція й когенерація» | однолінійна схема (ввід 10 кВ → RM6 → T1/T2 → ГРЩ 2 секції + QS), N-1, PM5560 клас 0,2S; генератор і АВР для критичних, LUNA2000 для зрізання піків і пуску ДГУ, СЕС 900 кВт пік, КГУ 800 кВт, баланс 10:30 | інструкції §4, сценарії ТК |

### 1.2 Ролі й сценарії використання

| Роль (групи) | Що робить | Де в меню |
|---|---|---|
| Головний енергетик (`group_energy_manager` ⊃ `factory3d_base.group_f3d_manager`) | веде схему мережі, прив'язку лічильників, тарифи й договірну потужність, пули спільних споживачів, пороги; дивиться баланс, події, відключення; запускає перерахунок | Завод 3D → Енергетика (усе) |
| Черговий електрик (`group_energy_user`) | дивиться схему, живі значення, події, журнал відключень, заявки ТО з енергетики | Енергетика → Огляд / Схема / Лічильники / Події / Відключення; Обслуговування → Заявки |
| Майстер / технолог (`mrp.group_mrp_user` ⇒ `group_energy_user`) | бачить кВт·год на завданні й МО (без гривень), енергію простою РЦ | форма МО → вкладка «Енергія», форма завдання, робочий центр |
| Бухгалтер / керівник виробництва (`group_energy_cost`, неявно з `account.group_account_readonly`, `account.group_account_invoice`, `mrp.group_mrp_manager`) | бачить вартість енергії на МО/завданні, тарифи, вартість за добу, нерозподілене й накладні | форма МО, «Розподіл на виробництво», дашборд |
| Адміністратор (`factory3d_base.group_f3d_admin`) | стоп-крани, повтор прив'язки даних, `neutralize` | Налаштування → Завод 3D → Енергетика |
| Переглядач/кіоск (`group_f3d_user`) | вкладка «Енергія», картки ГРЩ, ліній, трансформаторів, СЕС/КГУ/BESS/АВР, кВт·год у картці МО (без грн у кіоску) | 3D-переглядач |
| Міст `factory3d_genset` (код) | читає `infra/ats/*`, `energy/consumers/*/p_now`, `infra.totals`, журнал відключень | CE-01…CE-04 |

### 1.3 Функціональні вимоги

| ID | Вимога (перевірювана) |
|---|---|
| FR-01 | Модель `f3d.energy.node` зберігає ієрархію електропостачання (123 вузли з макета: ввід 10 кВ, RM6-1, T1/T2, ГРЩ SWB-1 з 11 шафами, секції 1/2, 6 ліній, 36 відгалужень, 49 споживачів, 14 вузлів генерації й резерву) з кодом, видом, батьком, номіналами, `p_inst/kf/cos φ`, зв'язками з `maintenance.equipment` і `mrp.workcenter`, ознакою критичного споживача й роллю в розподілі. |
| FR-02 | Модель `f3d.energy.meter` описує 67 лічильників (57 PM5560, 8 SUN2000, LUNA2000, TEDOM) на вузлах із посиланнями на сигнали потужності й накопичувальної енергії (імпорт/експорт) і станом даних. |
| FR-03 | Модуль створює 68 джерел Modbus TCP (по одному на пристрій) і 297 сигналів зони енергетики (220 з пристроїв із PDU-адресами за документами вендорів, 75 обчислених на локальному джерелі `EN-DERIVED`, 2 температури трансформаторів — прив'язує telemetry), ідемпотентно оновлюючи 87 мігрованих і 63 каталожні сигнали. |
| FR-04 | 15-хвилинний профіль `f3d.energy.interval` на кожен лічильник: кВт·год з різниці накопичувального лічильника, середня кВт, зона тарифу, ціна, вартість, якість (`measured/interpolated/reset/missing`); пропуски й скидання лічильника не гублять енергію. |
| FR-05 | Тарифи `f3d.energy.tariff` з періодом дії, зонами доби за днями тижня, ціною грн/кВт·год, ціною експорту й договірною потужністю; демо — один тариф 8,4 грн/кВт·год (макет). |
| FR-06 | Живі показники: споживання, повна потужність, cos φ до/після компенсації, увімкнена компенсація PFC, навантаження й температура трансформаторів, СЕС, КГУ, накопичувач, імпорт/експорт мережі, критичні споживачі — за формулами макета з живих сигналів. |
| FR-07 | Погодинна перевірка балансу вводів і фідерів (сума дочірніх лічильників ≈ лічильник вузла ± допуск 3 % і 2 кВт·год) з записом `f3d.energy.balance` і обчисленим сигналом `imbalance_pct`. |
| FR-08 | кВт·год робочого завдання = різниця лічильника його РЦ за інтервалами роботи й налагодження (machine_connect CM-03; без нього — журнал часу `mrp.workcenter.productivity`; без даних лічильника — оцінка макета `p_inst × kf × хв/60`), з поділом одночасних завдань і обліком енергії простою РЦ. |
| FR-09 | Енергія спільних споживачів (пули: стиснене повітря, аспірація, подача плит, освітлення, вентиляція) розподіляється на завдання кожні 15 хв за драйвером пулу (кВт·год прямих або машинний час); нерозподілене й накладні (котельня, зарядна, офіс, витяжки) — окремими рядками. |
| FR-10 | На `mrp.production` і `mrp.workorder` — кВт·год прямі/спільні/разом, вартість, якість, стан; при закритті МО розподіл фіксується, енергія входить у `extra_cost` (для FIFO/AVCO, стандарт Odoo 19 `_cal_price`), додаються аналітичні рядки за аналітикою РЦ. |
| FR-11 | Обчислені сигнали `energy/consumers/<код>/kwh_shift` (кВт·год з початку зміни за лічильником) для 49 споживачів. |
| FR-12 | Події з порогами (перевищення договірної потужності, низький cos φ, асиметрія струмів, перегрів і перевантаження трансформатора, перевантаження фідера, аварійне вимкнення автомата, аварія інвертора/накопичувача/КГУ, небаланс обліку, FAIL START генератора) створюють заявки ТО за §6.8 каркаса через telemetry CT-05 і сповіщають енергетиків. |
| FR-13 | Журнал подій енергетики `f3d.energy.event` (пороги, піки, баланс, лічильники, АВР, відключення, ступені компенсації) — джерело `energy.events` переглядача й дашборда. |
| FR-14 | Відключення мережі визначаються за ATyS p (Annexe III) або за вводами; журнал `f3d.energy.outage` (початок/кінець, тривалість, переключення, скинуте навантаження, FAIL START); обидва варіанти логіки AMF підтримуються без зміни коду. |
| FR-15 | Для моста генератора модуль публікує CE-01…CE-04: сигнали `infra/ats/*` за Annexe III, `infra.totals` з балансом в острові (`grid_kw=0`, `export_kw=0`, `shed_kw`, `bess_mode`), `critical_kw`, і не пише картку `GENSET` та ключі `genset_*`, `island`, `grid_ok`. |
| FR-16 | Провайдер переглядача `f3d.viewer.provider.energy` (100) будує розділ `energy` за viewer A.12 з живих даних, доповнює `workcenters[*].energy` і перекриває `productions[].energy_kwh/energy_cost` фактичними значеннями. |
| FR-17 | Провайдер `f3d.viewer.provider.infra` (150) пише в `infra.cards` лише `PV-ROOF`, `PV-INV`, `CHP`, `ATS-1`, `BESS` і енергетичні ключі `infra.totals`; інші картки (статика чи інші модулі) не чіпає. |
| FR-18 | Живі оновлення: зміни сигналів енергетики й перерахунки → шина `f3d_viewer`; дельта провайдерів зливається глибоко з чужими частинами розділу `infra`. |
| FR-19 | Представлення: схема мережі (ієрархія), вузли, лічильники, профіль (графік/зведена), баланс, розподіл на виробництво (зведена), відключення, події, тарифи, пули, вкладка «Енергія» на МО й завданні, статбокс на РЦ і обладнанні. |
| FR-20 | Дашборд «Огляд»: kanban ліній і трансформаторів з живими значеннями, графік профілю доби, KPI доби (кВт·год, пік, вартість, власна генерація), стандартні graph/pivot. |
| FR-21 | Меню «Завод 3D → Енергетика» (`sequence=50`) і «Налаштування → Енергетика». |
| FR-22 | Права: перегляд кВт·год — `group_energy_user`; вартість — `group_energy_cost` (поля `groups=`, payload без грн для кіоску й без групи); редагування — `group_energy_manager`; стоп-крани — `group_f3d_admin`. |
| FR-23 | Стоп-крани `factory3d.energy.read_enabled`, `factory3d.energy.write_enabled` (запис уставок у пристрої заборонено у v1 обмеженням), `factory3d.energy.costing_enabled`; `neutralize.sql`. |
| FR-24 | `post_init_hook` будує мережу, лічильники, джерела, сигнали, тариф і пули з data-файлів, згенерованих з макета; повторний запуск нічого не дублює; `uninstall_hook` не видаляє бізнес-даних. |
| FR-25 | Ротація: інтервали й баланс — 400 діб, події — 90 діб; розподіл на МО не ротується. |
| FR-26 | Майстер перерахунку (енергетик): перебудувати інтервали за період і розподіл за дні, крім зафіксованих МО. |
| FR-27 | Стан лічильника (`ok/stale/gap/reset/no_data`) і правила пропусків: лінійна інтерполяція накопичувального лічильника, позначка якості, подія при пропуску > 60 хв. |
| FR-28 | Профіль доби (кВт·год по годинах сьогодні), типовий день (середнє за 20 робочих днів), пік 15-хв потужності доби з часом. |
| FR-29 | Службовий метод `f3d.energy.meter._f3d_kwh(meter, date_from, date_to) -> (kwh, quality)` для інших модулів (CE-06). |

### 1.4 Межі: що не входить

- Власні плагіни колектора — немає: усі пристрої енергетики читає плагін telemetry `modbus_tcp` (каркас §6.5).
- Сирі ряди — лише `f3d.reading` telemetry (D-04, D-11); власного журналу показань модуль не має: `f3d.energy.interval` — розрахунковий профіль (кВт·год і грн за 15 хв), як дані комерційного обліку (A-01).
- Запис у пристрої (уставки PFC, режим LUNA2000, навантаження КГУ, команди ATyS p, скидання енергії PM5560) — **заборонено у v1** (A-15).
- Генератор (показання, тривоги, картка `GENSET`, `genset_*`, `island`, `grid_ok`) — `td_genset` і міст `factory3d_genset`; модуль лише публікує CE-01…CE-04.
- Вода (`infra/water/*`) — telemetry; освітлення й вентиляція як системи — bms (модуль бере лише лічильники щитів LP-* і вентиляції як споживачів).
- Бухгалтерські проводки за рахунками постачальника електроенергії, ПДВ, нарахування за реактивну енергію ОСР — стандартний облік; модуль не створює `account.move` (лише `extra_cost` і аналітичні рядки).
- Прогноз споживання, оптимізація графіка BESS, керування зрізанням піків — не у v1.
- Spreadsheet-дашборд — після UAT (Q-16, A-12).

## 2. Технічна реалізація

### 2.1 Місце в системі

`depends`: `factory3d_telemetry` (CT-01 моделі, CT-05 заявки, CT-10 `_f3d_ingest`, CT-12 локальні джерела; через неї —
`factory3d_base`, `maintenance`, `mail`), `mrp_account` (`extra_cost`, `_cal_price`, аналітика РЦ), `mrp_workorder`
(журнал часу завдань), `analytic`, `web_hierarchy` (вид «Схема мережі»). Необов'язкові: `factory3d_viewer` (провайдери —
моделі `f3d.viewer.provider.*` без `_inherit`, A-04; шина — `if 'f3d.viewer.event' in env`), `factory3d_machine_connect`
(CM-03 — `if 'f3d.machine' in env`, A-05), `factory3d_genset` (параметр `factory3d.genset.amf_master` читається як рядок).
Циклів немає: `td_genset ← factory3d_genset ← factory3d_energy ← factory3d_telemetry ← factory3d_base`.

Контракти, які **задає** модуль (посилатися як `factory3d_energy CE-xx`; CE-01…CE-03 — нумерація запитів td_genset):

| ID | Контракт | Споживачі |
|---|---|---|
| CE-01 | Провайдер `infra` (150) **не** пише `infra.cards.GENSET`, `infra.genset`, `infra.totals.genset_*`, `island`, `grid_ok`, `genset_kva` | `factory3d_genset` (155) |
| CE-02 | Сигнали АВР Socomec ATyS p за Annexe III (PDU 20482…20487): `infra/ats/position` (`kind='state'`, `last_value` = код 0 невідомо / 1 положення 0 / 2 положення I «мережа» / 3 положення II «генератор», `last_text` = `unknown/pos_0/pos_I/pos_II`), `infra/ats/mode` (`manual/locked/auto/remote/inhibit`), `infra/ats/gen_start` (`off/on`, `last_value` 0/1), `infra/ats/src1_state`, `src2_state` (`under/present/available` = 0/1/2), обчислені `infra/ats/src1_ok`, `src2_ok` (1 = `available`, інакше 0; оновлюються з тим самим `ts`, що й стан), `infra/ats/fail_start` (0/1); період 5 с | міст (R-05 td_genset), viewer, тести |
| CE-03 | `infra.totals` (без ключів CE-01): `pv_now`, `pv_today`, `pv_kwp`, `chp_kw`, `chp_rated`, `chp_heat`, `chp_load`, `bess_kw` (+ заряд / − розряд), `bess_soc` (частка), `bess_kwh`, `load_kw`, `grid_kw`, `export_kw`, `critical_kw`, `n_modules`, `shed_kw`, `bess_mode` (`charge/discharge/idle`); в острові `grid_kw=0`, `export_kw=0`, `shed_kw = load_before − load_kw` | міст, viewer `backupSummary()` |
| CE-04 | Критичні споживачі: `f3d.energy.node.is_critical` (LP-1…3, DUST-1, COMPRESSOR, BOILER, OFFICE, EF-ELEC, EF-CHG і лінія BW-1 — `plant/infra.py:CRITICAL`); `infra.totals.critical_kw` = Σ `p_now` цих вузлів (макет 347,8 → 348); сигнали `energy/consumers/<код>/p_now` і `energy/lines/BW-1/p_now` існують для всіх 10 | міст (параметр `critical_codes` дублює список — Q-13 td_genset/R-04) |
| CE-05 | Моделі `f3d.energy.node`, `meter`, `interval`, `tariff`, `pool`, `alloc`, `balance`, `event`, `outage` з іменами полів SPEC §2 — лише читання для інших модулів | viewer, звіти, міст, bms (за потреби) |
| CE-06 | Метод `env['f3d.energy.meter']._f3d_kwh(meter, date_from, date_to) -> tuple[float, str]` (кВт·год і найгірша якість) і `env['f3d.energy.node']._f3d_kwh_by_code(code, date_from, date_to)` | machine_connect (питома енергія CM-04 — за потреби), bms |
| CE-07 | Поля `mrp.production.f3d_energy_kwh`, `f3d_energy_direct_kwh`, `f3d_energy_shared_kwh`, `f3d_energy_cost`, `f3d_energy_state`, `f3d_energy_locked`; `mrp.workorder.f3d_energy_kwh`, `f3d_energy_cost`; `mrp.workcenter.f3d_energy_node_id`, `f3d_kwh_today` | viewer, звіти |
| CE-08 | Провайдери `f3d.viewer.provider.energy` (100, розділ `energy` за A.12, `workcenters[*].energy`, `productions[].energy_kwh/energy_cost/energy_quality`) і `f3d.viewer.provider.infra` (150); події шини `_notify('f3d.energy', codes, 'signal')` і `_notify('mrp.production', names, 'doc')` | viewer |
| CE-09 | Коди обчислених сигналів (`energy/totals/*`, `energy/*/imbalance_pct`, `i_unbal_pct`, `kwh_shift`, `infra/totals/pv_now|grid_kw|export_kw`, `infra/ats/src1_ok|src2_ok|fail_start`) на джерелі `EN-DERIVED` типу `f3d_energy` (локальний, CT-12) | telemetry, міст, bms |

Що **бере**: CB-01 (`search_f3d` для обладнання/РЦ), CB-07/CB-08 (`f3d_get_num('wp'|'kw_ac'|'kwh'|'power_kw'|
'heat_kw'|'heat_kw_50'|'gas_m3h'|'gas_m3h_50'|'eta_el'|'eta_th')`), CB-09 (меню 50), CB-10 (групи, `environment`); telemetry
CT-01 (`f3d.collector` `COL-MAIN` — xml-id `factory3d_telemetry.collector_main`, `f3d.source`, `f3d.signal`, `f3d.reading`),
CT-03 (схема `modbus_tcp`: `fc`, `addr` PDU, `type` `f32/i64/u32/i32/u16`, `scale`, `map`, `doc`), CT-05 (пороги →
заявки), CT-10/M-03 (`_f3d_ingest` — перевизначається, як machine_connect M-18), CT-12 (`_f3d_local_types`); iot_sim §8.7,
§8.9, Додаток A; viewer M-01, M-03, R-01, R-14, A.12, A.13; machine_connect CM-03 (`_f3d_wo_intervals`,
`_f3d_wc_intervals`), CM-02 (стан верстата `workcenters/<код>/machine_state` — для `status` споживача); td_genset R-05/R-06.

### 2.2 Архітектурна схема

```
  мережа цеху / f3d_sim                                docker compose (/opt/timur-o19)
┌───────────────────────────┐ Modbus TCP 502  ┌──────── services/collector (telemetry) ────────┐
│ PM5560 u1–8 (Q1,Q2,QF-*)  │◄──── poll ──────│ plugins/modbus_tcp: f32, i64 (Wh), u32, i32,    │
│ PM5560 u11–59 (49 спож.)  │                 │ u16+map; групування регістрів у блоки            │
│ SUN2000 u61–68, LUNA u69  │                 └───────────────┬─────────────────────────────────┘
│ ATyS p u71, TEDOM u72     │                                 │ POST /f3d/telemetry/push (≤ 1 000 показань / 5 с)
│ ADAM-6015 u96 (T1/T2 °C)  │──── (telemetry) ────────────────┤
└───────────────────────────┘                                 ▼
┌──────────────────────────────── Odoo 19: factory3d_telemetry ─────────────────────────────────────────────────┐
│ f3d.source (68 MB-U*) ─ f3d.signal (297 зони energy) ─ f3d.reading (60–300 с) ─ пороги R-04 ─► maintenance.request│
│                           ▲ _f3d_ingest(...) ── перевизначення M-15 energy: ATS-похідні, події, відключення   │
└───────────────────────────┼────────────────────────────────────────────────────────────────────────────────────┘
┌───────────────────────────┴──────────── factory3d_energy ──────────────────────────────────────────────────────┐
│ f3d.energy.node (123, ієрархія) ── f3d.energy.meter (67) ──► сигнали p_now / kwh_total / kwh_export             │
│   крон 5 хв: лічильник Ec(t) (R-03) ─► f3d.energy.interval (15 хв, тариф R-05) ─► kwh_shift, load15, grid15     │
│   крон 1 хв: тотали R-06 ─► EN-DERIVED: energy/totals/*, infra/totals/*, i_unbal_pct (CT-10 _f3d_ingest)          │
│   крон год: баланс R-07 ─► f3d.energy.balance, imbalance_pct                                                    │
│   крон 15 хв: розподіл R-08/R-09 ◄── machine_connect CM-03 _f3d_wo_intervals | mrp.workcenter.productivity      │
│        ─► f3d.energy.alloc (завдання × пул × доба) ─► mrp.workorder / mrp.production f3d_energy_*                │
│   mrp.production._cal_price ─► R-10: фіксація, extra_cost (FIFO/AVCO), аналітика (_perform_analytic_distribution)│
│   АВР/блекаут R-14 ─► f3d.energy.outage, f3d.energy.event, infra/ats/src*_ok, fail_start                        │
│   f3d.viewer.provider.energy (100) / .infra (150) ─► payload energy, infra (CE-01, CE-03), шина _notify           │
└──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
          ▲ читає сигнали infra/ats/*, energy/consumers/*/p_now; пише свої ключі після 150
   factory3d_genset (155) ── td_genset (SmartGen HGM6120N, варіант A: HGM веде AMF, ATyS p у Remote control)
```

Потоки: (1) колектор опитує пристрої за адресами з Odoo (API-01 telemetry) і шле показання; (2) перевизначений
`_f3d_ingest` після `super()` ловить зміни стану сигналів енергетики й АВР (події, відключення, похідні АВР); (3) крони
будують профіль, тотали, баланс, розподіл; (4) закриття МО фіксує енергію й вартість; (5) провайдери віддають payload,
шина повідомляє переглядач.

### 2.3 Нові й розширені об'єкти

| Об'єкт | Призначення | Пише | Читає |
|---|---|---|---|
| `f3d.energy.node` (M-01) | вузол мережі: вид, батько (`parent_path`), шафа ГРЩ, секція, номінали, `p_inst/kf/idle_k/cos φ`, `is_critical`, роль у розподілі, пул, обладнання, РЦ | хук, енергетик | усі розрахунки, провайдери, міст |
| `f3d.energy.meter` (M-02) | лічильник на вузлі: модель, джерело, сигнали `p_signal_id`, `e_import_signal_id`, `e_export_signal_id`, `counter_offset`, стан даних, останній інтервал | хук, енергетик, крони | R-03, R-04 |
| `f3d.energy.interval` (M-03) | 15-хв профіль лічильника: `e_start`, `e_end`, `kwh`, `kw_avg`, `zone`, `price`, `cost`, `quality` | крон R-04 | баланс, профіль, дашборд, запасний `Ec(t)` |
| `f3d.energy.tariff`, `.tariff.zone` (M-04, M-05) | договір: період дії, зони (вікна годин за днями тижня), ціни, ціна експорту, договірна потужність | енергетик, бухгалтер | R-05, пороги `grid15_kw` |
| `f3d.energy.pool` (M-06) | пул спільних споживачів: вузли-члени, драйвер (`kwh/time`), обслуговувані РЦ | хук, енергетик | R-09 |
| `f3d.energy.alloc` (M-07) | розподіл енергії за добу: завдання/МО/РЦ × вид (`direct/shared/idle/unallocated/overhead`) × пул, кВт·год, хв, вартість, якість, `locked`, аналітичні рядки | крон R-08/R-09, `_cal_price` | МО, завдання, дашборд |
| `f3d.energy.balance` (M-08) | погодинна звірка вузла: виміряно, очікувано, різниця, %, стан | крон R-07 | енергетик, сигнал `imbalance_pct` |
| `f3d.energy.event` (M-09) | журнал подій енергетики | хук `_f3d_ingest`, крони | `energy.events`, дашборд |
| `f3d.energy.outage` (M-10) | журнал відключень мережі | R-14 | картка ATS-1, міст, звіт |
| `f3d.energy.recompute.wizard` (M-19, Transient) | перерахунок інтервалів/розподілу | енергетик | — |
| `mrp.workorder` (+M-11), `mrp.production` (+M-12), `mrp.workcenter` (+M-13), `maintenance.equipment` (+M-14) | поля енергії, `_cal_price`, `_get_backorder_mo_vals`, статбокси | R-08…R-10 | форми, провайдер |
| `f3d.signal` (+M-15) | перевизначення `_f3d_ingest` (після `super()`), обмеження «запис енергетики заборонено» | — | — |
| `f3d.source` (+M-16) | `type` += `f3d_energy` (локальний, CT-12) | — | — |
| `maintenance.request` (+M-17) | підписка енергетиків на заявки з сигналів `module='energy'` | — | — |
| `res.config.settings` (+M-18) | стоп-крани й параметри | адміністратор | — |
| `f3d.viewer.provider.energy` / `.infra` (M-20) | AbstractModel без `_inherit` (A-04) | — | переглядач |

### 2.4 Інтеграції

| P-xx / канал | Пристрої (коди) | Протокол, адреса на стенді | Напрямок | Частота (`period_s` / `store_period_s`) | При недоступності |
|---|---|---|---|---|---|
| P-05 | PM5560 вводів Q1/Q2 (u1, u2), фідерів QF-1…4, QF-C1/C2 (u3–u8), 49 споживачів (u11–u59) | Modbus TCP `iot-sim:502`, джерело = пристрій (`MB-U01-PM-Q1`…); регістри iot_sim §8.7 (1-based) → PDU = N − 1: P 3060 → `addr 3059 f32`; енергія 3204–3207 → `addr 3203 i64 ×0,001` (Вт·год → кВт·год); експорт 3208 → `3207`; I 3010 → `3009`; фази 3000/3002/3004; Q 3068; S 3076; PF 3084; стан вимикача 2018 → `2017 u16 map` (ПРИПУЩЕННЯ iot_sim, Q-09) | опитування | P 10/300; лічильники 60/60; струми фаз 30/300; стани 10/300 | плагін бекоф; сигнали `stale` (telemetry R-07); інтервали чекають до 6 год, далі `missing` (R-04); енергія через пропуск не губиться (R-03) |
| P-07 СЕС | SUN2000-115KTL-M2 PV-INV-1…8 (u61–u68) | Huawei «SUN2000MB Modbus Interface Definitions» — адреса документа **є PDU** (A-06): P 32080 `i32 ×0,001`; стан 32089 `u16 map`; добовий 32114 `u32 ×0,01`; накопичений 32106 `u32 ×0,01` | опитування | 10/300; лічильники 60/300 | як вище; аварійний стан → заявка (CT-05) |
| P-07 BESS | LUNA2000 (u69) | 37000 стан, 37001 `i32 ×0,001` кВт (+ заряд), 37004 SOC `u16 ×0,1`, 37014/37016 заряд/розряд `u32 ×0,01` (ПРИПУЩЕННЯ iot_sim §8.9.2) | опитування | 10–30/300 | як вище |
| P-07 КГУ | TEDOM Quanto D800 (u72) | 40000 стан, 40001 P ел., 40002 тепло, 40003 газ `×0,1`, 40010 мотогодини `u32`, 40014 енергія `u32` — PDU = номер (ПРИПУЩЕННЯ, Q-08) | опитування | 10–300/300 | як вище |
| P-07 АВР | Socomec ATyS p (u71) | Annexe III: 20482 режим, 20483 положення, 20484 реле пуску ДГУ, 20486/20487 стан джерел — PDU = номер (A-06, CE-02) | опитування | 5/300 (зміни стану — завжди) | без свіжих даних АВР острів визначається за вводами (R-14 п. 3) |
| P-07 температура T1/T2 | ADAM-6015 u96 | прив'язує telemetry (Додаток C.2); energy лише ставить пороги (CT-05) | — | 30/300 | — |
| CT-10 | 75 обчислених сигналів | `_f3d_ingest(src='module')` на джерелі `EN-DERIVED` (`type='f3d_energy'`, локальне) | з Odoo | 10 с…1 год | крони неактивні → енергія сама ставить `stale` (R-21) |
| CM-03 | 35 РЦ | `env['f3d.machine']._f3d_wo_intervals(wos, d0, d1)` | читання | крон 15 хв, `_cal_price` | модуля немає → журнал часу `mrp.workcenter.productivity` (R-08 п. 2) |
| viewer | — | `f3d.viewer.event._notify` (C-03) | Odoo → переглядач | ≤ 1 раз / 10 с на код (дебаунс telemetry R-13) + крони | без viewer — нічого |

### 2.5 Потік даних від пристрою до екрана

Приклад 1 — кВт·год і вартість завдання (Розкрій SAW-1, `WH/MO/00231`): 1) колектор раз на 60 с читає PM5560 u11
регістри 3204–3207 (`addr 3203`, `i64`, `×0,001`) і шле `energy/consumers/SAW-1/kwh_total`; telemetry зберігає кожне
показання (`store_period_s=60`); 2) machine_connect закриває інтервал `working` 01:36–02:54 UTC (CM-03); 3) крон розподілу
(15 хв) за добу 12.10 будує безперервний лічильник `Ec(t)` (R-03): `Ec(01:36) = 1000,000`, `Ec(02:54) = 1017,160` →
пряма енергія завдання 17,160 кВт·год, ціна зони «Цілодобова» 8,40 → 144,14 грн; 4) у слоті 02:45–03:00 аспірація DUST-1
спожила 31,875 кВт·год і ділиться між SAW-1 (1,98 кВт·год прямих) та EDGE-1 (8,775) → SAW-1 отримує 5,868 (R-09);
5) рядки `f3d.energy.alloc` (`direct`, `shared`/`POOL-DUST`, …) → `mrp.workorder.f3d_energy_kwh`, МО — сума; 6) при
`button_mark_done` МО `_cal_price` фіксує розподіл, для FIFO/AVCO додає `f3d_energy_cost / qty` до `extra_cost`, створює
аналітичні рядки за аналітикою РЦ (R-10); 7) `_notify('mrp.production', ['WH/MO/00231'], 'doc')` → переглядач
дозапитує дельту, провайдер production (30) дає МО, провайдер energy (100) ставить `energy_kwh`, `energy_cost`; картка МО:
«Електроенергія 86,2 кВт·год · ≈ 724 грн (виконані операції)» у режимі «оцінка» або фактичні числа з лічильників.

Приклад 2 — блекаут (варіант A, сценарій `blackout`): емулятор ставить `src1_ok=0`, PM5560 вводів `P=0`, СЕС `0x0303`;
ATyS p (Remote control) за наказом HGM6120N переходить у II; колектор привозить `infra/ats/src1_state=under` (0) і через
≈ 14–30 с `position=pos_II` (3); перевизначений `_f3d_ingest` (R-14) ставить `src1_ok=0`, відкриває `f3d.energy.outage`
(«Зникла напруга мережі»), подію `bad`, при `position=3` фіксує `transfer_s`; провайдер `infra` (150) пише
`grid_kw=0`, `export_kw=0`, `load_kw=348` (Σ фідерів), `shed_kw = 626 − 348 = 278`, `bess_mode='discharge'` поки накопичувач
тримає критичних; міст (155) додає `island=true`, `genset_kw=348`, картку GENSET. Повернення мережі: `position=2` →
відключення закрито з тривалістю, подія `info`, картка ATS-1 «Останнє спрацювання: 14.10, 10:05 — відключення мережі
10 хв».

Приклад 3 — експорт СЕС у полудень (ясно, 12.10 10:30 макета): Σ інверторів `pv_now=468`, КГУ 400, фідери 626 → R-06:
`surplus=242`, LUNA2000 `bess_kw=+200`, Q2 віддає 376,7 кВт, Q1 бере 334,7 → `grid_kw=0`, `export_kw=42`; провайдер `infra`
дає `totals.export_kw=42`, картка BESS «заряджається 200 кВт (надлишок СЕС і КГУ)»; профіль Q2 за 15 хв — `kwh_export`
зростає на 94,2 кВт·год, ціна експорту з тарифу.

### 2.6 Безпека

- **Групи** (`security/f3d_energy_security.xml`): `group_energy_user` («Енергетика: перегляд», неявно з
  `mrp.group_mrp_user` і `group_energy_manager`; implied `group_f3d_user`), `group_energy_cost` («Енергетика: вартість»,
  неявно з `account.group_account_readonly`, `account.group_account_invoice`, `mrp.group_mrp_manager`,
  `group_energy_manager`), `group_energy_manager` («Енергетика: енергетик», implied `group_energy_user`,
  `group_energy_cost`, `factory3d_base.group_f3d_manager`). Стоп-крани й повтор хука — `factory3d_base.group_f3d_admin`.
- **Вартість**: усі грошові поля (`cost`, `price`, `f3d_energy_cost`, тарифні ціни) — `groups="factory3d_energy.group_energy_cost"`;
  у payload `energy.totals.cost_today`, `productions[].energy_cost` — лише для користувача з групою і не в кіоску (`ctx.kiosk`).
- **Стоп-крани**: `factory3d.energy.read_enabled` (умовчання `environment == 'test'`, CB-10) — `read_enabled` 68 джерел
  енергетики і робота кронів; `factory3d.energy.write_enabled` — `False`; у v1 обмеження на `f3d.signal`: сигнал
  `module='energy'` з `write_enabled=True` → `ValidationError` (жодних команд на пристрої енергетики, A-15);
  `factory3d.energy.costing_enabled` (`True`) — внесення енергії в `extra_cost`. `neutralize.sql`: три параметри
  `False`, крони модуля вимкнено, джерела `MB-U*` енергетики `read_enabled=false`.
- **Токени** — немає власних (колектор telemetry, A-02 telemetry).
- **Ін'єкції**: коди вузлів/лічильників — regex `^[A-Z0-9][A-Z0-9\-]{0,31}$`; адреси сигналів перевіряє telemetry
  (`validate_address`); SQL лише параметризований (агрегати інтервалів — `execute` з `%s`); `time` зон тарифу — числа.
- **Заборонено**: Odoo не ходить у мережу цеху; модуль не створює `f3d.command`; не змінює `costs_hour` РЦ; не створює
  `account.move`; провайдери читають від імені користувача (без `sudo`), крім службових кронів (`sudo()` на власних моделях).

### 2.7 Продуктивність і обсяги

Сигнали зони енергетики (Додаток C SPEC): 220 з пристроїв, 75 обчислених, 2 — telemetry.

| Клас | Сигналів | `period_s` | `store_period_s` | Сирих/добу через API | Збережених/добу |
|---|---|---|---|---|---|
| Потужність P (PM5560 57 + T1/T2, SUN2000 8, LUNA, TEDOM) | 69 | 10 | 300 | 596 160 | 19 872 |
| Накопичувальні лічильники PM5560 (`kwh_total` 57, `kwh_export` 2) | 59 | 60 | 60 | 84 960 | 84 960 |
| Лічильники й добові значення СЕС/BESS/КГУ, мотогодини | 20 | 60–300 | 300 | 27 648 | 5 760 |
| Струми, фази, cos φ, Q, S, тепло, газ, SOC | 49 | 10–30 | 300 | 267 840 | 14 112 |
| Стани (вимикачі, інвертори, BESS, КГУ, АВР) | 23 | 5–30 | 300 + зміни | 187 200 | ≈ 6 600 + зміни |
| Обчислені (`kwh_shift`, тотали, асиметрія, баланс, АВР) | 75 | 10…3 600 | 0…300 | 49 920 | 19 104 |
| **Разом енергетика** (+ 2 температури — telemetry) | **295** | | | **≈ 1,21 М/добу (≈ 14/с)** | **≈ 150 000/добу** |

`f3d.reading` енергетики: 150 тис./добу × 30 діб (`keep_days`) ≈ **4,5 М рядків ≈ 580 МБ**; разом з іншими модулями
(telemetry оцінює ≈ 81 тис./добу) ≈ 7 М рядків — нижче порогу 20 М (telemetry Q-01). `f3d.energy.interval`: 67 × 96 =
6 432/добу, 400 діб ≈ **2,6 М рядків ≈ 300 МБ**; `f3d.energy.balance`: 8 × 24 = 192/добу; `f3d.energy.alloc`: ≈ 35 РЦ ×
(1 пряма + 5 пулів + простій) + 6 накладних ≈ 260/добу; `f3d.energy.event` ≤ 200/добу (90 діб). Індекси:
`f3d_energy_interval (meter_id, ts_start)` унікальний, `(ts_start)`; `f3d_energy_alloc (day, workorder_id)`,
`(production_id)`; `f3d_energy_balance (node_id, hour)` унікальний. Крон інтервалів: 67 лічильників × ≤ 2 доби
(`execute` одного вибору показань за вікно) ≤ 10 с; крон розподілу за добу: 96 слотів × 35 РЦ × 8 пулових лічильників у
пам'яті ≤ 5 с; провайдер `energy` ≤ 200 мс (один `search_read` сигналів зони, один агрегат інтервалів доби); `_f3d_ingest`
— додатково один `search_read` кодів енергетики з пакета (≤ 5 мс на 1 000 показань). TimescaleDB — не у v1 (Q-02).

### 2.8 Міграція з демо-бази і деінсталяція

Власних `x_`-полів немає. Сигнали рівня 0 мігрує telemetry (87 `energy/*`, `infra/*` з `origin='sim_data'`,
`module='energy'`, без джерела). `post_init_hook` модуля (SPEC §5.3), ідемпотентно, у транзакції установки:

1. Параметри (`read_enabled` за CB-10), джерело `EN-DERIVED` (`type='f3d_energy'`, без колектора).
2. 123 вузли з `data/energy_nodes.csv` (upsert за `code`; обладнання — `search_f3d(equipment_code)`, РЦ — за `code`).
3. 68 джерел `MB-U*` з `data/energy_sources.csv` (колектор `factory3d_telemetry.collector_main`, `read_enabled` = параметр).
4. 297 сигналів з `data/energy_signals.csv`: існуючі за `code` — оновлення визначення (джерело, адреса, період, пороги;
   `last_*` не чіпаються), нові — створення; `energy/consumers/*/kwh_shift` (40 рівня 0) переводяться на `EN-DERIVED`,
   `derived_from_id` → `kwh_total` (A-20); `energy/transformers/T*/temp_c` — лише пороги (адреси — telemetry).
5. 67 лічильників (`data/energy_meters.csv`), 5 пулів (`data/energy_pools.csv`), тариф демо 8,4 (data XML).
6. Звіт `factory3d.energy.install_report` (JSON з лічильниками, `state` ∈ {`done`, `partial`}).

Очікувано на копії демо: вузлів 123 (з обладнанням 80 — 72 різні одиниці, з РЦ 35, критичних 10), лічильників 67,
джерел 68 + `EN-DERIVED`, сигналів створено 210 (63 каталожні iot_sim — telemetry їх не створює — і 147 власних), оновлено
87, `unmatched_equipment: 0`. На чистій базі:
вузли без обладнання/РЦ (WARNING), решта — те саме.

`uninstall_hook`: параметри `factory3d.energy.*` видалити; сигнали належать моделям telemetry і лишаються: хук ставить
`source_id=False` усім сигналам зони енергетики, `active=False` — створеним модулем (`origin='catalog'` з каталогу й
`'manual'` власні, за списком кодів з `energy_signals.csv`), мігровані 87 лишаються активними без джерела (як після
міграції рівня 0); джерела `MB-U*` і `EN-DERIVED` — `active=False`; моделі `f3d.energy.*` видаляються з модулем, поля на
МО/завданнях зникають, `extra_cost` закритих МО не змінюється (бізнес-дані стандарту).

## 3. Налаштування системи

| Об'єкт | Параметр | Значення для тестового сервера | Коментар |
|---|---|---|---|
| `ir.config_parameter` | `factory3d.energy.read_enabled` | `True` (тест) / `False` (прод одразу після встановлення) | джерела енергетики й крони |
| `ir.config_parameter` | `factory3d.energy.write_enabled` | `False` | у v1 ввімкнути неможливо (A-15) |
| `ir.config_parameter` | `factory3d.energy.costing_enabled` | `True` | енергія в `extra_cost` при закритті МО |
| `ir.config_parameter` | `factory3d.energy.analytic_enabled` | `True` | аналітичні рядки за аналітикою РЦ |
| `ir.config_parameter` | `factory3d.energy.balance_tol_pct` / `balance_tol_kwh` | `3` / `2.0` | допуск балансу за годину (Q-11) |
| `ir.config_parameter` | `factory3d.energy.gap_alarm_min` | `60` | подія про пропуск даних лічильника |
| `ir.config_parameter` | `factory3d.energy.max_wait_h` | `6` | після цього інтервал без даних стає `missing` |
| `ir.config_parameter` | `factory3d.energy.keep_interval_days` / `keep_event_days` | `400` / `90` | ротація |
| `ir.config_parameter` | `factory3d.energy.shift_calendar_id` | id «Зміна 1 (07:00–15:30)» | початок зміни для `kwh_shift` |
| `ir.config_parameter` | `factory3d.energy.typical_days` | `20` | типовий день — середнє за N робочих днів |
| `ir.config_parameter` | `factory3d.energy.ats_fail_start_s` | `35` | FAIL START (варіант B) |
| `ir.config_parameter` | `factory3d.energy.peak_shave_kw` | `600` | текст картки BESS (макет) |
| `f3d.energy.tariff` | «Умовний тариф (демо)» | 01.01.2026 — ∞, одна зона 00:00–24:00 щодня, 8,40 грн/кВт·год, експорт 0, договірна потужність 800 кВт | замінити договором постачальника (Q-03, Q-04) |
| `f3d.energy.pool` | 5 пулів | `POOL-AIR` (COMPRESSOR, кВт·год), `POOL-DUST` (DUST-1, кВт·год), `POOL-GANTRY` (GANTRY-1, кВт·год, РЦ SAW-1…3, NEST-1), `POOL-LIGHT` (LP-1…3, час), `POOL-HVAC` (RV-ALL, AHU-1, час) | Q-01, Q-18 |
| `f3d.source` | 68 `MB-U*` + `EN-DERIVED` | колектор `COL-MAIN`, `host=iot-sim`, `port=502`, `unit` за iot_sim §8.4.1 | у проді — IP лічильників (iot_sim Q-12) |
| `ir.cron` | `cron_f3d_energy_live` | 1 хв | тотали, похідні, PFC, асиметрія (R-06, R-12) |
| `ir.cron` | `cron_f3d_energy_intervals` | 5 хв | профіль, `kwh_shift`, `load15/grid15` (R-04, R-11, R-15) |
| `ir.cron` | `cron_f3d_energy_alloc` | 15 хв | розподіл сьогодні (і вчора до 02:00) (R-08, R-09) |
| `ir.cron` | `cron_f3d_energy_balance` | 1 год (хв 07) | баланс (R-07) |
| `ir.cron` | `cron_f3d_energy_rotate` | щодня 03:10 (Київ) | ротація (R-19) |
| `res.groups` | енергетик, бухгалтер, майстер | користувачам демо: енергетик — `group_energy_manager`; бухгалтер — через `account.group_account_readonly` | |
| `maintenance.team` | «Служба головного механіка» | команда обладнання енергетики (у демо вже) | заявки CT-05 |

## 4. Інструкція

**4.1 Перевірити, що лічильники пишуть** (черговий електрик). Завод 3D → Енергетика → Лічильники: колонка «Стан» —
зелені `ok`; червоні `stale`/`gap` — відкрити, на вкладці «Сигнали» видно час останнього показання. Якщо лічильник
мовчить > 60 хв — у Подіях «Лічильник PM-SAW-1: немає даних 60 хв»; перевірити живлення і мережу пристрою; енергія за
пропуск відновиться з накопичувального лічильника, коли пристрій повернеться (інтервали позначаться «інтерпольовано»).

**4.2 Подивитися енергію й вартість МО** (майстер, бухгалтер). Виробництво → МО → вкладка «Енергія»: прямі кВт·год
(лічильник верстата за час роботи й налагодження), спільні (аспірація, повітря, світло, вентиляція), разом, якість
(«виміряно»/«оцінка»), вартість (лише бухгалтер/керівник). Рядки розподілу — кнопка «Розподіл». Після «Позначити як
виконано» розподіл фіксується (позначка «Зафіксовано»), для товарів із FIFO/середньою вартістю енергія додається до
«Extra Unit Cost».

**4.3 Змінити тариф або договірну потужність** (енергетик, бухгалтер). Енергетика → Налаштування → Тарифи → Створити:
період дії з дати нового договору, зони (напр. «Ніч» 23:00–07:00, «День» 07:00–23:00, ціни), ціна експорту, договірна
потужність. Попередній тариф — закрити датою «по». Поріг сигналу `energy/totals/grid15_kw` оновиться автоматично;
перерахунок минулих днів — майстер «Перерахувати» (лише незафіксовані МО).

**4.4 Небаланс обліку** (енергетик). Енергетика → Баланс: рядок «відхилення» (BW-1, 3,3 % при допуску 3 %) — порівняти
показники фідера QF-1 і споживачів лінії на вкладці вузла; дві години поспіль → заявка ТО «Небаланс обліку BW-1».
Типові причини: лічильник споживача без даних (інтервали `missing`), новий споживач без лічильника, ТТ з неправильним
коефіцієнтом.

**4.5 Відключення мережі** (черговий електрик). Під час блекауту в 3D картка ATS-1 «Генератор», вкладка «Енергія»:
«Власна генерація й резерв» — скинуто N кВт. Енергетика → Відключення: початок, тривалість, час переключення АВР,
скинуте навантаження, «FAIL START» (варіант B, генератор не запустився за 35 с). Картку генератора веде модуль
`td_genset`.

**4.6 Стоп-крани на проді** (адміністратор). Налаштування → Завод 3D → Енергетика: «Читати лічильники» вимкнено →
джерела енергетики не опитуються, крони нічого не роблять; «Вносити енергію в собівартість» — вимикає зміну
`extra_cost`. «Запис у пристрої» недоступний у v1. Копія проду — `neutralize.sql` модуля разом із telemetry.

## 5. Ризики й відкриті питання

### 5.1 Відкриті питання (ті самі номери — у SPEC §15)

| ID | Питання | Кому | Рекомендована відповідь | Що робимо тим часом |
|---|---|---|---|---|
| Q-01 | **Правило розподілу спільних споживачів.** Варіанти: (а) усі пули пропорційно машинному часу завдань; (б) усі пропорційно прямим кВт·год; (в) драйвер на пул: технологічні (повітря, аспірація, подача плит) — за прямими кВт·год, «будівельні» (освітлення, вентиляція) — за машинним часом; котельня, зарядна, офіс, витяжки — накладні, не на МО; (г) не розподіляти взагалі (лише прямі, як макет) | головний енергетик, бухгалтер, менеджер | **(в)**: аспірація й повітря ростуть разом із потужністю верстатів (кВт·год — найкращий корелят), світло й вентиляція працюють «на зміну» незалежно від потужності (час); накладні періоду — не в собівартість (облікова політика) | реалізовано (в) як дані пулів (`driver` на пулі змінюється без коду); (а)/(б) — зміною `driver`; (г) — архівувати пули |
| Q-02 | TimescaleDB для сирих рядів (D-11) | менеджер | **ні у v1**: ≈ 150 тис. збережених показань/добу енергетики, 4,5 М за 30 діб (§2.7) — у межах PostgreSQL Odoo; вмикати, коли `f3d_reading` > 20 М рядків, потрібні ряди 1 с (якість електроенергії, гармоніки) або `keep_days` > 90 | профіль 15 хв зберігається 400 діб в Odoo; сирі — 30 діб |
| Q-03 | Тариф і зони доби: постачальник, ціна, двозонний (ніч 23–07) чи тризонний (пік 08–11, 20–22; напівпік; ніч), складова розподілу/передачі, ціна експорту (активний споживач) | бухгалтер, замовник | взяти з договору постачальника; модель підтримує будь-яку кількість зон і періодів | один тариф 8,40 грн/кВт·год цілодобово (макет `TARIFF`), експорт 0 |
| Q-04 | Договірна (дозволена) потужність і як міряти перевищення (імпорт з мережі, 15-хв середнє) | енергетик, ОСР | значення з договору про розподіл; контроль — 15-хв імпорт `grid15_kw` | 800 кВт (ПРИПУЩЕННЯ: пік макета 654 кВт < 800), попередження з 90 % |
| Q-05 | Ціна енергії для собівартості: тариф мережі чи середньозважена (мережа + газ КГУ + СЕС ≈ 0) | бухгалтер | **тариф у v1** (консервативно, як макет); середньозважена — v2 з даними газу | тариф |
| Q-06 | Метод оцінки ГП: усі категорії `standard` → `extra_cost` на вартість не впливає (Odoo 19 `_cal_price` — лише FIFO/AVCO) | бухгалтер | AVCO для готової продукції й напівфабрикатів або періодичне оновлення `standard_price` з кошторисом енергії | поля й звіт працюють; `extra_cost` змінюється лише для FIFO/AVCO |
| Q-07 | Енергія простою прямих РЦ (верстат увімкнений без завдання) — на МО чи накладні | бухгалтер | накладні РЦ (рядки `idle`), щоб МО не платило за простій сусіда | так і зроблено |
| Q-08 | Нотація Modbus-адрес у iot_sim: правило §8.4.1 (−1 / −40001) хибне для Huawei (документ уже в PDU), Socomec (Annexe III — PDU) і TEDOM (40000 і 40001 після правила збігаються з іншими адресами); карта ATyS p §8.9.4 не збігається з Annexe III (td_genset Q-07) | автор iot_sim, менеджер | iot_sim приймає «PDU = номер» для Huawei, ATyS p, TEDOM і карту ATyS за Annexe III (20482…20487, коди положення 1/2/3) | energy пише адреси за документами вендорів (A-06); ТК із СЕС/АВР/КГУ блоковані до виправлення iot_sim (ризик) |
| Q-09 | Стан вимикачів MasterPact MTZ2 (MicroLogic X, модуль IFE) — регістри | енергетик / Schneider | окреме джерело IFE (Modbus TCP) з картою MicroLogic X | регістр 2018 PM5560 (ПРИПУЩЕННЯ iot_sim §8.7) |
| Q-10 | Уставки температури Trihal (PT100: попередження/вимкнення) | енергетик | за паспортом класу F: 140 °C попередження, 150 °C вимкнення; у Odoo — 130/140 | 100/110 °C (макет і каталог) |
| Q-11 | Допуск балансу обліку | енергетик | 3 % і 2 кВт·год за годину (клас 0,2S + втрати кабелів) | так |
| Q-12 | Пороги асиметрії струмів і cos φ | енергетик | асиметрія 10 % попередження / 20 % тривога (15 хв); cos φ на вводах 0,95 / 0,90 | так |
| Q-13 | Однолінійна схема: генерація (СЕС, КГУ, BESS) на секції 2, критична шина за АВР | проєктант електрики | підтвердити схему; дерево вузлів правиться даними | так, як iot_sim §8.7.2 (ПРИПУЩЕННЯ) |
| Q-14 | Вартість енергії під час роботи від генератора | бухгалтер | v1 — тариф; паливо ДГУ — у `td_genset` | тариф |
| Q-15 | Частота опитування лічильників і термін зберігання (каркас §9 п. 6) | замовник | P 10 с, лічильники 60 с; сирі 30 діб, профіль 400 діб | так (§2.7) |
| Q-16 | Spreadsheet-дашборд | замовник | після UAT: аналітик збирає spreadsheet на pivot-ах модуля в групі «Виробництво» | graph/pivot «Огляд» (A-12) |
| Q-17 | PM5560: порядок слів INT64 (FAQ FA237865 у прикладі читає 3204 як молодші 32 біти) | енергетик при пусконаладці | реєстровий лист Schneider: INT64 старше слово першим; на заводі звірити з Float32-копією 2700 | `wordorder=big`; ТК-11 порівнює `kwh_total` з `2700` (`|Δ| ≤ 1 кВт·год`) |
| Q-18 | Склад пулів і обслуговувані РЦ (портал — лише розкрій/нестинг? аспірація — лише деревообробні?) | технолог | портал → SAW-1…3, NEST-1; аспірація, повітря, світло, вентиляція → усі РЦ | так (дані) |
| Q-19 | Початок зміни для `kwh_shift` (одна чи дві зміни) | технолог | за календарем РЦ: перший інтервал доби | календар «Зміна 1 (07:00–15:30)» |
| Q-20 | Рахунок поглинання енергії в собівартість (кредит виробничого рахунку проти витрат за рахунком постачальника) | бухгалтер | облікова політика підприємства; модуль лише `extra_cost` і аналітика | без проводок |

### 5.2 Ризики

| Ризик | Вплив | Пом'якшення |
|---|---|---|
| iot_sim не виправить нотацію Huawei/ATyS/TEDOM (Q-08) | на стенді СЕС на 1 регістр зсунута (сміття), АВР без острова, КГУ сміття | адреси лише в даних; ТК-11 «звірка адрес» до решти ТК; запасне визначення острова за вводами (R-14 п. 3) |
| Карта PM5560 на заводі інша (прошивка), порядок слів INT64 | неправильні кВт·год → неправильна собівартість | ТК-11 (звірка з Float32 2700 і з дисплеєм), баланс R-07 ловить системні помилки |
| Розподіл «на ходу» змінюється після закриття МО (слот ще не закритий) | невелика розбіжність між зафіксованим МО і добою | зафіксовані рядки не перераховуються; залишок слоту — іншим завданням/нерозподіленому; звірка за добу на дашборді |
| Стандартна оцінка (`standard`) — енергія не доходить до вартості складу | очікування замовника «енергія в собівартості» не виконане | Q-06; поля МО, звіт «Розподіл», аналітика працюють незалежно від методу |
| Обсяг `f3d_reading` (лічильники 60 с) | гальмування графіків | `store_period_s` у даних; ротація telemetry; Q-02 поріг |
| Небаланс через відсутні лічильники (OFFICE, RV-ALL — групові) | постійні попередження балансу C2 | допуск, `imbalance_pct` з `min_duration` 2 год; лічильники груп — у даних iot_sim u51/u55 |
| Перевизначення `_f3d_ingest` кількома модулями (machine_connect, energy) | порядок, рекурсія | `super()` першим, контекст `f3d_energy_internal` для власних вкладень, результат `super()` не змінюється |

## 6. План сборки агентами

Межі файлів жорсткі; спільні файли (`__manifest__.py`, `__init__.py`, `models/__init__.py`,
`security/ir.model.access.csv`, `security/f3d_energy_security.xml`, `views/menus.xml`, `tests/common.py`) належать W0.

| Воркер | Файли | Здає | Залежить від |
|---|---|---|---|
| W0 каркас і дані | маніфест, `__init__.py`, `models/__init__.py`, `security/*`, `data/ir_config_parameter.xml`, `data/ir_cron.xml`, `data/neutralize.sql`, `views/menus.xml`, `tools/__init__.py`, `tools/gen_energy_data.py`, `data/energy_*.csv` (згенеровані), `tests/__init__.py`, `tests/common.py`, `tests/test_data_sync.py`, README, CHANGELOG | модуль ставиться порожнім, меню 50, групи, CSV детерміновані з макета | SPEC §0, §1, §3 (меню), §4, §5.1–§5.2, Додатки B–D |
| W1 мережа, лічильники, тарифи, хук | `models/f3d_energy_node.py`, `f3d_energy_meter.py`, `f3d_energy_tariff.py`, `f3d_energy_pool.py`, `f3d_source.py`, `f3d_signal.py` (лише обмеження A-15), `hooks.py`, `views/f3d_energy_node_views.xml`, `…meter…`, `…tariff…`, `…pool…`, `tools/tariff.py`, `tests/test_node.py`, `test_tariff.py`, `test_hooks.py` | M-01, M-02, M-04…M-06, M-16; R-01, R-05, R-22; AC-01…AC-14, AC-70…AC-74 | W0 |
| W2 профіль, баланс, тотали, події | `tools/counter.py`, `tools/balance.py`, `tools/live.py`, `models/f3d_energy_interval.py`, `f3d_energy_balance.py`, `f3d_energy_event.py`, `models/f3d_signal.py` (`_f3d_ingest`, разом із W1 через W0), `views/…interval…`, `…balance…`, `…event…`, `tests/test_counter.py`, `test_interval.py`, `test_balance.py`, `test_live.py`, `test_events.py` | M-03, M-08, M-09, M-15; R-02…R-04, R-06, R-07, R-11…R-13, R-15, R-19, R-21; AC-15…AC-36, AC-83, AC-84, AC-86, AC-87 | W1 |
| W3 розподіл і собівартість | `tools/alloc.py`, `models/f3d_energy_alloc.py`, `mrp_workorder.py`, `mrp_production.py`, `mrp_workcenter.py`, `maintenance_equipment.py`, `maintenance_request.py`, `wizard/recompute_wizard.py`, `views/mrp_*_views.xml`, `…alloc…`, `wizard/…xml`, `tests/test_alloc.py`, `test_costing.py`, `test_mo231.py` | M-07, M-11…M-14, M-17, M-19; R-08…R-10, R-23; AC-37…AC-54, AC-85 | W2 |
| W4 АВР, відключення, генерація | `models/f3d_energy_outage.py`, `tools/ats.py`, `views/…outage…`, `tests/test_ats.py`, `test_island.py` | M-10; R-14; CE-01…CE-04; AC-55…AC-62 | W2 (паралельно з W3) |
| W5 переглядач і налаштування | `models/viewer_provider.py`, `tools/payload.py`, `models/res_config_settings.py`, `views/res_config_settings_views.xml`, `views/dashboard_views.xml`, `tests/test_payload.py`, `test_security.py` | M-18, M-20; R-16…R-18; AC-63…AC-69, AC-75…AC-82 | W3, W4 |
| W6 стенд і звіти | `tests/stand/*` (pytest `-m stand`), `docs/modules/factory3d_energy/DEPLOY_TEST.md`, `TEST_REPORT.md` | ТК-01…ТК-12, ТБ-01…ТБ-06, ТП-01…ТП-06, DEPLOY_TEST; AC-13, AC-53, AC-73, AC-88…AC-92 | W5; iot_sim з виправленням Q-08 для ТК-05…ТК-08 |

Порядок злиття: W0 → W1 → W2 → (W3 ‖ W4) → W5 → W6. Кожен воркер здає зелені тести своїх файлів
(`odoo-bin -d test --test-tags /factory3d_energy:<TestClass> --stop-after-init`); після W5 — повний прогін
`--test-tags /factory3d_energy` на чистій базі й на копії демо; після W6 — стенд.

## 7. Рішення автора (A-xx)

| ID | Рішення | Обґрунтування | Що змінює відносно каркаса |
|---|---|---|---|
| A-01 | `f3d.energy.interval` — розрахунковий 15-хв профіль (кВт·год, грн, якість) на лічильник, не журнал показань | D-04 забороняє власні журнали показань; профіль — бізнес-дані комерційного обліку, потрібні 400 діб (сирі — 30), і без нього неможливі ціни за зонами та пік 15 хв | уточнює D-04 |
| A-02 | Джерело істини для кВт·год — накопичувальний лічильник PM5560 (3204 INT64), а не інтеграл `p_now` | клас 0,2S; пропуски зв'язку не губять енергію; відповідь на telemetry Q-09 | — |
| A-03 | Сітка 15 хв за UTC (`date_trunc` на чверть години); доба, профіль і розподіл — за Києвом | зсув Києва — цілі години, тож чверті збігаються; DST лише змінює кількість годин доби (23/25) | — |
| A-04 | Провайдери переглядача — `AbstractModel` з `_name='f3d.viewer.provider.energy'`/`'.infra'` **без** `_inherit`, з власними `_f3d_sequence/_f3d_sections/_f3d_group` і трьома методами | рішення менеджера 14.10 (viewer збирає провайдерів за префіксом імені); без моста-модуля | — |
| A-05 | machine_connect — необов'язковий: `if 'f3d.machine' in self.env` → CM-03; інакше журнал часу | рішення менеджера; ті самі інтервали (machine_connect веде таймери завдань) | — |
| A-06 | Modbus-адреси за документом вендора: PM5560 — `N − 1`; Huawei, ATyS p (Annexe III), TEDOM — `N` (вже PDU) | модулі для проду не знають про емулятор (каркас §1); telemetry A-01 вимагає PDU | розходиться з iot_sim §8.4.1 (Q-08) |
| A-07 | Сигнали АВР — `kind='state'` зі списком `states`, де індекс = код Annexe III (`unknown, pos_0, pos_I, pos_II`) | `last_value` (індекс) дорівнює коду положення, як чекає міст (R-05 td_genset); зміна стану зберігається одразу (telemetry R-03 п. в) | — |
| A-08 | Обчислені сигнали — на локальному джерелі `EN-DERIVED` (`type='f3d_energy'`, CT-12) | stale/стан веде модуль; сигнали без джерела ніколи не `stale` (telemetry R-07) | — |
| A-09 | Розподіл — повний перерахунок доби слотами 15 хв; рядки `f3d.energy.alloc` на (доба, завдання, вид, пул); рядки МО фіксуються при закритті | спільні пули потребують усіх одночасних завдань; добова гранулярність — малий обсяг, ідемпотентність | — |
| A-10 | Енергія в собівартість — через `extra_cost` у перевизначенні `_cal_price` (з поправкою `_get_backorder_mo_vals`), не через `costs_hour` | `costs_hour` — ставка за годину (енергія не пропорційна часу); `extra_cost` Odoo 19 множить на кількість і входить у вартість FIFO/AVCO | — |
| A-11 | Аналітика — `account.analytic.account._perform_analytic_distribution(distribution, amount, kwh, lines, obj)` з рядком розподілу як `obj` (`_prepare_analytic_line_values`, одиниця `uom.product_uom_kwh`) | так само, як `mrp_account` для РЦ; аналітика РЦ вже налаштовується стандартно | — |
| A-12 | Дашборд — kanban/graph/pivot, не spreadsheet | JSON spreadsheet не пишеться надійно вручну й не тестується; Q-16 | — |
| A-13 | Події енергетики (договірна потужність, cos φ, асиметрія, небаланс, FAIL START) — обчислені сигнали з порогами → заявки через telemetry CT-05 | єдине правило §6.8; дедуплікація й закриття заявок — telemetry | — |
| A-14 | Острів для власних тоталів energy визначає сама за сигналами АВР (R-14); ключі `island`/`grid_ok` у payload пише міст | провайдер energy (150) іде раніше моста (155) | — |
| A-15 | Запис у пристрої енергетики неможливий у v1: обмеження `_check_f3d_energy_write` на `f3d.signal` | вимога замовника «енергетика лише читає»; `write_enabled` лишається параметром для v2 | — |
| A-16 | Дерево вузлів — за живленням (`parent_id` = вузол, від якого живиться); `SWB-1` і `ATS-1` — фізичні корені; секційний вимикач `QS` — дитина секції 1 з `peer_id` = секція 2; шафи мають `cabinet_id = SWB-1` | одна ієрархія для балансу й схеми; фізичне розміщення — окремим полем | — |
| A-17 | Договірна потужність — поле тарифу (договору), не параметр | змінюється разом із договором; історія | — |
| A-18 | Вартість ховається групою на полях і в payload | майстер бачить кВт·год, не гроші (вимога) | — |
| A-19 | 9 споживачів без сигналів у каталозі iot_sim (OFFICE, LP-1…3, RV-ALL, AHU-1, EF-*) отримують `p_now`, `kwh_total`, `kwh_shift` (u51–u59 у iot_sim §8.4.1 існують) | баланс лінії C2 і пули без них неможливі | доповнює каталог iot_sim |
| A-20 | `kwh_shift` — обчислений сигнал (різниця лічильника з початку зміни), а не адреса PM5560 | регістр 3204 — накопичувальний; «різниця за зміну» з каталогу iot_sim у пристрої немає | змінює прив'язку 40 сигналів рівня 0 |
| A-21 | Схема мережі — вид `hierarchy` (`web_hierarchy`, встановлений) на `f3d.energy.node` | стандартний Odoo 19, дерево ГРЩ без власного JS | — |
| A-22 | Власний `_f3d_viewer_delta` з глибоким злиттям `infra` (не копіювання розділу) | базова дельта viewer R-14 п. 5 копіює розділ цілком — затерла б частину моста (155) або навпаки | запит до viewer/міст |
