-- td_genset_factory3d: нейтралізована копія проду — тестове середовище (CB-10, CR-10).
UPDATE ir_cron SET active = false WHERE id IN (
  SELECT res_id FROM ir_model_data WHERE module = 'td_genset_factory3d' AND model = 'ir.cron');
UPDATE ir_config_parameter SET value = 'False' WHERE key IN ('td.genset.read_enabled', 'td.genset.requests_enabled');
UPDATE td_genset3d_link SET last_publish_ts = NULL, last_publish_error = NULL, last_event_ts = NULL, last_event_id = 0;
