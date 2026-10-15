-- factory3d_bms: нейтралізація копії проду (CB-10, каркас §5)
UPDATE ir_config_parameter SET value = 'False' WHERE key IN ('factory3d.bms.read_enabled', 'factory3d.bms.write_enabled');
UPDATE ir_cron c SET active = false FROM ir_model_data d
  WHERE d.model = 'ir.cron' AND d.res_id = c.id AND d.module = 'factory3d_bms';
UPDATE f3d_source SET read_enabled = false, write_enabled = false, state = 'disabled' WHERE module = 'bms';
UPDATE f3d_signal SET write_enabled = false WHERE module = 'bms';
