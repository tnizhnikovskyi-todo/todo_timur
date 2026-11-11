# Анкета власника (фікстура: невалідна, порожні блокуючі поля)

```yaml
editions: maybe                 # * ce|ee|both — для яких редакцій Odoo будуємо пакет (CE — основа; EE — окремі модулі td_*_ee, К-06)
ee_bridges: now                # * now|later — мости EE будувати з першого релізу чи пізніше
demo_edition: ce               # * ce|ee — на якій редакції знімаємо зріз A-21 (EE — лише позначкою)
market:
  country: уточнити              # країна ринку
  language: uk                  # мова інтерфейсу й матеріалів
  localization: l10n_ua         # локалізація Odoo (уточнити, якщо інша)
  accounting_system: BAS/BAF    # система обліку клієнта
  accounting_mode: exchange     # exchange|replace — обмін з обліковою системою чи заміна
icp:
  min_employees: 10             # поріг ICP: працівників
  revenue_min: 0                # мінімальна виручка, грн (0 — без порога)
  legal_forms: [ТОВ, ФОП]       # юридичні форми клієнтів
  light_tariff_fop: true        # чи потрібен «легкий» тариф для ФОП
ambition:
  scope:                   # full|mvp — обсяг концепції
  evidence_gate: risk           # risk|block — брак доказів = ризик у план перевірки (risk) чи стоп (block)
  company_marking: false        # чи розмічати компанії сегмента (segment-selector)
  trials: deferred              # тріали: no|deferred|yes
  sessions_a05_a06: false       # чи потрібні сесії A-05/A-06 з еталонними клієнтами (шлюз «Потрібні сесії?»)
pricing:
  ce_entry: true                # CE — вхідний продукт
  ee_upgrade: true              # EE — апгрейд
  box_fixed_price: "коробка A"  # коробка з фіксованою ціною (варіант)
  pilot: "платний зі знижкою"   # модель пілоту
todo_data:
  allowed_sources: [crm, fathom, unitalk, aikb, gmail, own-erp]  # які внутрішні джерела ToDo дозволено читати
  mode: read                    # лише читання
  internal_raw_storage: repo-sources   # де лежить internal-raw: research/sources/ у репо галузі (К-07, К-19)
  push_deidentified: true       # чи можна пушити знеособлені висновки в репо галузі
do_not_reject:
  items: [конфігуратор, обрізки, міграція даних, дашборд керівника, кілька юросіб, премії/штрафи, якість з фото]  # замовчування «меблів»; позиції, які не відкидати без власника
  class_rule: "усе, що є у ≥N конкурентів або було в попередній концепції"   # правило класу
  n: 3                          # N для class_rule
licenses:
  own_modules: LGPL-3           # за замовчуванням; остаточно — рішення власника
  oca: idea                     # idea|dependency — OCA лише як ідея (К-09)
reuse:
  repos: []                     # GitHub-репо ToDo, де шукати готові модулі (A-03c)
  projects: []                  # коди проєктів (П-xx) / ERP
brand:
  materials: ToDo               # бренд матеріалів (brand-todo/)
  demo_client: вигаданий        # бренд демо-клієнта
  white_label: false
materials:
  formats: [video_16x9, reels_9x16, mobile, one_pager]
  languages: [uk]
prototype:
  fidelity: real-slice          # real-slice (mock у 0.2.0 не підтримується, К-23)
  new_record_in_frame: false    # К-13: «Новий» у кадрі
legal_ambiguous:
  to_answers_yaml: true         # юридично неоднозначне виносити в параметр answers.yaml
rounds:
  review_max: 2                 # кіл рецензії (+1 контрольне)
  review_control: 1
  human_target: 2               # ціль кіл людини на крок
```
