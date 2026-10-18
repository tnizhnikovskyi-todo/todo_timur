-- factory3d_machine_connect: нейтралізована копія проду.
UPDATE ir_config_parameter SET value = 'False'
 WHERE key IN ('factory3d.machine_connect.read_enabled', 'factory3d.machine_connect.auto_start_enabled',
               'factory3d.machine_connect.write_enabled', 'factory3d.machine_connect.gantry_auto_replenish',
               'factory3d.machine_connect.gantry_auto_feed');
UPDATE ir_config_parameter SET value = 'manual' WHERE key = 'factory3d.machine_connect.cutting_mode';
UPDATE f3d_cut_map SET export_token_hash = NULL, export_token_expires = NULL;
UPDATE f3d_machine SET read_enabled = false, auto_start_mode = 'off';
UPDATE ir_cron SET active = false
 WHERE id IN (SELECT res_id FROM ir_model_data WHERE module = 'factory3d_machine_connect' AND model = 'ir.cron');
