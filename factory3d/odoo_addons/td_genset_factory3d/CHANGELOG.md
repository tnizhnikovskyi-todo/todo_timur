# Changelog

## 19.0.1.1.0
- W1 «Енергетика» (міст у застосунку «Енергетика»): екрани й меню td_genset хостяться в розділі «Генерація й резерв»
  (`td_energy.menu_td_energy_generation`): 25 нових меню `menu_gf_*` (V-10) замість верхнього меню «Генератор» у корені
  `td_factory3d`; меню «Налаштування генератора» (адмін) лишилось під `td_factory3d.menu_td_config`.
- Корінна плитка td_genset прихована, поки встановлено міст (`data/menu_hide.xml`, V-11, E-08); `uninstall_hook`
  повертає її (`_restore_td_genset_root`); `-u td_genset` оновлює й міст, тож плитка лишається прихованою.
- `td.energy.dashboard`: хуки `_td_genset_summary`, `_td_generation_cards`, `_td_node_facts_extra`,
  `_td_node_card_extra` (M-10, R-15): картка «ДГУ», факти вузлів `ATS-1`/`GENSET`, зведення для Пульту; читання td_genset
  лише через адаптер, помилки адаптера не валять Пульт.
- Адаптер: ADP-11 `next_event(gen)` (`FIELD_NEXT_EVENT = "next_event_text"`).
- Групи (M-11): `td_energy.group_td_energy_manager` → `td_genset.group_user`; перегляд енергетики прав td_genset не
  отримує (факти ДГУ — через адаптер із `sudo()`).
- Відхилення від SPEC: меню «Заявки ТО генератора» (`menu_gf_requests`) — група `td_factory3d.group_td_user`
  (R-16 п. 2), а не `td_genset.group_user` (B.3.1); див. W1_SPEC, рішення автора td_genset_factory3d A-23.
- Тести: AC-74…AC-83, ТБ-11 (`test_w1_section.py`, `test_w1_hooks.py`), стенд ТК-G14/G15 (`tests/stand/`).

## 19.0.1.0.0
- Перший випуск: каркас моста (W0).
