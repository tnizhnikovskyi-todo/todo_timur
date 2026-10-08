# Security Review: td_genset (Odoo 18.0 / Community)

Reviewing diff after: pr-review APPROVE — `git diff d062947..c4cf9b3 -- smartgen/td_genset`
(гілка `claude/dreamy-ramanujan-p2wlej`, HEAD `c4cf9b3`)
Engine: Step A — сканер мовного рівня (ін'єкції, `eval`/десеріалізація, секрети, XSS-синки) +
Step B — Odoo-чекліст (ACL, record rules, `sudo()`, SQL, контролери/RPC, bus/websocket, токен, групи на кнопках).
Reviewer: security-review (скіл; одиночний прохід, без раунду критиків і KB).
Дата: 07.10.2026. Код не змінювався; живі перевірки — на власних базах `td_sec_a`/`td_sec_b`
(видалені після аудиту) з локальним емулятором `tools/fake_relay.py`; до реального ретранслятора звернень не було.

---

## Verdict: BLOCK

Одна експлуатована вразливість (VULN-1): публічні методи клієнта ретранслятора `td.genset.relay.client`
доступні через стандартний JSON-RPC будь-якому автентифікованому користувачу — Співробітнику і навіть
внутрішньому користувачу без жодної групи модуля — в обхід пульта, `_td_check_group`, `commands_allowed`,
`remote_lock`, стану зв'язку і журналу команд. Підтверджено на живій базі. Решта матриці прав
(ТР 2.2/2.5, SPEC §7) витримана.

Підсумок: VULN[1] / REQUIRED[0] / WARNING[5] / SUGGESTION[4]. Після виправлення VULN-1 (одна правка,
перевірена на копії модуля: RPC заблоковано для всіх ролей, кнопки й 16 наявних тестів працюють) — APPROVE.

---

## 1. Access control (`ir.model.access`)

**PASS.** `security/ir.model.access.csv` — 34 рядки; усі 15 звичайних моделей і 4 майстри мають ACL.
`td.genset.relay.client` — AbstractModel без таблиці (ACL не застосовний — див. VULN-1).
Матриця збігається зі SPEC §7:

| Модель | С | А | Т | Примітка |
| --- | --- | --- | --- | --- |
| `td.genset` | R | R | CRWU | `commands_allowed` — `groups='td_genset.group_tech'` у моделі й поданні (`genset.py:156–159`, `genset_views.xml:428`) |
| `td.genset.reading` | R | R | R+U | списки `create="0" edit="0" delete="0"` |
| `td.genset.event` / `.alarm` | R | R | RWU | «Прийняв» — метод, не ACL (§3) |
| `td.genset.command` | R | R | R | ніхто не має C/W — створює лише код через `sudo()` (`genset_command.py:326–374`) |
| `.schedule` / `.schedule.exception` | R | CRWU | CRWU | |
| `.config` | R | R | RW | `create`/`unlink` немає ні в кого — singleton захищений |
| `.notify.level`, `.controller.model` | R | R | CRWU | |
| `.storage.location`, `.canister`, `.refuel` | R | CRWU | CRWU | |
| `.fuel.move` | R | R+C | R+C+U | див. WARNING-3 |
| `.fuel.calibration` | R | R | CRWU | |
| майстри | timer — С | refuel, receipt — А | command — Т | усі 4 TransientModel мають ACL |

- Групи існують і є в `depends` (`base`, `maintenance`); `group_user → group_admin → group_tech` через
  `implied_ids` (`groups.xml:14, 21, 28`). `base.group_public`/`base.group_portal` — нічого не надано.
- Live (60 RPC-проб, ролі С / А / Т / С-поза-ланцюжком / внутрішній-без-груп): усі заборонені
  `create`/`write`/кнопки → `AccessError` без змін у базі; для С `read` поля `commands_allowed` → `AccessError`;
  дозволене за матрицею (таймер — С; розклад, майстри палива — А; пульт, калібрування, налаштування — Т) працює.

## 2. Record rules & cross-record access

**PASS** (SUGGESTION-1). Record rules немає — свідоме рішення SPEC §7 / `genset.py:110–112` (одна компанія).
Власницького скоупу специфікація не вимагає; портальних/публічних моделей немає.
Bus-канал генератора: `ir_websocket.py:18–35` перетворює `td_genset_<id>` на запис лише після
`has_access('read')`, публічного користувача відкидає. Live (websocket): С отримав 3 повідомлення
`td_genset.update` (`alarm`, `reading`) на `td_genset_1`; внутрішній користувач без груп модуля на тому ж
каналі — 0; неіснуючий id відкидається.

- **SUGGESTION-1** — `models/genset.py:110–112` (`company_id`), `genset_fuel.py:349–351` (`currency_id`).
  Сценарій: поява другої компанії — усі генератори/паливо видно всім. Виправлення (у single-company нічого
  не змінює): `security/record_rules.xml` з глобальним правилом
  `['|', ('company_id', '=', False), ('company_id', 'in', company_ids)]` для `td.genset` і правилом по
  `genset_id.company_id` для дочірніх моделей.

## 3. `sudo()` audit

**PASS.** ~170 викликів; усі належать до двох задокументованих патернів (SPEC §7, А.10): «технічні записи
після перевірки прав» і «cron/обробник від суперкористувача». Перевірено:

- кожна кнопка/майстер перевіряє групу в Python **до** `sudo()` через `_td_check_group` (`genset.py:593–601`):
  пульт — `genset_scheduler.py:516`, `command_wizard.py:145`; тест — `genset_scheduler.py:360`; таймер —
  `:250, :282, :314, :530–558`, `timer_wizard.py:47`; паливо — `refuel_wizard.py:125`,
  `fuel_receipt_wizard.py:112`, `genset_fuel.py:315`; тех. дії — `genset_monitoring.py:473, :525`,
  `genset_fuel.py:902`, `genset_config.py:248`;
- «Прийняв» — `genset_alarm.py:360–382`: `_can_ack` = учасник ланцюжка (`config.level_ids.user_id`) або
  `group_tech`, інакше `AccessError`; live: С-поза-ланцюжком → `AccessError` (прямий `write(state)` →
  `AccessError` за ACL), С у ланцюжку → ok, А/Т → ok (AC-43);
- жоден `sudo()` не виконує пошук/запис за доменом чи значеннями від користувача без перевірки
  (аргументи майстрів — selection/float з валідацією; `_enqueue`/`_raise`/`_post` отримують записи);
- `maintenance_ext.py:43–69` — `sudo()` після стандартного `write` заявки ТО (див. WARNING-2);
- `get_pult_state` (`genset_ui.py:155–165`) робить `check_access('read')`; токена/адреси у відповіді немає (live).

Зауваження: окремі `sudo()` без власного коментаря — обґрунтування в docstring методу; для нових методів
тримати той самий патерн («Права перевіряє викликач»).

## 4. Injection & unsafe evaluation

**PASS.** Увесь сирий SQL — `odoo.tools.SQL` з параметрами, ідентифікатори лише з констант модуля
(`SQL.identifier`): `genset_reading.py:629–633` (`init`, `sql.create_index`), `:833–843` (`_mark_journal`),
`:864–888` (чистка: параметри, `unlink` за списком id), `genset_fuel.py:947–993` (перерахунок літрів:
`before_id`/`limit` — int, `VALUES` через параметризований `SQL`), `genset_event.py:231–266`,
`genset_command.py:441–458`, `genset_alarm.py:393–398`, `genset_scheduler.py:68`, `genset_monitoring.py:96, :343`.
`eval`/`safe_eval`/`pickle`/`yaml`/`subprocess` — відсутні. Домени/`order` з `kwargs` не будуються.
HTML: `current_data_html` (`genset.py:555–557`, `sanitize=False`) — обчислюване, не зберігається, не пишеться
користувачем; значення з `last_values_json`/ретранслятора проходять `markupsafe.escape` або `Markup % …`
(`genset_ui.py:307–559`); OWL-шаблон пульта без сирого HTML. `fields.Json` — `readonly`, пише лише cron.

## 5. Controllers & routes

**PASS щодо контролерів, BLOCK щодо RPC-поверхні.** `@http.route`/`Controller` у модулі немає. Але Odoo 18
дозволяє через `/web/dataset/call_kw` викликати будь-який публічний метод будь-якої моделі, зокрема
AbstractModel (`odoo/service/model.py:get_public_method` блокує лише імена з `_` і `@api.private`);
ACL до AbstractModel не застосовуються, тож єдиний захист — приватність методу.

### VULN-1 — BLOCK — `models/relay_client.py:163–226`

- **Що:** сім публічних методів `td.genset.relay.client` — `status` (:163), `device_status` (:168),
  `latest` (:176), `readings` (:186), `post_command` (:205), `command` (:217), `commands` (:222) — без
  префікса `_` і без `@api.private`; перевірок груп усередині немає (за контрактом А.11 права перевіряє
  викликач — cron/майстер), адреса й токен читаються через `sudo()` (:89, :104).
- **Наслідок:** `post_command` надсилає команду контролеру поза стан-машиною команд (`_enqueue`/`_precheck`):
  без `_td_check_group('td_genset.group_tech')`, без `commands_allowed`, `remote_lock`, стану зв'язку,
  без запису в `td.genset.command` і чатер (немає сліду, хто й що надіслав) — порушення AC-24, AC-56, AC-66.
  Методи читання розкривають дані ретранслятора (`/status`, знімки, журнал команд) користувачам, які не
  мають навіть права читання `td.genset`; `readings(limit)` — неконтрольоване навантаження на ретранслятор.
  Поверхня `auth='user'` охоплює й портальних користувачів, якщо колись буде встановлено `portal`.
- **Підтверджено live** (`td_sec_a`, локальний емулятор): для ролей С, А і внутрішнього користувача без
  груп модуля виклик пройшов; емулятор зафіксував 3 команди з ознакою RPC-походження; у `td.genset.command`
  — 0 записів; ті самі користувачі отримали відповіді `status`/`latest`/`readings`/`commands`.
- **Виправлення:** додати `@api.private` (Odoo 18, `odoo/api.py:448`) над `@api.model` для всіх семи
  методів — імена А.11 зберігаються, Python-виклики з cron/майстрів/кнопок не змінюються. Додати регресійний
  тест у `tests/test_w3_security.py::TestW3SecurityRpc`: RPC-виклик `post_command` і `status` від С (і від
  користувача лише з `base.group_user`) → `AccessError`.
- **Перевірка виправлення** (копія модуля з патчем, `td_sec_b`): RPC-виклики `post_command`/`status`/`readings`
  для С/А/Т/без-груп → `AccessError «Private methods … cannot be called remotely»`; кнопка «Перевірити
  зв'язок» (Т) працює; `TestW1RelayClient` + `TestW3Security` + `TestW3SecurityRpc` — 16 тестів, 0 помилок.

## 6. Secrets, fields & irreversible ops

**PASS** (із WARNING). Токен і адреса — лише `ir.config_parameter` (ACL `base.group_system`; `get_param` робить
`check_access('read')` — live: С/А/Т → `AccessError`); блок налаштувань `groups="base.group_system"`
(`res_config_settings_views.xml:12`), поле-пароль, `get_values` не повертає токен, порожнє значення не затирає
(`res_config_settings.py:35–48`; live: `default_get`/`create` → `AccessError`, `get_values()` → `{}`).
`relay_client.py:101–110, :131–138`: заголовки не логуються, у винятках — метод/шлях/статус/`error`
без адреси й токена; `verify=True`, `timeout=(5, http_timeout)` (:127–130). Секретів/ключів у коді й XML немає;
тести — домен `.test` і фіктивні токени. Cron (`data/ir_cron.xml`) — від `base.user_root`, усі точки входу
приватні, винятки перехоплені. Чистка (`genset_reading.py:864–888`) обмежена терміном зберігання, 0 вимикає,
не чіпає журнальні/посилані знімки. Перерахунок літрів — лише Т, повторюваний.

- **WARNING-1** — `README.md:33`: у документації модуля вказано адресу API продового ретранслятора.
  Сценарій: модуль передається клієнту/підряднику разом з README. Виправлення: замінити на плейсхолдер
  (`https://<адреса ретранслятора>/api/v1`), адреса — лише в системних параметрах (як і каже `res_config_settings.py:10`).
- **WARNING-2** — `models/maintenance_ext.py:33–41` + стандартний ACL `maintenance.request`
  (`base.group_user`: CRWU). Сценарій: будь-який внутрішній користувач (не лише Т) переводить заявку ТО
  генератора у «виконано» → `_td_on_done` через `sudo()` скидає відлік ТО і знімає тривогу `maintenance_due`.
  Це узгоджено зі SPEC §7 («`maintenance.*` — стандартні групи»), але суперечить матриці «ТО — Т».
  Виправлення (якщо потрібна матриця): у `MaintenanceRequest.write` для заявок з `td_genset_id` при зміні
  `stage_id` на `done` вимагати `td_genset.group_tech` (або `maintenance.group_equipment_manager`), якщо не `env.su`.
- **WARNING-3** — `models/genset_fuel.py:323–477`, ACL `access_td_genset_fuel_move_admin` (C). Сценарій: А через
  імпорт/RPC створює `td.genset.fuel.move` напряму (live: ok), обминаючи `_post` — запас у каністрах
  перестає дорівнювати Σ рухів (інваріант модуля). Виправлення: у `TdGensetFuelMove.create` дозволяти лише
  з контексту `_post` (ключ на кшталт `td_fuel_posting`) або `env.su`, інакше `UserError`.
- **WARNING-4** — `ondelete='cascade'` на `genset_id`: `genset_command.py:141`, `genset_alarm.py:106`,
  `genset_event.py:65`, `genset_reading.py:202`, `genset_fuel.py:536, :721`, `genset_schedule.py:74, :117`.
  Сценарій: Т видаляє генератор (ACL U) — безповоротно зникає журнал команд, тривог і подій (аудит дій).
  Виправлення: `@api.ondelete(at_uninstall=False)` на `td.genset` — заборонити `unlink`, якщо є команди/події
  («архівуйте замість видалення»), або `ondelete='restrict'` для `td.genset.command`/`.alarm`/`.event`.
- **WARNING-5** — `security/groups.xml:14`: `group_user` імплікує `base.group_allow_export`. Експорт
  дозволяється для всіх моделей, які користувач читає (контакти, користувачі тощо), не лише для показань/подій.
  Рішення менеджера (AC-59) — зафіксувати в документації впровадження як відоме розширення прав.

- **SUGGESTION-2** — `models/res_config_settings.py:42–48`: після `set_param` токен лишається у стовпці
  транзієнтної таблиці `res_config_settings` до vacuum (читає лише `base.group_system`). Виправлення: після
  збереження `settings.td_genset_relay_token = False`.
- **SUGGESTION-3** — `models/genset_monitoring.py:43` (`_mail_post_access = 'read'`): С може `message_post`
  з будь-яким підтипом, зокрема `td_genset.mt_alarm` (live: ok) — підписники підтипу «Тривога» отримають
  повідомлення, схоже на тривогу (автор — користувач). Виправлення: перевизначити `message_post` на `td.genset`
  і для не-`su` дозволяти лише `mail.mt_note`/`mail.mt_comment`.
- **SUGGESTION-4** — `models/relay_client.py:127`: `requests.Session()` з `trust_env=True` — `.netrc`/проксі з
  оточення сервера можуть підмінити `Authorization`. Якщо проксі не потрібен — `session.trust_env = False`.

---

## Summary

Модуль побудовано за правильною схемою: ACL мінімальні й повні, кожна кнопка перевіряє групу в Python до
`sudo()`, SQL параметризований, токен не витікає ні у форму, ні в логи, bus-канал закритий правом читання.
Деплоювати не можна через одну дірку: клієнт ретранслятора є AbstractModel з публічними методами, і Odoo віддає
їх через RPC будь-кому, хто залогінений, — команда контролеру без прав і без сліду. Виправлення — `@api.private`
на сім методів `relay_client.py` плюс регресійний тест; після цього (і бажано WARNING-1) — APPROVE.
WARNING-2…5 і SUGGESTION — у беклог на розсуд менеджера.

## Додаток. Що підтверджено живими перевірками

База `td_sec_a` (модуль з HEAD), користувачі: С у ланцюжку, А у ланцюжку, Т, С поза ланцюжком, внутрішній
користувач лише з `base.group_user`; генератор із `commands_allowed`, локальний емулятор ретранслятора.

| Перевірка | Результат |
| --- | --- |
| С/А/без-груп: RPC `td.genset.relay.client.post_command` / `status` / `latest` / `readings` / `commands` | **пройшло — VULN-1** |
| С/А/Т: `ir.config_parameter.get_param(relay_token)`, `search_read`; `res.config.settings.default_get`/`create` | `AccessError` |
| С: `get_pult_state` | ok, без токена/адреси |
| С/А: `action_open_command_wizard`, `td.genset.command.wizard.create`, `td.genset.command.create` | `AccessError` |
| С: `schedule`/`schedule.exception`/`refuel`/`fuel.move`/`fuel.calibration`/`notify.level` `create`; `canister.write`, `action_write_off`; `config.write`, `action_send_test_notification`; `td.genset.write`, `read(commands_allowed)`; `action_check_relay`, `action_recompute_liters` | `AccessError` |
| С: `action_refresh`, `action_open_timer_wizard`, `timer.wizard.create` | ok (за матрицею) |
| А: `config.write`, `action_send_test_notification`, `td.genset.write`, `action_check_relay`, `action_recompute_liters`, `fuel.calibration.create` | `AccessError` |
| А: `schedule.create`, `refuel.wizard.create`; `fuel.move.create` напряму | ok (останнє — WARNING-3) |
| Т: `action_open_command_wizard`, `command.wizard.create`, `config.write` | ok |
| «Прийняв»: С поза ланцюжком → `AccessError`; С/А у ланцюжку, Т → ok | відповідає AC-43 |
| Websocket `td_genset_<id>`: С — отримує `td_genset.update`; без-груп — ні | відповідає А.9 |
| Копія модуля з `@api.private` (`td_sec_b`): RPC до клієнта → `AccessError` для всіх ролей; кнопка Т працює; 16 тестів W1/W3 — 0 помилок | виправлення підтверджено |

---

## Статус виправлень (08.10.2026)

**Вердикт після виправлень: APPROVE.** VULN-1 закрито; WARNING-1…5 і SUGGESTION-2 виконано за рішенням
менеджера; SUGGESTION-1, -3, -4 — у беклог (див. нижче). Гілка `claude/dreamy-ramanujan-p2wlej`, коміти після
`9628f48` (без push).

| Знахідка | Що зроблено | Коміт | Регресійний тест |
| --- | --- | --- | --- |
| **VULN-1** (BLOCK) | `@api.private` над `@api.model` для всіх семи методів `td.genset.relay.client` (`status`, `device_status`, `latest`, `readings`, `post_command`, `command`, `commands`); імена А.11 ті самі, Python-виклики з cron, майстрів і кнопок не змінилися | `a925f7e` | `TestW3SecurityRpc.test_ac24_ac66_relay_client_not_callable_over_rpc`: С, А, Т і внутрішній користувач без груп модуля × 7 методів через `/web/dataset/call_kw` → `AccessError` «Private methods … cannot be called remotely», команда не створюється |
| WARNING-1 | `README.md`: адреса API — плейсхолдер `https://<relay-host>/api/v1`, адреса проду — лише в системних параметрах | `b66ddc3` | — |
| WARNING-2 | `maintenance_ext.py`: заявку з `td_genset_id` переводить у стадію «виконано» (і створює одразу в ній) лише `td_genset.group_tech`, інакше `AccessError` з поясненням; заявки іншого обладнання — стандартні права | `260205a` | `TestW3Security.test_ac56_maintenance_done_only_tech` |
| WARNING-3 | `genset_fuel.py`: `td.genset.fuel.move.create` — лише з контексту `td_genset_post`, який ставить `_post`; інакше `UserError` «Рух запасу створюється лише через заправку/надходження/коригування» | `0a0f998` | `TestW3Security.test_ac49_fuel_move_only_via_post` |
| WARNING-4 | `genset.py`: `@api.ondelete(at_uninstall=False)` — генератор зі знімками, подіями, тривогами, командами, заправками або рухом палива не видаляється («Архівуйте генератор замість видалення»); `ondelete='cascade'` дочірніх лишився (чистий генератор видаляється) | `28547e8` | `TestW3Security.test_ac56_genset_with_history_not_deleted` |
| WARNING-5 | `base.group_allow_export` у групі «Співробітник» лишається (рішення щодо AC-59); у `README.md` модуля — розділ «Права: важливо знати» з описом розширення прав і способом його прибрати | `b66ddc3` | `TestW3Security.test_ac59_export_template_all_values` (група приходить через `implied_ids`) |
| SUGGESTION-2 | `res_config_settings.py`: після `set_values` поле токена транзієнтного запису очищується — у таблиці `res_config_settings` токена немає | `eb4078e` | `TestW3Security.test_ac57_settings_token_never_returned` (стовпець `NULL` після `execute()`) |
| i18n | нові тексти помилок — у `i18n/uk_UA.po` (1853 рядки, без порожніх і `fuzzy`) | `0e2ff05` | — |

**Перевірка:** `run_tests.sh td_int_c` (HEAD `0e2ff05`) — код 0, 147 тестів, 0 помилок, без WARNING/ERROR;
`update.sh td_int_c` — код 0; `run_stand_tests.sh td_int_c_stand` — 45/45. Контрольний прогін п'яти регресійних
тестів на коді без виправлень (моделі відкочено, тести ті самі) — усі 5 падають, тобто тести ловлять саме ці дірки.

**Беклог (не робили, за рішенням менеджера):** SUGGESTION-1 — правила за компаніями (`record_rules.xml`) на
випадок другої компанії; SUGGESTION-3 — обмежити підтипи `message_post` для не тех. користувачів
(`_mail_post_access = 'read'`); SUGGESTION-4 — `requests.Session.trust_env = False` у клієнті ретранслятора.
