/** @odoo-module */
// Пакетування статичної геометрії сцени (PERF: draw-виклики за кадр).
// GLB кожної частини містить тисячі дрібних мешів (палети, коробки, деталі верстатів) з окремим матеріалом на кожен —
// це 3–7 тис. draw-викликів за кадр (основний прохід + тіні). Тут меші, які ніхто не чіпає, малюються пакетами:
//  - один пакет = один Mesh на (вузол шару, параметри матеріалу, клітинка плану); геометрія запечена у систему вузла
//    шару, колір кожного мешу — атрибут вершин (матеріал пакета білий), тож зміна кольору мешу (планка-ярлик комірки)
//    не виводить його з пакета;
//  - оригінальні меші лишаються в сцені як «проксі»: вибір (pick), bbox, підсвітка, stock_load, розкладка конструктора
//    працюють з ними, як і раніше. Проксі, що в пакеті («холодні»), ховаються лише на час `renderer.render`
//    (`beforeRender`/`afterRender`), поза рендером `visible` не чіпаємо — isShown() і сторонні Raycaster не змінюються;
//  - якщо проксі «розігрівся» (emissive від paint/drill, непрозорість, зсув або приховування розкладкою, вантаж
//    сховано stock_load), його діапазон індексів у пакеті обнуляється (виродженні трикутники), і він малюється сам,
//    як до пакетування. Повернувся в початковий стан — знову в пакеті. `sync()` порівнює стан усіх проксі, `touch(root)` —
//    лише піддерева (викликається з paint без очікування опитування).
// Не пакетуються: InstancedMesh, лампи статусу (role=status), прозорі й текстуровані матеріали, f3dStock, skinned.
// УВАГА (rjsmin): мінімізатор асетів Odoo стирає пробіли у вкладених шаблонних літералах — тут їх немає.

const MAX_U16 = 65535;
const TEX = ["map", "normalMap", "roughnessMap", "metalnessMap", "emissiveMap", "aoMap", "alphaMap", "envMap", "lightMap", "bumpMap"];

/** Меш придатний для пакета: лише `position`+`normal`, один непрозорий матеріал без текстур. */
export function batchable(o) {
    if (!o.isMesh || o.isInstancedMesh || o.isSkinnedMesh || o.userData.f3dStock || o.userData.isPulse || o.userData.role === "status") {
        return false;
    }
    const m = o.material, g = o.geometry;
    if (!m || Array.isArray(m) || !(m.isMeshStandardMaterial || m.isMeshBasicMaterial) || !m.color) {
        return false;
    }
    if (m.transparent || m.depthWrite === false || m.alphaTest > 0 || m.wireframe || m.blending !== 1 || m.vertexColors || m.polygonOffset) {
        return false;
    }
    if (TEX.some((k) => m[k]) || o.renderOrder !== 0 || o.layers.mask !== 1 || o.frustumCulled === false) {
        return false;
    }
    const pos = g?.attributes?.position, nor = g?.attributes?.normal;
    if (!pos || !nor || pos.itemSize !== 3 || nor.itemSize !== 3 || (g.morphAttributes && Object.keys(g.morphAttributes).length)) {
        return false;
    }
    return g.drawRange.start === 0 && g.drawRange.count === Infinity;
}

function groupKey(o, cx, cz) {
    const m = o.material, e = m.emissive;
    return [
        m.type, m.side, m.roughness, m.metalness, m.flatShading ? 1 : 0, m.envMapIntensity, m.depthTest ? 1 : 0,
        o.castShadow ? 1 : 0, o.receiveShadow ? 1 : 0, e ? e.r + "," + e.g + "," + e.b + "," + m.emissiveIntensity : "-", cx, cz,
    ].join("|");
}

/**
 * @param {object} env { THREE, scene, cell } — `cell`: розмір клітинки плану, м. За замовчуванням 0 — без поділу: найменше
 *   draw-викликів (≈ 260 пакетів на всю модель проти ≈ 620 з клітинкою 40 м); клітинки лише трохи економлять трикутники
 *   на наближених видах (відсікання за пірамідою видимості), але множать виклики в загальному вигляді.
 */
export function createBatcher(env) {
    const { THREE, scene } = env;
    const cell = env.cell ?? 0;
    const batches = [];
    const recs = [];
    const recOf = new Map(); // проксі-меш -> запис
    const coldList = [];
    const dirty = new Set(); // пакети зі зміненими буферами (завантажити в GPU при flush)
    let coldDirty = true;
    let disposed = false;
    const inv = new THREE.Matrix4(), M = new THREE.Matrix4(), N = new THREE.Matrix3(), v = new THREE.Vector3();
    const sph = new THREE.Sphere();

    const hostOf = (mesh, root) => {
        for (let o = mesh.parent; o; o = o.parent) {
            if (o.userData?.layer && o.name.startsWith("LAYER_")) { return o; }
            if (o === root) { break; }
        }
        return root;
    };

    function buildBatch(host, list) {
        const rep = list[0].mesh;
        let nv = 0, ni = 0;
        for (const r of list) {
            const g = r.mesh.geometry;
            r.vn = g.attributes.position.count;
            r.in = g.index ? g.index.count : r.vn;
            nv += r.vn; ni += r.in;
        }
        const Idx = nv > MAX_U16 ? Uint32Array : Uint16Array;
        const pos = new Float32Array(nv * 3), nor = new Float32Array(nv * 3), col = new Float32Array(nv * 3), idx = new Idx(ni);
        host.updateWorldMatrix(true, false);
        inv.copy(host.matrixWorld).invert();
        let v0 = 0, i0 = 0;
        for (const r of list) {
            const mesh = r.mesh, g = mesh.geometry;
            M.multiplyMatrices(inv, mesh.matrixWorld);
            N.getNormalMatrix(M);
            const flip = M.determinant() < 0;
            const pa = g.attributes.position, na = g.attributes.normal, c = mesh.material.color;
            for (let i = 0; i < r.vn; i++) {
                v.set(pa.getX(i), pa.getY(i), pa.getZ(i)).applyMatrix4(M);
                const o = (v0 + i) * 3;
                pos[o] = v.x; pos[o + 1] = v.y; pos[o + 2] = v.z;
                v.set(na.getX(i), na.getY(i), na.getZ(i)).applyMatrix3(N).normalize();
                nor[o] = v.x; nor[o + 1] = v.y; nor[o + 2] = v.z;
                col[o] = c.r; col[o + 1] = c.g; col[o + 2] = c.b;
            }
            const ix = g.index;
            for (let i = 0; i < r.in; i += 3) {
                const a = ix ? ix.getX(i) : i, b = ix ? ix.getX(i + 1) : i + 1, d = ix ? ix.getX(i + 2) : i + 2;
                idx[i0 + i] = v0 + a;
                idx[i0 + i + 1] = v0 + (flip ? d : b);
                idx[i0 + i + 2] = v0 + (flip ? b : d);
            }
            r.v0 = v0; r.i0 = i0;
            v0 += r.vn; i0 += r.in;
        }
        const geom = new THREE.BufferGeometry();
        geom.setAttribute("position", new THREE.BufferAttribute(pos, 3));
        geom.setAttribute("normal", new THREE.BufferAttribute(nor, 3));
        geom.setAttribute("color", new THREE.BufferAttribute(col, 3));
        geom.setIndex(new THREE.BufferAttribute(idx, 1));
        geom.setDrawRange(0, ni);
        geom.computeBoundingBox();
        geom.computeBoundingSphere();
        const mat = rep.material.clone();
        mat.color.setRGB(1, 1, 1);
        mat.vertexColors = true;
        mat.name = "f3d_batch";
        const mesh = new THREE.Mesh(geom, mat);
        mesh.name = "F3D_BATCH";
        mesh.castShadow = rep.castShadow;
        mesh.receiveShadow = rep.receiveShadow;
        mesh.raycast = () => {}; // вибір — за проксі-мешами
        mesh.userData.f3dBatch = true;
        host.add(mesh);
        const b = { mesh, geom, mat, host, idx, orig: idx.slice(), col, recs: list, dirtyIdx: false, dirtyCol: false };
        for (const r of list) { r.b = b; r.cold = true; }
        batches.push(b);
    }

    /** Запакувати придатні меші частини `root` (вже додано в сцену). Повертає кількість запакованих мешів. */
    function add(root) {
        if (disposed) { return 0; }
        root.updateWorldMatrix(true, true);
        const groups = new Map();
        root.traverse((o) => {
            if (!batchable(o) || recOf.has(o)) { return; }
            const g = o.geometry;
            if (!g.boundingSphere) { g.computeBoundingSphere(); }
            sph.copy(g.boundingSphere).applyMatrix4(o.matrixWorld);
            const host = hostOf(o, root);
            const cx = cell > 0 ? Math.floor(sph.center.x / cell) : 0, cz = cell > 0 ? Math.floor(sph.center.z / cell) : 0;
            const key = host.uuid + "|" + groupKey(o, cx, cz);
            let gr = groups.get(key);
            if (!gr) { gr = { host, list: [] }; groups.set(key, gr); }
            const m = o.material, e = m.emissive;
            const r = {
                mesh: o, b: null, cold: false, base: o.matrixWorld.elements.slice(), v0: 0, vn: 0, i0: 0, in: 0,
                cr: m.color.r, cg: m.color.g, cb: m.color.b, op: m.opacity,
                er: e ? e.r : 0, eg: e ? e.g : 0, eb: e ? e.b : 0, ei: e ? m.emissiveIntensity : 0,
            };
            gr.list.push(r);
            recs.push(r);
            recOf.set(o, r);
        });
        let n = 0;
        for (const gr of groups.values()) { buildBatch(gr.host, gr.list); n += gr.list.length; }
        coldDirty = true;
        sync();
        return n;
    }

    function recolor(r, c) {
        const col = r.b.col;
        for (let i = r.v0 * 3, e = (r.v0 + r.vn) * 3; i < e; i += 3) { col[i] = c.r; col[i + 1] = c.g; col[i + 2] = c.b; }
        r.cr = c.r; r.cg = c.g; r.cb = c.b;
        r.b.dirtyCol = true;
        dirty.add(r.b);
    }
    /** Привести запис у відповідність до проксі; true, якщо проксі перейшов між пакетом і «сам». */
    function evalRec(r) {
        const mesh = r.mesh, m = mesh.material;
        let ok = m.visible !== false;
        if (ok) {
            for (let p = mesh; p !== r.b.host; p = p.parent) {
                if (!p || !p.visible) { ok = false; break; }
            }
        }
        if (ok) {
            const e = mesh.matrixWorld.elements, s = r.base;
            for (let i = 0; i < 16; i++) { if (e[i] !== s[i]) { ok = false; break; } }
        }
        const em = m.emissive;
        if (ok && (m.transparent || m.opacity !== r.op || (em && (em.r !== r.er || em.g !== r.eg || em.b !== r.eb || m.emissiveIntensity !== r.ei)))) {
            ok = false;
        }
        const c = m.color;
        if (c.r !== r.cr || c.g !== r.cg || c.b !== r.cb) { recolor(r, c); }
        if (ok === r.cold) { return false; }
        r.cold = ok;
        r.b.dirtyIdx = true;
        dirty.add(r.b);
        coldDirty = true;
        return true;
    }
    /** Індекси пакета — лише «холодні» проксі підряд (без вироджених трикутників); решта діапазону не малюється. */
    function compact(b) {
        let w = 0;
        for (const r of b.recs) {
            if (!r.cold) { continue; }
            b.idx.set(b.orig.subarray(r.i0, r.i0 + r.in), w);
            w += r.in;
        }
        b.geom.setDrawRange(0, w);
        b.geom.index.needsUpdate = true;
        b.mesh.visible = w > 0;
    }
    function flush() {
        for (const b of dirty) {
            if (b.dirtyIdx) { compact(b); b.dirtyIdx = false; }
            if (b.dirtyCol) { b.geom.attributes.color.needsUpdate = true; b.dirtyCol = false; }
        }
        dirty.clear();
    }

    /** Повний обхід усіх проксі (опитування, після stock_load/розкладки). true — склад пакетів змінився. */
    function sync() {
        if (disposed || !recs.length) { return false; }
        scene.updateMatrixWorld();
        let changed = false;
        for (const r of recs) { if (evalRec(r)) { changed = true; } }
        flush();
        return changed;
    }
    /** Лише піддерево `root` (paint, миготіння пожежі): без очікування опитування. */
    function touch(root) {
        if (disposed || !root || !recs.length) { return false; }
        root.updateWorldMatrix(true, true);
        let changed = false;
        root.traverse((o) => {
            const r = recOf.get(o);
            if (r && evalRec(r)) { changed = true; }
        });
        flush();
        return changed;
    }

    function rebuildCold() {
        coldList.length = 0;
        for (const r of recs) { if (r.cold) { coldList.push(r.mesh); } }
        coldDirty = false;
    }
    /** Сховати «холодні» проксі перед `renderer.render` (інакше вони малювались би поверх пакетів). */
    function beforeRender() {
        if (coldDirty) { rebuildCold(); }
        for (let i = 0; i < coldList.length; i++) { coldList[i].visible = false; }
    }
    function afterRender() {
        for (let i = 0; i < coldList.length; i++) { coldList[i].visible = true; }
    }
    /** Обгортка рендера: проксі ховаються лише на час виклику. */
    function render(fn) {
        beforeRender();
        try { return fn(); } finally { afterRender(); }
    }

    function stats() {
        let cold = 0;
        for (const r of recs) { if (r.cold) { cold++; } }
        return { batches: batches.length, eligible: recs.length, cold, solo: recs.length - cold };
    }
    function dispose() {
        disposed = true;
        for (const b of batches) {
            b.mesh.removeFromParent();
            b.geom.dispose();
            b.mat.dispose();
        }
        for (const r of recs) { r.mesh.visible = true; }
        batches.length = 0; recs.length = 0; recOf.clear(); coldList.length = 0; dirty.clear();
    }
    return { add, sync, touch, render, beforeRender, afterRender, stats, dispose, batches, isBatched: (mesh) => !!recOf.get(mesh)?.cold };
}
