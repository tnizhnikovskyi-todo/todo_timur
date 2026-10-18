-- factory3d_yard: нейтралізація копії проду (каркас §5, FR-25)
UPDATE ir_config_parameter SET value = 'False' WHERE key IN ('factory3d.yard.write_enabled', 'factory3d.yard.read_enabled');
UPDATE ir_cron c SET active = false FROM ir_model_data d
  WHERE d.model = 'ir.cron' AND d.res_id = c.id AND d.module = 'factory3d_yard';
UPDATE f3d_yard_gate SET mode = 'manual', hold_until = NULL, open_cmd_id = NULL;
UPDATE f3d_source SET read_enabled = false, write_enabled = false WHERE module = 'yard';
