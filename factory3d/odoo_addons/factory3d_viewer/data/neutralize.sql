-- factory3d_viewer: прод-режим копії бази (SPEC §5.1, §13.3, ТК-12). Odoo виконує файл при `odoo-bin neutralize`.
-- Параметри factory3d.viewer.demo_enabled / kiosk_token створює post_init, тому тут upsert, а не UPDATE.
INSERT INTO ir_config_parameter (key, value, create_date, write_date)
VALUES ('factory3d.viewer.demo_enabled', 'False', now() at time zone 'UTC', now() at time zone 'UTC'),
       ('factory3d.viewer.kiosk_enabled', 'False', now() at time zone 'UTC', now() at time zone 'UTC'),
       ('factory3d.viewer.bus_enabled', 'False', now() at time zone 'UTC', now() at time zone 'UTC')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, write_date = EXCLUDED.write_date;

-- новий випадковий токен кіоска (32 hex, як secrets.token_hex(16)); старі URL кіоска перестають працювати
INSERT INTO ir_config_parameter (key, value, create_date, write_date)
VALUES ('factory3d.viewer.kiosk_token', replace(gen_random_uuid()::text, '-', ''),
        now() at time zone 'UTC', now() at time zone 'UTC')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, write_date = EXCLUDED.write_date;

-- крони модуля (знімок, ротація, сигнали, демо) вимкнути
UPDATE ir_cron
   SET active = false
 WHERE id IN (SELECT res_id FROM ir_model_data
               WHERE module = 'factory3d_viewer' AND model = 'ir.cron');
