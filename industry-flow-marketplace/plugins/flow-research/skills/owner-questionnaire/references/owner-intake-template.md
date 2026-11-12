# Шаблон анкети власника `OWNER-INTAKE.md` (A-02b)

Файл галузі: `docs/industries/<галузь>/OWNER-INTAKE.md`. Цей файл — еталон форми: `check_intake.py` (`plugins/flow-core/skills/flow-autocheck/scripts/`) читає з нього блокуючі поля (`*`) і переліки значень. Розмітка YAML-блока: `*` після ключа верхнього рівня — усі підключі блокуючі; `a|b|c` у коментарі — дозволені значення.

## Як заповнювати (простою мовою)
Шість питань, ≈5 хвилин. При копіюванні в `OWNER-INTAKE.md` знак `*` після ключів верхнього рівня прибрати (це лише розмітка шаблона). Відповіли — добре; не відповіли — діє замовчування. Блок `defaults:` заповнює AI, власника по ньому не питаємо; суттєве замовчування (редакція, ринок, облікова система) AI записує рядком у `research/AI-DECISIONS.md`, власник має вето на гейті концепції (A-20c). Тарифи — необов'язково: якщо власник дав, AI лише цитує їх у BOX §1 і не рахує.

## YAML-блок (копіюється в `OWNER-INTAKE.md`)

```yaml
editions*: both                 # * ce|ee|both — для яких редакцій Odoo будуємо пакет
demo_edition: ce                # ce|ee — редакція зрізу A-21 (замовчування ce)
ee_bridges: now                 # now|later — мости EE (замовчування now)
icp*:
  min_employees: 10             # поріг ICP: працівників
  legal_forms: [ТОВ, ФОП]       # юридичні форми клієнтів
  light_tariff_fop: true        # чи потрібен «легкий» тариф для ФОП
  # revenue_min — лише якщо власник сам дав
todo_data*:
  allowed_sources: [crm, fathom, unitalk, aikb, gmail, own-erp]  # які внутрішні джерела ToDo дозволено читати
  mode: read                    # лише читання
  internal_raw_storage: repo-sources   # internal-raw лежить у research/sources/ репо галузі
  push_deidentified: true       # чи можна пушити знеособлені висновки в репо галузі
brand*:
  materials: todo               # todo|white_label — бренд матеріалів
  demo_client: вигаданий        # бренд демо-клієнта
materials*:
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
    repos: []                   # GitHub-репо ToDo з готовими модулями; "—" якщо немає
    projects: []                # коди проєктів/ERP; "—" якщо немає
  prototype:
    fidelity: real-slice
    new_record_in_frame: false
  legal_ambiguous:
    to_answers_yaml: true
  rounds:
    review_max: 2
    review_control: 1
```

## Журнал змін (власник/AI)
| Дата | Поле | Було | Стало | Джерело (повідомлення/задача) |
|---|---|---|---|---|

## Примітки до блоків
- Короткі шляхи `market.*`, `ambition.*`, `licenses.*`, `reuse.*`, `prototype.*`, `rounds.*` у скілах і довідках означають `defaults.<шлях>` (напр. `market.language` = `defaults.market.language`).
- Блокуючі: `editions`, `icp`, `todo_data`, `brand`, `materials`. `do_not_do` і `tariffs` не блокують.
- Вилучено в 0.3.0 (не вимагається; наявність у старій анкеті ігнорується з WARN): `ambition.scope`, `ambition.evidence_gate`, `pricing.*`, `do_not_reject.*`, `rounds.human_target`.
- `todo_data.allowed_sources` без `internal_raw_storage: repo-sources` -> `internal-raw` не зберігати (WARN у C-00).
- Словник `todo_data.allowed_sources`: `crm` — CRM-угоди власної ERP через alias `own-erp`; `own-erp` — інші моделі власної ERP (наприклад `ir.module.module`); `fathom`, `unitalk`, `aikb`, `gmail` — відповідні внутрішні джерела.
- `defaults.reuse.repos` і `projects` — список або `"—"`; порожній `[]` означає «не з'ясовано» і йде рядком AI-DECISIONS (A-03c тоді працює зеленим шляхом «Нуль кандидатів»).
