# Структура сторінок власника (A-20c)

Каркаси — `flow-research/references/templates/owner-page/{index,competitors,rejected}.html`, контракт — `flow-research/references/PAGE-CONTRACT.md`.
Наповнення замінює `{{…}}`; структуру, токени, навігацію, блок «Що вирішив AI» і скрипт не змінювати без причини в `memo`.

## Порядок розділів `index.html` (id якоря → джерело)
Відповідає порядку з LESSONS §24: висновок → біль → сценарій → екрани → «Що вирішив AI і з яким ризиком» → ризики → «не робимо». Грошового розділу немає (`OP-money`).
| # | id | Розділ | Джерело в `research/` (для `data-src`) | Обов'язковість якоря |
|---|---|---|---|---|
| 1 | `summary` | Висновок: що будуємо і для кого (без грошей) | `FUNCTIONAL-MAP.md§5`, `BOX.md§1` | так |
| 2 | `pain` | Для кого і який біль (цитати) | `../concept/features.md§Болі`, `SRC-NNN` | так |
| 3 | `scenario` | Наскрізний сценарій | `../concept/scenarios.md§Сценарії` (`SC-xx`) | бажано |
| 4 | `day` | День з життя ролей | `../concept/scenarios.md§Сценарії` | бажано |
| 5 | `screens` | Екрани MVP з основою Стд CE / Стд EE / td_ / ToDo-готовий / Інтегр | `../concept/screens.md§Екрани`, `FUNCTIONAL-MAP.md§4`, `REUSE.md§…` | так |
| 6 | `current` | Що вже є в зрізі | `../prototype-real/PLAN.md§…` — **лише якщо зріз існує**; інакше розділ і пункт навігації не виводити | так, якщо є |
| 7 | `competitors` | Конкуренти коротко (+ посилання на `competitors.html`) | `competitors-registry.md§…` | бажано |
| 8 | `signals` | Внутрішні сигнали ToDo (лише `internal-aggregated`) | `sources-log.md` (`SRC-NNN`) | бажано |
| 9 | `box` / `sales` | Що в коробці (склад, тарифи власника дослівно) / як продаємо | `BOX.md§1`, `SALES.md` | бажано |
| 10 | `ai-decisions` | Що вирішив AI і з яким ризиком: рядки `AI-DECISIONS.md` (≤15) + «Скопіювати мої заперечення» | `AI-DECISIONS.md§Рішення` | так |
| 11 | `risks` | Ризики й що з ними робити (`ризик: перевірити на пілоті`, SALES §3) | `SALES.md§3`, `AI-DECISIONS.md§Рішення` | так |
| 12 | `not-doing` | Що не робимо й чому (+ `rejected.html`) | `REJECTED.md§…` | бажано |
| 13 | `chain`, `evidence`, `limits`, `sources` | Додатки: ланцюг ROLE→PAIN→F→S→SC, докази, обмеження й план перевірки, джерела | `concept/*`, `sources-log.md`, `AI-DECISIONS.md§Повнота` | — |

Перший екран — розділ 1 + посилання на `#ai-decisions` («що вирішив AI»). Додатки (13) — внизу, мовою без жаргону їх не виносити нагору. «Повнота» (A-20b) окремим розділом не виводиться: незакрите — рядки «ризик» у `ai-decisions`/`risks`.

## Якорі на рядки дослідження (OP-anchors)
Кожна теза розділу несе `<a class="src" href="#sources" data-src="<значення>">підпис</a>`; `<значення>`: `<файл у research/>§<номер або фрагмент заголовка>` (напр. `BOX.md§4`, `REJECTED.md§4а`) або `SRC-NNN` (рядок `research/sources-log.md`).
Правила: файл і розділ існують (скрипт перевіряє з `--research`); число на сторінці = `facts.yaml`; ◎ (наш пакет) — лише з позначкою «гіпотеза / план», не як факт; `internal-raw` на сторінці немає.
Якір не на файл з `internal-raw` (`research/sources/**`): лише на знеособлений висновок; `OP-anchors` дає FAIL на `sources/...`.
Якір на файли поза `research/` пишуть відносно `research/`: `../prototype-real/PLAN.md§…`, `../OWNER-INTAKE.md§…`, `../concept/…§…`. Розділ `#current` з'являється лише тоді, коли `../prototype-real/PLAN.md` існує: нема файла — прибрати і розділ, і пункт `<a href="#current">` у навігації (`OP-contract`).
Нечисловий фрагмент шукається лише в заголовках `.md` (допустимі «## §4 …», «## Розділ 4»), у `.yaml` — ключ на початку рядка; `SRC-NNN` — цілим словом у рядку таблиці `sources-log.md`.

## Маркери чисел
Кожне число з одиницею з `facts.yaml` (ринок, кількості; цін і годин там немає) — `<span data-fact="ключ">12 компаній</span>` (або `<!--fact:ключ-->` одразу після числа). Без маркерів `check_facts.py --require-markers` дає FAIL (`FACT-markers`/`FACT-mismatch`). Угода — `flow-core/skills/flow-autocheck/references/checks.md`, «Маркери фактів». Ключ має існувати в `facts.yaml` (`FACT-orphan`).

## `competitors.html` і `rejected.html`
- `competitors.html`: ландшафт, матриця (фільтр груп, рядки «Odoo 19 Community/Enterprise», «наш пакет ◎»; у рядку чи колонці «наш пакет» лише ◎, ● або ◐ там — FAIL скрипта), «Що казати проти», звірені цитати (`SRC-NNN`), висновки. Джерело — `competitors-registry.md`, `competitor-features.md`, `competitors/*.md`.
- `rejected.html`: один розділ `not-doing` — короткий список «ID · що не робимо · чому · коли повернутись» (`flow-core/references/rejected-register.md`; без груп і журналу). Позиції зі списком `do_not_do` анкети — з причиною «рішення власника». Позиція, на яку власник наклав вето (повернув у концепцію), у списку не показується.
- Навігація «Концепція · Конкуренти · Що відкинули» на кожній сторінці, `aria-current="page"` на активній.

## Зразок (`params.sample: true`)
Лише `index.html`: перший екран (висновок без грошей, 1 біль із цитатою, блок «що вирішив AI») + навігація + каркас решти розділів з якорями. Мета — власник підтверджує тон і подачу до повного обсягу. Пункти навігації на `competitors.html` і `rejected.html` у зразку неактивні (без `href`, позначка «у повному обсязі»): цих сторінок за URL зразка ще немає. Результат `waiting_human`; повний обсяг — `resume {sample: false}`.
