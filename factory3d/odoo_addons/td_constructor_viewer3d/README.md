# td_constructor_viewer3d

Міст (auto_install) між `td_constructor` і `td_viewer3d`: «Переглядач» показує розкладку, опубліковану
в конструкторі (етап 2). Провайдер `td.viewer.provider.layout` (180) кладе в payload `/f3d/viewer/data` ключ `layout`
(`moved` / `added` / `hidden` / `replaced` відносно бази — версії-імпорту seed); JS-розширення
`static/src/layout/` застосовує його до сцени через точку розширення ядра (`registerViewerExtension`, viewer R-25).
Без опублікованої версії ключа немає — «Переглядач» працює як раніше. Власних моделей і меню немає.

Документація: `factory3d/docs/modules/td_constructor_viewer3d/{SPEC,ARCHITECTURE}.md`.

Тест: `F3D_TEST_INSTALL=td_factory3d,td_viewer3d,td_constructor,td_constructor_viewer3d factory3d/tools/odoo/run_tests.sh <db> /td_constructor_viewer3d`
