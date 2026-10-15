```sql
-- factory3d_telemetry: нейтралізація копії проду (CB-10, каркас §5)
UPDATE ir_config_parameter SET value = 'False' WHERE key IN ('factory3d.telemetry.read_enabled', 'factory3d.telemetry.write_enabled');
UPDATE ir_cron c SET active = false FROM ir_model_data d
  WHERE d.model = 'ir.cron' AND d.res_id = c.id AND d.module = 'factory3d_telemetry';
UPDATE f3d_source SET read_enabled = false, write_enabled = false, state = 'disabled';
UPDATE f3d_collector SET token_hash = NULL, token_hint = NULL, state = 'never';
UPDATE f3d_command SET state = 'expired' WHERE state IN ('queued', 'sent');
UPDATE f3d_signal SET write_enabled = false;
```
