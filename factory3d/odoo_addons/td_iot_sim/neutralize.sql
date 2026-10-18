UPDATE ir_cron SET active = false WHERE id IN (
  SELECT res_id FROM ir_model_data WHERE module = 'td_iot_sim' AND model = 'ir.cron');
UPDATE ir_config_parameter SET value = 'False' WHERE key IN
  ('td.iot_sim.read_enabled', 'td.iot_sim.write_enabled', 'td.iot_sim.level0_enabled');
UPDATE ir_config_parameter SET value = '' WHERE key IN
  ('td.iot_sim.url', 'td.iot_sim.token', 'td.iot_sim.export_token');
UPDATE td_sim_panel SET state = 'unconfigured', level0_state = 'forced_off';
