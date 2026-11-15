# PLAN (фікстура ok)
## Модель даних
| Модель / поле | Нова чи розширення | Стандартний аналог (файл:рядок 19.0) | Чому не стандарт |
|---|---|---|---|
| sale.order.td_expected_date | розширення (_inherit), compute | addons/purchase/models/purchase_order.py:NNN (date_planned, читаємо) | — |
| td.mebli.margin.report | нова | немає | Звіту маржі за виробом у стандарті немає |
| td.mebli.catalog | нова | немає | Є у ToDo-готовому модулі, перенесено |
