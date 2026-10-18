-- td_machine_connect: нейтралізована копія проду.
UPDATE ir_config_parameter SET value = 'False'
 WHERE key IN ('td.machine_connect.read_enabled', 'td.machine_connect.auto_start_enabled',
               'td.machine_connect.write_enabled', 'td.machine_connect.gantry_auto_replenish',
               'td.machine_connect.gantry_auto_feed');
UPDATE ir_config_parameter SET value = 'manual' WHERE key = 'td.machine_connect.cutting_mode';
UPDATE td_cut_map SET export_token_hash = NULL, export_token_expires = NULL;
UPDATE td_machine SET read_enabled = false, auto_start_mode = 'off';
UPDATE ir_cron SET active = false
 WHERE id IN (SELECT res_id FROM ir_model_data WHERE module = 'td_machine_connect' AND model = 'ir.cron');
