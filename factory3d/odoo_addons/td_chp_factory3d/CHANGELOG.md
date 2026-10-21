# Changelog — td_chp_factory3d

## 19.0.1.1.0

* Виправлення: «Пуск»/«Стоп» з пульта КГУ не доходили до КГУ. `chp_start`/`chp_stop` мали виконавця `intent` (команда в сигнал `energy_control/intent` збирача
  енергетики, а той пише у вікно ГРЩ `energy_control/chp/cmd`, u73:230 — сигнал без `write_enabled` і поза картою u72). Тепер, як решта 7 видів, вони йдуть
  виконавцем `chp`: `td.command` у `chp/ctl/cmd` (1 — пуск, 2 — стоп; Modbus u72, HR 40900), верифікація за `chp/ctl/ack` (R-09, як `estop`/`reset`).
  Клас B (1/2 + 2/2), `checks` і `remote_gated` td_energy_control збережено. Виконавець підмінюється даними `data/td_energy_command_kind_data.xml`;
  `uninstall_hook` повертає `intent` (інакше `ondelete='cascade'` видалив би ці види).

## 19.0.1.0.0

* Перша версія моста «КГУ ↔ завод» (SPEC td_chp_factory3d, W3; рішення D-15).
* Усі 9 видів команд КГУ — через `td_energy_control`: `chp_start`/`chp_stop` (клас B) і 7 видів моста `chp_estop`, `chp_reset`, `chp_set_mode`,
  `chp_set_setpoint`, `chp_set_cos`, `chp_set_heat_dir`, `chp_set_bypass` (клас A, виконавець `chp`). Хуки пульта td_chp (`_td_route`, `_td_dispatch`,
  `_td_command_rows`, `_td_pending_rows`, `_td_flags`) перевизначено цілком: `td.chp.command` не створюється, журнал і картка «Очікує 2/2» — з `td.energy.action`.
* Розширення `td.energy.action` / `td.energy.command.kind`: виконавець `chp` (`td.command` `origin='energy'` у `chp/ctl/*`), верифікація R-09, строк
  `td.chp.verify_timeout_s`, одна активна дія на КГУ, `chp_estop` дозволено завжди; стоп-крани — `td.energy_control.*` і засуви запису телеметрії.
* `td.chp.unit`: вузли `CHP`/`QF-CHP`, стани й P з Енергетики, `_td_remote_switching` з td_energy_control; сигнали `chp/…` на джерелі `MB-U72-CHP`.
* Групи `td_energy.group_td_energy_user/manager/chief` ⊃ `td_chp.group_td_chp_user/operator/chief`; меню КГУ в «Енергетика → Генерація й резерв».
* Залежність від `td_energy_control` жорстка (розширення моделей); без нього міст не ставиться.
* Оператор КГУ без ролі «Енергетик» td_energy (DB-06) отримує зрозумілу відмову «Для команд КГУ потрібна роль Енергетика: …» замість службової помилки; права не розширено.
