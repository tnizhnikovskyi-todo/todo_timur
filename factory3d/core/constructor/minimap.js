// Мініатюра плану (F19 «мініатюра», N-01): контур будівлі, зони, місця й обладнання видимих шарів у плані з рамкою поточного виду;
// клік чи перетягування по мініатюрі переносить камеру (`E.focusOn`). Малюється на canvas після кожного кадру сцени (хук collab_ui),
// без змін scene.js. У 2D і 3D однакова: рамка — проєкція кутів екрана на підлогу.
import { slotObb } from "./cells.js";
import { addFrameHook, centerEl, ensureStyle } from "./collab_ui.js";
import { obbCorners, placementObb } from "./geometry.js";
import { addEn, t } from "./i18n.js";
import { E, S, V, variantOf } from "./state.js";
import { THREE } from "./three.js";
import { $, h } from "./util.js";

const W = 168;
const MAXH = 120;
const FAR = 400;

/** Проєкція кутів екрана на площину підлоги: чотири точки плану (x, y) у метрах; промені над горизонтом обрізаються за `FAR`. */
export function viewFootprint(camera) {
    if (!camera || !THREE.Vector3) {
        return null;
    }
    const o = camera.position.clone();
    const pts = [];
    for (const [nx, ny] of [[-1, -1], [1, -1], [1, 1], [-1, 1]]) {
        const d = new THREE.Vector3(nx, ny, 0.5).unproject(camera).sub(o).normalize();
        let k = d.y < -1e-4 ? -o.y / d.y : FAR;
        k = Math.min(Math.max(k, 0), FAR);
        pts.push([o.x + d.x * k, -(o.z + d.z * k)]);
    }
    return pts;
}

/** Масштаб мініатюри: {k (px/м), w, h} за габаритом будівлі. */
export function miniScale(B, maxW = W, maxH = MAXH) {
    const k = Math.min(maxW / (B.length || 1), maxH / (B.width || 1));
    return { k, w: Math.round(B.length * k), h: Math.round(B.width * k) };
}
/** Піксель мініатюри → точка плану (метри). */
export const miniToWorld = (px, py, B, sc) => ({ x: Math.max(0, Math.min(B.length, px / sc.k)), y: Math.max(0, Math.min(B.width, (sc.h - py) / sc.k)) });

let canvas = null;
let drag = false;

function ensureMini() {
    const c = centerEl();
    if (!c) {
        return null;
    }
    let box = c.querySelector("#s6Mini");
    if (!box) {
        canvas = h("canvas", { width: W, height: 90, id: "s6MiniCanvas", "aria-label": t("Мініатюра плану: клік переносить камеру"), role: "img" });
        box = h("div", { class: "s6-mini", id: "s6Mini", title: t("Мініатюра плану: клік переносить камеру") }, canvas);
        const move = (e) => {
            const r = canvas.getBoundingClientRect();
            const B = S.site.building;
            const sc = miniScale(B);
            const p = miniToWorld(((e.clientX - r.left) / r.width) * canvas.width, ((e.clientY - r.top) / r.height) * canvas.height, B, sc);
            E.focusOn?.(p.x, p.y);
        };
        canvas.addEventListener("pointerdown", (e) => {
            drag = true;
            canvas.setPointerCapture?.(e.pointerId);
            move(e);
        });
        canvas.addEventListener("pointermove", (e) => drag && move(e));
        canvas.addEventListener("pointerup", () => (drag = false));
        canvas.addEventListener("pointercancel", () => (drag = false));
        c.append(box);
    }
    canvas = box.querySelector("canvas");
    return box;
}

const css = (name, fallback) => (getComputedStyle(ROOTEL()).getPropertyValue(name) || fallback).trim() || fallback;
const ROOTEL = () => centerEl() || document.body;

/** Малює многокутник (точки плану → пікселі); повертає чи намалював. */
function poly(g, pts, X, Y, fill) {
    if (!pts || pts.length < 3) {
        return false;
    }
    g.beginPath();
    pts.forEach(([x, y], i) => (i ? g.lineTo(X(x), Y(y)) : g.moveTo(X(x), Y(y))));
    g.closePath();
    if (fill) {
        g.fill();
    }
    return true;
}

function draw() {
    const box = $("#s6Mini");
    if (!box || !S.site || box.hidden) {
        return;
    }
    const B = S.site.building;
    const sc = miniScale(B);
    if (canvas.width !== sc.w || canvas.height !== sc.h) {
        canvas.width = sc.w;
        canvas.height = sc.h;
    }
    const g = canvas.getContext("2d");
    const ink = css("--ink", "#1f2933");
    g.clearRect(0, 0, sc.w, sc.h);
    g.fillStyle = css("--surface2", "#f2f4f6");
    g.fillRect(0, 0, sc.w, sc.h);
    const X = (x) => x * sc.k;
    const Y = (y) => sc.h - y * sc.k;
    const layers = new Map(S.layers.map((l) => [l.id, l]));
    for (const s of S.slots) {
        const ly = layers.get(s.layer_id);
        if (!ly || (V.hidden && V.hidden.has(ly.id)) || ly.kind === "building") {
            continue;
        }
        if (E.objVisible && !E.objVisible("slot", s.id)) {
            continue;
        }
        g.fillStyle = ly.color || "#888";
        if (s.template === "zone") {
            g.globalAlpha = 0.12;
            poly(g, s.params && s.params.polygon, X, Y, true);
            g.globalAlpha = 1;
            continue;
        }
        let pts = null;
        try {
            pts = obbCorners(slotObb(s.template, s.params || {}, s.x, s.y, s.rotation || 0));
        } catch {
            pts = null;
        }
        poly(g, pts, X, Y, true);
    }
    for (const p of S.placements) {
        const ly = layers.get(p.layer_id);
        if (!ly || (V.hidden && V.hidden.has(ly.id)) || (E.objVisible && !E.objVisible("placement", p.id))) {
            continue;
        }
        g.fillStyle = ly.color || "#557";
        const v = variantOf(p.variant_id);
        let pts = null;
        try {
            pts = v ? obbCorners(placementObb(v, p.x, p.y, p.rotation || 0)) : null;
        } catch {
            pts = null;
        }
        if (!poly(g, pts, X, Y, true)) {
            g.fillRect(X(p.x) - 1.5, Y(p.y) - 1.5, 3, 3);
        }
    }
    g.strokeStyle = ink;
    g.lineWidth = 1;
    g.strokeRect(0.5, 0.5, sc.w - 1, sc.h - 1);
    const sel = S.sel && (S.sel.kind === "slot" ? S.sIdx : S.pIdx).get(S.sel.id);
    if (sel) {
        g.strokeStyle = css("--accent", "#0e7c86");
        g.lineWidth = 2;
        g.strokeRect(X(sel.x) - 4, Y(sel.y) - 4, 8, 8);
    }
    const fp = V.ok && viewFootprint(V.camera);
    if (fp) {
        g.strokeStyle = "#e11d48";
        g.lineWidth = 1.5;
        g.beginPath();
        fp.forEach(([x, y], i) => (i ? g.lineTo(X(x), Y(y)) : g.moveTo(X(x), Y(y))));
        g.closePath();
        g.stroke();
    }
}

export function renderMini() {
    const box = ensureMini();
    if (box) {
        box.hidden = S.ui.minimap === false;
        draw();
    }
}

export function toggleMini(on = S.ui.minimap === false) {
    S.ui.minimap = !!on;
    renderMini();
}

E.lifecycle.mount.add(() => {
    ensureStyle();
    ensureMini();
    addFrameHook("minimap", draw);
    renderMini();
    E.requestRender?.();
});
E.lifecycle.unmount.add(() => {
    canvas = null;
    drag = false;
});

Object.assign(E, { renderMini, toggleMini, miniViewFootprint: viewFootprint });

addEn({ "Мініатюра плану: клік переносить камеру": "Minimap: click to move the camera", "Мініатюра": "Minimap" });
