# factory3d_iot_sim
Статус: IN_PROGRESS
Тесты: svc 156/156 + Odoo 40/40 (2026-10-14), ТК: ждут стенд
Решений без заказчика: 0 (ниже)
Упирался в лимит: 0
Требует внимания человека: нет

| Воркер | Статус | Коммит | Тест |
|---|---|---|---|
| W0 | принят | 670b3fb | unit 3/3, TestInstall OK |
| W1a | принят | e3023b2 | unit 79/79, core cov 99 %, ruff OK |
| W1b-2 | принят | d2fdc56 | svc 156/156, models cov 99 % |
| W1b-1 | в работе (worktree) | — | — |
| W2 | принят | 1348d5d | svc tests 98/98, ruff OK |
| W3 | в работе (worktree) | — | — |
| W4 | ждёт | — | — |
| W5 | принят | 6e43f5b | Odoo /factory3d_iot_sim 40/40 |
| W6 | ждёт | — | — |

## Решения без заказчика
- DEC-1: `services/iot_sim` из SPEC §0.1 размещён в `factory3d/services/iot_sim` (как `factory3d/odoo_addons`).
- DEC-2: `check-config` требует SIM_API_TOKEN ≥32 символов и пароли протоколов (exit 2/1); в W0 версии зависимостей не закреплены «==» — закрепить при добавлении библиотек протоколов (W2–W4). — `services/iot_sim/iot_sim/__main__.py`, `requirements.txt`
- DEC-3: W1 разбит на W1a (ядро, World/Model/Event, сценарии) и W1b (машины поведения пристроїв) — объём; W5 зависит только от W0 и запущен параллельно с W1a.
- DEC-4: переход на зимнее время — 25.10.2026 (последнее воскресенье октября), а не 26.10 из SPEC §11 — правка SPEC. — `tests/unit/test_clock.py`
- DEC-5: допущения W1a (`# ASSUMPTION` в `core/scenarios.py`): blackout занимает dev:COMPRESSOR и dev:AIR-RING для конфликтов; календарь смен Пн–Пт 07:00–15:30; `ctx.cleanup` сбрасывает принудительные сигналы на номинал.
- DEC-6 (W5): полный прогон всех odoo_addons не стартует — мост `factory3d_base_mrp_maintenance` требует Enterprise (ENV-1 base); тестируем `F3D_TEST_INSTALL=factory3d_base,factory3d_iot_sim`.
- DEC-7 (W5): перенос меню рівня 0 — в `views/menus.xml` (в level0.xml ref ещё не разрешим по порядку §1). Уникальность unit_id — по (unit_id, driver), ADAM-драйверы исключены (§5.2 кладёт несколько пристроїв на один ADAM-unit). — `models/sim_device.py`
- DEC-8 (W5): CSV каталога W0 без name/kind/origin — загрузчик выводит origin из `status`, kind из dtype/model, name «пристрій · лист»; `energy/consumers/X/*` → пристрій `X-PM`. На шаблоне без демо-данных 180 пристроїв каталога создаются пассивными. — `hooks.py`
- DEC-9 (W5): test_migration упрощён (нет фикстуры data-модуля 19.0.1.0.0): повтор хука сохраняет x_f3d_signal/меню; uninstall удаляет и x_-данные рівня 0 (их файлы принадлежат модулю) — предупреждение в логе. icon.png — не сделан.
- DEC-10 (W2): JobOrderList — String[] JobOrderID (без nodeset ISA-95), события — BaseEventType; Call-запросы OPC UA разрешены только SIM_OPCUA_USER; follow_odoo auto-feed портала и состояния running/done в /jobs не реализованы (TODO W4/W6). — `protocols/opcua_server.py`, `jobs_api.py`
- TODO `__main__ run`: регистрация серверов W2–W4 и цикл world.tick_real — после W4 (лидер).
- DEC-11 (W1b-2): R-11 по формуле даёт коэффициент 0,84…1,0 (r ∈ [−1,1)), AC-11 пишет 0,92…1,0 — реализовано по формуле, правка SPEC. Хук ретранслятора genset — `models/ats.py` (relay_cb; без ответа — запасной режим §8.14). Нет в каталоге: AIR-RING, ATyS 20490+, датчики освещения 322.
- TODO ядро: коллизия коротких ключей `World.devices[code].signals` (AHU-1/p_now из ventilation и energy/consumers) — один сигнал теряется; модели читают по полному коду. — `core/world.py` `_build`
