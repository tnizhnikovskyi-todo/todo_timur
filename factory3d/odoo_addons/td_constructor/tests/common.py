import json
import struct

from odoo import Command
from odoo.tests import HttpCase, TransactionCase

PASSWORD = 'f3dpass-Test1'
GROUP = 'td_constructor.group_td_constructor_%s'


def make_glb(triangles=24, size=(1.0, 0.5, 2.0), pad_to=0):
    """Мінімальний GLB 2.0: один меш без індексів (3 вершини на трикутник), габарит `size` у метрах.

    BIN доповнюється до `pad_to` байтів."""
    verts = []
    for _ in range(triangles):
        verts += [(0.0, 0.0, 0.0), (size[0], 0.0, 0.0), (size[0], size[1], size[2])]
    binary = b''.join(struct.pack('<3f', *v) for v in verts)
    gltf = {
        'asset': {'version': '2.0'},
        'scene': 0,
        'scenes': [{'nodes': [0]}],
        'nodes': [{'mesh': 0}],
        'meshes': [{'primitives': [{'attributes': {'POSITION': 0}}]}],
        'accessors': [
            {
                'bufferView': 0,
                'componentType': 5126,
                'count': len(verts),
                'type': 'VEC3',
                'min': [0.0, 0.0, 0.0],
                'max': [float(size[0]), float(size[1]), float(size[2])],
            }
        ],
        'bufferViews': [{'buffer': 0, 'byteLength': len(binary)}],
        'buffers': [{'byteLength': len(binary)}],
    }
    if pad_to > len(binary):
        binary += b'\0' * (pad_to - len(binary))
        gltf['buffers'][0]['byteLength'] = len(binary)
    text = json.dumps(gltf).encode()
    text += b' ' * (-len(text) % 4)
    binary += b'\0' * (-len(binary) % 4)
    total = 12 + 8 + len(text) + 8 + len(binary)
    return (
        struct.pack('<III', 0x46546C67, 2, total)
        + struct.pack('<II', len(text), 0x4E4F534A)
        + text
        + struct.pack('<II', len(binary), 0x004E4942)
        + binary
    )


class F3DConstructorMixin:
    """Спільні фікстури: компанія, користувачі чотирьох ролей, площадка з 5 шарами (R-23).

    Також локації й паспорт із варіантом."""

    @classmethod
    def _td_setup(cls):
        env = cls.env
        cls.company = env.company
        cls.u_manager = cls._td_user('f3d_manager', ['manager'])
        cls.u_tech = cls._td_user('f3d_tech', ['technologist'])
        cls.u_store = cls._td_user('f3d_store', ['storekeeper'])
        cls.u_eng = cls._td_user('f3d_eng', ['engineer'])
        cls.u_plain = cls._td_user('f3d_plain', [])
        cls.site = env['td.site'].with_context(f3d_blank=True).create({'name': "Тестова площадка", 'code': 'TST'})
        cls.layers = {layer.kind: layer for layer in cls.site.layer_ids}
        cls.wh_stock = env['stock.location'].search([('complete_name', '=', 'WH/Stock')], limit=1)
        if not cls.wh_stock:
            cls.wh_stock = env['stock.location'].create({'name': 'Stock', 'usage': 'internal'})
        cls.wh_fg = env['stock.location'].create({'name': 'FG', 'usage': 'internal', 'location_id': cls.wh_stock.id})
        cls.site.default_parent_location_id = cls.wh_stock
        cls.passport = env['td.equipment.passport'].create(
            {
                'role': 'test_machine',
                'manufacturer': "Тест",
                'model': "Верстат",
                'td_category': 'machine',
                'dim_l_mm': 4000,
                'dim_w_mm': 1200,
                'dim_h_mm': 1600,
                'power_kw': 11,
            }
        )
        cls.variant = env['td.equipment.variant'].create(
            {'passport_id': cls.passport.id, 'name': "Стандарт", 'weight_kg': 2400, 'service_front_mm': 1000}
        )

    @classmethod
    def _td_user(cls, login, roles):
        groups = [cls.env.ref('base.group_user').id, cls.env.ref('td_factory3d.group_td_user').id]
        groups += [cls.env.ref(GROUP % role).id for role in roles]
        return (
            cls.env['res.users']
            .with_context(no_reset_password=True)
            .create(
                {
                    'name': login,
                    'login': login,
                    'email': '%s@example.com' % login,
                    'password': PASSWORD,
                    'group_ids': [Command.set(groups)],
                }
            )
        )

    # --- помічники ---------------------------------------------------------------------------------
    def make_slot(self, kind='storage', prefix='TQ-R1', template='pallet_rack', x=30.0, y=10.0, rotation=0, **params):
        defaults = (
            {
                'bays': 4,
                'levels': 2,
                'bay_width': 2.7,
                'depth': 1.1,
                'level_height': 1.5,
                'positions_per_bay': 3,
                'max_load_kg': 1000,
            }
            if template == 'pallet_rack'
            else {}
        )
        defaults.update(params)
        return self.env['td.slot'].create(
            {
                'layer_id': self.layers[kind].id,
                'template': template,
                'code_prefix': prefix,
                'x_m': x,
                'y_m': y,
                'rotation': rotation,
                'params': defaults,
                'parent_location_id': self.wh_fg.id,
            }
        )

    def make_placement(self, kind='production', code='SAW-9', x=20.0, y=10.0, rotation=0, variant=None, **extra):
        return self.env['td.placement'].create(
            dict(
                {
                    'layer_id': self.layers[kind].id,
                    'variant_id': (variant or self.variant).id,
                    'code': code,
                    'name': "Верстат %s" % code,
                    'x_m': x,
                    'y_m': y,
                    'rotation': rotation,
                },
                **extra,
            )
        )

    def advance_clock(self, seconds=2):
        """`write_date` = час транзакції; у тесті (одна транзакція) зсуваємо годинник, щоб etag відрізнявся (R-21)."""
        from datetime import timedelta

        cr = self.env.cr
        cr._now = cr.now() + timedelta(seconds=seconds)


class F3DConstructorCase(F3DConstructorMixin, TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._td_setup()


class F3DConstructorHttpCase(F3DConstructorMixin, HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._td_setup()

    def rpc(self, route, **params):
        return self.make_jsonrpc_request(route, params)
