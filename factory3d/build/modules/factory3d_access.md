# factory3d_access
Статус: IN_PROGRESS
Тесты: 39/39 (2026-10-15), ТК: ждут W5
Решений без заказчика: 3 (ниже)
Упирался в лимит: 0
Требует внимания человека: нет

| Воркер | Статус | Коммит | Тест |
|---|---|---|---|
| W0 | принят | 917c547 | TestAccessInstall 6/6 |
| W1 | принят | e663a0d | /factory3d_access 39/39 |
| W2 | в работе | — | — |
| W3 | ждёт | — | — |
| W4 | ждёт | — | — |
| W5 | ждёт | — | — |

## Решения без заказчика
- DEC-1: factory3d_telemetry/viewer/fire_safety не смержены — мост factory3d_access_telemetry и опциональные интеграции тестируются только при наличии модулей (`'<model>' in env`), иначе тесты skip — tests/
- DEC-2: TestPoll (AC-06…AC-09) перенесён из W1 в W2 — опрос создаёт f3d.access.event (модель W2) — tests/test_events.py
- DEC-3: data/f3d_access_server_data.xml и f3d_access_device_data.xml сделаны в W1 (нужны тестам W1), W4 лишь дополняет
