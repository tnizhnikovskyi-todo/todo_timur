# td_chp — специфікація

Версія 0.1 · 20.10.2026 · автор: агент (крок 1 циклу) · статус: чернетка. Технічне рішення — [ARCHITECTURE.md](ARCHITECTURE.md); міст — [td_chp_factory3d](../td_chp_factory3d/SPEC.md).
Спирається на: `docs/ARCHITECTURE.md` §5, §6.4, §6.6 P-07, §6.8; td_telemetry (`td.signal`, `td.source`, `td.command`, D-19); td_energy_control (R-39, R-40, API-17…22, D-46); td_iot_sim.
Еталон — мокап `factory3d/build/chp/mockup/` (`a_head.html` розмітка й CSS, `b_sim.js` модель величин, `c_3d.js` сцена, `d_scheme.js` мнемосхема; артефакт «Пульт КГУ»); `b_sim.js:N` — рядок файлу.

## Рішення (D-xx)

| ID | Рішення |
|---|---|
| D-01 | Два модулі за зразком td_genset: `td_chp` (продукт) і `td_chp_factory3d` (міст, `auto_install`). |
| D-02 | `infra/chp/*` і `infra/totals/chp_kw` (td_energy) не змінюються. Нова карта — префікс `chp/…` (§5.2); регістри 40000–40003 мають у ній сигнали-дублі (td_chp самодостатній). |
| D-03 | Карта типова (ПРИПУЩЕННЯ), налаштовується в Odoo: адреса, тип, множник, одиниця, період, пороги кожного сигналу редагуються у `td.signal` і списку V-06; `code` незмінний (ключ пульта). Під реальний контролер — правка даних за його документацією. |
| D-04 | Команди з Odoo — усі види мокапу (пуск, стоп, аварійний стоп, режим, уставка P, cos φ, напрямок тепла, заслінка вихлопу) + `reset` (в мокапі лише в демо); усі з підтвердженням, блокуваннями, журналом. Клас і підтвердження — як у td_energy_control (R-39, R-40): B (`start`, `stop`) — chief одноосібно або operator + 2/2 **іншої** особи; A — одне підтвердження. |
| D-05 | `td.chp.command` — мінімальний полесумісний еквівалент `td.energy.action` (імена полів, ключі `state`, TTL, правила токена й 2/2); без mail.thread, undo, розкладу, сценаріїв. |
| D-06 | Без подвійного журналу: команда живе в одному сховищі — без мосту `td.chp.command`, з мостом `td.energy.action` (D-15). Заблокована спроба — запис зі `state='blocked'` у тому ж сховищі; у `td.chp.event` команди не дублюються. |
| D-07 | Групи: `group_td_chp_user`, `group_td_chp_operator` («КГУ: енергетик»), `group_td_chp_chief` («КГУ: головний енергетик» ⊃ operator). Міст: `td_energy.group_td_energy_manager` ⊃ operator, `group_td_energy_chief` ⊃ chief. |
| D-08 | Стоп-крани `td.chp.read_enabled`, `td.chp.write_enabled`, `td.chp.remote_switching_enabled` (як D-46; гейтить лише `start`; міст підставляє `td.energy_control.remote_switching_enabled`). |
| D-09 | Відхилення від мокапу: `stop` не гейтиться «дистанційними перемиканнями» (як `chp_stop`), блокує лише `ctl/remote=0`; уставка P діє лише в режимі «Ручний»; зміни режиму/уставок — через діалог; «2/2» виконує інший користувач (картка «Очікує другого підтвердження»). |
| D-10 | three.js: власна копія r147 — `static/lib/three/three.min.js` (607 784 Б) і `OrbitControls.js` (26 660 Б), ≈ 634 КБ (≈ 150 КБ gzip), **не** в `web.assets_backend`; `loadJS` при першому відкритті дії, далі кеш. Мокап написаний під UMD r147; бандл td_viewer3d (725 КБ, ESM, новіша версія) — інший API, залежність від нього заборонена; 634 КБ на кожній сторінці бекенду неприйнятні. |
| D-11 | Емулятор: розширюється модель `chp` (Modbus u72); `catalog/signals.csv` (1215 рядків, `test_catalog.py`) не змінюється — нові регістри з JSON-карти; старі регістри й вікно u73 — без змін; `ctl/mode=4` (за замовчуванням) відтворює старий профіль день/ніч. |
| D-12 | Кнопки «Імітація» — лише з моделлю `td.sim.scenario` (td_iot_sim) і для `td_factory3d.group_td_manager`. |
| D-13 | Тексти UI українською в коді, без `.po`; системні шрифти. |
| D-14 | `td_chp` залежить від `td_telemetry` (+`td_factory3d`): карта налаштовується через `td.signal`; для Odoo Apps платформа публікується разом (Q-01). |
| D-15 | Один механізм і один журнал команд із пультом енергетики (вибір користувача; змінює D-06 і Q-03): при встановленому мосту `td_chp_factory3d` у `td_energy_control` ідуть **усі 9 видів** (start, stop, estop, reset, set_mode, set_setpoint, set_cos, set_heat_dir, set_bypass), а не лише start/stop, і `td.chp.command` не створюється; без мосту — `td.chp.command` (D-05). У M-06 — два перевизначувані хуки на ВСІ види: `_td_dispatch` (відправка `command`) і `_td_command_rows` (читання журналу команд для API-03); міст перевизначає їх цілком. |

## 0. Дерево файлів `odoo_addons/td_chp/`

```
__manifest__.py __init__.py hooks.py neutralize.sql ruff.toml README.md CHANGELOG.md
models/ td_chp_{unit,event,command,maintenance_rule,pult}.py td_signal.py td_source.py td_command.py res_config_settings.py
tools/  signals.py kpi.py interlocks.py alarms.py bus.py trend.py command_flow.py gen_chp_signals.py
controllers/main.py   data/ {ir_config_parameter,td_chp_unit,td_chp_maintenance_rule,ir_sequence,ir_cron}.xml chp_signals.json
security/ ir.model.access.csv td_chp_security.xml   views/ td_chp_{unit,event,command,maintenance,signal}_views.xml
         res_config_settings_views.xml td_chp_actions.xml td_chp_menus.xml
static/lib/three/{three.min.js,OrbitControls.js,LICENSE,README.md}   static/description/{icon.png,banner.png,index.html}
static/src/pult/ pult.{js,xml,scss} store.js scene3d.js scheme.js nodes.js trend.js diag.js cmd_panel.js format.js
static/tests/hoot/*.test.js   tests/ common.py test_*.py (§13.1)  stand/test_tk_chp.py
```

## 1. Маніфест
`name` «Cogeneration Unit Console», `version` `19.0.1.0.0`, `category` `Manufacturing/Maintenance`, `author` `ToDo`, `license` `LGPL-3`, `application` True. `depends`: `td_factory3d`, `td_telemetry`, `maintenance`, `mail`, `bus`, `web`.
`data` (порядок): `security/td_chp_security.xml`, `ir.model.access.csv`, `data/ir_config_parameter.xml`, `ir_sequence.xml`, `td_chp_unit.xml`, `td_chp_maintenance_rule.xml`, `ir_cron.xml`, `views/*` (меню — останнім). `assets`: `web.assets_backend` ← `static/src/pult/**/*` (**без** `static/lib`); `web.assets_unit_tests` ← `static/tests/hoot/*`. `post_init_hook=hooks.post_init` (R-14); `uninstall_hook` — лише крони й параметри.

## 2. Моделі

### M-01 `td.chp.unit` — паспорт агрегата
`_description` «КГУ: агрегат (паспорт)», `_order` `sequence, id`, `_inherit` `mail.thread`; один запис `КГУ-1` (`data/td_chp_unit.xml`, `noupdate`). Поля: `name` Char req («КГУ-1 · TEDOM · 800 кВт»); `code` Char req, UNIQUE per company, default `CHP`; `equipment_id` M2o `maintenance.equipment` (default — `td_code=code`, xml `td_factory3d.eq_chp`; null допустимо — заявки ТО без обладнання не створюються); `source_id` M2o `td.source` (default `td_chp.source_chp_u72`); `manufacturer`, `model`, `engine`, `fuel` Char («TEDOM a.s.», «Quanto D800 NG», «MWM TCG 3016 V16», «Природний газ»); `cylinders` Integer 16 (`_check`: лише 16 — «У версії 1 пульт підтримує лише V16.»); Float: `p_nom_kw` 800, `u_nom_v` 400, `f_nom_hz` 50, `rpm_nom` 1500, `i_nom_a` 1178, `lhv_kwh_m3` 9,5 і `co2_kg_m3` 1,98 (> 0), `gas_min_bar` 1,5, `gas_warn_bar` 1,7, `ret_set_c` 70, `jacket_warn_c` 92, `jacket_max_c` 95, `bat_min_v` 23,5, `oil_min_pct` 40, `lel_warn_pct` 10, `lel_alarm_pct` 20, `nox_limit` 250, `co_limit` 300, `cyl_dev_warn_k` 25, `cyl_dev_alarm_k` 40, `knock_warn` 35, `knock_alarm` 60, `plug_interval_h` 4000; `is_assumption` Boolean True (бейдж «Паспорт: типова комплектація (допущення)»); `note` Text; `state_code` Integer readonly 0 і `state_ts` Datetime (оновлює R-04); `rule_ids` O2m M-04; `active`, `company_id`, `sequence`. Методи: `action_open_pult()` (`td_chp.pult`, `context.unit_code`); `action_reset_map()` (manager, R-14); `_td_value(key)` → Float|None (R-01); `_td_signal(key)`; `_td_remote_switching()` → bool (`td.chp.remote_switching_enabled`; хук мосту).

### M-02 `td.chp.event` — журнал подій і аварій
`_description` «КГУ: подія», `_order` `ts desc, id desc`. Поля: `unit_id` M2o req idx cascade; `ts` Datetime req idx (now); `level` `info|warn|alarm` req; `kind` `state|step|alarm|trip|warn|protection|comm|ack|maintenance` req; `text` Char(256) req; `code` Char(48); `signal_id` M2o `td.signal` set null; `ack_state` `none|new|acked` idx (`none` для info, `new` для warn/alarm); `acked_by` M2o `res.users`, `acked_at`; `node` Char(16) (вузол мокапу, R-05); `request_id` M2o `maintenance.request` set null. Індекси `(unit_id, ts desc)`, `(ack_state, level)`. Запис — лише `sudo()` у методах `_td_log(unit, level, kind, text, **kw)`, `_td_on_ingest(before, readings)` (R-04), `_td_ack(ids=None)`, `_cron_stale` (R-01), `_cron_gc` (старше `event_keep_days`).

### M-03 `td.chp.command` — команда (D-05)
`_description` «КГУ: команда», `_order` `create_date desc, id desc`. Поля й ключі `state` — як у `td.energy.action` (td_energy_control M-33): `name` Char readonly (`ir.sequence` `td_chp.seq_command`, `CHP/%(y)s/#####`); `unit_id` M2o req idx; `kind_code` `start|stop|estop|reset|set_mode|set_setpoint|set_cos|set_heat_dir|set_bypass` req idx; `origin` (`manual`); `cls` `A|B`; `state` `prepared|awaiting_second|queued|sent|executing|done|failed|blocked|expired|cancelled` (підписи як у M-33), default `prepared`, idx; `params`, `checks` Json (`[{code,label,state:ok|fail|unknown,hard,detail}]`); `token_hash` Char(64), `token_expires_at`; `needs_second` Boolean; `prepared_by`, `confirmed_by`, `second_by` M2o `res.users` (SQL-CHECK `second_by IS NULL OR (second_by<>prepared_by AND second_by<>confirmed_by)`); `prepared_at`, `confirmed_at`, `second_at`, `second_expires_at`, `started_at`, `finished_at` Datetime; `command_id` M2o `td.command` set null; `expect` Json; `idem` Char(40) (`sha1("<id>:<kind_code>")`, частковий UNIQUE `WHERE idem IS NOT NULL`); `summary`, `detail`, `result_text`, `error` Char. Запис — лише `sudo()` у методах (`_td_prepare`, `_td_confirm`, `_td_confirm_second`, `_td_cancel`, `_td_enqueue`, `_td_on_command`, `_td_on_ingest`, `_td_close`, `_cron_expire`; R-08, R-09); `unlink` — лише admin.

### M-04 `td.chp.maintenance.rule` — інтервал ТО за наробітком
Поля: `unit_id` req; `name` Char req; `every_h` Float req (> 0); `last_h` Float; `lead_pct` Float 15; `request_id` M2o `maintenance.request` (readonly); `left_h` compute (`last_h + every_h − hours`, `hours=_td_value('eng/hours')`); `state` compute `ok|soon` (`left_h ≤ every_h·lead_pct/100`) `|overdue` (`left_h<0`); `sequence`. Дані (`b_sim.js:765`): «Планове ТО (кожні 2 000 мотогод)» 2000/17000; «Заміна моторного масла» 1000/17900; «Свічки запалювання» 4000/16000; «Повітряний фільтр» 2000/17600; «Огляд каталізатора» 8000/16000. Методи: `_cron_check` (R-10); `action_td_done()` (operator: `last_h=hours`, закриває заявку в стадії `done`, якщо є).

### M-05 Розширення `td.signal`, `td.source`, `td.command`
`module`: `selection_add=[('chp','Когенерація')]` на `td.signal` і `td.source`. `td.signal._td_ingest(self, readings, src="module", collector=None)`: `super()` першим (D-19), далі для кодів `chp/…` — `td.chp.event._td_on_ingest`, `td.chp.command._td_on_ingest`, `unit.state_code`, `bus.tick('state')`. `td.signal.write`: зміна `code` при `module='chp'` → `ValidationError("Код сигналу КГУ незмінний: на нього спирається пульт.")`. `td.command.write`: зміна `state` при `origin='chp'` → `td.chp.command._td_on_command(cmd)`.

### M-06 `td.chp.pult` — API пульта (AbstractModel)
Методи `@api.model` (розд. 7); читання — `group_td_chp_user`; `ack`, `command`, `maintenance_done` — operator; `sim` — `td_factory3d.group_td_manager`. Хуки C-chp-03 (D-15; база — потік `td.chp.command`, міст перевизначає цілком, для всіх 9 видів): `_td_route(kind)` → `None|'energy'`; `_td_dispatch(op, unit, kind=None, params=None, ref=None, token=None)` → DTO API-05 — єдина відправка `command` (`op=prepare|confirm|confirm_second|cancel|get`, `ref` — `chp:<id>`|`energy:<id>`, викликається після перевірки груп); `_td_command_rows(unit, limit, before)` — єдине читання команд для API-03 (R-12); `_td_pending_rows(unit)` — очікують 2/2 з того ж сховища; `_td_flags(unit)` → `{bridge, remote_switching}`. **M-07** `res.config.settings`: блок «Когенерація» (admin) з параметрами §5.1.

## 3. Представлення, меню, клієнт

| ID | XML-id | Зміст |
|---|---|---|
| V-01 | `action_td_chp_pult` | `ir.actions.client`, tag `td_chp.pult`, «Пульт КГУ» |
| V-02 | `view_td_chp_unit_form/list` | вкладки «Паспорт», «Пороги й блокування», «Джерело й карта» (кнопки «Відкрити карту регістрів», «Відновити типову карту»), «ТО»; «Відкрити пульт» |
| V-03 | `view_td_chp_event_list/search` | час, рівень (декорації), текст, квитовано; фільтри «Не квитовані», «Аварії», «Сьогодні»; «Квитувати вибране» |
| V-04 | `view_td_chp_command_list/form` | лише читання: статусбар, параметри, перевірки, 1/2-е підтвердження, результат |
| V-05 | `view_td_chp_rule_list/form` | «Через, год», прогрес-смуга, стан, «ТО виконано» |
| V-06 | `action_td_chp_signal` | editable list `td.signal`, domain `module='chp'`: `code` (readonly), `name`, `unit`, `address_text`, `period_s`, `decimals`, пороги, `write_enabled`, `create_request`; manager |
| V-07 | `res_config_settings_view_form` | блок «Когенерація» |
| V-08 | `menu_td_chp_root` | «Когенерація» → «Пульт КГУ» 10, «Журнал подій» 20, «Команди» 30, «ТО» 40, «Паспорт» 50 (manager), «Карта регістрів» 60 (manager), «Налаштування» 70 (admin) |

**Клієнтська дія `td_chp.pult` (порт мокапу, W2).** Розмітка, класи, поведінка — як у мокапі: `a_head.html` → `pult.xml` + `pult.scss` (усе під `.o_td_chp_pult`; `:root`/`[data-theme]` — на корінь; `@import` шрифтів видалити); `b_sim.js` → `store.js`; `c_3d.js` → `scene3d.js`; `d_scheme.js` → `scheme.js`; `NODES` (`b_sim.js:464`) → `nodes.js`.
- **UI-01 `pult.js`** (`ChpPult`): вкладки «Пульт»/«Діагностика», `#plaque`, `#perm`, теми, `context.unit_code`; помилка завантаження — банер «Немає зв'язку з Odoo».
- **UI-02 `store.js`**: `store={S,V,K,cyl,jr,to,caps,il,pending}`; оновлення — шина `td_chp` (`addChannel("td_chp")`, тип `td_chp/update`, debounce 300 мс) → API-01 + опитування 5 с (2 с при відкритій команді); числа згладжуються `approach` (`b_sim.js:7`); ключі `V.*`/`S.*` — колонка «мокап» §5.2; немає значення — «—».
- **UI-03 `scene3d.js`**: геометрія без змін; перед стартом `await loadJS("/td_chp/static/lib/three/three.min.js?v=<ver>")`, далі `OrbitControls.js`, перевірка `THREE.REVISION=="147"`; помилка/немає WebGL — `#cv-fallback`; при закритті дії — `renderer.dispose()`, `ResizeObserver.disconnect()`, зупинка `requestAnimationFrame`.
- **UI-04 `scheme.js`**: 6 шарів (Огляд, Газ і електрика, Тепло ВТ і опалення, НТ і повітря, Вихлоп і викиди, Масло і безпека). **UI-05 `nodes.js`**: 37 вузлів, 8 систем, `nodeActive`, `nodeBadge`, `S.hl` (R-05). **UI-06 `trend.js`**: 24 год/1 год (API-02 + точки зі `store`). **UI-07 `diag.js`**: 16 циліндрів (пороги з паспорта), 22 системи (`b_sim.js:955`).
- **UI-08 `cmd_panel.js`**: Пуск/Стоп/Аварійний стоп; `#il` (з `prepare`); діалог класу B (`#clsb`, «1/2 · енергетик» → «2/2 · головний енергетик»); картка «Очікує другого підтвердження» для інших користувачів (ініціатору кнопки 2/2 немає); `#es-confirm`; **діалог класу A** («Виконати/Скасувати») для `#sel-mode`, `#rng-sp`, `#rng-cos`, `#sel-heat`, `#sel-byp` (до `confirm` значення не змінюється); «Скинути аварію» (стан 3); `#seq`, `#cool-box`; `disabled` за станом (`b_sim.js:824`) і `caps`.
- **UI-09**: блок `#demo` («Імітація») — лише при `caps.sim`; кнопки викликають API-07; чекбокси дозволів мокапу замінено кнопками сценаріїв `chp_no_permit`, `ctl_local`.

## 4. Права
Групи (`td_chp_security.xml`, привілей `privilege_td_chp` «Когенерація»): `group_td_chp_user` (⊃ `td_factory3d.group_td_user`), `group_td_chp_operator` (⊃ user), `group_td_chp_chief` (⊃ operator). Правило компанії для M-01…M-04: `company_id in company_ids or False` (через `unit_id`). `td.chp.pult` без ACL — доступ перевіряють методи.
`ir.model.access.csv` (U=`td_chp.group_td_chp_user`, O=`td_chp.group_td_chp_operator`, M=`td_factory3d.group_td_manager`, A=`td_factory3d.group_td_admin`; колонки `id,model,group,r,w,c,u`):
```
access_td_chp_unit_user,td.chp.unit,U,1,0,0,0
access_td_chp_unit_manager,td.chp.unit,M,1,1,0,0
access_td_chp_unit_admin,td.chp.unit,A,1,1,1,1
access_td_chp_event_user,td.chp.event,U,1,0,0,0
access_td_chp_event_admin,td.chp.event,A,1,0,0,1
access_td_chp_command_user,td.chp.command,U,1,0,0,0
access_td_chp_command_admin,td.chp.command,A,1,0,0,1
access_td_chp_rule_user,td.chp.maintenance.rule,U,1,0,0,0
access_td_chp_rule_operator,td.chp.maintenance.rule,O,1,1,0,0
access_td_chp_rule_manager,td.chp.maintenance.rule,M,1,1,1,1
```

## 5. Дані

### 5.1 `data/ir_config_parameter.xml` (`noupdate="1"`)
`td.chp.read_enabled` = `True` (тест; прод — `False` до звірки): `False` → API-01 `{"read_disabled":true}`, події й ТО не створюються. `td.chp.write_enabled` = `False` (стенд `True`) — запис команд. `td.chp.remote_switching_enabled` = `False` (стенд `True`) — дистанційний пуск (D-08). `td.chp.confirm_ttl_s`=60, `second_ttl_s`=600, `verify_timeout_s`=30, `command_ttl_s`=60, `stale_s`=30, `event_keep_days`=365, `bus_throttle_s`=1.

### 5.2 Карта сигналів `chp/…` (C-chp-01; ПРИПУЩЕННЯ — типова)

Джерело `td.source` `CHP-U72` (`data/td_chp_unit.xml`): `type=modbus_tcp`, `module=chp`, `params={"host":"iot-sim","port":502,"unit":72,"timeout_s":3,"retries":2,"max_block":125,"gap_max":8}`. Сигнал: `module='chp'`, `kind=gauge` (прапори й стани — також `gauge`: пульт читає числа, а `kind=state` вимагає текстових станів, яких Modbus-колектор без `address.map` не віддає), `equipment_id` агрегата, `address={"fc":3,"addr":<PDU>,"type":<тип>,"scale":<×>}` (PDU без «−1», D-20 каркасу; запис — fc 6/16), `store_period_s=300` (`gen/p_kw`, `ht/q_total`, `gas/flow` — 30, джерело тренду), `create_request=False` (крім `✓з`). Формат рядка: `код (після chp/)|PDU|тип|×|одиниця|R/W (порожньо — R)|T|пороги|мокап, примітка`. Типи `u16`, `i16`, `u32` (2 регістри, старше слово першим); прапор — `u16` 0/1; `×` — множник (інж. = регістр·×); `T` — `period_s`, с; `W≥/A≥` = `warn_high/alarm_high`, `W≤/A≤` = `warn_low/alarm_low`; «мокап» — ім'я в `b_sim.js` (`V.`/`S.`) для UI-02. Усе редагується (D-03).

```text
# ctl — стан і керування
ctl/state|40000|u16|1|||2||S.state: 0 резерв,1 пуск,2 робота,3 аварія,4 охолодження (= infra/chp/state)
ctl/cmd|40900|u16|1||W|||1 пуск,2 стоп,3 аварійний стоп,4 скидання аварії; пристрій очищає після виконання
ctl/ack|40901|u16|1|||2||0 немає результату (скидається при новій cmd),1 прийнято,2 відхилено
ctl/ack_reason|40902|u16|1|||2||причина відхилення (R-06)
ctl/mode|40903|u16|1||RW|2||S.mode: 0 heat,1 el,2 peak,3 manual,4 профіль макета (лише емулятор,D-11)
ctl/sp_pct|40904|u16|1|%|RW|2||S.setpoint 50…100
ctl/cos_set|40905|u16|0,01||RW|2||S.cosSet 0,90…1,00
ctl/heat_dir|40906|u16|1||RW|2||S.heatDir: 0 auto,1 boiler,2 cooler
ctl/bypass_mode|40907|u16|1||RW|2||S.bypassMode: 0 auto,1 ht,2 bypass
ctl/step|40908|u16|1|||2||S.stepI+1; 0 — не пуск; 1…9 (R-13)
ctl/step_left|40909|u16|0,1|с||2||залишок кроку (stepDur−stepT)
ctl/cool_left|40910|u16|1|с||2||S.coolLeft
ctl/sync_du|40911|i16|0,1|%||2||S.sync.du
ctl/sync_df|40912|i16|0,01|Гц||2||S.sync.df
ctl/sync_dphi|40913|i16|1|°||2||S.sync.dp
ctl/sync_ok|40914|u16|1|||2||прапор S.sync.ok
ctl/warm_skip|40915|u16|1|||2||прапор S.warmSkip
ctl/target_pct|40917|u16|0,1|%||2||ціль режиму (modeTarget()·100)
ctl/heat_demand|40918|u16|1|кВт||10||V.demand — потреба котельні
ctl/remote|40930|u16|1|||2||S.remote,прапор: «Дистанційне» на щиті
ctl/permit|40931|u16|1|||2||S.permit,прапор: дозвіл КГУ
alarm/code|40920|u16|1|||2|A≥1 ✓з|S.alarm: 0,111 тиск газу,112 перегрів ОЖ,113 зворотка,114 загазованість,115 пожежа,116 аварійний стоп
alarm/trip|40921|u16|1|||2||остання причина зупинки без аварії: 0,1 зникла мережа S2,2 ROCOF,3 знято дозвіл
# eng — двигун,турбіна,пуск
eng/rpm|40100|u16|1|об/хв||2||V.rpm
eng/torque|40101|u16|0,01|кН·м||5||V.torque
eng/shaft_kw|40102|u16|1|кВт||5||V.pShaft
eng/t_jacket_out|40103|i16|0,1|°C||2|W≥92 A≥95 ✓з|V.tJo
eng/t_jacket_in|40104|i16|0,1|°C||5||V.tJi
eng/p_oil|40105|u16|0,01|бар||2||V.pOil
eng/t_oil|40106|i16|0,1|°C||5||V.tOil
eng/t_bearing|40107|i16|0,1|°C||5||V.tBrg
eng/vib|40108|u16|0,01|мм/с||5||V.vib
eng/tc_rpm|40109|u16|10|об/хв||5||V.tcRpm
eng/p_boost|40110|u16|0,01|бар||5||V.pBoost
eng/t_turb_in|40111|i16|0,1|°C||5||V.tTurb
eng/t_air_in|40112|i16|0,1|°C||5||V.tAirIn
eng/t_air_out|40113|i16|0,1|°C||5||V.tAirOut
eng/throttle|40114|u16|0,1|%||5||V.thr
eng/lambda|40115|u16|0,001|||5||V.lambda
eng/p_mix|40116|u16|0,01|бар||5||V.pMix
eng/hours|40120|u32|0,1|год||60||S.hours (мотогодини; ТО M-04)
eng/starts|40122|u32|1|||60||S.starts
eng/starter_a|40124|u16|1|А||2||V.starterI
eng/bat_v|40125|u16|0,1|В||5|W≤24,5 A≤23,5|V.batV
eng/bat_a|40126|u16|0,1|А||5||V.batI
eng/starter_on|40127|u16|1|||2||прапор S.starter
# oil — масло
oil/level|40130|u16|0,1|%||5|W≤60 A≤45 ✓з|V.oilLvl
oil/t_out|40131|i16|0,1|°C||5||V.tOilOut
oil/dp_filter|40132|u16|0,01|бар||5||V.dpOilF
oil/cons|40133|u16|0,01|г/кВт·год||10||V.oilCons
oil/fresh|40134|u16|0,1|%||10|W≤20|V.oilFresh
oil/waste|40135|u16|0,1|%||10|W≥80|V.oilWaste
oil/topup|40136|u16|1|||5||прапор S.topup
# gen — генератор,АРН
gen/p_kw|40001|u16|1|кВт||2||V.pel (= infra/totals/chp_kw)
gen/u_v|40140|u16|0,1|В||2||V.U
gen/i_a|40141|u16|1|А||2||V.I
gen/cos|40142|u16|0,001|||2||V.cos
gen/q_kvar|40143|i16|1|квар||2||V.Q
gen/f_hz|40144|u16|0,01|Гц||2||V.f
gen/i_pct|40145|u16|0,1|%||5|W≥105|V.Ipct
gen/exc_a|40146|u16|0,1|А||5||V.excI
gen/exc_v|40147|u16|1|В||5||V.excU
gen/load_pct|40148|u16|0,1|%||2||S.load·100
# gas — газова рампа
gas/flow|40003|u16|0,1|м³/год||2||V.gas (= infra/chp/gas_m3h)
gas/p_in|40200|u16|0,01|бар||2|W≤1,7 A≤1,5 ✓з|V.gasP
gas/p_reg|40201|u16|1|мбар||5||V.gasReg
gas/dp_filter|40202|u16|1|мбар||5||V.dpFilter
gas/yv1,gas/yv2|40203,40204|u16|1|||2||S.valves: 0 закрито,1 відкрито,2 тест
gas/vp_state|40205|u16|1|||2||S.vp.st: 0 —,1 виконується,2 успішно,3 витік
gas/vp_leak|40206|u16|0,1|мбар/хв||5||витік valve proving
gas/vp_ts|40207|u32|1|с (Unix UTC)||10||S.vp.time; 0 — немає
gas/total|40210|u32|1|м³||60||S.gasTotal
gas/day|40212|u32|1|м³||60||S.gDay
gas/psl,gas/psh,gas/inlet_valve|40214,40215,40216|u16|1|||5||прапори: датчик min (1 — спрацював),max,кран (1 — відкрито)
# ht — тепло ВТ,опалення
ht/q_total|40002|u16|1|кВт||2||V.qth (= infra/chp/heat_kw)
ht/t_sup|40300|i16|0,1|°C||2||V.tSup
ht/t_mid|40301|i16|0,1|°C||5||V.tMid
ht/t_ret|40302|i16|0,1|°C||2|W≥66 A≥70 ✓з|V.tRet (на вході ТО,після клапана)
ht/t_ret_raw|40303|i16|0,1|°C||2|W≥65 A≥75|V.tRetRaw (до клапана)
ht/flow|40304|u16|0,1|м³/год||5||V.flow
ht/q_phe,ht/q_exh|40305,40306|u16|1|кВт||5||V.qPhe,V.qExh
ht/q_boiler,ht/q_cooler|40307,40308|u16|1|кВт||5||V.qBoiler,V.qCooler
ht/mix_pos|40309|u16|0,1|%||5||V.mixPos
ht/cap_pct|40310|u16|0,1|%||5|W≤99,5|V.cap ·100,обмеження потужності
ht/p_loop|40311|u16|0,01|бар||10||V.pLoop
ht/p_exp_ht,ht/p_exp_lt,ht/p_exp_h|40312,40313,40314|u16|0,01|бар||10||V.pExpHT/pExpLT/pExpH
ht/pump_ht_f,ht/pump_he_f|40315,40317|u16|0,1|Гц||5||V.pHT.f,V.pHe.f
ht/pump_ht_a,ht/pump_he_a|40316,40318|u16|0,1|А||5||V.pHT.I,V.pHe.I
ht/p_dis_ht|40319|u16|0,01|бар||10||V.pDisHT
ht/cooler_fan|40320|u16|0,1|%||5||V.fan
ht/t_cool_out|40321|i16|0,1|°C||5||V.tCoolOut
ht/flow_cool|40322|u16|0,1|м³/год||5||V.flowC
ht/heat_total|40324|u32|0,1|Гкал||60||V.hmTot
ht/heat_day|40326|u32|0,01|Гкал||60||S.qDay
ht/pump_ht_run,ht/pump_he_run|40328,40329|u16|1|||2||прапори V.pHT.run,V.pHe.run
# lt — тепло НТ
lt/q_kw|40400|u16|1|кВт||5||V.qLT
lt/flow|40401|u16|0,1|м³/год||5||V.flowLT
lt/t_in,lt/t_out|40402,40403|i16|0,1|°C||5||V.tLTin,V.tLTout
lt/fan|40404|u16|0,1|%||5||V.fanLT
lt/pump_f|40405|u16|0,1|Гц||5||V.pLT.f
lt/pump_a|40406|u16|0,1|А||5||V.pLT.I
lt/p_dis|40407|u16|0,01|бар||10||V.pDisLT
lt/pump_run|40408|u16|1|||2||прапор V.pLT.run
# exh — вихлоп і викиди
exh/t_e1|40500|i16|0,1|°C||5||V.tE1 (після турбіни,до каталізатора)
exh/t_cat_out|40501|i16|0,1|°C||5||V.tCatOut
exh/t_e2|40502|i16|0,1|°C||5||V.tE2
exh/t_stack|40503|i16|0,1|°C||5||V.tStack
exh/dp_cat|40504|u16|0,1|мбар||10|W≥18|V.dpCat
exh/nox|40505|u16|1|мг/нм³||10|W≥225 A≥250|V.nox
exh/co|40506|u16|1|мг/нм³||10|W≥270 A≥300|V.co
exh/co_raw|40507|u16|1|мг/нм³||10||V.coRaw
exh/o2|40508|u16|0,01|%||10||V.o2
exh/bypass_pct|40509|u16|0,1|%||5||V.bypass·100
exh/back_p|40510|u16|1|мбар||10||протитиск (b_sim.js:620)
# air — повітря,контейнер
air/dp_filter|40600|u16|0,1|мбар||10|W≥12 A≥15|V.airDp
air/t_cont|40601|i16|0,1|°C||5|W≥38 A≥45|V.tCont
air/fan_sup,air/fan_exh|40602,40603|u16|0,1|%||5||V.fanSup,V.fanExh
air/louver|40604|u16|0,1|%||5||V.louver
air/t_amb|40605|i16|0,1|°C||10||S.tAmb
# safe — безпека,мережа
safe/lel|40610|u16|0,1|% НКПР||2|W≥10 A≥20 ✓з|V.lel
safe/fire|40611|u16|1|||2||прапор S.fire
safe/ext_state|40612|u16|1|||2||S.ext: 0 готове,1 випуск,2 спрацювало
safe/ext_level|40613|u16|1|%||10||S.extLevel
safe/estop_loop|40614|u16|1|||2||S.estopLoop: 1 замкнений
safe/rocof|40615|u16|1|||2||прапор S.rocofFlag
safe/rocof_dfdt|40616|u16|0,01|Гц/с||5||df/dt (b_sim.js:659)
safe/rocof_dphi|40617|u16|0,1|°||5||векторний зсув
safe/grid_ok|40618|u16|1|||2||S.grid: 1 мережа S2 наявна
safe/u_grid|40619|u16|0,1|В||5||U мережі
safe/qf_closed|40620|u16|1|||2||S.qf: 1 QF-CHP увімкнено
safe/ctrl_v|40621|u16|0,1|В||10||живлення контролера
safe/es_cab,safe/es_door,safe/es_ext|40622,40623,40624|u16|1|||2||кнопки аварійного стопу: 1 натиснута
# em — лічильник TEDOM-1,добові
em/kwh|40700|u32|1|кВт·год||60||V.eTot
em/kvarh|40702|u32|1|квар·год||60||V.eRe
em/kwh_day|40704|u32|0,1|кВт·год||60||S.eDay
em/runh_day|40706|u16|0,01|год||60||S.runDay
# cyl — 16 циліндрів** (`<id>` = A1…A8,B1…B8; індекс `i` = 0…15 за порядком)
cyl/<id>/t|40800+i|i16|0,1|°C||10||V.cyl[i].t
cyl/<id>/knock|40816+i|u16|1|од.||10|W≥35 A≥60|.knock
cyl/<id>/kv|40832+i|u16|0,1|кВ||10|W≥29|.kv (пробій)
cyl/<id>/ms|40848+i|u16|0,01|мс||10||.ms (іскра)
cyl/<id>/plug_h|40864+i|u16|1|год||60|W≥3200 A≥3800|.plug (наробіток свічки)
```

Разом **230 сигналів** (150 + 80 циліндрових; рядки з кількома кодами — окремі сигнали, адреси за порядком), записуваних 6 (`ctl/cmd`, `ctl/mode`, `ctl/sp_pct`, `ctl/cos_set`, `ctl/heat_dir`, `ctl/bypass_mode`).

### 5.3 Інші дані; R-14
`data/chp_signals.json` (C-chp-01): масив `{code,name,unit,kind,pdu,type,scale,rw,period_s,decimals,warn_low,warn_high,alarm_low,alarm_high,create_request,note}` на 230 сигналів; `name` українською («КГУ: тиск газу на вході»); W1 генерує з §5.2 скриптом `tools/gen_chp_signals.py` (одноразово). **R-14** (`hooks.post_init`, ідемпотентно): за `code` немає → створити (`origin='module'`, `source_id`, `equipment_id`); є → адресу/тип/множник/одиницю/період/пороги не чіпати (правки інженера зберігаються); `action_reset_map()` перезаписує їх із JSON.

## 6. Крони
`cron_td_chp_expire` (1 хв, `td.chp.command._cron_expire`): `prepared` після `token_expires_at` і `awaiting_second` після `second_expires_at` → `expired`; `queued/sent/executing` після `started_at+verify_timeout_s` → `failed` («Контролер не підтвердив команду за N с»). `cron_td_chp_stale` (1 хв, R-01). `cron_td_chp_maintenance` (15 хв, R-10). `cron_td_chp_gc` (1 доба). Усі no-op при `read_enabled=False`.
**R-15 `neutralize.sql`:** `active=false` для 4 кронів; `td.chp.write_enabled` і `td.chp.remote_switching_enabled` = `False`; `write_enabled=false` у сигналах і джерелі `module='chp'`.

## 7. HTTP/JSON API
Маршрути `type="jsonrpc"`, `auth="user"`, POST; логіка в `td.chp.pult` (M-06), контролер лише викликає метод від імені сесії. Помилки — `AccessError`/`UserError`/`ValidationError` українською; відповідь ≤ 64 КБ.

| ID | Маршрут → метод | Вхід → вихід |
|---|---|---|
| API-01 | `/td_chp/state` → `get_state(unit=None, etag=None)` | `unit` — код (default перший активний) → `{"not_modified":true}` при збігу `etag`, інакше DTO |
| API-02 | `/td_chp/trend` → `get_trend(unit=None, range_h=24)` | `range_h∈{1,24}` → `{"range_h","step_s","t0","series":{"pel","qth","gas"}}` (R-11) |
| API-03 | `/td_chp/journal` → `get_journal(unit=None, limit=50, before=None)` | → `{"items":[{"type":"event\|command","id","ref","ts","level","text","ack_state","state"}],"more"}` (R-12); `ref`: `event:<id>` для подій, `chp:<id>`/`energy:<id>` для команд; рядки-команди — лише з хука `_td_command_rows` (одне сховище, D-15) |
| API-04 | `/td_chp/ack` → `ack(unit=None, ids=None)` | operator; `ids=None` — усі `new` → `{"acked":N}` |
| API-05 | `/td_chp/cmd` → `command(op, **kw)` | `op=prepare{kind,params}` / `confirm{ref,token}` / `confirm_second{ref}` / `cancel{ref,token}` / `get{ref}` |
| API-06 | `/td_chp/maintenance` → `get_maintenance(unit=None)`, `maintenance_done(rule_id)` | список `{id,name,every_h,last_h,left_h,state,request}` |
| API-07 | `/td_chp/sim` → `sim(op, code=None, params=None)` | `op=list` → `{"available","scenarios":[{code,label}]}`; `start`/`stop`/`reset`; без td_iot_sim `available=false`; `start` = `td.sim.run.wizard.create({scenario_id,params_text}).action_confirm()` від імені користувача |

**DTO `get_state`** (фікстура — `static/tests/fixtures/state.json`; `ver` — sha1 канонічного JSON DTO без `ver/ts/age_s`; `unit.passport={manufacturer,model,engine,fuel,p_nom_kw,u_nom_v,f_nom_hz,rpm_nom,i_nom_a}`; `to[].request` — `{id,name}|null`): `{"ver":sha1,"ts":ISO,"read_enabled","stale","age_s","unit":{code,name,p_nom_kw,cylinders,passport,assumption,"th":{пороги, `lhv_kwh_m3`, `co2_kg_m3` з M-01}},"caps":{operate,chief,sim,write,rsw,bridge},"v":{"<код без chp/>":число|null},"u":{код:"од."},"st":{код:"ok|warn|alarm|stale"},"k":{fuel_kw,eta_e,eta_h,eta_t,co2_kgh,co2_day_t,dT},"cyl":[{id,t,dev,knock,kv,ms,plug_h}×16],"alarm":{code,text,node,acked}|null,"trip":{code,text}|null,"il":{ok,list:[{code,label,state,hard,detail}]},"pending":[{ref,kind,title,prepared_by,can_second,second_expires_at}],"jr":[8 останніх, як API-03],"to":[як API-06]}`. `il` — перевірки `start` (R-07). Невідомий `unit` → `UserError`; без групи → `AccessError("Немає доступу до Когенерації.")`.
**`prepare`** → `{ref:"chp:12"|"energy:55",action_id,token,ttl_s,verify_timeout_s,kind,cls,title,text,sub,checks,blocked,blocked_reason,needs_second,confirm_label,disabled_reason}` (td_energy_control 7.2 + `ref`); **`confirm`/`confirm_second`** → `{ref,state,state_label,needs_second,message,blocked_reason}`; **`get`** → `{ref,state,state_label,summary,result_text,error,finished_at,needs_second,checks}`; `confirm_label` — «Виконати» (клас A або chief) / «Підтвердити (1/2)».
**Шина:** `tools/bus.py` за зразком `td_energy.tools.bus`: канал `td_chp`, тип `td_chp/update`, тіло без даних `{"kinds":["state"|"journal"|"command"|"maintenance"]}`, не частіше `td.chp.bus_throttle_s` на воркер; збій шини ковтається.

## 8. Сервісна частина: емулятор КГУ (W3)

Файли: `services/iot_sim/iot_sim/models/chp.py` (переписати), `protocols/modbus_maps/tedom.py`, `catalog/chp_registers.json` (копія `td_chp/data/chp_signals.json`, AC-26), `core/scenarios.py` (S-24…S-29), `tests/unit/test_chp_{full,map}.py`; Odoo — `td_iot_sim/data/td_sim_scenario.xml` (+6 записів).
1. **Карта.** `tedom.py` будує регістри u72 із JSON (`pdu,type,scale,rw`); значення — з моделі (`Chp.regs[code]`, інж. одиниці; регістр = round(інж/scale)); запис у `W/RW` — `Chp.write_reg`, при `ctx.write_accept=False` — `ModbusError(4)`. Доступ до моделі — `Ctx.model("CHP")` (додати в `modbus_maps/__init__.py`, якщо немає). Старі регістри 40000–40007, 40010–40015, 40020 і вікно u73 (230–233) — без змін; `ctl/ack` пише й `chp_ack` u73.
2. **Модель.** Порт `step()` (`b_sim.js:252–365`) і `computeV()` (`367–452`) у `Chp.tick(dt)`; константи `b_sim.js:29`; шум `self.r(key)`; sim-час `World`. Старт у резерві; початкові `eng/hours=18400,0`, `eng/starts=612`, `em/kwh=10 912 450`, `gas/total=3 940 620` (`b_sim.js:56–66`).
3. **Режими** (`ctl/mode`): 0 — `xFromQ(heatDemand(t))`; 1 — 0,88 (07–22 Київ) / 0,66; 2 — 1,0 у 08–11 і 17–21, інакше 0,60; 3 — `sp_pct/100`; **4 (за замовчуванням)** — старий профіль: 0,5 вдень (`sun>0,05` і `outdoor≥0`), інакше 1,0; P/тепло/газ 400/497/109 або 800/856/199. Зміна навантаження ≤ 0,04·P_nom/с; `P=800·x`.
4. **Пуск:** кроки й тривалість — R-13 (масштаб `chp_start_s/60`; `warm` при `t_jacket_out≥55` — 1,5 с). Охолодження — 60 с (`TRANSITION_S`).
5. **Аварії** (`b_sim.js:303–325`): `gas/p_in<1,5` → 111; `t_jacket_out≥97` → 112; `t_ret≥75,5` понад 2 с → 113 (раніше — зниження потужності `cap`, `b_sim.js:309`); `lel≥20` → 114; `fire` → 115 (гасіння через 3 с: `ext_state` 1, рівень −25 %/с, потім 2); аварійний стоп → 116, `estop_loop=0`. У станах 1/2/4 аварія → state 3, клапани закриті, QF розімкнено. Зупинки без аварії (→ 4, `alarm/trip`): мережа S2 зникла й `chp_island=false` → 1; `chp_rocof` → 2 (`rocof_dfdt=2,4`, `rocof_dphi=14`); `chp_permit=0` → 3. `gas_bar` (існуючий прапор, 2,10) — ціль `gas/p_in`, стала часу 1,4 с.
6. **Команди** (`ctl/cmd` u72 і `chp/cmd` u73 → `Chp._command`): 1 пуск — якщо проходять перевірки пристрою (R-07 №1–5, 7–14) і `state=0`, інакше `ack=2` + `ack_reason` (R-06); 2 стоп — у станах 1/2 → охолодження, інакше ack=2/12; 3 аварійний стоп — завжди, крім `state=3`; 4 скидання — лише `state=3` і причини усунуто (`gas_bar≥1,5`, `t_jacket_out<95`, немає `chp_ret_fault/gas_leak/fire`), замикає `estop_loop` → state 0, інакше ack=2. `ctl_remote=0` → ack=2/3. Нова команда скидає `ack=0`, результат — ≤ 1 тік.
7. **Сценарії** (група `energy`, `duration_s` 600; відкіт повертає прапори): S-24 `chp_overheat` «КГУ: перегрів ОЖ» (`chp_temp_fault=1`, ціль `t_jacket_out`=107 → 112); S-25 `chp_hot_return` «КГУ: гаряча зворотка» (`chp_ret_fault=1`, `t_ret_raw`→84 → `cap`, 113); S-26 `chp_gas_leak` «КГУ: загазованість» (`chp_gas_leak=1`, `lel`→32); S-27 `chp_fire` «КГУ: пожежа» (`chp_fire=1` → 115); S-28 `chp_rocof` «КГУ: спрацював ROCOF» (`chp_rocof=1` → trip 2); S-29 `chp_no_permit` «КГУ: знято дозвіл» (`chp_permit=0` → trip 3 / відмова пуску). Для UI-09 — також S-20 `chp_no_gas`, S-19 `ctl_local`, `blackout`.

## 9. Алгоритми й правила

**R-01 Свіжість.** Сигнал свіжий, якщо `now − last_ts ≤ max(3·period_s, td.chp.stale_s)`; інакше `_td_value=None`, `st=stale`, `v=null`. `_cron_stale`: `ctl/state` застарів (DTO `stale=true`) → один `warn`/`comm` «Втрата зв'язку з КГУ: немає даних N с»; перше свіже значення → `info` «Зв'язок з КГУ відновлено».
**R-02 KPI** (`tools/kpi.py`): `fuel_kw=gas/flow·lhv`; `ok = fuel_kw>20 і eng/rpm>1200`; `eta_e=gen/p_kw/fuel_kw·100`, `eta_h=ht/q_total/fuel_kw·100`, `eta_t` — сума (0, якщо не `ok`); `co2_kgh=gas/flow·co2_kg_m3`; `co2_day_t=gas/day·co2_kg_m3/1000`; `dT=ht/t_sup−ht/t_ret`. Приклади: газ 109, P 400, Q 497 → fuel 1035,5, η 38,6/48,0/86,6 %, CO₂ 215,8 кг/год; газ 199, 800, 856 → 42,3/45,3/87,6 %, 394,0.
**R-03 Циліндри.** `mean=avg(t₁…t₁₆)`; `dev=t−mean` лише при `eng/rpm>1200`, інакше `null`; `|dev|>cyl_dev_alarm_k` alarm, `>cyl_dev_warn_k` warn. Свічка: `plug_h/plug_interval_h` ≥95 % «Замінити», ≥80 % «Зношується», інакше «Норма». Приклад (`b_sim.js:51–52`): A5 `dev=+27,3` К → warn; `plug_h=3560` → 89 %.
**R-04 Події з показань** (`_td_on_ingest(before, readings)`; лише зміни; дедуплікація `code+значення` 5 с): (1) `ctl/state` a→b — `info`/`state` «Стан КГУ: Резерв → Пуск» (Резерв, Пуск, Робота, Аварія, Охолодження), 1→2 ще «Пуск завершено: КГУ в роботі, P ел. = N кВт», `unit.state_code`; (2) `ctl/step`→k — `step` «Пуск, крок k/9: <назва R-13>»; (3) `gas/vp_state`→2/3 (valve proving), `safe/qf_closed` 0→1/1→0 (QF-CHP), `oil/topup` (автодолив), `safe/ext_state` 0→1 (гасіння, `alarm`/`protection`) — тексти як `b_sim.js:275–276, 294, 323, 345–346`; (5) `alarm/code` 0→N — `alarm`/`alarm`, `new`, текст і вузол R-05; N→0 — `info` «Аварію скинуто»; (6) `alarm/trip` 0→N — R-05 (`warn`/`alarm`, `new`); (7) статус сигналу ok→warn/alarm — kind `warn`, «<назва>: <значення> <од.> (поріг <значення>)», `new`; (8) `_td_ack`: `new`→`acked` і одна `info`/`ack` «Квитування: підтверджено повідомлень — N» (N=0 — без запису).
**R-05 Аварії, зупинки, вузли** (`tools/alarms.py`; значення з `v`). alarm 111 «Низький тиск газу: {gas/p_in:.2f} бар < {gas_min_bar} бар» → `gasramp`; 112 «Перегрів ОЖ: {eng/t_jacket_out:.1f} °C ≥ 97 °C» → `engine`; 113 «Висока температура зворотки: {ht/t_ret:.1f} °C > {ret_set_c} °C (уставка)» → `mixv`; 114 «Загазованість у контейнері: {safe/lel:.0f} % НКПР ≥ {lel_alarm_pct} %» → `gasdet`; 115 «Пожежа в контейнері: спрацювала пожежна сигналізація» → `fire`; 116 «Аварійний стоп оператора» → `estop`. trip 1 (warn) «Зникла мережа S2: QF-CHP відключено, острівний режим не передбачено → охолодження» → `qf`; trip 2 (alarm) «Захист ROCOF / векторний зсув: df/dt = {safe/rocof_dfdt} Гц/с (> 1,0), Δφ = {safe/rocof_dphi}° (> 12°). QF-CHP відключено → охолодження» → `qf`; trip 3 (warn) «Дозвіл КГУ знято: контрольована зупинка» → `cabinet`. Невідомий код — «Невідома аварія N», `cabinet`. `S.hl`: alarm → `{node,'alarm'}`, trip → `{node,'warn'}`; знімається при коді 0 і стані 0.
**R-06 `ctl/ack_reason`:** 1 немає дозволу КГУ; 2 тиск газу нижче мінімуму; 3 не «Дистанційне»; 4 немає мережі S2; 5 спрацював ROCOF; 6 загазованість ≥ 10 % НКПР; 7 пожежа або гасіння; 8 t зворотки > уставки; 9 t ОЖ ≥ 95 °C; 10 АКБ < 23,5 В; 11 рівень масла або контур аварійного стопу; 12 стан не допускає команду; 13 значення поза діапазоном.
**R-07 Блокування** (`tools/interlocks.CHECKS[code](unit, ctx)→(ok|fail|unknown, detail)`; підписи й тексти відмови — `t`/`d`/`bad` з `b_sim.js:123–139`; `unknown` — вхід застарів). Для `start` усі 14: 1 `not_cooling` `ctl/state≠4`; 2 `no_alarm` `≠3`; 3 `permit` `ctl/permit=1`; 4 `gas_pressure` `gas/p_in≥gas_min_bar`; 5 `remote` `ctl/remote=1` (також stop, reset, `set_*`); 6 `rsw` `unit._td_remote_switching()`; 7 `grid` `safe/grid_ok=1`; 8 `no_rocof` `safe/rocof=0`; 9 `lel_lt` `safe/lel<lel_warn_pct`; 10 `no_fire` `safe/fire=0` і `ext_state=0`; 11 `ret_temp` `ht/t_ret≤ret_set_c`; 12 `jacket_temp` `eng/t_jacket_out<jacket_max_c`; 13 `battery` `eng/bat_v≥bat_min_v`; 14 `oil_estop` `oil/level≥oil_min_pct` і `safe/estop_loop=1`. За видом додатково: `state_run` (stop: `ctl/state∈{1,2}`), `alarm_active` (reset: `=3`), `not_alarm` (estop: `≠3`), `manual_mode` (`set_setpoint`: `ctl/mode=3`), `write_enabled` (параметр, сигнал і джерело цілі). Для видів, маршрутизованих мостом (`_td_route`≠None), `rsw` і `write_enabled` не перевіряються — діють стоп-крани td_energy_control. Усі жорсткі: `blocked = fail або unknown` (для estop `unknown` не блокує). Золоті: `gas_pressure` 2,10/1,15/— → ok/fail/unknown (так само `ret_temp` 58/72/—, `lel_lt` 0,6/12/—); `oil_estop` (66,8; 1)/(35; 1)/(66,8; 0) → ok/fail/fail.
**R-08 Потік команди** (R-39/R-40 td_energy_control, мінімально; це потік td_chp без мосту — з мостом `_td_dispatch` перевизначено й усі види виконує td_energy_control, D-15). (1) Клас B — `start`, `stop`; A — решта. `prepare/confirm/cancel` — operator; B без chief → `awaiting_second` (`second_expires_at=now+second_ttl_s`); `confirm_second` — operator/chief, `second_by ∉ {prepared_by, confirmed_by}`; chief виконує одноосібно й може бути другою особою; admin без груп не підтверджує. (2) `prepare(kind, params)`: `write_enabled=False` → `UserError("Керування вимкнено: td.chp.write_enabled. Зверніться до адміністратора.")`, `start` при `remote_switching_enabled=False` — так само з `td.chp.remote_switching_enabled`; параметри: `set_mode{mode:heat|el|peak|manual}`, `set_setpoint{sp_pct 50…100}`, `set_cos{cos 0,90…1,00 крок 0,01}`, `set_heat_dir{dir:auto|boiler|cooler}`, `set_bypass{mode:auto|ht|bypass}`, решта `{}`; поза межами → `ValidationError("Команда {name}: параметр {label} поза межами {min}…{max}.")`; повтор ≤ 5 с — той самий запис, новий токен; перевірки R-07 → `checks`; жорстка невдача → запис одразу `blocked`, токена немає; інакше `prepared`, токен `secrets.token_urlsafe(24)` (у БД `sha256`), TTL `confirm_ttl_s`. (3) `confirm(token)` (FOR UPDATE): чужий токен → `AccessError`, невідомий → `UserError`, прострочений → `expired` + `UserError` (тексти як у td_energy_control API-18); перевірки повторюються (невдача → `blocked`); B без chief → `awaiting_second`, інакше `_td_enqueue`; повторний `confirm` — поточний стан без нової команди (`idem`); `cancel(token)`: `prepared/awaiting_second` → `cancelled`. (4) `_td_enqueue`: одна активна команда (`queued/sent/executing`) на агрегат, інакше `blocked` «Уже виконується команда {name}» (`estop` завжди дозволено, скасовує інші `queued`); `td.command` (`sudo`, `origin='chp'`, `requested_by=confirmed_by`, `expires_at=now+command_ttl_s`): `start→chp/ctl/cmd=1`, `stop→2`, `estop→3`, `reset→4`, `set_mode→chp/ctl/mode` 0…3, `set_setpoint→chp/ctl/sp_pct`, `set_cos→chp/ctl/cos_set`, `set_heat_dir→chp/ctl/heat_dir`, `set_bypass→chp/ctl/bypass_mode` (0…2); сигнал без `write_enabled` → `blocked` «Запис вимкнено: {сигнал}». (5) `td.command`→команда: `sent`→`sent`; `done`→`executing`; `failed|expired|cancelled` — так само.
**R-09 Верифікація** (`_td_on_ingest`): `start/stop/estop/reset` — перше показання `chp/ctl/ack` з `ts ≥ done_at`: 1 → `done` («Контролер прийняв команду»); 2 → `failed`, `error` = текст R-06. `set_*` — цільовий сигнал дорівнює значенню (|Δ| ≤ 0,5·scale) → `done`. Без підтвердження за `verify_timeout_s` → `failed` (крон). Після завершення — `bus.tick('command')`.
**R-10 ТО.** `_cron_check`: заявка правила в стадії `done` → `last_h=hours`, `request_id=False`; правило без відкритої заявки зі `state∈{soon,overdue}` → `maintenance.request` (`preventive`, `equipment_id`, «ТО КГУ: {name} — через N год» / «… — прострочено на N год», опис: наробіток, інтервал, остання відмітка) + `info`/`maintenance`; поки заявка відкрита, нова не створюється; `hours=None` — пропуск.
**R-11 Тренд:** `gen/p_kw`→`pel`, `ht/q_total`→`qth`, `gas/flow`→`gas` із `td.reading`; `step_s`=300 (24 год, ≤288 точок) або 30 (1 год, ≤120); середнє у відрізку, порожній — `null`; `t0` — UTC.
**R-12 Журнал (API-03):** події `td.chp.event` + рядки-команди з хука `_td_command_rows` (D-15: у базі `td.chp.command` без `prepared/cancelled`, з мостом — `td.energy.action`; `ts` = `finished_at` або `prepared_at`), текст «Команда «{вид}»: {стан}» (+ « · 1/2 {prepared_by}, 2/2 {second_by}»); `ts desc, id desc`; `before` — ISO `ts`; `more` — є старіші рядки.
**R-13 Пуск, 9 кроків** (`b_sim.js:30–40`): 1 `vent` Вентиляція контейнера; 2 `warm` Попередній підігрів ОЖ; 3 `lube` Попереднє змащення; 4 `proving` Перевірка герметичності клапанів; 5 `crank` Прокрутка стартером; 6 `ign` Запалювання; 7 `idle` Холостий хід; 8 `sync` Синхронізація з мережею; 9 `load` Набір навантаження. Тривалість у емуляторі, с: 5, 6, 5, 7, 6, 5, 5, 9, 12 (разом 60).

## 10. Стани й переходи
Агрегат: 0 → 1 Пуск → 2 Робота → (стоп/мережа/ROCOF/дозвіл) 4 Охолодження → 0; з 1/2/4 → (аварія) 3 → (скидання) 0. Команда: `prepared → awaiting_second → queued → sent → executing → done`; бічні `blocked`, `failed`, `expired`, `cancelled`; лише «вперед». Подія: `new → acked`.

## 11. Обробка помилок
Немає зв'язку: `stale`, `v=null`, команди `disabled` («Немає свіжих даних»), крім аварійного стопу. Немає шини — опитування. `read_enabled=False` — «Читання вимкнено адміністратором». Невідомий код аварії — нейтральний текст. БД — UTC, пульт — пояс користувача; «пік» емулятора — Europe/Kyiv.

## 12. Acceptance Criteria
Типи: UT — Odoo-тест (теги `post_install -at_install f3d`); UT-JS — Hoot; UT-E — pytest емулятора; TC — стенд.

| AC | Given / When / Then | Тип |
|---|---|---|
| AC-01 | Чиста база з `td_telemetry`; `-i td_chp` → агрегат `CHP`, джерело `CHP-U72`, 230 сигналів `module='chp'`, 5 правил ТО, 3 групи, 4 крони; повторне `-u` не дублює | UT |
| AC-02 | Коди унікальні, адреси/типи/множники = §5.2 (звірка з `chp_signals.json`); записуваних 6, усі `write_enabled=False`; зміна `code` сигналу `chp` → `ValidationError` | UT |
| AC-03 | Інженер змінив `address/scale/unit` `chp/gas/p_in`; `-u` зберігає; `action_reset_map()` повертає типові | UT |
| AC-04 | `get_state` → DTO §7 (`v/u/st/k/cyl/il/jr/to/caps`); `ver` змінюється зі значенням; повтор з `etag` → `not_modified` | UT |
| AC-05 | Немає даних > `stale_s`; крон → один `comm` warn, `stale=true`, `v=null`; нові дані → один `comm` info | UT |
| AC-06 | R-02: 109/400/497 і 199/800/856 дають η і CO₂ з точністю 0,1; `rpm<1200` → η=0 | UT |
| AC-07 | R-03: A5 `dev=+27,3` → warn; `rpm<1200` → `dev=null`; `plug_h=3560` → «Зношується» | UT |
| AC-08 | `ctl/state` 0→1→2 і `ctl/step` 1…9 → події R-04 (1–2) по порядку; `unit.state_code=2` | UT |
| AC-09 | `alarm/code` 0→111 → `alarm`-подія (текст R-05, вузол `gasramp`, `new`); `_td_ack` operator → `acked` + одна `info`/`ack`; без operator → `AccessError`; код →0 → «Аварію скинуто» | UT |
| AC-10 | R-07 золоті випадки; застарілий вхід → `unknown` і блок | UT |
| AC-11 | `prepare(start)` без operator → `AccessError`; operator → `cls='B'`, `needs_second`, 14 перевірок; A `confirm` → `awaiting_second`; A `confirm_second` → `UserError`; інший operator → `queued`, `td.command` `chp/ctl/cmd=1`; chief виконує одноосібно | UT |
| AC-12 | Тиск газу 1,15: `prepare(start)` → запис `blocked`, токена й `td.command` немає, рядок у журналі; `stop` проходить при `remote_switching_enabled=False`, блок при `ctl/remote=0`; `start` при `False` → `UserError`; `estop` проходить при `ctl/remote=0` і застарілих даних, блок лише при `ctl/state=3` | UT |
| AC-13 | `set_setpoint` при `ctl/mode≠3` → `blocked`; `sp_pct=45` → `ValidationError`; `set_cos 0,98` → `td.command` 0,98; `write_enabled=False` → `UserError`; сигнал без `write_enabled` → `blocked` | UT |
| AC-14 | `ctl/ack=1` після `done_at` → `done`; `ack=2`, `reason=2` → `failed` з текстом; без показання за `verify_timeout_s` → `failed` | UT |
| AC-15 | Подвійний `confirm` → одна `td.command`; чужий токен → `AccessError`; прострочений → `expired`; друга активна команда → `blocked` | UT |
| AC-16 | ТО: `left_h ≤ 15 %` інтервалу → одна `maintenance.request`, без дублів; заявка `done` → `last_h=hours` | UT |
| AC-17 | `get_trend(24)` ≤ 288 точок × 3 серії, `get_trend(1)` ≤ 120; `get_journal`: події й команди разом, `ts desc`, пагінація, без дублів | UT |
| AC-18 | Без сесії відмова; без `group_td_chp_user` → `AccessError`; `ack/cmd/maintenance_done` — operator; `sim` — manager | UT |
| AC-19 | `sim(list)`: без `td.sim.scenario` → `available=false`; з td_iot_sim — 9 сценаріїв; `start` через `td.sim.run.wizard` | UT |
| AC-20 | Зміна `ctl/state` у `_td_ingest` → одне `td_chp/update` на `bus_throttle_s`, збій шини не ламає ingest; `neutralize.sql` вимикає 4 крони, `write_enabled`, `remote_switching_enabled`, запис у сигналах/джерелі | UT |
| AC-21 | `web.assets_backend` без `static/lib/three`; three вантажиться `loadJS` лише при відкритті дії; `REVISION=="147"`; без WebGL — `#cv-fallback`, решта працює | UT-JS |
| AC-22 | UI: 37 вузлів у 8 системах, 6 шарів, 14 плиток KPI, 16 рядків діагностики | UT-JS |
| AC-23 | «Пуск» при невиконаних умовах — `#il` без діалогу; при виконаних — 1/2, після `confirm` «Очікує другого підтвердження»; зміна режиму/уставок відкриває діалог A, до `confirm` значення не змінюється | UT-JS |
| AC-24 | Емулятор: старі регістри 40000–40020 і u73 230–233 — як раніше (існуючі тести зелені); нові — за §5.2 | UT-E |
| AC-25 | Емулятор: `ctl/cmd=1` → 9 кроків за R-13, `ctl/step` 1…9, `state` 1→2; при `gas_bar=1,15` → `ack=2`, `reason=2` | UT-E |
| AC-26 | `catalog/chp_registers.json` байт-в-байт = `td_chp/data/chp_signals.json`; адреси без перетинів, поза 40004–40020 | UT |
| AC-27 | Емулятор: S-24…S-28 → коди 112/113/114/115 і trip 2; `ctl/cmd=4` скидає лише коли причину усунуто; `ctl/cmd=3` → 116; A5 `dev≈+27 К`, `plug_h=3560` | UT-E |
| AC-28 | TC: Пуск (1/2 operator, 2/2 chief) → `state` 1→2, журнал із кроками; «Імітація → Пожежа» → 3, підсвітка `fire`, «Квитувати», «Скинути» → 0 | TC |

## 13. План тестування
**13.1** UT: `tests/test_install.py` (01, 20), `test_signal_map.py` (02, 03, 26), `test_state_api.py` (04, 05), `test_kpi.py` (06, 07), `test_events.py` (08, 09), `test_interlocks.py` (10), `test_command_flow.py` (11–13, 15), `test_command_verify.py` (14), `test_maintenance.py` (16), `test_trend_journal.py` (17), `test_routes.py` (18, 20), `test_sim.py` (19); база `tests/common.py` (користувачі user/operator/operator2/chief). UT-JS: `static/tests/hoot/` (21–23). UT-E: `services/iot_sim/tests/unit/test_chp_full.py`, `test_chp_map.py` (24, 25, 27).
**13.2 ТК-01** (AC-28): `tests/stand/test_tk_chp.py`, стенд `iot_sim` (`write_enabled`, `remote_switching_enabled`=True, колектор із `CHP-U72`). ТК моста — [td_chp_factory3d](../td_chp_factory3d/SPEC.md). **13.3 Безпека:** невідомі `kind/params/ref` → `UserError`; чужий токен; admin без груп не підтверджує; `td.chp.pult` без групи недоступна; прямий запис у `td.chp.event/command` заборонено. **13.4 Продуктивність:** `get_state` ≤ 150 мс (230 сигналів), `get_trend(24)` ≤ 300 мс. **13.5 DEPLOY_TEST:** установка на копію демо-бази з `td_telemetry`, повторне `-u`.

## 14. Definition of Done
Усі UT/UT-JS/UT-E зелені; `ruff check`/`ruff format --check` = 0; `neutralize.sql`; `CHANGELOG.md`; `static/description` (іконка, банер, `index.html` для Apps); AC-28 на стенді.

## 15. Відкриті питання
Q-01 Odoo Apps: `td_telemetry`/`td_factory3d` важкі (stock, mrp, hr…) — рекомендація: публікувати платформу разом; до відповіді залежності не змінюємо. Q-02 Реальний контролер і його карта — типова карта (D-03), далі правка даних. Q-03 Реєструвати `estop/set_*/reset` у td_energy_control? — так, але лише через міст (D-15: один механізм і журнал із пультом енергетики); без мосту — `td.chp.command`. Q-04 V16 та інтервали ТО — допущення (`is_assumption`).
