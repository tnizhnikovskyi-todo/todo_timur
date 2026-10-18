"""Правила розміщення: підбір місця й перевірка «не вміститься» (F04, API-15).

* `td.putaway.rule` (чернетка) → `stock.putaway.rule`: будівник плану і застосовувач (лише публікацією, Q4); правило,
  що веде в комірку, яка ще не опублікована (`out_code`), залежить від її рядка створення (`depends_code`);
* «Куди покладе Odoo» (`where`): метод стратегії розміщення локації `_get_putaway_strategy`, лише застосовані правила;
* «Чи вміститься» (`fit_problems`, `check_putaway_fit`): вага/об'єм товару й габарити упаковки проти габаритів і
  макс. ваги комірки; невідоме пропускається; перевірка чиста — дані кладе в `scene.extra` будівник плану
  (`extra.putaway`);
* розділ знімка `putaway_rules` (R-14).
"""

from . import capacity, publish as pub, state as state_mod
from .registry import CHECKS, PLAN_BUILDERS, SNAPSHOT_SECTIONS, SnapshotSection

FIT_EPS = 1e-6


# --- вхідні дані «чи вміститься» ----------------------------------------------------------------------------


def _label(rule):
    if rule.product_id:
        return rule.product_id.default_code or rule.product_id.display_name
    if rule.category_id:
        return rule.category_id.display_name
    return "усі товари"


def item_of(env, product, packages, factors=None):
    """Дані товару й упаковок у метрах/кг/м³: `{weight_kg, volume_m3, packages: [{name, dims_m, max_weight_kg}]}`."""
    factors = factors or capacity.unit_factors(env)
    item = {'weight_kg': None, 'volume_m3': None, 'packages': []}
    if product:
        item['weight_kg'] = (product.weight or 0.0) * factors['weight'] or None
        item['volume_m3'] = (product.volume or 0.0) * factors['volume'] or None
    for pt in packages:
        dims = [(pt.packaging_length or 0.0), (pt.width or 0.0), (pt.height or 0.0)]
        item['packages'].append(
            {
                'name': pt.display_name,
                'dims_m': [d * factors['length'] for d in dims] if all(dims) else None,
                'max_weight_kg': (pt.max_weight or 0.0) * factors['weight'] or None,
            }
        )
    return item


def fit_problems(item, cell, limit_kg, eps=FIT_EPS):
    """Причини, чому товар/упаковка не вміщується в комірку (порожньо — вміщується або невідомо).

    `cell` — `{l, w, h}` у метрах; `limit_kg` — макс. вага комірки (0 — не задана)."""
    reasons = []
    cell_dims = sorted([cell.get('l') or 0.0, cell.get('w') or 0.0, cell.get('h') or 0.0])
    volume = (cell.get('l') or 0.0) * (cell.get('w') or 0.0) * (cell.get('h') or 0.0)
    if limit_kg and item.get('weight_kg') and item['weight_kg'] > limit_kg + eps:
        reasons.append("вага товару %g кг більша за %g кг комірки" % (round(item['weight_kg'], 3), limit_kg))
    if volume and item.get('volume_m3') and item['volume_m3'] > volume + eps:
        reasons.append("об'єм товару %g м³ більший за %g м³ комірки" % (round(item['volume_m3'], 4), round(volume, 4)))
    for pack in item.get('packages') or []:
        if limit_kg and pack.get('max_weight_kg') and pack['max_weight_kg'] > limit_kg + eps:
            reasons.append(
                "упаковка «%s» (до %g кг) важча за %g кг комірки"
                % (pack['name'], round(pack['max_weight_kg'], 3), limit_kg)
            )
        dims = pack.get('dims_m')
        if dims and all(cell_dims) and any(a > b + eps for a, b in zip(sorted(dims), cell_dims, strict=True)):
            reasons.append(
                "упаковка «%s» (%s м) не вміщується в габарит комірки"
                % (pack['name'], "×".join("%g" % round(d, 3) for d in dims))
            )
    return reasons


def rule_fit_inputs(site):
    """Для кожного діючого правила розміщення: `{uid, label, targets: [коди комірок чернетки], product…}`."""
    env = site.env
    factors = capacity.unit_factors(env)
    scene_codes = set()
    for slot in env['td.slot'].search([('site_id', '=', site.id), ('layer_id.active', '=', True)]):
        scene_codes.update(c['code'] for c in slot._f3d_cells())
    out = []
    for rule in env['td.putaway.rule'].search([('site_id', '=', site.id), ('deleted', '=', False)]):
        code = rule.out_code or (rule.out_location_id.td_code if rule.out_location_id else '')
        if not code or code not in scene_codes:
            continue
        item = item_of(env, rule.product_id, rule.package_type_ids, factors)
        if not (item['weight_kg'] or item['volume_m3'] or item['packages']):
            continue
        out.append(dict(item, uid=rule.uid, label=_label(rule), targets=[code]))
    return out


def _fit_findings(scene):
    """`[(правило, код, місце, причина)]` — правила (`extra.putaway`) проти габаритів і макс. ваги комірок-цілей."""
    extra = getattr(scene, 'extra', None) or {}
    rules, limits = extra.get('putaway') or [], extra.get('limits') or {}
    if not rules:
        return []
    cells = {}
    for slot in scene.slots.values():
        for code, cell in scene.slot_cells(slot).items():
            cells[code] = (slot, cell)
    out = []
    for rule in rules:
        for code in rule.get('targets') or []:
            slot, cell = cells.get(code, (None, None))
            if cell is None:
                continue
            limit = limits.get(code) or cell['max_load_kg'] or 0.0
            out.extend((rule, code, slot, reason) for reason in fit_problems(rule, cell, limit))
    return out


def check_putaway_fit(scene, config, eps):
    """`putaway_fit`: «Правило: не вміститься» — правила проти габаритів і макс. ваги комірки-цілі."""
    return [
        {
            'check': 'putaway_fit',
            'severity': config['mode'],
            'layer_id': slot['layer_id'],
            'codes': [code],
            'message': "Правило «%s»: не вміститься в %s — %s" % (rule['label'], code, reason),
        }
        for rule, code, slot, reason in _fit_findings(scene)
    ]


CHECKS.register('putaway_fit', check_putaway_fit, sequence=90)


def fit_rules(site):
    """API-15 `fit`: `{uid правила: [{code, reason}]}` — лише правила з проблемами (незалежно від налаштування)."""
    scene = capacity.plan_check_scene(
        site, {'putaway': rule_fit_inputs(site), 'limits': capacity.site_cell_limits(site)}
    )
    out = {}
    for rule, code, _slot, reason in _fit_findings(scene):
        out.setdefault(rule['uid'], []).append({'code': code, 'reason': reason})
    return out


def _plan_fit(site, env, issues):
    config = capacity.check_config(site, 'putaway_fit')
    if not config:
        return
    scene = capacity.plan_check_scene(
        site, {'putaway': rule_fit_inputs(site), 'limits': capacity.site_cell_limits(site)}
    )
    capacity.add_new_issues(issues, check_putaway_fit(scene, config, state_mod.eps_m(env)))


# --- план правил розміщення (F04-01…03) ----------------------------------------------------------------------------


def default_location_in(site):
    """«Коли надходить у»: склад площадки (запас) або батьківська локація площадки."""
    return site.warehouse_id.lot_stock_id or site.default_parent_location_id


def _rule_name(rule, target_code):
    return "%s → %s" % (_label(rule), target_code or '?')


def _same_package_types(rule, existing):
    return set(rule.package_type_ids.ids) == set(existing.package_type_ids.ids)


def plan_putaway(site, env, lines, issues):
    """Чернетки `td.putaway.rule` → рядки для `stock.putaway.rule`; повертає число «без змін»."""
    Rule = env[pub.PUTAWAY].with_context(active_test=False)
    unchanged = 0
    drafts = env['td.putaway.rule'].with_context(active_test=False).search([('site_id', '=', site.id)])
    taken = set()
    for rule in drafts:
        target = capacity.resolve_target(site, env, lines, rule.out_code, rule.out_location_id)
        name = _rule_name(rule, target['code'])
        linked = rule.odoo_rule_id
        extra = {'rule_uid': rule.uid, 'zone_uid': target['zone_uid'], 'target_code': target['code']}
        if rule.deleted or not rule.active:
            if linked and linked.active:
                line = pub._line(
                    'archive', pub.PUTAWAY, name, name, None, linked, rule.uid, "буде архівовано",
                    dict(extra, explicit=True),
                )  # fmt: skip
                line['scope_uid'] = target['scope_uid']
                lines.append(line)
            continue
        loc_in = rule.in_location_id or default_location_in(site)
        out_loc = target['location']
        problem = ''
        if not rule.product_id and not rule.category_id:
            problem = "Вкажіть товар або категорію товару"
        elif not out_loc and not target['depends']:
            problem = "Не знайдено місце призначення %s" % (rule.out_code or '—')
        elif not loc_in:
            problem = "Не задано «Коли надходить у» і немає складу площадки"
        if problem:
            line = pub._line('create', pub.PUTAWAY, name, name, {}, None, rule.uid, problem, extra)
            pub._block(line, problem, 'target')
            lines.append(line)
            issues.append(
                pub._issue('conflict', 'warn', "Правило розміщення %s: %s" % (name, problem), [rule.out_code or ''])
            )
            continue
        want = {
            'product_id': rule.product_id.id or False,
            'category_id': rule.category_id.id or False,
            'location_in_id': loc_in.id,
            'sequence': rule.sequence,
            'sublocation': rule.sublocation or 'no',
            'storage_category_id': (rule.storage_category_id.id or False)
            if rule.sublocation == 'closest_location'
            else False,
            'package_type_ids': rule.package_type_ids.ids,
        }
        if out_loc:
            want['location_out_id'] = out_loc.id
        existing = linked if linked and linked.active else Rule
        if not existing and out_loc:  # такого самого правила вже є в Odoo: зв'язуємо
            for cand in Rule.search(
                [
                    ('company_id', '=', site.company_id.id),
                    ('product_id', '=', want['product_id']),
                    ('category_id', '=', want['category_id']),
                    ('location_in_id', '=', loc_in.id),
                    ('location_out_id', '=', out_loc.id),
                ]
            ):
                if cand.id not in taken and _same_package_types(rule, cand):
                    existing = cand
                    extra['link'] = True
                    break
        if existing:
            taken.add(existing.id)
            vals = {}
            for key, value in want.items():
                cur = existing[key]
                if key == 'package_type_ids':
                    cur, value = sorted(cur.ids), sorted(value)
                elif hasattr(cur, 'id'):
                    cur = cur.id or False
                if cur != value:
                    vals[key] = want[key]
            if not existing.active:
                vals['active'] = True
            if vals or extra.get('link'):
                text = pub._diff_text(existing, vals) if vals else "зв'язати з наявним правилом"
                lines.append(
                    pub._line(
                        'attrs', pub.PUTAWAY, name, name, vals, existing, rule.uid, text, extra,
                        target['depends'], target['scope_uid'],
                    )
                )  # fmt: skip
            else:
                unchanged += 1
            continue
        vals = dict(want, company_id=site.company_id.id)
        card = "%s → %s" % (_label(rule), target['code'])
        lines.append(
            pub._line(
                'create', pub.PUTAWAY, name, name, vals, None, rule.uid, card, extra,
                target['depends'], target['scope_uid'],
            )
        )  # fmt: skip
    return unchanged


def apply_putaway(site, lines, records, ops):
    """Застосування рядків `stock.putaway.rule`: create / attrs / archive; зв'язує чернетки; пише журнал."""
    env = site.env
    Rule = env[pub.PUTAWAY].with_context(active_test=False)
    Draft = env['td.putaway.rule'].with_context(active_test=False)
    entries = []
    for line in lines:
        draft = Draft.search([('site_id', '=', site.id), ('uid', '=', line['extra'].get('rule_uid'))], limit=1)
        kind, vals = line['kind'], dict(line['vals'])
        target = records.get((pub.LOCATION, line['depends_code']))
        if target:
            vals['location_out_id'] = target.id
        if kind == 'create':
            rec = Rule.create(pub.write_vals(vals, model=Rule))
            if draft:
                draft.odoo_rule_id = rec
            ops.append(pub.make_op('create', pub.PUTAWAY, rec, line['code'], {}, dict(vals, active=True)))
        elif kind == 'archive':
            rec = Rule.browse(line['res_id'])
            rec.write({'active': False})
            ops.append(pub.make_op('archive', pub.PUTAWAY, rec, line['code'], {'active': True}, {'active': False}))
        else:
            rec = Rule.browse(line['res_id'])
            before = pub.read_values(rec, vals)
            if vals:
                rec.write(pub.write_vals(vals, record=rec))
            if draft and draft.odoo_rule_id != rec:
                draft.odoo_rule_id = rec
            ops.append(pub.make_op('attrs', pub.PUTAWAY, rec, line['code'], before, pub.read_values(rec, vals)))
        entries.append({'kind': kind, 'model': pub.PUTAWAY, 'code': line['code'], 'id': rec.id})
    return entries


def _plan(site, env, lines, issues):
    unchanged = plan_putaway(site, env, lines, issues)
    _plan_fit(site, env, issues)
    return unchanged


PLAN_BUILDERS.register('putaway', _plan, sequence=70)
pub.APPLIERS[pub.PUTAWAY] = apply_putaway


# --- «Куди покладе Odoo» (F04-05, API-15 where) ------------------------------------------------------------------


def where(env, site, product, quantity, location, package_type=None):
    """Куди Odoo покладе товар, що прийшов у `location`: `_get_putaway_strategy`, лише застосовані правила.

    Повертає `{'location': {id, code, name}, 'moved': bool}`; без застосованих правил — сама локація приймання."""
    loc = location.sudo()
    kwargs = {}
    if package_type:
        try:
            kwargs['packaging'] = (
                env['product.packaging'].sudo().new({'product_id': product.id, 'package_type_id': package_type.id})
            )
        except Exception:  # noqa: BLE001 - модуль без product.packaging.package_type_id: розмір упаковки не враховуємо
            kwargs = {}
    dest = loc._get_putaway_strategy(product.sudo(), quantity=quantity or 0.0, **kwargs)
    return {
        'location': {
            'id': dest.id,
            'code': dest.td_code or dest.barcode or '',
            'name': dest.complete_name,
        },
        'moved': dest != loc,
    }


# --- розділ знімка: правила розміщення (R-14) ---------------------------------------------------------------------


def snapshot_build(site):
    rules = site.env['td.putaway.rule'].with_context(active_test=False).search([('site_id', '=', site.id)], order='uid')
    return [
        {
            'uid': r.uid,
            'product_id': r.product_id.id or None,
            'category_id': r.category_id.id or None,
            'package_type_ids': sorted(r.package_type_ids.ids),
            'in_location_id': r.in_location_id.id or None,
            'out_code': r.out_code or None,
            'out_location_id': r.out_location_id.id or None,
            'sublocation': r.sublocation,
            'storage_category_id': r.storage_category_id.id or None,
            'sequence': r.sequence,
            'deleted': r.deleted,
            'active': r.active,
        }
        for r in rules
    ]


def snapshot_apply(site, data):
    """Чернетка правил = знімок: за uid оновити/створити; відсутні зняти (зв'язані з Odoo — позначити `deleted`)."""
    env = site.env
    Rule = env['td.putaway.rule'].with_context(active_test=False, f3d_no_touch=True)
    have = {r.uid: r for r in Rule.search([('site_id', '=', site.id)])}
    seen = set()

    def existing(model, rid):
        return rid if rid and env[model].with_context(active_test=False).browse(rid).exists() else False

    for item in data or []:
        vals = {
            'product_id': existing('product.product', item.get('product_id')),
            'category_id': existing('product.category', item.get('category_id')),
            'package_type_ids': [
                (6, 0, [i for i in item.get('package_type_ids') or [] if existing('stock.package.type', i)])
            ],
            'in_location_id': existing('stock.location', item.get('in_location_id')),
            'out_code': item.get('out_code') or False,
            'out_location_id': existing('stock.location', item.get('out_location_id')),
            'sublocation': item.get('sublocation') or 'no',
            'storage_category_id': existing('stock.storage.category', item.get('storage_category_id')),
            'sequence': item.get('sequence') or 0,
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
        if rule.odoo_rule_id:
            rule.write({'deleted': True})
        else:
            rule.unlink()


SNAPSHOT_SECTIONS.register('putaway_rules', SnapshotSection(snapshot_build, snapshot_apply), sequence=70)
