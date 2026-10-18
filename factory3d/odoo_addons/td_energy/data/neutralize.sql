-- td_energy: нейтралізація копії проду (каркас §5, CB-10)
-- W1: усі крони модуля (у т.ч. cron_td_energy_advice, _outage_plan, _verification) і джерела `module = 'energy'`
--     (у т.ч. MB-U73-SWB-CTRL) вимикаються нижче; `write_enabled` лишається False.
UPDATE ir_config_parameter SET value = 'False'
 WHERE key IN ('td.energy.read_enabled', 'td.energy.write_enabled', 'td.energy.costing_enabled');
UPDATE ir_cron c SET active = false FROM ir_model_data d
 WHERE d.model = 'ir.cron' AND d.res_id = c.id AND d.module = 'td_energy';
UPDATE td_source SET read_enabled = false, state = 'disabled' WHERE module = 'energy';
