-- td_telemetry: нейтралізація копії проду (CB-10, каркас §5)
UPDATE ir_config_parameter SET value = 'False' WHERE key IN ('td.telemetry.read_enabled', 'td.telemetry.write_enabled');
UPDATE ir_cron c SET active = false FROM ir_model_data d
  WHERE d.model = 'ir.cron' AND d.res_id = c.id AND d.module = 'td_telemetry';
UPDATE td_source SET read_enabled = false, write_enabled = false, state = 'disabled';
UPDATE td_collector SET token_hash = NULL, token_hint = NULL, state = 'never';
UPDATE td_command SET state = 'expired' WHERE state IN ('queued', 'sent');
UPDATE td_signal SET write_enabled = false;
