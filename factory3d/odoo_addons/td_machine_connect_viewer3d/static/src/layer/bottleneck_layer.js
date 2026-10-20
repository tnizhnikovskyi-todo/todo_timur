/** @odoo-module **/
// R-30: розширення «Переглядача» (R-26, VX-03/VX-04) — «Вузьке місце»: червона стопка завдань, що чекають перед ділянкою
// (висота за кількістю), і блок з показниками в картці верстата. Дані — `workcenters[code].flow` (дає провайдер `td_machine_connect`):
// показники ділянки, а для вузького місця ще `codes` (верстати ділянки), `prev` (верстати перед нею) і `hint`.
// Шар «Замовлення в роботі» ядра не чіпається й не дублюється: стопка живе у власній групі сцени, поза режимами розфарбування.
// УВАГА (rjsmin): без вкладених шаблонних літералів у `${...}` — рядки склеєно конкатенацією.
import { registerViewerExtension } from "@td_viewer3d/viewer/core";
import { esc, nf } from "@td_viewer3d/viewer/format";

export const EXT_ID = "td_machine_connect_bottleneck";
export const STACK_NAME = "td_bottleneck_stack";
/** Найбільше «коробок» у стопці (далі висота не росте, а кількість видно на табличці). */
export const MAX_BOXES = 12;
const BOX = { w: 1.3, h: 0.22, d: 0.9, gap: 0.04 };
const GAP = 1.2; // м від краю ділянки до центра стопки
const RED = "#e74c3c";
const VERDICT_TEXT = {
    growing: "черга росте",
    queue: "є черга",
    load: "черги немає: не виражене",
    low: "завантаження низьке: імовірне",
};

/** Вузол `flow` верстата або `null` (немає ключа: старий сервер, верстат без ділянки). */
export function flowOf(D, code) {
    const f = D?.workcenters?.[code]?.flow;
    return f && typeof f === "object" ? f : null;
}

/** Вузьке місце з payload: `{ code, ...flow }` першого верстата ділянки з `flow.bottleneck`, інакше `null`. */
export function bottleneckOf(D) {
    for (const [code, wc] of Object.entries(D?.workcenters || {})) {
        if (wc?.flow?.bottleneck) {
            return { code, ...wc.flow };
        }
    }
    return null;
}

/** Висота стопки в коробках: за кількістю завдань у черзі, не більше `MAX_BOXES`. */
export function boxCount(queue) {
    const n = Math.round(Number(queue) || 0);
    return Math.max(0, Math.min(MAX_BOXES, n));
}

const pct = (v) => (typeof v === "number" ? Math.round(v * 100) + " %" : "—");
const delta = (d) => (!d ? "" : d > 0 ? " (↑ +" + d + ")" : " (↓ −" + -d + ")");

/** Блок «Вузьке місце» картки верстата (VX-04): показники ділянки; для вузького місця — підказка «що якщо». */
export function cardHtml(code, D) {
    const f = flowOf(D, code);
    if (!f) {
        return "";
    }
    const total = new Set(Object.values(D.workcenters || {}).map((w) => w?.flow?.key).filter(Boolean)).size;
    let h = "<div class=\"o_f3d_sub\">Вузьке місце · " + esc(f.station) + "</div>";
    h += "<div class=\"o_td_bn_flow\" data-station=\"" + esc(f.key) + "\">";
    h += f.bottleneck
        ? "<span class=\"o_f3d_chip o_f3d_bad\">Вузьке місце" + (f.verdict ? " · " + esc(VERDICT_TEXT[f.verdict] || f.verdict) : "") + "</span>"
        : "<span class=\"o_f3d_chip o_f3d_idle\">Не обмежує випуск</span>";
    h += "<dl class=\"o_f3d_kv\">" +
        "<dt>Завантаження</dt><dd>" + pct(f.load) + "</dd>" +
        "<dt>Черга</dt><dd>" + nf.format(f.queue || 0) + esc(delta(f.queue_delta)) + "</dd>" +
        "<dt>Очікування</dt><dd>" + (typeof f.wait_min === "number" ? nf.format(Math.round(f.wait_min)) + " хв" : "—") + "</dd>" +
        "<dt>Випуск</dt><dd>" + nf.format(Math.round(f.output || 0)) + "</dd>" +
        "<dt>Рейтинг</dt><dd>" + nf.format(f.rank || 0) + (total ? " з " + nf.format(total) : "") + "</dd>" +
        "</dl>";
    if (f.bottleneck && f.hint) {
        h += "<div class=\"o_f3d_hint o_td_bn_hint\">Що якщо: " + esc(f.hint) + "</div>";
    }
    return h + "</div>";
}

function numberTexture(T, n) {
    const canvas = document.createElement("canvas");
    canvas.width = 128;
    canvas.height = 128;
    const ctx = canvas.getContext("2d");
    if (ctx) {
        ctx.beginPath();
        ctx.arc(64, 64, 58, 0, Math.PI * 2);
        ctx.fillStyle = RED;
        ctx.fill();
        ctx.lineWidth = 8;
        ctx.strokeStyle = "#ffffff";
        ctx.stroke();
        ctx.fillStyle = "#ffffff";
        ctx.font = "bold " + (String(n).length > 2 ? 52 : 72) + "px sans-serif";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(String(n), 64, 70);
    }
    const map = new T.CanvasTexture(canvas);
    map.colorSpace = T.SRGBColorSpace;
    return map;
}

export class BottleneckExtension {
    constructor() {
        this.id = EXT_ID;
        this.states = new WeakMap(); // api.scene → { group, sig, geometry, material }
        this.THREE = null;
    }

    stateOf(api) {
        let st = this.states.get(api.scene);
        if (!st) {
            st = { group: null, sig: null, geometry: null, material: null };
            this.states.set(api.scene, st);
        }
        return st;
    }

    /** Прибрати стопку зі сцени (геометрія й матеріал лишаються для наступної). */
    clear(api) {
        const st = this.stateOf(api);
        if (st.group) {
            st.group.traverse((o) => {
                o.material?.map?.dispose?.();
                if (o.isSprite) {
                    o.material?.dispose?.();
                }
            });
            st.group.removeFromParent();
        }
        st.group = null;
        st.sig = null;
    }

    _box(T, codes, api) {
        const box = new T.Box3();
        for (const code of codes || []) {
            const root = api.items.get(code);
            if (root) {
                root.updateWorldMatrix(true, true);
                box.expandByObject(root);
            }
        }
        return box;
    }

    /** Стопка перед ділянкою: з боку попередньої ділянки (`prev`), на підлозі; `force` — перебудувати й за тим самим складом. */
    sync(api, D, force = false) {
        const T = api.THREE;
        this.THREE = T;
        const st = this.stateOf(api);
        const info = bottleneckOf(D);
        const n = info ? boxCount(info.queue) : 0;
        const roots = info ? (info.codes || [info.code]).filter((c) => api.items.get(c)) : [];
        if (!info || n === 0 || !roots.length) {
            this.clear(api);
            return;
        }
        const sig = [n, info.queue, roots.join(","), (info.prev || []).join(",")].join("|");
        if (!force && st.group && st.sig === sig) {
            return;
        }
        this.clear(api);
        const own = this._box(T, roots, api);
        if (own.isEmpty()) {
            return;
        }
        const center = own.getCenter(new T.Vector3());
        const size = own.getSize(new T.Vector3());
        const prev = this._box(T, info.prev, api);
        const dir = new T.Vector3(-1, 0, 0); // без попередньої ділянки — з боку -X
        if (!prev.isEmpty()) {
            const d = center.clone().sub(prev.getCenter(new T.Vector3()));
            d.y = 0;
            if (d.lengthSq() > 1e-6) {
                dir.copy(d.normalize().negate()); // у бік попередньої ділянки: звідки приходять завдання
            }
        }
        const reach = (Math.abs(dir.x) * size.x + Math.abs(dir.z) * size.z) / 2 + GAP;
        if (!st.geometry) {
            st.geometry = new T.BoxGeometry(BOX.w, BOX.h, BOX.d);
            st.material = new T.MeshStandardMaterial({ color: RED, emissive: "#5a1410", roughness: 0.6, metalness: 0.05 });
        }
        const group = new T.Group();
        group.name = STACK_NAME;
        group.userData = { bottleneckStack: true, queue: info.queue, station: info.station };
        for (let i = 0; i < n; i++) {
            const mesh = new T.Mesh(st.geometry, st.material);
            const jitter = ((i * 37) % 11) - 5;
            mesh.position.set(jitter * 0.006, BOX.h / 2 + i * (BOX.h + BOX.gap), jitter * -0.005);
            mesh.rotation.y = jitter * 0.03;
            mesh.castShadow = true;
            group.add(mesh);
        }
        const label = new T.Sprite(new T.SpriteMaterial({ map: numberTexture(T, info.queue), transparent: true, depthTest: false }));
        label.name = STACK_NAME + "_label";
        label.scale.set(1.4, 1.4, 1);
        label.position.set(0, n * (BOX.h + BOX.gap) + 0.9, 0);
        label.renderOrder = 999;
        group.add(label);
        group.position.set(center.x + dir.x * reach, own.min.y, center.z + dir.z * reach);
        api.scene.add(group);
        st.group = group;
        st.sig = sig;
    }

    // розкладка змінилась / модель довантажилась: положення верстатів інше — стопку ставимо заново
    applyLayout(api) {
        this.sync(api, api.D, true);
    }

    // VX-03
    applyData(api, D) {
        this.sync(api, D);
    }

    // VX-04
    cardBlocks(code, D) {
        const html = cardHtml(code, D);
        return html ? [html] : [];
    }

    /** Зняти стопку (тести; у ядрі екземпляр знищується разом зі сценою). */
    disposeAll(api) {
        this.clear(api);
        this.states.delete(api.scene);
    }
}

export const bottleneckExtension = new BottleneckExtension();
registerViewerExtension(bottleneckExtension);
