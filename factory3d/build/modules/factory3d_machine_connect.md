# factory3d_machine_connect
Статус: IN_PROGRESS
Тесты: —, ТК: ждут W9
Решений без заказчика: 15 (ниже)
Упирался в лимит: 0
Требует внимания человека: правка в factory3d_telemetry (DEC-7); AC-13 vs R-05 (DEC-8); ISA95-структуры — допущение Q-01

| Воркер | Статус | Коммит | Тест |
|---|---|---|---|
| W0 | принят | 34039a1 | TestCommands 5/5 |
| W1 | принят | e202c60 | /factory3d_machine_connect 23/23 |
| W7 | принят | 7643fa9 | pytest unit 51/51, ruff |
| W2 | принят | 98d7c3c | /factory3d_machine_connect 55/55 (с W5) |
| W5 | принят | 0dce9e7 | /factory3d_machine_connect 55/55 |
| W4 | принят | 57a6daf | /factory3d_machine_connect 68/68 |
| W6 | принят | ca5b681 | /factory3d_machine_connect 80/80 |
| W3 | принят | 29ca2f4 | /factory3d_machine_connect 100/100 |
| W8 | в работе | | |

## Решения без заказчика
- DEC-1 (ENV-3): `mrp_workorder` (Enterprise) убран из `depends`; в CE 19.0 у `mrp.workorder`/`mrp.workcenter` нет
  `employee_ids`/`start_employee`/`stop_employee`. Ядро: собственное поле `mrp.workorder.f3d_employee_id` (оператор,
  проставляется при автостарте), старт/стоп — через `start_employee`/`stop_employee`, если метод есть (duck typing),
  иначе `button_start`/`button_finish`; разрешённые работники РЦ — `wc.employee_ids`, если поле есть, иначе пусто.
  Мост `factory3d_machine_connect_mrp_workorder` (auto_install) — минимальный, не тестирован (нет Enterprise).
  Тесты, требующие полей Enterprise, — с пропуском. — `models/mrp_workorder.py`, `models/f3d_machine_wo.py`
- DEC-2: AC-58 требует ключ запобіжника telemetry в тексте ошибки, а telemetry его не пишет — проверки module/source/signal
  продублированы в `_f3d_mc_create_command` до `create`; telemetry не менялся. — `models/f3d_command.py`
- DEC-3: Odoo 19 не принимает `target='inline'` у act_window — `action_f3d_mc_settings` без target. — `views/menus.xml`
- DEC-4: push-маршрут `mc_woodstore/status` → `f3d.gantry.job._f3d_apply_status` (SPEC не называет владельца). — `models/push_handler.py`
- Тесты гонять с `F3D_TEST_INSTALL=factory3d_machine_connect` (иначе ставится мост base_mrp_maintenance без Enterprise).
- DEC-5: kanban V-01 в Odoo 19 не берёт dotted-поля — вместо `current_downtime_id.loss_id` показан сам простой,
  цвет OEE — фиксированные пороги 0.75/0.5 вместо `oee_color`. — `views/f3d_machine_views.xml`
- DEC-6: пізні показання (`ts < state_since`) пропускают state/mode/alarm/job, счётчик обрабатывается; показания
  с одним `ts` — один переход (AC-03). — `models/f3d_machine.py`
- DEC-7: дефект в factory3d_telemetry `push_handler._f3d_handler_models` — `registry.descendants` в Odoo 19 возвращает
  имена, а не классы; push-события не маршрутизировались никуда. Исправлено в telemetry (229/229 зелёные), коммит dfab530.
  Обходы `patch.object` в тестах W2/W5 безвредны.
- DEC-8: AC-13 (простой 1,5 хв «лишається») противоречит R-05 п.4 (micro_stop_s=120 → удаление). Реализовано по R-05,
  тест AC-13 снижает `micro_stop_s` до 60. — `models/f3d_machine_downtime.py`, `tests/test_downtime.py`
- DEC-9: R-06 п.5 — новый «Аварія триває» открывается, только если у простоя нет ни одного открытого записи
  (машинного или оператора) — без перекрытий. — `models/mrp_workcenter_productivity.py`
- DEC-10: портал — завдання `sent` без `ws_id` усыновляется событием woodStore с тем же МО и товаром (без дубля);
  R-17 расщепляет зарезервированную строку при недоподаче; авто-поповнення не чаще раза в час на стос (`replenish_at`). — `models/f3d_gantry_*.py`
- DEC-11: адаптер `cutopt` держит связь job_id→карта в памяти; после рестарта колектора `map` в событиях = null,
  Odoo сопоставляет по `job_id` (проверить в W6). Метрики `collector_mc_*` создаются лениво в реестре ядра;
  `mc_state_dir` → env `F3D_MC_STATE_DIR` → `buffer_dir`. — `f3d_collector_mc/{cutopt,events}.py`
- DEC-12: OEE — категории timelog по xmlid (setup = `mrp.block_reason2` + `loss_tool`, fault = `mrp.block_reason1`,
  прочие availability/quality = idle; productive/performance = run); запись смены не создаётся до её начала и в
  выходной; действие «OEE за період» — `action_f3d_oee_period_sum` (id `action_f3d_oee_period` занят W0). — `models/f3d_oee_shift.py`
- DEC-13: API-01 отдаёт карту в состояниях `exported` и `optimizing` (409 для прочих) — `action_send_optimizer` сразу
  ставит `optimizing`, по букве SPEC колектор всегда получал бы 409; 413 — при >5000 строк карты или теле >1 МБ;
  тайм-аут оптимизации 30 хв — от `optimizing_since` (запасной — `write_date`). — `controllers/cutmap.py`, `models/f3d_cut_map.py`
- DEC-11 (доп.): push_handler `mc_cutopt` — `map` необязателен, карта через `f3d.cut.map._f3d_find_for_event(map, job_id)`. — `models/push_handler.py`
- DEC-14: автостарт (DEC-1 в CE) — R-09 п.4(б) упрощён: «сегодня» = начало локального дня, а не первый интервал ППЧ;
  работник записи = `wo.f3d_employee_id`, иначе работник пользователя; ответственный активности «нет задания» —
  `equipment.technician_user_id`, иначе admin (у `mrp.workcenter` в CE нет technician). `f3d.machine` получил
  `mail.activity.mixin`. `_f3d_close_timers` режет `date_end` до `ts` всегда (AC-11). — `models/f3d_machine_wo.py`
- DEC-15: неполная партия снимает `active_workorder_id`, автостарт пропускает WO с `f3d_partial_hold`; отложенная
  микрозупинка считается «не working» для завершения I/O по `finish_idle_s`. — `models/f3d_machine_wo.py`
