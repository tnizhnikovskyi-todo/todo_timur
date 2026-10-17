# td_genset (перенос 18 → 19) і factory3d_genset — специфікація

Версія 0.3 · 14.10.2026 (0.2 — 14.10.2026) · технічне рішення: `docs/modules/td_genset/ARCHITECTURE.md` (далі ARCH: CR-01…CR-10,
FR-A01…FR-A08, FR-01…FR-17, A-01…A-18, Q-01…Q-24). Контракти, на які спирається: каркас v0.2 §3, §5, §6.1–6.4, §6.7,
§6.8, D-17, D-18, D-21; `factory3d_base` CB-01, CB-02, CB-07…CB-10; `factory3d_viewer` (необов'язково, X-20) C-02, C-03,
C-07, M-01 (duck-typing, хелпер `deep_merge`), M-03, R-01, R-14, Додаток A.13; `factory3d_energy` CE-01…CE-04, R-14 п. 9;
`factory3d_iot_sim` P-07 (§8.9.4), P-12 (§8.14), API-13, API-16, S-03, S-14, §8.1.3–8.1.4, Q-07, Q-15;
`factory3d_telemetry` — каркас §6.4 і SPEC telemetry v0.1 (14.10.2026: M-02 `f3d.source`, M-03 `f3d.signal`, M-04
`f3d.reading`, M-07, M-08, CT-10 `_f3d_ingest`, CT-12 `_f3d_local_types`, R-03…R-07, R-26); розбіжності з припущеннями
цього документа зведено в §2.0.3 і мають пріоритет над текстом §2.0.2. Контракти, які задає цей документ: CG-01…CG-06
(ARCH §2.1), API-F-01…API-F-09 (§8), ADP-01…ADP-10 (§2.0.1), TEL-01…TEL-04 (§2.0.2).

Зміни: 14.10.2026 — правки за CONSISTENCY.md: X-69 (§3: пункт «Налаштування генератора» `menu_f3d_genset_settings` під
`factory3d_base.menu_f3d_config`, sequence 55, дія `action_f3d_genset_settings`; M-07: поля `f3d_genset_ats_position_i_value`/`ii_value`,
`set_values` перевіряє I ≠ II і перераховує `period_s` 26 сигналів при зміні `offline_min` за T-6; V-07; нова AC-73) (v0.3).

Зміни (v0.2): 14.10.2026 — правки за `docs/CONSISTENCY.md`: X-01 (локальне джерело лише через хук telemetry `_f3d_local_types()`,
без перевизначення `collector_id` — M-04, §2.0.3 T-1, TEL-01), X-10 (КГУ в острові — виміряне `infra/totals/chp_kw`, R-06,
AC-56), X-11 (критичні споживачі — `f3d.energy.node.is_critical`, `critical_codes` запасний, `critical_kw` пише лише energy —
R-04, M-08, §5.1), X-13 (T-6 без telemetry R-07, TEL-02 `address={"leaf": …}`), X-20 (`depends` без `factory3d_viewer` і `bus`,
провайдер за префіксом без `_inherit`), X-23 (власна `_f3d_viewer_delta` з `deep_merge`, R-13), X-41 (ATyS p за Annexe III:
положення I/II = 2/3 без стендових винятків), X-62 (§8.6: у каталозі iot_sim 1 довідковий рядок); ТК-G03/G04/G06 — тіло
запуску сценарію `{"params": {…}}` за iot_sim API-13 (як X-57); нові FR-17, R-13,
AC-69…AC-72, A-18; закрито Q-07, Q-09, Q-20, Q-21, Q-23.
Зміни: 14.10.2026 — закрито відповідями замовника (CONSISTENCY, «Відповіді на питання до замовника»): Q-01, Q-02, Q-03, Q-05, Q-06, Q-08, Q-22, Q-24.
Зміни: 14.10.2026 — закрито рішеннями менеджера: Q-10, Q-11, Q-12, Q-13, Q-14, Q-15, Q-16, Q-17, Q-18, Q-19.
Зміни: 14.10.2026 — аудит 2: X-105 (T-2: у результат `_f3d_ingest` дописано `alarms_opened`).
Зміни: 14.10.2026 — аудит 2 (доповнення): X-102 (легенда типів перевірок на початку §12; REG — складений тип регресії).

Документ має дві частини: **§A — запит на зміни до `td_genset` (чек-лист переносу MG-01…MG-32 і профіль D700
для `fake_relay.py`)** і **§0–§15 — специфікація модуля `factory3d_genset`** за `DOC_STANDARD.md`. Позначення
перевірок: UT — юніт-тест (`odoo.tests`), TC — стенд (`fake_relay` D700 + емулятор `factory3d_iot_sim`), MAN —
ручна перевірка на timur-o19demo (база `odoo`), REG — регресія `td_genset`.

Усі імена остаточні. Рядки інтерфейсу — українською в коді, без `.po` (D-14). Жодних `x_`-полів. Odoo 19:
SQL-обмеження — `models.Constraint`, хуки `post_init_hook(env)`/`uninstall_hook(env)`, `odoo.fields.Command`.

---

## §A. Запит на зміни до `td_genset`: перенос Odoo 18 → 19 (CR-01, CR-02, CR-03, CR-09, CR-10)

### A.1 Процедура

1. Гілка `19.0` від тега `18.0.2.0.2` (версія на тесті; прод — з 12.10.2026 — звірити, що прод на тому самому тезі).
2. Пройти чек-лист A.2 по порядку MG-01 → MG-32; кожен пункт — окремий коміт з посиланням на MG-xx; результат
   кожної перевірки (команда `grep`, кількість входжень до/після) — у `docs/MIGRATION_19.md` репозиторію `td_genset`.
3. Запустити 176 юніт-тестів: `odoo -d test_td19 -i td_genset --test-enable --test-tags /td_genset --stop-after-init`
   на порожній базі **без демо-даних** (MG-16) і на копії демо-бази заводу.
4. Стенд: `docker compose` `td_genset` з образом `odoo:19` (MG-31) + `fake_relay` профіль офісу → ТК-01…ТК-14 (45 сценаріїв);
   потім профіль `d700` → ті самі ТК (очікувано ті самі результати, інші числа) + нові ТК §13.3.
5. Матриця регресії ТР 1.2 AC-01…AC-69 ↔ тест/ТК (§13.2) — усі 69 позначені «зелено» або «змінено (MG-xx)».
6. DEPLOY_TEST для 19.0 (§13.6), `neutralize.sql` (MG-30), CHANGELOG `19.0.1.0.0`.

### A.2 Чек-лист змін Odoo 18 → 19 (MG-xx)

Колонка «Джерело»: О — офіційна документація/код Odoo 19 (перевірено 14.10.2026, ARCH §8); Ж — жива база
timur-o19demo (`fields_get`); С — сторонні огляди міграції (підтвердити на стенді). Колонка «Перевірка» — як
довести, що пункт закрито.

| MG | Область | Що перевірити в коді (команда) | Що зробити | Джерело | Перевірка |
|---|---|---|---|---|---|
| MG-01 | Маніфест | `cat __manifest__.py` | `version: "19.0.1.0.0"`, `installable: True`, `license` без змін, `depends` лише з модулів, що є в 19 (перевірити `ir.module.module` на демо: `maintenance`, `mail`, `bus`, `web` є); ключ `assets` — бандли `web.assets_backend`, `web.assets_unit_tests` (HOOT), `web.assets_tests` (тури) | О, Ж | модуль видно в «Застосунки» на 19.0, установка без traceback |
| MG-02 | Python | `python -m py_compile`, `grep -rn "from odoo.osv" .` | Python ≥ 3.10 синтаксис; `odoo.osv` deprecated у 19 → домени через `odoo.fields.Domain` або списки | О (changelog 19.0 «Deprecated odoo.osv») | 0 входжень `odoo.osv`, тести зелені |
| MG-03 | Хуки | `grep -n "post_init_hook\|uninstall_hook" __init__.py __manifest__.py` | сигнатура `def post_init_hook(env)` / `def uninstall_hook(env)` (з 17.0; у 18 уже так — підтвердити) | О | `-i td_genset` виконує хук без TypeError |
| MG-04 | Представлення list | `grep -rn "<tree\|</tree>\|//tree\|'tree'\|\"tree\"" views/ models/ static/ data/` | `<tree>` → `<list>`, `xpath //tree` → `//list`, `view_mode: 'tree,form'` → `'list,form'` в XML і Python; `ir.ui.view.type` у 19 не має значення `tree` (Selection: list, form, graph, pivot, calendar, kanban, search, qweb) | О (`ir_ui_view.py` 19.0 `type` Selection), С | 0 входжень; `ir.ui.view` `td_genset` усі `type='list'`; форми відкриваються |
| MG-05 | `attrs`/`states` | `grep -rn "attrs=\|states=" views/` | видалені з 17.0 → `invisible="…"`, `readonly="…"`, `required="…"`, `column_invisible="…"` з виразами Python; підтвердити 0 входжень (18.0 уже без них) | О | 0 входжень |
| MG-06 | Kanban | `grep -rn "kanban-box\|kanban-menu" views/` | шаблон картки `<t t-name="card">` замість `kanban-box` (Odoo 18+; у 19 за С — лише `card`) | С (deploymonkey, skills-guides) | kanban `td_genset` рендериться без помилки в консолі |
| MG-07 | Контекст форм | `grep -rn "active_id" views/ models/` | у контексті кнопок/дій з форми в 19 використовувати `id` (`context="{'default_genset_id': id}"`); `active_id` лишається у `ir.actions.server`/`act_window` з списку — перевірити кожне входження | С | кнопки з форми передають правильний id (ТК пульта) |
| MG-08 | Групи | `grep -rn "res.groups\|category_id\|implied_ids" security/` | `res.groups` у 19 **не має** `category_id`; створити запис `res.groups.privilege` (`name`, `category_id` → `ir.module.category`, `sequence`) і в кожній групі `privilege_id` замість `category_id`; `implied_ids` через `Command.link`; XML-id груп **не змінювати** (права 111 користувачів зберігаються) | О (`res_groups.py`, `res_groups_privilege.py` 19.0), Ж (`fields_get`) | `-u td_genset` на копії проду без ValueError; кількість користувачів у кожній групі до/після однакова (SQL `res_groups_users_rel`) |
| MG-09 | Користувачі | `grep -rn "groups_id" models/ security/ data/ tests/` | `res.users.groups_id` → `group_ids` (прямі), `all_group_ids` (транзитивні); у доменах/`search`/XML демо-користувачів; `has_group('td_genset.group_…')` — без змін | О (`res_users.py` 19.0: `group_ids`, `all_group_ids`) | 0 входжень `groups_id` у коді `td_genset` |
| MG-10 | SQL-обмеження | `grep -rn "_sql_constraints" models/` | `_sql_constraints = [(name, sql, msg)]` → атрибути класу `_<name> = models.Constraint("UNIQUE(…)", "повідомлення українською")`, `models.Index`, `models.UniqueIndex`; імена обмежень у БД лишаються `<table>_<name>` (без переіменування таблиць) | О (changelog 18.1 «Constraints and indexes as model attributes»; `res_groups.py` 19.0 використовує `models.Constraint`) | 0 входжень; тест на порушення унікальності дає `ValidationError` з тим самим текстом |
| MG-11 | Крони | `grep -rn "numbercall\|doall" data/` | прибрати `numbercall`, `doall` (поля не існують); лишити `interval_number`, `interval_type` ∈ {minutes, hours, days, weeks, months}, `nextcall`, `user_id`, `model_id`, `state="code"`, `code`, `priority`; `ir.cron` 19 має `failure_count` (деактивація після 5 збоїв за 7 днів) — крон опитування ретранслятора **не має** кидати виняток при offline (лог + `return`) | О (`ir_cron.py` 19.0), Ж | 0 входжень; крони видно в «Технічні → Заплановані дії»; симуляція offline 10 хв не вимикає крон |
| MG-12 | Контролери | `grep -rn "type='json'\|type=\"json\"\|jsonrequest" controllers/` | `type='json'` → `type='jsonrpc'` (18.1); `request.jsonrequest` → `request.get_json_data()`; `auth`, `csrf` без змін; ендпоінти, які викликає ретранслятор (push), — перевірити сумісність формату з `relay_api.md` | О (changelog 18.1) | ТК push від `fake_relay` проходить |
| MG-13 | ORM-API | `grep -rn "read_group(\|name_get\|_name_search\|check_access_rights\|check_access_rule\|self\._cr\|self\._context\|self\._uid\|\.flush()\|inselect\|group_operator\|_flush_search" models/ tests/` | `read_group` (deprecated 18.2) → `_read_group(domain, groupby, aggregates)` (кортежі) або `formatted_read_group`; `name_get` (видалено 17) → `_compute_display_name`; `_name_search` → `_search_display_name` (18); `check_access_rights/rule` → `check_access`/`has_access`/`_filtered_access` (18); `self._cr/_context/_uid` → `self.env.cr/.context/.uid` (deprecated 19); `inselect` видалено (17.4); `group_operator` → `aggregator` (17.2); `_flush_search` deprecated (17.1) | О (changelog 17.1–19.0) | 0 входжень застарілих імен; лог установки без `DeprecationWarning` від `td_genset` |
| MG-14 | RPC-поверхня | `grep -rn "def " models/*.py \| grep -v "def _"` | публічні методи, що не мають бути доступні через RPC (клієнт ретранслятора з токеном, стоп-крани), позначити `@api.private` (18.2) або перейменувати з `_` | О (changelog 18.2) | `call_kw` на приватний метод → помилка доступу (тест безпеки) |
| MG-15 | `Command` | `grep -rn "(6, 0\|(4, \|(0, 0\|(2, \|(3, " models/ data/ tests/` | трійки лишаються сумісними; де правиться код — `from odoo.fields import Command` | О | — |
| MG-16 | Демо-дані | `grep -rn "demo" __manifest__.py; grep -rn "ref('base\.\|ref(\"base\." tests/` | у 18.3+ демо-дані не вантажаться за замовчуванням; тести, що покладаються на демо `res.partner`/`hr.employee`/`maintenance.*`, створюють власні фікстури в `setUpClass` | О (changelog 18.3) | 176 UT зелені на базі без демо |
| MG-17 | `mail` | `grep -rn "message_post\|_track_subtype\|activity_schedule\|mail.template\|render_template\|_render_field" models/` | `message_post(body=Markup(...), subtype_xmlid=...)`; `mail.template._render_field(...)` (не `render_template`); `mail.activity` `activity_schedule(act_type_xmlid, date_deadline, summary)`; перевірити `website_message_ids` у формах (поле є в 19) | Ж (`maintenance.request` має `website_message_ids`), О | ескалація тривог (пошта/activity) проходить у ТК |
| MG-18 | Переклади | `grep -rn "from odoo import .*_\b\|_(" models/ \| head` | `from odoo import _` працює; `self.env._(...)` — рекомендовано (18.0: переклади з `Environment`); `.po` `td_genset` лишаються як є (D-14 стосується модулів factory3d) | О | рядки UI у 19 без `Translation not found` у логах |
| MG-19 | `safe_eval` | `grep -rn "safe_eval" models/` | контексти `safe_eval` без `__import__`, модулі лише через `wrap_module`; формули розкладу/порогів — перевірити, що виконуються в 19 | О | UT розкладу зелені |
| MG-20 | OWL: RPC | `grep -rn "useService(\"rpc\")\|useService('rpc')\|jsonrpc\|@web/legacy" static/src/` | `rpc` з `@web/core/network/rpc` (`import { rpc } from "@web/core/network/rpc"`), `jsonrpc` видалено; `orm` через `useService("orm")` — ок; `session` з `@web/session` | С (skills-guides: `rpc`-сервіс недоступний у 19), підтвердити на стенді | пульт: кнопки «Авто», старт/стоп, тест 3 хв працюють (ТК пульта) |
| MG-21 | OWL: компоненти | `grep -rn "constructor(\|static props\|setup()" static/src/` | OWL 2: `setup()` замість `constructor`, `static template`, `static props` (валідація у dev), `registry.category("actions").add("td_genset.pult", …)`, `_t` з `@web/core/l10n/translation` | С (вимога `setup()` — stронні джерела), О (OWL 2 з 16.0) | консоль без помилок у `?debug=assets` |
| MG-22 | Assets | `grep -rn "assets" __manifest__.py; ls static/src/scss` | бандли `web.assets_backend`, `web._assets_primary_variables` існують у 19; шляхи `td_genset/static/src/**/*`; QWeb-шаблони `.xml` у `static/src` | О | `/web` вантажиться, бандл містить файли `td_genset` (debug=assets) |
| MG-23 | Тести JS/тури | `ls static/tests; grep -rn "QUnit\|browser_js\|start_tour" static/tests tests/` | JS-юніт-тести → HOOT (`@odoo/hoot`), тури → `start_tour` з `HttpCase`; `@tagged("post_install", "-at_install")` на класах; `odoo.tests.Form` для форм | О (теги), С (HOOT у 19) | `--test-tags /td_genset` виконує й JS-тести |
| MG-24 | Шина | `grep -rn "_sendone\|_sendmany\|bus.bus" models/` | `self.env["bus.bus"]._sendone(channel, notification_type, message)` — сигнатура та сама; канали-рядки без `(db, name)`; перевірити підписку пульта (`useBus`/`bus_service.subscribe`) | О | живе оновлення пульта при зміні стану (ТК) |
| MG-25 | `ir.cron` ↔ `ir.actions.server` | `grep -rn "ir.cron" data/` | `_inherits ir.actions.server` (як у 18): поля `model_id`, `state`, `code` на записі крона — ок; `ir_actions_server_id` не задавати вручну | О | — |
| MG-26 | Налаштування | `grep -rn "config_parameter" models/res_config_settings.py` | поля `res.config.settings` з `config_parameter` — без змін; перевірити `module_*` поля | О | сторінка «Налаштування → td_genset» відкривається |
| MG-27 | Права | `cat security/ir.model.access.csv security/*.xml` | формат CSV без змін; `ir.rule` `groups` без змін; `perm_*`; групи за MG-08 | О | тести прав зелені |
| MG-28 | Data-файли | `grep -rn "noupdate" data/` | `noupdate="1"` на параметрах/кронах/послідовностях; `eval="[(6,0,…)]"` можна лишити або `Command.set` | О | `-u` не затирає налаштування |
| MG-29 | Тести Python | `grep -rn "setUpClass\|TransactionCase\|HttpCase\|freeze_time" tests/` | `cls.env` у `setUpClass`; `freezegun` є в залежностях Odoo 19; `MockRequest`/`patch` без змін; мережеві виклики до ретранслятора мокаються (`unittest.mock.patch` на клієнт) | О | 176 UT без мережі |
| MG-30 | `neutralize.sql`, preflight | `cat neutralize.sql preflight.*` | таблиці/колонки існують у 19 (`ir_cron.active`, `ir_config_parameter.key/value`); узгодити з CB-10: після `neutralize.sql` `factory3d.base.environment='test'` → стоп-крани `td_genset` і моста в тестовому положенні; preflight перевіряє версію сервера `19.0` | Ж, CB-10 | `psql -f neutralize.sql` на копії проду без помилок; крони вимкнені; адреса ретранслятора стендова |
| MG-31 | Docker-стенд | `cat docker-compose*.yml Dockerfile relay/Dockerfile` | образ `odoo:19` (або збірка з `odoo/odoo` 19.0), PostgreSQL версії, яку вимагає Odoo 19 (ЗВІРИТИ в `odoo/setup` 19.0; мінімум 13), Python `fake_relay` — 3.12 (як `services/iot_sim`), `requirements.txt` із закріпленими версіями; порт `fake_relay` 8000 (`SIM_GENSET_RELAY_URL=http://genset_relay:8000` в iot_sim §8.2.1) | iot_sim §8.1.3–8.1.4 | `docker compose up` стенда `td_genset` і `docker compose --profile demo up genset_relay` з `services/iot_sim` обидва піднімаються |
| MG-32 | Документи | — | `relay_api.md` + розділ «Емуляція (API-F-01…09)», CHANGELOG `19.0.1.0.0` (перелік MG-xx), DEPLOY_TEST.md для 19.0, інструкції (ARCH §4.4, §4.5) | — | файли оновлені, рецензовані менеджером |

Де чек-лист спирається на С (MG-06, MG-07, MG-20, MG-21, MG-23), розробник W1 обов'язково підтверджує
поведінку на стенді 19.0 і записує в `docs/MIGRATION_19.md` «підтверджено/спростовано» з посиланням на
файл коду Odoo 19, який це доводить.

### A.3 Регресія: які AC `td_genset` перевіряються повторно

Усі **AC-01…AC-69** ТР 1.2 — повторно (CR-09), без винятків. Обов'язково вручну (MAN) на стенді 19.0, крім
автоматики, — блоки підвищеного ризику: пульт OWL (MG-20…MG-23), групи й права (MG-08, MG-09), крони опитування
ретранслятора й розкладу (MG-11), kanban/list представлення (MG-04, MG-06), ескалація тривог через `mail`
(MG-17), ендпоінти push від ретранслятора (MG-12). Матриця `REGRESSION_19.md`: рядок на AC — `AC-xx | тест/ТК |
результат 18.0 | результат 19.0 | MG-xx, якщо змінювалось`. Тестувальник (W5) не читає код переносу: він бере
ТР 1.2 SPEC і ганяє тести/ТК як є; розбіжність — дефект переносу, а не оновлення тесту (крім випадків, явно
перелічених у `MIGRATION_19.md` з посиланням на MG-xx).

### A.4 Профіль D700 для `fake_relay.py` і REST для емулятора

Описано в §8 (сервісна частина): формат профілю (§8.2), стан-машина HGM6120N (§8.3), REST API-F-01…API-F-09
(§8.4), compose (§8.5), контракт з емулятором (§8.6). Клієнтська сторона `td_genset` ↔ `fake_relay` (ендпоінти
`relay_api.md`) **не змінюється**: профіль змінює лише числа (бак, витрата, потужності, таймери) і додає
окремий префікс `/sim/v1/*` для керування симуляцією.

---

## 0. Дерево файлів модуля `factory3d_genset`

```
odoo_addons/factory3d_genset/
├── __init__.py                      from . import models, adapters, hooks; from .hooks import post_init_hook, uninstall_hook
├── __manifest__.py                  §1
├── hooks.py                         post_init_hook(env), uninstall_hook(env) — §5.3, §5.4
├── neutralize.sql                   §5.5
├── README.md                        що робить міст, залежності, параметри, як підключити генератор (ARCH §4.1)
├── CHANGELOG.md                     19.0.1.0.0 — перший випуск
├── adapters/
│   ├── __init__.py
│   ├── td_genset.py                 ADP-01…ADP-10: константи імен td_genset (ЗВІРИТИ) + функції читання
│   └── telemetry.py                 TEL-01…TEL-04: джерело, сигнали, прийом показань, читання значень
├── models/
│   ├── __init__.py                  порядок: genset_profile, genset_event_map, genset_link, f3d_source,
│   │                                maintenance_equipment, maintenance_request, res_config_settings, viewer_provider
│   ├── genset_profile.py            M-02 f3d.genset.profile (+ R-01, R-02, експорт профілю для fake_relay)
│   ├── genset_event_map.py          M-03 f3d.genset.event.map (+ R-07 match/render)
│   ├── genset_link.py               M-01 f3d.genset.link (+ publish, events, service, island — R-03…R-05, R-08, R-09, R-12)
│   ├── f3d_source.py                M-04 selection_add td_genset + хук _f3d_local_types() (X-01)
│   ├── maintenance_equipment.py     M-05
│   ├── maintenance_request.py       M-06 (+ закриття заявки → статус сигналу, R-08 крок 4)
│   ├── res_config_settings.py       M-07
│   └── viewer_provider.py           M-08 f3d.viewer.provider.genset — за префіксом, без _inherit (R-05, R-06, R-10, R-11, R-13)
├── views/
│   ├── genset_link_views.xml        V-01, V-02 + дії
│   ├── genset_profile_views.xml     V-03, V-04
│   ├── genset_event_map_views.xml   V-05
│   ├── maintenance_views.xml        V-06 (equipment), V-09 (request)
│   ├── res_config_settings_views.xml V-07 + дія `action_f3d_genset_settings` (X-69)
│   └── menus.xml                    V-08
├── security/
│   └── ir.model.access.csv          §4.1
├── data/
│   ├── ir_config_parameter.xml      §5.1 (noupdate)
│   ├── f3d_genset_profile.xml       §5.2 профіль D700 (noupdate="0")
│   ├── f3d_genset_event_map.xml     §5.2 мапа подій HGM6120N (noupdate="0")
│   └── ir_cron.xml                  §6 (noupdate)
├── static/description/icon.png      іконка (генератор)
└── tests/
    ├── __init__.py
    ├── common.py                    фікстури §13.0: обладнання GENSET з паспортом, профіль, мок адаптера td_genset
    ├── test_adapter_contract.py     ADP-xx: fields_get на константи (падає, поки імена не звірені)
    ├── test_rules.py                R-01…R-06, R-11
    ├── test_publish.py              крон publish, сигнали, stale/offline (R-12)
    ├── test_events.py               мапа подій, заявки, дедуплікація (R-07, R-08)
    ├── test_service.py              ТО за мотогодинами (R-09)
    ├── test_provider.py             провайдер 155, картка, тотали, шина, дельта deep_merge (R-10, R-13, CG-02, CG-05; лише з viewer)
    ├── test_no_viewer.py            база без factory3d_viewer: установка, публікація, події, без f3d.viewer.event (FR-17, AC-71)
    ├── test_access.py               права, стоп-крани
    ├── test_hooks.py                post_init/uninstall, neutralize
    ├── test_views.py                V-01…V-09: представлення завантажуються, меню й групи
    ├── test_static.py               grep-тести коду модуля (AC-34, AC-41, §14)
    └── stand/                       ТК-G01…ТК-G13 (pytest, §13.3): conftest.py, orchestrator.py, test_tk_g*.py
```

Файли, яких торкається запит на зміни в репозиторії `td_genset` (W1, W4): `__manifest__.py`, `security/*.xml`,
`views/*.xml`, `models/*.py` (за MG-xx), `static/src/**` (пульт), `data/ir_cron*.xml`, `controllers/*.py`,
`tests/*`, `neutralize.sql`, `preflight*`, `docker-compose*.yml`, `relay/fake_relay.py`, `relay/profiles/office.json`
(існуючий профіль, винесений у файл — якщо його ще нема), `relay/profiles/d700.json` (новий), `relay/profiles/d700_slow.json` (фікстура ТК-G04: `warming_s=60`), `relay/Dockerfile`,
`relay/tests/test_sim_api.py` (новий), `relay_api.md`, `CHANGELOG.md`, `DEPLOY_TEST.md`, `docs/MIGRATION_19.md`
(новий), `docs/REGRESSION_19.md` (новий), `docs/ADAPTER_MAP.md` (новий — таблиця імен для ADP-xx).

## 1. Маніфест

```python
{
    "name": "Завод 3D: генератор (td_genset)",
    "summary": "Зв'язка генератора td_genset з моделлю заводу: телеметрія, заявки ТО, картка в 3D, баланс при блекауті",
    "version": "19.0.1.0.0",
    "author": "ToDo",
    "license": "LGPL-3",
    "category": "Manufacturing/Maintenance",
    "depends": ["td_genset", "factory3d_base", "factory3d_telemetry", "factory3d_energy"],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_config_parameter.xml",
        "data/f3d_genset_profile.xml",
        "data/f3d_genset_event_map.xml",
        "data/ir_cron.xml",
        "views/genset_profile_views.xml",
        "views/genset_event_map_views.xml",
        "views/genset_link_views.xml",
        "views/maintenance_views.xml",
        "views/res_config_settings_views.xml",
        "views/menus.xml",
    ],
    "post_init_hook": "post_init_hook",
    "uninstall_hook": "uninstall_hook",
    "installable": True,
    "application": False,
    "external_dependencies": {"python": []},
}
```

Порядок `data` важливий: профіль до мапи й до представлень (дія «Експорт профілю» посилається на профіль);
меню — останнім. Без `assets`: пульт — у `td_genset`, переглядач — у `factory3d_viewer`.

`depends` — точно за каркасом §3 і D-18 (X-20): `factory3d_viewer` і `bus` **не** входять. `maintenance` приходить
транзитивно через `factory3d_base`; `bus.bus` міст напряму не викликає. Зв'язок із переглядачем необов'язковий:
провайдер M-08 — `AbstractModel` з префіксом `f3d.viewer.provider.` без `_inherit` (viewer збирає провайдерів за префіксом,
M-01/R-01); події шини — лише якщо `"f3d.viewer.event" in env` (M-01 `_notify_state_change`); хелпер `deep_merge` viewer
імпортується всередині методу дельти R-13 (метод викликає лише viewer, отже модуль у реєстрі є). Без viewer міст
встановлюється й працює (публікація, події, заявки, ТО) — FR-17, AC-71.

## 2. Моделі

### 2.0 Адаптери (єдине місце звірки з іншими модулями)

#### 2.0.1 `adapters/td_genset.py` — ADP-01…ADP-10 (CR-04, A-09)

Файл починається з блоку констант, кожна з коментарем `# ЗВІРИТИ з td_genset (ADP-xx, Q-10…Q-19)`. Поки
константа дорівнює `None`, відповідна функція кидає `NotImplementedError("ADP-xx: звірити з td_genset")`, а
`tests/test_adapter_contract.py` падає з переліком незвірених імен — це навмисно: міст не вгадує.

| ID | Сигнатура | Повертає | Алгоритм / вимоги |
|---|---|---|---|
| ADP-01 | `GENSET_MODEL: str \| None` (константа) | ім'я моделі «генератор» у `td_genset` | звірити; використовується в `Reference`-полі M-01 і в `generators()` |
| ADP-02 | `generators(env) -> models.Model` | активні записи генераторів | `env[GENSET_MODEL].search([("active","=",True)])` якщо є `active`, інакше `search([])`; порядок за `id` |
| ADP-03 | `snapshot(gen) -> dict` | останній знімок показань | ключі (усі можуть бути `None`, якщо `td_genset` їх не має): `ts` (datetime UTC останнього показання), `online` (bool: ретранслятор відповідає і дані свіжі за правилом `td_genset`), `state_raw` (str — стан за `td_genset`), `mode_raw` (str), `mains_ok` (bool), `breaker_raw` (str: мережа/генератор/жодного), `p_kw` (float, сумарна активна), `u_v` (float, середня лінійна напруга генератора), `f_hz`, `i_a` (max фази), `pf`, `kwh` (накопичена енергія), `fuel_pct`, `fuel_l`, `hours` (мотогодини), `starts`, `coolant_c`, `oil_bar` (якщо кПа → /100), `batt_v`, `charger_v`, `rpm`, `alarms` (list[dict]: `code`, `name`, `severity` ∈ {warning, shutdown}, `since`), `mains_u_v`, `mains_f_hz`. Реалізація читає поля через константи `FIELD_*`; відсутні → `None` |
| ADP-04 | `events_since(gen, since: datetime \| None, limit: int = 200) -> list[dict]` | події журналу `td_genset` новіші за `since` | ключі: `id` (int), `ts` (datetime UTC), `code` (str; regex `^[A-Za-z0-9_.-]{1,64}$`, інакше `""`), `severity` ∈ {info, warning, shutdown, comm, service, command}, `name` (str), `value` (float\|None), `unit` (str\|None), `threshold` (float\|None), `text` (str). Порядок `ts, id`; `since=None` → останні 24 год |
| ADP-05 | `service_info(gen) -> dict` | ТО за мотогодинами | `hours_now`, `interval_h`, `next_service_hours`, `last_service_hours`, `last_service_date`, `due` (bool за `td_genset`), `hours_left` = `next_service_hours − hours_now` (≥ 0 або від'ємне = прострочено) |
| ADP-06 | `schedule_info(gen) -> dict` | розклад | `enabled` (bool), `windows` (list[str] людською мовою, напр. «Пн–Пт 08:45–18:45»), `timer_vs_schedule` (str\|None) — лише для картки |
| ADP-07 | `last_test(gen) -> dict \| None` | останній тестовий пуск | `ts`, `duration_min`, `result` (str: «норма»/текст `td_genset`) |
| ADP-08 | `open_action(gen) -> dict` | `ir.actions.act_window` на запис генератора `td_genset` | `{"type":"ir.actions.act_window","res_model":GENSET_MODEL,"res_id":gen.id,"view_mode":"form","target":"current"}` |
| ADP-09 | `set_fuel_rate(gen, lph: float) -> bool` | записати еквівалентну витрату (CR-05) | якщо `td_genset` має сталу витрату — записати `lph` і повернути `True`; якщо має криву або поля немає — `False` без запису. Викликається лише з кнопки профілю «Застосувати до td_genset» (менеджер), ніколи з крона |
| ADP-10 | `STATE_MAP`, `MODE_MAP`, `BREAKER_MAP: dict[str, int]` | відповідність сирих значень `td_genset` → коди R-03 | ключі — рядки `td_genset` у нижньому регістрі; невідоме → `None` → код `0` (невідомо/офлайн) з записом у `last_publish_error` «невідомий стан: …» |

Усі функції — чисті читання (`search`, `read`, `browse`); жодного `write`/`create` у моделях `td_genset`, крім ADP-09.
Тест-контракт: для кожної константи `FIELD_*`/`GENSET_MODEL` — `GENSET_MODEL in env` і `name in env[GENSET_MODEL]._fields`
(або в моделі показань/подій за константами `READING_MODEL`, `EVENT_MODEL`).

#### 2.0.2 `adapters/telemetry.py` — TEL-01…TEL-04 (каркас §6.4, Q-04)

| ID | Сигнатура | Алгоритм |
|---|---|---|
| TEL-01 | `ensure_source(env, link) -> f3d.source` | `search([("code","=","GENSET-RELAY")], limit=1)`; немає → `create({"code": "GENSET-RELAY", "name": "Ретранслятор SmartGen (td_genset)", "type": "td_genset", "module": "genset", "equipment_id": link.equipment_id.id, "params": {}, "read_enabled": True, "period_s_default": 60})` — без `collector_id` (локальний тип за хуком telemetry `_f3d_local_types()`, CT-12/R-26, M-04; X-01); поля `address` у `f3d.source` немає; записати в `link.source_id` (§2.0.3 T-1) |
| TEL-02 | `ensure_signals(env, link) -> dict[str, f3d.signal]` | для кожного рядка Додатка A: `search([("code","=",code)])`; немає → `create({"code", "name", "equipment_id": link.equipment_id.id, "source_id": link.source_id.id, "unit", "kind" (§2.0.3 T-5), "period_s": max(60, offline_min·20) (T-6), "store_period_s": 0, "scale": 1.0, "viewer_visible": True, "create_request": False, "alarm_states": [], "address": {"leaf": leaf}})` (адреса — JSON-об'єкт, довідково: на локальному джерелі telemetry її не перевіряє, R-26; X-13); пороги — лише T-4 (`alarm_level`: `alarm_high_on=True`, `alarm_high=0.5`), решта `*_on=False` (A-05); повертає `{code: signal}` |
| TEL-03 | `ingest(env, batch: list[dict]) -> dict` | `batch = [{"code", "ts" (datetime UTC), "value" (float), "q" (0/1)}]`. Якщо `hasattr(env["f3d.signal"], "_f3d_ingest")` → `return env["f3d.signal"]._f3d_ingest(batch)` (CT-01, той самий метод, що й `POST /f3d/telemetry/push`). Інакше запасний шлях: для кожного елемента — `signal = by_code[code]`; якщо `f3d.reading` з `(signal_id, ts)` уже є → пропустити (ідемпотентно); `create f3d.reading {ts, signal_id, value, quality: q}`; `signal.write({"last_value": value, "last_ts": ts, "status": "ok" if q else "stale"})`. Повертає `{"accepted": n, "skipped": m}` |
| TEL-04 | `read_values(env, codes: list[str]) -> dict[str, tuple[float \| None, datetime \| None, str]]` | `search_read([("code","in",codes)], ["code","last_value","last_ts","status"])` → `{code: (value, ts, status)}`; відсутній код → відсутній ключ |

Імена полів `f3d.signal`/`f3d.reading`/`f3d.source` — константи у верхній частині файлу (`SIGNAL_CODE="code"`, …) з
коментарем «за каркасом §6.4; звірити зі SPEC factory3d_telemetry M-xx». `test_adapter_contract.py` перевіряє їх через
`fields_get` так само, як ADP.

#### 2.0.3 Звірка з SPEC `factory3d_telemetry` v0.1 (14.10.2026) — рішення A-15 (обов'язкові для W2 і тестів)

SPEC telemetry з'явився після §2.0.2; де він конкретніший, діє цей рядок (він має пріоритет над §2.0.2, M-04…M-06, R-09,
R-12 у частині, що тут названа). Q-20 закрито: telemetry дає хук CT-12 `_f3d_local_types()` і правило R-26 (X-01).

| # | Припущення моста | Факт у telemetry v0.1 | Рішення для моста |
|---|---|---|---|
| T-1 | `f3d.source` без колектора з маркером адреси «local» (скасовано, X-01) | M-02: `code` (req, `^[A-Z0-9][A-Z0-9\-\.]{0,31}$`), `collector_id` (обов'язковий для всіх типів, крім локальних — constraint telemetry `_check_f3d_collector_required`, R-26), `params` (Json, `validate_params(type, params, self._f3d_local_types())`), `module` ∈ … `genset`; поля `address` немає; хук CT-12 `@api.model _f3d_local_types() -> list[str]` (базово `[]`) | TEL-01 створює `{"code": "GENSET-RELAY", "name": "Ретранслятор SmartGen (td_genset)", "type": "td_genset", "module": "genset", "equipment_id": eq.id, "params": {}, "read_enabled": True, "period_s_default": 60}`; пошук — `search([("code","=","GENSET-RELAY")], limit=1)`. Локальність — **лише** через хук (X-01, D-17): M-04 `_f3d_local_types()` повертає `super()._f3d_local_types() + ["td_genset"]`; міст **не** перевизначає `collector_id` і **не** має власного constraint на колектор (перевірку `_check_f3d_collector_required` і `validate_params` з `local_types` робить telemetry). Наслідки R-26: `is_local=True`, `collector_id` порожній, `validate_params("td_genset", {}, local_types)` → `[]`, джерело не потрапляє в API-01 і крони R-07/R-25, показання — лише CT-10 `_f3d_ingest(…, src="module")`, команди — `UserError` |
| T-2 | `ingest` з `q` 0/1, повертає `skipped` | CT-10 `_f3d_ingest(readings, src="module")`, `readings=[{"code","ts","value","text","q"}]`, `q` ∈ `good/uncertain/bad`; повертає `{"accepted","stored","duplicates","rejected","changed_codes","alarms_opened"}` (`rejected[]` може містити й прийняті показання з `reason='unknown_state'`, telemetry CT-10, X-105); `q="bad"` статус не змінює (R-04); R-03 пише в `f3d.reading` лише за політикою `store_period_s` | TEL-03 викликає `_f3d_ingest(batch, src="module")` з `q="good"` і повертає `{"accepted": r["accepted"], "stored": r["stored"], "skipped": r["accepted"] - r["stored"]}` (ключ `skipped` у AC-10 — саме це число). Запасний шлях §2.0.2 не реалізується (метод є) |
| T-3 | R-12: при застарілих даних «`q=0` → `status=stale`» | `q="bad"` статус не змінює; є `f3d.signal._mark_stale(reason)` (R-07) | Не `fresh` (R-12) → TEL-03 публікує лише 4 похідні сигнали з `ts=now`, `q="good"`: `online=0`, `state=0`, `fuel_lph=0`, `autonomy_h` (останній `fuel_l` при 75 %); решта 22 сигнали → `_mark_stale("td_genset: немає свіжих даних")` (ідемпотентно, чаттер — раз на перехід). Наступний свіжий знімок повертає статус за R-04 |
| T-4 | Пороги «порожні» (`alarm_state`) | M-03: `warn_low/…/alarm_high` + прапори `warn_low_on/…/alarm_high_on` (default `False`), `alarm_states` (Json), `create_request` (**default `True`**) | TEL-02 для всіх 26: `create_request=False`, `alarm_states=[]`, усі `*_on=False`; виняток — `alarm_level`: `alarm_high_on=True`, `alarm_high=0.5` (статус `alarm` при значенні ≥ 1 — R-08 крок 4; заявку telemetry не створює, бо `create_request=False`) |
| T-5 | `kind='state'` для кодів стану (A-10) | `kind='state'` — значення як індекс у `states`/текст, числові пороги заборонені constraint'ом | Коди `state`, `mode`, `breaker`, `mains_ok`, `alarm_level`, `alarm_count`, `online` — `kind='gauge'`; `kwh`, `hours`, `starts` — `counter`; решта — `gauge` (Додаток A). A-10 у частині `kind` замінено; числовий код 0…10 лишається |
| T-6 | `period_s=60` | M-03: `period_s` — очікуваний період оновлення сигналу; R-26: сигнали локального джерела крон stale telemetry **не бачить** — `stale` за таймаутом не настає, його ставить лише власник через `_mark_stale(reason)`; R-03: `store_period_s` default 300 | TEL-02: `period_s = max(60, offline_min·20)` (умовчання 100 с — те саме значення, що в прикладі telemetry R-26/AC-92) — довідковий очікуваний період, який для людини й діагностики дає ті самі «3 періоди» = `offline_min` (5 хв), що й поріг моста; `stale` для 22 сигналів ставить **лише** міст (R-12, T-3: `_mark_stale` при не-`fresh` знімку; X-13). `store_period_s = 0` (кожна публікація моста зберігається: 26 × 1 440 = 37 440/добу, ARCH §2.7). Публікація лишається раз на 60 с. Зміна `offline_min` у налаштуваннях (M-07 `set_values`) перераховує `period_s` 26 сигналів GENSET; повторний хук наявних сигналів не змінює |
| T-7 | `f3d_meter_signal_id` = `hours` без інтервалу (A-04) | M-07: constraint «Задайте інтервал ТО за лічильником (> 0)»; з інтервалом telemetry R-11 сам створює планові заявки | Міст **не** ставить `f3d_meter_signal_id` (§5.3 крок 7 і R-09 крок 6 скасовано); ТО веде лише `td_genset` + R-09 моста (A-04 без змін за змістом) |
| T-8 | Міст «заповнює» `f3d_equipment_code` | M-08: `f3d_equipment_code` = `related equipment_id.f3d_code`, `store=True`; є `f3d_value`, `f3d_threshold`, `f3d_origin` | R-07 vals **без** `f3d_equipment_code` (значення дає related); додати `f3d_value = ev["value"]`, `f3d_threshold = ev["threshold"]` (якщо не `None`); `f3d_origin` не задається (заявка не з порогу telemetry) |
| T-9 | M-06 пише `status="ok"` при закритті | M-08 `write` при переході в `done` викликає `f3d_signal_id._on_request_closed()` (R-06: статус перераховується з `last_value`) | M-06 `_f3d_genset_on_closed` статус **не** пише; лише `link.message_post("Заявку … закрито")`. Ефект R-08 крок 4 дає telemetry R-06 (alarm_level 0 → `ok`, ≥ 1 → `alarm`) |
| T-10 | `infra.totals.genset_kva`, `critical_kw` — Float | viewer Додаток A.13: `genset_kva int`, `critical_kw int`; energy CE-03: `critical_kw` пише провайдер `infra` energy | провайдер пише `int(round(profile.kva_prp))`; `infra.totals.critical_kw` міст **не** пише (X-11 — власність energy CE-03/CE-04; рядок картки «Критичні споживачі зараз» рахує R-04); нові ключі `genset_*`, `island`, `grid_ok`, вузол `infra.genset` — схема 1.1 приймає їх адитивно (X-24, каркас §6.7; Q-23 закрито) |

Тестованість (обов'язково для коду): модулі моста викликають адаптери **через атрибут модуля** (`from ..adapters import
td_genset as td` → `td.snapshot(...)`, `td.GENSET_MODEL`), а не `from ..adapters.td_genset import snapshot`, — інакше
`unittest.mock.patch` фікстури §13.0 не діє; `_td_models()` читає `td.GENSET_MODEL` у момент виклику.

### M-01 `f3d.genset.link` — зв'язка генератора з моделлю заводу (FR-01, FR-03, FR-08, FR-09, FR-11, FR-15)

```python
class F3dGensetLink(models.Model):
    _name = "f3d.genset.link"
    _description = "Генератор: зв'язка з моделлю заводу"
    _inherit = ["mail.thread"]
    _order = "equipment_id"
    _rec_name = "name"
```

| Поле | Тип | Параметри |
|---|---|---|
| `name` | Char | `compute="_compute_name"`, `store=True`: `"%s (%s)" % (equipment_id.name, equipment_id.f3d_code or "—")` |
| `equipment_id` | Many2one `maintenance.equipment` | `string="Обладнання"`, `required=True`, `ondelete="restrict"`, `index=True`, `domain="[('f3d_passport_id.role','=','genset')]"`, `tracking=True` |
| `f3d_code` | Char | `related="equipment_id.f3d_code"`, `string="Код сцени"` |
| `td_genset_ref` | Reference | `selection="_td_models"`, `string="Генератор td_genset"`, `required=True`; `_td_models` → `[(adapters.td_genset.GENSET_MODEL, "Генератор td_genset")]` якщо константа задана й модель є в реєстрі, інакше `[]` |
| `profile_id` | Many2one `f3d.genset.profile` | `string="Профіль"`, `required=True`, `default=lambda self: self.env.ref("factory3d_genset.profile_d700", raise_if_not_found=False)`, `ondelete="restrict"` |
| `source_id` | Many2one `f3d.source` | `string="Джерело телеметрії"`, `readonly=True`, `ondelete="set null"` |
| `publish_enabled` | Boolean | `string="Публікувати в телеметрію"`, `default=True`, `tracking=True` |
| `amf_master` | Selection | `[("hgm","HGM6120N веде AMF"),("ats","ATyS p головний")]`, `compute="_compute_amf_master"` (з параметра `factory3d.genset.amf_master`), не зберігається, `string="Логіка AMF"` |
| `last_publish_ts` | Datetime | `string="Остання публікація"`, `readonly=True` |
| `last_publish_error` | Char | `string="Помилка публікації"`, `readonly=True` |
| `last_event_ts` | Datetime | `string="Остання оброблена подія"`, `readonly=True` |
| `last_event_id` | Integer | `readonly=True`, `default=0` |
| `last_state_json` | Json | `string="Останній знімок"`, `readonly=True` — dict з `state`, `mode`, `breaker`, `alarm_level`, `island`, `grid_ok`, `online` (коди R-03/R-05) |
| `last_state_text` | Char | `compute="_compute_last_state_text"` (не зберігається), `string="Знімок (JSON)"` — `json.dumps(last_state_json or {}, ensure_ascii=False, indent=1)` (V-01) |
| `online` | Boolean | `compute="_compute_live"`, `string="На зв'язку"` — з `last_state_json.online` |
| `state_code` | Integer | `compute="_compute_live"` — `last_state_json.state` |
| `state_label` | Char | `compute="_compute_live"` — текст за R-03 |
| `island` | Boolean | `compute="_compute_live"`, `string="Острів (від генератора)"` |
| `signal_count` | Integer | `compute="_compute_counts"` — `f3d.signal` з `equipment_id` і `code like "infra/genset/%s/%%" % f3d_code` |
| `request_open_count` | Integer | `compute="_compute_counts"` — відкриті `maintenance.request` з `equipment_id` і `f3d_genset_event_key != False` |
| `active` | Boolean | `default=True` |
| `company_id` | Many2one `res.company` | `default=lambda self: self.env.company` |

```python
    _equipment_uniq = models.Constraint("UNIQUE(equipment_id)", "Для цього обладнання зв'язка вже існує.")
    _td_ref_uniq = models.Constraint("UNIQUE(td_genset_ref)", "Цей генератор td_genset уже зв'язано.")
```

`@api.constrains("equipment_id")`: `equipment_id.f3d_code` порожній → `ValidationError("Обладнання не має коду сцени
(f3d_code). Заповніть «Завод 3D → Код сцени» в base.")`; `equipment_id.f3d_passport_id.role != "genset"` →
`ValidationError("Паспорт обладнання має роль «%s», потрібна «genset».")`.

Методи (усі крім `action_*` — приватні, `@api.private` не потрібен для `_`):

| Сигнатура | Алгоритм |
|---|---|
| `_param(self, key, default)` | `self.env["ir.config_parameter"].sudo().get_param("factory3d.genset." + key, default)`; булеві: `in ("True","true","1")` |
| `_read_enabled(self)` | `_param("read_enabled", "True" if environment == "test" else "False")` де `environment = get_param("factory3d.base.environment","test")` (CB-10) |
| `_cron_publish(self)` (`@api.model`) | якщо не `_read_enabled()` → `return`; для `search([("publish_enabled","=",True)])`: `try: with self.env.cr.savepoint(): link._publish_one()` `except Exception as e: link.last_publish_error = "%s: %s" % (type(e).__name__, e)[:250]; _logger.exception(...)` — виняток **не** піднімається (MG-11: `failure_count`) |
| `_publish_one(self)` | 1) `snap = adapters.td_genset.snapshot(self.td_genset_ref)`; 2) `signals = adapters.telemetry.ensure_signals(env, self)` (кешує в `self.env.cr.cache`? — ні: викликати раз, результат ≤ 26 записів); 3) `vals = self._compute_values(snap)` (R-03, R-01, R-02, R-09: dict `leaf → float`); 4) `ts = snap["ts"] or now`; `q = 1 if snap["online"] and (now − ts) ≤ offline_min else 0`; 5) `batch = [{"code": prefix+leaf, "ts": ts, "value": v, "q": q} for leaf, v in vals.items() if v is not None]`; 6) `adapters.telemetry.ingest(env, batch)`; 7) `new_state = {...}` (R-03/R-05/R-12); якщо `new_state != (last_state_json or {})` за ключами `state, mode, alarm_level, island, grid_ok, online` → `self._notify_state_change(new_state)`; 8) `write({"last_publish_ts": now, "last_publish_error": False, "last_state_json": new_state})` |
| `_compute_values(self, snap) -> dict` | R-03 (коди), `p_kw`, `load_pct`, `fuel_l` (якщо `None` і є `fuel_pct` → `fuel_pct/100·tank_l`), `fuel_lph` (R-01; `0.0` якщо `state` ∉ {6,7}), `autonomy_h` (R-02; `None` якщо `fuel_lph==0`), `service_h_left` (ADP-05 `hours_left`), `alarm_level` (2 якщо є `shutdown`, 1 якщо `warning`, 0), `alarm_count`, `online` (1/0), решта напряму |
| `_island_state(self, snap) -> dict` | R-05 → `{"island": bool\|None, "grid_ok": bool\|None, "source": "ats"\|"hgm"\|"stale"}` |
| `_critical_kw(self) -> tuple[float, list[str], list[str]]` | R-04 → `(sum, missing_codes, item_names)`: список критичних — `f3d.energy.node.is_critical` (energy CE-04), запасний — параметр `critical_codes` (X-11); у `infra.totals` не пише |
| `_notify_state_change(self, new_state)` | якщо `"f3d.viewer.event" in self.env` (viewer встановлено; X-20) — `self.env["f3d.viewer.event"]._notify("maintenance.equipment", [self.f3d_code], "state")` (C-03), інакше подію шини пропустити без помилки; `message_post` з текстом «Стан: <label>, режим: <label>, тривога: <рівень>, острів: так/ні» лише коли змінились `state`/`alarm_level`/`island` (не `online` окремо, щоб не засмічувати чаттер) |
| `_cron_events(self)` (`@api.model`) | якщо не `_param("requests_enabled","True")` → `return`; для кожної активної зв'язки у savepoint: `_process_events_one()`; винятки — лог, без підняття |
| `_process_events_one(self)` | `events = adapters.td_genset.events_since(self.td_genset_ref, self.last_event_ts, 200)`; для кожної: `row = env["f3d.genset.event.map"]._match(ev)`; `self._apply_event(ev, row)` (R-07, R-08); після циклу `write({"last_event_ts": max ts, "last_event_id": max id})`; якщо `len(events)==200` → крон продовжить наступного разу |
| `_apply_event(self, ev, row)` | за `row.action`: `ignore` → нічого; `bus_only` → `_notify_state_change`-подібна подія `kind="state"`; `request_*` → R-08: `key = "GENSET:%s" % row.key`; `open = env["maintenance.request"].search([("equipment_id","=",eq.id),("f3d_genset_event_key","=",key),("stage_id.done","=",False)], limit=1)`; якщо є → `open.message_post(body="Повтор: %s о %s" % (name, local_ts))`; інакше `create(R-07 vals)` |
| `_cron_service(self)` (`@api.model`) | R-09 для кожної зв'язки |
| `action_check(self)` | `ensure_one()`; якщо `not self.env.user.has_group("factory3d_base.group_f3d_manager")` → `AccessError("Перевірку зв'язки може виконати лише менеджер «Завод 3D».")` (метод публічний — кнопка `groups` не захищає RPC, AC-60); `_publish_one()` незалежно від стоп-крана? — **ні**: якщо `_read_enabled()` False → `UserError("Публікацію вимкнено стоп-краном factory3d.genset.read_enabled")`; інакше виконати й повернути `display_notification` «Знімок: стан <label>, <p_kw> кВт, паливо <fuel_pct> % (<fuel_l> л), мотогодини <hours>; записано <accepted> показань» |
| `action_open_td(self)` | `adapters.td_genset.open_action(self.td_genset_ref)` |
| `action_open_signals(self)` | `act_window` `f3d.signal`, `domain=[("code","=like","infra/genset/%s/%%" % f3d_code)]`, list,form |
| `action_open_requests(self)` | `act_window` `maintenance.request`, `domain=[("equipment_id","=",eq.id),("f3d_genset_event_key","!=",False)]` |
| `action_show_3d(self)` | `self.equipment_id.action_f3d_show()` (CB-02) |

### M-02 `f3d.genset.profile` — профіль генератора (FR-02)

```python
class F3dGensetProfile(models.Model):
    _name = "f3d.genset.profile"
    _description = "Генератор: профіль (паливо, потужність, таймери)"
    _order = "code"
    _rec_name = "name"
```

| Поле | Тип | Параметри |
|---|---|---|
| `code` | Char(32) | `required`, `index`, `string="Код"` (`D700`) |
| `name` | Char | `required`, `string="Назва"` («KOHLER-SDMO D700, SmartGen HGM6120N») |
| `passport_id` | Many2one `f3d.equipment.passport` | `string="Паспорт"`, `domain="[('role','=','genset')]"`, `ondelete="set null"` |
| `kva_prp` | Float | `digits=(8,1)`, `string="PRP, кВА"`, `required`, default 634 |
| `kw_prp` | Float | `digits=(8,1)`, `string="PRP, кВт"`, `required`, default 507 |
| `kva_esp` | Float | `string="ESP, кВА"`, default 697 |
| `kw_esp` | Float | `string="ESP, кВт"`, default 558 |
| `tank_l` | Float | `digits=(8,1)`, `string="Бак, л"`, `required`, default 610 |
| `fuel_lph_25` | Float | `digits=(8,1)`, `string="Витрата при 25 %, л/год"`, default 38.6 |
| `fuel_lph_50` | Float | `string="Витрата при 50 %, л/год"`, default 71.2 |
| `fuel_lph_75` | Float | `string="Витрата при 75 %, л/год"`, default 103.8 |
| `fuel_lph_100` | Float | `string="Витрата при 100 % PRP, л/год"`, default 136.4 |
| `fuel_lph_esp` | Float | `string="Витрата при 100 % ESP, л/год"`, default 149.5 |
| `oil_l` | Float | `string="Олива, л"`, default 34 |
| `oil_pressure_min_bar` | Float | `string="Мін. тиск оливи, бар"`, default 0.5 |
| `start_to_load_s` | Integer | `string="Пуск до навантаження, с"`, default 15 (ціль заводу; умовчання HGM ≈ 30 с — §9 Додаток D) |
| `autonomy_warn_h` | Float | `string="Попередження про автономність, год"`, default 2.0 — лише для `warn` картки (R-10) |
| `timer_preset` | Selection | `[("default","Умовчання HGM6120N (Table 7)"),("plant","Заводський пресет (Q-06)")]`, default `default` |
| `timers_json` | Json | `string="Таймери"` — dict ключів §8.2 (`mains_abnormal_s`, `start_delay_s`, `crank_s`, `crank_rest_s`, `start_times`, `safety_on_s`, `warming_s`, `transfer_s`, `mains_normal_s`, `stop_delay_s`, `cooling_s`, `ets_hold_s`), compute `_compute_timers` з `timer_preset` (store=False): `default` = {5,1,8,10,3,10,10,1.0,10,1,10,20}; `plant` = {2,0,8,10,3,5,3,1.0,10,1,10,20}; плюс в обох пресетах `crank_fire_s=3`, `over_current_delay_s=30` (§8.2, Додаток D) |
| `timers_text` | Char | `compute="_compute_timers_text"` (не зберігається), `string="Таймери (JSON)"` — `json.dumps(timers_json, ensure_ascii=False)` (V-03) |
| `note` | Text | джерела (URL датасітів) |
| `active` | Boolean | default True |

```python
    _code_uniq = models.Constraint("UNIQUE(code)", "Код профілю має бути унікальним.")
```

`@api.constrains`: `tank_l > 0`, `kw_prp > 0`, `kva_prp >= kw_prp`; `fuel_lph_25 ≤ fuel_lph_50 ≤ fuel_lph_75 ≤ fuel_lph_100 ≤ fuel_lph_esp`
(«Крива витрати має бути неспадною.»); усі витрати > 0.

| Сигнатура | Алгоритм |
|---|---|
| `fuel_lph(self, load_pct: float) -> float` | R-01 |
| `autonomy_h(self, fuel_l: float, load_pct: float) -> float \| None` | R-02 |
| `to_relay_profile(self) -> dict` | §8.2 JSON (ключі й вкладеність — **точно** як у §8.2, бо файл читає `fake_relay`): `{"profile": code, "rated": {"kva_prp", "kw_prp", "kva_esp", "kw_esp"}, "tank_l", "fuel_lph": {"25": …, "50": …, "75": …, "100": …, "esp": …}, "timers": timers_json, "timers_plant": {4 ключі пресету plant}, "sensors": {...}, "alarms": {...}, "start": {...}}`; значення `sensors`/`alarms`/`start` — константа модуля `RELAY_DEFAULTS` = словники §8.2 з коментарем «макет: картка GENSET; пороги — ПРИПУЩЕННЯ Q-06/Q-13» |
| `action_export_relay_profile(self)` | `ir.actions.act_url` на `/web/content?...` — ні: простіше повернути `ir.actions.act_window` з `TransientModel`? Ні. Рішення: кнопка створює `ir.attachment` `d700.json` (`res_model=self._name, res_id=self.id`, `mimetype="application/json"`) і повертає `{"type":"ir.actions.act_url","url":"/web/content/%d?download=true" % att.id,"target":"self"}` |
| `action_apply_to_td(self)` | не менеджер (`has_group("factory3d_base.group_f3d_manager")`) → `AccessError("Записувати в td_genset може лише менеджер «Завод 3D».")` (AC-60); для кожної `f3d.genset.link` з цим профілем: `adapters.td_genset.set_fuel_rate(link.td_genset_ref, self.fuel_lph_75)` (ADP-09); повідомлення «Записано в td_genset: N генераторів; пропущено (крива/поля немає): M» |

### M-03 `f3d.genset.event.map` — мапа подій контролера → дії (FR-04, FR-05)

```python
class F3dGensetEventMap(models.Model):
    _name = "f3d.genset.event.map"
    _description = "Генератор: мапа подій → заявки ТО"
    _order = "sequence, key"
```

| Поле | Тип | Параметри |
|---|---|---|
| `key` | Char(64) | `required`, `index`, `string="Ключ"` (латиниця, напр. `LOW_OIL_PRESSURE_SD`) |
| `sequence` | Integer | default 10 |
| `hgm_name` | Char | `string="Назва за мануалом HGM6120N"` (напр. `Low Oil Pressure`) |
| `hgm_table` | Selection | `[("warning","Table 4 — попередження"),("shutdown","Table 5 — аварійна зупинка"),("other","Інше")]`, default `other` |
| `severity` | Selection | `[("warning","Попередження"),("shutdown","Аварійна зупинка"),("comm","Зв'язок"),("service","ТО"),("info","Інформація")]`, `required` |
| `td_code` | Char(64) | `index`, `string="Код у td_genset"` — ЗВІРИТИ (Q-13); порожній → збіг за `hgm_name` |
| `action` | Selection | `[("request_corrective","Заявка ТО (ремонт)"),("request_preventive","Заявка ТО (планова)"),("bus_only","Лише подія в 3D"),("ignore","Ігнорувати")]`, `required`, default `bus_only` |
| `priority` | Selection | `[("0","Дуже низький"),("1","Низький"),("2","Звичайний"),("3","Високий")]`, default `2` |
| `name_tpl` | Char | `required`, `string="Шаблон назви заявки"` — `str.format` з ключами `{code}` (код сцени), `{name}`, `{value}`, `{unit}`, `{threshold}`, `{ts}`; приклад `Генератор {code}: низький тиск оливи — {value} {unit} при нормі ≥ {threshold} {unit}` |
| `description_tpl` | Text | шаблон опису (ті самі ключі + `{text}`, `{td_link}`) |
| `match_regex` | Char | необов'язково: regex по `ev["name"]` (регістронезалежно), якщо `td_code` і `hgm_name` не збіглись |
| `active` | Boolean | default True |

```python
    _key_uniq = models.Constraint("UNIQUE(key)", "Ключ мапи має бути унікальним.")
```

| Сигнатура | Алгоритм |
|---|---|
| `_match(self, ev) -> record` (`@api.model`) | R-07 крок 1 (лише `active` рядки): (а) `td_code` точно = `ev["code"]`; (б) `hgm_name` iequals `ev["name"]` **і** `severity == ev["severity"]` (вісім назв є і в Table 4, і в Table 5 — Додаток B; A-16); (в) `match_regex` `re.search(..., ev["name"], re.I)`; (г) `key == "DEFAULT_" + ev["severity"].upper()` (`DEFAULT_WARNING`, `DEFAULT_SHUTDOWN`, `DEFAULT_COMM`, `DEFAULT_SERVICE`, `DEFAULT_INFO`); порядок пошуку — `sequence, key`; перший збіг; немає збігу (напр. `severity="command"`) → порожній recordset, `_apply_event` нічого не робить (рівнозначно `ignore`) |
| `_check_templates(self)` (`@api.constrains("name_tpl","description_tpl")`) | `string.Formatter().parse(tpl)`: кожне ім'я поля ∈ {`code`, `name`, `value`, `unit`, `threshold`, `ts`, `text`, `td_link`} і без `.`/`[` (доступ до атрибутів/індексів заборонено), інакше `ValidationError("Шаблон: дозволені лише поля {code} {name} {value} {unit} {threshold} {ts} {text} {td_link}.")` (AC-61). Невідомий ключ у даних події під час рендерингу — «—» (SafeDict, §11 п. 9) |
| `_render(self, ev, link) -> tuple[str, str]` | `fmt = {code, name, value (форматовано `%.1f` або "—"), unit or "", threshold (так само), ts (local Europe/Kyiv "DD.MM HH:MM"), text, td_link (URL запису `td_genset` `/odoo/action-…`? — простіше `"%s,%d" % (model, id)`)}`; `name = self.name_tpl.format_map(SafeDict(fmt))[:120]`; `description = html_escape(self.description_tpl or "").format_map(...)` з `<br/>` замість `\n` |

### M-04 `f3d.source` — розширення (CG-04)

```python
class F3dSource(models.Model):
    _inherit = "f3d.source"
    type = fields.Selection(selection_add=[("td_genset", "td_genset (ретранслятор SmartGen)")],
                            ondelete={"td_genset": "cascade"})

    @api.model
    def _f3d_local_types(self):
        # CT-12, R-26 factory3d_telemetry: джерело типу td_genset — локальне, без колектора (X-01, D-17)
        return super()._f3d_local_types() + ["td_genset"]
```

`ondelete` — `cascade`: поле `type` у telemetry M-02 обов'язкове й без умовчання, тож `set default`/`set null` Odoo відхиляє
при завантаженні реєстру; при деінсталяції моста джерело `GENSET-RELAY` видаляється, сигнали лишаються з `source_id=False`
(telemetry M-03 `ondelete="set null"`), показання й заявки — без змін.

Локальність джерела — **лише** через хук telemetry (X-01, §2.0.3 T-1): M-04 не перевизначає `collector_id` і не додає
власного constraint на колектор — обов'язковість колектора для нелокальних типів (`_check_f3d_collector_required`),
`validate_params(type, params, local_types)` (для `td_genset` — лише об'єкт JSON без секретів), невидимість у API-01 і в кронах
R-07/R-25, заборона команд (R-18) — правила telemetry R-26, які спрацьовують, бо `"td_genset" in _f3d_local_types()`. Без цього
розширення telemetry Додаток A.0 відхиляє тип («type: невідомий тип джерела «td_genset»») і `GENSET-RELAY` не створюється (AC-01,
AC-50, AC-69). Поля адреси на `f3d.source` немає; адреси сигналів — `{"leaf": <leaf>}` (Додаток A, довідково).

### M-05 `maintenance.equipment` — розширення

| Поле / метод | Визначення |
|---|---|
| `f3d_genset_link_ids` | One2many `f3d.genset.link` `equipment_id`, `string="Зв'язка генератора"` |
| `f3d_genset_link_id` | Many2one `f3d.genset.link`, `compute="_compute_f3d_genset_link"` = `f3d_genset_link_ids[:1]` |
| `f3d_is_genset` | Boolean, `compute="_compute_f3d_genset_link"` = `f3d_passport_id.role == "genset"` |
| `action_open_f3d_genset(self)` | якщо `f3d_genset_link_id` → `act_window` форма зв'язки; інакше — `act_window` створення з `context={"default_equipment_id": self.id}` |

`f3d_meter_signal_id` (поле telemetry M-07) **не** перевизначається і мостом **не заповнюється** (§2.0.3 T-7: telemetry
вимагає інтервал > 0, а інтервал запустив би telemetry R-11 — друге джерело правди ТО); ТО за мотогодинами — лише R-09 (A-04).

### M-06 `maintenance.request` — розширення (R-08)

| Поле / метод | Визначення |
|---|---|
| `f3d_genset_event_key` | Char(80), `index=True`, `string="Ключ події генератора"`, `readonly=True`, `copy=False` |
| `write(self, vals)` | `res = super().write(vals)`; якщо `"stage_id" in vals`: для `self.filtered(lambda r: r.f3d_genset_event_key and r.stage_id.done)` → `r._f3d_genset_on_closed()`; `return res` |
| `_f3d_genset_on_closed(self)` | R-08 крок 4: `link = env["f3d.genset.link"].search([("equipment_id","=",self.equipment_id.id)], limit=1)`; `link.message_post(body="Заявку %s закрито" % self.name)`. Статус сигналу **не** пише — його перераховує telemetry M-08 → R-06 `_on_request_closed` (§2.0.3 T-9) |

Поля `f3d_signal_id`, `f3d_equipment_code` — з telemetry (§6.8); міст їх заповнює, не оголошує.

### M-07 `res.config.settings` — розширення

| Поле | Тип | `config_parameter` |
|---|---|---|
| `f3d_genset_read_enabled` | Boolean | `factory3d.genset.read_enabled` |
| `f3d_genset_requests_enabled` | Boolean | `factory3d.genset.requests_enabled` |
| `f3d_genset_write_enabled` | Boolean (readonly у формі, `help="Зарезервовано: міст команд на генератор не надсилає"`) | `factory3d.genset.write_enabled` |
| `f3d_genset_amf_master` | Selection `[("hgm","HGM6120N веде AMF"),("ats","ATyS p головний")]` | `factory3d.genset.amf_master` |
| `f3d_genset_offline_min` | Integer | `factory3d.genset.offline_min` |
| `f3d_genset_ats_position_code` | Char | `factory3d.genset.ats_position_code` |
| `f3d_genset_ats_src1_code` | Char | `factory3d.genset.ats_src1_code` |
| `f3d_genset_ats_src2_code` | Char | `factory3d.genset.ats_src2_code` |
| `f3d_genset_ats_position_i_value` | Integer (`string="Положення I (мережа): значення сигналу"`, `default=2`, `help="Значення сигналу положення АВР для положення I «мережа» (Socomec ATyS p, Annexe III: 2)"`) | `factory3d.genset.ats_position_i_value` (X-69, R-05) |
| `f3d_genset_ats_position_ii_value` | Integer (`string="Положення II (генератор): значення сигналу"`, `default=3`, `help="Значення сигналу положення АВР для положення II «генератор» (Socomec ATyS p, Annexe III: 3)"`) | `factory3d.genset.ats_position_ii_value` (X-69, R-05) |
| `f3d_genset_critical_codes` | Char | `factory3d.genset.critical_codes` |
| `f3d_genset_publish_period_s` | Integer | `factory3d.genset.publish_period_s` |

`set_values()`: перед `super()` — якщо `f3d_genset_ats_position_i_value == f3d_genset_ats_position_ii_value` → `ValidationError("Значення положень I і II АВР мають відрізнятися.")` (R-05 інакше не розрізнить острів; X-69); після `super()` — якщо змінився `publish_period_s` → `env.ref("factory3d_genset.cron_f3d_genset_publish").write({"interval_number": max(1, period//60) if period >= 60 else 1, "interval_type": "minutes"})`; якщо змінився `offline_min` → перерахувати `period_s = max(60, offline_min·20)` у 26 сигналах GENSET кожної активної зв'язки (`f3d.signal` з `code =like "infra/genset/<f3d_code>/%"`, `sudo()`, один `write`) — §2.0.3 T-6, AC-62 (X-69); значення положень I/II R-05 читає з параметрів у момент виклику (перерахунку не потребують).

### M-08 `f3d.viewer.provider.genset` — провайдер переглядача (FR-07, FR-09, CG-02)

```python
class F3dViewerProviderGenset(models.AbstractModel):
    _name = "f3d.viewer.provider.genset"     # за префіксом f3d.viewer.provider.*, без успадкування моделей viewer (X-20, D-18; як energy A-04)
    _description = "3D: постачальник даних генератора"
    _f3d_sequence = 155          # A-07: після infra (150) energy
    _f3d_sections = ("infra",)
    _f3d_group = "factory3d_base.group_f3d_user"
```

Контракт — duck-typing viewer M-01 (каркас §6.7): модель визначає **усі** атрибути й методи сама (`_f3d_sequence`,
`_f3d_sections`, `_f3d_group`, `_f3d_viewer_collect`, `_f3d_viewer_delta`, `_f3d_viewer_bus_models`) і не успадковує
`f3d.viewer.provider` — тож модуль не залежить від `factory3d_viewer` (X-20); без viewer модель просто ніхто не викликає.

| Метод | Алгоритм |
|---|---|
| `_f3d_viewer_collect(self, payload, ctx)` | для кожної `f3d.genset.link` (`active`, `search_read` полів `equipment_id`, `f3d_code`, `profile_id`, `last_state_json`, `last_publish_ts`): 1) `vals = adapters.telemetry.read_values(env, [26 кодів])`; 2) `node = payload.setdefault("infra", {}).setdefault("genset", {}).setdefault(code, {})`; `node[leaf] = R-11(value)` для наявних; `node["updated"] = local(max last_ts)`; `node["state_label"]`, `node["mode_label"]`, `node["breaker_label"]`, `node["alarm_label"]` (R-03 тексти); 3) `isl = link._island_state_from_signals(vals)` (R-05 з уже прочитаних значень + TEL-04 для кодів ATS); 4) `payload["infra"].setdefault("totals", {}).update({"genset_kw": node.get("p_kw", 0.0), "genset_state": node["state_label"], "genset_fuel_pct": node.get("fuel_pct"), "genset_autonomy_h": node.get("autonomy_h"), "island": isl["island"], "grid_ok": isl["grid_ok"], "genset_kva": int(round(profile.kva_prp))})` — лише ключі CG-02 моста; `infra.totals.critical_kw` міст **не** пише й не перезаписує (власність energy CE-03/CE-04, X-11); рядок картки «Критичні споживачі зараз» і `items` — з R-04 (`link._critical_kw()`); 5) `payload["infra"].setdefault("cards", {})[code] = R-10`; 6) якщо є `infra.cards["ATS-1"]` і `isl["island"]` — **не** чіпати (картка ATS — energy; CV-01 — viewer) |
| `_f3d_viewer_delta(self, patch, ctx)` | R-13 (X-23): власна дельта; лише якщо `ctx["changes"]` зачіпає генератор (умова R-13 п. 1) → `tmp = {}`; `self._f3d_viewer_collect(tmp, ctx)`; `deep_merge(patch.setdefault("infra", {}), tmp.get("infra", {}))` — доповнює `patch["infra"]`, ніколи не присвоює `patch["infra"] = …` (ключі energy/yard/access у `patch["infra"]` лишаються) |
| `_f3d_viewer_bus_models(self)` | `["maintenance.equipment", "f3d.signal"]` |

Якщо зв'язок немає — провайдер нічого не пише (`infra.cards.GENSET` лишається статичним з моделі; `meta.sections.infra`
не змінюється). Виняток у провайдері ізолює viewer R-01 (savepoint) — провайдер не має власного `try` навколо всього,
лише навколо читання ATS (відсутні коди — не помилка).

### M-09 Технічні обмеження на `td_genset` — немає

Жодна модель `td_genset` не успадковується і не розширюється (A-09). Якщо під час звірки виявиться, що для ADP-03/ADP-04
бракує агрегованого методу, його додають **у `td_genset`** як `_f3d_snapshot()`/`_f3d_events_since()` (CR-04, мінімальні
геттери без логіки), а адаптер їх викликає; це єдиний дозволений дотик до `td_genset` з боку моста.

## 3. Представлення й меню

| ID | XML-id | Тип | Модель | Структура |
|---|---|---|---|---|
| V-01 | `factory3d_genset.view_f3d_genset_link_form` | form | `f3d.genset.link` | `header`: кнопки «Перевірити» (`action_check`, `btn-primary`, `groups="factory3d_base.group_f3d_manager"`), «Показати в 3D» (`action_show_3d`); `sheet`: `button_box` — stat-кнопки «Сигнали» (`action_open_signals`, `signal_count`, `fa-signal`), «Заявки ТО» (`action_open_requests`, `request_open_count`, `fa-wrench`), «td_genset» (`action_open_td`, `fa-external-link`); `widget="badge"` поля `state_label` з `decoration-success="state_code == 7"`, `decoration-warning="state_code in (3,4,5,6,8,9)"`, `decoration-danger="state_code in (0,10)"`; група «Зв'язка»: `equipment_id`, `f3d_code` (readonly), `td_genset_ref`, `profile_id`, `publish_enabled`, `amf_master` (readonly); група «Стан»: `online` (`widget="boolean_toggle"`, readonly), `island`, `last_publish_ts`, `last_publish_error` (`invisible="not last_publish_error"`, `decoration-danger`), `last_event_ts`, `source_id`; `notebook`: «Знімок» (`last_state_json` widget `json`? — у 19 немає стандартного; показати як `Text` через compute `last_state_text` — додати поле `last_state_text` Char compute = `json.dumps(ensure_ascii=False, indent=1)` readonly), «Примітки» (`mail.thread` чаттер — `chatter` тег). Поля `equipment_id`, `td_genset_ref`, `profile_id` — `readonly="not is_f3d_manager"`? — ні: права на запис дає ACL (§4), форма без додаткових умов |
| V-02 | `factory3d_genset.view_f3d_genset_link_list` | list | `f3d.genset.link` | `name`, `f3d_code`, `td_genset_ref`, `profile_id`, `state_label` (badge), `online`, `island`, `last_publish_ts`, `publish_enabled` (`boolean_toggle`); `decoration-danger="not online"`; без `editable` |
| V-03 | `factory3d_genset.view_f3d_genset_profile_form` | form | `f3d.genset.profile` | `header`: «Експорт профілю для fake_relay» (`action_export_relay_profile`), «Застосувати витрату до td_genset» (`action_apply_to_td`, `groups=group_f3d_manager`, confirm «Записати 75 %-витрату в td_genset для всіх зв'язок з цим профілем?»); група «Паспорт»: `code`, `name`, `passport_id`; група «Потужність»: `kva_prp`, `kw_prp`, `kva_esp`, `kw_esp`; група «Паливо»: `tank_l`, `fuel_lph_25`, `fuel_lph_50`, `fuel_lph_75`, `fuel_lph_100`, `fuel_lph_esp`, `autonomy_warn_h`; група «Двигун»: `oil_l`, `oil_pressure_min_bar`, `start_to_load_s`; група «Таймери HGM6120N»: `timer_preset`, `timers_text` (Char compute, readonly — JSON у рядок); `note` |
| V-04 | `factory3d_genset.view_f3d_genset_profile_list` | list | `f3d.genset.profile` | `code`, `name`, `kw_prp`, `tank_l`, `fuel_lph_75`, `timer_preset` |
| V-05 | `factory3d_genset.view_f3d_genset_event_map_list` / `_form` | list (`editable="bottom"`), form | `f3d.genset.event.map` | list: `sequence` (handle), `key`, `hgm_name`, `hgm_table`, `severity`, `td_code`, `action`, `priority`, `active` (`boolean_toggle`); form: ті самі + `name_tpl`, `description_tpl`, `match_regex`; search: фільтри «Заявка ТО» (`action like 'request_%'`), «Аварійні» (`severity='shutdown'`), групування за `severity`, `action` |
| V-06 | `factory3d_genset.view_maintenance_equipment_form_f3d_genset` | form inherit `maintenance.view_equipment_form` | `maintenance.equipment` | у `div[@name='button_box']` — stat-кнопка «Генератор» (`action_open_f3d_genset`, `fa-bolt`, `invisible="not f3d_is_genset"`); поля `f3d_is_genset`, `f3d_genset_link_id` — `invisible="1"` |
| V-07 | `factory3d_genset.res_config_settings_view_form` | form inherit `base.res_config_settings_view_form` | `res.config.settings` | блок `app_settings_block` `data-string="Завод 3D: генератор"` `data-key="factory3d_genset"` (у 19 — `<app data-string=… string=… name="factory3d_genset">` / `<block>` / `<setting>`): setting «Публікувати показання в телеметрію» (`f3d_genset_read_enabled`), «Створювати заявки ТО» (`f3d_genset_requests_enabled`), «Команди на генератор (зарезервовано)» (`f3d_genset_write_enabled`, readonly), «Логіка AMF» (`f3d_genset_amf_master`), «Офлайн через, хв» (`f3d_genset_offline_min`), «Період публікації, с» (`f3d_genset_publish_period_s`), «Сигнали АВР» (три коди і значення положень I/II — `f3d_genset_ats_position_i_value`, `f3d_genset_ats_position_ii_value`, X-69), «Критичні споживачі — запасний список (коди сигналів через кому)» (`f3d_genset_critical_codes`, widget `char` з `placeholder`; `help` «Використовується, лише якщо в energy немає жодного вузла з ознакою «Критичний» (`f3d.energy.node.is_critical`)»; X-11) |
| V-08 | `views/menus.xml` | menu | — | таблиця нижче |
| V-09 | `factory3d_genset.view_maintenance_request_form_f3d_genset` | form inherit `maintenance.hr_equipment_request_view_form` | `maintenance.request` | після поля `equipment_id`: `f3d_genset_event_key` (readonly, `invisible="not f3d_genset_event_key"`, `groups="factory3d_base.group_f3d_user"`) |

Меню (CB-09, A-06; пункт налаштувань за правилом X-32 — X-69):

| XML-id | Назва | Батько | sequence | Групи | Дія |
|---|---|---|---|---|---|
| `menu_f3d_genset` | Генератор | `factory3d_base.menu_f3d_root` | 55 | `group_f3d_user` | — |
| `menu_f3d_genset_link` | Зв'язка | `menu_f3d_genset` | 10 | `group_f3d_user` | `action_f3d_genset_link` (`f3d.genset.link`, list,form) |
| `menu_f3d_genset_profile` | Профілі | `menu_f3d_genset` | 20 | `group_f3d_manager` | `action_f3d_genset_profile` (list,form) |
| `menu_f3d_genset_event_map` | Події → ТО | `menu_f3d_genset` | 30 | `group_f3d_manager` | `action_f3d_genset_event_map` (list,form; `context={"search_default_group_severity": 1}`) |
| `menu_f3d_genset_requests` | Заявки ТО генератора | `menu_f3d_genset` | 40 | `group_f3d_user` | `action_f3d_genset_requests` (`maintenance.request`, kanban,list,form; `domain=[("f3d_genset_event_key","!=",False)]`) |
| `menu_f3d_genset_settings` | Налаштування генератора | `factory3d_base.menu_f3d_config` | 55 (резерв genset CB-09; X-32, X-69) | `group_f3d_admin` | `action_f3d_genset_settings` (`res.config.settings`, `form`, `target='inline'`, `context={'module': 'factory3d_genset'}`; визначена в `views/res_config_settings_views.xml`) |

Дії (`ir.actions.act_window`): `view_mode` лише `list`/`form`/`kanban` (MG-04). Пульт і меню `td_genset` — без змін.

## 4. Права

### 4.1 `security/ir.model.access.csv` (повністю)

```
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_f3d_genset_link_user,f3d.genset.link user,model_f3d_genset_link,factory3d_base.group_f3d_user,1,0,0,0
access_f3d_genset_link_manager,f3d.genset.link manager,model_f3d_genset_link,factory3d_base.group_f3d_manager,1,1,1,1
access_f3d_genset_profile_user,f3d.genset.profile user,model_f3d_genset_profile,factory3d_base.group_f3d_user,1,0,0,0
access_f3d_genset_profile_manager,f3d.genset.profile manager,model_f3d_genset_profile,factory3d_base.group_f3d_manager,1,1,1,1
access_f3d_genset_event_map_user,f3d.genset.event.map user,model_f3d_genset_event_map,factory3d_base.group_f3d_user,1,0,0,0
access_f3d_genset_event_map_manager,f3d.genset.event.map manager,model_f3d_genset_event_map,factory3d_base.group_f3d_manager,1,1,1,1
```

Абстрактна `f3d.viewer.provider.genset` доступів не потребує. `f3d.source`/`f3d.signal`/`f3d.reading` — права telemetry;
крони працюють від `base.user_root` (`OdooBot`) — ACL не обмежує; у коді `sudo()` лише для `ir.config_parameter` і для
`create` `maintenance.request` з крона (коментар `# R-07: заявка від імені OdooBot`). `action_check` виконується від
користувача (менеджер): запис у `f3d.reading` потребує прав telemetry на create — менеджер `group_f3d_manager` їх має
(каркас §5 «налаштування джерел… — manager»); якщо telemetry дасть лише колектору — `action_check` викликає `_publish_one`
через `self.sudo()` з перевіркою `has_group("factory3d_base.group_f3d_manager")` перед тим (запис у код як виняток із
коментарем).

### 4.2 Record rules

Немає: один завод, одна компанія; `company_id` на зв'язці — довідкове. `maintenance.request` — стандартні правила `maintenance`.

### 4.3 Відповідність груп `td_genset` ↔ `factory3d_base` (CR-07, Q-12)

Міст не змінює груп `td_genset` і не створює своїх. Рекомендована (не автоматична) відповідність для адміністратора,
яку W1 записує в `docs/ADAPTER_MAP.md` після звірки XML-id:

| Роль `td_genset` (ЗВІРИТИ XML-id) | Дати додатково | Навіщо |
|---|---|---|
| оператор генератора (пульт, показання) | `factory3d_base.group_f3d_user` | картка GENSET у переглядачі, меню «Генератор → Зв'язка/Заявки» (читання) |
| менеджер генератора (налаштування, розклад, ТО) | `factory3d_base.group_f3d_manager` | зв'язка, профіль, мапа подій, «Перевірити» |
| адміністратор `td_genset` (стоп-крани, ретранслятор) | `factory3d_base.group_f3d_admin` | стоп-крани моста, параметри, емулятор |
| служба механіка (отримує заявки) | `maintenance.group_equipment_manager` (стандарт) | заявки ТО |

Правило перевірки після оновлення проду (MG-08): `SELECT g.id, count(*) FROM res_groups_users_rel r JOIN res_groups g
ON g.id=r.gid WHERE g.id IN (<ids груп td_genset>) GROUP BY g.id` до і після — однакові числа.

### 4.4 Стоп-крани й токени (ARCH §2.6)

| Що | Де | Хто змінює | Умовчання | Перевірка |
|---|---|---|---|---|
| `factory3d.genset.read_enabled` | `ir.config_parameter`, V-07 | `group_f3d_admin` (`base.group_system` — «Параметри системи») | `True` на тесті, `False` на проді (CB-10, §5.3 крок 1) | AC-08, AC-09 |
| `factory3d.genset.requests_enabled` | те саме | те саме | `True`; `neutralize.sql` → `False` | AC-16, AC-35 |
| `factory3d.genset.write_enabled` | те саме; поле V-07 `readonly` | — (зарезервовано) | `False`; значення **ніде не читається** кодом моста — міст не має коду команд | AC-34, AC-58 |
| Стоп-кран команд `td_genset` (ім'я — ЗВІРИТИ, Q-16) | `td_genset` | як у ТР 1.2 | як у ТР 1.2; на проді — вимкнено до етапу 2 §13.6 | AC-A15, ТБ-04 |
| `RELAY_SIM_TOKEN` | env контейнера `genset_relay` (`.env` стенда, не в репозиторії) | адміністратор стенда | порожньо = `/sim/v1/*` вимкнено (404) | AC-A06, ТБ-05 |
| Токен ретранслятора `td_genset` | параметри `td_genset` (як ТР 1.2) | адмін `td_genset` | після `neutralize.sql` — новий/порожній (FR-A07) | AC-A07 |

Міст власних токенів і HTTP-ендпоінтів не має (§7).

## 5. Дані

### 5.1 `data/ir_config_parameter.xml` (`noupdate="1"`)

| key | value | XML-id |
|---|---|---|
| `factory3d.genset.read_enabled` | `True` (хук перезаписує за CB-10: `environment=='prod'` → `False`) | `param_read_enabled` |
| `factory3d.genset.requests_enabled` | `True` | `param_requests_enabled` |
| `factory3d.genset.write_enabled` | `False` | `param_write_enabled` |
| `factory3d.genset.amf_master` | `hgm` | `param_amf_master` |
| `factory3d.genset.offline_min` | `5` | `param_offline_min` |
| `factory3d.genset.ats_position_code` | `infra/ats/position` | `param_ats_position_code` |
| `factory3d.genset.ats_src1_code` | `infra/ats/src1_ok` | `param_ats_src1_code` |
| `factory3d.genset.ats_src2_code` | `infra/ats/src2_ok` | `param_ats_src2_code` |
| `factory3d.genset.ats_position_i_value` | `2` | `param_ats_position_i_value` — R-05: значення `infra/ats/position` для положення I «мережа» (Annexe III ATyS p, energy CE-02; iot_sim §8.9.4 веде ту саму кодировку за X-41) — однаково на стенді й на проді |
| `factory3d.genset.ats_position_ii_value` | `3` | `param_ats_position_ii_value` — положення II «генератор» (Annexe III; X-41) — однаково на стенді й на проді |
| `factory3d.genset.critical_codes` | `energy/consumers/LP-1/p_now,energy/consumers/LP-2/p_now,energy/consumers/LP-3/p_now,energy/consumers/DUST-1/p_now,energy/consumers/COMPRESSOR/p_now,energy/consumers/BOILER/p_now,energy/consumers/OFFICE/p_now,energy/consumers/EF-ELEC/p_now,energy/consumers/EF-CHG/p_now,energy/lines/BW-1/p_now` | `param_critical_codes` — **запасний** список (X-11): R-04 бере критичні вузли `f3d.energy.node.is_critical` (energy CE-04); параметр діє, лише якщо моделі `f3d.energy.node` немає в реєстрі або жоден вузол не позначено критичним |
| `factory3d.genset.publish_period_s` | `60` | `param_publish_period_s` |
| `factory3d.genset.service_warn_h` | `50` | `param_service_warn_h` |
| `factory3d.genset.migration_report` | `{}` | `param_migration_report` |

Читання булевих: `get_param(key, 'False') in ('True', 'true', '1')` (як у base).

### 5.2 Data-файли

| Файл | Що створює | Джерело | XML-id | Ідемпотентність |
|---|---|---|---|---|
| `data/f3d_genset_profile.xml` | профіль `D700`: `code="D700"`, `name="KOHLER-SDMO D700 · SmartGen HGM6120N"`, `kva_prp=634`, `kw_prp=507`, `kva_esp=697`, `kw_esp=558`, `tank_l=610`, `fuel_lph_25=38.6`, `fuel_lph_50=71.2`, `fuel_lph_75=103.8`, `fuel_lph_100=136.4`, `fuel_lph_esp=149.5`, `oil_l=34`, `oil_pressure_min_bar=0.5`, `start_to_load_s=15`, `autonomy_warn_h=2.0`, `timer_preset="default"`, `note` з URL датасітів (ARCH §8); `passport_id` — хук прив'язує паспорт `role='genset'` (data не може посилатись на запис base, створений хуком) | `plant/equipment_specs.json[role=genset]`, датасіт SDMO D700, Doosan DP180LB | `profile_d700` | `noupdate="0"` — числа паспорта оновлюються з модулем; менеджерські зміни — у власних профілях (копія) |
| `data/f3d_genset_event_map.xml` | 48 рядків (Додаток B): 17 попереджень Table 4, 24 аварійні зупинки Table 5, `COMM_LOST` (comm → `request_corrective`, priority 2; використовує R-12), `SERVICE_DUE` (service → `request_preventive`, 1; використовує R-09), `DEFAULT_WARNING` (bus_only), `DEFAULT_SHUTDOWN` (request_corrective, 3), `DEFAULT_COMM` (bus_only — заявку дає R-12 `COMM_LOST`), `DEFAULT_SERVICE` (bus_only — заявку дає R-09), `DEFAULT_INFO` (ignore); A-16 | мануал HGM6100N §5.1, §5.2 | `evmap_<key_lower>` | `noupdate="0"`; `td_code` — порожній у data, заповнюється W1/менеджером (після `-u` **не** затирається: поле виключене з оновлення через окремий `<function>`? — простіше: `noupdate="1"` на `td_code`-записах неможливо по полю; рішення: data-файл не містить `td_code`, а хук після оновлення відновлює `td_code` з `migration_report["td_codes"]`, куди зберігає перед оновленням — див. §5.3 крок 0) |
| `data/ir_cron.xml` | 3 крони §6 | — | `cron_f3d_genset_publish`, `_events`, `_service` | `noupdate="1"` |

### 5.3 `post_init_hook(env)` — кроки, джерела, ідемпотентність, очікувані кількості

Усі кроки ідемпотентні; звіт у `factory3d.genset.migration_report` (JSON: `{"step": {"created": n, "existing": m, "skipped": reason}}`).

0. **Збереження `td_code`** (виконується і в `post_init`, і в `pre`-частині оновлення — через `migrations/19.0.1.0.0/pre-migrate.py`
   при наступних версіях; у першому випуску — крок виконується на початку хука): `report["td_codes"] = {key: td_code}` для
   рядків мапи з непорожнім `td_code`; після завантаження data — відновити `td_code` за `key`.
1. **Стоп-крани за CB-10:** `environment = get_param("factory3d.base.environment","test")`; якщо `prod` → `read_enabled=False`.
2. **Паспорт профілю:** `passport = env["f3d.equipment.passport"].search([("role","=","genset")], limit=1)`; якщо є →
   `profile_d700.passport_id = passport`; звірити `passport.get_num("tank_l")`, `get_num("kva")`, `get_num("fuel_lph_75")`: якщо
   значення є і відрізняються від профілю → **профіль не змінюємо**, у звіт `{"passport_mismatch": {...}}` (джерело істини для
   профілю — датасіт; паспорт base може містити округлення).
3. **Обладнання GENSET:** `eq = env["maintenance.equipment"].search([("f3d_code","=","GENSET")], limit=1)`; якщо нема →
   `report["link"]="skipped: немає обладнання з f3d_code=GENSET"`, кроки 4–7 пропущені.
4. **Джерело:** TEL-01 → 1 запис `f3d.source` типу `td_genset`.
5. **Сигнали:** TEL-02 → 26 `f3d.signal` (Додаток A) для `eq`; очікувано `created=26` при першій установці, `existing=26` при повторній.
6. **Зв'язка:** `gens = adapters.td_genset.generators(env)` (якщо `GENSET_MODEL` не звірений → `NotImplementedError` ловиться:
   `report["link"]="skipped: ADP-01 не звірено"`); якщо `len(gens)==1` → `create f3d.genset.link {equipment_id, td_genset_ref:
   "%s,%d", profile_id: profile_d700, source_id}`; якщо `>1` → `skipped: кілька генераторів — зв'яжіть вручну`; `0` → `skipped: у
   td_genset немає генераторів`.
7. **Лічильник ТО:** не виконується (§2.0.3 T-7) — `eq.f3d_meter_signal_id` і `f3d_meter_interval` не змінюються; у звіт `"meter": "skipped: A-04"`.
8. **Крони:** `active = read_enabled` для `publish`; `events`/`service` — `active = requests_enabled`; `cron_f3d_genset_service.nextcall` =
   найближче 06:00 Europe/Kyiv, переведене в UTC naive (`zoneinfo`).
9. Звіт → параметр; лог INFO «factory3d_genset: міграцію виконано: …».

Очікувано на копії демо-бази timur-o19demo після `factory3d_base` + `factory3d_telemetry` + `td_genset`: 1 профіль, 1 джерело,
26 сигналів, 48 рядків мапи, 3 крони, зв'язка — 1 або `skipped` (залежить від даних `td_genset` на копії), 0 заявок, 0 показань.

### 5.4 `uninstall_hook(env)`

1. Крони модуля видаляються з модулем (XML-id) — додатково нічого.
2. `ir.config_parameter` з ключами `factory3d.genset.%` — `unlink()`.
3. `f3d.source` типу `td_genset` → `active=False` (хук виконується до видалення значення селекції; після нього Odoo видаляє джерело за
   `ondelete="cascade"` M-04, сигнали лишаються з `source_id=False`).
4. `f3d.signal`, `f3d.reading`, `maintenance.request`, `f3d.genset.profile` (таблиця видаляється з модулем — профілі не
   бізнес-дані; експортований `d700.json` лишається у вкладеннях) — не чіпати.
5. `maintenance.equipment.f3d_meter_signal_id` — не чіпати (сигнал лишається).

### 5.5 `neutralize.sql`

```sql
-- factory3d_genset: нейтралізована копія проду — тестове середовище (CB-10, CR-10).
UPDATE ir_cron SET active = false WHERE id IN (
  SELECT res_id FROM ir_model_data WHERE module = 'factory3d_genset' AND model = 'ir.cron');
UPDATE ir_config_parameter SET value = 'False' WHERE key IN ('factory3d.genset.read_enabled', 'factory3d.genset.requests_enabled');
UPDATE f3d_genset_link SET last_publish_ts = NULL, last_publish_error = NULL, last_event_ts = NULL, last_event_id = 0;
```

Після `neutralize.sql` `td_genset` (ЗВІРИТИ зміст, Q-16) і base (`environment='test'`) адміністратор вручну вмикає
`read_enabled`/`requests_enabled` на стенді (ARCH §4.2). Порядок виконання на копії проду: base → td_genset → factory3d_genset.

## 6. Крони й фонові процеси (`data/ir_cron.xml`, `noupdate="1"`)

| XML-id | Назва | Інтервал | `model_id` / `code` | Що робить за прогін | Ліміти |
|---|---|---|---|---|---|
| `cron_f3d_genset_publish` | Генератор: публікація показань у телеметрію | 1 хв (`interval_number=1`, `interval_type=minutes`; змінюється з налаштувань M-07) | `f3d.genset.link` / `model._cron_publish()` | R-03, R-01, R-02, R-12 для кожної зв'язки; 1 пакет TEL-03 на зв'язку (≤ 26 показань); подія шини при зміні стану | ≤ 2 с на зв'язку; винятки — у `last_publish_error`, крон не падає (MG-11) |
| `cron_f3d_genset_events` | Генератор: події контролера → заявки ТО | 2 хв | `f3d.genset.link` / `model._cron_events()` | ADP-04 з `last_event_ts`, ≤ 200 подій, R-07/R-08 | повтор наступного прогону при 200 |
| `cron_f3d_genset_service` | Генератор: ТО за мотогодинами | 1 день, `nextcall` = наступне 06:00 Europe/Kyiv (хук ставить `nextcall` у UTC) | `f3d.genset.link` / `model._cron_service()` | R-09 | 1 заявка на `next_service_hours` |

Усі крони: `user_id = base.user_root`, `priority = 5`, `active` за §5.3 крок 8. Жоден крон не викликає команд `td_genset`.

## 7. HTTP/JSON API

Нових ендпоінтів міст **не додає**. Використовує (лише якщо встановлено `factory3d_viewer`, X-20): API-02 `/f3d/viewer/data`,
API-03 `/f3d/viewer/delta` (через провайдер M-08 і дельту R-13), шину `f3d_viewer` (M-03); `factory3d_telemetry` — внутрішній метод CT-01 (не HTTP). Стендові REST
`fake_relay` API-F-01…API-F-09 — §8.4 (належать `td_genset`, викликає `factory3d_iot_sim`). Ендпоінти `td_genset` для
ретранслятора (`relay_api.md`) — без змін (MG-12 лише `jsonrpc`).

## 8. Сервісна частина: `fake_relay.py` з профілем D700 і REST для емулятора (CR-02, CR-03, CG-03)

### 8.1 Структура (у репозиторії `td_genset`)

```
relay/
├── fake_relay.py                 існуючий емулятор ретранслятора (сервер relay_api.md) + новий роутер /sim/v1/* (§8.4)
├── genset_model.py               новий: стан-машина HGM6120N + фізика D700 (§8.3), без залежності від Odoo
├── profiles/
│   ├── office.json               існуючий набір значень офісного генератора, винесений у файл (якщо був у коді)
│   └── d700.json                 §8.2 (експорт M-02 `to_relay_profile()`)
├── Dockerfile                    python:3.12-slim, `pip install -r requirements.txt`, `CMD ["python", "fake_relay.py"]`
├── requirements.txt              як у fake_relay сьогодні (ЗВІРИТИ; очікувано stdlib/`aiohttp` або `flask`), версії закріплені
└── tests/test_sim_api.py         §13.3.2 ТК-F01…ТК-F07
```

Змінні середовища контейнера: `RELAY_PROFILE` (`office` \| `d700`, умовчання `office`), `RELAY_PORT` (8000), `RELAY_SIM_TOKEN`
(порожньо = `/sim/v1/*` вимкнено, 404), `RELAY_TIME_FACTOR` (1.0; 0.1…60), `RELAY_SEED` (детермінований шум), `RELAY_TZ`
(`Europe/Kyiv`), `RELAY_LOG_LEVEL`. Існуючий токен/автентифікація `relay_api.md` — без змін.

### 8.2 Профіль `d700.json` (формат)

```json
{"profile": "D700", "rated": {"kva_prp": 634, "kw_prp": 507, "kva_esp": 697, "kw_esp": 558},
 "tank_l": 610, "fuel_lph": {"25": 38.6, "50": 71.2, "75": 103.8, "100": 136.4, "esp": 149.5},
 "timers": {"mains_abnormal_s": 5, "start_delay_s": 1, "crank_s": 8, "crank_fire_s": 3, "crank_rest_s": 10, "start_times": 3,
            "safety_on_s": 10, "warming_s": 10, "transfer_s": 1.0, "mains_normal_s": 10, "stop_delay_s": 1,
            "cooling_s": 10, "ets_hold_s": 20, "over_current_delay_s": 30},
 "timers_plant": {"mains_abnormal_s": 2, "start_delay_s": 0, "safety_on_s": 5, "warming_s": 3},
 "sensors": {"coolant_idle_c": 22, "coolant_run_c": 85, "coolant_tau_s": 600, "oil_run_bar": 4.5, "oil_idle_bar": 0.0,
             "batt_v": 25.2, "charger_v": 27.6, "rpm_run": 1500, "u_v": 400, "f_hz": 50.0, "pf": 0.8},
 "alarms": {"low_fuel_warn_pct": 25, "low_fuel_sd_pct": 10, "coolant_high_c": 98, "oil_low_bar": 1.0, "batt_low_v": 23.0, "batt_high_v": 33.0},
 "start": {"hours": 1213.0, "starts": 184, "fuel_pct": 82, "kwh": 61250, "mode": "auto", "mains_ok": true, "load_kw": 348, "last_test": "2026-10-12T07:30:00+03:00"}}
```

`timers` — умовчання Table 7 мануалу HGM6100N; `timers_plant` — пресет Q-06 (застосовується при `POST /sim/v1/preset {"name":"plant"}`
або env `RELAY_TIMER_PRESET=plant`); `alarms` — ПРИПУЩЕННЯ (пороги контролера замовника — Q-06/Q-13); `start` — значення картки
GENSET з макета (`plant/infra.py`: паливо 82 %, «сьогодні 07:30 — щотижневий пуск 15 хв»; мотогодини й пуски — ПРИПУЩЕННЯ,
не з макета). Профіль `office.json` містить ті самі ключі зі значеннями офісного генератора (W4 переносить їх з коду).

### 8.3 Стан-машина HGM6120N у `genset_model.py` (R-03 коди, Додаток D)

Стани (`state`, код R-03): `standby`(1) → [`mains_ok=false` або `remote_start`] → `mains_abnormal`(2, таймер `mains_abnormal_s`;
при `remote_start` — пропускається) → `starting`(3): `start_delay_s` → прокрутка `crank_s`, двигун «схоплює» на `crank_fire_s`; якщо
`fault.start_fail` — `start_times` спроб по `crank_s` + `crank_rest_s`, потім `alarm_shutdown`(10, «Fail to Start») →
`safety_on`(4, `safety_on_s`) → `warming`(5, `warming_s`) → `running`(6: напруга/частота в нормі; у режимі `auto` з AMF
через `transfer_s` → `breaker=gen`) → `loaded`(7) ; повернення: `mains_ok=true` → `mains_normal_s` → `stop_delay_s` →
`breaker=mains` (через `transfer_s`) → `cooling`(8, `cooling_s`) → `stopping`(9, `ets_hold_s`) → `standby`(1). Режими:
`auto` (AMF як вище), `manual` (пуск/стоп лише командами `relay_api.md`; перемикання — командою), `stop` (усе вимкнено),
`test` (пуск на `test_min` з навантаженням за `test_on_load`; `td_genset` «тест 3 хв» — як у ТР 1.2). Команди пульта
`td_genset` через існуючі ендпоінти `relay_api.md` впливають на `mode`/`start`/`stop` як сьогодні.

Фізика на тік (1 с × `RELAY_TIME_FACTOR`): у `running`/`loaded` — `p_kw = load_kw` (з `POST /sim/v1/load`, умовчання
`start.load_kw` = 348 за макетом `critical_kw`), `load_pct = p_kw/kw_prp·100`, `fuel_l −= fuel_lph(load_pct)·dt/3600` (R-01),
`hours += dt/3600`, `kwh += p_kw·dt/3600`, `coolant_c → coolant_run_c` експоненційно з `coolant_tau_s`, `oil_bar = oil_run_bar`
(± шум 0,1), `rpm = 1500 ± 5`, `u_v = 400 ± 2`, `f_hz = 50,0 ± 0,1`, `i_a = p_kw·1000/(√3·400·pf)`, `charger_v = 27,6`;
у `standby` — `p_kw=0`, `coolant_c → coolant_idle_c`, `oil_bar=0`, `rpm=0`, `charger_v=0`, `batt_v=25,2`; `starts += 1` на
кожну успішну прокрутку. Тривоги: `fuel_pct < low_fuel_warn_pct` → warning «Low Fuel Level»; `< low_fuel_sd_pct` → shutdown;
`coolant_c > coolant_high_c` → shutdown «High Temp.»; `oil_bar < oil_low_bar` у `running/loaded` після `safety_on` → shutdown
«Low Oil Pressure»; `batt_v` поза межами → warning. Події (`id` зростаючий, `ts`, `code`, `severity`, `name`, `value`, `unit`,
`threshold`, `text`) — у журнал, який `td_genset` читає через `relay_api.md` як сьогодні (ЗВІРИТИ формат — Q-14).

### 8.4 REST `/sim/v1/*` для емулятора (API-F-01…API-F-09)

Спільне: `Authorization: Bearer <RELAY_SIM_TOKEN>`; JSON; помилки `{"detail": "..."}` з кодами 401 (токен), 404 (роутер вимкнений
або невідомий ресурс), 409 (команда неможлива в поточному стані), 422 (валідація). Часи — ISO 8601 з зоною (`RELAY_TZ`).

| ID | Метод і шлях | Тіло запиту | Відповідь 200 | Примітки |
|---|---|---|---|---|
| API-F-01 | `GET /sim/v1/state` | — | `{"profile":"D700","sim_time":"…","factor":1.0,"mode":"auto","state":"loaded","state_code":7,"engine":"running","mains_ok":false,"gen_ok":true,"breaker":"gen","remote_start":false,"p_kw":348.0,"load_pct":68.6,"u_v":400.2,"f_hz":50.0,"i_a":628.0,"pf":0.8,"kwh":61255.3,"fuel_l":497.4,"fuel_pct":81.5,"fuel_lph":95.5,"hours":1213.3,"starts":185,"coolant_c":84.1,"oil_bar":4.4,"batt_v":25.3,"charger_v":27.6,"rpm":1502,"alarms":[],"alarm_level":0,"timers":{"active":null,"remaining_s":0},"last_test":"…"}` | читають iot_sim (модель ATyS R-22: `gen_ok` → `src2_ok`, `breaker` у варіанті A) і тести |
| API-F-02 | `POST /sim/v1/mains` | `{"available": false}` / `{"available": true, "u_v": 400, "f_hz": 50.0}` | `{"mains_ok": false, "state": "mains_abnormal"}` | варіант A: контролер бачить мережу сам; варіант B: лише для індикації `mains_ok` (перемиканням керує ATyS через API-F-03) |
| API-F-03 | `POST /sim/v1/remote_start` | `{"on": true}` | `{"remote_start": true, "state": "starting"}` | вхід «Remote Start» (варіант B: контакт ATyS 71/74); у `mode != auto` → 409 |
| API-F-04 | `POST /sim/v1/load` | `{"kw": 348}` | `{"load_kw": 348, "load_pct": 68.6}` | навантаження на шині генератора (iot_sim рахує з балансу R-06); `kw > kw_esp` → 422; `kw` між PRP і ESP → warning «Genset Over Current» (Table 4 № 2) після `over_current_delay_s`=30 |
| API-F-05 | `POST /sim/v1/fault` / `POST /sim/v1/clear` | `{"alarm": "low_oil_pressure" \| "high_temp" \| "low_fuel" \| "start_fail" \| "batt_low" \| "comm_lost" \| "over_speed" \| "emergency_stop"}` / `{"alarm": "…"}` або `{}` (усі) | `{"alarms": [{"code","name","severity","since"}]}` | `comm_lost` — ретранслятор відповідає 503 на ендпоінти `relay_api.md` (не на `/sim/v1`) — для ТК офлайну; `clear` аварійної зупинки → стан `standby`, лічильник спроб скинуто |
| API-F-06 | `POST /sim/v1/fuel` | `{"liters": 500}` або `{"pct": 82}` або `{"add_liters": 110}` | `{"fuel_l": 500.0, "fuel_pct": 82.0}` | заправка (ТК «Заправка»); > `tank_l` → 422 |
| API-F-07 | `POST /sim/v1/time` | `{"factor": 10.0}` і/або `{"set": "2026-10-12T07:00:00+03:00"}` | `{"factor": 10.0, "sim_time": "…"}` | як iot_sim API-14; `factor` 0,1…60 |
| API-F-08 | `POST /sim/v1/reset` | `{"profile": "d700", "preset": "plant"}` (обидва необов'язкові) | `{"ok": true, "profile": "D700", "preset": "plant"}` | повертає `start` профілю, журнал подій очищається, `id` подій продовжує рости (щоб `td_genset` не плутав `since`) |
| API-F-09 | `GET /sim/v1/events?since=<id>&limit=500` | — | `{"items": [{"id","ts","code","severity","name","value","unit","threshold","text"}], "next": id}` | дзеркало журналу подій для тестів; `td_genset` читає журнал своїм шляхом (`relay_api.md`) |

Приклад (варіант A, блекаут):

```http
POST /sim/v1/mains HTTP/1.1
Authorization: Bearer 9c2e…
Content-Type: application/json

{"available": false}

HTTP/1.1 200 OK
{"mains_ok": false, "state": "mains_abnormal", "timers": {"active": "mains_abnormal_s", "remaining_s": 5}}
```

Через ≈ 30 с (умовчання) `GET /sim/v1/state` → `"state": "loaded", "breaker": "gen", "gen_ok": true, "p_kw": 348.0`.

### 8.5 Compose (CR-03, iot_sim §8.1.4)

У `services/iot_sim/docker-compose.sim.yml` сервіс `genset_relay` уже описаний (`build: ${TD_GENSET_PATH}/relay`, профілі
`demo`/`dev`, мережа `f3d_sim`). Запит на зміни до iot_sim (CI-02): додати `environment: {RELAY_PROFILE: d700, RELAY_PORT: "8000",
RELAY_SIM_TOKEN: "${RELAY_SIM_TOKEN}", RELAY_TIME_FACTOR: "1", RELAY_TZ: Europe/Kyiv}`, `healthcheck: {test: ["CMD", "python", "-c", "import socket; socket.create_connection(('localhost', 8000), 3)"]}`
(TCP-перевірка порту: образ `python:3.12-slim` (§8.1) без `curl`, шлях health `relay_api.md` не потрібен; X-90), `networks: [f3d_sim, odoo_default]` — другий потрібен, щоб Odoo (`td_genset`) достукався до `genset_relay:8000`
(allow-list iot_sim §2.6 стосується вихідних з'єднань емулятора, не Odoo). Стенд `td_genset` (власний compose) лишається для
регресії ТК-01…ТК-14 з профілем `office` і `d700`.

### 8.6 Контракт з емулятором `factory3d_iot_sim` (CI-01, P-12, сценарії `blackout`/`genset_test`)

Напрямок: **iot_sim → fake_relay** (емулятор — оркестратор; `fake_relay` нічого не викликає сам). Параметри сценарію `blackout`
(iot_sim §9.3 S-03; існуючі — `duration_s` (умовчання 600), `genset` (bool, true), `restore_delay_s` (60); запит CI-01 додає):
`amf_master` ∈ {`hgm`, `ats`} (умовчання з `SIM_GENSET_AMF_MASTER=hgm`), `genset_load_kw` (умовчання — `critical_kw` з балансу
емулятора, 348). Мережа повертається по закінченні `duration_s` або по `stop`. Параметри CI-01 внесено в SPEC iot_sim (X-59; Q-21 закрито) — послідовність
нижче виконує емулятор; тестовий оркестратор `tests/stand/orchestrator.py` (§13.3.0) лишається для регресії на власному стенді td_genset (X-91).

Послідовність у iot_sim (варіант `hgm`): t0: мережа PM5560 unit 1/2 → 0 В, SUN2000 → `0x0303`, TEDOM — за моделлю iot_sim R-12
(острівний режим — Q-02; міст і energy беруть `infra/totals/chp_kw` виміряним, X-10), ATyS модель: `src1_ok=0`;
`POST /sim/v1/mains {"available": false}`; кожну 1 с `GET /sim/v1/state`: коли `breaker == "gen"` → ATyS `position=3 (II)`,
`src2_ok=1`, `POST /sim/v1/load {"kw": genset_load_kw}`; баланс R-06 у емуляторі (`infra/totals/*`). Завершення: `POST /sim/v1/mains
{"available": true}`; коли `breaker == "mains"` → ATyS `position=2 (I)`; після `state == standby` — `src2_ok=0`.
Варіант `ats`: iot_sim веде таймери ATyS p: `src1_ok=0` → 1FT 3 с → `POST /sim/v1/remote_start {"on": true}` (реєстр 20484=1) →
опитування `gen_ok` → 2AT 5 с → `position` 2→1(0, ODT 3 с)→3 → `POST /sim/v1/load`; якщо `gen_ok` не настав за 2ST 30 с —
подія iot_sim «FAIL START» (ТК-G04); повернення: `src1_ok=1` → 1RT 180 с → `position` 3→1→2, `POST /sim/v1/load {"kw": 0}` → 2CT 180 с →
`POST /sim/v1/remote_start {"on": false}`. У варіанті `ats` iot_sim **не** викликає API-F-02 (для HGM мережа «в нормі»; перемикає ATyS) —
правило станів `fake_relay` для цього випадку в Додатку D.3. Сценарій `genset_test` (S-14): `POST /sim/v1/remote_start {"on": true}` на
`duration_s` (умовчання 900 = 15 хв) без перемикання ATyS (`test_on_load=false`, новий параметр CI-01) або з перемиканням (`true`);
по закінченні `{"on": false}`; `fake_relay` фіксує `last_test`.

У каталозі iot_sim (Додаток A) для генератора **один** довідковий рядок — № 662 `infra/genset/GENSET/state` (`source=td_genset`,
у зведенні каталогу «`td_genset` 1»; X-62); емулятор його не веде. Значення всіх 26 кодів CG-01 (Додаток A цього документа) веде
міст із `td_genset`; повний перелік — тут, не в каталозі iot_sim.
Якщо `RELAY_SIM_TOKEN` порожній (роутер вимкнений) — iot_sim застосовує запасний режим Q-15 (генератор «запущений» через 15 с).

### 8.7 Логування `fake_relay`

JSON-рядки: `{"ts","level","msg","state","mode","p_kw","fuel_l","event"}`; переходи стан-машини — INFO; команди `/sim/v1` — INFO
з тілом (без токена); тривоги — WARNING. Токен у логах не друкується (фільтр як у iot_sim §8.16).

## 9. Алгоритми й правила

### R-01 Витрата палива за навантаженням (FR-02, CR-05, A-13)

`profile.fuel_lph(load_pct)`; `p = min(max(load_pct, 0.0), 110.0)`; вузли `(25, fuel_lph_25)`, `(50, fuel_lph_50)`, `(75, fuel_lph_75)`,
`(100, fuel_lph_100)`, `(110, fuel_lph_esp)` (110 % PRP = 558/507 — ESP). `p ≤ 25` → `fuel_lph_25` (даних нижче 25 % у датасіті немає —
консервативна стала); інакше лінійна інтерполяція між сусідніми вузлами; результат `round(…, 1)`.

| Вхід `load_pct` | Вихід, л/год | Розрахунок |
|---|---|---|
| 0 | 38,6 | стала нижче 25 % |
| 25 | 38,6 | вузол |
| 50 | 71,2 | вузол |
| 68,6 (348 кВт) | 95,5 | 71,2 + (18,6/25)·(103,8 − 71,2) = 71,2 + 24,25 |
| 75 | 103,8 | вузол (картка макета) |
| 100 | 136,4 | вузол |
| 105 | 143,0 | 136,4 + 0,5·(149,5 − 136,4) |
| 110 і більше | 149,5 | обмеження ESP |

Сигнал `fuel_lph` = `fuel_lph(load_pct)` якщо `state ∈ {6, 7}` і `p_kw > 0`, інакше `0.0` (генератор не працює). Джерела: SDMO D700 datasheet
(50/75/100 % PRP, 100 % ESP), Doosan DP180LB spec (25 %) — ARCH §8.

### R-02 Автономність (FR-02)

`profile.autonomy_h(fuel_l, load_pct)` = `round(fuel_l / fuel_lph(load_pct), 1)`; `fuel_lph ≤ 0` → `None`. Опорне навантаження для сигналу
`autonomy_h` і картки: `ref_pct = load_pct` якщо `state == 7` і `p_kw > 0`, інакше `75` (як у `plant/infra.py`: «≈ 4,8 год при 75 %»).

| `fuel_l` | `ref_pct` | Вихід, год |
|---|---|---|
| 500 (82 % × 610) | 75 | 4,8 (500/103,8 = 4,817) — збігається з карткою макета |
| 500 | 68,6 | 5,2 (500/95,45) |
| 610 | 75 | 5,9 — збігається з паспортом («≈ 5,9 год») |
| 610 | 100 | 4,5 |
| 500 | 25 | 13,0 |
| 0 | 75 | 0,0 |

### R-03 Коди стану, режиму, вимикача, тривоги; навантаження (A-10)

| Сигнал | Код → текст картки (`state_label` тощо) | Джерело (ADP-10, ЗВІРИТИ сирі значення `td_genset`) |
|---|---|---|
| `state` | 0 «немає даних»; 1 «очікування»; 2 «мережа втрачена, затримка»; 3 «пуск»; 4 «захисна затримка»; 5 «прогрів»; 6 «працює без навантаження»; 7 «під навантаженням»; 8 «охолодження»; 9 «зупинка»; 10 «аварійна зупинка» | `STATE_MAP[state_raw.lower()]`; очікувані сирі значення (англ./укр., HGM/`td_genset`): standby/очікування → 1; mains abnormal → 2; start/crank/запуск → 3; safety on → 4; warming → 5; running/робота → 6, але 7 якщо `breaker == 2` **або** `p_kw ≥ 0.05·kw_prp` (25,35 кВт для D700; варіант B — навантаження перемикає ATyS, реле HGM не задіяне, A-16); cooling/охолодження → 8; stop idle/ets/зупинка → 9; alarm/shutdown/аварія → 10; невідомо → 0 + `last_publish_error` |
| `mode` | 0 «стоп»; 1 «ручний»; 2 «авто»; 3 «тест» | `MODE_MAP` |
| `breaker` | 0 «жодного»; 1 «мережа»; 2 «генератор» | `BREAKER_MAP` (у HGM — стан реле закриття мережі/генератора) |
| `mains_ok` | 0/1 | `snap["mains_ok"]` |
| `alarm_level` | 0 «немає»; 1 «попередження»; 2 «аварійна зупинка» | 2 якщо ∃ `alarms[].severity == "shutdown"`, 1 якщо ∃ `warning`, інакше 0 |
| `alarm_count` | ціле | `len(alarms)` |
| `online` | 0/1 | R-12 |

`load_pct = round(p_kw / profile.kw_prp · 100, 1)`: 348 кВт → 68,6 %; 507 → 100,0; 0 → 0,0. `fuel_l`: якщо `td_genset` дає літри — вони;
інакше `round(fuel_pct/100 · tank_l, 1)` (82 % → 500,2 л).

### R-04 Критичні споживачі (FR-11, X-11)

Джерело списку — **energy** (CE-04): `f3d.energy.node` з `is_critical=True` (10 вузлів: LP-1, LP-2, LP-3, DUST-1, COMPRESSOR,
BOILER, OFFICE, EF-ELEC, EF-CHG і лінія BW-1 — `plant/infra.py:CRITICAL`). Параметр `factory3d.genset.critical_codes` — лише
**запасний** (§5.1). Міст `infra.totals.critical_kw` **не** пише (його пише провайдер `infra` energy, CE-03/R-06 п. 7); число R-04
потрібне мосту лише для рядка картки «Критичні споживачі зараз» і `items` (R-10).

1. Основний шлях: якщо `"f3d.energy.node" in env` — `nodes = env["f3d.energy.node"].search_read([("is_critical","=",True)],
   ["code","kind","name","equipment_id"], order="code")`; код сигналу вузла — `energy/consumers/<code>/p_now` для `kind == "consumer"`,
   `energy/lines/<code>/p_now` для `kind == "line"` (ті самі сигнали, з яких energy рахує `critical_kw`, CE-04); вузли інших `kind` —
   пропуск з записом у лог DEBUG; назва для `items` — `equipment_id[1]`, якщо обладнання задано, інакше `name` вузла.
2. Запасний шлях (моделі немає або `nodes` порожні): `codes = [c.strip() for c in param("critical_codes").split(",") if c.strip()]`;
   назва для `items` — обладнання за кодом з шляху (передостанній сегмент: `energy/consumers/LP-1/p_now` → `LP-1` → `maintenance.equipment`
   «Щит освітлення LP-1»; `energy/lines/BW-1/p_now` → «Шинопровід BW-1»), **один** `maintenance.equipment.search_read([("f3d_code","in",
   codes_eq)], ["f3d_code","name"])`, для не знайдених — `f3d_resolve(code)` (CB-01), інакше сам код.
3. `vals = TEL-04(codes)`; `critical_kw = round(Σ value, 1)` для наявних кодів (незалежно від `status`); `missing = [коди без запису]` —
   у `node["critical_missing"]` (list) провайдера (діагностика) і в лог DEBUG; `item_names` — назви лише для наявних кодів (порядок `code`).
   Повертає `(critical_kw, missing, item_names)`.
4. Приклад макета (12.10, 10:30): сума LP-1..3, DUST-1, COMPRESSOR, BOILER, OFFICE, EF-ELEC, EF-CHG + лінія BW-1 = 347,8 → у картці
   «348 кВт з 507 кВт» — те саме число, що energy пише в `infra.totals.critical_kw` (energy AC-28: 347,847 → 348), бо список вузлів і
   сигнали спільні. Читання: ≤ 3 SQL (вузли, сигнали, назви обладнання) — провайдер укладається в ТП-02 (≤ 8 SQL).

### R-05 Острів і наявність мережі (FR-09, FR-10)

Входи: `pos = TEL-04([ats_position_code])`, `s1 = TEL-04([ats_src1_code])` (якщо коди непорожні), знімок контролера (`mains_ok`, `breaker`,
`state`, `online`), `now`. Свіжість сигналу ATS: `status != "stale"` **і** `now − last_ts ≤ 3·period_s` сигналу (`period_s` з запису; якщо
порожній — 30 с). Значення положення — за Annexe III ATyS p: `ats_position_ii_value` (параметр, умовчання `3`) = положення II, `ats_position_i_value`
(`2`) = положення I; `src1_ok` — 1/0 (energy зводить Source 1 State: 2 «Available» → 1, інакше 0 — CE-02).

| Пріоритет | Умова | `island` | `grid_ok` | `source` |
|---|---|---|---|---|
| 1 | `pos` свіжий | `pos == ii_value` | `s1 == 1` якщо `s1` свіжий; інакше `True` якщо `pos == i_value`, `False` якщо `pos == ii_value`, `None` інакше | `ats` |
| 2 | ATS нема/несвіжий, контролер `online` | `breaker == 2 and state in (6, 7)` | `mains_ok` | `hgm` |
| 3 | контролер офлайн | `last_state_json.island` (останнє відоме) | `None` | `stale` |

`amf_master` **не** змінює таблицю (ATS, якщо є, завжди точніший за контролер щодо положення вимикача); він впливає лише на рядок картки
«Логіка AMF» і на підказку ТК. Приклади: `pos=3` свіжий, `s1=0` → острів, мережі немає; `pos=2`, `s1=1` → не острів, мережа є; ATS нема,
`breaker=2`, `state=7`, `mains_ok=False` → острів (`hgm`); ATS нема, `online=False` → останнє відоме, `grid_ok=None`.

### R-06 Баланс при блекауті (спільне правило; тотали рахує `factory3d_energy`, міст дає `genset_kw`, `island`, `grid_ok` — CE-03)

Позначення (кВт): `load` — споживання до події, `pv`, `chp`, `bess` (+ заряд / − розряд), `grid`, `export`, `gen`, `crit` (R-04).
Нормальний режим (макет 12.10 10:30, `plant/infra.py`): `pv = min(900,16·0,52; 8·115) = 468`, `chp = 800·0,5 = 400`, `load = 626`;
`surplus = 468 + 400 − 626 = 242` → `bess = +200` (ліміт), `export = 42`, `grid = 0` (`dist/odoo_demo.json`: `export_kw=42`, `bess_kw=200`).

Острів (`island=True`): `grid = 0`, `export = 0` (energy R-14 п. 9); `pv`, `chp`, `bess` — **виміряні** значення energy
(`infra/totals/pv_now`, `infra/totals/chp_kw`, `infra/totals/bess_kw`; CE-03) — міст і energy нічого не підставляють (X-10).
СЕС у блекаут дає `0x0303` (anti-islanding SUN2000) → `pv = 0` вимірюванням, а не правилом. КГУ: чи працює TEDOM в острові (опція
PE/I, паралель з ДГУ) — питання до замовника (Q-02); до відповіді `chp` — те, що виміряно (`0`, якщо КГУ зупинилась від втрати
мережі; `> 0`, якщо працює). `gen = infra/genset/GENSET/p_kw` (сигнал моста). Баланс острова на виміряних значеннях:
`load_island = gen + chp + pv − bess` (`bess`: + заряд / − розряд), `shed = max(0, load − load_island)` (некритичні скинуті).
Приклади (вхід — виміряні значення, макет 12.10 10:30, `load = 626`, Σ критичних 348 — R-04):
- КГУ зупинилась (`chp = 0`): після перемикання `gen = 348`, `pv = 0`, `bess = 0` → `load_island = 348 + 0 + 0 − 0 = 348` ✓,
  `shed = 626 − 348 = 278` кВт; на інтервалі пуску (до `breaker=gen`) `gen = 0`, `bess = −200` (ліміт розряду; ПРИПУЩЕННЯ — критична
  шина тримається накопичувачем, недостача 148 кВт, Q-08) → `load_island = 200`.
- КГУ працює в острові (виміряно `chp > 0`): навантаження острова покривається `gen + chp`, тобто генератор бере лише
  `gen = load_island − chp − pv + bess`; міст публікує виміряний `p_kw`, energy — виміряний `chp_kw`; жодне з чисел не
  обнуляється й не перераховується мостом.
Після повернення мережі (`island=False`) — нормальні формули energy.
Ключі, які energy додає в `infra.totals` (CE-03, необов'язково для v1): `shed_kw`, `bess_mode` (`charge`/`discharge`/`idle`).
Автономність в острові: R-02 при 68,6 % і 500 л → 5,2 год; при повному баку 610 л → 6,4 год.

### R-07 Подія контролера → заявка ТО (FR-05, §6.8 каркаса)

1. `row = f3d.genset.event.map._match(ev)` (M-03): `td_code` → `hgm_name`+`severity` → `match_regex` → `DEFAULT_<severity>`; немає збігу → кінець.
   Поля заявки в кроці 3 уточнено §2.0.3 T-8 (без `f3d_equipment_code`; з `f3d_value`, `f3d_threshold`).
2. `row.action == "ignore"` → кінець; `"bus_only"` → подія шини `state` для GENSET; інакше крок 3.
3. `name, description = row._render(ev, link)`; `vals = {"name": name, "description": description, "maintenance_for": "equipment",
   "equipment_id": eq.id, "maintenance_team_id": eq.maintenance_team_id.id or env["maintenance.team"].search([("company_id","in",(eq.company_id.id, False))], limit=1).id,
   "maintenance_type": "preventive" if row.action == "request_preventive" else "corrective", "priority": row.priority,
   "request_date": today, "schedule_date": now (пріоритет 3) / now + 1 день (інакше), "user_id": eq.technician_user_id.id or False,
   "f3d_signal_id": signal("alarm_level" | "online" для comm | "hours" для service).id, "f3d_equipment_code": eq.f3d_code,
   "f3d_genset_event_key": "GENSET:%s" % row.key, "company_id": eq.company_id.id}`; `create` з `sudo()` (крон).
4. Приклади назв (шаблони data): `Генератор GENSET: аварійна зупинка — низький тиск оливи 0,8 бар при нормі ≥ 1,0 бар`;
   `Генератор GENSET: низький рівень палива 18 % (110 л) при нормі ≥ 25 %`; `Генератор GENSET: не вдалося запустити (3 спроби)`;
   `Генератор GENSET: втрачено зв'язок з контролером (немає даних 7 хв)`; `Генератор GENSET: планове ТО через 37 мотогодин (наступне на 1 250, зараз 1 213)`.
   Де `value`/`threshold` відсутні — фрагмент « — {value} …» у шаблоні замінюється на «—» (SafeDict повертає «—»).

### R-08 Дедуплікація й закриття (A-12)

1. Ключ: `GENSET:<map.key>` (події), `GENSET:SERVICE:<int(next_service_hours)>` (ТО), `GENSET:COMM_LOST` (R-12).
2. Є відкрита заявка (`stage_id.done = False`) з таким `f3d_genset_event_key` і `equipment_id` → `message_post("Повтор: <name> о <HH:MM DD.MM>")`,
   нову не створюємо (одна відкрита заявка на ключ).
3. Немає — створюємо (R-07). Закрита заявка з тим самим ключем не заважає новій (нова подія після закриття → новий запис).
4. Закриття (M-06): якщо поточний `alarm_level == 0` → `f3d_signal_id.status = "ok"`; інакше статус лишається `alarm` до наступного
   знімка без тривог (`_publish_one` ставить `status` через `q`, а `alarm` — це `last_state_json.alarm_level>0` → TEL-03 `status="alarm"`
   для сигналу `alarm_level` лише). Уточнення до TEL-03: статус `alarm` виставляється для сигналу `alarm_level` при `value ≥ 1`, інакше `ok`.
5. Відновлення зв'язку (R-12) → у відкриту `COMM_LOST`-заявку `message_post("Зв'язок відновлено о …")`; закриває людина.

### R-09 ТО за мотогодинами (FR-06, A-04, Q-17)

Щоденно (`cron_f3d_genset_service`) і при кожній події `severity == "service"`:
1. Якщо `adapters.td_genset.SERVICE_REQUESTS_BY_TD` (константа, умовчання `False`; `True`, якщо звірка Q-17 покаже, що `td_genset` сам створює
   `maintenance.request`) → міст лише дописує `f3d_equipment_code`, `f3d_signal_id` (`hours`) у заявки `td_genset` для GENSET без цих полів; кінець.
2. `info = ADP-05`; `due = info["due"] or info["hours_left"] ≤ param("service_warn_h", 50)`; якщо не `due` → кінець.
3. `avg_h_per_day`: з показань сигналу `hours` — `(hours_now − hours_30d_ago) / 30`, де `hours_30d_ago` — перше показання за останні 30 діб
   (`f3d.reading`), мінімум `0.1`; якщо показань нема — `1.0`.
4. `days = min(365, max(0, hours_left / avg_h_per_day))`; `schedule_date = now + days`; `priority = "3"` якщо `hours_left < 0`, `"2"` якщо
   `≤ 10`, інакше `"1"`.
5. R-07 з рядком мапи `SERVICE_DUE` (`request_preventive`), ключ `GENSET:SERVICE:<int(next_service_hours)>`, `f3d_signal_id = hours`,
   `name` «Генератор GENSET: планове ТО через 37 мотогодин (наступне на 1 250, зараз 1 213)» / «…прострочено на 12 мотогодин…».
   Приклад: `hours_now=1213`, `next=1250`, `avg=1.2` → `days=30.8` → `schedule_date` = 14.11.2026, пріоритет 1.
6. `maintenance.equipment.f3d_meter_signal_id` мостом не заповнюється (§2.0.3 T-7); `f3d_signal_id` заявки = сигнал `hours`.
7. Подія `td_genset` з `severity == "service"` (крон events): спершу дія рядка мапи (`MAINTENANCE_DUE_W`/`MAINTENANCE_DUE_SD`/`DEFAULT_SERVICE`,
   Додаток B), потім кроки 1–5 цього правила для зв'язки — одна планова заявка на `next_service_hours` незалежно від кількості подій.

### R-10 Картка GENSET у payload (FR-07, CG-02)

`fmt(v, d)` — як `plant/infra.py:_fmt`: тисячі пробілом, десятковий роздільник кома. `card = {"rows": [...], "items": [...], "note": NOTE, "warn": warn}`:

| # | Рядок | Значення (приклад: під навантаженням 348 кВт) |
|---|---|---|
| 1 | Потужність | `"{kva_prp} кВА / {kw_prp} кВт (основна)"` → «634 кВА / 507 кВт (основна)» |
| 2 | Стан | `state_label` + ` · {p_kw} кВт ({load_pct} %)` якщо `state == 7` → «під навантаженням · 348 кВт (68,6 %)»; при `state ∈ {0}` → «немає даних» |
| 3 | Режим | `mode_label` → «авто» |
| 4 | Логіка AMF | «HGM6120N (AMF)» / «ATyS p (головний)» за `amf_master` |
| 5 | Контролер | «SmartGen HGM6120N · CMM366B-4G → Odoo (td_genset)» |
| 6 | Паливо | `"{fuel_pct} % · {fuel_l} л"` → «82 % · 500 л» |
| 7 | Автономність | `"≈ {autonomy_h} год при {ref_pct} %"` → «≈ 5,2 год при 69 %» (у очікуванні — «≈ 4,8 год при 75 %») |
| 8 | Критичні споживачі зараз | `"{critical_kw} кВт з {kw_prp} кВт"` (`critical_kw` — R-04 з вузлів energy `is_critical`; `infra.totals.critical_kw` міст не пише, X-11) → «348 кВт з 507 кВт» |
| 9 | Мережа | «є» / «відсутня» / «—» + « · острів: генератор живить критичних» якщо `island` |
| 10 | Напруга · частота | `"{u_v} В · {f_hz} Гц"` лише при `state ∈ {6, 7}` → «400 В · 50,0 Гц» |
| 11 | Мотогодини | `"{hours} · до ТО {service_h_left}"` → «1 213 · до ТО 37» |
| 12 | Тривоги | «немає» / `"{n}: {name1}, {name2}"` |
| 13 | Остання перевірка | ADP-07 → «12.10 07:30 — тест 15 хв, норма» / «—» |
| 14 | Зв'язок | «оновлено 10:31» / «втрачено з 10:19» |

`items` — назви критичних споживачів (R-04). `NOTE` — стала (текст `plant/infra.py` картки: «Під час відключення генератор тримає…»).
`warn`: `alarm_level == 2` → «Аварійна зупинка: <назви>»; `online == 0` → «Зв'язок із контролером втрачено (<хв> хв)»; `alarm_level == 1` →
«Попередження: <назви>»; `island and autonomy_h < autonomy_warn_h` → «Палива на ≈ <год> год — підготувати заправку»; інакше ключа `warn` немає.
`infra.genset.GENSET` — усі 26 значень за R-11 + `state_label`, `mode_label`, `breaker_label`, `alarm_label`, `updated`, `critical_missing`.

### R-11 Округлення значень у payload (як viewer M-01h, `plant/odoo_pull.py`)

`unit == "%"` → `round(v/100, 3)` (82 → 0.82); інакше `|v| < 20` → `round(v, 2)`, інакше `round(v, 1)`; сигнали з колонкою
«Payload» = `int` у Додатку A (коди стану й `starts`) → `int(v)`. Для `float`-сигналів правило однакове з viewer M-01h і telemetry R-12
(провайдер full і `signals` у `/delta`) — значення не «стрибають»; для `int`-сигналів дельта дає те саме число (7 і 7.0 у JSON рівні).

### R-12 Застарілі дані й офлайн (FR-15)

`fresh = snap["online"] and snap["ts"] and (now − snap["ts"]) ≤ offline_min`. Не `fresh` → публікуються `online=0`, `state=0`, `fuel_lph=0`,
`autonomy_h` (за останнім `fuel_l` при 75 %) з `ts=now`; решта 22 сигнали → `status="stale"` через `_mark_stale` (точний механізм — §2.0.3 T-3). Перехід `online 1→0`, що триває ≥ `offline_min`
(перевірка на кожному прогоні: `last_state_json.offline_since`) → одна подія `COMM_LOST` через R-07 (рядок мапи `COMM_LOST`), подія шини.
Перехід `0→1` → `message_post` у відкриту заявку, подія шини. Часові пояси: усі `ts` у БД — UTC naive (Odoo); `snap["ts"]` з `td_genset`
нормалізується в UTC (якщо aware → `astimezone(UTC).replace(tzinfo=None)`); картка показує Europe/Kyiv (`ctx["now_local"]`-стиль viewer R-02).
Годинник ретранслятора попереду Odoo > 120 с → `ts = now` і `last_publish_error = "годинник ретранслятора попереду на N с"`.

### R-13 Дельта переглядача: власна `_f3d_viewer_delta` з глибоким злиттям (FR-07, FR-17, X-23)

Розділ `infra` спільний: energy `infra` (150) пише `cards` PV-ROOF/PV-INV/CHP/ATS-1/BESS і `totals` CE-03, міст (155) — `cards.GENSET`,
`genset.GENSET`, `totals` CG-02; у дельті energy також зливає `infra` глибоко (energy A-22, R-18 п. 3). Базова дельта viewer (копія
розділу цілком) затерла б чужі ключі, тому міст має власний метод (M-08):

1. Умова (інакше метод нічого не робить, `patch` не змінюється): `ctx["changes"]` містить (а) `maintenance.equipment` з кодом сцени
   будь-якої активної зв'язки (`GENSET`) — подія M-01 `_notify_state_change`; або (б) `f3d.signal` з кодом із префіксом
   `infra/genset/` чи `infra/ats/` (острів R-05); або (в) `f3d.signal` з кодом зі списку критичних R-04 (рядок 8 картки).
2. `tmp = {}`; `self._f3d_viewer_collect(tmp, ctx)` — у `tmp["infra"]` лише ключі моста: `cards.GENSET`, `genset.GENSET`,
   `totals.genset_kw/genset_state/genset_fuel_pct/genset_autonomy_h/island/grid_ok/genset_kva`.
3. `deep_merge(patch.setdefault("infra", {}), tmp.get("infra", {}))` — рекурсивне злиття словників, списки — заміна (семантика
   energy R-18 п. 3); **ніколи** `patch["infra"] = …`. Хелпер — спільний `deep_merge` viewer M-01 (X-23); імпорт усередині методу
   (`from odoo.addons.factory3d_viewer.tools.payload import deep_merge` — модуль хелпера за viewer M-01), бо метод викликає лише
   viewer R-14, а на рівні модуля моста імпорту viewer немає (X-20).
4. Порядок провайдерів неважливий для результату: energy (150) і міст (155) пишуть різні листові ключі `infra`, злиття комутативне
   за ними; клієнт viewer зливає дельту глибоко (viewer R-14 п. 7, X-23).

Приклад: `patch = {"infra": {"cards": {"PV-INV": {…}}, "totals": {"pv_now": 468, "chp_kw": 400}}}` (уже від energy),
`ctx.changes = {"f3d.signal": {"infra/genset/GENSET/state"}}` → після методу `patch.infra.cards` має `PV-INV` і `GENSET`,
`patch.infra.totals` — `pv_now=468`, `chp_kw=400` і `genset_kw`, `island`, `grid_ok`… (AC-26, AC-72).

## 10. Стани й переходи

### 10.1 Генератор (сигнал `state`, за мануалом HGM6100N §4.3; емулятор §8.3)

| Зі стану | Подія/умова | У стан | Побічні ефекти моста |
|---|---|---|---|
| 1 очікування | мережа поза межами (AMF) / remote start | 2 / 3 | подія шини `state` |
| 2 затримка | Mains Abnormal Delay минув | 3 | — |
| 3 пуск | двигун запущено | 4 | `starts += 1` (лічильник з контролера) |
| 3 пуск | `Start Times` вичерпано | 10 | тривога shutdown «Fail to Start» → заявка (R-07) |
| 4 захисна затримка | Safety On минув | 5 (або 6, якщо Warming = 0) | — |
| 5 прогрів | Warming Up минув, U/f у нормі | 6 | — |
| 6 без навантаження | реле генератора закрито (Transfer Delay) | 7 | `island` може стати True (R-05) |
| 7 під навантаженням | мережа в нормі → Mains Normal Delay → Stop Delay; реле мережі закрито | 8 | `island=False` |
| 6/7 | shutdown-тривога | 10 | заявка, `alarm_level=2` |
| 8 охолодження | Cooling минув | 9 | — |
| 9 зупинка | двигун зупинено (After Stop) | 1 | — |
| 10 аварійна зупинка | скидання на контролері/пульті | 1 | заявка лишається відкритою до закриття людиною |
| будь-який | дані застаріли (R-12) | 0 | `online=0`, `stale`, `COMM_LOST` |

### 10.2 Зв'язка `f3d.genset.link`

`online` ∈ {True, False}; `publish_enabled` ∈ {True, False}; `last_publish_error` ∈ {False, текст}. Переходи — крон publish. Архівація
(`active=False`) зупиняє публікацію і події; сигнали лишаються (стають `stale` природно).

### 10.3 Заявка ТО з ключем генератора

Стандартні стадії `maintenance.stage` («New Request» → «In Progress» → «Repaired»/«Scrap»); міст реагує лише на перехід у стадію з `done=True`
(R-08 крок 4). Повтор події у відкриту — коментар; після `done` — новий запис при новій події.

## 11. Обробка помилок

1. **Ретранслятор недоступний** — фіксує `td_genset`; міст бачить `online=False`/застарілий `ts` → R-12. Крон не падає, `failure_count` не росте.
2. **Адаптер не звірений** (`NotImplementedError`) — `last_publish_error="ADP-xx: звірити з td_genset"`, крон продовжує інші зв'язки; `action_check`
   показує `UserError` з тим самим текстом; `post_init_hook` — `skipped` у звіті.
3. **Запис у телеметрію впав** (виняток TEL-03) — savepoint відкочує частковий пакет, `last_publish_error`, повтор через хвилину; показання не
   втрачаються (у `td_genset` вони лишаються; міст публікує лише останній знімок — історія між збоями відсутня, це прийнятно: сирі ряди веде `td_genset`).
4. **Немає обладнання GENSET / паспорта** — зв'язку створити не можна (`ValidationError` M-01); хук — `skipped`.
5. **Відсутні сигнали ATS / критичних споживачів** — пропуск без помилки; `critical_missing` у `infra.genset.GENSET`, R-05 пріоритет 2.
6. **Дублікати показань** — TEL-03 ідемпотентний за `(signal, ts)`; той самий знімок двічі (ретранслятор не оновив `ts`) → `skipped`, `last_publish_ts`
   оновлюється, але `online` рахується від `snap["ts"]`, не від часу прогону.
7. **Невідомий сирий стан/режим** — код 0/`None` + `last_publish_error` «невідомий стан: …»; картка «немає даних»; тест ADP-10 перелічує всі сирі значення
   `td_genset` з його селекцій (`fields_get` → `selection`) і вимагає, щоб кожне було в мапі.
8. **Невалідний код події** (regex) — `code=""`, збіг за `hgm_name`/regex/`DEFAULT_*`.
9. **Шаблон заявки з невідомим ключем** (`{foo}`, `{name.__class__}`) — відхиляється при збереженні (M-03 `_check_templates`, AC-61);
   відсутнє значення події (`value=None`, `threshold=None`) — `SafeDict` → «—», без винятку. Числа в шаблонах — `%.1f` з комою як
   десятковим роздільником (`0,8`), як у AC-12.
10. **Часові пояси** — R-12; `schedule_date` заявок — UTC naive; `request_date` — дата за Europe/Kyiv (`fields.Date.context_today` з `tz` користувача крона = `Europe/Kyiv`, умовчання `base.user_root` виставити в хуку? — ні: використовувати `datetime.now(ZoneInfo("Europe/Kyiv")).date()` явно).
11. **Кілька зв'язок на одне обладнання** — SQL-обмеження; **одна зв'язка на кілька генераторів** — `td_ref_uniq`.
12. **Провайдер впав** — viewer R-01 ізолює (`meta.sections.infra="error"`, `meta.errors`), картка лишається статичною з моделі.
13. **`fake_relay` без `RELAY_SIM_TOKEN`** — `/sim/v1/*` → 404; iot_sim запасний режим Q-15.

## 12. Acceptance Criteria

Тип перевірки (легенда, DOC_STANDARD, X-102): **UT** — юніт-тест Odoo (`odoo.tests`, §13.1), **TC** — стенд (`fake_relay` D700 + емулятор `factory3d_iot_sim`, §13.3), **MAN** — ручна перевірка на timur-o19demo (база `odoo`), **REG** — регресія `td_genset` (176 UT + 45 ТК за ТР 1.2, §13.2; складений тип UT/TC); комбінації «UT/TC», «TC/MAN» — перевірка двома способами.

Частина A (перенос `td_genset`):

| AC | FR | Given / When / Then | Тип |
|---|---|---|---|
| AC-A01 | FR-A01 | Given порожня база Odoo 19.0 без демо; When `-i td_genset`; Then установка без traceback, `ir.module.module.installed_version = 19.0.1.0.0`, усі `ir.ui.view` модуля мають `type ∈ {list, form, kanban, search, graph, pivot, calendar, qweb}` | REG/UT |
| AC-A02 | FR-A02 | When `--test-tags /td_genset`; Then 176 тестів `OK`, 0 `skipped` через версію, 0 `DeprecationWarning` від `td_genset` у логу | REG |
| AC-A03 | FR-A03 | Given стенд `td_genset` з `fake_relay` профіль `office`; When ТК-01…ТК-14 (45); Then результати = ТР 1.2; When профіль `d700`; Then ті самі результати з числами D700 (бак 610, витрата R-01) | REG/TC |
| AC-A04 | FR-A04 | Given користувач-оператор; When «Авто», «Старт», «Стоп», «Тест 3 хв» на пульті; Then команди доходять до `fake_relay` (журнал API-F-09 містить `command`), консоль браузера без помилок, у коді 0 входжень `useService("rpc")`/`jsonrpc` | REG/MAN |
| AC-A05 | FR-A05 | Given копія проду 18.0 з 111 користувачами; When `-u td_genset` на 19.0; Then для кожної групи `td_genset` кількість користувачів до/після однакова; `res.groups.privilege` для `td_genset` існує; `category_id` на `res.groups` не використовується | REG/UT |
| AC-A06 | FR-A06 | Given `RELAY_PROFILE=d700`, `RELAY_SIM_TOKEN` задано; When `GET /sim/v1/state`; Then `profile="D700"`, `fuel_l=500.2`, `hours=1213.0`, `mode="auto"`; When без токена; Then 401; When `RELAY_SIM_TOKEN` порожній; Then 404 | TC |
| AC-A07 | FR-A07 | Given копія проду; When `neutralize.sql` base → td_genset → factory3d_genset; Then крони `td_genset` і моста `active=false`, адреса ретранслятора не прод, `factory3d.genset.read_enabled='False'` | TC |
| AC-A08 | FR-A08 | Then `relay_api.md` містить розділ API-F-01…09, `CHANGELOG.md` — `19.0.1.0.0` з переліком MG-xx, `DEPLOY_TEST.md` — кроки 19.0, `docs/MIGRATION_19.md`, `docs/REGRESSION_19.md` (69 рядків), `docs/ADAPTER_MAP.md` | MAN |

Частина B (міст):

| AC | FR | Given / When / Then | Тип |
|---|---|---|---|
| AC-01 | FR-01 | Given обладнання `GENSET` з паспортом `genset` і один генератор у `td_genset` (мок ADP-02); When `post_init_hook`; Then 1 `f3d.genset.link` з `equipment_id=GENSET`, `profile_id=profile_d700`, `source_id.type='td_genset'`; `migration_report.link.created=1` | UT |
| AC-02 | FR-01 | Given два генератори (мок); When хук; Then 0 зв'язок, `report.link="skipped: кілька генераторів — зв'яжіть вручну"`; When менеджер створює зв'язку вручну; Then ок; When другу на те саме обладнання; Then `ValidationError` «Для цього обладнання зв'язка вже існує.» | UT |
| AC-03 | FR-01 | Given обладнання без `f3d_code` або з паспортом ролі `compressor`; When `create` зв'язки; Then `ValidationError` з текстами M-01 | UT |
| AC-04 | FR-02 | When `profile_d700.fuel_lph(x)` для x ∈ {0, 25, 50, 68.6, 75, 100, 105, 110, 150}; Then 38,6; 38,6; 71,2; 95,5; 103,8; 136,4; 143,0; 149,5; 149,5 | UT |
| AC-05 | FR-02 | When `autonomy_h(500, 75)`, `(500, 68.6)`, `(610, 75)`, `(610, 100)`, `(0, 75)`; Then 4,8; 5,2; 5,9; 4,5; 0,0; When `fuel_lph` повертає 0 (мок); Then `None` | UT |
| AC-06 | FR-02 | When `write({"fuel_lph_50": 30})` (менше за 25 %-значення); Then `ValidationError` «Крива витрати має бути неспадною.»; `tank_l=0` → `ValidationError` | UT |
| AC-07 | FR-03 | Given зв'язка, мок ADP-03 (стан running, breaker gen, 348 кВт, 82 %, 1213 год, online, ts=now); When `_cron_publish`; Then 26 `f3d.reading` з `ts=snap.ts`, `f3d.signal.last_value`: `state=7`, `p_kw=348`, `load_pct=68.6`, `fuel_l=500.2`, `fuel_lph=95.5`, `autonomy_h=5.2`, `hours=1213`, `online=1`; `last_publish_ts` заповнено, `last_publish_error=False` | UT |
| AC-08 | FR-03 | Given `factory3d.genset.read_enabled=False`; When `_cron_publish`; Then 0 показань; When `action_check`; Then `UserError` «Публікацію вимкнено стоп-краном factory3d.genset.read_enabled» | UT |
| AC-09 | FR-03 | Given `environment='prod'` (base); When `post_init_hook`; Then `read_enabled='False'`, крон publish `active=False`; `environment='test'` → `True`/`True` | UT |
| AC-10 | FR-03 | Given той самий знімок двічі (однаковий `ts`); When два прогони; Then 26 показань (не 52), `ingest` повернув `skipped=26` на другому | UT |
| AC-11 | FR-04 | Then усі 26 сигналів GENSET мають `create_request=False`, `alarm_states` порожній; 25 з них — `warn_low_on = warn_high_on = alarm_low_on = alarm_high_on = False`; `infra/genset/GENSET/alarm_level` — лише `alarm_high_on=True`, `alarm_high=0.5` (§2.0.3 T-4); When сигнал `alarm_level` отримує 2; Then `status='alarm'` і telemetry заявки не створює (`maintenance_request_id=False`) | UT |
| AC-12 | FR-05 | Given подія `{"code":"LOP_SD","severity":"shutdown","name":"Low Oil Pressure","value":0.8,"unit":"бар","threshold":1.0}` і рядок мапи з `hgm_name="Low Oil Pressure"`; When `_cron_events`; Then 1 `maintenance.request`: `maintenance_type='corrective'`, `priority='3'`, `maintenance_for='equipment'`, `equipment_id=GENSET`, `maintenance_team_id=команда обладнання`, `name="Генератор GENSET: аварійна зупинка — низький тиск оливи 0,8 бар при нормі ≥ 1,0 бар"`, `f3d_equipment_code='GENSET'`, `f3d_signal_id=сигнал alarm_level`, `f3d_genset_event_key='GENSET:LOW_OIL_PRESSURE_SD'`, `schedule_date` ≈ now | UT |
| AC-13 | FR-05 | Given та сама подія повторно (новий `id`), заявка відкрита; When крон; Then заявок 1, у чаттері «Повтор: … о …»; When заявку переведено в «Repaired» і подія знову; Then заявок 2 | UT |
| AC-14 | FR-05 | Given подія warning «Genset Over Current» (рядок `GENSET_OVER_CURRENT_W`, `bus_only`); When крон; Then заявок 0, `f3d.viewer.event` з `model='maintenance.equipment'`, `codes=['GENSET']`, `kind='state'` | UT |
| AC-15 | FR-05 | Given подія з невідомими `code`/`name` і `severity='shutdown'`; Then рядок `DEFAULT_SHUTDOWN` → заявка `corrective`, пріоритет 3, назва «Генератор GENSET: аварійна зупинка — <name>» | UT |
| AC-16 | FR-05 | Given `requests_enabled=False`; When крон events; Then 0 заявок, `last_event_ts` не зсувається | UT |
| AC-17 | FR-05 | Given 250 подій; When один прогін; Then оброблено 200, `last_event_id` = id 200-ї; другий прогін — решта 50 | UT |
| AC-18 | FR-06 | Given ADP-05 `{hours_now:1213, next_service_hours:1250, interval_h:250, due:False}`, показання `hours` 30 днів тому = 1177; When `_cron_service`; Then 1 заявка `preventive`, `priority='1'`, `name="Генератор GENSET: планове ТО через 37 мотогодин (наступне на 1 250, зараз 1 213)"`, `schedule_date` = now + 30,8 дня (±1 день), `f3d_genset_event_key='GENSET:SERVICE:1250'`, `f3d_signal_id=hours`; повторний прогін — заявок 1 | UT |
| AC-19 | FR-06 | Given `hours_left=-12`; Then `priority='3'`, `schedule_date` ≈ now, назва «…прострочено на 12 мотогодин…»; Given `hours_left=120`, `due=False`; Then заявок 0 | UT |
| AC-20 | FR-06 | Given установка моста (хук) і 3 прогони `_cron_service` та `_cron_publish`; Then `maintenance.equipment(GENSET).f3d_meter_signal_id` порожнє, `f3d_meter_interval == 0`, `f3d_meter_request_id` порожнє; заявок з `f3d_origin='meter'` — 0 (§2.0.3 T-7, A-04) | UT |
| AC-21 | FR-06 | Given `SERVICE_REQUESTS_BY_TD=True` і заявка `td_genset` для GENSET без `f3d_equipment_code`; When крон; Then у неї `f3d_equipment_code='GENSET'`, `f3d_signal_id=hours`; нових заявок 0 | UT |
| AC-22 | FR-07 | Given зв'язка, сигнали з AC-07; When `PayloadBuilder.build(full=True)`; Then `infra.cards.GENSET.rows` = 14 рядків R-10 з очікуваними текстами («634 кВА / 507 кВт (основна)», «під навантаженням · 348 кВт (68,6 %)», «82 % · 500 л», «≈ 5,2 год при 69 %», «348 кВт з 507 кВт»…), `items` = 10 назв, `note` — стала; `infra.genset.GENSET.p_kw=348.0`, `fuel_pct=0.82`, `state=7`, `state_label="під навантаженням"`; `infra.totals.genset_kw=348.0`, `genset_state`, `island`, `grid_ok` | UT |
| AC-23 | FR-07 | Given провайдер `zz_test` у `test_factory3d_viewer`? — ні: Given порядок; Then у `PayloadBuilder.providers` `f3d.viewer.provider.genset` стоїть після `f3d.viewer.provider.infra` (якщо energy встановлено) і після `…signals` (90), `…telemetry` (95); `_f3d_sequence == 155` | UT |
| AC-24 | FR-07 | Given зв'язок немає; When `build()`; Then `infra.cards.GENSET` дорівнює статиці з `model_static.json`, `meta.sections.infra` без `error` | UT |
| AC-25 | FR-07 | Given сигнали `stale` (R-12); Then рядок «Зв'язок: втрачено з HH:MM», `warn` «Зв'язок із контролером втрачено (N хв)», `state_label="немає даних"` | UT |
| AC-26 | FR-07, FR-17 | Given `ctx.changes={"maintenance.equipment": {"GENSET"}}` і `patch={}`; When `_f3d_viewer_delta(patch, ctx)`; Then `patch.infra.cards.GENSET` і `patch.infra.genset.GENSET` присутні, інших карток немає, у `patch.infra.totals` лише ключі CG-02 (без `critical_kw`); Given `ctx.changes={"mrp.production": {"WH/MO/00231"}}`; Then `patch` не змінився (R-13 п. 1) | UT |
| AC-27 | FR-08 | Given попередній `last_state_json.state=1`; When знімок зі `state=7`; Then 1 `f3d.viewer.event` (`maintenance.equipment`, `['GENSET']`, `state`) і `message_post` у зв'язці; When той самий стан ще раз; Then подій не додається | UT |
| AC-28 | FR-08 | When лише `online` змінився (1→0) без зміни стану; Then подія шини є (R-12), `message_post` — немає | UT |
| AC-29 | FR-09 | Given сигнал `infra/ats/position=3` свіжий, `src1_ok=0`; Then `island=True`, `grid_ok=False`, `source='ats'`; Given `position=2`, `src1_ok=1`; Then `False/True`; Given `position` старіший за 3·period; Then беруться дані контролера (`breaker=2`, `state=7`, `mains_ok=False` → `island=True`, `source='hgm'`); Given контролер офлайн і ATS нема; Then `island` = останній, `grid_ok=None`, `source='stale'` | UT |
| AC-30 | FR-09 | Given `island=True` і тотали energy в `payload.infra.totals` (`grid_kw`, `chp_kw`, `pv_now`, `bess_kw`, `critical_kw`); Then жоден із цих ключів мостом **не** змінюється (власність energy; `chp_kw` — виміряне, X-10), але `infra.totals.island=True`, `genset_kw=348.0`; рядок картки «Мережа: відсутня · острів: генератор живить критичних» | UT |
| AC-31 | FR-10 | Given `amf_master='ats'`; Then рядок «Логіка AMF: ATyS p (головний)»; R-05 результати ті самі, що при `hgm` на тих самих входах | UT |
| AC-32 | FR-11 | Given 10 вузлів energy `is_critical=True` (energy AC-04), сигнали `p_now` з сумою 348, сигнал `energy/lines/BW-1/p_now` архівовано; Then `_critical_kw()` = `(348.0, ['energy/lines/BW-1/p_now'], names)`, `infra.genset.GENSET.critical_missing=['energy/lines/BW-1/p_now']`, `items` — 9 назв (обладнання вузла або `name` вузла); Given параметр `critical_codes` = `energy/consumers/LP-1/p_now` (один код); Then результат той самий (параметр ігнорується, бо є вузли `is_critical`, X-11) | UT |
| AC-33 | FR-12 | Given користувач `group_f3d_user`; When `write` зв'язки/профілю/мапи; Then `AccessError`; `group_f3d_manager` — ок; параметри `factory3d.genset.*` у меню «Параметри системи» видно лише `group_f3d_admin` (base) | UT |
| AC-34 | FR-12 | Then `factory3d.genset.write_enabled='False'` після установки; у коді моста немає викликів методів `td_genset` з іменами `start`/`stop`/`command` (grep-тест `test_no_commands`: жоден файл `models/*.py`, `adapters/*.py` не містить `.action_start`, `.action_stop`, `write(` на `GENSET_MODEL` крім ADP-09) | UT |
| AC-35 | FR-13 | When `neutralize.sql`; Then крони моста `active=false`, `read_enabled='False'`, `requests_enabled='False'`, `last_publish_ts` NULL; When `uninstall_hook`; Then параметри `factory3d.genset.%` відсутні, `f3d.signal` GENSET (26) і заявки лишились, джерело `active=False` | UT/TC |
| AC-36 | FR-14 | Given `docker compose --profile demo up genset_relay`; When `td_genset` адреса `http://genset_relay:8000`; Then `td_genset` показує показання профілю D700 (паливо 82 %, 500 л), міст публікує 26 сигналів | TC |
| AC-37 | FR-14 | Given сценарій `blackout` (`amf_master=hgm`); When старт; Then у `fake_relay` через ≤ 35 с `state=loaded`, `breaker=gen`, `p_kw=348`; в Odoo через ≤ 2 хв `infra/genset/GENSET/state=7`, `infra/ats/position=3` (energy), картка «острів», подія шини; When стоп; Then повернення: `state` 8 → 9 → 1, `island=False` | TC |
| AC-38 | FR-14 | Given сценарій `blackout` (`amf_master=ats`) з умовчаннями HGM; Then наказ пуску (`remote_start=true`) через 3 с після втрати мережі, `gen_ok` через ≈ 25 с, переключення через 2AT 5 с; `FAIL START` не виникає; Given пресет HGM `warming_s=60`; Then iot_sim фіксує «FAIL START» через 2ST 30 с (ТК-G04) | TC |
| AC-39 | FR-14 | Given `genset_test` (15 хв, `test_on_load=false`); Then `fake_relay.last_test` оновлено, картка «Остання перевірка: <дата> — тест 15 хв, норма», ATyS не перемикався (`position=2`) | TC |
| AC-40 | FR-15 | Given `POST /sim/v1/fault {"alarm":"comm_lost"}`; When ≥ `offline_min` (5 хв; на стенді `offline_min=1`, `RELAY_TIME_FACTOR=1` — §13.3.0); Then `online=0` і `state=0` (`status='ok'`, `ts`≈now), решта 22 сигнали `stale` (§2.0.3 T-3), заявка «Генератор GENSET: втрачено зв'язок з контролером (немає даних N хв)» з ключем `GENSET:COMM_LOST`; When `clear`; Then `online=1`, у заявці «Зв'язок відновлено о …», заявка відкрита | TC/UT |
| AC-41 | FR-16 | grep `models/`, `views/`, `data/`: усі `string=`, `help=`, тексти `UserError`/`ValidationError`, назви крона/меню — кирилицею (regex `[А-Яа-яІіЇїЄєҐґ]`), файлів `i18n/*.po` у модулі немає | UT (grep-тест) |
| AC-42 | FR-02, CR-05 | When `action_export_relay_profile`; Then вкладення `d700.json` з ключами §8.2, `fuel_lph.75=103.8`, `timers.mains_abnormal_s=5`; When `action_apply_to_td` з мок ADP-09 → `True`; Then повідомлення «Записано в td_genset: 1 генераторів; пропущено: 0» | UT |
| AC-43 | ADP | Given константи адаптера не заповнені; When `test_adapter_contract`; Then тест падає з переліком `ADP-01, ADP-03…`; Given заповнені (мок реєстру); Then усі `FIELD_*` є у `fields_get` відповідної моделі | UT |
| AC-44 | R-03 | Given `fields_get` селекції стану `td_genset` (мок: 6 значень); Then кожне значення є ключем `STATE_MAP` (тест перелічує відсутні) | UT |
| AC-45 | R-11 | When провайдер отримує `fuel_pct=82`, `p_kw=348.04`, `oil_bar=4.456`, `hours=1213.2`, `state=7.0`, `starts=185.0`; Then `0.82`, `348.0`, `4.46`, `1213.2`, `7` (`int`), `185` (`int`) | UT |
| AC-46 | R-12 | Given `snap.ts` = now + 300 с (годинник ретранслятора попереду); Then показання з `ts=now`, `last_publish_error` містить «годинник ретранслятора попереду» | UT |
| AC-47 | API-F | ТК-F01, ТК-F02 (§13.3.2): `GET /sim/v1/state` без токена → 401; `POST /load {"kw": 600}` → 422; `POST /remote_start` у `mode=manual` → 409; `POST /fuel {"liters": 700}` → 422; `POST /reset {"preset":"plant"}` → таймери пресету | TC |
| AC-48 | §8.3 | Given профіль d700, `POST /mains {"available": false}`; Then послідовність станів `mains_abnormal`(5 с) → `starting` → `safety_on`(10) → `warming`(10) → `running` → `loaded` з `breaker=gen`, усього 29–32 с при `factor=1`; `starts` +1; з `preset=plant` — 13–16 с; `fuel_l` зменшується на 95,5/3600 л за секунду при 348 кВт (±2 %) | TC |
| AC-49 | §8.3 | Given `POST /fault {"alarm":"start_fail"}` і `POST /mains {"available": false}`; Then 3 спроби по 8 с + 10 с пауза → `state=alarm_shutdown`, подія `Fail to Start` severity shutdown у `GET /sim/v1/events` | TC |
| AC-50 | §5.3 | Given копія демо-бази з base + telemetry + td_genset; When установка моста; Then кількості §5.3 (1 профіль, 1 джерело, 26 сигналів, 48 рядків мапи, 3 крони); повторне `-u` — ті самі кількості, `td_code` рядків мапи збережені | TC |
| AC-51 | FR-02, FR-03 | Given стенд §13.3.0, `fake_relay` `d700` у `loaded`, `POST /sim/v1/load {"kw": 348}`, паливо 500,2 л (82 %); When 10 хв при `RELAY_TIME_FACTOR=1`; Then `GET /sim/v1/state`: `fuel_lph=95.5`, `fuel_l` = 484,3 ± 0,4 (500,2 − 95,454·600/3600); в Odoo `infra/genset/GENSET/fuel_lph=95.5`, `fuel_l` = значення `td_genset` на момент останньої публікації (± витрата за 1 хв = 1,6 л), `autonomy_h=5.1`; When `POST /sim/v1/load {"kw": 507}`; Then `load_pct=100.0`, `fuel_lph=136.4`, `autonomy_h` = `round(fuel_l/136.4, 1)` (3,6 при 484,3 л) | TC |
| AC-52 | FR-03, FR-05, FR-07 | Given `standby`; When `POST /sim/v1/fuel {"liters": 140}` (23 % < `alarms.low_fuel_warn_pct`=25); Then подія «Low Fuel Level» (warning) у `GET /sim/v1/events`; в Odoo ≤ 4 хв рівно 1 заявка `f3d_genset_event_key='GENSET:LOW_FUEL_LEVEL_W'`, `priority='3'`, `name` починається «Генератор GENSET: низький рівень палива» і містить «при нормі ≥ 25,0 %»; картка: «Паливо: 23 % · 140 л», `warn` = «Попередження: Low Fuel Level»; When заправка за інструкцією «Заправка» (`POST /sim/v1/fuel {"add_liters": 360}` або дія пульта `td_genset`); Then `fuel_l=500.0`, payload `infra.genset.GENSET.fuel_pct=0.82`, картка «82 % · 500 л» і «≈ 4,8 год при 75 %», `alarm_level=0`; заявка лишається відкритою до закриття людиною | TC |
| AC-53 | FR-03, FR-08, FR-A04 | Given `standby`, `mode=auto`, мережа є; When оператор натискає «Тест 3 хв» на пульті `td_genset`; Then `fake_relay`: `mode=test`, `running` через 24 ± 3 с (Start Delay 1 + схоплювання 3 + Safety On 10 + Warming Up 10), `breaker=mains`, `p_kw=0`, через 180 с від `running` — `cooling` (10 с) → `stopping` (20 с) → `standby`; в Odoo серед показань `f3d.reading` сигналу `state` за час тесту є 6, останнє — 1; `island=False` і `breaker=1` увесь час; заявок 0; ≥ 2 події шини `state`; у чаттері зв'язки «Стан: працює без навантаження…» і «Стан: очікування…»; рядок картки «Остання перевірка» = ADP-07 (дата й час тесту, тривалість, результат `td_genset`) | TC/MAN |
| AC-54 | FR-03, FR-08 | Given розклад `td_genset` без вікна на поточний час (стенд: розклад за Q-03), `standby`; When оператор за інструкцією «Робота поза графіком» (ARCH §4.4) переводить пульт у ручний режим, запускає генератор, через 5 хв зупиняє і повертає «Авто»; Then в Odoo сигнал `mode` 2 → 1 → 2, `state` 1 → … → 6 → 8 → 9 → 1; події шини на кожну зміну `mode`/`state`; заявок 0 (події `command`/`info` → немає дії, Додаток B); `td_genset` фіксує роботу поза графіком так, як ТР 1.2 (REG) | TC/MAN |
| AC-55 | FR-05, FR-08 | Given `loaded` 348 кВт (варіант A); When `POST /sim/v1/fault {"alarm":"low_oil_pressure"}`; Then `fake_relay` `state=alarm_shutdown`; в Odoo ≤ 4 хв рівно 1 заявка `GENSET:LOW_OIL_PRESSURE_SD`, `maintenance_type='corrective'`, `priority='3'`, `maintenance_team_id` = «Служба головного механіка», `name` починається «Генератор GENSET: аварійна зупинка — низький тиск оливи»; сигнал `alarm_level=2`, `status='alarm'`; картка `warn` «Аварійна зупинка: Low Oil Pressure»; ескалація `td_genset` — за ТР 1.2 (AC-A13); When `clear` → повторний пуск → той самий `fault` до закриття заявки; Then заявок 1, у чаттері «Повтор: …»; When заявку переведено в «Repaired» при активній тривозі; Then `alarm_level` лишається `alarm` (telemetry R-06); When `clear` і знімок з `alarm_level=0`; Then статус `ok` | TC |
| AC-56 | FR-09 | Given сценарій `blackout` `amf_master=hgm`, `factory3d_energy` з CE-02/CE-03; When генератор під навантаженням; Then payload: `infra.totals.island=true`, `grid_ok=false`, `genset_kw=348.0`, `genset_state="під навантаженням"`, `genset_autonomy_h` = 5,2 ± 0,1; `grid_kw=0`, `export_kw=0`, `pv_now=0`; `chp_kw` дорівнює `last_value` сигналу `infra/totals/chp_kw` у момент знімка (виміряне, мостом і energy не обнуляється — X-10, energy R-14 п. 9; значення залежить від моделі КГУ iot_sim R-12 і Q-02, тест його не фіксує); картка: «Мережа: відсутня · острів: генератор живить критичних», «Критичні споживачі зараз: 348 кВт з 507 кВт» (емулятор R-22: P_genset = Σ критичних) | TC |
| AC-57 | FR-10 | Given `blackout` `amf_master=ats` в острові; When мережа повертається; Then `infra/ats/position` = II ще 180 ± 5 с (1RT; `island=true`), далі I; генератор 180 ± 5 с (2CT) у `running` з `p_kw=0` (`state=6`, `island=false`), далі 8 → 9 → 1; у `f3d.reading` сигналу `state` послідовність 7 → 6 → 8/9 → 1 (з точністю до періоду публікації); заявок 0 | TC |
| AC-58 | FR-12 | Given `factory3d.genset.write_enabled='True'` (вручну) і шпигун (`MagicMock(wraps=…)`) на кожній функції адаптера; When `_cron_publish`, `_cron_events`, `_cron_service`, `action_check`, `PayloadBuilder.build()`; Then викликались лише ADP-02…ADP-08, ADP-09 — 0 разів; у V-07 поле `f3d_genset_write_enabled` має `readonly="1"`; `grep -rn "write_enabled" models/ adapters/` не знаходить читання параметра (лише M-07 поле налаштувань) | UT |
| AC-59 | FR-12 | Given `user_nobody` (лише `base.group_user`); When `env["f3d.genset.link"].with_user(user_nobody).search([])`; Then `AccessError`; `menu_f3d_genset` відсутній у `env["ir.ui.menu"].with_user(user_nobody)._visible_menu_ids()`; `PayloadBuilder` від його імені не містить `infra.genset`; Given `user_reader`; Then читання зв'язки й профілю ок, payload має `infra.cards.GENSET` з 14 рядками | UT |
| AC-60 | FR-12 | Given `user_reader`; When `link.with_user(user_reader).action_check()`, `profile.with_user(user_reader).action_apply_to_td()`, `profile.with_user(user_reader).action_export_relay_profile()`; Then `AccessError` (тексти M-01, M-02; третій — права `ir.attachment` на запис профілю); Given `user_manager`; Then усі три успішні | UT |
| AC-61 | FR-05, FR-16 | When менеджер зберігає `name_tpl` = `"{name.__class__}"`, `"{value[0]}"`, `"{foo}"`; Then `ValidationError` «Шаблон: дозволені лише поля …» для кожного; Given подія `{"code": "../x; DROP TABLE", "name": "<script>alert(1)</script>", "severity": "shutdown", "text": "a"·10 240}`; When крон events; Then `code` нормалізовано в `""`, рядок `DEFAULT_SHUTDOWN`, `description` містить `&lt;script&gt;`, `len(name) ≤ 120`, винятку немає | UT |
| AC-62 | FR-03 | Then для кожного з 26 кодів Додатка A: `name`, `unit`, `kind` — як у таблиці; `equipment_id=GENSET`, `source_id.code='GENSET-RELAY'`, `module='genset'`, `period_s=100` (при `offline_min=5`), `store_period_s=0`, `viewer_visible=True`; When `offline_min=10` через `res.config.settings`; Then `period_s=200` у всіх 26; повторний хук наявні сигнали не змінює | UT |
| AC-63 | FR-04, FR-05 | Then `f3d.genset.event.map` має 48 рядків з ключами Додатка B: `hgm_table='warning'` — 17, `'shutdown'` — 24, `'other'` — 7; усі 24 аварійні — `request_corrective`, `priority='3'`; When `_match({"name": "Low Oil Pressure", "severity": "warning", "code": ""})`; Then `LOW_OIL_PRESSURE_W`; з `severity="shutdown"` — `LOW_OIL_PRESSURE_SD`; `_match({"name": "Remote start", "severity": "command", "code": ""})` — порожньо, `_apply_event` — 0 заявок і 0 подій шини | UT |
| AC-64 | FR-06 | Given ADP-05 як в AC-18 і дві події `{"name": "Maintenance Due Warning", "severity": "warning"}` (різні `id`); When `_cron_events`; Then заявок з ключем `GENSET:MAINTENANCE_DUE_W` — 0, з `GENSET:SERVICE:1250` — рівно 1 (R-09 крок 7), подія шини `state` є | UT |
| AC-65 | R-03 | Given знімок `state_raw="running"`, `breaker_raw="mains"`, `p_kw=348.0`; Then `state=7`; `p_kw=20.0` → `6`; `breaker_raw="generator"`, `p_kw=0.0` → `7`; `state_raw="невідомо"` → `0` і `last_publish_error` містить «невідомий стан» | UT |
| AC-66 | FR-07 | Given 1 зв'язка, 26 сигналів, 10 критичних, 3 сигнали ATS; When `PayloadBuilder.build()` від `user_reader`; Then провайдер genset додає ≤ 8 SQL (різниця `assertQueryCount` зі зв'язкою і без) і ≤ 50 мс (медіана 5 прогонів); `link._publish_one()` з моками адаптера — ≤ 40 SQL і ≤ 0,5 с | UT |
| AC-67 | FR-12, FR-13 | Given копія проду, `factory3d.base.environment='prod'`; When установка моста; Then `factory3d.genset.read_enabled='False'`, `cron_f3d_genset_publish.active=False`, за 10 хв 0 нових `f3d.reading` GENSET; When адміністратор вмикає `read_enabled` за ARCH §4.6 після звірки двох знімків з пультом; Then показання з'являються ≤ 2 хв; команди пульта `td_genset` на етапі 1 §13.6 заблоковані стоп-краном `td_genset` (Q-16) | MAN |
| AC-68 | FR-14, FR-A06 | Given `services/iot_sim/docker-compose.sim.yml` з CI-02; When `docker compose --profile demo config`; Then `genset_relay` має `RELAY_PROFILE=d700`, `RELAY_PORT=8000`, `RELAY_SIM_TOKEN` з `.env`, `healthcheck`, мережі `f3d_sim` і `odoo_default`, без `ports:` на хост; When `docker compose --profile demo up -d genset_relay`; Then `healthy` ≤ 60 с, `GET /sim/v1/state` з токеном → `profile="D700"` | TC |
| AC-69 | FR-03, CG-04 | Given база з telemetry і мостом; Then `"td_genset" in env["f3d.source"]._f3d_local_types()`; `tools.address.validate_params("td_genset", {}, env["f3d.source"]._f3d_local_types())` → `[]`; джерело `GENSET-RELAY` після хука: `type='td_genset'`, `module='genset'`, `collector_id` порожній, `is_local=True`, `params={}`; When менеджер створює друге джерело `type='td_genset'` без колектора; Then збережено без `ValidationError`; When джерело `type='modbus_tcp'` без колектора; Then `ValidationError` «Джерело …: вкажіть колектор.» (constraint telemetry, R-26); `f3d.source._fields["collector_id"]` — визначення telemetry (міст його не перевизначає: `models/f3d_source.py` не містить `collector_id` і `_check_f3d_collector_required`, X-01) | UT |
| AC-70 | FR-11 | Given вузли energy `is_critical` скинуто (`is_critical=False` у всіх, `sudo`) і `critical_codes` за §5.1; Then `_critical_kw()` рахує за параметром (запасний шлях R-04 п. 2), `items` — назви обладнання за кодом; Given знову 10 критичних вузлів; Then — за вузлами (п. 1). При обох шляхах `PayloadBuilder.build()` не змінює `infra.totals.critical_kw`, записаний провайдером `infra` energy (міст не пише ключ, X-11) | UT |
| AC-71 | FR-17 | Given `__manifest__.py` моста; Then `depends == ["td_genset", "factory3d_base", "factory3d_telemetry", "factory3d_energy"]` (без `factory3d_viewer`, `bus`); `models/viewer_provider.py` не містить `_inherit` (grep-тест), `"f3d.viewer.provider"` не входить у `type(env["f3d.viewer.provider.genset"])._inherit`. Given база **без** `factory3d_viewer` (§13.0 прогін 2); When `-i factory3d_genset`, хук, `_cron_publish` зі зміною стану 1 → 7, `_cron_events` з подією `bus_only`; Then установка без помилок, 26 показань, `last_state_json.state=7`, повідомлення «Стан: …» у чаттері, винятків немає, `"f3d.viewer.event" not in env` | UT |
| AC-72 | FR-07, FR-17 | Given `patch={"infra": {"cards": {"PV-INV": {"rows": [["Стан", "усі в мережі"]]}}, "totals": {"pv_now": 468, "chp_kw": 400, "critical_kw": 348}}}` і `ctx.changes={"f3d.signal": {"infra/genset/GENSET/state"}}`; When `_f3d_viewer_delta(patch, ctx)`; Then `patch.infra.cards` має `PV-INV` (незмінна) і `GENSET`; `patch.infra.totals` зберіг `pv_now=468`, `chp_kw=400`, `critical_kw=348` і отримав `genset_kw`, `island`, `grid_ok`, `genset_kva=634` (R-13, X-23); When `ctx.changes={"f3d.signal": {"infra/ats/position"}}`; Then те саме злиття; When `ctx.changes={"f3d.signal": {"energy/totals/p_now"}}`; Then `patch` не змінився | UT |
| AC-73 | FR-09, FR-15 | Given модуль установлено; Then `menu_f3d_genset_settings`: `parent_id` = `factory3d_base.menu_f3d_config`, `sequence=55`, `group_ids` = `factory3d_base.group_f3d_admin`, дія `action_f3d_genset_settings` (`res_model='res.config.settings'`, `target='inline'`, `context.module='factory3d_genset'`); When адміністратор у налаштуваннях ставить `f3d_genset_ats_position_i_value=1`, `f3d_genset_ats_position_ii_value=4` і `execute()`; Then `factory3d.genset.ats_position_i_value='1'`, `…_ii_value='4'`, R-05 з `pos=4` свіжим → `island=True`, з `pos=3` → не острів; When обидва значення 3; Then `ValidationError` «Значення положень I і II АВР мають відрізнятися.», параметри не змінені; When `f3d_genset_offline_min=10`; Then `period_s=200` у 26 сигналах GENSET (T-6, як AC-62) (X-69) | UT |

Частина A, продовження — регресія `td_genset` на 19.0 (CR-09). Позначення «ТР 1.2 AC-xx» — acceptance criteria SPEC `td_genset`
v1.2 (AC-01…AC-69); їхній зміст тут не повторюється й не вигадується: матриця `docs/REGRESSION_19.md` (репозиторій `td_genset`)
зв'язує кожен з тестом/ТК ТР 1.2. У цьому документі номери AC `td_genset` завжди пишемо з префіксом «ТР 1.2», щоб не плутати з
AC-01…AC-73 моста.

| AC | FR | Given / When / Then | Тип |
|---|---|---|---|
| AC-A09 | FR-A02, FR-A03 | Given `docs/REGRESSION_19.md` з 69 рядками (ТР 1.2 AC-01…AC-69); When прогін §13.2 на 19.0; Then кожен рядок має результат 19.0 «зелено» або «змінено (MG-xx)» з посиланням на запис `docs/MIGRATION_19.md`, погоджений менеджером; 0 рядків «червоно», 0 рядків без результату | REG |
| AC-A10 | FR-A01 | When команди колонки «Що перевірити» для MG-02, MG-04, MG-05, MG-06, MG-09, MG-10, MG-11, MG-12, MG-13, MG-20 (скрипт `tools/mg_check.sh` репозиторію `td_genset`, вивід — у `MIGRATION_19.md`); Then 0 заборонених входжень для кожного MG; для MG-06, MG-07, MG-20, MG-21, MG-23 у `MIGRATION_19.md` є запис «підтверджено/спростовано» з посиланням на файл Odoo 19 | REG |
| AC-A11 | FR-A02 | Given дві бази: порожня `--without-demo=all` і копія демо-бази timur-o19demo (MG-16); When `--test-tags /td_genset` на кожній; Then на обох 176/176 OK; базовий прогін тега `18.0.2.0.2` на Odoo 18 записано в `REGRESSION_19.md` (OK/FAIL до переносу); жоден тест не звертається в мережу (MG-29) | REG |
| AC-A12 | FR-A03 | Given стенд `td_genset` + `fake_relay` `d700`; When `POST /sim/v1/fault {"alarm":"comm_lost"}` на 10 хв, потім `clear`; Then усі крони `td_genset` `active=True`, `ir.cron.failure_count=0`, у лозі Odoo немає traceback крона опитування (MG-11); після `clear` показання оновлюються не пізніше 2 періодів опитування (Q-15) | REG/TC |
| AC-A13 | FR-A03 | Given стенд; When `POST /sim/v1/fault {"alarm":"low_oil_pressure"}` під навантаженням; Then ескалація тривоги `td_genset` проходить так, як вимагають ТР 1.2 AC ескалації (номери — з матриці, ЗВІРИТИ), без помилок `mail` у лозі (MG-17); пульт показує тривогу без перезавантаження сторінки (MG-24); push-ендпоінти ретранслятора, якщо є, відповідають 200 (MG-12) | REG/TC |
| AC-A14 | FR-A01, FR-A04 | Given менеджер `td_genset`; When відкрити кожен пункт меню `td_genset` (list, kanban, form, пульт) з `?debug=assets`; Then кожне представлення рендериться, консоль без помилок OWL; `ir.ui.view` модуля без `type='tree'` (MG-04, MG-06, MG-21, MG-22) | REG/MAN |
| AC-A15 | FR-A05, FR-A07 | Given користувач без груп `td_genset`; When JSON-RPC `call_kw` на методи команд пульта і на методи з `@api.private` (MG-14); Then помилка доступу; Given стоп-кран команд `td_genset` вимкнено (ім'я — ЗВІРИТИ, Q-16); When «Старт» на пульті; Then у журналі `GET /sim/v1/events` немає `command`, користувач бачить повідомлення ТР 1.2 | REG/TC |
| AC-A16 | FR-A07 | Given копія проду після оновлення платформи до 19 (§13.6 етап 2, Q-24); When `psql -f neutralize.sql` `td_genset`, потім моста; Then 0 помилок SQL, preflight повідомляє версію сервера `19.0`, крони обох модулів `active=false`, адреса ретранслятора — не прод (MG-30) | REG/TC |

Покриття FR: FR-01 — AC-01…03; FR-02 — AC-04…06, 42, 51; FR-03 — AC-07…10, 51…54, 62, 69; FR-04 — AC-11, 63; FR-05 — AC-12…17, 52, 55,
61, 63; FR-06 — AC-18…21, 64; FR-07 — AC-22…26, 52, 66, 72; FR-08 — AC-27, 28, 53…55; FR-09 — AC-29, 30, 56, 73; FR-10 — AC-31, 38, 57;
FR-11 — AC-32, 70; FR-12 — AC-33, 34, 58…60, 67; FR-13 — AC-35, 67; FR-14 — AC-36…39, 68; FR-15 — AC-40, 73; FR-16 — AC-41, 61; FR-17 — AC-26, 71, 72;
FR-A01 — AC-A01, A10, A14; FR-A02 — AC-A02, A09, A11; FR-A03 — AC-A03, A09, A12, A13; FR-A04 — AC-A04, A14, AC-53; FR-A05 — AC-A05,
A15; FR-A06 — AC-A06, AC-47…49, 68; FR-A07 — AC-A07, A15, A16; FR-A08 — AC-A08. Блекаут: варіант A (HGM6120N веде AMF) — AC-37, 48,
56; варіант B (ATyS p головний) — AC-38, 57, 65; обидва — AC-29, 31 (UT, без стенда).

## 13. План тестування (для Opus)

Тестувальник (W5) пише тести з цього розділу й §12, **не читаючи код** моста й переносу. Типи: UT — `odoo.tests`
(`TransactionCase`, теги `post_install`, `-at_install`, `f3d`, `f3d_genset`); REG — регресія `td_genset` (§13.2); TC — стенд
(§13.3); MAN — ручна перевірка з протоколом у `docs/modules/td_genset/TEST_REPORT.md`. Числа очікуваних значень — з §9 і
Додатків A–D; якщо тест не збігається з документом — дефект коду, а не привід правити тест (крім помилки в документі — тоді Q-xx).

### 13.0 Фікстури

**База для UT.** Прогін 1 (основний): `odoo-bin -d f3d_genset_test --without-demo=all -i factory3d_genset,factory3d_viewer
--test-tags /factory3d_genset --stop-after-init`; залежності моста (`td_genset` 19.0, `factory3d_base`, `factory3d_telemetry`,
`factory3d_energy`) ставляться автоматично, `factory3d_viewer` — явно, бо міст від нього не залежить (X-20). Прогін 2 (без
переглядача, FR-17): `odoo-bin -d f3d_genset_noviewer --without-demo=all -i factory3d_genset --test-tags /factory3d_genset
--stop-after-init` — класи, яким потрібен viewer (`TestProvider`, тести шини й `PayloadBuilder`), у `setUpClass` роблять
`raise unittest.SkipTest("factory3d_viewer не встановлено")`, якщо `"f3d.viewer.event" not in cls.env`; `test_no_viewer.py` — навпаки,
виконується лише без viewer. Прогін 3 — на копії демо-бази timur-o19demo (`odoo` → `odoo_genset_test`) з модулями прогону 1.

**`tests/common.py` — `class GensetCase(F3DCase)`** (`from odoo.addons.factory3d_base.tests.common import F3DCase`):

| Фікстура | Що створює / робить | Значення |
|---|---|---|
| користувачі | з `F3DCase`: `user_reader` (`group_f3d_user`), `user_manager` (`group_f3d_manager`), `user_admin` (`group_f3d_admin`); додатково `user_nobody` (лише `base.group_user`), `user_mech` (`base.group_user` + `maintenance.group_equipment_manager`) | логіни `genset_nobody`, `genset_mech` |
| `cls.team` | `maintenance.team` `name="Служба головного механіка"` (пошук, інакше створити) | на демо — id 2 |
| `cls.passport` | `f3d.equipment.passport` `role="genset"` (пошук, інакше `{"role": "genset", "manufacturer": "KOHLER-SDMO", "model": "D700"}`) | — |
| `cls.passport_comp` | те саме для `role="compressor"` (`Atlas Copco`, `GA 37 VSD+`) | для AC-03 |
| `cls.eq` | `maintenance.equipment` з `f3d_code="GENSET"` (пошук, інакше `{"name": "Дизель-генератор", "serial_no": "GENSET", "f3d_code": "GENSET", "f3d_passport_id": passport, "maintenance_team_id": team}`) | на демо — id 65 |
| `cls.eq_nocode`, `cls.eq_comp` | обладнання без `f3d_code` з паспортом genset; обладнання `f3d_code="COMP-T"` з `passport_comp` | AC-03 |
| `cls.profile` | `env.ref("factory3d_genset.profile_d700")` | Додаток C |
| `cls.td_gen` | заміна генератора `td_genset`: `res.partner` `{"name": "Генератор td_genset (тест)"}`; `GENSET_MODEL` мока = `"res.partner"` | Reference `td_genset_ref = "res.partner,<id>"` |
| `self.td` (у `setUp`) | `unittest.mock.patch.multiple("odoo.addons.factory3d_genset.adapters.td_genset", GENSET_MODEL="res.partner", STATE_MAP=…, MODE_MAP=…, BREAKER_MAP=…, SERVICE_REQUESTS_BY_TD=False, generators=MagicMock(return_value=td_gen), snapshot=MagicMock(side_effect=lambda g: self.snap_value), events_since=MagicMock(side_effect=self._events), service_info=MagicMock(return_value=SERVICE_DEFAULT), schedule_info=MagicMock(return_value={"enabled": True, "windows": ["Пн–Пт 08:45–18:45"], "timer_vs_schedule": None}), last_test=MagicMock(return_value={"ts": datetime(2026,10,12,4,30), "duration_min": 15, "result": "норма"}), open_action=MagicMock(return_value={"type": "ir.actions.act_window"}), set_fuel_rate=MagicMock(return_value=True))`; `self.addCleanup(patcher.stop)` | вимога до коду — §2.0.3 «Тестованість» |
| `STATE_MAP` / `MODE_MAP` / `BREAKER_MAP` (мок) | `{"standby":1, "mains abnormal":2, "starting":3, "safety on":4, "warming":5, "running":6, "cooling":8, "stopping":9, "alarm":10}` / `{"stop":0, "manual":1, "auto":2, "test":3}` / `{"none":0, "mains":1, "generator":2}` | R-03 |
| `self.snap(**over)` | `self.snap_value = {**SNAP_LOADED, **over}`; `SNAP_LOADED = {"ts": now, "online": True, "state_raw": "running", "mode_raw": "auto", "mains_ok": False, "breaker_raw": "generator", "p_kw": 348.0, "u_v": 400.2, "f_hz": 50.0, "i_a": 628.0, "pf": 0.8, "kwh": 61255.3, "fuel_pct": 82.0, "fuel_l": None, "hours": 1213.0, "starts": 185, "coolant_c": 84.1, "oil_bar": 4.4, "batt_v": 25.3, "charger_v": 27.6, "rpm": 1502, "alarms": [], "mains_u_v": 0.0, "mains_f_hz": 0.0}`; `SNAP_STANDBY` = те саме з `state_raw="standby"`, `breaker_raw="mains"`, `mains_ok=True`, `p_kw=0.0`, `rpm=0`, `oil_bar=0.0` | значення API-F-01 |
| `self.ev(id, name, severity, code="", value=None, unit=None, threshold=None, text="", ts=None)` | додає подію в список, який повертає мок `events_since` (лише `ts > since`, сортування `ts, id`, ліміт) | ADP-04 |
| `SERVICE_DEFAULT` | `{"hours_now": 1213.0, "interval_h": 250.0, "next_service_hours": 1250.0, "last_service_hours": 1000.0, "last_service_date": date(2026,3,2), "due": False, "hours_left": 37.0}` | AC-18 |
| `self.link` | `f3d.genset.link` `{"equipment_id": eq, "td_genset_ref": "res.partner,%d", "profile_id": profile}` + `adapters.telemetry.ensure_source/ensure_signals` (через хук або напряму) | 26 сигналів |
| `self.make_critical(drop=None, override=None)` | 10 сигналів критичних споживачів R-04: для кожного з 10 вузлів energy `is_critical` (energy AC-04; коди `energy/consumers/<code>/p_now`, `energy/lines/BW-1/p_now`) — наявний `f3d.signal` energy за кодом, інакше створити (`kind="gauge"`, `unit="кВт"`, без джерела); `last_value` через `set_sql` = `CRITICAL_VALUES` = LP-1 12, LP-2 10, LP-3 8, DUST-1 75, COMPRESSOR 37, BOILER 6, OFFICE 25, EF-ELEC 15, EF-CHG 60, BW-1 100 (Σ 348, синтетично); `drop` — код, сигнал якого архівувати (`active=False`); `override` — заміна значень; обладнання вузла LP-1 — «Щит освітлення LP-1» | AC-22, AC-32: `drop="energy/lines/BW-1/p_now", override={"EF-CHG": 160.0}`; AC-70 — те саме + `is_critical=False` на всіх вузлах |
| `self.make_ats(position, src1, age_s=0, period_s=10)` | 3 сигнали `infra/ats/position`, `src1_ok`, `src2_ok` (обладнання `ATS-1`) і показання через `_f3d_ingest` з `ts = now − age_s` | R-05 |
| `self.payload(user, **kw)` | `PayloadBuilder(self.env(user=user), **kw).build()` (`odoo.addons.factory3d_viewer.tools.payload`; імпорт усередині хелпера — лише прогони з viewer) | viewer §13.0 |
| `self.flush_notify()` | `self.env.cr.precommit.run()` — `f3d.viewer.event._notify` пише події на precommit (viewer M-03) | події шини в UT |
| `self.bus` | `patch.object(type(self.env["bus.bus"]), "_sendone")` → список викликів | AC-27, AC-28 |
| годинник | `freezegun.freeze_time("2026-10-12 07:30:00")` (UTC = 10:30 Київ) у `setUp`; зсуви — `frozen.tick(timedelta(...))` | R-12, R-09 |
| параметри | `self.set_param(key, value)` = `ir.config_parameter.sudo().set_param`; умовчання тесту: `read_enabled=True`, `requests_enabled=True`, `offline_min=5` | §5.1 |

Без мережі: жоден UT не звертається до ретранслятора чи `fake_relay` (адаптер замоканий); `test_adapter_contract.py` — єдиний
файл без мока адаптера.

### 13.1 Юніт-тести моста (на кожен AC типу UT)

| Файл | Клас | Тест | Фікстури | Що саме assert | AC |
|---|---|---|---|---|---|
| `test_hooks.py` | `TestHook` | `test_hook_single_generator` | `generators` → `td_gen` | після `hooks.post_init_hook(env)`: 1 зв'язка для `eq`, `profile_id == profile`, `source_id.code == "GENSET-RELAY"`, `source_id.type == "td_genset"`, `json.loads(param("migration_report"))["link"]["created"] == 1`; 26 сигналів `infra/genset/GENSET/%`; 48 рядків мапи; 3 крони модуля | AC-01, AC-62 |
| | | `test_hook_two_generators` | `generators` → 2 записи | 0 зв'язок; `report["link"] == "skipped: кілька генераторів — зв'яжіть вручну"` | AC-02 |
| | | `test_hook_adapter_not_verified`, `test_hook_no_equipment` | `generators.side_effect = NotImplementedError("ADP-02: звірити з td_genset")`; `eq.f3d_code="GENSET-X"` | `report["link"]` = «skipped: ADP-01 не звірено» / «skipped: немає обладнання з f3d_code=GENSET»; винятку немає | §11 п. 2, 4 |
| | | `test_hook_prod_env` | `factory3d.base.environment="prod"`, потім `"test"` | `read_enabled` = `"False"` і `cron_f3d_genset_publish.active is False`; для `test` — `"True"`/`True` | AC-09 |
| | | `test_hook_idempotent` | два виклики хука; `td_code="LOP_SD"` у рядку `LOW_OIL_PRESSURE_SD` між ними | кількості після другого = після першого (1/1/26/48/3); `td_code` збережено | AC-50 |
| | | `test_hook_meter_untouched`, `test_service_nextcall` | — | `eq.f3d_meter_signal_id` порожнє, `report["meter"] == "skipped: A-04"`; `nextcall` крона service у Києві = 06:00 наступного дня | AC-20, §5.3 |
| | `TestLocalSource` | `test_local_type_hook`, `test_source_without_collector`, `test_other_type_needs_collector` | хук | AC-69: `_f3d_local_types()` містить `td_genset`; `GENSET-RELAY` (`is_local`, без `collector_id`, `params={}`); друге джерело `td_genset` без колектора — ок; `modbus_tcp` без колектора → `ValidationError` «…вкажіть колектор.» | AC-69 |
| | `TestNeutralizeUninstall` | `test_neutralize_sql` | `cr.execute(file_open("factory3d_genset/neutralize.sql").read())` | 3 крони `active=False`; `read_enabled`, `requests_enabled` = `"False"`; `link.last_publish_ts` порожнє, `last_event_id == 0` | AC-35 |
| | | `test_uninstall_hook` | 1 заявка GENSET; `hooks.uninstall_hook(env)` | `ir.config_parameter` `factory3d.genset.%` — 0; джерело `active=False`; 26 сигналів і заявка на місці | AC-35 |
| `test_rules.py` | `TestLinkConstraints` | `test_unique_equipment`, `test_bad_equipment` | `eq`, `eq_nocode`, `eq_comp` | друга зв'язка на `eq` → `ValidationError`/`IntegrityError` з «Для цього обладнання зв'язка вже існує.»; `eq_nocode` → текст «…не має коду сцени…»; `eq_comp` → «Паспорт обладнання має роль «compressor», потрібна «genset».» | AC-02, AC-03 |
| | `TestFuel` | `test_fuel_curve` (параметризований), `test_autonomy`, `test_curve_monotonic` | `profile` | `fuel_lph(x)` для x ∈ {0, 25, 50, 68.6, 75, 100, 105, 110, 150} = 38.6, 38.6, 71.2, 95.5, 103.8, 136.4, 143.0, 149.5, 149.5; `autonomy_h` (500,75)=4.8, (500,68.6)=5.2, (610,75)=5.9, (610,100)=4.5, (0,75)=0.0; мок `fuel_lph→0` → `None`; `fuel_lph_50=30` → `ValidationError` «Крива витрати має бути неспадною.»; `tank_l=0` → `ValidationError` | AC-04, AC-05, AC-06 |
| | `TestCodes` | `test_state_by_breaker_or_power`, `test_load_and_fuel_l`, `test_unknown_state` | `snap()` | AC-65; `load_pct` 348 → 68.6, 507 → 100.0, 0 → 0.0; `fuel_l` з `fuel_pct=82` → 500.2 | AC-65, R-03 |
| | `TestIsland` | `test_ats_priority`, `test_ats_stale_fallback_hgm`, `test_offline_last_known`, `test_amf_master_no_effect` | `make_ats(3,0)`, `make_ats(2,1)`, `make_ats(3,0, age_s=31)`, `snap(online=False)`; параметри `ats_position_*_value` = 2/3 | AC-29 чотири випадки (`island`, `grid_ok`, `source`); при `amf_master="ats"` ті самі результати | AC-29, AC-31 |
| | `TestCritical` | `test_sum_and_missing`, `test_fallback_param`, `test_totals_untouched` | `make_critical(drop=BW-1, override={"EF-CHG": 160})`; потім `is_critical=False` на всіх вузлах energy; payload з тоталами energy | `_critical_kw()[:2] == (348.0, ["energy/lines/BW-1/p_now"])`, 9 назв; параметр `critical_codes` з одним кодом ігнорується, поки є вузли `is_critical`; без них — сума за параметром (запасний шлях); `infra.totals.critical_kw` після `build()` = значення energy (міст не пише) | AC-32, AC-70 |
| | `TestProfileExport` | `test_export_json`, `test_apply_to_td` | `user_manager` | вкладення `d700.json` (`mimetype="application/json"`), `json.loads` має ключі `profile, rated, tank_l, fuel_lph, timers, timers_plant, sensors, alarms, start`, `fuel_lph["75"] == 103.8`, `timers["mains_abnormal_s"] == 5`, `timers["crank_fire_s"] == 3`; `action_apply_to_td` → `set_fuel_rate` викликано з `(td_gen, 103.8)`, повідомлення містить «Записано в td_genset: 1» і «пропущено (крива/поля немає): 0» | AC-42 |
| `test_publish.py` | `TestPublish` | `test_publish_values` | `link`, `snap()` | після `_cron_publish()`: 26 `f3d.reading` з `ts == snap.ts`; `last_value`: `state` 7, `p_kw` 348.0, `load_pct` 68.6, `fuel_l` 500.2, `fuel_lph` 95.5, `autonomy_h` 5.2, `hours` 1213.0, `online` 1; `last_publish_ts` заповнено, `last_publish_error is False` | AC-07 |
| | | `test_stop_crane` | `read_enabled="False"` | 0 нових `f3d.reading`; `action_check()` від `user_manager` → `UserError` з текстом AC-08 | AC-08 |
| | | `test_idempotent_same_ts` | той самий `snap()` двічі | `f3d.reading` = 26; другий `adapters.telemetry.ingest` повертає `skipped == 26` | AC-10 |
| | | `test_signals_appendix_a`, `test_alarm_level_status`, `test_offline_min_changes_period` | хук | поля 26 сигналів = Додаток A і §2.0.3 T-4/T-6; `alarm_level=2` → `status="alarm"`, `maintenance_request_id` порожнє; `offline_min=10` через `res.config.settings` → `period_s == 200` | AC-11, AC-62 |
| | | `test_state_change_bus_and_chatter`, `test_online_only` | `last_state_json={"state":1,…}`, `snap()`; потім `snap(online=False)` з `tick(6 хв)` | 1 `f3d.viewer.event` (`model="maintenance.equipment"`, `codes=["GENSET"]`, `kind="state"`) після `flush_notify()` і 1 повідомлення «Стан: …» у чаттері; повтор того самого стану — подій не додається; лише `online` 1→0 — подія є, нового повідомлення «Стан:» немає | AC-27, AC-28 |
| | | `test_offline_stale`, `test_comm_lost_once` | `snap(ts=now−7 хв, online=True)`; три прогони з `tick(1 хв)` | `online=0`, `state=0` (`status="ok"`), 22 сигнали `status="stale"`; рівно 1 заявка `GENSET:COMM_LOST`, назва містить «втрачено зв'язок з контролером»; `snap()` свіжий → у заявці «Зв'язок відновлено о …», заявка відкрита | AC-40, AC-25 |
| | | `test_clock_ahead` | `snap(ts=now+300 с)` | показання з `ts == now`; `last_publish_error` містить «годинник ретранслятора попереду» | AC-46 |
| | | `test_adapter_not_verified`, `test_cron_isolation` | `snapshot.side_effect=NotImplementedError("ADP-03: звірити з td_genset")`; друга зв'язка (другий `eq` `GENSET-2`) з робочим `snap` | `last_publish_error` = «NotImplementedError: ADP-03: звірити з td_genset»; друга зв'язка опублікована; `_cron_publish` не кидає | §11 п. 2, MG-11 |
| `test_events.py` | `TestEvents` | `test_shutdown_request` | `ev(1,"Low Oil Pressure","shutdown","LOP_SD",0.8,"бар",1.0)` | 1 `maintenance.request` з полями AC-12 (`name == "Генератор GENSET: аварійна зупинка — низький тиск оливи 0,8 бар при нормі ≥ 1,0 бар"`, `priority="3"`, `maintenance_team_id == team`, `f3d_equipment_code == "GENSET"`, `f3d_signal_id.code` закінчується `/alarm_level`, `f3d_value == 0.8`, `f3d_threshold == 1.0`, `f3d_genset_event_key == "GENSET:LOW_OIL_PRESSURE_SD"`) | AC-12 |
| | | `test_repeat_and_reopen` | та сама подія з `id=2`; заявку в стадію `done=True`; подія `id=3` | 1 заявка + повідомлення «Повтор: …»; після закриття — 2 заявки | AC-13 |
| | | `test_bus_only`, `test_default_shutdown`, `test_requests_disabled`, `test_batch_200` | `ev(…,"Genset Over Current","warning")`; `ev(…,"Щось нове","shutdown")`; `requests_enabled="False"`; 250 подій | AC-14 (0 заявок, подія шини), AC-15 (назва «Генератор GENSET: аварійна зупинка — Щось нове»), AC-16 (`last_event_ts` незмінний), AC-17 (200, потім 50; `last_event_id` = id 200-ї) | AC-14…AC-17 |
| | | `test_map_data`, `test_match_severity`, `test_command_ignored` | data | AC-63 | AC-63 |
| | | `test_template_validation`, `test_injection_event` | `user_manager` | AC-61 | AC-61 |
| | | `test_close_request_status` | заявка з AC-12; `snap(alarms=[{"severity":"shutdown",…}])` → закриття; потім `snap()` без тривог | після закриття при тривозі сигнал `alarm_level` `status="alarm"`; після знімка з 0 — `ok`; у чаттері зв'язки «Заявку … закрито» | R-08, AC-55 (UT) |
| `test_service.py` | `TestService` | `test_planned_request`, `test_overdue_and_not_due`, `test_td_creates_requests`, `test_service_event` | `SERVICE_DEFAULT`; показання `hours` 1177 на `now − 29 д 23 год`; `hours_left=-12`; `hours_left=120`; `SERVICE_REQUESTS_BY_TD=True` + відкрита `preventive` заявка GENSET без `f3d_signal_id`; дві події «Maintenance Due Warning» | AC-18 (назва, `priority="1"`, `schedule_date` = now + 30,8 д ± 1 д, ключ `GENSET:SERVICE:1250`, повтор — 1 заявка), AC-19, AC-21 (`f3d_signal_id` = `hours`, нових 0), AC-64 | AC-18, AC-19, AC-21, AC-64 |
| `test_provider.py` | `TestProvider` | `test_card_rows` | `link`, `snap()`, `_cron_publish`, `make_critical()` | `payload(user_reader)["infra"]["cards"]["GENSET"]["rows"]` — 14 пар `[назва, значення]` R-10 у порядку таблиці (рядки 1, 2, 6, 7, 8 — точні тексти AC-22), `items` — 10, `note` — стала; `infra.genset.GENSET`: `p_kw == 348.0`, `fuel_pct == 0.82`, `state == 7`, `state_label == "під навантаженням"`; `infra.totals`: `genset_kw == 348.0`, `genset_kva == 634` (`int`), `island is True`, `grid_ok is False` | AC-22, AC-30 |
| | | `test_order`, `test_no_link_static`, `test_stale_card`, `test_delta`, `test_delta_deep_merge` | — / без зв'язки / R-12 / `ctx.changes` / `patch` з ключами energy | AC-23 (`_f3d_sequence == 155`, індекс у списку провайдерів більший за `…infra` і `…telemetry`), AC-24 (картка = `model_static.json`), AC-25 (рядок «Зв'язок: втрачено з 10:2x», `warn`), AC-26 (умова R-13 п. 1), AC-72 (ключі energy в `patch.infra` збережені, ключі моста додані; `deep_merge` — з viewer) | AC-23…AC-26, AC-72 |
| | | `test_amf_row`, `test_critical_items`, `test_rounding`, `test_perf`, `test_nobody` | `amf_master="ats"`; `make_critical(drop=…)`; `snap(p_kw=348.04, oil_bar=4.456, hours=1213.2)` | рядок «Логіка AMF: ATyS p (головний)»; `critical_missing`; значення AC-45; AC-66 (`assertQueryCount`, `time.perf_counter`); AC-59 (немає `infra.genset`) | AC-31, AC-32, AC-45, AC-66, AC-59 |
| `test_access.py` | `TestAccess` | `test_acl_reader_manager`, `test_params_admin_only` | користувачі | `user_reader`: `write` зв'язки/профілю/мапи → `AccessError`; `user_manager` — ок; `ir.config_parameter` від `user_manager` → `AccessError` | AC-33 |
| | | `test_no_commands_runtime` | `write_enabled="True"`, шпигуни адаптера | AC-58 | AC-58 |
| | | `test_nobody`, `test_actions_manager_only` | `user_nobody`, `user_reader`, `user_manager` | AC-59, AC-60 | AC-59, AC-60 |
| `test_no_viewer.py` | `TestWithoutViewer` (лише прогін 2 §13.0; інакше `SkipTest`) | `test_install_publish_events` | `link`, `snap()`, `ev(…,"Genset Over Current","warning")` | AC-71: `"f3d.viewer.event" not in env`; хук → 1/1/26/48/3; `_cron_publish` зі зміною стану 1 → 7 — 26 показань, повідомлення «Стан: …», винятків немає; `_cron_events` з `bus_only` — 0 заявок, винятків немає | AC-71 |
| `test_adapter_contract.py` | `TestAdapterContract` (без моків) | `test_constants_filled`, `test_fields_exist`, `test_maps_complete`, `test_telemetry_contract` | реальні `td_genset` і telemetry | AC-43: жодна константа ADP не `None` (інакше `fail` з переліком ADP-xx); кожне `FIELD_*` ∈ `env[model]._fields`; AC-44: кожне значення селекцій стану/режиму/вимикача `td_genset` (`fields_get`) у нижньому регістрі ∈ `STATE_MAP`/`MODE_MAP`/`BREAKER_MAP`; telemetry: `hasattr(env["f3d.signal"], "_f3d_ingest")`, `"_mark_stale"`, поля `create_request`, `alarm_high_on`, `store_period_s`, `module`; `"td_genset" in env["f3d.source"]._f3d_local_types()` і `validate_params("td_genset", {}, local_types) == []` (CT-12, R-26; X-01) | AC-43, AC-44, AC-69, §2.0.3 |
| `test_views.py` | `TestViews` | `test_views_load`, `test_menus`, `test_settings_readonly`, `test_actions_view_mode`, `test_settings_menu_and_ats_values` | — | V-01…V-09: `env.ref(xml_id)` існує, `get_views` без помилки; меню §3 (батько, `sequence`, `group_ids`); у V-07 `f3d_genset_write_enabled` з `readonly="1"`; жодна дія модуля не має `tree` у `view_mode`; `menu_f3d_genset_settings` під `factory3d_base.menu_f3d_config` з `sequence=55`; `res.config.settings` зі значеннями 1/4 → параметри `'1'`/`'4'` і `link._island_state_from_signals(…)` з `pos=4` → `island is True`; 3/3 → `ValidationError` (X-69) | AC-33, AC-58, AC-73 |
| `test_static.py` | `TestStatic` (читає файли модуля через `odoo.modules.get_module_path`) | `test_no_commands_grep`, `test_ukrainian_strings`, `test_no_i18n`, `test_no_x_fields`, `test_no_deprecated`, `test_adapter_import_style`, `test_manifest_depends`, `test_provider_no_inherit`, `test_source_no_collector_override` | — | AC-34 (жоден `models/*.py`, `adapters/*.py` не містить `.action_start`, `.action_stop`, `command`-викликів на `GENSET_MODEL`, `write(`/`create(` на моделях `td_genset` поза ADP-09); AC-41 (усі `string=`, `help=`, тексти `UserError/ValidationError/AccessError`, назви меню й кронів містять `[А-Яа-яІіЇїЄєҐґ]`; теки `i18n/` немає); `grep -rn "x_[a-z]" models/ views/ data/` порожньо; 0 входжень `odoo.osv`, `<tree`, `_sql_constraints`, `name_get`, `read_group(`, `self._cr`; немає `from ..adapters.td_genset import` (§2.0.3); `__manifest__.py` `depends` = 4 модулі AC-71 (без `factory3d_viewer`, `bus`); `models/viewer_provider.py` без `_inherit` і без імпорту `factory3d_viewer` на рівні модуля; `models/f3d_source.py` без `collector_id` і `_check_f3d_collector_required` (X-01) | AC-34, AC-41, AC-69, AC-71, §14 |

### 13.2 Регресія `td_genset` на Odoo 19 (176 UT + 45 ТК, ТР 1.2 AC-01…AC-69)

Тестувальник ганяє тести й ТК `td_genset` **як є** (з гілки `19.0` після W1) і порівнює з базовою лінією 18.0; код переносу не
читає. Зміна тесту дозволена лише там, де `docs/MIGRATION_19.md` прямо називає MG-xx (наприклад, `groups_id` → `group_ids` у фікстурі);
кожна така зміна — окремий рядок «змінено (MG-xx)» у матриці.

**13.2.1 Середовища.**

| Код | База | Odoo | Призначення |
|---|---|---|---|
| R0 | копія тестової бази `td_genset` 18.0 (стенд `td_genset`) | 18.0, тег `18.0.2.0.2` | базова лінія: скільки з 176 UT і 45 ТК зелені до переносу |
| R1 | порожня `td19_empty`, `--without-demo=all` | 19.0 (образ `odoo:19`, MG-31) | 176 UT (MG-16: без демо) |
| R2 | копія демо-бази timur-o19demo → `td19_demo` | 19.0 | 176 UT поруч з модулями factory3d |
| R3 | стенд `td_genset` (власний compose) + `fake_relay` | 19.0 | 45 ТК: профіль `office`, потім `d700` |
| R4 | копія проду після оновлення платформи 18 → 19 (§13.6 етап 2) | 19.0 | `-u td_genset`, групи (AC-A05), `neutralize.sql` (AC-A16), вибіркові ТК пульта |

**13.2.2 Прогін 176 UT** (R0, R1, R2): `odoo-bin -d <db> -i td_genset --test-enable --test-tags /td_genset --stop-after-init
--log-level=test 2>&1 | tee reg_<db>.log`. Підсумок — рядки `odoo.tests.result: … tests` і `0 failed, 0 error(s)`; список
впалих — `grep -E "^(FAIL|ERROR):" reg_<db>.log`; попередження — `grep -c "DeprecationWarning.*td_genset" reg_<db>.log` (має
бути 0, AC-A02). JS-тести HOOT і тури (MG-23) входять у той самий прогін тегом `/td_genset`; якщо W1 виніс їх у окремий тег — він
зазначений у `MIGRATION_19.md` і запускається так само.

**13.2.3 Прогін 45 ТК** (R3): `docker compose up -d` стенда `td_genset` з `RELAY_PROFILE=office` → ТК-01…ТК-14 ТР 1.2 (45 сценаріїв)
за їхніми процедурами; потім `RELAY_PROFILE=d700`, `docker compose up -d --force-recreate fake_relay` → ті самі 45. Для D700
очікувані числа беруться з профілю (бак 610 л, витрата за R-01, таймери Додатка D); логіка (стани, події, ескалація, пульт) — та
сама, що з `office`. Протокол кожного ТК: дата, профіль, результат, посилання на скриншот/лог.

**13.2.4 Матриця `docs/REGRESSION_19.md`** (репозиторій `td_genset`): 69 рядків, колонки `ТР 1.2 AC | тест/ТК ТР 1.2 | R0 | R1 | R2 |
R3 office | R3 d700 | MG-xx (якщо змінено) | коментар`. Додатково 6 рядків блоків підвищеного ризику §A.3 → AC-A12…AC-A15
(пульт, групи, крони, kanban/list, ескалація `mail`, push-ендпоінти) з позначкою MAN і протоколом.

**13.2.5 Критерій «зелено»** (усе одночасно):
1. R1 і R2: 176/176 OK, 0 failed, 0 errors, 0 `skip` з причиною версії, 0 `DeprecationWarning` від `td_genset`.
2. R3: 45/45 з `office` і 45/45 з `d700`.
3. Кожен з 69 рядків матриці — «зелено» або «змінено (MG-xx)» з погодженням менеджера; 0 «червоно».
4. Якщо в R0 тест/ТК був червоним до переносу — у матриці «червоно в 18.0 (не регресія)», окремий дефект `td_genset`, не блокує
   DoD переносу лише з письмовим рішенням менеджера.
5. AC-A10…AC-A16 зелені; MAN-блоки §A.3 мають протокол.

### 13.3 Стендові сценарії: `fake_relay` (профіль D700) + емулятор `factory3d_iot_sim`

Нумерація: **ТК-G01…ТК-G13** — стенд моста (Odoo + `fake_relay` + iot_sim), **ТК-F01…ТК-F07** — `fake_relay` окремо (pytest у
репозиторії `td_genset`). Префікси потрібні, бо ТК-01…ТК-14 — це сценарії ТР 1.2 `td_genset`, а ТК-01…ТК-16 — iot_sim (A-17).

#### 13.3.0 Стенд і загальні передумови

| Що | Значення |
|---|---|
| Odoo | тестовий сервер, база `odoo_genset_test` (копія демо-бази timur-o19demo) з `factory3d_base`, `factory3d_telemetry`, `factory3d_energy` (якщо готовий — CE-02/CE-03), `factory3d_viewer`, `factory3d_iot_sim`, `td_genset` 19.0, `factory3d_genset` |
| Контейнери | `docker compose -f services/iot_sim/docker-compose.sim.yml --profile demo up -d iot_sim mosquitto genset_relay` (+ `collector`, якщо energy читає ATyS p по Modbus) |
| `fake_relay` | `RELAY_PROFILE=d700`, `RELAY_TIME_FACTOR=1` (для ТК-G — завжди 1: мітки часу ретранслятора мають іти з реальним часом, інакше R-12 «годинник попереду»), `/sim/v1/time` у ТК-G не викликається; `RELAY_SIM_TOKEN`, `SIM_API_TOKEN` — з `.env` стенда (у документах не наводяться) |
| `td_genset` | адреса ретранслятора `http://genset_relay:8000`, токен стенда; період опитування `P_td` — з Q-15 (до відповіді приймається 60 с) |
| Параметри моста | `read_enabled=True`, `requests_enabled=True`, `offline_min=5` (ТК-G11 — 1), `publish_period_s=60`; `ats_position_i_value`/`ats_position_ii_value` = `2`/`3` — Annexe III, як на проді (iot_sim §8.9.4 за X-41; стендових винятків немає) |
| Час спостереження в Odoo | `T_obs = 60 с (крон publish) + P_td + 60 с запасу` = 180 с при `P_td=60`; для подій — `120 с (крон events) + P_td + 60 с` = 240 с |
| Обв'язка | `tests/stand/conftest.py`: клієнти `relay` (`requests`, `Authorization: Bearer $RELAY_SIM_TOKEN`), `sim` (iot_sim `/sim/v1`, `SIM_API_TOKEN`), `odoo` (XML-RPC адміністратора тестової бази; пароль — з `.env`), `viewer` (HTTP-сесія `user_reader`, `POST /f3d/viewer/data`); хелпери `wait_until(fn, timeout_s, every_s=5)`, `sig(code) -> (last_value, last_ts, status)`, `readings(code, since)`, `requests_by_key(key)`, `card() -> dict(rows)`, `relay_timeline(seconds)` — опитування `GET /sim/v1/state` раз на 1 с з записом переходів `state` |
| Оркестратор | `tests/stand/orchestrator.py` виконує послідовності §8.6 (варіанти `hgm`/`ats`), якщо iot_sim ще не має CI-01 (Q-21): викликає API-F-02/03/04 і виставляє ATyS через iot_sim `PUT /sim/v1/signals/infra/ats/<leaf> {"value": …, "hold_s": 3600}` (API-16; колектор доносить у energy). Без energy й колектора — пише `infra/ats/*` у Odoo через telemetry API-02 від тестового колектора `TEST-ATS` (джерело `http_push`, 3 сигнали) |
| Після кожного ТК | `POST /sim/v1/reset {"profile": "d700"}` (`fake_relay`), iot_sim `POST /sim/v1/reset`, відкриті заявки GENSET → стадія «Repaired» (XML-RPC), очікування `sig(".../state") == 1` |

#### 13.3.1 ТК-G (стенд моста)

| ТК | Назва | Передумови | Кроки | Очікуваний результат | Де дивитися | AC |
|---|---|---|---|---|---|---|
| ТК-G01 | Установка і перший знімок | стенд без моста; `td_genset` бачить `genset_relay` | 1) `-i factory3d_genset`; 2) Завод 3D → Генератор → Зв'язка (якщо `skipped` — створити вручну); 3) «Перевірити»; 4) 3 хв | §5.3: 1 профіль, 1 джерело, 26 сигналів, 48 рядків мапи, 3 крони; повідомлення «Знімок: стан очікування, 0 кВт, паливо 82 % (500,2 л), мотогодини 1 213…»; 26 сигналів з `last_ts` ≤ 2 хв; картка GENSET: «Паливо: 82 % · 500 л», «Автономність: ≈ 4,8 год при 75 %» | Телеметрія → Сигнали (`infra/genset/`), Переглядач → GENSET | AC-36, AC-50, AC-07 |
| ТК-G02 | Блекаут, варіант A (HGM6120N веде AMF) | `amf_master=hgm`; `relay_timeline` запущено | 1) iot_sim `POST /sim/v1/scenario/blackout/start {"params": {"duration_s": 600, "amf_master": "hgm"}}` (або оркестратор); 2) чекати `loaded`; 3) `T_obs`; 4) знімок payload; 5) `stop` сценарію; 6) чекати `standby` | `fake_relay`: `mains_abnormal` 5 с → `starting` → `safety_on` 10 с → `warming` 10 с → `running` → `loaded`, `breaker=gen`, 29–32 с від t0, `p_kw=348`, `starts` +1; Odoo: `state=7`, `breaker=2`, `mains_ok=0`, `island=True` (за ATyS, якщо CE-02 є, інакше `source='hgm'`), подія шини, AC-56 (тотали, картка «Мережа: відсутня · острів…», «≈ 5,2 год при 69 %»); повернення: `breaker=mains` через 12 ± 2 с (Mains Normal 10 + Stop Delay 1 + Transfer 1), `cooling` 10 с, `stopping` 20 с, `standby` ≈ 42 с після t_restore; Odoo `island=False` ≤ `T_obs`; заявок 0 | `relay_timeline`, Переглядач → вкладка «Енергія», GENSET, ATS-1 | AC-37, AC-48, AC-56 |
| ТК-G03 | Блекаут, варіант B (ATyS p головний), умовчання | `amf_master=ats`; таймери HGM — Table 7; ATyS — 1FT 3, 2AT 5, ODT 3, 1RT 180, 2CT 180, 2ST 30 | 1) `POST /sim/v1/scenario/blackout/start {"params": {"duration_s": 300, "amf_master": "ats"}}`; 2) `relay_timeline`; 3) після `duration_s` — повернення; 4) 7 хв спостереження | `remote_start=true` через 3 ± 1 с від t0; `running` ще через 24 ± 3 с; `gen_ok` → ATyS I → 0 (3 с) → II ≈ t0 + 35 с; «FAIL START» немає; `fake_relay` `breaker=mains`, `state=loaded` при `load_kw>0` (Додаток D.3); Odoo `state=7` (R-03 за потужністю), `island=True`, `grid_ok=False` (`source='ats'`), рядок картки «Логіка AMF: ATyS p (головний)»; повернення — AC-57 | `relay_timeline`, `/sim/v1/events` iot_sim, сигнали `infra/ats/*` | AC-38, AC-57, AC-65 |
| ТК-G04 | Варіант B: «FAIL START» | `amf_master=ats`; `fake_relay` `POST /sim/v1/reset {"profile": "d700_slow"}` (фікстура `relay/profiles/d700_slow.json` = `d700.json` з `timers.warming_s=60`) | 1) `POST /sim/v1/scenario/blackout/start {"params": {"duration_s": 180, "amf_master": "ats"}}`; 2) 2 хв | iot_sim подія «FAIL START» через 2ST 30 ± 2 с після наказу пуску (t0 + 33 с); ATyS не переходить у II; `fake_relay` доходить до `running` через ≈ 74 с від наказу (без навантаження); Odoo `island=False`, `state=6`; заявок моста 0 (тривоги контролера немає; «FAIL START» — подія iot_sim/energy) | iot_sim `/events`, «Емулятор → Події» | AC-38 |
| ТК-G05 | «Тест 3 хв» з пульта `td_genset` | `standby`, `mode=auto`, мережа є; користувач-оператор `td_genset` | 1) пульт → «Тест 3 хв»; 2) `relay_timeline` 5 хв; 3) Odoo через `T_obs` після `standby` | AC-53; журнал `GET /sim/v1/events` містить `command` від пульта; консоль браузера без помилок | пульт `td_genset`, картка GENSET «Остання перевірка» | AC-53, AC-A04 |
| ТК-G06 | Щотижневий тест `genset_test` | `standby` | 1) iot_sim `POST /sim/v1/scenario/genset_test/start {"params": {"duration_s": 900, "test_on_load": false}}`; 2) 17 хв | `remote_start` 15 хв, `breaker=mains`, ATyS `position` = I увесь час; Odoo `island=False`, `state` 6 ≥ 14 публікацій; після — `last_test` оновлено; картка «Остання перевірка: <дата> — тест 15 хв, норма» (текст результату — з `td_genset`) | Переглядач, `f3d.reading` сигналу `state` | AC-39 |
| ТК-G07 | Витрата палива D700 під навантаженням | `blackout` варіант A у `loaded`, `POST /sim/v1/fuel {"liters": 500.2}` | 1) зафіксувати `fuel_l` у `fake_relay` і Odoo; 2) 10 хв; 3) `POST /sim/v1/load {"kw": 507}`; 4) 3 хв | AC-51 (95,5 л/год; −15,9 л за 10 хв; `autonomy_h` 5,1; при 507 кВт — 136,4 л/год); `hours` +0,17 ± 0,02; `kwh` +58 ± 1 | сигнали `fuel_l`, `fuel_lph`, `autonomy_h`, картка | AC-51, AC-48 |
| ТК-G08 | Заправка і низький рівень палива | `standby` | 1) `POST /sim/v1/fuel {"liters": 140}`; 2) `T_obs` для подій; 3) заправка за інструкцією «Заправка» (дія пульта `td_genset` або `{"add_liters": 360}`); 4) `T_obs` | AC-52; після кроку 3 `td_genset` фіксує заправку так, як ТР 1.2 (REG) | Обслуговування → Заявки, картка GENSET | AC-52 |
| ТК-G09 | Робота поза графіком | розклад `td_genset` без поточного вікна; `standby` | кроки AC-54 (інструкція ARCH §4.4) | AC-54 | пульт, сигнали `mode`/`state`, чаттер зв'язки | AC-54 |
| ТК-G10 | Тривога з ескалацією | варіант A у `loaded` | 1) `POST /sim/v1/fault {"alarm": "low_oil_pressure"}`; 2) події + ескалація `td_genset`; 3) `clear`, повторний пуск, той самий `fault`; 4) закрити заявку при тривозі; 5) `clear` | AC-55; ескалація `td_genset` (пошта/активності) — як ТР 1.2 (AC-A13) | заявки, сигнал `alarm_level`, пошта/активності `td_genset` | AC-55, AC-A13 |
| ТК-G11 | Втрата зв'язку з ретранслятором | `offline_min=1`, `loaded` або `standby` | 1) `POST /sim/v1/fault {"alarm": "comm_lost"}`; 2) 4 хв; 3) `clear`; 4) `T_obs` | AC-40 (22 сигнали `stale`, `online=0`, `state=0`, заявка `GENSET:COMM_LOST`, «Зв'язок відновлено о …»); картка «Зв'язок: втрачено з HH:MM», `warn` «Зв'язок із контролером втрачено (N хв)»; крони `td_genset` і моста `active`, `failure_count=0` (AC-A12) | сигнали, заявки, «Технічні → Заплановані дії» | AC-40, AC-25, AC-A12 |
| ТК-G12 | Нейтралізація, деінсталяція, повторна установка | друга копія бази `odoo_genset_test2` з ТК-G01 | 1) `psql -f neutralize.sql` (base → `td_genset` → міст); 2) 10 хв; 3) деінсталяція моста; 4) повторна установка | після 1: крони моста й `td_genset` `active=false`, `read_enabled`/`requests_enabled`=`False`, `last_publish_ts` NULL, 0 нових показань за 10 хв, `fake_relay` не отримує запитів від Odoo; після 3: параметри `factory3d.genset.%` відсутні, 26 сигналів (з `source_id=False`) і заявки на місці, джерела `GENSET-RELAY` немає (M-04 `cascade`); після 4: кількості §5.3 без дублів сигналів | `psql`, лог `genset_relay` | AC-35, AC-50, AC-A07 |
| ТК-G13 | Контролер: «Fail to Start» | варіант A; `POST /sim/v1/fault {"alarm": "start_fail"}` | 1) `POST /sim/v1/mains {"available": false}`; 2) 2 хв; 3) `T_obs` для подій | `fake_relay`: 3 прокрутки по 8 с з паузами 10 с → `alarm_shutdown` ≈ t0 + 50 с, подія `Fail to Start` (shutdown); Odoo: 1 заявка `GENSET:FAIL_TO_START_SD`, `priority='3'`, назва «Генератор GENSET: не вдалося запустити…» (Додаток B); `alarm_level=2`; `island=False`; `warn` «Аварійна зупинка: Fail to Start» | заявки, картка | AC-49, AC-15 |

#### 13.3.2 ТК-F (`fake_relay` окремо; `relay/tests/test_sim_api.py`, pytest, контейнер з `RELAY_SIM_TOKEN=test`)

| ТК | Перевірка | Очікувано | AC |
|---|---|---|---|
| ТК-F01 | `GET /sim/v1/state` з токеном / без / з хибним; рестарт з порожнім `RELAY_SIM_TOKEN` | 200 (`profile="D700"`, `fuel_l=500.2`, `hours=1213.0`, `mode="auto"`, `state_code=1`) / 401 / 401 / 404 на всі `/sim/v1/*`; ендпоінти `relay_api.md` працюють в усіх випадках | AC-A06, AC-47 |
| ТК-F02 | валідація: `load {"kw": 600}`, `fuel {"liters": 700}`, `remote_start` у `mode=manual`, `time {"factor": 100}`, `fault {"alarm": "nope"}`; `load {"kw": 530}` 35 с | 422, 422, 409, 422, 422; після 30 с — warning «Genset Over Current» у `GET /sim/v1/events` | AC-47 |
| ТК-F03 | `mains {"available": false}` з `factor=1`; те саме після `reset {"preset": "plant"}`; повернення мережі | переходи і тривалості Додатка D.2: `loaded` за 29–32 с (умовчання) і 13–16 с (`plant`); `starts` +1; повернення до `standby` за 42 ± 3 с | AC-48 |
| ТК-F04 | `fault {"alarm": "start_fail"}` + `mains {"available": false}` | 3 прокрутки (8 с) з паузами 10 с → `alarm_shutdown` ≈ 50 с; подія `Fail to Start` `severity=shutdown`; `clear` → `standby`, лічильник спроб скинуто | AC-49 |
| ТК-F05 | `factor=60`, `loaded`, `load {"kw": 348}`, 60 с реального часу (1 год sim) | `fuel_l` −95,5 ± 2 %, `hours` +1,00 ± 0,02, `kwh` +348 ± 2 %, `coolant_c` → 85 ± 2 | AC-48 |
| ТК-F06 | 5 подій, `reset`, ще 2 події | `id` подій після `reset` > максимального до `reset`; стан = `start` профілю; `GET /sim/v1/events?since=<max_before>` повертає лише 2 нові | API-F-08, API-F-09 |
| ТК-F07 | `fault {"alarm": "comm_lost"}`; запит до ендпоінта `relay_api.md`; `clear` | 503 на `relay_api.md`, `/sim/v1/state` — 200; після `clear` — 200 | AC-40 (передумова) |

### 13.4 Тести безпеки (ТБ)

| ТБ | Перевірка | Очікувано | Де |
|---|---|---|---|
| ТБ-01 | Матриця ACL: 3 моделі моста × `read/write/create/unlink` × `user_nobody`, `user_reader`, `user_manager`, `user_admin` (UT `with_user` і XML-RPC на стенді) | точно §4.1: `nobody` — `AccessError` на все; `reader` — лише `read`; `manager`/`admin` — усе | `test_access.py`, стенд |
| ТБ-02 | RPC на публічні дії від `user_reader`: `action_check`, `action_apply_to_td`, `action_export_relay_profile`; RPC на приватні: `_publish_one`, `_cron_publish`, `_apply_event`, `_compute_values` через `/web/dataset/call_kw` | `AccessError` (AC-60); для `_…` — відмова Odoo «Private methods … cannot be called remotely» | `test_access.py`, `HttpCase` |
| ТБ-03 | Команди з моста: grep (AC-34) + рантайм-шпигун (AC-58) + стенд: за весь прогін ТК-G журнал `fake_relay` (`GET /sim/v1/events`, лог `genset_relay`) містить команди лише в ТК-G05/ТК-G09 і лише з ініціатором-користувачем пульта `td_genset` | 0 команд від моста й від кронів | `test_static.py`, `test_access.py`, лог |
| ТБ-04 | Стоп-кран команд `td_genset` (Q-16) вимкнено → кнопки пульта; нейтралізована копія → кнопки пульта | команди не доходять до `fake_relay`, повідомлення ТР 1.2 | стенд (AC-A15) |
| ТБ-05 | `fake_relay`: без токена / хибний / порожній `RELAY_SIM_TOKEN`; `docker compose port genset_relay 8000` (публікація на хост); `docker logs genset_relay` і лог Odoo за весь прогін — пошук значення токена | 401 / 401 / 404; порт не опубліковано; 0 збігів | ТК-F01, стенд |
| ТБ-06 | Ін'єкції: події з `code` `../x; DROP TABLE`, `name` `<script>…</script>`, `text` 10 КБ, `value` `NaN`/`inf`; шаблони `{name.__class__}`, `{value[0]}` | AC-61; `NaN`/`inf` → «—» у тексті, у `f3d_value` не пишеться; чаттер «Повтор: …» показує екрановане ім'я | `test_events.py` |
| ТБ-07 | `sudo()` і SQL: `grep -rn "sudo()" models/ adapters/ hooks.py`; `grep -rn "cr.execute" models/ adapters/` | `sudo()` лише: читання `ir.config_parameter`; `create` `maintenance.request` у кронах (коментар R-07); `action_check` після `has_group`; `cr.execute` у моделях і адаптерах — 0 | `test_static.py` |
| ТБ-08 | Нейтралізація (AC-35, AC-A07): після `neutralize.sql` 10 хв | крони неактивні; `fake_relay` не отримує жодного запиту від Odoo (лог); адреса ретранслятора `td_genset` не прод | ТК-G12 |
| ТБ-09 | Права після оновлення проду (MG-08, AC-A05): SQL §4.3 до/після | однакові кількості користувачів у кожній групі `td_genset` | R4 §13.2 |
| ТБ-10 | Поле `f3d_genset_write_enabled`: запис через `res.config.settings` від `user_admin`; читання коду | поле readonly у формі; значення ніде не читається (AC-58) | `test_views.py`, `test_static.py` |

### 13.5 Тести продуктивності (ТП)

| ТП | Навантаження | Критерій | Де |
|---|---|---|---|
| ТП-01 | `_publish_one` з моками; на стенді — тривалість прогону `cron_f3d_genset_publish` (лог `ir_cron` «Job done … in N s») для 1 зв'язки і для 5 синтетичних (5 обладнань `GENSET-1…5`, заміни `td_gen`) | UT ≤ 40 SQL, ≤ 0,5 с (AC-66); стенд ≤ 2 с на зв'язку, ≤ 10 с на 5 | `test_provider.py`, лог |
| ТП-02 | Провайдер genset у `PayloadBuilder.build()`; `/f3d/viewer/data` з мостом і без | ≤ 8 SQL і ≤ 50 мс приросту (AC-66); загальний бюджет viewer (≤ 1,5 с, ≤ 80 SQL, viewer §13.4) не перевищено | `test_provider.py` |
| ТП-03 | 200 подій за прогін з 200 різними назвами `severity=shutdown` (усі → `DEFAULT_SHUTDOWN`) | ≤ 10 с; 1 заявка + 199 повідомлень «Повтор» | `test_events.py::test_batch_200` |
| ТП-04 | 24 год стенда, `factor=1`, публікація 60 с | `f3d.reading` сигналів GENSET = 37 440 ± 1 % (`store_period_s=0`); приріст `pg_total_relation_size('f3d_reading')` записати в TEST_REPORT (орієнтир ≤ 5 МБ/добу); ротація telemetry видаляє старші `keep_days` | стенд, `psql` |
| ТП-05 | 30 хв `comm_lost` з `offline_min=1`; 60 прогонів з `NotImplementedError` адаптера | `ir.cron.failure_count = 0` для кронів моста; у чаттері зв'язки ≤ 2 нових повідомлення; 1 заявка `COMM_LOST` | ТК-G11, `test_publish.py` |
| ТП-06 | Тривалість 176 UT `td_genset` на R1 проти R0 | ≤ 1,5 × базової лінії 18.0; перевищення — дефект переносу з профілюванням | §13.2 |

### 13.6 DEPLOY_TEST: тестовий сервер → прод («спершу моніторинг, потім команди під наглядом людини на об'єкті»)

Файл протоколу — `docs/modules/td_genset/DEPLOY_TEST.md` (міст) і `DEPLOY_TEST.md` репозиторію `td_genset` (перенос); здає W5.
Кожен етап має умову входу, кроки, критерій виходу й відкат. Наступний етап — лише після підпису менеджера під попереднім.

| Етап | Де | Кроки | Критерій виходу | Відкат |
|---|---|---|---|---|
| 0. Підготовка | — | теги: `td_genset` `19.0.1.0.0`, `factory3d_genset` `19.0.1.0.0`; знімки: дамп проду, кількості користувачів у групах `td_genset` (SQL §4.3), список кронів `td_genset` з `active`; погоджене вікно робіт і відповідальні (Q-22, Q-24) | артефакти в протоколі | — |
| 1. Тестовий сервер | timur-o19demo, копія `odoo` → `odoo_genset_test` | 1) `-i td_genset,factory3d_genset` поверх base/telemetry/energy/viewer/iot_sim; 2) звіт хука: кількості §5.3; 3) 176 UT (R2) і UT моста; 4) ТК-G01…ТК-G13, ТК-F01…ТК-F07; 5) ТБ, ТП; 6) ТК-G12 на другій копії | AC-01…AC-72 і AC-A01…AC-A16 зелені або з відміткою «блокер X-59» (iot_sim ще не додав параметри CI-01 — Q-21) чи «блокер X-24» (viewer ще не оновив Додаток A до схеми 1.1 — Q-23), лише з рішенням менеджера | видалити копію; робоча база `odoo` не змінювалась |
| 2. Копія проду | тестовий сервер, дамп проду → `prod_copy` | 1) `neutralize.sql` `td_genset` (на 18.0); 2) оновлення платформи 18 → 19 штатною процедурою Odoo Upgrade (Enterprise; Q-24); 3) `-u td_genset` (19.0.1.0.0); 4) ТБ-09: групи до/після; 5) `-i factory3d_genset` з `factory3d.base.environment=prod` → AC-67 (моніторинг вимкнено); 6) пульт відкривається, команди заблоковані стоп-краном `td_genset`; 7) `neutralize.sql` моста (AC-A16) | групи збігаються; 0 traceback у лозі оновлення; AC-A05, AC-A16, AC-67 | видалити `prod_copy` |
| 3. Прод: моніторинг | прод-база у погоджене вікно | 1) резервна копія; 2) оновлення платформи й `-u td_genset` (як етап 2, без `neutralize`); 3) `-i factory3d_genset` (`environment=prod` → `read_enabled=False`); 4) звірка: два знімки «Перевірити» збігаються з пультом `td_genset` (стан, кВт, паливо, мотогодини) з різницею ≤ 1 період опитування; 5) `read_enabled=True`; 6) 24 год спостереження: сигнали оновлюються, `stale` лише при реальній втраті зв'язку; 7) `requests_enabled=True`; 8) 7 діб: заявки ТО відповідають подіям `td_genset`, без дублів; стоп-кран команд `td_genset` увесь етап **вимкнено** | протокол 7 діб без дефектів класу «дублі заявок», «хибний острів», «помилкові дані»; підпис головного енергетика замовника | `read_enabled=False`, `requests_enabled=False` (миттєво); за дефекту переносу — відновлення резервної копії й попередніх тегів |
| 4. Прод: команди під наглядом | генератор на об'єкті | 1) присутня відповідальна особа замовника на об'єкті (черговий електрик з допуском, Q-22) з телефонним зв'язком із оператором пульта і доступом до аварійної кнопки контролера; 2) увімкнути стоп-кран команд `td_genset` лише на час перевірки; 3) «Тест 3 хв» без навантаження (ТК-G05 на живому обладнанні): пуск, параметри в нормі, зупинка; особа на об'єкті підтверджує фактичний стан; 4) у погоджене вікно — тест під навантаженням через АВР (за регламентом замовника, Q-22); 5) повернути «Авто», стоп-кран — за рішенням замовника | протокол з підписами оператора й особи на об'єкті; картка GENSET і пульт показували ті самі стани, що й контролер | особа на об'єкті натискає аварійну кнопку / переводить контролер у «Стоп»; стоп-кран команд вимкнути; інцидент — у протокол |

Міст на етапах 3–4 команд не надсилає (A-09, AC-34); етап 4 перевіряє пульт `td_genset` на 19.0 у реальному середовищі.

### 13.7 Матриця покриття AC → перевірка

| AC | Перевірка |
|---|---|
| AC-01…AC-35, AC-41…AC-46, AC-58…AC-66, AC-69…AC-73 | UT §13.1 (файл/тест — у колонці AC таблиці §13.1; AC-71 — прогін 2 без viewer) |
| AC-36…AC-40, AC-47…AC-57, AC-68 | ТК-G01…ТК-G13, ТК-F01…ТК-F07 (§13.3, колонка AC) |
| AC-67 | MAN, §13.6 етапи 2–3 |
| AC-A01, AC-A02, AC-A09…AC-A11 | REG §13.2 (R1, R2, матриця) |
| AC-A03, AC-A12, AC-A13, AC-A15 | REG/TC §13.2 R3 + ТК-G05, ТК-G10, ТК-G11 |
| AC-A04, AC-A14 | MAN + ТК-G05 |
| AC-A05, AC-A16 | R4 §13.2, §13.6 етап 2, ТБ-09 |
| AC-A06 | ТК-F01; AC-A07 — ТК-G12; AC-A08 — MAN (рецензія документів менеджером) |

## 14. Definition of Done

Перенос `td_genset` (W1, W4, W5):
- AC-A01…AC-A16 зелені; `REGRESSION_19.md` — 69 рядків за критерієм §13.2.5; 176/176 UT на R1 і R2; 45/45 ТК з `office` і `d700`.
- `docs/MIGRATION_19.md`: кожен MG-01…MG-32 закрито з командою перевірки й результатом; пункти зі джерелом «С» — «підтверджено/спростовано».
- `relay/tests/test_sim_api.py` (ТК-F01…ТК-F07) зелений; `relay/profiles/d700.json` = експорт `f3d.genset.profile` D700 (побайтово
  після `json.dumps(sort_keys=True)`); `relay_api.md` має розділ «Емуляція» (API-F-01…API-F-09).
- `CHANGELOG.md` `19.0.1.0.0` з переліком MG-xx; `DEPLOY_TEST.md` для 19.0; `neutralize.sql` і preflight перевірені на копії проду (AC-A16).
- `docs/ADAPTER_MAP.md`: таблиця імен для ADP-01…ADP-10 (Q-10…Q-19 закриті або з рішенням менеджера).

Міст `factory3d_genset` (W0, W2, W3, W5):
- Усі UT §13.1 зелені на чистій базі (прогони 1 і 2 §13.0 — з viewer і без) і на копії демо, включно з `test_adapter_contract.py` (без
  моків — тобто константи ADP заповнені).
- ТК-G01…ТК-G13 пройдені на стенді §13.3.0, протокол у `TEST_REPORT.md` (дата, версії образів, профіль, результат, скриншоти карток).
- ТБ-01…ТБ-10, ТП-01…ТП-06 пройдені.
- Кожен AC-01…AC-73 зелений або позначений «блокер X-59» (параметри CI-01 в iot_sim) чи «блокер X-24» (схема 1.1 у viewer Додаток A) з
  письмовим рішенням менеджера (інші блокери неприпустимі; Q-20 закрито X-01 — AC-01, AC-50, AC-69 мають бути зелені).
- `ruff check` (довжина рядка 120) і XML-lint без помилок; жодного `x_`-поля; рядки UI українською, без `i18n/` (AC-41).
- `neutralize.sql` виконується без помилки (AC-35); `uninstall_hook` не видаляє бізнес-даних.
- `README.md` (залежності, параметри, «Підключити генератор» ARCH §4.1), `CHANGELOG.md` `19.0.1.0.0`, інструкції ARCH §4.1–§4.6 звірено з UI.
- Перегляд безпеки за ARCH §2.6 і §13.4 підписаний менеджером; DEPLOY_TEST етапи 0–2 пройдені до будь-яких дій на проді.
- Розбіжності з SPEC telemetry/viewer/iot_sim (§2.0.3, CE-xx, CT-xx, CV-01, CI-01, CI-02) передані авторам тих модулів як запити.

## 15. Відкриті питання

Номери — ті самі, що в ARCH §5.1 (Q-01…Q-24); повне формулювання й адресат — там. Тут — що робить код і тести, поки відповіді немає.

| ID | Суть | Рекомендована відповідь | Поки немає відповіді |
|---|---|---|---|
| Q-01 | **Закрито 14.10 (відповідь № 1, CONSISTENCY):** варіант A — HGM6120N веде AMF, ATyS p у Remote control. Логіка AMF: HGM6120N чи ATyS p | **Варіант A (HGM6120N веде AMF, ATyS у Remote control)** — A-08; варіант B лише за вимогою проєктувальника, тоді 2ST ≥ 45 с | `amf_master=hgm`; код без змін підтримує обидва (R-05, R-03 за потужністю); тести покривають обидва: A — AC-37, 48, 56 (ТК-G02); B — AC-38, 57, 65 (ТК-G03, ТК-G04); UT AC-29, 31 |
| Q-02 | **Закрито 14.10 (відповідь № 3, CONSISTENCY):** в острові — виміряні значення КГУ; карта ProCon — ПРИПУЩЕННЯ до документа TEDOM. КГУ в острові паралельно з ДГУ (острівний режим TEDOM — до замовника, CONSISTENCY «Питання до замовника» № 3) | на код не впливає — в острові виміряні значення (X-10) | R-06: `chp` в острові — **виміряне** `infra/totals/chp_kw` (energy R-14 п. 9; X-10), міст нічого не підставляє; AC-56 не фіксує число КГУ |
| Q-03 | **Закрито 14.10 (відповідь № 5, CONSISTENCY):** тестовий пуск 15 хв раз на тиждень на початку зміни 1 (07:30); блекаут — без розкладу (AMF). Розклад генератора на заводі | тест 15 хв раз на тиждень поза змінами; блекаут — AMF | розклад `td_genset` офісний; ТК-G09 використовує поточний розклад стенда |
| Q-04 | Метод прийому показань telemetry | закрито SPEC telemetry v0.1: CT-10 `_f3d_ingest` (§2.0.3 T-2) | — |
| Q-05 | **Закрито 14.10 (відповідь № 5, CONSISTENCY):** у v1 зовнішнього бака немає (профіль 610 л); бак додається пізніше зміною `tank_l` профілю, без зміни коду. Зовнішній паливний бак | 1 950 л з датчиком | профіль 610 л |
| Q-06 | **Закрито 14.10 (відповідь № 1, CONSISTENCY):** заводський пресет `plant`, підтвердити на ПНР. Заводський пресет таймерів HGM/ATyS, пороги тривог | пресет `plant` (Додаток D); 2ST 45 с | `timer_preset=default`; пороги `fake_relay` — ПРИПУЩЕННЯ §8.2 |
| Q-07 | Карта Modbus ATyS p в iot_sim | **закрито (X-41):** iot_sim §8.9.4 і каталог переводяться на Annexe III (20483 положення, 1 = 0, 2 = I, 3 = II) | `ats_position_i_value`/`ii_value` = `2`/`3` на стенді й на проді, без стендових винятків (§5.1, §13.3.0) |
| Q-08 | **Закрито 14.10 (відповідь № 4, CONSISTENCY):** накопичувач від генератора не заряджається, в острові лише розряд; генерація — на секції 2. Заряд накопичувача від генератора | ні | R-06: `bess ≤ 0` в острові |
| Q-09 | Місце меню «Генератор» | **закрито (X-32):** base CB-09 резервує «55 genset» | A-06 |
| Q-10 | **Закрито 14.10 (рішення менеджера):** закривається розробником при перенесенні `td_genset` на 19 за репозиторієм (відповідь № 5г–д). Імена моделей/полів `td_genset` (ADP) | заповнити `adapters/td_genset.py` | `test_adapter_contract` червоний (навмисно); міст `skipped`/`last_publish_error` (§11 п. 2) |
| Q-11 | **Закрито 14.10 (рішення менеджера):** закривається розробником при перенесенні `td_genset` на 19 за репозиторієм (відповідь № 5г–д). Модель палива `td_genset` | стала → 103,8 л/год | ADP-09 повертає `False`; крива — у мосту (R-01) |
| Q-12 | **Закрито 14.10 (рішення менеджера):** закривається розробником при перенесенні `td_genset` на 19 за репозиторієм (відповідь № 5г–д). Групи `td_genset` | таблиця §4.3 | — |
| Q-13 | **Закрито 14.10 (рішення менеджера):** закривається розробником при перенесенні `td_genset` на 19 за репозиторієм (відповідь № 5г–д). Коди подій `td_genset` | заповнити `td_code` 41 рядка | збіг за `hgm_name`+`severity` і `DEFAULT_*` |
| Q-14 | **Закрито 14.10 (рішення менеджера):** закривається розробником при перенесенні `td_genset` на 19 за репозиторієм (відповідь № 5г–д). `fake_relay`: порт, формат, команди | узгодити з API-F-xx | W4 додає §8 |
| Q-15 | **Закрито 14.10 (рішення менеджера):** закривається розробником при перенесенні `td_genset` на 19 за репозиторієм (відповідь № 5г–д). Період опитування ретранслятора, ознака offline | `offline_min=5` ≥ 3 періоди | `P_td=60 с` у §13.3.0 |
| Q-16 | **Закрито 14.10 (рішення менеджера):** закривається розробником при перенесенні `td_genset` на 19 за репозиторієм (відповідь № 5г–д). Стоп-крани й `neutralize.sql` `td_genset` | узгодити з CB-10 | AC-A15/ТБ-04 використовують ім'я з `ADAPTER_MAP.md` |
| Q-17 | **Закрито 14.10 (рішення менеджера):** закривається розробником при перенесенні `td_genset` на 19 за репозиторієм (відповідь № 5г–д). Чи створює `td_genset` заявки ТО | якщо так — `SERVICE_REQUESTS_BY_TD=True` | R-09 варіант а |
| Q-18 | **Закрито 14.10 (рішення менеджера):** закривається розробником при перенесенні `td_genset` на 19 за репозиторієм (відповідь № 5г–д). «Останній тест» у `td_genset` | ADP-07 | рядок картки «—» |
| Q-19 | **Закрито 14.10 (рішення менеджера):** закривається розробником при перенесенні `td_genset` на 19 за репозиторієм (відповідь № 5г–д). Сервіси OWL-пульта | MG-20…MG-24 | — |
| Q-20 | telemetry: локальне джерело `td_genset` без колектора, `validate_params("td_genset", {})` | **закрито (X-01):** telemetry CT-12 `_f3d_local_types()` і R-26 | M-04 розширює хук (`super()._f3d_local_types() + ["td_genset"]`), `collector_id` не перевизначає (§2.0.3 T-1); AC-01, AC-50, AC-69 |
| Q-21 | iot_sim CI-01: `amf_master`, `genset_load_kw`, `test_on_load`, оркестрація через API-F замість власних таймерів R-22 | **закрито (X-59):** параметри доповнює SPEC iot_sim (S-03, S-14, §8.14, R-22 з API-F-01…09); у мосту без змін | до правки iot_sim — `tests/stand/orchestrator.py` (§13.3.0) виконує §8.6 сам; AC — «блокер X-59» лише з рішенням менеджера |
| Q-22 | **Закрито 14.10 (відповідь № 5, CONSISTENCY):** команди D700 за умовчанням вимкнено (стоп-кран); вмикає адміністратор після підписаного протоколу етапу 4 §13.6. Дозвіл на дистанційні команди D700 на заводі; відповідальна особа на об'єкті; вікно тесту під навантаженням | команди лише після підписаного протоколу етапу 4 §13.6; перший пуск — «Тест 3 хв» без навантаження у присутності чергового електрика | на проді стоп-кран команд `td_genset` вимкнено; міст команд не має |
| Q-23 | viewer Додаток A.13: `infra.genset`, ключі `genset_*`, `island`, `grid_ok` | **закрито (X-24):** схема `meta.schema="1.1"` приймає додаткові ключі модулів адитивно (каркас §6.7); перелік — viewer Додаток A | провайдер пише ключі; до оновлення viewer Додатка A — AC-22 «блокер X-24» лише з рішенням менеджера |
| Q-24 | **Закрито 14.10 (відповідь № 5, CONSISTENCY):** оновлення `td_genset` 18 → 19 — у рамках розробки (репозиторій — вхідні дані, пункти «ЗВІРИТИ» закриває розробник); платформа прод-бази — у погоджене вікно, спершу на копії; одна база. Оновлення платформи прод-бази 18 → 19 (Odoo Upgrade): коли, хто, та сама база для `td_genset` і factory3d | одна база; оновлення платформи у вікно, погоджене з замовником; спершу копія (§13.6 етап 2) | етапи 0–2 §13.6 на копіях; етапи 3–4 не починаються |

---

## Додаток A. Сигнали генератора (CG-01, TEL-02) — 26 кодів

Код — `infra/genset/<f3d_code>/<leaf>` (для заводу `infra/genset/GENSET/<leaf>`); `name` — «Генератор <f3d_code>: <назва>». Для
всіх 26: `equipment_id` = GENSET, `source_id` = `GENSET-RELAY`, `module='genset'`, `period_s = max(60, offline_min·20)` (100),
`store_period_s=0`, `scale=1.0`, `viewer_visible=True`, `create_request=False`, `address={"leaf": <leaf>}` (довідково; колектор
сигнал не читає), пороги — §2.0.3 T-4. «Payload» — правило R-11 (`int` — ціле число; `частка` — `unit='%'` → `/100`). «Stale» —
чи переводиться в `stale` за R-12/T-3 (4 сигнали без позначки публікуються завжди). Приклад — знімок `SNAP_LOADED` (§13.0, AC-07).

| # | leaf | Назва | Одиниця | `kind` | Payload | Джерело значення | Stale | Приклад |
|---|---|---|---|---|---|---|---|---|
| 1 | `state` | стан (код 0–10) | — | gauge | int | R-03 `STATE_MAP` + правило 6/7 | ні | 7 |
| 2 | `mode` | режим (0 стоп, 1 ручний, 2 авто, 3 тест) | — | gauge | int | R-03 `MODE_MAP` | так | 2 |
| 3 | `breaker` | вимикач (0 жодного, 1 мережа, 2 генератор) | — | gauge | int | R-03 `BREAKER_MAP` | так | 2 |
| 4 | `mains_ok` | мережа в нормі | — | gauge | int | ADP-03 `mains_ok` | так | 0 |
| 5 | `alarm_level` | рівень тривоги (0/1/2) | — | gauge | int | R-03 з `alarms` | так | 0 |
| 6 | `alarm_count` | кількість активних тривог | — | gauge | int | `len(alarms)` | так | 0 |
| 7 | `online` | зв'язок з контролером | — | gauge | int | R-12 | ні | 1 |
| 8 | `p_kw` | активна потужність | кВт | gauge | float | ADP-03 `p_kw` | так | 348.0 |
| 9 | `load_pct` | навантаження від PRP | % | gauge | частка | R-03 `p_kw/kw_prp` | так | 68.6 (→ 0.686) |
| 10 | `u_v` | лінійна напруга | В | gauge | float | ADP-03 `u_v` | так | 400.2 |
| 11 | `f_hz` | частота | Гц | gauge | float | ADP-03 `f_hz` | так | 50.0 |
| 12 | `i_a` | струм (найбільша фаза) | А | gauge | float | ADP-03 `i_a` | так | 628.0 |
| 13 | `pf` | коефіцієнт потужності | — | gauge | float | ADP-03 `pf` | так | 0.8 |
| 14 | `kwh` | вироблена енергія | кВт·год | counter | float | ADP-03 `kwh` | так | 61255.3 |
| 15 | `fuel_pct` | рівень палива | % | gauge | частка | ADP-03 `fuel_pct` | так | 82.0 (→ 0.82) |
| 16 | `fuel_l` | паливо в баку | л | gauge | float | ADP-03 `fuel_l` або R-03 з `fuel_pct` | так | 500.2 |
| 17 | `fuel_lph` | витрата палива | л/год | gauge | float | R-01 (0 поза станами 6/7) | ні | 95.5 |
| 18 | `autonomy_h` | автономність | год | gauge | float | R-02 | ні | 5.2 |
| 19 | `hours` | мотогодини | год | counter | float | ADP-03 `hours` | так | 1213.0 |
| 20 | `starts` | кількість пусків | шт | counter | int | ADP-03 `starts` | так | 185 |
| 21 | `service_h_left` | до ТО | год | gauge | float | ADP-05 `hours_left` | так | 37.0 |
| 22 | `coolant_c` | температура ОЖ | °C | gauge | float | ADP-03 `coolant_c` | так | 84.1 |
| 23 | `oil_bar` | тиск оливи | бар | gauge | float | ADP-03 `oil_bar` (кПа → /100) | так | 4.4 |
| 24 | `batt_v` | напруга АКБ | В | gauge | float | ADP-03 `batt_v` | так | 25.3 |
| 25 | `charger_v` | напруга зарядного | В | gauge | float | ADP-03 `charger_v` | так | 27.6 |
| 26 | `rpm` | оберти | об/хв | gauge | float | ADP-03 `rpm` | так | 1502.0 |

Значення `None` з адаптера не публікується (сигнал лишається з попереднім значенням). Крон stale telemetry сигнали локального
джерела `GENSET-RELAY` не бачить (R-26), тож `stale` за таймаутом не настає: його ставить лише міст — при не-`fresh` знімку (R-12,
§2.0.3 T-3; X-13).

## Додаток B. Мапа подій HGM6120N → дії (`data/f3d_genset_event_map.xml`, 48 рядків, A-16)

Назви `hgm_name` — дослівно з «HGM6100N Series Genset Controller User Manual», §5.1 Table 4 «Controller Warning Alarms» (17) і §5.2
Table 5 «Shutdown Alarms» (24), smartgen.cn, переглянуто 14.10.2026. Вісім назв є в обох таблицях (Loss of Speed Signal, Low Fuel
Level, Low Coolant Level, Temp. Sensor Open, Oil Pressure Sensor Open, High Temp., Low Oil Pressure, Over Power) — тому `_match` (б)
порівнює ще й `severity`. XML-id — `evmap_<key_lower>`; `td_code` у data порожній (Q-13); `match_regex` порожній; `active=True`.
У шаблонах числа — `%.1f` з комою (§11 п. 9); `{code}` — код сцени обладнання.

`description_tpl` (однаковий для всіх 48): «Подія контролера SmartGen HGM6120N (через td_genset): {name}.\nПоказник: {value} {unit};
поріг: {threshold} {unit}.\nЧас: {ts} (Київ).\nТекст td_genset: {text}\nЗапис td_genset: {td_link}».

| seq | `key` | `hgm_table` | `severity` | `hgm_name` | `action` | `priority` | `name_tpl` |
|---|---|---|---|---|---|---|---|
| 101 | `LOSS_OF_SPEED_SIGNAL_W` | warning | warning | Loss of Speed Signal | request_corrective | 2 | Генератор {code}: втрачено сигнал датчика обертів |
| 102 | `GENSET_OVER_CURRENT_W` | warning | warning | Genset Over Current | bus_only | 2 | Генератор {code}: перевищення струму — {value} {unit} при нормі ≤ {threshold} {unit} |
| 103 | `FAIL_TO_STOP_W` | warning | warning | Fail to Stop | request_corrective | 3 | Генератор {code}: не зупиняється після команди «Стоп» |
| 104 | `LOW_FUEL_LEVEL_W` | warning | warning | Low Fuel Level | request_corrective | 3 | Генератор {code}: низький рівень палива — {value} {unit} при нормі ≥ {threshold} {unit} |
| 105 | `FAIL_TO_CHARGE_W` | warning | warning | Fail to Charge | request_corrective | 2 | Генератор {code}: немає зарядки АКБ від генератора (D+/WL) |
| 106 | `BATTERY_UNDER_VOLTAGE_W` | warning | warning | Battery Under Voltage | request_corrective | 2 | Генератор {code}: низька напруга АКБ — {value} {unit} при нормі ≥ {threshold} {unit} |
| 107 | `BATTERY_OVER_VOLTAGE_W` | warning | warning | Battery Over Voltage | request_corrective | 2 | Генератор {code}: висока напруга АКБ — {value} {unit} при нормі ≤ {threshold} {unit} |
| 108 | `LOW_COOLANT_LEVEL_W` | warning | warning | Low Coolant Level | request_corrective | 2 | Генератор {code}: низький рівень охолоджувальної рідини |
| 109 | `TEMP_SENSOR_OPEN_W` | warning | warning | Temp. Sensor Open | request_corrective | 2 | Генератор {code}: обрив датчика температури ОЖ |
| 110 | `OIL_PRESSURE_SENSOR_OPEN_W` | warning | warning | Oil Pressure Sensor Open | request_corrective | 2 | Генератор {code}: обрив датчика тиску оливи |
| 111 | `MAINTENANCE_DUE_W` | warning | warning | Maintenance Due Warning | bus_only | 1 | Генератор {code}: контролер повідомляє про строк ТО (заявку створює R-09) |
| 112 | `HIGH_TEMP_W` | warning | warning | High Temp. | request_corrective | 3 | Генератор {code}: висока температура ОЖ — {value} {unit} при нормі ≤ {threshold} {unit} (зупинку заблоковано) |
| 113 | `LOW_OIL_PRESSURE_W` | warning | warning | Low Oil Pressure | request_corrective | 3 | Генератор {code}: низький тиск оливи — {value} {unit} при нормі ≥ {threshold} {unit} (зупинку заблоковано) |
| 114 | `INPUT_WARN_W` | warning | warning | Input Warn | bus_only | 2 | Генератор {code}: зовнішній вхід попередження — {text} |
| 115 | `FAILED_TO_CHARGE_INPUT_W` | warning | warning | Failed to Charge | request_corrective | 2 | Генератор {code}: сигнал «немає зарядки» від зарядного пристрою |
| 116 | `OVER_POWER_W` | warning | warning | Over Power | bus_only | 2 | Генератор {code}: перевищення потужності — {value} {unit} при нормі ≤ {threshold} {unit} |
| 117 | `ECU_WARN_W` | warning | warning | ECU Warn | ignore | 0 | Генератор {code}: попередження ECU — {text} (HGM6120N без J1939) |
| 201 | `EMERGENCY_STOP_SD` | shutdown | shutdown | Emergency Stop | request_corrective | 3 | Генератор {code}: аварійна зупинка — натиснуто аварійну кнопку |
| 202 | `HIGH_TEMP_SD` | shutdown | shutdown | High Temp. | request_corrective | 3 | Генератор {code}: аварійна зупинка — висока температура ОЖ {value} {unit} при нормі ≤ {threshold} {unit} |
| 203 | `LOW_OIL_PRESSURE_SD` | shutdown | shutdown | Low Oil Pressure | request_corrective | 3 | Генератор {code}: аварійна зупинка — низький тиск оливи {value} {unit} при нормі ≥ {threshold} {unit} |
| 204 | `OVER_SPEED_SD` | shutdown | shutdown | Over Speed | request_corrective | 3 | Генератор {code}: аварійна зупинка — перевищення обертів {value} {unit} при нормі ≤ {threshold} {unit} |
| 205 | `UNDER_SPEED_SD` | shutdown | shutdown | Under Speed | request_corrective | 3 | Генератор {code}: аварійна зупинка — низькі оберти {value} {unit} при нормі ≥ {threshold} {unit} |
| 206 | `LOSS_OF_SPEED_SIGNAL_SD` | shutdown | shutdown | Loss of Speed Signal | request_corrective | 3 | Генератор {code}: аварійна зупинка — втрачено сигнал датчика обертів |
| 207 | `GEN_OVER_VOLTAGE_SD` | shutdown | shutdown | Gen Over Voltage | request_corrective | 3 | Генератор {code}: аварійна зупинка — перенапруга {value} {unit} при нормі ≤ {threshold} {unit} |
| 208 | `GEN_UNDER_VOLTAGE_SD` | shutdown | shutdown | Gen Under Voltage | request_corrective | 3 | Генератор {code}: аварійна зупинка — знижена напруга {value} {unit} при нормі ≥ {threshold} {unit} |
| 209 | `GEN_OVER_CURRENT_SD` | shutdown | shutdown | Gen Over Current | request_corrective | 3 | Генератор {code}: аварійна зупинка — перевищення струму {value} {unit} при нормі ≤ {threshold} {unit} |
| 210 | `FAIL_TO_START_SD` | shutdown | shutdown | Fail to Start | request_corrective | 3 | Генератор {code}: не вдалося запустити — аварійна зупинка після всіх спроб пуску |
| 211 | `GEN_OVER_FREQUENCY_SD` | shutdown | shutdown | Gen Over Frequency | request_corrective | 3 | Генератор {code}: аварійна зупинка — підвищена частота {value} {unit} при нормі ≤ {threshold} {unit} |
| 212 | `GEN_UNDER_FREQUENCY_SD` | shutdown | shutdown | Gen Under Frequency | request_corrective | 3 | Генератор {code}: аварійна зупинка — знижена частота {value} {unit} при нормі ≥ {threshold} {unit} |
| 213 | `GENSET_FAILED_SD` | shutdown | shutdown | Genset Failed | request_corrective | 3 | Генератор {code}: аварійна зупинка — генератор не видає напругу (частота 0) |
| 214 | `LOW_FUEL_LEVEL_SD` | shutdown | shutdown | Low Fuel Level | request_corrective | 3 | Генератор {code}: аварійна зупинка — низький рівень палива {value} {unit} при нормі ≥ {threshold} {unit} |
| 215 | `LOW_COOLANT_LEVEL_SD` | shutdown | shutdown | Low Coolant Level | request_corrective | 3 | Генератор {code}: аварійна зупинка — низький рівень охолоджувальної рідини |
| 216 | `TEMP_SENSOR_OPEN_SD` | shutdown | shutdown | Temp. Sensor Open | request_corrective | 3 | Генератор {code}: аварійна зупинка — обрив датчика температури ОЖ |
| 217 | `OIL_PRESSURE_SENSOR_OPEN_SD` | shutdown | shutdown | Oil Pressure Sensor Open | request_corrective | 3 | Генератор {code}: аварійна зупинка — обрив датчика тиску оливи |
| 218 | `MAINTENANCE_DUE_SD` | shutdown | shutdown | Maintenance Due | request_corrective | 3 | Генератор {code}: аварійна зупинка — настав строк ТО, контролер заблокував роботу |
| 219 | `INPUT_SHUTDOWN_SD` | shutdown | shutdown | Input Shutdown | request_corrective | 3 | Генератор {code}: аварійна зупинка — зовнішній вхід: {text} |
| 220 | `OVER_POWER_SD` | shutdown | shutdown | Over Power | request_corrective | 3 | Генератор {code}: аварійна зупинка — перевищення потужності {value} {unit} при нормі ≤ {threshold} {unit} |
| 221 | `ECU_SHUTDOWN_SD` | shutdown | shutdown | ECU Shutdown | request_corrective | 3 | Генератор {code}: аварійна зупинка — ECU: {text} |
| 222 | `ECU_COMM_FAILURE_SD` | shutdown | shutdown | ECU Comm. Failure | request_corrective | 3 | Генератор {code}: аварійна зупинка — немає зв'язку з ECU |
| 223 | `OVER_CURRENT_FAULT_SD` | shutdown | shutdown | Over Current Fault | request_corrective | 3 | Генератор {code}: аварійна зупинка — вхід «перевищення струму» |
| 224 | `OVER_SPEED_INPUT_SD` | shutdown | shutdown | Over Speed Shutdown Input Alarm | request_corrective | 3 | Генератор {code}: аварійна зупинка — вхід «перевищення обертів» |
| 300 | `COMM_LOST` | other | comm | — | request_corrective | 2 | Генератор {code}: втрачено зв'язок з контролером (немає даних {value} хв) |
| 310 | `SERVICE_DUE` | other | service | — | request_preventive | 1 | Генератор {code}: планове ТО {text} |
| 900 | `DEFAULT_WARNING` | other | warning | — | bus_only | 2 | Генератор {code}: попередження — {name} |
| 910 | `DEFAULT_SHUTDOWN` | other | shutdown | — | request_corrective | 3 | Генератор {code}: аварійна зупинка — {name} |
| 920 | `DEFAULT_COMM` | other | comm | — | bus_only | 2 | Генератор {code}: зв'язок — {name} |
| 930 | `DEFAULT_SERVICE` | other | service | — | bus_only | 1 | Генератор {code}: ТО — {name} |
| 940 | `DEFAULT_INFO` | other | info | — | ignore | 0 | Генератор {code}: {name} |

`COMM_LOST` викликає R-12 (подія моста, `value` = хвилини без даних), `SERVICE_DUE` — R-09 (`text` = «через 37 мотогодин (наступне
на 1 250, зараз 1 213)» або «прострочено на 12 мотогодин (наступне на 1 250, зараз 1 262)»; так отримується назва AC-18/AC-19).
Рядки без `hgm_name` у пункті (б) `_match` не беруть участі. Подія `severity="command"` (команди пульта) рядка не має — дії немає.

## Додаток C. Профіль D700 (`data/f3d_genset_profile.xml`, `profile_d700`) — значення і джерела

| Поле | Значення | Джерело |
|---|---|---|
| `code` / `name` | `D700` / «KOHLER-SDMO D700 · SmartGen HGM6120N» | `plant/equipment_specs.json[role=genset]` |
| `kva_prp` / `kw_prp` | 634 / 507 | там само (`kva=634`, `power_kw=507`); SDMO D700 datasheet (PRP) |
| `kva_esp` / `kw_esp` | 697 / 558 | `kva_standby=697`; 697 × 0,8 = 557,6 → 558 (ESP, PF 0,8) |
| `tank_l` | 610 | `tank_l=610`; datasheet «Tank capacity 610 L» (опція 1 950 L — Q-05) |
| `fuel_lph_25` | 38,6 | Doosan DP180LB engine spec, 25 % |
| `fuel_lph_50` / `_75` / `_100` | 71,2 / 103,8 / 136,4 | SDMO D700 datasheet @ 50/75/100 % PRP; `fuel_lph_75=103.8` у `equipment_specs.json` |
| `fuel_lph_esp` | 149,5 | SDMO D700 datasheet @ 100 % ESP |
| `oil_l` / `oil_pressure_min_bar` | 34 / 0,5 | datasheet «Oil system 34 L», «Min. oil pressure 0,50 bar» |
| `start_to_load_s` | 15 | ціль заводу: картка ATS-1 «Переключення: після пуску генератора, 10–15 с» (`plant/infra.py`); з умовчаннями HGM фактично 30 с (Додаток D.2) |
| `autonomy_warn_h` | 2,0 | рішення автора для `warn` картки (R-10) |
| `timer_preset` | `default` | Додаток D.1 |
| `note` | URL датасітів SDMO D700 і Doosan DP180LB, мануалу HGM6100N (ARCH §8) | — |

Контрольні точки (AC-04, AC-05): витрата 95,5 л/год при 348 кВт (68,6 %); автономність повного бака — 5,9 год при 75 %, 6,4 год при
348 кВт; картка макета «Паливо 82 % · 500 л», «≈ 4,8 год при 75 %».

## Додаток D. Таймери й послідовності HGM6120N (для `fake_relay`, R-03, ТК)

### D.1 Таймери (Table 7 «Parameter Content and Range», мануал HGM6100N; пресет `plant` — Q-06)

| Ключ профілю | Параметр HGM | Умовчання (Table 7) | `plant` |
|---|---|---|---|
| `mains_normal_s` | Mains Normal Delay | 10 с | 10 |
| `mains_abnormal_s` | Mains Abnormal Delay | 5 с | 2 |
| `transfer_s` | Transfer Delay | 1,0 с | 1,0 |
| `start_delay_s` | Start Delay | 1 с | 0 |
| `stop_delay_s` | Stop Delay | 1 с | 1 |
| `start_times` | Start Times | 3 | 3 |
| `crank_s` | Cranking Time | 8 с | 8 |
| `crank_rest_s` | Crank Rest Time | 10 с | 10 |
| `crank_fire_s` | — (модель `fake_relay`: двигун «схоплює» на 3-й секунді прокрутки) | 3 с | 3 |
| `safety_on_s` | Safety On Time | 10 с | 5 |
| `warming_s` | Warming Up Time | 10 с | 3 |
| `cooling_s` | Cooling Time | 10 с | 10 |
| `ets_hold_s` | ETS Solenoid Hold | 20 с | 20 |
| `over_current_delay_s` | Over Current Delay | 30 с | 30 |
| — | Start Idle / Stop Idle Time | 0 / 0 с | 0 / 0 |

### D.2 Варіант A — HGM6120N веде AMF (стани `fake_relay` → код R-03)

| Час (умовчання) | Час (`plant`) | Подія | `state` `fake_relay` (код) | `breaker` |
|---|---|---|---|---|
| t0 | t0 | мережа поза межами (`POST /sim/v1/mains {"available": false}`) | `mains_abnormal` (2) | mains |
| t0 + 5 | t0 + 2 | Mains Abnormal Delay минув | `starting` (3), Start Delay | none (мережу відкрито) |
| t0 + 6 | t0 + 2 | прокрутка; на 3-й с двигун запущено, `starts` +1 | `starting` (3) | none |
| t0 + 9 | t0 + 5 | Safety On | `safety_on` (4) | none |
| t0 + 19 | t0 + 10 | Warming Up | `warming` (5) | none |
| t0 + 29 | t0 + 13 | U/f у нормі; Transfer Delay | `running` (6) | none |
| t0 + 30 | t0 + 14 | реле генератора закрито | `loaded` (7) | gen |
| t_r | t_r | мережа в нормі (`{"available": true}`) | `loaded` (7), Mains Normal Delay | gen |
| t_r + 11 | t_r + 11 | Mains Normal 10 + Stop Delay 1; реле генератора відкрито | `cooling` (8) | none |
| t_r + 12 | t_r + 12 | Transfer Delay; реле мережі закрито | `cooling` (8) | mains |
| t_r + 22 | t_r + 22 | Cooling минув | `stopping` (9), ETS Hold | mains |
| t_r + 42 | t_r + 42 | двигун зупинено | `standby` (1) | mains |

Fail to Start (`fault start_fail`): t0 + 5 → Start Delay 1 → 3 × (прокрутка 8 с) з 2 паузами по 10 с → `alarm_shutdown` (10) на t0 + 50,
подія «Fail to Start» (shutdown). Remote start / «Тест» (без втрати мережі): Start Delay 1 + 3 + Safety On 10 + Warming Up 10 → `running`
через 24 с; у `test_on_load=false` реле мережі лишається закритим.

### D.3 Варіант B — ATyS p головний (таймери ATyS p — instruction manual 542 001 D)

| Час | Подія | ATyS p (`infra/ats/position`) | `fake_relay` |
|---|---|---|---|
| t0 | Source 1 зникла (`src1_ok=0`) | I | `standby`, `mains_ok=true` (API-F-02 у варіанті B не викликається) |
| t0 + 3 | 1FT 3 с минув; реле пуску (20484=1) → `POST /sim/v1/remote_start {"on": true}` | I | `starting` (3) |
| t0 + 27 | Start Delay 1 + 3 + Safety On 10 + Warming Up 10 | I | `running` (6), `gen_ok=true` |
| t0 + 32 | 2AT 5 с; переключення I → 0 | 0 | `running` (6) |
| t0 + 35 | ODT 3 с; 0 → II; `POST /sim/v1/load {"kw": 348}` | II | `loaded` (7), `breaker=mains` |
| t_r | Source 1 повернулась | II | `loaded` (7) |
| t_r + 180 | 1RT 180 с; II → 0 → I (ODT 3 с); `POST /sim/v1/load {"kw": 0}` | I | `running` (6), `p_kw=0` |
| t_r + 363 | 2CT 180 с; `remote_start {"on": false}` | I | Stop Delay 1 → `cooling` (8) 10 с → `stopping` (9) 20 с |
| t_r + 394 | — | I | `standby` (1) |

Правило станів `fake_relay` для варіанта B (A-16): при `remote_start=true` і `mains_ok=true` реле HGM не перемикаються (`breaker=mains`),
а стан `loaded` (7) — коли двигун працює і `load_kw > 0`, `running` (6) — коли `load_kw = 0`. Міст визначає 7 за R-03 (`p_kw ≥ 5 %
kw_prp`). FAIL START: якщо `gen_ok` не настав за 2ST 30 с від наказу пуску (t0 + 33), iot_sim/energy фіксує «FAIL START», ATyS у II не
переходить; з умовчаннями HGM `gen_ok` на 24-й с — запас 6 с (Q-06: рекомендовано 2ST ≥ 45 с).

### D.4 Пороги тривог: умовчання HGM проти профілю `fake_relay`

| Тривога | Умовчання Table 7 | `fake_relay` `alarms` (§8.2) | Статус |
|---|---|---|---|
| High Temperature Shutdown | 98 °C | `coolant_high_c` 98 | збігається |
| Low Oil Pressure Shutdown | 103 кПа (1,03 бар) | `oil_low_bar` 1,0 | округлено; уточнити при ПНР (Q-06) |
| Low Fuel Level Warning | 10 % | `low_fuel_warn_pct` 25 | ПРИПУЩЕННЯ заводу (Q-06), використано в AC-52 |
| Fuel Level Low Shutdown | 5 % | `low_fuel_sd_pct` 10 | ПРИПУЩЕННЯ (Q-06) |
| Battery Under / Over Voltage | 8,0 / 33,0 В | `batt_low_v` 23,0 / `batt_high_v` 33,0 | для АКБ 24 В нижній поріг задає ПНР (Q-06) |
