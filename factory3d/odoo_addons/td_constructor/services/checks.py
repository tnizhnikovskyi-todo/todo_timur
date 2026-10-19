"""R-04…R-10: перевірки розкладки (чистий Python; дзеркало — static/src/editor/checks.js).

Вхід — словник стану у форматі API-03 `load` (метри для шарів/місць/розміщень, мм для варіантів):

    state = {
      'site': {'building': {'length', 'width', 'height'}, 'column_grid': {'step_x', 'step_y'}, 'sprinkler_height',
               'aisle_tech'},
      'layers': [{id, name, kind, elevation, max_floor_load, bounds, slot_types, aisles, fire_paths, utilities, items}],
      'slots': [{id, layer_id, template, code_prefix, x, y, rotation, params, overrides, type_id, function_id, tech,
                 addr, …}],
      'placements': [{id, layer_id, variant_id, slot_id, cell_code, code, name, x, y, rotation, dynamic}],
      'variants': [{id, length, width, height, service: {front, back, left, right}, rotations, layer_kinds,
                    slot_types, utilities, weight_kg, floor_load, anchor, front_side}],
    }
    configs = [{'check': 'fits', 'enabled': True, 'mode': 'block', 'params': {}}]

Результат — список `issue = {check, severity, layer_id, codes, message}` лише для увімкнених перевірок.
Коди пар у `collide` відсортовані за алфавітом (пара не має напрямку).
Перевірки слайсів (MERGE.md §5.0) реєструються в `registry.CHECKS` і запускаються після вбудованих.
"""

import math

from . import addr as addr_mod
from . import cells as cells_mod
from . import geometry as geo
from .registry import CHECKS

CHECK_KEYS = ['fits', 'collide', 'service_free', 'aisles_free', 'load', 'utility_reach', 'fire']

CHECK_LABELS = {
    'fits': "Вміщується",
    'collide': "Перетини",
    'service_free': "Зона обслуговування вільна",
    'aisles_free': "Проходи вільні",
    'load': "Навантаження",
    'utility_reach': "Досяжність підключення",
    'fire': "Пожежні проходи й виходи",
}

# R-04: (check_key, enabled, mode, params), sequence = 10…70 за порядком
CHECK_DEFAULTS = [
    ('fits', True, 'block', {}),
    ('collide', True, 'block', {}),
    ('service_free', True, 'warn', {}),
    ('aisles_free', True, 'block', {}),
    ('load', True, 'warn', {}),
    ('utility_reach', True, 'warn', {'max_m': 15}),
    ('fire', True, 'block', {}),
]

DEFAULT_EPS_M = 0.001
DEFAULT_REACH_M = 15.0
ROTATION_TOLERANCE_DEG = 0.01


def _fmt_angle(value):
    return '%g' % round(value, 2)


def _rotation_ok(mode, rotation):
    period = {'q': 90.0, 'h': 180.0, 'z': 360.0}.get(mode)
    if period is None:  # 'any' або невідомий режим
        return True
    rem = rotation % period
    return min(rem, period - rem) <= ROTATION_TOLERANCE_DEG


def _has_addr(state):
    """Чи є в стані адресація (площадки, зони чи місця) або глибина «комірка»: інакше контексти не потрібні."""
    site = state.get('site') or {}
    if site.get('addr') or site.get('depth_mode') == 'cell':
        return True
    return any(s.get('addr') or s.get('depth_mode') for s in state.get('slots') or [])


class _Scene:
    """Індекси стану й кеш геометрії для перевірок."""

    def __init__(self, state):
        self.building = (state.get('site') or {}).get('building') or {}
        self.layers = {layer['id']: layer for layer in state.get('layers') or []}
        self.variants = {v['id']: v for v in state.get('variants') or []}
        self.slots = {s['id']: s for s in state.get('slots') or []}
        self.placements = [p for p in state.get('placements') or [] if p['variant_id'] in self.variants]
        self.dynamic = {p['id'] for p in self.placements if p.get('dynamic')}
        self._slot_obb = {}
        self._slot_cells = {}
        self._state = state
        self._extra = None
        self._contexts = None
        self._body = {}
        self._service = {}

    @property
    def extra(self):
        """Дані БД для перевірок слайсів (залишки, правила розміщення, зайнятість кодів): `state['extra']` — словник
        або функція `fn(scene)` (обчислюється один раз, лише коли потрібна ввімкненим перевіркам)."""
        if self._extra is None:
            raw = self._state.get('extra')
            self._extra = raw(self) if callable(raw) else (raw or {})
        return self._extra

    @extra.setter
    def extra(self, value):
        self._extra = value

    def slot_obb(self, slot):
        key = slot['id']
        if key not in self._slot_obb:
            self._slot_obb[key] = cells_mod.slot_obb(
                slot['template'],
                slot.get('params') or {},
                slot.get('x') or 0.0,
                slot.get('y') or 0.0,
                slot.get('rotation') or 0.0,
            )
        return self._slot_obb[key]

    def _slot_ctx(self, slot):
        """Контекст адресації місця (F01): коди комірок як у розкладці; без адресації — None (legacy-коди)."""
        if self._contexts is None:
            self._contexts = addr_mod.state_contexts(self._state) if _has_addr(self._state) else {}
        return addr_mod.usable_context(self._contexts.get(slot.get('uid') or slot['id']))

    def slot_cells(self, slot):
        key = slot['id']
        if key not in self._slot_cells:
            elevation = (self.layers.get(slot['layer_id']) or {}).get('elevation') or 0.0
            self._slot_cells[key] = {
                cell['code']: cell
                for cell in cells_mod.generate_cells(
                    slot['template'],
                    slot.get('code_prefix') or '',
                    slot.get('x') or 0.0,
                    slot.get('y') or 0.0,
                    slot.get('rotation') or 0.0,
                    slot.get('params') or {},
                    slot.get('overrides') or {},
                    elevation,
                    self._slot_ctx(slot),
                )
            }
        return self._slot_cells[key]

    def body(self, placement):
        key = placement['id']
        if key not in self._body:
            self._body[key] = geo.placement_obb(
                self.variants[placement['variant_id']],
                placement.get('x') or 0.0,
                placement.get('y') or 0.0,
                placement.get('rotation') or 0.0,
            )
        return self._body[key]

    def service(self, placement):
        key = placement['id']
        if key not in self._service:
            self._service[key] = geo.service_obb(
                self.variants[placement['variant_id']],
                placement.get('x') or 0.0,
                placement.get('y') or 0.0,
                placement.get('rotation') or 0.0,
            )
        return self._service[key]

    def objects(self):
        """F = розміщення ∪ місця (крім zone): [{kind, id, code, layer_id, obb, slot_id}]."""
        out = []
        for placement in self.placements:
            if placement['id'] in self.dynamic:
                continue  # люди й транспорт: не беруть участі в collide/aisles/service/fire (лише fits)
            out.append(
                {
                    'kind': 'placement',
                    'id': placement['id'],
                    'code': placement['code'],
                    'layer_id': placement['layer_id'],
                    'obb': self.body(placement),
                    'slot_id': placement.get('slot_id'),
                }
            )
        for slot in self.slots.values():
            if slot['template'] != 'zone':
                out.append(
                    {
                        'kind': 'slot',
                        'id': slot['id'],
                        'code': slot['code_prefix'],
                        'layer_id': slot['layer_id'],
                        'obb': self.slot_obb(slot),
                        'slot_id': None,
                    }
                )
        return out

    def container_polygon(self, layer):
        bounds = layer.get('bounds') if layer else None
        if bounds and len(bounds) >= 3:
            return [tuple(p) for p in bounds], "контуру шару"
        return geo.rect_polygon(self.building.get('length') or 0.0, self.building.get('width') or 0.0), "будівлі"


def _issue(check, severity, layer_id, codes, message):
    return {'check': check, 'severity': severity, 'layer_id': layer_id, 'codes': list(codes), 'message': message}


def _eps(config, eps):
    tol = (config.get('params') or {}).get('tolerance_mm')
    return tol / 1000.0 if isinstance(tol, (int, float)) and not isinstance(tol, bool) else eps


# --- окремі перевірки -----------------------------------------------------------------------------------


def check_fits(scene, config, eps):
    sev = config['mode']
    issues = []
    for p in scene.placements:
        variant = scene.variants[p['variant_id']]
        layer = scene.layers.get(p['layer_id']) or {}
        code, lid = p['code'], p['layer_id']
        kinds = variant.get('layer_kinds') or []
        if kinds and layer.get('kind') not in kinds:
            issues.append(
                _issue(
                    'fits',
                    sev,
                    lid,
                    [code],
                    "%s: варіант не допускається на шарі «%s»" % (code, layer.get('name') or ''),
                )
            )
        slot = scene.slots.get(p.get('slot_id')) if p.get('slot_id') else None
        types = variant.get('slot_types') or []
        if slot is not None and types and slot['template'] not in types:
            issues.append(
                _issue(
                    'fits', sev, lid, [code], "%s: варіант не допускається в місці типу %s" % (code, slot['template'])
                )
            )
        rotation = p.get('rotation') or 0.0
        if not _rotation_ok(variant.get('rotations'), rotation):
            issues.append(
                _issue('fits', sev, lid, [code], "%s: поворот %s° недозволений" % (code, _fmt_angle(rotation)))
            )
        cell_code = p.get('cell_code')
        if cell_code and slot is not None:
            cell = scene.slot_cells(slot).get(cell_code)
            if cell is None:
                issues.append(
                    _issue(
                        'fits',
                        sev,
                        lid,
                        [code],
                        "%s: комірки %s немає в місці %s" % (code, cell_code, slot['code_prefix']),
                    )
                )
                continue
            container = geo.obb_corners(
                geo.make_obb(cell['x'], cell['y'], cell['l'] / 2.0, cell['w'] / 2.0, cell['rot'])
            )
            what = "комірки"
        elif slot is not None:
            container, what = geo.obb_corners(scene.slot_obb(slot)), "місця"
        else:
            container, what = scene.container_polygon(layer)
        if not geo.obb_inside_polygon(scene.body(p), container, eps):
            issues.append(_issue('fits', sev, lid, [code], "%s: виходить за межі %s" % (code, what)))
    for slot in scene.slots.values():
        if slot['template'] == 'zone':
            continue
        container, what = scene.container_polygon(scene.layers.get(slot['layer_id']) or {})
        if not geo.obb_inside_polygon(scene.slot_obb(slot), container, eps):
            issues.append(
                _issue(
                    'fits',
                    sev,
                    slot['layer_id'],
                    [slot['code_prefix']],
                    "%s: виходить за межі %s" % (slot['code_prefix'], what),
                )
            )
    return issues


def _by_layer(objects):
    groups = {}
    for obj in objects:
        groups.setdefault(obj['layer_id'], []).append(obj)
    return groups


def _same_slot(a, b):
    if a['kind'] == 'placement' and b['kind'] == 'slot':
        return a['slot_id'] == b['id']
    if a['kind'] == 'slot' and b['kind'] == 'placement':
        return b['slot_id'] == a['id']
    return False


def check_collide(scene, config, eps):
    sev = config['mode']
    issues = []
    for layer_id, group in _by_layer(scene.objects()).items():
        boxes = [geo.obb_aabb(o['obb']) for o in group]
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                a, b = group[i], group[j]
                if _same_slot(a, b) or not geo.aabb_overlap(boxes[i], boxes[j], eps):
                    continue
                depth = geo.sat_penetration(a['obb'], b['obb'])
                if depth > eps:
                    codes = sorted([a['code'], b['code']])
                    issues.append(
                        _issue(
                            'collide',
                            sev,
                            layer_id,
                            codes,
                            "%s перетинається з %s на %.2f м" % (codes[0], codes[1], depth),
                        )
                    )
    return issues


def check_service_free(scene, config, eps):
    sev = config['mode']
    issues = []
    groups = _by_layer(scene.objects())
    for p in scene.placements:
        service = None if p['id'] in scene.dynamic else scene.service(p)
        if service is None:
            continue
        box = geo.obb_aabb(service)
        for other in groups.get(p['layer_id'], []):
            if other['kind'] == 'placement' and other['id'] == p['id']:
                continue
            if other['kind'] == 'slot' and other['id'] == p.get('slot_id'):
                continue
            if not geo.aabb_overlap(box, geo.obb_aabb(other['obb']), eps):
                continue
            if geo.sat_penetration(service, other['obb']) > eps:
                issues.append(
                    _issue(
                        'service_free',
                        sev,
                        p['layer_id'],
                        [p['code'], other['code']],
                        "Зона обслуговування %s зачіпає %s" % (p['code'], other['code']),
                    )
                )
    return issues


def _check_rects(scene, config, eps, check, key):
    sev = config['mode']
    issues = []
    for layer_id, group in _by_layer(scene.objects()).items():
        rects = (scene.layers.get(layer_id) or {}).get(key) or []
        for obj in group:
            for rect in rects:
                rect_obb = geo.rect_obb(rect['x0'], rect['y0'], rect['x1'], rect['y1'])
                if geo.sat_penetration(obj['obb'], rect_obb) <= eps:
                    continue
                name = rect.get('name') or ''
                if check == 'aisles_free':
                    message = "Прохід перекрито: %s × %s" % (obj['code'], name)
                elif rect.get('kind') == 'exit':
                    message = "Вихід перекрито: %s × %s" % (obj['code'], name)
                else:
                    message = "Пожежний прохід перекрито: %s × %s" % (obj['code'], name)
                issues.append(_issue(check, sev, layer_id, [obj['code']], message))
    return issues


def check_aisles_free(scene, config, eps):
    return _check_rects(scene, config, eps, 'aisles_free', 'aisles')


def check_fire(scene, config, eps):
    return _check_rects(scene, config, eps, 'fire', 'fire_paths')


def check_load(scene, config, eps):
    sev = config['mode']
    issues = []
    for p in scene.placements:
        variant = scene.variants[p['variant_id']]
        layer = scene.layers.get(p['layer_id']) or {}
        limit = layer.get('max_floor_load') or 0.0
        load = variant.get('floor_load') or 0.0
        if limit > 0 and load > limit:
            issues.append(
                _issue(
                    'load',
                    sev,
                    p['layer_id'],
                    [p['code']],
                    "%s: навантаження %.1f кН/м² перевищує %.1f" % (p['code'], load, limit),
                )
            )
        cell_code = p.get('cell_code')
        slot = scene.slots.get(p.get('slot_id')) if p.get('slot_id') else None
        if cell_code and slot is not None:
            cell = scene.slot_cells(slot).get(cell_code)
            weight = variant.get('weight_kg') or 0.0
            if cell is not None and cell['max_load_kg'] > 0 and weight > cell['max_load_kg']:
                issues.append(
                    _issue(
                        'load',
                        sev,
                        p['layer_id'],
                        [p['code']],
                        "%s: маса %g кг перевищує %g кг комірки %s"
                        % (p['code'], weight, cell['max_load_kg'], cell_code),
                    )
                )
    return issues


def check_utility_reach(scene, config, eps):
    sev = config['mode']
    max_m = (config.get('params') or {}).get('max_m')
    if not isinstance(max_m, (int, float)) or isinstance(max_m, bool) or max_m <= 0:
        max_m = DEFAULT_REACH_M
    points = {}
    for layer in scene.layers.values():
        for util in layer.get('utilities') or []:
            kind = 'electric' if util.get('kind') == 'panel' else util.get('kind')
            points.setdefault(kind, []).append((util['x'], util['y']))
    issues = []
    for p in scene.placements:
        variant = scene.variants[p['variant_id']]
        for kind, ux, uy in geo.utility_points(variant, p.get('x') or 0.0, p.get('y') or 0.0, p.get('rotation') or 0.0):
            candidates = points.get(kind) or []
            if not candidates:
                issues.append(
                    _issue(
                        'utility_reach',
                        sev,
                        p['layer_id'],
                        [p['code']],
                        "%s: на площадці немає точки «%s»" % (p['code'], kind),
                    )
                )
                continue
            dist = min(math.hypot(ux - cx, uy - cy) for cx, cy in candidates)
            if dist > max_m:
                issues.append(
                    _issue(
                        'utility_reach',
                        sev,
                        p['layer_id'],
                        [p['code']],
                        "%s: до найближчої точки «%s» %.1f м (ліміт %g м)" % (p['code'], kind, dist, max_m),
                    )
                )
    return issues


CHECKERS = {
    'fits': check_fits,
    'collide': check_collide,
    'service_free': check_service_free,
    'aisles_free': check_aisles_free,
    'load': check_load,
    'utility_reach': check_utility_reach,
    'fire': check_fire,
}


def run_checks(state, configs, eps=DEFAULT_EPS_M):
    """R-04: усі увімкнені перевірки; `severity = config.mode`; порядок — за CHECK_KEYS."""
    scene = _Scene(state)
    by_key = {c['check']: c for c in configs or [] if c.get('enabled')}
    issues = []
    for key in CHECK_KEYS:
        config = by_key.get(key)
        if config is not None:
            issues.extend(CHECKERS[key](scene, config, _eps(config, eps)))
    # перевірки слайсів (services.registry.CHECKS) — після вбудованих; вбудовані ключі реєстром не перекриваються
    for key, checker in CHECKS.items():
        config = by_key.get(key)
        if config is not None and key not in CHECKERS:
            issues.extend(checker(scene, config, _eps(config, eps)))
    return issues


def summarize(issues):
    return {
        'block': sum(1 for i in issues if i['severity'] == 'block'),
        'warn': sum(1 for i in issues if i['severity'] == 'warn'),
    }
