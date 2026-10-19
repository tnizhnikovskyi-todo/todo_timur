// 3D будівлі (F18-09): підлога за контуром, колони (instancing), стіни/ворота/док/двері/офіс/зарядка боксами, контур у висоту стелі,
// помаранчева лінія спринклерів, виділення об'єкта й ручки вершин контуру (режим «Будівля»). Група живе у `V.world` і оновлюється
// разом зі сценою: `E.syncScene` обгорнуто (scene.js не змінюється). Прев'ю двох кліків і маркер прив'язки — окремий оверлей.
import { ITEM_HEIGHT, itemObb } from "./building_core.js";
import { THREE } from "./three.js";
import { E, S, V, isLayerVisible } from "./state.js";

const PAL = {
    light: { floor: "#c9d3dc", line: "#2b3640", wall: "#5b6b7b", column: "#7a8794", gate: "#3b82c4", dock: "#2a9d8f", door: "#c08a3e", office: "#8fa3b5", charger: "#e0b341" },
    dark: { floor: "#33414e", line: "#cfd8e0", wall: "#8696a6", column: "#a1adb9", gate: "#5aa1de", dock: "#43b9aa", door: "#d9a45a", office: "#6b8297", charger: "#e9c45a" },
};
const SPRINKLER = "#ff8a00";
const SELECT = "#e11d74";
const rad = (a) => (a * Math.PI) / 180;

/** Вигляд, який задає режим «Будівля»: виділення й ручки вершин. */
const view = { sel: null, handles: false, handleSize: 0.5 };
export function setBuildingView(o) {
    Object.assign(view, o);
}

const buildingLayer = () => S.layers.find((l) => l.kind === "building") || null;

function disposeGroup(g) {
    g.traverse((o) => {
        if (o.geometry) {
            o.geometry.dispose();
        }
        if (o.material) {
            (Array.isArray(o.material) ? o.material : [o.material]).forEach((m) => m.dispose());
        }
        if (o.isInstancedMesh) {
            o.dispose();
        }
    });
}

const P3 = (x, y, z = 0) => new THREE.Vector3(x, z, -y);

function lineLoop(pts, y, mat) {
    const g = new THREE.BufferGeometry().setFromPoints(pts.map(([x, z]) => P3(x, z, y)));
    return new THREE.LineLoop(g, mat);
}

function build(ly) {
    const pal = PAL[V.theme === "dark" ? "dark" : "light"];
    const B = S.site.building;
    const H = B.height || 8;
    const g = new THREE.Group();
    g.name = "td-building";
    const elev = ly.elevation || 0;
    const lineMat = new THREE.LineBasicMaterial({ color: pal.line });
    const unit = new THREE.BoxGeometry(1, 1, 1);
    const edges = new THREE.EdgesGeometry(unit);
    const mats = {};
    const mat = (kind, opacity = 1) => (mats[kind + opacity] ||= new THREE.MeshLambertMaterial({ color: pal[kind], transparent: opacity < 1, opacity }));

    // контур: підлога (лише для явного контуру), обвід на підлозі й під стелею, ребра
    const pts = ly.bounds && ly.bounds.length >= 3 ? ly.bounds : null;
    if (pts) {
        const shape = new THREE.Shape(pts.map(([x, y]) => new THREE.Vector2(x, y)));
        const fill = new THREE.ShapeGeometry(shape);
        fill.rotateX(-Math.PI / 2);
        const floor = new THREE.Mesh(fill, new THREE.MeshBasicMaterial({ color: pal.floor, transparent: true, opacity: 0.55, side: THREE.DoubleSide, depthWrite: false }));
        floor.position.y = elev + 0.012;
        g.add(floor);
        g.add(lineLoop(pts, elev + 0.03, lineMat));
        g.add(lineLoop(pts, elev + H, lineMat));
        const ribs = [];
        for (const [x, y] of pts) {
            ribs.push(P3(x, y, elev), P3(x, y, elev + H));
        }
        g.add(new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(ribs), lineMat));
        const sp = S.site.sprinkler_height || 0;
        if (sp > 0 && sp < H + 0.01) {
            g.add(lineLoop(pts, elev + sp, new THREE.LineBasicMaterial({ color: SPRINKLER })));
        }
    }

    // об'єкти: колони — instancing, решта — бокси з ребрами
    const items = ly.items || [];
    const columns = items.filter((it) => it.kind === "column");
    if (columns.length) {
        const im = new THREE.InstancedMesh(unit, mat("column"), columns.length);
        const m4 = new THREE.Matrix4();
        columns.forEach((c, i) => {
            const h = c.h || H;
            m4.compose(P3(c.x, c.y, elev + h / 2), new THREE.Quaternion().setFromEuler(new THREE.Euler(0, rad(c.rot || 0), 0)), new THREE.Vector3(c.w, h, c.d));
            im.setMatrixAt(i, m4);
        });
        im.instanceMatrix.needsUpdate = true;
        g.add(im);
    }
    const place = (obj, it, h) => {
        obj.scale.set(it.w, h, it.d);
        obj.position.copy(P3(it.x, it.y, elev + h / 2));
        obj.rotation.y = rad(it.rot || 0);
        return obj;
    };
    for (const it of items) {
        if (it.kind === "column") {
            continue;
        }
        const h = it.h || ITEM_HEIGHT[it.kind] || H;
        const opacity = it.kind === "office" ? 0.4 : it.kind === "gate" || it.kind === "door" ? 0.75 : 1;
        g.add(place(new THREE.Mesh(unit, mat(it.kind, opacity)), it, h));
        g.add(place(new THREE.LineSegments(edges, lineMat), it, h));
    }
    const sel = view.sel && view.sel.kind === "item" ? items.find((it) => it.id === view.sel.id) : null;
    if (sel) {
        const m = new THREE.LineBasicMaterial({ color: SELECT, depthTest: false, transparent: true });
        const h = sel.h || ITEM_HEIGHT[sel.kind] || H;
        const o = place(new THREE.LineSegments(edges, m), { ...sel, w: sel.w + 0.1, d: sel.d + 0.1 }, h + 0.1);
        o.renderOrder = 5;
        g.add(o);
    }
    const aisle = view.sel && view.sel.kind === "aisle" ? (ly.aisles || []).find((a) => a.id === view.sel.id) : null;
    if (aisle) {
        const m = new THREE.LineBasicMaterial({ color: SELECT, depthTest: false, transparent: true });
        const ring = lineLoop([[aisle.x0, aisle.y0], [aisle.x1, aisle.y0], [aisle.x1, aisle.y1], [aisle.x0, aisle.y1]], elev + 0.06, m);
        ring.renderOrder = 5;
        g.add(ring);
    }

    // ручки вершин контуру
    const handles = new THREE.Group();
    handles.name = "td-building-handles";
    if (view.handles && pts) {
        const hm = new THREE.MeshBasicMaterial({ color: SELECT, depthTest: false, transparent: true });
        const selIdx = view.sel && view.sel.kind === "vertex" ? view.sel.index : -1;
        pts.forEach(([x, y], i) => {
            const m = new THREE.Mesh(unit, i === selIdx ? new THREE.MeshBasicMaterial({ color: "#ffffff", depthTest: false, transparent: true }) : hm);
            m.position.copy(P3(x, y, elev + 0.12));
            m.renderOrder = 6;
            handles.add(m);
        });
        scaleHandles(handles);
    }
    g.add(handles);
    g.userData.handles = handles;
    g.userData.dispose = () => {
        unit.dispose();
        edges.dispose();
        Object.values(mats).forEach((m) => m.dispose());
        lineMat.dispose();
    };
    return g;
}

function scaleHandles(handles) {
    if (!V.camera || !V.controls) {
        return;
    }
    const d = V.camera.position.distanceTo(V.controls.target);
    const s = Math.min(3, Math.max(0.25, d * 0.014));
    view.handleSize = s;
    handles.children.forEach((m) => m.scale.set(s, s * 0.4, s));
}

/** Синхронізація 3D будівлі зі станом (викликається після кожного `E.syncScene`). */
export function syncBuilding3D(force) {
    if (!V.ok || !S.site || !THREE.Scene) {
        return;
    }
    const ly = buildingLayer();
    const shown = !!ly && isLayerVisible(ly);
    const sig = JSON.stringify([shown, ly && [ly.bounds, ly.items, ly.elevation, ly.aisles && view.sel && view.sel.kind === "aisle" ? ly.aisles : null], S.site.building, S.site.sprinkler_height || 0, V.theme, view.sel, view.handles]);
    const cur = V.bld5;
    if (cur && cur.sig === sig && !force) {
        return;
    }
    if (cur && cur.g) {
        V.world.remove(cur.g);
        disposeGroup(cur.g);
        cur.g.userData.dispose?.();
    }
    const g = shown ? build(ly) : null;
    if (g) {
        V.world.add(g);
    }
    V.bld5 = { g, sig };
    if (!V.bld5Hook && V.controls) {
        V.bld5Hook = true;
        V.controls.addEventListener("change", () => {
            const h = V.bld5 && V.bld5.g && V.bld5.g.userData.handles;
            if (h && h.children.length) {
                scaleHandles(h);
            }
        });
    }
    E.requestRender?.();
}

export function disposeBuilding3D() {
    const cur = V.bld5;
    if (cur && cur.g) {
        V.world.remove(cur.g);
        disposeGroup(cur.g);
        cur.g.userData.dispose?.();
    }
    if (V.bld5Over) {
        V.world.remove(V.bld5Over);
        disposeGroup(V.bld5Over);
    }
    V.bld5 = null;
    V.bld5Over = null;
}

/** Оверлей інструмента: маркер прив'язки й прев'ю ({snap: [x, y]|null, line: [[x, y], …]|null (ламана), rect: {x0, y0, x1, y1}|null}). */
export function setOverlay(o) {
    if (!V.ok || !THREE.Scene) {
        return;
    }
    if (V.bld5Over) {
        V.world.remove(V.bld5Over);
        disposeGroup(V.bld5Over);
        V.bld5Over = null;
    }
    if (!o || (!o.snap && !o.line && !o.rect)) {
        E.requestRender?.();
        return;
    }
    const g = new THREE.Group();
    const y = (buildingLayer() || { elevation: 0 }).elevation + 0.08;
    const mat = new THREE.LineBasicMaterial({ color: SELECT, depthTest: false, transparent: true });
    if (o.line && o.line.length > 1) {
        g.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(o.line.map(([x, z]) => P3(x, z, y))), mat));
    }
    if (o.rect) {
        const r = o.rect;
        g.add(lineLoop([[r.x0, r.y0], [r.x1, r.y0], [r.x1, r.y1], [r.x0, r.y1]], y, mat));
    }
    if (o.snap) {
        const d = Math.max(0.25, view.handleSize * 0.9);
        const [x, z] = o.snap;
        const seg = [P3(x - d, z, y), P3(x + d, z, y), P3(x, z - d, y), P3(x, z + d, y)];
        g.add(new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(seg), mat));
    }
    g.traverse((m) => {
        m.renderOrder = 7;
    });
    V.world.add(g);
    V.bld5Over = g;
    E.requestRender?.();
}

// 3D будівлі оновлюється разом зі сценою: scene.js не змінюється, тому обгортаємо `E.syncScene` (як S3 — `E.renderAll`)
const origSync = E.syncScene;
if (typeof origSync === "function" && !origSync.__s5) {
    const wrapped = function syncSceneS5(...a) {
        const r = origSync.apply(this, a);
        try {
            syncBuilding3D(a[0]);
        } catch (e) {
            console.error("S5 3D будівлі:", e);
        }
        return r;
    };
    wrapped.__s5 = true;
    E.syncScene = wrapped;
}
export { itemObb };
