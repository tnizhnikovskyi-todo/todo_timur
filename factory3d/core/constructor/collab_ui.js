// Спільна основа інтерфейсу слайса S6 (F12–F14, F19, N-01, N-03): стилі (вбудовано, як у s3_chrome.js — один код у модулі й прототипі),
// шар накладок над 3D-сценою, проєкція точок сцени на екран і хук «після кожного кадру» (`V.renderer.render` обгортається один раз:
// значки коментарів, блокувань і мініатюра плану оновлюються разом зі сценою, не змінюючи scene.js).
import { E, V } from "./state.js";
import { THREE } from "./three.js";
import { ROOT } from "./util.js";

const STYLE_ID = "f3d-s6-style";
const CSS = `
.s6-layer{position:absolute;inset:0;pointer-events:none;z-index:2;overflow:hidden}
.s6-badge{position:absolute;left:0;top:0;pointer-events:auto;cursor:pointer;min-width:22px;height:22px;padding:0 6px;border-radius:11px;border:2px solid var(--surface);color:#fff;font:600 12px/18px var(--sans,system-ui);text-align:center;box-shadow:0 1px 4px rgba(0,0,0,.35);transform:translate(-50%,-100%)}
.s6-badge[data-tone="note"]{background:#2563eb}
.s6-badge[data-tone="task"]{background:#ea8a1a}
.s6-badge[data-tone="done"]{background:#8b8b8b}
.s6-badge:hover,.s6-badge:focus-visible{outline:2px solid var(--ink);z-index:3}
.s6-lockb{position:absolute;left:0;top:0;pointer-events:auto;padding:1px 7px;border-radius:3px;border:1px solid var(--surface);color:#fff;font:600 11px/17px var(--sans,system-ui);white-space:nowrap;box-shadow:0 1px 4px rgba(0,0,0,.3);transform:translate(-50%,-50%)}
.s6-lockb[data-mine="1"]{background:#15803d}
.s6-lockb[data-mine="0"]{background:#b91c1c}
.s6-panel{display:flex;flex-direction:column;gap:6px}
.s6-row{display:flex;gap:6px;align-items:center;flex-wrap:wrap}
.s6-row.sp{justify-content:space-between}
.s6-item{border:1px solid var(--line2,var(--line));background:var(--surface);padding:6px 8px;display:flex;flex-direction:column;gap:4px}
.s6-item[data-active="1"]{border-color:var(--accent);background:var(--accent-soft)}
.s6-item.res{opacity:.7}
.s6-tag{display:inline-block;border:1px solid var(--line);padding:0 5px;font-size:11px;color:var(--ink2);background:var(--surface2,var(--surface))}
.s6-tag.ok{border-color:var(--accent);color:var(--accent)}
.s6-tag.warn{border-color:var(--warn);color:var(--warn);background:var(--warn-soft)}
.s6-muted{color:var(--ink2);font-size:12px}
.s6-text{white-space:pre-wrap;word-break:break-word;font-size:13px}
.s6-cmp{width:100%;border-collapse:collapse;font-size:12px}
.s6-cmp th,.s6-cmp td{border-bottom:1px solid var(--line2,var(--line));padding:3px 5px;text-align:right}
.s6-cmp th:first-child,.s6-cmp td:first-child{text-align:left}
.s6-cmp .pos{color:#15803d}.s6-cmp .neg{color:#b91c1c}
#ltabs{flex-wrap:wrap}
.s6-dock{flex:none;max-height:46%;overflow:auto;border-top:1px solid var(--line);padding:8px 12px 10px;background:var(--surface)}
.s6-dock[hidden]{display:none}
.s6-train{position:absolute;left:50%;top:76px;transform:translateX(-50%);z-index:4;background:var(--warn-soft);color:var(--ink);border:1px solid var(--warn);padding:6px 10px;display:flex;gap:8px;align-items:center;flex-wrap:wrap;max-width:calc(100% - 24px);box-shadow:0 2px 10px rgba(0,0,0,.2)}
.s6-train[hidden]{display:none}
.s6-crumbs{position:absolute;left:8px;top:44px;z-index:3;display:flex;gap:2px;align-items:center;flex-wrap:wrap;background:var(--surface);border:1px solid var(--line);padding:2px 4px;font-size:12px;max-width:calc(100% - 200px)}
.s6-crumbs[hidden]{display:none}
.s6-crumbs,.s6-pick{pointer-events:none}
.s6-crumbs button,.s6-pick select,.s6-pick button,.s6-pick label{pointer-events:auto}
.s6-crumbs button{border:0;background:transparent;padding:2px 5px;cursor:pointer;color:var(--ink);font:inherit}
.s6-crumbs button:hover{background:var(--accent-soft)}
.s6-crumbs button[aria-current="true"]{font-weight:700}
.s6-crumbs .sep{color:var(--ink2)}
.s6-pick{position:absolute;left:8px;top:76px;z-index:3;display:flex;gap:6px;align-items:center;background:var(--surface);border:1px solid var(--line);padding:2px 6px;font-size:12px}
.s6-pick select{min-height:24px;font-size:12px}
.s6-mini{position:absolute;right:8px;top:44px;z-index:3;border:1px solid var(--ink);background:var(--surface);padding:2px}
.s6-mini canvas{display:block;cursor:crosshair}
.s6-mini[hidden]{display:none}
.s6-tour-dim{position:absolute;inset:0;z-index:50;pointer-events:auto;background:transparent}
.s6-tour-hole{position:fixed;z-index:51;border:2px solid var(--accent);border-radius:3px;box-shadow:0 0 0 9999px rgba(0,0,0,.45);pointer-events:none;transition:all .15s}
.s6-tour-card{position:fixed;z-index:52;width:min(340px,calc(100% - 16px));background:var(--surface);color:var(--ink);border:1px solid var(--ink);box-shadow:0 8px 28px rgba(0,0,0,.4);padding:10px 12px;display:flex;flex-direction:column;gap:6px}
.s6-tour-card h3{margin:0;font-size:14px}
.s6-tour-card .body{font-size:13px;line-height:1.45}
.s6-tour-card .kind{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--accent)}
.s6-help{display:grid;grid-template-columns:200px minmax(0,1fr);gap:10px;min-height:320px;max-height:60vh}
.s6-help nav{overflow:auto;border:1px solid var(--line2,var(--line));display:flex;flex-direction:column}
.s6-help nav button{border:0;border-bottom:1px solid var(--line2,var(--line));background:var(--surface);text-align:left;padding:6px 8px;cursor:pointer;font-size:12px;color:var(--ink)}
.s6-help nav button[aria-current="true"]{background:var(--accent-soft);font-weight:700}
.s6-help article{overflow:auto;font-size:13px;line-height:1.5;padding-right:4px}
.s6-plan{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.s6-plan svg{width:100%;height:auto;border:1px solid var(--line);background:var(--surface)}
@media (max-width:768px){.s6-help{grid-template-columns:1fr}.s6-crumbs{top:6px;max-width:calc(100% - 12px)}.s6-pick,.s6-mini,.s6-train{display:none}}
`;

/** Вбудовує стилі S6 у корінь редактора (один раз на монтування). */
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

export const centerEl = () => ROOT.el?.querySelector(".center") || null;

/** Шар накладок над сценою з потрібним id (створюється при першому зверненні). */
export function layerEl(id, tag = "div") {
    const c = centerEl();
    if (!c) {
        return null;
    }
    let el = c.querySelector("#" + id);
    if (!el) {
        el = document.createElement(tag);
        el.id = id;
        el.className = "s6-layer";
        c.append(el);
    }
    return el;
}

/** Екранна точка світової (x, y — план у метрах, z — висота): {x, y, ok} відносно кута сцени; ok — в межах кадру й перед камерою. */
export function project(x, y, z = 0) {
    const host = ROOT.el?.querySelector("#vp");
    if (!V.ok || !V.camera || !host || !THREE.Vector3) {
        return { x: 0, y: 0, ok: false };
    }
    const w = host.clientWidth;
    const hh = host.clientHeight;
    const p = new THREE.Vector3(x, z, -y).project(V.camera);
    const sx = (p.x * 0.5 + 0.5) * w;
    const sy = (-p.y * 0.5 + 0.5) * hh;
    return { x: sx, y: sy, ok: p.z > -1 && p.z < 1 && sx > -20 && sx < w + 20 && sy > -20 && sy < hh + 20 };
}

/* ---------- хуки кадру: `pre` — перед малюванням (видимість об'єктів), решта — після (накладки) ---------- */
const hooks = new Map();
export function addFrameHook(key, fn, { pre = false } = {}) {
    hooks.set(key, { fn, pre });
    installRenderHook();
}
export function removeFrameHook(key) {
    hooks.delete(key);
}
export function installRenderHook() {
    const r = V.renderer;
    if (!r || r.__s6) {
        return;
    }
    const orig = r.render.bind(r);
    const run = (pre) => {
        for (const [key, hook] of hooks) {
            if (hook.pre === pre) {
                try {
                    hook.fn();
                } catch (e) {
                    console.error(`S6 кадр «${key}»:`, e);
                }
            }
        }
    };
    r.render = function renderS6(scene, camera) {
        run(true);
        orig(scene, camera);
        run(false);
    };
    r.__s6 = true;
}
/** Просить перемалювати накладки: кадр сцени + хуки. */
export const redrawOverlays = () => E.requestRender?.();

E.lifecycle.mount.add(() => {
    ensureStyle();
    installRenderHook();
    redrawOverlays();
});
E.lifecycle.unmount.add(() => hooks.clear());
