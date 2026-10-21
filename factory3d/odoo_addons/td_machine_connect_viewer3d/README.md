# td_machine_connect_viewer3d

Міст `td_machine_connect` + `td_viewer3d` (`auto_install`): режим розфарбування 3D «Простої, ₴» поруч з «OEE верстатів».
Власних даних немає; береться `workcenters[code].downtime_cost` з провайдера `td_machine_connect` (лише менеджеру «Завод 3D», не в кіоску).
Реалізація — `registerViewerExtension` (td_viewer3d R-26, VX-01…VX-03), ядро `core.js` не змінюється. SPEC: `docs/modules/td_machine_connect/SPEC.md` R-29.

«Вузьке місце» (вау №16, SPEC R-30): стопка завдань, що чекають перед вузьким місцем заводу (червоні коробки, висота за кількістю), і блок з показниками
в картці верстата; дані — `workcenters[code].flow` (провайдер `td_machine_connect`). Файл — `static/src/layer/bottleneck_layer.js`, ядро не змінюється.

«Портальний склад плит у 3D наживо» (вау №19, SPEC R-31): стоси під порталом за реальним числом листів (висота = листи × товщина, підпис матеріалу), портал, що їде до стосу,
бере лист і везе до верстата розкрою за часом завдань (у «живому» режимі й у «Потоці зміни» за часом `t`), блоки в картках стосу, порталу й верстата-цілі (лист → завдання → карта
розкрою з відходами → замовлення). Дані — `equipment["GANTRY-1"].portal` і `locations[PLT-*].portal` (провайдер `td_machine_connect`, `td.portal`). Файли —
`static/src/layer/portal_model.js` (чиста модель, без THREE), `portal_layer.js` (сцена), `portal_layer.scss`; ядро не змінюється, без вузла `portal` розширення неактивне.
