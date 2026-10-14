# td_genset (перенос 18 → 19) і factory3d_genset — специфікація

Версія 0.1 · 14.10.2026 · технічне рішення: `docs/modules/td_genset/ARCHITECTURE.md` (далі ARCH: CR-01…CR-10,
FR-A01…FR-A08, FR-01…FR-16, A-01…A-17, Q-01…Q-24). Контракти, на які спирається: каркас §5, §6.1–6.4, §6.7,
§6.8; `factory3d_base` CB-01, CB-02, CB-07…CB-10; `factory3d_viewer` C-02, C-03, C-07, M-01, M-03, R-01,
Додаток A.13; `factory3d_iot_sim` P-07 (§8.9.4), P-12 (§8.14), API-13, API-16, S-03, S-14, §8.1.3–8.1.4, Q-07, Q-15;
`factory3d_telemetry` — каркас §6.4 і SPEC telemetry v0.1 (14.10.2026: M-02 `f3d.source`, M-03 `f3d.signal`, M-04
`f3d.reading`, M-07, M-08, CT-10 `_f3d_ingest`, R-03…R-07); розбіжності з припущеннями цього документа зведено в §2.0.3 і
мають пріоритет над текстом §2.0.2. Контракти, які задає цей документ: CG-01…CG-06 (ARCH §2.1), API-F-01…API-F-09 (§8),
ADP-01…ADP-10 (§2.0.1), TEL-01…TEL-04 (§2.0.2).

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
5. Матриця регресії AC-01…AC-69 ↔ тест/ТК (§13.2) — усі 69 позначені «зелено» або «змінено (MG-xx)».
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
│   ├── f3d_source.py                M-04 selection_add td_genset
│   ├── maintenance_equipment.py     M-05
│   ├── maintenance_request.py       M-06 (+ закриття заявки → статус сигналу, R-08 крок 4)
│   ├── res_config_settings.py       M-07
│   └── viewer_provider.py           M-08 f3d.viewer.provider.genset (R-05, R-06, R-10, R-11)
├── views/
│   ├── genset_link_views.xml        V-01, V-02 + дії
│   ├── genset_profile_views.xml     V-03, V-04
│   ├── genset_event_map_views.xml   V-05
│   ├── maintenance_views.xml        V-06 (equipment), V-09 (request)
│   ├── res_config_settings_views.xml V-07
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
    ├── test_provider.py             провайдер 155, картка, тотали, шина (R-10, CG-02, CG-05)
    ├── test_access.py               права, стоп-крани
    ├── test_hooks.py                post_init/uninstall, neutralize
    ├── test_views.py                V-01…V-09: представлення завантажуються, меню й групи
    ├── test_static.py               grep-тести коду модуля (AC-34, AC-41, §14)
    └── stand/                       ТК-G01…ТК-G13 (pytest, §13.3): conftest.py, orchestrator.py, test_tk_g*.py
```

Файли, яких торкається запит на зміни в репозиторії `td_genset` (W1, W4): `__manifest__.py`, `security/*.xml`,
`views/*.xml`, `models/*.py` (за MG-xx), `static/src/**` (пульт), `data/ir_cron*.xml`, `controllers/*.py`,
`tests/*`, `neutralize.sql`, `preflight*`, `docker-compose*.yml`, `relay/fake_relay.py`, `relay/profiles/office.json`
(існуючий профіль, винесений у файл — якщо його ще нема), `relay/profiles/d700.json` (новий), `relay/Dockerfile`,
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
    "depends": ["td_genset", "factory3d_base", "factory3d_telemetry", "factory3d_energy", "factory3d_viewer",
                "maintenance", "bus"],
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
| TEL-01 | `ensure_source(env, link) -> f3d.source` | `search([("type","=","td_genset"),("name","=","Ретранслятор SmartGen (td_genset)")], limit=1)`; немає → `create({"name": …, "type": "td_genset", "address": "local", "read_enabled": True})`; записати в `link.source_id` |
| TEL-02 | `ensure_signals(env, link) -> dict[str, f3d.signal]` | для кожного рядка Додатка A: `search([("code","=",code)])`; немає → `create({"code", "name", "equipment_id": link.equipment_id.id, "source_id": link.source_id.id, "unit", "kind", "period_s": 60, "scale": 1.0, "address": leaf})`; пороги не задаються (A-05); повертає `{code: signal}` |
| TEL-03 | `ingest(env, batch: list[dict]) -> dict` | `batch = [{"code", "ts" (datetime UTC), "value" (float), "q" (0/1)}]`. Якщо `hasattr(env["f3d.signal"], "_f3d_ingest")` → `return env["f3d.signal"]._f3d_ingest(batch)` (CT-01, той самий метод, що й `POST /f3d/telemetry/push`). Інакше запасний шлях: для кожного елемента — `signal = by_code[code]`; якщо `f3d.reading` з `(signal_id, ts)` уже є → пропустити (ідемпотентно); `create f3d.reading {ts, signal_id, value, quality: q}`; `signal.write({"last_value": value, "last_ts": ts, "status": "ok" if q else "stale"})`. Повертає `{"accepted": n, "skipped": m}` |
| TEL-04 | `read_values(env, codes: list[str]) -> dict[str, tuple[float \| None, datetime \| None, str]]` | `search_read([("code","in",codes)], ["code","last_value","last_ts","status"])` → `{code: (value, ts, status)}`; відсутній код → відсутній ключ |

Імена полів `f3d.signal`/`f3d.reading`/`f3d.source` — константи у верхній частині файлу (`SIGNAL_CODE="code"`, …) з
коментарем «за каркасом §6.4; звірити зі SPEC factory3d_telemetry M-xx». `test_adapter_contract.py` перевіряє їх через
`fields_get` так само, як ADP.

#### 2.0.3 Звірка з SPEC `factory3d_telemetry` v0.1 (14.10.2026) — рішення A-15 (обов'язкові для W2 і тестів)

SPEC telemetry з'явився після §2.0.2; де він конкретніший, діє цей рядок (він має пріоритет над §2.0.2, M-04…M-06, R-09,
R-12 у частині, що тут названа). Відкрите для автора telemetry — Q-20.

| # | Припущення моста | Факт у telemetry v0.1 | Рішення для моста |
|---|---|---|---|
| T-1 | `f3d.source` без колектора, поле `address="local"` | M-02: `code` (req, `^[A-Z0-9][A-Z0-9\-\.]{0,31}$`), `collector_id` (req), `params` (Json, перевірка `validate_params(type, params)`), `module` ∈ … `genset`; поля `address` немає | TEL-01 створює `{"code": "GENSET-RELAY", "name": "Ретранслятор SmartGen (td_genset)", "type": "td_genset", "module": "genset", "equipment_id": eq.id, "params": {}, "read_enabled": True, "period_s_default": 60}`; пошук — `search([("code","=","GENSET-RELAY")], limit=1)`. M-04 перевизначає `collector_id = fields.Many2one(required=False)` і додає `@api.constrains("type","collector_id") _check_f3d_collector_required`: `type != "td_genset" and not collector_id` → `ValidationError("Джерело %s: вкажіть колектор.")` — для всіх інших типів поведінка telemetry не змінюється. Якщо `validate_params("td_genset", {})` telemetry повертає помилку — це блокер Q-20 (AC-01, AC-50 червоні), міст не обходить перевірку |
| T-2 | `ingest` з `q` 0/1, повертає `skipped` | CT-10 `_f3d_ingest(readings, src="module")`, `readings=[{"code","ts","value","text","q"}]`, `q` ∈ `good/uncertain/bad`; повертає `{"accepted","stored","duplicates","rejected","changed_codes"}`; `q="bad"` статус не змінює (R-04); R-03 пише в `f3d.reading` лише за політикою `store_period_s` | TEL-03 викликає `_f3d_ingest(batch, src="module")` з `q="good"` і повертає `{"accepted": r["accepted"], "stored": r["stored"], "skipped": r["accepted"] - r["stored"]}` (ключ `skipped` у AC-10 — саме це число). Запасний шлях §2.0.2 не реалізується (метод є) |
| T-3 | R-12: при застарілих даних «`q=0` → `status=stale`» | `q="bad"` статус не змінює; є `f3d.signal._mark_stale(reason)` (R-07) | Не `fresh` (R-12) → TEL-03 публікує лише 4 похідні сигнали з `ts=now`, `q="good"`: `online=0`, `state=0`, `fuel_lph=0`, `autonomy_h` (останній `fuel_l` при 75 %); решта 22 сигнали → `_mark_stale("td_genset: немає свіжих даних")` (ідемпотентно, чаттер — раз на перехід). Наступний свіжий знімок повертає статус за R-04 |
| T-4 | Пороги «порожні» (`alarm_state`) | M-03: `warn_low/…/alarm_high` + прапори `warn_low_on/…/alarm_high_on` (default `False`), `alarm_states` (Json), `create_request` (**default `True`**) | TEL-02 для всіх 26: `create_request=False`, `alarm_states=[]`, усі `*_on=False`; виняток — `alarm_level`: `alarm_high_on=True`, `alarm_high=0.5` (статус `alarm` при значенні ≥ 1 — R-08 крок 4; заявку telemetry не створює, бо `create_request=False`) |
| T-5 | `kind='state'` для кодів стану (A-10) | `kind='state'` — значення як індекс у `states`/текст, числові пороги заборонені constraint'ом | Коди `state`, `mode`, `breaker`, `mains_ok`, `alarm_level`, `alarm_count`, `online` — `kind='gauge'`; `kwh`, `hours`, `starts` — `counter`; решта — `gauge` (Додаток A). A-10 у частині `kind` замінено; числовий код 0…10 лишається |
| T-6 | `period_s=60` | R-07: `stale_after = max(stale_periods·period_s, stale_min_s)` = `max(3·period_s, 60)` для сигналів із `source_id`; R-03: `store_period_s` default 300 | TEL-02: `period_s = max(60, offline_min·20)` (умовчання 100 → `stale_after` 300 с = `offline_min`), `store_period_s = 0` (кожна публікація моста зберігається: 26 × 1 440 = 37 440/добу, ARCH §2.7). Публікація лишається раз на 60 с |
| T-7 | `f3d_meter_signal_id` = `hours` без інтервалу (A-04) | M-07: constraint «Задайте інтервал ТО за лічильником (> 0)»; з інтервалом telemetry R-11 сам створює планові заявки | Міст **не** ставить `f3d_meter_signal_id` (§5.3 крок 7 і R-09 крок 6 скасовано); ТО веде лише `td_genset` + R-09 моста (A-04 без змін за змістом) |
| T-8 | Міст «заповнює» `f3d_equipment_code` | M-08: `f3d_equipment_code` = `related equipment_id.f3d_code`, `store=True`; є `f3d_value`, `f3d_threshold`, `f3d_origin` | R-07 vals **без** `f3d_equipment_code` (значення дає related); додати `f3d_value = ev["value"]`, `f3d_threshold = ev["threshold"]` (якщо не `None`); `f3d_origin` не задається (заявка не з порогу telemetry) |
| T-9 | M-06 пише `status="ok"` при закритті | M-08 `write` при переході в `done` викликає `f3d_signal_id._on_request_closed()` (R-06: статус перераховується з `last_value`) | M-06 `_f3d_genset_on_closed` статус **не** пише; лише `link.message_post("Заявку … закрито")`. Ефект R-08 крок 4 дає telemetry R-06 (alarm_level 0 → `ok`, ≥ 1 → `alarm`) |
| T-10 | `infra.totals.genset_kva`, `critical_kw` — Float | viewer Додаток A.13: `genset_kva int`, `critical_kw int` | провайдер пише `int(round(profile.kva_prp))` і `int(round(critical_kw))`; нові ключі `genset_*`, `island`, `grid_ok`, вузол `infra.genset` — запит до viewer Q-23 |

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
| `_critical_kw(self) -> tuple[float, list[str]]` | R-04 → `(sum, missing_codes)` |
| `_notify_state_change(self, new_state)` | `self.env["f3d.viewer.event"]._notify("maintenance.equipment", [self.f3d_code], "state")` (C-03); `message_post` з текстом «Стан: <label>, режим: <label>, тривога: <рівень>, острів: так/ні» лише коли змінились `state`/`alarm_level`/`island` (не `online` окремо, щоб не засмічувати чаттер) |
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
                            ondelete={"td_genset": "set default"})
```

Рішення за telemetry v0.1 — §2.0.3 T-1: `collector_id = fields.Many2one(required=False)` + `_check_f3d_collector_required`;
абзац нижче — історія припущення, діє лише в частині «колектор цей тип ігнорує». Перевизначення, якщо telemetry перевіряє `address` за типом: для `td_genset` `address="local"` допустимий (у
`_check_address` — пропуск для цього типу; реалізація: `if self.type == "td_genset": continue` — узгодити з telemetry,
Q-04). Колектор цей тип ігнорує (`GET /f3d/telemetry/config` не віддає джерела типу `td_genset` — вимога до telemetry
CT-02; поки її нема, `collector_id` лишається порожнім, тож джерело не потрапляє в конфіг жодного колектора).

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
| `f3d_genset_critical_codes` | Char | `factory3d.genset.critical_codes` |
| `f3d_genset_publish_period_s` | Integer | `factory3d.genset.publish_period_s` |

`set_values()`: після `super()` — якщо змінився `publish_period_s` → `env.ref("factory3d_genset.cron_f3d_genset_publish").write({"interval_number": max(1, period//60) if period >= 60 else 1, "interval_type": "minutes"})`.

### M-08 `f3d.viewer.provider.genset` — провайдер переглядача (FR-07, FR-09, CG-02)

```python
class F3dViewerProviderGenset(models.AbstractModel):
    _name = "f3d.viewer.provider.genset"
    _inherit = "f3d.viewer.provider"
    _description = "3D: постачальник даних генератора"
    _f3d_sequence = 155          # A-07: після infra (150) energy
    _f3d_sections = ("infra",)
    _f3d_group = "factory3d_base.group_f3d_user"
```

| Метод | Алгоритм |
|---|---|
| `_f3d_viewer_collect(self, payload, ctx)` | для кожної `f3d.genset.link` (`active`, `search_read` полів `equipment_id`, `f3d_code`, `profile_id`, `last_state_json`, `last_publish_ts`): 1) `vals = adapters.telemetry.read_values(env, [26 кодів])`; 2) `node = payload.setdefault("infra", {}).setdefault("genset", {}).setdefault(code, {})`; `node[leaf] = R-11(value)` для наявних; `node["updated"] = local(max last_ts)`; `node["state_label"]`, `node["mode_label"]`, `node["breaker_label"]`, `node["alarm_label"]` (R-03 тексти); 3) `isl = link._island_state_from_signals(vals)` (R-05 з уже прочитаних значень + TEL-04 для кодів ATS); 4) `payload["infra"].setdefault("totals", {}).update({"genset_kw": node.get("p_kw", 0.0), "genset_state": node["state_label"], "genset_fuel_pct": node.get("fuel_pct"), "genset_autonomy_h": node.get("autonomy_h"), "island": isl["island"], "grid_ok": isl["grid_ok"], "genset_kva": profile.kva_prp, "critical_kw": crit})` (`critical_kw` — лише якщо energy ще не записав: `if "critical_kw" not in totals`); 5) `payload["infra"].setdefault("cards", {})[code] = R-10`; 6) якщо є `infra.cards["ATS-1"]` і `isl["island"]` — **не** чіпати (картка ATS — energy; CV-01 — viewer) |
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
| V-07 | `factory3d_genset.res_config_settings_view_form` | form inherit `base.res_config_settings_view_form` | `res.config.settings` | блок `app_settings_block` `data-string="Завод 3D: генератор"` `data-key="factory3d_genset"` (у 19 — `<app data-string=… string=… name="factory3d_genset">` / `<block>` / `<setting>`): setting «Публікувати показання в телеметрію» (`f3d_genset_read_enabled`), «Створювати заявки ТО» (`f3d_genset_requests_enabled`), «Команди на генератор (зарезервовано)» (`f3d_genset_write_enabled`, readonly), «Логіка AMF» (`f3d_genset_amf_master`), «Офлайн через, хв» (`f3d_genset_offline_min`), «Період публікації, с» (`f3d_genset_publish_period_s`), «Сигнали АВР» (три коди), «Критичні споживачі (коди сигналів через кому)» (`f3d_genset_critical_codes`, widget `char` з `placeholder`) |
| V-08 | `views/menus.xml` | menu | — | таблиця нижче |
| V-09 | `factory3d_genset.view_maintenance_request_form_f3d_genset` | form inherit `maintenance.hr_equipment_request_view_form` | `maintenance.request` | після поля `equipment_id`: `f3d_genset_event_key` (readonly, `invisible="not f3d_genset_event_key"`, `groups="factory3d_base.group_f3d_user"`) |

Меню (CB-09, A-06):

| XML-id | Назва | Батько | sequence | Групи | Дія |
|---|---|---|---|---|---|
| `menu_f3d_genset` | Генератор | `factory3d_base.menu_f3d_root` | 55 | `group_f3d_user` | — |
| `menu_f3d_genset_link` | Зв'язка | `menu_f3d_genset` | 10 | `group_f3d_user` | `action_f3d_genset_link` (`f3d.genset.link`, list,form) |
| `menu_f3d_genset_profile` | Профілі | `menu_f3d_genset` | 20 | `group_f3d_manager` | `action_f3d_genset_profile` (list,form) |
| `menu_f3d_genset_event_map` | Події → ТО | `menu_f3d_genset` | 30 | `group_f3d_manager` | `action_f3d_genset_event_map` (list,form; `context={"search_default_group_severity": 1}`) |
| `menu_f3d_genset_requests` | Заявки ТО генератора | `menu_f3d_genset` | 40 | `group_f3d_user` | `action_f3d_genset_requests` (`maintenance.request`, kanban,list,form; `domain=[("f3d_genset_event_key","!=",False)]`) |

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
| `factory3d.genset.critical_codes` | `energy/consumers/LP-1/p_now,energy/consumers/LP-2/p_now,energy/consumers/LP-3/p_now,energy/consumers/DUST-1/p_now,energy/consumers/COMPRESSOR/p_now,energy/consumers/BOILER/p_now,energy/consumers/OFFICE/p_now,energy/consumers/EF-ELEC/p_now,energy/consumers/EF-CHG/p_now,energy/lines/BW-1/p_now` | `param_critical_codes` |
| `factory3d.genset.publish_period_s` | `60` | `param_publish_period_s` |
| `factory3d.genset.service_warn_h` | `50` | `param_service_warn_h` |
| `factory3d.genset.migration_report` | `{}` | `param_migration_report` |

Читання булевих: `get_param(key, 'False') in ('True', 'true', '1')` (як у base).

### 5.2 Data-файли

| Файл | Що створює | Джерело | XML-id | Ідемпотентність |
|---|---|---|---|---|
| `data/f3d_genset_profile.xml` | профіль `D700`: `code="D700"`, `name="KOHLER-SDMO D700 · SmartGen HGM6120N"`, `kva_prp=634`, `kw_prp=507`, `kva_esp=697`, `kw_esp=558`, `tank_l=610`, `fuel_lph_25=38.6`, `fuel_lph_50=71.2`, `fuel_lph_75=103.8`, `fuel_lph_100=136.4`, `fuel_lph_esp=149.5`, `oil_l=34`, `oil_pressure_min_bar=0.5`, `start_to_load_s=15`, `autonomy_warn_h=2.0`, `timer_preset="default"`, `note` з URL датасітів (ARCH §8); `passport_id` — хук прив'язує паспорт `role='genset'` (data не може посилатись на запис base, створений хуком) | `plant/equipment_specs.json[role=genset]`, датасіт SDMO D700, Doosan DP180LB | `profile_d700` | `noupdate="0"` — числа паспорта оновлюються з модулем; менеджерські зміни — у власних профілях (копія) |
| `data/f3d_genset_event_map.xml` | 45 рядків: 17 попереджень Table 4, 24 аварійні зупинки Table 5 (Додаток B), `COMM_LOST` (comm → `request_corrective`, priority 2), `SERVICE_DUE` (service → `request_preventive`, 1), `DEFAULT_WARNING` (bus_only), `DEFAULT_SHUTDOWN` (request_corrective, 3), `DEFAULT_COMM` (request_corrective, 2), `DEFAULT_SERVICE` (request_preventive, 1), `DEFAULT_INFO` (ignore) | мануал HGM6100N §5.1, §5.2 | `evmap_<key_lower>` | `noupdate="0"`; `td_code` — порожній у data, заповнюється W1/менеджером (після `-u` **не** затирається: поле виключене з оновлення через окремий `<function>`? — простіше: `noupdate="1"` на `td_code`-записах неможливо по полю; рішення: data-файл не містить `td_code`, а хук після оновлення відновлює `td_code` з `migration_report["td_codes"]`, куди зберігає перед оновленням — див. §5.3 крок 0) |
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
7. **Лічильник ТО:** якщо `eq.f3d_meter_signal_id` порожнє і поле існує → поставити сигнал `hours`; інтервал телеметрії не чіпати (A-04).
8. **Крони:** `active = read_enabled` для `publish`; `events`/`service` — `active = requests_enabled`.
9. Звіт → параметр; лог INFO «factory3d_genset: міграцію виконано: …».

Очікувано на копії демо-бази timur-o19demo після `factory3d_base` + `factory3d_telemetry` + `td_genset`: 1 профіль, 1 джерело,
26 сигналів, 45 рядків мапи, 3 крони, зв'язка — 1 або `skipped` (залежить від даних `td_genset` на копії), 0 заявок, 0 показань.

### 5.4 `uninstall_hook(env)`

1. Крони модуля видаляються з модулем (XML-id) — додатково нічого.
2. `ir.config_parameter` з ключами `factory3d.genset.%` — `unlink()`.
3. `f3d.source` типу `td_genset` → `active=False` (поле `active` в telemetry — якщо нема, лишити як є).
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

Нових ендпоінтів міст **не додає**. Використовує: `factory3d_viewer` API-02 `/f3d/viewer/data`, API-03 `/f3d/viewer/delta`
(через провайдер M-08), шину `f3d_viewer` (M-03); `factory3d_telemetry` — внутрішній метод CT-01 (не HTTP). Стендові REST
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
└── tests/test_sim_api.py         §13.2 ТК-F
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
            "cooling_s": 10, "ets_hold_s": 20},
 "timers_plant": {"mains_abnormal_s": 2, "start_delay_s": 0, "safety_on_s": 5, "warming_s": 3},
 "sensors": {"coolant_idle_c": 22, "coolant_run_c": 85, "coolant_tau_s": 600, "oil_run_bar": 4.5, "oil_idle_bar": 0.0,
             "batt_v": 25.2, "charger_v": 27.6, "rpm_run": 1500, "u_v": 400, "f_hz": 50.0, "pf": 0.8},
 "alarms": {"low_fuel_warn_pct": 25, "low_fuel_sd_pct": 10, "coolant_high_c": 98, "oil_low_bar": 1.0, "batt_low_v": 23.0, "batt_high_v": 33.0},
 "start": {"hours": 1213.0, "starts": 184, "fuel_pct": 82, "kwh": 61250, "mode": "auto", "mains_ok": true, "last_test": "2026-10-12T07:30:00+03:00"}}
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
| API-F-04 | `POST /sim/v1/load` | `{"kw": 348}` | `{"load_kw": 348, "load_pct": 68.6}` | навантаження на шині генератора (iot_sim рахує з балансу R-06); `kw > kw_esp` → 422; `kw` між PRP і ESP → warning «Gen Over Current» після `over_current_delay_s`=30 |
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
RELAY_SIM_TOKEN: "${RELAY_SIM_TOKEN}", RELAY_TIME_FACTOR: "1", RELAY_TZ: Europe/Kyiv}`, `healthcheck: curl -fsS
http://localhost:8000/health` (існуючий health `relay_api.md` — ЗВІРИТИ шлях; інакше `GET /sim/v1/state` без токена → 401 вважати
«живий»), `networks: [f3d_sim, odoo_default]` — другий потрібен, щоб Odoo (`td_genset`) достукався до `genset_relay:8000`
(allow-list iot_sim §2.6 стосується вихідних з'єднань емулятора, не Odoo). Стенд `td_genset` (власний compose) лишається для
регресії ТК-01…ТК-14 з профілем `office` і `d700`.

### 8.6 Контракт з емулятором `factory3d_iot_sim` (CI-01, P-12, сценарії `blackout`/`genset_test`)

Напрямок: **iot_sim → fake_relay** (емулятор — оркестратор; `fake_relay` нічого не викликає сам). Параметри сценарію `blackout`
(запит до iot_sim §9.3): `duration_min` (умовчання 30), `amf_master` ∈ {`hgm`, `ats`} (умовчання з `SIM_GENSET_AMF_MASTER=hgm`),
`genset_load_kw` (умовчання — `critical_kw` з балансу емулятора, 348), `restore` (bool, умовчання true — повернути мережу по
закінченні).

Послідовність у iot_sim (варіант `hgm`): t0: мережа PM5560 unit 1/2 → 0 В, SUN2000 → `0x0303`, TEDOM → стоп, ATyS модель: `src1_ok=0`;
`POST /sim/v1/mains {"available": false}`; кожну 1 с `GET /sim/v1/state`: коли `breaker == "gen"` → ATyS `position=3 (II)`,
`src2_ok=1`, `POST /sim/v1/load {"kw": genset_load_kw}`; баланс R-06 у емуляторі (`infra/totals/*`). Завершення: `POST /sim/v1/mains
{"available": true}`; коли `breaker == "mains"` → ATyS `position=2 (I)`; після `state == standby` — `src2_ok=0`.
Варіант `ats`: iot_sim веде таймери ATyS p: `src1_ok=0` → 1FT 3 с → `POST /sim/v1/remote_start {"on": true}` (реєстр 20484=1) →
опитування `gen_ok` → 2AT 5 с → `position` 2→1(0, ODT 3 с)→3 → `POST /sim/v1/load`; якщо `gen_ok` не настав за 2ST 30 с —
подія iot_sim «FAIL START» (ТК-08); повернення: `src1_ok=1` → 1RT 180 с → `position` 3→1→2 → 2CT 180 с → `POST /sim/v1/remote_start
{"on": false}`. Сценарій `genset_test`: `POST /sim/v1/remote_start {"on": true}` на `test_min` (15) без перемикання ATyS (`test_on_load=false`)
або з перемиканням (`true`); `fake_relay` фіксує `last_test`.

У каталозі iot_sim (Додаток A) 26 кодів CG-01 — довідкові рядки `source=td_genset`, емулятор їх не веде (значення — міст із `td_genset`).
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
| `state` | 0 «немає даних»; 1 «очікування»; 2 «мережа втрачена, затримка»; 3 «пуск»; 4 «захисна затримка»; 5 «прогрів»; 6 «працює без навантаження»; 7 «під навантаженням»; 8 «охолодження»; 9 «зупинка»; 10 «аварійна зупинка» | `STATE_MAP[state_raw.lower()]`; очікувані сирі значення (англ./укр., HGM/`td_genset`): standby/очікування → 1; mains abnormal → 2; start/crank/запуск → 3; safety on → 4; warming → 5; running/робота → 6, але 7 якщо `breaker == 2`; cooling/охолодження → 8; stop idle/ets/зупинка → 9; alarm/shutdown/аварія → 10; невідомо → 0 + `last_publish_error` |
| `mode` | 0 «стоп»; 1 «ручний»; 2 «авто»; 3 «тест» | `MODE_MAP` |
| `breaker` | 0 «жодного»; 1 «мережа»; 2 «генератор» | `BREAKER_MAP` (у HGM — стан реле закриття мережі/генератора) |
| `mains_ok` | 0/1 | `snap["mains_ok"]` |
| `alarm_level` | 0 «немає»; 1 «попередження»; 2 «аварійна зупинка» | 2 якщо ∃ `alarms[].severity == "shutdown"`, 1 якщо ∃ `warning`, інакше 0 |
| `alarm_count` | ціле | `len(alarms)` |
| `online` | 0/1 | R-12 |

`load_pct = round(p_kw / profile.kw_prp · 100, 1)`: 348 кВт → 68,6 %; 507 → 100,0; 0 → 0,0. `fuel_l`: якщо `td_genset` дає літри — вони;
інакше `round(fuel_pct/100 · tank_l, 1)` (82 % → 500,2 л).

### R-04 Критичні споживачі (FR-11)

`codes = [c.strip() for c in param("critical_codes").split(",") if c.strip()]`; `vals = TEL-04(codes)`; `critical_kw = round(Σ value, 1)`
для наявних кодів (незалежно від `status`); `missing = [коди без запису]`. У картці — рядок «Критичні споживачі зараз: 348 кВт з 507 кВт»;
`missing` — у `last_publish_error`? Ні — у `meta`? Ні: у `node["critical_missing"]` (list) провайдера (для діагностики) і в лог DEBUG. Приклад
макета (12.10, 10:30): сума LP-1..3, DUST-1, COMPRESSOR, BOILER, OFFICE, EF-ELEC, EF-CHG + лінія BW-1 = **348 кВт** (`infra.totals.critical_kw`).
`items` картки — `f3d_resolve(<код обладнання з шляху>)`: для `energy/consumers/LP-1/p_now` код `LP-1` → `maintenance.equipment` «Щит освітлення LP-1»;
для `energy/lines/BW-1/p_now` — `BW-1` → обладнання «Шинопровід BW-1» (назви — з бази; код, якщо не знайдено).

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

Острів (`island=True`): `grid = 0`, `export = 0`, `pv = 0` (anti-islanding SUN2000 `0x0303`), `chp = 0` (блокування з ДГУ, Q-02),
`gen = infra/genset/GENSET/p_kw` (сигнал моста), `bess ≤ 0`: на інтервалі пуску (до `breaker=gen`) `bess = −min(200, crit)` = −200
(ПРИПУЩЕННЯ: критична шина тримається накопичувачем, недостача 148 кВт — Q-08), після перемикання `bess = 0`; `load_island = gen + |bess|`;
`shed = max(0, load − load_island)` = 626 − 348 = 278 кВт (некритичні споживачі скинуті). Перевірка балансу в острові:
`gen + |bess| + pv + chp = load_island` → 348 + 0 + 0 + 0 = 348 ✓. Після повернення мережі (`island=False`) — нормальні формули energy.
Ключі, які energy додає в `infra.totals` (CE-03, необов'язково для v1): `shed_kw`, `bess_mode` (`charge`/`discharge`/`idle`).
Автономність в острові: R-02 при 68,6 % і 500 л → 5,2 год; при повному баку 610 л → 6,4 год.

### R-07 Подія контролера → заявка ТО (FR-05, §6.8 каркаса)

1. `row = f3d.genset.event.map._match(ev)` (M-03): `td_code` → `hgm_name` → `match_regex` → `DEFAULT_<severity>`.
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
6. `maintenance.equipment.f3d_meter_signal_id` = сигнал `hours` (виставляється один раз, §5.3 крок 7); поле інтервалу телеметрії — порожнє.

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
| 8 | Критичні споживачі зараз | `"{critical_kw} кВт з {kw_prp} кВт"` → «348 кВт з 507 кВт» |
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

`unit == "%"` → `round(v/100, 3)` (82 → 0.82); інакше `|v| < 20` → `round(v, 2)`, інакше `round(v, 1)`; `kind in (state, counter)` → `int(v)`.
Правило однакове для провайдера (full) і для `signals` у `/delta` (telemetry) — тому після дельти значення не «стрибають».

### R-12 Застарілі дані й офлайн (FR-15)

`fresh = snap["online"] and snap["ts"] and (now − snap["ts"]) ≤ offline_min`. Не `fresh` → `online=0`, `state=0`, `q=0` для всіх показань
(TEL-03 ставить `status="stale"`), `fuel_lph=0`, `autonomy_h` — за останнім `fuel_l` при 75 %. Перехід `online 1→0`, що триває ≥ `offline_min`
(перевірка на кожному прогоні: `last_state_json.offline_since`) → одна подія `COMM_LOST` через R-07 (рядок мапи `COMM_LOST`), подія шини.
Перехід `0→1` → `message_post` у відкриту заявку, подія шини. Часові пояси: усі `ts` у БД — UTC naive (Odoo); `snap["ts"]` з `td_genset`
нормалізується в UTC (якщо aware → `astimezone(UTC).replace(tzinfo=None)`); картка показує Europe/Kyiv (`ctx["now_local"]`-стиль viewer R-02).
Годинник ретранслятора попереду Odoo > 120 с → `ts = now` і `last_publish_error = "годинник ретранслятора попереду на N с"`.

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
9. **Шаблон заявки з невідомим ключем** (`{foo}`) — `SafeDict` → «—», без винятку.
10. **Часові пояси** — R-12; `schedule_date` заявок — UTC naive; `request_date` — дата за Europe/Kyiv (`fields.Date.context_today` з `tz` користувача крона = `Europe/Kyiv`, умовчання `base.user_root` виставити в хуку? — ні: використовувати `datetime.now(ZoneInfo("Europe/Kyiv")).date()` явно).
11. **Кілька зв'язок на одне обладнання** — SQL-обмеження; **одна зв'язка на кілька генераторів** — `td_ref_uniq`.
12. **Провайдер впав** — viewer R-01 ізолює (`meta.sections.infra="error"`, `meta.errors`), картка лишається статичною з моделі.
13. **`fake_relay` без `RELAY_SIM_TOKEN`** — `/sim/v1/*` → 404; iot_sim запасний режим Q-15.

## 12. Acceptance Criteria

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
| AC-11 | FR-04 | Then усі 26 сигналів GENSET мають порожні `warn_low/warn_high/alarm_low/alarm_high/alarm_state` | UT |
| AC-12 | FR-05 | Given подія `{"code":"LOP_SD","severity":"shutdown","name":"Low Oil Pressure","value":0.8,"unit":"бар","threshold":1.0}` і рядок мапи з `hgm_name="Low Oil Pressure"`; When `_cron_events`; Then 1 `maintenance.request`: `maintenance_type='corrective'`, `priority='3'`, `maintenance_for='equipment'`, `equipment_id=GENSET`, `maintenance_team_id=команда обладнання`, `name="Генератор GENSET: аварійна зупинка — низький тиск оливи 0,8 бар при нормі ≥ 1,0 бар"`, `f3d_equipment_code='GENSET'`, `f3d_signal_id=сигнал alarm_level`, `f3d_genset_event_key='GENSET:LOW_OIL_PRESSURE_SD'`, `schedule_date` ≈ now | UT |
| AC-13 | FR-05 | Given та сама подія повторно (новий `id`), заявка відкрита; When крон; Then заявок 1, у чаттері «Повтор: … о …»; When заявку переведено в «Repaired» і подія знову; Then заявок 2 | UT |
| AC-14 | FR-05 | Given подія warning «Gen Over Current» з мапою `bus_only`; When крон; Then заявок 0, `f3d.viewer.event` з `model='maintenance.equipment'`, `codes=['GENSET']`, `kind='state'` | UT |
| AC-15 | FR-05 | Given подія з невідомими `code`/`name` і `severity='shutdown'`; Then рядок `DEFAULT_SHUTDOWN` → заявка `corrective`, пріоритет 3, назва «Генератор GENSET: аварійна зупинка — <name>» | UT |
| AC-16 | FR-05 | Given `requests_enabled=False`; When крон events; Then 0 заявок, `last_event_ts` не зсувається | UT |
| AC-17 | FR-05 | Given 250 подій; When один прогін; Then оброблено 200, `last_event_id` = id 200-ї; другий прогін — решта 50 | UT |
| AC-18 | FR-06 | Given ADP-05 `{hours_now:1213, next_service_hours:1250, interval_h:250, due:False}`, показання `hours` 30 днів тому = 1177; When `_cron_service`; Then 1 заявка `preventive`, `priority='1'`, `name="Генератор GENSET: планове ТО через 37 мотогодин (наступне на 1 250, зараз 1 213)"`, `schedule_date` = now + 30,8 дня (±1 день), `f3d_genset_event_key='GENSET:SERVICE:1250'`, `f3d_signal_id=hours`; повторний прогін — заявок 1 | UT |
| AC-19 | FR-06 | Given `hours_left=-12`; Then `priority='3'`, `schedule_date` ≈ now, назва «…прострочено на 12 мотогодин…»; Given `hours_left=120`, `due=False`; Then заявок 0 | UT |
| AC-20 | FR-06 | Then `maintenance.equipment(GENSET).f3d_meter_signal_id.code == 'infra/genset/GENSET/hours'`, поле інтервалу ТО telemetry порожнє/0 | UT |
| AC-21 | FR-06 | Given `SERVICE_REQUESTS_BY_TD=True` і заявка `td_genset` для GENSET без `f3d_equipment_code`; When крон; Then у неї `f3d_equipment_code='GENSET'`, `f3d_signal_id=hours`; нових заявок 0 | UT |
| AC-22 | FR-07 | Given зв'язка, сигнали з AC-07; When `PayloadBuilder.build(full=True)`; Then `infra.cards.GENSET.rows` = 14 рядків R-10 з очікуваними текстами («634 кВА / 507 кВт (основна)», «під навантаженням · 348 кВт (68,6 %)», «82 % · 500 л», «≈ 5,2 год при 69 %», «348 кВт з 507 кВт»…), `items` = 10 назв, `note` — стала; `infra.genset.GENSET.p_kw=348.0`, `fuel_pct=0.82`, `state=7`, `state_label="під навантаженням"`; `infra.totals.genset_kw=348.0`, `genset_state`, `island`, `grid_ok` | UT |
| AC-23 | FR-07 | Given провайдер `zz_test` у `test_factory3d_viewer`? — ні: Given порядок; Then у `PayloadBuilder.providers` `f3d.viewer.provider.genset` стоїть після `f3d.viewer.provider.infra` (якщо energy встановлено) і після `…signals` (90), `…telemetry` (95); `_f3d_sequence == 155` | UT |
| AC-24 | FR-07 | Given зв'язок немає; When `build()`; Then `infra.cards.GENSET` дорівнює статиці з `model_static.json`, `meta.sections.infra` без `error` | UT |
| AC-25 | FR-07 | Given сигнали `stale` (R-12); Then рядок «Зв'язок: втрачено з HH:MM», `warn` «Зв'язок із контролером втрачено (N хв)», `state_label="немає даних"` | UT |
| AC-26 | FR-07 | Given `ctx.changes={"maintenance.equipment": {"GENSET"}}`; When `_f3d_viewer_delta(patch, ctx)`; Then `patch.infra.cards.GENSET` і `patch.infra.genset.GENSET` присутні, інші картки — ні | UT |
| AC-27 | FR-08 | Given попередній `last_state_json.state=1`; When знімок зі `state=7`; Then 1 `f3d.viewer.event` (`maintenance.equipment`, `['GENSET']`, `state`) і `message_post` у зв'язці; When той самий стан ще раз; Then подій не додається | UT |
| AC-28 | FR-08 | When лише `online` змінився (1→0) без зміни стану; Then подія шини є (R-12), `message_post` — немає | UT |
| AC-29 | FR-09 | Given сигнал `infra/ats/position=3` свіжий, `src1_ok=0`; Then `island=True`, `grid_ok=False`, `source='ats'`; Given `position=2`, `src1_ok=1`; Then `False/True`; Given `position` старіший за 3·period; Then беруться дані контролера (`breaker=2`, `state=7`, `mains_ok=False` → `island=True`, `source='hgm'`); Given контролер офлайн і ATS нема; Then `island` = останній, `grid_ok=None`, `source='stale'` | UT |
| AC-30 | FR-09 | Given `island=True`; Then `infra.totals.grid_kw` **не** змінюється мостом (власність energy), але `infra.totals.island=True`, `genset_kw=348.0`; рядок картки «Мережа: відсутня · острів: генератор живить критичних» | UT |
| AC-31 | FR-10 | Given `amf_master='ats'`; Then рядок «Логіка AMF: ATyS p (головний)»; R-05 результати ті самі, що при `hgm` на тих самих входах | UT |
| AC-32 | FR-11 | Given сигнали критичних з сумою 348 і один відсутній код; Then `critical_kw=348.0`, `infra.genset.GENSET.critical_missing=['energy/lines/BW-1/p_now']`, `items` без назви для відсутнього; `f3d_resolve('LP-1')` → назва обладнання в `items` | UT |
| AC-33 | FR-12 | Given користувач `group_f3d_user`; When `write` зв'язки/профілю/мапи; Then `AccessError`; `group_f3d_manager` — ок; параметри `factory3d.genset.*` у меню «Параметри системи» видно лише `group_f3d_admin` (base) | UT |
| AC-34 | FR-12 | Then `factory3d.genset.write_enabled='False'` після установки; у коді моста немає викликів методів `td_genset` з іменами `start`/`stop`/`command` (grep-тест `test_no_commands`: жоден файл `models/*.py`, `adapters/*.py` не містить `.action_start`, `.action_stop`, `write(` на `GENSET_MODEL` крім ADP-09) | UT |
| AC-35 | FR-13 | When `neutralize.sql`; Then крони моста `active=false`, `read_enabled='False'`, `requests_enabled='False'`, `last_publish_ts` NULL; When `uninstall_hook`; Then параметри `factory3d.genset.%` відсутні, `f3d.signal` GENSET (26) і заявки лишились, джерело `active=False` | UT/TC |
| AC-36 | FR-14 | Given `docker compose --profile demo up genset_relay`; When `td_genset` адреса `http://genset_relay:8000`; Then `td_genset` показує показання профілю D700 (паливо 82 %, 500 л), міст публікує 26 сигналів | TC |
| AC-37 | FR-14 | Given сценарій `blackout` (`amf_master=hgm`); When старт; Then у `fake_relay` через ≤ 35 с `state=loaded`, `breaker=gen`, `p_kw=348`; в Odoo через ≤ 2 хв `infra/genset/GENSET/state=7`, `infra/ats/position=3` (energy), картка «острів», подія шини; When стоп; Then повернення: `state` 8 → 9 → 1, `island=False` | TC |
| AC-38 | FR-14 | Given сценарій `blackout` (`amf_master=ats`) з умовчаннями HGM; Then наказ пуску (`remote_start=true`) через 3 с після втрати мережі, `gen_ok` через ≈ 25 с, переключення через 2AT 5 с; `FAIL START` не виникає; Given пресет HGM `warming_s=60`; Then iot_sim фіксує «FAIL START» через 2ST 30 с (ТК-08) | TC |
| AC-39 | FR-14 | Given `genset_test` (15 хв, `test_on_load=false`); Then `fake_relay.last_test` оновлено, картка «Остання перевірка: <дата> — тест 15 хв, норма», ATyS не перемикався (`position=2`) | TC |
| AC-40 | FR-15 | Given `POST /sim/v1/fault {"alarm":"comm_lost"}`; When ≥ `offline_min` (5 хв; на стенді `RELAY_TIME_FACTOR=10` або `offline_min=1`); Then `online=0`, усі 26 сигналів `stale`, заявка «Генератор GENSET: втрачено зв'язок з контролером (немає даних N хв)» з ключем `GENSET:COMM_LOST`; When `clear`; Then `online=1`, у заявці «Зв'язок відновлено о …», заявка відкрита | TC/UT |
| AC-41 | FR-16 | grep `models/`, `views/`, `data/`: усі `string=`, `help=`, тексти `UserError`/`ValidationError`, назви крона/меню — кирилицею (regex `[А-Яа-яІіЇїЄєҐґ]`), файлів `i18n/*.po` у модулі немає | UT (grep-тест) |
| AC-42 | FR-02, CR-05 | When `action_export_relay_profile`; Then вкладення `d700.json` з ключами §8.2, `fuel_lph.75=103.8`, `timers.mains_abnormal_s=5`; When `action_apply_to_td` з мок ADP-09 → `True`; Then повідомлення «Записано в td_genset: 1 генераторів; пропущено: 0» | UT |
| AC-43 | ADP | Given константи адаптера не заповнені; When `test_adapter_contract`; Then тест падає з переліком `ADP-01, ADP-03…`; Given заповнені (мок реєстру); Then усі `FIELD_*` є у `fields_get` відповідної моделі | UT |
| AC-44 | R-03 | Given `fields_get` селекції стану `td_genset` (мок: 6 значень); Then кожне значення є ключем `STATE_MAP` (тест перелічує відсутні) | UT |
| AC-45 | R-11 | When провайдер отримує `fuel_pct=82`, `p_kw=348.04`, `oil_bar=4.456`, `hours=1213.2`; Then `0.82`, `348.0`, `4.46`, `1213` | UT |
| AC-46 | R-12 | Given `snap.ts` = now + 300 с (годинник ретранслятора попереду); Then показання з `ts=now`, `last_publish_error` містить «годинник ретранслятора попереду» | UT |
| AC-47 | API-F | ТК-F (§13.2): `GET /sim/v1/state` без токена → 401; `POST /load {"kw": 600}` → 422; `POST /remote_start` у `mode=manual` → 409; `POST /fuel {"liters": 700}` → 422; `POST /reset {"preset":"plant"}` → таймери пресету | TC |
| AC-48 | §8.3 | Given профіль d700, `POST /mains {"available": false}`; Then послідовність станів `mains_abnormal`(5 с) → `starting` → `safety_on`(10) → `warming`(10) → `running` → `loaded` з `breaker=gen`, усього 29–32 с при `factor=1`; `starts` +1; з `preset=plant` — 13–16 с; `fuel_l` зменшується на 95,5/3600 л за секунду при 348 кВт (±2 %) | TC |
| AC-49 | §8.3 | Given `POST /fault {"alarm":"start_fail"}` і `POST /mains {"available": false}`; Then 3 спроби по 8 с + 10 с пауза → `state=alarm_shutdown`, подія `Fail to Start` severity shutdown у `GET /sim/v1/events` | TC |
| AC-50 | §5.3 | Given копія демо-бази з base + telemetry + td_genset; When установка моста; Then кількості §5.3 (1 профіль, 1 джерело, 26 сигналів, 45 рядків мапи, 3 крони); повторне `-u` — ті самі кількості, `td_code` рядків мапи збережені | TC |
