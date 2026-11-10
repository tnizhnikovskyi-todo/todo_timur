# Зведений чек-лист C-00 (людський крок: налаштування бази й інструментів)

Зведення вимог скілів до C-00. Подробиці й формулювання питань — у розділах «Відкриті питання» вказаних скілів. Технічні імена полів і стадій у скілах не вигадуються: їх фіксує C-00.

- [ ] `flow/ODOO_SCHEMA.md`: технічні імена кастомних полів проєкту/задачі і стадій (`stage.*`) — `odoo-bridge.md`, `flow-orchestrator`, `flow-state-keeper`.
- [ ] Автоматизація Odoo «задача C-01 на зміну стадії» — `flow-orchestrator`, `flow-state-keeper`.
- [ ] Класи баз і alias у `odoo-mcp`: `flow`, `test-<клієнт>`, `test-pkg-<пакет>`, `demo-<пакет>`, `emu-<галузь>`; рішення про `anon-<клієнт>` — прод-alias заборонено; про `data-and-connections.md` §3.5, `package-upgrade-runner`, `package-usage-metrics`.
- [ ] Скрипти `tools/odoo/`: шаблони є в `references/templates/tools-odoo/` (README там) — C-00 копіює, адаптує й перевіряє на тестовій базі; `import.sh` і snapshot/restore реалізує C-00; також C-00 звіряє опції демо-даних Odoo 19, текст підсумку тестів (і skipped) та гарантує, що `PGHOST`/`db_host` — непродовий сервер. Вимоги скілів: (чиста база за тегом, установка, імпорт шаблонів, smoke, знімок/скидання, тести) — `ci-pipeline-builder`, `demo-base-builder`, `master-data-template-builder`, `package-release-builder`, `odoo-version-migrator`.
- [ ] Тип агента (`FLOW_AGENT_KIND`/конфіг) і технічні користувачі агентів — `flow-step-runner` (open-questions №4), `odoo-bridge.md` §6.
- [ ] Хто моніторить рядок `FLOW_STOP step0 no-agents` і сповіщає AI-інженера — `flow-step-runner` (open-questions №13).
- [ ] Встановлення плагінів агентом і закріплення версії (тег каталогу) — `flow-step-runner` (open-questions №3), `eval-builder`.
- [ ] Ліміти запуску (`costLimit`, `timeoutMin`) для `init`/`regress` евалів і довгого CI — `eval-builder`, `package-upgrade-runner`, `demo-base-builder`.
- [ ] Джерело календаря `work_calendar` і `lease_factor` — `flow-orchestrator` (`dispatcher-config.md`).
- [ ] Прапорець HTML у `message_post` (Odoo 19) — `flow-step-runner` (open-questions №11), `odoo-bridge.md` §4.
- [ ] Кнопка зміни зрілості кроку і хто записує `maturity` — `flow-state-keeper`, `eval-builder`.
- [ ] До першої диспетчеризації оновити в картках `skills`/`skillRef`/`gap`/`raciR` за `references/step-skill-map.md` (зараз жодна картка не посилається на скіл пакета).
- [ ] `PGHOST`/`ODOO_CONF` скриптів `tools/odoo/` — лише непродовий сервер; `guard_db` перевіряє тільки ім'я бази, тож C-00 додає перевірку хоста в `_common.sh`.
