# Відкриті питання flow-step-runner
1. ~~Агенти `flow-executor`/`flow-reviewer`~~ — закрито: визначення в `plugins/flow-core/agents/` (одна копія), README плагіна оновлено.
2. ~~Формула оренди~~ — закрито: єдина формула `timeout_min × lease_factor` у `odoo-bridge.md` §7; runner її не дублює.
3. `claude plugin install <plugin>[@marketplace]` за `--help` приймає лише ім'я й маркетплейс — прапорця закріплення версії немає; версія визначається маркетплейсом. Тож звірка за `plugin.json` і повернення в чергу — штатний шлях; рішення q21: окремий репозиторій каталогу, закріплення — тег релізу; чи може агент ставити плагіни — рішення AI-інженера.
4. Де фіксується тип агента (`FLOW_AGENT_KIND`/конфіг) — C-00.
5. Знеособлена копія: рішення q02 — пілот без знеособлених копій; ознака (`anon/` або маркер `anonymized: true`) визначається після пілоту (розділи `data-policy-template.md` «Дозволено передавати в AI», «Знеособлення»); до того клас «знеособлено» не використовується.
6. ~~Ключ `maturity` / `check.risk_paths`~~ — закрито: описані в `naryad-format.md`.
7. ~~Доповнення звіту runner'а (`attempts_in_run`, `models_used`, `routing`, `audit`, `audit_failed`, `untrusted_instructions`, `lease`, `stop_reason`, `cost_estimated`, `base_sha`) ~~ — закрито: внесено в `report-format.md` (розділ «Доповнення runner»).
8. `effort` наряду для субагента не застосовується (немає параметра); щабля «opus + effort high» немає.
9. `.gitignore` з `__pycache__/` на рівні пакета — поза межами цього скіла (у скілі додано локальний `.gitignore`).
10. Як дізнатися поточного користувача через odoo-mcp, не підтверджено: runner бере `write_uid` задачі після запису оренди; перевірити на живій базі (альтернатива — `odoo_execute(model='res.users', method='context_get')` і `uid`).
11. `mail.thread.message_post` у Odoo 19: чи потрібен `body_is_html=True` для HTML-тіла через RPC — **не перевірено** (`boost:source-check`). Власник `odoo-bridge.md` §4 фіксує; до того runner перечитує пост і не дублює його.
12. `odoo-bridge.md` §4/§7: `done` → `stage.autocheck`/`stage.on_human`; перехід `stage.autocheck` → `stage.done` має зафіксувати той самий документ (хто ставить — `flow-autocheck` чи оркестратор). Лічильник аудиту рахує обидві стадії.
13. Рішення q23: аварійні зупинки (`FLOW_STOP`) фіксуються активністю в задачі Odoo для AI-інженера (поведінка — runner, крок 0). Відкрито (вузько): чи має технічний користувач агента право створювати `mail.activity` (зараз `odoo-bridge.md` §6 дозволяє лише `message_post`); в якій задачі створювати активність, коли наряд ще не взято (вказує людина чи є службова задача C-00).
