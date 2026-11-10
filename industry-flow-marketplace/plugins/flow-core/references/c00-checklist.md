# Зведений чек-лист C-00 (людський крок: налаштування бази й інструментів)

Зведення вимог скілів до C-00. Подробиці й формулювання питань — у розділах «Відкриті питання» вказаних скілів. Технічні імена полів і стадій у скілах не вигадуються: їх фіксує C-00.

- [ ] `flow/ODOO_SCHEMA.md` (q14: AI-чернетка, Тімлід затверджує): технічні імена кастомних полів проєкту/задачі і стадій (`stage.*`) — `odoo-bridge.md`, `flow-orchestrator`, `flow-state-keeper`.
- [ ] q10: назва стадії угоди CRM «підписано» і поле-дзеркало в проєкті клієнта; C-01 за ним вписує в наряди B-02/B-04/B-06/B-11 ключ `preconditions_confirmed.crm_deal_stage` (`discovery_signed` для B-02, `sow_signed` для B-04/B-06/B-11; `naryad-format.md`) — `flow-orchestrator`, `odoo-bridge.md`.
- [ ] q37: Тімлід підтверджує, що технічний користувач `prod-ro-<клієнт>` не має прав запису/створення/видалення (роль, дата) і вносить рядок у `kb-index.md` клієнта — без цього `client-help-bot` `answer` не читає прод.
- [ ] Автоматизація Odoo «задача C-01 на зміну стадії» — `flow-orchestrator`, `flow-state-keeper`.
- [ ] Тестові бази не називати з «prod» в імені (`guard_db` відхиляє, напр., `test-prod`).
- [ ] Класи баз і alias у `odoo-mcp`: `flow`, `test-<клієнт>`, `test-pkg-<пакет>`, `demo-<пакет>`, `emu-<галузь>`; `anon-<клієнт>` відкладено після пілоту (q02/q03); прод-alias заборонено, окрім `prod-ro-<клієнт>` для `client-help-bot` (q37, read-only, технічний користувач клієнта з мінімальними групами); про `data-and-connections.md` §3.5, `package-upgrade-runner`, `package-usage-metrics`.
- [ ] Скрипти `tools/odoo/`: шаблони є в `references/templates/tools-odoo/` (README там) — C-00 копіює, адаптує й перевіряє на тестовій базі; `import.sh` і snapshot/restore реалізує C-00; також C-00 звіряє опції демо-даних Odoo 19, текст підсумку тестів (і skipped) та гарантує, що `PGHOST`/`db_host` — непродовий сервер. Вимоги скілів: (чиста база за тегом, установка, імпорт шаблонів, smoke, знімок/скидання, тести) — `ci-pipeline-builder`, `demo-base-builder`, `master-data-template-builder`, `package-release-builder`, `odoo-version-migrator`.
- [ ] Тип агента (`FLOW_AGENT_KIND`/конфіг) і технічні користувачі агентів — `flow-step-runner` (open-questions №4), `odoo-bridge.md` §6.
- [ ] Налаштування q23: технічному користувачу агента дозволено створювати активність (`mail.activity`) AI-інженеру в задачі Odoo для `FLOW_STOP`; AI-інженер у переліку отримувачів сповіщень Odoo (`flow-step-runner`, open-questions №13).
- [ ] q26: AI-інженер проганяє 1 згенерований `evals_to_cli.py` кейс через реальний `claude plugin eval` до подання пакета (`eval-builder`, open-questions).
- [ ] q24: на першому прогоні C-03 перевірити, що MCP `github` повертає `display_title`; запас — пошук за SHA (`ci-pipeline-builder`).
- [ ] Встановлення плагінів агентом і закріплення версії (q21: окремий репо каталогу, тег релізу) — `flow-step-runner` (open-questions №3), `eval-builder`.
- [ ] Ліміти запуску (`costLimit`, `timeoutMin`) для `init`/`regress` евалів і довгого CI (q25: порції; CI поза таймаутом) — `eval-builder`, `package-upgrade-runner`, `demo-base-builder`.
- [ ] Джерело календаря `work_calendar` і `lease_factor` — `flow-orchestrator` (`dispatcher-config.md`).
- [ ] Прапорець HTML у `message_post` (Odoo 19) — `flow-step-runner` (open-questions №11), `odoo-bridge.md` §4.
- [ ] Кнопка зміни зрілості кроку; `maturity` записує AI у PR автоекспорту (q16); PR автоекспорту — auto-merge за перевіркою (q22) — `flow-state-keeper`, `eval-builder`.
- [ ] До першої диспетчеризації оновити в картках `skills`/`skillRef`/`gap`/`raciR` за `references/step-skill-map.md` (зараз жодна картка не посилається на скіл пакета).
- [ ] `PGHOST`/`ODOO_CONF` скриптів `tools/odoo/` — лише непродовий сервер; `guard_db` перевіряє тільки ім'я бази, тож C-00 додає перевірку хоста в `_common.sh`.
- [ ] Еталони `install.sh` (доставка `--addons-src` у `ODOO_DELIVERY_DIR` ∈ `ODOO_ADDONS_PATH` + `--tag`), `apply.py`, `validate.py` (q17): C-00 копіює в `tools/odoo/`, задає `ODOO_DELIVERY_DIR` (ОКРЕМИЙ каталог доставки, не стандартні addons Odoo), `ODOO_URL`/`ODOO_LOGIN`/`ODOO_API_KEY` (технічний користувач тестової бази), `ODOO_ALLOWED_HOSTS` і проганяє на реальній тестовій базі Odoo 19; рішення людини: сигнатури еталонів `install.sh`/`validate.py` відрізняються від контракту `config-package-format.md` (перейменувати чи змінити контракт); звіряє відкриті питання з README шаблонів (JSON-2, коміт `odoo-bin shell`, `res.config.settings`, `update_list` при `-i`).
