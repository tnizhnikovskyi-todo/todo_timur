"""Спільна класифікація об'єктів 3D-моделі для сіда модуля (extract_seed.py) і для прикладу прототипу (build/constructor/proto/gen_scene.py).

Вхід — `data/scene_inventory.json` (`objects`: {код: {kind, layer, x, y, z, L, W, H, yaw, label, …}}). Кожен кодований об'єкт стає рівно одним із:
  * `cell`    — комірка шаблону стелажа (FG-R*, RCK-R*, FUR-R*, EB-U*): її породжує шаблон місця, окремого запису немає;
  * `frame`   — каркас стелажа (FG-RACK-R*, RACK-R*, EB-U*): це саме місце-шаблон;
  * `machine` / `zone` — верстат із каталогу й зона-розмітка (їх будує сід за старою розкладкою);
  * `exact`   — окреме місце на одну комірку (стоси, комплекти, зони видачі): `floor_stack` з `code_style='exact'`;
  * `contour` — контур-зона (мережі, розмітка на підлозі, док-ворота, дах, огорожа; більший з пари тверді-що-перетинаються):
    шаблон `zone`, не твердий об'єкт;
  * `place`   — розміщення зі зведеним варіантом «Об'єкти сцени» (паспорт на вид, габарит — AABB моделі).
Люди й транспорт (`DYNAMIC_KINDS`) — динамічні: прототип пропускає їх у перетинах, проходах і пожежних проходах.
"""

import math
import re
import statistics

TPL_CELL = re.compile(r'^(FG-R\d+-B|RCK-R\d+-\d[A-D]$|FUR-R\d+-S|EB-U\d+-S)')
FRAME = re.compile(r'^(FG-RACK-R\d+|RACK-R\d+|EB-U\d+)$')
GROUP_KIND = {
    'Будівля': 'building',
    'Склади й логістика': 'storage',
    'Виробництво': 'production',
    'Інженерні мережі': 'engineering',
    'Пожежна безпека': 'engineering',
    'ІТ і Odoo': 'engineering',
    'Територія й охорона': 'yard',
    'Люди й транспорт': 'custom',
}
_ALL_SLOTS = ['pallet_rack', 'cantilever', 'shelf', 'floor_stack', 'zone']
# група шарів переглядача → вид шару й типові параметри (edit-ролі без менеджера: менеджер редагує все завжди)
GROUP_DEF = {
    'Будівля': dict(kind='building', roles=[], grid=1.0, aisle=3.0, slots=['zone'], load=0.0, opacity=0.35),
    'Склади й логістика': dict(kind='storage', roles=['storekeeper'], grid=0.5, aisle=3.3, slots=_ALL_SLOTS, load=30.0, opacity=0.55),
    'Виробництво': dict(kind='production', roles=['technologist'], grid=0.5, aisle=3.6, slots=['machine_spot', 'zone'], load=40.0, opacity=0.55),
    'Інженерні мережі': dict(kind='engineering', roles=['engineer'], grid=1.0, aisle=1.0, slots=['zone'], load=5.0, opacity=0.4),
    'Пожежна безпека': dict(kind='engineering', roles=['engineer'], grid=1.0, aisle=1.0, slots=['zone'], load=5.0, opacity=0.4),
    'ІТ і Odoo': dict(kind='engineering', roles=['engineer'], grid=1.0, aisle=1.0, slots=['zone'], load=5.0, opacity=0.4),
    'Територія й охорона': dict(kind='yard', roles=[], grid=1.0, aisle=5.0, slots=['floor_stack', 'machine_spot', 'zone'], load=80.0, opacity=0.45),
    'Люди й транспорт': dict(kind='custom', roles=[], grid=0.5, aisle=1.2, slots=['zone'], load=5.0, opacity=0.45),
}  # fmt: skip
DYNAMIC_KINDS = ('person', 'vehicle')
# вид об'єкта → (назва паспорта, категорія конструктора)
SCENE_KINDS = {
    'building': ('Будівлі й споруди', 'other'),
    'equipment': ('Допоміжне обладнання', 'other'),
    'power': ('Електрообладнання', 'panel'),
    'it': ('ІТ-обладнання', 'panel'),
    'hvac': ('Вентиляція й опалення', 'other'),
    'lighting': ('Освітлення', 'other'),
    'fire': ('Пожежна автоматика', 'other'),
    'safety': ('Засоби безпеки', 'other'),
    'security': ('Охорона й доступ', 'other'),
    'vehicle': ('Транспорт', 'forklift'),
    'person': ('Персонал', 'other'),
}
# шари, що відкриваються схованими (мережі, пожежа, ІТ, територія, дах): стають видимими при активації; приклад читається краще
HIDDEN_GROUPS = ('Інженерні мережі', 'Пожежна безпека', 'ІТ і Odoo', 'Територія й охорона')
HIDDEN_LAYERS = ('roof', 'roofdeck')
GROUP_HUE = {
    'Будівля': 210, 'Склади й логістика': 145, 'Виробництво': 207, 'Інженерні мережі': 36, 'Пожежна безпека': 5,
    'ІТ і Odoo': 265, 'Територія й охорона': 65, 'Люди й транспорт': 15,
}  # fmt: skip
ROOF_ELEVATION = {'roof': 9.0}  # у моделі шар без кодованих об'єктів: відмітка покрівлі


def classify(objects, machine_codes, zone_codes):
    """→ {'cell': [...], 'frame': [...], 'machine': [...], 'zone': [...], 'exact': [...], 'contour': [...], 'place': [...]}.

    Кожен елемент — `{code, layer, kind, label, x, y, z, L, W, H, yaw}` (метри, градуси; x,y — центр AABB)."""
    out = {k: [] for k in ('cell', 'frame', 'machine', 'zone', 'exact', 'contour', 'place')}
    for code, o in objects.items():
        row = dict(o, code=code, yaw=o.get('yaw') or 0)
        kind = o['kind']
        if TPL_CELL.match(code):
            bucket = 'cell'
        elif FRAME.match(code):
            bucket = 'frame'
        elif code in machine_codes:
            bucket = 'machine'
        elif code in zone_codes:
            bucket = 'zone'
        elif kind in ('stock', 'bin', 'kit'):
            bucket = 'exact'
        else:
            area = o['L'] * o['W']
            big = area > (2000 if kind == 'building' else 150) or max(o['L'], o['W']) > (
                200 if kind == 'building' else 25
            )
            flat = o['H'] < 0.2  # розмітка на підлозі (маршрути евакуації) — контур, а не твердий об'єкт
            if kind not in DYNAMIC_KINDS and kind != 'machine' and (big or flat or kind == 'dock'):
                bucket = 'contour'  # док-ворота — частина стіни
            else:
                bucket = 'place'
        out[bucket].append(row)
    _demote_overlaps(out)
    return out


def _corners(row):
    a = math.radians(row['yaw'])
    c, s = math.cos(a), math.sin(a)
    hx, hy = row['L'] / 2.0, row['W'] / 2.0
    return [
        (row['x'] + px * c - py * s, row['y'] + px * s + py * c)
        for px, py in ((-hx, -hy), (hx, -hy), (hx, hy), (-hx, hy))
    ]


def _overlap(a, b, eps=0.01):
    """SAT для двох прямокутників: перетин глибше за eps (дотик краєм не рахується)."""
    pa, pb = _corners(a), _corners(b)
    for poly in (pa, pb):
        for i in range(4):
            (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % 4]
            nx, ny = y1 - y2, x2 - x1
            n = math.hypot(nx, ny) or 1.0
            nx, ny = nx / n, ny / n
            da = [x * nx + y * ny for x, y in pa]
            db = [x * nx + y * ny for x, y in pb]
            if max(da) <= min(db) + eps or max(db) <= min(da) + eps:
                return False
    return True


def _demote_overlaps(out):
    """Об'єкти одного шару, що перетинаються (вкладені групи: РП «RM6-1» навколо щитів, зона QC навколо стосу тощо), не можуть бути
    твердими разом: більший за площею стає контуром-зоною (не твердий об'єкт). Верстати каталогу не чіпаємо."""
    while True:
        rows = [r for r in out['place'] + out['exact'] if r['kind'] not in DYNAMIC_KINDS]
        hit = None
        for i, a in enumerate(rows):
            for b in rows[i + 1 :]:
                if a['layer'] == b['layer'] and _overlap(a, b):
                    hit = max((a, b), key=lambda r: r['L'] * r['W'])
                    break
            if hit:
                break
        if not hit:
            return
        for bucket in ('place', 'exact'):
            if hit in out[bucket]:
                out[bucket].remove(hit)
        hit['demoted'] = True
        out['contour'].append(hit)


def layer_elevations(inventory_layers, classified):
    """{ключ шару: відмітка, м}: медіана z об'єктів шару (крім комірок/стосів), 0, якщо < 0.5 м; покрівля — 9.0."""
    zs = {}
    for bucket in ('machine', 'zone', 'contour', 'place'):
        for row in classified[bucket]:
            zs.setdefault(row['layer'], []).append(row['z'])
    out = {}
    for layer in inventory_layers:
        key = layer['key']
        if key in ROOF_ELEVATION:
            out[key] = ROOF_ELEVATION[key]
            continue
        med = statistics.median(zs[key]) if zs.get(key) else 0
        out[key] = round(med, 1) if med >= 0.5 else 0
    return out


def layer_visible(layer):
    return layer['group'] not in HIDDEN_GROUPS and layer['key'] not in HIDDEN_LAYERS


def layer_colors(inventory_layers):
    """{ключ шару: '#rrggbb'}: відтінок за групою, світлота змінюється за номером шару в групі."""
    import colorsys

    out, index = {}, {}
    for layer in inventory_layers:
        group = layer['group']
        i = index[group] = index.get(group, -1) + 1
        rgb = colorsys.hls_to_rgb(GROUP_HUE[group] / 360, 0.42 + 0.05 * (i % 4), 0.45)
        out[layer['key']] = '#%02x%02x%02x' % tuple(int(c * 255) for c in rgb)
    return out
