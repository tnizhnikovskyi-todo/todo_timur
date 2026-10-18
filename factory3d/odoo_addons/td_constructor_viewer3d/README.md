# factory3d_constructor_viewer

Міст (auto_install) між `factory3d_constructor` і `factory3d_viewer`: «Переглядач» показує розкладку, опубліковану
в конструкторі (етап 2). Провайдер `f3d.viewer.provider.layout` (180) кладе в payload `/f3d/viewer/data` ключ `layout`
(`moved` / `added` / `hidden` / `replaced` відносно бази — версії-імпорту seed); JS-розширення
`static/src/layout/` застосовує його до сцени через точку розширення ядра (`registerViewerExtension`, viewer R-25).
Без опублікованої версії ключа немає — «Переглядач» працює як раніше. Власних моделей і меню немає.

Документація: `factory3d/docs/modules/factory3d_constructor_viewer/{SPEC,ARCHITECTURE}.md`.

Тест: `F3D_TEST_INSTALL=factory3d_base,factory3d_viewer,factory3d_constructor,factory3d_constructor_viewer factory3d/tools/odoo/run_tests.sh <db> /factory3d_constructor_viewer`
