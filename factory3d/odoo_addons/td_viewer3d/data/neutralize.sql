-- td_viewer3d: прод-режим копії бази (SPEC §5.1, §13.3, ТК-12). Odoo виконує файл при `odoo-bin neutralize`.
-- Параметри td.viewer.demo_enabled / kiosk_token створює post_init, тому тут upsert, а не UPDATE.
INSERT INTO ir_config_parameter (key, value, create_date, write_date)
VALUES ('td.viewer.demo_enabled', 'False', now() at time zone 'UTC', now() at time zone 'UTC'),
       ('td.viewer.kiosk_enabled', 'False', now() at time zone 'UTC', now() at time zone 'UTC'),
       ('td.viewer.bus_enabled', 'False', now() at time zone 'UTC', now() at time zone 'UTC')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, write_date = EXCLUDED.write_date;

-- новий випадковий токен кіоска (32 hex, як secrets.token_hex(16)); старі URL кіоска перестають працювати
INSERT INTO ir_config_parameter (key, value, create_date, write_date)
VALUES ('td.viewer.kiosk_token', replace(gen_random_uuid()::text, '-', ''),
        now() at time zone 'UTC', now() at time zone 'UTC')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, write_date = EXCLUDED.write_date;

-- крони модуля (знімок, ротація, сигнали, демо) вимкнути
UPDATE ir_cron
   SET active = false
 WHERE id IN (SELECT res_id FROM ir_model_data
               WHERE module = 'td_viewer3d' AND model = 'ir.cron');
