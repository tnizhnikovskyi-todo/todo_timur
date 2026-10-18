# td_telemetry_viewer3d

Міст (auto_install) між `td_telemetry` і 3D-переглядачем: провайдер значень сигналів телеметрії
у payload переглядача (контракт CT-07, duck typing за ARCHITECTURE §6.7). Власних моделей, даних і меню немає.
Залежності: `td_factory3d`, `td_telemetry`; залежність на `td_viewer3d` додати, коли модуль з'явиться.

Тест: `F3D_TEST_INSTALL=td_telemetry,td_telemetry_viewer3d factory3d/tools/odoo/run_tests.sh <db> /td_telemetry_viewer3d`
