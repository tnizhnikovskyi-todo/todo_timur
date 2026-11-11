# Структура сторінок власника (A-20c)

Каркаси — `flow-research/references/templates/owner-page/{index,competitors,rejected}.html`, контракт — `flow-research/references/PAGE-CONTRACT.md`.
Наповнення замінює `{{…}}`; структуру, токени, навігацію, блок рішень і скрипт не змінювати без причини в `memo`.

## Порядок розділів `index.html` (id якоря → джерело)
| # | id | Розділ | Джерело в `research/` (для `data-src`) | Обов'язковість якоря |
|---|---|---|---|---|
| 1 | `verdict` | Висновок і чесний вердикт про гроші | `OWNER-BRIEF.md§6` (гроші; висновок — шапка `OWNER-BRIEF.md`), `facts.yaml§<ключ>`, `BOX.md§…` | так |
| 2 | `pain` | Для кого і який біль (цитати) | `OWNER-BRIEF.md§1`, `SRC-NNN` | так |
| 3 | `scenario` | Наскрізний сценарій | `OWNER-BRIEF.md§2` (`concept/scenarios.md`, `SC-xx`) | бажано |
| 4 | `day` | День з життя ролей | `OWNER-BRIEF.md§2` / `§4` | бажано |
| 5 | `screens` | Екрани MVP з основою Стд CE / Стд EE / td_ / ToDo-готовий / Інтегр | `OWNER-BRIEF.md§3`, `FUNCTIONAL-MAP.md§4`, `REUSE.md§…` | так |
| 6 | `current` | Що вже є в зрізі | `../prototype-real/PLAN.md§…` — **лише якщо зріз існує**; інакше розділ і пункт навігації не виводити | так, якщо є |
| 7 | `competitors` | Конкуренти коротко (+ посилання на `competitors.html`) | `competitors-registry.md§…` | бажано |
| 8 | `not-doing` | Що свідомо не робимо (+ `rejected.html`) | `OWNER-BRIEF.md§5`, `REJECTED.md§…` | бажано |
| 9 | `signals` | Внутрішні сигнали ToDo (лише `internal-aggregated`) | `sources-log.md` (`SRC-NNN`) | бажано |
| 10 | `money` | Гроші: коробка, TCO, окупність, чутливість | `OWNER-BRIEF.md§6`, `BOX.md§…`, `facts.yaml§<ключ>` | так |
| 11 | `box` / `sales` | Що в коробці / як продаємо | `BOX.md`, `SALES.md` | бажано |
| 12 | `returned` | Повернуто рішенням власника (група 4а) | `REJECTED.md§4а` | бажано |
| 13 | `risks` | Ризики й що з ними робити | `OWNER-BRIEF.md§7` | так |
| 14 | `completeness` | Повнота концепції (closed/partial/open, G-xx) | `COMPLETENESS.md§1` | бажано |
| 15 | `decisions` | Рішення власника: ≤5 питань + «Скопіювати мої відповіді» (джерело питань — `OWNER-BRIEF.md§8`) | — | — |
| 16 | `chain`, `evidence`, `limits`, `sources` | Додатки: ланцюг ROLE→PAIN→F→S→SC, докази, обмеження й план перевірки, джерела | `concept/*`, `sources-log.md` | — |

Перший екран — розділ 1 + блок «що вирішити» (посилання на `#decisions`). Додатки (16) — внизу, мовою без жаргону їх не виносити нагору.

## Якорі на рядки дослідження (OP-anchors)
Кожна теза розділу несе `<a class="src" href="#sources" data-src="<значення>">підпис</a>`; `<значення>`: `<файл у research/>§<номер або фрагмент заголовка>` (напр. `BOX.md§4`, `REJECTED.md§4а`) або `SRC-NNN` (рядок `research/sources-log.md`).
Правила: файл і розділ існують (скрипт перевіряє з `--research`); число на сторінці = `facts.yaml`; ◎ (наш пакет) — лише з позначкою «гіпотеза / план», не як факт; `internal-raw` на сторінці немає.
Якір не на файл з `internal-raw` (`research/sources/**`): лише на знеособлений висновок; `OP-anchors` дає FAIL на `sources/...`.
Якір на файли поза `research/` пишуть відносно `research/`: `../prototype-real/PLAN.md§…`, `../OWNER-INTAKE.md§…`, `../concept/…§…`. Розділ `#current` з'являється лише тоді, коли `../prototype-real/PLAN.md` існує: нема файла — прибрати і розділ, і пункт `<a href="#current">` у навігації (`OP-contract`).
Нечисловий фрагмент шукається лише в заголовках `.md` (допустимі «## §4 …», «## Розділ 4»), у `.yaml` — ключ на початку рядка; `SRC-NNN` — цілим словом у рядку таблиці `sources-log.md`.

## Маркери чисел
Кожне число з одиницею з `facts.yaml` — `<span data-fact="ключ">12 000 грн</span>` (або `<!--fact:ключ-->` одразу після числа). Без маркерів `check_facts.py --require-markers` дає FAIL (`FACT-markers`/`FACT-mismatch`). Угода — `flow-core/skills/flow-autocheck/references/checks.md`, «Маркери фактів». Ключ має існувати в `facts.yaml` (`FACT-orphan`).

## `competitors.html` і `rejected.html`
- `competitors.html`: ландшафт, матриця (фільтр груп, рядки «Odoo 19 Community/Enterprise», «наш пакет ◎»; у рядку чи колонці «наш пакет» лише ◎, ● або ◐ там — FAIL скрипта), «Що казати проти», звірені цитати (`SRC-NNN`), висновки. Джерело — `competitors-registry.md`, `competitor-features.md`, `competitors/*.md`.
- `rejected.html`: групи `g1`, `g2`, `g3`, `g4`, `g4a`, журнал знятих рішень `log`; колонки реєстру — `flow-core/references/rejected-register.md`. Позиції `do_not_reject` з анкети, відкинуті без K1, на сторінку не виводити як «відкинуті» — це прогалина A-20 (повернути).
- Навігація «Концепція · Конкуренти · Що відкинули» на кожній сторінці, `aria-current="page"` на активній.

## Зразок (`params.sample: true`)
Лише `index.html`: перший екран (вердикт і гроші, 1 біль із цитатою, блок «що вирішити») + навігація + каркас решти розділів з якорями. Мета — власник підтверджує тон і подачу до повного обсягу. Пункти навігації на `competitors.html` і `rejected.html` у зразку неактивні (без `href`, позначка «у повному обсязі»): цих сторінок за URL зразка ще немає. Результат `waiting_human`; повний обсяг — `resume {sample: false}`.
