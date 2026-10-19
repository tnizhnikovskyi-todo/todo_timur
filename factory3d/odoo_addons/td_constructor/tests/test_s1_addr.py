from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged

from ..services import addr, cells
from .common import F3DConstructorCase, F3DConstructorHttpCase


def _slot(uid, template, prefix, x, y, rot=0, params=None, addr_value=None, **extra):
    return dict(
        {
            'uid': uid,
            'layer_id': 1,
            'template': template,
            'code_prefix': prefix,
            'x': x,
            'y': y,
            'rotation': rot,
            'params': params or {},
            'addr': addr_value or {},
        },
        **extra,
    )


def _zone(uid, cx, cy, length, width, addr_value=None, **extra):
    return _slot(uid, 'zone', uid, cx, cy, 0, {'length': length, 'width': width}, addr_value, **extra)


@tagged("post_install", "-at_install", "f3d", "f3d_constructor", "f3d_s1")
class TestAddrEngine(TransactionCase):
    """F01-01…04, F01-07, F01-08, F01-10: шаблон, сегменти, напрями, коди й колізії (чистий Python)."""

    RACK = {'bays': 3, 'levels': 2}

    def codes(self, template='pallet_rack', prefix='AB-R1', rot=0, params=None, **ctx):
        full = {'addr': None, 'zone': None, 'row': 1, 'spot': None, 'depth_mode': 'level'}
        full.update(ctx)
        if isinstance(full['addr'], dict):
            full['addr'] = addr.normalize_addr(full['addr'])
        out = cells.generate_cells(template, prefix, 0, 0, rot, params or self.RACK, None, 0, full)
        return [c['code'] for c in out]

    # --- сегменти -------------------------------------------------------------------------------------
    def test_alpha_and_num_segments(self):
        self.assertEqual(
            [addr.to_alpha(n) for n in (1, 26, 27, 52, 53, 702, 703)], ['A', 'Z', 'AA', 'AZ', 'BA', 'ZZ', 'AAA']
        )
        self.assertEqual([addr.from_alpha(t) for t in ('A', 'Z', 'AA', 'ZZ', 'AAA')], [1, 26, 27, 702, 703])
        self.assertIsNone(addr.from_alpha('a1'))
        with self.assertRaises(addr.AddrError):
            addr.to_alpha(0)
        num = {'kind': 'num', 'width': 3, 'start': 0}
        self.assertEqual((addr.format_value(num, 1), addr.format_value(num, 12)), ('000', '011'))
        self.assertEqual(addr.format_value({'kind': 'alpha', 'width': 1, 'start': 3}, 1), 'C')
        self.assertEqual(addr.format_value({'kind': 'num', 'width': 1, 'start': 1}, 'X1'), 'X1')  # код зони як є

    def test_template_words_aliases_and_skipped_words(self):
        a = addr.normalize_addr({'tpl': '{prefix} B{bay} L{level} {pos}', 'sep': '-'})
        vals = {'prefix': 'AB-R1', 'bay': 3, 'level': 2}
        self.assertEqual(addr.render_code(a, vals), 'AB-R1-B03-L2')  # слово {pos} без значення пропущено
        self.assertEqual(addr.render_code(a, dict(vals, pos=4)), 'AB-R1-B03-L2-4')
        self.assertEqual(addr.render_code(a, {'prefix': 'AB-R1', 'level': 2}), 'AB-R1-L2')  # слово B{bay} теж пропущено
        uk = addr.normalize_addr({'tpl': '{зона} {ряд} {секція} {ярус} {позиція}', 'sep': '.'})
        en = addr.normalize_addr({'tpl': '{zone} {aisle} {section} {tier} {position}', 'sep': '.'})
        vals = {'zone': 1, 'row': 2, 'bay': 3, 'level': 4, 'pos': 5}
        self.assertEqual(addr.render_code(uk, vals), 'A.02.03.4.5')
        self.assertEqual(addr.render_code(uk, vals), addr.render_code(en, vals))
        self.assertEqual(addr.tpl_segments(uk), {'zone', 'row', 'bay', 'level', 'pos'})

    def test_parse_code_roundtrip(self):
        a = addr.normalize_addr({'tpl': '{zone} {row} {bay} {level}', 'sep': '.', 'seg': {'level': {'kind': 'alpha'}}})
        code = addr.render_code(a, {'zone': 2, 'row': 7, 'bay': 12, 'level': 3})
        self.assertEqual(code, 'B.07.12.C')
        self.assertEqual(
            addr.parse_code(a, code), {'prefix': None, 'zone': 2, 'row': 7, 'bay': 12, 'level': 3, 'pos': None}
        )
        no_zone = addr.parse_code(a, '07.12.C')  # слово зони пропущено
        self.assertEqual((no_zone['zone'], no_zone['row'], no_zone['bay']), (None, 7, 12))
        self.assertIsNone(addr.parse_code(a, 'нічого'))
        with_prefix = addr.normalize_addr({'tpl': '{prefix} B{bay} L{level}'})
        self.assertEqual(addr.parse_code(with_prefix, 'AB-R1-B03-L2', 'AB-R1')['bay'], 3)
        self.assertEqual(addr.parse_code(with_prefix, 'AB-R1-B03-L2')['prefix'], 'AB-R1')

    def test_normalize_errors_and_defaults(self):
        self.assertEqual(addr.normalize_addr(None), {})
        self.assertEqual(addr.normalize_addr('legacy'), {})
        self.assertEqual(addr.normalize_addr({'row_no': 3, 'zone_code': 'X1'}), {'row_no': 3, 'zone_code': 'X1'})
        self.assertEqual(addr.normalize_addr({'legacy': True}), {'legacy': True})
        full = addr.normalize_addr({'tpl': ' {row} {bay} '})
        self.assertEqual(
            (full['tpl'], full['sep'], full['row_from'], full['bay_dir']), ('{row} {bay}', '-', 'up', 'ltr')
        )
        self.assertEqual(full['seg']['bay'], {'kind': 'num', 'width': 2, 'start': 1})
        for bad in (
            {'tpl': 'abc'},
            {'tpl': '{foo}'},
            {'tpl': '{bay} {section}'},  # той самий сегмент двічі (синонім)
            {'tpl': '{bay}', 'sep': 'abcd'},
            {'tpl': '{bay}', 'sep': ' '},
            {'tpl': '{bay}', 'row_from': 'x'},
            {'tpl': '{bay}', 'seg': {'bay': {'width': 9}}},
            {'tpl': '{bay}', 'seg': {'bay': {'kind': 'alpha', 'start': 0}}},
            {'tpl': 'ря{bay}'},
            {'tpl': '{bay' + 'x' * 70 + '}'},
            {'row_no': 0},
            {'zone_code': 'TOOLONGCODE'},
            'x',
            [],
        ):
            with self.assertRaises(addr.AddrError, msg=str(bad)):
                addr.normalize_addr(bad)
        self.assertEqual(addr.preset_addr('legacy'), {})
        for key in addr.PRESETS:
            addr.preset_addr(key)
        with self.assertRaises(addr.AddrError):
            addr.preset_addr('nope')

    def test_inheritance_nearest_wins(self):
        site, zone, own = {'tpl': '{row}'}, {'tpl': '{bay}'}, {'tpl': '{level}'}
        norm = addr.normalize_addr
        self.assertEqual(addr.effective_addr(norm(own), norm(zone), norm(site))['tpl'], '{level}')
        self.assertEqual(addr.effective_addr({}, norm(zone), norm(site))['tpl'], '{bay}')
        self.assertEqual(
            addr.effective_addr({'row_no': 3}, {}, norm(site))['tpl'], '{row}'
        )  # закріплений номер — не налаштування
        self.assertIsNone(addr.effective_addr({'legacy': True}, norm(zone), norm(site)))
        self.assertIsNone(addr.effective_addr({}, {}, {}))

    # --- напрями (F01-04) ----------------------------------------------------------------------------
    def test_legacy_equivalents_do_not_change_codes(self):
        legacy = self.codes()
        self.assertEqual(
            legacy, ['AB-R1-B01-L1', 'AB-R1-B01-L2', 'AB-R1-B02-L1', 'AB-R1-B02-L2', 'AB-R1-B03-L1', 'AB-R1-B03-L2']
        )
        like = addr.preset_addr('prefix_bay_level')
        self.assertEqual(self.codes(addr=like), legacy)
        letters = cells.generate_cells('pallet_rack', 'AB-R1', 0, 0, 0, dict(self.RACK, code_style='bay_letter'))
        self.assertEqual(self.codes(addr=addr.preset_addr('prefix_bay_letter')), [c['code'] for c in letters])
        stack = cells.generate_cells('floor_stack', 'ST', 0, 0, 0, {'rows': 2, 'cols': 2})
        like_stack = {'tpl': '{prefix} {pos}{bay}', 'seg': {'pos': {'width': 2}, 'bay': {'kind': 'alpha'}}}
        self.assertEqual(
            self.codes('floor_stack', 'ST', params={'rows': 2, 'cols': 2}, addr=like_stack), [c['code'] for c in stack]
        )

    def test_bay_direction_rotation_snake_odd_even_level_down(self):
        base = {'tpl': '{row} {bay} {level}', 'sep': '.'}
        self.assertEqual(self.codes(addr=base, params={'bays': 3, 'levels': 1}), ['01.01.1', '01.02.1', '01.03.1'])
        self.assertEqual(
            self.codes(addr=dict(base, bay_dir='rtl'), params={'bays': 3, 'levels': 1}),
            ['01.03.1', '01.02.1', '01.01.1'],
        )
        # у повернутих 90° нумерація «зверху вниз»: перша за X локальна секція — внизу, тож має останній номер
        self.assertEqual(
            self.codes(addr=base, rot=90, params={'bays': 3, 'levels': 1}), ['01.03.1', '01.02.1', '01.01.1']
        )
        self.assertEqual(
            self.codes(addr=base, rot=270, params={'bays': 3, 'levels': 1}), ['01.01.1', '01.02.1', '01.03.1']
        )
        self.assertEqual(
            self.codes(addr=base, rot=180, params={'bays': 3, 'levels': 1}), ['01.03.1', '01.02.1', '01.01.1']
        )
        snake = dict(base, row_mode='snake')
        odd = self.codes(addr=snake, row=1, params={'bays': 2, 'levels': 1})
        even = self.codes(addr=snake, row=2, params={'bays': 2, 'levels': 1})
        self.assertEqual((odd, even), (['01.01.1', '01.02.1'], ['02.02.1', '02.01.1']))
        oe = dict(base, bay_dir='odd_even')
        self.assertEqual(self.codes(addr=oe, row=1, params={'bays': 3, 'levels': 1}), ['01.01.1', '01.03.1', '01.05.1'])
        self.assertEqual(self.codes(addr=oe, row=2, params={'bays': 3, 'levels': 1}), ['02.02.1', '02.04.1', '02.06.1'])
        both = self.codes(addr=oe, row=1, params={'bays': 2, 'levels': 1, 'double_sided': True})
        self.assertEqual(both, ['01.01.1', '01.03.1', '01.02.1', '01.04.1'])  # сторона 1 — непарні, сторона 2 — парні
        down = self.codes(addr=dict(base, level_dir='down'), params={'bays': 1, 'levels': 3})
        self.assertEqual(down, ['01.01.3', '01.01.2', '01.01.1'])

    def test_two_sided_row_numbers_continue(self):
        out = self.codes(
            addr={'tpl': '{prefix} B{bay} L{level}'}, params={'bays': 2, 'levels': 1, 'double_sided': True}
        )
        self.assertEqual(out, ['AB-R1-B01-L1', 'AB-R1-B02-L1', 'AB-R1-B03-L1', 'AB-R1-B04-L1'])
        legacy = self.codes(params={'bays': 2, 'levels': 1, 'double_sided': True})
        self.assertEqual(legacy, out)

    # --- глибина локацій (F01-10) ---------------------------------------------------------------------
    def test_depth_cell_splits_levels(self):
        params = {'bays': 1, 'levels': 2, 'cells_per_level': 3}
        legacy = self.codes(params=params, depth_mode='cell')
        self.assertEqual(
            legacy,
            [
                'AB-R1-B01-L1-1',
                'AB-R1-B01-L1-2',
                'AB-R1-B01-L1-3',
                'AB-R1-B01-L2-1',
                'AB-R1-B01-L2-2',
                'AB-R1-B01-L2-3',
            ],
        )
        out = cells.generate_cells(
            'pallet_rack',
            'AB-R1',
            0,
            0,
            0,
            dict(params, positions_per_bay=3, bay_width=3.0),
            None,
            0,
            {'addr': None, 'depth_mode': 'cell'},
        )
        self.assertEqual([round(c['l'], 3) for c in out], [1.0] * 6)
        self.assertEqual([c['capacity'] for c in out], [1.0] * 6)  # місткість ярусу ділиться між локаціями
        self.assertEqual(round(out[1]['x'] - out[0]['x'], 3), 1.0)
        reverse = self.codes(addr={'tpl': '{bay} {level} {pos}'}, rot=180, params=params, depth_mode='cell')
        self.assertEqual(
            reverse[:3], ['01-1-3', '01-1-2', '01-1-1']
        )  # у повернутих 180° позиції рахуються справа наліво
        self.assertEqual(cells.count_cells('pallet_rack', 'P', params, None, {'addr': None, 'depth_mode': 'cell'}), 6)
        self.assertEqual(cells.count_cells('pallet_rack', 'P', params), 2)

    # --- місця на підлозі (F01-08) ----------------------------------------------------------------------
    def test_floor_spot_numbering_by_first_available_segment(self):
        self.assertEqual(self.codes('floor_spot', 'DOCK-IN', params={}), ['DOCK-IN'])  # legacy: код = префікс
        pos = {'tpl': '{zone} {pos}', 'sep': '.'}
        self.assertEqual(self.codes('floor_spot', 'FS', params={}, addr=pos, zone=1, spot=7), ['A.7'])
        row_first = {'tpl': '{zone} {row} {bay} {level}', 'sep': '-'}
        self.assertEqual(self.codes('floor_spot', 'FS', params={}, addr=row_first, zone=2, spot=3), ['B-03'])
        bay_only = {'tpl': '{prefix} {bay}', 'sep': '/'}
        self.assertEqual(self.codes('floor_spot', 'FS', params={}, addr=bay_only, spot=4), ['FS/04'])

    # --- контекст сцени --------------------------------------------------------------------------------
    def test_context_rows_by_geometry_pins_and_zones(self):
        site = {'tpl': '{zone} {row} {bay} {level}'}
        slots = [
            _zone('z1', 0, 0, 20, 20),
            _slot('r1', 'pallet_rack', 'P1', 5, 3, 0, {'bays': 2, 'levels': 1}),
            _slot('r2', 'pallet_rack', 'P2', 5, -4, 0, {'bays': 2, 'levels': 1}),
            _slot('r3', 'pallet_rack', 'P3', 40, 0, 0, {'bays': 2, 'levels': 1}),  # поза зоною: свій ряд 1 без зони
            _slot('f1', 'floor_spot', 'FS1', -3, 5),
            _slot('f2', 'floor_spot', 'FS2', -3, -5),
        ]
        ctx = addr.address_context(slots, site)
        self.assertEqual([ctx[k]['row'] for k in ('r2', 'r1', 'r3')], [1, 2, 1])
        self.assertEqual([ctx[k]['zone'] for k in ('r1', 'r2', 'r3')], [1, 1, None])
        self.assertEqual([ctx[k]['spot'] for k in ('f2', 'f1')], [1, 2])
        codes = addr.scene_codes(slots, site)
        self.assertEqual(codes['r2'][0], 'A-01-01-1')
        self.assertEqual(codes['r3'][0], '01-01-1')  # слово зони пропущено
        # напрям рядів: down — навпаки
        down = addr.address_context(slots, dict(site, row_from='down'))
        self.assertEqual([down[k]['row'] for k in ('r1', 'r2')], [1, 2])
        # закріплений номер лишається, нові беруть вільні
        pinned = [dict(s, addr={'row_no': 5}) if s['uid'] == 'r1' else s for s in slots]
        ctx = addr.address_context(pinned, site)
        self.assertEqual((ctx['r1']['row'], ctx['r2']['row']), (5, 1))
        # код зони замість номера, власні налаштування зони, глибина зони
        zoned = [
            dict(s, addr={'zone_code': 'X1', 'tpl': '{prefix} {bay}'}, depth_mode='cell') if s['uid'] == 'z1' else s
            for s in slots
        ]
        ctx = addr.address_context(zoned, site)
        self.assertEqual(ctx['r1']['zone'], 'X1')
        self.assertEqual(ctx['r1']['addr']['tpl'], '{prefix} {bay}')
        self.assertEqual((ctx['r1']['depth_mode'], ctx['r3']['depth_mode']), ('cell', 'level'))
        # найвужча (вкладена) зона виграє
        nested = slots + [_zone('z2', 5, 3, 4, 4, {'tpl': '{row}'})]
        ctx = addr.address_context(nested, site)
        self.assertEqual(ctx['r1']['addr']['tpl'], '{row}')
        self.assertEqual(ctx['r2']['addr']['tpl'], '{zone} {row} {bay} {level}')

    def test_context_without_addressing_is_legacy(self):
        slots = [_slot('r1', 'pallet_rack', 'P1', 5, 3, 0, {'bays': 2, 'levels': 1})]
        ctx = addr.address_context(slots, {})['r1']
        self.assertIsNone(ctx['addr'])
        self.assertEqual(addr.scene_codes(slots, {})['r1'], ['P1-B01-L1', 'P1-B02-L1'])

    # --- колізії, довжина, попередній перегляд ------------------------------------------------------------
    def test_collisions_preview_and_length(self):
        slots = [
            _slot('a', 'pallet_rack', 'A1', 0, 0, 0, {'bays': 2, 'levels': 1}),
            _slot('b', 'pallet_rack', 'A2', 0, 5, 0, {'bays': 2, 'levels': 1}),
        ]
        by_slot = addr.scene_codes(slots, {'tpl': '{bay} {level}'})  # без {row}: коди двох рядів збігаються
        found = addr.conflicts(by_slot)
        self.assertEqual(sorted(found), ['01-1', '02-1'])
        self.assertEqual(sorted(found['01-1']), ['a', 'b'])
        self.assertEqual(addr.conflicts(addr.scene_codes(slots, {'tpl': '{row} {bay} {level}'})), {})
        self.assertEqual(addr.conflicts({'a': ['X', 'Y']}, occupied={'Y'}), {'Y': ['a']})  # зайнятий поза проєктом
        pv = addr.preview(['C%d' % i for i in range(25)], ['C%d' % i if i < 5 else 'old' for i in range(25)])
        self.assertEqual((len(pv['first']), pv['last'], pv['total'], pv['changed']), (10, 'C24', 25, 20))
        self.assertEqual(addr.preview(['A', 'B', 'A', 'A'])['duplicates'], ['A'])
        self.assertEqual(addr.preview(['X' * 33])['too_long'], ['X' * 33])
        with self.assertRaises(cells.CellsError):
            cells.generate_cells(
                'pallet_rack',
                'LONG-PREFIX-LONG-PREFIX-X',
                0,
                0,
                0,
                {'bays': 1, 'levels': 1},
                None,
                0,
                {'addr': addr.normalize_addr({'tpl': '{prefix} {bay} {level}', 'sep': '---'}), 'row': 1},
            )

    def test_location_vals_flat_and_row(self):
        a = addr.normalize_addr({'tpl': '{zone} {row} {bay} {level}'})
        vals = {'zone': 1, 'row': 3, 'bay': 12, 'level': 2}
        code = addr.render_code(a, vals)
        flat = addr.location_vals(code, vals, a, 'flat')
        self.assertEqual(
            flat, {'name': 'A-03-12-2', 'barcode': 'A-03-12-2', 'td_row': 3, 'td_bay': 12, 'td_level': 2, 'td_pos': 0}
        )
        self.assertEqual(addr.location_vals(code, vals, a, 'row')['name'], '2')
        self.assertEqual(addr.location_vals(code, vals, a, 'row')['barcode'], 'A-03-12-2')


@tagged("post_install", "-at_install", "f3d", "f3d_constructor", "f3d_s1")
class TestAddrModels(F3DConstructorCase):
    """F01 у моделях: R-22 для addr, коди за адресацією, перенумерація (overrides, розміщення), закріплення."""

    def storage_rack(self, prefix, x, y, **params):
        return self.make_slot(prefix=prefix, x=x, y=y, bays=2, levels=2, **params)

    def test_r22_validation(self):
        slot = self.storage_rack('AD-1', 10, 5)
        with self.assertRaises(ValidationError):
            slot.addr = {'tpl': '{foo}'}
        with self.assertRaises(ValidationError):
            self.site.addr = {'tpl': 'abc'}
        slot.addr = {'tpl': ' {prefix} B{bay} '}
        self.assertEqual(slot.addr['tpl'], '{prefix} B{bay}')  # нормалізовано з умовчаннями
        self.assertEqual(slot.addr['sep'], '-')

    def test_site_addr_changes_codes_and_remaps_overrides_and_placements(self):
        slot = self.storage_rack('AD-2', 10, 5)
        self.assertEqual([c['code'] for c in slot._td_cells()][:2], ['AD-2-B01-L1', 'AD-2-B01-L2'])
        slot.overrides = {'AD-2-B02-L2': {'capacity': 9.0}, 'AD-2-B01-L1': {'disabled': True}}
        placement = self.make_placement(kind='storage', code='PL-1', slot_id=slot.id, cell_code='AD-2-B02-L2')
        self.assertEqual(slot.cell_count, 3)
        self.site._td_apply_addr({'addr': {'tpl': '{row} {bay} {level}', 'sep': '.'}}, renumber='all')
        codes = [c['code'] for c in slot._td_cells()]
        self.assertEqual(codes, ['01.01.2', '01.02.1', '01.02.2'])  # перша комірка вимкнена
        self.assertEqual(slot.overrides, {'01.02.2': {'capacity': 9.0}, '01.01.1': {'disabled': True}})
        self.assertEqual(placement.cell_code, '01.02.2')
        self.assertEqual(slot.cell_count, 3)
        self.site._td_apply_addr({'addr': {}}, renumber='all')  # назад до legacy
        self.assertEqual(placement.cell_code, 'AD-2-B02-L2')
        self.assertIn('AD-2-B01-L1', slot.overrides)

    def test_slot_and_zone_level_settings_and_depth(self):
        self.layers['storage'].allowed_slot_type_ids = False  # зона й стелаж в одному шарі
        zone = self.env['td.slot'].create(
            {
                'layer_id': self.layers['storage'].id,
                'template': 'zone',
                'code_prefix': 'ZN-1',
                'params': {'polygon': [[0, 0], [30, 0], [30, 30], [0, 30]]},
            }
        )
        slot = self.storage_rack('AD-3', 10, 5, cells_per_level=2)
        self.assertEqual(slot.cell_count, 4)
        zone.write({'addr': {'tpl': '{zone} {row} {bay} {level} {pos}', 'zone_code': 'W'}, 'depth_mode': 'cell'})
        self.assertEqual(slot.cell_count, 8)
        self.assertEqual([c['code'] for c in slot._td_cells()][:2], ['W-01-01-1-1', 'W-01-01-1-2'])
        slot.addr = {'legacy': True}  # власне «як зараз» перебиває зону
        self.assertEqual(
            [c['code'] for c in slot._td_cells()][:2], ['AD-3-B01-L1-1', 'AD-3-B01-L1-2']
        )  # глибина — від зони
        slot.depth_mode = 'level'
        self.assertEqual(slot.cell_count, 4)

    def test_apply_new_pins_published_slots(self):
        old = self.storage_rack('AD-4', 10, 5)
        new = self.storage_rack('AD-5', 20, 5)
        self.env['stock.location'].create(
            {
                'name': 'AD-4-B01-L1',
                'usage': 'internal',
                'barcode': 'AD-4-B01-L1',
                'td_site_id': self.site.id,
                'td_slot_uid': old.uid,
            }
        )
        result = self.site._td_apply_addr({'addr': {'tpl': '{row} {bay} {level}', 'sep': '.'}}, renumber='new')
        self.assertEqual(result['pinned'], 1)
        self.assertEqual(
            old.addr.get('legacy'), True
        )  # опублікований: лишився зі старими кодами (legacy) і закріпленим номером
        self.assertEqual(old.addr['row_no'], 1)
        self.assertEqual([c['code'] for c in old._td_cells()][0], 'AD-4-B01-L1')
        self.assertEqual(
            [c['code'] for c in new._td_cells()][0], '02.01.1'
        )  # новий: за шаблоном, наступний вільний номер

    def test_stock_location_address_helpers(self):
        loc = self.env['stock.location'].create(
            {'name': 'L-X', 'usage': 'internal', 'td_row': 1, 'td_bay': 2, 'td_level': 3, 'td_pos': 4}
        )
        self.assertEqual((loc.td_row, loc.td_bay, loc.td_level, loc.td_pos), (1, 2, 3, 4))
        with self.assertRaises(ValidationError):
            loc.td_row = -1
        vals = self.env['stock.location']._td_address_vals('A-01-02-3', {'row': 1, 'bay': 2, 'level': 3})
        self.assertEqual((vals['name'], vals['barcode'], vals['td_bay']), ('A-01-02-3', 'A-01-02-3', 2))


@tagged("post_install", "-at_install", "f3d", "f3d_constructor", "f3d_s1")
class TestSiteAddrApi(F3DConstructorHttpCase):
    """Маршрут `/site/addr`: запис полів td.site проєктувальником за правилами API-01…10 (R-11, Q2)."""

    ADDR = {'tpl': '{row} {bay} {level}', 'sep': '.'}

    def login(self, user):
        from .common import PASSWORD

        self.authenticate(user.login, PASSWORD)

    def test_manager_and_designers(self):
        slot = self.make_slot(prefix='AA-1', bays=2, levels=1)
        self.login(self.u_manager)
        res = self.rpc(
            '/f3d/constructor/site/addr', site_id=self.site.id, addr=self.ADDR, loc_tree='row', depth_mode='cell'
        )
        self.assertTrue(res['ok'], res)
        self.assertEqual(
            (res['loc_tree'], res['depth_mode'], res['addr']['tpl']), ('row', 'cell', '{row} {bay} {level}')
        )
        self.assertEqual(self.site.loc_tree, 'row')
        load = self.rpc('/f3d/constructor/load', site_id=self.site.id)
        self.assertEqual(
            (load['site']['addr']['sep'], load['site']['loc_tree'], load['site']['depth_mode']), ('.', 'row', 'cell')
        )
        self.assertEqual(load['slots'][0]['id'], slot.id)
        # комірник редагує шар «Склади»: може змінити адресацію (чернетка), але не ієрархію опублікованої площадки
        self.login(self.u_store)
        res = self.rpc('/f3d/constructor/site/addr', site_id=self.site.id, addr={}, depth_mode='level')
        self.assertTrue(res['ok'], res)
        self.assertFalse(self.site.addr)
        self.env['stock.location'].create(
            {'name': 'AA-1-B01-L1', 'usage': 'internal', 'td_site_id': self.site.id, 'td_slot_uid': slot.uid}
        )
        res = self.rpc('/f3d/constructor/site/addr', site_id=self.site.id, addr=self.ADDR, renumber='all')
        self.assertEqual((res['ok'], res['code']), (False, 'rights'))  # «перенумерувати все» — менеджеру (Q2)
        res = self.rpc('/f3d/constructor/site/addr', site_id=self.site.id, loc_tree='section')
        self.assertEqual(res['code'], 'rights')
        res = self.rpc('/f3d/constructor/site/addr', site_id=self.site.id, addr=self.ADDR)  # 'new' за замовчуванням
        self.assertTrue(res['ok'], res)
        self.assertEqual(res['pinned'], 1)

    def test_rights_and_validation(self):
        self.login(self.u_plain)  # лише «перегляд»
        res = self.rpc('/f3d/constructor/site/addr', site_id=self.site.id, addr=self.ADDR)
        self.assertEqual((res['ok'], res['code']), (False, 'rights'))
        self.login(self.u_manager)
        for kwargs, code in (
            ({'addr': {'tpl': '{foo}'}}, 'validation'),
            ({'addr': 'x'}, 'validation'),
            ({'loc_tree': 'tree'}, 'validation'),
            ({'depth_mode': 'x'}, 'validation'),
            ({'addr': self.ADDR, 'renumber': 'sometimes'}, 'validation'),
            ({}, 'validation'),
        ):
            res = self.rpc('/f3d/constructor/site/addr', site_id=self.site.id, **kwargs)
            self.assertEqual((res['ok'], res['code']), (False, code), kwargs)
        self.assertEqual(self.rpc('/f3d/constructor/site/addr', site_id=0, addr={})['code'], 'not_found')
        self.assertFalse(self.site.addr)  # хибні запити нічого не записали

    def test_slot_addr_saved_through_api04(self):
        slot = self.make_slot(prefix='AA-2', bays=2, levels=1)
        self.login(self.u_manager)
        ops = [
            {
                'op': 'write',
                'model': 'td.slot',
                'id': slot.id,
                'vals': {'addr': {'tpl': '{prefix} {bay}'}, 'depth_mode': 'cell'},
            }
        ]
        res = self.rpc('/f3d/constructor/save', site_id=self.site.id, ops=ops)
        self.assertTrue(res['ok'], res)
        slot.invalidate_recordset()
        self.assertEqual((slot.addr['tpl'], slot.depth_mode), ('{prefix} {bay}', 'cell'))
        bad = [{'op': 'write', 'model': 'td.slot', 'id': slot.id, 'vals': {'addr': {'tpl': '{nope}'}}}]
        res = self.rpc('/f3d/constructor/save', site_id=self.site.id, ops=bad)
        self.assertEqual((res['ok'], res['code']), (False, 'validation'))
