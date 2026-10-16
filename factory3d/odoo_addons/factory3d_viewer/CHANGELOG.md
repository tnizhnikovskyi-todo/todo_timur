# Changelog

## Unreleased
- Заявки ТО в картках (обладнання, робочий центр, вентустановка, пожежна група): замість «Планове ТО · Планове ТО» — пілюля
  «<тема> · <обладнання> · <стадія> · ДД.ММ[, прострочено N дн.]» і кнопка «Відкрити заявку в Odoo». Плановому ТО без відкритої
  заявки (дата минула або ≤ 7 днів) — кнопка «Запланувати ТО» і рядок у «Потребує уваги»: `POST /f3d/viewer/maintenance/plan`
  (API-11, R-22; jsonrpc, ідемпотентно, не для кіоску, перевірка права `create`). У payload заявки мають `res_id` (назви
  не унікальні), обладнання — `maintenance_request_id`, `maintenance_due`; картка обладнання більше не падає, коли `meta.iot.updated = null`.
- Вихід зі сторінки під час `load()`: відхилений fetch після `destroy()` більше не кидає «TypeError: Cannot read properties of null (reading 'classList')» у `loadFailed` і не показує «Не вдалося завантажити дані»; `load()` перевіряє `destroyed` після кожного `await`, `loadFailed`/`syncConnState` не звертаються до знесеного DOM, дія й обгортка `F3dViewer` тихі після закриття (HOOT R19g–R19l).
- Склад у 3D за живими залишками Odoo: палети в комірках ГП (N = min(місткість, палети)), вантаж стосів, лотків, полиць крайки й комплектів видно лише при qty > 0, без статичного вантажу — узагальнений блок × fill; порожні комірки клікабельні; у картці «За Odoo: … / Порожньо» замість статичного опису. Без живих даних (демо) — як раніше.
- Кіоск: бандл `assets_kiosk` не компілювався (SCSS «Undefined variable $theme-colors-rgb» у bootstrap `_utilities.scss`), сторінка `/f3d/kiosk/<токен>` була без стилів. Додано `_variables-dark.scss` і `_maps.scss` (як у `web.assets_backend`); тест `TestKioskAssets` компілює бандл.
- Y-2: фільтри «Сьогодні» і «Цей тиждень» журналу знімків — пошукові поля `is_today`, `is_this_week` за київською добою
  сервера (шкала `demo_clock`), а не `context_today()` браузера (UTC на стенді: з 21:00 до 24:00 UTC доба зсувалась).

## 19.0.1.0.0
- Перший випуск: 3D-переглядач заводу всередині Odoo (OWL-дія, ядро `F3dViewer`, `DataClient`, режим `lite`).
- API `/f3d/viewer/{static,data,delta,resolve,snapshots,snapshot,parts/manifest.json,cycle_check}`: живі дані з ORM
  через провайдери (`f3d.viewer.provider`), права користувача, ETag/gzip, кеш статики за mtime.
- Журнал станів: `f3d.viewer.snapshot` (крон знімків і ротації), `f3d.viewer.event` + шина `bus.bus`
  (дельти, стоп-кран `bus_enabled`), програвання зміни.
- «Показати в 3D» на формах МО, переміщення, РЦ, локації, обладнання, співробітника, зони, замовлення;
  міст `factory3d_viewer_sale`.
- Кіоск: `/f3d/kiosk/<token>/…`, користувач `user_kiosk`, токен у `factory3d.viewer.kiosk_token`,
  стоп-кран `kiosk_enabled`, обмеження частоти запитів.
- Перевірка циклу (`cycle_check`) і майстер демо-даних (стоп-кран `demo_enabled`).
- `post_init_hook` / `uninstall_hook`; `data/neutralize.sql` (прод-режим копії: демо, кіоск і шина вимкнені,
  новий токен кіоска, крони модуля вимкнені).
- Тести: UT/HT/HOOT/тури, `test_perf` (пороги ARCHITECTURE §2.7), `test_neutralize_sql`.
- Відомо: SQL-пороги AC-52 (`/data` ≤ 80, `/delta` ≤ 30) не тримаються (≈ 198 і ≈ 64) — див. `DEPLOY_TEST.md`.
