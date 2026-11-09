# industry-flow

Маркетплейс Claude Code зі скілами для флоу створення тиражованих галузевих пакетів на Odoo 19 («AI робить, людина вирішує й перевіряє»). Концепція — `_work/CONCEPT.md`.

## Плагіни

| Плагін | Призначення | Кроки |
|---|---|---|
| `flow-core` | Ядро флоу | Наскрізний: C-06 (цикл AI-кроку), C-05, C-07, C-08; вхід для всіх кроків флоу. |
| `flow-research` | Дослідження до рішення «будуємо пакет?» | A-01, A-04, A-05, A-20, A-21, A-23 (+ список лідів B-01). |
| `flow-package-build` | Збірка тиражованого пакета | A-09, A-12, A-13, A-14, A-15 (+A-22), A-18. |
| `flow-client-delivery` | Впровадження пакета в клієнта | B-02, B-03, B-04, B-06, B-09/B-10, B-11 (+B-13). |
| `flow-package-evolution` | Розвиток пакета | D-01, D-02, D-03; чернетки рішень A-07, A-17, D-04, D-05. |

`flow-core` потрібен усім: у ньому цикл AI-кроку і спільні конвенції (`plugins/flow-core/references/`).

## Установка

```
claude plugin marketplace add <шлях до цієї теки або репозиторій GitHub>
claude plugin install flow-core@industry-flow
claude plugin install flow-research@industry-flow
claude plugin install flow-package-build@industry-flow
claude plugin install flow-client-delivery@industry-flow
claude plugin install flow-package-evolution@industry-flow
```

Версія скіла в наряді = версія плагіна (`skill_ref: <плагін>:<скіл>@<semver>`), звірка точна.

## Правила

Наряд — задача Odoo; результат — PR; звіт — у задачу; прод клієнта заборонено; `connection_id` явно в кожному виклику `odoo-mcp`.
