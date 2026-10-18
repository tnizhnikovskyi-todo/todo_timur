-- td_energy_mobile: нейтралізація копії проду (SPEC H.6, AC-H21): вимкнути крони cron_td_energy_round_open,
-- cron_td_energy_round_close, cron_td_energy_round_rotate (усі крони модуля). Обходи й події не змінюються.
UPDATE ir_cron c SET active = false FROM ir_model_data d
 WHERE d.model = 'ir.cron' AND d.res_id = c.id AND d.module = 'td_energy_mobile';
