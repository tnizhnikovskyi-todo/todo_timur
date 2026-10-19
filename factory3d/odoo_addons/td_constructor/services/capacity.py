"""Місткість, категорії зберігання, атрибути зони, min/max (F03; перевірка `cell_load`).

* категорії зберігання (`stock.storage.category` + ємності) — прямий виклик API-12 із підтвердженням (CD-20), у план
  не входять;
* довідники «Функція зони» (10) і «Атрибути зони» (4): `td.term` із `data/td_term_data.xml` (читає `zone_terms`);
* правила поповнення min/max (`td.replenish.rule` → `stock.warehouse.orderpoint`): будівник плану і застосовувач;
* залишки за кодами комірок (`stock_loads`) і перевірка `cell_load` (вага запасу з `stock.quant` проти `max_load_kg`
  комірки або `max_weight` категорії); перевірка чиста: працює з даними, що їх кладе в `scene.extra` будівник плану;
* розділ знімка `replenish_rules` (R-14): правила входять до версії.

Реєстрація — в реєстрах `registry.py` (`CHECKS`, `PLAN_BUILDERS`, `SNAPSHOT_SECTIONS`) і `publish.APPLIERS`.
"""

from . import checks as checks_mod, publish as pub, state as state_mod
from .registry import CHECKS, PLAN_BUILDERS, SNAPSHOT_SECTIONS, SnapshotSection

ALLOW_NEW_PRODUCT = ('empty', 'same', 'mixed')
MAX_CAPACITY_ROWS = 200
CATEGORY = 'stock.storage.category'


# --- довідники зони (F03-03, F03-04) --------------------------------------------------------------------------


def zone_terms(env):
    """Довідники зони з БД (`data/td_term_data.xml`): `(functions, attrs)` — активні терміни за порядком."""
    Term = env['td.term'].sudo()
    out = {'zone_function': [], 'zone_attr': []}
    for rec in Term.search([('term_type', 'in', tuple(out))], order='sequence, id'):
        out[rec.term_type].append(
            {'id': rec.id, 'key': rec.key, 'name': rec.name, 'color': rec.color or '', 'value': rec.value or ''}
        )
    return out['zone_function'], out['zone_attr']


# --- одиниці виміру Odoo (конфігурація product) ---------------------------------------------------------------


def unit_factors(env):
    """Множники до метрів / кілограмів / м³: Odoo зберігає розміри в мм (або футах), вагу в кг (або фунтах)."""
    get = env['ir.config_parameter'].sudo().get_param
    feet = get('product.volume_in_cubic_feet') in ('1', 'True', True)
    lbs = get('product.weight_in_lbs') in ('1', 'True', True)
    return {
        'length': 0.3048 if feet else 0.001,
        'weight': 0.45359237 if lbs else 1.0,
        'volume': 0.0283168466 if feet else 1.0,
    }


# --- категорії зберігання (F03-02, API-12) --------------------------------------------------------------------


def category_dict(cat):
    rows = [
        {
            'id': cap.id,
            'product_id': cap.product_id.id or None,
            'product': cap.product_id.display_name or None,
            'package_type_id': cap.package_type_id.id or None,
            'package_type': cap.package_type_id.display_name or None,
            'quantity': cap.quantity,
        }
        for cap in cat.capacity_ids
    ]
    return {
        'id': cat.id,
        'name': cat.name,
        'max_weight': cat.max_weight,
        'allow_new_product': cat.allow_new_product,
        'company_id': cat.company_id.id or None,
        'capacity': rows,
        'locations': len(cat.location_ids),
        'in_use': bool(cat.location_ids),
    }


def list_categories(env, company):
    cats = env[CATEGORY].sudo().search([('company_id', 'in', (False, company.id))])
    return [category_dict(c) for c in cats]


def _capacity_commands(env, rows):
    if not isinstance(rows, list) or len(rows) > MAX_CAPACITY_ROWS:
        raise ValueError("Ємність: очікується список не довший за %d рядків." % MAX_CAPACITY_ROWS)
    cmds = [(5, 0, 0)]
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Ємність: рядок має бути об'єктом.")
        product, package = row.get('product_id') or False, row.get('package_type_id') or False
        qty = row.get('quantity')
        if bool(product) == bool(package):
            raise ValueError("Ємність: вкажіть товар або тип упаковки (одне з двох).")
        if not isinstance(qty, int | float) or isinstance(qty, bool) or qty <= 0:
            raise ValueError("Ємність: кількість має бути додатним числом.")
        key = ('p', product) if product else ('k', package)
        if key in seen:
            raise ValueError("Ємність: товар або упаковка повторюється.")
        seen.add(key)
        if product and not env['product.product'].sudo().browse(product).exists():
            raise ValueError("Ємність: товар не знайдено.")
        if package and not env['stock.package.type'].sudo().browse(package).exists():
            raise ValueError("Ємність: тип упаковки не знайдено.")
        cmds.append((0, 0, {'product_id': product, 'package_type_id': package, 'quantity': float(qty)}))
    return cmds


def save_category(env, company, vals, cat_id=None):
    """Створює або змінює категорію зберігання (менеджер, після підтвердження). `ValueError` — помилка вхідних даних."""
    Cat = env[CATEGORY].sudo()
    name = vals.get('name', '').strip() if isinstance(vals.get('name'), str) else ''
    if not name:
        raise ValueError("Назва категорії обов'язкова.")
    max_weight = vals.get('max_weight', 0)
    if not isinstance(max_weight, int | float) or isinstance(max_weight, bool) or max_weight < 0:
        raise ValueError("Максимальна вага має бути невід'ємним числом.")
    policy = vals.get('allow_new_product', 'mixed')
    if policy not in ALLOW_NEW_PRODUCT:
        raise ValueError("Політика має бути однією з: %s." % ", ".join(ALLOW_NEW_PRODUCT))
    data = {'name': name, 'max_weight': float(max_weight), 'allow_new_product': policy}
    if 'capacity' in vals:
        data['capacity_ids'] = _capacity_commands(env, vals['capacity'])
    if cat_id:
        cat = Cat.browse(cat_id).exists()
        if not cat or (cat.company_id and cat.company_id != company):
            raise LookupError("Категорію не знайдено.")
        cat.write(data)
    else:
        cat = Cat.create(dict(data, company_id=company.id))
    return cat


def delete_category(env, company, cat_id):
    """Видаляє лише категорію без локацій, правил розміщення й місць чернеток (F03-02: видалити можна лише нову)."""
    cat = env[CATEGORY].sudo().browse(cat_id).exists()
    if not cat or (cat.company_id and cat.company_id != company):
        raise LookupError("Категорію не знайдено.")
    used = cat.location_ids
    for model, field in (
        ('stock.putaway.rule', 'storage_category_id'),
        ('td.slot', 'storage_category_id'),
        ('td.putaway.rule', 'storage_category_id'),
    ):
        used = used or env[model].sudo().with_context(active_test=False).search([(field, '=', cat.id)], limit=1)
    if used:
        raise ValueError("Категорію вже використано: її не можна видалити.")
    cat.unlink()


def list_strategies(env):
    return [{'id': s.id, 'name': s.name, 'method': s.method} for s in env['product.removal'].sudo().search([])]


# --- залишки й вага запасу (F03-08, cell_load) ----------------------------------------------------------------


def stock_loads(env, codes):
    """`{код: {qty, weight_kg, products}}` для комірок із залишком (`stock.quant`, quantity > 0)."""
    codes = [c for c in codes if c]
    if not codes:
        return {}
    locs = env['stock.location'].sudo().search([('td_code', 'in', codes)])
    if not locs:
        return {}
    factors = unit_factors(env)
    groups = (
        env['stock.quant']
        .sudo()
        ._read_group(
            [('location_id', 'in', locs.ids), ('quantity', '>', 0)], ['location_id', 'product_id'], ['quantity:sum']
        )
    )
    by_loc = {}
    for loc, product, qty in groups:
        row = by_loc.setdefault(loc.id, {'qty': 0.0, 'weight_kg': 0.0, 'products': 0})
        row['qty'] += qty
        row['weight_kg'] += qty * (product.weight or 0.0) * factors['weight']
        row['products'] += 1
    return {loc.td_code: by_loc[loc.id] for loc in locs if loc.id in by_loc}


def site_cell_limits(site):
    """`{код: макс. вага, кг}` комірок площадки: `max_load_kg` (перевизначення/шаблон), інакше категорія зберігання."""
    zones = pub._zones(site)
    out = {}
    for slot in site.env['td.slot'].search([('site_id', '=', site.id), ('layer_id.active', '=', True)]):
        for cell in slot._td_cells():
            limit = cell['max_load_kg'] or 0.0
            if not limit:
                cat = pub.inherited('storage_category_id', slot, pub.zone_chain(zones, cell['x'], cell['y']))
                limit = cat.max_weight if cat else 0.0
            out[cell['code']] = limit
    return out


def check_cell_load(scene, config, eps):
    """`cell_load`: вага запасу (`extra.loads`) проти макс. ваги комірки (`extra.limits`, інакше `max_load_kg`)."""
    extra = getattr(scene, 'extra', None) or {}
    loads, limits = extra.get('loads') or {}, extra.get('limits') or {}
    issues = []
    for slot in scene.slots.values():
        for code, cell in scene.slot_cells(slot).items():
            load = loads.get(code)
            limit = limits.get(code) or cell['max_load_kg'] or 0.0
            if load and limit > 0 and load['weight_kg'] > limit + eps:
                issues.append(
                    {
                        'check': 'cell_load',
                        'severity': config['mode'],
                        'layer_id': slot['layer_id'],
                        'codes': [code],
                        'message': "%s: вага запасу %g кг перевищує допустимі %g кг"
                        % (code, round(load['weight_kg'], 2), limit),
                    }
                )
    return issues


CHECKS.register('cell_load', check_cell_load, sequence=80)


def plan_check_scene(site, extra):
    """Сцена перевірок із заданими даними в `scene.extra` (тести, API-15 `fit`); `{}` — без даних."""
    scene = checks_mod._Scene(state_mod.checks_state(site))
    scene.extra = dict(extra)
    return scene


def check_config(site, key):
    """Налаштування перевірки площадки або None (не налаштовано / вимкнено)."""
    config = site.check_config_ids.filtered(lambda c: c.check_key == key)[:1]
    if not config or not config.enabled:
        return None
    return {'check': key, 'enabled': True, 'mode': config.mode, 'params': config.params or {}}


def add_new_issues(issues, found):
    have = {(i['check'], i['message']) for i in issues}
    issues.extend(i for i in found if (i['check'], i['message']) not in have)


def check_extra(site, scene):
    """Дані БД для перевірок `cell_load`, `putaway_fit`, `code_conflict` (`scene.extra`): лише для ввімкнених, коди — із
    комірок сцени (з урахуванням адресації). Читання під sudo; викликається ледачо з `_Scene.extra` — тож живий
    API-05 і план публікації бачать ті самі зауваження."""
    on = {c.check_key for c in site.check_config_ids if c.enabled} & {'cell_load', 'putaway_fit', 'code_conflict'}
    if not on:
        return {}
    site = site.sudo()
    codes = [code for slot in scene.slots.values() for code in scene.slot_cells(slot)]
    extra = {}
    if on & {'cell_load', 'putaway_fit'}:
        extra['limits'] = site_cell_limits(site)
    if 'cell_load' in on:
        extra['loads'] = stock_loads(site.env, codes)
    if 'putaway_fit' in on:
        from . import putaway

        extra['putaway'] = putaway.rule_fit_inputs(site)
    if 'code_conflict' in on:
        extra['code_states'] = pub.code_states(site.env, site, codes)
    return extra


# --- правила поповнення min/max (F03-07) ------------------------------------------------------------------------


def resolve_target(site, env, lines, code='', location=None):
    """Ціль правила: наявна локація або комірка, що створюється цим планом.

    Повертає `{'location', 'depends', 'scope_uid', 'zone_uid', 'code'}`; порожні `location` і `depends` — не знайдено.
    """
    Loc = env['stock.location'].with_context(active_test=False)
    out = {'location': Loc, 'depends': '', 'scope_uid': '', 'zone_uid': '', 'code': code or ''}
    if location:
        out.update(location=location, code=location.td_code or location.barcode or location.complete_name)
        out['scope_uid'] = location.td_slot_uid or ''
        return out
    if not code:
        return out
    found = Loc.search([('td_code', '=', code), ('td_site_id', '=', site.id)], order='active desc', limit=1)
    if found and found.active:
        out.update(location=found, scope_uid=found.td_slot_uid or '')
        return out
    for line in lines:
        restoring = line['kind'] == 'attrs' and line['vals'].get('active') and line['res_id'] == found.id
        if line['res_model'] == pub.LOCATION and line['code'] == code and (line['kind'] == 'create' or restoring):
            out.update(
                location=found if restoring else Loc,
                depends=code,
                scope_uid=line['source_uid'],
                zone_uid=line['extra'].get('zone_uid', ''),
            )
            return out
    return out


def _orderpoint_name(rule, target):
    return "%s @ %s" % (rule.product_id.default_code or rule.product_id.display_name, target['code'] or '?')


def plan_orderpoints(site, env, lines, issues):
    """Чернетки `td.replenish.rule` → рядки для `stock.warehouse.orderpoint`; повертає число «без змін»."""
    Op = env[pub.ORDERPOINT].with_context(active_test=False)
    unchanged = 0
    rules = env['td.replenish.rule'].with_context(active_test=False).search([('site_id', '=', site.id)])
    for rule in rules:
        target = resolve_target(site, env, lines, rule.cell_code, rule.location_id)
        name = _orderpoint_name(rule, target)
        linked = rule.odoo_orderpoint_id
        extra = {'rule_uid': rule.uid, 'zone_uid': target['zone_uid'], 'target_code': target['code']}
        if rule.deleted or not rule.active:
            if linked and linked.active:
                line = pub._line(
                    'archive', pub.ORDERPOINT, name, name, None, linked, rule.uid, "буде архівовано",
                    dict(extra, explicit=True),
                )  # fmt: skip
                line['scope_uid'] = target['scope_uid']
                lines.append(line)
            continue
        loc = target['location']
        if not loc and not target['depends']:
            line = pub._line(
                'create', pub.ORDERPOINT, name, name, {}, None, rule.uid, "ціль правила не знайдено", extra
            )
            pub._block(line, "Не знайдено локацію %s" % (rule.cell_code or '—'), 'target')
            lines.append(line)
            issues.append(
                pub._issue(
                    'conflict', 'warn', "Правило поповнення %s: не знайдено локацію" % name, [rule.cell_code or '']
                )
            )
            continue
        want = {'product_min_qty': rule.min_qty, 'product_max_qty': rule.max_qty}
        existing = linked if linked and linked.active else Op
        if not existing and loc:  # той самий товар у тій самій локації: зв'язуємо (унікальність Odoo) або відновлюємо
            existing = Op.search(
                [
                    ('product_id', '=', rule.product_id.id),
                    ('location_id', '=', loc.id),
                    ('company_id', '=', site.company_id.id),
                ],
                limit=1,
            )
            extra['link'] = bool(existing)
        if existing:
            vals = {k: v for k, v in want.items() if existing[k] != v}
            if loc and existing.location_id != loc:
                vals['location_id'] = loc.id
            if not existing.active:
                vals['active'] = True
            if vals or extra.get('link'):
                text = pub._diff_text(existing, vals) if vals else "зв'язати з наявним правилом"
                lines.append(
                    pub._line(
                        'attrs', pub.ORDERPOINT, name, name, vals, existing, rule.uid, text, extra,
                        target['depends'], target['scope_uid'],
                    )
                )  # fmt: skip
            else:
                unchanged += 1
            continue
        if loc and not loc.warehouse_id:
            line = pub._line('create', pub.ORDERPOINT, name, name, {}, None, rule.uid, "локація поза складом", extra)
            pub._block(line, "Локація %s не належить жодному складу" % target['code'], 'warehouse')
            lines.append(line)
            continue
        vals = dict(want, product_id=rule.product_id.id, company_id=site.company_id.id)
        if loc:
            vals['location_id'] = loc.id
        card = "мін %s / макс %s" % (pub._fmt(rule.min_qty), pub._fmt(rule.max_qty))
        lines.append(
            pub._line(
                'create', pub.ORDERPOINT, name, name, vals, None, rule.uid, card, extra,
                target['depends'], target['scope_uid'],
            )
        )  # fmt: skip
    return unchanged


def apply_orderpoints(site, lines, records, ops):
    """Застосування рядків `stock.warehouse.orderpoint`: create / attrs / archive; зв'язує чернетки; пише журнал."""
    env = site.env
    Op = env[pub.ORDERPOINT].with_context(active_test=False)
    Rule = env['td.replenish.rule'].with_context(active_test=False)
    entries = []
    for line in lines:
        rule = Rule.search([('site_id', '=', site.id), ('uid', '=', line['extra'].get('rule_uid'))], limit=1)
        kind, vals = line['kind'], dict(line['vals'])
        target = records.get((pub.LOCATION, line['depends_code']))
        if target:
            vals['location_id'] = target.id
        if kind == 'create':
            rec = Op.create(vals)
            if rule:
                rule.odoo_orderpoint_id = rec
            ops.append(pub.make_op('create', pub.ORDERPOINT, rec, line['code'], {}, dict(vals, active=True)))
        elif kind == 'archive':
            rec = Op.browse(line['res_id'])
            rec.write({'active': False})
            ops.append(pub.make_op('archive', pub.ORDERPOINT, rec, line['code'], {'active': True}, {'active': False}))
        else:
            rec = Op.browse(line['res_id'])
            before = pub.read_values(rec, vals)
            if vals:
                rec.write(vals)
            if rule and rule.odoo_orderpoint_id != rec:
                rule.odoo_orderpoint_id = rec
            ops.append(pub.make_op('attrs', pub.ORDERPOINT, rec, line['code'], before, pub.read_values(rec, vals)))
        entries.append({'kind': kind, 'model': pub.ORDERPOINT, 'code': line['code'], 'id': rec.id})
    return entries


def _plan_capacity(site, env, lines, issues):
    # cell_load входить у зауваження плану через `run_site_checks` (`scene.extra`), тут лише правила поповнення
    return plan_orderpoints(site, env, lines, issues)


PLAN_BUILDERS.register('capacity', _plan_capacity, sequence=60)
pub.APPLIERS[pub.ORDERPOINT] = apply_orderpoints


# --- розділ знімка: правила поповнення (R-14) ---------------------------------------------------------------------


def snapshot_build(site):
    rules = (
        site.env['td.replenish.rule'].with_context(active_test=False).search([('site_id', '=', site.id)], order='uid')
    )
    return [
        {
            'uid': r.uid,
            'product_id': r.product_id.id,
            'cell_code': r.cell_code or None,
            'location_id': r.location_id.id or None,
            'min_qty': r.min_qty,
            'max_qty': r.max_qty,
            'deleted': r.deleted,
            'active': r.active,
        }
        for r in rules
    ]


def snapshot_apply(site, data):
    """Чернетка правил = знімок: за uid оновити/створити; відсутні зняти (зв'язані з Odoo — позначити `deleted`)."""
    env = site.env
    Rule = env['td.replenish.rule'].with_context(active_test=False, f3d_no_touch=True)
    have = {r.uid: r for r in Rule.search([('site_id', '=', site.id)])}
    seen = set()
    for item in data or []:
        if not env['product.product'].with_context(active_test=False).browse(item['product_id']).exists():
            continue
        vals = {
            'product_id': item['product_id'],
            'cell_code': item.get('cell_code') or False,
            'location_id': item.get('location_id') or False,
            'min_qty': item.get('min_qty') or 0.0,
            'max_qty': item.get('max_qty') or 0.0,
            'deleted': bool(item.get('deleted')),
            'active': item.get('active', True),
        }
        seen.add(item['uid'])
        if item['uid'] in have:
            have[item['uid']].write(vals)
        else:
            Rule.create(dict(vals, site_id=site.id, uid=item['uid']))
    for uid, rule in have.items():
        if uid in seen:
            continue
        if rule.odoo_orderpoint_id:
            rule.write({'deleted': True})
        else:
            rule.unlink()


SNAPSHOT_SECTIONS.register('replenish_rules', SnapshotSection(snapshot_build, snapshot_apply), sequence=60)
