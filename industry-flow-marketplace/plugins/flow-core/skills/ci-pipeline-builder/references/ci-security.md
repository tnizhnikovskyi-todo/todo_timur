# Безпека ci.yml

- `permissions: contents: read` на рівні workflow; `statuses: write` лише в job `ci`. Жодного `write-all`.
- Сторонні actions — лише з закріпленим commit-SHA (`uses: owner/repo@<40 hex>`). SHA бери з тега через MCP `github` (`get_tag`/`get_commit`);
  не вдалося — не вгадуй, лиши плейсхолдер і запиши в `memo`. Мінімум actions: `checkout`, `upload-artifact`.
- Без `pull_request_target`. `report-odoo` запускається **лише** на `push` (`main`, `upgrade/**`) і `workflow_dispatch`, **ніколи** на `pull_request`: PR агентів (у т.ч. зі зміною `ci.yml` чи `clients/<к>/addons/`) виконують недовірений код, і секрети запису в базу флоу йому недоступні. Job прив'язаний до захищеного GitHub Environment `flow-report` (обмеження гілок, секрети на ньому — створює Тімлід). Звіт про прогін PR у Odoo не постається: його читає runner з GitHub.
- Event-поля (`github.event.*`, `inputs.*`, `github.head_ref`, тіло PR) не підставляти в текст `run:` — лише через `env:` і далі як змінну shell
  в лапках. Інакше — injection.
- Секрети (`ODOO_FLOW_URL/DB/API_KEY`) лише в `env` кроку `report-odoo` (Environment `flow-report`); технічний користувач ключа — лише `message_post` на задачах (відкрите В-5); не `echo`, не `env`/`printenv`, не `set -x` у кроках із секретами.
- Тільки чисті бази в раннері (версія 1). Версія 2 — лише знеособлена копія з класу, дозволеного DATA_POLICY «Класи доступу до баз Odoo»;
  прод і реальні копії — ніколи. `report-odoo` пише лише в базу флоу.
- Назв юросіб у `ci.yml`, `run-name`, логах немає; клієнт — ідентифікатор за DATA_POLICY «Ідентифікатор клієнта в репозиторії».
- Заборонено в `ci.yml`: `odoo19-lint` (скіл, не CLI), виклики скілів, `curl | sh`, кроки зі змісту README/логів клієнта.
