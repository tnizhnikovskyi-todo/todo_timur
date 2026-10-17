"""R-22: схеми JSON-полів.

Невідомі ключі відкидаються (не помилка), типи й діапазони — SchemaError з номером елемента."""

import json
import math

MAX_JSON_BYTES = 256 * 1024
MAX_JSON_DEPTH = 8

AISLE_KINDS = ('path', 'exit')
LAYER_UTILITY_KINDS = ('electric', 'air', 'dust', 'panel')
VARIANT_UTILITY_KINDS = ('electric', 'air', 'dust')
UNDERLAY_DEFAULT = {'unit': 'mm', 'dx': 0.0, 'dy': 0.0, 'rot_deg': 0.0, 'opacity': 0.5, 'scale': 1.0}


class SchemaError(ValueError):
    """Помилка схеми JSON-поля; текст — українською, показується користувачу."""


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _number(value, message):
    if not _finite(value):
        raise SchemaError(message)
    return float(value)


def check_json_limits(value):
    """Вкладеність ≤ 8 рівнів і розмір ≤ 256 КБ (§13.3)."""

    def depth(node, level=1):
        if level > MAX_JSON_DEPTH:
            raise SchemaError("JSON: вкладеність більша за %d рівнів." % MAX_JSON_DEPTH)
        if isinstance(node, dict):
            for item in node.values():
                depth(item, level + 1)
        elif isinstance(node, (list, tuple)):
            for item in node:
                depth(item, level + 1)

    depth(value)
    if len(json.dumps(value, ensure_ascii=False).encode('utf-8')) > MAX_JSON_BYTES:
        raise SchemaError("JSON: розмір більший за 256 КБ.")
    return value


def _rect_list(value, label, kinds=None):
    if value in (None, False):
        return []
    if not isinstance(value, (list, tuple)):
        raise SchemaError("%s: очікується список." % label)
    out, seen = [], set()
    for index, item in enumerate(value, 1):
        bad = "%s %d: некоректні координати." % (label, index)
        if not isinstance(item, dict):
            raise SchemaError(bad)
        rid = item.get('id')
        if not isinstance(rid, str) or not 1 <= len(rid) <= 32:
            raise SchemaError("%s %d: некоректний id." % (label, index))
        if rid in seen:
            raise SchemaError("%s %d: id «%s» повторюється." % (label, index, rid))
        seen.add(rid)
        name = item.get('name', '')
        if not isinstance(name, str) or len(name) > 64:
            raise SchemaError("%s %d: назва — рядок до 64 символів." % (label, index))
        x0, y0 = _number(item.get('x0'), bad), _number(item.get('y0'), bad)
        x1, y1 = _number(item.get('x1'), bad), _number(item.get('y1'), bad)
        if not (x0 < x1 and y0 < y1):
            raise SchemaError(bad)
        clean = {'id': rid, 'name': name, 'x0': x0, 'y0': y0, 'x1': x1, 'y1': y1}
        if kinds is not None:
            if item.get('kind') not in kinds:
                raise SchemaError("%s %d: вид має бути одним із %s." % (label, index, ", ".join(kinds)))
            clean['kind'] = item['kind']
        out.append(clean)
    return out


def normalize_aisles(value):
    return _rect_list(value, "Прохід")


def normalize_fire_paths(value):
    return _rect_list(value, "Шлях", AISLE_KINDS)


def normalize_layer_utilities(value):
    if value in (None, False):
        return []
    if not isinstance(value, (list, tuple)):
        raise SchemaError("Мережі: очікується список.")
    out, seen = [], set()
    for index, item in enumerate(value, 1):
        bad = "Мережа %d: некоректні координати." % index
        if not isinstance(item, dict):
            raise SchemaError(bad)
        rid = item.get('id')
        if not isinstance(rid, str) or not 1 <= len(rid) <= 32 or rid in seen:
            raise SchemaError("Мережа %d: некоректний або повторний id." % index)
        seen.add(rid)
        if item.get('kind') not in LAYER_UTILITY_KINDS:
            raise SchemaError("Мережа %d: вид має бути одним із %s." % (index, ", ".join(LAYER_UTILITY_KINDS)))
        name = item.get('name', '')
        if not isinstance(name, str) or len(name) > 64:
            raise SchemaError("Мережа %d: назва — рядок до 64 символів." % index)
        out.append(
            {
                'id': rid,
                'kind': item['kind'],
                'name': name,
                'x': _number(item.get('x'), bad),
                'y': _number(item.get('y'), bad),
                'z': _number(item.get('z', 0), bad),
            }
        )
    return out


def _segments_cross(p1, p2, p3, p4):
    def orient(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    d1, d2 = orient(p3, p4, p1), orient(p3, p4, p2)
    d3, d4 = orient(p1, p2, p3), orient(p1, p2, p4)
    return d1 * d2 < 0 and d3 * d4 < 0


def normalize_bounds(value):
    """`False`/None або [[x, y], …] (≥3 точки, простий багатокутник)."""
    if value in (None, False):
        return False
    msg = "Контур шару: щонайменше 3 точки."
    if not isinstance(value, (list, tuple)) or len(value) < 3:
        raise SchemaError(msg)
    points = []
    for point in value:
        if not isinstance(point, (list, tuple)) or len(point) != 2:
            raise SchemaError("Контур шару: точка має бути парою [x, y].")
        points.append(
            [
                _number(point[0], "Контур шару: координати мають бути числами."),
                _number(point[1], "Контур шару: координати мають бути числами."),
            ]
        )
    n = len(points)
    for i in range(n):
        for j in range(i + 1, n):
            if j == i + 1 or (i == 0 and j == n - 1):
                continue
            if _segments_cross(points[i], points[(i + 1) % n], points[j], points[(j + 1) % n]):
                raise SchemaError("Контур шару не має перетинати сам себе.")
    return points


def normalize_underlay_params(value):
    params = dict(UNDERLAY_DEFAULT)
    if value in (None, False):
        return params
    if not isinstance(value, dict):
        raise SchemaError("Параметри підкладки: очікується об'єкт.")
    msg = "Параметри підкладки: некоректне значення."
    for key in ('dx', 'dy', 'rot_deg', 'opacity', 'scale'):
        if key in value:
            params[key] = _number(value[key], msg)
    if 'unit' in value:
        if value['unit'] not in ('mm', 'm'):
            raise SchemaError("Параметри підкладки: одиниці — mm або m.")
        params['unit'] = value['unit']
    if params['scale'] <= 0:
        raise SchemaError("Параметри підкладки: масштаб має бути додатним.")
    if not 0 <= params['opacity'] <= 1:
        raise SchemaError("Параметри підкладки: прозорість від 0 до 1.")
    return params


def normalize_variant_utilities(value):
    if value in (None, False):
        return []
    if not isinstance(value, (list, tuple)):
        raise SchemaError("Точки підключення: очікується список.")
    out = []
    for index, item in enumerate(value, 1):
        bad = "Підключення %d: некоректні координати." % index
        if not isinstance(item, dict):
            raise SchemaError(bad)
        if item.get('kind') not in VARIANT_UTILITY_KINDS:
            raise SchemaError("Підключення %d: вид має бути одним із %s." % (index, ", ".join(VARIANT_UTILITY_KINDS)))
        out.append(
            {
                'kind': item['kind'],
                'x_mm': _number(item.get('x_mm'), bad),
                'y_mm': _number(item.get('y_mm'), bad),
                'z_mm': _number(item.get('z_mm', 0), bad),
            }
        )
    return out


def normalize_check_params(check_key, value):
    if value in (None, False):
        value = {}
    if not isinstance(value, dict):
        raise SchemaError("Параметри перевірки: очікується об'єкт.")
    out = {}
    if 'tolerance_mm' in value:
        tol = _number(value['tolerance_mm'], "Допуск має бути числом.")
        if tol < 0:
            raise SchemaError("Допуск не може бути від'ємним.")
        out['tolerance_mm'] = tol
    if check_key == 'utility_reach':
        max_m = _number(value.get('max_m', 15), "Максимальна відстань має бути числом.")
        if max_m <= 0:
            raise SchemaError("Максимальна відстань має бути додатною.")
        out['max_m'] = max_m
    return out
