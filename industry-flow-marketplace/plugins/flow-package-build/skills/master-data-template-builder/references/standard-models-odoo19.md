# Типові моделі майстер-даних і мінімальні колонки

Відправна точка для переліку, не джерело істини. **Кожну колонку звіряти через `odoo_get_fields` на тестовій базі**
(з установленими модулями пакета); сумнів щодо Odoo 19 - `boost:source-check`. Чого тут немає - не вигадувати.
Чи потрібна модель, вирішують ТР (довідник) і ALLOCATION (трек), а не цей список.

| Модель | Модуль | Орієнтовні колонки (перевірити) | Залежить від |
|---|---|---|---|
| `uom.uom` | uom/product | `id`, `name`, поля коефіцієнта/базової одиниці (структуру в 19 звірити) | - |
| `product.category` | product | `id`, `name`, `parent_id/id` | сама на себе (спершу батьки) |
| `product.attribute`, `product.attribute.value` | product | `id`, `name`, `attribute_id/id` | attribute -> value |
| `res.partner` (компанії) | base | `id`, `name`, `is_company`, ранги постачальника/клієнта за наявності | - |
| `product.template` | product (+stock, mrp) | `id`, `name`, `type`, `is_storable` (якщо є), `categ_id/id`, `uom_id/id` | category, uom |
| `product.supplierinfo` | product/purchase | `id`, `partner_id/id`, `product_tmpl_id/id`, `min_qty`, `delay` | partner, product |
| `stock.warehouse` | stock | `id`, `name`, `code` | - |
| `stock.location` | stock | `id`, `name`, `location_id/id`, `usage` | warehouse / батьківська локація |
| `mrp.workcenter` | mrp | `id`, `name`, `code` (решту звірити) | - |
| `mrp.bom` | mrp | `id`, `product_tmpl_id/id`, `product_qty`, `type` | product |
| `mrp.bom.line` | mrp | `id`, `bom_id/id`, компонент (`product_id/id`, звірити), `product_qty` | bom, product |
| `mrp.routing.workcenter` | mrp | `id`, `name`, `bom_id/id`, `workcenter_id/id` (час - звірити поле) | bom, workcenter |

Правила:
- Модель без установленого модуля на тестовій базі в шаблон не потрапляє: звіт «тестова база не відповідає переліку».
- `product.product` окремо - лише якщо ТР потребує варіантів; інакше достатньо `product.template`.
- Моделі `td_*` - лише в `td/` (SKILL.md, Крок 2).
