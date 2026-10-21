# td_chp_factory3d — технічне рішення

Версія 0.1 · 20.10.2026 · автор: агент (крок 1 циклу) · статус: чернетка. Міст між продуктом `td_chp` і заводом (`td_energy`, необов'язково `td_energy_control`, `td_energy_viewer3d`). Специфікація — [SPEC.md](SPEC.md); продукт — [td_chp](../td_chp/ARCHITECTURE.md). Зразок — `td_genset_factory3d`.

## 1. Функціональні вимоги
FR-B01 Зв'язати агрегат КГУ з вузлами енергетики `CHP` і `QF-CHP` (AC-B01). FR-B02 Перенести сигнали `chp/…` на існуюче джерело `MB-U72-CHP` — один Modbus-клієнт на пристрій (AC-B02). FR-B03 Пуск і стоп КГУ з пульта виконуються через `td_energy_control` з тими самими правилами класу B, підтвердженням 2/2 і журналом; одна команда — один запис (AC-B03…B05, B07…B09). FR-B04 Групи енергетики автоматично дають права в пульті КГУ (AC-B01). FR-B05 Меню КГУ — у розділі «Генерація й резерв» (AC-B01). FR-B06 Кнопка «Відкрити пульт КГУ» в 3D-картці `CHP` (AC-B10). Не входить: тепло КГУ в BMS (вже є), кнопки `chp_*` у картці вузла Пульту енергетика (Q-B1).

## 2. Технічна реалізація
```
 td_chp ──(хуки M-06)──► td_chp_factory3d ──► td.energy.control.prepare/confirm/…  ──► td.energy.action (chp_start|chp_stop)
   │  td.chp.command (estop, reset, set_*)           │ (preflight td_chp R-07; _close('blocked'))
   └── td.chp.unit ◄── energy_node_id (CHP), energy_qf_node_id (QF-CHP);  signals chp/* ──► source MB-U72-CHP (td_energy)
 td_energy_viewer3d: PULT_BUTTONS["CHP"] → td_chp.action_td_chp_pult  (layer.can_chp_pult)
```
Залежності: `td_chp`, `td_energy`. Усе інше — `env.get`/перевірка наявності моделі (D-18 каркасу). Безпека: права й стоп-крани маршрутизованих видів — td_energy_control (R-39, R-40, D-46); міст нічого не виконує від `sudo`, окрім `_td_close('blocked')` власного preflight. Міграції немає; деінсталяція повертає джерело й корінь меню (SPEC RB-05).

## 6. План збирання агентами
Збирає воркер **W3** (разом з емулятором) — файли, команди тестів, порядок і критерії готовності в [td_chp ARCHITECTURE §6](../td_chp/ARCHITECTURE.md). Міст стартує після злиття W1 (хуки M-06, `td.chp.unit`, `td.chp.pult`). Файли моста: `__manifest__.py`, `__init__.py`, `hooks.py`, `ruff.toml`, `README.md`, `CHANGELOG.md`, `models/{td_chp_unit,td_chp_pult}.py`, `tools/energy_route.py`, `data/td_chp_factory3d_menu_hide.xml`, `security/td_chp_factory3d_security.xml`, `views/{td_chp_unit_views,menus}.xml`, `tests/**`; адитивні правки `td_energy_viewer3d` — SPEC §8.
