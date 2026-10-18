# td_factory3d

Ядро factory3d (Odoo 19): домішка `td.scene.mixin` (коди сцени), зони цеху `td.zone`, ворота як доки,
паспорти обладнання, групи прав «Завод 3D», міграція демо-полів `x_dock/x_truck/x_vehicle` у пакети.

## Установка
`odoo-bin -d <db> -i td_factory3d`. Після установки `post_init_hook` виконує кроки 1–11 (SPEC §5.3):
коди локацій/РЦ/працівників/обладнання, прив'язка паспортів і зон, міграція x_* у `stock.picking.batch`,
звірка, видалення демо-полів. Результат: `td.base.migration_state` (`skipped`/`partial`/`done`) і
`migration_report` (JSON). Повтор: «Завод 3D → Налаштування → Повторити міграцію демо-даних» (адміністратор).

## Параметри (`td.base.*`)
`environment`, `plant_length_m/width_m/height_m`, `site_x0_m/y0_m/x1_m/y1_m`, `keep_x_fields` (True — не видаляти
x_* поля), `uninstall_restore_x_fields` (True — відновити x_* при деінсталяції), `migration_state`, `migration_report`.

## Інструкції
1. Перед установкою на копію демо-бази: зняти знімки S1–S5 (`DEPLOY_TEST.md`).
2. Розбіжність звірки → стан `partial`, поля x_* лишаються; виправити дані й повторити міграцію.
3. Для переглядача/`odoo_pull`: `x_dock` → `td_dock_code`, `x_truck` → `td_truck_code`, `x_vehicle` → `batch_id.td_vehicle_id.td_code`.
4. Тестова база: `data/neutralize.sql` виставляє `environment='test'`.

Міст із Enterprise `mrp_maintenance`: `td_factory3d_mrp_maintenance`.
