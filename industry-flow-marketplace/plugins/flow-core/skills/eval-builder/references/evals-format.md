# Формат evals/<набір>/evals.json

Файл у репо флоу: `evals/<скіл>/evals.json` або `evals/<код-кроку>/evals.json`. Фікстури — `evals/<набір>/fixtures/<case>/`,
заглушки MCP — `evals/<набір>/mocks/`. Це **підмножина-розширення** схеми CONCEPT §3.8. Формат CLI (`prompt.md` + `graders/*.md`)
генерується з нього в тимчасову теку; точні поля CLI перевіряти `claude plugin eval --help` і `claude plugin eval init --bare`.

## Схема
```json
{"skill": "pr-review", "set_kind": "skill|step", "cases": [
  {"id": "ir-rule-line-model",
   "status": "regress|new-red|not-reproduced|queued|declined-proposed",
   "source": "observation 2026-11-03-pr-review-ir-rule-line.md",
   "sources": ["observation 2026-11-03-pr-review-ir-rule-line.md", "failureMode картки A-14"],
   "step": "A-14", "skill_version_seen": "odoo19-mvp-build@1.4.0",
   "barrier": false, "requires": [],
   "input": {"fixtures": "evals/pr-review/fixtures/ir-rule-line-model/"},
   "prompt": "наряд або запит, як у запуску",
   "expected": {"checks": ["що має бути в результаті"], "must_not": ["чого не має бути"]}}
]}
```

## Поля
| Поле | Обов'язкове | Зміст |
|---|---|---|
| `id` | так | kebab-case, унікальний у наборі |
| `source` | так | формат: `failureMode картки <код>` / `observation <файл>` / `incident <id>` (перевірка `source-filled`) |
| `sources[]` | якщо >1 джерела | усі джерела після дедуплікації; `source` = перше |
| `step` | для скіл-набору | код кроку, де помилку видно (`^[ABCD]-\d{2}[a-z]?$`) |
| `status` | так | `regress` — зелений, у регресі; `new-red` — новий, червоний, скіл до виправлення; `not-reproduced` — новий, зелений, рішення Тімліда; `queued` — «немає — в черзі»; `declined-proposed` — пропозиція відхилити (рішення Тімліда) |
| `skill_version_seen` | для нових | версія, на якій помилку бачила людина |
| `barrier` | ні | `true` для повтору (`repeat_of`): кейс обов'язковий у регресі |
| `requires` | ні | напр. `["odoo-mcp:test"]`; у звичайному прогоні кейс «пропущено» з явним статусом |
| `input.fixtures` | ні | знеособлені чи синтетичні вхідні артефакти (<= ~50 KB на кейс) |
| `prompt` | так | як у реальному запуску; без рамки «ти оцінювач / це тест» |
| `expected.checks` | так | перевірювані твердження з «Ожидали» / з причини інциденту |
| `expected.must_not` | так | з «Получили»; щонайменше одне |

## Відповідність CLI
- `<tmp>/<плагін>/flow-evals/<набір>__<case>/prompt.md` — frontmatter (`max_turns`, `allowed_tools`: Read, Glob, Grep, Skill) + `prompt`;
- `graders/NN-check.md` — `type: llm`, `weight`, текст = одне твердження з `expected.checks`;
- `graders/99-must-not.md` — один грейдер на весь `must_not`;
- `contains` — лише для формальних полів (шлях файла, код кроку).
`<тека>` у `--case` фільтрі: `'<набір>__*'`.

## Результати
`evals/results/<YYYY-MM-DD>-<mode>.json`: `[{"case","score","runs","model","skill_version","cost_usd"}]`. Повний JSON CLI — лише в тимчасовій теці.
