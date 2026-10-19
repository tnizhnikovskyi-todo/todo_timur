"""R-12, R-13, F02: план публікації (diff → підтвердження → створення/зміна stock.location, maintenance.equipment,
mrp.workcenter, правила поповнення й розміщення), журнал операцій і відкат (MERGE.md §2.6).

Вигляди рядків плану (`kind`): `create` (з батьками: `depends_code`), `move` (інший батько), `rename` (ім'я/код),
`attrs` (атрибути: штрихкод, вид, місткість, категорія зберігання, стратегія списання, відновлення з архіву), `update`
(обладнання й робочі центри), `archive`. Порядок застосування: створення (батьки раніше) → перенесення →
перейменування → атрибути → обладнання → архів → правила поповнення → правила розміщення. Категорії зберігання в план не
входять (API-12, окремий виклик із підтвердженням).

Збіг із наявними записами — за `td_code`, потім `barcode` (комірки) / `serial_no` (обладнання): дублікатів не створюємо,
нічого не видаляємо. Зайве — лише пропозиція архівації (`selected=False`), тільки для записів із `td_site_id` площадки.
Читання плану — під `sudo()`; публікація — під `sudo()` лише після перевірки групи менеджера й стоп-крана (§4.4).

Журнал: `td.publish.op` (`before`/`after` кожної операції); відкат (`rollback_version`) виконує обернені операції лише в
Odoo, чернетка не змінюється. Правила поповнення й розміщення плануються й застосовуються з `capacity.py` / `putaway.py`
(реєстри `PLAN_BUILDERS` і `APPLIERS` цього модуля).
"""

import datetime
import logging

from psycopg2 import errors as pg_errors

from odoo import Command, fields
from odoo.exceptions import UserError

from . import addr as addr_mod, cells as cells_mod, geometry as geo, odoo_sync, snapshot, state as state_mod
from .registry import CHECKS, PLAN_BUILDERS
from .schemas import SCENE_ROLE_PREFIX

_logger = logging.getLogger(__name__)

PARAM_PUBLISH = 'td.constructor.publish_enabled'
LOCATION, EQUIPMENT, WORKCENTER = 'stock.location', 'maintenance.equipment', 'mrp.workcenter'
ORDERPOINT, PUTAWAY = 'stock.warehouse.orderpoint', 'stock.putaway.rule'
CHANGE_KINDS = ('create', 'move', 'rename', 'attrs', 'update')
LOCATION_KINDS = ('move', 'rename', 'attrs')
PART_FIELDS = ('td_row', 'td_bay', 'td_level', 'td_pos')
# застосовувачі рядків правил (реєструють capacity.py / putaway.py):
# `res_model -> fn(site, lines, records, ops) -> [entry]`
APPLIERS = {}
LOG_OP = {'update': 'attrs'}  # вид рядка → операція журналу


class PublishError(UserError):
    """Очікувана відмова публікації.

    `code` — код API-07 (disabled, blocked, no_changes, conflict_codes, conflict, rollback, rights)."""

    def __init__(self, code, message, issues=None):
        super().__init__(message)
        self.code = code
        self.issues = issues or []


def publish_enabled(env):
    return env['ir.config_parameter'].sudo().get_param(PARAM_PUBLISH) == 'True'


def _issue(check, severity, message, codes=(), layer_id=False):
    return {
        'check': check,
        'severity': severity,
        'layer_id': layer_id or False,
        'codes': list(codes),
        'message': message,
    }


def _fmt(value):
    if hasattr(value, '_name') and hasattr(value, 'display_name'):
        return value.display_name or '—'
    if value in (False, None, ''):
        return '—'
    if isinstance(value, float) and value == int(value):
        return str(int(value))
    return str(value)


def read_values(record, names):
    """`{поле: значення}` для журналу: many2one → id (або False), набори → список id, дата → рядок."""
    out = {}
    for name in names:
        field = record._fields[name]
        value = record[name]
        if field.type == 'many2one':
            value = value.id or False
        elif field.type in ('many2many', 'one2many'):
            value = list(value.ids)
        elif isinstance(value, datetime.datetime | datetime.date):
            value = str(value)
        out[name] = value
    return out


def _diff_text(record, vals):
    parts = []
    for key, new in vals.items():
        field = record._fields[key]
        old = record[key]
        if field.type == 'many2one':
            new = record.env[field.comodel_name].browse(new) if new else record.env[field.comodel_name]
        elif field.type == 'many2many':
            old = ", ".join(old.mapped('display_name')) or '—'
            new = ", ".join(record.env[field.comodel_name].browse(new).mapped('display_name')) or '—'
        parts.append("%s: %s → %s" % (key, _fmt(old), _fmt(new)))
    return "; ".join(parts)


def write_vals(vals, record=None, model=None):
    """Значення для `create`/`write`: у рядках плану й журналі many2many — списки id, тут вони стають `Command.set`."""
    fields_ = (record if record is not None else model)._fields
    return {
        key: [Command.set(list(value))]
        if fields_.get(key) is not None and fields_[key].type == 'many2many' and isinstance(value, list | tuple)
        else value
        for key, value in vals.items()
    }


def _line(
    kind,
    res_model,
    code,
    name,
    vals=None,
    record=None,
    source_uid='',
    changes='',
    extra=None,
    depends_code='',
    scope_uid='',
):
    """Рядок плану. `before` — прежні значення полів `vals` у записі Odoo (для показу в майстрі)."""
    vals = vals or {}
    before = read_values(record, vals) if record is not None and vals else {}
    return {
        'kind': kind,
        'res_model': res_model,
        'code': code,
        'name': name or code,
        'res_id': record.id if record else 0,
        'source_uid': source_uid,
        'changes': changes,
        'vals': vals,
        'selected': kind != 'archive' or bool(extra and extra.get('explicit')),
        'blocked': False,
        'blocked_reason': '',
        'extra': extra or {},
        'depends_code': depends_code or '',
        'scope_uid': scope_uid or source_uid or '',
        'before': before,
    }


def line_key(line):
    """Ключ рядка: `(модель, код, вид)`; запис може мати кілька рядків різного виду (перенесення + атрибути)."""
    return (line['res_model'], line['code'], line['kind'])


def _block(line, reason, flag):
    line['blocked'] = True
    line['blocked_reason'] = reason
    line['extra'].setdefault('flags', []).append(flag)


# --- зони й успадкування (F03-02, F03-06) -------------------------------------------------------------------


def _zones(site):
    """Зони площадки (місця-полігони) для успадкування категорії зберігання й стратегії списання вниз:
    `[(зона, многокутник, рамка, площа)]`."""
    zones = []
    for zone in site.env['td.slot'].search(
        [('site_id', '=', site.id), ('template', '=', 'zone'), ('layer_id.active', '=', True)]
    ):
        poly = (zone.params or {}).get('polygon')
        if poly:
            xs, ys = [p[0] for p in poly], [p[1] for p in poly]
            zones.append((zone, poly, (min(xs), min(ys), max(xs), max(ys)), _area(poly)))
    return zones


def _area(poly):
    """Площа многокутника (формула шнурівки), м²."""
    return abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1], strict=True))) / 2.0


def zone_chain(zones, x, y):
    """Зони, що містять точку, від найменшої до найбільшої (вкладена зона перекриває далеку)."""
    hit = [
        (area, zone)
        for zone, poly, (x0, y0, x1, y1), area in zones
        if x0 - 0.001 <= x <= x1 + 0.001 and y0 - 0.001 <= y <= y1 + 0.001 and geo.polygon_contains(poly, (x, y))
    ]
    return [zone for _area_, zone in sorted(hit, key=lambda item: item[0])]


def zone_of(zones, x, y):
    chain = zone_chain(zones, x, y)
    return chain[0] if chain else None


def inherited(field, slot, chain):
    """Категорія зберігання / стратегія: своя в місця, інакше найближчої зони ланцюжка з заданим значенням (вниз)."""
    if slot[field]:
        return slot[field]
    zones = chain if isinstance(chain, list | tuple) else ([chain] if chain else [])
    for zone in zones:
        if zone[field]:
            return zone[field]
    return slot[field]


# --- локації ---------------------------------------------------------------------------------------------


def is_scene_passport(passport):
    """Зведений паспорт «Об'єкти сцени · …» (не каталожний): наявному обладнанню його не записуємо."""
    return bool(passport) and (passport.role or '').startswith(SCENE_ROLE_PREFIX)


def _match(code, by_f3d, by_alt, site, issues, label, by_alias=None, restorable=()):
    """Збіг запису за td_code, потім за другим кодом сцени (td_alias), потім за запасним ключем (barcode/serial_no);
    повертає (record|None, skip: bool).

    Збіг за td_alias — не конфлікт: 3D малює один запис двома об'єктами (ворота DOCK-W1 і майданчик UNLOAD-1).
    `restorable` — id записів, архівованих відкатом цієї ж площадки: їх план пропонує відновити (`attrs: active`)."""
    rec = by_f3d.get(code) or (by_alias or {}).get(code)
    if rec is None:
        candidates = by_alt.get(code, [])
        if len(candidates) > 1:
            issues.append(_issue('conflict', 'block', "Неоднозначний збіг для %s" % code, [code]))
            return None, True
        if candidates:
            rec = candidates[0]
            if rec.td_code and rec.td_code != code:
                issues.append(
                    _issue(
                        'conflict',
                        'block',
                        "Код %s: %s «%s» має інший код сцени %s" % (code, label, rec.display_name, rec.td_code),
                        [code],
                    )
                )
                return None, True
    if rec is not None:
        if rec.td_site_id and rec.td_site_id != site:
            issues.append(
                _issue('conflict', 'block', "Код %s зайнятий записом площадки %s" % (code, rec.td_site_id.name), [code])
            )
            return None, True
        if rec.company_id and rec.company_id != site.company_id:
            issues.append(_issue('conflict', 'block', "Код %s зайнятий записом іншої компанії" % code, [code]))
            return None, True
        if not rec.active and rec.id not in restorable:
            issues.append(
                _issue('conflict', 'warn', "Запис %s архівований; не відновлюється автоматично" % code, [code])
            )
            return None, True
    return rec, False


def _group_by(records, field):
    out = {}
    for rec in records:
        key = rec[field]
        if key:
            out.setdefault(key, []).append(rec)
    return out


def cell_addr(slot):
    """Повна адресація місця (S1), що дала коди його комірок, або None (legacy-коди чи `code_style = exact`)."""
    ctx = slot._f3d_addr_context()
    if ctx and ctx.get('addr') and (slot.params or {}).get('code_style') != 'exact':
        return ctx
    return None


def cell_segments(cell, ctx, prefix=''):
    """Логічні номери сегментів комірки `{row, bay, level, pos}` (відсутні — немає ключа).

    `cell['parts']`, якщо ядро його віддає. З адресацією S1 — зворотним розбором коду лише за тими словами шаблону, які
    справді потрапили в код цієї комірки (зона й ряд — із контексту, ярус — лише в шаблонів з ярусами, позиція — у
    глибини «комірка»): так три числа в коді не плутаються з секцією/ярусом/позицією. Місце на підлозі — номер із
    контексту (`addr.spot_vals`). Без адресації (legacy) — секція = індекс комірки, ярус."""
    if cell.get('parts'):
        return {k: v for k, v in cell['parts'].items() if v}
    if not ctx:
        return {'bay': cell.get('index') or 0, 'level': cell.get('level') or 0}
    addr = ctx['addr']
    if cell['template'] == 'floor_spot':
        vals = addr_mod.spot_vals(ctx, prefix)
        return {k: vals[k] for k in ('row', 'bay', 'level', 'pos') if vals.get(k)}
    expected = {'prefix', 'bay'}
    expected |= {key for key in ('zone', 'row') if ctx.get(key) is not None}
    if cell['template'] in cells_mod.LEVEL_KEYS:
        expected.add('level')
        if ctx.get('depth_mode') == 'cell':
            expected.add('pos')
    words = addr_mod.parse_tpl(addr['tpl'])
    keep = [
        raw
        for raw, word in zip(addr['tpl'].split(), words, strict=True)
        if all(name in expected for kind, name in word if kind == 'seg')
    ]
    found = addr_mod.parse_code(dict(addr, tpl=' '.join(keep)), cell['code'], prefix) if keep else None
    return {k: v for k, v in (found or {}).items() if k in ('row', 'bay', 'level', 'pos') and v}


def cell_parts(cell, ctx=None, prefix=''):
    """Номери сегментів адреси комірки для `td_row/td_bay/td_level/td_pos` (0 — не задано)."""
    seg = cell_segments(cell, ctx, prefix)
    return {
        'td_row': int(seg.get('row') or 0),
        'td_bay': int(seg.get('bay') or 0),
        'td_level': int(seg.get('level') or 0),
        'td_pos': int(seg.get('pos') or 0),
    }


def row_code(site, slot, ctx):
    """Код віртуальної локації «ряд» (loc_tree = row; CD-31 Q1: секції локаціями не робимо); порожньо — плоско.

    Це слова шаблону адресації S1, що не залежать від секції/ярусу/позиції (`addr.render_code` з номером ряду місця і
    зоною з `address_context`) — той самий префікс, що видно в кодах комірок у попередньому перегляді адресації; без
    адресації (legacy) — `code_prefix` місця. Для місць без рядів (зони, місце на підлозі) — порожньо."""
    if site.loc_tree not in ('row', 'section') or slot.template not in addr_mod.ROW_TEMPLATES:
        return ''
    if ctx:
        vals = {'prefix': slot.code_prefix, 'zone': ctx.get('zone'), 'row': ctx.get('row')}
        vals.update(dict.fromkeys(('bay', 'level', 'pos')))
        return addr_mod.render_code(ctx['addr'], vals) or slot.code_prefix
    return slot.code_prefix


def loc_name(cell, ctx, tree, prefix):
    """Ім'я локації комірки: без власної назви — за правилом F01-05 (`addr.location_vals`: останній сегмент для дерева
    ряд/секція, повний код — у штрихкоді); інакше повний код (плоско, legacy)."""
    if cell['name'] != cell['code'] or tree == 'flat' or not ctx:
        return cell['name']
    return addr_mod.location_vals(cell['code'], cell_segments(cell, ctx, prefix), ctx['addr'], tree)['name']


def _restorable_ids(site, model=LOCATION):
    """id записів, архівованих відкатом створення (журнал): наступний план пропонує їх відновити."""
    ops = (
        site.env['td.publish.op']
        .sudo()
        .search(
            [
                ('res_model', '=', model),
                ('op', '=', 'create'),
                ('rolled_back', '=', True),
                ('version_id.site_id', '=', site.id),
            ]
        )
    )
    return set(ops.mapped('res_id'))


def _desired_cells(site, slots, zones, issues):
    desired = {}
    for slot in slots:
        cells = slot._f3d_cells()
        if not cells:
            continue
        ctx = cell_addr(slot)
        rcode = row_code(site, slot, ctx)
        parent = slot.parent_location_id or site.default_parent_location_id
        if not parent:
            issues.append(
                _issue(
                    'data',
                    'block',
                    "Для місця %s не задано батьківську локацію" % slot.code_prefix,
                    [slot.code_prefix],
                    slot.layer_id.id,
                )
            )
            continue
        for cell in cells:
            if cell['code'] in desired:
                issues.append(
                    _issue(
                        'conflict',
                        'block',
                        "Код %s дублюється в місцях %s і %s"
                        % (cell['code'], desired[cell['code']]['slot'].code_prefix, slot.code_prefix),
                        [cell['code']],
                    )
                )
                continue
            chain = zone_chain(zones, cell['x'], cell['y'])
            desired[cell['code']] = {
                'cell': cell,
                'slot': slot,
                'parent': parent,
                'zone': chain[0] if chain else None,
                'chain': chain,
                'ctx': ctx,
                'row_code': rcode if rcode and rcode != cell['code'] else '',
                'tree': site.loc_tree if rcode and rcode != cell['code'] else 'flat',
                'parts': cell_parts(cell, ctx, slot.code_prefix),
            }
    return desired


def _plan_locations(site, env, lines, issues):
    Loc = env[LOCATION].with_context(active_test=False)
    slots = env['td.slot'].search([('site_id', '=', site.id), ('layer_id.active', '=', True)])
    desired = _desired_cells(site, slots, _zones(site), issues)
    unchanged = 0
    codes = list(desired)
    prefixes = {item['row_code'] for item in desired.values()} - {''}
    existing = (
        Loc.search(
            [
                '|',
                '|',
                ('td_code', 'in', codes + sorted(prefixes)),
                ('td_alias', 'in', codes),
                ('barcode', 'in', codes),
            ]
        )
        if codes
        else Loc
    )
    by_f3d = {r.td_code: r for r in existing if r.td_code}
    by_alias = {r.td_alias: r for r in existing if r.td_alias}
    by_barcode = _group_by(existing, 'barcode')
    restorable = _restorable_ids(site)
    kept = set(codes) | prefixes  # коди сцени, що лишаються за площадкою (в т.ч. td_code/td_alias знайдених записів)
    rows = {}  # префікс → рядок створення віртуальної локації «ряд»
    for prefix in sorted(prefixes):
        item = next(it for it in desired.values() if it['row_code'] == prefix)
        if prefix not in by_f3d:
            vals = {
                'name': prefix,
                'usage': 'view',
                'location_id': item['parent'].id,
                'td_code': prefix,
                'td_site_id': site.id,
                'td_slot_uid': item['slot'].uid,
                'company_id': site.company_id.id,
            }
            rows[prefix] = _line(
                'create', LOCATION, prefix, prefix, vals, None, item['slot'].uid, "ряд (віртуальна локація)"
            )
            rows[prefix]['extra']['virtual'] = True
            lines.append(rows[prefix])
    by_slot = {}
    if any(
        it['ctx'] for it in desired.values()
    ):  # з адресацією S1 перейменування знаходить локацію за номерами сегментів
        for rec in Loc.search([('td_site_id', '=', site.id), ('td_slot_uid', '!=', False)]):
            by_slot.setdefault(rec.td_slot_uid, []).append(rec)
    taken = set()
    mode = _code_mode(site)
    for code, item in desired.items():
        slot, zone = item['slot'], item['zone']
        rec, skip = _match(code, by_f3d, by_barcode, site, issues, "локація", by_alias, restorable)
        if skip:
            continue
        zone_uid = zone.uid if zone else ''
        if rec is not None:
            kept.update(c for c in (rec.td_code, rec.td_alias) if c)
            taken.add(rec.id)
        else:
            old = _renumbered(item, by_slot, desired, taken)
            if old is not None:
                taken.add(old.id)
                kept.add(old.td_code)
                _plan_rename(lines, issues, old, code, item, zone_uid, mode)
                continue
            lines.append(_plan_create(site, code, item, zone_uid, rows, by_f3d))
            continue
        parent_rec = by_f3d.get(item['row_code']) if item['row_code'] else slot.parent_location_id
        if not _plan_existing(lines, issues, rec, code, item, zone_uid, site, mode, parent_rec):
            unchanged += 1
    return kept, unchanged


def _plan_create(site, code, item, zone_uid, rows, by_f3d):
    cell, slot, parent, chain, parts = item['cell'], item['slot'], item['parent'], item['chain'], item['parts']
    row = item['row_code']
    vals = {
        'name': loc_name(cell, item['ctx'], item['tree'], slot.code_prefix),
        'barcode': code,
        'td_code': code,
        'usage': 'internal',
        'location_id': parent.id,
        'td_loc_kind': cell['kind'],
        'td_capacity': cell['capacity'] or 0.0,
        'td_site_id': site.id,
        'td_slot_uid': slot.uid,
        'company_id': site.company_id.id,
        **parts,
    }
    vals.update(flag_vals(cell))
    extra = {'zone_uid': zone_uid, 'parts': parts}
    depends = ''
    if row in rows:  # батьківський ряд створюється в цьому ж плані: id підставить застосування
        depends, extra['parent_code'] = row, row
    elif row and row in by_f3d:
        vals['location_id'] = by_f3d[row].id
    category = inherited('storage_category_id', slot, chain)
    strategy = inherited('removal_strategy_id', slot, chain)
    if category:
        vals['storage_category_id'] = category.id
    if strategy:
        vals['removal_strategy_id'] = strategy.id
    card = "вид %s" % cell['kind'] + (", місткість %s" % _fmt(cell['capacity']) if cell['capacity'] else "")
    if category:
        card += ", категорія %s" % category.name
    line = _line('create', LOCATION, code, cell['name'], vals, None, slot.uid, card, extra, depends)
    problem = flag_problem(slot.env, vals, None, parent)
    if problem:
        _block(line, *problem)
    return line


def _renumbered(item, by_slot, desired, taken):
    """Наявна локація того ж місця з тими самими номерами сегментів, але іншим кодом (зміна адресації)."""
    if not item['ctx']:
        return None
    mine = item['parts']
    for rec in by_slot.get(item['slot'].uid, []):
        if rec.id in taken or not rec.active or not rec.td_code or rec.td_code in desired:
            continue
        if all(rec[f] == mine[f] for f in PART_FIELDS) and any(rec[f] for f in PART_FIELDS):
            return rec
    return None


def _plan_rename(lines, issues, rec, code, item, zone_uid, mode='warn'):
    cell, slot = item['cell'], item['slot']
    vals = {'name': loc_name(cell, item['ctx'], item['tree'], slot.code_prefix), 'barcode': code, 'td_code': code}
    line = _line('rename', LOCATION, code, rec.complete_name or code, vals, rec, slot.uid, _diff_text(rec, vals))
    line['extra'].update({'zone_uid': zone_uid, 'old_code': rec.td_code})
    busy = (
        rec.env[LOCATION]
        .with_context(active_test=False)
        .search([('barcode', '=', code), ('id', '!=', rec.id)], limit=1)
    )
    if busy:
        reason = "Штрихкод %s уже зайнятий: %s" % (code, busy.display_name)
        _block(line, reason, 'barcode_busy')
        if mode:
            issues.append(_issue('code_conflict', mode, reason, [code]))
    lines.append(line)


def _plan_existing(lines, issues, rec, code, item, zone_uid, site, mode='warn', parent_rec=None):
    cell, slot, chain, parts = item['cell'], item['slot'], item['chain'], item['parts']
    """Рядки для наявної локації: перенесення, перейменування, атрибути. Повертає, чи є зміни."""
    mine = []
    # F02-11: штрихкод зайнятий не внутрішньою локацією або іншого складу — застосувати не можна
    foreign = ''
    if rec.usage != 'internal':
        foreign = "Штрихкод %s зайнятий локацією типу «%s»: %s" % (code, rec.usage, rec.display_name)
    elif site.warehouse_id and rec.warehouse_id and rec.warehouse_id != site.warehouse_id:
        foreign = "Штрихкод %s зайнятий локацією іншого складу: %s" % (code, rec.display_name)

    def add(kind, vals, text=None):
        line = _line(
            kind, LOCATION, code, rec.complete_name or code, vals, rec, slot.uid, text or _diff_text(rec, vals)
        )
        line['extra']['zone_uid'] = zone_uid
        mine.append(line)
        return line

    # перенесення: інший батько (лише коли він заданий явно: батьківська локація місця або наявний ряд)
    if parent_rec and rec.location_id != parent_rec:
        line = add('move', {'location_id': parent_rec.id})
        stock = _stock_qty(rec)
        if stock:
            line['extra']['flags'] = ['stock']
            issues.append(
                _issue('conflict', 'warn', "Локацію %s із залишком %s буде перенесено" % (code, _fmt(stock)), [code])
            )
    # перейменування: власне ім'я комірки (overrides.name) відрізняється від імені локації
    if cell['name'] != code and rec.name != cell['name']:
        add('rename', {'name': cell['name']})
    vals = {}
    if not rec.active:
        vals['active'] = True
    if not rec.td_code:
        vals['td_code'] = code
    if not rec.barcode:
        vals['barcode'] = code
    if cell['kind'] and rec.td_loc_kind != cell['kind']:
        vals['td_loc_kind'] = cell['kind']
    if cell['capacity'] and cell['capacity'] != rec.td_capacity:
        vals['td_capacity'] = cell['capacity']
    if rec.td_site_id != site:
        vals['td_site_id'] = site.id
    if rec.td_slot_uid != slot.uid:
        vals['td_slot_uid'] = slot.uid
    category = inherited('storage_category_id', slot, chain)
    strategy = inherited('removal_strategy_id', slot, chain)
    if category and rec.storage_category_id != category:
        vals['storage_category_id'] = category.id
    if strategy and rec.removal_strategy_id != strategy:
        vals['removal_strategy_id'] = strategy.id
    if any(rec[f] for f in PART_FIELDS):  # номери адреси наявних локацій оновлюємо, лише коли вони вже ведуться
        vals.update({f: parts[f] for f in PART_FIELDS if rec[f] != parts[f]})
    flags = flag_vals(cell, rec)
    vals.update(flags)
    if vals:
        text = _diff_text(rec, vals)
        line = add('attrs', vals, ("відновити з архіву (після відкату); " + text) if 'active' in vals else text)
        problem = flag_problem(rec.env, flags, rec) if flags else None
        if problem:
            _block(line, *problem)
            issues.append(_issue('conflict', 'warn', "%s: %s" % (code, problem[0]), [code]))
    if foreign and mine:
        for line in mine:
            _block(line, foreign, 'barcode_busy')
        if mode:
            issues.append(_issue('code_conflict', mode, foreign, [code]))
    lines.extend(mine)
    return bool(mine)


def _replenish_nested(env, loc):
    """Odoo забороняє вкладені місця поповнення: є інша `replenish_location` серед батьків або нащадків `loc`."""
    return bool(
        env[LOCATION].search_count(
            [
                ('id', '!=', loc.id),
                ('replenish_location', '=', True),
                '|',
                ('location_id', 'child_of', loc.id),
                ('location_id', 'parent_of', loc.id),
            ]
        )
    )


def flag_vals(cell, rec=None):
    """Прапорці локації з перевизначень комірки (F03-05): `usage` (internal/view) і `replenish_location`; для наявної
    локації — лише відмінні. Порожньо, коли комірка їх не задає."""
    vals = {}
    usage = cell.get('usage')
    if usage and usage != (rec.usage if rec is not None else 'internal'):
        vals['usage'] = usage
    if 'replenish_location' in cell:
        want = bool(cell['replenish_location'])
        if (rec is None and want) or (rec is not None and rec.replenish_location != want):
            vals['replenish_location'] = want
    return vals


def flag_problem(env, vals, rec=None, parent=None):
    """Чому прапорці не можна застосувати: `(причина, мітка)` або None. Місце із залишком не стане view; місце
    поповнення — лише внутрішня локація без вкладених місць поповнення."""
    usage = vals.get('usage') or (rec.usage if rec is not None else 'internal')
    if rec is not None and vals.get('usage') == 'view' and _stock_qty(rec):
        return "Є залишки: місце з товаром не стане типом view", 'stock'
    if vals.get('replenish_location'):
        if usage != 'internal':
            return "Місце поповнення має бути внутрішньою локацією", 'replenish_usage'
        nested = (
            _replenish_nested(env, rec)
            if rec is not None
            else bool(
                parent is not None
                and env[LOCATION].search_count([('replenish_location', '=', True), ('id', 'parent_of', parent.id)])
            )
        )
        if nested:
            return (
                "Вкладені місця поповнення заборонені (батько чи нащадок уже місце поповнення)",
                'replenish_nested',
            )
    return None


def _stock_qty(location):
    """Залишок у самій локації (`stock.quant`, quantity > 0)."""
    return sum(
        qty
        for _loc, qty in location.env['stock.quant']._read_group(
            [('location_id', '=', location.id), ('quantity', '>', 0)], ['location_id'], ['quantity:sum']
        )
    )


# --- штрихкоди компанії (F02-11, API-17, перевірка code_conflict) ---------------------------------------------


def _code_mode(site):
    """Серйозність зауважень плану про зайнятий штрихкод: без налаштування `code_conflict` — попередження; з
    налаштуванням (увімкнене чи ні) зауваження дає перевірка `code_conflict` через `scene.extra`, тож тут — None."""
    return None if site.check_config_ids.filtered(lambda c: c.check_key == 'code_conflict') else 'warn'


def code_states(env, site, codes):
    """Зайнятість кодів у Odoo для площадки: `{код: {state, reason}}`; state: `free`, `own` (локація цієї площадки),
    `match` (наявна локація без площадки: публікація зв'яже її), `busy` (застосувати не можна: інша площадка, інша
    компанія, архівна, не внутрішня, інший склад). Назви чужих компаній не розкриваються."""
    codes = [c for c in codes if c]
    Loc = env[LOCATION].sudo().with_context(active_test=False)
    found = Loc.search(['|', ('barcode', 'in', codes), ('td_code', 'in', codes)]) if codes else Loc
    by_code = {}
    for rec in found:
        for key in {rec.barcode, rec.td_code}:
            if key in codes:
                by_code.setdefault(key, []).append(rec)
    out = {}
    for code in codes:
        recs = by_code.get(code) or []
        if not recs:
            out[code] = {'state': 'free', 'reason': ''}
            continue
        rec = recs[0]
        if len(recs) > 1:
            out[code] = {'state': 'busy', 'reason': "Код збігається з кількома локаціями"}
        elif rec.company_id and rec.company_id != site.company_id:
            out[code] = {'state': 'busy', 'reason': "Штрихкод зайнятий записом іншої компанії"}
        elif rec.td_site_id and rec.td_site_id != site:
            out[code] = {'state': 'busy', 'reason': "Штрихкод зайнятий локацією площадки %s" % rec.td_site_id.name}
        elif not rec.active and not rec.td_site_id:
            out[code] = {'state': 'busy', 'reason': "Штрихкод зайнятий архівною локацією %s" % rec.display_name}
        elif rec.usage != 'internal':
            out[code] = {
                'state': 'busy',
                'reason': "Штрихкод зайнятий локацією типу «%s»: %s" % (rec.usage, rec.display_name),
            }
        elif site.warehouse_id and rec.warehouse_id and rec.warehouse_id != site.warehouse_id:
            out[code] = {'state': 'busy', 'reason': "Штрихкод зайнятий локацією іншого складу: %s" % rec.display_name}
        elif rec.td_site_id == site:
            out[code] = {'state': 'own', 'reason': ''}
        else:
            out[code] = {'state': 'match', 'reason': "Наявну локацію %s буде зв'язано" % rec.display_name}
    return out


def check_code_conflict(scene, config, eps):
    """`code_conflict`: коди комірок чернетки, зайняті в Odoo (`extra.code_states`); порожньо без даних БД."""
    states = (getattr(scene, 'extra', None) or {}).get('code_states') or {}
    issues = []
    for slot in scene.slots.values():
        for code in scene.slot_cells(slot):
            st = states.get(code)
            if st and st['state'] == 'busy':
                issues.append(
                    {
                        'check': 'code_conflict',
                        'severity': config['mode'],
                        'layer_id': slot['layer_id'],
                        'codes': [code],
                        'message': "%s: %s" % (code, st['reason']),
                    }
                )
    return issues


CHECKS.register('code_conflict', check_code_conflict, sequence=95)


# --- обладнання й робочі центри --------------------------------------------------------------------------


def _plan_equipment(site, env, lines, issues):
    Equipment = env[EQUIPMENT].with_context(active_test=False)
    Workcenter = env[WORKCENTER].with_context(active_test=False)
    placements = env['td.placement'].search([('site_id', '=', site.id), ('layer_id.active', '=', True)])
    codes = placements.mapped('code')
    eq_existing = (
        Equipment.search(['|', '|', ('td_code', 'in', codes), ('td_alias', 'in', codes), ('serial_no', 'in', codes)])
        if codes
        else Equipment
    )
    by_f3d = {r.td_code: r for r in eq_existing if r.td_code}
    by_alias = {r.td_alias: r for r in eq_existing if r.td_alias}
    by_serial = _group_by(eq_existing.filtered(lambda r: not r.td_code), 'serial_no')
    wc_codes = placements.filtered(lambda p: p.variant_id.create_workcenter).mapped('code')
    wc_existing = (
        Workcenter.search(['|', ('td_code', 'in', wc_codes), ('code', 'in', wc_codes)]) if wc_codes else Workcenter
    )
    wc_by_f3d = {r.td_code: r for r in wc_existing if r.td_code}
    wc_by_code = _group_by(wc_existing.filtered(lambda r: not r.td_code), 'code')
    Zone = env['td.zone']
    unchanged = 0
    kept = set(codes)
    restore_eq, restore_wc = _restorable_ids(site, EQUIPMENT), _restorable_ids(site, WORKCENTER)
    for p in placements:
        code = p.code
        passport = p.variant_id.passport_id
        zone = Zone.zone_at(p.x_m, p.y_m, site.company_id)
        rec, skip = _match(code, by_f3d, by_serial, site, issues, "обладнання", by_alias, restore_eq)
        if not skip and rec is None and p.dynamic:
            continue  # люди й транспорт без наявного обладнання: запис обладнання не створюємо
        if rec is not None:
            kept.update(c for c in (rec.td_code, rec.td_alias) if c)  # не пропонувати архівацію (збіг за alias)
        if not skip:
            if rec is None:
                if p.variant_id.create_equipment:  # зведені варіанти сцени (прапорець вимкнено) обладнання не створюють
                    vals = {
                        'name': p.name,
                        'td_code': code,
                        'td_passport_id': passport.id,
                        'td_site_id': site.id,
                        'td_placement_uid': p.uid,
                        'company_id': site.company_id.id,
                    }
                    if zone:
                        vals['td_zone_id'] = zone.id
                    lines.append(
                        _line(
                            'create', EQUIPMENT, code, p.name, vals, None, p.uid, "паспорт %s" % passport.display_name
                        )
                    )
            else:
                vals = {}
                if not rec.active:
                    vals['active'] = True
                if not rec.td_code:
                    vals['td_code'] = code
                # зведений паспорт «Об'єкти сцени» ніколи не записується в наявне обладнання (ні замість справжнього
                # паспорта, ні замість порожнього); зона наявного обладнання публікацією не змінюється: вона
                # задається каталогом base (scene_zone_links), а не геометрією розміщення
                if rec.td_passport_id != passport and not is_scene_passport(passport):
                    vals['td_passport_id'] = passport.id
                if rec.td_site_id != site:
                    vals['td_site_id'] = site.id
                if rec.td_placement_uid != p.uid:
                    vals['td_placement_uid'] = p.uid
                if vals:
                    lines.append(
                        _line('update', EQUIPMENT, code, rec.display_name, vals, rec, p.uid, _diff_text(rec, vals))
                    )
                else:
                    unchanged += 1
        if p.variant_id.create_workcenter:
            wrec, wskip = _match(code, wc_by_f3d, wc_by_code, site, issues, "робочий центр", None, restore_wc)
            if wskip:
                continue
            if wrec is None:
                vals = {
                    'name': p.name,
                    'code': code,
                    'td_code': code,
                    'td_site_id': site.id,
                    'company_id': site.company_id.id,
                }
                lines.append(_line('create', WORKCENTER, code, p.name, vals, None, p.uid, "робочий центр"))
            else:
                vals = {}
                if not wrec.active:
                    vals['active'] = True
                if not wrec.td_code:
                    vals['td_code'] = code
                if wrec.td_site_id != site:
                    vals['td_site_id'] = site.id
                if vals:
                    lines.append(
                        _line('update', WORKCENTER, code, wrec.display_name, vals, wrec, p.uid, _diff_text(wrec, vals))
                    )
                else:
                    unchanged += 1
    return kept, set(wc_codes), unchanged


# --- пропозиції архівації (R-13, F02-05) ------------------------------------------------------------------


def _plan_archive(site, env, lines, loc_codes, eq_codes, wc_codes):
    def candidates(model, desired):
        recs = env[model].search([('td_site_id', '=', site.id), ('active', '=', True)])
        return recs.filtered(lambda r: r.td_code and r.td_code not in desired)

    locations = candidates(LOCATION, loc_codes)
    stock, moving = {}, set()
    if locations:
        for loc, qty in env['stock.quant']._read_group(
            [('location_id', 'in', locations.ids), ('quantity', '>', 0)], ['location_id'], ['quantity:sum']
        ):
            stock[loc.id] = qty
        pending = env['stock.move'].search(
            [
                ('state', 'not in', ('done', 'cancel', 'draft')),
                '|',
                ('location_id', 'in', locations.ids),
                ('location_dest_id', 'in', locations.ids),
            ]
        )
        for move in pending:
            moving.update({move.location_id.id, move.location_dest_id.id})
    equipment = candidates(EQUIPMENT, eq_codes)
    busy_eq = set()
    if equipment and 'maintenance.request' in env:
        requests = env['maintenance.request'].search(
            [('equipment_id', 'in', equipment.ids), ('stage_id.done', '=', False), ('archive', '=', False)]
        )
        busy_eq = set(requests.mapped('equipment_id').ids)
    workcenters = candidates(WORKCENTER, wc_codes)
    busy_wc = set()
    if workcenters and 'mrp.workorder' in env:
        orders = env['mrp.workorder'].search(
            [('workcenter_id', 'in', workcenters.ids), ('state', 'not in', ('done', 'cancel'))]
        )
        busy_wc = set(orders.mapped('workcenter_id').ids)
    for rec in locations:
        line = _line('archive', LOCATION, rec.td_code, rec.complete_name, None, rec, '', "буде архівовано")
        if stock.get(rec.id):
            _block(line, "Є залишки: %s" % _fmt(stock[rec.id]), 'stock')
        elif rec.id in moving:
            _block(line, "Є незавершені переміщення", 'moves')
        lines.append(line)
    for rec in equipment:
        line = _line('archive', EQUIPMENT, rec.td_code, rec.name, None, rec, '', "буде архівовано")
        if rec.id in busy_eq:
            _block(line, "Є відкриті заявки ТО", 'requests')
        lines.append(line)
    for rec in workcenters:
        line = _line('archive', WORKCENTER, rec.td_code, rec.name, None, rec, '', "буде архівовано")
        if rec.id in busy_wc:
            _block(line, "Є незавершені завдання", 'workorders')
        lines.append(line)


def build_plan(site):
    """R-12: `{lines, issues, unchanged, draft_rev}`; в Odoo нічого не змінює."""
    site = site.sudo()
    env = site.env
    issues = [dict(i) for i in state_mod.run_site_checks(site)]
    lines, unchanged = [], 0
    loc_codes, loc_unchanged = _plan_locations(site, env, lines, issues)
    eq_codes, wc_codes, eq_unchanged = _plan_equipment(site, env, lines, issues)
    unchanged = loc_unchanged + eq_unchanged
    _plan_archive(site, env, lines, loc_codes, eq_codes, wc_codes)
    # будівники плану слайсів (registry.PLAN_BUILDERS): дописують рядки й зауваження, повертають число «без змін»
    for builder in PLAN_BUILDERS.values():
        unchanged += builder(site, env, lines, issues) or 0
    return {'lines': lines, 'issues': issues, 'unchanged': unchanged, 'draft_rev': site.draft_rev}


def summary(plan, archive_keys=()):
    keys = set(archive_keys)
    count = lambda *kinds: sum(1 for line in plan['lines'] if line['kind'] in kinds)  # noqa: E731
    return {
        'create': count('create'),
        'update': count('update', 'move', 'rename', 'attrs'),
        'move': count('move'),
        'rename': count('rename'),
        'attrs': count('attrs'),
        'archive': len(
            [line for line in plan['lines'] if line['kind'] == 'archive' and (line['res_model'], line['code']) in keys]
        ),
        'archive_offer': count('archive'),
        'blocked': sum(1 for line in plan['lines'] if line['blocked']),
        'unchanged': plan['unchanged'],
        'warn': sum(1 for i in plan['issues'] if i['severity'] == 'warn'),
        'block': sum(1 for i in plan['issues'] if i['severity'] == 'block'),
    }


# --- вибір рядків: частинами, залежності (F02-03) ---------------------------------------------------------


def _in_set(line, keys):
    """Ключ із двох елементів `(модель, код)` збігається з будь-яким видом рядка, із трьох — лише з точним."""
    return (line['res_model'], line['code']) in keys or (None, line['code']) in keys or line_key(line) in keys


def select_lines(plan, archive_keys=(), excluded=(), scope=None):
    """Рядки, що застосовуються, і пропущені: `(lines, skipped)`.

    Позначені: створення/зміни — усі, крім `excluded`; архів — лише `archive_keys` (явне видалення правила — як зміна);
    заблоковані не беруть участі; `scope` (uid місць/зон) обмежує область. Батьки додаються самі, навіть знявши їх;
    рядок із заблокованим батьком пропускається (`skipped`).
    """
    keys = {k if isinstance(k, tuple) else (None, k) for k in archive_keys}
    skip = {k if isinstance(k, tuple) else (None, k) for k in excluded}
    chosen = []
    for line in plan['lines']:
        if line['blocked']:
            continue
        proposal = line['kind'] == 'archive' and not line['extra'].get(
            'explicit'
        )  # явне видалення правила — не пропозиція
        ok = _in_set(line, keys) if proposal else not _in_set(line, skip)
        if ok:
            chosen.append(line)
    if scope is not None:
        uids = set(scope)
        chosen = [ln for ln in chosen if ln['scope_uid'] in uids or ln['extra'].get('zone_uid') in uids]
    # залежність — рядок, що створює локацію або відновлює її з архіву (після відкату)
    creates = {
        (ln['res_model'], ln['code']): ln
        for ln in plan['lines']
        if ln['kind'] == 'create' or (ln['kind'] == 'attrs' and ln['vals'].get('active'))
    }

    def blocked_parent(line):
        """Код заблокованого батька в ланцюжку залежностей рядка (інакше None)."""
        dep = line['depends_code']
        for _guard in range(20):
            parent = creates.get((LOCATION, dep)) if dep else None
            if parent is None:
                return None
            if parent['blocked']:
                return dep
            dep = parent['depends_code']
        return None

    alive, skipped = [], []
    for line in chosen:
        bad = blocked_parent(line)
        if bad:
            skipped.append({'code': line['code'], 'reason': "Залежність %s заблокована" % bad})
        else:
            alive.append(line)
    chosen, have = alive, {id(ln) for ln in alive}
    for line in list(chosen):  # батьки додаються самі, навіть коли їх знято
        dep = line['depends_code']
        for _guard in range(20):
            parent = creates.get((LOCATION, dep)) if dep else None
            if parent is None:
                break
            if id(parent) not in have:
                chosen.append(parent)
                have.add(id(parent))
            dep = parent['depends_code']
    return chosen, skipped


def _creation_levels(creates):
    """Рядки створення групами: батьки (залежності з цього ж плану) раніше за дітей."""
    codes = {ln['code'] for ln in creates}
    done, levels, left = set(), [], list(creates)
    while left:
        level = [ln for ln in left if ln['depends_code'] not in codes or ln['depends_code'] in done]
        if not level:  # цикл залежностей неможливий, але не зависаємо
            level = left
        levels.append(level)
        done.update(ln['code'] for ln in level)
        left = [ln for ln in left if ln not in level]
    return levels


# --- застосування ------------------------------------------------------------------------------------------


def _lock_site(env, site):
    try:
        with env.cr.savepoint():
            env.cr.execute("SELECT id FROM td_site WHERE id = %s FOR UPDATE NOWAIT", (site.id,))
    except pg_errors.LockNotAvailable:
        raise PublishError('conflict', "Публікація вже виконується іншим користувачем") from None


def _check_preconditions(site, plan):
    env = site.env
    if not (env.su or env.user.has_group('td_constructor.group_td_constructor_manager')):
        raise PublishError('rights', "Публікувати розкладку може лише менеджер конструктора.")
    if not publish_enabled(env):
        raise PublishError('disabled', "Публікацію вимкнено: стоп-кран td.constructor.publish_enabled.")
    if plan['draft_rev'] != site.draft_rev:
        raise PublishError('conflict', "Чернетка змінилась. Закрийте вікно й відкрийте майстер знову.")
    blocks = [i for i in plan['issues'] if i['severity'] == 'block']
    if blocks:
        code = 'conflict_codes' if any(i['check'] == 'conflict' for i in blocks) else 'blocked'
        raise PublishError(
            code, "Публікацію заборонено: є зауваження зі статусом «Заборона» (%d)." % len(blocks), blocks
        )
    changed = [line for line in plan['lines'] if line['kind'] in CHANGE_KINDS and not line['blocked']]
    if not changed and not site.has_changes:
        raise PublishError('no_changes', "Немає змін для публікації")


def _refresh_baseline(site):
    """S4: після публікації база порівняння «Оновити з Odoo» (`site.odoo_baseline_id`, F02-12) = нинішня стрічка локацій складу.
    Без цього створене й змінене самою публікацією показувалося б як «з'явилося / перейменовано в Odoo», а експорт
    «нові й змінені» тягнув би його знову. Помилка бази публікацію не скасовує (стрічка читається в окремій точці збереження)."""
    try:
        with site.env.cr.savepoint():
            odoo_sync.save_baseline(site, odoo_sync.full_feed(site.env, site)['locations'])
    except Exception:  # noqa: BLE001 - база порівняння не варта відкату публікації
        _logger.warning("Площадка %s: базу порівняння після публікації не оновлено", site.id, exc_info=True)


def apply_plan(site, plan, archive_keys=(), note='', excluded=(), scope=None):
    """R-12 п. 6: застосувати план у транзакції; повертає
    `{'version', 'created', 'updated', 'archived', 'warnings', 'ops', 'skipped'}`.

    `archive_keys` — множина `(res_model, code)` або голих кодів позначених пропозицій архівації (blocked ігноруються).
    `excluded` — множина `(res_model, code)` або `(res_model, code, kind)` знятих у майстрі рядків (пропускаються).
    `scope` — uid місць/зон: застосувати лише їхні рядки (F02-03); потрібні батьки додаються самі.
    Після успіху база порівняння S4 оновлюється нинішньою стрічкою локацій (`_refresh_baseline`).
    Будь-який неочікуваний виняток відкочує все (`PublishError('rollback')`).
    """
    _check_preconditions(site, plan)
    chosen, skipped = select_lines(plan, archive_keys, excluded, scope)
    if scope is not None and not chosen:
        raise PublishError('no_changes', "Немає змін для публікації")
    env = site.env
    try:
        with env.cr.savepoint():
            _lock_site(env, site)
            result = _apply(site, plan, chosen, note, scope)
            result['skipped'] = skipped
            _refresh_baseline(site)
            return result
    except (PublishError, UserError):
        env.invalidate_all()
        raise
    except Exception as exc:  # noqa: BLE001 - відкат усієї публікації
        env.invalidate_all()
        _logger.exception("Публікація площадки %s відкотилась", site.id)
        raise PublishError(
            'rollback', "Публікацію скасовано через помилку: %s" % (str(exc)[:300] or exc.__class__.__name__)
        ) from exc


def make_op(op, model, rec, code, before, after):
    """Запис журналу (`td.publish.op`) без версії й номера: `seq` і `version_id` додає застосування."""
    return {
        'op': op,
        'res_model': model,
        'res_id': rec.id,
        'code': code,
        'before': before or {},
        'after': after or {},
    }


def _write_lines(base, model, lines, records, ops, updated):
    """`write` для рядків move/rename/attrs/update однієї моделі; прежні значення читаються перед записом."""
    for line in lines:
        rec = base[model].with_context(active_test=False).browse(line['res_id'])
        vals = dict(line['vals'])
        before = read_values(rec, vals)
        rec.write(write_vals(vals, record=rec))
        records[(model, line['code'])] = rec
        kind = line['kind']
        ops.append(make_op(LOG_OP.get(kind, kind), model, rec, line['code'], before, read_values(rec, vals)))
        updated.append({'model': model, 'code': line['code'], 'id': rec.id, 'kind': kind})


def _apply(site, plan, chosen, note, scope=None):
    site = (
        site.sudo()
        .with_company(site.company_id)
        .with_context(f3d_no_touch=True, tracking_disable=True, mail_notrack=True, mail_create_nolog=True)
    )
    base = site.env
    created, updated, archived, ops = [], [], [], []
    records = {}  # (res_model, code) → record для зв'язування розміщень і правил

    def pick(model, *kinds):
        return [ln for ln in chosen if ln['res_model'] == model and ln['kind'] in kinds]

    for model in (LOCATION, EQUIPMENT, WORKCENTER):
        Model = base[model]
        for level in _creation_levels(pick(model, 'create')):
            for line in level:
                parent = records.get((LOCATION, line['extra'].get('parent_code')))
                if parent:
                    line['vals']['location_id'] = parent.id
            vals_list = [write_vals(line['vals'], model=Model) for line in level]
            for line, rec in zip(level, Model.create(vals_list), strict=True):
                records[(model, line['code'])] = rec
                created.append({'model': model, 'code': line['code'], 'id': rec.id})
                ops.append(make_op('create', model, rec, line['code'], {}, dict(line['vals'], active=True)))
        for kind in ('move', 'rename', 'attrs', 'update'):
            _write_lines(base, model, pick(model, kind), records, ops, updated)
    # зв'язок обладнання з робочим центром (лише якщо поле існує, DEC-16) і розміщень із записами
    has_wc_field = 'workcenter_id' in base[EQUIPMENT]._fields
    now = fields.Datetime.now()
    for placement in base['td.placement'].search([('site_id', '=', site.id), ('layer_id.active', '=', True)]):
        eq = records.get((EQUIPMENT, placement.code)) or placement.equipment_id
        wc = records.get((WORKCENTER, placement.code)) or placement.workcenter_id
        if not eq:
            eq = base[EQUIPMENT].with_context(active_test=False).search([('td_code', '=', placement.code)], limit=1)
        if not wc and placement.variant_id.create_workcenter:
            wc = base[WORKCENTER].with_context(active_test=False).search([('td_code', '=', placement.code)], limit=1)
        vals = {}
        if eq and placement.equipment_id != eq:
            vals['equipment_id'] = eq.id
        if wc and placement.workcenter_id != wc:
            vals['workcenter_id'] = wc.id
        if vals:
            vals['published_at'] = now
            placement.write(vals)
        if has_wc_field and eq and wc and eq.workcenter_id != wc:
            eq.write({'workcenter_id': wc.id})
    # пропозиції архівації: лише позначені й не заблоковані (R-13)
    for model in (LOCATION, EQUIPMENT, WORKCENTER):
        for line in pick(model, 'archive'):
            rec = base[model].browse(line['res_id'])
            rec.write({'active': False})
            archived.append({'model': model, 'code': line['code'], 'id': rec.id})
            ops.append(make_op('archive', model, rec, line['code'], {'active': True}, {'active': False}))
    # правила поповнення й розміщення (застосовують capacity.py / putaway.py)
    for model in (ORDERPOINT, PUTAWAY):
        lines = pick(model, 'create', 'attrs', 'update', 'archive')
        if lines and model in APPLIERS:
            for entry in APPLIERS[model](site, lines, records, ops):
                {'create': created, 'archive': archived}.get(entry['kind'], updated).append(entry)
    warnings = [i for i in plan['issues'] if i['severity'] == 'warn']
    report = {
        'created': created,
        'updated': updated,
        'archived': archived,
        'warnings': warnings,
        'scope': sorted(scope) if scope is not None else None,
    }
    version = snapshot.create_version(site, note=note, report=report)
    base['td.publish.op'].create([dict(op, version_id=version.id, seq=i) for i, op in enumerate(ops, 1)])
    return {
        'version': version,
        'created': created,
        'updated': updated,
        'archived': archived,
        'warnings': warnings,
        'ops': len(ops),
    }


# --- журнал й відкат (F02-08) ------------------------------------------------------------------------------


def op_counts(version):
    """Число операцій версії за видами: `{create, move, rename, attrs, archive}`."""
    counts = dict.fromkeys(('create', 'move', 'rename', 'attrs', 'archive'), 0)
    for op in version.op_ids:
        counts[op.op] = counts.get(op.op, 0) + 1
    return counts


def _used_locations(env, ops):
    """Серед локацій, створених `ops`, ті, що вже використані (залишки, рухи в них або в нащадках): `{op.id: чому}`."""
    Location = env[LOCATION].with_context(active_test=False)
    created = [op for op in ops if op.op == 'create' and op.res_model == LOCATION]
    if not created:
        return {}
    ids = [op.res_id for op in created]
    tree = Location.search([('id', 'child_of', ids)])
    used = {}
    for quant in env['stock.quant']._read_group(
        [('location_id', 'in', tree.ids), ('quantity', '!=', 0)], ['location_id'], ['__count']
    ):
        used[quant[0].id] = "є залишки"
    for field in ('location_id', 'location_dest_id'):
        for line in env['stock.move.line']._read_group([(field, 'in', tree.ids)], [field], ['__count']):
            used.setdefault(line[0].id, "є рухи товару")
    out = {}
    for op in created:
        rec = Location.browse(op.res_id)
        if not rec.exists() or not rec.active:
            continue
        path = rec.parent_path or ''
        for loc in tree.browse(list(used)):
            if (loc.parent_path or '').startswith(path):
                out[op.id] = used[loc.id]
                break
    return out


def rollback_problems(version):
    """Що заважає відкату версії: `[{'code', 'reason'}]`; порожньо — відкат дозволено (F02-08, Q5)."""
    env = version.env
    if version.kind != 'publish':
        return [{'code': '', 'reason': "Контрольна точка не змінює Odoo"}]
    if version.rolled_back_at:
        return [{'code': '', 'reason': "Версію вже відкочено"}]
    ops = version.op_ids.sorted('seq')
    if not ops:
        return [{'code': '', 'reason': "У версії немає операцій в Odoo"}]
    problems = []
    later = (
        env['td.layout.version']
        .sudo()
        .search(
            [
                ('site_id', '=', version.site_id.id),
                ('n', '>', version.n),
                ('kind', '=', 'publish'),
                ('rolled_back_at', '=', False),
            ]
        )
    )
    mine = {(op.res_model, op.code) for op in ops}
    for ver in later:
        clash = sorted({op.code for op in ver.op_ids if (op.res_model, op.code) in mine})
        if clash:
            problems.append(
                {
                    'code': clash[0],
                    'reason': "Є пізніша публікація v%d з тими самими кодами (відкотіть її першою)" % ver.n,
                }
            )
            break
    used = _used_locations(env, ops)
    for op in ops:
        rec = env[op.res_model].with_context(active_test=False).browse(op.res_id).exists()
        if not rec:
            problems.append({'code': op.code, 'reason': "Запис Odoo видалено"})
        elif op.op == 'create':
            reason = used.get(op.id) or (_is_unused(env, op.res_model, rec) if rec.active else '')
            if reason:
                problems.append({'code': op.code, 'reason': "Створене вже використано: %s" % reason})
        elif op.op == 'archive':
            if rec.active:
                problems.append({'code': op.code, 'reason': "Запис змінено в Odoo після публікації"})
        elif read_values(rec, list(op.after or {})) != (op.after or {}):
            problems.append({'code': op.code, 'reason': "Запис змінено в Odoo після публікації"})
    return problems


def _is_unused(env, model, rec):
    """Обладнання без заявок ТО, робочий центр без завдань (локації перевіряє `_used_locations`)."""
    if model == EQUIPMENT and 'maintenance.request' in env:
        if env['maintenance.request'].search_count([('equipment_id', '=', rec.id)]):
            return "є заявки ТО"
    elif model == WORKCENTER and 'mrp.workorder' in env:
        if env['mrp.workorder'].search_count([('workcenter_id', '=', rec.id)]):
            return "є завдання"
    return ''


def rollback_version(site, version):
    """Відкат публікації: обернені операції в зворотному порядку (створене → в архів, значення назад, архівне
    відновити).

    Лише записи Odoo; чернетка не змінюється. Повертає `{'reverted': n, 'version': version}`."""
    env = site.env
    if not (env.su or env.user.has_group('td_constructor.group_td_constructor_manager')):
        raise PublishError('rights', "Відкотити публікацію може лише менеджер конструктора.")
    site, version = site.sudo(), version.sudo()
    if version.site_id != site:
        raise PublishError('not_found', "Версію не знайдено.")
    problems = rollback_problems(version)
    if problems:
        raise PublishError('rollback_blocked', "Відкат неможливий: %s." % problems[0]['reason'], problems)
    try:
        with env.cr.savepoint():
            _lock_site(env, site)
            return _rollback(site.with_context(f3d_no_touch=True, tracking_disable=True, mail_notrack=True), version)
    except (PublishError, UserError):
        env.invalidate_all()
        raise
    except Exception as exc:  # noqa: BLE001
        env.invalidate_all()
        _logger.exception("Відкат версії %s відкотився", version.id)
        raise PublishError(
            'rollback', "Відкат скасовано через помилку: %s" % (str(exc)[:300] or exc.__class__.__name__)
        ) from exc


def _rollback(site, version):
    env = site.env
    version = version.with_env(env)
    n = 0
    for op in version.op_ids.sorted('seq', reverse=True):
        rec = env[op.res_model].with_context(active_test=False).browse(op.res_id).exists()
        if not rec:
            continue
        if op.op == 'create':
            rec.write({'active': False})
            _forget_draft_link(env, op)
        elif op.op == 'archive':
            rec.write({'active': True})
        else:
            rec.write(write_vals(dict(op.before), record=rec))
        op.rolled_back = True
        n += 1
    version.write({'rolled_back_at': fields.Datetime.now(), 'rolled_back_by_id': env.user.id})
    return {'reverted': n, 'version': version}


def _forget_draft_link(env, op):
    """Відкат створення правила: чернетка забуває зв'язок із записом Odoo (наступний план створить його знову)."""
    link = {PUTAWAY: ('td.putaway.rule', 'odoo_rule_id'), ORDERPOINT: ('td.replenish.rule', 'odoo_orderpoint_id')}.get(
        op.res_model
    )
    if link:
        env[link[0]].with_context(active_test=False).search([(link[1], '=', op.res_id)]).write({link[1]: False})


def publish_log(site, limit=20):
    """Журнал публікацій площадки (API-18): версії з числом операцій за видами й ознакою «можна відкотити»."""
    site = site.sudo()
    versions = site.env['td.layout.version'].search(
        [('site_id', '=', site.id), ('kind', '=', 'publish')], order='n desc', limit=limit
    )
    out = []
    for ver in versions:
        problems = rollback_problems(ver) if ver.op_ids and not ver.rolled_back_at else []
        out.append(
            {
                'id': ver.id,
                'n': ver.n,
                'published_at': str(ver.published_at),
                'by': ver.published_by_id.name or '',
                'note': ver.note or '',
                'counts': op_counts(ver),
                'ops': len(ver.op_ids),
                'rolled_back': bool(ver.rolled_back_at),
                'rolled_back_at': str(ver.rolled_back_at) if ver.rolled_back_at else None,
                'rolled_back_by': ver.rolled_back_by_id.name or '',
                'can_rollback': bool(ver.op_ids) and not ver.rolled_back_at and not problems,
                'reason': problems[0]['reason'] if problems else '',
            }
        )
    return out


def op_rows(version, limit=500):
    """Операції версії для показу в журналі: без службових полів."""
    return [
        {
            'seq': op.seq,
            'op': op.op,
            'res_model': op.res_model,
            'res_id': op.res_id,
            'code': op.code or '',
            'before': op.before or {},
            'after': op.after or {},
            'rolled_back': op.rolled_back,
        }
        for op in version.op_ids.sorted('seq')[:limit]
    ]
