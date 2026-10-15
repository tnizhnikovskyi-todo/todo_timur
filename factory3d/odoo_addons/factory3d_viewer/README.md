# factory3d_viewer

3D-переглядач заводу всередині Odoo 19: живі дані з ORM (склад, виробництво, ТО, люди, логістика), «Показати в 3D»
з документів, журнал станів із програванням зміни, екран у цеху (кіоск), перевірка циклу, заливка демо-даних.
Залежності: `factory3d_base`, `bus`, `web`; провайдери даних підключаються за наявності `stock`, `mrp`, `maintenance`, `hr` тощо.

## Установка
`odoo-bin -d <db> -i factory3d_viewer`. `post_init_hook`: група й користувач кіоска, токен
`factory3d.viewer.kiosk_token`, ознака демо-бази (`demo_enabled`, `demo_clock`), перевірка кодів сцени, знімок `install`.
Права: `group_f3d_user` (перегляд), `group_f3d_manager`, `group_f3d_admin` (налаштування, токен, демо).

## Параметри (`factory3d.viewer.*`)
`snapshot_minutes`, `snapshot_hours`, `snapshot_keep_days`, `event_keep_hours`, `delta_debounce_ms`, `kiosk_enabled`,
`kiosk_refresh_s`, `kiosk_token`, `bus_enabled`, `lite_default`, `demo_enabled`, `demo_clock`; службові: `signal_bus_ts`,
`demo_queue`, `demo_state`. Налаштування: Завод 3D → Налаштування → Налаштування переглядача.

## Крони
`3D: знімок стану` (10 хв), `3D: ротація журналу станів` (щодня), `3D: сигнали імітації в шину` і `3D: заливка демо`
(вимкнені за замовчуванням).

## Тести
`F3D_TEST_INSTALL=factory3d_viewer,test_factory3d_viewer factory3d/tools/odoo/run_tests.sh <db> /factory3d_viewer`
(на копії демо-бази: `F3D_TEMPLATE_DB=f3d_demo_tpl`). Тільки продуктивність: `:TestPerf`; суворі SQL-пороги —
`F3D_PERF_SQL_STRICT=1`. HOOT: `:TestHoot`.

## Інструкції для користувачів
Див. `static/description/index.html` (вкладка «Опис» модуля) — «Показати в 3D», з 3D у форму Odoo, екран у цеху,
програвання зміни, перевірка циклу, демо-дані.

## Тестова база і прод
`data/neutralize.sql` (виконується `odoo-bin neutralize`): `demo_enabled=False`, `kiosk_enabled=False`, `bus_enabled=False`,
новий випадковий `kiosk_token`, крони модуля вимкнені. Деінсталяція: параметри `factory3d.viewer.*` видаляються,
`user_kiosk` архівується, бізнес-дані не чіпаються.

## Асети
`plant/export_viewer_assets.py odoo_addons/factory3d_viewer` збирає `static/lib/three`, `static/model/parts/*.glb`,
`static/data/*` і `BUILD.json`. GLB не змінювати без нового запису в `BUILD.json`.
