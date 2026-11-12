# Анкета власника (фікстура: валідна, company_marking: false, схема 0.3.0)

```yaml
editions: both                 # * ce|ee|both — для яких редакцій Odoo будуємо пакет
demo_edition: ce                # ce|ee — редакція зрізу A-21 (замовчування ce)
ee_bridges: now                 # now|later — мости EE (замовчування now)
icp:
  min_employees: 10             # поріг ICP: працівників
  legal_forms: [ТОВ, ФОП]       # юридичні форми клієнтів
  light_tariff_fop: true        # чи потрібен «легкий» тариф для ФОП
  # revenue_min — лише якщо власник сам дав
todo_data:
  allowed_sources: [crm, fathom, unitalk, aikb, gmail, own-erp]  # які внутрішні джерела ToDo дозволено читати
  mode: read                    # лише читання
  internal_raw_storage: repo-sources   # internal-raw лежить у research/sources/ репо галузі
  push_deidentified: true       # чи можна пушити знеособлені висновки в репо галузі
brand:
  materials: todo               # todo|white_label — бренд матеріалів
  demo_client: вигаданий        # бренд демо-клієнта
materials:
  formats: [video_16x9, reels_9x16, mobile, one_pager]
  languages: [uk]
do_not_do: []                   # що точно не робимо (може бути порожнім); кожен пункт -> рядок REJECTED із причиною «рішення власника»
tariffs: ""                     # необов'язково: вільний текст власника; AI не рахує й не обґрунтовує, лише цитує в BOX §1

defaults:                       # заповнює AI; власника не питаємо; ключі читають інші скіли
  market:
    country: Україна
    language: uk
    localization: l10n_ua
    accounting_system: BAS/BAF  # галузеве: для нової галузі — уточнити + рядок AI-DECISIONS
    accounting_mode: exchange   # exchange|replace
  ambition:
    company_marking: false      # чи розмічати компанії сегмента (segment-selector)
    trials: deferred            # no|deferred|yes
    sessions_a05_a06: false     # чи потрібні сесії A-05/A-06 з еталонними клієнтами
  licenses:
    own_modules: LGPL-3
    oca: idea                   # idea|dependency
  reuse:
    repos: "—"                   # GitHub-репо ToDo з готовими модулями; "—" якщо немає
    projects: "—"                # коди проєктів/ERP; "—" якщо немає
  prototype:
    fidelity: real-slice
    new_record_in_frame: false
  legal_ambiguous:
    to_answers_yaml: true
  rounds:
    review_max: 2
    review_control: 1
```
