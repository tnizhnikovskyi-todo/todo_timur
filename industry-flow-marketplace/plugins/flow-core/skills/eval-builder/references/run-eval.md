# Прогін claude plugin eval

Довідка CLI станом на 2026-11 (`claude plugin eval --help`); на місці перевірити, чи прапорці не змінились.

## Команда
```bash
claude plugin eval <tmp>/<плагін> --eval-dir flow-evals --case '<набір>__*' --runs 3 \
  --no-publish --mocks record --trust-plugin --ablation none --max-cost-usd 3 \
  --json <tmp>/res.json --threshold 0 --output-dir <tmp>/out
```
- Бюджет `--max-cost-usd`: 3 для C-04, 1 для C-07 (решта ліміту запуску — на сам скіл; агент не бачить власних витрат). Єдине місце цього правила.
- `<tmp>` — тимчасова тека поза репо; плагін — копія встановленої точної версії (`claude plugin list`); eval dir лежить під плагіном.
- Нові кейси: `--runs 1`, `--threshold 0` (червоне очікуване). Регрес: `--runs 3`, рішення більшістю.
- `--trust-plugin` — лише для плагінів каталогу організації; чужі плагіни не оцінювати.
- `--concurrency` <= 3 (спільний ліміт запитів).
- `--ablation none` — завжди (за замовчуванням `with-without` подвоює вартість і для нових червоних кейсів беззмістовний);
  `with-without` вмикає лише окреме рішення AI-інженера. `--judge-model` (за замовчуванням haiku) входить у вартість; не змінювати.

## Заборонено
`--allow-real-servers`, `--mocks off`, `--publish-report` (звіт піде на claude.ai), `--scaffold` (виконує bash з файлів кейсів),
`--allow-tools` з будь-чим, крім переліку нижче. Реальні MCP-сервери в евалах не стартують; кейси з odoo-mcp — заглушки `mocks/`.

## Вузькі гранти `--allow-tools`
Write/Edit/Bash — gated tools: `allowed_tools` у frontmatter їх сам не відкриває.
- `--allow-tools Write Edit` — лише для кейсів `needs_write: true` (кейс перевіряє запис файла); без Bash, WebFetch, `mcp__*`; запис —
  лише в тимчасовій теці `<tmp>`. Такі кейси проганяти окремим викликом з `--case` на їхні id.
- `--allow-tools Bash` — лише при прогоні власного набору `eval-builder` (його кейс 1 вимагає запуску `claude plugin eval`); решта наборів без Bash.

## Зразок файлів кейса (вивід `cd <tmp> && claude plugin eval init --bare --eval-dir e <name>`; `--eval-dir` для `init` — відносно поточної теки)
Першим кроком розкладки в `<tmp>` — перевірити формат тим самим `init --bare` (він створює `graders/criteria.md`; файли `graders/01-check.md` скіл розкладає сам). `<tmp>/e/<name>/prompt.md`:
```
---
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
---

<вхід кейса>
```
`<tmp>/e/<name>/graders/01-check.md` (одне твердження — один грейдер):
```
---
type: llm
weight: 1
---

<опис успішної відповіді>
```

## Коди виходу
- `0` — усі кейси >= порога; `1` — є кейс нижче порога (для нових кейсів очікувано); `2` — перевищено `--max-cost-usd`, результати часткові.
- exit 2 -> `partial: true`, непрогнані кейси `queued` («немає — в черзі <дата>»), ескалації немає.
- Інше (падіння CLI, таймаут) -> технічний збій: повтор; 3 невдалі прогони -> ескалація Тімліду (`escalation` C-04).

## Бюджет
Агент не бачить власних витрат, тому розподіл сталий: `--max-cost-usd 3` для C-04 (з $5 на запуск; решта — на роботу агента) і `1` для C-07
(з $2). Оцінка на кейс невідома до першого прогону: спершу 1 кейс, `cost_usd` з `res.json`, далі порції; перевищення -> exit 2.
Місячного бюджету AI немає.

## Після прогону
Стиснути `res.json` у `evals/results/<YYYY-MM-DD>-<mode>.json` (кейс, score, runs, модель, версія, $). Повний JSON і `<tmp>` у git не йдуть.
