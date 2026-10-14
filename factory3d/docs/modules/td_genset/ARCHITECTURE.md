# td_genset — технічне рішення: запит на зміни (перенос 18 → 19) і міст `factory3d_genset`

Версія 0.3 · 14.10.2026 (0.2 — 14.10.2026) · автор: агент-архітектор (Claude) · статус: **чернетка на погодження**.

Зміни: 14.10.2026 — правки за CONSISTENCY.md: X-69 (пункт «Налаштування генератора» під `factory3d_base.menu_f3d_config`, sequence 55 —
§1.2, §2.1 CB-09, A-06; поля значень положень АВР і перерахунок `period_s` — SPEC M-07) (v0.3).

Зміни (v0.2): 14.10.2026 — правки за `docs/CONSISTENCY.md`: X-01 (джерело `GENSET-RELAY` локальне лише через хук telemetry
`_f3d_local_types()`, без перевизначення `collector_id` — A-15, Q-20 закрито), X-10 (КГУ в острові — виміряне `infra/totals/chp_kw`,
§2.5.3, Q-02), X-11 (критичні споживачі — `f3d.energy.node.is_critical`, `critical_codes` запасний, `critical_kw` пише лише energy —
FR-11, §3), X-13 (`stale` сигналів GENSET ставить лише міст), X-20 (`depends` за каркасом §3 без `factory3d_viewer`, провайдер за
префіксом без `_inherit` — §2.1, A-03 вилучено, A-18, FR-17), X-23 (власна дельта `infra` з `deep_merge` — §2.5.1), X-41 (ATyS p за
Annexe III: положення I/II = 2/3 без стендових винятків — §3, Q-07 закрито), X-62 (у каталозі iot_sim 1 довідковий рядок генератора);
закрито також Q-09 (X-32), Q-21 (X-59), Q-23 (X-24).
Зміни: 14.10.2026 — закрито відповідями замовника (CONSISTENCY, «Відповіді на питання до замовника»): Q-01, Q-02, Q-03, Q-05, Q-06, Q-08, Q-22, Q-24.
Зміни: 14.10.2026 — закрито рішеннями менеджера: Q-10, Q-11, Q-12, Q-13, Q-14, Q-15, Q-16, Q-17, Q-18, Q-19.

Форма документа — **запит на зміни (change request) до ТР `td_genset` v1.2** (далі «ТР 1.2») плюс
технічне рішення нового модуля-моста **`factory3d_genset`**. Рішення менеджера D-12 (каркас
`docs/ARCHITECTURE.md` §8): `td_genset` переносять «як є»; у проєкті factory3d — лише перенос на
Odoo 19 і зв'язка з моделлю заводу. Специфікація для розробника й тестувальника — `SPEC.md` поруч.

Репозиторію `td_genset` у цьому середовищі **немає**. Усе, що стосується внутрішніх імен моделей,
полів, груп і файлів `td_genset`, тут описано **ролями** й позначено «ЗВІРИТИ з td_genset»; кожна
така позиція зведена в Q-10…Q-19 (§5) і в SPEC §15. Жодне внутрішнє ім'я `td_genset` не вигадане;
міст звертається до `td_genset` **тільки** через один файл-адаптер (SPEC §2.0, ADP-01…ADP-10), який
заповнює розробник переносу після звірки з кодом.

Факти про тестовий сервер (timur-o19demo, база `odoo`, лише читання, перевірено 14.10.2026):
Odoo `19.0.1.3` (`base`), установлені `maintenance 19.0.1.0`, `mrp_maintenance`, `mail 19.0.1.19`,
`bus`, `web`, `web_enterprise`, `iot`, `factory3d_iot_sim 19.0.1.0.0`; модулі `factory3d_base`,
`factory3d_viewer`, `factory3d_telemetry`, `factory3d_energy`, `td_genset` **не встановлені**.
`maintenance.equipment` id 65: `name="Дизель-генератор"`, `serial_no="GENSET"`, `model="KOHLER-SDMO D700
(шумозахисне виконання M230)"`, категорія «Електропостачання», команда «Служба головного механіка»,
`x_f3d_signal_ids=[]` (сигналів генератора в data-модулі немає — мігрувати нічого); `ATS-1` id 177,
`BESS` id 178, `CHP` id 181 — та сама категорія й команда. `maintenance.request`: обов'язкові `name`,
`company_id`, `kanban_state`, `maintenance_team_id`, `maintenance_for` (`equipment`/`workcenter`);
`maintenance_type` ∈ {`corrective`, `preventive`}; стадії «New Request», «In Progress», «Repaired»
(done), «Scrap» (done). `res.groups` має `privilege_id` і **не має** `category_id`; `ir.cron` без
`numbercall`/`doall`; `interval_type` ∈ {minutes, hours, days, weeks, months}.

## Загальна інформація

| Етап ToDo | Що здається | Люд./год (оцінка автора; `docs/оцінки` в репозиторії ще немає) |
|---|---|---|
| ТР | цей документ (CR до ТР 1.2 + технічне рішення моста) і `SPEC.md` | 24 |
| Архітектура | погодження A-xx/Q-xx з менеджером і автором `td_genset`; фіксація контрактів CG-xx/CT-xx/CE-xx | 8 |
| Розробка | W1 перенос `td_genset` на 19.0 (гілка `19.0`) — 40; W2–W4 міст `factory3d_genset` + профіль D700 для `fake_relay.py` — 56 | 96 |
| Тестування | регресія `td_genset` (176 юніт + 45 ТК) на 19.0 — 24; тести моста (UT + ТК на `fake_relay` D700 + блекаут з емулятором) — 32 | 56 |
| Інструкція | адаптація «Робота поза графіком» і «Заправка» під завод, README/CHANGELOG обох модулів, DEPLOY_TEST | 12 |
| **Разом** | | **196** |

## 0. Зведення запиту на зміни до ТР `td_genset` 1.2

| CR | Зміна | Причина | Виконавець | Де описано |
|---|---|---|---|---|
| CR-01 | Перенос на Odoo 19: маніфест `19.0.1.0.0`, представлення, групи (`res.groups.privilege`), SQL-обмеження (`models.Constraint`), ORM 19, OWL-пульт, крони, тести | платформа заводу — Odoo 19 Enterprise | W1 | SPEC §A (MG-01…MG-32) |
| CR-02 | `fake_relay.py`: профіль **D700** (бак 610 л, крива витрати 38,6/71,2/103,8/136,4 л/год, таймери HGM6120N) і REST-контракт керування для емулятора заводу (`/sim/v1/*`) | P-12 каркаса: емулятор = існуючий `fake_relay.py`; сценарій `blackout` має вести послідовність у ретрансляторі | W4 | SPEC §8 (API-F-01…API-F-09) |
| CR-03 | Docker-стенд: контейнер `genset_relay` у `docker-compose.sim.yml` (`services/iot_sim`), порт 8000, токен, профіль через env | спільний стенд з `factory3d_iot_sim` | W4 | SPEC §8.5 |
| CR-04 | Точки читання для моста (адаптер): модель генератора, знімок показань, журнал подій, ТО за мотогодинами, розклад — **без зміни `td_genset`**, лише підтвердження імен; якщо чогось немає — мінімальний метод-геттер | міст публікує показання в `f3d.signal` і події → заявки ТО | W1 (звірка) + W2 | SPEC §2.0 ADP-01…ADP-10 |
| CR-05 | Паливо: витрата за навантаженням із паспорта D700 (4 точки) замість сталої; якщо модель палива `td_genset` приймає лише сталу — міст веде криву сам, а в `td_genset` записує еквівалент при 75 % (103,8 л/год) | у заводі навантаження генератора змінюється 25…100 % | W1/W2 | SPEC R-01, R-02; Q-11 |
| CR-06 | Розклад роботи: дані під завод (дві зміни за `plant/energy.py:day_profile`), без зміни коду | офісний графік 08:45–18:45 не підходить | адміністратор (дані) | §3, Q-03 |
| CR-07 | Ролі: відповідність груп `td_genset` групам `factory3d_base` (`group_f3d_user/manager/admin`) — таблиця, без злиття груп | 111 співробітників на проді мають права `td_genset`; завод додає своїх | W1 | SPEC §4.3; Q-12 |
| CR-08 | Інструкції «Робота поза графіком» і «Заправка» — редакція під завод (структура §4; процедури замовника — з існуючих інструкцій) | інші ролі й місця (каністри ↔ зовнішній бак) | W1 + менеджер | §4.4, §4.5 |
| CR-09 | Регресія: 176 юніт + 45 ТК (ТК-01…ТК-14) на 19.0, матриця ТР 1.2 AC-01…AC-69 ↔ тести, DEPLOY_TEST для 19.0 | підтвердження «як є» | W5 | SPEC §13.2, §13.6 |
| CR-10 | `neutralize.sql`/preflight: узгодити з CB-10 (`factory3d.base.environment`) і стоп-кранами моста | один порядок нейтралізації для всього стенда | W1/W2 | SPEC §5.5 |

Що **не** змінюється в `td_genset` (D-12): моделі, пульт, ескалація тривог, модель палива з каністрами,
ТО за мотогодинами, ролі, протокол ретранслятора (`relay_api.md`). Усе заводське — у `factory3d_genset`.

## 1. Опис процесу і функціональні вимоги

### 1.1 Контекст: що є в макеті

| Джерело | Що містить | Як використовує документ |
|---|---|---|
| `plant/equipment_specs.json[role=genset]` | KOHLER-SDMO D700 (M230): 634 кВА / 507 кВт PRP, 697 кВА / 558 кВт ESP, Doosan DP180LB, бак 610 л, витрата 103,8 л/год при 75 % PRP, 136,4 / 149,5 л/год при 100 % PRP / ESP, контролер SmartGen HGM6120N (AMF), зв'язок CMM366B-4G → ретранслятор → Odoo; ключі `power_kw=507`, `kva=634`, `kva_standby=697`, `fuel_lph_75=103.8`, `tank_l=610`, `controller` | профіль D700 (SPEC M-02, Додаток C), рядки картки |
| `plant/equipment_specs.json[role=ats]` | Socomec ATyS p 1600 A 4P (арт. 95734160), Advanced Integrated Logic, схема «мережа–ДГУ», опції Modbus RS485 / Ethernet TCP | обидва варіанти логіки AMF (§2.5.3), контракт з energy (CE-02) |
| `plant/equipment_specs.json[role=bess]`, `[role=chp]` | LUNA2000 2 × 193,5 кВт·год / 2 × 100 кВт; TEDOM Quanto D800 800 кВт, острівний режим — опція PE/I, black start не опубліковано, `min_load=0.5` | правило балансу при блекауті (R-06) |
| `plant/infra.py` | `GENSET_POS=(128.5, 76.2)`; `CRITICAL=["LP-1","LP-2","LP-3","DUST-1","COMPRESSOR","BOILER","OFFICE","EF-ELEC","EF-CHG","BW-1-LINE"]` (рядок 248) + лінія `BW-1`; `infra_data()` (рядки 258–389): картка `GENSET` з рядками «Потужність», «Стан», «Контролер: SmartGen HGM6120N · CMM366B-4G → Odoo», «Паливо 82 % · 500 л», «Автономність ≈ 4,8 год при 75 %», «Критичні споживачі зараз 348 кВт з 507 кВт», «Остання перевірка: сьогодні 07:30 — щотижневий пуск 15 хв, норма», `items` (10 критичних споживачів), `note`; картка `ATS-1` («Положення: Мережа (T1/T2)», «Переключення: після пуску генератора, 10–15 с», «Останнє спрацювання: 05.10, 18:42 — відключення мережі 2 год 11 хв»); картка `BESS` («резерв на пуск генератора», «Тримає критичні ≈ 51 хв»); `totals`: `genset_kva=634`, `critical_kw=348`, `load_kw=626`, `chp_kw=397.3`, `bess_kw=200`, `bess_soc=0.761`, `grid_kw=0`, `export_kw=42` | рядки картки GENSET (R-10), критичні споживачі (R-04), приклади в R-06 |
| `plant/energy.py` | `ENERGY_ROLES["GENSET"]=("genset", [])` (рядок 428); `totals.p_now=626`, `peak_kw=654`, `capacity_kva=2000`; `day_profile` — дві зміни | розклад (CR-06), баланс |
| `plant/site2.py` рядки 127–154 | об'єкти `GENSET` («Дизель-генератор», kind `power`, кожух 5031×1690×2672), `ATS-1` («Шафа АВР»), `BESS` («Накопичувач енергії… запускається генератор») | коди сцени, зона `Z-ENERGY` (GENSET) і `Z-ELEC` (ATS-1) за base Додаток F |
| `plant/odoo_flows.py` | назви обладнання (рядки 25, 29), ролі інфраструктури (45), сигнали `infra/totals/pv_now`, `infra/totals/chp_kw`, `infra/totals/bess_soc` (755–760) — сигналів генератора **немає** | нові коди `infra/genset/GENSET/*` (SPEC Додаток A) |
| `plant/odoo_pull.py` рядки 280–297 | `sync_signals`: шлях `a/b/c/leaf` → вузол payload; `%` → частка; `energy.totals.pv_kw/chp_kw` з `infra.totals` | правило округлення в провайдері (R-11) |
| `dist/odoo_demo.json` | `infra.cards.GENSET` (7 рядків, `items`, `note`), `infra.cards.ATS-1`, `infra.cards.BESS`, `infra.totals` (18 ключів), `energy.totals` (16 ключів), `passports.GENSET` | структура, яку провайдер відтворює (viewer Додаток A.13) |
| `viewer/index.html` | `infraHtml()` (рядки 2607–2620: картка з `rows`/`warn`/`note`/`items` → «Критичні споживачі»), `backupSummary()` (2622–2641: рядок `GENSET` з `T.critical_kw`, `T.genset_kva`; рядок `ATS-1` «мережа ↔ генератор» завжди «мережа»; підказка «З мережі зараз…»), вид «Когенерація» (рядок 609: камера на майданчик енергетики) | що показує переглядач; запит CV-01 (рядок ATS/GENSET при острові) |
| `odoo_addons/factory3d_iot_sim` (data-модуль) | 196 сигналів `x_f3d_signal`, генератора серед них немає | міграції для GENSET немає (§2.8) |

Що є в `td_genset` (з опису замовника, ТР 1.2, SPEC AC-01…AC-69): показання генератора, події,
тривоги з ескалацією, пульт (OWL: «Авто», старт/стоп, тест на 3 хв), розписання роботи (будні
08:45–18:45; таймер проти розкладу), паливо з каністрами (заправка), ТО за мотогодинами, ролі
(111 співробітників), інструкції «Робота поза графіком» і «Заправка», `relay_api.md`, `fake_relay.py`,
Docker-стенд, стоп-крани, `neutralize.sql`, preflight, CHANGELOG, DEPLOY_TEST.md; 18 тис. рядків
Python, 176 юніт-тестів, 45 стендових сценаріїв ТК-01…ТК-14. Протоколи HGM6100N і CMM366 звірені на
етапі макета; ретранслятор з API вже є в замовника (офіс).

Факти з мануалу SmartGen «HGM6100N Series Genset Controller User Manual» (HGM6110N/6120N/6110NC/6120NC/
6110CAN/6120CAN; https://www.smartgen.cn/yun/data/download/HGM6110N_6120N_6110NC_6120NC_6110CAN_6120CAN_en.pdf,
переглянуто 14.10.2026): HGM6120N = HGM6110N + контроль мережі й автоматичне перемикання мережа/генератор
(AMF); **HGM6120N не має RS485** (RS485/Modbus — лише HGM6120NC; CAN — лише HGM6120CAN), налаштування через
USB; вимірює напруги/струми/частоту/кВт/кВА/PF/кВт·год генератора, напругу/частоту мережі, тиск оливи
(кПа/psi/бар), температуру ОЖ, рівень палива (% і л), напругу АКБ і зарядного, мотогодини, кількість
пусків; таблиця 4 «Warnings» (17 позицій) і таблиця 5 «Shutdown Alarms» (24 позиції); функція ТО (за
мотогодинами або датою, дія warning/shutdown); плановий пуск («Scheduled Run»); таймери за
замовчуванням (Table 7): Mains Normal Delay 10 с, Mains Abnormal Delay 5 с, Mains Under/Over Voltage
184/276 В, Transfer Delay 1,0 с, Start Delay 1 с, Stop Delay 1 с, Start Times 3, Cranking Time 8 с, Crank
Rest 10 с, Safety On 10 с, Warming Up 10 с, Cooling 10 с, ETS Solenoid Hold 20 с, Battery Over/Under
33,0 / 8,0 В, Gen Abnormal Delay 10 с, Over Current Delay 30 с. CMM366B-4G — модуль хмарного моніторингу
(USB/RS485 → 4G); окремої публічної специфікації саме «B-4G» не знайдено (є CMM366A-4G/ET: живлення
DC 8–35 В, порти RS485/USB/LINK) — у заводі ланка «контролер → CMM366B-4G → ретранслятор → Odoo» лишається
такою, як в офісі (`relay_api.md`), і в цьому документі не змінюється.

Факти з мануалу Socomec «ATyS p — Automatic Transfer Switching Equipment, Instruction manual 542 001 D»
(https://www.nhp.com.au/public/assets/pim/Original/10043/Socomec-Transfer-Switch-ATyS-P-User-Manual.pdf,
переглянуто 14.10.2026): застосування `APP = M-G` (мережа–генератор); контакт пуску ДГУ — клеми 71
(спільний), 72 (NC), 74 (NO) «Signal to Start / Stop the Genset»; таймери за замовчуванням: 1FT 3 с
(втрата джерела 1), 1RT 180 с (повернення джерела 1), 2FT 3 с, 2RT 5 с, 2AT 5 с (стабілізація джерела
2), 2CT 180 с (охолодження ДГУ після повернення), 2ST 30 с (тайм-аут пуску ДГУ → «FAIL START»), ODT 3 с
(мертва зона при переключенні), TOT 10 с; режими Manual / Auto / Locked / Remote control / Inhibit; опції
зв'язку RS485 Modbus RTU і Ethernet Modbus TCP; Annexe III (адреси Modbus, dec): 20480–20481 дата/час,
**20482 Operating Mode** (0x0000 Manual, 0x0001 Locked, 0x0010 Auto, 0x0020 Remote, 0x0040 Inhibit),
**20483 Switch Position** (0 Unknown, 1 Position 0, 2 Position I, 3 Position II), **20484 Source 2 Start
Generator relay State** (0/1), 20485 Priority, **20486 Source 1 State** (0 Under threshold, 1 Present,
2 Available), **20487 Source 2 State**, 21761 Set Operating Mode (запис), 57635 Modbus slave address.
Припущення `factory3d_iot_sim` SPEC §8.9.4 (20480 = Switch position) розходилось з цим — рішення X-41: iot_sim переводить
карту P-07 на Annexe III (20483, коди 1/2/3), як energy CE-02; Q-07 закрито.

### 1.2 Ролі й сценарії використання

| Роль (група) | Що робить | Де |
|---|---|---|
| Черговий електрик / оператор генератора (група оператора `td_genset` — ЗВІРИТИ ім'я; плюс `factory3d_base.group_f3d_user`) | дивиться показання й тривоги, керує з пульта («Авто», старт/стоп, тест), фіксує заправку, читає інструкції | меню `td_genset` (як є) + картка GENSET у «Завод 3D → Переглядач» |
| Головний енергетик (менеджер `td_genset` — ЗВІРИТИ; `group_f3d_manager`) | налаштовує розклад, пороги, профіль D700, прив'язку GENSET ↔ генератор, мапу подій → заявки ТО, дивиться баланс при блекауті | `td_genset` (як є); «Завод 3D → Генератор → Зв'язка / Профіль / Події → ТО» |
| Служба головного механіка (`maintenance.group_equipment_manager`) | отримує заявки ТО від моста (аварійні — з тривог, планові — за мотогодинами), закриває їх | Обслуговування → Заявки (стандарт) |
| Диспетчер / керівник (`group_f3d_user`) | бачить стан генератора, АВР, накопичувача і баланс у 3D | «Завод 3D → Переглядач», вкладка «Енергія», картка GENSET |
| Адміністратор factory3d (`group_f3d_admin`) | стоп-крани моста, джерело телеметрії, емулятор, `neutralize.sql`, токени стенда | «Завод 3D → Налаштування → Налаштування генератора» (X-69) і «… → Параметри системи»; compose |
| Автор `td_genset` | звіряє адаптер (ADP-xx), профіль D700 для `fake_relay.py`, REST для емулятора, регресію | репозиторій `td_genset`, гілка `19.0` |

Сценарії: (1) щоденно — показання генератора в 3D і в телеметрії; (2) блекаут — АВР/генератор,
картка GENSET і баланс енергії перемикаються в «острів», журнал подій; (3) тривога контролера —
заявка ТО в команду «Служба головного механіка» з показником і порогом; (4) ТО за мотогодинами —
планова заявка; (5) заправка — за інструкцією «Заправка» (`td_genset`), результат видно в сигналах
`fuel_l`/`autonomy_h`; (6) щотижневий тестовий пуск — сценарій `genset_test` емулятора на стенді.

### 1.3 Функціональні вимоги

Частина A — перенос `td_genset` (CR-01…CR-03, CR-09, CR-10):

| ID | Вимога |
|---|---|
| FR-A01 | `td_genset` встановлюється на Odoo 19.0 Enterprise з маніфестом `version 19.0.1.0.0` без помилок завантаження (XML, Python, assets). |
| FR-A02 | Усі 176 юніт-тестів `td_genset` проходять на 19.0 (теги `post_install`, `-at_install`), без `skip` через версію. |
| FR-A03 | Усі 45 стендових сценаріїв ТК-01…ТК-14 проходять на Docker-стенді з `fake_relay.py` (профіль офісу — як у ТР 1.2) і з профілем D700. |
| FR-A04 | Пульт (OWL) працює в 19.0: «Авто», старт/стоп, тест 3 хв, без `useService("rpc")`/`jsonrpc`. |
| FR-A05 | Групи `td_genset` оголошені через `res.groups.privilege`; права 111 користувачів проду після оновлення зберігаються (той самий набір груп на тих самих користувачах). |
| FR-A06 | `fake_relay.py` має профіль `d700` і REST-контракт API-F-01…API-F-09 (SPEC §8) за токеном; профіль офісу лишається за замовчуванням. |
| FR-A07 | `neutralize.sql` `td_genset` + `neutralize.sql` моста роблять копію проду безпечною: крони вимкнені, адреса ретранслятора порожня/стендова, токени нові. |
| FR-A08 | `relay_api.md` доповнено розділом «Емуляція» (API-F-xx), CHANGELOG — записом `19.0.1.0.0`, DEPLOY_TEST — кроками для 19.0. |

Частина B — міст `factory3d_genset`:

| ID | Вимога |
|---|---|
| FR-01 | Один запис зв'язки `f3d.genset.link` пов'язує генератор `td_genset` з `maintenance.equipment` `f3d_code='GENSET'` (роль паспорта `genset`); зв'язка створюється `post_init_hook`, якщо в `td_genset` рівно один генератор. |
| FR-02 | Профіль `f3d.genset.profile` «D700» із паспорта: бак 610 л, PRP 634 кВА / 507 кВт, ESP 697 / 558, витрата 38,6 / 71,2 / 103,8 / 136,4 л/год при 25 / 50 / 75 / 100 % PRP, 149,5 при 100 % ESP; інтерполяція витрати за навантаженням (R-01) і автономність (R-02). |
| FR-03 | Міст публікує 26 сигналів генератора в `f3d.signal` за кодами `infra/genset/GENSET/<leaf>` (SPEC Додаток A) через джерело `f3d.source` типу `td_genset` — локально, без колектора (тип оголошено локальним хуком telemetry `_f3d_local_types()`, CT-12/R-26; X-01), кроном раз на хвилину (або швидше за подією адаптера). |
| FR-04 | Міст не дублює тривог: пороги в `f3d.signal` генератора порожні; джерело тривог — контролер через `td_genset`; заявки ТО створює лише мапа подій `f3d.genset.event.map` (R-07) з дедуплікацією (R-08). |
| FR-05 | Аварійна зупинка (shutdown alarm) → `maintenance.request` `corrective`, пріоритет High, команда обладнання, текст з показником і порогом українською; попередження — за мапою (заявка або лише подія шини). |
| FR-06 | ТО за мотогодинами лишається в `td_genset` (єдине джерело правди); міст створює планову заявку `preventive` на дату «ТО через» за даними `td_genset` (R-09) і **не** заповнює `maintenance.equipment.f3d_meter_signal_id` (telemetry M-07 вимагає інтервал, а інтервал запустив би друге джерело ТО — SPEC §2.0.3 T-7). |
| FR-07 | Провайдер `f3d.viewer.provider.genset` (sequence 155; за префіксом, без `_inherit` — FR-17) віддає `infra.cards.GENSET` (рядки як у `plant/infra.py` + «Режим», «Мотогодини / до ТО», «Напруга · частота», «Зв'язок»), `infra.genset.GENSET` (значення сигналів) і `infra.totals.genset_kw/genset_state/genset_fuel_pct/genset_autonomy_h/island/grid_ok`; `factory3d_energy` картку GENSET не пише (CE-01), міст не пише `infra.totals.critical_kw` (CE-03, X-11); дельта `infra` — глибоким злиттям, без затирання ключів energy (SPEC R-13, X-23). |
| FR-08 | Зміна стану генератора, режиму, тривоги або острова → подія шини `f3d_viewer` (`model='maintenance.equipment'`, `codes=['GENSET']`, `kind='state'`) через `f3d.viewer.event._notify` (C-03), якщо `factory3d_viewer` встановлено (без нього — лише повідомлення в чаттері зв'язки); показання — без окремих повідомлень (їх дає телеметрія). |
| FR-09 | Острів визначається за ATyS p (сигнали energy `infra/ats/position`, `infra/ats/src1_ok`, `infra/ats/src2_ok`, коди — параметри), а без них — за показаннями контролера (`mains_ok`, `breaker`); у острові `infra.totals.grid_kw=0`, `export_kw=0`, `genset_kw=p_kw` (R-05, R-06). |
| FR-10 | Обидва варіанти логіки AMF (HGM6120N веде пуск і перемикання; ATyS p головний, HGM6120N в «Авто» за сигналом) підтримуються без зміни коду: параметр `factory3d.genset.amf_master` ∈ {`hgm`, `ats`} впливає лише на джерело `grid_ok`/`island` і рядок картки. |
| FR-11 | Критичні споживачі (кВт) для картки GENSET рахуються як сума сигналів `p_now` вузлів `f3d.energy.node` з `is_critical=True` (energy CE-04: LP-1…3, DUST-1, COMPRESSOR, BOILER, OFFICE, EF-ELEC, EF-CHG, лінія BW-1 — `plant/infra.py:CRITICAL`); параметр `factory3d.genset.critical_codes` — лише запасний (немає критичних вузлів); відсутні сигнали пропускаються й перелічуються в діагностиці; `infra.totals.critical_kw` пише energy, міст — ні (X-11). |
| FR-12 | Стоп-крани `factory3d.genset.read_enabled` (публікація в телеметрію), `factory3d.genset.requests_enabled` (заявки ТО), `factory3d.genset.write_enabled` (зарезервовано, міст команд не шле); умовчання за CB-10 (`environment`). |
| FR-13 | `neutralize.sql` моста вимикає крони моста й обнуляє `last_publish_ts`; `uninstall_hook` видаляє лише крони/параметри моста, не чіпає `f3d.signal`/`f3d.reading`/заявки. |
| FR-14 | Стенд: `docker-compose.sim.yml` піднімає `genset_relay` з профілем D700; сценарії `blackout` і `genset_test` емулятора ведуть послідовність у `fake_relay` через API-F-xx; в Odoo `td_genset` налаштований на `http://genset_relay:8000`. |
| FR-15 | Втрата зв'язку з ретранслятором довше `factory3d.genset.offline_min` (5 хв) → сигнал `online=0`, статус `stale` у всіх сигналах генератора (ставить сам міст через `_mark_stale` — крон stale telemetry локальних джерел не бачить, R-26; X-13), подія шини, заявка за мапою `COMM_LOST`. |
| FR-16 | Усі рядки інтерфейсу моста — українською в коді, без `.po` (D-14); технічні імена — англійською. |
| FR-17 | Міст не залежить від `factory3d_viewer` (`depends` за каркасом §3: `td_genset`, `factory3d_base`, `factory3d_telemetry`, `factory3d_energy`; X-20): встановлюється й працює без переглядача (публікація, події, заявки, ТО); провайдер — `AbstractModel` за префіксом `f3d.viewer.provider.` без `_inherit` (D-18, duck-typing viewer M-01), події шини — лише за наявності `f3d.viewer.event`, хелпер `deep_merge` viewer — лише в методі дельти (X-23). |

### 1.4 Межі: що не входить

- Будь-які зміни логіки `td_genset` (пульт, ескалація, паливо з каністрами, розклад, ТО, ролі) — D-12.
- Команди на генератор з моста (старт/стоп/«Авто») — лише пульт `td_genset`; стоп-кран
  `factory3d.genset.write_enabled` зарезервований і `False`.
- Опитування ATyS p по Modbus — `factory3d_energy` (P-07); міст лише читає сигнали `f3d.signal`.
- Баланс енергії в `infra.totals`/`energy.totals` (крім ключів `genset_*`, `island`, `grid_ok`) — `factory3d_energy`.
- Зовнішній паливний бак, облік палива в `stock` (бухгалтерія ПММ) — не в v1 (Q-05).
- Протокол CMM366B-4G ↔ ретранслятор — як в офісі; окремого колектора/плагіна не пишемо (A-02).
- J1939/ECU Doosan (HGM6120N без CAN) — дані двигуна лише з резистивних датчиків.

## 2. Технічна реалізація

### 2.1 Місце в системі

`__manifest__.py` `depends`: `td_genset`, `factory3d_base`, `factory3d_telemetry`, `factory3d_energy` — точно як
каркас v0.2 §3 (`factory3d_genset (міст) ← td_genset, factory3d_base, factory3d_telemetry, factory3d_energy`) і D-18 (X-20).
`factory3d_viewer` і `bus` **не** входять: переглядач — необов'язковий зв'язок (каркас §6.7) — провайдер за префіксом
`f3d.viewer.provider.genset` без `_inherit` (як energy A-04), події шини — лише за наявності `f3d.viewer.event`, хелпер
`deep_merge` — лише в методі дельти (A-18, FR-17); `maintenance` — транзитивно через `factory3d_base`. Залежність від
factory3d перенесено з `td_genset` у міст (A-01). Циклів немає: `factory3d_energy ← factory3d_telemetry ← factory3d_base`;
`td_genset` ні від чого з factory3d не залежить.

Що бере:

| Контракт | Звідки | Що саме |
|---|---|---|
| CB-01, CB-02 | `factory3d_base` | `maintenance.equipment.f3d_code='GENSET'`, `f3d_resolve('GENSET')`, кнопка «Показати в 3D» |
| CB-07, CB-08 | `factory3d_base` | паспорт ролі `genset` (`f3d_passport_id`), `f3d_get_num('kva')`, `('tank_l')`, `('fuel_lph_75')` — числа профілю з паспорта, якщо є в `spec_ids` |
| CB-09, CB-10 | `factory3d_base` | меню під `menu_f3d_root` (sequence 55, A-06), пункт «Налаштування генератора» під `menu_f3d_config` (sequence 55, правило X-32; X-69), групи `group_f3d_*`, `factory3d.base.environment` для умовчань стоп-кранів |
| C-6.4 (каркас), CT-10, CT-12 | `factory3d_telemetry` | `f3d.source` (тип додаємо `selection_add` і оголошуємо локальним хуком `_f3d_local_types()` — CT-12, R-26, X-01; `collector_id` не перевизначаємо), `f3d.signal` (`code`, `equipment_id`, `source_id`, `unit`, `kind`, `period_s`, `last_value`, `last_ts`, `status`), `f3d.reading`, `maintenance.equipment.f3d_meter_signal_id`, `maintenance.request.f3d_signal_id`/`f3d_equipment_code`; метод прийому показань CT-10 `_f3d_ingest`, `_mark_stale` |
| C-6.8 (каркас) | `factory3d_telemetry` | правило заявок ТО (поля, дедуплікація, тексти) |
| C-02, C-03, C-07 (необов'язково, X-20) | `factory3d_viewer` | хук провайдера за префіксом `f3d.viewer.provider.*` (duck-typing M-01, без `_inherit`), шина `f3d.viewer.event._notify` (M-03) — якщо модель є в реєстрі, хелпер `deep_merge` (M-01, X-23), шляхи сигналів у payload, Додаток A.13 `infra` (схема 1.1, X-24) |
| CE-02, CE-03, CE-04 | `factory3d_energy` | сигнали ATyS p у `f3d.signal` (P-07, Annexe III); `infra.totals` без ключів генератора, у т. ч. `critical_kw` і виміряні в острові `chp_kw`/`pv_now`/`bess_kw` (R-14 п. 9, X-10); критичні вузли `f3d.energy.node.is_critical` (X-11) |
| P-12, API-13 | `factory3d_iot_sim` | контейнер `genset_relay`, сценарії `blackout`/`genset_test` → API-F-xx |

Що віддає (ідентифікатори для інших SPEC: `td_genset CG-xx`):

| ID | Контракт | Споживач |
|---|---|---|
| CG-01 | Коди сигналів генератора `infra/genset/GENSET/<leaf>` (26, SPEC Додаток A), одиниці, kind, період 60 с; значення веде міст | `factory3d_telemetry` (каталог), `factory3d_iot_sim` (Додаток A — 1 довідковий рядок № 662 `infra/genset/GENSET/state`, X-62), `factory3d_viewer` |
| CG-02 | `infra.cards.GENSET`, `infra.genset.GENSET`, `infra.totals.genset_kw`, `genset_state`, `genset_fuel_pct`, `genset_autonomy_h`, `island`, `grid_ok` — пише **тільки** провайдер моста (sequence 155) | `factory3d_energy` (не пише GENSET), `factory3d_viewer` (CV-01) |
| CG-03 | REST `fake_relay` для емулятора: API-F-01…API-F-09 (`/sim/v1/state`, `/mains`, `/remote_start`, `/load`, `/fault`, `/clear`, `/fuel`, `/time`, `/reset`), токен `RELAY_SIM_TOKEN`, порт 8000, профіль `d700` | `factory3d_iot_sim` (сценарії `blackout`, `genset_test`; модель ATyS R-22) |
| CG-04 | Тип джерела телеметрії `td_genset` (локальне, без колектора — через хук `f3d.source._f3d_local_types()`, CT-12/R-26; X-01) і сигнали без порогів | `factory3d_telemetry` |
| CG-05 | Події шини `maintenance.equipment`/`GENSET`/`state` при зміні стану, режиму, тривоги, острова | `factory3d_viewer` |
| CG-06 | Заявки ТО генератора: `maintenance_for='equipment'`, `equipment_id=GENSET`, `f3d_signal_id`, `f3d_equipment_code='GENSET'`, `f3d_genset_event_key` | служба механіка, `factory3d_viewer` (`maintenance_requests`) |

Запити до інших модулів (фіксуються як їхні Q): CE-01 energy не пише `infra.cards.GENSET` і ключі
`genset_*`; CE-02 energy публікує `infra/ats/position` (0/1/2/3 за Annexe III ATyS p), `infra/ats/src1_ok`,
`infra/ats/src2_ok`, `infra/ats/gen_start` з реальних адрес 20482–20487 (не 20480…); CT-01 telemetry дає
метод прийому `f3d.signal._f3d_ingest(batch)` або еквівалент; CV-01 viewer у `backupSummary` показує
`genset_kw` і «генератор» для ATS-1, коли `infra.totals.island`; CI-01 iot_sim: параметр сценарію
`blackout` `amf_master` і виклики API-F-xx (рішення X-59: доповнює SPEC iot_sim); каталог iot_sim — 1 довідковий рядок генератора
(№ 662, X-62), повний перелік 26 кодів CG-01 — SPEC Додаток A моста.

### 2.2 Архітектурна схема

```
 Генератор D700 ── SmartGen HGM6120N ── CMM366B-4G ─4G─► ретранслятор замовника (API relay_api.md)
                         │ (у стенді: fake_relay.py, профіль d700, контейнер genset_relay:8000)
                         │                     ▲ REST /sim/v1/* (API-F-xx, токен)      ┌──────────────┐
                         ▼                     │                                        │ iot_sim      │
┌──────── Odoo 19 ─────────────────────────────┼────────────────────────────────────┐   │ сценарії     │
│  td_genset (як є): клієнт ретранслятора ─► показання, події, тривоги, пульт,     │   │ blackout,    │
│      паливо, ТО, розклад, ролі                                                   │   │ genset_test; │
│          │ ORM-читання через adapters/td_genset.py (ADP-01…10)                   │   │ модель ATyS  │
│          ▼                                                                       │   │ (R-22) ──────┼─► Modbus P-07
│  factory3d_genset (міст)                                                         │   └──────────────┘        │
│   ├─ f3d.genset.link ── maintenance.equipment GENSET (f3d_code, паспорт genset)  │                          ▼
│   ├─ f3d.genset.profile D700 (бак, крива витрати) ── R-01 витрата, R-02 автоном. │   collector ─► factory3d_energy
│   ├─ крон publish (60 с) ─► f3d.source[td_genset] / f3d.signal infra/genset/*    │        (сигнали infra/ats/*,
│   ├─ крон events ─► f3d.genset.event.map ─► maintenance.request (R-07, R-08)     │         баланс infra.totals)
│   ├─ крон service ─► планова заявка ТО за мотогодинами td_genset (R-09)          │               │
│   ├─ f3d.viewer.provider.genset (155) ─► infra.cards.GENSET, infra.genset,       │ ◄── читає f3d.signal
│   │        infra.totals.genset_*/island/grid_ok (R-05, R-06, R-10)               │
│   └─ f3d.viewer.event._notify('maintenance.equipment', ['GENSET'], 'state')      │
│                      ▼ /f3d/viewer/data, /delta, шина f3d_viewer                 │
│  factory3d_viewer: картка GENSET, вкладка «Енергія» (backupSummary)              │
└──────────────────────────────────────────────────────────────────────────────────┘
```

### 2.3 Нові й розширені об'єкти — огляд

| Модель | Тип | Призначення | Хто пише | Хто читає |
|---|---|---|---|---|
| `f3d.genset.link` | нова | зв'язка генератор `td_genset` ↔ `maintenance.equipment` GENSET; профіль; джерело телеметрії; стан публікації | `post_init_hook`, менеджер, крони | провайдер, крони |
| `f3d.genset.profile` | нова | профіль генератора (D700): потужності, бак, 5 точок витрати, таймери | data-файл, менеджер | R-01, R-02, `fake_relay` (експорт JSON) |
| `f3d.genset.event.map` | нова | мапа подій/тривог контролера → дія (заявка/подія шини/нічого), пріоритет, текст | data-файл (HGM6120N таблиці 4/5), менеджер | крон events |
| `f3d.source` | розширення | `type` += `td_genset` («td_genset (ретранслятор SmartGen)»), `_f3d_local_types()` += `td_genset` (CT-12, X-01) | міст | telemetry |
| `f3d.signal` | без полів | 26 сигналів GENSET (дані) | `post_init_hook` | telemetry, провайдер |
| `maintenance.equipment` | розширення | `f3d_genset_link_id` (one2one через one2many), кнопка «Генератор (td_genset)» | міст | форми |
| `maintenance.request` | розширення | `f3d_genset_event_key` (Char, index) для дедуплікації | крон events | крон events |
| `f3d.viewer.provider.genset` | нова (abstract, за префіксом **без** `_inherit`, X-20) | картка/тотали GENSET у payload, власна дельта `infra` з `deep_merge` (X-23) | — | viewer (якщо встановлено) |
| `res.config.settings` | розширення | стоп-крани й параметри моста | адміністратор | — |
| `td_genset.*` | **без змін** | генератор, показання, події, ТО, розклад | `td_genset` | адаптер (читання) |

### 2.4 Інтеграції

| Система | Протокол | Напрямок | Частота | При недоступності |
|---|---|---|---|---|
| Ретранслятор SmartGen (прод) / `fake_relay.py` (стенд) | HTTP API за `relay_api.md` (клієнт — `td_genset`, без змін) | ретранслятор → Odoo (показання, події); Odoo → ретранслятор (команди пульта) | як у `td_genset` (ЗВІРИТИ період; очікувано 30–60 с) | `td_genset` фіксує offline; міст: `online=0`, `stale`, подія, заявка `COMM_LOST` після `offline_min` |
| `factory3d_telemetry` | ORM локально (CT-01) | міст → `f3d.reading`/`f3d.signal` | 60 с (крон) | помилка запису → `last_publish_error`, повтор наступного циклу; без втрат (знімок `td_genset` лишається) |
| `factory3d_energy` (ATyS p, P-07) | `f3d.signal` (читання) | energy → міст | за energy (1–10 с) | без сигналів ATS острів визначається за контролером (R-05, варіант «без АВР у телеметрії») |
| `factory3d_viewer` (необов'язково, X-20) | хук C-02 за префіксом, шина C-03 | міст → viewer | на запит `/data`, `/delta`; події при зміні стану | провайдер у savepoint; падіння не ламає payload (viewer R-01); viewer не встановлено — провайдер ніхто не викликає, подій шини немає, решта моста працює (FR-17) |
| Емулятор `factory3d_iot_sim` | REST API-F-xx до `fake_relay` (CG-03) | iot_sim → `fake_relay` | за сценарієм | iot_sim Q-15: без відповіді `fake_relay` сценарій веде лише ATyS/баланс |

### 2.5 Потік даних від пристрою до екрана

#### 2.5.1 Показання (щохвилини)

1. Контролер HGM6120N → CMM366B-4G → ретранслятор → `td_genset` (клієнт, період `td_genset`): знімок показань
   і журнал подій у моделях `td_genset` (ролі «показання», «подія» — ЗВІРИТИ імена, ADP-03/ADP-04).
2. Крон `cron_f3d_genset_publish` (60 с): для кожного `f3d.genset.link` з `publish_enabled` і стоп-краном
   `read_enabled=True` → `adapters.td_genset.snapshot(link.td_genset_ref)` → dict ADP-03.
3. Обчислення: `load_pct = p_kw / profile.kw_prp · 100` (R-03), `fuel_l = fuel_pct/100 · tank_l` (якщо `td_genset`
   дає лише %), `fuel_lph = profile.fuel_lph(load_pct)` (R-01), `autonomy_h = fuel_l / fuel_lph` (R-02),
   `service_h_left` з ADP-06, `state`/`mode`/`breaker`/`alarm_level` → числові коди (R-03), `online`.
4. `adapters.telemetry.ingest(env, [{code, ts, value, q}])` → `f3d.reading` + `f3d.signal.last_value/last_ts/status`
   (CT-01). Лічильники (`kwh`, `hours`, `starts`) — як `kind='counter'`.
5. Зміна `state`/`mode`/`alarm_level`/`island` проти попереднього знімка (`link.last_state_json`) →
   `f3d.viewer.event._notify('maintenance.equipment', ['GENSET'], 'state')` (C-03), якщо `factory3d_viewer` встановлено
   (`'f3d.viewer.event' in env`; X-20).
6. `GET /f3d/viewer/data`: провайдер `telemetry` (95) кладе сигнали за шляхами (вузла `infra.genset` ще нема —
   пропускає, viewer M-01h); провайдер `infra` energy (150) заповнює `infra.totals` без `genset_*`; провайдер
   `genset` (155) будує `infra.genset.GENSET` зі значень `f3d.signal.last_value` (округлення R-11), картку
   `infra.cards.GENSET` (R-10), ключі `infra.totals.genset_*`, `island`, `grid_ok` (R-05).
7. Переглядач: `infraHtml("GENSET")` показує рядки картки; `backupSummary()` — рядок GENSET (CV-01: при
   `island` — `genset_kw` кВт і ATS «генератор»). `/delta`: провайдер має **власну** `_f3d_viewer_delta` (SPEC R-13, X-23): за
   змінами GENSET/`infra/genset/*`/`infra/ats/*`/критичних сигналів збирає свої ключі в тимчасовий dict і зливає в `patch["infra"]`
   спільним `deep_merge` viewer — ключі energy (`infra` 150) у дельті не затираються; сигнали — масивом `signals` від telemetry.

#### 2.5.2 Події й тривоги → заявки ТО

1. `td_genset` фіксує подію контролера (попередження/аварійна зупинка/зв'язок) і веде власну ескалацію (як є).
2. Крон `cron_f3d_genset_events` (120 с): `adapters.td_genset.events_since(link, link.last_event_ts)` → список
   ADP-04 `{id, ts, code, severity, name, value, text}`.
3. Для кожної події — рядок `f3d.genset.event.map` за `td_code` (точно) або `hgm_name` (регістронезалежно),
   інакше рядок `DEFAULT_<severity>`; дія `request_corrective` / `request_preventive` / `bus_only` / `ignore`.
4. Дедуплікація (R-08): ключ `f"GENSET:{map.key}"`; якщо є відкрита заявка з `f3d_genset_event_key` = ключ —
   нову не створюємо, лише `message_post` у наявну («Повтор: … о HH:MM»); інакше `maintenance.request`
   (`maintenance_for='equipment'`, `equipment_id`, `maintenance_team_id = equipment.maintenance_team_id`,
   `maintenance_type`, `priority`, `name` за шаблоном українською з показником і порогом, `f3d_signal_id` =
   сигнал `alarm_level`, `f3d_equipment_code='GENSET'`, `f3d_genset_event_key`, `description` з текстом
   події й посиланням на запис `td_genset`).
5. Подія шини `kind='maintenance'` (`model='maintenance.request'`) — її дає `factory3d_viewer` M-07 сам при
   `create`; міст додатково шле `state` для GENSET.
6. Закриття заявки (стадія `done`) → `f3d.signal.status` сигналу `alarm_level` → `ok`, якщо `alarm_level=0`
   у поточному знімку (інакше лишається, бо тривога триває) — перевизначення `write` на `maintenance.request`
   (R-08 крок 4).

#### 2.5.3 Блекаут: обидва варіанти логіки AMF (Q-01)

Загальне для обох: мережа зникає → СЕС (SUN2000) зупиняється (anti-islanding, статус `0x0303` в
емуляторі), КГУ — за фактом: в острові міст і energy беруть **виміряне** `infra/totals/chp_kw` (energy R-14 п. 9; X-10) —
зупинилась (захист від втрати мережі, блокування з ДГУ за паспортом `chp.note` п. 3) чи працює (опція PE/I) — вирішує
відповідь замовника/TEDOM (Q-02), код від неї не залежить; накопичувач тримає критичних споживачів на час пуску (картка BESS:
«резерв на пуск генератора», ≈ 51 хв на 348 кВт), генератор бере критичні споживачі (348 кВт з 507; за вирахуванням
виміряної КГУ, якщо вона працює — SPEC R-06), некритичні — скинуті (626 − 348 = 278 кВт). Міст бачить острів і перемикає картку/тотали (R-05, R-06).

**Варіант A — HGM6120N веде AMF (рекомендований, A-08):** HGM6120N стежить за мережею сам (вхід
мережі 3P4W), ATyS p у режимі *Remote control* (0x0020) виконує накази положення від виходів контролера
(«close relay» мережа/генератор; Switch Close Delay 5 с — імпульс). Послідовність (умовчання Table 7 /
заводський пресет Q-06 у дужках): t0 мережа втрачена → Mains Abnormal Delay 5 с (2) → Start Delay 1 с (0)
→ прокрутка ≤ 8 с, двигун запускається ≈ 3 с → Safety On 10 с (5) → Warming Up 10 с (3) → генератор у
нормі, Transfer Delay 1 с → ATyS у положення II ≈ t0 + 30 с (≈ t0 + 14 с з пресетом — відповідає
«10–15 с» картки ATS-1). Повернення: мережа в нормі → Mains Normal Delay 10 с → Stop Delay 1 с →
генератор відкрито, Transfer Delay 1 с → ATyS у положення I → Cooling 10 с → Stop Idle/ETS 20 с → очікування.
Сигнали моста: `mains_ok` з контролера; `breaker` (1 мережа / 2 генератор) з контролера; якщо energy
дає `infra/ats/position` — він пріоритетний для `island`.

**Варіант B — ATyS p головний, HGM6120N лише «Авто» за сигналом:** ATyS p у режимі *Auto*, `APP=M-G`,
стежить за джерелом 1 (мережа) і 2 (генератор) сам; контакт 71/74 → вхід «Remote Start» HGM6120N (як у
HGM6110: пуск за входом, контроль мережі контролера не керує перемиканням). Послідовність (умовчання
ATyS p): t0 → 1FT 3 с → наказ пуску (реле 20484 = 1) → HGM: Start Delay 1 с → прокрутка ≈ 3 с → Safety On
10 с → Warming Up 10 с → напруга/частота в нормі → ATyS 2AT 5 с → I → 0 (ODT 3 с) → II ≈ t0 + 35 с; якщо
джерело 2 не стало доступним за 2ST 30 с — повідомлення «FAIL START» (з умовчаннями HGM це на межі —
Q-06: 2ST ≥ 45 с або пресет HGM). Повернення: джерело 1 → 1RT 180 с → II → 0 → I → 2CT 180 с (генератор
працює без навантаження) → наказ пуску знято → HGM Stop Delay → Cooling 10 с → стоп. Сигнали моста:
`grid_ok` з `infra/ats/src1_ok`, `island` з `infra/ats/position == 3` (II); `mains_ok` контролера —
довідково (може бути «мережа є», коли ATyS уже перейшов на генератор за якістю мережі).

Вибір варіанта не змінює код моста: `factory3d.genset.amf_master` керує лише рядком картки «Логіка
AMF» і пріоритетом джерел `grid_ok`/`island` (R-05). В емуляторі варіант задає параметр сценарію
`blackout.amf_master` (CI-01): A — iot_sim викликає `POST /sim/v1/mains {"available": false}` у
`fake_relay`, модель ATyS iot_sim слідує за `breaker` з `GET /sim/v1/state`; B — модель ATyS iot_sim
веде таймери 1FT/2AT/1RT/2CT і викликає `POST /sim/v1/remote_start`, читаючи `gen_ok` для `src2_ok`.

### 2.6 Безпека

- Групи: нових груп міст не створює. Читання зв'язки/профілю/мапи — `factory3d_base.group_f3d_user`;
  зміна — `group_f3d_manager`; стоп-крани, джерело, `neutralize` — `group_f3d_admin`. Пульт і дані
  `td_genset` — його власні групи (CR-07: таблиця відповідності в SPEC §4.3, без злиття). Заявки ТО —
  стандартні права `maintenance`; крон працює від `OdooBot` (`user_id` крона) з `sudo()` лише для
  `ir.config_parameter` і створення заявок (коментар у коді з посиланням на R-07).
- Стоп-крани (`ir.config_parameter`, умовчання за CB-10): `factory3d.genset.read_enabled`
  (`environment=='test'` → `True`, `prod` → `False`), `factory3d.genset.requests_enabled` (`True`),
  `factory3d.genset.write_enabled` (`False`, зарезервовано — міст **ніколи** не викликає команди
  `td_genset`). `neutralize.sql` моста: крони `active=false`, `read_enabled=False`, `last_publish_ts=NULL`.
- Токени: міст токенів не має. `fake_relay` на стенді: `RELAY_SIM_TOKEN` (env контейнера, лише мережа
  `f3d_sim`), у логах не друкується; токен ретранслятора `td_genset` — як у ТР 1.2 (лише адмін).
- Заборонено: запис у `td_genset` з моста (крім `message_post`? — ні, і його не робимо; усі коментарі —
  у `maintenance.request`), зміна порогів контролера, прямий доступ до ретранслятора з моста.
- Вхідні дані адаптера (рядки подій) — лише текст: в `name`/`description` заявки екрануються стандартно
  (`html_escape` для `description`), коди подій — regex `^[A-Za-z0-9_.-]{1,64}$`, інакше `DEFAULT_*`.

### 2.7 Продуктивність і обсяги

- 26 сигналів × 1 440 хв = 37 440 `f3d.reading`/добу на генератор (ротація `factory3d.telemetry.keep_days`);
  агрегати `f3d.reading.hour` — telemetry. Крон publish: ≤ 2 запити до `td_genset`, один `ingest` пакетом.
- Події: ≤ 50 на добу; крон events читає лише `ts > last_event_ts`, ліміт 200 за прогін.
- Провайдер: 26 читань `f3d.signal` одним `search_read` (індекс `code`), ≤ 5 мс; картка ≤ 2 КБ.
- Індекси: `maintenance.request.f3d_genset_event_key` (btree), `f3d.genset.link.equipment_id` unique.

### 2.8 Міграція з демо-бази й деінсталяція

- Демо-база: сигналів генератора в `x_f3d_signal` немає (`x_f3d_signal_ids=[]` у GENSET), `x_*`-полів
  моста немає — мігрувати нічого. `post_init_hook`: (1) профіль D700 з data (ідемпотентно за `code`);
  (2) `f3d.source` `td_genset` «Ретранслятор SmartGen (td_genset)»; (3) 26 `f3d.signal` для
  `maintenance.equipment` з `f3d_code='GENSET'` (за `code` ідемпотентно; якщо GENSET немає — крок
  пропущено з записом у `factory3d.genset.migration_report`); (4) зв'язка, якщо `adapters.td_genset.
  generators(env)` повертає рівно 1 запис; (5) `f3d_meter_signal_id` і інтервал
  телеметрії не чіпаємо (SPEC §2.0.3 T-7); (6) звіт у параметр. Очікувано на копії демо: 1 профіль, 1 джерело, 26 сигналів, 0 або 1 зв'язка
  (залежить від даних `td_genset`), 0 заявок.
- Деінсталяція: `uninstall_hook(env)` вимикає/видаляє крони й параметри `factory3d.genset.*`; сигнали,
  показання, заявки, профілі лишаються (бізнес-дані); тип джерела `td_genset` у `f3d.source.type` зникає
  з селекції — `uninstall_hook` архівує джерело, після чого Odoo видаляє його за `ondelete="cascade"` (поле `type` обов'язкове
  без умовчання — інша політика неможлива, SPEC M-04); сигнали лишаються з `source_id=False`.
- `td_genset`: міграція даних 18 → 19 — стандартна (`odoo -u td_genset`), без скриптів `migrations/`,
  якщо чек-лист SPEC §A не виявить перейменувань (MG-08 `res.groups`: записи груп зберігають XML-id —
  користувачі не втрачають прав).

## 3. Налаштування системи

| Об'єкт | Параметр | Значення (тестовий сервер) | Коментар |
|---|---|---|---|
| `ir.config_parameter` | `factory3d.genset.read_enabled` | `True` | публікація в телеметрію; на проді після встановлення `False`, увімкнути після звірки з живим ретранслятором |
| `ir.config_parameter` | `factory3d.genset.requests_enabled` | `True` | заявки ТО з подій і за мотогодинами |
| `ir.config_parameter` | `factory3d.genset.write_enabled` | `False` | зарезервовано; міст команд не шле |
| `ir.config_parameter` | `factory3d.genset.amf_master` | `hgm` | `hgm` (варіант A) / `ats` (варіант B) — Q-01 |
| `ir.config_parameter` | `factory3d.genset.offline_min` | `5` | хвилин без оновлення знімка → `online=0`, `stale`, заявка `COMM_LOST` |
| `ir.config_parameter` | `factory3d.genset.ats_position_code` | `infra/ats/position` | код сигналу energy (CE-02); порожньо — не використовувати ATS |
| `ir.config_parameter` | `factory3d.genset.ats_src1_code` | `infra/ats/src1_ok` | — |
| `ir.config_parameter` | `factory3d.genset.ats_src2_code` | `infra/ats/src2_ok` | — |
| `ir.config_parameter` | `factory3d.genset.ats_position_i_value` / `ats_position_ii_value` | `2` / `3` (стенд і прод однаково; iot_sim §8.9.4 за X-41) | значення `infra/ats/position` для положень I / II (Annexe III ATyS p, energy CE-02), R-05 |
| `ir.config_parameter` | `factory3d.genset.critical_codes` | `energy/consumers/LP-1/p_now,energy/consumers/LP-2/p_now,energy/consumers/LP-3/p_now,energy/consumers/DUST-1/p_now,energy/consumers/COMPRESSOR/p_now,energy/consumers/BOILER/p_now,energy/consumers/OFFICE/p_now,energy/consumers/EF-ELEC/p_now,energy/consumers/EF-CHG/p_now,energy/lines/BW-1/p_now` | **запасний** список (X-11): основний — вузли energy `f3d.energy.node.is_critical` (CE-04); параметр діє, лише якщо критичних вузлів немає; склад — `plant/infra.py:CRITICAL` + лінія BW-1; відсутні пропускаються |
| `ir.config_parameter` | `factory3d.genset.publish_period_s` | `60` | інтервал крона publish (крон перечитує при старті) |
| `ir.config_parameter` | `factory3d.genset.migration_report` | `{}` | звіт `post_init_hook` |
| `f3d.genset.profile` | `D700` | бак 610 л; PRP 634/507; ESP 697/558; 38,6/71,2/103,8/136,4/149,5 л/год; `start_to_load_s=15`; таймери HGM умовчання + пресет `plant` | data-файл; числа паспорта |
| `f3d.genset.link` | GENSET ↔ генератор `td_genset` | 1 запис | `post_init_hook` або вручну менеджером |
| `f3d.genset.event.map` | 48 рядків (SPEC Додаток B): 17 warnings + 24 shutdown HGM6120N + `COMM_LOST`, `SERVICE_DUE`, `DEFAULT_WARNING`, `DEFAULT_SHUTDOWN`, `DEFAULT_COMM`, `DEFAULT_SERVICE`, `DEFAULT_INFO` | data-файл | колонка `td_code` заповнюється після звірки (Q-13) |
| `ir.cron` | `cron_f3d_genset_publish` / `_events` / `_service` | 1 хв / 2 хв / 1 день 06:00 Київ | `active` за `read_enabled`; `neutralize.sql` вимикає |
| `td_genset` | адреса ретранслятора, токен | `http://genset_relay:8000`, токен стенда | назви параметрів — як у ТР 1.2 (ЗВІРИТИ) |
| `td_genset` | розклад роботи | дві зміни за `plant/energy.py:day_profile` (ЗВІРИТИ формат) — Q-03 | дані, не код |
| `td_genset` | паливо: витрата | 103,8 л/год (еквівалент 75 %), якщо модель приймає сталу (CR-05) | Q-11 |
| compose `genset_relay` | `RELAY_PROFILE=d700`, `RELAY_SIM_TOKEN`, `RELAY_PORT=8000`, `RELAY_TIME_FACTOR=1` | профіль `dev`/`demo` | SPEC §8.5 |
| `factory3d_energy` | `infra/ats/*` | адреси ATyS p 20482–20487 | CE-02 |

## 4. Інструкція

**4.1 Підключити генератор до моделі заводу** (менеджер «Завод 3D»). 1) Обслуговування → Обладнання →
«Дизель-генератор» (код сцени `GENSET`, паспорт KOHLER-SDMO D700) — переконатися, що паспорт і зона
`Z-ENERGY` заповнені (base); 2) Завод 3D → Генератор → Зв'язка → «Створити»: обладнання `GENSET`,
генератор `td_genset` (список), профіль «D700»; 3) кнопка «Перевірити» — показує знімок (стан, кВт, паливо,
мотогодини) і результат запису в телеметрію; 4) Завод 3D → Телеметрія → Сигнали, фільтр `infra/genset/` —
26 сигналів з `last_ts` ≤ 2 хв; 5) Переглядач → об'єкт GENSET — картка з живими рядками.

**4.2 Блекаут на стенді** (адміністратор, тестувальник). 1) `docker compose --profile demo up -d iot_sim
mosquitto genset_relay`; 2) у `td_genset` адреса ретранслятора `http://genset_relay:8000`; 3) Обслуговування →
Емулятор → Сценарії → `blackout` → «Запустити» (параметри `duration_s=1800`, `amf_master=hgm`); 4) очікувано:
картка ATS-1 «Генератор», картка GENSET «Стан: під навантаженням · 348 кВт», `infra.totals.island=true`,
подія в журналі; 5) «Зупинити» → повернення на мережу, охолодження, «Стан: очікування».

**4.3 Тривога контролера → заявка ТО** (служба механіка). Заявка приходить у команду «Служба головного
механіка» з назвою «Генератор GENSET: <тривога> — <показник> при нормі <поріг>», пріоритетом і описом;
після усунення — стадія «Repaired»; якщо тривога ще активна, сигнал `alarm_level` лишається в статусі
`alarm`, і наступна подія знову відкриє заявку.

**4.4 «Робота поза графіком»** (адаптація інструкції `td_genset`; оператор генератора, диспетчер). Структура,
яку зберігаємо з існуючої інструкції: (1) коли дозволено пускати генератор поза розкладом (беремо з
інструкції замовника); (2) хто дає дозвіл (роль замовника — з інструкції); (3) дії на пульті `td_genset`
(«Авто» → ручний пуск/стоп) — без змін; (4) що фіксується (подія в `td_genset`, причина); (5) повернення
в «Авто». Заводські доповнення: (а) перед ручним пуском перевірити в картці GENSET «Критичні споживачі
зараз» і автономність; (б) якщо запущено на час блекауту — не вимикати до повернення мережі (`grid_ok` у
картці); (в) при тесті під навантаженням (сценарій `genset_test`) попередити зміну про перемикання АВР;
(г) запис про причину — у заявку ТО або в чаттер зв'язки (не вигадуємо процедуру замовника).

**4.5 «Заправка»** (адаптація інструкції `td_genset`; оператор, служба механіка). Структура з існуючої
інструкції: (1) коли заправляти (поріг рівня — із налаштувань `td_genset`); (2) як фіксувати заправку в
`td_genset` (каністри/об'єм — як є); (3) контроль після заправки (рівень у показаннях). Заводські
доповнення: (а) бак 610 л — за паспортом; при 75 % навантаження це ≈ 5,9 год повного бака, при 348 кВт
(68,6 %) ≈ 6,4 год; (б) рядок «Автономність» у картці GENSET — орієнтир для рішення про заправку під час
блекауту; (в) зовнішній паливний бак (Q-05) — поза v1; (г) місце зберігання палива, відповідальний,
облік — з інструкції замовника.

**4.6 Увімкнути на проді** (адміністратор). 1) `odoo -u td_genset,factory3d_genset`; 2) перевірити групи
користувачів `td_genset` (кількість користувачів у кожній групі до/після однакова); 3) `factory3d.base.
environment=prod`; 4) `factory3d.genset.read_enabled=True` лише після звірки показань з ретранслятором
(два знімки збігаються з пультом `td_genset`); 5) `requests_enabled=True`.

## 5. Ризики й відкриті питання

### 5.1 Відкриті питання (ті самі номери — SPEC §15)

| ID | Питання | Кому | Рекомендована відповідь | Що робимо тим часом |
|---|---|---|---|---|
| Q-01 | **Закрито 14.10 (відповідь № 1, CONSISTENCY):** варіант A — HGM6120N веде AMF, ATyS p у Remote control. Хто веде логіку мережа/генератор: HGM6120N (AMF) чи ATyS p (Advanced Integrated Logic)? (каркас §9 п. 1) | замовник, проєктувальник електропостачання | **Варіант A — HGM6120N веде AMF**, ATyS p у режимі Remote control (один контролер, один пульт `td_genset`, менше таймерів, що узгоджуються; HGM6120N уже стежить за мережею і керує ATS за мануалом). Варіант B тримати для випадку, коли проєктувальник вимагає власну логіку ATSE (M-G, таймери 1FT/1RT) — тоді 2ST ≥ 45 с | `amf_master=hgm`; код і емулятор підтримують обидва (§2.5.3) |
| Q-02 | **Закрито 14.10 (відповідь № 3, CONSISTENCY):** в острові — виміряні значення КГУ; карта ProCon — ПРИПУЩЕННЯ до документа TEDOM. Чи КГУ має опцію острівного режиму PE/I і чи може працювати паралельно з ДГУ? | замовник / TEDOM | на код не впливає: в острові беремо виміряні значення (X-10); відповідь потрібна для очікувань балансу на стенді й проді (CONSISTENCY «Питання до замовника» № 3) | R-06: `chp` в острові — **виміряне** `infra/totals/chp_kw` (energy R-14 п. 9; X-10); міст і energy нічого не підставляють |
| Q-03 | **Закрито 14.10 (відповідь № 5, CONSISTENCY):** тестовий пуск 15 хв раз на тиждень на початку зміни 1 (07:30); блекаут — без розкладу (AMF). Розклад роботи генератора на заводі (дві зміни? дозволені вікна тестів?) | замовник | тестовий пуск 15 хв раз на тиждень поза змінами (картка: «сьогодні 07:30»); блекаут — без розкладу (AMF) | розклад `td_genset` лишаємо офісний до відповіді; тест — `genset_test` |
| Q-04 | Назва методу прийому показань у `factory3d_telemetry` і чи створює telemetry заявку при `stale` | автор telemetry | `f3d.signal._f3d_ingest(batch)` (той самий, що й `POST /f3d/telemetry/push`); `stale` → лише статус, без заявки | **закрито** SPEC telemetry v0.1: CT-10 `_f3d_ingest`, `stale` заявок не створює (R-07); звірка — SPEC §2.0.3 |
| Q-05 | **Закрито 14.10 (відповідь № 5, CONSISTENCY):** у v1 зовнішнього бака немає (профіль 610 л); бак додається пізніше зміною `tank_l` профілю, без зміни коду. Зовнішній паливний бак (паспорт: «для довгих відключень») — чи купують, який об'єм, чи є датчик | замовник | 1 950 л (опція D700 за датасітом) з датчиком на той самий контролер — тоді профіль `tank_l` змінюється | профіль 610 л |
| Q-06 | **Закрито 14.10 (відповідь № 1, CONSISTENCY):** заводський пресет `plant`, підтвердити на ПНР. Заводський пресет таймерів HGM6120N (Mains Abnormal 2 с, Start 0, Safety On 5, Warming 3) і ATyS p (2ST 45 с) | замовник / пусконалагодження | пресет `plant` у профілі; підтвердити при ПНР | `fake_relay` профіль `d700` з умовчаннями Table 7 і пресетом `plant` (параметр) |
| Q-07 | Карта Modbus ATyS p в iot_sim §8.9.4 (20480 = position) не збігається з Annexe III (20483) | автор iot_sim/energy | **закрито (X-41):** iot_sim §8.9.4 і каталог № 426–428 → Annexe III (20482 режим, 20483 положення 1 = 0 / 2 = I / 3 = II, 20484 реле пуску, 20486/20487 стан джерел), як energy CE-02 | `ats_position_i_value=2`, `ii_value=3` без стендових винятків; міст читає коди сигналів, не адреси |
| Q-08 | **Закрито 14.10 (відповідь № 4, CONSISTENCY):** накопичувач від генератора не заряджається, в острові лише розряд; генерація — на секції 2. Чи накопичувач може заряджатися від генератора в острові | замовник / Huawei | ні (стрибки навантаження на ДГУ); режим «UPS на час пуску» | R-06: `bess_kw` в острові ≤ 0 (розряд) або 0 |
| Q-09 | Місце меню «Генератор» у `menu_f3d_root` — 55 не зарезервовано CB-09 | менеджер | **закрито (X-32):** base CB-09 резервує «55 genset» | A-06 |
| Q-10 | **Закрито 14.10 (рішення менеджера):** закривається розробником при перенесенні `td_genset` на 19 за репозиторієм (відповідь № 5г–д). **ЗВІРИТИ з td_genset:** імена моделей/полів: генератор, знімок показань (поля стан/режим/кВт/напруга/частота/струм/PF/кВт·год/паливо %/л/мотогодини/пуски/ОЖ/олива/АКБ/зарядне/обороти/тривоги/онлайн/ts), журнал подій (id/ts/code/severity/name/value/text), ТО (наступне ТО в мотогодинах, інтервал), розклад, останній тест | автор `td_genset` | заповнити константи `adapters/td_genset.py` (ADP-01…ADP-10); де поля немає — `None` і рядок картки «—» | тест `test_adapter_contract` падає, поки константи не підтверджені |
| Q-11 | **Закрито 14.10 (рішення менеджера):** закривається розробником при перенесенні `td_genset` на 19 за репозиторієм (відповідь № 5г–д). **ЗВІРИТИ:** модель палива `td_genset` — стала витрата чи крива? чи є «рівень у літрах»? | автор `td_genset` | якщо стала — записати 103,8 л/год; криву веде міст (R-01) | міст рахує `fuel_lph`/`autonomy_h` сам |
| Q-12 | **Закрито 14.10 (рішення менеджера):** закривається розробником при перенесенні `td_genset` на 19 за репозиторієм (відповідь № 5г–д). **ЗВІРИТИ:** групи `td_genset` (XML-id, ієрархія), чи є `category_id` у XML груп (MG-08) | автор `td_genset` | таблиця відповідності SPEC §4.3 | — |
| Q-13 | **Закрито 14.10 (рішення менеджера):** закривається розробником при перенесенні `td_genset` на 19 за репозиторієм (відповідь № 5г–д). **ЗВІРИТИ:** коди подій/тривог у `td_genset` (як іменовані: за мануалом HGM чи власні), ознака severity | автор `td_genset` | заповнити `td_code` у 41 рядку мапи | мапа працює за `hgm_name` + `DEFAULT_*` |
| Q-14 | **Закрито 14.10 (рішення менеджера):** закривається розробником при перенесенні `td_genset` на 19 за репозиторієм (відповідь № 5г–д). **ЗВІРИТИ:** `fake_relay.py` — порт, формат профілю, чи є команди «втрата мережі»/«несправність» (iot_sim Q-15) | автор `td_genset` | якщо є — узгодити імена з API-F-xx; якщо нема — додати за SPEC §8 | — |
| Q-15 | **Закрито 14.10 (рішення менеджера):** закривається розробником при перенесенні `td_genset` на 19 за репозиторієм (відповідь № 5г–д). **ЗВІРИТИ:** період опитування ретранслятора `td_genset`, ознака offline і її таймаут | автор `td_genset` | `offline_min=5` ≥ 3 періоди | — |
| Q-16 | **Закрито 14.10 (рішення менеджера):** закривається розробником при перенесенні `td_genset` на 19 за репозиторієм (відповідь № 5г–д). **ЗВІРИТИ:** стоп-крани `td_genset` (імена параметрів `read/write`), `neutralize.sql` — що саме обнуляє | автор `td_genset` | узгодити з CB-10 (`environment`) | — |
| Q-17 | **Закрито 14.10 (рішення менеджера):** закривається розробником при перенесенні `td_genset` на 19 за репозиторієм (відповідь № 5г–д). **ЗВІРИТИ:** чи створює `td_genset` `maintenance.request` або має власну модель ТО | автор `td_genset` | якщо створює — міст лише додає `f3d_*` поля до його заявок (R-09 варіант б), не дублює | R-09 варіант а (міст створює) |
| Q-18 | **Закрито 14.10 (рішення менеджера):** закривається розробником при перенесенні `td_genset` на 19 за репозиторієм (відповідь № 5г–д). **ЗВІРИТИ:** як `td_genset` зберігає «останній тестовий пуск» і результат | автор `td_genset` | рядок «Остання перевірка» картки | рядок «—» |
| Q-19 | **Закрито 14.10 (рішення менеджера):** закривається розробником при перенесенні `td_genset` на 19 за репозиторієм (відповідь № 5г–д). **ЗВІРИТИ:** OWL-пульт — які сервіси використовує (`rpc`, `orm`, `jsonrpc`), чи є `type='json'` контролери для ретранслятора | автор `td_genset` | MG-20…MG-24 | — |
| Q-20 | `factory3d_telemetry` v0.1: чи дозволяє telemetry локальне джерело модуля (`type='td_genset'`) без колектора і з порожніми `params`; чи `f3d.signal._f3d_ingest(src='module')` і `_mark_stale` — підтримуваний вхід для модулів | автор telemetry | **закрито (X-01):** telemetry CT-12 `f3d.source._f3d_local_types()` і R-26 — колектор не обов'язковий для локальних типів, `validate_params` з `local_types` → `[]`, API-01 і крони R-07/R-25 їх не бачать, показання — CT-10 | міст розширює хук (`super()._f3d_local_types() + ['td_genset']`) і **не** перевизначає `collector_id` (SPEC M-04, §2.0.3 T-1); AC-01, AC-50, AC-69 |
| Q-21 | `factory3d_iot_sim` CI-01: параметри S-03 `blackout` (`amf_master`, `genset_load_kw`) і S-14 `genset_test` (`test_on_load`), оркестрація генератора через API-F-xx замість власних таймерів R-22 (20520/20521) | автор iot_sim | **закрито (X-59):** параметри доповнює SPEC iot_sim (S-03, S-14, §8.14, R-22 з API-F-01…09); у мосту без змін | до правки iot_sim стендовий оркестратор `tests/stand/orchestrator.py` виконує послідовність SPEC §8.6 сам (SPEC §13.3.0) |
| Q-22 | **Закрито 14.10 (відповідь № 5, CONSISTENCY):** команди D700 за умовчанням вимкнено (стоп-кран); вмикає адміністратор після підписаного протоколу етапу 4 §13.6. Дистанційні команди D700 на заводі: чи дозволено пуск/стоп з пульта `td_genset`, хто — відповідальна особа на об'єкті при першому пуску, вікно для тесту під навантаженням через АВР | замовник (головний енергетик, служба охорони праці) | команди лише після підписаного протоколу етапу 4 SPEC §13.6; перший пуск — «Тест 3 хв» без навантаження у присутності чергового електрика з допуском і доступом до аварійної кнопки | на проді стоп-кран команд `td_genset` вимкнено; міст команд не має (FR-12) |
| Q-23 | `factory3d_viewer` Додаток A.13: додати вузол `infra.genset` і ключі `infra.totals.genset_kw/genset_state/genset_fuel_pct/genset_autonomy_h/island/grid_ok` (разом з CV-01) | автор viewer | **закрито (X-24):** схема `meta.schema="1.1"` приймає додаткові ключі модулів адитивно (каркас §6.7), перелік — viewer Додаток A | провайдер пише ключі; `genset_kva` — `int` за A.13; `critical_kw` міст не пише (X-11); до оновлення viewer Додатка A — AC-22 «блокер X-24» лише з рішенням менеджера |
| Q-24 | **Закрито 14.10 (відповідь № 5, CONSISTENCY):** оновлення `td_genset` 18 → 19 — у рамках розробки (репозиторій — вхідні дані, пункти «ЗВІРИТИ» закриває розробник); платформа прод-бази — у погоджене вікно, спершу на копії; одна база. Оновлення платформи прод-бази 18 → 19 (Odoo Upgrade, Enterprise): коли, хто, чи `td_genset` і factory3d на одній базі | менеджер, замовник | одна база; оновлення платформи у вікно, погоджене з замовником, спершу на копії (SPEC §13.6 етап 2) | DEPLOY_TEST етапи 0–2 на копіях; етапи 3–4 (прод) не починаються |

Від замовника потрібно: доступ до репозиторію `td_genset` (гілка 18.0, теги `18.0.2.0.2`), ТР 1.2, SPEC,
`relay_api.md`, `fake_relay.py`, DEPLOY_TEST.md, інструкції; відповіді Q-01…Q-03, Q-05, Q-06, Q-08, Q-22, Q-24.

### 5.2 Ризики

| Ризик | Вплив | Пом'якшення |
|---|---|---|
| Внутрішні імена `td_genset` відрізняються від припущень адаптера | міст не збирається/не читає | усі звернення — в одному файлі адаптера; `test_adapter_contract` на `fields_get`; CR-04 |
| Перенос 18 → 19 зачепить OWL-пульт (видалений `rpc`-сервіс, `jsonrpc`) | пульт не працює | MG-20…MG-24 з перевірками; ТК пульта в регресії |
| Групи `res.groups` без `privilege_id` не завантажаться в 19 (`category_id` відсутній) | модуль не оновиться на проді | MG-08 перед усім іншим; тест кількості користувачів у групах |
| Подвійні тривоги (telemetry пороги + `td_genset`) | спам заявок | пороги в сигналах генератора порожні (A-05); дедуплікація R-08 |
| Два джерела правди ТО | розбіжні дати ТО | ТО веде `td_genset`; telemetry-інтервал не ставимо (A-04) |
| Карта ATyS p в iot_sim розходилась з Annexe III (20480 vs 20483) | острів не визначається від АВР | X-41: iot_sim переходить на Annexe III (Q-07 закрито); запасне визначення острова за контролером (R-05) |
| `fake_relay.py` без команд емуляції | сценарій `blackout` не веде генератор | CR-02 додає API-F-xx; iot_sim Q-15 запасний режим «генератор запущений через 15 с» |
| 2ST 30 с ATyS p < час пуску з умовчаннями HGM | «FAIL START» у варіанті B | Q-06: пресет або 2ST 45 с; ТК-G04 перевіряє |
| Обсяг показань (37 тис./добу) у PostgreSQL | ріст таблиці | ротація telemetry; період 60 с; D-11 |
| SPEC `factory3d_telemetry` v0.1 розходиться з припущеннями моста (`collector_id` обов'язковий, `create_request=True` за замовчуванням, `f3d_meter_signal_id` вимагає інтервал, `q='bad'` не дає `stale`) | дублі заявок, джерело не створюється, хибний ТО | рішення A-15 (SPEC §2.0.3 T-1…T-10); локальне джерело — хук CT-12 `_f3d_local_types()` (X-01, Q-20 закрито); `test_adapter_contract` перевіряє telemetry-контракт |

## 6. План сборки агентами

| Воркер | Межі файлів | Здає | Залежить від |
|---|---|---|---|
| W0 (каркас) | `odoo_addons/factory3d_genset/__manifest__.py`, `__init__.py`, `security/ir.model.access.csv`, порожні `models/__init__.py`, `adapters/__init__.py` з сигнатурами ADP-01…ADP-10 і константами «ЗВІРИТИ», `data/ir_config_parameter.xml`, `neutralize.sql`, `README.md`, `CHANGELOG.md` | модуль встановлюється на копію демо-бази поруч з `td_genset` 19.0; адаптер віддає `NotImplementedError` з текстом «звірити ADP-xx» | `td_genset` 19.0 (W1) |
| W1 (перенос `td_genset`) | репозиторій `td_genset`, гілка `19.0`: усе за чек-листом SPEC §A (MG-01…MG-32); `adapters/td_genset.py` моста — заповнення констант після звірки (ADP); `relay/profiles/d700.json`; CHANGELOG, DEPLOY_TEST | 176 UT зелені на 19.0; модуль ставиться на копію проду після `neutralize.sql`; таблиця відповідності імен (Q-10…Q-19) у `docs/modules/td_genset/ADAPTER_MAP.md` | — |
| W2 (міст: дані й телеметрія) | `models/genset_link.py`, `genset_profile.py`, `genset_event_map.py`, `f3d_source.py`, `maintenance_equipment.py`, `maintenance_request.py`, `res_config_settings.py`, `adapters/telemetry.py`, `data/f3d_genset_profile.xml`, `data/f3d_genset_event_map.xml`, `data/ir_cron.xml`, `hooks.py`, `tests/test_rules.py`, `test_publish.py`, `test_events.py`, `test_service.py`, `test_adapter_contract.py` | M-01…M-07, R-01…R-04, R-07…R-09, R-12, крони, AC типу UT | W0, W1 (адаптер) |
| W3 (міст: переглядач і представлення) | `models/viewer_provider.py`, `views/*.xml`, `views/menus.xml`, `tests/test_provider.py`, `tests/test_no_viewer.py`, `tests/test_views.py` | M-08, V-01…V-08, R-05, R-06, R-10, R-11, R-13, CG-02, CG-05; провайдер за префіксом без `_inherit`, власна дельта з `deep_merge` (A-18) | W0, W2 (поля) |
| W4 (стенд: `fake_relay` D700 + REST + compose) | у `td_genset`: `relay/fake_relay.py` (профіль, стан-машина HGM, API-F-01…09), `relay/profiles/d700.json`, `relay/Dockerfile`, `relay_api.md` розділ «Емуляція»; у factory3d: PR до `services/iot_sim/docker-compose.sim.yml` (env `genset_relay`) | API-F-xx з тестами `relay/tests/test_sim_api.py`; `docker compose --profile demo up` піднімає `genset_relay` | W1 |
| W5 (тестувальник) | `tests/stand/*` моста, матриця регресії `td_genset` (ТР 1.2 AC-01…AC-69 ↔ тести), `docs/modules/td_genset/TEST_REPORT.md`, DEPLOY_TEST | §13.2 регресія (176 UT + 45 ТК, ТР 1.2 AC-01…AC-69), ТК-G01…ТК-G13, ТК-F01…ТК-F07, ТБ-01…ТБ-10, ТП-01…ТП-06, DEPLOY_TEST §13.6 | W1–W4 |

Порядок злиття: W1 → W0 → (W2 ‖ W4) → W3 → W5. Інтерфейс між W1 і W2 — сигнатури ADP-01…ADP-10 (SPEC §2.0),
фіксуються W0 першим комітом; W1 заповнює тіла. Інтерфейс між W4 і iot_sim — API-F-xx (CG-03).

## 7. Рішення автора (A-xx)

| ID | Рішення | Обґрунтування | Що змінює відносно каркаса |
|---|---|---|---|
| A-01 | Усе заводське — в окремому модулі `factory3d_genset`; `td_genset` не отримує залежностей від factory3d | D-12 «як є»; `td_genset` стоїть на проді в офісі без factory3d | §3: `td_genset ← … + factory3d_base, factory3d_energy` → `factory3d_genset ← td_genset, factory3d_base, …` |
| A-02 | Без колектора й плагіна `relay_genset`: показання вже в Odoo, міст пише в телеметрію локально через `f3d.source` типу `td_genset` | дублювати опитування ретранслятора колектором — другий клієнт і друге джерело | §6.5 рядок `relay_genset` = клієнт `td_genset`, не плагін колектора |
| A-03 | **Вилучено (X-20)** — замінено A-18. Було: залежність від `factory3d_viewer` явна (`depends`), провайдер — `_inherit` абстрактної моделі viewer | каркас v0.2 §3 і D-18: жорсткі `depends` лише за §3, viewer необов'язковий (§6.7) | — |
| A-04 | ТО за мотогодинами веде `td_genset`; telemetry-інтервал (`f3d_meter_signal_id` + інтервал) не задається; міст створює планову заявку за даними `td_genset` | одне джерело правди; `td_genset` уже має інтервали й регламент замовника | §6.4 «ТО за лічильником» для GENSET не використовується |
| A-05 | Пороги в `f3d.signal` генератора порожні; тривоги — лише з контролера через мапу подій | контролер має власні пороги (Table 7), `td_genset` — ескалацію; третій набір порогів дав би подвійні заявки | §6.4 «пороги → заявка» для GENSET замінено на «події → заявка» (§6.8 дотримано) |
| A-06 | Меню «Генератор» під `menu_f3d_root` з sequence 55; «Налаштування генератора» — під `factory3d_base.menu_f3d_config` з тим самим sequence 55 (X-32, X-69) | слот «55 genset» резервує base CB-09 (X-32; Q-09 закрито) | CB-09 |
| A-07 | Провайдер `f3d.viewer.provider.genset` sequence **155**, не 150 | viewer сортує за `(sequence, name)`: при 150 `…genset` ішов би перед `…infra` і energy затирав би картку; 155 гарантує, що картка/тотали генератора записуються після energy | C-02 (`td_genset`/`factory3d_energy` (`infra` 150)) |
| A-08 | Рекомендований варіант AMF — HGM6120N веде (варіант A); обидва реалізовані | один контролер, один пульт, менше узгоджень таймерів | §9 п. 1 (Q-01 відкрите) |
| A-09 | Усі звернення до `td_genset` — через `adapters/td_genset.py` (ADP-01…ADP-10); жодних `_inherit` моделей `td_genset` | імен не знаємо; зміни `td_genset` заборонені; адаптер — єдине місце звірки | — |
| A-10 | Стан генератора — числовий enum 0…10 у `f3d.signal` (`kind='gauge'` — уточнено A-15, бо `kind='state'` у telemetry текстовий), текст — у провайдері | `last_value` сигналу числове; переглядач отримує текст з картки | C-07 |
| A-11 | Коди сигналів `infra/genset/GENSET/<leaf>` (не `equipment/GENSET/<leaf>`) | P-12 iot_sim уже посилається на `infra/genset/GENSET/state`; картка GENSET живе в `infra` | §5 конвенція шляхів (новий префікс `infra/genset/`) |
| A-12 | Дедуплікація заявок — за ключем події (`f3d_genset_event_key`), а не лише за сигналом | усі тривоги прив'язані до одного сигналу `alarm_level`; §6.8 «одна відкрита заявка на сигнал» дала б одну заявку на всі тривоги | уточнення §6.8 |
| A-13 | Витрата палива нижче 25 % = 38,6 л/год (константа), вище 100 % PRP — лінійно до 149,5 при 110 % (ESP) | даних нижче 25 % у датасіті немає; ESP 558 кВт = 110 % PRP | — |
| A-14 | `fake_relay` отримує REST керування `/sim/v1/*` (той самий префікс, що в емуляторі) і профіль JSON | один стиль з iot_sim; профіль експортується з `f3d.genset.profile` | P-12 |
| A-15 | Звірка з SPEC `factory3d_telemetry` v0.1 (SPEC §2.0.3 T-1…T-10): джерело `GENSET-RELAY` без колектора — **лише** через хук telemetry `f3d.source._f3d_local_types()` (CT-12, R-26; M-04 додає `td_genset` через `super()`, `collector_id` і constraint на колектор не перевизначає — X-01), `_f3d_ingest(src='module')` з `q='good'`, `stale` ставить сам міст через `_mark_stale` (крон stale telemetry локальних джерел не бачить — X-13), `create_request=False` і поріг лише на `alarm_level`, `kind='gauge'` для кодів, `period_s=max(60, offline_min·20)` (довідковий), `store_period_s=0`, `f3d_meter_signal_id` не заповнюється | telemetry з'явився пізніше за SPEC моста; без цього — дублі заявок і хибний ТО | A-04, A-05, A-10 уточнено; Q-04 і Q-20 закрито |
| A-16 | Мапа подій — 48 рядків (17 Table 4 + 24 Table 5 + 7 службових), збіг за `hgm_name` **разом з** `severity` (8 назв є в обох таблицях); `DEFAULT_COMM`/`DEFAULT_SERVICE` — лише подія шини (заявки дають R-12 `COMM_LOST` і R-09); стан 7 — також за `p_kw ≥ 5 % PRP` (варіант B AMF) | без цього — неоднозначний збіг і дубль заявок ТО/зв'язку; у варіанті B реле HGM не задіяне | SPEC M-03, R-03, Додаток B, Додаток D.3 |
| A-17 | Стендові сценарії моста нумеруються ТК-G01…, сценарії `fake_relay` — ТК-F01…; AC `td_genset` у тексті — «ТР 1.2 AC-xx» | ТК-01…ТК-14 і AC-01…AC-69 уже зайняті ТР 1.2, ТК-01…ТК-16 — iot_sim | SPEC §12, §13 |
| A-18 | Провайдер `f3d.viewer.provider.genset` — `AbstractModel` за префіксом без `_inherit` з усіма атрибутами duck-typing viewer M-01; власна `_f3d_viewer_delta` зливає ключі моста в `patch["infra"]` спільним `deep_merge` viewer (імпорт усередині методу); події шини — лише за `'f3d.viewer.event' in env` (SPEC M-08, R-13) | X-20, X-23: міст ставиться без viewer (каркас §3, D-18); базова дельта viewer копіювала б `infra` цілком і затирала ключі energy (A-22) | каркас §6.7 дотримано; замінює A-03 |

## 8. Джерела

- Каркас `docs/ARCHITECTURE.md` v0.2 (14.10.2026): §2, §3, §5, §6.1–6.8, §8 D-12, D-17, D-18, D-21, D-23, §9 п. 1;
  реєстр розбіжностей `docs/CONSISTENCY.md` v0.3 (X-01, X-10, X-11, X-13, X-20, X-23, X-41, X-62; також X-24, X-32, X-59).
- `docs/DOC_STANDARD.md`; `docs/modules/factory3d_base/SPEC.md` (CB-01…CB-12, Додатки C, E, F);
  `docs/modules/factory3d_viewer/SPEC.md` (M-01, M-01h, M-03, R-01, R-14, API-02, Додатки A.13, C);
  `docs/modules/factory3d_telemetry/SPEC.md` (M-02, M-03, CT-10, CT-12, R-07, R-26); `docs/modules/factory3d_energy/ARCHITECTURE.md`,
  `SPEC.md` (CE-01…CE-04, A-04, A-22, R-14, R-18);
  `docs/modules/factory3d_iot_sim/ARCHITECTURE.md`, `SPEC.md` (§8.1.3–8.1.4, §8.4, §8.9.4, §8.14, §8.15, API-13, Q-07, Q-15).
- SmartGen, «HGM6100N Series Genset Controller User Manual» (HGM6110N/6120N/…/6120CAN), smartgen.cn, переглянуто 14.10.2026.
- Socomec, «ATyS p Automatic Transfer Switching Equipment — Instruction manual», 542 001 D (NHP mirror), переглянуто 14.10.2026.
- SDMO/KOHLER, «D700 datasheet» (Doosan DP180LB): Consumption @ 100 % ESP 149,50; @ 100 % PRP 136,40; @ 75 % PRP 103,80;
  @ 50 % PRP 71,20 L/h; Tank capacity 610 L (опція 1 950 L); Oil system 34 L; Min. oil pressure 0,50 bar —
  https://assets.serverroomenvironments.co.uk/assets/files/65/82/01/sdmo-d700-generator-datasheet.pdf, переглянуто 14.10.2026.
- Doosan, «DP180LB engine spec» (50 Hz, 1500 rpm): fuel consumption 25/50/75/100 % = 38,6 / 71,2 / 103,8 / 136,4 L/h —
  https://bnhgenerators.com/wp-content/uploads/2022/02/DP180LB-engine-spec-1.pdf, переглянуто 14.10.2026.
- Odoo 19.0: `odoo/documentation` «ORM changelog» (19.0: deprecated `odoo.osv`, `record._cr/_context/_uid`; 18.2: `read_group`
  deprecated → `_read_group`/`formatted_read_group`; 18.1: `odoo.Domain`, constraints/indexes як атрибути моделі, контролери
  `json` → `jsonrpc`; 18.0: `_search_display_name`, `check_access`/`has_access`); `odoo/odoo` 19.0 `res_groups.py`
  (`privilege_id`, `models.Constraint`), `res_groups_privilege.py`, `res_users.py` (`group_ids`), `ir_cron.py`
  (без `numbercall`/`doall`, `failure_count`), `ir_ui_view.py` (`type` без `tree`); переглянуто 14.10.2026.
- Сторонні огляди міграції 18 → 19 (звірити з кодом): cybrosys.com «how to migrate custom modules from odoo 18 to odoo 19»;
  deploymonkey.com «odoo 19 breaking changes»; octurasolutions.com «privilege system: category_id → privilege_id».
