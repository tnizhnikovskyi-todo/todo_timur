-- td_access: нейтралізована копія проду (FR-16).
UPDATE ir_cron SET active = false
 WHERE id IN (SELECT res_id FROM ir_model_data WHERE module = 'td_access' AND model = 'ir.cron');
UPDATE ir_config_parameter SET value = 'False'
 WHERE key IN ('td.access.read_enabled', 'td.access.write_enabled');
DELETE FROM ir_config_parameter WHERE key = 'td.access.biostar_password';
UPDATE td_access_server SET session_id = NULL, state = 'offline', next_try_at = NULL, error_count = 0;
UPDATE td_access_card SET sync_state = 'local' WHERE sync_state = 'pending';
UPDATE td_access_visitor SET sync_state = 'local' WHERE sync_state = 'pending';
