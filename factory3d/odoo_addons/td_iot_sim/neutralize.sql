UPDATE ir_cron SET active = false WHERE id IN (
  SELECT res_id FROM ir_model_data WHERE module = 'factory3d_iot_sim' AND model = 'ir.cron');
UPDATE ir_config_parameter SET value = 'False' WHERE key IN
  ('factory3d.iot_sim.read_enabled', 'factory3d.iot_sim.write_enabled', 'factory3d.iot_sim.level0_enabled');
UPDATE ir_config_parameter SET value = '' WHERE key IN
  ('factory3d.iot_sim.url', 'factory3d.iot_sim.token', 'factory3d.iot_sim.export_token');
UPDATE f3d_sim_panel SET state = 'unconfigured', level0_state = 'forced_off';
