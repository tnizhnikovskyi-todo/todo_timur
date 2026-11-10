# Автоперевірка B-02: точні команди

Основне — `python3 -I scripts/check_fit_gap.py --client <к> --tag <тег> --base <git.base>`. Нижче — те саме вручну
(для MANUAL і для звірки). `<тег>` і `<git.base>` — з наряду (`inputs`, `git.base`).

| ID | Команда / правило |
|---|---|
| FG-headings | `grep -nE '^## (Джерела\|Вимоги\|Суперечності й відкриті питання\|Рішення з сесій\|Запити в D-02\|Відповідність пакету\|Факти для пілоту)$' clients/<к>/fit-gap.md` — 7 збігів |
| FG-anchor | VP: `git show <тег>:package/templates/answers.yaml \| grep -c '<VP-xx>'`; модуль: `git show <тег>:package/ALLOCATION.md \| grep td_<м>`; розділ: `git show <тег>:package/config/CONFIG.md \| grep -n '^#.*<розділ>'`; сценарій: `git show <тег>:package/demo/scenarios.md \| grep 'S-xx'`. Порожньо = якоря немає |
| FG-schema | ключі = `git show <тег>:package/templates/answers.yaml \| grep -oE '^VP-[0-9]+'` без рядків з `deprecated`; значення з `allowed:` схеми або `уточнити` |
| FG-pii | `grep -nE` / `grep -nP` за шаблонами `flow-core/references/pii-patterns.md` (email, phone `(?<![\w:])(\+?380\d{9}\|0\d{9})(?!\w)`, IBAN `UA\d{2}[\s\d]{20,}`, ЄДРПОУ `ЄДРПОУ\D{0,5}\d{8}\b`, ПІБ) по трьох файлах; + заборонені рядки з наряду (`grep -nFif <файл>`). У звіт — тип:файл:рядок, не значення |
| FG-scope | `git -c core.quotePath=false diff --name-only <git.base>..HEAD -- .`; `git -c core.quotePath=false status --porcelain --untracked-files=all` (без quotePath=false кириличні шляхи sales/ виходять в octal-лапках; перейменування `R a -> b` — обидва шляхи) — лише 3 файли `clients/<к>/` і 2 файли `sales/` |
| FG-ignore | `git check-ignore -q clients/<к>/_input/x` (код 0) і `test ! -d clients/<к>/_input` перед здачею |
| FG-d02 | колонка «Рішення D-02…» порожня для нових рядків; для старих збігається з `git show <git.base>:clients/<к>/fit-gap.md` |
| FG-threshold | `--business-case <шлях>`: скрипт звіряє SHA і число; вручну — цитата порогу й `SHA` з `git log -1 --format=%H -- <business-case>`; частки перерахувати з таблиці «Вимоги» (рядки і макс-години) |
| FG-coverage, FG-agreement | вручну за SKILL.md і `agreement-check.md` |
