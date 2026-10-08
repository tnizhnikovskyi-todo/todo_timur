# Part of td_genset (ToDo). Власник файлу: W3.
"""HttpCase — форма генератора і пульт у браузері, ``get_pult_state``, «Поточні дані», порожні стани,
bus-канал, живе оновлення і мобільна верстка (AC-05, AC-06, AC-24, AC-60, AC-61, AC-62).

Браузерні перевірки (Chrome HttpCase): будь-яка помилка JS/RPC у консолі валить тест.
"""
import json
from datetime import timedelta

from lxml import etree

from odoo import fields
from odoo.tests import HttpCase, tagged
from odoo.tools.safe_eval import safe_eval

from .common import TdGensetCase, snapshot

# Синтаксис до 17.0, якого не має бути в поданнях (рядки складені, щоб grep по модулю лишався порожнім)
LEGACY_VIEW_SYNTAX = (' att' + 'rs=', ' sta' + 'tes=', '<tr' + 'ee', 't-r' + 'aw')

# Інтервали групування дат, які приймає web-клієнт Odoo 18 (web/static/src/search/utils/dates.js, INTERVAL_OPTIONS;
# дата без інтервалу — month); інші (``hour``) — «Invalid groupBy description», графік не відкривається (D-01)
WEB_DATE_INTERVALS = ('year', 'quarter', 'month', 'week', 'day')

JS_WAIT = """
const __until = Date.now() + 25000;
const waitFor = async (fn, what) => {
    while (Date.now() < __until) {
        const result = fn();
        if (result) { return result; }
        await new Promise((resolve) => setTimeout(resolve, 100));
    }
    throw new Error("timeout: " + what);
};
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
"""


@tagged('post_install', '-at_install')
class TestW3UiHttp(TdGensetCase, HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        for user in (cls.user_s, cls.user_a, cls.user_t, cls.user_x):
            user.password = user.login
        cls.reading_seq = 9000

    def setUp(self):
        super().setUp()
        self.relay.stop()  # HttpCase і Chrome ходять через requests — мок ретранслятора тут не потрібен

    # ------------------------------------------------------------------ помічники
    def _online(self, genset=None, link_state='online', **values):
        """Стан «на зв'язку» з останнім знімком (як після забору W1): поля генератора + ``last_values_json``."""
        genset = genset or self.genset
        type(self).reading_seq += 1
        snap = snapshot(**values)
        now = fields.Datetime.now()
        reading = self.env['td.genset.reading'].create({
            'genset_id': genset.id, 'relay_id': self.reading_seq, 'ts': now - timedelta(seconds=12),
            'fuel_level': snap.get('fuel_level') or 0.0,
        })
        genset.sudo().write({
            'last_reading_id': reading.id,
            'last_values_json': snap,
            'link_state': link_state,
            'link_changed_at': now - timedelta(hours=1),
            'relay_commands_enabled': True,
            'relay_commands_ready': True,
            'relay_online': link_state == 'online',
            'relay_version': '1.1.3',
            'controller_mode': snap.get('controller_mode') or 'unknown',
            'genset_status': str(snap['genset_status']) if snap.get('genset_status') is not None else False,
            'mains_on_load': bool(snap.get('mains_on_load')),
            'gen_on_load': bool(snap.get('gen_on_load')),
            'mains_ok': bool(snap.get('mains_normal')),
            'feed_source': 'genset' if snap.get('gen_on_load') else 'mains' if snap.get('mains_on_load') else 'none',
            'fuel_liters': round((snap.get('fuel_level') or 0) / 100.0 * genset.tank_volume_l, 1),
            'fuel_source': 'pct',
            'remote_lock': bool(snap.get('remote_lock')),
        })
        return snap

    def _js(self, body):
        return JS_WAIT + "\n(async () => {\n" + body + "\n})().catch((error) => console.error(error.message || error));"

    # ------------------------------------------------------------------ AC-24: стан пульта за ролями
    def test_ac24_pult_state_by_role_and_link(self):
        """AC-24: плитки й автомати активні лише для Т на зв'язку; для С/А — причина «Ваша роль — …»; без
        зв'язку — «Немає зв'язку з модулем — команди неможливо доставити»; формат А.9."""
        self._online(controller_mode='auto', oil_pressure=None)
        genset = self.genset
        state_t = genset.with_user(self.user_t).get_pult_state()
        for key in ('can_control', 'block_reason', 'buttons', 'breakers', 'gauges', 'status', 'feed', 'timer', 'test',
                    'server_now'):
            self.assertIn(key, state_t)
        self.assertTrue(state_t['can_control'])
        self.assertIsNone(state_t['block_reason'])
        self.assertTrue(all(button['enabled'] for button in state_t['buttons'].values()))
        self.assertTrue(state_t['buttons']['auto']['active'])
        self.assertFalse(state_t['buttons']['manual']['active'])
        self.assertEqual(state_t['breakers']['mains']['target_label'], 'Розімкнути')
        self.assertEqual(state_t['breakers']['gen']['target_label'], 'Замкнути')
        self.assertTrue(state_t['breakers']['mains']['available'])
        self.assertIsNone(state_t['gauges']['oil_pressure'], 'AC-06: null у знімку → «немає даних»')
        self.assertEqual(state_t['gauges']['water_temp'], 35)
        self.assertEqual(state_t['status']['label'], 'Очікування')
        json.dumps(state_t)  # RPC-серіалізація
        for user, role in ((self.user_s, 'Співробітник'), (self.user_a, 'Адміністратор')):
            state = genset.with_user(user).get_pult_state()
            self.assertFalse(state['can_control'])
            self.assertIn('Ваша роль — %s: пульт і автомати доступні тех. адміністратору' % role, state['block_reason'])
            self.assertFalse(any(button['enabled'] for button in state['buttons'].values()))
            self.assertFalse(state['breakers']['gen']['enabled'])
        # без зв'язку — пульт недоступний і тех. адміністратору
        genset.sudo().link_state = 'offline'
        state = genset.with_user(self.user_t).get_pult_state()
        self.assertFalse(state['can_control'])
        self.assertIn("Немає зв'язку з модулем — команди неможливо доставити", state['block_reason'])
        state = genset.with_user(self.user_s).get_pult_state()
        self.assertIn("Немає зв'язку з модулем", state['block_reason'])
        self.assertIn('Ваша роль — Співробітник', ' '.join(note['text'] for note in state['notes']))
        # керування вимкнено на ретрансляторі (AC-11/AC-16)
        genset.sudo().write({'link_state': 'online', 'relay_commands_enabled': False})
        state = genset.with_user(self.user_t).get_pult_state()
        self.assertFalse(state['can_control'])
        self.assertIn('Керування вимкнено на ретрансляторі', state['block_reason'])
        # блокування на контролері і вимкнений перемикач команд — пояснення, команда запишеться зі станом
        # «Не надіслано: …» (AC-23, AC-66)
        genset.sudo().write({'relay_commands_enabled': True, 'remote_lock': True, 'commands_allowed': False})
        state = genset.with_user(self.user_t).get_pult_state()
        self.assertTrue(state['can_control'])
        notes = ' '.join(note['text'] for note in state['notes'])
        self.assertIn('Дистанційне керування заблоковано на контролері', notes)
        self.assertIn('Дозволити команди', notes)
        # HGM6110N без автомата мережі (1.5-29)
        genset.sudo().controller_model_id = self.env.ref('td_genset.controller_hgm6110n')
        state = genset.with_user(self.user_t).get_pult_state()
        self.assertFalse(state['breakers']['mains']['available'])
        self.assertFalse(state['breakers']['mains']['enabled'])

    def test_ac31_timer_and_test_in_pult_state(self):
        """Таймер і тест у стані пульта: кінець, хто запустив, прогрес; прогрес таймера 0–100 на картці."""
        self._online()
        now = fields.Datetime.now()
        self.genset.sudo().write({'timer_started_at': now - timedelta(minutes=30), 'timer_end': now + timedelta(minutes=30),
                                  'timer_user_id': self.user_s.id, 'test_end': now + timedelta(minutes=3),
                                  'test_mode': 'load'})
        self.assertAlmostEqual(self.genset.timer_progress, 50.0, delta=1.0)
        state = self.genset.with_user(self.user_s).get_pult_state()
        self.assertEqual(state['timer']['started_by'], self.user_s.name)
        self.assertAlmostEqual(state['timer']['progress'], 0.5, delta=0.01)
        self.assertEqual(state['test']['mode'], 'load')
        self.assertEqual(state['test']['mode_label'], 'З навантаженням')

    # ------------------------------------------------------------------ AC-05/AC-06: «Поточні дані»
    def test_ac05_ac06_current_data_html(self):
        """AC-05, AC-06: «Поточні дані» — значення знімка з підписами й адресами; null/відсутній ключ — «немає
        даних»; оми датчиків поруч із °C / kPa / %; літри з позначкою джерела (ФВ-31); блок «Ретранслятор»."""
        snap = self._online(oil_pressure=None, water_temp=41, fuel_level=50, fuel_sensor_ohm=95.5,
                            water_temp_sensor_ohm=515.4, oil_pressure_sensor_ohm=9.5)
        values = dict(snap)
        del values['controller_sw']  # ключа немає (ретранслятор < 1.1.3)
        values['brand_new_key'] = 42
        self.genset.sudo().last_values_json = values
        html = str(self.genset.with_user(self.user_s).current_data_html)
        for text in ('Мережа', 'Генератор', 'Навантаження', 'Двигун', 'Лічильники і ТО', 'Сигнали', 'Ретранслятор',
                     'Температура ОР', '41 °C', '515.4 Ом', '9.5 Ом', '95.5 Ом', '03H 0018', '03H 0020', '03H 0022',
                     'За % контролера', '50 %', '72.5 L', 'немає даних', 'brand_new_key', 'Інші значення'):
            self.assertIn(text, html)
        # Тиск оливи null → «немає даних» у рядку 0019
        row = html[html.index('0019'):html.index('0021')]
        self.assertIn('немає даних', row)
        # літри за калібруванням
        self.genset.sudo().fuel_source = 'ohm'
        self.assertIn('За датчиком (Ом)', str(self.genset.current_data_html))
        # без зв'язку — дані сірі з позначкою часу
        self.genset.sudo().link_state = 'offline'
        html = str(self.genset.current_data_html)
        self.assertIn('o_td_genset_stale', html)
        self.assertIn("Немає зв&#39;язку з модулем: показано дані на", html)
        # HTML екранує значення з ретранслятора
        values['controller_hw'] = '<script>alert(1)</script>'
        self.genset.sudo().last_values_json = values
        self.assertNotIn('<script>', str(self.genset.current_data_html))

    # ------------------------------------------------------------------ AC-60: порожні стани
    def test_ac60_empty_states(self):
        """AC-60: новий генератор без hostid — підказки «Вкажіть hostid…», «очікуємо перший знімок», «Немає каністр
        — оформіть надходження»; пульт неактивний з поясненням; форма відкривається без помилок."""
        genset = self.env['td.genset'].create({'name': 'Новий без hostid', 'power_kw': 8.0,
                                               'controller_model_id': self.controller_model.id})
        state = genset.with_user(self.user_t).get_pult_state()
        self.assertFalse(state['can_control'])
        self.assertIn('Вкажіть hostid і ввімкніть опитування', state['block_reason'])
        self.assertFalse(state['has_reading'])
        self.assertTrue(all(value is None for value in state['gauges'].values()))
        html = str(genset.current_data_html)
        self.assertIn('Вкажіть hostid і ввімкніть опитування', html)
        self.assertIn('Очікуємо перший знімок', html)
        arch = self.env['td.genset'].get_views([(False, 'form')])['views']['form']['arch']
        self.assertIn('Вкажіть hostid і ввімкніть опитування', arch)
        self.assertIn('Очікуємо перший знімок', arch)
        helps = {
            'td_genset.action_td_genset_reading': 'Очікуємо перший знімок',
            'td_genset.action_td_genset_event': 'Подій ще немає',
            'td_genset.action_td_genset_canister': 'Немає каністр — оформіть надходження',
            'td_genset.action_td_genset_refuel': 'Заправок ще не було',
            'td_genset.action_td_genset_fuel_move': 'Рухів палива ще немає',
        }
        for xmlid, text in helps.items():
            self.assertIn(text, str(self.env.ref(xmlid).help), xmlid)
        self.assertEqual((genset.kpi_run_hours_7d, genset.kpi_starts_30d, genset.kpi_covered_pct_30d), (0, 0, 0))
        self.browser_js('/odoo/td.genset/%d' % genset.id, self._js("""
            const root = await waitFor(() => document.querySelector(".o_td_pult[data-loaded='1']"), "pult");
            if (root.querySelectorAll(".o_td_pult_tile:not([disabled])").length) { throw new Error("tiles enabled"); }
            const lock = root.querySelector(".o_td_pult_lock");
            if (!lock || !lock.innerText.includes("Вкажіть hostid")) { throw new Error("no hostid hint in pult"); }
            const sheet = document.querySelector(".o_form_sheet");
            if (!sheet.innerText.includes("Вкажіть hostid і ввімкніть опитування")) { throw new Error("no hostid alert"); }
            document.querySelector(".o_notebook .nav-link[name='current_data']").click();
            await waitFor(() => document.querySelector(".o_td_genset_current_data"), "current data tab");
            if (!document.querySelector(".o_td_genset_current_data").innerText.includes("Очікуємо перший знімок")) {
                throw new Error("no first snapshot hint");
            }
            console.log("test successful");
        """), login='td_user_t')

    # ------------------------------------------------------------------ AC-62: bus
    def test_ac62_bus_channel_and_message(self):
        """AC-62: канал ``td_genset_<id>`` → запис генератора для користувача з правом читання (інакше відкидається);
        ``_notify_bus`` надсилає ``td_genset.update`` у канал запису генератора."""
        other, gensets = self.env['ir.websocket'].with_user(self.user_x)._td_genset_bus_channels(
            ['td_genset_%d' % self.genset.id, 'broadcast'])
        self.assertEqual(gensets, self.genset)
        self.assertEqual(other, ['broadcast'])
        outsider = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Без доступу', 'login': 'td_outsider', 'groups_id': [(6, 0, [self.env.ref('base.group_user').id])]})
        _other, gensets = self.env['ir.websocket'].with_user(outsider)._td_genset_bus_channels(
            ['td_genset_%d' % self.genset.id])
        self.assertFalse(gensets)
        self.genset._notify_bus('command', {'command_id': 7, 'state': 'done'})
        self.env.cr.precommit.run()
        message = self.env['bus.bus'].sudo().search([], order='id desc', limit=1)
        self.assertEqual(json.loads(message.channel), [self.env.cr.dbname, 'td.genset', self.genset.id])
        payload = json.loads(message.message)
        self.assertEqual(payload['type'], 'td_genset.update')
        self.assertEqual(payload['payload']['kind'], 'command')

    def test_ac62_live_update_and_polling(self):
        """AC-62: віджет підписується на канал генератора; повідомлення bus → перечитування запису і пульта
        (плитка «Ручний» підсвічується без перезавантаження сторінки); без websocket — резервне опитування."""
        self._online(controller_mode='auto')
        self.browser_js('/odoo/action-td_genset.action_td_genset', self._js("""
            const ID = %(id)d;
            await waitFor(() => window.odoo && odoo.__WOWL_DEBUG__ && document.querySelector(".o_view_controller"),
                          "web client");
            const env = odoo.__WOWL_DEBUG__.root.env;
            const bus = env.services.bus_service;
            const pultModule = odoo.loader.modules.get("@td_genset/pult/pult_widget");
            pultModule.PULT_TIMING.debounceMs = 50;
            pultModule.PULT_TIMING.pollMs = 400;
            let workerState = "CONNECTED";
            Object.defineProperty(bus, "workerState", { get: () => workerState, configurable: true });
            Object.defineProperty(bus, "isActive", { get: () => true, configurable: true });
            const channels = [];
            const callbacks = [];
            const addChannel = bus.addChannel;
            bus.addChannel = (channel) => { channels.push(channel); return addChannel(channel); };
            const subscribe = bus.subscribe;
            bus.subscribe = (type, callback) => {
                if (type === "td_genset.update") { callbacks.push(callback); }
                return subscribe(type, callback);
            };
            await env.services.action.doAction({
                type: "ir.actions.act_window", res_model: "td.genset", res_id: ID, views: [[false, "form"]],
            });
            const root = await waitFor(() => document.querySelector(".o_td_pult[data-loaded='1']"), "pult");
            if (!channels.includes("td_genset_" + ID)) { throw new Error("channel not added: " + channels); }
            if (!callbacks.length) { throw new Error("not subscribed to td_genset.update"); }
            await waitFor(() => root.querySelector(".o_td_pult_tile_auto.o_td_pult_active"), "auto active");
            await sleep(900);
            const quiet = Number(root.dataset.refresh);
            await sleep(900);
            if (Number(root.dataset.refresh) !== quiet) { throw new Error("polling while websocket connected"); }
            await env.services.orm.write("td.genset", [ID], { controller_mode: "manual" });
            callbacks.forEach((callback) => callback({ genset_id: ID + 100000, kind: "reading" }));
            await sleep(300);
            if (root.querySelector(".o_td_pult_tile_manual.o_td_pult_active")) { throw new Error("foreign genset"); }
            callbacks.forEach((callback) => callback({ genset_id: ID, kind: "reading" }));
            await waitFor(() => root.querySelector(".o_td_pult_tile_manual.o_td_pult_active"), "manual active");
            const formMode = document.querySelector(".o_form_view .o_field_widget[name='controller_mode']");
            if (!formMode || !formMode.innerText.includes("Ручний")) { throw new Error("form field not reloaded"); }
            workerState = "DISCONNECTED";
            const before = Number(root.dataset.refresh);
            await waitFor(() => Number(root.dataset.refresh) >= before + 2, "fallback polling");
            console.log("test successful");
        """ % {'id': self.genset.id}), login='td_user_t')

    def test_ac62_pult_survives_rpc_failure(self):
        """AC-61, AC-62 (ревю коду, п. 2): відмова RPC стану пульта (обрив мережі, 5xx) не ламає форму і не дає
        «Uncaught Promise»: без даних — «Пульт тимчасово недоступний», після відновлення — пульт (повтор
        резервним опитуванням навіть при живому websocket); помилка оновлення лишає останній стан з позначкою."""
        self._online(controller_mode='auto')
        self.browser_js('/odoo/action-td_genset.action_td_genset', self._js("""
            const ID = %(id)d;
            await waitFor(() => window.odoo && odoo.__WOWL_DEBUG__ && document.querySelector(".o_view_controller"),
                          "web client");
            const env = odoo.__WOWL_DEBUG__.root.env;
            const bus = env.services.bus_service;
            const pultModule = odoo.loader.modules.get("@td_genset/pult/pult_widget");
            pultModule.PULT_TIMING.debounceMs = 50;
            pultModule.PULT_TIMING.pollMs = 400;
            Object.defineProperty(bus, "workerState", { get: () => "CONNECTED", configurable: true });
            Object.defineProperty(bus, "isActive", { get: () => true, configurable: true });
            const callbacks = [];
            const subscribe = bus.subscribe;
            bus.subscribe = (type, callback) => {
                if (type === "td_genset.update") { callbacks.push(callback); }
                return subscribe(type, callback);
            };
            const orm = env.services.orm;
            const call = orm.call;
            let fail = true;
            orm.call = function (model, method, ...args) {
                if (fail && model === "td.genset" && method === "get_pult_state") {
                    return Promise.reject(new Error("simulated RPC failure"));
                }
                return call.call(this, model, method, ...args);
            };
            await env.services.action.doAction({
                type: "ir.actions.act_window", res_model: "td.genset", res_id: ID, views: [[false, "form"]],
            });
            const root = await waitFor(() => document.querySelector(".o_td_pult[data-error='1']"), "error state");
            if (root.dataset.loaded !== "0" || !root.querySelector(".o_td_pult_unavailable")) {
                throw new Error("no placeholder");
            }
            if (!document.querySelector(".o_form_view .o_field_widget[name='controller_mode']")) {
                throw new Error("form not rendered");
            }
            fail = false;
            await waitFor(() => root.dataset.loaded === "1" && root.dataset.error === "0", "recovered by polling");
            await waitFor(() => root.querySelector(".o_td_pult_tile_auto.o_td_pult_active"), "auto active");
            fail = true;
            callbacks.forEach((callback) => callback({ genset_id: ID, kind: "reading" }));
            await waitFor(() => root.dataset.error === "1", "refresh error");
            if (root.dataset.loaded !== "1" || !root.querySelector(".o_td_pult_tile_auto")) {
                throw new Error("last state lost");
            }
            fail = false;
            await waitFor(() => root.dataset.error === "0", "recovered again");
            console.log("test successful");
        """ % {'id': self.genset.id}), login='td_user_t')

    # ------------------------------------------------------------------ AC-56/AC-24: форма для кожної ролі
    def test_ac56_form_and_tabs_for_each_role(self):
        """AC-56, AC-24: картка відкривається для С/А/Т без помилок JS/RPC; плитки активні лише для Т; для С/А —
        пояснення ролі; усі вкладки відкриваються."""
        self._online(controller_mode='auto')
        for login, enabled in (('td_user_s', 0), ('td_user_a', 0), ('td_user_t', 5)):
            self.browser_js('/odoo/td.genset/%d' % self.genset.id, self._js("""
                const root = await waitFor(() => document.querySelector(".o_td_pult[data-loaded='1']"), "pult");
                const tiles = [...root.querySelectorAll(".o_td_pult_tile")];
                if (tiles.length !== 5) { throw new Error("tiles: " + tiles.length); }
                const enabled = tiles.filter((tile) => !tile.disabled).length;
                if (enabled !== %(enabled)d) { throw new Error("enabled tiles " + enabled); }
                const lock = root.querySelector(".o_td_pult_lock");
                if (%(enabled)d === 0 && !(lock && lock.innerText.includes("Ваша роль"))) {
                    throw new Error("no role explanation");
                }
                const gauges = root.querySelectorAll(".o_td_pult_gauge");
                if (gauges.length !== 4) { throw new Error("gauges: " + gauges.length); }
                for (const link of document.querySelectorAll(".o_notebook .nav-link")) {
                    link.click();
                    await sleep(150);
                }
                await waitFor(() => document.querySelector(".o_td_genset_current_data") || true, "tabs");
                console.log("test successful");
            """ % {'enabled': enabled}), login=login)

    # ------------------------------------------------------------------ AC-61: 390 px
    def test_ac61_mobile_layout(self):
        """AC-61: на 390 px (емуляція телефона) картка без горизонтальної прокрутки сторінки, «Керування» — перший
        блок пульта, плитки 2 × N (Тест — на всю ширину); показання, події, заправка, налаштування — теж без
        горизонтальної прокрутки сторінки."""
        self._online(controller_mode='auto')
        self.browser_size = '390x844'
        self.touch_enabled = True
        self.browser_js('/odoo/td.genset/%d' % self.genset.id, self._js("""
            const doc = document;
            await waitFor(() => doc.querySelector(".o_td_pult[data-loaded='1']"), "pult at 390px");
            await sleep(500);
            if (window.innerWidth > 400) { throw new Error("not a phone viewport: " + window.innerWidth); }
            const width = doc.documentElement.scrollWidth;
            if (width > window.innerWidth) { throw new Error("horizontal scroll: " + width); }
            const controls = doc.querySelector(".o_td_pult_controls").getBoundingClientRect();
            for (const selector of [".o_td_pult_gauges", ".o_td_pult_diagram", ".o_td_pult_params"]) {
                if (doc.querySelector(selector).getBoundingClientRect().top <= controls.top) {
                    throw new Error(selector + " is above controls");
                }
            }
            const columns = getComputedStyle(doc.querySelector(".o_td_pult_tiles")).gridTemplateColumns.split(" ");
            if (columns.length !== 2) { throw new Error("tile columns: " + columns.length); }
            const test = doc.querySelector(".o_td_pult_tile_test").getBoundingClientRect();
            const auto = doc.querySelector(".o_td_pult_tile_auto").getBoundingClientRect();
            if (test.width < auto.width * 1.5) { throw new Error("test tile is not full width"); }
            const env = odoo.__WOWL_DEBUG__.root.env;
            for (const xmlid of ["td_genset.action_td_genset_reading", "td_genset.action_td_genset_event",
                                 "td_genset.action_td_genset_canister", "td_genset.action_td_genset_config",
                                 "td_genset.action_td_genset_analytics_run_outage"]) {
                await env.services.action.doAction(xmlid, { clearBreadcrumbs: true });
                await waitFor(() => doc.querySelector(".o_action_manager .o_view_controller"), xmlid);
                await sleep(400);
                if (doc.documentElement.scrollWidth > window.innerWidth) {
                    throw new Error(xmlid + ": horizontal scroll " + doc.documentElement.scrollWidth);
                }
            }
            console.log("test successful");
        """ % {'id': self.genset.id}), login='td_user_t')

    # ------------------------------------------------------------------ подання: синтаксис 18.0, вкладки, дії
    def test_views_odoo18_and_actions(self):
        """Подання модуля — лише синтаксис 18.0 (BUILD_PLAN 1.1), форма генератора з пультом і вкладками
        мокапа; дії «Показання», «Події», «Заправка», «Аналітика» відкриваються."""
        view_ids = self.env['ir.model.data'].search([('module', '=', 'td_genset'), ('model', '=', 'ir.ui.view')])
        views = self.env['ir.ui.view'].browse(view_ids.mapped('res_id'))
        self.assertGreater(len(views), 40)
        for view in views:
            for legacy in LEGACY_VIEW_SYNTAX:
                self.assertNotIn(legacy, view.arch_db, view.xml_id)
        arch = etree.fromstring(self.env['td.genset'].get_views([(False, 'form')])['views']['form']['arch'])
        pages = [page.get('name') for page in arch.xpath('//notebook/page')]
        self.assertEqual(pages, ['schedule', 'current_data', 'alarms', 'maintenance', 'commands', 'fuel', 'analytics',
                                 'relay'])
        self.assertTrue(arch.xpath("//widget[@name='td_genset_pult']"))
        self.assertTrue(arch.xpath("//chatter"))
        self.assertTrue(arch.xpath("//field[@name='genset_stage'][@widget='statusbar']"))
        for xmlid in ('action_td_genset_reading', 'action_td_genset_event', 'action_td_genset_canister',
                      'action_td_genset_analytics_run_outage', 'action_td_genset_analytics_energy',
                      'action_td_genset_analytics_cranks', 'action_td_genset_analytics_fuel_used',
                      'action_td_genset_analytics_fuel_level', 'action_td_genset_analytics_battery',
                      'action_td_genset_analytics_last_run'):
            action = self.env.ref('td_genset.%s' % xmlid)
            modes = action.view_mode.split(',')
            self.env[action.res_model].with_user(self.user_s).get_views([(False, mode) for mode in modes])
        for key in ('run_outage', 'energy', 'cranks', 'fuel_used', 'fuel_level', 'battery'):
            action = self.genset.with_user(self.user_s).with_context(td_analytics=key).action_open_analytics()
            self.assertEqual(action['context']['search_default_genset_id'], self.genset.id)
        action = self.genset.with_user(self.user_s).action_open_last_run_load()
        self.assertEqual(action['domain'], [('id', '=', 0)])
        start = fields.Datetime.now() - timedelta(hours=2)
        self.env['td.genset.event'].create({'genset_id': self.genset.id, 'event_type': 'run', 'date_start': start,
                                            'date_end': start + timedelta(hours=1)})
        action = self.genset.with_user(self.user_s).action_open_last_run_load()
        self.assertIn(('ts', '>=', start), action['domain'])
        self.assertEqual(self.genset.with_user(self.user_s).action_open_canisters()['res_model'], 'td.genset.canister')
        self.assertEqual(self.genset.with_user(self.user_s).action_open_escalation()['res_model'], 'td.genset.config')

    def test_kpi_analytics(self):
        """KPI «Аналітики» 7/30 днів з подій і знімків (2.10): мотогодини, пуски, вироблено, відключення,
        покрито генератором, середнє навантаження, пуск з 1-ї спроби, мінімум АКБ при прокрутці."""
        now = fields.Datetime.now()
        Event = self.env['td.genset.event']
        Event.create([
            {'genset_id': self.genset.id, 'event_type': 'run', 'date_start': now - timedelta(days=2),
             'date_end': now - timedelta(days=2) + timedelta(hours=2), 'energy_kwh': 10.0, 'crank_attempts': 1,
             'crank_min_battery_v': 22.5},
            {'genset_id': self.genset.id, 'event_type': 'run', 'date_start': now - timedelta(days=10),
             'date_end': now - timedelta(days=10) + timedelta(hours=1), 'energy_kwh': 5.0, 'crank_attempts': 3,
             'crank_min_battery_v': 20.9},
            {'genset_id': self.genset.id, 'event_type': 'outage', 'date_start': now - timedelta(days=2),
             'date_end': now - timedelta(days=2) + timedelta(hours=3)},
        ])
        Reading = self.env['td.genset.reading']
        for index, (mains_ok, feed, running, load) in enumerate([(False, 'genset', True, 40.0), (False, 'none', False, 0),
                                                                 (True, 'mains', False, 0), (False, 'genset', True, 60.0)]):
            Reading.create({'genset_id': self.genset.id, 'relay_id': 7000 + index, 'ts': now - timedelta(hours=index + 1),
                            'mains_ok': mains_ok, 'feed_source': feed, 'is_running': running, 'load_pct': load})
        self.genset.invalidate_recordset()
        genset = self.genset.with_user(self.user_s)
        self.assertAlmostEqual(genset.kpi_run_hours_7d, 2.0, places=2)
        self.assertAlmostEqual(genset.kpi_run_hours_30d, 3.0, places=2)
        self.assertEqual((genset.kpi_starts_7d, genset.kpi_starts_30d), (1, 2))
        self.assertEqual((genset.kpi_energy_kwh_7d, genset.kpi_energy_kwh_30d), (10.0, 15.0))
        self.assertEqual(genset.kpi_outages_30d, 1)
        self.assertAlmostEqual(genset.kpi_covered_pct_7d, 66.7, places=1)
        self.assertAlmostEqual(genset.kpi_avg_load_pct_7d, 50.0, places=1)
        self.assertEqual((genset.kpi_first_try_pct_7d, genset.kpi_first_try_pct_30d), (100.0, 50.0))
        self.assertEqual(genset.kpi_crank_battery_min_30d, 20.9)

    # ------------------------------------------------------------------ D-01: графіки й зведені таблиці
    def _graph_pivot_actions(self):
        """Дії модуля (``ir.actions.act_window``) з поданням graph або pivot: ``{xmlid: дія}`` як для web-клієнта."""
        data = self.env['ir.model.data'].search([('module', '=', 'td_genset'), ('model', '=', 'ir.actions.act_window')])
        Action = self.env['ir.actions.act_window'].with_user(self.user_s)
        actions = {}
        for xmlid in sorted('td_genset.%s' % name for name in data.mapped('name')):
            action = Action._for_xml_id(xmlid)
            if {'graph', 'pivot'} & {mode for _view_id, mode in action['views']}:
                actions[xmlid] = action
        return actions

    def _web_groupby(self, spec, fields, where):
        """``getGroupBy`` web-клієнта Odoo 18 (web/static/src/search/utils/group_by.js): поле існує; дата —
        інтервал лише з ``WEB_DATE_INTERVALS``; не дата — без інтервалу."""
        name, _sep, interval = spec.partition(':')
        self.assertIn(name, fields, '%s: %s' % (where, spec))
        if fields[name]['type'] in ('date', 'datetime'):
            self.assertIn(interval or 'month', WEB_DATE_INTERVALS, '%s: %s' % (where, spec))
        else:
            self.assertFalse(interval, '%s: %s' % (where, spec))
        return spec

    def _analytics_data(self):
        """Знімки за 3 дні (частина — під час роботи) і події «Робота»/«Відключення мережі» для графіків."""
        now = fields.Datetime.now()
        for index in range(12):
            running = index % 3 == 0
            self.env['td.genset.reading'].create({
                'genset_id': self.genset.id, 'relay_id': 8000 + index, 'ts': now - timedelta(hours=6 * index + 1),
                'is_journal': True, 'fuel_level': 90 - index, 'battery_v': 26.5 - index * 0.1, 'is_running': running,
                'active_power': 6.0 if running else 0.0, 'load_pct': 25.0 if running else 0.0,
                'mains_ok': not running, 'feed_source': 'genset' if running else 'mains'})
        self.env['td.genset.event'].create([
            {'genset_id': self.genset.id, 'event_type': 'run', 'date_start': now - timedelta(days=1, hours=2),
             'date_end': now - timedelta(days=1), 'energy_kwh': 9.0, 'crank_attempts': 1},
            {'genset_id': self.genset.id, 'event_type': 'outage', 'date_start': now - timedelta(days=1, hours=2),
             'date_end': now - timedelta(days=1)},
        ])

    def test_d01_graph_pivot_groupby_web_intervals(self):
        """D-01: кожна graph/pivot-дія модуля — групування за правилами web-клієнта Odoo 18 (дати лише
        ``year``…``day``, без ``ts:hour``) у поданні, у фільтрах «Групувати за» її пошуку і в контексті дії;
        ``web_read_group`` / ``read_group`` з контекстом дії і цими групуваннями виконується без помилки."""
        self._analytics_data()
        actions = self._graph_pivot_actions()
        for xmlid in ('td_genset.action_td_genset_reading', 'td_genset.action_td_genset_event',
                      'td_genset.action_td_genset_analytics_fuel_level', 'td_genset.action_td_genset_analytics_battery',
                      'td_genset.action_td_genset_analytics_last_run', 'td_genset.action_td_genset_analytics_run_outage'):
            self.assertIn(xmlid, actions)
        for xmlid, action in actions.items():
            Model = self.env[action['res_model']].with_user(self.user_s)
            context = safe_eval(action['context'] or '{}', {'uid': self.user_s.id, 'active_id': False})
            domain = safe_eval(action['domain'] or '[]', {'uid': self.user_s.id})
            search_view = action['search_view_id'] and action['search_view_id'][0]
            result = Model.with_context(context).get_views(
                [list(view) for view in action['views']] + [[search_view, 'search']])
            fields_info = result['models'][action['res_model']]['fields']
            search_arch = etree.fromstring(result['views']['search']['arch'])
            filters = {node.get('name'): node for node in search_arch.iter('filter')}
            default_groupby = []
            for node in search_arch.iter('filter'):
                group_by = safe_eval(node.get('context') or '{}', {'uid': self.user_s.id}).get('group_by') or []
                for spec in [group_by] if isinstance(group_by, str) else group_by:
                    self._web_groupby(spec, fields_info, '%s: фільтр «%s»' % (xmlid, node.get('string')))
                    if context.get('search_default_%s' % node.get('name')):
                        default_groupby.append(spec)
            action_groupby = context.get('group_by') or []
            for spec in [action_groupby] if isinstance(action_groupby, str) else action_groupby:
                default_groupby.append(self._web_groupby(spec, fields_info, '%s: context group_by' % xmlid))
            self.assertTrue(all(name.removeprefix('search_default_') in filters or
                                name.removeprefix('search_default_') in fields_info
                                for name in context if name.startswith('search_default_')), xmlid)
            for mode in ('graph', 'pivot'):
                if mode not in result['views']:
                    continue
                arch = etree.fromstring(result['views'][mode]['arch'])
                groupby, measures = [], []
                for node in arch.iter('field'):
                    name = node.get('name')
                    if node.get('type') == 'measure':
                        measures.append('%s:%s' % (name, fields_info[name].get('aggregator') or 'sum'))
                        continue
                    spec = name + (':%s' % node.get('interval') if node.get('interval') else '')
                    groupby.append(self._web_groupby(spec, fields_info, '%s: %s-подання' % (xmlid, mode)))
                self.assertTrue(groupby, '%s: %s без групування' % (xmlid, mode))
                groupby = default_groupby or groupby
                web = Model.with_context(**dict(context, tz=self.user_s.tz))
                if mode == 'graph':  # як graph_model.js: webReadGroup, lazy=False, fill_temporal
                    data = web.with_context(fill_temporal=True).web_read_group(domain, measures, groupby, lazy=False)
                else:  # як pivot_model.js: readGroup, lazy=False
                    data = {'groups': web.read_group(domain, measures or ['__count'], groupby, lazy=False)}
                self.assertTrue(data['groups'], '%s: %s без даних' % (xmlid, mode))

    def test_d01_graph_pivot_actions_open_in_browser(self):
        """D-01: кожне graph/pivot-подання дій модуля відкривається у web-клієнті під Співробітником без помилки JS
        «Invalid groupBy description» і вікна «От халепа!»."""
        self._analytics_data()
        targets = [[xmlid, mode] for xmlid, action in self._graph_pivot_actions().items()
                   for _view_id, mode in action['views'] if mode in ('graph', 'pivot')]
        self.assertGreaterEqual(len(targets), 12)
        self.browser_js('/odoo/action-td_genset.action_td_genset', self._js("""
            await waitFor(() => window.odoo && odoo.__WOWL_DEBUG__ && document.querySelector(".o_view_controller"),
                          "web client");
            const env = odoo.__WOWL_DEBUG__.root.env;
            for (const [xmlid, viewType] of %(targets)s) {
                await env.services.action.doAction(xmlid, { viewType, clearBreadcrumbs: true });
                const selector = viewType === "graph" ? ".o_graph_view .o_graph_renderer canvas"
                                                      : ".o_pivot_view .o_pivot table";
                await waitFor(() => document.querySelector(".o_action_manager " + selector), xmlid + " " + viewType);
                if (document.querySelector(".o_error_dialog, .o_dialog .modal-body .o_error_detail")) {
                    throw new Error(xmlid + " " + viewType + ": error dialog");
                }
            }
            console.log("test successful");
        """ % {'targets': json.dumps(targets)}), login='td_user_s')

    # ------------------------------------------------------------------ D-05: «Зв'язок» у шапці
    def test_d05_link_relative_age(self):
        """D-05 (ТК-01.2): «Зв'язок» у шапці картки — бейдж «Онлайн» і «· N с тому» з відліком щосекунди (запис
        оновлює bus / резервне опитування пульта), повна дата й час останнього знімка — у підказці, а не в рядку."""
        self._online()
        year = str(fields.Date.today().year)
        self.browser_js('/odoo/td.genset/%d' % self.genset.id, self._js("""
            const age = await waitFor(() => document.querySelector(".o_td_genset_link_age"), "link age");
            const row = age.closest(".o_row");
            const badge = row.querySelector(".badge");
            if (!badge || !badge.innerText.includes("Онлайн")) {
                throw new Error("no online badge: " + (badge && badge.innerText));
            }
            const first = age.innerText.trim();
            if (!/^· \\d+ с тому$/.test(first)) { throw new Error("relative text: " + first); }
            if (row.innerText.includes("%(year)s")) { throw new Error("absolute date in header: " + row.innerText); }
            if (!age.title.includes("%(year)s") || !/\\d{1,2}:\\d{2}:\\d{2}/.test(age.title)) {
                throw new Error("tooltip: " + age.title);
            }
            await waitFor(() => age.innerText.trim() !== first, "tick");
            console.log("test successful");
        """ % {'year': year}), login='td_user_s')
