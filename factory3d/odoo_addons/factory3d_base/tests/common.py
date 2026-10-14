from contextlib import contextmanager
from unittest import mock

from odoo.tests import TransactionCase, new_test_user


class F3DCase(TransactionCase):
    """Общие фикстуры factory3d_base (SPEC §13.1)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.company = env.company
        cls.wh = env['stock.warehouse'].search([('company_id', '=', cls.company.id)], limit=1)

        base_user = 'base.group_user'
        cls.user_reader = new_test_user(
            env, login='f3d_reader', groups=f'{base_user},factory3d_base.group_f3d_user')
        cls.user_manager = new_test_user(
            env, login='f3d_manager', groups=f'{base_user},factory3d_base.group_f3d_manager')
        cls.user_stock_mgr = new_test_user(
            env, login='f3d_stock_mgr', groups=f'{base_user},stock.group_stock_manager')
        cls.user_admin = new_test_user(
            env, login='f3d_admin', groups=f'{base_user},factory3d_base.group_f3d_admin')

        Categ = env['product.category']
        cls.categ_boards = Categ.create({'name': 'Плитні матеріали'})
        cls.categ_hdf = Categ.create({'name': 'ХДФ', 'parent_id': cls.categ_boards.id})
        cls.categ_edge = Categ.create({'name': 'Крайка'})

        Loc = env['stock.location']
        parent = cls.wh.view_location_id
        cls.loc_in = Loc.create({'name': 'Вхід-Т', 'usage': 'internal', 'location_id': parent.id})
        cls.dock_w1 = Loc.create({'name': 'Док-Т-W1', 'usage': 'internal',
                                  'location_id': parent.id, 'barcode': 'UNLOAD-T1'})
        cls.dock_e1 = Loc.create({'name': 'Док-Т-E1', 'usage': 'internal',
                                  'location_id': parent.id, 'barcode': 'DOCK-TE1'})

        cls.wc = env['mrp.workcenter'].create({'name': 'Пила-Т', 'code': 'SAW-T'})
        cls.eq = env['maintenance.equipment'].create({'name': 'Пила-Т', 'serial_no': 'SAW-T'})
        cls.emp = env['hr.employee'].create({'name': 'Оператор-Т', 'barcode': 'OPSAWT'})

    # --- хелперы (модели f3d.* появляются в следующих воркерах) ---
    def make_zone(self, code, polygon=None, **vals):
        vals.setdefault('name', f'Зона {code}')
        vals.setdefault('zone_type', 'storage')
        vals['f3d_code'] = code
        if polygon is not None:
            vals['polygon_text'] = polygon
        return self.env['f3d.zone'].create(vals)

    def make_dock(self, loc, side, no, x, y):
        loc.write({'f3d_kind': 'dock', 'f3d_side': side, 'f3d_dock_no': no,
                   'f3d_x': x, 'f3d_y': y})
        return loc

    def make_batch(self, pickings, dock=None, **vals):
        vals['picking_ids'] = [(6, 0, pickings.ids)]
        if dock:
            vals['dock_id'] = dock.id
        return self.env['stock.picking.batch'].create(vals)

    def make_picking(self, ptype, products, state='draft'):
        picking = self.env['stock.picking'].create({
            'picking_type_id': ptype.id,
            'location_id': ptype.default_location_src_id.id,
            'location_dest_id': ptype.default_location_dest_id.id,
            'move_ids': [(0, 0, {
                'product_id': p.id, 'product_uom_qty': 1, 'product_uom': p.uom_id.id,
                'location_id': ptype.default_location_src_id.id,
                'location_dest_id': ptype.default_location_dest_id.id,
            }) for p in products],
        })
        if state == 'confirmed':
            picking.action_confirm()
        return picking

    @contextmanager
    def viewer_installed(self, flag):
        from odoo.addons.factory3d_base.models.f3d_scene_mixin import F3dSceneMixin
        with mock.patch.object(F3dSceneMixin, '_f3d_viewer_installed', return_value=flag):
            yield

    @contextmanager
    def with_data_file(self, name, rows):
        from odoo.addons.factory3d_base import hooks
        with mock.patch.object(hooks, 'read_data_file', create=True,
                               side_effect=lambda n, *a, **k: rows if n == name else []):
            yield

    def snapshot_moves(self, pickings):
        return sorted(pickings.move_ids.mapped(
            lambda m: (m.id, m.product_id.id, m.product_uom_qty, m.state)))
