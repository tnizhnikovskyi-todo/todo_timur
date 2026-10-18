# Дописує в src/seed.json шари й об'єкти сцени з інвентаря 3D-моделі (scene_inventory.json).
# Класифікація — спільна з сідом модуля: td_constructor/tools/scene_classify.py.
# Запуск: python3 gen_scene.py [<корінь td_constructor>]; ідемпотентний (ключі layers/scene перезаписуються).
import json
import os
import sys

D = os.path.dirname(os.path.abspath(__file__))
MOD = sys.argv[1] if len(sys.argv) > 1 else os.path.normpath(os.path.join(D, '../../../odoo_addons/td_constructor'))
sys.path.insert(0, os.path.join(MOD, 'tools'))
import scene_classify as sc  # noqa: E402

SEED = os.path.join(D, 'src', 'seed.json')
inv = json.load(open(os.path.join(MOD, 'data', 'scene_inventory.json'), encoding='utf-8'))
seed = json.load(open(SEED, encoding='utf-8'))
for k in ('layers', 'scene'):
    seed.pop(k, None)
OBJ = inv['objects']
r3 = lambda v: round(v, 3)
cl = sc.classify(OBJ, {m[0] for m in seed['machines']}, {z[0] for z in seed['zones']})
elev = sc.layer_elevations(inv['layers'], cl)

col = sc.layer_colors(inv['layers'])
layers = [[ly['key'], ly['label'], ly['group'], elev[ly['key']], col[ly['key']], 1 if sc.layer_visible(ly) else 0] for ly in inv['layers']]
seed['layers'] = layers
for m in seed['machines']:  # поза верстата — з інвентаря (x,y — центр AABB; rotation = yaw): збігається з базою «Переглядача»
    o = OBJ[m[0]]
    m[3], m[4], m[5] = o['x'], o['y'], o.get('yaw', 0)
    m[6:] = [o['layer']]
seed['scene'] = {
    'p': [[r['code'], r['layer'], r['kind'], r3(r['x']), r3(r['y']), r3(r['z']), r3(r['L']), r3(r['W']), r3(r['H']), r['yaw'], r.get('label') or r['code']] for r in cl['place']],
    's': [[r['code'], r['layer'], r3(r['x']), r3(r['y']), r3(r['z']), max(r3(r['L']), 0.1), max(r3(r['W']), 0.1), max(r3(r['H']), 0.05), r['yaw'], r.get('label') or r['code']] for r in cl['exact']],
    'c': [[r['code'], r['layer'], r3(r['x']), r3(r['y']), r3(r['z']), r3(r['L']), r3(r['W']), r.get('label') or r['code']] for r in cl['contour']],
}
seed['src'] = seed.get('src', '').split(' + scene_inventory')[0] + ' + scene_inventory.json (3D-модель переглядача)'
s = json.dumps(seed, ensure_ascii=False, separators=(',', ':'))
open(SEED, 'w', encoding='utf-8').write(s)
print(len(s), 'bytes;', len(layers), 'шарів;', {k: len(v) for k, v in cl.items()})
print('усього', sum(len(v) for v in cl.values()), 'з', len(OBJ))
