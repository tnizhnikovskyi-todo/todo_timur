# f3d-loaders: вендорені бібліотеки

Один файл `f3d-loaders.esm.js` збирається `tools/build_loaders.mjs` (esbuild, minify, ESM). Серверу нічого збирати не треба.

| Що | Версія | Ліцензія | Звідки |
|---|---|---|---|
| three.js examples/jsm: `OBJLoader`, `MTLLoader`, `STLLoader`, `FBXLoader` (+`NURBSCurve`), `ColladaLoader` (+`TGALoader`), `3MFLoader` (експортується як `ThreeMFLoader`), `exporters/GLTFExporter` | three r160 (`three@0.160.0`) | MIT, © 2010-2023 three.js authors | `npm pack three@0.160.0` → `package/examples/jsm` |
| fflate (потрібна FBX і 3MF; експортується як `fflate`) | 0.6.9 (вбудована в three r160 `examples/jsm/libs/fflate.module.js`) | MIT, © Arjun Barrett | там само |
| Збирач esbuild | будь-який актуальний (на момент збірки 0.2x) | MIT | `npm install esbuild` (лише для розробника) |

Модуль `three` усередині бандла замінено shim-ом на `globalThis.__F3D_THREE__`: ядро three.js — бандл переглядача
`factory3d_viewer/static/lib/three/three-bundle.esm.js` (той самий r160), тому класи (`Mesh`, `BufferGeometry`, …) спільні.
`loadThree()` (`static/src/model/three.js`) кладе `THREE` у `globalThis.__F3D_THREE__` перед `import()` цього файла.

Перезбірка: `node tools/build_loaders.mjs` (потрібен npm-реєстр) або з локальними каталогами:
`node tools/build_loaders.mjs --three-dir <розпакований three@0.160.0/package> --esbuild-dir <каталог з node_modules/esbuild>`.
Ніяких CDN: усе вантажиться з `/factory3d_constructor/static/lib/f3d-loaders/` (AC-05).
