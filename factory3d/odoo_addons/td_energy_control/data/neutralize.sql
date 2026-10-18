-- td_energy_control: нейтралізація копії проду (SPEC 5.7). Прапори запису й автоматики вимикаються, крони й черга команд — теж.
UPDATE ir_config_parameter SET value = 'False'
 WHERE key IN ('td.energy_control.write_enabled', 'td.energy_control.automation_enabled',
               'td.energy_control.remote_switching_enabled');
UPDATE td_source SET write_enabled = false, read_enabled = false, state = 'disabled' WHERE module = 'energy_control';
UPDATE td_signal SET write_enabled = false WHERE module = 'energy_control';
UPDATE ir_cron c SET active = false FROM ir_model_data d
 WHERE d.model = 'ir.cron' AND d.res_id = c.id AND d.module = 'td_energy_control';
UPDATE td_command SET state = 'cancelled' WHERE origin = 'energy' AND state IN ('queued', 'sent');
