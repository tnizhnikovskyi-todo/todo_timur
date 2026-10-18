// 3D-сцена редактора (порт 40_scene.js; three r160 з бандла переглядача, рендер на вимогу, один WebGLRenderer).
// Умовні моделі об'єктів без файла — `buildGenericModel` (W3, R-17); моделі варіантів — GLB із вкладень (API-10), завантажує app.js.
import { host } from "./host.js";
import { registries } from "./registry.js";
import { cellsOf, normalizeParams } from "./cells.js";
import { FRONT_ANGLE, TPL } from "./data.js";
import { polygonContains } from "./geometry.js";
import { newBlocks, pGeom, runLive, sGeom, slotDims } from "./live.js";
import { canEditLayer, lockHint, toastLock } from "./roles.js";
import { E, S, V, elevOf, isLayerVisible, layerOf, objKey, passportOf, recOfRef, selKeys, snapStep, snapV, variantOf } from "./state.js";
import { THREE } from "./three.js";
import { $, clamp, clone, fmt, h, rad, rnd, toast } from "./util.js";

const BODY = { other: "#9ba6b1" };
const UCOL = { electric: "#e0a030", air: "#3a8fd0", dust: "#6aa04a" };

function readColors() {
    const cs = getComputedStyle($("#app") || document.documentElement);
    const g = (n) => cs.getPropertyValue(n).trim() || "#888888";
    return {
        scene: g("--scene"),
        grid: g("--grid"),
        grid2: g("--grid2"),
        floor: g("--floor"),
        stroke: g("--stroke"),
        accent: g("--accent"),
        warn: g("--warn"),
        block: g("--block"),
        ink: g("--ink"),
        unsaved: "#12a5a0", // бірюзовий «не збережено» (N-05)
        hl: "#f2c200", // підсвітка результатів пошуку (F06-02)
    };
}

function initMats() {
    const C = V.col;
    const M = (V.mat = {});
    const T = (V.themed = []);
    const th = (m, k) => {
        T.push([m, k]);
        return m;
    };
    M.edge = th(new THREE.LineBasicMaterial({ color: C.stroke, transparent: true, opacity: 0.85 }), "stroke");
    M.edgeGhost = th(new THREE.LineBasicMaterial({ color: C.stroke, transparent: true, opacity: 0.22 }), "stroke");
    const dash = (k, o, ds, gs) =>
        th(new THREE.LineDashedMaterial({ color: C[k], dashSize: ds || 0.4, gapSize: gs || 0.22, transparent: true, opacity: o || 0.95 }), k);
    M.dash = { normal: dash("stroke", 0.85), sel: dash("accent"), warn: dash("warn"), block: dash("block"), unsaved: dash("unsaved") };
    M.dashGhost = dash("stroke", 0.28);
    M.svc = dash("accent", 0.7, 0.18, 0.16);
    M.sel = th(new THREE.LineBasicMaterial({ color: C.accent }), "accent");
    const fl = (k, o) => th(new THREE.MeshBasicMaterial({ color: C[k], transparent: true, opacity: o, depthWrite: false, side: THREE.DoubleSide }), k);
    M.fill = { sel: fl("accent", 0.2), warn: fl("warn", 0.34), block: fl("block", 0.38) };
    M.hit = new THREE.MeshBasicMaterial({ visible: false });
    M.gridMinor = th(new THREE.LineBasicMaterial({ color: C.grid, transparent: true, opacity: 0.75 }), "grid");
    M.gridMajor = th(new THREE.LineBasicMaterial({ color: C.grid2, transparent: true, opacity: 0.9 }), "grid2");
    M.floor = th(new THREE.MeshBasicMaterial({ color: C.floor }), "floor");
    M.bld = th(new THREE.LineBasicMaterial({ color: C.stroke }), "stroke");
    M.col = new THREE.MeshLambertMaterial({ color: "#8a96a3", transparent: true, opacity: 0.5 });
    M.ruler = th(new THREE.LineBasicMaterial({ color: C.accent, depthTest: false }), "accent");
    M.rulerPt = th(new THREE.MeshBasicMaterial({ color: C.accent, depthTest: false }), "accent");
    M.cell = new THREE.MeshLambertMaterial({ color: "#ffffff", transparent: true, opacity: 0.62, depthWrite: false });
    M.cellGhost = new THREE.MeshLambertMaterial({ color: "#ffffff", transparent: true, opacity: 0.16, depthWrite: false });
    M.pt = {};
    for (const k in UCOL) {
        M.pt[k] = new THREE.MeshLambertMaterial({ color: UCOL[k] });
    }
    M.under = th(new THREE.LineBasicMaterial({ color: C.accent, transparent: true, opacity: 0.8 }), "accent");
}
export function recolorMats() {
    V.col = readColors();
    for (const [m, k] of V.themed) {
        m.color.set(V.col[k]);
    }
    V.scene.background = new THREE.Color(V.col.scene);
}
function bodyMat(name, ghost) {
    const k = name + (ghost ? "_g" : "");
    let m = V.bodyMats.get(k);
    if (!m) {
        m = new THREE.MeshLambertMaterial({ color: BODY[name] || "#999999", transparent: !!ghost, opacity: ghost ? 0.3 : 1, depthWrite: !ghost });
        V.bodyMats.set(k, m);
    }
    return m;
}

/** Нульовий рендерер для тестів: ті самі події/промені, без малювання. */
function nullRenderer() {
    return {
        domElement: document.createElement("canvas"),
        setSize() {},
        setPixelRatio() {},
        // як справжній рендерер: оновлює світові матриці (від них залежать промені вибору й перетягування)
        render(scene, camera) {
            scene.updateMatrixWorld();
            if (camera.parent === null) {
                camera.updateMatrixWorld();
            }
        },
        dispose() {},
        forceContextLoss() {},
    };
}

export function initScene() {
    const host = $("#vp");
    let renderer = null;
    if (V.testMode) {
        renderer = nullRenderer();
    } else {
        try {
            renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
        } catch {
            host.append(h("div", { class: "nogl" }, "3D недоступне в цьому браузері. Форми й перевірки працюють, 3D-вид — ні."));
            return false;
        }
    }
    V.renderer = renderer;
    V.ok = true;
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    V.canvas = renderer.domElement;
    V.canvas.tabIndex = 0;
    V.canvas.setAttribute("aria-label", "3D-сцена площадки");
    host.append(V.canvas);
    V.scene = new THREE.Scene();
    V.col = readColors();
    V.scene.background = new THREE.Color(V.col.scene);
    initMats();
    const G = V.geo;
    G.box = new THREE.BoxGeometry(1, 1, 1);
    G.boxEdges = new THREE.EdgesGeometry(G.box);
    G.cyl = new THREE.CylinderGeometry(1, 1, 1, 18);
    G.plane = new THREE.PlaneGeometry(1, 1).rotateX(-Math.PI / 2);
    G.octa = new THREE.OctahedronGeometry(0.45);
    G.cone = new THREE.ConeGeometry(0.4, 0.9, 10);
    G.sph = new THREE.SphereGeometry(0.4, 12, 8);
    V.camera = new THREE.PerspectiveCamera(42, 1, 0.5, 4000);
    // r155+: інтенсивності світла більше не множаться на π — компенсуємо, щоб вигляд збігався з прототипом (r147)
    const lk = Number(THREE.REVISION) >= 155 ? Math.PI : 1;
    V.scene.add(new THREE.AmbientLight(0xffffff, 0.78 * lk));
    const dl = new THREE.DirectionalLight(0xffffff, 0.55 * lk);
    dl.position.set(40, 100, 60);
    V.scene.add(dl);
    V.world = new THREE.Group();
    V.scene.add(V.world);
    V.raycaster = new THREE.Raycaster();
    initPointer();
    V.controls = new THREE.OrbitControls(V.camera, V.canvas);
    V.controls.enableDamping = false;
    V.controls.screenSpacePanning = false;
    V.controls.maxPolarAngle = Math.PI * 0.495;
    V.controls.minDistance = 2;
    V.controls.maxDistance = 900;
    V.controls.addEventListener("change", requestRender);
    V.ro = new ResizeObserver(() => resizeScene());
    V.ro.observe(host);
    resizeScene();
    return true;
}

/** Звільняє все, що тримає сцена: рендерер, геометрії/матеріали/текстури, таймери, слухачі (onWillUnmount). */
export function disposeScene() {
    cancelAnimationFrame(V.raf);
    cancelAnimationFrame(V.hoverRaf);
    V.raf = 0;
    V.hoverRaf = 0;
    V.ro?.disconnect();
    V.controls?.dispose();
    for (const v of V.views.values()) {
        dispose(v.root);
    }
    for (const d of V.decor.values()) {
        disposeDecor(d.g);
    }
    for (const u of V.underlays.values()) {
        u.o.geometry.dispose();
        u.o.material.dispose();
    }
    if (V.buildingG) {
        const shared = Object.values(V.geo);
        V.buildingG.traverse((o) => {
            if (o.geometry && !shared.includes(o.geometry)) {
                o.geometry.dispose();
            }
        });
    }
    for (const c of V.labelCache.values()) {
        c.tex.dispose();
    }
    for (const m of V.bodyMats.values()) {
        m.dispose();
    }
    for (const g of Object.values(V.geo)) {
        g.dispose?.();
    }
    for (const m of Object.values(V.mat)) {
        if (m && m.dispose) {
            m.dispose();
        } else if (m && typeof m === "object") {
            Object.values(m).forEach((x) => x.dispose?.());
        }
    }
    V.renderer?.dispose();
    V.renderer?.forceContextLoss?.();
    V.ok = false;
}

export function resizeScene() {
    if (!V.ok) {
        return;
    }
    const host = $("#vp");
    const w = host.clientWidth;
    const hh = host.clientHeight;
    if (w < 2 || hh < 2) {
        return;
    }
    V.renderer.setSize(w, hh, false);
    V.camera.aspect = w / hh;
    V.camera.updateProjectionMatrix();
    requestRender();
}
export function requestRender() {
    if (V.ok && !V.raf) {
        V.raf = requestAnimationFrame(() => {
            V.raf = 0;
            render();
        });
    }
}
function render() {
    if (!V.ok) {
        return;
    }
    const dist = V.camera.position.distanceTo(V.controls.target);
    const on = S.settings.labels;
    for (const l of V.labels) {
        l.s.visible = on && dist < l.max;
    }
    V.renderer.render(V.scene, V.camera);
    updateRulerLabel();
}
const P3 = (x, y, z) => new THREE.Vector3(x, z || 0, -y);

/* ===== камера ===== */
export function setView(kind) {
    if (!V.ok) {
        return;
    }
    V.camMode = kind;
    const b = S.site.building;
    const cx = b.length / 2;
    const cz = -b.width / 2;
    const tgt = new THREE.Vector3(cx, 0, cz);
    const dir = kind === "plan" ? new THREE.Vector3(0, 1, 0.0001) : new THREE.Vector3(-0.42, 0.72, 0.7).normalize();
    const pts = [];
    for (const x of [0, b.length]) {
        for (const y of [0, b.width]) {
            for (const z of [0, b.height]) {
                pts.push(new THREE.Vector3(x, z, -y));
            }
        }
    }
    V.camera.aspect = Math.max(0.2, ($("#vp").clientWidth || 800) / Math.max(1, $("#vp").clientHeight || 600));
    V.camera.updateProjectionMatrix();
    let d = Math.hypot(b.length, b.width) * 0.25;
    for (let i = 0; i < 80; i++) {
        V.camera.position.copy(tgt).addScaledVector(dir, d);
        V.camera.lookAt(tgt);
        V.camera.updateMatrixWorld();
        let ok = true;
        for (const p of pts) {
            const q = p.clone().project(V.camera);
            if (Math.abs(q.x) > 0.97 || Math.abs(q.y) > 0.92 || q.z > 1) {
                ok = false;
                break;
            }
        }
        if (ok) {
            break;
        }
        d *= 1.05;
    }
    // План: вид згори вирівняний по осях, тож обертання вимкнене; ліва кнопка (і один палець) панорамує, колесо масштабує
    const plan = kind === "plan";
    V.controls.enableRotate = !plan;
    V.controls.mouseButtons.LEFT = plan ? THREE.MOUSE.PAN : THREE.MOUSE.ROTATE;
    V.controls.touches.ONE = plan ? THREE.TOUCH.PAN : THREE.TOUCH.ROTATE;
    V.controls.target.copy(tgt);
    V.controls.update();
    requestRender();
}
export function focusOn(x, y, dist) {
    if (!V.ok) {
        return;
    }
    const el = V.controls.target.clone();
    const off = V.camera.position.clone().sub(el);
    const nt = P3(x, y, 0);
    if (dist) {
        off.setLength(dist);
    }
    V.controls.target.copy(nt);
    V.camera.position.copy(nt).add(off);
    V.controls.update();
    requestRender();
}
export function camTarget() {
    if (!V.ok) {
        return { x: S.site.building.length / 2, y: S.site.building.width / 2 };
    }
    const t = V.controls.target;
    return { x: t.x, y: -t.z };
}

/* ===== підписи ===== */
const FONT = '"Arial Narrow", "Roboto Condensed", system-ui, sans-serif';
function makeLabel(text, h0, max, color, flatW) {
    const col = color || V.col.stroke;
    const key = text + "|" + col + "|" + V.theme;
    let c = V.labelCache.get(key);
    if (!c) {
        const cv = document.createElement("canvas");
        const ctx = cv.getContext("2d");
        const fs = 34;
        ctx.font = `500 ${fs}px ${FONT}`;
        const w = Math.ceil(ctx.measureText(text).width) + 20;
        cv.width = w;
        cv.height = 50;
        ctx.font = `500 ${fs}px ${FONT}`;
        ctx.textBaseline = "middle";
        ctx.lineWidth = 6;
        ctx.strokeStyle = V.col.scene;
        ctx.lineJoin = "round";
        ctx.strokeText(text, 10, 27);
        ctx.fillStyle = col;
        ctx.fillText(text, 10, 27);
        const tex = new THREE.CanvasTexture(cv);
        if (THREE.SRGBColorSpace) {
            tex.colorSpace = THREE.SRGBColorSpace;
        }
        tex.minFilter = THREE.LinearFilter;
        tex.generateMipmaps = false;
        c = { tex, aspect: w / 50 };
        V.labelCache.set(key, c);
    }
    let sp;
    if (flatW) {
        // плоский підпис на підлозі (зони): читається з плану, не засмічує 3D
        if (h0 * c.aspect > flatW) {
            h0 = flatW / c.aspect;
        }
        sp = new THREE.Mesh(V.geo.plane, new THREE.MeshBasicMaterial({ map: c.tex, transparent: true, depthWrite: false }));
        sp.scale.set(h0 * c.aspect, 1, h0);
        sp.renderOrder = 1;
    } else {
        sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: c.tex, transparent: true, depthWrite: false }));
        sp.scale.set(h0 * c.aspect, h0, 1);
    }
    sp.userData.label = true;
    const rec = { s: sp, max: max || 120 };
    V.labels.push(rec);
    sp.userData.rec = rec;
    return sp;
}
function dropLabels(root) {
    root.traverse((o) => {
        if (o.userData.rec) {
            const i = V.labels.indexOf(o.userData.rec);
            if (i >= 0) {
                V.labels.splice(i, 1);
            }
            if (o.material) {
                o.material.dispose();
            }
        }
    });
}

/* ===== допоміжні будівники ===== */
function boxMesh(w, hh, d, x, y, z, mat) {
    const m = new THREE.Mesh(V.geo.box, mat);
    m.scale.set(w, hh, d);
    m.position.set(x, y, z);
    return m;
}
function boxEdge(w, hh, d, x, y, z, mat) {
    const e = new THREE.LineSegments(V.geo.boxEdges, mat);
    e.scale.set(w, hh, d);
    e.position.set(x, y, z);
    return e;
}
export function lineGeo(pts) {
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(pts, 3));
    return g;
}
export function dashRect(hx, hy, ox, oy, mat, y) {
    const g = lineGeo([-hx + ox, y, -(-hy + oy), hx + ox, y, -(-hy + oy), hx + ox, y, -(hy + oy), -hx + ox, y, -(hy + oy)]);
    const l = new THREE.LineLoop(g, mat);
    l.computeLineDistances();
    return l;
}
function planeMesh(w, d, x, y, z, mat) {
    const m = new THREE.Mesh(V.geo.plane, mat);
    m.scale.set(w, 1, d);
    m.position.set(x, y, z);
    return m;
}
function dispose(root) {
    root.traverse((o) => {
        if (o.userData.own && o.geometry) {
            o.geometry.dispose();
        }
        if (o.userData.inst) {
            o.dispose();
        }
    });
    (root.userData.mats || []).forEach((m) => m.dispose());
    dropLabels(root);
}

/* ===== тіло розміщення: модель варіанта (GLB) або умовна модель категорії (R-17) ===== */
const genericCategory = (cat) => (cat === "cabinet" ? "panel" : cat || "other");
export function variantBody(cat, v, norm, ghost) {
    const L = v.length / 1000;
    const W = v.width / 1000;
    const H = v.height / 1000;
    if (norm) {
        return modelBody(norm, L, H, W, ghost);
    }
    const ang = FRONT_ANGLE[v.front_side || "s"];
    const swap = ang === 90 || ang === 270;
    const g = new THREE.Group();
    const b = host.buildGenericModel(genericCategory(cat), { l: swap ? W : L, w: swap ? L : W, h: H }, THREE);
    if (ghost) {
        b.traverse((c) => {
            if (c.isMesh) {
                c.material = bodyMat("other", true);
            }
        });
    }
    b.rotation.y = rad(ang);
    g.add(b);
    g.add(boxEdge(L, H, W, 0, H / 2, 0, ghost ? V.mat.edgeGhost : V.mat.edge));
    return g;
}
/* нормалізована модель → група під габарити варіанта */
function modelBody(m, L, H, W, ghost) {
    const g = new THREE.Group();
    const o = m.obj.clone(true);
    const sz = m.size;
    o.scale.set(L / Math.max(sz.x, 1e-6), H / Math.max(sz.y, 1e-6), W / Math.max(sz.z, 1e-6));
    if (ghost) {
        o.traverse((c) => {
            if (c.isMesh) {
                c.material = bodyMat("other", true);
            }
        });
    }
    g.add(o);
    return g;
}

/* ===== вигляди розміщень ===== */
const isGhost = (ly) => ly.id !== S.ui.layer;
function variantSig(v, p) {
    return [v.length, v.width, v.height, v.service, v.front_side, v.anchor, p && p.category];
}
export function buildPlacementView(pl, opts) {
    opts = opts || {};
    const v = variantOf(pl.variant_id);
    const ly = layerOf(pl.layer_id);
    if (!v || !ly) {
        return null;
    }
    const p = passportOf(pl.variant_id);
    const g = pGeom(pl, v);
    const ghost = opts.ghost != null ? opts.ghost : isGhost(ly);
    const H = v.height / 1000;
    const root = new THREE.Group();
    root.userData.ref = { kind: "placement", id: pl.id };
    root.add(variantBody((p && p.category) || "other", v, V.models.get(v.id), ghost));
    const view = { key: "p:" + pl.id, root, kind: "placement", id: pl.id, g, H, ghost, layerId: ly.id };
    view.foot = dashRect(g.L / 2 + 0.06, g.W / 2 + 0.06, 0, 0, ghost ? V.mat.dashGhost : V.mat.dash.normal, 0.03);
    root.add(view.foot);
    if (g.svc && !ghost) {
        view.svc = dashRect(g.shx, g.shy, g.sox, g.soy, V.mat.svc, 0.025);
        root.add(view.svc);
    }
    view.fill = planeMesh(g.L + 0.7, g.W + 0.7, 0, 0.02, 0, V.mat.fill.sel);
    view.fill.visible = false;
    root.add(view.fill);
    view.sel = boxEdge(g.L * 1.03, H * 1.02, g.W * 1.03, 0, H / 2, 0, V.mat.sel);
    view.sel.visible = false;
    root.add(view.sel);
    const hit = boxMesh(g.L, Math.max(H, 0.4), g.W, 0, Math.max(H, 0.4) / 2, 0, V.mat.hit);
    hit.userData.ref = root.userData.ref;
    hit.userData.view = view;
    root.add(hit);
    view.hit = hit;
    if (!opts.noLabel) {
        const lb = makeLabel(pl.code || pl.name || "", 0.9, 70);
        lb.position.set(0, H + 0.7, 0);
        root.add(lb);
        view.label = lb;
    }
    poseView(view, pl, v);
    return view;
}
export function poseView(view, rec, v) {
    if (view.kind === "placement") {
        v = v || variantOf(rec.variant_id);
        const g = pGeom(rec, v);
        view.g = g;
        view.root.position.set(g.cx, elevOf(rec.layer_id), -g.cy);
    } else {
        view.root.position.set(rec.x, elevOf(rec.layer_id), -rec.y);
    }
    view.root.rotation.y = rad(rec.rotation || 0);
}

/* ===== вигляди місць-шаблонів ===== */
/** Каркас стелажа: відрізки [x1, y1, z1, x2, y2, z2…] у локальних осях місця (x вздовж довжини, y — глибина, z — висота). */
const frameOf = {
    pallet_rack(p, d, sg) {
        for (let b = 0; b <= p.bays; b++) {
            const x = -d.L / 2 + b * p.bay_width;
            for (const sy of [-d.W / 2, d.W / 2]) {
                sg([x, sy, 0], [x, sy, d.H]);
            }
            sg([x, -d.W / 2, d.H], [x, d.W / 2, d.H]);
        }
        for (let l = 1; l <= p.levels; l++) {
            for (const sy of [-d.W / 2, d.W / 2]) {
                sg([-d.L / 2, sy, l * p.level_height], [d.L / 2, sy, l * p.level_height]);
            }
        }
    },
    shelf(p, d, sg) {
        for (let b = 0; b <= p.sections; b++) {
            const x = -d.L / 2 + b * p.cell_w;
            for (const sy of [-d.W / 2, d.W / 2]) {
                sg([x, sy, 0], [x, sy, d.H]);
            }
        }
        for (let l = 0; l <= p.shelves; l++) {
            const z = l * p.cell_h + 0.05;
            for (const sy of [-d.W / 2, d.W / 2]) {
                sg([-d.L / 2, sy, z], [d.L / 2, sy, z]);
            }
        }
    },
    cantilever(p, d, sg) {
        const y0 = -d.W / 2 + 0.075;
        for (let b = 0; b <= p.arms; b++) {
            const x = -d.L / 2 + (b * d.L) / p.arms;
            sg([x, y0, 0], [x, y0, d.H]);
            for (let l = 1; l <= p.levels; l++) {
                sg([x, y0, l * p.level_height], [x, d.W / 2, l * p.level_height]);
            }
        }
    },
};
// Реєстр shapes (registry.js): ключ шаблону/типу місця → {frame(params, dims) → відрізки каркаса}. Нові форми типів місць (каталог
// типів, MERGE.md §4.2) додаються тут же; шаблон без запису в реєстрі малюється лише коробками комірок.
for (const [tpl, fn] of Object.entries(frameOf)) {
    registries.shapes.add(
        tpl,
        {
            frame(p, d) {
                const pts = [];
                fn(p, d, (a, b) => pts.push(a[0], a[2], -a[1], b[0], b[2], -b[1]));
                return pts;
            },
        },
        { force: true }
    );
}
function frameLines(s, d) {
    const shape = registries.shapes.get(s.template, null);
    return shape && shape.frame ? shape.frame(normalizeParams(s.template, s.params), d) : [];
}
function cellColor(c, s, ly, sel) {
    if (sel) {
        return new THREE.Color(V.col.accent);
    }
    if (S.hl && S.hl.codes.has(c.code)) {
        return new THREE.Color(V.col.hl); // результат пошуку «де лежить»
    }
    // Реєстр metrics: обраний показник (S.ui.metric) може дати колір комірки (теплові карти); немає значення — звичайний колір
    const metric = S.ui.metric ? registries.metrics.get(S.ui.metric, null) : null;
    const mc = metric && metric.color ? metric.color(c, s, ly) : null;
    if (mc) {
        return new THREE.Color(mc);
    }
    if (c.disabled) {
        return new THREE.Color("#8b8b8b");
    }
    const col = new THREE.Color(ly.color);
    if (c.ov) {
        col.lerp(new THREE.Color(V.col.warn), 0.5);
    }
    return col;
}
/** Частка площі будівлі, з якої зона вважається «на весь цех». */
const ZONE_HUGE = 0.1;
export function buildSlotView(s, opts) {
    opts = opts || {};
    const ly = layerOf(s.layer_id);
    if (!ly) {
        return null;
    }
    const ghost = opts.ghost != null ? opts.ghost : isGhost(ly);
    const d = slotDims(s);
    const g = sGeom(s);
    const root = new THREE.Group();
    root.userData.ref = { kind: "slot", id: s.id };
    const view = { key: "s:" + s.id, root, kind: "slot", id: s.id, g, H: d.H, ghost, layerId: ly.id, tpl: s.template };
    const edgeMat = ghost ? V.mat.edgeGhost : V.mat.edge;
    const mkHit = (hh) => {
        const hit = boxMesh(d.L, hh, d.W, 0, hh / 2, 0, V.mat.hit);
        hit.userData.ref = root.userData.ref;
        hit.userData.view = view;
        root.add(hit);
        view.hit = hit;
    };
    if (s.template === "zone") {
        const col = new THREE.Color(s.params.color || ly.color);
        // зона на весь цех (пожежні, інженерні, дахові шари) не має заливати верстати: чужі шари — лише контур, активний — ледь помітна заливка
        const B = S.site.building;
        const huge = d.L * d.W > ZONE_HUGE * B.length * B.width;
        const fm = new THREE.MeshBasicMaterial({
            color: col,
            transparent: true,
            opacity: ghost ? (huge ? 0 : 0.06) : huge ? 0.06 : clamp(ly.opacity * 0.55, 0.1, 0.5),
            depthWrite: false,
            side: THREE.DoubleSide,
        });
        root.userData.mats = [fm];
        if (fm.opacity > 0) {
            root.add(planeMesh(d.L, d.W, 0, 0.012, 0, fm));
        }
        const ol = new THREE.LineLoop(
            lineGeo([-d.L / 2, 0.016, d.W / 2, d.L / 2, 0.016, d.W / 2, d.L / 2, 0.016, -d.W / 2, -d.L / 2, 0.016, -d.W / 2]),
            new THREE.LineBasicMaterial({ color: col.clone().multiplyScalar(0.55), transparent: true, opacity: ghost ? 0.25 : 0.9 })
        );
        ol.userData.own = 1;
        root.userData.mats.push(ol.material);
        root.add(ol);
        mkHit(0.05);
        view.fillSel = planeMesh(d.L, d.W, 0, 0.02, 0, V.mat.fill.sel);
        view.fillSel.visible = false;
        root.add(view.fillSel);
        view.fill = view.fillSel;
        view.foot = null;
        const t = s.params.title || s.code_prefix;
        const lb = makeLabel(t, clamp(Math.min(d.W * 0.3, d.L * 0.2), 0.8, 2.4), 420, null, d.L * 0.92);
        lb.position.set(0, 0.03, 0);
        root.add(lb);
        view.label = lb;
    } else if (s.template === "machine_spot") {
        view.foot = dashRect(d.L / 2, d.W / 2, 0, 0, ghost ? V.mat.dashGhost : V.mat.dash.normal, 0.03);
        root.add(view.foot);
        if (g.shx != null && !ghost) {
            root.add(dashRect(g.shx, g.shy, g.sox, g.soy, V.mat.svc, 0.025));
        }
        view.fill = planeMesh(d.L, d.W, 0, 0.02, 0, V.mat.fill.sel);
        view.fill.visible = false;
        root.add(view.fill);
        mkHit(0.3);
        const lb = makeLabel(s.code_prefix, 0.8, 90);
        lb.position.set(0, 0.25, 0);
        root.add(lb);
        view.label = lb;
        view.sel = boxEdge(d.L, 0.3, d.W, 0, 0.15, 0, V.mat.sel);
        view.sel.visible = false;
        root.add(view.sel);
    } else {
        const cells = cellsOf(s);
        const im = new THREE.InstancedMesh(V.geo.box, ghost ? V.mat.cellGhost : V.mat.cell, Math.max(cells.length, 1));
        im.userData.inst = 1;
        im.count = cells.length;
        const m4 = new THREE.Matrix4();
        const q = new THREE.Quaternion();
        const sc = new THREE.Vector3();
        const ps = new THREE.Vector3();
        const stack = s.template === "floor_stack";
        cells.forEach((c, i) => {
            const hh = stack ? Math.min(c.h, 0.5) : c.h * 0.78;
            sc.set(c.l * 0.92, hh, c.w * 0.9);
            ps.set(c.lx, c.dz + (s.template === "shelf" ? 0.05 : 0) + hh / 2 + (stack ? 0.02 : 0.1), -c.ly);
            m4.compose(ps, q, sc);
            im.setMatrixAt(i, m4);
            im.setColorAt(i, cellColor(c, s, ly, false));
        });
        im.instanceMatrix.needsUpdate = true;
        if (im.instanceColor) {
            im.instanceColor.needsUpdate = true;
        }
        root.add(im);
        view.cells = im;
        view.cellList = cells;
        view.ly = ly;
        const fl = frameLines(s, d);
        if (fl.length) {
            const ls = new THREE.LineSegments(lineGeo(fl), edgeMat);
            ls.userData.own = 1;
            root.add(ls);
        }
        view.foot = dashRect(d.L / 2 + 0.06, d.W / 2 + 0.06, 0, 0, ghost ? V.mat.dashGhost : V.mat.dash.normal, 0.03);
        root.add(view.foot);
        view.fill = planeMesh(d.L + 0.7, d.W + 0.7, 0, 0.02, 0, V.mat.fill.sel);
        view.fill.visible = false;
        root.add(view.fill);
        mkHit(Math.max(d.H, 0.3));
        view.sel = boxEdge(d.L * 1.02, d.H * 1.02, d.W * 1.02, 0, d.H / 2, 0, V.mat.sel);
        view.sel.visible = false;
        root.add(view.sel);
        const lb = makeLabel(s.code_prefix, 1.1, 130);
        lb.position.set(0, d.H + 0.8, 0);
        root.add(lb);
        view.label = lb;
    }
    poseView(view, s);
    return view;
}
function colorCells(view, selCode) {
    if (!view.cells) {
        return;
    }
    const s = S.sIdx.get(view.id);
    if (!s) {
        return;
    }
    view.cellList.forEach((c, i) => view.cells.setColorAt(i, cellColor(c, s, view.ly, c.code === selCode)));
    if (view.cells.instanceColor) {
        view.cells.instanceColor.needsUpdate = true;
    }
    view.selCode = selCode;
}

/* ===== декор шарів: сітка, завіса відмітки, проходи, пожежні зони, точки мереж ===== */
function gridStepDisplay(step, span) {
    // крок відображення: крок шару, а для дуже густої сітки — грубіший (не більше ~160 ліній на сторону)
    let d = step;
    if (span / d > 160) {
        for (const k of [1, 2, 5, 10, 20]) {
            if (k <= d) {
                continue;
            }
            d = k;
            if (span / d <= 160) {
                break;
            }
        }
    }
    while (span / d > 160) {
        d *= 2;
    }
    return Math.max(d, step);
}
/** Габаритний прямокутник контуру шару (або будівлі). */
function boundsBox(ly) {
    const B = S.site.building;
    if (!ly.bounds || ly.bounds.length < 3) {
        return { x0: 0, y0: 0, x1: B.length, y1: B.width };
    }
    const xs = ly.bounds.map((p) => p[0]);
    const ys = ly.bounds.map((p) => p[1]);
    return { x0: Math.min(...xs), y0: Math.min(...ys), x1: Math.max(...xs), y1: Math.max(...ys) };
}
function buildDecor(ly) {
    const g = new THREE.Group();
    const own = [];
    const active = ly.id === S.ui.layer;
    const el = ly.elevation;
    const bp = boundsBox(ly);
    const add = (o, ownGeo) => {
        g.add(o);
        if (ownGeo) {
            o.userData.own = 1;
        }
        return o;
    };
    const col = new THREE.Color(ly.color);
    if (active) {
        const ds = gridStepDisplay(ly.grid_step || 1, Math.max(bp.x1 - bp.x0, bp.y1 - bp.y0));
        const mj = [];
        const mn = [];
        const y = el + 0.006;
        const nx = Math.floor((bp.x1 - bp.x0) / ds + 1e-6);
        const ny = Math.floor((bp.y1 - bp.y0) / ds + 1e-6);
        for (let i = 0; i <= nx; i++) {
            const x = bp.x0 + i * ds;
            (i % 5 === 0 ? mj : mn).push(x, y, -bp.y0, x, y, -(bp.y0 + ny * ds));
        }
        for (let j = 0; j <= ny; j++) {
            const yy = bp.y0 + j * ds;
            (j % 5 === 0 ? mj : mn).push(bp.x0, y, -yy, bp.x0 + nx * ds, y, -yy);
        }
        if (mn.length) {
            add(new THREE.LineSegments(lineGeo(mn), V.mat.gridMinor), 1);
        }
        if (mj.length) {
            add(new THREE.LineSegments(lineGeo(mj), V.mat.gridMajor), 1);
        }
    }
    const outline = (yv) => {
        const poly =
            ly.bounds && ly.bounds.length >= 3
                ? ly.bounds
                : [
                      [bp.x0, bp.y0],
                      [bp.x1, bp.y0],
                      [bp.x1, bp.y1],
                      [bp.x0, bp.y1],
                  ];
        return lineGeo(poly.flatMap(([x, y]) => [x, yv, -y]));
    };
    if (el > 0.01) {
        const vm = new THREE.MeshBasicMaterial({ color: col, transparent: true, opacity: active ? 0.06 : 0.015, depthWrite: false, side: THREE.DoubleSide });
        own.push(vm);
        g.add(planeMesh(bp.x1 - bp.x0, bp.y1 - bp.y0, (bp.x0 + bp.x1) / 2, el, -(bp.y0 + bp.y1) / 2, vm));
        const lm = new THREE.LineBasicMaterial({ color: col, transparent: true, opacity: active ? 0.9 : 0.45 });
        own.push(lm);
        add(new THREE.LineLoop(outline(el), lm), 1);
        const vl = [];
        for (const [x, y] of [
            [bp.x0, bp.y0],
            [bp.x1, bp.y0],
            [bp.x1, bp.y1],
            [bp.x0, bp.y1],
        ]) {
            vl.push(x, 0, -y, x, el, -y);
        }
        add(new THREE.LineSegments(lineGeo(vl), lm), 1);
    } else if (ly.bounds) {
        const lm = new THREE.LineDashedMaterial({ color: col, dashSize: 1, gapSize: 0.6 });
        own.push(lm);
        const ol = new THREE.LineLoop(outline(0.02), lm);
        ol.computeLineDistances();
        add(ol, 1);
    }
    const zone = (x0, y0, x1, y1, color, op, lab) => {
        const fm = new THREE.MeshBasicMaterial({ color, transparent: true, opacity: active ? op : op * 0.4, depthWrite: false, side: THREE.DoubleSide });
        own.push(fm);
        g.add(planeMesh(Math.abs(x1 - x0), Math.abs(y1 - y0), (x0 + x1) / 2, el + 0.018, -(y0 + y1) / 2, fm));
        const lm = new THREE.LineDashedMaterial({ color, dashSize: 0.4, gapSize: 0.25, transparent: true, opacity: active ? 0.9 : 0.35 });
        own.push(lm);
        const ol = new THREE.LineLoop(lineGeo([x0, el + 0.02, -y0, x1, el + 0.02, -y0, x1, el + 0.02, -y1, x0, el + 0.02, -y1]), lm);
        ol.computeLineDistances();
        add(ol, 1);
        if (lab && active) {
            const lb = makeLabel(lab, 0.7, 70, color);
            lb.position.set((x0 + x1) / 2, el + 0.4, -(y0 + y1) / 2);
            g.add(lb);
        }
    };
    for (const a of ly.aisles || []) {
        zone(a.x0, a.y0, a.x1, a.y1, "#2e9d8f", 0.16, a.name);
    }
    for (const f of ly.fire_paths || []) {
        zone(f.x0, f.y0, f.x1, f.y1, "#d6453d", f.kind === "exit" ? 0.2 : 0.18, f.name);
    }
    if ((ly.utilities || []).length) {
        const stems = [];
        for (const u of ly.utilities) {
            const geo = u.kind === "electric" || u.kind === "panel" ? V.geo.octa : u.kind === "air" ? V.geo.sph : V.geo.cone;
            const m = new THREE.Mesh(geo, V.mat.pt[u.kind] || V.mat.pt.electric);
            m.position.set(u.x, el + 0.1, -u.y);
            g.add(m);
            if (el > 0.5) {
                stems.push(u.x, 0, -u.y, u.x, el, -u.y);
            }
        }
        if (stems.length) {
            const sm = new THREE.LineBasicMaterial({ color: col, transparent: true, opacity: 0.25 });
            own.push(sm);
            add(new THREE.LineSegments(lineGeo(stems), sm), 1);
        }
    }
    g.userData.ownMats = own;
    return g;
}
function disposeDecor(g) {
    g.traverse((o) => {
        if (o.userData.own && o.geometry) {
            o.geometry.dispose();
        }
    });
    (g.userData.ownMats || []).forEach((m) => m.dispose());
    dropLabels(g);
}

/* ===== будівля ===== */
function buildBuilding() {
    const B = S.site.building;
    const g = new THREE.Group();
    g.add(planeMesh(B.length, B.width, B.length / 2, -0.01, -B.width / 2, V.mat.floor));
    const e = new THREE.LineSegments(V.geo.boxEdges, V.mat.bld);
    e.scale.set(B.length, B.height, B.width);
    e.position.set(B.length / 2, B.height / 2, -B.width / 2);
    g.add(e);
    const sx = S.site.column_grid.step_x;
    const sy = S.site.column_grid.step_y;
    if (sx > 1 && sy > 1) {
        const xs = [];
        const ys = [];
        for (let x = sx; x < B.length - 0.01; x += sx) {
            xs.push(x);
        }
        for (let y = sy; y < B.width - 0.01; y += sy) {
            ys.push(y);
        }
        const n = xs.length * ys.length;
        if (n > 0 && n < 2000) {
            const im = new THREE.InstancedMesh(V.geo.box, V.mat.col, n);
            const m4 = new THREE.Matrix4();
            let i = 0;
            for (const x of xs) {
                for (const y of ys) {
                    m4.compose(new THREE.Vector3(x, B.height / 2, -y), new THREE.Quaternion(), new THREE.Vector3(0.4, B.height, 0.4));
                    im.setMatrixAt(i++, m4);
                }
            }
            g.add(im);
        }
    }
    return g;
}
function syncStatic() {
    const B = S.site.building;
    const sig = JSON.stringify([B, S.site.column_grid, V.theme, S.site.id]);
    if (sig === V.staticSig) {
        return;
    }
    V.staticSig = sig;
    if (V.buildingG) {
        V.world.remove(V.buildingG);
        const shared = Object.values(V.geo);
        V.buildingG.traverse((o) => {
            if (o.geometry && !shared.includes(o.geometry)) {
                o.geometry.dispose();
            }
            if (o.isInstancedMesh) {
                o.dispose();
            }
        });
    }
    V.buildingG = buildBuilding();
    V.world.add(V.buildingG);
}

/* ===== синхронізація сцени зі станом ===== */
export function syncScene(force) {
    if (!V.ok) {
        return;
    }
    syncStatic();
    // декор
    const lseen = new Set();
    for (const ly of S.layers) {
        lseen.add(ly.id);
        const sig = JSON.stringify([ly.elevation, ly.grid_step, ly.bounds, ly.color, !isLayerVisible(ly), ly.aisles, ly.fire_paths, ly.utilities, ly.id === S.ui.layer, S.site.building, V.theme]);
        const cur = V.decor.get(ly.id);
        if (cur && cur.sig === sig && !force) {
            continue;
        }
        if (cur) {
            V.world.remove(cur.g);
            disposeDecor(cur.g);
        }
        if (!isLayerVisible(ly)) {
            V.decor.delete(ly.id);
            continue;
        }
        const g = buildDecor(ly);
        V.world.add(g);
        V.decor.set(ly.id, { g, sig });
    }
    for (const [id, d] of V.decor) {
        if (!lseen.has(id)) {
            V.world.remove(d.g);
            disposeDecor(d.g);
            V.decor.delete(id);
        }
    }
    // розміщення й місця
    const seen = new Set();
    for (const pl of S.placements) {
        const ly = layerOf(pl.layer_id);
        const v = variantOf(pl.variant_id);
        if (!ly || !v || !isLayerVisible(ly)) {
            continue;
        }
        const key = "p:" + pl.id;
        seen.add(key);
        const sig = JSON.stringify([pl.x, pl.y, pl.rotation, pl.variant_id, pl.layer_id, pl.code, variantSig(v, passportOf(pl.variant_id)), ly.elevation, isGhost(ly), V.theme, V.models.has(v.id)]);
        const cur = V.views.get(key);
        if (cur && cur.sig === sig && !force) {
            continue;
        }
        if (cur) {
            V.world.remove(cur.root);
            dispose(cur.root);
        }
        const view = buildPlacementView(pl);
        if (!view) {
            continue;
        }
        view.sig = sig;
        V.world.add(view.root);
        V.views.set(key, view);
    }
    for (const s of S.slots) {
        const ly = layerOf(s.layer_id);
        if (!ly || !isLayerVisible(ly)) {
            continue;
        }
        const key = "s:" + s.id;
        seen.add(key);
        const sig = JSON.stringify([s, ly.elevation, ly.color, ly.opacity, isGhost(ly), V.theme]);
        const cur = V.views.get(key);
        if (cur && cur.sig === sig && !force) {
            continue;
        }
        if (cur) {
            V.world.remove(cur.root);
            dispose(cur.root);
        }
        const view = buildSlotView(s);
        if (!view) {
            continue;
        }
        view.sig = sig;
        V.world.add(view.root);
        V.views.set(key, view);
    }
    for (const [k, v] of V.views) {
        if (!seen.has(k)) {
            V.world.remove(v.root);
            dispose(v.root);
            V.views.delete(k);
        }
    }
    V.pick = [];
    for (const v of V.views.values()) {
        if (v.hit) {
            V.pick.push(v.hit);
        }
    }
    syncUnderlays();
    updateVisual();
}
/** Підпис кольорового стану комірок: показник, підсвітка пошуку, залишки — зміна перефарбовує всі місця (F06, F07). */
const colorSig = () => `${S.ui.metric || ""}|${S.hl ? S.hl.rev || S.hl.codes.size : 0}|${S.stock ? S.stock.rev || 0 : 0}`;
/** Перефарбовує комірки всіх місць (після зміни показника, залишків чи підсвітки). */
export function recolorCells() {
    V.colorSig = null;
    updateVisual();
}
/* стан підсвічування: вибір (в т.ч. мультивиділення) + проблеми + «не збережено» */
export function updateVisual() {
    if (!V.ok) {
        return;
    }
    const keys = selKeys();
    const selKey = S.sel ? objKey(S.sel.kind, S.sel.id) : null;
    const sig = colorSig();
    const recolor = V.colorSig !== sig;
    V.colorSig = sig;
    for (const [key, v] of V.views) {
        const st = S.issues.byKey.get(key);
        const lvl = st ? st.level : "normal";
        const isSel = keys.has(key);
        const unsaved = S.unsaved.has(key);
        if (v.foot) {
            v.foot.material = v.ghost ? V.mat.dashGhost : lvl === "normal" && unsaved ? V.mat.dash.unsaved : V.mat.dash[lvl] || V.mat.dash.normal;
        }
        if (v.fill) {
            v.fill.visible = !v.ghost && (lvl !== "normal" || isSel);
            v.fill.material = lvl === "normal" ? V.mat.fill.sel : V.mat.fill[lvl];
        }
        if (v.sel) {
            v.sel.visible = isSel;
        }
        if (v.cells) {
            const want = key === selKey ? S.selCell || "" : "";
            if (recolor || (v.selCode || "") !== want) {
                colorCells(v, want || null);
            }
        }
    }
    requestRender();
}

/* ===== лінійка ===== */
export function rulerClear() {
    for (const o of V.ruler.objs) {
        V.world.remove(o);
        if (o.geometry && o.geometry !== V.geo.sph) {
            o.geometry.dispose();
        }
    }
    V.ruler.objs = [];
    V.ruler.pts = [];
    const rl = $("#rlabel");
    if (rl) {
        rl.hidden = true;
    }
    requestRender();
}
export function rulerPoint(pt) {
    const R = V.ruler;
    if (R.pts.length >= 2) {
        rulerClear();
    }
    R.pts.push(pt);
    const m = new THREE.Mesh(V.geo.sph, V.mat.rulerPt);
    m.position.set(pt.x, pt.z + 0.05, -pt.y);
    m.scale.setScalar(0.6);
    m.renderOrder = 10;
    V.world.add(m);
    R.objs.push(m);
    if (R.pts.length === 2) {
        const [a, b] = R.pts;
        const l = new THREE.Line(lineGeo([a.x, a.z + 0.06, -a.y, b.x, b.z + 0.06, -b.y]), V.mat.ruler);
        l.renderOrder = 10;
        V.world.add(l);
        R.objs.push(l);
        R.dist = Math.hypot(b.x - a.x, b.y - a.y);
        const rl = $("#rlabel");
        rl.textContent = fmt(R.dist, 2) + " м · Δx " + fmt(Math.abs(b.x - a.x), 2) + " · Δy " + fmt(Math.abs(b.y - a.y), 2);
        rl.hidden = false;
    }
    requestRender();
}
function updateRulerLabel() {
    const R = V.ruler;
    if (R.pts.length < 2) {
        return;
    }
    const a = R.pts[0];
    const b = R.pts[1];
    const mid = new THREE.Vector3((a.x + b.x) / 2, (a.z + b.z) / 2, -(a.y + b.y) / 2).project(V.camera);
    const w = V.canvas.clientWidth;
    const hh = V.canvas.clientHeight;
    const el = $("#rlabel");
    el.style.left = ((mid.x + 1) / 2) * w + "px";
    el.style.top = ((1 - mid.y) / 2) * hh + "px";
}

/* ===== підкладка DXF (дані — V.uldata, параметри — layer.underlay.params) ===== */
export function syncUnderlays() {
    for (const [id, cur] of V.underlays) {
        if (!layerOf(id)) {
            V.world.remove(cur.o);
            cur.o.geometry.dispose();
            cur.o.material.dispose();
            V.underlays.delete(id);
        }
    }
    for (const ly of S.layers) {
        const u = ly.underlay;
        const data = V.uldata.get(ly.id);
        const sig = u && data && u.status === "ready" ? JSON.stringify([u.params, ly.elevation, !isLayerVisible(ly), V.theme, data.n]) : "";
        const cur = V.underlays.get(ly.id);
        if (cur && cur.sig === sig) {
            continue;
        }
        if (cur) {
            V.world.remove(cur.o);
            cur.o.geometry.dispose();
            cur.o.material.dispose();
            V.underlays.delete(ly.id);
        }
        if (!sig || !isLayerVisible(ly)) {
            continue;
        }
        const p = u.params;
        const segs = data.segs;
        const k = (p.unit === "m" ? 1 : 0.001) * (p.scale || 1);
        const a = rad(p.rot_deg || 0);
        const c = Math.cos(a);
        const s = Math.sin(a);
        const pos = new Float32Array((segs.length / 2) * 3);
        const y0 = ly.elevation + 0.04;
        for (let i = 0, j = 0; i < segs.length; i += 2, j += 3) {
            const px = segs[i] * k;
            const py = segs[i + 1] * k;
            pos[j] = px * c - py * s + p.dx;
            pos[j + 1] = y0;
            pos[j + 2] = -(px * s + py * c + p.dy);
        }
        const geo = new THREE.BufferGeometry();
        geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
        const mat = V.mat.under.clone();
        mat.opacity = clamp(p.opacity == null ? 0.7 : p.opacity, 0.05, 1);
        const o = new THREE.LineSegments(geo, mat);
        o.renderOrder = 2;
        V.world.add(o);
        V.underlays.set(ly.id, { o, sig });
    }
    requestRender();
}
export function underlayVertex(layerId, wx, wy, maxD) {
    // найближча вершина підкладки у світових координатах
    const cur = V.underlays.get(layerId);
    if (!cur) {
        return null;
    }
    const p = cur.o.geometry.attributes.position.array;
    let best = null;
    let bd = maxD;
    for (let i = 0; i < p.length; i += 3) {
        const d = Math.hypot(p[i] - wx, -p[i + 2] - wy);
        if (d < bd) {
            bd = d;
            best = { x: p[i], y: -p[i + 2] };
        }
    }
    return best;
}

/* ===== вказівник: вибір, перетягування, режими ===== */
function ndc(e) {
    const r = V.canvas.getBoundingClientRect();
    return new THREE.Vector2(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
}
export function floorPoint(e, elev) {
    V.raycaster.setFromCamera(ndc(e), V.camera);
    const out = new THREE.Vector3();
    if (!V.raycaster.ray.intersectPlane(new THREE.Plane(new THREE.Vector3(0, 1, 0), -(elev || 0)), out)) {
        return null;
    }
    return { x: out.x, y: -out.z, z: elev || 0 };
}
/** Шари-накладки: будівля й інженерні мережі. Їхні об'єкти — оболонки, повітряні об'єми й траси, що перекривають цех. */
const OVERLAY_KINDS = ["building", "engineering"];
/**
 * Кандидати вибору під курсором, уже відфільтровані й відсортовані за пріоритетом:
 * 1) шар кандидата видимий; зони й об'єкти шарів-накладок (будівля, інженерні мережі) вибираються лише на активному шарі;
 * 2) активний шар → шар, який можна редагувати → решта;
 * 3) менший габарит (верстат перемагає зону чи штабель, що його містить) → розміщення перед місцем → ближче до камери.
 */
export function pickCandidates(e) {
    V.world.updateMatrixWorld(true); // матриці нових/переміщених видів оновлюються при рендері; клік може прийти раніше за кадр
    V.raycaster.setFromCamera(ndc(e), V.camera);
    const hits = V.raycaster.intersectObjects(V.pick, false);
    const seen = new Set();
    const out = [];
    for (const h0 of hits) {
        const ref = h0.object.userData.ref;
        const view = h0.object.userData.view;
        if (!ref || !view || seen.has(view.key)) {
            continue;
        }
        seen.add(view.key);
        const ly = layerOf(view.layerId);
        if (!ly || !isLayerVisible(ly)) {
            continue; // приховані шари не вибираються
        }
        const active = view.layerId === S.ui.layer;
        if (!active && (view.tpl === "zone" || OVERLAY_KINDS.includes(ly.kind))) {
            continue; // зони й накладки вибираються лише на активному шарі
        }
        const tier = active ? 0 : canEditLayer(ly) ? 1 : 2;
        out.push({ ref, view, hit: h0, tier, area: view.g.L * view.g.W, kind: view.kind === "placement" ? 0 : 1 });
    }
    out.sort((a, b) => a.tier - b.tier || a.area - b.area || a.kind - b.kind || a.hit.distance - b.hit.distance);
    return out;
}
function pickAt(e) {
    const best = pickCandidates(e)[0];
    return best ? { ref: best.ref, view: best.view, hit: best.hit } : null;
}
const rafLive = (() => {
    let f = 0;
    return () => {
        if (f) {
            return;
        }
        f = requestAnimationFrame(() => {
            f = 0;
            liveCheck();
        });
    };
})();

function initPointer() {
    const cv = V.canvas;
    const listeners = {
        pointerdown: onDown,
        pointermove: onMove,
        pointerup: onUp,
        pointercancel: onUp,
        pointerleave: () => E.hideTip?.(),
        contextmenu: (e) => e.preventDefault(),
        dragover: (e) => {
            if ([...e.dataTransfer.types].includes("text/f3d-variant")) {
                e.preventDefault();
                e.dataTransfer.dropEffect = "copy";
            }
        },
        drop: (e) => {
            const id = e.dataTransfer.getData("text/f3d-variant");
            if (!id) {
                return;
            }
            e.preventDefault();
            const ly = layerOf(S.ui.layer);
            const pt = floorPoint(e, ly ? ly.elevation : 0);
            if (pt) {
                E.addPlacementAt(id, pt.x, pt.y, true);
            }
        },
    };
    for (const [t, fn] of Object.entries(listeners)) {
        cv.addEventListener(t, fn); // canvas знищується разом зі сценою: окремо знімати слухачі не потрібно
    }
}
function onDown(e) {
    V.canvas.focus({ preventScroll: true });
    if (e.pointerType === "mouse" && e.button !== 0) {
        return;
    }
    const ly = layerOf(S.ui.layer);
    const elev = ly ? ly.elevation : 0;
    if (V.pickMode) {
        const pt = floorPoint(e, elev);
        if (pt) {
            E.pickModeClick(pt);
        }
        e.preventDefault();
        return;
    }
    if (V.ruler.on) {
        const pt = floorPoint(e, elev);
        if (pt) {
            pt.x = rnd(pt.x, 2);
            pt.y = rnd(pt.y, 2);
            rulerPoint(pt);
        }
        return;
    }
    if (V.placing) {
        V.placing.down = { x: e.clientX, y: e.clientY };
        V.controls.enabled = true;
        return;
    }
    const hit = pickAt(e);
    V.bg = null;
    const additive = e.ctrlKey || e.metaKey;
    if (e.shiftKey && V.camMode === "plan" && e.pointerType !== "touch") {
        startBox(e, hit, additive); // рамка виділення в 2D (F09-03): Shift — нове виділення, Shift+Ctrl — додати
        return;
    }
    if (!hit) {
        V.bg = { x: e.clientX, y: e.clientY };
        return;
    }
    if (additive) {
        E.toggleMulti(hit.ref); // Ctrl+клік: додати в мультивиділення чи прибрати (F09-02)
        return;
    }
    const inMulti = S.multi.length > 1 && S.multi.some((r) => r.kind === hit.ref.kind && r.id === hit.ref.id);
    if (inMulti) {
        S.sel = { kind: hit.ref.kind, id: hit.ref.id }; // основним стає натиснутий; решта лишається виділеною
    } else {
        E.selectObj(hit.ref);
    }
    if (hit.view.cells && !inMulti) {
        // клік по комірці стелажа вибирає її в списку
        const ci = V.raycaster.intersectObject(hit.view.cells, false)[0];
        if (ci && ci.instanceId != null && hit.view.cellList[ci.instanceId]) {
            S.selCell = hit.view.cellList[ci.instanceId].code;
            updateVisual();
            E.renderCellsBox();
            const tr = $("#cellsBox tr.sel");
            if (tr) {
                tr.scrollIntoView({ block: "nearest" });
            }
            E.cellPicked?.(hit.ref.id, S.selCell, e);
        }
    }
    const rec = recOfRef(hit.ref);
    if (!rec) {
        return;
    }
    const lyr = layerOf(rec.layer_id);
    if (!canEditLayer(lyr)) {
        if (S.app.mode === "edit") {
            toastLock(lyr);
        }
        return;
    }
    if (rec.locked) {
        toast("Складний контур зони редагується у формі Odoo.", "warn");
        return;
    }
    const pt = floorPoint(e, lyr.elevation);
    if (!pt) {
        return;
    }
    let group = null;
    if (inMulti) {
        group = [];
        for (const r of S.multi) {
            const rr = recOfRef(r);
            if (!rr || !canEditLayer(layerOf(rr.layer_id)) || rr.locked) {
                toast(rr && !canEditLayer(layerOf(rr.layer_id)) ? lockHint(layerOf(rr.layer_id)) : "Складний контур зони редагується у формі Odoo.", "warn");
                return;
            }
            group.push({ ref: r, rec: rr, key: objKey(r.kind, r.id), start: { x: rr.x, y: rr.y } });
        }
    }
    V.controls.enabled = false;
    try {
        V.canvas.setPointerCapture(e.pointerId);
    } catch {
        /* ок */
    }
    V.drag = { ref: hit.ref, rec, key: objKey(hit.ref.kind, hit.ref.id), start: { x: rec.x, y: rec.y }, pt0: pt, moved: false, sx: e.clientX, sy: e.clientY, before: S.issues, elev: lyr.elevation, group };
}
function onMove(e) {
    const ly = layerOf(S.ui.layer);
    const elev = ly ? ly.elevation : 0;
    const pp = floorPoint(e, V.drag ? V.drag.elev : elev);
    if (pp) {
        V.cursor = pp;
        E.updateStamp();
    }
    if (V.placing) {
        movePlacing(e);
        return;
    }
    if (V.box) {
        moveBox(e);
        return;
    }
    if (!V.drag && !V.hoverRaf) {
        const ex = { clientX: e.clientX, clientY: e.clientY };
        V.hoverRaf = requestAnimationFrame(() => {
            V.hoverRaf = 0;
            hoverAt(ex);
        });
    }
    const d = V.drag;
    if (!d) {
        return;
    }
    if (!d.moved && Math.hypot(e.clientX - d.sx, e.clientY - d.sy) < 4) {
        return;
    }
    d.moved = true;
    if (!pp) {
        return;
    }
    const st = e.altKey ? 0.01 : snapStep(d.rec);
    d.rec.x = snapV(d.start.x + (pp.x - d.pt0.x), st);
    d.rec.y = snapV(d.start.y + (pp.y - d.pt0.y), st);
    const view = V.views.get(d.key);
    if (view) {
        poseView(view, d.rec);
    }
    if (d.group) {
        // мультивиділення: усі зсуваються на ту саму дельту, що й натиснутий (взаємне положення зберігається)
        const ddx = d.rec.x - d.start.x;
        const ddy = d.rec.y - d.start.y;
        for (const it of d.group) {
            if (it.rec === d.rec) {
                continue;
            }
            it.rec.x = rnd(it.start.x + ddx, 4);
            it.rec.y = rnd(it.start.y + ddy, 4);
            const v2 = V.views.get(it.key);
            if (v2) {
                poseView(v2, it.rec);
            }
        }
    }
    rafLive();
}
function hoverAt(e) {
    if (!V.canvas || V.drag || V.box || V.placing || V.ruler.on || V.pickMode) {
        return;
    }
    const hit = pickAt(e);
    let cell = null;
    if (hit && hit.view.cells) {
        const ci = V.raycaster.intersectObject(hit.view.cells, false)[0];
        cell = ci && ci.instanceId != null ? hit.view.cellList[ci.instanceId] || null : null;
    }
    const key = hit ? objKey(hit.ref.kind, hit.ref.id) : null;
    const hk = key ? key + "|" + (cell ? cell.code : "") : null;
    if (hk === V.hoverKey) {
        return;
    }
    V.hoverKey = hk;
    const rec = hit && recOfRef(hit.ref);
    V.canvas.style.cursor = hit ? (canEditLayer(layerOf(rec.layer_id)) ? "move" : "pointer") : "";
    const el = $("#hoverName");
    if (el) {
        el.textContent = rec ? (rec.code || rec.code_prefix) + (rec.name ? " · " + rec.name : rec.params && rec.params.title ? " · " + rec.params.title : "") : "—";
    }
    if (rec) {
        E.showTip?.({ x: e.clientX, y: e.clientY, rec, kind: hit.ref.kind, cell });
    } else {
        E.hideTip?.();
    }
}
function onUp(e) {
    try {
        V.canvas.releasePointerCapture(e.pointerId);
    } catch {
        /* ок */
    }
    if (V.placing && V.placing.down) {
        const d0 = V.placing.down;
        V.placing.down = null;
        if (Math.hypot(e.clientX - d0.x, e.clientY - d0.y) < 5) {
            movePlacing(e);
            placeClick(e.shiftKey);
        }
        return;
    }
    if (V.box) {
        finishBox(e);
        return;
    }
    const d = V.drag;
    V.drag = null;
    V.controls.enabled = true;
    if (V.bg) {
        const b = V.bg;
        V.bg = null;
        if (Math.hypot(e.clientX - b.x, e.clientY - b.y) < 4) {
            E.selectObj(null);
        }
        return;
    }
    if (!d || !d.moved) {
        return;
    }
    finishMove(d);
}
function liveCheck() {
    S.issues = runLive();
    updateVisual();
    E.syncPropsValues();
    E.renderChecksBlock();
}
/** Завершення перетягування: нова заборона → об'єкт (чи вся група) повертається; інакше позиція (прив'язка до місця) і запис у чергу. */
function finishMove(d) {
    const items = d.group || [d];
    const after = runLive();
    const nb = items.flatMap((it) => newBlocks(d.before, after, it.key));
    if (nb.length) {
        for (const it of items) {
            it.rec.x = it.start.x;
            it.rec.y = it.start.y;
            const view = V.views.get(it.key);
            if (view) {
                poseView(view, it.rec);
            }
        }
        S.issues = runLive();
        updateVisual();
        E.syncPropsValues();
        E.renderChecksBlock();
        toast("Заблоковано: " + nb[0].msg + (items.length > 1 ? ". Групу повернуто на місце." : ". Об’єкт повернуто на місце."), "err");
        return;
    }
    for (const it of items) {
        if (it.ref.kind === "placement") {
            assignSlot(it.rec);
        }
    }
    if (items.some((it) => it.start.x !== it.rec.x || it.start.y !== it.rec.y)) {
        E.commit({});
    } else {
        S.issues = after;
        updateVisual();
    }
    const first = items.map((it) => S.issues.byKey.get(it.key)).find((st) => st && st.level !== "block");
    if (first) {
        toast(first.items[0].msg, "warn");
    }
}

/* ===== рамка виділення (F09-03): Shift+протягнути в 2D ===== */
function startBox(e, hit, add) {
    V.box = { x0: e.clientX, y0: e.clientY, x1: e.clientX, y1: e.clientY, add, moved: false, hit };
    V.controls.enabled = false;
    try {
        V.canvas.setPointerCapture(e.pointerId);
    } catch {
        /* ок */
    }
}
function moveBox(e) {
    const b = V.box;
    b.x1 = e.clientX;
    b.y1 = e.clientY;
    if (!b.moved && Math.hypot(b.x1 - b.x0, b.y1 - b.y0) < 5) {
        return;
    }
    b.moved = true;
    if (!b.el) {
        b.el = h("div", { class: "s3-box", style: { position: "absolute", pointerEvents: "none", border: "1px dashed var(--accent)", background: "color-mix(in srgb, var(--accent) 14%, transparent)", zIndex: "3" } });
        $("#vp").append(b.el);
    }
    const r = $("#vp").getBoundingClientRect();
    Object.assign(b.el.style, { left: Math.min(b.x0, b.x1) - r.left + "px", top: Math.min(b.y0, b.y1) - r.top + "px", width: Math.abs(b.x1 - b.x0) + "px", height: Math.abs(b.y1 - b.y0) + "px" });
}
/** Об'єкти активного шару, що цілком у прямокутнику (екранні координати client). */
export function refsInRect(rect) {
    const cv = V.canvas.getBoundingClientRect();
    const out = [];
    const q = new THREE.Vector3();
    for (const v of V.views.values()) {
        if (v.layerId !== S.ui.layer || !v.g || !v.g.poly) {
            continue;
        }
        const ly = layerOf(v.layerId);
        if (!ly || !isLayerVisible(ly) || OVERLAY_KINDS.includes(ly.kind) || v.tpl === "building") {
            continue;
        }
        const el = ly.elevation || 0;
        const inside = v.g.poly.every(([px, py]) => {
            q.set(px, el, -py).project(V.camera);
            const cx = cv.left + ((q.x + 1) / 2) * cv.width;
            const cy = cv.top + ((1 - q.y) / 2) * cv.height;
            return cx >= rect.x0 && cx <= rect.x1 && cy >= rect.y0 && cy <= rect.y1;
        });
        if (inside) {
            out.push({ kind: v.kind, id: v.id });
        }
    }
    return out;
}
function finishBox(e) {
    const b = V.box;
    V.box = null;
    V.controls.enabled = true;
    if (b.el) {
        b.el.remove();
    }
    if (!b.moved) {
        // Shift+клік без протягування: як звичайний клік
        if (b.hit) {
            if (b.add) {
                E.toggleMulti(b.hit.ref);
            } else {
                E.selectObj(b.hit.ref);
            }
        } else if (!b.add) {
            E.selectObj(null);
        }
        return;
    }
    const rect = { x0: Math.min(b.x0, b.x1), y0: Math.min(b.y0, b.y1), x1: Math.max(b.x0, b.x1), y1: Math.max(b.y0, b.y1) };
    E.boxSelect(refsInRect(rect), b.add);
}
/** Місце під верстат, у яке потрапив центр розміщення. */
export function assignSlot(pl) {
    const v = variantOf(pl.variant_id);
    if (!v) {
        return;
    }
    const g = pGeom(pl, v);
    let found = null;
    for (const s of S.slots) {
        if (s.template === "machine_spot" && s.layer_id === pl.layer_id && polygonContains(sGeom(s).poly, [g.cx, g.cy], 1e-6)) {
            found = s;
        }
    }
    pl.slot_id = found ? found.id : null;
}

/* режим розміщення (ghost) */
export function startPlacing(spec) {
    cancelModes();
    const ly = layerOf(S.ui.layer);
    if (!ly) {
        return;
    }
    if (!canEditLayer(ly)) {
        toastLock(ly);
        return;
    }
    const c = camTarget();
    let rec;
    if (spec.kind === "placement") {
        const v = variantOf(spec.variantId);
        if (!v) {
            return;
        }
        rec = { id: "tmp", layer_id: ly.id, variant_id: v.id, slot_id: null, cell_code: null, x: snapV(c.x, ly.grid_step), y: snapV(c.y, ly.grid_step), rotation: 0, code: "", name: v.name };
    } else {
        if (!ly.slot_types.includes(spec.template)) {
            toast(`Шар «${ly.name}» не допускає шаблон «${TPL[spec.template].name}»`, "warn");
            return;
        }
        rec = { id: "tmp", layer_id: ly.id, template: spec.template, code_prefix: spec.prefix, x: snapV(c.x, ly.grid_step), y: snapV(c.y, ly.grid_step), rotation: 0, params: clone(spec.params), overrides: {} };
    }
    const view = rec.template ? buildSlotView(rec, { ghost: false }) : buildPlacementView(rec, { ghost: false, noLabel: true });
    if (!view) {
        return;
    }
    V.world.add(view.root);
    V.placing = { spec, rec, view, kind: spec.kind };
    V.canvas.style.cursor = "copy";
    V.placing.hint = toast("Клацніть на сцені, щоб поставити. Shift — поставити кілька, Esc — скасувати.");
    liveGhost();
    requestRender();
    E.renderVTools();
}
function movePlacing(e) {
    const P = V.placing;
    if (!P) {
        return;
    }
    const ly = layerOf(P.rec.layer_id);
    const pt = floorPoint(e, ly.elevation);
    if (!pt) {
        return;
    }
    const st = e.altKey ? 0.01 : ly.grid_step || 0.5;
    P.rec.x = snapV(pt.x, st);
    P.rec.y = snapV(pt.y, st);
    poseView(P.view, P.rec);
    liveGhost();
}
function liveGhost() {
    const P = V.placing;
    if (!P) {
        return;
    }
    const isSlot = !!P.rec.template;
    const arr = isSlot ? S.slots : S.placements;
    const idx = isSlot ? S.sIdx : S.pIdx;
    arr.push(P.rec);
    idx.set("tmp", P.rec);
    const res = runLive();
    arr.pop();
    idx.delete("tmp");
    const key = (isSlot ? "s:" : "p:") + "tmp";
    const st = res.byKey.get(key);
    const lvl = st ? st.level : "normal";
    P.lvl = lvl;
    P.issues = st ? st.items : [];
    const v = P.view;
    if (v.foot) {
        v.foot.material = V.mat.dash[lvl] || V.mat.dash.normal;
    }
    if (v.fill) {
        v.fill.visible = true;
        v.fill.material = lvl === "normal" ? V.mat.fill.sel : V.mat.fill[lvl];
    }
    requestRender();
}
function placeClick(keep) {
    const P = V.placing;
    if (!P) {
        return;
    }
    if (P.lvl === "block") {
        toast("Заблоковано: " + P.issues.find((i) => i.level === "block").msg, "err");
        return;
    }
    if (P.kind === "placement") {
        E.addPlacementAt(P.spec.variantId, P.rec.x, P.rec.y, false);
    } else {
        E.addSlotAt(P.spec, P.rec.x, P.rec.y);
    }
    if (!keep) {
        cancelModes();
    }
}
export function cancelModes() {
    if (V.placing) {
        if (V.placing.hint) {
            V.placing.hint.remove();
        }
        V.world.remove(V.placing.view.root);
        dispose(V.placing.view.root);
        V.placing = null;
        if (V.canvas) {
            V.canvas.style.cursor = "";
        }
    }
    if (V.ruler.on) {
        V.ruler.on = false;
        rulerClear();
    }
    if (V.pickMode) {
        V.pickMode = null;
    }
    requestRender();
    E.renderVTools?.();
}

Object.assign(E, {
    requestRender,
    setView,
    focusOn,
    camTarget,
    syncScene,
    updateVisual,
    recolorCells,
    rulerClear,
    rulerPoint,
    syncUnderlays,
    underlayVertex,
    startPlacing,
    cancelModes,
    assignSlot,
    initScene,
    disposeScene,
    resizeScene,
    recolorMats,
    floorPoint,
    poseView,
    buildPlacementView,
    buildSlotView,
});
