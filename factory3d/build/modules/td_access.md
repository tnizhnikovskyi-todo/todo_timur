# td_access
Статус: DONE (юнит + стенд); вне среды: копия демо-базы, ТК-09 (viewer), мост telemetry, drill ТК-10 (fire_safety)
Тесты: 156/156 (2026-10-15), ruff/xmllint OK; ТК: прогнаны 9/10 (ТК-09 skip), ТБ 8/8, ТП 4/4, stand 21 passed/1 skip
Решений без заказчика: 13 (ниже)
Упирался в лимит: 0
Требует внимания человека: мост td_access_telemetry не установлен/не тестирован (нет td_telemetry); AC-69 target inline→current (правка SPEC); эмулятор: PUT /api/users и POST /api/cards дают 404 вместо 405 (D-2, iot_sim); деинсталляция с картами пишет ERROR FK card.server_id (O-1); подпись security-review и pr-review менеджером; повторить ТП-04 после фикса D-1

| Воркер | Статус | Коммит | Тест |
|---|---|---|---|
| W0 | принят | 917c547 | TestAccessInstall 6/6 |
| W1 | принят | e663a0d | /td_access 39/39 |
| W2 | принят | 4194342 | /td_access 83/83 |
| W3 | принят | a7f9485 | /td_access 116/116 |
| W4 | принят | b5cd612 | /td_access 154/154; мост не ставится (нет telemetry) |
| W5 | принят | 44e564b | stand 21/22 (1 skip), D-1 исправлен лидером |

## Решения без заказчика
- DEC-1: td_telemetry/viewer/fire_safety не смержены — мост td_access_telemetry и опциональные интеграции тестируются только при наличии модулей (`'<model>' in env`), иначе тесты skip — tests/
- DEC-2: TestPoll (AC-06…AC-09) перенесён из W1 в W2 — опрос создаёт td.access.event (модель W2) — tests/test_events.py
- DEC-3: data/td_access_server_data.xml и td_access_device_data.xml сделаны в W1 (нужны тестам W1), W4 лишь дополняет
- DEC-4: пожарный код 26368 действует на все двери сервера, даже если door_id определён через устройство — models/td_access_event.py
- DEC-5: в presence проход периметра in/out сбрасывает td_access_zone_door_id; reprocess для done без attendance_id — полная обработка — models/td_access_event.py
- DEC-6: AC-37 без td_fire_safety — _f3d_drill_active мокается в тесте; без модуля возвращает False — models/fire_passage_source.py
- DEC-7: возвращённая карта посетителя хранит visitor_id до R-20 шаг 5 (constraint «пул без человека» не для returned); карта lost уходит в API-08 как заблокированная — models/td_access_card.py
- DEC-8: пользователь BioStar посетителя создаётся до выдачи карты (карте нужен user_id), под write_enabled — models/td_access_visitor.py
- DEC-9: разрешённые зоны посетителя проверяются только на внутренних дверях; поздние события посетителя — attendance_action='late' — models/td_access_visitor.py
- DEC-10: action_td_access_settings target='current' — 'inline' недопустим в Odoo 19 (AC-69 в SPEC требует inline, нужна правка SPEC) — views/res_config_settings_views.xml
- DEC-11: sudo-агрегаты провайдера вынесены в AbstractModel td.access.viewer.data (A-21, DoD «sudo только в _f3d_access_public_presence» буквально) — models/viewer_data.py
- DEC-12: поле document_checked (V-08, Q-06) исключено из запрета AC-64 на поля «document» — tests/test_security.py
- DEC-13: ТК-01 и стенд — на чистой базе (копии timur-o19demo в среде нет); ТК-06 — неверный пароль/недоступный порт вместо остановки контейнера (нет docker) — docs/modules/td_access/TEST_REPORT.md
