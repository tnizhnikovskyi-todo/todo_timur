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

