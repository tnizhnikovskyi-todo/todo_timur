# Публікація набору з 3 сторінок (A-20c)

Скіл **не публікує сам**: інструмент публікації Artifact (веб-хостинг claude.ai) доступний сесії runner, не профілю `base`. Тому в «Запис» скіл лише готує файли й рядок «КОМАНДИ:», який виконує `flow-core:flow-step-runner` (як для будь-якого Bash/Playwright).

## Файли
- Каталог: `docs/industries/<галузь>/research/owner-page/` — `index.html`, `competitors.html`, `rejected.html` (копія в репо = те, що опубліковано).
- `index.html` — основна сторінка Artifact (без `<!doctype>/<html>/<head>/<body>`); `competitors.html`, `rejected.html` — додаткові файли `files` із власними `<!doctype html>`, `charset`, `viewport`.
- Відносні посилання між сторінками (`index.html`, `competitors.html`, `rejected.html`); зовнішніх картинок немає.

## КОМАНДИ (виконує runner)
```
КОМАНДИ:
1. python3 -I <корінь flow-research>/skills/concept-presentation/scripts/check_owner_page.py docs/industries/<галузь>/research/owner-page --research docs/industries/<галузь>/research   # без FAIL; для зразка додати --sample (навігація на дві інші сторінки в зразку неактивна)
1а. сусідні скрипти за flow-core/skills/flow-autocheck/references/checks/A-20c.yaml: check_facts (--require-markers не для зразка), check_brand, check_privacy, check_intake --page …/index.html, check_rejected, check_stale; DEPENDS.yaml існує
2. Playwright 390 і 1280 px: для кожної сторінки document.documentElement.scrollWidth <= clientWidth; знімки -> `research/owner-page/screens-390/` і `screens-1280/` (їх пише runner, не скіл; цього вимагають `A-20c.yaml` (`reviewer-shots`) і чек-лист `owner-page.md`; `check_owner_page.py` ці теки допускає; чи вносити їх у `outArtifacts` картки A-20c — запит власникам пакета)
3. artifact-publish: перша публікація — Artifact з file_path=index.html і files={competitors.html, rejected.html}; повторна — з url із research/owner-page/PUBLISHED.md (той самий URL, не новий)
4. записати research/owner-page/PUBLISHED.md
```
Артефакт створюється приватним; передавання посилання власнику — рішення людини (BA/Власник продукту), не скіла.

## `PUBLISHED.md`
```
# Публікація сторінок власника
URL Artifact: <посилання>
Дата: <ISO>
Режим: sample | full   # sample — публікується index.html; full — повний обсяг на той самий URL
SHA комітів: <sha гілки кроку>
Сторінки: index.html, competitors.html, rejected.html
Версія: <N> (повторна публікація — той самий URL)
```
Без URL (інструмент недоступний) — `waiting_human`: «опублікувати рядком КОМАНДИ вручну»; URL не вигадувати.

## Оновлення
Після повернення з гейта (`gate.return_to`) і перерахунку (`params.mode: recalc`) — публікація з `url` із `PUBLISHED.md`; «Скопіювати мої заперечення» на сторінці лишається в тому ж місці; стара чернетка в браузері власника зберігається за `KEY` (версію ключа підняти, якщо змінився склад питань).
