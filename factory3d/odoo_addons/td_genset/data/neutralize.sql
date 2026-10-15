-- td_genset: нейтралізація копії бази (odoo-bin neutralize, відновлення / дублювання бази з «neutralize», staging).
-- Тестовий сервер ToDo — копія проду: без цього копія почала б опитувати ретранслятор і надсилати команди
-- справжньому генератору — два Odoo керували б одним контролером. Стандарт Odoo 16+: odoo/modules/neutralize.py
-- виконує data/neutralize.sql кожного встановленого модуля.

-- стоп-крани всіх генераторів: без опитування ретранслятора і без команд
UPDATE td_genset
   SET relay_enabled = false,
       commands_allowed = false;

-- токен ретранслятора не переходить у копію (як облікові дані поштових серверів у base/data/neutralize.sql);
-- адреса API лишається — на тесті системний адміністратор вводить лише токен
DELETE FROM ir_config_parameter
 WHERE key = 'td_genset.relay_token';

-- заплановані дії модуля (base і так вимикає всі cron, крім autovacuum; тут — явно, за xml id td_genset)
UPDATE ir_cron
   SET active = false
 WHERE id IN (
       SELECT res_id
         FROM ir_model_data
        WHERE model = 'ir.cron'
          AND module = 'td_genset'
);
