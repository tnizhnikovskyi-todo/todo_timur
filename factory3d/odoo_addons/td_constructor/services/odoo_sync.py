"""Стрічка локацій Odoo й розбіжності з базою порівняння (F10, F02-09, F02-12; API-16).

Нейтральна стрічка (`locations_feed`) — локації складу площадки з усіма вкладеними (типи internal і view), їхні
назви, батьки, штрихкоди й сума залишків; ядро JS (`core/constructor/structure.js`) будує з неї зони, ряди й місця за
правилами розбору кодів (`site.parse_rules`). База порівняння — вкладення `site.odoo_baseline_id` (стрічка на момент
останнього «Оновити з Odoo»); `diff_feeds` дає розбіжності з'явилося / зникло / перейменовано / інший батько
(дзеркало `diffFeeds` у `core/constructor/artifact/sample_locations.js`).

Схема `site.parse_rules` (R-22): `{v: 1, rules: [{id, mode: mask|regex, mask|regex, type, enabled}], tray: [{code,
name, parent, usage, reason}], tray_more}` — правила розбору кодів і лоток «Не розміщено»; `normalize_parse_rules` її
перевіряє (дзеркало `normalizeRules` у `parse_codes.js`). Читання локацій і залишків іде від імені сервера (`sudo`)
після перевірки групи «Перегляд» у контролері."""

import base64
import json
import re

from odoo import fields
from odoo.exceptions import UserError, ValidationError

FEED_BATCH = 20000
FEED_MAX = 50000
RULES_MAX = 30
TRAY_MAX = 5000
TEXT_MAX = 160
RULE_TYPES = ('auto', 'pallet_rack', 'shelf', 'cantilever', 'floor_stack', 'floor_spot')
PART_NAMES = {
    *('зона', 'zone', 'ряд', 'row', 'aisle', 'секція', 'секция', 'bay', 'section'),
    *('ярус', 'level', 'tier', 'позиція', 'позиция', 'pos', 'position', 'префікс', 'префикс', 'prefix'),
}
USAGES = ('internal', 'view')
BASELINE_NAME = 'td_constructor_odoo_baseline.json'


# --- схема parse_rules -------------------------------------------------------------------------------
def _text(value, label, limit):
    if value is None:
        return ''
    if not isinstance(value, str):
        raise ValidationError("%s: очікується рядок." % label)
    return value[:limit]


def _check_mask(mask):
    if not mask.strip():
        raise ValidationError("Маска порожня.")
    stripped = re.sub(r'\{([^{}]*)\}', lambda m: _check_part(m.group(1)), mask)
    if '{' in stripped or '}' in stripped:
        raise ValidationError("Маска: дужки { } мають обрамляти назву частини.")


def _check_part(body):
    name = body.split(':', 1)[0].strip().lower()
    if name not in PART_NAMES:
        raise ValidationError("Маска: невідома частина {%s}." % body.strip())
    return ''


def _check_regex(regex):
    if not regex.strip():
        raise ValidationError("Регулярний вираз порожній.")
    try:
        re.compile(re.sub(r'\(\?<([A-Za-z_]\w*)>', r'(?P<\1>', regex))
    except re.error as exc:
        raise ValidationError("Регулярний вираз хибний: %s" % exc) from exc


def normalize_parse_rules(value):
    """`parse_rules` → чистий словник за схемою (невідоме відкидається; хибне — `ValidationError`). Порожнє → `{}`."""
    if not value:
        return {}
    if not isinstance(value, dict):
        raise ValidationError("parse_rules: очікується об'єкт.")
    rules = value.get('rules') or []
    if not isinstance(rules, list) or len(rules) > RULES_MAX:
        raise ValidationError("parse_rules.rules: список до %d правил." % RULES_MAX)
    out_rules = []
    for index, rule in enumerate(rules):
        if not isinstance(rule, dict):
            raise ValidationError("Правило %d: очікується об'єкт." % (index + 1))
        mode = 'regex' if rule.get('mode') == 'regex' else 'mask'
        item = {
            'id': (_text(rule.get('id'), 'id', 24) or 'r%d' % (index + 1)),
            'mode': mode,
            'type': rule.get('type') if rule.get('type') in RULE_TYPES else 'auto',
            'enabled': rule.get('enabled') is not False,
        }
        body = _text(rule.get(mode), 'Правило %d' % (index + 1), TEXT_MAX)
        (_check_regex if mode == 'regex' else _check_mask)(body)
        item[mode] = body
        out_rules.append(item)
    out = {'v': 1, 'rules': out_rules}
    tray = value.get('tray') or []
    if not isinstance(tray, list) or len(tray) > TRAY_MAX:
        raise ValidationError("parse_rules.tray: список до %d записів." % TRAY_MAX)
    if tray:
        out['tray'] = [
            {
                'code': _text(t.get('code'), 'tray.code', 64),
                'name': _text(t.get('name'), 'tray.name', 128),
                'parent': _text(t.get('parent'), 'tray.parent', 256),
                'usage': _text(t.get('usage'), 'tray.usage', 16) or 'internal',
                'reason': _text(t.get('reason'), 'tray.reason', 32),
            }
            for t in tray
            if isinstance(t, dict) and t.get('code')
        ]
    more = value.get('tray_more')
    if isinstance(more, int) and not isinstance(more, bool) and more > 0:
        out['tray_more'] = more
    return out


# --- стрічка ------------------------------------------------------------------------------------------
def warehouse_and_root(env, site, warehouse_id=None):
    """(склад, коренева локація стрічки): вказаний склад, інакше склад площадки (`warehouse_id`, склад батьківської
    локації), інакше
    перший склад компанії. Корінь — батьківська локація площадки (якщо вона в цьому складі), інакше `lot_stock_id`,
    інакше вигляд складу."""
    Warehouse = env['stock.warehouse'].sudo()
    warehouse = Warehouse.browse(int(warehouse_id)) if warehouse_id else Warehouse
    if warehouse_id and not warehouse.exists():
        raise UserError("Склад %s не знайдено." % warehouse_id)
    parent = site.default_parent_location_id.sudo()
    if not warehouse:
        warehouse = site.warehouse_id.sudo() or (parent.warehouse_id if parent else Warehouse)
    if not warehouse:
        warehouse = Warehouse.search([('company_id', '=', site.company_id.id)], limit=1) or Warehouse.search(
            [], limit=1
        )
    if not warehouse:
        raise UserError("У Odoo немає складів: структуру прочитати нема з чого.")
    if parent and parent.warehouse_id == warehouse:
        root = parent
    else:
        root = warehouse.lot_stock_id or warehouse.view_location_id
    return warehouse, root


def locations_feed(env, site, warehouse_id=None, offset=0, limit=FEED_BATCH):
    """Нейтральна стрічка (API-16 `feed`): {root, warehouse, warehouses, locations, truncated, next}; локація — {id,
    code, name, parent,
    parent_id, usage, barcode, qty, active}. `code` = td_code | штрихкод | ім'я (код місця в конструкторі)."""
    warehouse, root = warehouse_and_root(env, site, warehouse_id)
    Location = env['stock.location'].sudo()
    domain = [('id', 'child_of', root.id), ('usage', 'in', USAGES)]
    total = Location.search_count(domain)
    limit = max(1, min(int(limit or FEED_BATCH), FEED_BATCH))
    offset = max(0, int(offset or 0))
    records = Location.search(domain, order='complete_name, id', offset=offset, limit=limit)
    qty = {}
    if records:
        for location, total_qty in (
            env['stock.quant']
            .sudo()
            ._read_group([('location_id', 'in', records.ids), ('quantity', '>', 0)], ['location_id'], ['quantity:sum'])
        ):
            qty[location.id] = total_qty
    rows = []
    for rec in records:
        parent = rec.location_id
        rows.append(
            {
                'id': rec.id,
                'code': rec.td_code or rec.barcode or rec.name,
                'name': rec.name,
                'parent': parent.complete_name if parent else '',
                'parent_id': parent.id if parent else None,
                'usage': rec.usage,
                'barcode': rec.barcode or '',
                'qty': round(qty.get(rec.id, 0.0), 4),
                'active': True,
            }
        )
    end = offset + len(records)
    truncated = end < min(total, FEED_MAX)
    return {
        'root': root.complete_name,
        'warehouse': {'id': warehouse.id, 'name': warehouse.name, 'code': warehouse.code},
        'locations': rows,
        'total': total,
        'truncated': truncated,
        'next': end if truncated else None,
    }


def full_feed(env, site, warehouse_id=None):
    """Уся стрічка одним списком (для порівняння): партіями по `FEED_BATCH`, не більше `FEED_MAX` локацій."""
    first = locations_feed(env, site, warehouse_id, 0, FEED_BATCH)
    rows = list(first['locations'])
    page = first
    while page['truncated'] and len(rows) < FEED_MAX:
        page = locations_feed(env, site, warehouse_id, page['next'], FEED_BATCH)
        rows.extend(page['locations'])
    return {**first, 'locations': rows[:FEED_MAX], 'truncated': first['total'] > FEED_MAX, 'next': None}


# --- розбіжності --------------------------------------------------------------------------------------
def diff_feeds(old, new):
    """Розбіжності двох стрічок: ключ — `id` (він є в обох), інакше код. Зміна коду за того самого id — «зникло» +
    «з'явилося»; зміна назви
    за того самого коду — «перейменовано»; іншого батька — «перенесено». Неактивні вважаються відсутніми."""

    def key(loc):
        return ('id', loc['id']) if loc.get('id') is not None else ('code', loc['code'])

    prev = {key(loc): loc for loc in old if loc.get('active', True)}
    nxt = {key(loc): loc for loc in new if loc.get('active', True)}
    out = {'appeared': [], 'disappeared': [], 'renamed': [], 'moved': []}
    for k, cur in nxt.items():
        was = prev.get(k)
        if was is None:
            out['appeared'].append(cur)
        elif was['code'] != cur['code']:
            out['disappeared'].append(was)
            out['appeared'].append(cur)
        else:
            if was['name'] != cur['name']:
                out['renamed'].append(
                    {'id': cur.get('id'), 'code': cur['code'], 'old': was['name'], 'new': cur['name']}
                )
            if (was.get('parent') or '') != (cur.get('parent') or ''):
                out['moved'].append(
                    {
                        'id': cur.get('id'),
                        'code': cur['code'],
                        'old_parent': was.get('parent') or '',
                        'new_parent': cur.get('parent') or '',
                        'new_parent_id': cur.get('parent_id'),
                    }
                )
    for k, was in prev.items():
        if k not in nxt:
            out['disappeared'].append(was)
    return out


# --- база порівняння ----------------------------------------------------------------------------------
_FIELDS = ('id', 'code', 'name', 'parent')


def load_baseline(site):
    """Стрічка бази порівняння (список локацій) або None, якщо бази ще немає."""
    attachment = site.sudo().odoo_baseline_id
    if not attachment or not attachment.datas:
        return None
    try:
        rows = json.loads(base64.b64decode(attachment.datas))
    except ValueError:
        return None
    return [dict(zip(_FIELDS, row, strict=False)) | {'active': True} for row in rows]


def save_baseline(site, locations):
    """База порівняння := поточна стрічка (компактно: [id, code, name, parent])."""
    site = site.sudo()
    payload = json.dumps(
        [[loc.get(f) for f in _FIELDS] for loc in locations], ensure_ascii=False, separators=(',', ':')
    )
    data = base64.b64encode(payload.encode())
    attachment = site.odoo_baseline_id
    if attachment:
        attachment.write({'datas': data})
    else:
        attachment = (
            site.env['ir.attachment']
            .sudo()
            .create(
                {
                    'name': BASELINE_NAME,
                    'datas': data,
                    'res_model': 'td.site',
                    'res_id': site.id,
                    'type': 'binary',
                    'mimetype': 'application/json',
                }
            )
        )
        site.write({'odoo_baseline_id': attachment.id})
    return fields.Datetime.now()


def sync(env, site, warehouse_id=None, save=True):
    """«Оновити з Odoo» (F02-12): читає стрічку, порівнює з базою; бази ще немає — створює її (розбіжностей немає), а
    користувач без права запису (`save=False`) бази не створює: `baseline: 'missing'`. Повертає {feed (без списку
    локацій), diff, baseline: 'created'|'existing'|'missing'}; базу після вибору користувача оновлює `save_baseline`."""
    feed = full_feed(env, site, warehouse_id)
    base = load_baseline(site)
    summary = {k: v for k, v in feed.items() if k != 'locations'}
    summary['count'] = len(feed['locations'])
    if base is None:
        if save:
            save_baseline(site, feed['locations'])
        return {
            'feed': summary,
            'diff': {'appeared': [], 'disappeared': [], 'renamed': [], 'moved': []},
            'baseline': 'created' if save else 'missing',
        }
    return {'feed': summary, 'diff': diff_feeds(base, feed['locations']), 'baseline': 'existing'}
