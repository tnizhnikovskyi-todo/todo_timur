from unittest import mock

from odoo.exceptions import AccessError
from odoo.tests import new_test_user, tagged

from .common import F3DCase

TABLE = {'OPSAW1': 'OP-SAW-1', 'OPASMLINE1': 'OP-ASMLINE-1'}


@tagged('post_install', '-at_install', 'f3d', 'f3d_base')
class TestEmployeeCode(F3DCase):

    def code(self, barcode, wc=None):
        with mock.patch('odoo.addons.factory3d_base.models.hr_employee._employee_table',
                        return_value=TABLE):
            return self.env['hr.employee']._f3d_code_from_barcode(barcode, wc)

    def test_from_table(self):
        self.assertEqual(self.code('OPSAW1'), 'OP-SAW-1')
        self.assertEqual(self.code('OPASMLINE1'), 'OP-ASMLINE-1')

    def test_from_workcenter(self):
        wc = self.env['mrp.workcenter'].create({'name': 'N', 'f3d_code': 'NEST-1'})
        self.assertEqual(self.code('OPNEST2', wc), 'OP-NEST-1')

    def test_opw_rule(self):
        self.assertEqual(self.code('OPW3'), 'OP-W3')

    def test_unknown(self):
        self.assertFalse(self.code('OPNEST2'))
        self.assertFalse(self.code(''))
        self.assertFalse(self.code(False))


@tagged('post_install', '-at_install', 'f3d', 'f3d_base')
class TestEmployeePublic(F3DCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.emp.sudo().write({'f3d_code': 'OP-SAW-T'})
        cls.plain = new_test_user(cls.env, login='f3d_plain', groups='base.group_user')

    def test_public_mirror_read(self):
        rows = self.env['hr.employee.public'].with_user(self.plain).search_read(
            [('f3d_code', '=', 'OP-SAW-T')], ['name', 'f3d_code', 'f3d_alias', 'f3d_kind'])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['f3d_code'], 'OP-SAW-T')
        self.assertFalse(rows[0]['f3d_alias'])
        self.assertEqual(rows[0]['f3d_kind'], 'employee')

    def test_private_read_without_hr_rights(self):
        emp = self.env['hr.employee'].with_user(self.plain).browse(self.emp.id)
        self.assertEqual(emp.name, 'Оператор-Т')
        self.assertEqual(emp.f3d_code, 'OP-SAW-T')

    def test_search_by_code_without_hr_rights(self):
        Emp = self.env['hr.employee'].with_user(self.plain)
        self.assertEqual(Emp.search([('f3d_code', '=', 'OP-SAW-T')]), self.emp)
        names = Emp.name_search('OP-SAW-T')
        self.assertIn(self.emp.id, [n[0] for n in names])

    def test_mirror_readonly_no_constraint(self):
        Public = self.env['hr.employee.public']
        self.assertTrue(Public._fields['f3d_code'].readonly)
        names = [c[0] if isinstance(c, tuple) else c for c in getattr(Public, '_table_objects', {})]
        self.assertNotIn('_f3d_code_uniq', list(getattr(Public, '_table_objects', {})))
        self.assertTrue(names is not None)

    def test_code_write_rights_employee(self):
        hr_user = new_test_user(
            self.env, login='f3d_hr', groups='base.group_user,hr.group_hr_manager')
        with self.assertRaisesRegex(AccessError, 'менеджер'):
            self.emp.with_user(hr_user).write({'f3d_code': 'OP-X-1'})
