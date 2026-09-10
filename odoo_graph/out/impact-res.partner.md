# Анализ влияния: `res.partner`

База `edu-online-todo`, Odoo 19.0. Снимок метаданных: 2026-09-10.

**Затронуто объектов:** 3 кастомных полей, 4 представлений, 0 автоматизаций, 0 действий сервера, 4 правил доступа.

## Кастомные поля

| Поле | Подпись | Тип | Связь | Где выводится | Кто пишет | Условие автоматизации |
|---|---|---|---|---|---|---|
| `x_dzherelo_migracii` | Джерело міграції (id у старій системі) | char | — | id 4876, id 4882 | только вручную | — |
| `x_migraciya_zvirena` | Звірено з джерелом | boolean | — | id 4876, id 4882 | только вручную | — |
| `x_todo_segment` | Сегмент клієнта | selection | — | id 4858, id 4860 | только вручную | — |

## Представления

| id | Название | Тип | Режим | Наследует |
|---|---|---|---|---|
| 4858 | res.partner.form — сегмент у картці (перевірка) | form | extension | res.partner.form (id 127) |
| 4860 | res.partner.form — тільки для ролі (перевірка) | form | extension | res.partner.form (id 127) |
| 4876 | res.partner.form.migraciya.todo | form | extension | res.partner.form (id 127) |
| 4882 | res.partner.list.migraciya.todo | list | primary | — |

## Автоматизации и действия

_Автоматизаций нет._

## Правила доступа

| id | Название | Глобальное | Группы | Домен |
|---|---|---|---|---|
| 2 | res.partner company | да | — | `['|', '|', ('partner_share', '=', False), ('company_id', 'parent_of', company_ids), ('company_id', '=', False)]` |
| 3 | res_partner: portal/public: read access on my commercial partner | нет | 10, 11 | `[('id', 'child_of', user.commercial_partner_id.id)]` |
| 178 | Власний довідник: бачити лише свої компанії (перевірка) | да | — | `[('company_id', 'in', company_ids + [False])]` |
| 97 | Контрагенти: менеджер бачить своїх (перевірка) | нет | 17 | `[('user_id', 'in', [user.id, False])]` |

