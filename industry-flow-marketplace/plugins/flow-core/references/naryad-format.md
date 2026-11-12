# Формат наряду Odoo

### 3.1 Формат наряду Odoo (що читає агент)

Наряд — задача `project.task` у проєкті пакета або клієнта внутрішньої бази флоу. Агент читає **структурований YAML-блок у `description`** (стійко до назв кастомних полів; технічні імена полів Odoo фіксує C-00 і експортує в `flow/ODOO_SCHEMA.md` — скіли на них не спираються, лише дзеркалять ключові поля для фільтрів черги). Ключі блоку:

```yaml
step: A-12                      # код кроку (картка)
scope: {kind: package|client, id: <пакет|ідентифікатор клієнта за DATA_POLICY>}
executor: any|central|human
access_profile: base|mail|research|research-internal|content|outreach|drive|repo   # агент-виконавець за ведучим скілом (step-skill-map.md); немає ключа = base
skill_ref: ["flow-package-build:config-as-code@0.1.0", "odoo19-mvp-build:config-review@1.4.0"]
called_skills: []               # необов'язково: ["плагін:скіл@semver"] — скіли, які ведучий (skill_ref[0]) викликає у своєму запуску; не гейти
model: sonnet            effort: medium
inputs:                          # з карток: inArtifacts; SHA фіксує оркестратор; для A-03b…A-21c обов'язково OWNER-INTAKE.md (docs/industries/<галузь>/OWNER-INTAKE.md)
  - {name: ALLOCATION.md, from: A-10, path: package/ALLOCATION.md, sha: <commit>}
where: package/config/           # куди писати результат
template: package/templates/<…>  # або "немає — створити"
done: "<критерій «Готово, коли» з картки>"
check: {mode: auto|human|both, how: "<checkHow картки>", audit_every_n: 10}
limits: {max_attempts: 3, timeout_min: 90, lease_factor: 1.5, cost_limit_usd: 15, context_budget_tokens: 120000}   # оренда = timeout_min x lease_factor (odoo-bridge §7)
human_sla: "2 робочі дні"        # лише для гейтів/людських кроків
client_data: none|commercial|personal|internal-aggregated|internal-raw   # personal -> executor: central; виняток q01: B-13/B-08a на test-<клієнт> — будь-який агент
data_rule: "<посилання на розділ DATA_POLICY>"
preconditions_confirmed: {crm_deal_stage: discovery_signed|sow_signed, by: <роль>, at: <дата>}   # q10: ознака стадії угоди в CRM; `discovery_signed` — угода дискавері підписана (наряд B-02), `sow_signed` — SOW підписано (B-04/B-06/B-11 і суміжні); назва стадії CRM, що відповідає значенню, — C-00; вписує C-01 з дзеркального поля
review:                          # лише кроки з рецензентом (К-/N-03): чек-листи й ліміти кругів
  checklists: [<файл з <FC>/references/review-checklists/>]
  max_rounds: 2                  # = defaults.rounds.review_max анкети OWNER-INTAKE.md (типово 2); + 1 контрольний круг (разом ≤3); human_rounds > 2 -> сигнал C-08R (метрика, не цільове число)
odoo_connections:                # allow-list для odoo-mcp на цей запуск; порожньо = odoo-mcp заборонено
  - {alias: flow, purpose: наряд/звіт}
  - {alias: test-<клієнт>, purpose: тестова база}
  - {alias: own-erp, purpose: читання внутрішніх даних ToDo (лише читання; лише профіль research-internal; поле todo_data анкети)}
  # q37, лише наряд client-help-bot: - {alias: prod-ro-<клієнт>, purpose: читання (client-help-bot)}
repo: {url: <github>, base_branch: main, branch: flow/<крок>-<scope>-<спроба>}
attempt: 1                       # ставить оркестратор; збільшується при повторі
returned_from: null              # код кроку/гейта, що повернув, і текст зауваження
```

Стадії задачі (назви фіксує C-00, семантика стала): `Черга → В роботі (оренда до <час>) → Автоперевірка → На рішенні людини → Готово | Повернено | Ескалація | Зупинено (стоп-лист)`. Гейт — окрема задача з кнопкою «Затвердити / Повернути», чек-листом з `checkHow`, полями «що виправлено в результаті AI», «зауваження до скіла (так/ні)». **AI не має прав на кнопку й не пише в поля рішення/підпису.**


## Додаткові ключі наряду (необов'язкові; відсутність ключа не є помилкою)

```yaml
params:                          # блок режимів кроку; ставить оркестратор за картками й flow-map.md
  mode: <рядок>                  # режим скіла (див. таблицю нижче)
  phase: <рядок>                 # фаза кроку (A-14: 1|2; A-18: release|tag)
  flow_version: 1|2              # версія флоу в gates-aggregator; немає ключа = 2
  period: {month: "2026-10", start: <дата>, end: <дата>}   # D-01 report, B-10 sla-month
  pilot: true|false              # крок для пілотного клієнта
  addendum_source: <шлях|код>    # B-03 mode: addendum
  group: <ключ>                  # злиття паралельних нарядів
  resume: {…}                    # перезапуск після waiting_human (зразок кроків із `params.sample: true` (за замовчуванням A-21, A-21c; A-03b і A-20c — лише на явний запит): `{sample: false}`; анкета A-02b: що саме прийшло від людини + посилання на повідомлення)
  sample: true|false             # зразок (N-18) перед повним обсягом; зразок за замовчуванням лише A-21, A-21c (A-03b, A-20c — `false`, `true` лише на явний запит або для першої галузі); обсяг — з картки (`step-cards.md`); зразок -> waiting_human, повний обсяг — resume з `sample: false`
  lessons: [LSN-NNN, …]          # C-04 (eval-builder): уроки з `eval_статус: запропоновано`, з яких робити евал-кейси; без ключа eval-builder weekly підбирає їх сам
  stale: [<шлях>, …]             # mode: recalc: застарілі артефакти цього кроку-власника (збігаються з `where`)
  reconcile: true|false          # B-11 фаза 1: звірка (у B-06 режим звірки — `mode: reconcile`)
  maturity: <0..3>               # C-07: поточна зрілість кроку (для maturity_proposals)
  # mode: recalc — перерахунок застарілого (N-07): один наряд на крок-власник (за flow/ARTIFACTS.md); список — `stale:` зі звіту наряду, де runner виконав check_stale.py (research/DEPENDS.yaml); порядок кроків — за DEPENDS.yaml; ключ ідемпотентності (step, scope.id, mode=recalc, base_sha)
git:                             # SHA для автоперевірок; заповнює runner після створення гілки
  base: <sha>                    # git merge-base head origin/<base_branch>
  head: <sha>                    # вершина repo.branch
  prev_tag: <package/vX.Y|null>  # попередній тег для A-18, D-03, B-11
date: <ISO-дата>                 # дата запуску (run.started); дати документів беруть звідси
```

Значення `params.mode` (оркестратор виводить за картками; якщо ключ відсутній — значення за замовчуванням):
| step | mode | коли | за замовчуванням |
|---|---|---|---|
| A-08 | `перша`, `нова-версія` | `нова-версія` — від D-04/D-05; | `перша` |
| A-14 | `перевірка`, `повернення`, `нова-версія`, `hotfix` | ставить C-01 за `returned_from` і джерелом; | `перевірка` |
| A-17, A-18 | `перша`, `нова-версія`, `hotfix` | A-18 hotfix — від A-19; | `перша` |
| A-09 | `first`, `review` (через `phase: review`) | `review` — оркестратор після `resume` | `first` |
| A-12 | `build`, `fix`, `new-version`, `validate` | `fix` — повернення з A-14; `new-version` — від D-04/D-05 | `build` |
| A-15, A-22 | `перша`, `нова-версія` | `нова-версія` — змінені AC і `git.prev_tag` | `перша` |
| A-02b | `prepare`, `validate` | `prepare` -> (власник заповнює 6 пунктів ≤5 хв: `waiting_human`+`resume`) -> `validate`; правка анкети після старту = новий `validate` (режиму `amend` немає) | `prepare` |
| A-03b | `—`, `recalc`; `params.sample: false` (за замовчуванням; `true` лише на явний запит) | K1 і питань власнику немає (рішення AI -> AI-DECISIONS); повний обсяг без зупинки (зразок — лише за явного `sample: true`: профіль одного конкурента + 10 рядків матриці -> `waiting_human`); `recalc` — за `params.stale` | `—` (`sample: false`) |
| A-03c | `—` | один наряд: `## Інвентар` і рішення AI «беремо / адаптуємо / ні» в `REUSE.md` (рядки AI-DECISIONS; без сесії й гейта) | `—` |
| A-20, A-20c | `main`, `recalc`; A-20c ще `params.sample: false\|true` (`true` лише на явний запит) | `recalc` — за `params.stale` (N-07; для A-20 `where` завжди містить `research/AI-DECISIONS.md`, і в main, і в recalc); A-20c: одразу повний обсяг і гейт (зразок першого екрана — лише за явного `sample: true`) | `main` (`sample: false`) |
| A-21 | `main`, `recalc`; `params.sample: true\|false` | зразок (`sample: true`) -> `waiting_human` -> повний обсяг; `defaults.prototype.fidelity: mock` -> `waiting_human` (К-23) | `—` (`sample: false`) |
| A-21c | `main`, `recalc`; `params.sample: true\|false` | зразок (15 с + 1 кадр титра) -> `waiting_human` -> повний обсяг; перемонтаж без перезйомки й без доступу до Odoo | `—` (`sample: false`) |
| C-08R | `daily`, `event` | `daily` — за розкладом; `event` — «Повернути», `escalated`, червоний CI, `human_rounds > 2` | `daily` |
| A-23 | `список`, `адреси`, `prep`, `results` | `список` -> `prep` (другий наряд); `адреси` — коли `список` у `waiting_human` (потрібні адреси), executor: central; `results` — після збору сигналів | `список` Для `prep` `inputs` містить `research/AI-DECISIONS.md` з SHA (рядки з A-23 у «Перевірка» -> `risk-plan.md`). |
| B-08a | `звірка`, `збіжність` | `збіжність` — другий наряд після APPROVE-звірки (`config-drift.md` на вході) | `звірка` |
| B-06 | `mode`: `main\|reconcile\|return` | `reconcile` — звірка після міграції; `return` — з `returned_from` | `main` |
| C-04 | `weekly`, `init`, `regress` | `weekly` — за розкладом; `init`, `regress` ставить лише AI-інженер (нова модель/версія плагіна) | `weekly` |
| C-07 | `incident` | після розбору `boost:debug-root-cause` у `flow/ai-incidents/<id>.md` | `incident` |
| D-03 | `prepare`, `verify` | `verify` — після `prepare` і рішення людини | `prepare` |
| B-03 | `main`, `addendum` | `addendum`, якщо step = B-11, або в `inputs` є `ТР-доробок.md`/`CHANGELOG.md`/підписаний `sow.md`; `main`, якщо `clients/<к>/sow.md` немає | `main` |
| B-07 | `prepare`, `answer` | `answer` лише коли в SOW є розділ бота й `prepare` = done; `period: {month, start, end}`; `params.handoff: help-log.md#HB-NNN` — вхід `support-desk` intake | `prepare` |
| B-09 | `intake`, `hypercare-close` | `hypercare-close` — минуло 14 днів без критичних або граничний строк | `intake` |
| B-10 | `intake`, `sla-month` | `sla-month` — на початку місяця, `period` = попередній місяць | `intake` без `period`; щомісячний запуск за розкладом без `period` -> попередній календарний місяць |
| D-01 | `collect`, `report` | N нарядів `collect` (scope client; `odoo_connections`: лише `flow`; дані — з вивантаження людини за `params.upload_path`, без файлу — `waiting_human`), після всіх `done` один `report` (scope package) | немає значення = стоп, питання Тімліду |
| D-02 | `mode`: `a\|b\|c\|d`; `phase`: `draft\|post-sign`; `trigger_ref`, `markers` | `a` — після D-01/B-01(б) за розкладом; решта — за подією | `a` |
| B-11 | `phase: 0\|1`, `pilot`, `reconcile` | `reconcile` — звірка після B-06 фази 1 | `phase: 0` |

**Решта кроків** (A-01, A-04, A-05/B-01 segment-selector: `mode`, `phase`, `size`, `seed`, `regions`, `extra_kved`; D-04/D-05 product-decision-drafter; A-13, A-20/A-21, A-23 demand-test-runner: `mode`, `round`, `final`, `start_sha`; B-02; B-04/B-13/B-08a runbook-executor): режими й ключі `params` описані в `SKILL.md` відповідного скіла, оркестратор бере їх із картки кроку; відсутній ключ -> значення за замовчуванням зі скіла.

Правила виведення, коли ключа немає (скіл не зупиняється й не питає):
- `flow_version` відсутній -> 2; `mode` A-14 відсутній -> `перевірка`; у версії 1 підкрок Тімліда — задача `human_substep` (`flow-step-run.md` §3), знайдена за `parent_id` = id наряду й стадією `stage.done`.
- `date` — з поля `date` наряду, інакше з `run.started` першого звіту; з пам'яті не брати.
- Для `inputs`, де SHA не вказано, runner ставить `origin/<base_branch>` на момент запуску й записує в `git.base`.
- Прямі ключі `mode`/`period`/`pilot` верхнього рівня (старі наряди) читаються як `params.*`.

`called_skills`: runner звіряє їхній semver так само, як `skill_ref` (Крок 3), але не запускає як гейти (Крок 9 (д) бере лише `skill_ref[1:]`). Джерело — примітка в `step-skill-map.md`.

Запис наряду в Odoo, розекранування `description`, дзеркальні поля — `odoo-bridge.md` §3. Шаблони задач наряду/гейта/ролі — `flow-step-run.md`.


## Команди й записи в Odoo, які виконує runner (виконавець їх не має)
Виконавець (`flow-core:flow-executor`) без Bash і без `odoo_write/create/execute`. Тому: (а) команди скіла — рядок відповіді «КОМАНДИ: …» (для C-04/C-07 дозволено лише `claude plugin eval|list`, `git`, `jq`); (б) виклики запису в Odoo — рядки «ODOO: {tool, connection_id, model, method, args}». Runner виконує їх на кроці 8–9, повертає вивід виконавцю й лише якщо `connection_id` у `odoo_connections` наряду належить класу `test-*`, `test-pkg-*`, `demo-*` чи `emu-*` з `purpose` запису (`data-and-connections.md`); `flow`, `prod-ro-<клієнт>` і будь-який прод — відмова для рядків «ODOO:», `escalated` (виконавець нічого не пише; `prod-ro-<клієнт>` лише читається самим скілом `client-help-bot` через `odoo_search_read`/`odoo_get_fields`). Рішення q13: записи в `test-*`, `test-pkg-*`, `demo-*`, `emu-*` виконує runner за рядками «ODOO:» і allow-list, окремого агента немає. **Прод-alias (`prod-*`) в `odoo_connections` наряду заборонено; єдиний виняток (q37) — `prod-ro-<клієнт>` у наряді, де `skill_ref[0]` = `flow-client-delivery:client-help-bot` і `purpose: читання (client-help-bot)`; інакше наряд → відмова, `escalated`; жодних «за рішенням».**
