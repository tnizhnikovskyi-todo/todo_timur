# Міст до Odoo: як агент і оркестратор читають і пишуть задачі флоу

Спільний контракт `flow-core:flow-orchestrator`, `flow-core:flow-step-runner`, `flow-core:flow-state-keeper` і скілів, що читають поля проєкту клієнта. Власник файлу — `flow-core` (не C-00). C-00 лише створює Odoo-об'єкти й віддає технічні імена в `flow/ODOO_SCHEMA.md`.

## 1. Правила, що діють завжди
- Кожен виклик `odoo-mcp` — з явним `connection_id` (alias `flow` для внутрішньої бази флоу) з `odoo_connections` наряду; без нього заборонено (CONCEPT §3.5). Після виклику перевірити `connection` у відповіді.
- Агент **не вгадує** технічні імена кастомних полів і стадій. Читає їх один раз за запуск з `flow/ODOO_SCHEMA.md` на SHA з наряду (`inputs`) і працює через логічні імена (§2). Немає файлу або потрібного логічного імені — `result: escalated`, `escalated_to: Тімлід`, у memo «визначає C-00: <логічне ім'я>; до того — стоп і питання Тімліду». Не створювати поля, не підбирати схожі.
- Стандартні (не кастомні) поля Odoo 19 можна використовувати за їх іменами: `project.task`: `name`, `description`, `stage_id`, `project_id`, `parent_id`, `user_ids`, `date_deadline`, `tag_ids`, `message_ids`; `mail.message`: `model`, `res_id`, `message_type`, `subtype_id`, `author_id`, `date`, `body`, `tracking_value_ids`; `mail.tracking.value`: `field_id`, `old_value_char`, `new_value_char`, `mail_message_id`; `mail.activity`: `res_model`, `res_id`, `activity_type_id`, `summary`, `note`, `date_deadline`, `user_id`.
- Видалення — ніколи (CONCEPT §3.5). Запис у чужі задачі й у поля рішення/підпису заборонено.

## 2. Логічні імена -> технічні (карта, яку C-00 має віддати в `flow/ODOO_SCHEMA.md`)
Формат `flow/ODOO_SCHEMA.md`: таблиця `логічне ім'я | модель | технічне ім'я / значення | тип | примітка`. Обов'язкові рядки (без будь-якого з них відповідний режим зупиняється):

| Логічне ім'я | Що це | Хто читає |
|---|---|---|
| `stage.queue`, `stage.in_progress`, `stage.autocheck`, `stage.on_human`, `stage.done`, `stage.returned`, `stage.escalation`, `stage.stopped` | `project.task.stage_id` (назви й id стадій §3.1 CONCEPT) | усі |
| `task.step` | код кроку (A-12) | оркестратор, runner |
| `task.executor` | `any/central/human` | оркестратор, runner |
| `task.client_data` | `none/commercial/personal` | оркестратор, runner |
| `task.scope_kind`, `task.scope_id` | `package|client`, ідентифікатор | оркестратор |
| `task.attempt` | номер спроби | оркестратор |
| `task.lease_until` | кінець оренди (datetime) | runner, оркестратор (sweep) |
| `task.kind` | `step` (наряд) / `gate` (гейт) / `human_substep` / `role_task` | оркестратор |
| `gate.decision` | відстежуване поле рішення гейта (значення `approve/return`) | оркестратор, flow-state-keeper |
| `gate.return_to`, `gate.comment` | куди повернути, текст зауваження | оркестратор |
| `gate.fixed_in_ai_result`, `gate.skill_feedback` | поля гейта «що виправлено», «зауваження до скіла» | flow-state-keeper, eval-builder |
| `project.state` | стан клієнта (B-01…B-13) | flow-state-keeper, support-desk, package-usage-metrics |
| `project.test_tag` | тег тестової установки (B-04) | runbook-executor (через runner), package-upgrade-runner |
| `project.package_tag`, `project.candidate_tag` | поточний і кандидатний тег пакета | package-upgrade-runner |
| `project.pilot` | позначка пілотного клієнта | support-desk, package-usage-metrics |
| `project.gmail_label` | відображувана назва мітки Gmail (не Label ID; у `search_threads` `label:` збігається за назвою) | support-desk |
| `project.contract_file_id` | file id договору на Drive | support-desk |
| `project.go_live` | дата go-live | support-desk, usage-metrics |
| `project.aggregates_consent` | згода на агрегати (пункт SOW) | package-usage-metrics |
| `project.ai_stop`, `project.ai_stop_reason` | ознака стоп-листа | runner, оркестратор |
| `project.flow_agent_users` | перелік технічних користувачів агентів (§6) | flow-state-keeper |

Поля `project.*` для клієнта фіксує C-00; поки їх немає в `ODOO_SCHEMA.md`, скіл-споживач читає автоекспорт `clients/REGISTRY.md` (формат — `flow-state.md`) лише як fallback для читання й позначає це в memo.

## 3. Читання наряду з `project.task`
`description` — поле Html. Контракт запису: оркестратор пише наряд **одним блоком** `<pre><code class="language-yaml">…YAML…</code></pre>` (YAML екранований як HTML: `&lt; &gt; &amp; &quot;`). Алгоритм читання (виконує runner, інші скіли отримують уже розібраний наряд):
1. `odoo_search_read` `project.task`, `domain=[["id","=",<id>]]`, `fields=["name","description","stage_id","parent_id","project_id", + технічні імена з §2]`.
2. У `description` знайти перший блок `<pre>…</pre>`; немає — перший ```` ```yaml ````-блок у тексті; немає обох — `escalated` («наряд без YAML-блоку»).
3. Зняти теги (`<br>`/`</p>`/`</div>` -> `\n`, решту тегів прибрати), `html.unescape`, прибрати ` `. Парсити `yaml.safe_load`; помилка парсингу — `escalated` з номером рядка, наряд не «лагодити».
4. Звірити дзеркальні поля (`task.step`, `task.executor`, `task.client_data`, `task.attempt`) із YAML: розбіжність — YAML недійсний, `escalated`.
5. Перевірити обов'язкові ключі за `naryad-format.md`; відсутні необов'язкові — значення за замовчуванням звідти ж.
Ключ `preconditions_confirmed.crm_deal_stage` (`discovery_signed` для B-02, `sow_signed` для B-04/B-06/B-11; пише C-01 з дзеркального поля стадії угоди CRM, q10) читається з YAML наряду; AI сам CRM не читає. Назва стадії CRM — з `flow/ODOO_SCHEMA.md` (C-00).
Ключі з `params:` (naryad-format.md) читаються так само; їхня відсутність не є помилкою.

## 4. Звіт у задачу
- `message_post` на `project.task` (id наряду): `body` = `<pre><code class="language-yaml">…блок з report-format.md, екранований…</code></pre>`, `message_type = "comment"`, `subtype_xmlid = "mail.mt_note"` (внутрішня нотатка), автор — технічний користувач агента. Один запуск = один повідомлення-звіт; повторний пост із тим самим `run.started` не робити (§7).
- Після звіту — зміна `stage_id` на стадію за `result` (done -> `stage.autocheck` або `stage.on_human` за `check.mode`; returned -> `stage.returned`; escalated/waiting_human -> `stage.escalation`/`stage.on_human` за report-format.md; stopped -> `stage.stopped`). Стадію ставить лише runner, гейти — людина.
- Читання останнього звіту: `odoo_search_read` `mail.message`, домен `[["model","=","project.task"],["res_id","=",<id>],["message_type","=","comment"],["body","ilike","run:"]]`, `order="id desc"`, `limit=5`; взяти перший, у якому після розекранування є YAML-ключ верхнього рівня `run:`.

### 4.1 `human_substep` для зразка й анкети; кнопка «вето»
- Зразок кроків із `params.sample: true` за карткою (A-03b, A-20c, A-21, A-21c) і заповнення анкети (A-02b) — `waiting_human` -> задача `human_substep` для власника/BA; відповіді власника фіксуються як повідомлення на цій підзадачі, їх посилання йде в `params.resume` і в журнал рішень (`flow-state.md` §3, режим `veto-batch`, лише для анкети й вето A-20c).
- Вето власника на A-20c = `mail.message` на задачі `human_substep`, автор — з ростера ролі `waiting_for.role`, зміна поля `<task.decision_batch>` (назву фіксує C-00 в `ODOO_SCHEMA`; до того — відкрите питання). Коментар без зміни поля не є рішенням: стоп, питання власнику. Далі власник одним натисканням підтверджує вето/анкету; AI вносить рядки в `flow/decisions.md` лише за цим повідомленням із позначкою «внесено AI від імені власника» (К-08). Немає кнопки в схемі — стоп і питання Тімліду (як у §5).

## 5. Як відрізнити рішення людини від коментаря
Рішення гейта = `mail.message` на задачі **гейта** (`task.kind = gate`), для якого одночасно:
- `message_type = "notification"` і `tracking_value_ids` містить запис з `field_id` = поле `gate.decision` або `stage_id` (перехід у `stage.done`/`stage.returned`);
- `author_id` не належить жодному технічному користувачу агента (§6);
- `date` = час натискання кнопки; значення рішення — `new_value_char` запису tracking.
Домен пошуку: `[["model","=","project.task"],["res_id","=",<id гейта>],["message_type","=","notification"],["tracking_value_ids","!=",false]]`, далі `odoo_search_read` `mail.tracking.value` за `mail_message_id in <ids>` для `field_id`, `old_value_char`, `new_value_char`.
`message_type = "comment"` (чаттер, «Затверджую», «ок») **ніколи** не є рішенням: це зауваження, яке читається як текст і не запускає перехід. Якщо поле/кнопки гейта в схемі немає — стоп і питання Тімліду. Агент не натискає кнопки й не пише в `gate.*` та поля підпису.

## 6. Технічні користувачі агентів
Перелік — логічне ім'я `project.flow_agent_users` (або група Odoo «Агенти флоу», яку створює C-00): `res.users`, які агенти використовують для `message_post`/запису стадій. Правило «автор рішення ≠ технічний користувач агента» перевіряється за цим переліком. Немає переліку — вважати рішенням лише записи з `author_id`, що явно людина за переліком ролей RACI у `flow/ODOO_SCHEMA.md`; інакше стоп. Центральний агент і агенти співробітників мають різні користувачі; `executor: central` перевіряється за користувачем, під яким працює runner.

## 7. Ідемпотентність і оренда
- Ключ запуску: `(task_id, attempt, run.started)`. Перед `message_post` перевірити §4 (останній `run:`): якщо вже є звіт з тим самим `attempt` і `finished` — не постити вдруге, лише виправити стадію.
- Оренда: перехід `stage.queue -> stage.in_progress` разом із записом `task.lease_until = now + limits.timeout_min x limits.lease_factor` (фактор — з наряду, за замовчуванням 1,5 з `dispatcher-config.md`); робити в одному `odoo_write`. Читання стадії перед записом; стадія вже не `queue` — задачу взяв інший агент, зупинитися без запису.
- `sweep` оркестратора: задачі в `stage.in_progress` з `lease_until < now` (лише це порівняння, без власної формули) — повернути в `stage.queue` з `attempt+1` (якщо `attempt` ≤ `limits.max_attempts`), інакше `stage.escalation` і активність Тімліду.
- Створення задач оркестратором ідемпотентне за ключем `(step, scope.id, attempt, scope-ключ злиття)`; для `params.mode: recalc` — `(step, scope.id, mode=recalc, base_sha)` (по одному наряду на крок-власник застарілих артефактів): перед створенням `odoo_search_read` задач із тим самим ключем у будь-якій стадії, крім `stage.returned`.

## 8. Активності (`mail.activity`)
Створює оркестратор (не runner). Виняток (q23): `FLOW_STOP` кроку 0 runner — активність AI-інженеру створює runner, за наявності права в технічного користувача (`c00-checklist.md`, п. q23). Оркестратор створює: `odoo_create` `mail.activity` з `res_model="project.task"`, `res_id`, `summary` (≤80 символів), `note` (що трапилось, `from`, `result`), `date_deadline` (дедлайн = сьогодні + `human_sla` у робочих днях; без `human_sla` — наступний робочий день), `user_id` — виконавець ролі за `ODOO_SCHEMA` (немає відповідності ролі — Тімлід). Використовується для: переходу, якого немає в `flow-map.md` (стоп + активність Тімліду), ескалацій, прострочення `human_sla`, нагадувань гейтам.
