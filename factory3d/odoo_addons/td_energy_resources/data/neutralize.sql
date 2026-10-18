-- td_energy_resources: нейтралізація копії проду (SPEC 5.6; каркас §5)
-- Крони модуля (res_build, res_rotate, opportunity, opportunity_links) і джерела газу й повітря вимикаються;
-- глобальні стоп-крани td.energy.* вимикає neutralize td_energy. `write_enabled` W3 не змінює (у пристрої не пише).
UPDATE ir_cron c SET active = false FROM ir_model_data d
 WHERE d.model = 'ir.cron' AND d.res_id = c.id AND d.module = 'td_energy_resources';
UPDATE td_source SET read_enabled = false, state = 'disabled' WHERE code IN ('MB-U74-GAS-MAIN', 'MB-U75-AIR-MAIN');
