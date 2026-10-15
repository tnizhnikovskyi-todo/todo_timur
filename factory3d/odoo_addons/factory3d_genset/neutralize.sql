-- factory3d_genset: нейтралізована копія проду — тестове середовище (CB-10, CR-10).
UPDATE ir_cron SET active = false WHERE id IN (
  SELECT res_id FROM ir_model_data WHERE module = 'factory3d_genset' AND model = 'ir.cron');
UPDATE ir_config_parameter SET value = 'False' WHERE key IN ('factory3d.genset.read_enabled', 'factory3d.genset.requests_enabled');
-- W2: після появи моделі f3d.genset.link додати:
-- UPDATE f3d_genset_link SET last_publish_ts = NULL, last_publish_error = NULL, last_event_ts = NULL, last_event_id = 0;
