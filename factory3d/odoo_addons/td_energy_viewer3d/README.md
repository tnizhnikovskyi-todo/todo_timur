# td_energy_viewer3d — міст «Енергетика в 3D»

`depends`: `td_energy`, `td_viewer3d`; `auto_install`. Дані не створює: видалення прибирає шар. Документація: `factory3d/build/energy/W2_SPEC.md` §8.4.

- **Сервер.** Провайдер `td.viewer.provider.energy_layer` (seq 101, секція `energy`) додає ключ `energy.layer`: стан вузлів схеми Пульту (той самий `td_energy.tools.sld.Snap`, що й у Пульті), тривоги, пороги, `show_markers`. `meta.schema` не змінюється. Дельта — повна заміна шару. Логіка — `tools/layer.py`.
- **«Відкрити в 3D».** `td.energy.node.action_td_open_3d(code=None)` → клієнтська дія `f3d_viewer.action` (шари, режим `td_energy`, вкладка «Енергія», `code` = об'єкт сцени); меню «Енергетика в 3D» (V-47). Параметри `td.energy_viewer3d.layers|marker_limit|show_markers` (форма налаштувань «Енергетика»).
- **Клієнт.** `static/src/layer/`: `energy_layer.js` — розширення ядра (`registerViewerExtension`, R-26): режим «Електромережа: стан вузлів» (`colors.js`), маркери тривог (`markers.js`), блок «Енергетика» в картці об'єкта; `links.js` — реєстр `td_energy.viewer_links` (ключ `default`, `open({code})`) для клієнта `td_energy`.
- **Тести.** `F3D_TEST_INSTALL=td_energy,td_viewer3d,td_energy_viewer3d factory3d/tools/odoo/run_tests.sh <db> /td_energy_viewer3d` (Python + hoot `TestEnergyLayerHoot`).
