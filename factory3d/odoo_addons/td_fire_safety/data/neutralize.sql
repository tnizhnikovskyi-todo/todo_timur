-- factory3d_fire_safety: нейтралізація копії проду (CB-10, FR-19, FR-24)
UPDATE ir_config_parameter SET value = 'False' WHERE key = 'factory3d.fire_safety.read_enabled';
DELETE FROM ir_config_parameter WHERE key = 'factory3d.fire_safety.write_enabled';   -- не існує; захист від ручного створення
UPDATE ir_cron c SET active = false FROM ir_model_data d
  WHERE d.model = 'ir.cron' AND d.res_id = c.id AND d.module = 'factory3d_fire_safety';
UPDATE f3d_source SET read_enabled = false, write_enabled = false WHERE f3d_fire_readonly IS TRUE;
UPDATE f3d_fire_drill SET sim_run_ref = NULL;
UPDATE f3d_fire_drill_person SET employee_id = NULL;
DELETE FROM mail_activity a USING ir_model_data d
  WHERE d.module = 'factory3d_fire_safety' AND d.name = 'mail_act_fire_alarm' AND d.model = 'mail.activity.type'
    AND a.activity_type_id = d.res_id;
UPDATE f3d_fire_panel SET comm = 'off';
