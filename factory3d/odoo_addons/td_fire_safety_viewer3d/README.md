# factory3d_fire_safety_viewer

Міст (auto_install) між `factory3d_fire_safety` і `factory3d_viewer`: провайдери `f3d.viewer.provider.fire` (130) і
`f3d.viewer.provider.evacuation` (140) для розділів `fire` і `evacuation` (SPEC M-17, R-20, R-21). Payload збирає
`factory3d_fire_safety/tools/payload.py`. Власних моделей, даних і меню немає.

Тест: `F3D_TEST_INSTALL=factory3d_base,factory3d_telemetry,factory3d_viewer,factory3d_fire_safety,factory3d_fire_safety_viewer factory3d/tools/odoo/run_tests.sh <db> /factory3d_fire_safety_viewer`
