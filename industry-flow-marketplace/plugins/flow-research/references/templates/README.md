# Шаблони артефактів галузі (flow-research)

Каркаси з еталона «меблі» (`flow/A-03b-deep` @ `008541f`, `flow/A-21-real` @ `74c90ca`): заголовки, колонки таблиць, позначки; **без галузевого змісту** (у кожному файлі коментар «звідки»). Плейсхолдери — `{{…}}`.
Файлів шаблонів — 12 (+ цей README). Повні файли еталона — золоті приклади для евалів (за SHA, не копія).

| Шаблон | Крок | Обов'язкові розділи |
|---|---|---|
| `FUNCTIONAL-MAP.tpl.md` | A-03b | вибір підсегмента; карта (гігієна/паритет/відмінності; основа CE і EE); позиціонування/вартість/ризики; зріз; джерела |
| `odoo-ecosystem.tpl.md`, `edition-claims.tpl.md` | A-03b | стандарт CE/EE; Apps Store; інтеграції; таблиця тверджень з вердиктом (EC-NNN) |
| `competitors.tpl.md` | A-03b | один шаблон на три вихідні файли: `competitors-registry.md` (§1–5), `competitor-features.md` (§6), `competitors/<slug>.md` (§7); реєстр за типами; матриця з рядками «Odoo 19 Community/Enterprise», «наш пакет ◎»; профілі 8–12 |
| `K1.tpl.md` | A-03b | ≤10 питань K1 з рекомендацією й замовчуванням |
| `OWNER-BRIEF.tpl.md` | A-20 | §1–10 |
| `BOX.tpl.md` | A-20 | §1–13 (+1а) |
| `SALES.tpl.md` | A-20 | §1–7 |
| `REJECTED.tpl.md` | A-03b, A-20 | групи 1–4, 4а, журнал знятих рішень (поверх `flow-core/references/rejected-register.md`) |
| `COMPLETENESS.tpl.md` | A-20b | §1–4, реєстр `G-xx` |
| `facts.yaml`, `DEPENDS.yaml` | A-03b → усі | єдине джерело чисел; залежності для перерахунку |
| `owner-page/{index,competitors,rejected}.html` | A-20c | навігація 3 сторінок; токени бренду ToDo; блок рішень із «Скопіювати мої відповіді»; розділи «Внутрішні сигнали ToDo», «Що казати проти», «Звірені цитати» |

Поруч: `../PAGE-CONTRACT.md`, `../brand-todo/`, `../needs-sources-catalog.md`, `../completeness-checklist.md`, `../sources-format.md`.
