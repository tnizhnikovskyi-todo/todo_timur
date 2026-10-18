# factory3d_bms — Завод 3D: будівля

Освітлення (норми, щити, групи DALI/HelvarNet), вентиляція й опалення (BACnet), тепловий баланс, журнал відхилень.
Специфікація: `factory3d/docs/modules/factory3d_bms/SPEC.md`. Залежності: `factory3d_telemetry`, `web`.

## Параметри
`factory3d.bms.*` (`data/ir_config_parameter.xml`, SPEC §5.1): `read_enabled`, `write_enabled` (за замовчуванням `False`),
`calendar_id`, затримки й пороги перевірок, `light_uf`, `light_mf`, `install_report`.

## Групи
`group_f3d_user` ⊂ `group_f3d_bms_operator` ⊂ `group_f3d_manager` ⊂ `group_f3d_admin`.

## Статус збирання
Каркас (W0). Ще не підключено в маніфест: `data/ir_cron.xml` (потребує моделі `f3d.bms.check`), рядки доступу нижче.

## Рядки `security/ir.model.access.csv` для W1…W5 (SPEC §4.1)
Заголовок: `id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink`. Для моделей
`f3d.bms.light.norm`, `.light.panel`, `.light.group`, `.light.scene`, `.hvac.unit`, `.heat.balance` (без unlink у менеджера),
`.heat.balance.line`: рядки `_user` (`factory3d_base.group_f3d_user`, 1,0,0,0) і `_manager` (`group_f3d_manager`, 1,1,1,1);
`f3d.bms.deviation`: `_user` (1,0,0,0), `_operator` (`factory3d_bms.group_f3d_bms_operator`, 1,1,0,0), `_admin`
(`group_f3d_admin`, 1,1,1,1); `f3d.bms.light.command.wizard` і `f3d.bms.hvac.command.wizard`: `_operator` (1,1,1,1).
Повний текст — SPEC §4.1.
