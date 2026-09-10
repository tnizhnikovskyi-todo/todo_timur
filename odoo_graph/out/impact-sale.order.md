# Анализ влияния: `sale.order`

База `edu-online-todo`, Odoo 19.0. Снимок метаданных: 2026-09-10.

**Затронуто объектов:** 6 кастомных полей, 5 представлений, 3 автоматизаций, 5 действий сервера, 4 правил доступа.

## Кастомные поля

| Поле | Подпись | Тип | Связь | Где выводится | Кто пишет | Условие автоматизации |
|---|---|---|---|---|---|---|
| `x_discount_approval` | Узгодження знижки | selection | — | **нигде** | «Поставити «потрібна віза керівника»», «Поставити «потрібна віза директора»», «Знижка узгоджена», «Узгодити знижку» | — |
| `x_discount_visa` | Віза керівника на знижку | boolean | — | **нигде** | только вручную | id 2, id 3, id 4 |
| `x_logistyka_sposib` | Логістика: спосіб передачі | char | — | id 4877, id 4883, id 4884 | только вручную | — |
| `x_logistyka_termin` | Логістика: обіцяна дата передачі | date | — | id 4877, id 4884 | только вручную | — |
| `x_taryf_pidpysky` | Тариф підписки | char | — | id 4877, id 4891 | только вручную | — |
| `x_todo_umova_postavky` | Умова поставки | selection | — | id 4861 | только вручную | — |

## Представления

| id | Название | Тип | Режим | Наследует |
|---|---|---|---|---|
| 4861 | sale.order.form — умова поставки (власне поле) | form | extension | sale.order.form (id 1528) |
| 4877 | sale.order.form.logistyka.todo | form | extension | sale.order.form (id 1528) |
| 4891 | sale.order.list.prodovzhennya.todo | list | primary | — |
| 4883 | sale.order.list.segment.todo | list | primary | — |
| 4884 | sale.order.list.shop.todo | list | primary | — |

## Автоматизации и действия

- **Віза керівника — знижка узгоджена** (id 4, триггер `on_create_or_write`)
  - условие: `[('x_discount_visa','=',True)]`
  - действия: «Знижка узгоджена» (object_write)
- **Знижка понад 10 % — віза керівника** (id 2, триггер `on_create_or_write`)
  - условие: `[('order_line.discount','>',10),('order_line.discount','<=',25),('state','in',('draft','sent')),('x_discount_visa','=',False)]`
  - действия: «Поставити «потрібна віза керівника»» (object_write)
- **Знижка понад 25 % — віза директора** (id 3, триггер `on_create_or_write`)
  - условие: `[('order_line.discount','>',25),('state','in',('draft','sent')),('x_discount_visa','=',False)]`
  - действия: «Поставити «потрібна віза директора»» (object_write)

Действия сервера без привязки к автоматизации (запускаются вручную):
- «Погодити знижку (перевірка)» (id 1311, object_write)
- «Узгодити знижку» (id 1317, object_write)

## Правила доступа

| id | Название | Глобальное | Группы | Домен |
|---|---|---|---|---|
| 185 | All Orders | нет | 18 | `[(1,'=',1)]` |
| 184 | Personal Orders | нет | 17 | `['|',('user_id','=',user.id),('user_id','=',False)]` |
| 182 | Portal Personal Quotations/Sales Orders | нет | 10 | `[('partner_id','child_of',[user.commercial_partner_id.id])]` |
| 179 | Sales Order multi-company | да | — | `[('company_id', 'in', company_ids)]` |

