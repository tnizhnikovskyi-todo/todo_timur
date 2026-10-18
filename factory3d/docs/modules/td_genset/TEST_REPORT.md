# TEST_REPORT — td_genset (W5), 2026-10-15

## Прогоны (Odoo 19.0 Community, `tools/odoo/run_tests.sh`, базы из `f3d_template`, без демо)

| # | Команда | Итог |
|---|---|---|
| A | `F3D_TEST_INSTALL=td_genset_factory3d run_tests.sh f3d_tdg_w5a /td_genset_factory3d` (без viewer, SPEC §13.0 прогон 2) | 0 failed, 0 error of 90 tests (классы с viewer — SkipTest) |
| B | `F3D_TEST_INSTALL=td_genset_factory3d,td_viewer3d run_tests.sh f3d_tdg_w5b /td_genset_factory3d,/td_genset` | 0 failed, 0 error of 276 tests: мост 100 + td_genset 176; 1 skip (DEFECT, ниже); 0 `DeprecationWarning` от td_genset |
| — | `python3 -m unittest discover -s tests` в `td_genset/relay` (ТК-F01…F07, in-process) | 20 тестов OK |

Новые тесты моста (было 78 UT, стало 100): `test_access.py` (6: AC-33, AC-58, AC-59, AC-60, ТБ-01, ТБ-02), `test_static.py` (6 + 1 skip: AC-34, AC-41, AC-58, AC-71, ТБ-03, ТБ-07, ТБ-10), `test_payload.py` (5: AC-25, AC-30, AC-32, AC-66, AC-70, AC-72), `test_source.py` (3: AC-69), `test_hooks.py::test_signals_appendix_a_fields` (AC-62).

## Дефекты

| # | Где | Что | Тест |
|---|---|---|---|
| D-1 | `td_genset_factory3d/views/td_genset_link_views.xml:23` | `string="td_genset"` без кириллицы — нарушение AC-41 (FR-16), мелкое | `test_static.py:TestStatic.test_ukrainian_view_strings` (`@unittest.skip("DEFECT: …")`) |

## ТК / ТБ / ТП

| Группа | Статус |
|---|---|
| ТК-F01…F07 | зелёно: 20 тестов `relay/tests/test_sim_api.py`; дополнительно на контейнере `python:3.12-slim` с кодом relay: ТК-F01 (200 с токеном, `profile=D700`, `fuel_l=500.2`, `hours=1213.0`, `mode=auto`, `state_code=1`; 401 без токена и с хибным; 404 при пустом `RELAY_SIM_TOKEN`), ТК-F02 (422 на `load 600`, `fuel 700`, `time factor 100`, `fault nope`) |
| ТК-G01…G13, ТК-01…14 td_genset на живом relay | ждут стенд: образ `genset_relay` не собрался (`pip install` в контейнере без сети), нет `.env`/iot_sim/Odoo-стенда; демон Docker в среде не был запущен — поднят вручную `dockerd` |
| ТБ-01, ТБ-02 | UT: `test_access.py` (матрица ACL 3 модели × 4 пользователя; приватные методы через `odoo.service.model.call_kw`); XML-RPC/HttpCase — на стенде |
| ТБ-03, ТБ-07, ТБ-10 | UT: `test_static.py` (команды, `cr.execute`, `write_enabled`), `test_access.py::test_no_commands_runtime`; журнал relay за прогон ТК-G — ждёт стенд |
| ТБ-04, ТБ-05, ТБ-08, ТБ-09 | ждут стенд / копию прода (ТБ-05 частично: 401/401/404 проверено) |
| ТБ-06 | UT: `test_events.py` (AC-61 шаблоны, инъекции) — зелёно |
| ТП-01, ТП-02 | UT: `test_payload.py::test_perf` — приращение ≤ 8 SQL, медиана collect ≤ 50 мс, `_publish_one` ≤ 40 SQL и ≤ 0,5 с — зелёно |
| ТП-03, ТП-05 (UT-часть) | `test_events.py::test_batch_200`, `test_publish.py::test_adapter_not_verified_and_isolation` — зелёно |
| ТП-04, ТП-05 (стенд), ТП-06 | ждут стенд; ТП-06: 176 UT td_genset за 89 с на 19.0, базовая линия 18.0 не измерялась |

## ruff (`ruff check --line-length 120 factory3d/odoo_addons/td_genset_factory3d`)

103 замечания (только отчёт, код не правился): UP031 ×40 (printf-форматирование), F401 ×34 (неиспользуемые импорты, в основном `__init__.py`), SIM115 ×9, I001 ×9, RUF046 ×3, по одному B023, RUF012, F811, FURB167, SIM905, RUF100, B018, RUF007. Из них 17 авто-исправимы (`--fix`). Приблизительно 14 замечаний — в моих новых тестах (UP031, SIM115 в `test_static.py`).

## Стенд (§13.3)

Демон Docker в среде не работал; запущен `dockerd` вручную. `docker build` relay упал на `pip install tzdata` (нет сети в сборочном контейнере; первый pull образа отдал 429, со второй попытки прошёл). Relay запущен из образа `python:3.12-slim` с примонтированным кодом — этого достаточно для ТК-F (relay на stdlib). Odoo + iot_sim + collector + ТК-G не поднимались (за пределами лимита времени).
