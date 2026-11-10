# Формат звіту в задачу

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


## Доповнення до формату звіту

`result` має п'ять значень:
```yaml
result: done|returned|escalated|stopped|waiting_human
returned_to: <код кроку>        # якщо returned
escalated_to: <роль>            # якщо escalated
waiting_for: {role: <роль RACI>, what: "<одна дія людини>", resume: {step: A-14, params: {phase: 2}}}   # якщо waiting_human
phase: <рядок|null>             # фаза кроку, якщо в наряді params.phase
flow_version: 1|2|null          # лише gates-aggregator
release: {tag: package/vX.Y, sha: <sha>, command: "git tag -a … && git push origin <тег>"}   # A-18 phase: tag, інакше null
project_fields: {test_tag: <тег>} # структурований запис для поля проєкту; пише runner/state-keeper, не скіл
partial: false                  # true — звіт неповний (state-keeper: що не записано, перелік у memo)
```

`waiting_human` — штатний результат («очікує людину»), а не помилка: крок не провалено, але далі без людини не рухається (приклади: застосувати конфіг у тестовій базі, внести значення джерела від BA, дані від клієнта, підкрок Тімліда в A-14 версії 1). Обробка:
- runner: постить звіт, ставить стадію `stage.on_human` (не `stage.escalation`), оренду знімає, `attempt` не збільшує;
- оркестратор (`flow-map.md`, правило 6): створює задачу `human_substep` з `waiting_for.what` для ролі `waiting_for.role` і дедлайном за `human_sla` (`flow-step-run.md` §3); після її `stage.done` створює наряд того самого кроку з `params.resume`;
- прострочення `human_sla` -> активність Тімліду; `waiting_human` без `waiting_for` — невалідний звіт (`escalated`).
Правило оркестратора (flow-map.md, правило 6): `waiting_human` ніколи не створює наступника за `flow-map.md` — лише перезапуск того самого кроку.

`returned` — крок повернув вихідну задачу попередникові (`returned_to`), `escalated` — виконати неможливо (ліміти, невідповідність наряду, немає прав/конфігу, невизначене технічне ім'я з `ODOO_SCHEMA`); `stopped` — стоп-лист.

Звіт постить runner (`odoo-bridge.md` §4): YAML у `<pre><code class="language-yaml">`, екранований.

## Блок `evals:` (eval-builder, C-04/C-07)
```yaml
evals: {mode: weekly|incident|init|regress, cases_new: <n>, cases_red_new: <n>, not_reproduced: <n>,
        regress: {pass: <n>, fail: <n>, skipped_requires: <n>}, fix_list: ["<плагін:скіл@версія>"], declined_obs: [],
        maturity_proposals: [{step, kind: downgrade|upgrade, from, to, reason, evidence, condition, regress_run}],
        open_questions_review: <дата|null>, partial: false}
```
Блок пише скіл `eval-builder`, звіт постить runner; детальні поля — `eval-builder/SKILL.md`, «Наряд і звіт».

## Доповнення runner
Додаткові ключі звіту (пише runner):
```yaml
attempts_in_run: 1            # спроб у цьому запуску
models_used: [sonnet]         # фактично задіяні моделі
routing: {…}                  # вибір щабля моделі (flow-step-runner/references/routing-and-tag.md)
audit: PASS|FAIL|null         # результат аудиту; audit_failed: <що не пройшло>
untrusted_instructions: []    # інструкції з недовірених даних, які проігноровано
lease: {until: <ISO>, agent: <id>}
stop_reason: null             # для result: stopped
cost_estimated: false         # true — вартість оцінена, а не виміряна
base_sha: <sha>               # SHA бази, на якій працював runner
```
