/** @odoo-module **/
// R-30: розширення «Переглядача» (R-26, VX-03/VX-04) — «Вузьке місце»: червона стопка завдань, що чекають перед ділянкою
// (висота за кількістю), і блок з показниками в картці верстата. Дані — `workcenters[code].flow` (дає провайдер `td_machine_connect`):
// показники ділянки, а для вузького місця ще `codes` (верстати ділянки), `prev` (верстати перед нею) і `hint`.
// Шар «Замовлення в роботі» ядра не чіпається й не дублюється: стопка живе у власній групі сцени, поза режимами розфарбування.
// Стопка стоїть на підлозі біля входу верстата ділянки (з боку попередньої ділянки), над нею бейдж із числом і підпис «Вузьке місце · черга N»
// (стиль підписів верстатів); наведення показує метрики, клік відкриває картку верстата-входу з блоком «Вузьке місце».
// Усе (коробки, бейдж, підпис) — одна група-власник `st.group`: при кожному оновленні стара група знімається цілком, а її CSS2D-підпис
// видаляється з DOM явно (`removed` у three спрацьовує лише на самому підписі, а не на групі, що його несе). Підпис один — біля поточного
// вузького місця; стопка й підпис завжди в межах ділянки (`areaBox`).
// Один на весь документ: посилання на живу групу (`LIVE.group`) лежить на `globalThis`, а не в `states` (стан за сценою) — воно не губиться,
// коли стан розширення втрачено, з'явилась друга сцена з іншим api чи модуль завантажено вдруге; стара група з будь-якої сцени знімається
// перед новою, а DOM підмітається по всьому документу (не лише в шарі підписів ядра). Групу, знятую зі сцени ззовні, перебудовуємо.
// УВАГА (rjsmin): без вкладених шаблонних літералів у `${...}` — рядки склеєно конкатенацією.
import { registerViewerExtension } from "@td_viewer3d/viewer/core";
import { esc, nf } from "@td_viewer3d/viewer/format";

export const EXT_ID = "td_machine_connect_bottleneck";
export const STACK_NAME = "td_bottleneck_stack";
/** Найбільше «коробок» у стопці (далі висота не росте, а кількість видно на табличці). */
export const MAX_BOXES = 12;
const BOX = { w: 1.3, h: 0.22, d: 0.9, gap: 0.04 };
const GAP = 0.9; // м від краю верстата-входу до центра стопки (півглибини стопки 0,45 + запас)
const PROBABLE = new Set(["load", "low"]); // вердикти, коли вузьке місце «імовірне, не виражене»
const RED = "#e74c3c";
/** Жива група стопки (одна на документ, з будь-якої сцени): її знімає наступне `clear`, хай яке розширення чи api її створило. */
const LIVE = (globalThis.__tdBottleneckLive ??= { group: null });
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

/** Підпис біля бейджа: «Вузьке місце · черга N»; для невираженого вузького місця (`load`, `low`) — «Ймовірне вузьке місце · черга N». */
export function labelText(info) {
    const n = Math.round(Number(info?.queue) || 0);
    return (PROBABLE.has(info?.verdict) ? "Ймовірне вузьке місце" : "Вузьке місце") + " · черга " + n;
}

/** Підказка при наведенні: ділянка, завантаження, черга, очікування, «що якщо». */
export function hoverText(info) {
    const pctOf = (v) => (typeof v === "number" ? Math.round(v * 100) + " %" : "—");
    const parts = [
        info.station,
        "завантаження " + pctOf(info.load),
        "черга " + nf.format(info.queue || 0) + (info.queue_delta ? " (" + (info.queue_delta > 0 ? "↑ +" : "↓ −") + Math.abs(info.queue_delta) + ")" : ""),
        "очікування " + (typeof info.wait_min === "number" ? nf.format(Math.round(info.wait_min)) + " хв" : "—"),
    ];
    return parts.join(" · ") + (info.hint ? ". Що якщо: " + info.hint : "");
}

/**
 * Де ставити стопку: на підлозі біля входу верстата ділянки. `machines` — `[{code, box}]` (Box3 верстатів ділянки), `prevCenter` —
 * центр попередньої ділянки або `null`. Вхід — верстат, найближчий до попередньої ділянки (без неї — найзахідніший), сторона —
 * та, що дивиться на попередню ділянку (без неї — −X); стопка — по центру цієї сторони, на `GAP` від краю, а не посеред проходу.
 */
export function entrySpot(T, machines, prevCenter) {
    const centerOf = (m) => m.box.getCenter(new T.Vector3());
    let pick = machines[0];
    let dir = new T.Vector3(-1, 0, 0);
    if (prevCenter) {
        pick = machines.reduce((a, m) => (centerOf(m).distanceTo(prevCenter) < centerOf(a).distanceTo(prevCenter) ? m : a));
        const d = prevCenter.clone().sub(centerOf(pick));
        d.y = 0;
        if (d.lengthSq() > 1e-6) {
            dir = d.normalize();
        }
    } else {
        pick = machines.reduce((a, m) => (m.box.min.x < a.box.min.x ? m : a));
    }
    const c = centerOf(pick);
    const b = pick.box;
    const alongX = Math.abs(dir.x) >= Math.abs(dir.z);
    const sign = Math.sign(alongX ? dir.x : dir.z) || -1;
    const x = alongX ? (sign > 0 ? b.max.x + GAP : b.min.x - GAP) : c.x;
    const z = alongX ? c.z : sign > 0 ? b.max.z + GAP : b.min.z - GAP;
    return { code: pick.code, x, y: b.min.y, z, dir: alongX ? new T.Vector3(sign, 0, 0) : new T.Vector3(0, 0, sign) };
}

/** Півглибини стопки: від межі ділянки стопка стоїть не ближче. */
const HALF = BOX.d / 2;

/**
 * Межі ділянки в сцені: зона (`D.zones[..].workcenters`), що містить верстати вузького місця, якщо її об'єкт є в сцені й справді охоплює
 * ці верстати; інакше об'єднання верстатів ділянки із запасом `GAP + HALF` (стопка стоїть біля входу, а не в проході далеко від них).
 */
export function areaBox(T, api, machines, D) {
    const union = new T.Box3();
    for (const m of machines) {
        union.union(m.box);
    }
    const codes = new Set(machines.map((m) => m.code));
    const zones = Array.isArray(D?.zones) ? D.zones.map((z) => [z?.code, z]) : Object.entries(D?.zones || {});
    for (const [zc, z] of zones) {
        const root = zc && (z?.workcenters || []).some((c) => codes.has(c)) ? api.items.get(zc) : null;
        if (!root) {
            continue;
        }
        root.updateWorldMatrix(true, true);
        const box = new T.Box3().setFromObject(root);
        if (!box.isEmpty() && box.containsBox(union)) {
            return box;
        }
    }
    return union.expandByVector(new T.Vector3(GAP + HALF, 0, GAP + HALF));
}

/** Притиснути точку стопки (x, z) до меж ділянки так, щоб вся стопка (півглибини) лежала всередині. */
export function clampToArea(box, x, z) {
    const fit = (v, lo, hi) => (hi - lo < 2 * HALF ? (lo + hi) / 2 : Math.min(Math.max(v, lo + HALF), hi - HALF));
    return { x: fit(x, box.min.x, box.max.x), z: fit(z, box.min.z, box.max.z) };
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

    /** Знімає групу цілком: підпис — з DOM (і з three), спрайти — з GPU; геометрія й матеріал коробок лишаються для наступної. */
    _drop(group) {
        if (!group) {
            return;
        }
        for (const o of [...group.children]) {
            if (o.isCSS2DObject) {
                group.remove(o); // подія `removed` у three знімає елемент підпису з DOM
                o.element?.remove(); // і прямо: на випадок, коли подія не дійшла
            } else if (o.isSprite) {
                o.material?.map?.dispose?.();
                o.material?.dispose?.();
            }
        }
        group.removeFromParent();
    }

    /** Знімає стопку цієї сцени і живу стопку документа (вона може лежати в іншій сцені або лишитись від втраченого стану). */
    clear(api) {
        const st = this.stateOf(api);
        this._drop(st.group);
        if (LIVE.group !== st.group) {
            this._drop(LIVE.group);
        }
        st.group = null;
        st.sig = null;
        LIVE.group = null;
        this._sweep(null);
    }

    /** Прибрати з документа всі підписи вузького місця, крім `keep` (залишки старих груп, чужі сцени, перезавантаження модуля). */
    _sweep(keep) {
        for (const el of document.querySelectorAll(".o_td_bn_label")) {
            if (el !== keep) {
                el.remove();
            }
        }
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

    /** Підпис у стилі підписів верстатів (CSS2D з класами ядра); клас `CSS2DObject` береться в наявних підписів ядра. */
    _label(api, info, entry) {
        const Css2d = (api.labels || []).find((l) => l.lbl?.isCSS2DObject)?.lbl.constructor;
        if (!Css2d) {
            return null;
        }
        const el = document.createElement("div");
        el.className = "o_f3d_lbl o_f3d_mach o_td_bn_label";
        el.innerHTML = "<span class=\"o_f3d_st\" style=\"background:var(--f3d-bad)\"></span>" + esc(labelText(info));
        el.title = hoverText(info);
        el.dataset.station = info.key || "";
        el.style.pointerEvents = "auto"; // підпис клікабельний: відкриває картку верстата-входу з метриками вузького місця
        el.style.cursor = "pointer";
        el.style.translate = "0 -10px"; // просто над бейджем, по центру стопки
        el.addEventListener("click", (e) => {
            e.stopPropagation();
            api.select(entry);
        });
        return new Css2d(el);
    }

    /** Стопка на підлозі біля входу верстата ділянки (див. `entrySpot`); `force` — перебудувати й за тим самим складом. */
    sync(api, D, force = false) {
        const T = api.THREE;
        this.THREE = T;
        const st = this.stateOf(api);
        const info = bottleneckOf(D);
        const n = info ? boxCount(info.queue) : 0;
        const codes = info ? (info.codes || [info.code]).filter((c) => api.items.get(c)) : [];
        if (!info || n === 0 || !codes.length) {
            this.clear(api);
            return;
        }
        const machines = codes.map((code) => ({ code, box: this._box(T, [code], api) })).filter((m) => !m.box.isEmpty());
        if (!machines.length) {
            this.clear(api);
            return;
        }
        const prev = this._box(T, info.prev, api);
        const raw = entrySpot(T, machines, prev.isEmpty() ? null : prev.getCenter(new T.Vector3()));
        const spot = { ...raw, ...clampToArea(areaBox(T, api, machines, D), raw.x, raw.z) };
        const sig = [n, info.queue, labelText(info), hoverText(info), spot.code, spot.x.toFixed(2), spot.z.toFixed(2)].join("|");
        const alive = st.group && st.group === LIVE.group && st.group.parent === api.scene; // групу могли зняти ззовні або замінити в іншій сцені
        if (!force && alive && st.sig === sig) {
            return;
        }
        this.clear(api);
        if (!st.geometry) {
            st.geometry = new T.BoxGeometry(BOX.w, BOX.h, BOX.d);
            st.material = new T.MeshStandardMaterial({ color: RED, emissive: "#5a1410", roughness: 0.6, metalness: 0.05 });
        }
        const group = new T.Group();
        group.name = STACK_NAME;
        group.userData = { bottleneckStack: true, queue: info.queue, station: info.station, entry: spot.code, label: labelText(info) };
        for (let i = 0; i < n; i++) {
            const mesh = new T.Mesh(st.geometry, st.material);
            const jitter = ((i * 37) % 11) - 5;
            mesh.position.set(jitter * 0.006, BOX.h / 2 + i * (BOX.h + BOX.gap), jitter * -0.005);
            mesh.rotation.y = jitter * 0.03;
            mesh.castShadow = true;
            group.add(mesh);
        }
        const top = n * (BOX.h + BOX.gap) + 0.7; // бейдж (діаметр 1 м) стоїть на `top`, підпис — над ним
        const badge = new T.Sprite(new T.SpriteMaterial({ map: numberTexture(T, info.queue), transparent: true, depthTest: false }));
        badge.name = STACK_NAME + "_label";
        badge.scale.set(1.0, 1.0, 1);
        badge.position.set(0, top, 0);
        badge.renderOrder = 999;
        group.add(badge);
        const label = this._label(api, info, spot.code);
        if (label) {
            label.name = STACK_NAME + "_text";
            label.position.set(0, top + 0.6, 0);
            group.add(label);
        }
        group.position.set(spot.x, spot.y, spot.z);
        api.scene.add(group);
        st.group = group;
        st.sig = sig;
        LIVE.group = group;
        this._sweep(label?.element ?? null);
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
