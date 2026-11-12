# Межі з сусідніми скілами

| Питання | Власник | Що робить industry-deep-dive |
|---|---|---|
| Галузева довідка для discovery клієнта (A-03) | `odoo19-discovery-initiation:industry-briefing` | читає `briefing.md` як вхід; не дублює й не переписує |
| Конкуренти одного клієнта | `odoo19-discovery-initiation:competitor-mapper` | не використовується; тут реєстр 25–40 галузі, не клієнта |
| Минулі проєкти (патерни) | `flow-research:past-projects-analyzer` (A-04) | читає `past-projects.md` |
| Сам код і модулі ToDo, рішення «беремо/адаптуємо/ні» | `flow-research:reuse-modules` (A-03c) | колонку «ToDo-готовий» лишає порожньою; заповнює A-20 |
| Анкета власника | `flow-research:owner-questionnaire` (A-02b) | читає, не змінює; блокуюче поле порожнє — `waiting_human` |
| Концепція, BOX, SALES, AI-DECISIONS (рядки A-20) | `flow-research:concept-mapper` (A-20) | пише лише `FUNCTIONAL-MAP §5` «Резюме» і свої рядки AI-DECISIONS (A-03b); решту пише A-20 |
| Сторінка для власника | `flow-research:concept-presentation` (A-20c) | віддає дані й `REJECTED.md`; сторінку не будує |
| Відбір компаній і ЄДРПОУ | `flow-research:segment-selector` | не відбирає; агрегати odb-catalog — лише для смуг ринку |
| Запис рішень власника в журнал | `flow-core:flow-state-keeper` | не пише в `flow/decisions.md` сам |
