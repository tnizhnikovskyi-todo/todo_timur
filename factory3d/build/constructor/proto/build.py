import json, os
D = os.path.dirname(os.path.abspath(__file__))
rd = lambda p: open(os.path.join(D, 'src', p), encoding='utf-8').read()
CDN = 'https://cdn.jsdelivr.net/npm/'
scripts = [
 'three@0.147.0/build/three.min.js',
 'three@0.147.0/examples/js/controls/OrbitControls.js',
 'three@0.147.0/examples/js/loaders/GLTFLoader.js',
 'three@0.147.0/examples/js/loaders/OBJLoader.js',
 'three@0.147.0/examples/js/loaders/MTLLoader.js',
 'three@0.147.0/examples/js/loaders/STLLoader.js',
 'three@0.147.0/examples/js/libs/fflate.min.js',
 'three@0.147.0/examples/js/loaders/FBXLoader.js',
 'three@0.147.0/examples/js/loaders/ColladaLoader.js',
 'three@0.147.0/examples/js/loaders/3MFLoader.js',
 'three@0.147.0/examples/js/exporters/GLTFExporter.js',
 'dxf-parser@1.1.2/dist/dxf-parser.min.js',
]
parts = ['00_util.js', '10_data.js', '20_store.js', '30_checks.js', '40_scene.js', '50_ui.js', '60_dialogs.js', '65_models.js', '70_main.js']
seed = rd('seed.json').strip()
js = "'use strict';\nconst SEED = " + seed + ";\n" + "\n".join(rd(p).replace("'use strict';\n", '', 1) if p == '00_util.js' else rd(p) for p in parts)
assert '</script' not in js.lower()
out = ['<title>Конструктор</title>', '<meta name="claude:viewport-fit-sides" content="cover">',
       '<style>\n' + rd('style.css') + '</style>', rd('body.html')]
out += ['<script src="%s%s"></script>' % (CDN, s) for s in scripts]
out.append('<script>\n' + js + '\n</script>\n')
html = "\n".join(out)
open(os.path.join(D, 'index.html'), 'w', encoding='utf-8').write(html)
print(len(html.encode('utf-8')), 'bytes')
