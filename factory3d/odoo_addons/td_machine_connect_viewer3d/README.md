# td_machine_connect_viewer3d

Міст `td_machine_connect` + `td_viewer3d` (`auto_install`): режим розфарбування 3D «Простої, ₴» поруч з «OEE верстатів».
Власних даних немає; береться `workcenters[code].downtime_cost` з провайдера `td_machine_connect` (лише менеджеру «Завод 3D», не в кіоску).
Реалізація — `registerViewerExtension` (td_viewer3d R-26, VX-01…VX-03), ядро `core.js` не змінюється. SPEC: `docs/modules/td_machine_connect/SPEC.md` R-29.
