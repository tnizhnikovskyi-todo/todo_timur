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
| 6 | `td_energy` (W1, енергетика) | 3 | [v0.2, 479 р.](modules/td_energy/ARCHITECTURE.md) | [v0.2, 2 469 р.; W1 — за посиланням на `build/energy/W1_SPEC.md`](modules/td_energy/SPEC.md) |
| 7 | `td_genset` (міст `td_genset_factory3d`) | 3 | [v0.3, 589 р.](modules/td_genset/ARCHITECTURE.md) | [v0.3, 1 720 р.](modules/td_genset/SPEC.md) |
| 8 | `td_yard` | 4 | [v0.3, 498 р.](modules/td_yard/ARCHITECTURE.md) | [v0.2, 2 516 р.](modules/td_yard/SPEC.md) |
| 9 | `td_access` | 4 | [v0.2, 506 р.](modules/td_access/ARCHITECTURE.md) | [v0.2, 2 070 р.](modules/td_access/SPEC.md) |
| 10 | `td_bms` | 5 | [v0.2, 444 р.](modules/td_bms/ARCHITECTURE.md) | [v0.2, 1 812 р.](modules/td_bms/SPEC.md) |
| 11 | `td_fire_safety` | 5 | [v0.3, 551 р.](modules/td_fire_safety/ARCHITECTURE.md) | [v0.3, 2 598 р.](modules/td_fire_safety/SPEC.md) |
| 12 | `td_constructor` («Конструктор»; злито з «Конструктором складу»: ядро `core/constructor`, M-16…M-31, API-11…API-24, AC-70…AC-138; модуль `19.0.1.4.0`) | 6 | [v0.2, 450 р.](modules/td_constructor/ARCHITECTURE.md) | [v0.2, 1 825 р.](modules/td_constructor/SPEC.md) |
| 13 | `td_constructor_viewer3d` (міст «Конструктор» → «Переглядач»; не оновлювався злиттям — Q-22) | 6 | [v0.1, 66 р.](modules/td_constructor_viewer3d/ARCHITECTURE.md) | [v0.1, 110 р.](modules/td_constructor_viewer3d/SPEC.md) |
| 14 | `td_energy_analytics` (W4, енергетика: аналітика, модель бази ISO 50001, звіти; вау №6 «Що якщо» — R-23) | 3 | [v0.2, 377 р.](modules/td_energy_analytics/ARCHITECTURE.md) | [v0.3, 1054 р.](modules/td_energy_analytics/SPEC.md) |
| 15 | `td_energy_mobile` (W4, енергетика: вкладка «Обхід» мобільного екрана) | 3 | [v0.2, 377 р. (спільне з № 14)](modules/td_energy_mobile/ARCHITECTURE.md) | [v0.2, 493 р.](modules/td_energy_mobile/SPEC.md) |
| 16 | `td_energy_control` (W2, енергетика: керування, плагін збирача `td_collector_energy`) | 3 | [v0.2, 336 р.](modules/td_energy_control/ARCHITECTURE.md) | [v0.2, 1 639 р.](modules/td_energy_control/SPEC.md) |
| 17 | `td_energy_viewer3d` (W2, міст «Енергетика в 3D» → «Переглядач») | 3 | [v0.2, 129 р.](modules/td_energy_viewer3d/ARCHITECTURE.md) | [v0.5, 279 р.](modules/td_energy_viewer3d/SPEC.md) |
| 18 | `td_energy_resources` (W3, енергетика: газ, повітря, тепло, тарифи, резерви) | 3 | [v0.2, 336 р.](modules/td_energy_resources/ARCHITECTURE.md) | [v0.2, 1 167 р.](modules/td_energy_resources/SPEC.md) |
| 19 | `td_energy_resources_bms` (W3, міст «Енергоресурси — Будівля») | 3 | [v0.2, 114 р.](modules/td_energy_resources_bms/ARCHITECTURE.md) | [v0.2, 136 р.](modules/td_energy_resources_bms/SPEC.md) |
| 20 | `td_sale_cost` (вау №25, міст «Собівартість замовлення наживо»: смарт-кнопка в замовленні продажу, план/факт за МО, верстати, енергія, матеріали) | 7 | [v0.1, 30 р.](modules/td_sale_cost/ARCHITECTURE.md) | [v0.1, 67 р.](modules/td_sale_cost/SPEC.md) |
| 21 | `td_live_production` (демо-стенд: живе виробництво — планувальник доби, диспетчер нарядів, простої, відвантаження, підготовка компанії; не частина продукту) | 7 | [v0.1, 44 р.](modules/td_live_production/ARCHITECTURE.md) | [v0.1, 63 р.](modules/td_live_production/SPEC.md) |

**Конструктор (`td_constructor`).** Продукт називається просто «Конструктор» (CD-28). З v0.2 документи описують об'єднаний конструктор (CD-27, CD-29…CD-31): один код ядра `factory3d/core/constructor` (JS + Three.js без Odoo; [README ядра](../core/constructor/README.md)) обслуговує модуль і прототип-артефакт через адаптер; хід злиття — хвилі 0–2, слайси S1…S6 ([ARCHITECTURE §2.2a і §6](modules/td_constructor/ARCHITECTURE.md)); критерії приймання злиття — [SPEC §12.1](modules/td_constructor/SPEC.md);
журнал змін модуля — [CHANGELOG](../odoo_addons/td_constructor/CHANGELOG.md). Плани й рішення замовника: [MERGE.md](../build/constructor/MERGE.md) (план злиття, російською), [DECISIONS.md](../build/constructor/DECISIONS.md) (CD-01…CD-31). Відкриті питання конструктора — Q-15…Q-22 (ARCHITECTURE §5.1).

**Енергетика (хвилі W1–W4, стан на 19.10.2026).** Модулі № 6 і 14–19 збудовано; їхні документи переведено з робочих файлів `build/energy/W*_SPEC.md`/`W*_ARCH.md` у `modules/`, а відхилення й рішення збірки внесено в розділ «Журнал змін документа» наприкінці кожного файлу. W1 (`td_energy`, `td_genset_factory3d`) лишається за посиланням на `build/energy/W1_SPEC.md` і `W1_ARCH.md` (див. кінець `modules/td_energy/SPEC.md`). W2 — `td_energy_control` і міст `td_energy_viewer3d` (плагін збирача — [README плагіна](../services/collector_plugins/td_collector_energy/README.md)), W3 — `td_energy_resources` і міст `td_energy_resources_bms`, W4 — `td_energy_analytics` і `td_energy_mobile` (архітектура спільна). Рішення D-45…D-49 (W2) також у журналі рішень [ARCHITECTURE.md](ARCHITECTURE.md) §8; нумерація D-xx у документах енергетики модульна.

## Як читати

1. Каркас `ARCHITECTURE.md` §2–§6 — що є в системі й які контракти спільні.
2. Технічне рішення модуля — процес, ролі, FR, інтеграції, налаштування, інструкції.
3. Специфікація модуля — розробнику (§0–§11) і тестувальнику (§12–§14: AC, юніт-тести, стендові ТК на емуляторі).
4. Питання до замовника — `CONSISTENCY.md`, розділи «Питання до замовника» (19 пунктів) і «Відповіді на питання до
   замовника» (усі 19 отримали відповідь 14.10.2026); у модулях — §5 ARCHITECTURE і §15 SPEC, закриті Q-xx мають
   позначку «Закрито 14.10 (відповідь № N)».
