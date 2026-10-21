# td_sale_cost

Вау-функція №25 «Собівартість замовлення наживо». Міст `auto_install` (`sale_mrp` + `td_factory3d`): у замовленні продажу смарт-кнопка
«Собівартість: факт N ₴ · маржа M %» і форма з розбивкою за статтями (верстати, енергія, матеріали, відходи) та за МО, план і факт, відхилення з кольором.
Усе рахується при відкритті з даних пов'язаних МО, нічого не зберігається. Колонки «Маржа план/факт, %» у списку замовлень (за замовчуванням сховані).

Верстати (`td_machine_connect`: `td.machine.state.log`) і енергія (`td_energy`: `td.energy.alloc`) необов'язкові: без них час береться з журналу часу операцій, а енергія — «немає даних».
Параметри: `td.sale_cost.warn_pct` (5), `td.sale_cost.alert_pct` (15). Права: керівник продажів або менеджер «3D Завод».

Документація: `factory3d/docs/modules/td_sale_cost/` (`SPEC.md`, `ARCHITECTURE.md`).
Тести: `F3D_TEST_INSTALL=td_sale_cost factory3d/tools/odoo/run_tests.sh <db> /td_sale_cost` (повніше: `td_sale_cost,td_energy,td_machine_connect`).
