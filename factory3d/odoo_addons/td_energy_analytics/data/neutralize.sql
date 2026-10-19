-- td_energy_analytics (W4_SPEC 5.5): вимкнути 4 крони модуля на копії проду.
UPDATE ir_cron c SET active = false FROM ir_model_data d
 WHERE d.model = 'ir.cron' AND d.res_id = c.id AND d.module = 'td_energy_analytics';
