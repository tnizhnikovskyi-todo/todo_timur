// Режим «Будівля» (F18): контур, колони, стіни, ворота, док, двері, офіс, зарядка, проходи; прив'язка, лінійки, перевірки будівлі, техніка (N-06).
// Режим стоїть поруч із 3D/План у `#vtools` і взаємовиключний з «Редагувати»: у ньому клацання по сцені обробляє цей файл (слухачі canvas у фазі
// захоплення), решта правки вимкнена. Усі зміни — звичайні `E.commit` над `layer.items / aisles / bounds`, тож скасування (Ctrl+Z) і збереження
// працюють так само, як для місць. Висоти й техніка складу — поля площадки (їх змінює менеджер, `saveSite`).
import {
    ITEM_DEFAULT_SIZE,
    ITEM_KINDS,
    LINK_KINDS,
    TECHS,
    aisleAxis,
    aisleFromPoints,
    aisleLinks,
    columnGrid,
    contourAroundObjects,
    contourBbox,
    contourOf,
    contourWalls,
    isRectContour,
    isSimplePolygon,
    itemAt,
    moveAisle,
    nearestEdge,
    newItem,
    nextName,
    parseTech,
    polygonArea,
    polygonPerimeter,
    rectContour,
    snapPoint,
    snapPoints,
    techMin,
    techValue,
} from "./building_core.js";
import { setBuildingView, setOverlay } from "./building_3d.js";
import { openDialog } from "./dialogs.js";
import { fld, numInput, selectEl, textInput } from "./fields.js";
import { obbAabb } from "./geometry.js";
import { runLive } from "./live.js";
import { slotObb } from "./cells.js";
import { registries } from "./registry.js";
import { canEditLayer, canManage, lockHint } from "./roles.js";
import { THREE } from "./three.js";
import { E, S, V, layerOf } from "./state.js";
import { $, ROOT, K, debounce, fmt, h, ic, rnd, toast, uid } from "./util.js";

/** Стан режиму (модульний: `S.ui` не підходить — його перезаписують слайси). Експортується для тестів. */
export const B = { on: false, tool: null, sel: null, step: 0.5, pend: null, drag: null, down: null, prev: null, siteId: null, cur: null, wallTh: 0.2, aisleW: null, rulers: false };
const CHECK_IDS = ["inside", "aisle_width", "height"];
const CHECK_NAMES = {
    inside: ["Усередині контуру й поза об'єктами будівлі", "Місця й обладнання в контурі будівлі, не перетинають колони, стіни, офіс, зарядку"],
    aisle_width: ["Ширина проходу й проїзду за технікою", "Проходи й проїзди між рядами не вужчі за мінімум техніки складу чи зони"],
    height: ["Висота до стелі й спринклерів", "Верх складування не вище стелі й не ближче 0,5 м до спринклерів"],
};
const TOOLS = [
    ["column", "Колона", "plus"],
    ["wall", "Стіна", "plus"],
    ["gate", "Ворота", "plus"],
    ["dock", "Док", "plus"],
    ["door", "Двері", "plus"],
    ["office", "Офіс", "plus"],
    ["charger", "Зарядка", "plus"],
    ["aisle", "Прохід", "plus"],
];
const TOOL_HINTS = {
    column: "Клацніть, щоб поставити колону.",
    wall: "Стіна: клацніть початок і кінець відрізка.",
    gate: "Ворота: клацніть на стіні чи ребрі контуру.",
    dock: "Док: клацніть на стіні чи ребрі контуру.",
    door: "Двері: клацніть на стіні чи ребрі контуру.",
    office: "Офіс: клацніть два протилежні кути.",
    charger: "Клацніть, щоб поставити зарядку техніки.",
    aisle: "Прохід: клацніть початок і кінець осі (кінець на іншому проході з'єднує їх).",
    vertex: "Клацніть ребро контуру, щоб додати вершину.",
};

/* ===== допоміжне ===== */
export const bLayer = () => S.layers.find((l) => l.kind === "building") || null;
const items = () => {
    const ly = bLayer();
    return ly ? (ly.items ||= []) : [];
};
const aisles = () => {
    const ly = bLayer();
    return ly ? (ly.aisles ||= []) : [];
};
const editable = () => !!bLayer() && canEditLayer(bLayer());
const contourEditable = () => !!bLayer() && canManage();
const contour = () => contourOf(bLayer(), S.site.building);
const camDist = () => (V.ok && V.camera && V.controls ? V.camera.position.distanceTo(V.controls.target) : 40);
const snapRad = () => Math.min(1, Math.max(0.2, camDist() * 0.012));
const hasExplicitContour = () => !!(bLayer() && bLayer().bounds && bLayer().bounds.length >= 3);
const selItem = () => (B.sel && B.sel.kind === "item" ? items().find((it) => it.id === B.sel.id) || null : null);
const selAisle = () => (B.sel && B.sel.kind === "aisle" ? aisles().find((a) => a.id === B.sel.id) || null : null);

function updateView() {
    setBuildingView({ sel: B.sel, handles: B.on && contourEditable() && hasExplicitContour() });
}
/** Живе оновлення під час правки: перевірки, сцена, виділення; перемальовування панелей — після коміту. */
function liveB() {
    updateView();
    S.issues = runLive();
    E.syncScene();
    E.updateVisual?.();
    E.requestRender?.();
}
function commitB(label) {
    updateView();
    growBuilding();
    // кожна дія будівлі — окремий крок скасування (undo.js зливає правки одного поля в межах 1,2 с: для безперервного введення, не для дій)
    const top = S.hist && S.hist.stack ? S.hist.stack[S.hist.idx] : null;
    if (top) {
        top.key = null;
    }
    E.commit({ label });
}
/** Габарит площадки не менший за контур: інакше `fits` вважав би місця в виступі поза будівлею. */
function growBuilding() {
    const ly = bLayer();
    if (!ly || !ly.bounds || ly.bounds.length < 3 || !S.site) {
        return;
    }
    const b = contourBbox(ly.bounds);
    const bd = S.site.building;
    let grown = false;
    if (b.x1 > bd.length) {
        bd.length = Math.ceil(b.x1);
        grown = true;
    }
    if (b.y1 > bd.width) {
        bd.width = Math.ceil(b.y1);
        grown = true;
    }
    if (grown) {
        E.saveSiteProps?.();
    }
}
const saveSiteExtra = debounce(async () => {
    const a = E.adapter;
    if (!a || !S.site) {
        return;
    }
    try {
        await a.saveSite({ sprinkler_height: S.site.sprinkler_height || 0, aisle_tech: S.site.aisle_tech || null });
    } catch (e) {
        toast("Не вдалося зберегти висоти й техніку: " + (e.data?.message || e.message || e), "err");
    }
}, 700);

/* ===== режим ===== */
export function enterBuilding() {
    if (B.on || !S.site) {
        return;
    }
    const ly = bLayer();
    if (!ly) {
        toast("На площадці немає шару «Будівля».", "warn");
        return;
    }
    S.app.mode = "edit";
    B.prev = { layer: S.ui.layer, tab: S.ui.leftTab };
    Object.assign(B, { on: true, tool: null, sel: null, pend: null, drag: null, cur: null, siteId: S.site.id });
    S.sel = null;
    S.multi = [];
    S.selCell = null;
    S.edit = null;
    E.cancelModes?.();
    if (S.ui.layer !== ly.id) {
        E.setActiveLayer?.(ly.id);
    }
    updateView();
    E.setView?.("plan");
    E.renderAll();
    E.setLeftTab?.("building");
    E.syncScene(true);
    drawRulers();
}
export function exitBuilding() {
    if (!B.on) {
        return;
    }
    Object.assign(B, { on: false, tool: null, sel: null, pend: null, drag: null, cur: null });
    setOverlay(null);
    updateView();
    const prev = B.prev || {};
    B.prev = null;
    if (prev.layer && layerOf(prev.layer) && S.ui.layer !== prev.layer) {
        E.setActiveLayer?.(prev.layer);
    }
    E.syncScene(true);
    E.renderAll();
    E.setLeftTab?.(prev.tab && prev.tab !== "building" ? prev.tab : "layers");
    drawRulers();
}
export const toggleBuilding = () => (B.on ? exitBuilding() : enterBuilding());

function setTool(tool) {
    E.cancelModes?.();
    B.tool = B.tool === tool ? null : tool;
    B.pend = null;
    B.cur = null;
    setOverlay(null);
    if (B.tool && TOOL_HINTS[B.tool]) {
        toast(TOOL_HINTS[B.tool]);
    }
    renderTab();
    renderVToolsButton();
}

/* ===== операції над об'єктами ===== */
function addItem(kind, x, y, extra = {}) {
    if (!editable()) {
        toast(lockHint(bLayer()), "warn");
        return null;
    }
    const it = newItem(kind, uid("bi_"), x, y, extra);
    it.name = extra.name ?? nextName(items(), kind);
    items().push(it);
    B.sel = { kind: "item", id: it.id };
    commitB(`Додано: ${it.name}`);
    return it;
}
function addAisle(rect) {
    const list = aisles();
    const a = { id: uid("ai_"), name: `Прохід ${list.length + 1}`, ...rect };
    list.push(a);
    B.sel = { kind: "aisle", id: a.id };
    commitB(`Додано: ${a.name}`);
    return a;
}
export function deleteSelection() {
    if (!B.sel || !editable()) {
        return false;
    }
    const ly = bLayer();
    if (B.sel.kind === "item") {
        const it = selItem();
        ly.items = items().filter((x) => x.id !== B.sel.id);
        B.sel = null;
        commitB(`Видалено: ${it ? it.name || ITEM_KINDS[it.kind] : "об'єкт"}`);
    } else if (B.sel.kind === "aisle") {
        const a = selAisle();
        ly.aisles = aisles().filter((x) => x.id !== B.sel.id);
        B.sel = null;
        commitB(`Видалено: ${a ? a.name || a.id : "прохід"}`);
    } else if (B.sel.kind === "vertex") {
        if (!contourEditable()) {
            return false;
        }
        if (ly.bounds.length <= 3) {
            toast("У контурі має лишатися щонайменше 3 вершини.", "warn");
            return true;
        }
        ly.bounds = ly.bounds.filter((_, i) => i !== B.sel.index);
        B.sel = null;
        commitB("Контур: видалено вершину");
    }
    return true;
}

/** Ворота/док/двері стають на ребро контуру чи стіну: центр — на лінії, поворот — уздовж. */
function alignOpening(kind, s) {
    const pts = contour();
    const edge = nearestEdge(pts, s.x, s.y);
    let best = null;
    if (edge && edge.dist <= 1) {
        const [a, b] = [pts[edge.index], pts[(edge.index + 1) % pts.length]];
        best = { x: edge.point[0], y: edge.point[1], rot: (Math.atan2(b[1] - a[1], b[0] - a[0]) * 180) / Math.PI };
    }
    for (const w of items().filter((it) => it.kind === "wall")) {
        const r = ((w.rot || 0) * Math.PI) / 180;
        const dx = s.x - w.x;
        const dy = s.y - w.y;
        const along = dx * Math.cos(r) + dy * Math.sin(r);
        const across = -dx * Math.sin(r) + dy * Math.cos(r);
        if (Math.abs(along) <= w.w / 2 && Math.abs(across) <= Math.max(1, w.d) && (!best || Math.abs(across) < 1)) {
            best = { x: rnd(w.x + along * Math.cos(r)), y: rnd(w.y + along * Math.sin(r)), rot: w.rot || 0 };
        }
    }
    const [, d] = ITEM_DEFAULT_SIZE[kind];
    return best ? { x: rnd(best.x), y: rnd(best.y), extra: { rot: rnd(best.rot, 2), d } } : { x: s.x, y: s.y, extra: {} };
}

/** Стіни вздовж ребер контуру (усередину на пів товщини, щоб місця біля стіни не перетинали її). */
export function wallsAlongContour(th = 0.3) {
    if (!editable()) {
        return 0;
    }
    const walls = contourWalls(contour(), th, () => uid("bi_"), items());
    if (walls.length) {
        items().push(...walls);
        commitB(`Стіни по контуру: ${walls.length}`);
    }
    return walls.length;
}

/** Контур за складом + відступ 2 м (F18-01). */
export function contourFromWarehouse(margin = 2) {
    const ly = bLayer();
    if (!ly || !contourEditable()) {
        return false;
    }
    const boxes = [];
    for (const s of S.slots) {
        const lk = (layerOf(s.layer_id) || {}).kind;
        if (s.template !== "zone" && lk !== "building" && lk !== "yard") {
            boxes.push(obbAabb(slotObb(s.template, s.params || {}, s.x || 0, s.y || 0, s.rotation || 0)));
        }
    }
    ly.bounds = contourAroundObjects(boxes, margin, S.site.building);
    commitB("Контур за складом");
    return true;
}

/* ===== вказівник ===== */
function pointer(e) {
    const ly = bLayer();
    return E.floorPoint ? E.floorPoint(e, ly ? ly.elevation : 0) : null;
}
const snapPts = (skipItemId = null) => snapPoints({ contour: bLayer()?.bounds || [], items: items().filter((it) => it.id !== skipItemId), aisles: aisles() });
function snapAt(pt, e, from = null, skipId = null) {
    return snapPoint(pt.x, pt.y, { step: B.step, pts: snapPts(skipId), aisles: aisles(), from, alt: !!e.altKey, rad: snapRad() });
}
const busy = () => !!(V.placing || V.ruler.on || V.pickMode);

function hitTest(pt) {
    const ly = bLayer();
    if (!ly) {
        return null;
    }
    if (B.on && contourEditable() && hasExplicitContour()) {
        const r = Math.max(0.35, (V.camera ? camDist() * 0.014 : 0.5) * 0.9);
        const i = ly.bounds.findIndex((p) => Math.hypot(p[0] - pt.x, p[1] - pt.y) <= r);
        if (i >= 0) {
            return { sel: { kind: "vertex", index: i }, drag: { kind: "vertex", index: i, orig: [...ly.bounds[i]] } };
        }
    }
    const it = itemAt(items(), pt.x, pt.y, Math.min(0.5, Math.max(0.1, camDist() * 0.004)));
    if (it) {
        return { sel: { kind: "item", id: it.id }, drag: { kind: "item", id: it.id, orig: { x: it.x, y: it.y } } };
    }
    const a = aisles()
        .filter((x) => pt.x >= x.x0 && pt.x <= x.x1 && pt.y >= x.y0 && pt.y <= x.y1)
        .sort((p, q) => (p.x1 - p.x0) * (p.y1 - p.y0) - (q.x1 - q.x0) * (q.y1 - q.y0))[0];
    return a ? { sel: { kind: "aisle", id: a.id }, drag: { kind: "aisle", id: a.id, orig: { cx: (a.x0 + a.x1) / 2, cy: (a.y0 + a.y1) / 2 } } } : null;
}

function onDown(e) {
    if (!B.on || !V.ok || busy() || (e.pointerType === "mouse" && e.button !== 0)) {
        return;
    }
    const pt = pointer(e);
    if (!pt) {
        return;
    }
    B.down = { x: e.clientX, y: e.clientY };
    if (B.tool) {
        return; // розставляння — на pointerup (клацання без зсуву), щоб у «Плані» лишалося перетягування для панорами
    }
    const hit = hitTest(pt);
    if (!hit) {
        return;
    }
    e.stopImmediatePropagation();
    e.preventDefault();
    B.sel = hit.sel;
    B.drag = { ...hit.drag, pt0: pt, sx: e.clientX, sy: e.clientY, moved: false };
    try {
        V.canvas.setPointerCapture(e.pointerId);
    } catch {
        /* ок */
    }
    updateView();
    E.syncScene();
    renderTab();
}

function dragMove(e, pt) {
    const d = B.drag;
    if (!d.moved && Math.hypot(e.clientX - d.sx, e.clientY - d.sy) < 4) {
        return;
    }
    d.moved = true;
    const ly = bLayer();
    if (!ly || (d.kind === "vertex" ? !contourEditable() : !editable())) {
        return;
    }
    const dx = pt.x - d.pt0.x;
    const dy = pt.y - d.pt0.y;
    if (d.kind === "item") {
        const it = items().find((x) => x.id === d.id);
        if (it) {
            const s = snapAt({ x: d.orig.x + dx, y: d.orig.y + dy }, e, null, d.id);
            it.x = s.x;
            it.y = s.y;
        }
    } else if (d.kind === "vertex") {
        const s = snapPoint(d.orig[0] + dx, d.orig[1] + dy, { step: B.step, pts: ly.bounds.map(([x, y], i) => ({ x, y, kind: "vertex", skip: i === d.index })).filter((p) => !p.skip), alt: !!e.altKey, rad: snapRad() });
        ly.bounds[d.index] = [s.x, s.y];
    } else if (d.kind === "aisle") {
        const a = aisles().find((x) => x.id === d.id);
        if (a) {
            const s = snapAt({ x: d.orig.cx + dx, y: d.orig.cy + dy }, e, null, null);
            moveAisle(aisles(), d.id, rnd(s.x - (a.x0 + a.x1) / 2), rnd(s.y - (a.y0 + a.y1) / 2));
        }
    }
    liveB();
}

function onMove(e) {
    if (!B.on || !V.ok) {
        return;
    }
    const pt = pointer(e);
    if (!pt) {
        return;
    }
    B.cursor = pt;
    drawRulers(true);
    if (B.drag) {
        e.stopImmediatePropagation();
        dragMove(e, pt);
        return;
    }
    if (B.tool && !busy()) {
        const from = B.pend ? B.pend[0] : null;
        const s = snapAt(pt, e, from ? [from.x, from.y] : null);
        B.cur = s;
        const ov = { snap: [s.x, s.y] };
        if (from && (B.tool === "wall" || B.tool === "aisle")) {
            ov.line = [[from.x, from.y], [s.x, s.y]];
        } else if (from && B.tool === "office") {
            ov.rect = { x0: from.x, y0: from.y, x1: s.x, y1: s.y };
        }
        setOverlay(ov);
        V.canvas.style.cursor = "crosshair";
    }
}

function onUp(e) {
    if (!B.on || !V.ok) {
        return;
    }
    try {
        V.canvas.releasePointerCapture(e.pointerId);
    } catch {
        /* ок */
    }
    const down = B.down;
    B.down = null;
    if (B.drag) {
        const d = B.drag;
        B.drag = null;
        e.stopImmediatePropagation();
        if (d.moved && (d.kind === "vertex" ? contourEditable() : editable())) {
            const ly = bLayer();
            if (d.kind === "vertex" && !isSimplePolygon(ly.bounds)) {
                ly.bounds[d.index] = d.orig;
                toast("Контур не має перетинати сам себе.", "warn");
                liveB();
                renderTab();
                return;
            }
            commitB(d.kind === "item" ? `Переміщено: ${selItem()?.name || "об'єкт"}` : d.kind === "aisle" ? `Переміщено: ${selAisle()?.name || "прохід"}` : "Контур: вершина");
        } else {
            renderTab();
        }
        return;
    }
    if (!down || Math.hypot(e.clientX - down.x, e.clientY - down.y) >= 5 || busy()) {
        return;
    }
    const pt = pointer(e);
    if (!pt) {
        return;
    }
    if (B.tool) {
        placeClick(snapAt(pt, e, B.pend ? [B.pend[0].x, B.pend[0].y] : null));
    } else if (B.sel) {
        B.sel = null;
        updateView();
        E.syncScene();
        renderTab();
    }
}

function placeClick(s) {
    if (!editable() && B.tool !== "vertex") {
        toast(lockHint(bLayer()), "warn");
        return;
    }
    switch (B.tool) {
        case "column":
        case "charger":
            addItem(B.tool, s.x, s.y);
            break;
        case "gate":
        case "dock":
        case "door": {
            const o = alignOpening(B.tool, s);
            addItem(B.tool, o.x, o.y, o.extra);
            break;
        }
        case "wall":
        case "office":
        case "aisle":
            if (!B.pend) {
                B.pend = [s];
                toast("Тепер клацніть другу точку.");
                break;
            }
            finishTwoClick(B.tool, B.pend[0], s);
            B.pend = null;
            setOverlay({ snap: [s.x, s.y] });
            break;
        case "vertex": {
            if (!contourEditable() || !hasExplicitContour()) {
                toast("Додавати вершини може менеджер до явного контуру: створіть контур.", "warn");
                break;
            }
            const ly = bLayer();
            const edge = nearestEdge(ly.bounds, s.x, s.y);
            ly.bounds.splice(edge.index + 1, 0, [rnd(edge.point[0]), rnd(edge.point[1])]);
            B.sel = { kind: "vertex", index: edge.index + 1 };
            commitB("Контур: додано вершину");
            break;
        }
        default:
    }
}

function finishTwoClick(tool, p, q) {
    if (Math.hypot(q.x - p.x, q.y - p.y) < 0.1) {
        toast("Точки збігаються.", "warn");
        return;
    }
    if (tool === "wall") {
        const len = Math.hypot(q.x - p.x, q.y - p.y);
        addItem("wall", (p.x + q.x) / 2, (p.y + q.y) / 2, { w: rnd(len), d: B.wallTh, th: B.wallTh, rot: rnd((Math.atan2(q.y - p.y, q.x - p.x) * 180) / Math.PI, 2) });
    } else if (tool === "office") {
        addItem("office", (p.x + q.x) / 2, (p.y + q.y) / 2, { w: rnd(Math.max(0.5, Math.abs(q.x - p.x))), d: rnd(Math.max(0.5, Math.abs(q.y - p.y))) });
    } else {
        const width = B.aisleW || (bLayer() || {}).aisle_width || 3;
        addAisle(aisleFromPoints([p.x, p.y], [q.x, q.y], width));
    }
}

/* ===== вікно «Колони сіткою» ===== */
export function openColumnGrid() {
    if (!editable()) {
        toast(lockHint(bLayer()), "warn");
        return;
    }
    const cg = S.site.column_grid || { step_x: 6, step_y: 6 };
    const bb = contourBbox(contour());
    const st = { x0: rnd(bb.x0 + (cg.step_x || 6), 2), y0: rnd(bb.y0 + (cg.step_y || 6), 2), sx: cg.step_x || 6, sy: cg.step_y || 6, nx: 0, ny: 0 };
    st.nx = Math.max(1, Math.floor((bb.x1 - bb.x0 - 1) / st.sx) - 0);
    st.ny = Math.max(1, Math.floor((bb.y1 - bb.y0 - 1) / st.sy) - 0);
    const info = h("div", { class: "small muted", id: "cgInfo" });
    const num = (k, label, min, max, step, int) =>
        fld(label, numInput({ value: st[k], min, max, step, int, label, set: (v) => { st[k] = v; draw(); } }), k.startsWith("n") ? null : "м");
    const draw = () => {
        info.textContent = `Буде створено до ${Math.max(0, Math.round(st.nx) * Math.round(st.ny))} колон; наявні в тих самих точках пропускаються.`;
    };
    draw();
    openDialog({
        title: "Колони сіткою",
        cls: "narrow",
        body: h("div", { class: "fcol" }, h("div", { class: "grid2" }, num("x0", "Початок X", -1000, 10000, 0.1), num("y0", "Початок Y", -1000, 10000, 0.1)), h("div", { class: "grid2" }, num("nx", "Колон по X", 1, 200, 1, true), num("ny", "Колон по Y", 1, 200, 1, true)), h("div", { class: "grid2" }, num("sx", "Крок X", 0.5, 200, 0.5), num("sy", "Крок Y", 0.5, 200, 0.5)), info),
        actions: [
            { label: "Скасувати" },
            {
                label: "Створити",
                cls: "primary",
                id: "dlgColumnGrid",
                onClick: () => {
                    const made = columnGrid({ x0: st.x0, y0: st.y0, nx: Math.round(st.nx), ny: Math.round(st.ny), sx: st.sx, sy: st.sy, existing: items(), idOf: () => uid("bi_") });
                    if (!made.length) {
                        toast("Нових колон немає: у цих точках вони вже стоять.", "warn");
                        return false;
                    }
                    items().push(...made);
                    B.sel = null;
                    commitB(`Колони сіткою: ${made.length}`);
                    toast(`Додано колон: ${made.length}.`);
                    return undefined;
                },
            },
        ],
    });
}

/* ===== панель (ліва вкладка «Будівля») ===== */
const sec = (title, ...kids) => h("div", { class: "sec b5-sec" }, h("h3", null, title), ...kids);
const btn = (label, fn, o = {}) => h("button", { class: "fbtn sm" + (o.cls ? " " + o.cls : ""), type: "button", id: o.id, disabled: o.dis, title: o.title, "aria-pressed": o.pressed == null ? null : String(!!o.pressed), onclick: fn }, o.icon ? ic(o.icon) : null, label);

function contourSection() {
    const ly = bLayer();
    const pts = contour();
    const dis = !contourEditable();
    const explicit = hasExplicitContour();
    const rect = isRectContour(pts) || !explicit;
    const b = contourBbox(pts);
    const kids = [
        h("div", { class: "small", id: "b5Area" }, `Площа ${fmt(polygonArea(pts), 1)} м² · периметр ${fmt(polygonPerimeter(pts), 1)} м${explicit ? "" : " · контур = габарит площадки"}`),
        dis ? h("div", { class: "note lock" }, ic("lock"), " Контур змінює Менеджер.") : null,
        h("div", { class: "frow wrap" }, btn("За складом (+2 м)", () => contourFromWarehouse(2), { dis, id: "btnContourAuto", title: "Контур за розмірами складу з відступом 2 м" }), btn("Стіни по контуру", () => wallsAlongContour(0.3), { dis: !editable(), id: "btnContourWalls" }), explicit ? btn("Скинути", () => { ly.bounds = null; B.sel = null; commitB("Контур скинуто до габариту площадки"); }, { dis, id: "btnContourReset" }) : null),
    ];
    if (rect) {
        const set = (k) => (v) => {
            const c = { x0: b.x0, y0: b.y0, x1: b.x1, y1: b.y1, [k]: v };
            if (c.x1 - c.x0 < 1 || c.y1 - c.y0 < 1) {
                return;
            }
            ly.bounds = rectContour(c.x0, c.y0, c.x1, c.y1);
            liveB();
        };
        const ed = { end: () => commitB("Контур: прямокутник") };
        kids.push(
            h("div", { class: "grid2" }, fld("Від X", numInput({ value: b.x0, dis, step: 0.5, label: "Від X", set: set("x0"), ...ed }), "м"), fld("Від Y", numInput({ value: b.y0, dis, step: 0.5, label: "Від Y", set: set("y0"), ...ed }), "м")),
            h("div", { class: "grid2" }, fld("До X", numInput({ value: b.x1, dis, step: 0.5, label: "До X", set: set("x1"), ...ed }), "м"), fld("До Y", numInput({ value: b.y1, dis, step: 0.5, label: "До Y", set: set("y1"), ...ed }), "м")),
            h("div", { class: "small muted" }, "Прямокутник задається числами; «+ Вершина» перетворює його на многокутник.")
        );
    }
    if (explicit) {
        kids.push(
            h("div", { class: "frow wrap" }, btn("+ Вершина", () => {
                const i = B.sel && B.sel.kind === "vertex" ? B.sel.index : ly.bounds.length - 1;
                const [a, c] = [ly.bounds[i], ly.bounds[(i + 1) % ly.bounds.length]];
                ly.bounds.splice(i + 1, 0, [rnd((a[0] + c[0]) / 2), rnd((a[1] + c[1]) / 2)]);
                B.sel = { kind: "vertex", index: i + 1 };
                commitB("Контур: додано вершину");
            }, { dis, id: "btnVertexPlus" }), btn("Додати вершину", () => setTool("vertex"), { dis, pressed: B.tool === "vertex", id: "btnVertexTool", title: "Клацніть ребро контуру на сцені" })),
            h("div", { class: "b5-verts", id: "b5Verts" }, ly.bounds.map(([x, y], i) => h("div", { class: "frow b5-vrow" + (B.sel && B.sel.kind === "vertex" && B.sel.index === i ? " sel" : "") }, h("a", { href: "#", onclick: (ev) => { ev.preventDefault(); B.sel = { kind: "vertex", index: i }; updateView(); E.syncScene(); renderTab(); } }, "№" + (i + 1)), numInput({ value: x, dis, step: 0.1, label: `Вершина ${i + 1} X`, set: (v) => { ly.bounds[i][0] = v; liveB(); }, end: () => commitB("Контур: вершина") }), numInput({ value: y, dis, step: 0.1, label: `Вершина ${i + 1} Y`, set: (v) => { ly.bounds[i][1] = v; liveB(); }, end: () => commitB("Контур: вершина") }), btn("✕", () => { B.sel = { kind: "vertex", index: i }; deleteSelection(); }, { dis, title: "Видалити вершину (Delete)" }))))
        );
    }
    return sec("Контур", ...K(kids));
}

function heightsSection() {
    const dis = !canManage();
    const bd = S.site.building;
    const bump = () => { liveB(); E.saveSiteProps?.(); };
    return sec(
        "Висоти",
        dis ? h("div", { class: "note lock" }, ic("lock"), " Висоти змінює Менеджер.") : null,
        h("div", { class: "grid2" },
            fld("До стелі", numInput({ value: bd.height, dis, min: 2, max: 60, step: 0.5, label: "Висота до стелі", set: (v) => { bd.height = v; bump(); } }), "м"),
            fld("До спринклерів", numInput({ value: S.site.sprinkler_height || 0, dis, min: 0, max: 60, step: 0.1, label: "Висота до спринклерів", set: (v) => { S.site.sprinkler_height = v; liveB(); saveSiteExtra(); } }), "м")
        ),
        (S.site.sprinkler_height || 0) > bd.height ? h("div", { class: "note err" }, "Спринклери вище стелі.") : h("div", { class: "small muted" }, "0 — спринклерів немає. Лінія спринклерів — помаранчева.")
    );
}

function techSection() {
    const dis = !canManage();
    const [key, custom] = parseTech(S.site.aisle_tech);
    const eff = techMin(S.site.aisle_tech);
    const opts = [["", "Не задано"], ...Object.entries(TECHS).map(([k, [n, m]]) => [k, m ? `${n} · від ${fmt(m, 1)} м` : n])];
    const set = (k, m) => { S.site.aisle_tech = techValue(k || null, m); saveSiteExtra(); liveB(); renderTab(); };
    const live = (v) => { S.site.aisle_tech = techValue(key, v); liveB(); };
    return sec(
        "Техніка складу",
        dis ? h("div", { class: "note lock" }, ic("lock"), " Техніку складу змінює Менеджер.") : null,
        h("div", { class: "grid2" },
            fld("Техніка", selectEl(opts, key || "", (v) => set(v, null), dis, "Техніка складу")),
            fld("Мін. ширина проїзду", numInput({ value: eff ?? "", dis: dis || !key || key === "none", min: 0.5, max: 12, step: 0.1, label: "Мінімальна ширина проїзду", set: live, end: () => { saveSiteExtra(); renderTab(); } }), "м")
        ),
        h("div", { class: "small muted" }, custom ? "Свій мінімум замість умовного для техніки." : "Зона може мати власну техніку (панель зони). Перевірка «Ширина проходу» використовує мінімум."),
        h("div", { class: "frow wrap" }, key ? btn("Скинути мінімум", () => set(key, null), { dis: dis || !custom }) : null)
    );
}

function toolsSection() {
    const dis = !editable();
    return sec(
        "Об'єкти й проходи",
        dis ? h("div", { class: "note lock" }, ic("lock"), " ", bLayer() ? lockHint(bLayer()) : "Шару «Будівля» немає.") : null,
        h("div", { class: "b5-tools", id: "b5Tools" }, TOOLS.map(([k, label]) => btn(label, () => setTool(k), { dis, pressed: B.tool === k, id: "tool-" + k }))),
        h("div", { class: "frow wrap" }, btn("Колони сіткою…", openColumnGrid, { dis, id: "btnColumnGrid" }), btn("Рулетка", () => { const on = !V.ruler.on; E.cancelModes?.(); V.ruler.on = on; B.tool = null; if (on) { toast("Рулетка: клацніть дві точки — відстань і Δx, Δy."); } E.renderVTools?.(); renderTab(); }, { pressed: V.ruler.on, id: "btnRuler" })),
        h("div", { class: "grid3" },
            fld("Товщина стіни", numInput({ value: B.wallTh, dis, min: 0.05, max: 5, step: 0.05, label: "Товщина стіни", set: (v) => { B.wallTh = v; } }), "м"),
            fld("Ширина проходу", numInput({ value: B.aisleW || (bLayer() || {}).aisle_width || 3, dis, min: 0.3, max: 12, step: 0.1, label: "Ширина проходу", set: (v) => { B.aisleW = v; } }), "м"),
            fld("Крок", selectEl([[0.1, "0,1 м"], [0.5, "0,5 м"], [1, "1 м"]], B.step, (v) => { B.step = Number(v); }, false, "Крок прив'язки"))
        ),
        h("div", { class: "small muted" }, "Alt — без прив'язки. Прив'язка: вершини контуру, кути об'єктів, кінці й осі проходів, сітка."),
        h("label", { class: "frow" }, h("input", { type: "checkbox", checked: B.rulers, "aria-label": "Лінійки по краях", onchange: (e) => { B.rulers = e.target.checked; drawRulers(); } }), " Лінійки по краях «Плану»")
    );
}

function itemSection() {
    const it = selItem();
    const a = selAisle();
    const dis = !editable();
    if (!it && !a) {
        const list = items();
        const counts = Object.entries(ITEM_KINDS).map(([k, n]) => [n, list.filter((x) => x.kind === k).length]).filter(([, c]) => c);
        return sec("Вибраний об'єкт", h("div", { class: "small muted" }, "Клацніть об'єкт чи прохід на сцені."), counts.length ? h("div", { class: "small", id: "b5Counts" }, "Усього: " + counts.map(([n, c]) => `${n} — ${c}`).join(" · ")) : h("div", { class: "small muted" }, "Об'єктів будівлі ще немає."));
    }
    if (a) {
        const ax = aisleAxis(a);
        const raw = aisleTechRaw(a);
        const need = techMin(raw);
        const set = (fn, label) => (v) => { fn(v); liveB(); void label; };
        const end = () => commitB(`Прохід: ${a.name}`);
        const linked = aisleLinks(aisles()).filter((l) => l.aisle === a.id || l.host === a.id).length;
        return sec(
            "Вибраний прохід",
            fld("Назва", textInput({ value: a.name, dis, label: "Назва проходу", set: set((v) => { a.name = v.slice(0, 64); }), end })),
            h("div", { class: "grid2" },
                fld("Довжина", numInput({ value: rnd(ax.len, 3), dis, min: 0.5, step: 0.5, label: "Довжина проходу", set: set((v) => { if (ax.dir === "h") { a.x1 = rnd(a.x0 + v); } else { a.y1 = rnd(a.y0 + v); } }), end }), "м"),
                fld("Ширина", numInput({ value: rnd(ax.width, 3), dis, min: 0.3, step: 0.1, label: "Ширина проходу", set: set((v) => { const c = ax.dir === "h" ? ax.cy : ax.cx; if (ax.dir === "h") { a.y0 = rnd(c - v / 2); a.y1 = rnd(c + v / 2); } else { a.x0 = rnd(c - v / 2); a.x1 = rnd(c + v / 2); } }), end }), "м")
            ),
            need != null ? h("div", { class: "small" + (ax.width < need - 0.001 ? " err" : " muted"), id: "b5AisleNeed" }, `Мінімум для техніки: ${fmt(need, 2)} м${ax.width < need - 0.001 ? " — прохід вужчий" : ""}`) : h("div", { class: "small muted" }, "Техніку для перевірки ширини не задано."),
            h("div", { class: "small muted" }, `З'єднань із сусідніми проходами: ${linked}`),
            h("div", { class: "frow" }, h("span", { class: "grow" }), btn("Видалити", deleteSelection, { dis, cls: "danger", icon: "trash", id: "btnItemDelete" }))
        );
    }
    const slotsForLink = S.slots.filter((s) => s.template === "floor_spot" || s.template === "zone");
    const wall = it.kind === "wall";
    const set = (fn) => (v) => { fn(v); liveB(); };
    const end = () => commitB(`Об'єкт: ${it.name || ITEM_KINDS[it.kind]}`);
    return sec(
        `${ITEM_KINDS[it.kind]} ${it.name || ""}`.trim(),
        fld("Назва", textInput({ value: it.name, dis, label: "Назва об'єкта", set: set((v) => { it.name = v.slice(0, 64); }), end })),
        h("div", { class: "grid3" },
            fld("x", numInput({ value: it.x, dis, step: B.step, label: "x", set: set((v) => { it.x = v; }), end }), "м"),
            fld("y", numInput({ value: it.y, dis, step: B.step, label: "y", set: set((v) => { it.y = v; }), end }), "м"),
            fld("Поворот", numInput({ value: it.rot || 0, dis, step: 5, label: "Поворот", set: set((v) => { it.rot = v; }), end }), "°")
        ),
        h("div", { class: "grid2" },
            fld(wall ? "Довжина" : "Ширина", numInput({ value: it.w, dis, min: 0.05, max: 1000, step: 0.1, label: wall ? "Довжина" : "Ширина", set: set((v) => { it.w = v; }), end }), "м"),
            fld(wall ? "Товщина" : "Глибина", numInput({ value: it.d, dis, min: 0.05, max: wall ? 5 : 1000, step: 0.05, label: wall ? "Товщина" : "Глибина", set: set((v) => { it.d = v; if (wall) { it.th = v; } }), end }), "м")
        ),
        LINK_KINDS.includes(it.kind)
            ? h("div", { class: "fcol", id: "b5Link" },
                fld("Пов'язати з локацією", selectEl([["", "— без зв'язку (геометрія) —"], ...slotsForLink.map((s) => [s.id, `${s.code_prefix}${s.template === "zone" ? " · зона" : ""}`])], slotsForLink.some((s) => s.id === it.location_uid) ? it.location_uid : "", (v) => { it.location_uid = v || null; commitB(`Зв'язок: ${it.name}`); }, dis, "Локація")),
                fld("або код локації", textInput({ value: slotsForLink.some((s) => s.id === it.location_uid) ? "" : it.location_uid || "", dis, label: "Код локації", set: (v) => { it.location_uid = v.trim() ? v.trim().slice(0, 64) : null; }, end })),
                h("div", { class: "small muted" }, it.location_uid ? "Зв'язано з локацією." : "Без зв'язку: лише геометрія."))
            : null,
        h("div", { class: "frow" }, h("span", { class: "grow" }), btn("Видалити", deleteSelection, { dis, cls: "danger", icon: "trash", id: "btnItemDelete" }))
    );
}
/** Техніка в центрі проходу за станом редактора (зона з власною технікою → техніка складу). */
function aisleTechRaw(a) {
    const cx = (a.x0 + a.x1) / 2;
    const cy = (a.y0 + a.y1) / 2;
    const zones = S.slots
        .filter((s) => s.template === "zone")
        .map((z) => {
            const w = z.params.length || 1;
            const hh = z.params.width || 1;
            const r = ((z.rotation || 0) * Math.PI) / 180;
            const dx = cx - z.x;
            const dy = cy - z.y;
            const lx = dx * Math.cos(r) + dy * Math.sin(r);
            const ly = -dx * Math.sin(r) + dy * Math.cos(r);
            return { z, inside: Math.abs(lx) <= w / 2 && Math.abs(ly) <= hh / 2, area: w * hh };
        })
        .filter((c) => c.inside && c.z.tech)
        .sort((p, q) => p.area - q.area);
    return zones.length ? zones[0].z.tech : S.site.aisle_tech || null;
}

function checksSection() {
    const dis = !canManage();
    const cfg = S.settings.checks;
    const save = (id) => {
        const c = cfg[id];
        const a = E.adapter;
        if (a.kind === "odoo" && c.id == null && typeof a.queue === "function") {
            a.queue({ model: "td.check.config", op: "create", uid: id, vals: { check_key: id, enabled: c.enabled, mode: c.mode, params: c.params || {} } });
            c.id = -1;
        } else {
            a.saveCheck(id, { enabled: c.enabled, mode: c.mode, params: c.params || {} });
        }
        E.commit({});
    };
    const issues = (S.issues.list || []).filter((i) => CHECK_IDS.includes(i.check));
    return sec(
        "Перевірки будівлі",
        dis ? h("div", { class: "note lock" }, ic("lock"), " Налаштування змінює Менеджер.") : null,
        CHECK_IDS.map((id) => {
            const cur = cfg[id] || { enabled: false, mode: "warn", params: {}, id: null };
            const ensure = () => (cfg[id] ||= { enabled: false, mode: "warn", params: {}, id: null });
            return h("div", { class: "frow", style: { margin: "5px 0" }, title: CHECK_NAMES[id][1] },
                h("input", { type: "checkbox", checked: !!cur.enabled && !!cfg[id], disabled: dis, "aria-label": CHECK_NAMES[id][0], "data-check": id, onchange: (e) => { ensure().enabled = e.target.checked; save(id); } }),
                h("span", { style: { flex: 1, minWidth: 0 } }, CHECK_NAMES[id][0]),
                selectEl([["warn", "Попередження"], ["block", "Заборона"]], cur.mode, (v) => { ensure().mode = v; save(id); }, dis, CHECK_NAMES[id][0]));
        }),
        issues.length
            ? h("div", { class: "b5-issues", id: "b5Issues" }, issues.slice(0, 12).map((i) => h("div", { class: "small " + (i.level === "block" ? "err" : "warn"), title: i.check }, i.msg)), issues.length > 12 ? h("div", { class: "small muted" }, `…і ще ${issues.length - 12}`) : null)
            : h("div", { class: "small muted" }, "Зауважень за ввімкненими перевірками будівлі немає.")
    );
}

function docsSection() {
    return sec(
        "Документи",
        h("div", { class: "frow wrap" }, btn("Специфікація стелажів…", () => E.runDialog("spec"), { id: "btnSpecDoc" }), btn("План…", () => E.runDialog("planDoc"), { id: "btnPlanDoc" }))
    );
}

export function renderBuildingTab(root) {
    if (!S.site) {
        return;
    }
    if (!bLayer()) {
        root.append(sec("Будівля", h("div", { class: "note" }, "На площадці немає шару «Будівля»: створіть його у вкладці «Шари».")));
        return;
    }
    root.append(
        ...K(
            sec("Режим «Будівля»", h("div", { class: "small muted" }, B.on ? "Правка будівлі: клацання по сцені обробляє цей режим. Звичайна правка вимкнена." : "Режим вимкнено. Він взаємовиключний з «Редагувати»."), h("div", { class: "frow wrap" }, btn(B.on ? "Вийти з режиму «Будівля»" : "Увімкнути режим «Будівля»", toggleBuilding, { cls: B.on ? "" : "primary", id: "btnBuildingToggle" }))),
            B.on ? K(contourSection(), heightsSection(), toolsSection(), itemSection(), techSection(), checksSection(), docsSection()) : K(docsSection())
        )
    );
}
registries.panels.add("left:building", { area: "left", tab: "building", label: "Будівля", render: renderBuildingTab }, { sequence: 15, force: true });

const renderTab = () => {
    if (ROOT.el && S.ui.leftTab === "building") {
        E.renderLeft?.();
    }
};

/* ===== техніка зони (N-06): блок у властивостях зони ===== */
registries.panels.add(
    "slot:tech",
    {
        area: "slot",
        when: ({ rec }) => !!rec && rec.template === "zone",
        render(root, { rec }) {
            const dis = !canEditLayer(layerOf(rec.layer_id));
            const [key, custom] = parseTech(rec.tech);
            const eff = techMin(rec.tech);
            const opts = [["", "Як у складу"], ...Object.entries(TECHS).map(([k, [n, m]]) => [k, m ? `${n} · від ${fmt(m, 1)} м` : n])];
            const set = (k, m) => { rec.tech = techValue(k || null, m); E.commit({ label: `Техніка зони: ${rec.params.title || rec.code_prefix}` }); };
            root.append(
                h("div", { class: "sec", id: "zoneTech" },
                    h("h3", null, "Техніка зони"),
                    h("div", { class: "grid2" },
                        fld("Техніка", selectEl(opts, key || "", (v) => set(v, null), dis, "Техніка зони")),
                        fld("Мін. ширина проїзду", numInput({ value: eff ?? "", dis: dis || !key || key === "none", min: 0.5, max: 12, step: 0.1, label: "Мінімальна ширина проїзду зони", set: (v) => { rec.tech = techValue(key, v); }, end: () => E.commit({ label: `Техніка зони: ${rec.params.title || rec.code_prefix}` }) }), "м")),
                    h("div", { class: "small muted" }, custom ? "Свій мінімум для зони." : "Для проходів і рядів у зоні діє мінімум цієї техніки (N-06).")
                )
            );
        },
    },
    { sequence: 60, force: true }
);

/* ===== кнопка режиму поруч із 3D/План, лінійки, підписи ===== */
const STYLE_ID = "f3d-s5-style";
const CSS = `
.b5-sec .b5-tools{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:4px;margin:6px 0}
.b5-sec .b5-verts{max-height:150px;overflow:auto;margin:4px 0}
.b5-sec .b5-vrow{gap:4px;margin:2px 0}.b5-sec .b5-vrow.sel{background:var(--warn-soft)}
.b5-sec .b5-vrow input{min-width:0;width:80px}
.b5-sec .b5-issues{margin-top:6px;max-height:140px;overflow:auto}
.b5-sec .err{color:var(--err,#b3261e)}.b5-sec .warn{color:var(--warn,#8a5a00)}
.b5-rx,.b5-ry{position:absolute;z-index:2;pointer-events:none;background:color-mix(in srgb,var(--surface) 88%,transparent)}
.b5-rx{left:0;right:0;top:0;height:18px;border-bottom:1px solid var(--line)}
.b5-ry{left:0;top:0;bottom:0;width:30px;border-right:1px solid var(--line)}
#vtools .b5-mode[aria-pressed="true"]{background:var(--ink);color:var(--surface)}
.b5-doc .b5-prev{border:1px solid var(--line);background:#fff;max-height:60vh;overflow:auto;padding:4px}
.b5-doc .b5-prev svg{max-width:100%;height:auto;display:block}
.b5-doc table.b5-t{border-collapse:collapse;width:100%;font-size:12px}
.b5-doc table.b5-t th,.b5-doc table.b5-t td{border:1px solid var(--line);padding:2px 6px;text-align:left}
.b5-doc table.b5-t td.n{text-align:right}
.b5-wiz .b5-steps{display:flex;gap:4px;flex-wrap:wrap;margin-bottom:8px}
.b5-wiz .b5-step{padding:3px 8px;border:1px solid var(--line);font-size:12px}
.b5-wiz .b5-step.on{background:var(--ink);color:var(--surface)}.b5-wiz .b5-step.done{border-color:var(--ink)}
`;
export function ensureStyle() {
    const root = ROOT.el;
    if (!root || root.querySelector("#" + STYLE_ID)) {
        return;
    }
    const st = document.createElement("style");
    st.id = STYLE_ID;
    st.textContent = CSS;
    root.prepend(st);
}

function renderVToolsButton() {
    const box = $("#vtools");
    if (!box) {
        return;
    }
    let b = $("#btnBuildingMode");
    if (!b) {
        b = h("button", { class: "fbtn b5-mode", type: "button", id: "btnBuildingMode", title: "Режим «Будівля»: контур, колони, стіни, проходи (взаємовиключний з «Редагувати»)", "aria-label": "Будівля", onclick: toggleBuilding }, ic("plan"), h("span", { class: "lg" }, "Будівля"));
        const second = box.children[1];
        if (second) {
            second.after(b);
        } else {
            box.append(b);
        }
    }
    b.setAttribute("aria-pressed", String(B.on));
}
function decorate() {
    ensureStyle();
    renderVToolsButton();
    const edit = $('#modeSeg button[data-mode="edit"]');
    if (edit && B.on) {
        edit.setAttribute("aria-pressed", "false"); // «Будівля» і «Редагувати» взаємовиключні
    }
    if (B.on && S.site && B.siteId !== S.site.id) {
        exitBuilding(); // площадку перемкнено
    }
}

/* ===== лінійки по краях «Плану» (F18-07) ===== */
function niceStep(pxPerM, min = 60) {
    for (const s of [0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100]) {
        if (s * pxPerM >= min) {
            return s;
        }
    }
    return 100;
}
function drawRulers(cursorOnly) {
    const center = ROOT.el && ROOT.el.querySelector(".center");
    let rx = $("#b5Rx");
    let ry = $("#b5Ry");
    const show = !!(B.on || B.rulers) && V.ok && V.camMode === "plan" && !V.testMode;
    if (!center || !show) {
        rx?.remove();
        ry?.remove();
        return;
    }
    if (!rx) {
        rx = h("canvas", { class: "b5-rx", id: "b5Rx" });
        ry = h("canvas", { class: "b5-ry", id: "b5Ry" });
        center.append(rx, ry);
    }
    const w = center.clientWidth;
    const hh = center.clientHeight;
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    const size = (c, cw, ch) => {
        if (c.width !== cw * dpr || c.height !== ch * dpr) {
            c.width = cw * dpr;
            c.height = ch * dpr;
            c.style.width = cw + "px";
            c.style.height = ch + "px";
        }
    };
    size(rx, w, 18);
    size(ry, 30, hh);
    const proj = (x, y) => {
        const v = new THREE.Vector3(x, 0, -y).project(V.camera);
        return [((v.x + 1) / 2) * w, ((1 - v.y) / 2) * hh];
    };
    const t = V.controls.target;
    const [ox, oy] = proj(t.x, -t.z);
    const pxX = Math.abs(proj(t.x + 1, -t.z)[0] - ox);
    const pxY = Math.abs(proj(t.x, -t.z + 1)[1] - oy);
    if (!pxX || !pxY) {
        return;
    }
    const css = getComputedStyle(center);
    const ink = css.getPropertyValue("--ink").trim() || "#222";
    const cx = rx.getContext("2d");
    const cy = ry.getContext("2d");
    for (const c of [cx, cy]) {
        c.setTransform(dpr, 0, 0, dpr, 0, 0);
        c.clearRect(0, 0, w, hh);
        c.strokeStyle = ink;
        c.fillStyle = ink;
        c.font = "10px sans-serif";
        c.lineWidth = 1;
    }
    const sx = niceStep(pxX);
    const sy = niceStep(pxY, 40);
    const x0 = t.x + (0 - ox) / pxX;
    const x1 = t.x + (w - ox) / pxX;
    for (let x = Math.ceil(x0 / sx) * sx; x <= x1; x += sx) {
        const px = ox + (x - t.x) * pxX;
        cx.beginPath();
        cx.moveTo(px + 0.5, 12);
        cx.lineTo(px + 0.5, 18);
        cx.stroke();
        cx.fillText(String(rnd(x, 2)), px + 2, 10);
    }
    const yTop = -t.z + (oy - 0) / pxY;
    const yBot = -t.z - (hh - oy) / pxY;
    for (let y = Math.ceil(yBot / sy) * sy; y <= yTop; y += sy) {
        const py = oy - (y + t.z) * pxY;
        cy.beginPath();
        cy.moveTo(24, py + 0.5);
        cy.lineTo(30, py + 0.5);
        cy.stroke();
        cy.fillText(String(rnd(y, 2)), 1, py - 2);
    }
    const cur = B.cursor || V.cursor;
    if (cur) {
        cx.strokeStyle = "#e11d74";
        cx.beginPath();
        cx.moveTo(ox + (cur.x - t.x) * pxX + 0.5, 0);
        cx.lineTo(ox + (cur.x - t.x) * pxX + 0.5, 18);
        cx.stroke();
        cy.strokeStyle = "#e11d74";
        const py = oy - (cur.y + t.z) * pxY;
        cy.beginPath();
        cy.moveTo(0, py + 0.5);
        cy.lineTo(30, py + 0.5);
        cy.stroke();
    }
    void cursorOnly;
}

/* ===== життєвий цикл ===== */
let mo = null;
function onMount() {
    Object.assign(B, { on: false, tool: null, sel: null, pend: null, drag: null, down: null, prev: null, siteId: null, cur: null });
    ensureStyle();
    renderVToolsButton();
    const cv = V.canvas;
    if (cv) {
        cv.addEventListener("pointerdown", onDown, true); // фаза захоплення: до обробника сцени й орбітальних контролів
        cv.addEventListener("pointermove", onMove, true);
        cv.addEventListener("pointerup", onUp, true);
        cv.addEventListener("pointercancel", onUp, true);
        V.controls?.addEventListener("change", () => drawRulers());
    }
    const seg = $("#modeSeg");
    if (seg) {
        seg.addEventListener(
            "click",
            (e) => {
                if (e.target.closest("button[data-mode]") && B.on) {
                    exitBuilding(); // «Перегляд» чи «Редагування» виводять із режиму «Будівля»
                }
            },
            true
        );
    }
    const vt = $("#vtools");
    if (vt && typeof MutationObserver !== "undefined") {
        mo = new MutationObserver(() => {
            if (!$("#btnBuildingMode")) {
                renderVToolsButton();
            }
        });
        mo.observe(vt, { childList: true });
    }
    if (typeof ResizeObserver !== "undefined" && cv) {
        new ResizeObserver(() => drawRulers()).observe(cv);
    }
}
function onUnmount() {
    mo?.disconnect();
    mo = null;
    Object.assign(B, { on: false, tool: null, sel: null, pend: null, drag: null, down: null, prev: null });
}
E.lifecycle.mount.add(onMount);
E.lifecycle.unmount.add(onUnmount);

// оновлення елементів режиму після кожного E.renderAll / E.setView / E.cancelModes (спільні файли не змінюються: обгортки, як у S3)
const origRenderAll = E.renderAll;
E.renderAll = function renderAllS5(...a) {
    const r = origRenderAll.apply(this, a);
    try {
        decorate();
        drawRulers();
    } catch (e) {
        console.error("S5 режим «Будівля»:", e);
    }
    return r;
};
const origSetView = E.setView;
E.setView = function setViewS5(...a) {
    const r = origSetView.apply(this, a);
    try {
        drawRulers();
    } catch (e) {
        console.error("S5 лінійки:", e);
    }
    return r;
};
const origCancel = E.cancelModes;
E.cancelModes = function cancelModesS5(...a) {
    B.tool = null;
    B.pend = null;
    B.drag = null;
    setOverlay(null);
    return origCancel ? origCancel.apply(this, a) : undefined;
};

registries.hotkeys.add(
    "building_escape",
    {
        key: "Escape",
        typing: true,
        run() {
            if (!B.on || !(B.tool || B.pend || B.sel)) {
                return false;
            }
            if (B.pend) {
                B.pend = null;
            } else if (B.tool) {
                B.tool = null;
            } else {
                B.sel = null;
            }
            setOverlay(null);
            updateView();
            E.syncScene();
            renderTab();
            renderVToolsButton();
            return true;
        },
    },
    { sequence: 8, force: true }
);
registries.hotkeys.add(
    "building_delete",
    {
        match: (e) => e.code === "Delete" || e.code === "Backspace",
        when: () => B.on && !!B.sel,
        run: (e) => (e.preventDefault(), deleteSelection()),
    },
    { sequence: 9, force: true }
);
registries.menu.add("building", { area: "more", label: "Будівля (режим)", icon: "plan", sequence: 20, run: () => toggleBuilding() }, { sequence: 20, force: true });

Object.assign(E, { enterBuilding, exitBuilding, toggleBuilding, buildingState: B, deleteBuildingSelection: deleteSelection, openColumnGrid, wallsAlongContour, contourFromWarehouse });
