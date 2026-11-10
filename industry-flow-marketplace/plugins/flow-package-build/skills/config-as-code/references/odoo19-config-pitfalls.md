# Пастки Odoo 19 для конфіг-даних

Довідка-нагадування; не дублює `boost:odoo19-lint` (він перевіряє файли). Кожен пункт звірити `boost:source-check`, коли від нього
залежить значення чи ім'я поля, -- тут не джерело правди.

| Було (≤17/18) | Odoo 19 | Куди дивитись |
|---|---|---|
| `res.users.groups_id` | `group_ids` | `odoo_get_fields res.users` |
| `res.groups.users` | `user_ids` | `odoo_get_fields res.groups` |
| `res.groups.category_id` | `privilege_id` | `odoo_get_fields res.groups` |
| `ir.cron`: `numbercall` | поля немає | `odoo_get_fields ir.cron` |
| `attrs=`, `states=` у XML-поданнях | прибрані | `odoo19-lint` |
| Продукт `type='product'` (склад) | `is_storable` на товарі типу consu | `odoo_get_fields product.template` |
| Категорії одиниць виміру (`uom`) | за довідкою категорій одиниць у 19 немає; не вживати `category_id`, спершу перевірити `odoo_get_fields uom.uom` | `odoo_get_fields uom.uom` |
| `_sql_constraints` | замінені (у модулях, не в даних) | `odoo19-lint` |

Загальне: поле, якого немає в `odoo_get_fields` на чистій базі, у дані не потрапляє (FAIL). Якщо наведене тут розходиться з
базою -- вірити базі й записати розбіжність у `memo`.
