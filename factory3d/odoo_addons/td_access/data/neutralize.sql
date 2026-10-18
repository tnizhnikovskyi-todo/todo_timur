-- factory3d_access: нейтралізована копія проду (FR-16).
UPDATE ir_cron SET active = false
 WHERE id IN (SELECT res_id FROM ir_model_data WHERE module = 'factory3d_access' AND model = 'ir.cron');
UPDATE ir_config_parameter SET value = 'False'
 WHERE key IN ('factory3d.access.read_enabled', 'factory3d.access.write_enabled');
DELETE FROM ir_config_parameter WHERE key = 'factory3d.access.biostar_password';
UPDATE f3d_access_server SET session_id = NULL, state = 'offline', next_try_at = NULL, error_count = 0;
UPDATE f3d_access_card SET sync_state = 'local' WHERE sync_state = 'pending';
UPDATE f3d_access_visitor SET sync_state = 'local' WHERE sync_state = 'pending';
