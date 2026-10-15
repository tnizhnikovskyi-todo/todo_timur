# factory3d_access
Статус: IN_PROGRESS
Тесты: 154/154 (2026-10-15), ТК: ждут W5
Решений без заказчика: 12 (ниже)
Упирался в лимит: 0
Требует внимания человека: мост factory3d_access_telemetry не установлен/не тестирован (нет factory3d_telemetry); AC-69 target inline→current (правка SPEC)

| Воркер | Статус | Коммит | Тест |
|---|---|---|---|
| W0 | принят | 917c547 | TestAccessInstall 6/6 |
| W1 | принят | e663a0d | /factory3d_access 39/39 |
| W2 | принят | 4194342 | /factory3d_access 83/83 |
| W3 | принят | a7f9485 | /factory3d_access 116/116 |
| W4 | принят | b5cd612 | /factory3d_access 154/154; мост не ставится (нет telemetry) |
| W5 | в работе | — | — |

## Решения без заказчика
- DEC-1: factory3d_telemetry/viewer/fire_safety не смержены — мост factory3d_access_telemetry и опциональные интеграции тестируются только при наличии модулей (`'<model>' in env`), иначе тесты skip — tests/
- DEC-2: TestPoll (AC-06…AC-09) перенесён из W1 в W2 — опрос создаёт f3d.access.event (модель W2) — tests/test_events.py
- DEC-3: data/f3d_access_server_data.xml и f3d_access_device_data.xml сделаны в W1 (нужны тестам W1), W4 лишь дополняет
- DEC-4: пожарный код 26368 действует на все двери сервера, даже если door_id определён через устройство — models/f3d_access_event.py
- DEC-5: в presence проход периметра in/out сбрасывает f3d_access_zone_door_id; reprocess для done без attendance_id — полная обработка — models/f3d_access_event.py
- DEC-6: AC-37 без factory3d_fire_safety — _f3d_drill_active мокается в тесте; без модуля возвращает False — models/fire_passage_source.py
- DEC-7: возвращённая карта посетителя хранит visitor_id до R-20 шаг 5 (constraint «пул без человека» не для returned); карта lost уходит в API-08 как заблокированная — models/f3d_access_card.py
- DEC-8: пользователь BioStar посетителя создаётся до выдачи карты (карте нужен user_id), под write_enabled — models/f3d_access_visitor.py
- DEC-9: разрешённые зоны посетителя проверяются только на внутренних дверях; поздние события посетителя — attendance_action='late' — models/f3d_access_visitor.py
- DEC-10: action_f3d_access_settings target='current' — 'inline' недопустим в Odoo 19 (AC-69 в SPEC требует inline, нужна правка SPEC) — views/res_config_settings_views.xml
- DEC-11: sudo-агрегаты провайдера вынесены в AbstractModel f3d.access.viewer.data (A-21, DoD «sudo только в _f3d_access_public_presence» буквально) — models/viewer_data.py
- DEC-12: поле document_checked (V-08, Q-06) исключено из запрета AC-64 на поля «document» — tests/test_security.py
