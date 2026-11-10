# Модель стану: подія → поля Odoo

Технічні імена — лише з `flow/ODOO_SCHEMA.md` (читається один раз за запуск; `flow-core/references/odoo-bridge.md` §1–§2). Нижче — логічні імена. Немає файлу → працює лише `record` з логічними іменами, у звіті `partial: true` і перелік не записаного (`flow-state.md` §5). Стан клієнта й прапорці — `flow-state.md` §1.

## 1. Подія → що записується
| Подія (джерело) | Куди | Що |
|---|---|---|
| `run:` у чаттері задачі кроку | задача кроку | дзеркальні поля запуску (§2), маркер `c02:recorded <message_id>;` (при неповному записі — `c02:partial <message_id>;`) |
| `dispatch:` у чаттері C-01 | задача кроку (за `step`, `scope`, `task_id`) | стан: створено / відкладено / заблоковано рішенням <роль> / стоп-лист; `units_N` |
| кнопка гейта (§4) | журнал рішень проєкту (+ «Параметри флоу», реєстр питань) | рядок журналу |
| подія з `event-rules.md` | проєкт клієнта (`project.state`) | стан + дата + «підтверджено PM» = ні |
| табель задачі кроку | посилання з задачі кроку | суми `unit_amount` за задачею й роллю/`employee_id`; `name` табеля не читати. Табель — `account.analytic.line` з `task_id` (модуль `hr_timesheet`, на задачі `timesheet_ids`) |

Стадії задачі в тексті — **логічні** (`stage.done`, `stage.returned` …); технічні назви ставить C-00 (`ODOO_SCHEMA`).

## 2. Обов'язкові поля запуску
`step, scope, attempt, started, finished, result (done|returned|escalated|stopped|waiting_human), skill_versions (точний semver),
usage.cost_usd, usage.tokens_in, usage.tokens_out, pr (url або null з причиною), data_sources`.
Умовні: `returned_to` (реальний код картки) при `returned`; `escalated_to` + дата при `escalated`; `waiting_for` {role, what, resume} при `waiting_human`;
непорожній `data_sources` при `client_data: personal`; `stop_reason` при `stopped`. Необов'язкові, які переносяться: `phase`, `release`, `attempts_in_run,
returns, models_used, audit`. Поля, яких немає, — не добудовувати: `run_status: неповний`. `waiting_human` — штатний результат (не помилка, `attempt` не росте): записати стан
«очікує людину» + `waiting_for.role`; `waiting_human` без `waiting_for` — невалідний звіт (`run_status: неповний`).
Фаза: A-18 `phase: tag` — крок «тег виставлено» фіксується в полі `package_tag` пакета лише за `release.tag` зі звіту й `release.sha`; тег сам не ставити.

## 3. Білий список `flow/runs/<YYYY-MM>.md`
Колонки — `export-format.md`: `step, scope, attempt, result, skill_versions, usage, задача`. **Не експортувати:** `memo`, `checks[].msg`, тексти зауважень,
`observations` (лише лічильник), будь-які поля клієнта поза ідентифікатором за DATA_POLICY.

## 4. Рішення людини й типи записів журналу
Правило розрізнення рішення й коментаря — `odoo-bridge.md` §5 (не копіюємо): `mail.message` на задачі гейта з `message_type = notification` і `tracking_value_ids`
для `gate.decision`/`stage_id`; `author_id` (`res.partner`) ∉ множини `partner_id` користувачів `project.flow_agent_users` (`res.users`; `odoo-bridge.md` §6). Роль у ростері — `res.users` за `partner_id = author_id`; `date` = час кнопки; значення — `new_value_char`. `message_type = comment` — ніколи не рішення.
Домен: `mail.message`: `[["model","=","project.task"],["res_id","=",<id гейта>],["message_type","=","notification"],["tracking_value_ids","!=",false]]`, далі `mail.tracking.value` за `mail_message_id`.
Перелік `project.flow_agent_users` порожній або недоступний → записувати рішення лише від автора, явно відомого в ростері як людина; інакше рішення **не записувати**,
активність Керівнику напряму, `partial: true`. Центральний агент і агенти співробітників — різні користувачі, усі в переліку.
Рядок журналу: колонки `flow-state.md` §3 (`№, дата, гейт/крок, scope, рішення, куди повернуто, роль автора, задача, коментар ≤200 без ПІБ/контактів/сум`).
Типи: гейт кроку; шлюз «Потрібні сесії з еталонними клієнтами?» (критерій і роль); вікно поставки в прод; зняті відхилення при оновленні (B-11, фаза 0); параметр флоу; закриття відкритого питання.

## 5. Ключі
Подія: `task_id + message_id` (маркер `c02:recorded <id>;` у чаттері, `SKILL.md` Крок 1). Рядки експорту — `export-format.md`.

## 6. Межі стану
Поля клієнта (крок пулу B, прапорці, планові дати) — лише в проєкті клієнта. У рядку/проєкті пакета — лише стан пакета (`package_tag`, `candidate_tag`, фаза, `flow_version`).
Планові дати — з Planning, SOW (B-03), `leadDays` карток; завантаження ролей — перелік, не розрахунок.
