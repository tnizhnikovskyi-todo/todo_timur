# td_genset: журнал переносу Odoo 18.0 → 19.0 (W1)

Формат: MG | команда | входжень до/після | що зроблено | (для джерела «С») підтверджено/спростовано.
Код Odoo 19 — `/home/user/odoo19` (далі `O19`). Результат: 176/176 тестів, 0 ERROR, 0 DeprecationWarning від td_genset.

| MG | Команда | До/після | Що зроблено |
|---|---|---|---|
| MG-01 | `cat __manifest__.py` | version 18.0 → 19.0.1.0.0 | `version` 19.0.1.0.0; `depends` (base, mail, bus, web, maintenance) є в 19; `assets` лише `web.assets_backend`, `td_genset/static/src/**/*` — достатньо; `uninstall_hook` без змін. |
| MG-02 | `grep -rn "from odoo.osv" .` | 1 / 0 | `genset_reading.py`: `expression.OR` → `Domain.OR` (`odoo.fields.Domain`). |
| MG-03 | `grep -n "uninstall_hook" __init__.py` | `def uninstall_hook(env)` / без змін | `post_init_hook` немає; сигнатура вже `(env)`; тест хука зелений. Доповнення: `category.alias_id` у 19 не існує (alias лише в `maintenance.team`, `O19/addons/maintenance/models/maintenance.py:427`) — гілку з alias категорії прибрано. |
| MG-04 | `grep "<tree\|//tree\|'tree'"` | 0 / 0 | Змін немає. Додатково (не в чек-листі, RNG 19): `<group expand="0" …>` і `<group string=…>` у `<search>` недопустимі (`O19/odoo/addons/base/rng/search_view.rng`) → `<group>` (7 подань); `ir.actions.act_window.target='inline'` прибране з Selection (`O19/odoo/addons/base/models/ir_actions.py:317`) → видалено з дії налаштувань (за замовчуванням `current`, як у `maintenance.action_maintenance_configuration`). |
| MG-05 | `grep "attrs=\|states="` у views | 0 / 0 | Змін немає (збіги лише в аргументах Python-тестів). |
| MG-06 | `grep "kanban-box\|kanban-menu"` | 0 / 0 | Kanban-подань немає. Джерело С — не застосовне. |
| MG-07 | `grep -rn active_id views/ models/` | 4 (wizard Python) / 4 | Лишено. **С спростовано**: у 19 кнопка `type="action"` з форми як і раніше додає `active_model/active_id/active_ids` у контекст — `O19/addons/web/static/src/webclient/actions/action_service.js:1623-1627` (`doActionButton`). Майстри `refuel`/`fuel_receipt` перевіряють `active_model == 'td.genset'`. |
| MG-08 | `grep "category_id\|implied_ids" security/` | 3 `category_id` / 0 (у групах) | Новий `res.groups.privilege` `res_groups_privilege_td_genset` (name «Генератори», `category_id` → `module_category_td_genset`, sequence 60); у трьох групах `privilege_id`; `implied_ids` і `user_ids` — `Command.link`; XML id груп без змін. `O19/odoo/addons/base/models/res_groups.py:36,69`; `O19/addons/maintenance/security/maintenance.xml:3-12`. Тест `test_w0_smoke`: `group_tech.privilege_id.category_id`. |
| MG-09 | `grep -rn groups_id` | 5 (меню 1, тести 4) / 0 | `menu.xml` (ir.actions.server) `group_ids`; тести `common.py`, `test_w3_security.py`, `test_w3_ui_http.py` — `group_ids` + `Command.set`. Додатково: `res.groups.users` → `user_ids` у `genset_alarm.py` (отримувачі тривог групи tech) і в `groups.xml`; без цього тривога «тех.» нікому не доходила (тест `test_ac10_relay_unavailable_and_auth`). |
| MG-10 | `grep -rn _sql_constraints models/` | 8 / 0 | Усі → `models.Constraint('unique(...)', 'повідомлення')` з атрибутами `_<name>`; імена в БД лишаються. Тест `test_w2_scheduler` читав `_sql_constraints` → тепер `_date_uniq.message`. |
| MG-11 | `grep "numbercall\|doall" data/` | 0 / 0 | Змін немає; крон `_cron_pull_readings` не кидає виняток при offline (перевірено тестом AC-10). |
| MG-12 | `grep "type='json'\|jsonrequest" controllers/` | каталогу `controllers/` немає | Контролерів у модулі немає (JS ходить через `orm.call`); нічого мігрувати. |
| MG-13 | grep з чек-листа | `_read_group` 10 (вже новий API), `_notify_progress` 3, `read_group`/`web_read_group` у тесті 2 / 0 застарілих | `ir.cron._notify_progress(done=,remaining=)` (DeprecationWarning у 19) → `_commit_progress(processed, remaining=)`. `read_group`, `name_get`, `check_access_rights`, `self._cr`, `group_operator` — 0. Тест graph/pivot: `web_read_group(domain, measures, groupby, lazy=)` у 19 має іншу сигнатуру → `formatted_read_group(domain, groupby, aggregates)` (як у web-клієнті 19, `O19/addons/web/models/models.py:802`). |
| MG-14 | `grep "def " models/*.py \| grep -v "def _"` | `@api.private` уже на публічних методах `td.genset.relay.client` | Публічні `action_*`/`get_pult_state` — свідомий API UI з перевіркою груп (`_td_check_group`); `td.genset.config.get` повертає запис за правилами доступу. Змін немає (тест безпеки `TestW3SecurityRpc` зелений). |
| MG-15 | grep Command-трійок | трійки в тестах/даних | Сумісні; у змінених місцях (groups.xml, menu.xml, тести) — `Command`. |
| MG-16 | `grep ref('base.` tests/ | `base.user_root/user_admin/main_company/group_user` | Це не демо-дані (є в базі без демо). Власні фікстури тестів — у `setUpClass`/`common.py`; 176 UT зелені на базі без демо. Тест не змінено. |
| MG-17 | grep mail | `message_post(subtype_xmlid=…, body=Markup)`, `activity_schedule` | Уже в стилі 18/19; змін немає. Заявки ТО: `maintenance.request.owner_user_id` на базі з `hr_maintenance` (auto_install) обчислюється з працівника і ігнорує значення з `create` → тест `test_ac56_maintenance_done_only_tech` викликає `create` від імені користувача ще й з `user_id` (правило запису 19 дозволяє `user_id = user`). Тест змінено. |
| MG-18 | `grep "from odoo import _"` | `_` імпортується, DeprecationWarning немає | Лишено (`.po` без змін). |
| MG-19 | `grep safe_eval models/` | 0 у models (лише тест) | Змін немає. |
| MG-20 | `grep "useService(\"rpc\")\|jsonrpc\|@web/legacy" static/src` | 0 / 0 | JS використовує `orm`, `bus_service`. Джерело С — не застосовне; пульт-тести (browser_js) зелені. |
| MG-21 | `grep "constructor(\|static props\|setup()"` | `setup()`, `static template/props` | **С підтверджено**: OWL-компоненти з `setup()`, `registry.category("fields"/"view_widgets")`; `_t` з `@web/core/l10n/translation` — збірка/консоль без помилок (HttpCase). |
| MG-22 | `ls static/src/scss` | scss лише в `static/src/*/` | Бандл `web.assets_backend`, `td_genset/static/src/**/*` (js, xml, scss) вантажиться у 19 (HttpCase). |
| MG-23 | `ls static/tests; grep QUnit` | `static/tests` немає; QUnit 0 | JS-тестів HOOT/QUnit у модулі немає (браузерні перевірки — `browser_js` у `test_w3_ui_http`). Тег `standard`/`at_install` — без змін. С — не застосовне. Зміна тестів: у `bus_service` 19 `isActive`/`workerState` — реактивні властивості, `Object.defineProperty` без `set` валив `addChannel` («'set' on proxy: trap returned falsish») → додано `set: () => {}` (`test_w3_ui_http`, 3 місця). Це доводить **С підтверджено**: `O19/addons/bus/static/src/services/bus_service.js:182-208` (`state.isActive = true`, `reactive`). |
| MG-24 | `grep "_sendone\|bus.bus"` | `bus.listener.mixin._bus_send` | Канал `td_genset_<id>` без змін; `pult_widget.js` — `addChannel`/`subscribe`; тести пульта зелені. |
| MG-25 | `grep ir.cron data/` | cron без `ir_actions_server_id` | Змін немає. Тести: `method_direct_trigger()` у 19 виконує крон в окремій транзакції → у `test_w1_link_health` (AC-10) виклик замінено на `cron.ir_actions_server_id.run()` (та сама дія, у транзакції тесту); решта викликів `method_direct_trigger` лишилась. |
| MG-26 | `grep config_parameter` | 2 | Змін немає. |
| MG-27 | `cat security/*` | CSV без змін | Групи — за MG-08; тести прав зелені. |
| MG-28 | `grep noupdate data/` | 7 блоків `noupdate="1"` | Змін немає; `eval="(4, …)"` у groups.xml/menu.xml замінено на `Command.link`. |
| MG-29 | `grep setUpClass\|freeze_time tests/` | | `cls.env`, freezegun, мок ретранслятора (локальний `RelayMock`) — без змін. Додано в `TdGensetCase.setUp`: патч `ir.cron._commit_progress` (поза cron 19 робить `cr.commit()`, у тесті це AssertionError; у cron-контексті метод коммітить прогрес партій — навмисна зміна 19). Тести, що перевіряють прогрес (`_commit_progress`), патчать його самі: сигнатура `notify(cron, processed=0, **kw)`. |
| MG-30 | `cat data/neutralize.sql` | | Таблиці/колонки (`td_genset.relay_enabled/commands_allowed`, `ir_config_parameter`, `ir_cron.active`) є; тест `test_neutralize_copy_of_production` зелений. Узгодження з CB-10 (`td.base.environment`) і preflight — окремого preflight-файла в модулі немає; лишено на менеджера/W5. |
| MG-31 | — | — | За W4/W5 (docker-стенд). |
| MG-32 | — | — | CHANGELOG 19.0.1.0.0 зроблено; `relay_api.md`, `DEPLOY_TEST.md` — за W4/W5. |

## Тести, змінені через API Odoo 19

- `test_w0_smoke` (MG-08), `test_w2_scheduler` (MG-10), `test_w3_security`, `test_w3_ui_http`, `common.py` (MG-09: `group_ids`);
- `test_w3_security.test_ac56_maintenance_done_only_tech` (MG-17: `user_id` у create);
- `test_w3_ui_http` (MG-13: `formatted_read_group`; MG-23: `set` для `isActive`/`workerState`);
- `test_w1_cleanup`, `test_w1_pull_readings`, `test_w4_fuel` (MG-13: `_commit_progress`), `common.py` (патч `_commit_progress`);
- `test_w1_link_health` (MG-25: `ir_actions_server_id.run()` замість `method_direct_trigger`).
