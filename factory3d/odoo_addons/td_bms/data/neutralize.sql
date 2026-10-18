-- td_bms: нейтралізація копії проду (CB-10, каркас §5)
UPDATE ir_config_parameter SET value = 'False' WHERE key IN ('td.bms.read_enabled', 'td.bms.write_enabled');
UPDATE ir_cron c SET active = false FROM ir_model_data d
  WHERE d.model = 'ir.cron' AND d.res_id = c.id AND d.module = 'td_bms';
UPDATE td_source SET read_enabled = false, write_enabled = false, state = 'disabled' WHERE module = 'bms';
UPDATE td_signal SET write_enabled = false WHERE module = 'bms';
