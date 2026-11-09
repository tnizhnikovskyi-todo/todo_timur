# Шаблон `e2e/<SC-id>.spec.mjs`

Один файл на сценарій. Кроки й очікування беруться зі `scenarios.md`; прототип підлаштовується під них, а не навпаки.

```js
import { test, expect } from '@playwright/test';
const URL = process.env.PROTOTYPE_URL;            // file://…/prototype/index.html, ставить record.mjs
const pause = (page) => page.waitForTimeout(1000); // 0,8–1,5 с для глядача
const caption = (page, text) => page.evaluate((t) => window.__caption && window.__caption(t), text);

test('SC-01 <назва сценарію>', async ({ page }) => {
  await page.goto(URL + '#/S-01');

  // SC-01.1 <дія кроку зі scenarios.md>
  await caption(page, 'SC-01.1 <дія>');
  await page.getByTestId('<testid>').click();
  await expect(page.getByText('<очікуваний текст зі scenarios.md>')).toBeVisible();
  await pause(page);

  // SC-01.2 …
});
```

## Правила
- Один `// SC-xx.n` блок на крок сценарію: підпис у банері відео, дія, перевірка очікуваного, пауза.
- Лише `getByTestId` і `getByText`; CSS-селекторів немає.
- Очікування — текст або стан, названий у `scenarios.md`. Немає в сценарії — не вигадувати; питання в `memo`.
- Мережа заблокована `record.mjs` (дозволено лише `file://`); у spec жодних `page.goto` на http(s).
- Таймаут кроку — типовий Playwright; `waitForTimeout` лише як пауза для глядача, не для синхронізації.
- Відео пише `record.mjs` (`recordVideo`), spec нічого не записує сам. Файл `video/<SC-id>.webm`.
- Не змінювати spec під «зелений» результат: червоний крок → виправляти `screens.json`/дані.
