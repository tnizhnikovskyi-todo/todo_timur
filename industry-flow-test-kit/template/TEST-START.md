# TEST-START — тест пакета скілів industry-flow, етап 1 (без Odoo, галузь «меблі»)

Мета етапу: перевірити, що скіли кроків A-01, A-03, A-04, A-05, A-20, A-21, A-23 (підготовка) знаходять свої входи, пишуть результат за `where`, проходять власні автоперевірки, і що формати сусідніх кроків зчіплюються (результат попереднього = вхід наступного). Odoo, черга, кнопки гейтів — поза етапом (розділ «Що тест НЕ перевіряє»).

## (а) Репозиторій уже готовий
Цей репо (`tnizhnikovskyi-todo/industry-flow-test-mebli`) уже містить усе: копію пакета `industry-flow-marketplace/` (без `_work/`), 29 скілів у `.claude/skills/`, 7 агентів у `.claude/agents/` (flow-executor, flow-executor-{drive,mail,outreach,repo,research}, flow-reviewer), каркас пакета «меблі», наряди `tests/naryad/`, правила тестового режиму `CLAUDE.md`. Нічого копіювати чи запускати bootstrap не треба.
Обмеження хмарних сесій: плагіни з `.claude/settings.json` не встановлюються, тому скіли лежать копіями в `.claude/skills/` — хмарна сесія підхоплює їх з клону.

## (б) Запуск хмарної сесії
Нова хмарна сесія Claude Code лише з цим репо (гілка `main`). Перевір `/skills` — у списку мають бути скіли пакета (industry-scoring, concept-mapper, prototype-builder…). Якщо їх немає — відкрий сесію ще раз (скіли підхоплюються при старті).

## (в) Перший промпт
```
Запусти `bash tests/restore-input.sh`, прочитай CLAUDE.md і TEST-START.md і скажи, що готовий до кроку A-01.
```
`docs/industries/*/_input/` поза git (`sources-format.md`): у кожній новій сесії спершу `bash tests/restore-input.sh` (без `crm.csv` A-05 зупиниться «очікує людину: crm.csv»); `sources.md` заповнюй у тій сесії, де запускаєш A-04.
Оновлення пакета (якщо скіли змінено в `tnizhnikovskyi-todo/todo_timur`, гілка `claude/ecstatic-einstein-wf59oh`) — `industry-flow-test-kit/bootstrap.sh` у тому репо; його запускає власник набору й пушить сюди.

## (г) Конектори (увімкнути до початку)
| Конектор | Для чого | Кроки |
|---|---|---|
| `odb-catalog` (MCP) | `query`/`db_schema` по реєстру компаній (знімок серпня 2026) | A-01, A-05, A-23 `список` |
| `AIKB` | звіти минулих проєктів (режим «лише звіти») | A-04 |
| Fathom | у тесті **не використовується** (DATA_POLICY); якщо є — не вмикати для A-04 | — |
| Chromium/Playwright | наявність не перевірена: перед A-21 виконай `npx playwright --version`; якщо немає — запиши в `observations/` і крок A-21 пропусти | A-21 |
| Веб-пошук (WebSearch/WebFetch) | ринок рішень, регуляторика | A-01, A-03 |
| GitHub (відкриття PR у тестовому репо) | PR кроку | усі |
| Каталог організації: плагін `odoo19-discovery-initiation` | скіл `industry-briefing` | A-03 |
| `odoo-mcp` | **вимкнений / не використовувати** (`odoo_connections: []`) | — |

## (д) Порядок кроків і готові промпти
Правила тесту — у `CLAUDE.md` (ТЕСТОВИЙ РЕЖИМ). Один крок = одна гілка `flow/<крок>-test` і один PR; перед наступним кроком **заміржи PR попереднього** (або працюй на одній гілці — тоді в `inputs` SHA = HEAD цієї гілки). Після кожного кроку читай `tests/reports/<ім’я наряду>[-<спроба>].md` (A-23-spisok.md, A-23.md, A-04-1.md, A-04-2.md) (`result`, `checks`, `memo` — спершу «Невпевнений:»).

| # | Крок | Промпт | Перед запуском | Перевір після («Готово, коли» скіла) |
|---|---|---|---|---|
| 1 | A-01 | `Виконай крок A-01 за нарядом tests/naryad/A-01.yaml скілом industry-scoring у тестовому режимі CLAUDE.md` | конектор odb-catalog; критерій уже в `flow/params.md`; для `check_scoring.py` передавай `--param flow/params/A-01-criterion.md` (не `params.md`) | `docs/industries/scoring.md`: топ-10 розділів КВЕД-2010 з метриками; біля кожної цифри `[odb 2026-08]`; є 8 заголовків і розділ «SQL-запити»; 3 цифри збігаються з запитом; `check_scoring.py` без FAIL (SC-repro — MANUAL у memo); меблі (31) у рейтингу — зауваж місце |
| 2 | A-02 | (людський крок) — рішення вже в `docs/industries/mebli/decision.md` і `flow/decisions.md` (№2) | можна змінити сегмент у `decision.md` | файл `decision.md` читається наступними скілами |
| 3 | A-03 | `Виконай крок A-03 за нарядом tests/naryad/A-03.yaml скілом odoo19-discovery-initiation:industry-briefing у тестовому режимі CLAUDE.md. Компанії немає — галузевий брифінг для пакета; галузь, країна (Україна) і розмір — з decision.md; назву компанії не вигадувати.` | каталог організації; веб-пошук | `docs/industries/mebli/briefing.md`: процеси галузі, болі, регуляторика з джерелами (або `[перевірити]`), модулі Odoo; немає назв клієнтів. «Структура відділів» у форматі industry-briefing 0.12.1 відсутня — очікувана розбіжність сусідніх форматів: запиши в `observations/`, провалом кроку не вважай. Зауваж: чи скіл писав у `where`, а не в `outputs/`; чи не вигадав назву компанії |
| 4 | A-04 | `Виконай крок A-04 за нарядом tests/naryad/A-04.yaml скілом past-projects-analyzer у тестовому режимі CLAUDE.md` | AIKB. Спершу прогін «як є»: порожній `_input/sources.md` -> очікуваний `waiting_human` (перевір, що скіл нічого не вигадав; звіт `A-04-1.md`). Потім заповни `sources.md` (≥1 рядок П-xx; «0 проєктів» можливе лише коли код П-xx у файлі є) і повтори (звіт `A-04-2.md`). Реальні проєкти AIKB у режимі «лише звіти» чи тестова заглушка `past-projects.md` «0 проєктів» — рішення людини (відкрите питання DATA_POLICY) | `docs/industries/mebli/past-projects.md`: шість розділів, усі рядки з П-xx і ідентифікатором `aikb:…`, без назв клієнтів; `check_past_projects.py` — PP-* PASS; `_input/` не в git |
| 5 | A-05 | `Виконай крок A-05 за нарядом tests/naryad/A-05.yaml скілом segment-selector у тестовому режимі CLAUDE.md` | A-03 змержено; `_input/crm.csv` є (порожній) | `reference-clients.md`: «Раунд 1: <дата>», 5–6 кандидатів, K-xx, ЄДРПОУ, статус «кандидат», тег знімка; без ПІБ/контактів; колонки частини 2 порожні; результат `waiting_human` (Sales, phase 2) — штатно |
| 6 | A-20 | `Виконай крок A-20 за нарядом tests/naryad/A-20.yaml скілом concept-mapper у тестовому режимі CLAUDE.md` | A-03 і A-04 змержено: concept-mapper (Крок 0) вимагає `past-projects.md`, без нього стоп «очікує A-03/A-04». Тому A-04 із заповненим `sources.md` (≥1 П-xx) обов’язковий, навіть якщо результат «0 проєктів» | `concept/features.md`, `screens.md`, `scenarios.md`; ID ROLE/PAIN/F/S/SC; кожна F-xx має біль із дослівною цитатою; 10–15 екранів; 4–6 сценаріїв; `check_concept.py` без FAIL |
| 7 | гейт A-20 | (людина) | дослідь `concept/`; якщо ок — додай у `flow/decisions.md` рядок «A-20 … package/mebli … затверджено» | — |
| 8 | A-21 | `Виконай крок A-21 за нарядом tests/naryad/A-21.yaml скілом prototype-builder у тестовому режимі CLAUDE.md` | `npx playwright --version` (якщо немає — `observations/`, крок пропустити); A-20 змержено | `prototype/index.html` відкривається, банер «Прототип, не робоча система»; відео на кожен сценарій; `complexity.md` для кожної F-xx; `check.mjs` (VP-*) без FAIL. Зауваж: чи скіл зупинився через `odoo_connections: []` |
| 9 | гейт A-21 | (людина) | додай у `flow/decisions.md` рядок «A-21 … package/mebli … затверджено» (`grep 'A-21' flow/decisions.md \| grep mebli` має його знайти) | — |
| 10 | A-23 `список` | `Виконай крок A-23 за нарядом tests/naryad/A-23-spisok.yaml скілом segment-selector у тестовому режимі CLAUDE.md` | odb-catalog; не запускати режим `адреси` | `demand/mailing-list.csv` + `.md` без адрес і телефонів; розмір 300–500 **або** розділ «Нестача корпоративних адрес» із лічильниками (очікувано для меблів); тег знімка; seed записано |
| 11 | рішення A-23 | (людина, якщо була «Нестача…») | додай у `flow/decisions.md` рядок A-23, scope mebli, у коментарі слово «досяжн…» і вибір: новий список / дзвінок / менший тест | — |
| 12 | A-23 `prep` | `Виконай крок A-23 за нарядом tests/naryad/A-23.yaml скілом demand-test-runner у тестовому режимі CLAUDE.md` | кроки 8–11 виконано; **нічого не надсилати** | `demand/thresholds.md` (6 розділів, пороги Р3–Р5б, «Тривалість»), `landing.md` (2–3 варіанти за `варіант` у CSV, форма «Заявка на пілот»), `emails.md`, `mailing-plan.md`; DT-honesty/variants/utm/reach/wave PASS; DT-consent = FAIL з плейсхолдером «текст згоди — Юрист» — очікувано (зауваження, не збій) |

Мінімум для швидкого проходу: кроки 1, 3, 4, 6, 8 (briefing -> past-projects -> concept -> prototype); крок 4 — із заповненим `sources.md`, бо A-20 потребує `past-projects.md`. Кроки 4, 5, 10, 12 — для перевірки сусідніх форматів і відомих відкритих питань.

### Куди писати зауваження
Усе, що розходиться з очікуванням, — у `observations/` через скіл `boost:skill-feedback` («запиши замечання до скіла industry-scoring: …»; одне зауваження — один файл; формат скіла). Дублюй у `tests/reports/<ім’я наряду>[-<спроба>].md`, поле `observations`. Що саме фіксувати — `observations/README.md`. Відкриті питання до власників пакета не вирішуй сам: запиши в `flow/open-questions.md`.
Особливо шукай: скіл не знайшов вхід, який мав за контрактом; шлях/формат результату не збігається з очікуваним сусіднім скілом; скіл вимагає Odoo/`flow` попри `odoo_connections: []`; посилання `flow-core/references/…` або `${CLAUDE_PLUGIN_ROOT}` не розв'язались у розкладці `CLAUDE.md`.

## (е) Чого цей етап НЕ перевіряє
- Чергу Odoo, `message_post`, стадії задач, оренду, дзеркальні поля, автоекспорт `flow/state.md` — наряд читається з файлу.
- Повний runner (`flow-step-runner`, C-06): аудит зрілості, драбину моделей, ескалації, лічильники спроб; `flow-orchestrator`, `flow-state-keeper`, `flow-autocheck`, `gates-aggregator` — не запускаються.
- Кнопки «Затвердити/Повернути» й права на них: рішення імітує людина рядком у `flow/decisions.md`.
- Кроки A-06 (сесії з еталонними клієнтами), A-22, A-23 `адреси` і `results` (розсилки немає), A-07 і далі (A-08…A-19), пули B, C, D; скіли `flow-package-build`, `flow-package-evolution`, `flow-client-delivery` (копіюються, але не тестуються).
- Дані клієнтів і Fathom; прод Odoo; реальну розсилку.
- Те, що плагіни в хмарі не встановлюються через `settings.json`: у тесті скіли — копії; перевірка встановлення плагінів (`claude plugin validate`, `skill_ref` з реальними версіями) — окремий етап.

## (є) Очікувана поведінка тесту (не дефекти скілів)
- A-04: у тесті без клієнтів виконавець `central`, а `client_data` — `personal`; це штатна розбіжність, рішення — за людиною (відкрите питання).
- A-21: зупинка через `odoo_connections: []` очікувана; обхід не вигадувати.
- A-03: `industry-briefing` може писати в `outputs/`, а не за `where` — запиши в `observations/`, не дефект.
- A-23 `prep`: DT-consent = FAIL (плейсхолдер «текст згоди — Юрист») — очікувано.
- Кількість агентів у bootstrap — 7 (не 2): flow-executor, п'ять flow-executor-*, flow-reviewer.
