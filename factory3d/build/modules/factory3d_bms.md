# factory3d_bms
Статус: IN_PROGRESS
Тесты: Odoo 68/68 (2026-10-15), плагин helvarnet 28/28; ТК: ждут W7
Решений без заказчика: 3 (ниже)
Упирался в лимит: 0
Требует внимания человека: нет

| Воркер | Статус | Коммит | Тест |
|---|---|---|---|
| W0 | принят | 9f850a6 | TestBmsInstall 4/4 |
| W1 | принят | 8c16524 | /factory3d_bms 33/33 (AC-01…12) |
| W2 | принят | 53e22bf | /factory3d_bms 22/22; AC-17 → W4 |
| W6 | принят | e46cfaf | pytest 28/28 (AC-64…78) |
| W3 | принят | 56d12b2 | /factory3d_bms 68/68, pytest data_sync 6/6; демо-копия (AC-49/50/52) не прогонялась |
| W4 | в работе | | |
| W5 | ждёт | | |
| W7 | ждёт | | |

## Решения без заказчика
- DEC-1 (ENV): тесты с `F3D_TEST_INSTALL=factory3d_base,factory3d_telemetry,factory3d_bms` (как yard DEC-2);
  манифест W0 перечисляет только существующие файлы, воркеры добавляют свои через лидера. — `__manifest__.py`
- DEC-2: W1 ‖ W2 ‖ W6 в worktree; воркерам разрешено дописывать свои строки в общие файлы (manifest, __init__,
  access.csv, menus action), конфликты при слиянии разрешает лидер. Record rule heat.balance (§4.3) — W2 с моделью.
- DEC-3: метрики helvarnet (§8.6) объявлены в `collector/core/metrics.py` с меткой `source` (+cmd/code), плагин
  обращается через getattr; пакет добавлен в `collector/requirements-extra.txt`. Слияние W1+W2: `ruff format` модуля.
- DEC-4: uninstall_hook снимает xml-id сигналов модуля и деактивирует/отвязывает их вместо удаления (история и
  заявки сохраняются, AC-55). Коллектор unit: 173 passed + известный env-fail `test_load_real_plugins_exactly_four`. — `hooks.py`
