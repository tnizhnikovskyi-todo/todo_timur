"""Показники по кодах для карти й картки: залишки, заповнення, вік, рух, min/max (F06, F07; API-13, API-14).

Код комірки — `stock.location.td_code`, площадка — `td_site_id`. Читання йде від імені сервера (`sudo`) і лише по
локаціях площадки: доступ до площадки перевіряє контролер (record rules + група «Перегляд»). Агрегати за локацією:
`qty`, `reserved`, `fill` (частка ємності категорії зберігання: за кількістю товару або за вагою; `None` — ємність
не задано), `in_date` / `age_days` (найстаріша партія із залишком), `moves` (рядки руху `stock.move.line` за N днів зі
`stock_days`), `min` / `max` (правила поповнення `stock.warehouse.orderpoint` локації). Відповідь ріжеться пачками
(≤ 2 МБ, `limit` локацій).
"""

import json
from collections import defaultdict
from datetime import timedelta

from odoo import fields

LOCATION_BATCH = 2000
MAX_BYTES = 2 * 1024 * 1024
DETAIL_ROWS = 50
DETAIL_MOVES = 20
FIND_LIMIT = 500


def stock_days(env):
    """Період руху (дні): параметр `td.constructor.stock_days`, за замовчуванням 90."""
    try:
        return max(1, int(env['ir.config_parameter'].sudo().get_param('td.constructor.stock_days', 90)))
    except (TypeError, ValueError):
        return 90


def site_locations(env, site, codes=None, offset=0, limit=LOCATION_BATCH):
    """Локації площадки з кодом сцени (усі чи за списком кодів), по `td_code`; пачка `offset`/`limit`."""
    domain = [('td_site_id', '=', site.id), ('td_code', '!=', False)]
    if codes is not None:
        domain.append(('td_code', 'in', list(codes)))
    return env['stock.location'].sudo().search(domain, order='td_code, id', offset=offset, limit=limit)


def _age_days(in_date, now):
    return max(0, (now - in_date).days) if in_date else None


def _capacity_maps(locations):
    """Ємність категорій: {(категорія, товар): кількість}, {категорія: макс. вага}."""
    by_product = {}
    max_weight = {}
    for cat in locations.storage_category_id:
        max_weight[cat.id] = cat.max_weight or 0.0
        for cap in cat.product_capacity_ids:
            by_product[(cat.id, cap.product_id.id)] = cap.quantity
    return by_product, max_weight


def _fill(category_id, by_product, max_weight, per_product, weights):
    """Заповнення: сума qty/ємність товару; без ємностей товарів — вага / макс. вага; нічого не задано — None."""
    if not category_id:
        return None, None
    caps = [cap for (cat, _prod), cap in by_product.items() if cat == category_id and cap]
    ratios = [
        qty / by_product[(category_id, prod)]
        for prod, qty in per_product.items()
        if by_product.get((category_id, prod))
    ]
    if ratios:
        return round(min(1.0, sum(ratios)), 3), max(caps)
    if max_weight.get(category_id):
        weight = sum(qty * weights.get(prod, 0.0) for prod, qty in per_product.items())
        return round(min(1.0, weight / max_weight[category_id]), 3), max_weight[category_id]
    if caps and not per_product:
        return 0.0, max(caps)
    return None, None


def stock_state(env, site, codes=None, days=None, detail=False, offset=0, limit=LOCATION_BATCH):
    """Залишки й показники по кодах (API-13). Повертає {at, days, demo, truncated, next, codes: {код: {...}}}."""
    days = days or stock_days(env)
    now = fields.Datetime.now()
    since = now - timedelta(days=days)
    locations = site_locations(env, site, codes, offset, limit)
    ids = locations.ids
    Quant = env['stock.quant'].sudo()
    quants = (
        Quant.search_read(
            [('location_id', 'in', ids)],
            ['location_id', 'product_id', 'lot_id', 'package_id', 'quantity', 'reserved_quantity', 'in_date'],
            order='location_id, in_date, id',
        )
        if ids
        else []
    )
    by_loc = defaultdict(list)
    for q in quants:
        by_loc[q['location_id'][0]].append(q)
    product_ids = {q['product_id'][0] for q in quants}
    weights = (
        {p['id']: p['weight'] for p in env['product.product'].sudo().browse(product_ids).read(['weight'])}
        if product_ids
        else {}
    )
    by_product, max_weight = _capacity_maps(locations)
    moves = defaultdict(int)
    if ids:
        MoveLine = env['stock.move.line'].sudo()
        base = [('date', '>=', since), ('state', '=', 'done')]
        for field in ('location_id', 'location_dest_id'):
            for loc, count in MoveLine._read_group(base + [(field, 'in', ids)], [field], ['__count']):
                moves[loc.id] += count
    points = defaultdict(lambda: [0.0, 0.0, False])
    if ids:
        for rec in (
            env['stock.warehouse.orderpoint']
            .sudo()
            .search_read(
                [('location_id', 'in', ids), ('active', '=', True)],
                ['location_id', 'product_min_qty', 'product_max_qty'],
            )
        ):
            slot = points[rec['location_id'][0]]
            slot[0] += rec['product_min_qty']
            slot[1] += rec['product_max_qty']
            slot[2] = True
    out = {}
    size = 0
    truncated = False
    last = offset
    for loc in locations:
        rows = [q for q in by_loc.get(loc.id, []) if q['quantity'] > 0]
        per_product = defaultdict(float)
        for q in rows:
            per_product[q['product_id'][0]] += q['quantity']
        dates = [q['in_date'] for q in rows if q['in_date']]
        oldest = min(dates) if dates else None
        fill, capacity = _fill(loc.storage_category_id.id, by_product, max_weight, per_product, weights)
        entry = {
            'qty': round(sum(q['quantity'] for q in rows), 4),
            'reserved': round(sum(q['reserved_quantity'] for q in rows), 4),
            'fill': fill,
            'capacity': capacity,
            'in_date': fields.Datetime.to_string(oldest) if oldest else None,
            'age_days': _age_days(oldest, now),
            'moves': moves.get(loc.id, 0),
            'min': round(points[loc.id][0], 4) if loc.id in points else None,
            'max': round(points[loc.id][1], 4) if loc.id in points else None,
            'top_product': rows and max(rows, key=lambda q: q['quantity'])['product_id'][1] or None,
            'location_id': loc.id,
        }
        if detail:
            entry['detail'] = _detail(env, loc, rows, now, since)
        size += len(json.dumps(entry)) + len(loc.td_code) + 6
        if size > MAX_BYTES and out:
            truncated = True
            break
        out[loc.td_code] = entry
        last += 1
    return {
        'at': fields.Datetime.to_string(now),
        'days': days,
        'demo': False,
        'truncated': truncated or (len(locations) == limit and codes is None),
        'next': last,
        'codes': out,
    }


def _detail(env, loc, rows, now, since):
    """Подробиці для картки: рядки залишків, рух за період, правила розміщення, категорія."""
    products = env['product.product'].sudo().browse([q['product_id'][0] for q in rows])
    refs = {p.id: p.default_code or '' for p in products}
    items = []
    for q in rows[:DETAIL_ROWS]:
        items.append(
            {
                'product': q['product_id'][1],
                'ref': refs.get(q['product_id'][0], ''),
                'qty': q['quantity'],
                'reserved': q['reserved_quantity'],
                'lot': q['lot_id'][1] if q['lot_id'] else '',
                'package': q['package_id'][1] if q['package_id'] else '',
                'in_date': fields.Datetime.to_string(q['in_date']) if q['in_date'] else None,
                'age_days': _age_days(q['in_date'], now),
            }
        )
    lines = (
        env['stock.move.line']
        .sudo()
        .search(
            [
                ('date', '>=', since),
                ('state', '=', 'done'),
                '|',
                ('location_id', '=', loc.id),
                ('location_dest_id', '=', loc.id),
            ],
            order='date desc, id desc',
            limit=DETAIL_MOVES,
        )
    )
    moves = [
        {
            'date': fields.Datetime.to_string(ml.date),
            'product': ml.product_id.display_name,
            'qty': ml.quantity,
            'from': ml.location_id.td_code or ml.location_id.complete_name,
            'to': ml.location_dest_id.td_code or ml.location_dest_id.complete_name,
        }
        for ml in lines
    ]
    rules = [
        '%s → %s' % (r.product_id.display_name or r.category_id.display_name or '—', r.location_in_id.display_name)
        for r in env['stock.putaway.rule'].sudo().search([('location_out_id', '=', loc.id)], limit=10)
    ]
    return {'rows': items, 'moves': moves, 'rules': rules, 'category': loc.storage_category_id.name or None}


FIND_MODES = {
    'product': ('product_id.name', 'product_id.default_code'),
    'lot': ('lot_id.name',),
    'package': ('package_id.name',),
    'any': ('product_id.name', 'product_id.default_code', 'lot_id.name', 'package_id.name'),
}


def stock_find(env, site, q, mode='any', limit=FIND_LIMIT):
    """«Де лежить» (API-14): усі слова запиту мають зустрітися в одному залишку (товар, артикул, партія, упаковка)."""
    words = [w for w in (q or '').split() if w]
    if not words:
        return {'hits': [], 'demo': False}
    paths = FIND_MODES.get(mode) or FIND_MODES['any']
    domain = [('quantity', '>', 0), ('location_id.td_site_id', '=', site.id), ('location_id.td_code', '!=', False)]
    for word in words:
        clause = [(path, 'ilike', word) for path in paths]
        domain += ['|'] * (len(clause) - 1) + clause
    quants = env['stock.quant'].sudo().search(domain, order='location_id, id', limit=limit)
    codes = {}
    refs = {p.id: p.default_code or '' for p in quants.product_id}
    for q_ in quants:
        item = {
            'product': q_.product_id.display_name,
            'ref': refs.get(q_.product_id.id, ''),
            'qty': q_.quantity,
            'lot': q_.lot_id.name or '',
            'package': q_.package_id.name or '',
        }
        codes.setdefault(q_.location_id.td_code, []).append(item)
    return {'hits': [{'code': code, 'items': items} for code, items in sorted(codes.items())], 'demo': False}
