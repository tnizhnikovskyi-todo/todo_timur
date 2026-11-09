# Автоперевірки A-04 (`scripts/check_past_projects.py`)

Запуск і прапорці — Крок 8 SKILL.md. Вивід — JSON `[{id, status, msg}]` = `checks` звіту. Значення PII у виводі не друкуються.

| ID | FAIL, коли |
|---|---|
| PP-sections | немає хоча б одного з шести заголовків |
| PP-sources | у `sources.md` немає колонки назви, дубль коду або кодів немає |
| PP-codes | П-xx у документі не з `sources.md` або код з `sources.md` не згаданий |
| PP-src | рядок таблиць процесів, модулів, болів, прогалин без `aikb:`/`fathom:`/`repo:` або без П-xx |
| PP-mode | для П-xx з режимом «лише звіти AIKB» є `fathom:`; з `--no-fathom` — будь-який `fathom:`; рядок з кількома П-xx і `fathom:` без пар «П-xx fathom:…» |
| PP-repo | шлях `repo:` з розділу модулів не існує на вказаному SHA |
| PP-ver | у модуля порожні версія Odoo або «сумісність з 19» |
| PP-repeat | рядок «Повторюваних вимог» має <2 різних П-xx |
| PP-count | число в «Для шлюзу» ≠ кількості рядків «у сегменті: так» |
| PP-pii | збіг із denylist (колонка назви + stdin), email, телефоном, url, ip, секретом, сумою, ЄДРПОУ/IBAN, ПІБ (`flow-core/references/pii-patterns.md`) |
| PP-gitignore | `_input/sources.md` не ігнорується або відстежується (стоп-інцидент) |
| PP-scope | змінені/нові файли й `git diff base...head` поза `--scope-files`; `observations/` дозволено завжди (його комітить runner); шлях `/_input/` у git |
| PP-input | видимий сторонній файл у `_input/` (приховані, `*.bak`, `*~` ігноруються): агент не прибирає → `waiting_human` |

`--self-test` перевіряє шаблон, приклад `sources-format.md`, PP-pii, PP-scope (untracked, observations/), PP-input, `--no-fathom`.
