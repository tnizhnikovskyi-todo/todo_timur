import importlib.util
import os

from odoo.tests import TransactionCase, tagged

from ..hooks import refresh_registry


@tagged('post_install', '-at_install', 'f3d', 'f3d_iot_sim')
class TestRegistryFix(TransactionCase):
    """S-2/S-3: params за §5.2, unit 96 у T1/T2, сигнали PV-INV-n на похідних, пасивні FL-6/SMOKE-VENTS.

    У чистій базі тестів немає обладнання з паспортами, тож усі пристрої каталогу — `passive`; драйвери, які
    у демо дає роль, виставляються тут, а відсутні (FL-6, SMOKE-VENTS, PV-INV-n) створюються.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Device = cls.env['td.sim.device'].sudo()
        cls.Signal = cls.env['td.sim.signal'].sudo()

    def dev(self, code):
        device = self.Device.search([('code', '=', code)])
        self.assertTrue(device, code)
        return device

    def make(self, code, driver, protocol, **extra):
        return self.Device.search([('code', '=', code)]) or self.Device.create(
            dict({'code': code, 'name': code, 'driver': driver, 'protocol': protocol}, **extra))

    def test_params_by_spec(self):
        expected = {
            'SLIDE-1': {'di_run': 0, 'di_fault': 1, 'counter': 0},
            'VSAW-1': {'di_run': 2, 'di_fault': 3, 'counter': 2},
            'GLUE-1': {'di_run': 8, 'di_fault': 9, 'counter': 8},
            'ASM-6': {'di_run': 8, 'di_fault': 9, 'counter': 8},
            'T1': {'rtd': [0, 1, 2]}, 'T2': {'rtd': [3, 4, 5]},
            'SPRINKLERS': {'ai': 2}, 'AIR-RING': {'ai': 3}, 'WATER': {'counter': 8},
            'DUST-1': {'ai_airflow': 0, 'ai_dp': 1, 'di_run': 0, 'di_fault': 1},
            'SPARK-1': {'di_spark': 0, 'di_ext': 1, 'di_fault': 2},
            'SMOKE-CTRL': {'di_open': 4, 'di_fault': 5, 'do_open': 0},
            'GATE-W': {'di_open': 0, 'di_loop': 1, 'di_photo': 4, 'do_open': 0, 'do_close': 2, 'do_hold': 4},
            'GATE-E': {'di_open': 2, 'di_loop': 3, 'di_photo': 5, 'do_open': 1, 'do_close': 3, 'do_hold': 5},
            'FA-RCV-1': {'lsz': 1}, 'FA-CUT': {'lsz': 12}, 'FA-OFFICE': {'lsz': 35},
            'LT-RCV-1': {'group': 1, 'router': '@1.1'}, 'LT-CUT': {'group': 12, 'router': '@1.2'},
            'LT-OUT-7': {'group': 32, 'router': '@1.3'},
        }
        for code, params in expected.items():
            self.assertEqual(self.dev(code).params, params, code)
        self.assertEqual(self.Device.search_count([('code', '=like', 'FA-%'), ('params', '!=', False)]), 35)
        self.assertEqual(self.Device.search_count([('code', '=like', 'LT-%'), ('params', '!=', False)]), 32)
        p02 = self.Signal.search([('protocol', '=', 'P-02'), ('code', '=like', 'workcenters/%/state')])
        self.assertEqual(len(p02), 20)
        self.assertTrue(all(self.dev(s.code.split('/')[1]).params for s in p02))

    def _make_old_registry(self):
        """Стан бази до виправлення: ADAM-драйвери, unit T1/T2 = 1/2, PV на батьку, FL-6 активний."""
        for code, driver in (('T1', 'modbus_adam6015'), ('T2', 'modbus_adam6015')):
            self.dev(code).write({'driver': driver, 'protocol': 'P-07', 'unit_id': 1 if code == 'T1' else 2,
                                  'params': False})
        self.make('PV-INV', 'modbus_sun2000', 'P-07')
        self.make('PV-INV-3', 'modbus_sun2000', 'P-07', unit_id=63)
        self.Signal.search([('code', '=like', 'infra/pv/PV-INV-3/%')]).write({'device_id': self.dev('PV-INV').id})
        self.make('FL-6', 'mqtt_mobile', 'P-06')
        self.make('SMOKE-VENTS', 'modbus_adam6050', 'P-09')

    def test_fixed_layout_units_and_passive(self):
        self._make_old_registry()
        refresh_registry(self.env)
        self.assertEqual((self.dev('T1').unit_id, self.dev('T2').unit_id), (96, 96))
        self.assertEqual(self.dev('T1').params, {'rtd': [0, 1, 2]})
        for code in ('FL-6', 'SMOKE-VENTS'):
            device = self.dev(code)
            self.assertEqual((device.driver, device.state), ('passive', 'passive'), code)
            self.assertFalse(device.signal_ids, code)
        self.assertEqual(self.dev('SMOKE-VENTS').params, {'di_open': 4, 'di_fault': 5, 'do_open': 0})

    def test_pv_signals_on_derived_devices(self):
        self._make_old_registry()
        refresh_registry(self.env)
        derived = self.dev('PV-INV-3')
        self.assertEqual(sorted(derived.signal_ids.mapped('code')),
                         ['infra/pv/PV-INV-3/%s' % leaf for leaf in ('kwh_today', 'kwh_total', 'p_kw', 'status')])
        # похідних PV-INV-4…8 у базі немає — їхні сигнали лишаються на батьку, а не створюють нових пристроїв
        parent = self.dev('PV-INV')
        self.assertEqual(self.Signal.search_count(
            [('device_id', '=', parent.id), ('code', '=like', 'infra/pv/PV-INV-%')]), 28)
        self.assertEqual(self.Signal.search_count([('code', '=like', 'infra/pv/PV-INV-%')]), 32)

    def _post_migrate(self):
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'migrations', '19.0.2.0.1', 'post-migrate.py')
        spec = importlib.util.spec_from_file_location('f3d_sim_post_migrate_2_0_1', path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def _snapshot(self):
        return {model: {r.id: r.write_date for r in self.env[model].sudo().search([])}
                for model in ('td.sim.device', 'td.sim.signal')}

    def test_post_migrate_repairs_old_registry(self):
        """Params порожні, T1/T2 unit 1/2, PV на батьку, FL-6 активний; ручні params лишаються; повтор без змін."""
        self._make_old_registry()
        lt, fa = self.dev('LT-CUT'), self.dev('FA-CUT')
        self.Device.search([('code', 'in', ('FA-CUT', 'LT-CUT', 'SLIDE-1'))]).write({'params': False})
        lt.params = {'group': 99, 'router': '@9.9'}  # ручна правка

        mod = self._post_migrate()
        mod.migrate(self.env.cr, '19.0.2.0.0')
        self.assertEqual(self.dev('T1').unit_id, 96)
        self.assertEqual(fa.params, {'lsz': 12})
        self.assertEqual(self.dev('SLIDE-1').params, {'di_run': 0, 'di_fault': 1, 'counter': 0})
        self.assertEqual(lt.params, {'group': 99, 'router': '@9.9'})
        self.assertEqual(self.dev('FL-6').driver, 'passive')
        self.assertEqual(len(self.dev('PV-INV-3').signal_ids), 4)

        snapshot = self._snapshot()
        counts = {m: len(r) for m, r in snapshot.items()}
        mod.migrate(self.env.cr, '19.0.2.0.0')  # повторно: без дублікатів і без записів
        self.assertEqual(self._snapshot(), snapshot)
        self.assertEqual({m: len(r) for m, r in self._snapshot().items()}, counts)
        self.assertEqual(counts['td.sim.signal'], 1168)
