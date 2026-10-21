# td_fire_safety_viewer3d

Міст (auto_install) між `td_fire_safety` і `td_viewer3d`: провайдери `td.viewer.provider.fire` (130) і
`td.viewer.provider.evacuation` (140) для розділів `fire` і `evacuation` (SPEC M-17, R-20, R-21). Payload збирає
`td_fire_safety/tools/payload.py`. Власних моделей, даних і меню немає.

**Евакуація в 3D (вау №8).** JS-розширення ядра (`static/src/layer/evac_layer.js`, `registerViewerExtension`; ядро `td_viewer3d` не змінено, хуки VX-03/VX-08)
оживляє сцену за ключем `evacuation.live`: бігучі стрілки маршрутів, виходи, напівпрозорий дим, підсвітка заблокованої вентиляції й люків, точки людей, що
рухаються до виходів за проходами СКУД, червоний «застряглий» із зоною й плашка «у будівлі N людей · 02:15 від тривоги». Модель часу й шляху — `evac_model.js`.
Без `live` (тривоги немає або старий сервер) нічого не малює. Тест: `/td_fire_safety_viewer3d` (провайдери + hoot `evac.test.js`).

Тест: `F3D_TEST_INSTALL=td_factory3d,td_telemetry,td_viewer3d,td_fire_safety,td_fire_safety_viewer3d factory3d/tools/odoo/run_tests.sh <db> /td_fire_safety_viewer3d`
