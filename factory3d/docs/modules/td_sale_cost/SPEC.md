# td_sale_cost — специфікація (вау №25 «Собівартість замовлення наживо»)

Версія `19.0.1.0.0`. Міст `auto_install`: у замовленні продажу видно собівартість і маржу (план і факт) з реальних даних пов'язаних МО. Нічого не зберігається, кожне відкриття рахує заново.
Рішення — [ARCHITECTURE.md](ARCHITECTURE.md).

## 1. Маніфест і файли

`depends: [sale_mrp, td_factory3d]` (`sale_mrp` → `sale`, `mrp`, `stock_account` з `stock.move.value`; `td_factory3d` — група `group_td_manager`). Верстати (`td.machine.state.log`),
енергія (`td.energy.alloc`) і карти розкроя (`td.cut.map`) — необов'язкові (`in self.env`); без них лише стаття «Енергія» порожня, а час верстатів береться з журналу часу.
Файли: `models/{td_sale_cost_calc,td_sale_cost,sale_order}.py`, `tools/cost.py` (чисті функції), `views/{sale_order,td_sale_cost}_views.xml`, `security/ir.model.access.csv`, `tests/`.

## 2. Моделі

- **M-01 `td.sale.cost.calc`** (Abstract): `_td_calc(orders) → {order.id: результат}` (лише замовлення з МО), пакетно, від `sudo()`.
- **M-02 `td.sale.cost`** (Transient): форма; `_td_open(order)`, `action_refresh`; підсумки `price`, `plan_cost`, `plan_now_cost`, `fact_cost`, `forecast_cost`, `margin_*[_pct]`, `dev_pct`, `level`, `progress_pct`, `warnings`; рядки `article_line_ids`, `mo_line_ids`.
- **M-03 `td.sale.cost.line`** (Transient): `plan`, `plan_now`, `fact`, `deviation`, `dev_pct`, `level`, `has_*`, `fact_{machine,energy,material,waste}` (для МО), `note`.
- **M-04 `sale.order`**: нескладені compute `td_cost_plan`, `td_cost_fact`, `td_margin_{plan,fact}_pct`, `td_cost_level`, `td_cost_label`; `action_td_sale_cost()`; `groups` = `sales_team.group_sale_manager`, `td_factory3d.group_td_manager`.

## 3. Правила

**R-01. МО.** `mrp_production_ids` (`sale_mrp`) ∪ МО з `origin` = номер замовлення (без батьківської групи), без скасованих; далі підМО напівфабрикатів (дочірня група або `origin` = номер МО), рекурсивно.
Напівфабрикат, який виготовляє підМО, не входить у матеріали батька (подвійного рахунку немає). Ціна = `amount_untaxed` у валюті компанії. «Зараз» = демо-годинник `td.viewer.demo_clock` (Київ), інакше реальний час (як R-30 td_machine_connect); відкриті записи журналу рахуються до нього.

**R-02. Верстати.** Факт = хвилини / 60 × `costs_hour` РЦ. Хвилини: `td.machine.state.log` (`working`+`setup`), якщо є записи для операції, інакше журнал часу (як `get_duration`). План = `duration_expected` / 60 × `costs_hour`. РЦ з хвилинами й нульовою ставкою — у нотатці.

**R-03. Енергія.** Факт = Σ `td.energy.alloc.cost` за МО; немає рядків — «немає даних» (`None`, не 0), немає модуля — «не встановлено». План (оцінка) = плановий час / 60 × ₴ за годину роботи РЦ за історією розподілу (немає історії — плану немає).

**R-04. Матеріали.** План = `product_qty` рухів `move_raw_ids` × `standard_price`. Факт: рух `done` — `abs(stock.move.value)`, без вартості — кількість × `standard_price` (оцінка); не виконаний, але `picked` — кількість × `standard_price` (оцінка); резерв — не факт («ще не списано»). Позиції з `standard_price = 0` — нотатка «матеріали занижені».

**R-05. Відходи.** Факт = виконані `stock.scrap` МО. Відхід розкроя за картами (`plan_waste_pct × plan_sheets × ціна листа`) — лише довідка, бо листи вже в матеріалах. Ні браку, ні карт — «немає даних». Плану відходів немає.

**R-06. Відхилення.** Частка операції: `done` = 1, інакше `min(тривалість / план, 1)`; прогрес МО — частки, зважені плановим часом. `plan_now`: верстати й енергія = план × частка; матеріали = план виконаних і «взятих» рухів. `dev% = (факт − plan_now) / plan_now`.
Колір: `ok` ≤ `td.sale_cost.warn_pct` (5), `warn` ≤ `td.sale_cost.alert_pct` (15), `alert` більше; недовитрата — `ok`; факт без плану — `warn`. Прогноз = факт + (план − `plan_now`). Маржа = (ціна − собівартість) / ціна: план, факт, прогноз.

**R-07. Інтерфейс.** V-01 смарт-кнопка «Собівартість: факт N ₴ · маржа M %» (валюта компанії, колір за `td_cost_level`, схована без МО) → V-02 форма `td.sale.cost`: підсумки, «За статтями», «За МО», «Дані й припущення», кнопка «Оновити».
V-03 колонки «Маржа план/факт, %» у `sale.view_order_tree` (`optional="hide"`, рахуються пакетно лише коли показані; без фільтрів і сортування).

**R-08. Права.** `group_sale_manager` або `group_td_manager`, інакше `AccessError`; розрахунок від `sudo()`.

## 4. Acceptance Criteria

| AC | Що перевіряє | Тести (`tests/test_calc.py`) |
|---|---|---|
| AC-01 | МО за `sale_mrp` і `origin`, підМО без подвійного рахунку, без МО — без результату | `test_fixture_links_mo`, `test_no_mo_no_cost`, `test_origin_linked_mo_and_semi_finished_rollup` |
| AC-02 | План за BOM і маршрутом, маржа плану | `test_plan_from_bom_and_route` |
| AC-03 | Факт верстатів: журнал часу, відкритий запис, нульова ставка, журнал станів, демо-годинник | `test_fact_machine_from_time_log`, `test_open_time_log_counts_live`, `test_zero_rate_is_flagged`, `test_state_log_preferred_over_time_log`, `test_demo_clock_is_now_for_open_logs` |
| AC-04 | Матеріали: резерв не рахується, «взято» — оцінка, `done` — `stock.move.value` | `test_materials_*` |
| AC-05 | Відходи: «немає даних», потім брак | `test_waste_no_data_then_scrap` |
| AC-06 | Енергія необов'язкова: нема модуля, нема рядків, є розподіл і план | `test_energy_optional` |
| AC-07 | Прогрес, `plan_now`, прогноз, колір, пороги з параметрів; чисті функції | `test_deviation_level_and_forecast`, `test_thresholds_from_parameters`, `test_cost.py` |
| AC-08 | Кнопка й поля, колонки (пакет = поодинці, приховані), незбережене замовлення | `test_smart_button_label_and_fields`, `test_list_columns_*`, `test_unsaved_order_has_no_cost` |
| AC-09 | Форма: статті, МО, нотатки, «Оновити» без дублів, замовлення без МО | `test_form_*` |
| AC-10 | Права й `auto_install` | `test_access_only_sale_manager_or_td_manager`, `test_auto_installed_bridge` |

Тести проходять у двох конфігураціях: лише `td_sale_cost` і разом із `td_energy`, `td_machine_connect`.

## 5. Демо-перевірка (набір factory3d, S00087…S00094, демо-годинник 12.10.2026 10:30)

4 МО на замовлення (3 з `origin` = замовлення + підМО фасаду). S00087: ціна 285 200, собівартість план 136 869, факт 6 874 (виконання 4,1 %, план на зараз 6 488, відхилення +6,0 %, «Увага»), маржа план 52,0 %, факт 97,6 % (занижена неповним виконанням), прогноз 51,9 %.
**Осмислена лише стаття «Верстати»** (ставки `demo_rates`, 184 записи журналу часу). Чого бракує (нічого не підганялось):
1. **Матеріали = 0:** у 59 товарів `standard_price = 0` (ціни постачальників теж 0), МО в роботі, виконаних рухів зі `stock.move.value` немає.
2. **Енергія — немає даних:** `td.energy.alloc` має лише `idle`/`overhead`/`unallocated`; пряму енергію на операції `td_energy` будує за журналом станів верстата (`td.machine.state.log`), а в демо там 1 запис.
3. **Відходи — немає даних:** карт розкроя й браку немає. 4. Валюта демо-компанії USD (`$`), на гривневій базі буде ₴.

## 6. Ризики

Ціна — усі рядки замовлення, собівартість — лише МО (змішані замовлення мають завищену маржу); МО без `origin` замовлення не знаходяться; план енергії — оцінка за історією.
