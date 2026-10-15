# REGRESSION_19 — td_genset 18.0 → 19.0 (ТР 1.2 AC-01…AC-69)

Дата: 2026-10-15. Прогон: `F3D_TEST_INSTALL=factory3d_genset,factory3d_viewer run_tests.sh f3d_tdg_w5b /factory3d_genset,/td_genset` (R1: база из `f3d_template`, `--without-demo`, Odoo 19.0 Community). Подробности — TEST_REPORT.md.

Легенда колонок: **R0** — базовая линия 18.0: стенд 18.0 в среде недоступен, берётся запись CHANGELOG `18.0.1.0.0` (176 UT и 45 ТК зелёные) — не перепрогонялась; **R1** — пустая база 19.0, `/td_genset`; **R2** — копия демо-базы timur-o19demo: не гонялась (нет базы); **R3 office / d700** — стенд с `fake_relay`: docker-стенд не поднят (rate limit реестра, см. TEST_REPORT), вместо него in-process эмулятор `tests/stand/*` (входит в прогон `/td_genset`) — результат указан как «эмулятор»; ТК на живом `fake_relay` — «ждёт стенд». Колонка MG — тесты, изменённые при переносе (MIGRATION_19.md).

| ТР 1.2 AC | тест / ТК ТР 1.2 | R0 | R1 | R2 | R3 office | R3 d700 | MG-xx | комментарий |
|---|---|---|---|---|---|---|---|---|
| AC-01 | `test_w1_relay_client.test_ac01_settings_from_config_parameter` | зелёно* | зелёно | не гонялся | ждёт стенд | ждёт стенд | — |  |
| AC-02 | `test_w1_link_health.test_ac02_check_relay_button` | зелёно* | зелёно | не гонялся | ждёт стенд | ждёт стенд | — |  |
| AC-03 | `test_w1_pull_readings.test_ac03_pages_cursor_no_duplicates` | зелёно* | зелёно | не гонялся | ждёт стенд | ждёт стенд | — |  |
| AC-04 | `test_w1_pull_readings.test_ac04_page_is_one_transaction` | зелёно* | зелёно | не гонялся | ждёт стенд | ждёт стенд | — |  |
| AC-05 | `test_w1_semantics.test_ac05_current_state_on_card`, `test_w3_ui_http.test_ac05_ac06_current_data_html` | зелёно* | зелёно | не гонялся | ждёт стенд | ждёт стенд | MG-09 | изменён при переносе |
| AC-06 | `test_w1_semantics.test_ac06_null_and_missing_keys`, `test_w1_semantics.test_ac06_unknown_keys_to_values_extra` | зелёно* | зелёно | не гонялся | ждёт стенд | ждёт стенд | — |  |
| AC-07 | `test_w1_semantics.test_ac07_mains_and_generator_semantics`, `test_w1_semantics.test_ac07_running_rule_and_unknown_mode` | зелёно* | зелёно | не гонялся | ждёт стенд | ждёт стенд | — |  |
| AC-08 | `test_w1_journal_slots.test_ac08_journal_96_records_per_day`, `test_w1_journal_slots.test_ac08_journal_dst_days`, `test_w1_journal_slots.test_ac08_slot_start_kyiv`, `test_w1_journal_slots.test_ac08_pull_marks_journal` | зелёно* | зелёно | не гонялся | ждёт стенд | ждёт стенд | — |  |
| AC-09 | `test_w1_link_health.test_ac09_link_lost_and_restored`, `test_w1_link_health.test_ac09_catchup_is_not_link_loss`, `test_w1_link_health.test_ac09_relay_unavailable_link_goes_offline` | зелёно* | зелёно | не гонялся | ждёт стенд | ждёт стенд | — |  |
| AC-10 | `test_w1_link_health.test_ac10_relay_unavailable_and_auth`, `test_w1_link_health.test_ac10_readings_5xx_counts_even_if_status_ok` | зелёно* | зелёно | не гонялся | ждёт стенд | ждёт стенд | — |  |
| AC-11 | `test_w1_link_health.test_ac11_relay_health` | зелёно* | зелёно | не гонялся | ждёт стенд | ждёт стенд | — |  |
| AC-12 | `test_w2_commands.test_ac12_button_command_confirmed_by_snapshot`, `test_w2_commands.test_ac12_confirmation_needs_snapshot_after_done` | зелёно* | зелёно | не гонялся | ждёт стенд | ждёт стенд | — |  |
| AC-13 | `test_w2_commands.test_ac13_not_needed_when_mode_already_target` | зелёно* | зелёно | не гонялся | ждёт стенд | ждёт стенд | — |  |
| AC-14 | `test_w2_commands.test_ac14_confirmation_retries_then_alarm` | зелёно* | зелёно | не гонялся | ждёт стенд | ждёт стенд | — |  |
| AC-15 | `test_w2_commands.test_ac15_transport_retry_on_409`, `test_w2_commands.test_ac15_transport_failure_whole_window_alarm` | зелёно* | зелёно | не гонялся | ждёт стенд | ждёт стенд | — |  |
| AC-16 | `test_w2_commands.test_ac16_commands_disabled_on_relay`, `test_w2_commands.test_ac16_auth_error_and_bad_request` | зелёно* | зелёно | не гонялся | ждёт стенд | ждёт стенд | — |  |
| AC-17 | `test_w2_commands.test_ac17_relay_restarted_retry_new_id`, `test_w2_commands.test_ac17_sent_without_final_status_is_timeout`, `test_w2_commands.test_ac17_sent_relay_unavailable_no_repost` | зелёно* | зелёно | не гонялся | ждёт стенд | ждёт стенд | — |  |
| AC-18 | `test_w2_commands.test_ac18_link_lost_before_confirmation`, `test_w2_commands.test_ac18_link_restored_not_confirmed_retries_new_window`, `test_w2_commands.test_ac18_awaiting_without_snapshots_does_not_resend`, `test_w2_commands.test_ac18_after_link_restore_next_retry_waits_interval` | зелёно* | зелёно | не гонялся | ждёт стенд | ждёт стенд | — |  |
| AC-19 | `test_w2_commands.test_ac19_manual_stop_batch`, `test_w2_commands.test_ac19_batch_goal_is_stop_mode` | зелёно* | зелёно | не гонялся | ждёт стенд | ждёт стенд | — |  |
| AC-20 | `test_w2_commands.test_ac20_queue_limit_two_inflight` | зелёно* | зелёно | не гонялся | ждёт стенд | ждёт стенд | — |  |
| AC-21 | `test_w2_commands.test_ac21_breaker_toggle`, `test_w2_commands.test_ac21_breaker_window_starts_with_first_post` | зелёно* | зелёно | не гонялся | ждёт стенд | ждёт стенд | — |  |
| AC-22 | `test_w2_commands.test_ac22_gen_breaker_close_only_when_running` | зелёно* | зелёно | не гонялся | ждёт стенд | ждёт стенд | — |  |
| AC-23 | `test_w2_commands.test_ac23_remote_lock_blocks` | зелёно* | зелёно | не гонялся | ждёт стенд | ждёт стенд | — |  |
| AC-24 | `test_w2_commands.test_ac24_pult_requires_tech_and_link`, `test_w3_security.test_ac24_ac66_relay_client_not_callable_over_rpc`, `test_w3_security.test_ac24_ac56_rpc_by_role`, `test_w3_ui_http.test_ac24_pult_state_by_role_and_link` | зелёно* | зелёно | не гонялся | ждёт стенд | ждёт стенд | MG-09 | изменён при переносе |
| AC-25 | `test_w2_commands.test_ac25_start_cancels_timer`, `test_w2_commands.test_ac25_start_when_running_or_cranking` | зелёно* | зелёно | не гонялся | ждёт стенд | ждёт стенд | — |  |
| AC-26 | `test_w2_commands.test_ac26_crank_failure`, `test_w2_commands.test_ac26_start_confirmed_only_when_engine_runs` | зелёно* | зелёно | не гонялся | ждёт стенд | ждёт стенд | — |  |
| AC-27 | `test_w1_events.test_ac27_external_control_events`, `test_w1_events.test_ac27_external_breaker_in_manual`, `test_w2_commands.test_ac27_external_control_not_reverted` | зелёно* | зелёно | не гонялся | ждёт стенд | ждёт стенд | — |  |
| AC-28 | `test_w2_scheduler.test_ac28_schedule_transitions`, `test_w2_scheduler.test_ac28_window_helpers` | зелёно* | зелёно | не гонялся | ждёт стенд | ждёт стенд | MG-10 | изменён при переносе |
| AC-29 | `test_w2_scheduler.test_ac29_schedule_validation` | зелёно* | зелёно | не гонялся | ждёт стенд | ждёт стенд | MG-10 | изменён при переносе |
| AC-30 | `test_w2_scheduler.test_ac30_exception_days` | зелёно* | зелёно | не гонялся | ждёт стенд | ждёт стенд | MG-10 | изменён при переносе |
| AC-31 | `test_w2_timer_test.test_ac31_timer_start_limits_extend_stop`, `test_w2_timer_test.test_ac31_timer_stop_in_window_keeps_auto`, `test_w3_ui_http.test_ac31_timer_and_test_in_pult_state` | зелёно* | зелёно | не гонялся | ждёт стенд | ждёт стенд | MG-09 | изменён при переносе |
| AC-32 | `test_w2_timer_test.test_ac32_timer_over_window_end`, `test_w2_timer_test.test_ac32_window_start_during_timer` | зелёно* | зелёно | не гонялся | ждёт стенд | ждёт стенд | — |  |
| AC-33 | `test_w2_timer_test.test_ac33_test_idle_returns_by_schedule`, `test_w2_timer_test.test_ac33_test_load_out_of_window`, `test_w2_timer_test.test_ac33_test_pauses_timer`, `test_w2_timer_test.test_ac33_auto_ends_test_early` | зелёно* | зелёно | не гонялся | ждёт стенд | ждёт стенд | — |  |
| AC-34 | `test_w2_scheduler.test_ac34_missed_transition_during_downtime`, `test_w2_scheduler.test_ac34_missed_transition_skipped_after_external_control` | зелёно* | зелёно | не гонялся | ждёт стенд | ждёт стенд | MG-10 | изменён при переносе |
| AC-35 | `test_w2_scheduler.test_ac35_missed_transition_without_link_until_next`, `test_w2_scheduler.test_ac35_missed_transition_window_only` | зелёно* | зелёно | не гонялся | ждёт стенд | ждёт стенд | MG-10 | изменён при переносе |
| AC-36 | `test_w2_timer_test.test_ac36_next_event_text` | зелёно* | зелёно | не гонялся | ждёт стенд | ждёт стенд | — |  |
| AC-37 | `test_w2_scheduler.test_ac37_dst_spring_forward`, `test_w2_scheduler.test_ac37_dst_fall_back` | зелёно* | зелёно | не гонялся | ждёт стенд | ждёт стенд | MG-10 | изменён при переносе |
| AC-38 | `test_w1_events.test_ac38_run_event`, `test_w1_events.test_ac38_run_reason_from_odoo_command` | зелёно* | зелёно | не гонялся | ждёт стенд | ждёт стенд | — |  |
| AC-39 | `test_w1_events.test_ac39_outage_with_pickup`, `test_w1_events.test_ac39_outage_without_run` | зелёно* | зелёно | не гонялся | ждёт стенд | ждёт стенд | — |  |
| AC-40 | `test_w1_events.test_ac40_refuel_and_drain` | зелёно* | зелёно | не гонялся | ждёт стенд | ждёт стенд | — |  |
| AC-41 | `test_w1_events.test_ac41_controller_alarms` | зелёно* | зелёно | не гонялся | ждёт стенд | ждёт стенд | — |  |
| AC-42 | `test_w1_alarms_escalation.test_ac42_escalation_chain_and_quiet_hours`, `test_w1_alarms_escalation.test_ac42_quiet_hours_window`, `test_w1_alarms_escalation.test_ac42_level_without_user_is_skipped`, `test_w1_alarms_escalation.test_ac42_escalation_cron_never_fails` | зелёно* | зелёно | не гонялся | ждёт стенд | ждёт стенд | — |  |
| AC-43 | `test_w1_alarms_escalation.test_ac43_ack_stops_escalation` | зелёно* | зелёно | не гонялся | ждёт стенд | ждёт стенд | — |  |
| AC-44 | `test_w1_alarms_escalation.test_ac44_test_notification` | зелёно* | зелёно | не гонялся | ждёт стенд | ждёт стенд | — |  |
| AC-45 | `test_w1_pull_readings.test_ac45_catchup_without_alarm_avalanche`, `test_w1_pull_readings.test_ac45_first_pull_starts_from_catchup_date` | зелёно* | зелёно | не гонялся | ждёт стенд | ждёт стенд | — |  |
| AC-46 | `test_w1_events.test_ac46_gap_is_not_interpolated` | зелёно* | зелёно | не гонялся | ждёт стенд | ждёт стенд | — |  |
| AC-47 | `test_w4_fuel.test_ac47_fuel_kpi_and_min_stock`, `test_w4_fuel.test_ac47_stock_not_checked_before_canisters` | зелёно* | зелёно | не гонялся | ждёт стенд | ждёт стенд | — |  |
| AC-48 | `test_w4_fuel.test_ac48_fuel_receipt_new_canisters`, `test_w4_fuel.test_ac48_fuel_receipt_fill_existing` | зелёно* | зелёно | не гонялся | ждёт стенд | ждёт стенд | — |  |
| AC-49 | `test_w3_security.test_ac49_fuel_move_only_via_post`, `test_w4_fuel.test_ac49_canister_fix_move_write_off`, `test_w4_fuel.test_ac49_archive_is_write_off` | зелёно* | зелёно | не гонялся | ждёт стенд | ждёт стенд | MG-09 | изменён при переносе |
| AC-50 | `test_w4_fuel.test_ac50_location_with_canisters_not_deleted` | зелёно* | зелёно | не гонялся | ждёт стенд | ждёт стенд | — |  |
| AC-51 | `test_w4_fuel.test_ac51_refuel_from_canisters_and_reconcile`, `test_w4_fuel.test_ac51_refuel_wizard_limits`, `test_w4_fuel.test_ac51_refuel_by_level_difference` | зелёно* | зелёно | не гонялся | ждёт стенд | ждёт стенд | — |  |
| AC-52 | `test_w4_fuel.test_ac52_fuel_consumption` | зелёно* | зелёно | не гонялся | ждёт стенд | ждёт стенд | — |  |
| AC-53 | `test_w4_maintenance.test_ac53_equipment_and_auto_request`, `test_w4_maintenance.test_ac53_maintenance_data_in_install_company`, `test_w4_maintenance.test_ac53_equipment_follows_genset` | зелёно* | зелёно | не гонялся | ждёт стенд | ждёт стенд | — |  |
| AC-54 | `test_w4_maintenance.test_ac54_close_request_new_countdown`, `test_w4_maintenance.test_ac54_next_maintenance_by_months` | зелёно* | зелёно | не гонялся | ждёт стенд | ждёт стенд | — |  |
| AC-55 | `test_w3_security.test_ac55_config_readonly_for_non_tech` | зелёно* | зелёно | не гонялся | ждёт стенд | ждёт стенд | MG-09 | изменён при переносе |
| AC-56 | `test_w3_security.test_ac56_rights_matrix`, `test_w3_security.test_ac56_buttons_hidden_by_group`, `test_w3_security.test_ac56_maintenance_done_only_tech`, `test_w3_security.test_ac56_genset_with_history_not_deleted`, `test_w3_ui_http.test_ac56_form_and_tabs_for_each_role` | зелёно* | зелёно | не гонялся | ждёт стенд | ждёт стенд | MG-09 | изменён при переносе |
| AC-57 | `test_w1_relay_client.test_ac57_token_not_in_logs_and_messages`, `test_w3_security.test_ac57_settings_token_never_returned` | зелёно* | зелёно | не гонялся | ждёт стенд | ждёт стенд | MG-09 | изменён при переносе |
| AC-58 | `test_w1_cleanup.test_ac58_cleanup_raw_readings`, `test_w1_cleanup.test_ac58_cleanup_batches_and_disabled`, `test_w1_cleanup.test_ac58_archive_old_exceptions` | зелёно* | зелёно | не гонялся | ждёт стенд | ждёт стенд | — |  |
| AC-59 | `test_w3_security.test_ac59_export_template_all_values` | зелёно* | зелёно | не гонялся | ждёт стенд | ждёт стенд | MG-09 | изменён при переносе |
| AC-60 | `test_w3_ui_http.test_ac60_empty_states` | зелёно* | зелёно | не гонялся | ждёт стенд | ждёт стенд | MG-09 | изменён при переносе |
| AC-61 | `test_w3_ui_http.test_ac61_mobile_layout` | зелёно* | зелёно | не гонялся | ждёт стенд | ждёт стенд | MG-09 | изменён при переносе |
| AC-62 | `test_w3_ui_http.test_ac62_bus_channel_and_message`, `test_w3_ui_http.test_ac62_live_update_and_polling`, `test_w3_ui_http.test_ac62_pult_survives_rpc_failure` | зелёно* | зелёно | не гонялся | ждёт стенд | ждёт стенд | MG-09 | изменён при переносе |
| AC-63 | `test_w1_alarms_escalation.test_ac63_low_fuel_activity_and_notes` | зелёно* | зелёно | не гонялся | ждёт стенд | ждёт стенд | — |  |
| AC-64 | `test_w1_relay_client.test_ac64_response_codes`, `test_w1_relay_client.test_ac64_readings_page_and_raw` | зелёно* | зелёно | не гонялся | ждёт стенд | ждёт стенд | — |  |
| AC-65 | — | зелёно* | зелёно | не гонялся | эмулятор: `test_w5_stand_harness`… | ждёт стенд | — |  |
| AC-66 | `test_w2_commands.test_ac66_commands_disabled_in_odoo` | зелёно* | зелёно | не гонялся | ждёт стенд | ждёт стенд | — |  |
| AC-67 | `test_w2_commands.test_ac67_stop_without_mains_warning_and_cooling` | зелёно* | зелёно | не гонялся | ждёт стенд | ждёт стенд | — |  |
| AC-68 | `test_w1_pull_readings.test_ac68_ohms_from_raw_image_v111`, `test_w1_pull_readings.test_ac68_ohms_from_keys_v113`, `test_w1_pull_readings.test_ac68_raw_mode_no_keeps_null` | зелёно* | зелёно | не гонялся | ждёт стенд | ждёт стенд | — |  |
| AC-69 | `test_w4_fuel.test_ac69_liters_by_calibration_and_recompute`, `test_w4_fuel.test_ac69_calibration_validation`, `test_w4_fuel.test_ac69_recompute_in_batches`, `test_w4_fuel.test_ac69_liters_from_ohm_contract` | зелёно* | зелёно | не гонялся | ждёт стенд | ждёт стенд | — |  |

Общие изменения тестов (не привязаны к одному AC): `common.py` / `TdGensetCase.setUp` — патч `ir.cron._commit_progress` (MG-29), `group_ids` вместо `groups_id` (MG-09).

Блоки повышенного риска §A.3 (AC-A12…AC-A15): MAN-протокол — ждёт стенд (см. AC_COVERAGE.md).

Критерий «зелено» §13.2.5: п.1 (R1) выполнен; R2, R3 (45/45 office и d700) и MAN-блоки — открыты до появления стенда; 0 «красно».
