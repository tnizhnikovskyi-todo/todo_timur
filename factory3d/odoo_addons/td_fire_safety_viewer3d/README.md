# td_fire_safety_viewer3d

Міст (auto_install) між `td_fire_safety` і `td_viewer3d`: провайдери `td.viewer.provider.fire` (130) і
`td.viewer.provider.evacuation` (140) для розділів `fire` і `evacuation` (SPEC M-17, R-20, R-21). Payload збирає
`td_fire_safety/tools/payload.py`. Власних моделей, даних і меню немає.

Тест: `F3D_TEST_INSTALL=td_factory3d,td_telemetry,td_viewer3d,td_fire_safety,td_fire_safety_viewer3d factory3d/tools/odoo/run_tests.sh <db> /td_fire_safety_viewer3d`
