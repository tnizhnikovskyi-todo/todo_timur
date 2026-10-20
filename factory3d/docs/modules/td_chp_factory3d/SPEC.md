# td_chp_factory3d — специфікація

Версія 0.1 · 20.10.2026 · автор: агент (крок 1 циклу) · статус: чернетка. Міст «КГУ ↔ завод», `auto_install` при встановлених `td_chp` і `td_energy`. Продукт — [td_chp SPEC](../td_chp/SPEC.md) (ID без префікса — звідти; тут `DB-xx`, `RB-xx`, `AC-Bxx`). План збирання (W3) — [td_chp ARCHITECTURE §6](../td_chp/ARCHITECTURE.md); [ARCHITECTURE.md](ARCHITECTURE.md). Зразок — `td_genset_factory3d`.

## Рішення (DB-xx)

| ID | Рішення |
|---|---|
| DB-01 | `depends`: `td_chp`, `td_energy`. `td_energy_control`, `td_viewer3d`, `td_bms`, `td_iot_sim` — необов'язкові (`env.get`, D-18 каркасу). Власних моделей і таблиць міст не має. |
| DB-02 | **Одна команда — один запис (D-06 td_chp).** `start`/`stop` ідуть через `td.energy.control` і живуть лише в `td.energy.action` (види `chp_start`/`chp_stop`; ті самі клас B, підтвердження й журнал, що в Пульті енергетика). `td.chp.command`, `td.command` від td_chp і події `td.chp.event` для них **не** створюються. Решта 7 видів (`estop`, `reset`, `set_*`) — `td.chp.command` (в td_energy_control їх немає; це уставки, а не комутації — Q-03 td_chp). Журнал пульта зводить сховища під час читання. |
| DB-03 | Без td_energy_control (лише td_energy) маршрутизації немає: `_td_route` → `None`, усе йде потоком td_chp. |
| DB-04 | Блокування td_chp (R-07) діють і в маршрутизованому потоці — до й після викликів td_energy_control; жорстка невдача → запис td_energy закривається `blocked`. Стоп-крани таких видів — `td.energy_control.write_enabled`/`remote_switching_enabled`. |
| DB-05 | Одне джерело Modbus на пристрій: сигнали `chp/…` переносяться на `MB-U72-CHP` td_energy; `CHP-U72` архівується. |
| DB-06 | Групи: `td_energy.group_td_energy_manager` ⊃ `td_chp.group_td_chp_operator`; `group_td_energy_chief` ⊃ `group_td_chp_chief`; `group_td_energy_user` ⊃ `group_td_chp_user`. |
| DB-07 | Меню td_chp — в «Енергетика → Генерація й резерв» (`td_energy.menu_td_energy_generation`); корінь «Когенерація» ховається (як `td_genset.menu_root` у `td_genset_factory3d`). |
| DB-08 | Кнопка «Відкрити пульт КГУ» в 3D-картці `CHP` — розширення `td_energy_viewer3d` (VX-06): `PULT_CODES` → `PULT_BUTTONS` з `CHP`. Окремий модуль для 3D не потрібен; `td_chp` від `td_viewer3d` не залежить. |
| DB-09 | Тепло КГУ в BMS (`td_bms`, `infra/chp/heat_kw`) уже є — не чіпаємо й не дублюємо; сигнали `infra/chp/*`, `infra/totals/chp_kw` не змінюються. |

## 0. Дерево файлів `odoo_addons/td_chp_factory3d/`
```
__manifest__.py __init__.py hooks.py ruff.toml README.md CHANGELOG.md
models/ td_chp_unit.py td_chp_pult.py     tools/energy_route.py     data/td_chp_factory3d_menu_hide.xml
security/td_chp_factory3d_security.xml    views/ td_chp_unit_views.xml menus.xml
tests/  test_install.py test_source_merge.py test_routing.py test_journal_pending.py test_flags.py stand/test_tk_b.py
```
Поза модулем (W3, адитивно): `td_energy_viewer3d/static/src/layer/energy_layer.js`, `tools/layer.py`, `static/tests/hoot/pult.test.js`, `tests/test_layer_payload.py`, рядок VX-06 у `docs/modules/td_energy_viewer3d/SPEC.md`.

## 1. Маніфест
`name` «КГУ ↔ завод (міст)», `version` `19.0.1.0.0`, `category` `Manufacturing/Maintenance`, `author` `ToDo`, `license` `LGPL-3`, `auto_install` True, `depends`: `td_chp`, `td_energy`. `data`: `security/td_chp_factory3d_security.xml`, `data/td_chp_factory3d_menu_hide.xml`, `views/td_chp_unit_views.xml`, `views/menus.xml`. `post_init_hook=hooks.post_init` (RB-05), `uninstall_hook=hooks.uninstall`. Даних і ACL немає.

## 2. Моделі
**M-B1 `td.chp.unit` (розширення).** `energy_node_id` M2o `td.energy.node` (default `code='CHP'`), `energy_qf_node_id` (default `code='QF-CHP'`), `energy_node_state`/`energy_qf_state` Selection related `sld_state`, `energy_p_kw` Float related `p_now` (readonly). `_check`: `energy_node_id.kind='generator'`, `energy_qf_node_id.kind='cell'`, інакше `ValidationError("Вузол {code} не є КГУ/вводом КГУ.")`. `action_open_energy_node()` → client action `td_energy.node_card`, `params={code}`. `_td_remote_switching()` (хук M-01 td_chp) → при `td_energy_control` `td.energy_control.remote_switching_enabled`.
**M-B2 `td.chp.pult` (розширення; хуки M-06 td_chp).** `_td_route(kind)` → `'energy'`, якщо `kind∈{start,stop}`, `'td.energy.control' in env` і активний вид `chp_start`/`chp_stop`; інакше `None` (DB-03). `_td_command_rows` (RB-03), `_td_pending_rows` (RB-04), `_td_flags(unit)` → `{"bridge":True,"remote_switching":unit._td_remote_switching()}` (`caps.bridge`, `caps.rsw`). Кроки `command(op,…)` для маршрутизованих видів — RB-01, RB-02.

## 3. Представлення
**V-B1** inherit `td.chp.unit` form: вкладка «Енергетика» (вузли, стани, P, кнопка «Відкрити вузол в Енергетиці»). **V-B2** меню в `td_energy.menu_td_energy_generation`: «Пульт КГУ» 25 (`td_chp.action_td_chp_pult`), «Події КГУ» 26, «ТО КГУ» 27, «Паспорт КГУ» 28 (manager); «Команди» td_chp не переноситься (пуск/стоп — в журналі Енергетики). `td_chp.menu_td_chp_root` → `active=False` (`noupdate="0"`). Група — `td_chp.group_td_chp_user`. **Права:** `implied_ids` за DB-06.

## 8. «КГУ в 3D» (`td_energy_viewer3d`, VX-06)
1. `energy_layer.js`: `PULT_CODES` → `PULT_BUTTONS = new Map([["EMS-1",{id:"open_pult",label:"Відкрити пульт",action:PULT_ACTION,flag:"can_pult"}],["SWB-1",…],["CHP",{id:"open_chp_pult",label:"Відкрити пульт КГУ",action:CHP_PULT_ACTION,flag:"can_chp_pult"}]])`, `CHP_PULT_ACTION="td_chp.action_td_chp_pult"`; `export const PULT_CODES = new Set(PULT_BUTTONS.keys())` лишається. `cardActions(code,D,api)`: кнопка, якщо `PULT_BUTTONS.has(code)`, `api.canOpenAction` і `layerOf(D)?.[flag]===true`; `onAction`: `open_chp_pult` → `api.openAction(CHP_PULT_ACTION)`.
2. `tools/layer.py`: у `layer` — `can_chp_pult = card_ok and "td.chp.pult" in env and env.user.has_group("td_chp.group_td_chp_user")` (без `td_chp` — `false`); `layer.schema`/`meta.schema` не змінюються, старий клієнт ключ ігнорує.
3. Тести: `pult.test.js` — `PULT_CODES`={CHP,EMS-1,SWB-1}, кнопка КГУ лише при `can_chp_pult`, EMS-1/SWB-1 без змін; `test_layer_payload.py` — `can_chp_pult` за групою й наявністю td_chp.

## 9. Правила
**RB-01 Маршрутизація.** `command(op)` при `_td_route='energy'`: `prepare` — (1) preflight td_chp (R-07 без `rsw`/`write_enabled`) → `pre`; (2) `res=td.energy.control.prepare('chp_start'|'chp_stop', {})` від імені користувача (класи, TTL, стоп-крани, дедуплікація — td_energy_control R-39, R-40); (3) жорстка невдача `pre` → `env['td.energy.action'].sudo().browse(res.action_id)._td_close('blocked', reason)`, відповідь `blocked=true`, `token=None`; (4) інакше DTO за RB-02. `confirm` — повторний preflight (невдача → `_td_close('blocked')`), далі `td.energy.control.confirm(token)`; `confirm_second` — preflight і `td.energy.control.confirm_second(action_id)`; `cancel` → `cancel(token)`; `get` → `get_action(action_id)`. `ref="energy:<action_id>"`; `chp:`-посилання обробляє td_chp.
**RB-02 Мапінг DTO.** `prepare`: `ref`, `action_id`, `token`, `ttl_s`, `verify_timeout_s`, `cls`, `title`, `text`, `sub`, `needs_second`, `confirm_label`, `disabled_reason` — з `res`; `kind` (`chp_start`→`start`, `chp_stop`→`stop`); `checks` = preflight td_chp + `res.checks`; `blocked = res.blocked or pre.blocked`; `blocked_reason` — перша невдала. `confirm/confirm_second/get` — поля API-18/19/22 td_energy_control + `ref`; ключі `state` ті самі. `UserError`/`AccessError` td_energy_control проходять як є.
**RB-03 Журнал.** `_td_command_rows(unit,limit,before)`: `td.energy.action` з `kind_code∈{chp_start,chp_stop}` або `kind_code ilike 'auto\\_%chp%'`, `state∉{prepared,cancelled}`, `create_date<before` → `{"type":"command","id","ref":"energy:<id>","ts":finished_at|prepared_at,"level":"warn" для failed/blocked/expired, інакше "info","text":summary|"Команда «Пуск КГУ»: {state_label}","state"}`. Подій td_chp про ці команди немає (DB-02).
**RB-04 Очікують 2/2.** `_td_pending_rows(unit)`: `td.energy.action` у `awaiting_second` (`chp_start|chp_stop`) → `{"ref","kind","title","prepared_by","can_second":користувач ∈ manager/chief і ∉{prepared_by,confirmed_by},"second_expires_at"}`. Пульт опитує `get` кожні 2 с до завершення (шини td_energy_control не слухає).
**RB-05 Джерело й вузли (`post_init`, ідемпотентно).** Є `td.source` `MB-U72-CHP` → `unit.source_id` і `source_id` усіх `td.signal` `module='chp'` на нього; `CHP-U72` → `active=False`; вузли — за кодами `CHP`/`QF-CHP`. `uninstall_hook`: сигнали й `unit.source_id` назад на `CHP-U72` (`active=True`), `td_chp.menu_td_chp_root` → `active=True`.
**RB-06 Інваріант.** Після повного `start` (1/2 + 2/2 → `done`): `td.energy.action(chp_start)`=1; `td.chp.command(start)`=0; `td.command(origin='chp')`=0; `td.chp.event` без записів про команду; `get_journal` — 1 рядок команди.
**Помилки.** td_energy_control видалено/вимкнено → `_td_route=None`, старі `energy:`-рядки журналу зникають разом із моделлю (`_td_command_rows` → `[]`). Вид `chp_start` деактивовано → `_td_route=None`.

## 12. Acceptance Criteria
| AC | Given / When / Then | Тип |
|---|---|---|
| AC-B01 | `td_chp`+`td_energy` → міст ставиться автоматично; `energy_node_id.code='CHP'`, `energy_qf_node_id.code='QF-CHP'`; групи `energy_manager/chief` ⊃ `operator/chief`; меню під «Генерація й резерв», корінь схований; видалення моста повертає корінь | UT |
| AC-B02 | Є `MB-U72-CHP`: усі 230 сигналів `chp/…` на ньому, `CHP-U72` архівовано; після видалення — назад | UT |
| AC-B03 | З `td_energy_control`: `prepare(start)` → 1 `td.energy.action` (`chp_start`, клас B), `ref='energy:<id>'`; operator 1/2 → `awaiting_second`; другий operator → `queued`; chief одноосібно → `queued` | UT |
| AC-B04 | Після повного `start` і `stop`: `td.chp.command`=0, `td.command(origin='chp')`=0, подій про команди в `td.chp.event`=0, `get_journal` — по 1 рядку (RB-06) | UT |
| AC-B05 | Тиск газу 1,15: `prepare(start)` → запис td_energy `blocked`, `blocked=true`, токена немає, у чергу не потрапило | UT |
| AC-B06 | `estop`, `set_mode`, `set_cos` з мостом — у `td.chp.command`; журнал зводить обидва сховища, `ts desc` | UT |
| AC-B07 | Без `td_energy_control` `_td_route('start')=None`, `start` виконується потоком td_chp | UT |
| AC-B08 | Дія в `awaiting_second`: інший operator бачить картку `can_second=true`, ініціатор — `false`; після `confirm_second` картка зникає | UT |
| AC-B09 | `caps.bridge=true`; `rsw` дзеркалить `td.energy_control.remote_switching_enabled`; при `False` `prepare(start)` → `UserError` td_energy_control, `stop` проходить | UT |
| AC-B10 | 3D: картка `CHP` має «Відкрити пульт КГУ» лише при `layer.can_chp_pult`, клік відкриває `td_chp.action_td_chp_pult`; EMS-1/SWB-1 без змін; без `td_chp`/групи `can_chp_pult=false` | UT, UT-JS |
| AC-B11 | TC (стенд): пульт → Пуск 1/2, 2/2 → в «Енергетика → Керування» один `chp_start` `done`, `state=2`; «Аварійний стоп» → запис у `td.chp.command`, `state=3` | TC |

## 13. План тестування, DoD
`tests/test_install.py` (B01), `test_source_merge.py` (B02), `test_routing.py` (B03–B07, B09), `test_journal_pending.py` (B04, B06, B08), `test_flags.py` (B09); `td_energy_viewer3d` (B10); `tests/stand/test_tk_b.py` (B11). Команда: `F3D_TEST_INSTALL=td_chp,td_energy,td_energy_control,td_chp_factory3d factory3d/tools/odoo/run_tests.sh <db> /td_chp_factory3d`. Безпека: чужий/невідомий `ref` → `UserError`; без груп td_energy пульт недоступний; `_td_close` — лише `sudo` усередині моста. DoD: тести моста й оновлені тести `td_energy_viewer3d` зелені (EMS-1/SWB-1 без змін), `ruff`=0, CHANGELOG.

## 15. Відкриті питання
Q-B1 Кнопки `chp_start/chp_stop` у картці вузла `CHP` Пульту енергетика (API-27) — рекомендація: так, окремою задачею td_energy_control. Q-B2 Види `estop/set_*/reset` у td_energy_control — Q-03 td_chp (ні).
