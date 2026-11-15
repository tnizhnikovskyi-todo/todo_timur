# Шаблон розділу версії package/CHANGELOG.md

Копія для `package/templates/CHANGELOG.md` на першому запуску. Спільний варіант плагіна
(`plugins/flow-package-build/references/changelog-template.md`) має пріоритет, коли з'явиться. Новий розділ — зверху файлу.
Заголовки — grep-контракт для B-11 і D-03, не перейменовувати.

```markdown
## Версія <тег>
- Тег: `package/...`; дата: <YYYY-MM-DD>; ревізія: `<SHA>`; Odoo: 19.0 (odoo-upgrade: <N>.0)

### Склад пакета
| Модуль | version | Тип (td_* / вендорений) | Джерело/коміт | Ліцензія |
|---|---|---|---|---|
<!-- td_<галузь>_demo — примітка «лише демо-стенд, клієнтам не ставиться»; td_home_menu/td_support/td_knowledge — власна версія -->

### Шаблони документів клієнта
`package/templates/migration-plan.md`, `training.md` — <що змінилось / без змін>

### Зміни анкети
- Нові: `VP-xx` — ключ, default, потрібне рішення клієнта (так/ні)
- Deprecated: `VP-xx` — що робити зі старою відповіддю
(або: «немає» / «Перша версія: попереднього тега немає»)

### Несумісні зміни
- <модель/поле/xmlid/API> — що робити `td_<клієнт>_*` (міграція: `migrations/<серія>.X.Y/...`)
(або: «немає»; «Міграція: не потрібна»)

### Міграція з попереднього тегу
- З: `<PREV>`; інстанс: <id бронювання>; SHA прогону: `<sha>`; результат: PASS/NOT_RUN
- Витяг з логу (<= 30 рядків): ...

### Команда установки
`<одна команда скрипта C-00>`

### Передача клієнту        <- release і odoo-upgrade (0.4.0)
- Модулі до установки (A-17b), лише при `elearning.mode: "on"`: `website_slides`, `td_<галузь>_elearning` (порядок установки; ці два рядки вносить у `config/{manifest.yaml,CONFIG.md}` сам A-17b за versioning.md п. 13 — тут дубль для передачі клієнту; R-05a звіряє CHANGELOG із CONFIG)
- Входить: `addons/` (td_* вкл. `td_<галузь>_elearning`, якщо `elearning.mode: "on"`), `docs/user-guide/`, `config/`, `master-data/`, `templates/`
- Виключено: `support/` (внутрішній KB A-17c), `research/`, `metrics/`, `demo/release-defects.md`

### Сумісність з Odoo        <- лише odoo-upgrade
### Виправлено (hotfix)       <- лише patch: дефект узагальнено, версії клієнтів ідентифікаторами
```
