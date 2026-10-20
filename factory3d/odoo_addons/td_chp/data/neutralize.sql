-- td_chp: нейтралізація копії проду (R-15). Запис у контролер КГУ вимкнено, крони зупинено, черга команд скасована.
UPDATE ir_config_parameter SET value = 'False'
 WHERE key IN ('td.chp.write_enabled', 'td.chp.remote_switching_enabled');
UPDATE td_source SET write_enabled = false WHERE module = 'chp';
UPDATE td_signal SET write_enabled = false WHERE module = 'chp';
UPDATE ir_cron c SET active = false FROM ir_model_data d
 WHERE d.model = 'ir.cron' AND d.res_id = c.id AND d.module = 'td_chp';
UPDATE td_command SET state = 'cancelled' WHERE origin = 'chp' AND state IN ('queued', 'sent');
