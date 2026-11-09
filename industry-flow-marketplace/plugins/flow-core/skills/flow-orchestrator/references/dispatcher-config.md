# Шаблон `package/flow/dispatcher.yaml`

Змінюється лише PR з рецензією Тімліда, не в запуску C-01. Значення нижче — пропозиції; звірити з картками перед першим запуском.

```yaml
role_pairs:                       # кому ескалювати, коли raciA не відповів 2×humanSla
  Власник продукту: Керівник напряму
  Керівник напряму: Власник продукту
  Архітектор рішення: Власник продукту
gate_owners_raciA:                # звірити з картками
  A-02: Власник продукту
  A-07: Власник продукту
  A-17: Власник продукту
  D-02: Власник продукту
  B-02: Керівник напряму
  B-03: Керівник напряму
  A-10: Архітектор рішення
catalog: {repo: "<org>/industry-flow-marketplace", ref: "<тег або SHA каталогу>"}   # джерело plugin.json для skill_ref
per_unit_steps: [D-01, B-10, B-09]   # кроки "на одиницю": ліміти x N; звірити з картками
periodic:
  monthly_first_workday: [D-01, B-01(b), D-02(a)]   # порядок обов'язковий
  monthly_per_client_on_support: [B-10]
  daily_per_client_in_hypercare: [B-09]
  weekly: [C-04]
lease_factor: 1.5                 # термін оренди = timeoutMin x factor
unclaimed_after_minutes: 60
parallelism: {per_package: 3, per_client: 1}
work_calendar: {timezone: Europe/Kyiv, workdays: [Mon, Tue, Wed, Thu, Fri], holidays: "Відкрите питання: джерело календаря"}
```
