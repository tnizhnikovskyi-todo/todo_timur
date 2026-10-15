# factory3d_fire_safety
Статус: IN_PROGRESS
Тесты: /factory3d_fire_safety 50/50, 1 skip до W2 (2026-10-15), ТК: ждут стенда
Решений без заказчика: 6 (ниже)
Упирался в лимит: 0
Требует внимания человека: нет

| Воркер | Статус | Коммит | Тест |
|---|---|---|---|
| W0 | принят | 8c85402 | TestW0Skeleton 4/4, test_data_sync 2/2 |
| W1 | принят | 48d3d27 (+f2c4b48 слияние) | модуль 50/50 вместе с W3 |
| W3 | принят | b652677 (+f717785 слияние) | модуль 50/50 |
| W2 | в работе | — | — |
| W4 | — | — | — |
| W5 | — | — | — |
| W6 | — | — | — |

## Решения без заказчика
- DEC-1: W0 не может поставить data-файлы и access.csv для моделей, которых ещё нет. W0 генерирует все data-файлы,
  но в `data` манифеста и в access.csv — только то, что ставится без моделей; остальное лидер включает по мере
  приёмки W1/W3/W2/W4 (порядок списка — как SPEC §1). — `__manifest__.py`
- DEC-2 (ENV): pytest `tests/test_data_sync.py` (AC-71) запускается только с Odoo в PYTHONPATH
  (пакет tests импортирует odoo); фактически гоняется `python3 -m unittest discover -s tests -t tests -p test_data_sync.py`, 2/2 OK. — `tests/test_data_sync.py`
- DEC-3: `f3d_fire_norm.csv` грузится CSV без noupdate (SPEC §0 помечает noupdate=1; CSV его не поддерживает) — оставлено как в
  манифесте SPEC §1. Для 7 авторских норм ref/note из Додатка D, формулировка примечаний — W0. — `data/f3d_fire_norm.csv`
- DEC-4: SPEC §1 называет CSV `f3d_fire_norm.csv` и т. п., но Odoo берёт модель из имени CSV — переименованы в
  `f3d.fire.<model>.csv` (norm, zone, smoke.zone, device, exit); манифест и gen_data.py поправлены. — `data/`
- DEC-5: регэксп ключа нормы `^[A-Za-z0-9_]+$` вместо `[a-z0-9_]`: в данных макета есть `evac_distance_prod_B`. — `models/f3d_fire_norm.py`
- DEC-6: скелет `f3d.fire.drill` (name, zone_id, state) до W4 — на него ссылается журнал событий W1. — `models/f3d_fire_drill.py`
