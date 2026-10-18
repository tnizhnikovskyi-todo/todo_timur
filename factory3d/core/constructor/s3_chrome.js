// Розмітка слайса S3 поверх базового DOM редактора (body.js не змінюється): кнопки ↶ ↷, перемикач «Показник» і легенда, мітка рівня доступу,
// підказка при наведенні (F06-05), мобільний режим комірника (F06-04: ≤ 768 px — згорнута панель ☰, пошук зверху, картка на весь екран,
// висувна «Панель об'єкта», правка вимкнена). Елементи створюються при першому рендері й оновлюються після кожного `E.renderAll`.
// Стилі вбудовано сюди (один код у модулі й прототипі, без правки спільного scss).
import { can } from "./registry.js";
import { E, S } from "./state.js";
import { $, ROOT, h, ic } from "./util.js";

export const MOBILE_QUERY = "(max-width: 768px)";
const STYLE_ID = "f3d-s3-style";

const CSS = `
.f3d-s3 .s3-burger,.f3d-s3 .s3-mbar,.f3d-s3 .s3-objbtn,.f3d-s3 .s3-card-ov{display:none}
.f3d-s3 .s3-tools{position:absolute;right:8px;top:8px;display:flex;gap:4px;flex-wrap:wrap;justify-content:flex-end;max-width:calc(100% - 16px);z-index:2;align-items:center}
.f3d-s3 .s3-tools select{max-width:190px;min-height:30px}
.f3d-s3 .s3-heat{position:absolute;right:8px;bottom:8px;z-index:2;background:var(--surface);border:1px solid var(--line);padding:6px 8px;font-size:12px;line-height:1.5;max-width:230px}
.f3d-s3 .s3-heat-h{display:flex;gap:6px;align-items:center;flex-wrap:wrap;margin-bottom:2px}
.f3d-s3 .s3-heat-row{display:flex;gap:6px;align-items:center}
.f3d-s3 .s3-heat-row .num{margin-left:auto;color:var(--ink2)}
.f3d-s3 .s3-heat .sq{display:inline-block;width:12px;height:12px;border:1px solid var(--line);flex:none}
.f3d-s3 .s3-demo{background:var(--warn-soft);color:var(--warn);border:1px solid var(--warn);padding:0 4px;font-size:11px}
.f3d-s3 .s3-tip{position:absolute;z-index:6;pointer-events:none;background:var(--ink);color:var(--surface);padding:5px 8px;font-size:12px;line-height:1.4;max-width:260px;box-shadow:0 4px 14px rgba(0,0,0,.3)}
.f3d-s3 .s3-list{display:flex;flex-direction:column;max-height:260px;overflow:auto;border:1px solid var(--line2);margin-top:4px}
.f3d-s3 .s3-list:empty{display:none}
.f3d-s3 .s3-item{display:flex;gap:8px;align-items:baseline;justify-content:space-between;border:0;border-bottom:1px solid var(--line2);background:var(--surface);padding:6px 8px;text-align:left;cursor:pointer;min-height:34px}
.f3d-s3 .s3-item:hover{background:var(--accent-soft)}
.f3d-s3 .s3-card table{width:100%;border-collapse:collapse;font-size:12px}
.f3d-s3 .s3-card td,.f3d-s3 .s3-card th{padding:2px 4px;border-bottom:1px solid var(--line2);text-align:left}
.f3d-s3 .s3-card .kv{display:grid;grid-template-columns:auto 1fr;gap:2px 10px;margin:4px 0}
.f3d-s3 .s3-card .kv span:nth-child(odd){color:var(--ink2)}
.f3d-s3 .s3-bar{height:8px;background:var(--surface3);border:1px solid var(--line);margin:2px 0 6px}
.f3d-s3 .s3-bar i{display:block;height:100%;background:var(--accent)}
.f3d-s3 .s3-status{background:var(--accent-soft)}
.f3d-s3 .s3-status[data-status="unsaved"]{background:#bfeceb;color:#064e4c}
.f3d-s3 .s3-status[data-status="new"]{background:var(--warn-soft)}
@media (max-width: 768px){
  .f3d-s3 .top{gap:4px 6px;padding:4px 6px}
  .f3d-s3 .top .brand,.f3d-s3 .top .grow,.f3d-s3 .top .grp:not(#siteGrp),.f3d-s3 #modeSeg,.f3d-s3 #draftChip,.f3d-s3 #storeTag,.f3d-s3 #s3Access,.f3d-s3 #btnPublish,.f3d-s3 #btnHistory,.f3d-s3 #menuExtra,.f3d-s3 #btnNewSite,.f3d-s3 .s3-undo{display:none!important}
  .f3d-s3 .s3-burger{display:inline-flex}
  .f3d-s3 #siteGrp{flex:1 1 0;min-width:0}
  .f3d-s3 #siteSel{max-width:none;width:100%}
  .f3d-s3 .main{grid-template-columns:minmax(0,1fr)!important;grid-template-rows:minmax(0,1fr)!important}
  .f3d-s3 .center{grid-column:1!important;grid-row:1!important;min-width:0}
  .f3d-s3 .mtabs,.f3d-s3 .stamp,.f3d-s3 .legend,.f3d-s3 .vnotice{display:none!important}
  .f3d-s3 .left,.f3d-s3 .right{display:none!important;position:absolute;top:0;bottom:0;z-index:30;width:min(88vw,360px);max-width:100%;grid-column:auto!important;grid-row:auto!important;background:var(--surface);box-shadow:0 0 24px rgba(0,0,0,.35);border:0}
  .f3d-s3.m-left .left{display:flex!important;left:0}
  .f3d-s3.m-right .right{display:flex!important;right:0}
  .f3d-s3 .ltabs{display:flex!important;flex-wrap:wrap}
  .f3d-s3 .s3-mbar{display:flex;position:absolute;left:6px;right:6px;top:6px;z-index:4;gap:4px}
  .f3d-s3 .s3-mbar input{flex:1;min-width:0;min-height:36px;font-size:16px}
  .f3d-s3 .s3-mlist{position:absolute;left:0;right:0;top:40px;background:var(--surface);border:1px solid var(--line);max-height:50vh;overflow:auto}
  .f3d-s3 .vtools{top:50px!important;left:6px!important}
  .f3d-s3 .vtools .fbtn{min-height:34px}
  .f3d-s3 .s3-tools{top:auto;bottom:56px;right:6px;left:6px;justify-content:flex-start}
  .f3d-s3 .s3-tools select{max-width:60vw}
  .f3d-s3 .s3-heat{right:6px;bottom:96px;max-width:46vw;font-size:11px}
  .f3d-s3 .s3-objbtn{display:inline-flex;position:absolute;right:6px;bottom:8px;z-index:40}
  .f3d-s3.m-left .s3-burger{position:absolute;left:calc(min(88vw,360px) - 46px);top:6px;z-index:40}
  .f3d-s3 .s3-card-ov{display:flex;flex-direction:column;position:fixed;inset:0;z-index:60;background:var(--surface)}
  .f3d-s3 .s3-card-ov[hidden]{display:none}
  .f3d-s3 .s3-card-ov .s3-card-h{display:flex;align-items:center;gap:8px;padding:8px 10px;border-bottom:1px solid var(--line)}
  .f3d-s3 .s3-card-ov .s3-card-b{flex:1;overflow:auto;padding:10px}
  .f3d-s3 dialog{max-width:100vw;width:100%}
  .f3d-s3 .fbtn,.f3d-s3 .s3-item{min-height:36px}
}
`;

export const isMobile = () => typeof window !== "undefined" && !!window.matchMedia && window.matchMedia(MOBILE_QUERY).matches;

function ensureStyle() {
    const root = ROOT.el;
    if (!root || root.querySelector("#" + STYLE_ID)) {
        return;
    }
    const st = document.createElement("style");
    st.id = STYLE_ID;
    st.textContent = CSS;
    root.prepend(st);
}

/** Мобільний режим: правка вимкнена (режим «Перегляд»), панелі — висувні; повернення на ПК відновлює режим. */
function applyMobile() {
    const app = $("#app");
    if (!app) {
        return;
    }
    const mob = isMobile();
    app.classList.toggle("m", mob);
    if (mob) {
        if (S.app.mode !== "view") {
            S.ui.modeBefore = S.app.mode;
            S.app.mode = "view";
            S.edit = null;
            E.cancelModes?.();
            E.renderAll?.();
        }
    } else {
        app.classList.remove("m-left", "m-right");
        hideCard();
        if (S.ui.modeBefore) {
            S.app.mode = S.ui.modeBefore;
            S.ui.modeBefore = null;
            E.renderAll?.();
        }
    }
}

/** Відкриває/закриває висувну панель ("left" — шари, місця, пошук; "right" — «Панель об'єкта»). */
export function mobilePanel(side, open = null) {
    const app = $("#app");
    if (!app || !isMobile()) {
        return;
    }
    const cls = side === "left" ? "m-left" : "m-right";
    const other = side === "left" ? "m-right" : "m-left";
    const on = open == null ? !app.classList.contains(cls) : open;
    app.classList.remove(other);
    app.classList.toggle(cls, on);
    decorate();
}

/* ---------- підказка при наведенні (F06-05) ---------- */
function tipHtml({ rec, kind, cell }) {
    const code = cell ? cell.code : kind === "placement" ? rec.code : rec.params?.title || rec.code_prefix;
    const lines = [h("b", null, code || "—")];
    const e = cell && E.stockOf?.(cell.code);
    if (cell) {
        if (e) {
            const top = e.top_product || (e.detail && e.detail.rows && e.detail.rows[0] && e.detail.rows[0].product);
            lines.push(h("div", null, top ? `Товар: ${top}` : e.qty ? `Кількість: ${e.qty}` : "Порожньо"));
            lines.push(h("div", null, e.fill != null ? `Заповненість: ${Math.round(e.fill * 100)} %` : "Заповненість: —"));
        } else if (can("stock")) {
            lines.push(h("div", { style: { opacity: 0.8 } }, S.stock ? "нова комірка · без даних Odoo" : "залишки не завантажено"));
        }
    } else if (kind === "placement") {
        lines.push(h("div", null, rec.name || ""));
    }
    return lines;
}
export function showTip(info) {
    const tip = $("#s3Tip");
    const cv = $("#vp");
    if (!tip || !cv || isMobile()) {
        return;
    }
    const r = cv.getBoundingClientRect();
    tip.replaceChildren(...tipHtml(info));
    tip.hidden = false;
    tip.style.left = Math.min(info.x - r.left + 14, r.width - 200) + "px";
    tip.style.top = Math.max(4, info.y - r.top + 14) + "px";
}
export function hideTip() {
    const tip = $("#s3Tip");
    if (tip) {
        tip.hidden = true;
    }
}

/* ---------- картка на весь екран (телефон) ---------- */
export function showCard(node, title) {
    const ov = $("#s3CardOv");
    if (!ov) {
        return;
    }
    $("#s3CardTitle").textContent = title || "";
    $("#s3CardBody").replaceChildren(node);
    ov.hidden = false;
}
export function hideCard() {
    const ov = $("#s3CardOv");
    if (ov) {
        ov.hidden = true;
    }
}

/* ---------- розмітка ---------- */
function ensureDom() {
    const app = $("#app");
    if (!app) {
        return false;
    }
    app.classList.add("f3d-s3");
    const center = $(".center");
    if (!$("#s3Tools")) {
        const tools = h(
            "div",
            { class: "s3-tools", id: "s3Tools" },
            h("button", { class: "fbtn icon s3-undo", type: "button", id: "s3Undo", "aria-label": "Скасувати", onclick: () => E.undo() }, ic("rot")),
            h("button", { class: "fbtn icon s3-undo", type: "button", id: "s3Redo", "aria-label": "Повторити", style: { transform: "scaleX(-1)" }, onclick: () => E.redo() }, ic("rot")),
            h("select", { id: "s3Metric", "aria-label": "Показник", onchange: (e) => E.setMetric(e.target.value) }),
            h("button", { class: "fbtn icon", type: "button", id: "s3Refresh", "aria-label": "Оновити дані", title: "Оновити дані", onclick: () => E.refreshStock() }, ic("hist"))
        );
        center.append(tools, h("div", { class: "s3-heat", id: "s3Heat", hidden: true }), h("div", { class: "s3-tip", id: "s3Tip", hidden: true }));
    }
    if (!$("#s3Burger")) {
        $(".top").prepend(h("button", { class: "fbtn icon s3-burger", type: "button", id: "s3Burger", "aria-label": "Панель", onclick: () => mobilePanel("left") }, h("span", { "aria-hidden": "true" }, "☰")));
    }
    if (!$("#s3Access")) {
        $("#storeTag").after(h("span", { class: "chip", id: "s3Access" }));
    }
    if (!$("#s3Mbar")) {
        const inp = h("input", { type: "search", id: "s3mSearch", placeholder: "Код місця, напр. PLT-01A", "aria-label": "Пошук місця", autocomplete: "off", enterkeyhint: "go" });
        const list = h("div", { class: "s3-mlist", id: "s3mList", hidden: true });
        const draw = () => {
            const { hits } = E.findCodes(inp.value, 8);
            list.hidden = !inp.value;
            list.replaceChildren(...hits.map((x) => h("button", { class: "s3-item", type: "button", onclick: () => (E.gotoHit(x), (list.hidden = true), inp.blur()) }, h("b", null, x.code), h("span", { class: "small muted" }, x.kind === "cell" ? "комірка" : x.kind === "placement" ? "обладнання" : "місце"))));
        };
        inp.addEventListener("input", draw);
        inp.addEventListener("keydown", (e) => {
            if (e.key === "Enter") {
                e.preventDefault();
                const { hits } = E.findCodes(inp.value, 5);
                const hit = hits.find((x) => x.rank === 0) || (hits.length === 1 ? hits[0] : null);
                if (hit) {
                    E.gotoHit(hit);
                    list.hidden = true;
                    inp.blur();
                } else {
                    draw();
                }
            }
        });
        center.append(h("div", { class: "s3-mbar", id: "s3Mbar" }, inp, h("button", { class: "fbtn", type: "button", id: "s3mFind", onclick: () => E.openSearch("find"), "aria-label": "Де лежить" }, "Де?"), list));
        center.append(h("button", { class: "fbtn primary s3-objbtn", type: "button", id: "s3ObjBtn", onclick: () => mobilePanel("right") }, "Панель об’єкта"));
        app.append(
            h(
                "div",
                { class: "s3-card-ov", id: "s3CardOv", hidden: true },
                h("div", { class: "s3-card-h" }, h("b", { id: "s3CardTitle", style: { flex: "1" } }), h("button", { class: "fbtn", type: "button", id: "s3CardClose", onclick: hideCard }, "Закрити")),
                h("div", { class: "s3-card-b", id: "s3CardBody" })
            )
        );
    }
    return true;
}

export function decorate() {
    ensureStyle();
    if (!ensureDom()) {
        return;
    }
    renderUndoButtons();
    E.renderHeat?.();
    const acc = E.access?.();
    const tag = $("#s3Access");
    if (tag && acc) {
        tag.textContent = acc.name;
        tag.title = "Рівень доступу: " + acc.name + (acc.design ? "" : ". " + E.accessHint("design"));
    }
    $("#modeSeg")?.querySelectorAll("button").forEach((b) => {
        b.disabled = isMobile();
        b.title = isMobile() ? "У мобільному режимі правка вимкнена" : "";
    });
    const br = $("#s3Burger");
    if (br) {
        const open = $("#app").classList.contains("m-left");
        br.setAttribute("aria-expanded", String(open));
        br.firstChild.textContent = open ? "✕" : "☰";
    }
    const ob = $("#s3ObjBtn");
    if (ob) {
        ob.textContent = $("#app").classList.contains("m-right") ? "Закрити панель" : "Панель об’єкта";
    }
}

export function renderUndoButtons() {
    const u = $("#s3Undo");
    if (!u) {
        return;
    }
    const st = E.undoState();
    const acc = E.access?.() || { design: true };
    const r = $("#s3Redo");
    u.disabled = !st.canUndo || !acc.design;
    r.disabled = !st.canRedo || !acc.design;
    u.title = !acc.design ? E.accessHint("design") : st.canUndo ? `Скасувати: ${st.undoLabel} (Ctrl+Z)` : "Немає що скасувати";
    r.title = !acc.design ? E.accessHint("design") : st.canRedo ? `Повторити: ${st.redoLabel} (Ctrl+Shift+Z)` : "Немає що повторити";
}

let mql = null;
const onMql = () => {
    applyMobile();
    decorate();
};
function onMount() {
    decorate();
    applyMobile();
    mql = window.matchMedia ? window.matchMedia(MOBILE_QUERY) : null;
    mql?.addEventListener("change", onMql);
    E.restoreMetric?.();
}
function onUnmount() {
    mql?.removeEventListener("change", onMql);
    mql = null;
}
E.lifecycle.mount.add(onMount);
E.lifecycle.unmount.add(onUnmount);

// після кожного E.renderAll елементи S3 оновлюються (renderTop/renderVTools самі їх не чіпають, але стан кнопок змінюється)
const origRenderAll = E.renderAll;
E.renderAll = function renderAllS3(...a) {
    const r = origRenderAll.apply(this, a);
    try {
        decorate();
        if (isMobile() && S.app.mode !== "view") {
            applyMobile();
        }
    } catch (e) {
        console.error("S3 chrome:", e);
    }
    return r;
};

Object.assign(E, { isMobile, mobilePanel, showTip, hideTip, showCard, hideCard, renderUndoButtons, decorateS3: decorate });
