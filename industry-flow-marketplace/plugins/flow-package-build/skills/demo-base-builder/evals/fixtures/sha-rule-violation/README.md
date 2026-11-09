# sha-rule-violation (A-15)
CHECKS.md = APPROVE на SHA S. Після S у HEAD є коміт, що змінив `package/addons/td_a/` (поза дозволеним `package/CHECKS.md`, `package/demo/`). Фікстуру відтворює `git init` + три коміти: S, коміт у addons, HEAD.
