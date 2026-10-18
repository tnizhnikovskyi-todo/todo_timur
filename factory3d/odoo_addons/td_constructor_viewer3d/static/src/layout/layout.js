/** @odoo-module */
// Розширення «Переглядача»: опублікована розкладка конструктора поверх запеченої моделі (bridge SPEC R-02…R-06).
// Реєструється в ядрі (`registerViewerExtension`); ядро викликає `applyLayout(api, D.layout)` після завантаження моделі,
// на кожній повній дельті й зміні розкладки — ДО stockLoad.sync, тож вантаж за залишками лягає у вже зсунуті комірки.
// Ідемпотентно: початкове положення вузла зберігається в userData.f3dBase, кожне застосування йде від бази.
// Координати payload — Blender (X уздовж, Y впоперек, Z угору), three.js: (x, z, −y). УВАГА (rjsmin): без вкладених `...`.

import { registerViewerExtension } from "@factory3d_viewer/viewer/core";
import { FRONT_ANGLE, buildGenericModel, disposeTree, fitModel } from "./generic_models";
import { buildSlotObject } from "./slot_view";

const STATES = new WeakMap(); // scene → стан застосованої розкладки (один на екземпляр переглядача)
const KIND_BY_CATEGORY = { machine: "machine", rack: "rack", forklift: "vehicle" };
const rad = (deg) => (deg * Math.PI) / 180;
const FRAME_TOLERANCE = 0.8; // м: вузол «rack» у GLB вважається каркасом місця, якщо його початок у межах 0,8 м від центра місця

function stateOf(api, create) {
    let st = STATES.get(api.scene);
    if (!st && create) {
        st = { moved: new Set(), hidden: new Map(), added: new Map(), models: new Map() };
        STATES.set(api.scene, st);
    }
    return st;
}

/** Початкове положення вузла (до розкладки); зберігається один раз. */
function baseOf(obj) {
    if (!obj.userData.f3dBase) {
        obj.userData.f3dBase = { pos: obj.position.clone(), quat: obj.quaternion.clone(), visible: obj.visible, centre: null };
    }
    return obj.userData.f3dBase;
}

/** Охопний об'єм меша вузла у світових координатах без службових об'єктів вантажу. */
function bboxOf(T, obj) {
    const box = new T.Box3();
    const tmp = new T.Box3();
    obj.updateWorldMatrix(true, true);
    obj.traverse((o) => {
        if (!o.isMesh || o.userData.f3dStock || !o.geometry) {
            return;
        }
        if (!o.geometry.boundingBox) {
            o.geometry.computeBoundingBox();
        }
        box.union(tmp.copy(o.geometry.boundingBox).applyMatrix4(o.matrixWorld));
    });
    return box;
}

/** Виставити локальне положення; змінене — позначає userData.f3dRev (stock_load розбирає комірку заново). */
function setPose(obj, pos, quat) {
    if (obj.position.distanceToSquared(pos) < 1e-12 && obj.quaternion.angleTo(quat) < 1e-9) {
        return;
    }
    obj.position.copy(pos);
    obj.quaternion.copy(quat);
    obj.updateMatrix();
    obj.userData.f3dRev = (obj.userData.f3dRev || 0) + 1;
}

function restorePose(obj) {
    const base = obj.userData.f3dBase;
    if (base) {
        setPose(obj, base.pos, base.quat);
        obj.updateMatrixWorld(true);
    }
}

/**
 * Зсув (dx, dy, м) і поворот (drot, °) відносно бази навколо центра bbox вузла; delev — зсув угору (м).
 * Світова матриця: T(c + t) · Ry(θ) · T(−c) · W0 (W0 — база); локальна — через обернену світову матрицю батька.
 * Проміжне положення в об'єкт не пишеться: userData.f3dRev змінюється лише коли вузол справді переставлено.
 */
export function moveNode(T, obj, mv) {
    const base = baseOf(obj);
    obj.parent?.updateWorldMatrix(true, false);
    const parentWorld = obj.parent ? obj.parent.matrixWorld : new T.Matrix4();
    const w0 = new T.Matrix4().multiplyMatrices(parentWorld, new T.Matrix4().compose(base.pos, base.quat, obj.scale));
    if (!base.centre) {
        // вузол ще на базовому положенні: baseOf створено при першому торканні (hide/moveNode)
        obj.updateMatrixWorld(true);
        const box = bboxOf(T, obj);
        base.centre = box.isEmpty() ? obj.getWorldPosition(new T.Vector3()) : box.getCenter(new T.Vector3());
    }
    const c = base.centre;
    const world = new T.Matrix4()
        .makeTranslation(c.x + (mv.dx || 0), c.y + (mv.delev || 0), c.z - (mv.dy || 0))
        .multiply(new T.Matrix4().makeRotationY(rad(mv.drot || 0)))
        .multiply(new T.Matrix4().makeTranslation(-c.x, -c.y, -c.z))
        .multiply(w0);
    const local = new T.Matrix4().copy(parentWorld).invert().multiply(world);
    const pos = new T.Vector3();
    const quat = new T.Quaternion();
    local.decompose(pos, quat, new T.Vector3());
    setPose(obj, pos, quat);
    obj.updateMatrixWorld(true);
}

/** Вузол-каркас стелажа в моделі за положенням місця у базі (код каркаса в GLB не збігається з префіксом місця). */
function frameNode(api, hint) {
    let best = null;
    let bestD = FRAME_TOLERANCE;
    const v = new api.THREE.Vector3();
    for (const obj of api.items.values()) {
        if (obj.userData.kind !== "rack" || obj.userData.f3dLayout) {
            continue;
        }
        obj.getWorldPosition(v);
        const d = Math.hypot(v.x - hint.x, -v.z - hint.y);
        if (d <= bestD) {
            best = obj;
            bestD = d;
        }
    }
    return best;
}

// ---------------------------------------------------------------- додані об'єкти

function modelUrl(api, e) {
    if (!e.model_url) {
        return null;
    }
    // кіоск без сесії бере GLB за токеном: `<base>/layout/model/<variant_id>` (контролер моста)
    return api.kiosk && api.client?.base ? api.client.base + "/layout/model/" + e.variant_id : e.model_url;
}

async function loadGlb(api, st, url) {
    if (!st.models.has(url)) {
        const get = async () => {
            const buf = api.opts?.fetchPart
                ? await api.opts.fetchPart(url)
                : await fetch(url, { credentials: "same-origin" }).then((r) => {
                      if (!r.ok) {
                          throw new Error(url + ": " + r.status);
                      }
                      return r.arrayBuffer();
                  });
            return new Promise((res, rej) => new api.GLTFLoader().parse(buf, "", res, rej));
        };
        st.models.set(url, get());
    }
    return st.models.get(url);
}

function styleMeshes(api, obj) {
    obj.traverse((o) => {
        if (o.isMesh) {
            o.material = o.material.clone(); // свій матеріал на екземпляр: підсвічування не фарбує сусідів
            o.material.envMapIntensity = api.envMapIntensity;
            o.castShadow = api.shadows && !o.material.transparent;
            o.receiveShadow = api.shadows && !o.material.transparent;
        }
    });
}

function placementBody(api, e) {
    const T = api.THREE;
    const { L, W, H } = e.dims;
    const ang = FRONT_ANGLE[e.front || "s"] || 0;
    const swap = ang === 90 || ang === 270;
    const body = fitModel(T, buildGenericModel(T, e.category, swap ? W : L, swap ? L : W, H), swap ? W : L, H, swap ? L : W);
    body.rotation.y = rad(ang);
    styleMeshes(api, body);
    return body;
}

function buildPlacement(api, st, e) {
    const T = api.THREE;
    const root = new T.Group();
    root.name = "F3D_LAYOUT_" + e.code;
    root.position.set(e.x, e.elev || 0, -e.y);
    root.rotation.y = rad(e.rot || 0);
    root.userData = {
        code: e.code,
        kind: KIND_BY_CATEGORY[e.category] || "equipment",
        label: e.name || e.code,
        desc: "Додано в конструкторі" + (e.model_url ? " (з 3D-моделлю варіанта)." : "."),
        status: "idle",
        f3dLayout: true,
    };
    const { L, W, H } = e.dims;
    // невидимий об'єм для вибору: GLB варіанта доходить пізніше за сам об'єкт
    const hit = new T.Mesh(new T.BoxGeometry(L, Math.max(H, 0.4), W), new T.MeshBasicMaterial({ visible: false }));
    hit.position.y = Math.max(H, 0.4) / 2;
    hit.userData.f3dStock = true; // службовий: не враховується в bbox
    root.add(hit);
    let body = placementBody(api, e);
    root.add(body);
    const rec = { root, roots: [{ code: e.code, obj: root }], disposed: false };
    const url = modelUrl(api, e);
    if (url) {
        loadGlb(api, st, url).then(
            (gltf) => {
                if (rec.disposed) {
                    return;
                }
                const inst = gltf.scene.clone(true);
                styleMeshes(api, inst);
                const fitted = fitModel(T, inst, L, H, W);
                root.remove(body);
                disposeTree(body);
                body = fitted;
                root.add(body);
                api.refreshSelection?.();
            },
            (err) => {
                console.warn("f3d layout: модель варіанта не завантажено, лишається умовна", url, err);
            }
        );
    }
    return rec;
}

function buildAdded(api, st, e) {
    if (e.kind === "slot") {
        const { group, roots } = buildSlotObject(api.THREE, e, { shadows: api.shadows, envMapIntensity: api.envMapIntensity });
        for (const r of roots) {
            r.obj.userData.f3dLayout = true;
        }
        return { root: group, roots, disposed: false };
    }
    return buildPlacement(api, st, e);
}

function register(api, rec) {
    for (const { code, obj } of rec.roots) {
        api.items.set(code, obj);
    }
}
function unregister(api, rec) {
    for (const { code, obj } of rec.roots) {
        if (api.items.get(code) === obj) {
            api.items.delete(code);
        }
    }
}
function disposeRec(api, rec) {
    rec.disposed = true;
    unregister(api, rec);
    api.dropLabels(rec.roots.map((r) => r.obj));
    rec.root.parent?.remove(rec.root);
    disposeTree(rec.root);
}

// ---------------------------------------------------------------- застосування

/**
 * Застосувати `layout` (D.layout або null) до сцени переглядача. Викликається ядром; ідемпотентна.
 * `api` — об'єкт точки розширення ядра (THREE, scene, items, stockLoad, relabel, …).
 */
export function applyLayout(api, layout) {
    let st = stateOf(api, false);
    if (!st && !layout) {
        return;
    }
    st = st || stateOf(api, true);
    const T = api.THREE;
    // 1. усе повертаємо до бази: додані об'єкти знімаємо з items (самі лишаються для повторного використання)
    for (const rec of st.added.values()) {
        unregister(api, rec);
    }
    const was = st.moved;
    st.moved = new Set();
    for (const [code, obj] of st.hidden) {
        obj.visible = obj.userData.f3dBase ? obj.userData.f3dBase.visible : true;
        if (!api.items.has(code)) {
            api.items.set(code, obj);
        }
    }
    st.hidden.clear();

    if (layout) {
        // 2. прибране й замінене: visible = false, з items — тож без вибору, пошуку за кодом і вантажу за залишками
        const hide = (obj, code) => {
            if (!obj || obj.userData.f3dLayout) {
                return;
            }
            baseOf(obj);
            obj.visible = false;
            api.items.delete(code);
            st.hidden.set(code, obj);
        };
        const frames = layout.frames || {};
        const gone = [...(layout.hidden || []), ...(layout.replaced || [])];
        for (const code of gone) {
            hide(api.items.get(code), code);
        }
        for (const prefix of gone) {
            if (frames[prefix]) {
                const frame = frameNode(api, frames[prefix]);
                if (frame) {
                    hide(frame, frame.userData.code);
                }
            }
        }
        // 3. переміщене: зсув/поворот навколо центра bbox відносно бази
        for (const [code, mv] of Object.entries(layout.moved || {})) {
            const obj = api.items.get(code) || (frames[code] ? frameNode(api, frames[code]) : null);
            if (obj && !obj.userData.f3dLayout) {
                moveNode(T, obj, mv);
                st.moved.add(obj);
            }
        }
    }

    // вузли, які були зсунуті раніше, а тепер ні, повертаються на базу (і лише вони)
    const touched = new Set(was);
    for (const obj of was) {
        if (!st.moved.has(obj)) {
            restorePose(obj);
        }
    }
    // 4. додане: будуємо (або беремо готове з тим самим описом) і реєструємо в items
    const wanted = new Map((layout?.added || []).map((e) => [e.code, e]));
    for (const [code, rec] of [...st.added]) {
        if (!wanted.has(code) || rec.sig !== JSON.stringify(wanted.get(code))) {
            disposeRec(api, rec);
            st.added.delete(code);
        }
    }
    const fresh = [];
    for (const [code, e] of wanted) {
        let rec = st.added.get(code);
        if (!rec) {
            rec = buildAdded(api, st, e);
            rec.sig = JSON.stringify(e);
            api.scene.add(rec.root);
            st.added.set(code, rec);
            fresh.push(...rec.roots.map((r) => r.obj));
        }
        register(api, rec);
    }
    if (fresh.length) {
        api.buildLabels(fresh);
    }
    // 5. підписи й вибір ідуть за вузлами
    api.relabel([...touched, ...st.moved]);
    api.refreshSelection?.();
    if (!st.moved.size && !st.hidden.size && !st.added.size && !layout) {
        STATES.delete(api.scene);
    }
}

registerViewerExtension({ applyLayout });
