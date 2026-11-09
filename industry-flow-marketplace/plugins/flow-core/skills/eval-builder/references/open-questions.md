# Відкриті питання eval-builder

Нотатки проєктування для власників; агент їх не виконує й не вгадує.

## Умови, без яких `done` недосяжний під runner'ом (власник — Власник продукту / AI-інженер)
1. `flow-autocheck/references/checks/C-04.yaml` і `C-07.yaml`: механічні `scope-evals-only`, `json-schema`, `no-pii`, `source-filled`,
   `skills-covered`, `incident-case`; решта (`index-checks.md`) — MANUAL. Без них runner дає `INCOMPLETE (spec-missing)` = збій, ручні
   перевірки заборонені -> результат `escalated`. Якщо специфікації відкладаються — прибрати `weekly: [C-04]` з `dispatcher-config.md` і
   рядок про C-04 із `sweep-rules.md` (інакше оркестратор і далі ставить C-04 щотижня).
2. `flow-step-runner`: виняток — для `skill_ref[0] = flow-core:eval-builder` крок виконує агент з Bash сам, без `flow-executor`
   (виконавець без Bash повертає лише «КОМАНДИ: …»). Альтернатива — два проходи (кейси й розкладка; потім статуси й INDEX), другий
   не рахується спробою.
3. Картки C-04/C-07: `skillRef` -> `flow-core:eval-builder@<версія>` першим (C-07: `debug-root-cause` — вхід, розбір уже в
   `flow/ai-incidents/<id>.md`); `done` C-07: «пропозицію пониження сформовано, кейс інциденту є»; `where` без «картка кроку (maturity)»;
   `checkHow` авто: «`maturity_proposals` присутній, якщо умова виконана». Оновити CONCEPT (розклад).
4. `naryad-format.md`: рядки `params.mode` для C-04 (`weekly|init|regress`) і C-07 (`incident`); `report-format.md`: блок `evals:`.
   До того носій пропозицій зрілості — `evals/INDEX.md` (таблиця 2).

## Інше
- Репозиторій плагінів каталогу (картка C-04: «не визначено»).
- Шлях карток у репо флоу (`flow/cards/<code>.json` — пропозиція C-01).
- Харнес прогону кейсів кроку (`requires: ["step-run"]`) — рішення AI-інженера; до того такі кейси `skipped`.
- Хто записує нове `maturity` після кнопки: `flow-state-keeper` (PR автоекспорту) чи людина — узгодити з C-02.
- Ліміт $5 / 45 хв замалий для `init` по всіх скілах і `regress` по всіх плагінах: окремі ліміти чи серія запусків порціями.
- Скрипти `scripts/evals_to_cli.py`, `index_check.py`, `pii_scan.py` ще не створено.
- Перенос зрілих кейсів у `skills/<s>/evals/` плагіна — лише Тімлід у репо плагіна.
