# td_chp — технічне рішення

Версія 0.1 · 20.10.2026 · автор: агент (крок 1 циклу) · статус: чернетка, на погодженні. Специфікація — [SPEC.md](SPEC.md) (ID `D-xx`, `M-xx`, `V-xx`, `API-xx`, `R-xx`, `AC-xx` — звідти); міст із заводом — [td_chp_factory3d](../td_chp_factory3d/SPEC.md).

## Загальна інформація

| Етап | Статус | Люд./год (оцінка) |
|---|---|---|
| Технічне рішення (ТР) | цей документ + SPEC | 10 |
| Архітектура | §2 | 6 |
| Розробка | W1 бекенд 36, W2 пульт 40, W3 емулятор і міст 32 | 108 |
| Тестування | UT/UT-JS/UT-E 24, стенд ТК-01 6 | 30 |
| Інструкція | §4 | 4 |

## 1. Опис процесу і функціональні вимоги

### 1.1 Контекст: що вже є
- **Мокап «Пульт КГУ»** — `factory3d/build/chp/mockup/`: `a_head.html` (розмітка, CSS, 37 вузлів у 8 системах, 2 вкладки), `b_sim.js` (модель величин `step()`/`computeV()`, 37 карток вузлів `NODES`, пуск з 9 кроків, 14 блокувань, аварії, журнал, ТО, діагностика 16 циліндрів), `c_3d.js` (three.js r147, лише примітиви), `d_scheme.js` (6 шарів мнемосхеми). Він же — основа карти регістрів (SPEC §5.2, колонка «мокап»).
- **Енергетика (td_energy, td_energy_control).** Вузли `CHP` (генерація, 800 кВт) і `QF-CHP` (`odoo_addons/td_energy/data/energy_nodes.csv`), джерело `MB-U72-CHP` (Modbus u72), сигнали `infra/chp/{state,heat_kw,gas_m3h,hours,kwh_total}` і `infra/totals/chp_kw` (`energy_signals.csv`); види команд `chp_start`/`chp_stop` (клас B, `td_energy_command_kind_data.xml`), вікно команд контролера ГРЩ u73 (230–233: `energy_control/chp/{cmd,ack,permit,gas_bar}`); сценарій автоматики `chp` («зрізання піку»). Тепло КГУ в BMS (`td_bms`, тепловий баланс) бере `infra/chp/heat_kw` — не дублюємо.
- **Емулятор.** `services/iot_sim/iot_sim/models/chp.py` (резерв/пуск 60 с/охолодження 60 с, P 400/800 кВт, тепло 497/856, газ 109/199, `GAS_MIN_BAR=1,5`), `protocols/modbus_maps/tedom.py` (u72: 40000–40020), сценарій S-20 `chp_no_gas`.
- **Прецедент «продукт + міст».** `td_genset` + `td_genset_factory3d` (docs/modules/td_genset).

### 1.2 Ролі й сценарії
| Роль (група) | Що робить | Де |
|---|---|---|
| Користувач (`group_td_chp_user`) | дивиться пульт, журнал, ТО | «Когенерація → Пульт КГУ» |
| Енергетик (`operator`) | готує й підтверджує команди (клас A — одноосібно; клас B — 1/2), квитує аварії, відмічає ТО | пульт |
| Головний енергетик (`chief`) | виконує клас B одноосібно або дає 2/2 | пульт, картка «Очікує другого підтвердження» |
| Інженер КіП (`td_factory3d.group_td_manager`) | паспорт, карта регістрів, джерело, пороги; кнопки «Імітація» | «Паспорт», «Карта регістрів» |
| Адміністратор (`group_td_admin`) | стоп-крани, токени колектора | «Налаштування» |

### 1.3 Функціональні вимоги
| FR | Вимога | AC |
|---|---|---|
| FR-01 | Паспорт агрегата з параметрами й порогами; за замовчуванням TEDOM Quanto D800, V16, позначка «типова комплектація, допущення» | 01 |
| FR-02 | Типова карта з 230 сигналів `chp/…`, на кожен адреса, тип, множник, одиниця, період, пороги редагуються в Odoo; `code` незмінний | 02, 03, 26 |
| FR-03 | Пульт показує живий стан із `td.signal`: JSON-маршрут стану, шина `td_chp`, резервне опитування, ознака застарілості | 04, 05, 20 |
| FR-04 | 3D-модель контейнера (37 вузлів, 8 систем, 3 режими корпусу), three.js — власна копія, лише в дії, без залежності від td_viewer3d | 21, 22 |
| FR-05 | Мнемосхема з 6 шарів за системами | 22 |
| FR-06 | 14 плиток KPI (ККД, CO₂ тощо) і тренд P/Q/газ за 24 год і 1 год | 06, 17 |
| FR-07 | Діагностика: 16 циліндрів (відхилення, детонація, пробій, іскра, свічка) і 22 допоміжні системи | 07, 22 |
| FR-08 | Команди: пуск, стоп, аварійний стоп, режим, уставка P, cos φ, напрямок тепла, заслінка вихлопу, скидання аварії — з підтвердженням, блокуваннями (14 умов), верифікацією й записом у журнал | 10–15 |
| FR-09 | Клас і підтвердження пуску/стопу — за правилами td_energy_control (клас B: chief або 1/2 + 2/2 іншої особи); без подвійного журналу з мостом | 11, 12, AC-B03, B04 |
| FR-10 | Послідовність пуску з 9 кроків, синхроноскоп, відлік охолодження | 08, 23, 25 |
| FR-11 | Журнал подій і аварій із квитуванням; помітка «не квитовано» | 05, 08, 09, 17 |
| FR-12 | Інтервали ТО за наробітком → `maintenance.request` | 16 |
| FR-13 | Режими роботи, уставки P і cos φ, напрямок тепла, заслінка вихлопу | 13, 23 |
| FR-14 | Кнопки «Імітація» лише з td_iot_sim; сценарії аварій емулятора | 19, 27 |
| FR-15 | Емулятор віддає повну карту, пуск 9 кроків, аварії, циліндри; старі регістри сумісні | 24, 25, 27 |
| FR-16 | Стоп-крани `read_enabled/write_enabled/remote_switching_enabled`, `neutralize.sql` | 12, 13, 20 |

### 1.4 Межі: що не входить
Реальний контролер (карта — типова, Q-02); кілька КГУ в одному пульті (модель допускає, пульт — один агрегат V16); сценарії автоматики (зрізання піку — td_energy_control); скасування (undo) команд; інтеграція в 3D-сцену заводу й енергетику (міст); тепло в BMS (є); мобільний пульт.

## 2. Технічна реалізація

### 2.1 Місце в системі
`td_chp` ← `td_factory3d`, `td_telemetry`, `maintenance`, `mail`, `bus`, `web` (D-14); **не** залежить від `td_viewer3d`, `td_energy*`, `td_iot_sim`. Використовує контракти каркасу: §6.4 (сигнали, `_td_ingest` D-19, `td.command`), §6.6 P-07 (Modbus u72), §6.8 (заявки ТО). Віддає мосту хуки `td.chp.pult._td_route/_td_command_rows/_td_pending_rows/_td_flags` (SPEC M-06) і маршрути API-01…07. Міст `td_chp_factory3d` (`auto_install` при `td_chp` + `td_energy`) додає зв'язок із вузлами, маршрутизацію пуску/стопу в td_energy_control, меню, групи, кнопку в 3D.

### 2.2 Схема
```
 TEDOM / емулятор u72 ──Modbus TCP──► collector ──POST /f3d/telemetry/push──► td.signal (chp/…)
        ▲ (cmd, mode, sp, cos…)           ▲ td.command (fc 6/16)                │ _td_ingest (D-19)
        │                                 │                                      ▼
        └──── collector ◄── td.command ◄── td.chp.command ◄── API-05 ◄──┐   td.chp.event ── bus td_chp ──┐
                                                        (start/stop: мост → td.energy.control/action)   │
 браузер: action td_chp.pult ──API-01…07 (jsonrpc)──► td.chp.pult ──► get_state/trend/journal/cmd ◄──────┘
          store.js (шина + опитування, згладжування) → pult.xml / scene3d.js (three r147, lazy) / scheme.js
```

### 2.3 Об'єкти
| Модель | Призначення | Пише / читає |
|---|---|---|
| `td.chp.unit` (M-01) | паспорт, пороги, стан | manager / усі |
| `td.chp.event` (M-02) | журнал подій і аварій | `_td_on_ingest`, `_cron_*` (sudo) / user |
| `td.chp.command` (M-03) | команди (мінімальний аналог `td.energy.action`) | `td.chp.pult.command` (sudo) / user |
| `td.chp.maintenance.rule` (M-04) | інтервали ТО | крон, operator / user |
| `td.signal`, `td.source`, `td.command` (M-05) | розширення td_telemetry | td_telemetry, td_chp |
| `td.chp.pult` (M-06) | API пульта (AbstractModel) | клієнт / — |

### 2.4 Інтеграції
- **Modbus TCP u72** (P-07), блоки ≤ 125 регістрів, `gap_max 8`; ≈ 10 запитів на цикл; `period_s` 2…60 с (SPEC §5.2). Недоступність → `stale`, подія `comm`, команди блокуються (крім аварійного стопу).
- **td_energy_control** (лише міст): `td.energy.control.prepare/confirm/confirm_second/cancel/get_action` (API-17…22), види `chp_start`/`chp_stop`.
- **td_iot_sim** (необов'язково): `td.sim.scenario`, `td.sim.run.wizard`; REST `/sim/v1` — лише через Odoo-пульт сценаріїв.

### 2.5 Потік даних від пристрою до екрана
1. Контролер КГУ (або `Chp.tick` емулятора) оновлює регістри u72. 2. Колектор опитує блоки за `td.signal.address`, множить на `scale`, шле пакет `[{code,ts,value,q}]`. 3. `td.signal._td_ingest` (super першим) пише `last_value/last_ts/status`. 4. Хук M-05 → `td.chp.event._td_on_ingest` (R-04), `td.chp.command._td_on_ingest` (R-09), `unit.state_code`, `bus.tick('state')`. 5. Шина `td_chp/update` → клієнт, debounce 300 мс. 6. `store.js` викликає API-01 (`get_state`): один `search_read` по 230 кодах, KPI (R-02), діагностика (R-03), перевірки `start` (R-07), `pending`, 8 рядків журналу. 7. `store.V/S` → згладжування → `renderAll` (шапка, KPI, вузли, мнемосхема, 3D). **Команда:** кнопка → API-05 `prepare` → діалог → `confirm` (→ `confirm_second` іншим користувачем) → `td.command` (`chp/ctl/cmd`…) → колектор пише регістр → пристрій ставить `ctl/ack` → ingest → `done/failed` → шина `command` → UI.

### 2.6 Безпека
Групи — D-07 SPEC; читання API — `group_td_chp_user`, команди — operator, 2/2 — chief або інший operator. Потрійний запобіжник запису: `td.chp.write_enabled` + `td.signal.write_enabled` + `td.source.write_enabled` (+ `td.telemetry.write_enabled`); пуск додатково — `remote_switching_enabled`. Токен підтвердження — випадковий, у БД лише `sha256`, чужий не приймається. Клієнт не пише в `td.chp.event/command` (лише `sudo()` у методах); `safe_eval` і код із БД заборонені. Жодних зовнішніх CDN і шрифтів: three.js — своя копія (MIT, `LICENSE`). Аварійний стоп не залежить від свіжості даних. Рішення пристрою остаточне (`ctl/ack=2`).

### 2.7 Продуктивність і обсяги
230 сигналів; `store_period_s` 300 (три трендові — 30) → ≈ 75 тис. показань/добу; подій ≤ 2 000/добу (ротація 365 діб); `get_state` — один запит по `code`, відповідь ≈ 12–15 КБ; опитування 5 с на відкритий пульт; шина ≤ 1 повідомлення/с. three.js ≈ 634 КБ (≈ 150 КБ gzip) вантажиться один раз на сесію, не у `web.assets_backend`.

### 2.8 Міграція й деінсталяція
Демо-полів `x_*` немає. Установка поруч із td_energy: сигнали `chp/…` нові, `infra/chp/*` не чіпаються. Деінсталяція: `uninstall_hook` видаляє лише крони й параметри; `td.signal`, `td.chp.*`, `maintenance.request` видаляються як дані модуля Odoo (стандарт Odoo); заявки ТО лишаються без посилання на правило.

## 3. Налаштування системи
| Об'єкт | Параметр | Значення (тест / прод) | Коментар |
|---|---|---|---|
| ir.config_parameter | `td.chp.read_enabled` | `True` / `False` до звірки | стоп-кран читання |
| | `td.chp.write_enabled` | `True` на стенді / `False` | стоп-кран команд |
| | `td.chp.remote_switching_enabled` | `True` / `False` | дистанційний пуск (регламент об'єкта) |
| | `td.chp.confirm_ttl_s`, `second_ttl_s`, `verify_timeout_s`, `command_ttl_s` | 60, 600, 30, 60 | як у td_energy_control |
| | `td.chp.stale_s`, `event_keep_days`, `bus_throttle_s` | 30, 365, 1 | |
| td.source `CHP-U72` | host, port, unit | `iot-sim`, 502, 72 / адреса контролера | прод — з документації |
| td.signal (module=chp) | address, scale, unit, period_s, пороги | типові (§5.2) | правка у «Карта регістрів»; `write_enabled` — лише 6 записуваних |
| Групи | `td_chp.group_td_chp_*` | призначає адміністратор | з мостом — через групи td_energy |
| Крони | 4 (SPEC §6) | активні | `neutralize.sql` вимикає |

## 4. Інструкція
1. **Пуск КГУ** (енергетик + головний енергетик). Пульт → «Пуск» → перелік умов; якщо все ✓ — діалог класу Б: «Підтвердити (1/2)». Головний енергетик відкриває пульт, у картці «Очікує другого підтвердження» тисне «Підтвердити (2/2)» (або сам виконує одноосібно). Далі — панель послідовності з 9 кроків; після «Набір навантаження» стан «Робота».
2. **Зупинка й аварійний стоп.** «Стоп» — клас Б (так само 1/2, 2/2), КГУ розвантажується й охолоджується 60 с. «Аварійний стоп» — діалог «Так», негайно, без охолодження.
3. **Аварія.** Червона табличка стану й вузол у 3D/мнемосхемі. «Квитувати» підтверджує повідомлення (табличка перестає блимати). Усуньте причину, натисніть «Скинути аварію» (стан → «Резерв»), далі — пуск за п. 1.
4. **Режим і уставки.** Режим, уставка P (лише «Ручний»), cos φ, напрямок тепла, заслінка вихлопу змінюються через діалог «Виконати»; до підтвердження значення не змінюється.
5. **Налаштування під реальний контролер** (інженер КіП). «Когенерація → Карта регістрів»: правка адреси, типу, множника, одиниці сигналу; адреса й порт — у джерелі `CHP-U72`; «Відновити типову карту» повертає заводські значення. Записуваним сигналам вмикайте `write_enabled` лише після звірки.
6. **ТО.** «ТО» показує залишок мотогодин; при 15 % до строку створюється заявка; після виконання — кнопка «ТО виконано».

## 5. Ризики й відкриті питання
Питання (SPEC §15): **Q-01** Apps і важкі залежності (рекомендація: публікувати платформу разом); **Q-02** реальний контролер (типова карта, правка даних); **Q-03** види команд у td_energy_control (ні); **Q-04** V16/інтервали ТО (допущення).
Ризики: (1) мокап → реальність: частина регістрів (крутний момент, детонація, пробій) на справжньому контролері може бути недоступна — пульт показує «—», сигнал можна вимкнути; (2) `examples/js` three r147 застаріли (видалені з r148) — версію зафіксовано, оновлення — окремим завданням; (3) навантаження колектора: 230 сигналів, ≈ 10 блоків — перевірити на стенді (ТП); (4) розбіжність емулятор ↔ карта — AC-26 (JSON-ідентичність); (5) режим `ctl/mode=4` лише в емуляторі — пульт показує його як «Профіль макета»; (6) автоматика td_energy_control може пускати/зупиняти КГУ паралельно з оператором — арбітраж у td_energy_control (R-44), пульт показує фактичний стан.

## 6. План збирання агентами

Три воркери; файли не перетинаються. Спільні контракти: **C-chp-01** — `td_chp/data/chp_signals.json` (карта, SPEC §5.2/5.3); **C-chp-02** — DTO API-01…07 (SPEC §7) і фікстура `static/tests/fixtures/state.json`; **C-chp-03** — хуки M-06 (для мосту). Сигнатури фіксує перший коміт W1 («scaffold:»).

| Воркер | Файли, які змінює (виключно) | Розділи SPEC | Здає |
|---|---|---|---|
| **W1 — бекенд `td_chp`** | `odoo_addons/td_chp/`: `__manifest__.py`, `__init__.py`, `hooks.py`, `neutralize.sql`, `ruff.toml`, `README.md`, `CHANGELOG.md`, `models/`, `tools/`, `controllers/`, `data/`, `security/`, `views/`, `tests/**` (крім `tests/test_hoot.py`); у першому коміті — заглушки чужих файлів: `tests/test_hoot.py`, `static/src/pult/pult.js` (реєструє tag `td_chp.pult` порожнім компонентом), `static/tests/fixtures/state.json` | §0–§2, §4–§7, §9–§11, §13.1, AC-01…20, 26 | M-01…M-07, V-01…V-08 (дія V-01 — лише `ir.actions.client`), API-01…07, R-01…R-12, R-14, R-15, 4 крони, `chp_signals.json` (230 сигналів), тести |
| **W2 — клієнт «Пульт КГУ»** | `odoo_addons/td_chp/static/**` (`lib/three`, `src/pult`, `tests/hoot`, `tests/fixtures`, `description`), `odoo_addons/td_chp/tests/test_hoot.py` | §3 (UI-01…UI-09), §7 (DTO), R-05 (`S.hl`), D-10, §11, AC-21…23 | порт мокапу: `pult.js/xml/scss`, `store.js`, `scene3d.js`, `scheme.js`, `nodes.js`, `trend.js`, `diag.js`, `cmd_panel.js`; three r147 + `OrbitControls.js` + `LICENSE` (з `cdn.jsdelivr.net/npm/three@0.147.0`, розміри 607 784 і 26 660 Б); Hoot-тести |
| **W3 — емулятор і міст** | `services/iot_sim/iot_sim/models/chp.py`, `protocols/modbus_maps/{tedom.py,__init__.py}`, `core/scenarios.py`, `catalog/chp_registers.json`, `tests/unit/test_chp_full.py`, `test_chp_map.py`, `CHANGELOG.md`; `odoo_addons/td_iot_sim/data/td_sim_scenario.xml`; **весь** `odoo_addons/td_chp_factory3d/`; адитивні правки `td_energy_viewer3d`: `static/src/layer/energy_layer.js`, `tools/layer.py`, `static/tests/hoot/pult.test.js`, `tests/test_layer_payload.py` (≤ 40 рядків) і рядок VX-06 у `docs/modules/td_energy_viewer3d/SPEC.md` | SPEC td_chp §8, §5.2, R-05–R-07, R-13, AC-24, 25, 27; SPEC td_chp_factory3d повністю | модель `chp` із повною картою; S-24…S-29; міст B01–B10 |

**Команди тестів.**
- W1: `F3D_TEST_INSTALL=td_chp factory3d/tools/odoo/run_tests.sh td_chp_w1 /td_chp` (усе, окрім Hoot).
- W2: `F3D_TEST_INSTALL=td_chp factory3d/tools/odoo/run_tests.sh td_chp_w2 /td_chp:TestChpHoot` (клас у `tests/test_hoot.py`, шаблон — `td_energy/tests/test_w1_hoot.py`, фільтр `@td_chp`); візуальна звірка зі зібраним мокапом (`factory3d/build/chp/mockup/build.sh`) — скриншоти світлої й темної теми 1280×800.
- W3, емулятор: `cd factory3d/services/iot_sim && .venv/bin/pytest tests/unit -q` (усі, зокрема `test_catalog.py` — 1215 рядків без змін); `/td_iot_sim` — `F3D_TEST_INSTALL=td_iot_sim ... /td_iot_sim`.
- W3, міст: `F3D_TEST_INSTALL=td_chp,td_energy,td_energy_control,td_chp_factory3d factory3d/tools/odoo/run_tests.sh td_chp_w3 /td_chp_factory3d`; `td_energy_viewer3d`: `F3D_TEST_INSTALL=td_energy,td_viewer3d,td_energy_viewer3d,td_chp,td_chp_factory3d ... /td_energy_viewer3d`.

**Порядок злиття.** (0) W1-scaffold: каркас, заглушки, `chp_signals.json`, фікстура DTO → (1) паралельно W1-решта ‖ W2 ‖ W3-емулятор (W3 бере `chp_signals.json` з (0)) → (2) W3-міст (після W1-решти) → (3) інтеграція: ТК-01 (AC-28) і ТК моста (AC-B11) на стенді, перевірка AC-26 (байт-в-байт JSON). Гілки: `claude/td-chp-w1|w2|w3` від `claude/td-chp`; зливає Opus, перетинів файлів немає (заглушки W2 перезаписує W2 — перший коміт W1 їх лише створює).

**Критерії готовності.**
- W1: усі UT зелені (AC-01…20, 26); `ruff check`/`ruff format --check` = 0; `chp_signals.json` проходить `td.signal._check_address` для 230 сигналів; `neutralize.sql` перевірено; жодного `x_`-поля; тексти українською.
- W2: Hoot зелені (AC-21…23); `web.assets_backend` без `static/lib`; fallback без WebGL перевірено; пульт на живому W1 API відтворює мокап (вкладки, 37 вузлів, 6 шарів, 14 плиток, 16 циліндрів, діалоги A/B/аварійного стопу, пуск 9 кроків).
- W3: pytest емулятора зелений (AC-24, 25, 27, існуючі тести без змін); міст — AC-B01…B10; `td_energy_viewer3d`: оновлені тести VX-06 зелені, EMS-1/SWB-1 без змін; `ruff` по `services`, `odoo_addons` = 0.
