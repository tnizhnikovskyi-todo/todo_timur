# Анкета власника: тестова галузь (вигадана)

```yaml
editions: both            # ce|ee|both
ee_bridges: later
demo_edition: ce
market: {country: UA, language: uk, localization: "UA-локалізація", accounting_system: "1С", accounting_mode: exchange}
icp: {min_employees: 20, revenue_min: 10000000, legal_forms: [ТОВ], light_tariff_fop: true}
ambition: {scope: full, evidence_gate: risk, company_marking: true, trials: deferred, sessions_a05_a06: false}
pricing: {ce_entry: 50000, ee_upgrade: 20000, box_fixed_price: true, pilot: true}
todo_data: {allowed_sources: [own-erp, fathom], mode: read, internal_raw_storage: repo-sources, push_deidentified: true}
do_not_reject:
  items: [Конфігуратор виробу, Облік залишків]
  class_rule: "не відкидати без рішення K1"
  n: 2
```
