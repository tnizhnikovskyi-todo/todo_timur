# td_chp_factory3d — технічне рішення

Версія 0.2 · 21.10.2026 · автор: агент (крок 1 циклу; W3 — D-15) · статус: чернетка. Міст між продуктом `td_chp` і заводом (`td_energy`, `td_energy_control`; `td_energy_viewer3d` — необов'язково). Специфікація — [SPEC.md](SPEC.md); продукт — [td_chp](../td_chp/ARCHITECTURE.md). Зразок — `td_genset_factory3d`.

## 1. Функціональні вимоги
FR-B01 Зв'язати агрегат КГУ з вузлами енергетики `CHP` і `QF-CHP` (AC-B01). FR-B02 Перенести сигнали `chp/…` на існуюче джерело `MB-U72-CHP` — один Modbus-клієнт на пристрій (AC-B02). FR-B03 Усі 9 видів команд КГУ з пульта (пуск, стоп, аварійний стоп, скидання, режим, P, cos φ, напрямок тепла, заслінка) виконуються через `td_energy_control` — один механізм і один журнал із Пультом енергетика: клас B (`start`, `stop`) з підтвердженням 2/2, клас A (решта) з одним підтвердженням; одна команда — один запис (AC-B03…B09, B12). FR-B04 Групи енергетики автоматично дають права в пульті КГУ (AC-B01). FR-B05 Меню КГУ — у розділі «Генерація й резерв» (AC-B01). FR-B06 Кнопка «Відкрити пульт КГУ» в 3D-картці `CHP` (AC-B10). Не входить: тепло КГУ в BMS (вже є), кнопки `chp_*` у картці вузла Пульту енергетика (Q-B1).

## 2. Технічна реалізація
```
 td_chp ──(хуки M-06)──► td_chp_factory3d ──► td.energy.control.prepare/confirm/…  ──► td.energy.action
   │  (без мосту: td.chp.command)                   │ (preflight td_chp R-07; _td_close('blocked'))     chp_start|chp_stop  — executor intent (збирач енергетики)
   │                                                 └ види моста chp_estop|chp_reset|chp_set_* — executor chp → td.command(origin='energy') → chp/ctl/*
   │                                                                                                    верифікація R-09 (td.chp.command._td_on_ingest → _td_chp_verify)
   └── td.chp.unit ◄── energy_node_id (CHP), energy_qf_node_id (QF-CHP);  signals chp/* ──► source MB-U72-CHP (td_energy)
 td_energy_viewer3d: PULT_BUTTONS["CHP"] → td_chp.action_td_chp_pult  (layer.can_chp_pult)
```
Залежності: `td_chp`, `td_energy`, `td_energy_control` (жорстка: міст розширює `td.energy.action` і `td.energy.command.kind`, D-18 — місток auto_install з `_inherit`). Усе інше — `env.get`/перевірка наявності моделі. Безпека: права й стоп-крани всіх 9 видів — td_energy_control (R-39, R-40, D-46); міст нічого не виконує від `sudo`, окрім `_td_close('blocked')` власного preflight і службових записів виконавця `chp` (`_me()` td_energy_control). Міграції немає; деінсталяція повертає джерело й корінь меню (SPEC RB-05).

## 6. План збирання агентами
Збирає воркер **W3** (разом з емулятором) — файли, команди тестів, порядок і критерії готовності в [td_chp ARCHITECTURE §6](../td_chp/ARCHITECTURE.md). Міст стартує після злиття W1 (хуки M-06, `td.chp.unit`, `td.chp.pult`). Файли моста: `__manifest__.py`, `__init__.py`, `hooks.py`, `ruff.toml`, `README.md`, `CHANGELOG.md`, `models/{td_chp_unit,td_chp_pult,td_chp_command,td_energy_command_kind,td_energy_action}.py`, `tools/energy_route.py`, `data/{td_chp_factory3d_menu_hide,td_energy_command_kind_data}.xml`, `security/td_chp_factory3d_security.xml`, `views/{td_chp_unit_views,menus}.xml`, `tests/**`; адитивні правки `td_energy_viewer3d` — SPEC §8.
