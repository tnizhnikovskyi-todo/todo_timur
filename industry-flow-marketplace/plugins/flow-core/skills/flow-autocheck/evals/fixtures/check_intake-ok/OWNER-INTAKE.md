# Анкета власника: тестова галузь (вигадана)

```yaml
editions*: both            # ce|ee|both
icp*: {min_employees: 20, legal_forms: [ТОВ], light_tariff_fop: true}
todo_data*: {allowed_sources: [own-erp, fathom], mode: read, internal_raw_storage: repo-sources, push_deidentified: true}
brand*: {materials: todo, demo_client: "вигаданий клієнт"}   # todo|white_label
materials*: {formats: [video_16x9, reels_9x16, one_pager], languages: [uk]}
do_not_do: [Бухоблік повний]
demo_edition: ce
ee_bridges: later
tariffs: "вхід власника: легкий тариф для ФОП"
defaults:
  market: {country: UA, language: uk, localization: "UA-локалізація", accounting_system: "1С", accounting_mode: exchange}
  ambition: {company_marking: true, trials: deferred, sessions_a05_a06: false}
  rounds: {review_max: 2, review_control: 1}
```
