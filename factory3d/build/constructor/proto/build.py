"""Збирає прототип конструктора (build/constructor/proto/index.html) з ТИХ САМИХ файлів, що й модуль td_constructor.

Ядро factory3d/core/constructor/* (+ artifact/*, хост src/main.js) → IIFE через `node tools/build_core.mjs proto`
(esbuild: змінна ESBUILD_DIR або `npm install esbuild` у тимчасовий каталог). Стилі — constructor_action.scss модуля
(CSS із вкладеністю; `//`-коментарі прибираються) + page.css (шрифти, тло, автотема). three.js та інші бібліотеки — з CDN
(CSP артефакта). Публікує прототип менеджер; тут лише збірка.
"""
import os
import re
import subprocess
import tempfile

D = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(D, '..', '..', '..'))  # factory3d/
rd = lambda p: open(p, encoding='utf-8').read()
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


def bundle():
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, 'proto.js')
        cmd = ['node', os.path.join(ROOT, 'tools', 'build_core.mjs'), 'proto', '--out', out]
        if os.environ.get('F3D_PROTO_MINIFY') == '1':
            cmd.append('--minify')
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)
        return rd(out)


def styles():
    scss = rd(os.path.join(ROOT, 'odoo_addons', 'td_constructor', 'static', 'src', 'action', 'constructor_action.scss'))
    scss = re.sub(r'(?m)^\s*//.*$', '', scss)
    return rd(os.path.join(D, 'src', 'page.css')) + '\n' + scss


js = bundle()
assert '</script' not in js.lower()
out = ['<title>Конструктор</title>', '<meta name="claude:viewport-fit-sides" content="cover">',
       '<style>\n' + styles() + '</style>', '<div id="f3dRoot" class="o_f3d_constructor"></div>']
out += ['<script src="%s%s"></script>' % (CDN, s) for s in scripts]
out.append('<script>\n' + js + '\n</script>\n')
html = "\n".join(out)
open(os.path.join(D, 'index.html'), 'w', encoding='utf-8').write(html)
print(len(html.encode('utf-8')), 'bytes')
