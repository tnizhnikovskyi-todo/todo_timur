"""Адресація (F01, MERGE.md §2.5): шаблон коду, сегменти, напрями, наслідування, контекст місць. Чистий Python.

Дзеркало — `factory3d/core/constructor/addr.js` (еталон узгодження — `static/tests/fixtures/addr_golden.json`).

`addr` (R-22) — JSON площадки, місця-зони чи місця. Повний вигляд (є `tpl`):

    {tpl, sep, seg: {zone,row,bay,level,pos: {kind: num|alpha, width, start}}, row_from, row_mode, bay_dir, level_dir,
     zone_code?, row_no?}

* `tpl` — слова через пробіл; слово = літери + `{сегмент}`: `{zone} {row} {bay} {level} {pos}` (+ `{prefix}` =
  `code_prefix` місця). Синоніми: UK `{зона} {ряд} {секція} {ярус} {позиція}`, EN `{aisle} {section} {tier}
  {position}`. Слово, в якому немає значення сегмента, пропускається цілком; слова з'єднує `sep` (до 3 символів);
  сегмент у шаблоні — не більше разу.
* Порожній `addr` ({}) = пресет «legacy»: коди як раніше (`ПРЕФІКС-B01-L1`), без жодних змін у seed і золотих фікстурах.
* Часткові вигляди без `tpl`: `{row_no}` — «закріплений» номер ряду (інакше за геометрією), `{zone_code}` — код зони
  замість номера, `{legacy: true}` — власне «як зараз» (не успадковувати шаблон зони чи площадки). Власні
  налаштування = є `tpl`; діють найближчі: місце → зона, що його містить → площадка (як «Власні налаштування зони»).
* Номер ряду: місця-ряди (`ROW_TEMPLATES`) зони чи шару за `row_from` (up/down — за Y, right/left — за X); закріплені
  `row_no` лишаються, решта (нові) беруть вільні номери за геометрією. Напрями секцій: `ltr` — зліва направо (у
  повернутих 90°/270° — зверху вниз), `rtl`, `odd_even` — непарні/парні по сторонах проходу; `row_mode=snake`
  змінює напрям у парних рядах; `level_dir=down` — ярус 1 вгорі. Місця на підлозі (`floor_spot`) нумеруються
  першим доступним сегментом шаблону (`pos`, `row`, `bay`, `level`) за геометрією в зоні (F01-08).
"""

import math
import re
from functools import lru_cache

from .geometry import polygon_contains

SEGMENT_KEYS = ('zone', 'row', 'bay', 'level', 'pos')
SEGMENT_KINDS = ('num', 'alpha')
ROW_FROM = ('up', 'down', 'left', 'right')
ROW_MODES = ('seq', 'snake')
BAY_DIRS = ('ltr', 'rtl', 'odd_even')
LEVEL_DIRS = ('up', 'down')
DEPTH_MODES = ('level', 'cell')
LOC_TREES = ('flat', 'row', 'section')
ROW_TEMPLATES = ('pallet_rack', 'cantilever', 'shelf', 'floor_stack')
SPOT_TEMPLATES = ('floor_spot',)
SPOT_SEGMENT_ORDER = ('pos', 'row', 'bay', 'level')
CODE_MAX_LEN = 32
TPL_MAX_LEN = 64
ZONE_CODE_MAX_LEN = 8
MAX_ROW_NO = 9999

ALIASES = {
    'prefix': 'prefix',
    'префікс': 'prefix',
    'zone': 'zone',
    'зона': 'zone',
    'row': 'row',
    'aisle': 'row',
    'ряд': 'row',
    'bay': 'bay',
    'section': 'bay',
    'секція': 'bay',
    'level': 'level',
    'tier': 'level',
    'ярус': 'level',
    'pos': 'pos',
    'position': 'pos',
    'позиція': 'pos',
}
DEFAULT_TPL = "{zone} {row} {bay} {level} {pos}"
DEFAULT_SEP = '-'
DEFAULT_SEG = {
    'zone': {'kind': 'alpha', 'width': 1, 'start': 1},
    'row': {'kind': 'num', 'width': 2, 'start': 1},
    'bay': {'kind': 'num', 'width': 2, 'start': 1},
    'level': {'kind': 'num', 'width': 1, 'start': 1},
    'pos': {'kind': 'num', 'width': 1, 'start': 1},
}
# Готові налаштування для вибору в панелі: ключ → addr (legacy = порожньо: коди як зараз)
PRESETS = {
    'legacy': {},
    'zone_row_bay_level': {'tpl': DEFAULT_TPL},
    'prefix_bay_level': {'tpl': "{prefix} B{bay} L{level} {pos}"},
    'prefix_bay_letter': {'tpl': "{prefix} {bay}{level} {pos}", 'seg': {'level': {'kind': 'alpha'}}},
    'row_odd_even': {'tpl': DEFAULT_TPL, 'bay_dir': 'odd_even'},
}

_SEP_RE = re.compile(r'^[A-Za-z0-9._/#:-]{0,3}$')
_LITERAL_RE = re.compile(r'^[A-Za-z0-9._/#:-]*$')
_TOKEN_RE = re.compile(r'\{([^{}]*)\}')


class AddrError(ValueError):
    """Помилка схеми адресації (R-22); текст — українською, показується користувачу."""


# --- розбір шаблону ---------------------------------------------------------------------------------------
@lru_cache(maxsize=256)
def parse_tpl(tpl):
    """Шаблон → кортеж слів; слово — кортеж токенів ('lit', текст) | ('seg', ключ). Помилка → AddrError."""
    if not isinstance(tpl, str) or not tpl.strip():
        raise AddrError("Шаблон коду порожній.")
    if len(tpl) > TPL_MAX_LEN:
        raise AddrError("Шаблон коду довший за %d символів." % TPL_MAX_LEN)
    words, seen = [], set()
    for raw in tpl.split():
        tokens, pos = [], 0
        for match in _TOKEN_RE.finditer(raw):
            _add_literal(tokens, raw[pos : match.start()])
            name = ALIASES.get(match.group(1).strip().lower())
            if name is None:
                raise AddrError("Невідомий сегмент {%s} у шаблоні." % match.group(1))
            if name in seen:
                raise AddrError("Сегмент {%s} повторюється в шаблоні." % match.group(1))
            seen.add(name)
            tokens.append(('seg', name))
            pos = match.end()
        _add_literal(tokens, raw[pos:])
        words.append(tuple(tokens))
    if not seen:
        raise AddrError("У шаблоні немає жодного сегмента ({ряд}, {секція}, {ярус} …).")
    return tuple(words)


def _add_literal(tokens, text):
    if not text:
        return
    if '{' in text or '}' in text:
        raise AddrError("Шаблон: дужки { } мають обрамляти назву сегмента.")
    if not _LITERAL_RE.match(text):
        raise AddrError("Шаблон: літери слова — латиниця, цифри та . _ / # : -")
    tokens.append(('lit', text))


def tpl_segments(addr):
    """Множина сегментів, що є в шаблоні (разом із prefix)."""
    return {name for word in parse_tpl(addr['tpl']) for kind, name in word if kind == 'seg'}


# --- значення сегментів -----------------------------------------------------------------------------------
def to_alpha(n):
    """1 → A, 26 → Z, 27 → AA."""
    if not isinstance(n, int) or n < 1:
        raise AddrError("Буквений сегмент: номер має бути ≥ 1.")
    out = ''
    while n:
        n, rem = divmod(n - 1, 26)
        out = chr(65 + rem) + out
    return out


def from_alpha(text):
    """A → 1, AA → 27; не буква → None."""
    if not text or not re.fullmatch(r'[A-Z]+', text):
        return None
    n = 0
    for ch in text:
        n = n * 26 + ord(ch) - 64
    return n


def format_value(spec, n):
    """Логічний номер (1-й ряд = 1) → рядок сегмента за `kind/width/start`; рядок (код зони, prefix) — як є."""
    if isinstance(n, str):
        return n
    value = spec['start'] + n - 1
    if spec['kind'] == 'alpha':
        return to_alpha(value)
    if value < 0:
        raise AddrError("Номер сегмента менший за нуль.")
    return str(value).zfill(spec['width'])


def _word_values(addr, vals):
    """Рядки слів шаблону; слово без значення сегмента → None."""
    words = []
    for word in parse_tpl(addr['tpl']):
        parts = []
        for kind, item in word:
            if kind == 'lit':
                parts.append(item)
                continue
            value = vals.get(item)
            if value is None or value == '':
                parts = None
                break
            parts.append(str(value) if item == 'prefix' else format_value(addr['seg'][item], value))
        words.append(None if parts is None else ''.join(parts))
    return words


def render_code(addr, vals):
    """Код за повним `addr` і значеннями {prefix, zone, row, bay, level, pos}; None — слово пропускається."""
    return addr['sep'].join(w for w in _word_values(addr, vals) if w is not None)


def short_name(addr, vals):
    """Останнє слово коду — коротке ім'я локації для `loc_tree` row/section (F01-05)."""
    words = [w for w in _word_values(addr, vals) if w is not None]
    return words[-1] if words else ''


def parse_code(addr, code, prefix=None):
    """Зворотний розбір: код → {prefix, zone, row, bay, level, pos} (логічні номери; відсутні — None) або None."""
    words = parse_tpl(addr['tpl'])
    for mask in range(2 ** len(words) - 1, 0, -1):
        chosen = [w for i, w in enumerate(words) if mask >> i & 1]
        pattern = re.escape(addr['sep']).join(_word_regex(addr, w, prefix) for w in chosen)
        match = re.fullmatch(pattern, code)
        if not match:
            continue
        found = dict.fromkeys(('prefix',) + SEGMENT_KEYS)
        for key, text in match.groupdict().items():
            found[key] = text if key == 'prefix' else _decode(addr['seg'][key], text)
        if all(v is not None for k, v in found.items() if k != 'prefix' and k in match.groupdict()):
            return found
    return None


def _word_regex(addr, word, prefix):
    parts = []
    for kind, item in word:
        if kind == 'lit':
            parts.append(re.escape(item))
        elif item == 'prefix':
            parts.append('(?P<prefix>%s)' % (re.escape(prefix) if prefix else r'[A-Z0-9]+(?:-[A-Z0-9]+)*?'))
        elif addr['seg'][item]['kind'] == 'alpha':
            parts.append('(?P<%s>[A-Z]+)' % item)
        else:
            parts.append('(?P<%s>[0-9]+)' % item)
    return ''.join(parts)


def _decode(spec, text):
    value = from_alpha(text) if spec['kind'] == 'alpha' else int(text)
    return None if value is None else value - spec['start'] + 1


# --- нормалізація (R-22) ----------------------------------------------------------------------------------
def _int_in(value, lo, hi, label):
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or int(value) != value
    ):
        raise AddrError("%s: очікується ціле число." % label)
    value = int(value)
    if value < lo or value > hi:
        raise AddrError("%s: допустимо від %d до %d." % (label, lo, hi))
    return value


def _choice(value, allowed, label):
    if value not in allowed:
        raise AddrError("%s: допустимо %s." % (label, ", ".join(allowed)))
    return value


def _empty(value):
    return value is None or value is False or (isinstance(value, str) and value == '')


def normalize_addr(value):
    """`addr` → чистий словник (невідомі ключі відкидаються). {} — legacy. Помилка → AddrError.

    Є `tpl` — повні налаштування з умовчаннями; немає — лише `row_no`/`zone_code`, якщо задані."""
    if _empty(value) or (isinstance(value, str) and value == 'legacy'):
        return {}
    if not isinstance(value, dict):
        raise AddrError("Адресація має бути об'єктом.")
    out = {}
    if not _empty(value.get('row_no')):
        out['row_no'] = _int_in(value['row_no'], 1, MAX_ROW_NO, "Номер ряду")
    zone_code = value.get('zone_code')
    if not _empty(zone_code):
        if not isinstance(zone_code, str) or len(zone_code) > ZONE_CODE_MAX_LEN or not _LITERAL_RE.match(zone_code):
            raise AddrError("Код зони: до %d символів, латиниця, цифри та . _ / # : -" % ZONE_CODE_MAX_LEN)
        out['zone_code'] = zone_code
    if _empty(value.get('tpl')):
        if value.get('legacy') is True:
            out['legacy'] = True  # власні налаштування «як зараз»: не успадковувати шаблон площадки чи зони
        return out
    parse_tpl(value['tpl'])
    sep = value.get('sep', DEFAULT_SEP)
    if not isinstance(sep, str) or not _SEP_RE.match(sep):
        raise AddrError("Роздільник: до 3 символів (латиниця, цифри та . _ / # : -).")
    segs = value.get('seg') or {}
    if not isinstance(segs, dict):
        raise AddrError("Сегменти мають бути об'єктом.")
    seg_out = {}
    for key in SEGMENT_KEYS:
        raw = segs.get(key) or {}
        if not isinstance(raw, dict):
            raise AddrError("Сегмент «%s»: очікується об'єкт." % key)
        base = DEFAULT_SEG[key]
        label = "Сегмент «%s»" % key
        kind = _choice(raw.get('kind', base['kind']), SEGMENT_KINDS, label + ": вид")
        seg_out[key] = {
            'kind': kind,
            'width': _int_in(raw.get('width', base['width']), 1, 8, label + ": ширина"),
            'start': _int_in(raw.get('start', base['start']), 1 if kind == 'alpha' else 0, 999, label + ": початок"),
        }
    out.update(
        tpl=value['tpl'].strip(),
        sep=sep,
        seg=seg_out,
        row_from=_choice(value.get('row_from', 'up'), ROW_FROM, "Напрям рядів"),
        row_mode=_choice(value.get('row_mode', 'seq'), ROW_MODES, "Режим рядів"),
        bay_dir=_choice(value.get('bay_dir', 'ltr'), BAY_DIRS, "Напрям секцій"),
        level_dir=_choice(value.get('level_dir', 'up'), LEVEL_DIRS, "Напрям ярусів"),
    )
    return out


def safe_normalize(value):
    """Як `normalize_addr`, але хибне значення (старі дані) вважається порожнім, а не помилкою."""
    try:
        return normalize_addr(value)
    except AddrError:
        return {}


def preset_addr(key):
    """Повні налаштування пресету (legacy → {})."""
    if key not in PRESETS:
        raise AddrError("Невідомий пресет адресації «%s»." % key)
    return normalize_addr(PRESETS[key])


def normalize_depth_mode(value):
    if _empty(value):
        return None
    return _choice(value, DEPTH_MODES, "Глибина локацій")


def is_own(addr):
    """Чи є власні налаштування (шаблон чи `legacy`) — а не лише закріплений номер чи код зони."""
    return bool(addr) and ('tpl' in addr or addr.get('legacy') is True)


def effective_addr(*levels):
    """Найближчі власні налаштування: `effective_addr(slot, zone, site)`; немає жодних чи `legacy` → None (legacy)."""
    for item in levels:
        if is_own(item):
            return None if item.get('legacy') else item
    return None


# --- геометрія місць і контекст --------------------------------------------------------------------------
def slot_polygon(slot):
    """Контур зони у світових координатах: `params.polygon` (сервер) або прямокутник `x,y,rotation,length,width`."""
    params = slot.get('params') or {}
    poly = params.get('polygon') or slot.get('polygon')
    if poly and len(poly) >= 3:
        return [(float(px), float(py)) for px, py in poly]
    length, width = params.get('length'), params.get('width')
    if not length or not width:
        return None
    rot = math.radians(slot.get('rotation') or 0.0)
    cos, sin = math.cos(rot), math.sin(rot)
    cx, cy = slot.get('x') or 0.0, slot.get('y') or 0.0
    corners = ((-length / 2, -width / 2), (length / 2, -width / 2), (length / 2, width / 2), (-length / 2, width / 2))
    return [(cx + px * cos - py * sin, cy + px * sin + py * cos) for px, py in corners]


def _poly_area(poly):
    total = 0.0
    for i, (x1, y1) in enumerate(poly):
        x2, y2 = poly[(i + 1) % len(poly)]
        total += x1 * y2 - x2 * y1
    return abs(total) / 2


def _center(slot, poly=None):
    if poly:
        return (sum(p[0] for p in poly) / len(poly), sum(p[1] for p in poly) / len(poly))
    return (slot.get('x') or 0.0, slot.get('y') or 0.0)


def _order_key(row_from, point, uid):
    """Ключ порядку рядів від входу: основна вісь за `row_from`, далі друга вісь, далі uid (стабільність)."""
    x, y = (
        math.floor(point[0] * 100 + 0.5),
        math.floor(point[1] * 100 + 0.5),
    )  # сантиметри, півці вгору (як Math.round у JS)
    main = {'up': y, 'down': -y, 'right': x, 'left': -x}[row_from]
    side = x if row_from in ('up', 'down') else y
    return (main, side, str(uid))


def _uid(slot):
    return slot.get('uid') or slot.get('id')


def _free_numbers(used):
    n = 0
    while True:
        n += 1
        if n not in used:
            yield n


def address_context(slots, site_addr=None, site_depth_mode='level'):
    """Контекст адресації кожного місця: uid → {addr, zone, row, spot, depth_mode}.

    `slots` — словники {uid|id, layer_id, template, code_prefix, x, y, rotation, params, addr, depth_mode}; місця зон
    (`template='zone'`) дають налаштування (addr, depth_mode, zone_code) і номер зони. Вхід не змінюється."""
    site_addr = safe_normalize(site_addr)
    out = {}
    by_layer = {}
    for slot in slots:
        by_layer.setdefault(slot.get('layer_id'), []).append(slot)
    for layer_slots in by_layer.values():
        zones = []
        for slot in layer_slots:
            poly = slot_polygon(slot) if slot['template'] == 'zone' else None
            if poly:
                zones.append((slot, poly, _poly_area(poly)))
        zone_from = site_addr.get('row_from', 'up')
        ordered = sorted(zones, key=lambda z: _order_key(zone_from, _center(z[0], z[1]), _uid(z[0])))
        zone_no = {_uid(z[0]): index for index, z in enumerate(ordered, 1)}
        scopes = {}
        for slot in layer_slots:
            if slot['template'] == 'zone':
                continue
            point = _center(slot)
            host = None
            for zone, poly, area in zones:
                if polygon_contains(poly, point) and (host is None or area < host[1]):
                    host = (zone, area)
            zone = host[0] if host else None
            scopes.setdefault(_uid(zone) if zone else None, (zone, []))[1].append(slot)
        for zone, members in scopes.values():
            zone_addr = safe_normalize(zone.get('addr')) if zone else {}
            scope_addr = effective_addr(zone_addr, site_addr) or {}
            row_from = scope_addr.get('row_from', 'up')
            zone_value = (zone_addr.get('zone_code') or zone_no.get(_uid(zone))) if zone else None
            depth_mode = (zone or {}).get('depth_mode') or site_depth_mode or 'level'
            numbers = {}
            for templates in (ROW_TEMPLATES, SPOT_TEMPLATES):
                group = [s for s in members if s['template'] in templates]
                pinned = {_uid(s): safe_normalize(s.get('addr')).get('row_no') for s in group}
                free = _free_numbers({n for n in pinned.values() if n})
                for slot in sorted(group, key=lambda s: _order_key(row_from, _center(s), _uid(s))):
                    numbers[_uid(slot)] = pinned[_uid(slot)] or next(free)
            for slot in members:
                uid = _uid(slot)
                is_row = slot['template'] in ROW_TEMPLATES
                out[uid] = {
                    'addr': effective_addr(safe_normalize(slot.get('addr')), zone_addr, site_addr),
                    'zone': zone_value,
                    'row': numbers.get(uid) if is_row else None,
                    'spot': None if is_row else numbers.get(uid),
                    'depth_mode': slot.get('depth_mode') or depth_mode,
                }
        for slot in layer_slots:
            if slot['template'] == 'zone':
                out[_uid(slot)] = {
                    'addr': effective_addr(safe_normalize(slot.get('addr')), site_addr),
                    'zone': None,
                    'row': None,
                    'spot': None,
                    'depth_mode': slot.get('depth_mode') or site_depth_mode or 'level',
                }
    return out


def usable_context(ctx):
    """Контекст, що змінює коди чи глибину; інакше None (legacy: `generate_cells` без `ctx`)."""
    return ctx if ctx and (ctx.get('addr') or ctx.get('depth_mode') == 'cell') else None


def state_contexts(state):
    """Контексти місць стану перевірок (`{site: {addr, depth_mode}, slots: […]}`): uid → ctx (див. `usable_context`).

    Для `checks._Scene.slot_cells`: `generate_cells(…, ctx=usable_context(contexts.get(uid)))`."""
    site = state.get('site') or {}
    return address_context(state.get('slots') or [], site.get('addr'), site.get('depth_mode') or 'level')


# --- номери сегментів комірки -----------------------------------------------------------------------------
def bay_forward(rot):
    """Чи збігається зростання локальної осі X з напрямом «зліва направо» (у повернутих 90°/270° — «зверху вниз»)."""
    radians = math.radians(rot or 0.0)
    cos, sin = math.cos(radians), math.sin(radians)
    return cos > 0 if abs(cos) >= abs(sin) else sin < 0


def cell_vals(ctx, prefix, rot, raw, sizes):
    """Значення сегментів комірки.

    raw: {k (секція вздовж X, 1…), side (1|2), level (1…|None), pos (1…|None), pos_n, pos_x (позиції вздовж X)};
    sizes: {bays, levels, sides}."""
    addr = ctx['addr']
    row = ctx.get('row')
    left_right = bay_forward(rot)
    forward = left_right
    if addr['row_mode'] == 'snake' and row and row % 2 == 0:
        forward = not forward
    if addr['bay_dir'] == 'rtl':
        forward = not forward
    k = raw['k'] if forward else sizes['bays'] - raw['k'] + 1
    side = raw.get('side', 1)
    if addr['bay_dir'] == 'odd_even':
        side_no = side if sizes.get('sides', 1) > 1 else (1 if (row or 1) % 2 else 2)
        bay = 2 * k - 1 if side_no == 1 else 2 * k
    else:
        bay = k + (side - 1) * sizes['bays']
    level = raw.get('level')
    if level is not None and addr['level_dir'] == 'down':
        level = sizes['levels'] - level + 1
    pos = raw.get('pos')
    if pos is not None and raw.get('pos_x') and not left_right:
        pos = raw['pos_n'] - pos + 1
    return {'prefix': prefix, 'zone': ctx.get('zone'), 'row': row, 'bay': bay, 'level': level, 'pos': pos}


def spot_vals(ctx, prefix):
    """Значення сегментів місця на підлозі: номер у зоні займає перший доступний сегмент шаблону (F01-08)."""
    have = tpl_segments(ctx['addr'])
    vals = {'prefix': prefix, 'zone': ctx.get('zone'), 'row': None, 'bay': None, 'level': None, 'pos': None}
    for key in SPOT_SEGMENT_ORDER:
        if key in have:
            vals[key] = ctx.get('spot') or 1
            break
    return vals


# --- попередній перегляд і конфлікти ---------------------------------------------------------------------
def find_duplicates(codes):
    """Коди, що повторюються (порядок першої появи)."""
    seen, dup = set(), []
    for code in codes:
        if code in seen and code not in dup:
            dup.append(code)
        seen.add(code)
    return dup


def preview(codes, old_codes=None, limit=10):
    """F01-03: {first (≤limit), last, total, changed, duplicates, too_long}; `old_codes` — попередні коди."""
    changed = 0
    if old_codes is not None:
        changed = sum(1 for index, code in enumerate(codes) if index >= len(old_codes) or old_codes[index] != code)
    return {
        'first': list(codes[:limit]),
        'last': codes[-1] if codes else None,
        'total': len(codes),
        'changed': changed,
        'duplicates': find_duplicates(codes),
        'too_long': [c for c in codes if len(c) > CODE_MAX_LEN],
    }


def slot_codes(slot, ctx, elevation=0.0):
    """Коди комірок місця (з урахуванням контексту адресації)."""
    from . import cells

    return [
        c['code']
        for c in cells.generate_cells(
            slot['template'],
            slot.get('code_prefix') or '',
            slot.get('x') or 0.0,
            slot.get('y') or 0.0,
            slot.get('rotation') or 0.0,
            slot.get('params') or {},
            None,
            elevation,
            ctx,
        )
    ]


def scene_codes(slots, site_addr=None, site_depth_mode='level', elevations=None):
    """uid → список кодів комірок усіх місць сцени (контекст рахується один раз)."""
    contexts = address_context(slots, site_addr, site_depth_mode)
    return {
        _uid(s): slot_codes(s, contexts[_uid(s)], (elevations or {}).get(s.get('layer_id'), 0.0))
        for s in slots
        if s['template'] != 'zone'
    }


def conflicts(codes_by_slot, occupied=()):
    """F01-07: {код: [uid місць]} для кодів, що повторюються в проєкті, і кодів, зайнятих поза ним (`occupied`)."""
    owners = {}
    for uid, codes in codes_by_slot.items():
        for code in codes:
            owners.setdefault(code, []).append(uid)
    occupied = set(occupied)
    return {code: uids for code, uids in owners.items() if len(uids) > 1 or code in occupied}


# --- що йде в Odoo (F01-05, F01-11): лише розрахунок -------------------------------------------------------
def location_vals(code, vals, addr=None, loc_tree='flat'):
    """Поля локації за кодом і значеннями сегментів: {name, barcode, td_row, td_bay, td_level, td_pos}.

    `flat` — ім'я = повний код; `row`/`section` — коротке ім'я (останнє слово), повний код у штрихкоді (F01-11)."""
    name = code
    if loc_tree != 'flat' and addr:
        name = short_name(addr, vals) or code
    return {
        'name': name,
        'barcode': code,
        'td_row': vals.get('row') or 0,
        'td_bay': vals.get('bay') or 0,
        'td_level': vals.get('level') or 0,
        'td_pos': vals.get('pos') or 0,
    }
