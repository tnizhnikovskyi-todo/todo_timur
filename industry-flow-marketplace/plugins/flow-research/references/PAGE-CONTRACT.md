# Контракт сторінки (Artifact, обов'язково)
- Файл: один .html БЕЗ <!doctype>, <html>, <head>, <body> — одразу <title>, <meta name="claude:viewport-fit-sides" content="cover">, <style>, контент, <script>.
- <title> — назва 2–4 слова (напр. «{{Галузевий}} пакет ToDo»), без пояснень після тире.
- Зовнішнє: лише Google Fonts (Open Sans) через <link>, скрипти лише з cdnjs з точною версією (краще без бібліотек). Mermaid — <pre class="mermaid"> рендериться нативно. Жодних iframe, зовнішніх картинок, fetch.
- Логотип ToDo — `references/brand-todo/todo-logo.png`, зменшений, як data:URI (base64 PNG); правила бренду — `brand-todo/BRAND.md`.
- Кольори — токени на :root (світла тема), перевизначення у @media (prefers-color-scheme: dark){:root:not([data-theme="light"]){…;color-scheme:dark}} і :root[data-theme="dark"]{…}. body має явний background з токена. Жодних літеральних кольорів у компонентах.
- Бренд ToDo: акцент #FE5000, темний #101820, шрифт Open Sans; нейтралі злегка тоновані, не чистий сірий.
- Адаптив: працює на 390px; body: padding-left: max(16px, env(safe-area-inset-left,0px)); padding-right: max(16px, env(safe-area-inset-right,0px)); вертикальні — padding-block. Таблиці в контейнері overflow-x:auto. Ніякого горизонтального скролу сторінки. Flex/grid з gap, min-width:0 для дітей з текстом.
- Липкий хедер: top: env(safe-area-inset-top,0px) + body::before смуга.
- Стан сторінки повний без скролу/кліків: не ховати контент під opacity:0. Вкладки/акордеони — ок, але перша вкладка відкрита; навігація по hash (#scenario тощо, ASCII-імена, не settings/sidebar/customize/upgrade/downloads).
- Без window.print, alert/confirm/prompt, <a download>. localStorage лише в try/catch.
- tabular-nums для цифр, text-wrap: balance для заголовків, тексти ~65 символів шириною, prefers-reduced-motion, видимий focus.
- Не робити: емодзі як маркери, нумерацію 01/02 де це не послідовність, однакові картки з тінню скрізь, градієнтний hero, 100vh hero.
- Копірайт: прямо, коротко, без «варто зазначити», без тире-вставок; українська.

## Багатофайловий Artifact (набір із 3 сторінок власника, A-20c)
- Одна публікація = один Artifact із трьома сторінками: `index.html` (концепція), `competitors.html`, `rejected.html`; **той самий URL** при оновленні (публікувати з `url`, не створювати новий).
- `index.html` — за контрактом вище (без `<!doctype>/<html>/<head>/<body>`; обгортку дає публікація). `competitors.html` і `rejected.html` — як **окремі сторінки в `files`**: кожна починається
  з власних `<!doctype html>`, `<meta charset>`, `<meta name="viewport" content="width=device-width,initial-scale=1">` і має власні стилі з тими самими токенами бренду ToDo.
- Верхня навігація між трьома сторінками на кожній; відносні посилання (`index.html`, `competitors.html`, `rejected.html`); активна сторінка — `aria-current="page"`.
- Логотип — `data:`-URI у кожній сторінці. Зовнішніх картинок і `img/` немає (картинки з екранів — лише якщо їх дав крок A-21; для A-20c — без них).
- Кожна сторінка ≤ 60 KB шаблону (після наповнення — ліміт публікації 16 MB, але сторінка має відкриватись без затримки).
- Копія всіх трьох файлів — у репо: `docs/industries/<галузь>/research/owner-page/`. Після публікації скіл пише `research/owner-page/PUBLISHED.md`: URL Artifact, дата, SHA комітів, список сторінок.
- Сторінка без грошового блоку (окупність, TCO, «вердикт про гроші» — заборонені; `check_owner_page.py` OP-money). Вето власника — лише через «Скопіювати мої заперечення» (готові рядки `AI-NN: не згоден — <що замість>` лише для відмічених рядків блоку «Що вирішив AI і з яким ризиком») → людина/AI вносить їх у `flow/decisions.md` (колонки — `flow-core/references/flow-state.md` §3; для AI — режим `veto-batch` із посиланням на повідомлення власника).
- Перевірка: `check_owner_page.py` (OP-pages, OP-nav, OP-anchors, OP-contract, OP-money, OP-target) + Playwright на 390 і 1280 px: `document.documentElement.scrollWidth <= clientWidth`.
