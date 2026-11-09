# stand-happy-profiles (A-15, старт 1)
Мінімальний пакет `package/`. SHA-плейсхолдери: `<S>` = SHA з CHECKS.md; HEAD = `<S>` + коміт, що змінив лише `package/CHECKS.md`
(фікстуру відтворює `git init` + два коміти за цим описом). Режим використання в наряді: окремі інстанси за ідентифікатором.
Скрипти C-00: `tools/odoo/{clean,install,import,smoke,snapshot,restore}.sh` (файли-заглушки, exit 0). ТР — `docs/industries/demo-ind/ТР.md`.
