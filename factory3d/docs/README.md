# Документація factory3d — індекс

Проєктна документація модулів Odoo 19 для 3D-моделі меблевого підприємства: прод-модулі, які на стенді
працюють з емулятором обладнання `td_iot_sim` замість реальних пристроїв. Стан на 14.10.2026 (після відповідей замовника й правки макета 12г).

## Імена за стандартом компанії (td_*)

Усі технічні імена переведено на стандарт: модулі `td_<область>`, моделі `td.*`, поля `td_*`, xml-id `group_td_*` / `menu_td_*`,
параметри `td.<область>.<параметр>`. Старі імена (`factory3d_*`, `f3d.*`, `f3d_*`) у модульних документах замінено на нові;
повна карта, список незмінних контрактів (маршрути `/f3d/...`, канал шини, коди сигналів і об'єктів) і розв'язання колізій —
у [../build/RENAME.md](../build/RENAME.md). Каталоги документів модулів: `modules/td_*`.

## Спільні документи

| Документ | Що в ньому |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Архітектурний каркас v0.2: склад і фази, граф залежностей, топологія, конвенції, наскрізні контракти (C-xx, P-xx), журнал рішень менеджера D-01…D-25, відкриті питання |
| [DOC_STANDARD.md](DOC_STANDARD.md) | Стандарт модульних документів: структура `ARCHITECTURE.md` і `SPEC.md`, планка якості, чек-лист |
| [CONSISTENCY.md](CONSISTENCY.md) | Реєстр розбіжностей між модулями X-01…X-93 (усі затверджені й внесені), питання до замовника й відповіді на них |

## Модулі

Кожен модуль має `ARCHITECTURE.md` (технічне рішення за стандартом ToDo) і `SPEC.md` (специфікація для
розробки й тестування: моделі, представлення, права, API, протокольні карти, AC, план тестів).

| # | Модуль | Фаза | Технічне рішення | Специфікація |
|---|---|---|---|---|
| 1 | `td_factory3d` | 1 | [v0.2, 378 р.](modules/td_factory3d/ARCHITECTURE.md) | [v0.2, 1 343 р.](modules/td_factory3d/SPEC.md) |
| 2 | `td_viewer3d` | 1 | [v0.2, 522 р.](modules/td_viewer3d/ARCHITECTURE.md) | [v0.2, 2 152 р.](modules/td_viewer3d/SPEC.md) |
| 3 | `td_iot_sim` | 1 | [v0.3, 323 р.](modules/td_iot_sim/ARCHITECTURE.md) | [v0.3, 2 964 р.](modules/td_iot_sim/SPEC.md) |
| 4 | `td_telemetry` | 2 | [v0.3, 522 р.](modules/td_telemetry/ARCHITECTURE.md) | [v0.3, 2 409 р.](modules/td_telemetry/SPEC.md) |
| 5 | `td_machine_connect` | 2 | [v0.2, 567 р.](modules/td_machine_connect/ARCHITECTURE.md) | [v0.2, 2 883 р.](modules/td_machine_connect/SPEC.md) |
| 6 | `td_energy` | 3 | [v0.2, 463 р.](modules/td_energy/ARCHITECTURE.md) | [v0.2, 2 445 р.](modules/td_energy/SPEC.md) |
| 7 | `td_genset` (міст `td_genset_factory3d`) | 3 | [v0.3, 589 р.](modules/td_genset/ARCHITECTURE.md) | [v0.3, 1 720 р.](modules/td_genset/SPEC.md) |
| 8 | `td_yard` | 4 | [v0.3, 498 р.](modules/td_yard/ARCHITECTURE.md) | [v0.2, 2 516 р.](modules/td_yard/SPEC.md) |
| 9 | `td_access` | 4 | [v0.2, 506 р.](modules/td_access/ARCHITECTURE.md) | [v0.2, 2 070 р.](modules/td_access/SPEC.md) |
| 10 | `td_bms` | 5 | [v0.2, 444 р.](modules/td_bms/ARCHITECTURE.md) | [v0.2, 1 812 р.](modules/td_bms/SPEC.md) |
| 11 | `td_fire_safety` | 5 | [v0.3, 551 р.](modules/td_fire_safety/ARCHITECTURE.md) | [v0.3, 2 598 р.](modules/td_fire_safety/SPEC.md) |
| 12 | `td_constructor` | 6 | [v0.1, 295 р.](modules/td_constructor/ARCHITECTURE.md) | [v0.1, 999 р.](modules/td_constructor/SPEC.md) |
| 13 | `td_constructor_viewer3d` (міст «Конструктор» → «Переглядач») | 6 | [v0.1, 66 р.](modules/td_constructor_viewer3d/ARCHITECTURE.md) | [v0.1, 110 р.](modules/td_constructor_viewer3d/SPEC.md) |

## Як читати

1. Каркас `ARCHITECTURE.md` §2–§6 — що є в системі й які контракти спільні.
2. Технічне рішення модуля — процес, ролі, FR, інтеграції, налаштування, інструкції.
3. Специфікація модуля — розробнику (§0–§11) і тестувальнику (§12–§14: AC, юніт-тести, стендові ТК на емуляторі).
4. Питання до замовника — `CONSISTENCY.md`, розділи «Питання до замовника» (19 пунктів) і «Відповіді на питання до
   замовника» (усі 19 отримали відповідь 14.10.2026); у модулях — §5 ARCHITECTURE і §15 SPEC, закриті Q-xx мають
   позначку «Закрито 14.10 (відповідь № N)».
