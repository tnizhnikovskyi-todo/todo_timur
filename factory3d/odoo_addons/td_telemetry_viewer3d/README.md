# factory3d_telemetry_viewer

Міст (auto_install) між `factory3d_telemetry` і 3D-переглядачем: провайдер значень сигналів телеметрії
у payload переглядача (контракт CT-07, duck typing за ARCHITECTURE §6.7). Власних моделей, даних і меню немає.
Залежності: `factory3d_base`, `factory3d_telemetry`; залежність на `factory3d_viewer` додати, коли модуль з'явиться.

Тест: `F3D_TEST_INSTALL=factory3d_telemetry,factory3d_telemetry_viewer factory3d/tools/odoo/run_tests.sh <db> /factory3d_telemetry_viewer`
