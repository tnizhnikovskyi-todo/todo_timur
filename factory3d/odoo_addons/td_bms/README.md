# td_bms — 3D Завод: будівля

Освітлення (норми, щити, групи DALI/HelvarNet), вентиляція й опалення (BACnet), тепловий баланс, журнал відхилень.
Специфікація: `factory3d/docs/modules/td_bms/SPEC.md`. Залежності: `td_telemetry`, `web`.

## Параметри
`td.bms.*` (`data/ir_config_parameter.xml`, SPEC §5.1): `read_enabled`, `write_enabled` (за замовчуванням `False`),
`calendar_id`, затримки й пороги перевірок, `light_uf`, `light_mf`, `install_report`.

## Групи
`group_td_user` ⊂ `group_td_bms_operator` ⊂ `group_td_manager` ⊂ `group_td_admin`.

## Статус збирання
Каркас (W0). Ще не підключено в маніфест: `data/ir_cron.xml` (потребує моделі `td.bms.check`), рядки доступу нижче.

## Рядки `security/ir.model.access.csv` для W1…W5 (SPEC §4.1)
Заголовок: `id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink`. Для моделей
`td.bms.light.norm`, `.light.panel`, `.light.group`, `.light.scene`, `.hvac.unit`, `.heat.balance` (без unlink у менеджера),
`.heat.balance.line`: рядки `_user` (`td_factory3d.group_td_user`, 1,0,0,0) і `_manager` (`group_td_manager`, 1,1,1,1);
`td.bms.deviation`: `_user` (1,0,0,0), `_operator` (`td_bms.group_td_bms_operator`, 1,1,0,0), `_admin`
(`group_td_admin`, 1,1,1,1); `td.bms.light.command.wizard` і `td.bms.hvac.command.wizard`: `_operator` (1,1,1,1).
Повний текст — SPEC §4.1.
