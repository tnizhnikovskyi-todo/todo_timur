# Решения менеджера по среде (Odoo 19 Community)

В среде нет трёх стандартных модулей: `mrp_maintenance`, `mrp_workorder`, `web_gantt` (Enterprise / нет в 19.0 CE).
Для них правило `BLOCKED-ENV` из `MODULE_LEAD.md` **не применяется**: ядро модуля ставится на Community,
зависящее от Enterprise — в мост `auto_install`. Каждое отступление от SPEC — `DEC-N` в отчёте модуля со ссылкой на `ENV-N`.
Мосты пишутся минимальными; в отчёте пометка «мост не тестирован — нет Enterprise». Тест, требующий модуля
Enterprise, — с пропуском, если модуль не установлен. Другие недоступные зависимости — `BLOCKED-ENV`, как в `MODULE_LEAD.md`.

- **ENV-1 `factory3d_base`**: убрать `mrp_maintenance` из `depends`. Связь оборудования с рабочим центром —
  по `f3d_code` (A-15). Заполнение стандартного `maintenance.equipment.workcenter_id` — в мосте
  `factory3d_base_mrp_maintenance` (depends `factory3d_base`, `mrp_maintenance`).
  Потребитель — `factory3d_viewer` (SPEC: заявка на обслуживание по РЦ): искать по коду, а не по `workcenter_id`.
- **ENV-2 `factory3d_energy`**: убрать `mrp_workorder`. `time_ids` и наследуемые представления V-16 брать из CE `mrp`
  (сверить xmlid в исходниках 19.0). Чего нет в CE — в мост `factory3d_energy_mrp_workorder`.
- **ENV-3 `factory3d_machine_connect`**: убрать `mrp_workorder`. Атрибуция оператора (R-09/R-12): сначала проверить
  в CE `mrp` 19.0 наличие `employee_ids` / `start_employee` / `stop_employee`; если нет — собственное поле
  оператора и штатные `button_start` / `button_finish`; связь с полями Enterprise — в мост
  `factory3d_machine_connect_mrp_workorder`.
- **ENV-4 `factory3d_yard`**: убрать `web_gantt`. V-09 (gantt) и его место первым видом `action_f3d_yard_booking` —
  в мост `factory3d_yard_gantt` (depends `factory3d_yard`, `web_gantt`); в ядре первый вид — календарь V-10.
  AC-53 — тест с пропуском без `web_gantt`.
