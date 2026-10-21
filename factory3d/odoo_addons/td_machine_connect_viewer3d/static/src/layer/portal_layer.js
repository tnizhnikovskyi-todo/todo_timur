/** @odoo-module **/
// R-31: розширення «Переглядача» (R-26, VX-03/VX-04/VX-05) — портальний склад плит наживо: стоси під порталом за реальною
// кількістю листів (висота = листи × товщина, підпис матеріалу), портал, що їде до стосу, бере лист і везе до верстата
// розкрою (рух за часом завдань, без телепортів), блоки в картках стосу, порталу й верстата-цілі.
// Дані — `equipment["GANTRY-1"].portal` і `locations[PLT-*].portal` (провайдер `td_machine_connect`); без них (старий
// сервер, портала немає) розширення неактивне й запечена сцена не чіпається. Ядро `core.js` не змінювалось.
// Час: у «живому» режимі — години сервера (`portal.now`), у «Потоці зміни» — `api.simMinutes()` ядра (VX-08); зміну часу ловить
// підписка `api.onSimTime`, кадр просимо `api.invalidate()` — без читання DOM повзунка й без подій у корені в'ювера.
// УВАГА (rjsmin): без вкладених шаблонних літералів у `${...}` — рядки склеєно конкатенацією.
import { registerViewerExtension } from "@td_viewer3d/viewer/core";
import {
    CYCLE_S, GANTRY, activeJobAt, carrying, decorColor, machineCardHtml, poseAt, poseLapse, portalCardHtml, portalOf, shortName,
    stackCardHtml, stackNodeOf, stackQtyAt, tableSheetsAt, MIN_THICKNESS_MM,
} from "@td_machine_connect_viewer3d/layer/portal_model";

export const EXT_ID = "td_machine_connect_portal";
export const LAYER_NAME = "td_portal_layer";
const SHEET_T = 0.016; // м, товщина листа за умовчанням (за стосом: td_thickness_mm)
const SHEET_W = 2.8; // м, лист 2800 × 2070 (як запечені плити стосів)
const SHEET_D = 2.07;
const PALLET_H = 0.1;
const LAPSE_RATE = 8; // швидше за 8× реального часу — «прискорене» програвання (рух за власним темпом)
const LAPSE_CYCLE_MS = 6000; // повний цикл «верстат → стос → верстат» у прискореному програванні
const MAX_SPEED = 18; // м/с — межа швидкості візка (різка зміна цілі не телепортує, а прискорено їде)
const FEED_DX = 2.9; // м від краю верстата до центру листа на приймальному столі (лист 2,8 м лежить на столі, не вилазить за колію)
const TABLE_FALLBACK = 0.9; // м, верх столу, якщо його не видно променем зверху
const TABLE_MAX = 1.6; // м, вище — це не стіл, а конструкція верстата
const SAFE_MARGIN = 0.5; // м, запас над найвищим стосом і столом на безпечній висоті переїзду
const STATIC_PARTS = /^GANTRY-1_(5|6|7|8|9|10)$/; // запечені міст, візок, траверса й лист: замінюємо рухомими
const BAKED_PLATES = /^stack_\d+_\d+_(1|2)$/; // запечені плити стосу (висота «на момент збирання моделі»)
const DEFAULTS = {
    bridge: { sx: 16.7, sy: 0.75, sz: 1.8, y: 7.125 },
    mast: { sx: 0.4, sy: 4.4, sz: 0.4, top: 7.5, bottom: 3.1 },
    head: { sx: 0.5, sy: 0.3, sz: 0.5 },
    frame: { sx: 2.2, sy: 0.1, sz: 1.4 },
    home: { x: 34, z: -22 },
    up: 2.6,
};

const lerp = (a, b, k) => a + (b - a) * k;
const ease = (p) => p * p * (3 - 2 * p);
const clamp01 = (v) => Math.min(1, Math.max(0, v));

/** Хвилина «Потоку зміни» або `null` («зараз»): `api.simMinutes()` ядра (VX-08); старе ядро без неї — завжди живий режим. */
export function replayMinutes(api) {
    return typeof api.simMinutes === "function" ? api.simMinutes() : null;
}

function boxOf(T, obj) {
    return obj ? new T.Box3().setFromObject(obj) : null;
}

/**
 * Розділити геометрію запеченого меша за світовою висотою: трикутники, усі вершини яких вище `y`, і решта. Запечена
 * `GANTRY-1_6` — це верхня балка моста (y 6,7…7,5) разом із траверсою (плита 2,6 × 1,8 м на y 2,7…2,8) в одному меші: балка
 * мусить їхати з мостом, а траверса — з візком і рамою; раніше траверса лишалась у повітрі й виглядала плитою, що висить сама.
 */
export function splitByHeight(T, mesh, y) {
    const g = mesh.geometry;
    const pos = g.attributes.position;
    const idx = g.index;
    const tris = (idx ? idx.count : pos.count) / 3;
    const v = new T.Vector3();
    const hi = [];
    const lo = [];
    const at = (n) => (idx ? idx.getX(n) : n);
    const wy = (i) => v.fromBufferAttribute(pos, i).applyMatrix4(mesh.matrixWorld).y;
    for (let t = 0; t < tris; t++) {
        const a = at(t * 3);
        const b = at(t * 3 + 1);
        const c = at(t * 3 + 2);
        (Math.min(wy(a), wy(b), wy(c)) > y ? hi : lo).push(a, b, c);
    }
    const make = (list) => {
        const n = new T.BufferGeometry();
        for (const [k, attr] of Object.entries(g.attributes)) {
            n.setAttribute(k, attr); // атрибути спільні з запеченою геометрією: самі їх не звільняємо
        }
        n.setIndex(list);
        // межі лише за вершинами цієї частини (за атрибутом вони охопили б усю запечену геометрію)
        const box = new T.Box3();
        for (const i of list) {
            box.expandByPoint(v.fromBufferAttribute(pos, i));
        }
        n.boundingBox = box;
        n.boundingSphere = box.getBoundingSphere(new T.Sphere());
        return n;
    };
    return [make(hi), make(lo)];
}

function textTexture(T, color) {
    const canvas = document.createElement("canvas");
    canvas.width = 256;
    canvas.height = 96;
    const tex = new T.CanvasTexture(canvas);
    tex.colorSpace = T.SRGBColorSpace;
    tex.userData = { canvas, lines: null, color };
    return tex;
}

function paintLabel(tex, lines) {
    const key = lines.join("|");
    if (tex.userData.lines === key) {
        return;
    }
    tex.userData.lines = key;
    const ctx = tex.userData.canvas.getContext("2d");
    if (!ctx) {
        return;
    }
    ctx.clearRect(0, 0, 256, 96);
    ctx.fillStyle = "rgba(20,24,30,0.78)";
    ctx.beginPath();
    if (ctx.roundRect) {
        ctx.roundRect(4, 4, 248, 88, 14);
    } else {
        ctx.rect(4, 4, 248, 88);
    }
    ctx.fill();
    ctx.fillStyle = tex.userData.color;
    ctx.fillRect(4, 4, 12, 88);
    ctx.fillStyle = "#ffffff";
    ctx.textAlign = "left";
    ctx.textBaseline = "middle";
    ctx.font = "bold 28px sans-serif";
    ctx.fillText(lines[0], 26, 32, 216);
    ctx.font = "bold 26px sans-serif";
    ctx.fillStyle = "#f2c230";
    ctx.fillText(lines[1], 26, 68, 216);
    tex.needsUpdate = true;
}

/** Смугаста текстура боків стосу: один тайл — один лист (світле тіло, темна кромка знизу). */
function plateStripes(T) {
    const canvas = document.createElement("canvas");
    canvas.width = 8;
    canvas.height = 32;
    const ctx = canvas.getContext("2d");
    if (ctx) {
        ctx.fillStyle = "#ffffff";
        ctx.fillRect(0, 0, 8, 32);
        ctx.fillStyle = "#9aa0a6";
        ctx.fillRect(0, 26, 8, 6);
    }
    const tex = new T.CanvasTexture(canvas);
    tex.wrapS = tex.wrapT = T.RepeatWrapping;
    tex.colorSpace = T.SRGBColorSpace;
    return tex;
}

export class PortalExtension {
    constructor() {
        this.id = EXT_ID;
        this.states = new WeakMap(); // api.scene → стан шару
        this.THREE = null;
    }

    stateOf(api) {
        let st = this.states.get(api.scene);
        if (!st) {
            st = {
                group: null, stacks: new Map(), geo: null, carriage: null, hidden: new Set(), cur: null, raf: 0, last: 0, own: [],
                clock: { anchorSec: 0, anchorMs: 0, P: null, min: null, minMs: 0, rate: 0, changeMs: 0 },
                t: null, pose: null, override: null, off: null, tables: new Map(), travelY: 0, texStripe: null, geometry: null,
            };
            this.states.set(api.scene, st);
        }
        return st;
    }

    // ---- життєвий цикл ---------------------------------------------------------------------------------
    clear(api) {
        const st = this.stateOf(api);
        st.off?.();
        st.off = null;
        if (st.raf) {
            cancelAnimationFrame(st.raf);
            st.raf = 0;
        }
        for (const mesh of st.hidden) {
            mesh.visible = true;
        }
        st.hidden.clear();
        for (const item of st.own) {
            item.dispose?.(); // лише власні матеріали й текстури: матеріали запечених деталей спільні зі сценою
        }
        st.own = [];
        st.geometry?.dispose?.();
        st.geometry = null;
        st.group?.removeFromParent();
        st.group = null;
        st.stacks.clear();
        st.carriage = null;
        st.tables.clear();
        st.geo = null;
        st.cur = null;
    }

    disposeAll(api) {
        this.clear(api);
        this.states.delete(api.scene);
    }

    // розкладка змінилась / модель довантажилась: положення стосів і верстатів інше — геометрію беремо заново
    applyLayout(api) {
        this.sync(api, true);
    }

    // VX-03
    applyData(api) {
        this.sync(api, false);
    }

    sync(api, force) {
        const T = api.THREE;
        this.THREE = T;
        const st = this.stateOf(api);
        const P = portalOf(api.D);
        if (!P) {
            this.clear(api);
            return;
        }
        if (force && st.group) {
            this.clear(api);
        }
        if (!st.group) {
            this.build(api, st, T);
        }
        st.clock.P = P;
        if (!st.off && typeof api.onSimTime === "function") {
            st.off = api.onSimTime((min) => this.onSimTime(api, min)); // VX-08: зміна часу «Потоку зміни»
        }
        this.start(api, st);
        this.tick(api, performance.now(), true);
    }

    // ---- побудова сцени -------------------------------------------------------------------------------
    stackCodes(api) {
        const out = [];
        for (const code of Object.keys(api.D?.locations || {})) {
            if (code.startsWith("PLT-") && stackNodeOf(api.D, code) && api.items.get(code)) {
                out.push(code);
            }
        }
        return out;
    }

    resolveGeo(api, T) {
        api.scene.updateMatrixWorld(true); // матриці ще могли не оновитись (модель щойно довантажилась): міряємо за актуальними
        const geo = { stacks: new Map(), targets: new Map(), parts: {}, home: { ...DEFAULTS.home }, up: DEFAULTS.up, baked: false };
        const gantry = api.items.get(GANTRY);
        const byName = {};
        gantry?.traverse((o) => {
            if (o.isMesh && STATIC_PARTS.test(o.name)) {
                byName[+o.name.split("_").pop()] = o;
            }
        });
        const bb = (n) => boxOf(T, byName[n]);
        const [deck, girder, mast, head, frame, sheet] = [5, 6, 7, 8, 9, 10].map(bb);
        if (deck && girder && mast && head && frame) {
            geo.baked = true;
            const size = (b) => b.getSize(new T.Vector3());
            const ctr = (b) => b.getCenter(new T.Vector3());
            geo.home = { x: ctr(frame).x, z: ctr(frame).z };
            geo.up = frame.min.y;
            const part = (n, b) => ({ obj: byName[n], b, s: size(b), c: ctr(b), top: b.max.y, bottom: b.min.y });
            geo.parts = {
                deck: part(5, deck),
                girder: part(6, girder),
                mast: part(7, mast),
                head: part(8, head),
                frame: part(9, frame),
                sheet: sheet ? part(10, sheet) : null,
            };
            geo.reach = { x0: girder.min.x, x1: girder.max.x };
        }
        for (const code of this.stackCodes(api)) {
            const root = api.items.get(code);
            let plates = null;
            root.traverse((o) => {
                if (o.isMesh && /_1$/.test(o.name) && BAKED_PLATES.test(o.name)) {
                    plates = o;
                }
            });
            const b = boxOf(T, plates) || boxOf(T, root);
            const c = b.getCenter(new T.Vector3());
            const s = b.getSize(new T.Vector3());
            geo.stacks.set(code, { x: c.x, z: c.z, w: plates ? s.x : s.x * 0.96, d: plates ? s.z : s.z * 0.96, y0: plates ? b.min.y : b.min.y + PALLET_H });
        }
        return geo;
    }

    /**
     * Точка кладення листа на верстат-ціль: `{x, z, top}` — центр листа над приймальним столом пили (з боку порталу, у межах колії
     * моста) і верх опори там (промінь зверху вниз по меших верстата: стіл разом із запеченою пачкою на ньому); невідомий верстат — парковка.
     */
    targetPoint(api, st, code) {
        const geo = st.geo;
        let pt = geo.targets.get(code);
        if (!pt) {
            const root = code ? api.items.get(code) : null;
            if (!root) {
                return { ...geo.home, top: TABLE_FALLBACK };
            }
            const T = api.THREE;
            const b = boxOf(T, root);
            const x = Math.min(b.min.x + FEED_DX, geo.reach ? geo.reach.x1 - 0.1 : Infinity);
            const z = b.getCenter(new T.Vector3()).z;
            const meshes = [];
            root.traverse((o) => {
                if (o.isMesh && o.visible) {
                    meshes.push(o);
                }
            });
            // верх опори — медіана променів по площі листа: тонкі поручні й планки верстата на лист не впливають
            const ray = new T.Raycaster();
            const ys = [];
            for (const dx of [-0.8, 0, 0.8]) {
                for (const dz of [-0.6, 0, 0.6]) {
                    ray.set(new T.Vector3(x + dx, b.max.y + 2, z + dz), new T.Vector3(0, -1, 0));
                    const hit = ray.intersectObjects(meshes, false)[0];
                    if (hit && hit.point.y < TABLE_MAX) {
                        ys.push(hit.point.y);
                    }
                }
            }
            ys.sort((a, c) => a - c);
            pt = { x, z, top: ys.length ? ys[Math.floor(ys.length / 2)] : TABLE_FALLBACK };
            geo.targets.set(code, pt);
        }
        return pt;
    }

    /** Безпечна висота переїзду (низ рами з листом): вища за найвищий можливий стос і стіл + запас, не нижча за запечену. */
    travelY(api, st) {
        let top = 0;
        for (const [code, g] of st.geo.stacks) {
            const node = stackNodeOf(api.D, code);
            top = Math.max(top, g.y0 + ((node?.capacity || 60) * (node?.thickness || MIN_THICKNESS_MM)) / 1000);
        }
        for (const code of new Set((portalOf(api.D)?.jobs || []).map((j) => j.target).filter(Boolean))) {
            top = Math.max(top, this.targetPoint(api, st, code).top);
        }
        return Math.max(st.geo.up, top + SHEET_T + SAFE_MARGIN);
    }

    build(api, st, T) {
        st.geo = this.resolveGeo(api, T);
        const group = new T.Group();
        group.name = LAYER_NAME;
        group.userData = { portalLayer: true };
        st.group = group;
        st.geometry = new T.BoxGeometry(1, 1, 1);
        st.texStripe = plateStripes(T);
        st.own.push(st.texStripe);
        // запечені плити стосів і візок порталу ховаємо: їх замінюють стоси за даними й рухомий візок
        for (const code of st.geo.stacks.keys()) {
            api.items.get(code).traverse((o) => {
                if (o.isMesh && BAKED_PLATES.test(o.name)) {
                    o.visible = false;
                    st.hidden.add(o);
                }
            });
        }
        if (st.geo.baked) {
            api.items.get(GANTRY).traverse((o) => {
                if (o.isMesh && STATIC_PARTS.test(o.name)) {
                    o.visible = false;
                    st.hidden.add(o);
                }
            });
        }
        for (const [code, g] of st.geo.stacks) {
            st.stacks.set(code, this.makeStack(T, st, code, g));
            group.add(st.stacks.get(code).group);
        }
        st.carriage = this.makeCarriage(T, st);
        group.add(st.carriage.bridge);
        api.scene.add(group);
    }

    makeStack(T, st, code, g) {
        const grp = new T.Group();
        grp.name = "td_portal_stack_" + code;
        const side = new T.MeshStandardMaterial({ color: "#c9a46f", roughness: 0.7, metalness: 0.02, map: st.texStripe.clone() });
        side.map.needsUpdate = true;
        const top = new T.MeshStandardMaterial({ color: "#c9a46f", roughness: 0.6, metalness: 0.02 });
        st.own.push(side.map, side, top);
        const plates = new T.Mesh(st.geometry, [side, side, top, top, side, side]);
        plates.castShadow = true;
        plates.receiveShadow = true;
        plates.raycast = () => {}; // клік проходить до запеченого піддона стосу: вибирається сам стос
        const labelTex = textTexture(T, "#c9a46f");
        const labelMat = new T.SpriteMaterial({ map: labelTex, transparent: true, depthWrite: false });
        st.own.push(labelTex, labelMat);
        const label = new T.Sprite(labelMat);
        label.scale.set(2.3, 0.86, 1);
        label.renderOrder = 998;
        label.raycast = () => {};
        grp.add(plates, label);
        return { group: grp, plates, label, side, top, tex: labelTex, qty: -1, color: "", g };
    }

    makeCarriage(T, st) {
        const geo = st.geo;
        const home = geo.home;
        const own = (mat) => {
            st.own.push(mat);
            return mat;
        };
        const steel = () => own(new T.MeshStandardMaterial({ color: "#aab2ba", roughness: 0.6, metalness: 0.4 }));
        // запечену деталь повторюємо тією ж геометрією й світовою матрицею: у початковому положенні збігається з нею
        const baked = (key, fb) => {
            const p = geo.parts[key];
            let mesh;
            if (p) {
                mesh = new T.Mesh(p.obj.geometry, p.obj.material);
                mesh.matrixAutoUpdate = false;
                mesh.matrix.copy(p.obj.matrixWorld);
            } else {
                mesh = new T.Mesh(st.geometry, steel());
                mesh.scale.set(fb.sx, fb.sy, fb.sz);
                mesh.position.set(fb.x ?? home.x, fb.y, fb.z ?? home.z);
            }
            mesh.castShadow = true;
            mesh.raycast = () => {};
            return mesh;
        };
        const bridge = new T.Group();
        bridge.name = "td_portal_bridge";
        const trolley = new T.Group();
        trolley.name = "td_portal_trolley";
        const lift = new T.Group();
        lift.name = "td_portal_lift";
        const deck = baked("deck", { sx: DEFAULTS.bridge.sx, sy: 0.7, sz: 1.2, y: DEFAULTS.bridge.y + 0.2 });
        const gp = geo.parts.girder;
        let girder;
        let plate = null; // траверса: їде з візком і рамою, а не з мостом
        if (gp) {
            const [hi, lo] = splitByHeight(T, gp.obj, 4.5);
            const from = (g) => {
                const m = new T.Mesh(g, gp.obj.material);
                m.matrixAutoUpdate = false;
                m.matrix.copy(gp.obj.matrixWorld);
                m.castShadow = true;
                m.raycast = () => {};
                return m;
            };
            girder = from(hi);
            plate = from(lo);
            plate.name = "td_portal_traverse";
        } else {
            girder = baked("girder", { sx: DEFAULTS.bridge.sx, sy: DEFAULTS.bridge.sy, sz: DEFAULTS.bridge.sz, y: DEFAULTS.bridge.y });
        }
        const head = baked("head", { sx: DEFAULTS.head.sx, sy: DEFAULTS.head.sy, sz: DEFAULTS.head.sz, y: 2.95 });
        const frame = baked("frame", { sx: DEFAULTS.frame.sx, sy: DEFAULTS.frame.sy, sz: DEFAULTS.frame.sz, y: 2.65 });
        const mp = geo.parts.mast;
        const mast = new T.Mesh(st.geometry, mp ? mp.obj.material : steel());
        mast.scale.set(mp ? mp.s.x : DEFAULTS.mast.sx, 1, mp ? mp.s.z : DEFAULTS.mast.sz);
        mast.castShadow = true;
        mast.raycast = () => {};
        const up = geo.up; // низ вакуумної рами (присоски) у спокої
        const sheetMat = own(new T.MeshStandardMaterial({ color: "#eceae3", roughness: 0.6, metalness: 0.02 }));
        const sheet = new T.Mesh(st.geometry, sheetMat);
        sheet.scale.set(SHEET_W, SHEET_T, SHEET_D);
        sheet.position.set(home.x, up - SHEET_T / 2, home.z); // верх листа = низ рами; рухається разом з рамою (дочірній `lift`)
        sheet.castShadow = true;
        sheet.raycast = () => {};
        sheet.visible = false;
        sheet.userData.f3dAnimated = true; // ядро перемальовує сцену, поки візок несе лист (userData.f3dAnimated)
        lift.add(head, frame, sheet);
        if (plate) {
            lift.add(plate);
        }
        trolley.add(mast, lift);
        bridge.add(deck, girder, trolley);
        const rest = {
            mastX: mp ? mp.c.x : home.x,
            mastZ: mp ? mp.c.z : home.z,
            mastTop: mp ? mp.top : DEFAULTS.mast.top,
            mastBottom: mp ? mp.bottom : DEFAULTS.mast.bottom,
            up: geo.up,
        };
        return { bridge, trolley, lift, mast, sheet, rest };
    }

    // ---- час -------------------------------------------------------------------------------------------
    /** `{t, replay, lapse}` — секунди доби для моделі: у «Потоці зміни» повзунок, інакше години сервера, що йдуть вперед. */
    readClock(api, st, nowMs) {
        const c = st.clock;
        if (st.override) {
            return st.override;
        }
        const min = replayMinutes(api);
        if (min !== null) {
            const lapse = c.rate > LAPSE_RATE && nowMs - c.changeMs < 700;
            return { t: min * 60, replay: true, lapse };
        }
        const P = c.P;
        if (!P) {
            return { t: 0, replay: false, lapse: false };
        }
        if (c.anchorP !== P) {
            c.anchorP = P;
            c.anchorSec = P.now;
            c.anchorMs = nowMs;
        }
        return { t: c.anchorSec + (nowMs - c.anchorMs) / 1000, replay: false, lapse: false };
    }

    /**
     * Підписка `api.onSimTime` (VX-08): час «Потоку зміни» змінився (`min` — хвилина або `null`). Швидкість програвання — з кроку
     * між змінами: понад 8× реального часу — «прискорений» цикл (`poseLapse`); одиночний перескок повзунка (перша зміна
     * після живого режиму чи пауза) лишає точну позу. Сцену оновлюємо одразу, не чекаючи кадру.
     */
    onSimTime(api, min) {
        const st = this.stateOf(api);
        const c = st.clock;
        const now = performance.now();
        if (min === null) {
            c.min = null;
            c.rate = 0;
        } else {
            if (c.min !== null && min !== c.min) {
                c.rate = (Math.abs(min - c.min) * 60000) / Math.max(1, now - c.minMs);
                c.changeMs = now;
            } else if (c.min === null) {
                c.rate = 0;
                c.changeMs = now;
            }
            c.min = min;
            c.minMs = now;
        }
        this.tick(api, now, true);
    }

    /** Для тестів і автоматизації: зафіксувати час (`{t, lapse?}`), `null` — знову за повзунком/годинником. */
    setTime(api, over) {
        const st = this.stateOf(api);
        st.override = over ? { t: over.t, replay: true, lapse: !!over.lapse } : null;
        this.tick(api, performance.now(), true);
    }

    // ---- анімація ---------------------------------------------------------------------------------------
    start(api, st) {
        if (st.raf) {
            return;
        }
        const reduce = !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches; // без анімації: оновлення раз на секунду
        const loop = (ms) => {
            const root = api.labelsRoot;
            if (!root || !root.isConnected) {
                st.raf = 0; // сцену знищено разом із в'ювером
                return;
            }
            st.raf = requestAnimationFrame(loop);
            const now = ms || performance.now();
            if (reduce && now - (st.lastTick || 0) < 1000) {
                return;
            }
            st.lastTick = now;
            this.tick(api, now, false);
        };
        st.raf = requestAnimationFrame(loop);
    }

    poseFor(P, clock, nowMs) {
        if (clock.lapse) {
            return poseLapse(P, clock.t, (nowMs % LAPSE_CYCLE_MS) / LAPSE_CYCLE_MS);
        }
        return poseAt(P, clock.t, CYCLE_S);
    }

    tick(api, nowMs, force) {
        const st = this.stateOf(api);
        const P = portalOf(api.D);
        if (!st.group || !P) {
            return;
        }
        const clock = this.readClock(api, st, nowMs);
        const pose = this.poseFor(P, clock, nowMs);
        st.t = clock.t;
        st.pose = pose;
        const dt = Math.min(0.25, Math.max(0, (nowMs - (st.last || nowMs)) / 1000));
        st.last = nowMs;
        const moved = this.updateStacks(api, st, P, clock.t, pose) | this.updateCarriage(api, st, P, pose, dt, force);
        if (moved) {
            api.invalidate?.(); // ядро малює «за потребою» (VX-08): просимо кадр після зміни положень
        }
    }

    updateStacks(api, st, P, t, pose) {
        let changed = 0;
        const takenCode = carrying(pose) ? pose.stack : null;
        for (const [code, s] of st.stacks) {
            const node = stackNodeOf(api.D, code);
            if (!node) {
                s.group.visible = false;
                continue;
            }
            let qty = stackQtyAt(node, P, code, t);
            const total = qty;
            if (takenCode === code && qty > 0) {
                qty -= 1; // лист уже в «руках» порталу
            }
            const thick = (node.thickness || MIN_THICKNESS_MM) / 1000;
            const color = decorColor(node.product, node.name);
            const key = qty + "|" + total + "|" + thick + "|" + color + "|" + node.product;
            if (s.key === key) {
                continue;
            }
            s.key = key;
            changed = 1;
            const g = s.g;
            s.group.visible = qty > 0 || total > 0;
            const h = Math.max(qty * thick, 0.0001);
            s.plates.visible = qty > 0;
            s.plates.scale.set(g.w, h, g.d);
            s.plates.position.set(g.x, g.y0 + h / 2, g.z);
            s.side.color.set(color);
            s.top.color.set(color);
            s.side.map.repeat.set(1, Math.max(1, qty));
            s.tex.userData.color = color;
            const shown = Math.max(total, qty);
            paintLabel(s.tex, [shortName(node.name, node.product) || node.product || code, shown > 0 ? shown + " арк." : "порожньо"]);
            s.label.position.set(g.x, g.y0 + h + 0.55, g.z);
            s.label.visible = !!(node.product || shown);
        }
        return changed;
    }

    /** Лист на приймальному столі верстата `code` (мешів по одному на верстат, створюються за потребою). */
    tableMesh(T, st, code) {
        let m = st.tables.get(code);
        if (!m) {
            const mat = new T.MeshStandardMaterial({ color: "#eceae3", roughness: 0.6, metalness: 0.02 });
            st.own.push(mat);
            m = new T.Mesh(st.geometry, mat);
            m.castShadow = true;
            m.receiveShadow = true;
            m.raycast = () => {};
            m.name = "td_portal_table_sheet_" + code;
            m.visible = false;
            st.group.add(m);
            st.tables.set(code, m);
        }
        return m;
    }

    /** Висота (м) і розмір листа за вузлом стосу: товщина — `td_thickness_mm`, габарит — як у плит стосу. */
    sheetDims(api, st, stackCode) {
        const node = stackCode ? stackNodeOf(api.D, stackCode) : null;
        const g = stackCode ? st.geo.stacks.get(stackCode) : null;
        return { t: (node?.thickness || MIN_THICKNESS_MM) / 1000, w: g ? g.w : SHEET_W, d: g ? g.d : SHEET_D };
    }

    /**
     * Координати рами для пози: `{x, z, y, sheet}` — `y` — низ вакуумної рами. Лист є лише в двох станах: висить під рамою
     * (`sheet`) або лежить на опорі (верх стосу — частина стосу; стіл пили — `tableSheets`). Порожня рама їде на безпечній висоті.
     */
    coordsOf(api, st, pose) {
        const geo = st.geo;
        const home = geo.home;
        const upY = st.travelY;
        const point = (code) => (code ? this.targetPoint(api, st, code) : home);
        const mix = (a, b, e) => ({ x: lerp(a.x, b.x, e), z: lerp(a.z, b.z, e) });
        const f = pose.from || { target: null, k: 1 };
        const fromPt = mix(point(f.target), home, ease(f.k));
        const stack = pose.stack ? geo.stacks.get(pose.stack) : null;
        const table = pose.target ? point(pose.target) : null;
        const dims = this.sheetDims(api, st, pose.stack);
        const node = pose.stack ? stackNodeOf(api.D, pose.stack) : null;
        const topWith = stack ? stack.y0 + stackQtyAt(node, portalOf(api.D), pose.stack, st.t) * dims.t : 0; // верх стосу разом із листом, що беруть
        const p = pose.p ?? 0;
        const dip = (y) => (p < 0.5 ? lerp(upY, y, ease(p * 2)) : lerp(y, upY, ease((p - 0.5) * 2))); // вниз до опори й назад
        switch (pose.kind) {
            case "toStack":
                if (stack) {
                    return { ...mix(fromPt, stack, ease(p)), y: upY, sheet: false };
                }
                break;
            case "pick":
                if (stack) {
                    return { x: stack.x, z: stack.z, y: dip(topWith), sheet: p >= 0.5, dims };
                }
                break;
            case "toTarget":
                if (stack && table) {
                    return { ...mix(stack, table, ease(p)), y: upY, sheet: true, dims };
                }
                break;
            case "place":
                if (table) {
                    return { x: table.x, z: table.z, y: dip(table.top + dims.t), sheet: p < 0.5, dims };
                }
                break;
            default:
        }
        return { ...fromPt, y: upY, sheet: false };
    }

    updateCarriage(api, st, P, pose, dt, force) {
        const car = st.carriage;
        if (!car) {
            return 0;
        }
        st.travelY = this.travelY(api, st);
        const tgt = this.coordsOf(api, st, pose);
        let cur = st.cur;
        if (!cur || force === "snap") {
            cur = st.cur = { x: tgt.x, z: tgt.z, y: tgt.y };
        } else {
            // межа швидкості: плавний рух іде точно за позою, а різка зміна цілі (перемотка) — швидким, але не миттєвим проїздом
            const dx = tgt.x - cur.x;
            const dz = tgt.z - cur.z;
            const dy = tgt.y - cur.y;
            const dist = Math.hypot(dx, dz, dy);
            const maxStep = MAX_SPEED * dt;
            const k = dist > maxStep ? maxStep / dist : 1;
            cur.x += dx * k;
            cur.z += dz * k;
            cur.y += dy * k;
        }
        const tables = new Map(tableSheetsAt(P, st.t, pose).map((s) => [s.target, s]));
        const tableKey = [...tables.values()].map((s) => s.target + s.job).join("|");
        const moved = Math.abs(cur.x - (st.shown?.x ?? 1e9)) + Math.abs(cur.z - (st.shown?.z ?? 1e9)) + Math.abs(cur.y - (st.shown?.y ?? 1e9)) > 0.002;
        const sheetOn = tgt.sheet;
        if (!moved && st.shown?.sheet === sheetOn && st.shown?.job === pose.job && st.shown?.tables === tableKey) {
            return 0;
        }
        const home = st.geo.home;
        const r = car.rest;
        car.bridge.position.set(0, 0, cur.z - home.z);
        car.trolley.position.set(cur.x - home.x, 0, 0);
        const dy = cur.y - r.up;
        car.lift.position.y = dy;
        const mastBottom = r.mastBottom + dy;
        car.mast.scale.y = Math.max(0.2, r.mastTop - mastBottom);
        car.mast.position.set(r.mastX, (r.mastTop + mastBottom) / 2, r.mastZ);
        const job = (P.jobs || []).find((j) => j.id === pose.job);
        car.sheet.visible = sheetOn;
        if (sheetOn) {
            const d = tgt.dims;
            car.sheet.scale.set(d.w, d.t, d.d);
            car.sheet.position.set(home.x, r.up - d.t / 2, home.z); // верх листа = низ рами
            car.sheet.material.color.set(decorColor(job?.product, job?.name));
        }
        // листи на столах пил: лежать на опорі (верх столу) до моменту, коли пила їх забере
        for (const [code, m] of st.tables) {
            m.visible = tables.has(code);
        }
        for (const [code, s] of tables) {
            const m = this.tableMesh(api.THREE, st, code);
            const pt = this.targetPoint(api, st, code);
            const sj = (P.jobs || []).find((j) => j.id === s.job);
            const d = this.sheetDims(api, st, s.stack);
            m.scale.set(d.w, d.t, d.d);
            m.position.set(pt.x, pt.top + d.t / 2, pt.z); // низ листа = верх опори
            m.material.color.set(decorColor(sj?.product, sj?.name));
            m.visible = true;
        }
        st.shown = { x: cur.x, z: cur.z, y: cur.y, sheet: sheetOn, job: pose.job, tables: tableKey };
        return 1;
    }

    // VX-04
    cardBlocks(code, D, api) {
        const st = api ? this.stateOf(api) : null;
        const P = portalOf(D);
        if (!P) {
            return [];
        }
        const m = api ? replayMinutes(api) : null; // картку малюють до `tick` підписки: час беремо в ядра
        const t = m !== null ? m * 60 : (st?.t ?? P.now);
        let html = "";
        if (code === GANTRY) {
            html = portalCardHtml(D, t, st?.pose);
        } else if (code.startsWith("PLT-")) {
            html = stackCardHtml(code, D, t);
        } else {
            html = machineCardHtml(code, D, t);
        }
        return html ? [html] : [];
    }

    // VX-05: клік по стосу/верстату в ланцюжку завдання вибирає його в 3D
    onAction(api, act, arg) {
        if (act === "select" && arg && api.items.get(arg)) {
            api.select(arg);
            api.focusOn(arg);
        }
    }

    /** Активне на `t` завдання (для тестів і зовнішніх шарів). */
    activeJob(api) {
        const st = this.stateOf(api);
        return activeJobAt(portalOf(api.D), st.t ?? 0);
    }
}

export const portalExtension = new PortalExtension();
registerViewerExtension(portalExtension);
