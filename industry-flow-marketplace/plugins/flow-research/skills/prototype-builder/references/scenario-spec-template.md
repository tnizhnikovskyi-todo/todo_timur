# Шаблон `e2e/<SC-id>.spec.mjs`

Один файл на сценарій; ім'я — `SC-NN.spec.mjs`. Файл експортує функцію, яку викликає `scripts/record.mjs` (він
створює контекст із `recordVideo`, блокує мережу, збирає помилки). Власних `chromium.launch`, `page.goto` на
http(s) і запису відео в spec немає. Прототип підлаштовується під сценарій, не навпаки.

## Нумерація і очікування кроків
- `SC-xx.n` — номер рядка в таблиці кроків сценарію в `scenarios.md` (колонка «№»). Формат таблиці — «№ | Час | Дія | Екран | Функція»
  (`concept-mapper/references/scenario-example.md`). Якщо сценарій поданий одним рядком (`concept-templates.md`), кроки — це
  екрани зі стовпця «екрани (S-NN)» по порядку.
- `scenarios.md` не містить очікуваного тексту на крок, тому **детермінований fallback** (очікування не вигадуються):
  1. крок з екраном S-xx: `seeTitle(<title екрана S-xx зі screens.md>)`;
  2. якщо дія кроку змінює статус (`set` у `actions`) — додатково `seeState(<нове значення>)`; значення беруться з `screens.json`, що походить із `concept/`;
  3. останній крок: перевірка критерію «Сценарій пройдено, якщо …» — `seeText`/`seeState`, що його відображає; не виходить
     виразити перевіркою на екрані — питання в `memo`, а не вигаданий текст.
- Очікування, якого немає в `scenarios.md` і не виводиться за правилами 1–3, не додавати.

```js
// e2e/SC-01.spec.mjs
export default async ({ goto, step, click, seeTitle, seeState, seeText, pause }) => {
  await goto('S-01');
  await step('SC-01.1', '<дія кроку 1>'); await seeTitle('<title S-01>'); await pause();
  await step('SC-01.2', '<дія кроку 2>'); await click('<testid>'); await seeTitle('<title S-02>'); await pause();
  await step('SC-01.3', '<дія кроку 3>'); await click('<testid>'); await seeState('<новий статус>'); await pause();
};
```
Помічники `record.mjs`: `goto(S-xx)`, `step(id, текст)` (підпис у банері відео), `click(testid)`, `seeTitle`, `seeState`
(`statusbar-current`), `seeText`, `pause(мс=1000)` (0,8–1,5 с для глядача). Таймаут очікування 5 с.

## Правила
- Один `step(...)` на крок сценарію: підпис, дія, перевірка, пауза.
- Лише `data-testid` (`click`) і тексти; CSS-селекторів немає. Оболонка дає: `screen-title`, `statusbar-current`,
  `state-<значення>`, `field-<name>`, `hint-<name>`, `row-<id>` (рядок списку), `card-<id>` (картка kanban), `tile-<name>`, `role-switch`.
- Мережа заблокована `record.mjs`; будь-який не-`file://` запит — FAIL.
- `pause` — лише для глядача, не для синхронізації.
- Червоний крок виправляти в `screens.json`/даних, а не послаблювати spec.
