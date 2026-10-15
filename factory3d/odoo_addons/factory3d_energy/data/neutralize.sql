-- factory3d_energy: нейтралізація копії проду (каркас §5, CB-10)
UPDATE ir_config_parameter SET value = 'False'
 WHERE key IN ('factory3d.energy.read_enabled', 'factory3d.energy.write_enabled', 'factory3d.energy.costing_enabled');
UPDATE ir_cron c SET active = false FROM ir_model_data d
 WHERE d.model = 'ir.cron' AND d.res_id = c.id AND d.module = 'factory3d_energy';
UPDATE f3d_source SET read_enabled = false, state = 'disabled' WHERE module = 'energy';
