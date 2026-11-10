# Відкриті питання (до проєктувальників, не інструкція агенту)
- Рішення q32: у метриці «поза пакетом» лише доробки коду, доналаштування не входять (метрика — рядки; число порогу — business-case).
- Чи залишати підкрок scorer на B-02, якщо коефіцієнта B-01 досить.
- «Рішення з сесій»: розділ fit-gap.md; чи дублювати в журнал продажу — вирішує людина.
- Формат схеми `package/templates/answers.yaml` (допустимі значення, deprecated) задає A-09; `check_fit_gap.py` очікує
  рядки `VP-xx: # allowed: a|b` / `deprecated`, інакше значення — MANUAL. Спільний валідатор — відкрито.
- Рішення q10: джерело істини підпису — стадія угоди в CRM Odoo.
- Відкрито (C-00): лише назва стадії CRM для `preconditions_confirmed.crm_deal_stage: discovery_signed` (ключ наряду визначено в `naryad-format.md`).
- Рішення q09: клієнтів без згоди на AI не беремо; відсутній пункт про AI → `escalated`, не продовжуємо. DATA_POLICY/business-case привести у відповідність (не цей скіл).
- Файл шаблону: `flow-client-delivery/skills/package-fit-gap/references/fit-gap-template.md` згадує `product-decision-drafter`
  (D-02); фактично файл у `references/` цього скіла — потрібен один спільний шлях.
- Строк зберігання записів Fathom — за DATA_POLICY.
