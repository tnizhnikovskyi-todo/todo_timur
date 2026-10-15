# factory3d_telemetry

Спільний хребет збору даних factory3d (Odoo 19): колектори, джерела, сигнали, показання, команди;
API `/f3d/telemetry/*`; пороги → заявки ТО; ТО за лічильником. Клієнт — `factory3d/services/collector`.

Специфікація: `factory3d/docs/modules/factory3d_telemetry/SPEC.md`.

Стан каркаса (W0): маніфест, меню «Телеметрія», параметри `factory3d.telemetry.*`, фікстури тестів.
Файли `*.full` у `security/`, `data/`, `views/` — повні версії для моделей, що з'являться пізніше.

Тест: `F3D_TEST_INSTALL=factory3d_telemetry factory3d/tools/odoo/run_tests.sh <db> /factory3d_telemetry`
