# Шаблони ідентифікаторів для автоперевірок (SHA, версії, теги)

Використовує `flow-core:flow-autocheck` (режими `inputs`, `result`, `form`). Один regex на значення; без збігу — перевірка `MANUAL` або `ERROR` за її описом, а не вгадування.

| Що | Regex (Python, `re`) | Де шукається |
|---|---|---|
| Мітка SHA | `(?i)\b(SHA\|commit)\b[:\s]*([0-9a-f]{7,40})` | `ACCEPTANCE.md`, `CHECKS.md`, README стенда (A-15), `scenarios.md` |
| Тег версії | `^package/v\d+\.\d+(-odoo\d+)?$` | `git tag --list 'package/v*'` (суфікс `-odoo<N>` лише для тега переходу на нову мажорну Odoo, рішення q19; звичайний випуск -- без суфікса) |
| Патч-тег | `^package/v\d+\.\d+\.\d+$` | hotfix A-19/A-18 |
| Гілка переходу (q19) | `^upgrade/v\d+\.\d+-odoo\d+$` | `git branch -r --list 'origin/upgrade/*'` (гілка переходу `upgrade/vX.Y-odoo<N>`, рішення q19; тег переходу -- `package/vX.Y-odoo<N>`) |
| Код кроку | `\b[A-D]-\d{2}[a-d]?\b` | наряди, звіти |
| Код П-xx | `П-\d{2}` | `sources.md`, `past-projects.md` |
| ID вимоги | `\b(?:ROLE\|PAIN\|F\|S\|SC)-\d{2,}\b` | концепція |
| VP | `VP-\d{2,}` | анкета |
| Питання бота | `HB-\d{3,}` | `help-log.md` (client-help-bot); передача в support-desk: `params.handoff` |

Джерела SHA для перевірок:
- `result`/`form`: `--base <sha>` і `--head <sha>` з `git:` наряду (`naryad-format.md`); немає — runner рахує: head = вершина `repo.branch`, base = `git merge-base head origin/<base_branch>`; обидва записати в `checks[]` JSON.
- `inputs`: `--base <sha>` = SHA `origin/<base_branch>` на момент запуску, зафіксований один раз у звіті.
- Попередній тег (A-18, D-03, B-11): `git.prev_tag` з наряду або найбільший `package/vX.Y` серед предків кандидата (`git tag --merged <head> --list 'package/v*' --sort=-v:refname | head -1`); у списку беруться теги без суфікса `-odoo<N>` (лінія поточної Odoo); для D-03/A-18 переходу (`-odoo<N>`) попередній -- найбільший тег без суфікса, для наступних випусків на лінії N -- найбільший тег із суфіксом `-odoo<N>` цієї N, інакше без суфікса; немає — `SKIP first-release`.
- `sha-eq`: SHA з `ACCEPTANCE.md`/`CHECKS.md` за «Мітка SHA»; мітки немає — `MANUAL`, а перевірки, що потребують SHA (`checks-ancestor`, `diff-checks-acc`, `tag-descendant`, `diff-allowed-7`), — `FAIL missing-sha` (не ERROR).
