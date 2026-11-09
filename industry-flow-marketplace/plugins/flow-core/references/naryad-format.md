# Формат наряду Odoo

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

