# td_chp_factory3d — міст «КГУ ↔ завод»

Модуль Odoo 19 (`depends`: `td_chp`, `td_energy`, `td_energy_control`; `auto_install`; LGPL-3). З'єднує пульт КГУ (`td_chp`) із заводом:
вузли однолінійної схеми, одне джерело Modbus, меню й права Енергетики, **керування через `td_energy_control`**.

Документація: `factory3d/docs/modules/td_chp_factory3d/` (`SPEC.md`, `ARCHITECTURE.md`); продукт — `factory3d/docs/modules/td_chp/`.

## Що робить

| Частина | Де |
|---|---|
| Усі 9 видів команд КГУ йдуть у `td.energy.action` (один механізм і журнал із Пультом енергетика, D-15): `start`/`stop` — наявні `chp_start`/`chp_stop` (клас B), решта — 7 видів моста (клас A, виконавець `chp`) | `models/td_chp_pult.py` (хуки), `models/td_energy_action.py`, `models/td_energy_command_kind.py`, `data/td_energy_command_kind_data.xml` |
| Блокування R-07 td_chp діють до й після викликів td_energy_control; верифікація за `chp/ctl/ack` / значенням цілі; строк `td.chp.verify_timeout_s` | `tools/energy_route.py`, `models/td_chp_command.py` |
| Вузли `CHP` і `QF-CHP` у картці агрегата, дозвіл дистанційних перемикань із td_energy_control | `models/td_chp_unit.py`, `views/td_chp_unit_views.xml` |
| Сигнали `chp/…` переносяться на джерело `MB-U72-CHP`, `CHP-U72` архівується; назад — при видаленні моста | `hooks.py` |
| Групи енергетики дають права в пульті КГУ; меню — в «Енергетика → Генерація й резерв», корінь «Когенерація» схований | `security/`, `views/menus.xml`, `data/td_chp_factory3d_menu_hide.xml` |
| Кнопка «Відкрити пульт КГУ» в 3D-картці `CHP` | розширення `td_energy_viewer3d` (VX-06) |

## Види команд моста

`chp_estop` «Аварійний стоп КГУ», `chp_reset`, `chp_set_mode`, `chp_set_setpoint`, `chp_set_cos`, `chp_set_heat_dir`, `chp_set_bypass` — клас A (одне
підтвердження, без другої особи), `remote_gated=False`, без плитки на екрані «Керування» (команди йдуть із пульта КГУ). Виконує запис у `chp/ctl/*`
через `td.command` (`origin='energy'`). Стоп-кран — `td.energy_control.write_enabled`, далі засуви запису телеметрії (джерело, сигнал).

## Тести

`F3D_TEST_INSTALL=td_chp,td_energy,td_energy_control,td_chp_factory3d factory3d/tools/odoo/run_tests.sh <db> /td_chp_factory3d`.
Стендовий ТК моста — `tests/stand/test_tk_b.py` (`F3D_ODOO_URL`, `F3D_ODOO_DB`, `F3D_ODOO_USER`, `F3D_ODOO_PASSWORD`).
