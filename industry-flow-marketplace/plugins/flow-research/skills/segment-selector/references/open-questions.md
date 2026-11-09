# Відкриті питання segment-selector
- Шлях списку лідів B-01 (`clients/_sales/leads-<дата>.csv`) і списку розсилки A-23
  (`demand/mailing-list.csv`) — додати в `where`/`inArtifacts` карток B-01, A-23 і в `flow/ARTIFACTS.md`.
- Чи email юрособи з відкритого реєстру — `commercial`, де зберігати файл адрес і чи можна імпортувати його в
  Odoo Email Marketing — питання до C-05 і Юриста.
- 300–500 корпоративних адрес у вузькому сегменті недосяжні (меблі, `kved_2010 LIKE '31.0%'`: ~94 за
  знімком 2026-08, перевірка 2026-11-09) — рішення Власника продукту про розширення сегмента або інший
  канал до старту A-23.
- Ваги формули балу A-05/B-01 — затвердити Керівнику напряму при першому запуску (запис у «Параметри
  флоу», C-02).
- Розмір списку лідів B-01 за замовчуванням (50) — оцінка, підтвердити Sales.
- Колонки `fin_history` (`code, year, revenue`) і діалект перевірено 2026-11-09; формат `kved_2010` і значення
  `source` усе одно звірити першим запитом.
- До flow-core: `naryad-format.md` не має `params.size/seed/regions/extra_kved` і `params.mode` для A-23
  (`список|адреси`); потрібен наряд `адреси` з `executor: central`.
- До менеджера карток: оновити `skills`, `skillRef`, `gap` карток A-05, B-01, A-23 на
  `flow-research:segment-selector@0.1.0` (зараз A-05 — `client-web-researcher@<версія>` з `gap: true`, B-01 —
  `gap: true` і скіли sales-prep, A-23 — `client-followup-writer`); без цього runner не підвантажить скіл.
- До `product-decision-drafter`: зафіксувати в `pilot/decision.md` один рядок рішення (`Рішення: тираж|доопрацювати`).
- До flow-core: правило оркестратора для A-23 `адреси` (рядок у таблиці `params.mode` `naryad-format.md`, `executor: central`, перехід у `flow-map.md`); до того наряд створює вручну Тімлід.
- Місце зберігання файлу адрес у `package/DATA_POLICY.md` (тека Drive за ролями) — Юрист; без нього режим `адреси` завершується `waiting_human`.
