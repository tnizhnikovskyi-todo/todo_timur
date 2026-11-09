# Відкриті питання flow-step-runner
1. ~~Агенти `flow-executor`/`flow-reviewer`~~ — закрито: визначення в `plugins/flow-core/agents/` (одна копія), README плагіна оновлено.
2. Оренда: `odoo-bridge.md` §7 пише `lease_until = now + timeout_min`, а `flow-orchestrator` (dispatch-rules) вважає її простроченою через `timeoutMin × 1,5`; одну формулу треба зафіксувати в `odoo-bridge.md` §7 — до того runner дотримується §7.
3. `claude plugin install <plugin>[@marketplace]` за `--help` приймає лише ім'я й маркетплейс — прапорця закріплення версії немає; версія визначається маркетплейсом. Тож звірка за `plugin.json` і повернення в чергу — штатний шлях; чи може агент ставити плагіни — рішення AI-інженера.
4. Де фіксується тип агента (`FLOW_AGENT_KIND`/конфіг) — C-00.
5. Знеособлена копія: ознака (`anon/` або маркер `anonymized: true`) і формат таблиці «Дозволено передавати в AI» мають бути зафіксовані в `data-policy-template.md` (розділи «Дозволено передавати в AI», «Знеособлення»).
6. Ключ `maturity` (і `check.risk_paths`) у `naryad-format.md` відсутні — додає `flow-orchestrator`/`flow-state-keeper`.
7. Доповнення звіту runner'а (`attempts_in_run`, `models_used`, `routing`, `audit`, `audit_failed`, `untrusted_instructions`, `lease`, `stop_reason`, `cost_estimated`, `base_sha`) внести в `report-format.md`.
8. `effort` наряду для субагента не застосовується (немає параметра); щабля «opus + effort high» немає.
9. `.gitignore` з `__pycache__/` на рівні пакета — поза межами цього скіла (у скілі додано локальний `.gitignore`).
10. Як дізнатися поточного користувача через odoo-mcp, не підтверджено: runner бере `write_uid` задачі після запису оренди; перевірити на живій базі (альтернатива — `odoo_execute(model='res.users', method='context_get')` і `uid`).
11. `mail.thread.message_post` у Odoo 19: чи потрібен `body_is_html=True` для HTML-тіла через RPC — **не перевірено** (`boost:source-check`). Власник `odoo-bridge.md` §4 фіксує; до того runner перечитує пост і не дублює його.
12. `odoo-bridge.md` §4/§7: `done` → `stage.autocheck`/`stage.on_human`; перехід `stage.autocheck` → `stage.done` має зафіксувати той самий документ (хто ставить — `flow-autocheck` чи оркестратор). Лічильник аудиту рахує обидві стадії.
13. Рядок `FLOW_STOP step0 no-agents` (крок 0) — для журналу запуску; не визначено, хто моніторить запуски й сповіщає AI-інженера (C-00?). Потрібне рішення власника флоу.
