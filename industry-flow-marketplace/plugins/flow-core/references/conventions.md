## 3. Спільні конвенції пакета

Джерело правди конвенцій — `flow-core/references/conventions.md`; інші плагіни копіюють стислий витяг у свій `README.md`, а кожен скіл має стандартний розділ **«Наряд і звіт»** (5–7 рядків): «Вхід — наряд задачі Odoo (поля §3.1), читає `flow-core:flow-step-runner`; результат — файли за `where` наряду в гілці кроку; звіт і PR — пише `flow-step-runner`, цей скіл його не пише; поза `flow-step-runner` скіл не запускати (файли конвенцій `flow-core/references/` розв'язуються лише через його теку контексту); усі виклики `odoo-mcp` — з `connection_id` з наряду».

### 3.1 Формат наряду Odoo (що читає агент)

Наряд — задача `project.task` у проєкті пакета або клієнта внутрішньої бази флоу. Агент читає **структурований YAML-блок у `description`** (стійко до назв кастомних полів; технічні імена полів Odoo фіксує C-00 і експортує в `flow/ODOO_SCHEMA.md` — скіли на них не спираються, лише дзеркалять ключові поля для фільтрів черги). Ключі блоку:

```yaml
step: A-12                      # код кроку (картка)
scope: {kind: package|client, id: <пакет|ідентифікатор клієнта за DATA_POLICY>}
executor: any|central|human
skill_ref: ["flow-package-build:config-as-code@0.1.0", "odoo19-mvp-build:config-review@1.4.0"]
model: sonnet            effort: medium
inputs:                          # з карток: inArtifacts; SHA фіксує оркестратор
  - {name: ALLOCATION.md, from: A-10, path: package/ALLOCATION.md, sha: <commit>}
where: package/config/           # куди писати результат
template: package/templates/<…>  # або "немає — створити"
done: "<критерій «Готово, коли» з картки>"
check: {mode: auto|human|both, how: "<checkHow картки>", audit_every_n: 10}
limits: {max_attempts: 3, timeout_min: 90, cost_limit_usd: 15, context_budget_tokens: 120000}
human_sla: "2 робочі дні"        # лише для гейтів/людських кроків
client_data: none|commercial|personal
data_rule: "<посилання на розділ DATA_POLICY>"
odoo_connections:                # allow-list для odoo-mcp на цей запуск; порожньо = odoo-mcp заборонено
  - {alias: flow, purpose: наряд/звіт}
  - {alias: test-<клієнт>, purpose: тестова база}
repo: {url: <github>, base_branch: main, branch: flow/<крок>-<scope>-<спроба>}
attempt: 1                       # ставить оркестратор; збільшується при повторі
returned_from: null              # код кроку/гейта, що повернув, і текст зауваження
```

Стадії задачі (назви фіксує C-00, семантика стала): `Черга → В роботі (оренда до <час>) → Автоперевірка → На рішенні людини → Готово | Повернено | Ескалація | Зупинено (стоп-лист)`. Гейт — окрема задача з кнопкою «Затвердити / Повернути», чек-листом з `checkHow`, полями «що виправлено в результаті AI», «зауваження до скіла (так/ні)». **AI не має прав на кнопку й не пише в поля рішення/підпису.**

### 3.2 Формат звіту в задачу

Після кожного запуску `flow-step-runner` постить у чаттер задачі (`message_post`) один блок і оновлює стадію:

```yaml
run: {step: A-12, scope: package/<id>, attempt: 1, started: <ISO>, finished: <ISO>}
result: done|returned|escalated|stopped     # returned_to: <код кроку>; escalated_to: <роль>
pr: <url>                                    # або null для кроків без змін у репо
skill_versions: {"flow-package-build:config-as-code": "0.1.0", …}   # фактично встановлені
model: {primary: sonnet, review: opus|null}
usage: {tokens_in: …, tokens_out: …, cost_usd: …, agent_hours: 0.4}
checks: [{id: VP-coverage, status: PASS}, {id: lint, status: FAIL, msg: "…"}]
data_sources: ["aikb:doc_…", "fathom:recording_…", "odoo-mcp:test-<клієнт>", "repo:package/SPEC.md@<sha>"]  # лише ідентифікатори
memo: |                                      # пам'ятка перевіряльнику — спочатку невпевненість AI
  Невпевнений: …
  Що змінилось: …   Де ризик: …   Що перевірити: …
observations: []                             # шляхи записів skill-feedback, якщо людина повернула
```

Пам'ятка дублюється в описі PR (`package/templates/pr-checklist.md`). Години людини — табель Odoo, агент їх не вигадує.

### 3.3–3.6 Звірка версії, стоп-лист, `connection_id`, дані клієнта
Єдине джерело — `data-and-connections.md` (§3.3 звірка `скіл@версія`, §3.4 стоп-лист C-08, §3.5 правило `connection_id` і класи баз, §3.6 дані клієнта). Тут не дублюється, щоб тексти не розходились.
