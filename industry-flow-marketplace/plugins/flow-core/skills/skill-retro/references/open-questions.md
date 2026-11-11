# Відкриті питання skill-retro

## До людини
1. Реєстр репо для спостереження (поле проєкту Odoo флоу): назва поля й ким заповнюється — власник схеми Odoo; до того — перелік у `params.repos` наряду.
2. Чи має профіль `repo` читати журнал запусків Odoo напряму (alias `flow`) або його надає runner у теці контексту — рішення власника пакета (до того — тека контексту).
3. Джерело «частка правок людини після AI» (diff PR ↔ merge) — доступність у GitHub MCP без запису; недоступно -> `н/д`.
4. Хто фіксує рішення «C-08R лише пропонує евал-кейс (`eval_статус: запропоновано`), кейс створює eval-builder нарядом C-04»: **відкрите питання до AI-інженера** (підтвердити чи змінити). Дія за замовчуванням, поки відповіді немає: діє схема «пропонує -> C-04 створює»; `eval-builder weekly` сам підбирає всі `запропоновано`.

## Запити до координатора (єдиний перелік за WP-11; усі — до інших пакетів, WP-11 їх файли не змінює)
| До | Що | Чому |
|---|---|---|
| WP-03 | `flow-autocheck/references/checks/C-08R.yaml`: замінити `script-check-lessons` на `python3 -I skills/skill-retro/scripts/check_retro.py --signals flow/lessons/signals-<дата>.json --lessons flow/lessons/ --today <дата>` | `check_lessons.py` без `--task/--since` для C-08R дає SKIP; покриття сигналів перевіряє лише `check_retro.py` |
| WP-03 | Дозволені шляхи `ACCEPTED.md` (`flow-autocheck`) — звірити з `flow/lessons/**` | вихідні артефакти C-08R |
| WP-01 | Правило диспетчера `flow-orchestrator`: звіт C-08R з `next: C-04` -> наряд C-04 з `params.lessons [LSN-…]`; ключ `params.lessons` у `flow-core/references/naryad-format.md` | замкнути цикл «урок -> евал -> закриття» |
| WP-01 | `flow-map.md`/картка C-08R: без змін, INDEX.md лишається вихідним артефактом C-08R (автор — skill-retro); keeper його не рендерить | узгодженість із `lessons-index` у `C-08R.yaml` |
| план §5 | SHA еталонів «меблі» (`eval-builder/references/gold/mebli.md`) — рішення власника пакета | кейси на еталонах без SHA лишаються «відкрите питання» |
