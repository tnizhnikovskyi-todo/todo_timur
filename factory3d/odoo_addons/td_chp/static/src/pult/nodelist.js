/** @odoo-module **/
// UI-05 (інтерфейс): фільтр систем, список 37 вузлів і картка параметрів вузла. Порт `b_sim.js:708–763`.
// Стан вибору (`sel`, `sys`) — тут, а не в сховищі: це стан екрана, не дані КГУ.

import { setText } from "./util";
import { SYS } from "./nodes";

export function makeNodeList({ root, store, api, get3D }) {
    const q = (s) => root.querySelector(s);
    const qa = (s) => Array.from(root.querySelectorAll(s));
    const { NODES, NODE_ORDER, nodeBadge } = api;
    const ui = { sel: null, sys: "all" };
    let ddCache = [];
    let badgeEl = null;
    const cleanups = [];

    function build() {
        const seg = q("#sys-seg");
        seg.textContent = "";
        SYS.forEach((s) => {
            const b = document.createElement("button");
            b.type = "button";
            b.dataset.sys = s[0];
            b.textContent = s[1];
            b.setAttribute("aria-pressed", s[0] === "all" ? "true" : "false");
            const h = () => setSystem(s[0]);
            b.addEventListener("click", h);
            cleanups.push(() => b.removeEventListener("click", h));
            seg.appendChild(b);
        });
        const host = q("#nodes");
        host.textContent = "";
        NODE_ORDER.forEach((id) => {
            const b = document.createElement("button");
            b.type = "button";
            b.dataset.node = id;
            b.dataset.sys = NODES[id].sys;
            b.textContent = NODES[id].chip;
            b.setAttribute("aria-pressed", "false");
            b.title = NODES[id].name;
            const h = () => select(ui.sel === id ? null : id, true);
            b.addEventListener("click", h);
            cleanups.push(() => b.removeEventListener("click", h));
            host.appendChild(b);
        });
    }
    function setSystem(sys) {
        ui.sys = sys;
        qa("#sys-seg button").forEach((b) => b.setAttribute("aria-pressed", b.dataset.sys === sys ? "true" : "false"));
        qa("#nodes button").forEach((b) => {
            b.hidden = !(sys === "all" || b.dataset.sys === sys);
        });
        if (ui.sel && sys !== "all" && NODES[ui.sel].sys !== sys) {
            select(null, false);
        }
        const A3 = get3D();
        if (A3 && A3.setSystem) {
            A3.setSystem(sys);
        }
    }
    function select(id, fromList) {
        ui.sel = id;
        render(true);
        const A3 = get3D();
        if (id && fromList && A3 && A3.focus) {
            A3.focus(id);
        }
    }
    /** Клік по вузлу в 3D. */
    function pick(id) {
        if (id && ui.sys !== "all" && NODES[id].sys !== ui.sys) {
            setSystem("all");
        }
        select(id, false);
    }
    function render(force = false) {
        const host = q("#node-detail");
        const S = store.S;
        qa("#nodes button").forEach((b) => {
            b.setAttribute("aria-pressed", b.dataset.node === ui.sel ? "true" : "false");
            const hl = S.hl && S.hl.node === b.dataset.node;
            b.classList.toggle("hl-alarm", !!hl && S.hl.kind === "alarm");
            b.classList.toggle("hl-warn", !!hl && S.hl.kind === "warn");
        });
        if (!ui.sel) {
            if (force || host.dataset.id) {
                host.dataset.id = "";
                host.innerHTML =
                    '<p class="nd-empty">Оберіть вузол у 3D-моделі (клік) або зі списку: тут з’являться його живі параметри. Кнопки систем вище підсвічують групу вузлів у 3D.</p>';
                ddCache = [];
                badgeEl = null;
            }
            return;
        }
        const d = NODES[ui.sel];
        if (force || host.dataset.id !== ui.sel) {
            host.dataset.id = ui.sel;
            host.textContent = "";
            ddCache = [];
            const hd = document.createElement("div");
            hd.className = "nd-h";
            const l = document.createElement("div");
            const h = document.createElement("h3");
            h.textContent = d.name;
            const sub = document.createElement("div");
            sub.className = "nd-sub";
            sub.textContent = d.sub;
            l.append(h, sub);
            const r = document.createElement("div");
            badgeEl = document.createElement("span");
            badgeEl.className = "badge";
            r.appendChild(badgeEl);
            hd.append(l, r);
            host.appendChild(hd);
            const dl = document.createElement("dl");
            dl.className = "nd-rows";
            dl.style.marginTop = "8px";
            d.rows.forEach((row) => {
                const w = document.createElement("div");
                const dt = document.createElement("dt");
                dt.textContent = row[0];
                const dd = document.createElement("dd");
                const v = document.createElement("span");
                dd.appendChild(v);
                if (row[2]) {
                    const u = document.createElement("small");
                    u.textContent = row[2];
                    dd.appendChild(u);
                }
                w.append(dt, dd);
                dl.appendChild(w);
                ddCache.push({ dd, v, fn: row[1] });
            });
            host.appendChild(dl);
        }
        ddCache.forEach((c) => {
            const r = c.fn();
            const t = Array.isArray(r) ? r[0] : r;
            const cls = Array.isArray(r) ? r[1] : "";
            setText(c.v, t);
            const nc = cls || "";
            if (c.dd.className !== nc) {
                c.dd.className = nc;
            }
        });
        const bd = nodeBadge(ui.sel);
        setText(badgeEl, bd[0]);
        const bc = "badge " + bd[1];
        if (badgeEl.className !== bc) {
            badgeEl.className = bc;
        }
    }
    function destroy() {
        cleanups.forEach((f) => f());
        cleanups.length = 0;
    }
    return { ui, build, setSystem, select, pick, render, destroy };
}
