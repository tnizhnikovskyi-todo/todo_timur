# factory3d_energy — карта покриття AC

Джерело AC — `SPEC.md`; результати стенда — `TEST_REPORT.md`; юніт-тести — `odoo_addons/factory3d_energy/tests/`.
Тести стенда (pytest) — `tests/stand/`. Статус UT: `F3D_TEST_INSTALL=factory3d_energy run_tests.sh <db> /factory3d_energy` — 0 failed.

| AC | Тип | Юніт-тест | Стенд / MAN | Статус |
|---|---|---|---|---|
| AC-01 | UT | `test_node.py::TestNodes.test_123_nodes` | — | UT зелений |
| AC-02 | UT | `test_node.py::TestNodes.test_node_constraints` | — | UT зелений |
| AC-03 | UT | `test_node.py::TestNodes.test_tree` | — | UT зелений |
| AC-04 | UT | `test_node.py::TestNodes.test_critical` | — | UT зелений |
| AC-05 | UT | `test_node.py::TestNodes.test_67_meters` | — | UT зелений |
| AC-06 | UT | `test_node.py::TestNodes.test_meter_signal_checks` | — | UT зелений |
| AC-07 | UT | `test_tariff.py::TestTariff.test_price_at` | — | UT зелений |
| AC-08 | UT | `test_tariff.py::TestTariff.test_zone_validation` | — | UT зелений |
| AC-09 | UT | `test_tariff.py::TestTariff.test_periods` | — | UT зелений |
| AC-10 | UT | `test_tariff.py::TestTariff.test_contract_thresholds` | — | UT зелений |
| AC-11 | UT | `test_interval.py::TestInterval.test_no_tariff_event` | — | UT зелений |
| AC-12 | UT | `test_hooks.py::TestHooks.test_install_report` | — | UT зелений |
| AC-13 | TC | `test_hooks.py::(модуль)` | `stand/test_tk.py::test_ac13_demo_report`<br>`stand/test_tk.py::test_tk01_install` | стенд ТК-01: skip (демо-копія) ; UT зелений |
| AC-14 | UT | `test_hooks.py::TestHooks.test_rebind_idempotent` | `stand/test_tb.py::test_tb05_neutralize_and_rebind` | UT зелений |
| AC-15 | UT | `test_counter.py::TestCounterPure.test_continuous_series` | — | UT зелений |
| AC-16 | UT | `test_counter.py::TestCounterPure.test_interpolated_gap` | — | UT зелений |
| AC-17 | UT | `test_counter.py::TestCounterPure.test_resets` | — | UT зелений |
| AC-18 | UT | `test_counter.py::TestCounterPure.test_delta_missing_and_order` | — | UT зелений |
| AC-19 | UT | `test_counter.py::TestCounterMeter.test_series_from_intervals` | — | UT зелений |
| AC-20 | UT | `test_interval.py::TestInterval.test_reset_offset_and_event` | — | UT зелений |
| AC-21 | UT | `test_interval.py::TestInterval.test_build_slot` | — | UT зелений |
| AC-22 | UT | `test_interval.py::TestInterval.test_wait_missing_and_gapfill` | `stand/test_tk.py::test_tk10_meter_unavailable` | стенд ТК-10: skip (90 хв) ; UT зелений |
| AC-23 | UT | `test_interval.py::TestInterval.test_export_and_roles` | — | UT зелений |
| AC-24 | UT | `test_interval.py::TestInterval.test_read_disabled` | — | UT зелений |
| AC-25 | UT | `test_interval.py::TestInterval.test_slot_limit` | — | UT зелений |
| AC-26 | UT | `test_live.py::TestLivePure.test_site_totals` | — | UT зелений |
| AC-27 | UT | `test_live.py::TestLivePure.test_grid_split` | — | UT зелений |
| AC-28 | UT | `test_live.py::TestLiveCron.test_critical_kw` | — | UT зелений |
| AC-29 | UT | `test_live.py::TestLiveCron.test_cron_live_stale_feeders`<br>`test_live.py::TestLiveCron.test_cron_live_writes_totals` | `stand/test_tk.py::test_tk02_readings_profile` | стенд ТК-02: FAIL (артефакт, O-4/O-3) ; UT зелений |
| AC-30 | UT | `test_balance.py::TestBalance.test_balance_sections_and_tolerance`<br>`test_balance.py::TestBalance.test_balance_states` | — | UT зелений |
| AC-31 | UT | `test_balance.py::TestBalance.test_balance_skipped` | — | UT зелений |
| AC-32 | UT | `test_balance.py::TestBalance.test_imbalance_alarm_two_hours` | — | UT зелений |
| AC-33 | UT | `test_events.py::TestEvents.test_threshold_events` | — | UT зелений |
| AC-34 | UT | `test_events.py::TestEvents.test_contract_power_request`<br>`test_mo231.py::TestMo231.test_request_followers` | `stand/test_tk.py::test_tk09_contract_power` | стенд ТК-09: FAIL (3 спроби) ; UT зелений |
| AC-35 | UT | `test_live.py::TestLiveCron.test_asymmetry`<br>`test_live.py::TestLivePure.test_unbalance` | — | UT зелений |
| AC-36 | UT | `test_events.py::TestEvents.test_machine_fault_event`<br>`test_events.py::TestEvents.test_peak_event`<br>`test_events.py::TestEvents.test_pfc_event` | — | UT зелений |
| AC-37 | UT | `test_alloc.py::TestDirect.test_measured_saw` | — | UT зелений |
| AC-38 | UT | `test_alloc.py::TestDirect.test_estimate_mo231` | — | UT зелений |
| AC-39 | UT | `test_alloc.py::TestDirect.test_concurrent_split` | — | UT зелений |
| AC-40 | UT | `test_alloc.py::TestDirect.test_idle_row` | — | UT зелений |
| AC-41 | UT | `test_alloc.py::TestDirect.test_machine_connect_path` | — | UT зелений |
| AC-42 | UT | `test_alloc.py::TestPools.test_dust_kwh_driver` | — | UT зелений |
| AC-43 | UT | `test_alloc.py::TestPools.test_light_time_driver` | — | UT зелений |
| AC-44 | UT | `test_alloc.py::TestPools.test_unallocated_overhead_conservation` | — | UT зелений |
| AC-45 | UT | `test_alloc.py::TestPools.test_locked_untouched` | — | UT зелений |
| AC-46 | UT | `test_costing.py::TestCosting.test_avco_extra_cost` | `stand/test_tk.py::test_tk04_costing_avco` | стенд ТК-04: skip ; UT зелений |
| AC-47 | UT | `test_costing.py::TestCosting.test_standard_no_change` | — | UT зелений |
| AC-48 | UT | `test_costing.py::TestCosting.test_costing_disabled` | — | UT зелений |
| AC-49 | UT | `test_costing.py::TestCosting.test_backorder` | — | UT зелений |
| AC-50 | UT | `test_costing.py::TestCosting.test_analytic_lines` | — | UT зелений |
| AC-51 | UT | `test_costing.py::TestCosting.test_cal_price_twice` | — | UT зелений |
| AC-52 | UT | `test_payload.py::TestPayload.test_viewer_numbers` | — | UT зелений |
| AC-53 | TC | — | `stand/test_tk.py::test_ac53_mo231` | стенд ТК-01/демо: skip (демо-копія) |
| AC-54 | UT | `test_mo231.py::TestMo231.test_master_rights` | `stand/test_tb.py::test_tb02_master_money_fields` | UT зелений |
| AC-55 | UT | `test_ats.py::TestAts.test_src_ok_derived` | — | UT зелений |
| AC-56 | UT | `test_ats.py::TestAts.test_outage_cycle_variant_a` | `stand/test_tk.py::test_tk05_blackout_variant_a` | стенд ТК-05: зелений ; UT зелений |
| AC-57 | UT | `test_ats.py::TestAts.test_fail_start_variant_b` | `stand/test_tk.py::test_tk06_fail_start_variant_b` | стенд ТК-06: skip (td_genset) ; UT зелений |
| AC-58 | UT | `test_ats.py::TestAts.test_no_fail_start_variant_a` | — | UT зелений |
| AC-59 | UT | `test_payload.py::TestPayload.test_island_totals` | `stand/test_tk.py::test_tk05_blackout_variant_a` | стенд ТК-05: зелений ; UT зелений |
| AC-60 | UT | `test_ats.py::TestAts.test_incomer_fallback` | — | UT зелений |
| AC-61 | UT | `test_payload.py::TestPayload.test_infra_cards_totals` | — | UT зелений |
| AC-62 | UT | `test_ats.py::TestAts.test_bridge_mismatch_event` | — | UT зелений |
| AC-63 | UT | `test_payload.py::TestPayload.test_energy_section_keys_and_numbers` | `stand/test_tk.py::test_tk12_viewer` | стенд ТК-12 / MAN: skip (factory3d_viewer) ; UT зелений |
| AC-64 | UT | `test_payload.py::TestPayload.test_cells_states_consumers` | — | UT зелений |
| AC-65 | UT | `test_payload.py::TestPayload.test_cost_hidden_kiosk` | `stand/test_tb.py::test_tb02_master_money_fields`<br>`stand/test_tk.py::test_tk12_viewer` | стенд ТК-12 / MAN: skip (factory3d_viewer) ; UT зелений |
| AC-66 | UT | `test_payload.py::TestPayload.test_workcenter_energy` | — | UT зелений |
| AC-67 | UT | `test_payload.py::TestPayload.test_infra_cards_totals` | — | UT зелений |
| AC-68 | UT | `test_payload.py::TestPayload.test_delta_deep_merge` | — | UT зелений |
| AC-69 | UT | `test_payload.py::TestPayload.test_providers_registered` | — | UT зелений |
| AC-70 | UT | `test_hooks.py::TestHooks.test_addresses` | — | UT зелений |
| AC-71 | UT | `test_hooks.py::TestHooks.test_derived_source` | — | UT зелений |
| AC-72 | UT | `test_hooks.py::TestHooks.test_thresholds_binding` | — | UT зелений |
| AC-73 | TC | `test_hooks.py::(модуль)` | `stand/test_tk.py::test_tk01_install` | стенд ТК-01: зелений ; UT зелений |
| AC-74 | UT | `test_hooks.py::TestHooks.test_uninstall` | — | UT зелений |
| AC-75 | UT | `test_security.py::TestSecurity.test_menus` | — | UT зелений |
| AC-76 | UT + MAN | `test_security.py::TestSecurity.test_views_load` | MAN (ручна перевірка не виконувалась) | UT зелений |
| AC-77 | UT | `test_security.py::TestSecurity.test_group_implications` | — | UT зелений |
| AC-78 | UT | `test_security.py::TestSecurity.test_acl` | — | UT зелений |
| AC-79 | UT | `test_security.py::TestSecurity.test_company_rules` | — | UT зелений |
| AC-80 | UT | `test_security.py::TestSecurity.test_read_disabled_crons` | — | UT зелений |
| AC-81 | UT | `test_security.py::TestSecurity.test_write_forbidden` | `stand/test_tb.py::test_tb03_setpoints_forbidden` | UT зелений |
| AC-82 | UT | `test_security.py::TestSecurity.test_neutralize_sql` | `stand/test_tb.py::test_tb05_neutralize_and_rebind` | UT зелений |
| AC-83 | UT | `test_interval.py::TestInterval.test_kwh_shift` | — | UT зелений |
| AC-84 | UT | `test_interval.py::TestInterval.test_rotate` | — | UT зелений |
| AC-85 | UT | `test_alloc.py::TestPools.test_wizard` | — | UT зелений |
| AC-86 | UT | `test_interval.py::TestInterval.test_day_profile` | — | UT зелений |
| AC-87 | UT | `test_counter.py::TestCounterMeter.test_kwh_api` | — | UT зелений |
| AC-88 | TC | — | `stand/test_tk.py::test_tk03_shift_to_mo` | стенд ТК-03: skip |
| AC-89 | TC | — | `stand/test_tk.py::test_tk05_blackout_variant_a` | стенд ТК-05: зелений |
| AC-90 | TC | — | `stand/test_tk.py::test_tk07_pv_export_noon` | стенд ТК-07: FAIL (емулятор, E-1) |
| AC-91 | TC | — | `stand/test_tk.py::test_tk11_address_reconciliation`<br>`stand/test_tk.py::test_tk11b_nonzero_counters` | стенд ТК-11: зелений |
| AC-92 | TC | — | `stand/test_tk.py::test_ac92_balance_nodes` | стенд ТК-08/DEPLOY_TEST: етап 2 зелений, етап 1 не запускався |
