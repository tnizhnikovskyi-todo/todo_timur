# AC_COVERAGE — td_genset (мост td_genset_factory3d), AC → тест

Дата: 2026-10-15. Тесты моста: `factory3d/odoo_addons/td_genset_factory3d/tests/` (путь в колонке — относительно). Статусы: **зелёный** — тест есть и проходит (TEST_REPORT.md); ТК — ждёт стенд (§13.3); MAN — ручная приёмка; блокер X-59 / X-24 — внешняя зависимость.

| AC | Тип (SPEC) | Покрытие | Статус |
|---|---|---|---|
| AC-A01 | REG/UT | ТК-G01 + прогон B: `-i` td_genset без traceback; `ir.module.module` 19.0.1.0.0 — проверяет MAN/REG | зелёный (прогон B) / версия — MAN |
| AC-A02 | REG | REG: прогон `/td_genset` (REGRESSION_19.md R1): 176 UT + 36 эмулятор-тестов, 0 failed | зелёный |
| AC-A03 | REG/TC | REG R3 office/d700: ТК-01…14 ТР 1.2 (45) — нужен стенд; in-process эмулятор `td_genset/tests/stand/*` зелёный | ТК — ждёт стенд |
| AC-A04 | REG/MAN | MAN + ТК-G05 | MAN |
| AC-A05 | REG/UT | R4 (копия прода 18→19), ТБ-09 | MAN — ждёт копию прода |
| AC-A06 | TC | ТК-F01 (`relay/tests/test_sim_api.py` 20 OK; контейнер: 200/401/401/404 проверено) | зелёный |
| AC-A07 | TC | ТК-G12 | ТК — ждёт стенд |
| AC-A08 | MAN | MAN (рецензия документов менеджером) | MAN |
| AC-01 | UT | test_hooks.py:TestHook.test_hook_single_generator | зелёный |
| AC-02 | UT | test_hooks.py:TestHook.test_hook_two_generators; test_rules.py:TestLinkConstraints.test_unique_equipment | зелёный |
| AC-03 | UT | test_rules.py:TestLinkConstraints.test_bad_equipment | зелёный |
| AC-04 | UT | test_rules.py:TestFuel.test_fuel_curve | зелёный |
| AC-05 | UT | test_rules.py:TestFuel.test_autonomy | зелёный |
| AC-06 | UT | test_rules.py:TestFuel.test_curve_monotonic | зелёный |
| AC-07 | UT | test_publish.py:TestPublish.test_publish_values | зелёный |
| AC-08 | UT | test_publish.py:TestPublish.test_stop_crane | зелёный |
| AC-09 | UT | test_hooks.py:TestHook.test_hook_prod_env | зелёный |
| AC-10 | UT | test_publish.py:TestPublish.test_idempotent_same_ts | зелёный |
| AC-11 | UT | test_publish.py:TestPublish.test_signals_appendix_a | зелёный |
| AC-12 | UT | test_events.py:TestEvents.test_shutdown_request | зелёный |
| AC-13 | UT | test_events.py:TestEvents.test_repeat_and_reopen | зелёный |
| AC-14 | UT | test_events.py:TestEvents.test_bus_only | зелёный |
| AC-15 | UT | test_events.py:TestEvents.test_default_shutdown | зелёный |
| AC-16 | UT | test_events.py:TestEvents.test_requests_disabled | зелёный |
| AC-17 | UT | test_events.py:TestEvents.test_batch_200 | зелёный |
| AC-18 | UT | test_service.py:TestService.test_planned_request | зелёный |
| AC-19 | UT | test_service.py:TestService.test_overdue_and_not_due | зелёный |
| AC-20 | UT | test_hooks.py:TestHook.test_hook_meter_untouched_and_nextcall | зелёный |
| AC-21 | UT | test_service.py:TestService.test_td_creates_requests | зелёный |
| AC-22 | UT | test_provider.py:TestProvider.test_card_rows | зелёный |
| AC-23 | UT | test_provider.py:TestProvider.test_order_and_bus_models | зелёный |
| AC-24 | UT | test_provider.py:TestProvider.test_no_link_static | зелёный |
| AC-25 | UT | test_payload.py:TestPayload.test_stale_card | зелёный |
| AC-26 | UT | test_provider.py:TestProvider.test_delta_condition | зелёный |
| AC-27 | UT | test_publish.py:TestPublish.test_state_change_chatter | зелёный |
| AC-28 | UT | test_publish.py:TestPublish.test_state_change_chatter | зелёный |
| AC-29 | UT | test_rules.py:TestIsland.test_ats_priority, test_ats_stale_fallback_hgm, test_offline_last_known | зелёный |
| AC-30 | UT | test_provider.py:TestProvider.test_card_rows; test_payload.py:TestPayload.test_full_payload_critical_kw_untouched | зелёный |
| AC-31 | UT | test_rules.py:TestIsland.test_amf_master_no_effect; test_provider.py:TestProvider.test_amf_row_and_rounding | зелёный |
| AC-32 | UT | test_rules.py:TestCritical.test_sum_and_missing; test_payload.py:TestPayload.test_critical_items | зелёный |
| AC-33 | UT | test_access.py:TestAccess.test_acl_matrix, test_params_admin_only; test_views.py:TestViews.test_menus | зелёный |
| AC-34 | UT | test_static.py:TestStatic.test_no_commands_grep | зелёный |
| AC-35 | UT/TC | test_hooks.py:TestHook.test_neutralize_sql, test_uninstall_hook (UT-часть; ТК-G12 — стенд) | зелёный |
| AC-36 | TC | ТК-G01/G02 | ТК — ждёт стенд |
| AC-37 | TC | ТК-G02 | ТК — ждёт стенд |
| AC-38 | TC | ТК-G03 | ТК — ждёт стенд |
| AC-39 | TC | ТК-G06 | ТК — ждёт стенд |
| AC-40 | TC/UT | ТК-G11 + ТК-F07; UT частично: test_publish.py:TestPublish.test_offline_stale, test_events.py:TestEvents.test_comm_lost_once | ТК — ждёт стенд |
| AC-41 | UT (grep-тест) | test_static.py:TestStatic.test_ukrainian_strings, test_no_i18n; **DEFECT** test_ukrainian_view_strings (skip) | зелёный (кроме skip-DEFECT) |
| AC-42 | UT | test_rules.py:TestProfileExport.test_export_json, test_apply_to_td | зелёный |
| AC-43 | UT | test_adapter_contract.py:TestAdapterContract (весь класс) | зелёный |
| AC-44 | UT | test_adapter_contract.py:TestAdapterContract.test_maps_cover_selections | зелёный |
| AC-45 | UT | test_provider.py:TestProvider.test_amf_row_and_rounding | зелёный |
| AC-46 | UT | test_publish.py:TestPublish.test_clock_ahead | зелёный |
| AC-47 | TC | ТК-F01, ТК-F02 | ТК — ждёт стенд |
| AC-48 | TC | ТК-F03, ТК-F05 | ТК — ждёт стенд |
| AC-49 | TC | ТК-F04, ТК-G13 | ТК — ждёт стенд |
| AC-50 | TC | ТК-G01 (UT-аналог: test_hooks.py:TestHook.test_hook_idempotent) | ТК — ждёт стенд |
| AC-51 | TC | ТК-G07 | ТК — ждёт стенд |
| AC-52 | TC | ТК-G08 | ТК — ждёт стенд |
| AC-53 | TC/MAN | ТК-G05 + MAN | ТК — ждёт стенд |
| AC-54 | TC/MAN | ТК-G09 + MAN | ТК — ждёт стенд |
| AC-55 | TC | ТК-G10 (UT-часть: test_events.py:TestEvents.test_close_request_status) | ТК — ждёт стенд |
| AC-56 | TC | ТК-G02 | ТК — ждёт стенд |
| AC-57 | TC | ТК-G03 | ТК — ждёт стенд |
| AC-58 | UT | test_access.py:TestAccess.test_no_commands_runtime; test_views.py:TestViews.test_settings_readonly; test_static.py:TestStatic.test_write_enabled_not_read | зелёный |
| AC-59 | UT | test_access.py:TestAccess.test_nobody | зелёный |
| AC-60 | UT | test_access.py:TestAccess.test_actions_manager_only; test_rules.py:TestProfileExport.test_apply_to_td | зелёный |
| AC-61 | UT | test_events.py:TestEvents.test_template_validation, test_injection_event | зелёный |
| AC-62 | UT | test_hooks.py:TestHook.test_signals_appendix_a_fields; test_publish.py:TestPublish.test_offline_min_changes_period, test_signals_appendix_a | зелёный |
| AC-63 | UT | test_events.py:TestEvents.test_map_data, test_match_severity, test_command_ignored | зелёный |
| AC-64 | UT | test_service.py:TestService.test_service_event | зелёный |
| AC-65 | UT | test_rules.py:TestCodes.test_state_by_breaker_or_power, test_unknown_state | зелёный |
| AC-66 | UT | test_payload.py:TestPayload.test_perf | зелёный |
| AC-67 | MAN | MAN, §13.6 этапы 2–3 (UT-часть: AC-09 test_hook_prod_env) | MAN |
| AC-68 | TC | статика проверена по `services/iot_sim/docker-compose.sim.yml` (профиль demo, env, сети f3d_sim/odoo_default, healthcheck, без `ports`); `compose up` — ТК, ждёт стенд (нет `.env`/`TD_GENSET_PATH`) | ТК — ждёт стенд |
| AC-69 | UT | test_source.py:TestLocalSource (3 теста) | зелёный |
| AC-70 | UT | test_rules.py:TestCritical.test_fallback_param; test_payload.py:TestPayload.test_full_payload_critical_kw_untouched | зелёный |
| AC-71 | UT | test_no_viewer.py:TestWithoutViewer.test_install_publish_events (прогон без viewer); test_static.py:TestStatic.test_manifest_depends | зелёный |
| AC-72 | UT | test_provider.py:TestProvider.test_delta_deep_merge; test_payload.py:TestPayload.test_delta_ac72 | зелёный |
| AC-73 | UT | test_views.py:TestViews.test_settings_menu_and_ats_values | зелёный |
| AC-A09 | REG | REGRESSION_19.md (69 строк) | зелёный (матрица составлена; R0/R2/R3 — см. файл) |
| AC-A10 | REG | `tools/mg_check.sh` репозитория td_genset — не запускался (нет скрипта в репозитории) | нет |
| AC-A11 | REG | REG: две базы (пустая и демо-копия) — прогон B на пустой; демо-копия timur-o19demo не гонялась | частично |
| AC-A12 | REG/TC | REG/ТК-G11, ТП-05 — стенд | ТК — ждёт стенд |
| AC-A13 | REG/TC | REG/ТК-G10 — стенд | ТК — ждёт стенд |
| AC-A14 | REG/MAN | MAN + ТК-G05 (UI `?debug=assets`) | MAN |
| AC-A15 | REG/TC | REG/ТК: JSON-RPC права пульта; UT-аналог `td_genset/tests/test_w3_security.py` | зелёный (UT) / ТК — ждёт стенд |
| AC-A16 | REG/TC | R4 neutralize.sql (ТБ-09, §13.6 этап 2); UT моста: test_hooks.py:TestHook.test_neutralize_sql | MAN — ждёт копию прода |

Сводка: зелёных 60, ТК (ждут стенд) 21, MAN 6, блокер X-59/X-24 0, нет 2.

Блокеры X-59 (CI-01 в iot_sim) и X-24 (схема 1.1 viewer): в текущей ветке параметры CI-01/CI-02 (`amf_master`, `genset_relay` в compose) и схема viewer уже есть, все UT моста зелёные, поэтому ни один AC не помечен блокером; ТК-G, зависящие от iot_sim, отмечены «ждёт стенд» (нет собранного стенда Odoo+iot_sim+relay).
