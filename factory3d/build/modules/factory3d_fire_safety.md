# factory3d_fire_safety
Статус: IN_PROGRESS
Тесты: W0 4/4 (2026-10-15), ТК: ждут стенда
Решений без заказчика: 3 (ниже)
Упирался в лимит: 0
Требует внимания человека: нет

| Воркер | Статус | Коммит | Тест |
|---|---|---|---|
| W0 | принят | 8c85402 | TestW0Skeleton 4/4, test_data_sync 2/2 |
| W1 | в работе | — | — |
| W3 | в работе | — | — |
| W2 | — | — | — |
| W4 | — | — | — |
| W5 | — | — | — |
| W6 | — | — | — |

## Решения без заказчика
- DEC-1: W0 не может поставить data-файлы и access.csv для моделей, которых ещё нет. W0 генерирует все data-файлы,
  но в `data` манифеста и в access.csv — только то, что ставится без моделей; остальное лидер включает по мере
  приёмки W1/W3/W2/W4 (порядок списка — как SPEC §1). — `__manifest__.py`
- DEC-2 (ENV): pytest `tests/test_data_sync.py` (AC-71) запускается только с Odoo в PYTHONPATH
  (`PYTHONPATH=/home/user/odoo19 odoo19-venv/bin/python -m pytest …`): пакет tests импортирует odoo; как в factory3d_base. — `tests/test_data_sync.py`
- DEC-3: `f3d_fire_norm.csv` грузится CSV без noupdate (SPEC §0 помечает noupdate=1; CSV его не поддерживает) — оставлено как в
  манифесте SPEC §1. Для 7 авторских норм ref/note из Додатка D, формулировка примечаний — W0. — `data/f3d_fire_norm.csv`
