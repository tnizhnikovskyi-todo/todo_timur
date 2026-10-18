import re

from odoo import api, fields, models

from .f3d_scene_mixin import F3D_KIND_SELECTION


def _employee_table(env):
    """barcode -> код сцени з scene_employee_codes.csv (hooks.codes з'являється в іншому воркері)."""
    try:
        from ..hooks import codes
    except ImportError:
        return {}
    return codes.employee_table(env)


class HrEmployee(models.Model):
    _name = 'hr.employee'
    _inherit = ['hr.employee', 'f3d.scene.mixin']

    _f3d_kind = 'employee'
    _rec_names_search = ['name', 'f3d_code']

    f3d_code = fields.Char(
        help="Код людини в сцені (OP-SAW-1); бейдж barcode — без дефісів")

    @api.model
    def _f3d_code_from_barcode(self, barcode, workcenter=None):
        if not barcode:
            return False
        code = _employee_table(self.env).get(barcode)
        if code:
            return code
        if workcenter and workcenter.f3d_code:
            return 'OP-' + workcenter.f3d_code
        match = re.fullmatch(r'OPW(\d+)', barcode)
        if match:
            return 'OP-W%s' % match.group(1)
        return False


class HrEmployeePublic(models.Model):
    _inherit = 'hr.employee.public'

    _rec_names_search = ['name', 'f3d_code']

    f3d_code = fields.Char(string='Код сцени', readonly=True)
    f3d_alias = fields.Char(string='Другий код сцени', readonly=True)
    f3d_kind = fields.Selection(F3D_KIND_SELECTION, string='Вид у сцені', readonly=True)
