# factory3d_machine_connect

Підключення верстатів (Odoo 19): стани HOMAG (OPC UA, OPC 40550-1) і верстатів без інтерфейсу (I/O ADAM) →
журнал станів і простоїв, автостарт/пауза/завершення робочих завдань, OEE за фактом; портал STORETEQ P-500
(стоси ↔ залишки, завдання порталу з МО); карти розкрою й програми ЧПК. Клієнт —
`factory3d/services/collector_plugins/machine_connect` (плагіни `opcua`, `rest_vendor`).
Специфікація: `factory3d/docs/modules/factory3d_machine_connect/SPEC.md`.

## Встановлення

Залежності: `factory3d_telemetry` (через нього `factory3d_base`, `maintenance`, `mail`), `mrp`, `hr`, `stock`.
`mrp_workorder` (Enterprise) не потрібен (DEC-1): оператор верстата — поле `mrp.workorder.f3d_employee_id`.

    F3D_TEST_INSTALL=factory3d_machine_connect \
        factory3d/tools/odoo/run_tests.sh <db> /factory3d_machine_connect

## Параметри (`ir.config_parameter`, `factory3d.machine_connect.*`, noupdate)

Стоп-крани (за замовчуванням вимкнено): `read_enabled` (хук: `True` у `test`), `auto_start_enabled`, `write_enabled`,
`gantry_auto_replenish`, `gantry_auto_feed`. Пороги: `micro_stop_s`, `pause_after_min`, `finish_idle_s`,
`qty_sync_mode`, `qty_sync_s`, `coverage_min`, `oee_good`, `oee_warn`, `no_job_activity_min`, `stack_diff_*`.
Розкрій: `cutting_mode`, `export_token_ttl_s`. Зберігання: `keep_log_days`, `keep_event_days`.
Повний список — SPEC §5.1; форма — Налаштування → Завод 3D → «Налаштування верстатів» (V-31).

## Команди на пристрої

Створюються лише `f3d.command._f3d_mc_create_command` (чотири запобіжники Odoo: параметр модуля, параметр
telemetry, джерело, сигнал; п'ятий — `F3D_WRITE_ENABLED` колектора). Формат — `tools/commands.py` (R-21);
файл копіюється в пакет колектора як `cmdtext.py` і не імпортує Odoo.

## Інструкції й тести

- Інструкції користувачів і налаштування — `docs/modules/factory3d_machine_connect/ARCHITECTURE.md` §3–§4.
- Перший тиждень на проді — лише читання (стоп-крани `write_enabled` вимкнені): `DEPLOY_TEST.md`.
- Тести: `F3D_TEST_INSTALL=factory3d_machine_connect factory3d/tools/odoo/run_tests.sh <db> /factory3d_machine_connect`;
  пакет — `pytest services/collector_plugins/machine_connect -m "not stand"`; стенд — `-m stand` (`TEST_REPORT.md`).
- Без Enterprise `mrp_workorder`: оператор завдання — `f3d_employee_id`; з Enterprise — `start_employee` (duck typing).
