/** @odoo-module */
// Підкладка DXF (CD-09, R-22): розбір DXF у відрізки (dxf-parser 1.1.2, ліниво, окремим script), панель підкладки, прив'язка масштабу.
// Файл зберігається вкладенням шару (`underlay_attachment_id`), параметри — `underlay_params` {unit, dx, dy, rot_deg, scale, opacity}.
import { fld, numInput } from "./fields";
import { canEditLayer, lockHint } from "./roles";
import { E, S, V, layerOf } from "./state";
import { $, K, fmt, fmtInt, h, ic, rad, rnd, toast } from "./util";

export const DXF_PARSER_URL = "/factory3d_constructor/static/lib/dxf-parser/dxf-parser.min.js";
export const DXF_MAX_BYTES = 5 * 1024 * 1024;
export const DXF_MAX_SEGMENTS = 200000;
export const DWG_MESSAGE = "Конвертуйте в DXF; DWG буде на сервері.";

let parserPromise = null;
/** Підвантажує dxf-parser (глобал `DxfParser`) один раз; без залежностей від Odoo (CD-29: ядро редактора окреме від адаптера). */
export function loadDxfParser() {
    if (window.DxfParser) {
        return Promise.resolve(window.DxfParser);
    }
    if (!parserPromise) {
        parserPromise = new Promise((resolve, reject) => {
            const el = document.createElement("script");
            el.src = DXF_PARSER_URL;
            el.onload = () => resolve(window.DxfParser);
            el.onerror = () => {
                parserPromise = null;
                reject(new Error("Не вдалося завантажити розбирач DXF."));
            };
            document.head.append(el);
        });
    }
    return parserPromise;
}

/**
 * DXF (текст) → {segs: Float32Array [x1,y1,x2,y2,…] у одиницях файла, n, bbox, truncated}.
 * Підтримано LINE, LWPOLYLINE, POLYLINE (з bulge), CIRCLE, ARC, INSERT (блоки до 3 рівнів).
 * @param {string} text
 * @param {Function} [Parser] клас DxfParser (за замовчуванням — глобал)
 */
export function parseDxf(text, Parser = window.DxfParser) {
    const dxf = new Parser().parseSync(text);
    const segs = [];
    const line = (x1, y1, x2, y2) => segs.push(x1, y1, x2, y2);
    const arc = (c, r, a0, a1, T) => {
        if (a1 <= a0) {
            a1 += Math.PI * 2;
        }
        const n = Math.max(8, Math.ceil((a1 - a0) / (Math.PI / 24)));
        let px = null;
        let py = null;
        for (let i = 0; i <= n; i++) {
            const a = a0 + ((a1 - a0) * i) / n;
            const p = T(c.x + r * Math.cos(a), c.y + r * Math.sin(a));
            if (px != null) {
                line(px, py, p[0], p[1]);
            }
            px = p[0];
            py = p[1];
        }
    };
    const bulgeArc = (p, q, b, T) => {
        const dx = q.x - p.x;
        const dy = q.y - p.y;
        const d = Math.hypot(dx, dy);
        if (d < 1e-9) {
            return;
        }
        const th = 4 * Math.atan(b);
        const r = d / (2 * Math.sin(th / 2));
        const off = r * Math.cos(th / 2);
        const cx = (p.x + q.x) / 2 - (dy / d) * off;
        const cy = (p.y + q.y) / 2 + (dx / d) * off;
        const a0 = Math.atan2(p.y - cy, p.x - cx);
        const n = Math.max(6, Math.ceil(Math.abs(th) / (Math.PI / 24)));
        let px = null;
        let py = null;
        for (let i = 0; i <= n; i++) {
            const a = a0 + (th * i) / n;
            const pt = T(cx + Math.abs(r) * Math.cos(a), cy + Math.abs(r) * Math.sin(a));
            if (px != null) {
                line(px, py, pt[0], pt[1]);
            }
            px = pt[0];
            py = pt[1];
        }
    };
    const ent = (e, T, depth) => {
        const pt = (v) => T(v.x, v.y);
        switch (e.type) {
            case "LINE": {
                const a = pt(e.vertices[0]);
                const b = pt(e.vertices[1]);
                line(a[0], a[1], b[0], b[1]);
                break;
            }
            case "LWPOLYLINE":
            case "POLYLINE": {
                const vs = e.vertices || [];
                const n = vs.length;
                for (let i = 0; i < n - 1 + (e.shape ? 1 : 0); i++) {
                    const p = vs[i];
                    const q = vs[(i + 1) % n];
                    if (p.bulge) {
                        bulgeArc(p, q, p.bulge, T);
                    } else {
                        const a = pt(p);
                        const b = pt(q);
                        line(a[0], a[1], b[0], b[1]);
                    }
                }
                break;
            }
            case "CIRCLE":
                arc(e.center, e.radius, 0, Math.PI * 2, T);
                break;
            case "ARC":
                arc(e.center, e.radius, e.startAngle, e.endAngle, T);
                break;
            case "INSERT": {
                const b = dxf.blocks && dxf.blocks[e.name];
                if (!b || !b.entities || depth > 3) {
                    break;
                }
                const sx = e.xScale == null ? 1 : e.xScale;
                const sy = e.yScale == null ? 1 : e.yScale;
                const rot = rad(e.rotation || 0);
                const c = Math.cos(rot);
                const s = Math.sin(rot);
                const bp = b.position || { x: 0, y: 0 };
                const p0 = e.position || { x: 0, y: 0 };
                const T2 = (x, y) => {
                    const lx = (x - bp.x) * sx;
                    const ly = (y - bp.y) * sy;
                    return T(p0.x + lx * c - ly * s, p0.y + lx * s + ly * c);
                };
                for (const be of b.entities) {
                    ent(be, T2, depth + 1);
                }
                break;
            }
            default:
                break;
        }
    };
    const ident = (x, y) => [x, y];
    for (const e of dxf.entities || []) {
        ent(e, ident, 0);
        if (segs.length >= DXF_MAX_SEGMENTS * 4) {
            break;
        }
    }
    const cap = Math.min(segs.length, DXF_MAX_SEGMENTS * 4);
    const arr = new Float32Array(cap);
    for (let i = 0; i < cap; i++) {
        arr[i] = segs[i];
    }
    let x0 = 1e30;
    let y0 = 1e30;
    let x1 = -1e30;
    let y1 = -1e30;
    for (let i = 0; i < arr.length; i += 2) {
        const x = arr[i];
        const y = arr[i + 1];
        x0 = Math.min(x0, x);
        x1 = Math.max(x1, x);
        y0 = Math.min(y0, y);
        y1 = Math.max(y1, y);
    }
    return { segs: arr, n: arr.length / 4, bbox: [x0, y0, x1, y1], truncated: segs.length > arr.length };
}

/** Параметри підкладки за умовчанням для щойно завантаженого файла (одиниці — за розміром креслення). */
export const defaultUnderlayParams = (bbox) => ({
    unit: Math.max(bbox[2] - bbox[0], bbox[3] - bbox[1]) > 500 ? "mm" : "m",
    dx: 0,
    dy: 0,
    rot_deg: 0,
    scale: 1,
    opacity: 0.75,
});

/** Завантажує підкладки шарів (DXF за `underlay.url`) у V.uldata; DWG ігнорується (статус pending_conversion). */
export async function loadUnderlays() {
    V.uldata.clear();
    let Parser = null;
    for (const ly of S.layers) {
        const u = ly.underlay;
        if (!u || u.format !== "dxf" || u.status !== "ready" || !u.url) {
            continue;
        }
        try {
            const r = await fetch(u.url, { credentials: "same-origin" });
            if (!r.ok) {
                continue;
            }
            Parser = Parser || (await loadDxfParser());
            const res = parseDxf(await r.text(), Parser);
            u.bbox = res.bbox;
            V.uldata.set(ly.id, { segs: res.segs, n: res.n });
        } catch (e) {
            console.warn("underlay", ly.name, e);
        }
    }
    E.syncUnderlays();
}

export function openDxfPanel() {
    S.ui.dxfOpen = true;
    renderDxfPanel();
}
function closeDxfPanel() {
    S.ui.dxfOpen = false;
    if (V.pickMode) {
        V.pickMode = null;
        E.rulerClear();
    }
    renderDxfPanel();
}

/** Обробка вибраного файла підкладки: DXF → розбір, вкладення, параметри; DWG → вкладення зі статусом «очікує перетворення». */
export async function importUnderlayFile(ly, file, store, msg) {
    const note = (cls, text) => msg && msg.replaceChildren(...K(h("div", { class: "note " + cls, style: { margin: "6px 0" } }, text)));
    msg && msg.replaceChildren();
    const isDwg = /\.dwg$/i.test(file.name);
    if (!isDwg && !/\.dxf$/i.test(file.name)) {
        note("err", "Потрібен файл .dxf.");
        return false;
    }
    if (isDwg) {
        note("lock", DWG_MESSAGE);
    } else if (file.size > DXF_MAX_BYTES) {
        toast("Файл завеликий (> 5 МБ): буде прочитано лише перші 200 тис. відрізків.", "warn");
    }
    let res = null;
    if (!isDwg) {
        try {
            const Parser = await loadDxfParser();
            res = parseDxf(await file.text(), Parser);
        } catch (e) {
            console.warn(e);
            note("err", "Не вдалося прочитати DXF: " + (e && e.message ? e.message : e));
            return false;
        }
        if (!res.n) {
            note("err", "У файлі не знайдено підтримуваних ліній.");
            return false;
        }
    }
    if (ly.rid == null) {
        await E.flushNow(); // шар має існувати на сервері, щоб прикріпити вкладення
    }
    const att = await store.attachUnderlay(ly, file);
    ly.underlay = {
        url: att.url,
        name: file.name,
        format: isDwg ? "dwg" : "dxf",
        status: isDwg ? "pending_conversion" : "ready",
        params: res ? defaultUnderlayParams(res.bbox) : { unit: "mm", dx: 0, dy: 0, rot_deg: 0, scale: 1, opacity: 0.75 },
        bbox: res ? res.bbox : null,
    };
    if (res) {
        V.uldata.set(ly.id, { segs: res.segs, n: res.n });
        toast(`Підкладку завантажено: ${fmtInt(res.n)} відрізків.` + (res.truncated ? " Файл обрізано до ліміту." : ""));
    } else {
        V.uldata.delete(ly.id);
    }
    E.liveEdit();
    return true;
}

export function renderDxfPanel() {
    const box = $("#dxfPanel");
    if (!box) {
        return;
    }
    if (!S.ui.dxfOpen) {
        box.hidden = true;
        return;
    }
    const ly = layerOf(S.ui.layer);
    if (!ly) {
        return;
    }
    box.hidden = false;
    box.replaceChildren();
    const u = ly.underlay;
    const dis = !canEditLayer(ly);
    const upd = () => {
        E.liveEdit();
    };
    box.append(
        ...K(
            h("h4", null, "Підкладка DXF", h("button", { class: "xbtn", type: "button", "aria-label": "Закрити", onclick: closeDxfPanel }, ic("x"))),
            h("div", { class: "small muted", style: { marginBottom: "6px" } }, `Шар «${ly.name}», відмітка ${fmt(ly.elevation, 1)} м. LINE, LWPOLYLINE, POLYLINE, CIRCLE, ARC, INSERT.`),
            dis ? h("div", { class: "note lock" }, lockHint(ly)) : null
        )
    );
    const fi = h("input", { type: "file", accept: ".dxf,.dwg", hidden: true, id: "dxfFile", "aria-label": "Файл DXF" });
    const msg = h("div", { id: "dxfMsg" });
    fi.addEventListener("change", async () => {
        const f = fi.files[0];
        if (!f) {
            return;
        }
        const ok = await importUnderlayFile(ly, f, E.store, msg);
        if (ok) {
            renderDxfPanel();
        }
    });
    box.append(...K(h("button", { class: "fbtn", type: "button", disabled: dis, onclick: () => fi.click() }, ic("upload"), u ? "Замінити файл" : "Обрати файл DXF"), fi, msg));
    if (!u) {
        box.append(h("div", { class: "small muted", style: { marginTop: "8px" } }, "Файл не завантажено. Підкладка малюється лініями на підлозі активного шару для обведення в масштабі."));
        return;
    }
    if (u.format === "dwg" || u.status === "pending_conversion") {
        box.append(h("div", { class: "note lock", id: "dwgNote", style: { margin: "8px 0" } }, DWG_MESSAGE), h("div", { class: "small" }, u.name));
        box.append(removeBtn(ly, dis));
        return;
    }
    const m = u.params;
    const real = V.underlays.get(ly.id) ? "" : h("div", { class: "note lock", style: { margin: "6px 0" } }, "Дані підкладки ще завантажуються або недоступні. Спробуйте замінити файл.");
    box.append(
        ...K(
            h("div", { class: "small", style: { margin: "8px 0 4px" } }, `${u.name}${V.uldata.get(ly.id) ? " · " + fmtInt(V.uldata.get(ly.id).n) + " відрізків" : ""}`),
            real,
            h(
                "div",
                { class: "fcol" },
                h("div", { class: "frow" }, h("span", { class: "lbl" }, "Одиниці"), h("span", { class: "seg" }, ["mm", "m"].map((x) => h("button", { type: "button", disabled: dis, "aria-pressed": String(m.unit === x), onclick: () => { m.unit = x; upd(); renderDxfPanel(); } }, x === "mm" ? "мм" : "м")))),
                h(
                    "div",
                    { class: "grid3" },
                    fld("Зсув X", numInput({ value: m.dx, dis, step: 0.5, label: "Зсув X", f: "dxf-dx", set: (v) => { m.dx = v; upd(); } }), "м"),
                    fld("Зсув Y", numInput({ value: m.dy, dis, step: 0.5, label: "Зсув Y", f: "dxf-dy", set: (v) => { m.dy = v; upd(); } }), "м"),
                    fld("Поворот", numInput({ value: m.rot_deg, dis, step: 1, label: "Поворот", f: "dxf-rot", set: (v) => { m.rot_deg = v; upd(); } }), "°")
                ),
                fld("Прозорість", h("input", { type: "range", min: 0.1, max: 1, step: 0.05, value: m.opacity, disabled: dis, "aria-label": "Прозорість", oninput: (e) => { m.opacity = parseFloat(e.target.value); upd(); } }), "лінії"),
                h("div", { class: "small muted" }, `Масштаб ×${fmt(m.scale || 1, 4)}`),
                h(
                    "div",
                    { class: "frow wrap" },
                    h("button", { class: "fbtn sm", type: "button", disabled: dis || !u.bbox, onclick: () => { const k = (m.unit === "m" ? 1 : 0.001) * (m.scale || 1), b = u.bbox; m.dx = rnd(S.site.building.length / 2 - ((b[0] + b[2]) / 2) * k, 2); m.dy = rnd(S.site.building.width / 2 - ((b[1] + b[3]) / 2) * k, 2); m.rot_deg = 0; upd(); renderDxfPanel(); } }, "До центру будівлі"),
                    h("button", { class: "fbtn sm", type: "button", disabled: dis, "aria-pressed": String(!!V.pickMode), onclick: () => { E.cancelModes(); V.pickMode = "dxfscale"; V.pickPts = []; S.ui.dxfScale = null; toast("Клацніть дві точки на підкладці, потім введіть реальну відстань."); renderDxfPanel(); } }, ic("ruler"), "Прив’язати масштаб по двох точках")
                ),
                S.ui.dxfScale
                    ? h(
                          "div",
                          { class: "note" },
                          `Відстань між точками на кресленні: ${fmt(S.ui.dxfScale.d, 3)} м`,
                          h(
                              "div",
                              { class: "frow", style: { marginTop: "6px" } },
                              numInput({ value: null, dis, min: 0.001, step: 0.01, label: "Реальна відстань, м", f: "ulreal", set: (v) => { S.ui.dxfScale.real = v; } }),
                              h("button", { class: "fbtn sm primary", type: "button", onclick: () => { const sc = S.ui.dxfScale; if (!sc.real) { toast("Введіть реальну відстань у метрах.", "warn"); return; } m.scale = rnd((m.scale || 1) * sc.real / sc.d, 6); S.ui.dxfScale = null; E.rulerClear(); upd(); renderDxfPanel(); toast("Масштаб підкладки уточнено."); } }, "Застосувати")
                          )
                      )
                    : null,
                removeBtn(ly, dis)
            )
        )
    );
}
function removeBtn(ly, dis) {
    return h(
        "button",
        {
            class: "fbtn sm danger",
            type: "button",
            id: "btnRemoveUnderlay",
            disabled: dis,
            onclick: () => {
                ly.underlay = null;
                V.uldata.delete(ly.id);
                E.store.queue({ model: "f3d.layer", op: "write", uid: ly.id, vals: { underlay_attachment_id: false } });
                E.liveEdit();
                renderDxfPanel();
            },
        },
        ic("trash"),
        "Прибрати підкладку"
    );
}
function pickModeClick(pt) {
    if (V.pickMode !== "dxfscale") {
        return;
    }
    const v = E.underlayVertex(S.ui.layer, pt.x, pt.y, 0.6);
    if (v) {
        pt.x = v.x;
        pt.y = v.y;
    }
    V.pickPts = V.pickPts || [];
    V.pickPts.push(pt);
    E.rulerPoint(pt);
    if (V.pickPts.length === 2) {
        const [a, b] = V.pickPts;
        V.pickMode = null;
        V.pickPts = [];
        S.ui.dxfScale = { d: Math.hypot(b.x - a.x, b.y - a.y), real: null };
        $("#rlabel").hidden = true;
        renderDxfPanel();
    }
}

Object.assign(E, { openDxfPanel, renderDxfPanel, pickModeClick, loadUnderlays });
