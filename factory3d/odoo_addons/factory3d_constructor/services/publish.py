"""R-12, R-13: план публікації (diff → підтвердження → створення/оновлення stock.location, maintenance.equipment, mrp.workcenter).

Збіг із наявними записами — за `f3d_code`, потім `barcode` (комірки) / `serial_no` (обладнання): дублікатів не створюємо, нічого не видаляємо.
Зайве — лише пропозиція архівації (`selected=False`), тільки для записів із `f3d_site_id` площадки.
Читання плану — під `sudo()`; публікація — під `sudo()` лише після перевірки групи менеджера й стоп-крана (§4.4).
"""
import logging

from psycopg2 import errors as pg_errors

from odoo import fields
from odoo.exceptions import UserError

from . import snapshot, state as state_mod

_logger = logging.getLogger(__name__)

PARAM_PUBLISH = 'factory3d.constructor.publish_enabled'
LOCATION, EQUIPMENT, WORKCENTER = 'stock.location', 'maintenance.equipment', 'mrp.workcenter'


class PublishError(UserError):
    """Очікувана відмова публікації; `code` — код API-07 (disabled, blocked, no_changes, conflict_codes, conflict, rollback, rights)."""

    def __init__(self, code, message, issues=None):
        super().__init__(message)
        self.code = code
        self.issues = issues or []


def publish_enabled(env):
    return env['ir.config_parameter'].sudo().get_param(PARAM_PUBLISH) == 'True'


def _issue(check, severity, message, codes=(), layer_id=False):
    return {'check': check, 'severity': severity, 'layer_id': layer_id or False, 'codes': list(codes), 'message': message}


def _fmt(value):
    if hasattr(value, '_name') and hasattr(value, 'display_name'):
        return value.display_name or '—'
    if value in (False, None, ''):
        return '—'
    if isinstance(value, float) and value == int(value):
        return str(int(value))
    return str(value)


def _diff_text(record, vals):
    parts = []
    for key, new in vals.items():
        field = record._fields[key]
        old = record[key]
        if field.type == 'many2one':
            new = record.env[field.comodel_name].browse(new) if new else record.env[field.comodel_name]
        parts.append("%s: %s → %s" % (key, _fmt(old), _fmt(new)))
    return "; ".join(parts)


def _line(kind, res_model, code, name, vals=None, record=None, source_uid='', changes='', extra=None):
    return {
        'kind': kind, 'res_model': res_model, 'code': code, 'name': name or code, 'res_id': record.id if record else 0,
        'source_uid': source_uid, 'changes': changes, 'vals': vals or {}, 'selected': kind != 'archive',
        'blocked': False, 'blocked_reason': '', 'extra': extra or {},
    }


# --- локації ---------------------------------------------------------------------------------------------

def _match(code, by_f3d, by_alt, site, issues, label):
    """Збіг запису за f3d_code, потім за запасним ключем (barcode/serial_no); повертає (record|None, skip: bool)."""
    rec = by_f3d.get(code)
    if rec is None:
        candidates = by_alt.get(code, [])
        if len(candidates) > 1:
            issues.append(_issue('conflict', 'block', "Неоднозначний збіг для %s" % code, [code]))
            return None, True
        if candidates:
            rec = candidates[0]
            if rec.f3d_code and rec.f3d_code != code:
                issues.append(_issue('conflict', 'block', "Код %s: %s «%s» має інший код сцени %s" % (
                    code, label, rec.display_name, rec.f3d_code), [code]))
                return None, True
    if rec is not None:
        if rec.f3d_site_id and rec.f3d_site_id != site:
            issues.append(_issue('conflict', 'block', "Код %s зайнятий записом площадки %s" % (code, rec.f3d_site_id.name), [code]))
            return None, True
        if rec.company_id and rec.company_id != site.company_id:
            issues.append(_issue('conflict', 'block', "Код %s зайнятий записом іншої компанії" % code, [code]))
            return None, True
        if not rec.active:
            issues.append(_issue('conflict', 'warn', "Запис %s архівований; не відновлюється автоматично" % code, [code]))
            return None, True
    return rec, False


def _group_by(records, field):
    out = {}
    for rec in records:
        key = rec[field]
        if key:
            out.setdefault(key, []).append(rec)
    return out


def _plan_locations(site, env, lines, issues):
    Loc = env[LOCATION].with_context(active_test=False)
    slots = env['f3d.slot'].search([('site_id', '=', site.id), ('layer_id.active', '=', True)])
    desired, unchanged = {}, 0
    for slot in slots:
        cells = slot._f3d_cells()
        if not cells:
            continue
        parent = slot.parent_location_id or site.default_parent_location_id
        if not parent:
            issues.append(_issue('data', 'block', "Для місця %s не задано батьківську локацію" % slot.code_prefix,
                                 [slot.code_prefix], slot.layer_id.id))
            continue
        for cell in cells:
            if cell['code'] in desired:
                issues.append(_issue('conflict', 'block', "Код %s дублюється в місцях %s і %s" % (
                    cell['code'], desired[cell['code']]['slot'].code_prefix, slot.code_prefix), [cell['code']]))
                continue
            desired[cell['code']] = {'cell': cell, 'slot': slot, 'parent': parent}
    codes = list(desired)
    existing = Loc.search(['|', ('f3d_code', 'in', codes), ('barcode', 'in', codes)]) if codes else Loc
    by_f3d = {r.f3d_code: r for r in existing if r.f3d_code}
    by_barcode = _group_by(existing, 'barcode')
    for code, item in desired.items():
        cell, slot, parent = item['cell'], item['slot'], item['parent']
        rec, skip = _match(code, by_f3d, by_barcode, site, issues, "локація")
        if skip:
            continue
        if rec is None:
            vals = {
                'name': cell['name'], 'barcode': code, 'f3d_code': code, 'usage': 'internal', 'location_id': parent.id,
                'f3d_loc_kind': cell['kind'], 'f3d_capacity': cell['capacity'] or 0.0, 'f3d_site_id': site.id,
                'f3d_slot_uid': slot.uid, 'company_id': site.company_id.id,
            }
            card = "вид %s" % cell['kind'] + (", місткість %s" % _fmt(cell['capacity']) if cell['capacity'] else "")
            lines.append(_line('create', LOCATION, code, cell['name'], vals, None, slot.uid, card))
            continue
        vals = {}
        if not rec.f3d_code:
            vals['f3d_code'] = code
        if not rec.barcode:
            vals['barcode'] = code
        if cell['kind'] and rec.f3d_loc_kind != cell['kind']:
            vals['f3d_loc_kind'] = cell['kind']
        if cell['capacity'] and cell['capacity'] != rec.f3d_capacity:
            vals['f3d_capacity'] = cell['capacity']
        if slot.parent_location_id and rec.location_id != slot.parent_location_id:
            vals['location_id'] = slot.parent_location_id.id
        if rec.f3d_site_id != site:
            vals['f3d_site_id'] = site.id
        if rec.f3d_slot_uid != slot.uid:
            vals['f3d_slot_uid'] = slot.uid
        if vals:
            lines.append(_line('update', LOCATION, code, rec.complete_name or code, vals, rec, slot.uid,
                               _diff_text(rec, vals)))
        else:
            unchanged += 1
    return set(codes), unchanged


# --- обладнання й робочі центри --------------------------------------------------------------------------

def _plan_equipment(site, env, lines, issues):
    Equipment = env[EQUIPMENT].with_context(active_test=False)
    Workcenter = env[WORKCENTER].with_context(active_test=False)
    placements = env['f3d.placement'].search([('site_id', '=', site.id), ('layer_id.active', '=', True)])
    codes = placements.mapped('code')
    eq_existing = Equipment.search(['|', ('f3d_code', 'in', codes), ('serial_no', 'in', codes)]) if codes else Equipment
    by_f3d = {r.f3d_code: r for r in eq_existing if r.f3d_code}
    by_serial = _group_by(eq_existing.filtered(lambda r: not r.f3d_code), 'serial_no')
    wc_codes = placements.filtered(lambda p: p.variant_id.create_workcenter).mapped('code')
    wc_existing = Workcenter.search(['|', ('f3d_code', 'in', wc_codes), ('code', 'in', wc_codes)]) if wc_codes else Workcenter
    wc_by_f3d = {r.f3d_code: r for r in wc_existing if r.f3d_code}
    wc_by_code = _group_by(wc_existing.filtered(lambda r: not r.f3d_code), 'code')
    Zone = env['f3d.zone']
    unchanged = 0
    for p in placements:
        code = p.code
        passport = p.variant_id.passport_id
        zone = Zone.zone_at(p.x_m, p.y_m, site.company_id)
        rec, skip = _match(code, by_f3d, by_serial, site, issues, "обладнання")
        if not skip:
            if rec is None:
                vals = {'name': p.name, 'f3d_code': code, 'f3d_passport_id': passport.id, 'f3d_site_id': site.id,
                        'f3d_placement_uid': p.uid, 'company_id': site.company_id.id}
                if zone:
                    vals['f3d_zone_id'] = zone.id
                lines.append(_line('create', EQUIPMENT, code, p.name, vals, None, p.uid,
                                   "паспорт %s" % passport.display_name))
            else:
                vals = {}
                if not rec.f3d_code:
                    vals['f3d_code'] = code
                if rec.f3d_passport_id != passport:
                    vals['f3d_passport_id'] = passport.id
                if zone and not rec.f3d_zone_id:
                    vals['f3d_zone_id'] = zone.id
                if rec.f3d_site_id != site:
                    vals['f3d_site_id'] = site.id
                if rec.f3d_placement_uid != p.uid:
                    vals['f3d_placement_uid'] = p.uid
                if vals:
                    lines.append(_line('update', EQUIPMENT, code, rec.display_name, vals, rec, p.uid, _diff_text(rec, vals)))
                else:
                    unchanged += 1
        if p.variant_id.create_workcenter:
            wrec, wskip = _match(code, wc_by_f3d, wc_by_code, site, issues, "робочий центр")
            if wskip:
                continue
            if wrec is None:
                vals = {'name': p.name, 'code': code, 'f3d_code': code, 'f3d_site_id': site.id,
                        'company_id': site.company_id.id}
                lines.append(_line('create', WORKCENTER, code, p.name, vals, None, p.uid, "робочий центр"))
            else:
                vals = {}
                if not wrec.f3d_code:
                    vals['f3d_code'] = code
                if wrec.f3d_site_id != site:
                    vals['f3d_site_id'] = site.id
                if vals:
                    lines.append(_line('update', WORKCENTER, code, wrec.display_name, vals, wrec, p.uid, _diff_text(wrec, vals)))
                else:
                    unchanged += 1
    return set(codes), set(wc_codes), unchanged


# --- пропозиції архівації (R-13) ----------------------------------------------------------------------------

def _plan_archive(site, env, lines, loc_codes, eq_codes, wc_codes):
    def candidates(model, desired):
        recs = env[model].search([('f3d_site_id', '=', site.id), ('active', '=', True)])
        return recs.filtered(lambda r: r.f3d_code and r.f3d_code not in desired)

    locations = candidates(LOCATION, loc_codes)
    stock = {}
    if locations:
        for loc, qty in env['stock.quant']._read_group(
                [('location_id', 'in', locations.ids), ('quantity', '>', 0)], ['location_id'], ['quantity:sum']):
            stock[loc.id] = qty
    equipment = candidates(EQUIPMENT, eq_codes)
    busy_eq = set()
    if equipment and 'maintenance.request' in env:
        requests = env['maintenance.request'].search([
            ('equipment_id', 'in', equipment.ids), ('stage_id.done', '=', False), ('archive', '=', False)])
        busy_eq = set(requests.mapped('equipment_id').ids)
    workcenters = candidates(WORKCENTER, wc_codes)
    busy_wc = set()
    if workcenters and 'mrp.workorder' in env:
        orders = env['mrp.workorder'].search([('workcenter_id', 'in', workcenters.ids), ('state', 'not in', ('done', 'cancel'))])
        busy_wc = set(orders.mapped('workcenter_id').ids)
    for rec in locations:
        line = _line('archive', LOCATION, rec.f3d_code, rec.complete_name, None, rec, '', "буде архівовано")
        if stock.get(rec.id):
            line.update(blocked=True, blocked_reason="Є залишки: %s" % _fmt(stock[rec.id]))
        lines.append(line)
    for rec in equipment:
        line = _line('archive', EQUIPMENT, rec.f3d_code, rec.name, None, rec, '', "буде архівовано")
        if rec.id in busy_eq:
            line.update(blocked=True, blocked_reason="Є відкриті заявки ТО")
        lines.append(line)
    for rec in workcenters:
        line = _line('archive', WORKCENTER, rec.f3d_code, rec.name, None, rec, '', "буде архівовано")
        if rec.id in busy_wc:
            line.update(blocked=True, blocked_reason="Є незавершені завдання")
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
    return {'lines': lines, 'issues': issues, 'unchanged': unchanged, 'draft_rev': site.draft_rev}


def summary(plan, archive_keys=()):
    keys = set(archive_keys)
    count = lambda kind: sum(1 for line in plan['lines'] if line['kind'] == kind)  # noqa: E731
    return {
        'create': count('create'), 'update': count('update'), 'archive': len([
            line for line in plan['lines'] if line['kind'] == 'archive' and (line['res_model'], line['code']) in keys]),
        'archive_offer': count('archive'), 'unchanged': plan['unchanged'],
        'warn': sum(1 for i in plan['issues'] if i['severity'] == 'warn'),
        'block': sum(1 for i in plan['issues'] if i['severity'] == 'block'),
    }


# --- застосування ------------------------------------------------------------------------------------------

def _lock_site(env, site):
    try:
        with env.cr.savepoint():
            env.cr.execute("SELECT id FROM f3d_site WHERE id = %s FOR UPDATE NOWAIT", (site.id,))
    except pg_errors.LockNotAvailable:
        raise PublishError('conflict', "Публікація вже виконується іншим користувачем") from None


def _check_preconditions(site, plan):
    env = site.env
    if not (env.su or env.user.has_group('factory3d_constructor.group_f3d_constructor_manager')):
        raise PublishError('rights', "Публікувати розкладку може лише менеджер конструктора.")
    if not publish_enabled(env):
        raise PublishError('disabled', "Публікацію вимкнено: стоп-кран factory3d.constructor.publish_enabled.")
    if plan['draft_rev'] != site.draft_rev:
        raise PublishError('conflict', "Чернетка змінилась. Закрийте вікно й відкрийте майстер знову.")
    blocks = [i for i in plan['issues'] if i['severity'] == 'block']
    if blocks:
        code = 'conflict_codes' if any(i['check'] == 'conflict' for i in blocks) else 'blocked'
        raise PublishError(code, "Публікацію заборонено: є зауваження зі статусом «Заборона» (%d)." % len(blocks), blocks)
    changed = [line for line in plan['lines'] if line['kind'] in ('create', 'update')]
    if not changed and not site.has_changes:
        raise PublishError('no_changes', "Немає змін для публікації")


def apply_plan(site, plan, archive_keys=(), note=''):
    """R-12 п. 6: застосувати план у транзакції; повертає `{'version', 'created', 'updated', 'archived', 'warnings'}`.

    `archive_keys` — множина `(res_model, code)` або голих кодів позначених пропозицій архівації (blocked ігноруються).
    Будь-який неочікуваний виняток відкочує все (`PublishError('rollback')`).
    """
    _check_preconditions(site, plan)
    env = site.env
    keys = {k if isinstance(k, tuple) else (None, k) for k in archive_keys}
    try:
        with env.cr.savepoint():
            _lock_site(env, site)
            return _apply(site, plan, keys, note)
    except (PublishError, UserError):
        env.invalidate_all()
        raise
    except Exception as exc:  # noqa: BLE001 - відкат усієї публікації
        env.invalidate_all()
        _logger.exception("Публікація площадки %s відкотилась", site.id)
        raise PublishError('rollback', "Публікацію скасовано через помилку: %s" % (str(exc)[:300] or exc.__class__.__name__)) from exc


def _apply(site, plan, keys, note):
    site = site.sudo().with_company(site.company_id).with_context(
        f3d_no_touch=True, tracking_disable=True, mail_notrack=True, mail_create_nolog=True)
    base = site.env
    created, updated, archived = [], [], []
    records = {}   # (res_model, code) → record для зв'язування розміщень

    def remember(model, code, rec):
        records[(model, code)] = rec

    for model in (LOCATION, EQUIPMENT, WORKCENTER):
        Model = base[model]
        creates = [line for line in plan['lines'] if line['kind'] == 'create' and line['res_model'] == model]
        if creates:
            for line, rec in zip(creates, Model.create([line['vals'] for line in creates])):
                remember(model, line['code'], rec)
                created.append({'model': model, 'code': line['code'], 'id': rec.id})
        for line in plan['lines']:
            if line['res_model'] != model or line['kind'] != 'update':
                continue
            rec = Model.browse(line['res_id'])
            rec.write(line['vals'])
            remember(model, line['code'], rec)
            updated.append({'model': model, 'code': line['code'], 'id': rec.id})
    # зв'язок обладнання з робочим центром (лише якщо поле існує, DEC-16) і розміщень із записами
    has_wc_field = 'workcenter_id' in base[EQUIPMENT]._fields
    now = fields.Datetime.now()
    for placement in base['f3d.placement'].search([('site_id', '=', site.id), ('layer_id.active', '=', True)]):
        eq = records.get((EQUIPMENT, placement.code)) or placement.equipment_id
        wc = records.get((WORKCENTER, placement.code)) or placement.workcenter_id
        if not eq:
            eq = base[EQUIPMENT].with_context(active_test=False).search([('f3d_code', '=', placement.code)], limit=1)
        if not wc and placement.variant_id.create_workcenter:
            wc = base[WORKCENTER].with_context(active_test=False).search([('f3d_code', '=', placement.code)], limit=1)
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
    for line in plan['lines']:
        if line['kind'] != 'archive' or line['blocked']:
            continue
        if (line['res_model'], line['code']) in keys or (None, line['code']) in keys:
            rec = base[line['res_model']].browse(line['res_id'])
            rec.write({'active': False})
            archived.append({'model': line['res_model'], 'code': line['code'], 'id': rec.id})
    warnings = [i for i in plan['issues'] if i['severity'] == 'warn']
    report = {'created': created, 'updated': updated, 'archived': archived, 'warnings': warnings}
    version = snapshot.create_version(site, note=note, report=report)
    return {'version': version, 'created': created, 'updated': updated, 'archived': archived, 'warnings': warnings}
