/** @odoo-module */
// HOOT-тести ядра переглядача на demo_payload.json + model_static.json (мок /static і /data), testMode=true.
// Сценарії R1…R23 — по одному test() на рядок реєстру (AC-06), далі AC-02/03/05/07/08/09/30/31/37/38/47/51/58/61/62/63.
import { after, describe, expect, test } from "@odoo/hoot";
import { advanceTime, animationFrame, tick } from "@odoo/hoot-mock";
import { FileClient, SchemaError, deepMerge, mergeData } from "@td_viewer3d/viewer/data_client";
import { detectLite } from "@td_viewer3d/viewer/lite";
import { F3dViewer } from "@td_viewer3d/viewer/core";
import { liveLine, palletCount } from "@td_viewer3d/viewer/stock_load";
import { BASE, json, loadFixtures, mountViewer } from "./helpers";

const q = (el, sel) => el.querySelector(sel);
const qa = (el, sel) => [...el.querySelectorAll(sel)];
const txt = (el, sel) => q(el, sel)?.textContent ?? "";
const text = (el) => (el.textContent || "").replace(/\s+/g, " ").trim();
/** Пари dt → dd усіх `<dl class="o_f3d_kv">` картки. */
const kv = (el) => Object.fromEntries(qa(el, ".o_f3d_cardbody dt").map((dt) => [text(dt), text(dt.nextElementSibling)]));
const key = (k) => window.dispatchEvent(new KeyboardEvent("keydown", { key: k, bubbles: true }));

describe.current.tags("desktop");

// ------------------------------------------------------------------ R1…R23

test("R1 заголовок: габарити і лічильник верстатів", async () => {
    const { viewer, el, fx } = await mountViewer({ model: "core" });
    const machines = [...viewer.items.values()].filter((o) => o.userData.kind === "machine").length;
    expect(machines).toBeGreaterThan(0);
    const dims = txt(el, ".o_f3d_dims");
    expect(dims.includes(fx.manifest.dims)).toBe(true);
    expect(dims.includes(String(machines))).toBe(true);
});

test("R2 індикатор Odoo: стан, джерело, клік веде в Огляд", async () => {
    const { viewer, el } = await mountViewer({ model: "none" });
    const pill = q(el, ".o_f3d_odoo-pill");
    expect(pill.classList.contains("o_f3d_on")).toBe(true);
    expect(txt(el, ".o_f3d_odoo-state")).toBe("демо-дані");
    expect(txt(el, ".o_f3d_odoo-time").startsWith("синхр.")).toBe(true);
    viewer.openTab("production");
    pill.click();
    expect(viewer.getState().tab).toBe("overview");
});

test("R2 годинник «синхр.»: секунди з meta.now_ms; патч лише посуває вперед", async () => {
    const { viewer, el } = await mountViewer({ model: "none" });
    const hm = viewer.D.meta.now.slice(11, 16);
    const now = viewer.D.meta.now;
    // now_ms % 60000 — секунди «зараз» (Київ зсунутий на цілі хвилини): годинник = hh:mm:45
    viewer.applyPatch({ meta: { now, now_ms: Date.parse("2026-01-01T00:00:00Z") + 45000 } });
    expect(txt(el, ".o_f3d_odoo-time").endsWith(`${hm}:45`)).toBe(true);
    // патч без секунд (старий сервер) або з меншими секундами не відкочує годинник назад
    viewer.applyPatch({ meta: { now } });
    expect(txt(el, ".o_f3d_odoo-time").endsWith(`${hm}:45`)).toBe(true);
    viewer.applyPatch({ meta: { now, now_ms: Date.parse("2026-01-01T00:00:00Z") + 10000 } });
    expect(txt(el, ".o_f3d_odoo-time").endsWith(`${hm}:45`)).toBe(true);
});

test("R3 програвання зміни: повзунок, мітка, «Зараз»", async () => {
    const { viewer, el } = await mountViewer({ model: "none" });
    viewer.setSimTime(600);
    expect(viewer.getState().simMinutes).toBe(600);
    expect(txt(el, ".o_f3d_shift-l")).toBe("10:00");
    expect(q(el, ".o_f3d_shift-t").value).toBe("600");
    q(el, ".o_f3d_shift-now").click();
    expect(viewer.getState().simMinutes).toBe(null);
    expect(txt(el, ".o_f3d_shift-l")).toBe("зараз");
});

test("R4 «Потік зміни»: смуги операцій і клік по смузі відкриває МО", async () => {
    const { viewer, el } = await mountViewer({ model: "none" });
    expect(q(el, ".o_f3d_flow").hidden).toBe(true);
    viewer.setSimTime(600);
    expect(q(el, ".o_f3d_flow").hidden).toBe(false);
    const bars = qa(el, ".o_f3d_flow-svg .o_f3d_wo");
    expect(bars.length).toBeGreaterThan(0);
    bars[0].dispatchEvent(new MouseEvent("click", { bubbles: true }));
    expect(viewer.getState().panel).toBe("mo");
    expect(qa(el, ".o_f3d_flow-feed li").length).toBeGreaterThan(0);
});

test("▶ «Потік зміни» не зсуває картинку: проєкція камери й розмір полотна не змінюються при відкритті й закритті панелі", async () => {
    const { viewer, el } = await mountViewer({ model: "none" });
    const { camera, renderer } = viewer.core;
    const canvas = renderer.domElement;
    Object.defineProperty(canvas, "clientWidth", { value: 1200, configurable: true }); // у тестах полотно без розміру
    Object.defineProperty(canvas, "clientHeight", { value: 700, configurable: true });
    const proj = () => [...camera.projectionMatrix.elements];
    const before = proj();
    q(el, ".o_f3d_shift-play").click();
    expect(q(el, ".o_f3d_flow").hidden).toBe(false);
    expect(camera.view?.enabled ?? false).toBe(false);
    expect(proj()).toEqual(before);
    window.dispatchEvent(new Event("resize")); // вузький екран / зміна розкладки теж не зсуває
    expect(camera.view?.enabled ?? false).toBe(false);
    expect(proj()).toEqual(before);
    q(el, ".o_f3d_shift-play").click(); // пауза
    q(el, ".o_f3d_shift-now").click(); // «Зараз» закриває панель
    expect(q(el, ".o_f3d_flow").hidden).toBe(true);
    expect(camera.view?.enabled ?? false).toBe(false);
    expect(proj()).toEqual(before);
});

test("R5 види: 13 кнопок, «Дах і СЕС» вмикає roofdeck, решта ховає", async () => {
    const { viewer, el } = await mountViewer({ model: "none" });
    expect(qa(el, ".o_f3d_view").length).toBe(13);
    viewer.goView("Дах і СЕС");
    expect(viewer.getState().layers.roofdeck).toBe(true);
    viewer.goView(0);
    expect(viewer.getState().layers.roofdeck).toBe(false);
    key("1");
    expect(q(el, '.o_f3d_view[aria-pressed="true"]')?.dataset.name).toBe("Загальний вигляд");
});

test("R6 розфарбування: режими й радіо", async () => {
    const { viewer, el } = await mountViewer({ model: "none" });
    expect(qa(el, 'input[name="cmode"]').length).toBe(5);
    for (const mode of ["fill", "oee", "power", "lux", "none"]) {
        viewer.setMode(mode);
        expect(viewer.getState().mode).toBe(mode);
        expect(q(el, `input[name="cmode"][value="${mode}"]`).checked).toBe(true);
    }
});

test("R7 шар «Замовлення в роботі»: маршрути МО в роботі", async () => {
    const { viewer, el } = await mountViewer({ model: "core" });
    const inProgress = viewer.D.productions.filter((m) => m.state === "progress").length;
    await viewer.setProdOverlay(true);
    expect(q(el, ".o_f3d_opt-prod").checked).toBe(true);
    expect(viewer.core.prodOv.on).toBe(true);
    expect(viewer.core.prodOv.byMo.size).toBeGreaterThan(0);
    expect(viewer.core.prodOv.dots.length).toBe(inProgress);
    expect(viewer.getState().tab).toBe("production");
    await viewer.setProdOverlay(false);
    expect(viewer.core.prodOv.on).toBe(false);
});

test("R8 шари: 7 груп, «Усі» / «Лише виробництво»", async () => {
    const { viewer, el, fx } = await mountViewer({ model: "none" });
    expect(qa(el, ".o_f3d_lgroup").length).toBe(new Set(fx.manifest.layers.map((l) => l.group)).size);
    expect(viewer.layers.size).toBe(fx.manifest.layers.length);
    q(el, ".o_f3d_all-on").click();
    const all = viewer.getState().layers;
    expect(Object.entries(all).filter(([k, v]) => !v && k !== "roofdeck").length).toBe(0);
    q(el, ".o_f3d_all-off").click();
    const prod = viewer.getState().layers;
    expect(prod.building).toBe(true);
    expect(prod.fire).toBe(false);
});

test("R9 показ: підписи, анімація, тіні", async () => {
    const { el } = await mountViewer({ model: "none" });
    expect(q(el, ".o_f3d_opt-labels").checked).toBe(true);
    expect(q(el, ".o_f3d_opt-motion").checked).toBe(!matchMedia("(prefers-reduced-motion: reduce)").matches);
    expect(q(el, ".o_f3d_opt-shadows")).not.toBe(null);
});

test("R10 Огляд: 4 KPI з даних", async () => {
    const { el, fx } = await mountViewer({ model: "none" });
    const wcs = Object.values(fx.data.workcenters);
    const working = wcs.filter((w) => w.status === "work").length;
    const oee = Math.round((wcs.reduce((s, w) => s + w.oee, 0) / wcs.length) * 100);
    const kpis = qa(el, ".o_f3d_kpis .o_f3d_kpi");
    expect(kpis.length).toBe(4);
    expect(txt(kpis[0], "b")).toBe(`${working}/${wcs.length}`);
    expect(txt(kpis[1], "b")).toBe(`${oee}%`);
});

test("R11 «Виробництво»: список МО, перший WH/MO/00231", async () => {
    const { viewer, el, fx } = await mountViewer({ model: "none" });
    viewer.openTab("production");
    const rows = qa(el, ".o_f3d_rows li");
    expect(rows.length).toBe(fx.data.productions.length);
    expect(text(rows[0]).includes("WH/MO/00231")).toBe(true);
});

test("R12 картка МО: шлях і маркери у 3D", async () => {
    const { viewer, fx } = await mountViewer({ model: "core" });
    const mo = fx.data.productions.find((m) => m.name === "WH/MO/00231");
    viewer.showMO("WH/MO/00231");
    await viewer.partsReady(); // решта частин (fire, site…) — для кроків маршруту
    await tick();
    expect(viewer.getState().panel).toBe("mo");
    expect(viewer.core.hl.path).not.toBe(null);
    const expected = mo.supply.steps.length + mo.workorders.length + mo.delivery.steps.length;
    expect(viewer.core.hl.markers.length).toBeGreaterThan(expected - 1); // + підписи гілок матеріалів
});

test("R13 «Склад»: пошук фільтрує список товарів", async () => {
    const { viewer, el } = await mountViewer({ model: "none" });
    viewer.openTab("stock");
    const before = qa(el, ".o_f3d_rows li").length;
    expect(before).toBeGreaterThan(1);
    const input = q(el, ".o_f3d_stock-q");
    input.value = "ДСП";
    input.dispatchEvent(new Event("input", { bubbles: true }));
    const after = qa(el, ".o_f3d_rows li").length;
    expect(after).toBeGreaterThan(0);
    expect(after).toBeLessThan(before);
});

test("R14 картка товару", async () => {
    const { viewer, el, fx } = await mountViewer({ model: "none" });
    const code = Object.keys(fx.data.products)[0];
    viewer.showProduct(code);
    expect(viewer.getState().panel).toBe("product");
    expect(text(el).includes(fx.data.products[code].name)).toBe(true);
});

test("R15 «Логістика»: ланцюжки, шляхи матеріалів, списки переміщень", async () => {
    const { viewer, el, fx } = await mountViewer({ model: "core" });
    viewer.openTab("logistics");
    expect(qa(el, '[data-go^="chain:"]').length).toBeGreaterThan(0);
    expect(qa(el, '[data-go^="matp:"]').length).toBe(fx.data.material_paths.length);
    expect(qa(el, '[data-go^="pick:"]').length).toBe(fx.data.pickings.length);
    await viewer.partsReady();
    viewer.showChain("all");
    await tick();
    expect(viewer.core.hl.roots.size).toBeGreaterThan(0);
    viewer.showMatPath(0);
    await tick();
    expect(viewer.core.hl.roots.size).toBeGreaterThan(0);
});

test("R16 картка переміщення: маршрут ГП → ворота → фура", async () => {
    const { viewer, fx } = await mountViewer({ model: "core" });
    await viewer.partsReady();
    for (const name of ["WH/OUT/00412", "WH/OUT/00413"]) {
        const p = fx.data.pickings.find((x) => x.name === name);
        viewer.showPicking(name);
        await tick();
        expect(viewer.getState().panel).toBe("picking");
        const roots = [...viewer.core.hl.roots].map((o) => o.userData.code);
        const expected = [...new Set(p.source_locations), "Z-OUT-" + p.dock.slice(-1), p.dock, p.truck].filter(Boolean);
        expect(expected.filter((c) => !roots.includes(c)).join()).toBe("");
        expect(viewer.core.hl.path).not.toBe(null);
    }
});

test("R17 «Енергія»: KPI, трансформатори, лінії, споживачі", async () => {
    const { viewer, el } = await mountViewer({ model: "none" });
    viewer.openTab("energy");
    expect(qa(el, ".o_f3d_kpis .o_f3d_kpi").length).toBe(4);
    expect(qa(el, '[data-go^="line:"]').length).toBeGreaterThan(0);
});

test("R18 картка лінії живлення", async () => {
    const { viewer, el, fx } = await mountViewer({ model: "core" });
    const code = Object.keys(fx.data.energy.lines)[0];
    viewer.showLine(code);
    expect(viewer.getState().panel).toBe("line");
    expect(text(el).includes(code)).toBe(true);
});

test("R19 картка 3D-об'єкта: назва, код, дані центру, «Наблизити»/«Закрити»", async () => {
    const { viewer, el } = await mountViewer({ model: "core" });
    viewer.select("SAW-1");
    expect(viewer.getState().selected).toBe("SAW-1");
    expect(txt(el, ".o_f3d_code")).toBe("SAW-1");
    expect(text(el).includes("OEE за зміну")).toBe(true);
    expect(q(el, ".o_f3d_c-focus")).not.toBe(null);
    q(el, ".o_f3d_c-close").click();
    expect(viewer.getState().selected).toBe(null);
});

test("R19a картка 3D-об'єкта: ряд кнопок угорі, перед даними і таблицею паспорта, «липкий»", async () => {
    const { viewer, el } = await mountViewer({
        model: "core",
        mutate: (fx) => {
            fx.data.passports = {
                "SAW-1": {
                    manufacturer: "HOMAG", model: "CENTATEQ", reason: "тест",
                    specs: { "Потужність": "10 кВт", "Маса": "5 т" }, sources: ["https://example.com/a"],
                    connected_note: "тест", connected_kw: 12,
                },
            };
        },
    });
    viewer.select("SAW-1");
    const before = (a, b) => !!(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING);
    const actions = q(el, ".o_f3d_cardbody .o_f3d_actions");
    expect(actions).not.toBe(null);
    expect(qa(el, ".o_f3d_cardbody .o_f3d_actions").length).toBe(1);
    // порядок кнопок і клас «липкого» ряду
    expect(actions.classList.contains("o_f3d_actions-top")).toBe(true);
    expect(qa(actions, "button").slice(0, 2).map((b) => b.className.includes("o_f3d_c-focus") ? "focus" : "close"))
        .toEqual(["focus", "close"]);
    // ряд — після заголовка і коду, але перед таблицею паспорта, джерелами і даними центру
    expect(before(q(el, ".o_f3d_cardbody h3"), actions)).toBe(true);
    expect(before(q(el, ".o_f3d_cardbody .o_f3d_code"), actions)).toBe(true);
    expect(before(actions, q(el, ".o_f3d_cardbody .o_f3d_tbl"))).toBe(true);
    expect(before(actions, q(el, ".o_f3d_cardbody .o_f3d_src"))).toBe(true);
    expect(before(actions, q(el, ".o_f3d_cardbody .o_f3d_kv"))).toBe(true);
    expect(getComputedStyle(actions).position).toBe("sticky");
    // кнопки лишаються робочими
    q(el, ".o_f3d_c-close").click();
    expect(viewer.getState().selected).toBe(null);
});

// ------------------------------------------------------------------ вантаж комірок за живими залишками (R-19)

/** Фікстура «живих» даних: meta.live і залишки конкретних комірок (решта — як у демо). */
const liveStock = (locs) => (fx) => {
    fx.data.meta.live = true;
    fx.data.meta.database = "odoo";
    for (const [code, patch] of Object.entries(locs)) {
        Object.assign(fx.data.locations[code], patch);
    }
};
const quant = (n, extra = {}) => ({ product: "OF-C800", qty: 10, package: "PACK-T" + n, ...extra });
const hitOf = (viewer, code) => viewer.items.get(code).children.find((c) => c.userData.f3dStock);

test("R19b офлайн-демо без живих даних: статичний вантаж комірок лишається як є", async () => {
    const { viewer } = await mountViewer({ model: "core" });
    const sl = viewer.stockLoad;
    for (const code of ["FG-R1-B01-L4", "PLT-01A", "FUR-R1-S01-L1"]) {
        const i = sl.info(code);
        expect(i.managed).toBe(false);
        expect(i.hit).toBe(false);
    }
    expect(sl.info("FG-R1-B01-L4").staticVisible).toBe(true);
    expect(sl.stats()).toEqual({ pallet: 0, carton: 0, wrap: 0, box: 0 });
});

test("R19c палетна комірка: N = min(місткість, палети за пакетами); порожня — без вантажу, але клікабельна", async () => {
    const { viewer, el } = await mountViewer({
        model: "core",
        mutate: liveStock({
            "FG-R1-B01-L4": { quants: [], fill: 0 },                                  // у GLB 2 палети, в Odoo порожньо
            "FG-R1-B01-L3": { quants: [quant(1)], fill: 0.5 },                        // 1 квант → 1 палета
            "FG-R1-B01-L2": { quants: [quant(1), quant(2, { product: "BR-K4" }), quant(3)], fill: 1 }, // 3 пакети > місткості 2
            "FG-R1-B01-L1": { quants: [quant(7), quant(7, { qty: 4 })], fill: 1 },     // два кванти в одному пакеті → 1 палета
        }),
    });
    const sl = viewer.stockLoad;
    const empty = sl.info("FG-R1-B01-L4");
    expect(empty.managed).toBe(true);
    expect(empty.pallets).toBe(0);
    expect(empty.staticVisible).toBe(false);
    expect(empty.hit).toBe(true);
    expect(sl.info("FG-R1-B01-L3").pallets).toBe(1);
    expect(sl.info("FG-R1-B01-L2").pallets).toBe(2);
    expect(sl.info("FG-R1-B01-L1").pallets).toBe(1);
    expect(sl.info("FG-R1-B01-L3").staticVisible).toBe(false);
    // спільні InstancedMesh: палет рівно стільки, скільки в комірках ГП
    let sum = 0;
    for (const code of Object.keys(viewer.D.locations)) {
        if (code.startsWith("FG-")) {
            sum += sl.info(code)?.pallets ?? 0;
        }
    }
    expect(sl.stats().pallet).toBe(sum);
    expect(sum).toBeGreaterThan(3);
    // невидимий об'єм: матеріал не малюється, але комірку можна вибрати і картка показує живий рядок
    const hit = hitOf(viewer, "FG-R1-B01-L4");
    expect(hit.material.visible).toBe(false);
    viewer.select("FG-R1-B01-L4");
    expect(viewer.getState().selected).toBe("FG-R1-B01-L4");
    expect(txt(el, ".o_f3d_cardbody .o_f3d_live")).toBe("Порожньо");
    expect(text(el).includes("2 палет.")).toBe(false);
    viewer.select("FG-R1-B01-L3");
    expect(txt(el, ".o_f3d_cardbody .o_f3d_live").startsWith("За Odoo: 1 палета · ")).toBe(true);
});

test("R19d інші комірки: статичний вантаж лише при qty>0, а без нього — узагальнений блок × fill", async () => {
    const { viewer } = await mountViewer({
        model: "core",
        mutate: liveStock({
            "PLT-01B": { quants: [], fill: 0 },                                       // у сцені стос листів, в Odoo порожньо
            "PLT-01C": { quants: [{ product: "OF-C800", qty: 30 }], fill: 0.5 },      // стос є і залишок є → видно як є
            "PLT-01A": { quants: [{ product: "OF-C800", qty: 30 }], fill: 0.5 },      // у сцені лише порожній піддон
            "EB-U1-S4-L1": { quants: [{ product: "OF-C800", qty: 3 }], fill: null },  // у сцені взагалі немає вантажу
        }),
    });
    const sl = viewer.stockLoad;
    expect(sl.info("PLT-01B").staticVisible).toBe(false);
    expect(sl.info("PLT-01B").proc).toBe(false);
    expect(sl.info("PLT-01C").staticVisible).toBe(true);
    expect(sl.info("PLT-01C").proc).toBe(false);
    const g = sl.info("PLT-01A");
    expect(g.proc).toBe(true);
    expect(g.generic.hMax).toBe(1);
    expect(Math.abs(g.generic.h - 0.5)).toBeLessThan(0.001);                          // висота × fill
    const e = sl.info("EB-U1-S4-L1");
    expect(e.proc).toBe(true);
    expect(e.generic.h).toBe(e.generic.hMax);                                         // fill = null → повна висота
    expect(e.hit).toBe(true);
    expect(sl.stats().box).toBeGreaterThan(1);
});

test("R19e дельта і «Зараз»: вантаж перемальовується; режим «Заповненість» тонує об'єм порожньої комірки", async () => {
    const { viewer } = await mountViewer({
        model: "core",
        mutate: liveStock({ "FG-R1-B01-L4": { quants: [quant(1), quant(2)], fill: 1 } }),
    });
    const sl = viewer.stockLoad;
    expect(sl.info("FG-R1-B01-L4").pallets).toBe(2);
    viewer.applyPatch({ locations: { "FG-R1-B01-L4": { quants: [], fill: 0 } } });
    expect(sl.info("FG-R1-B01-L4").pallets).toBe(0);
    expect(sl.info("FG-R1-B01-L4").staticVisible).toBe(false);
    viewer.setMode("fill");
    const mat = hitOf(viewer, "FG-R1-B01-L4").material;
    expect(mat.visible).toBe(true);
    expect(mat.color.getHexString()).toBe("e74c3c");
    viewer.setMode("none");
    expect(hitOf(viewer, "FG-R1-B01-L4").material.visible).toBe(false);
    viewer.applyPatch({ locations: { "FG-R1-B01-L4": { quants: [quant(5)], fill: 0.5 } } });
    expect(sl.info("FG-R1-B01-L4").pallets).toBe(1);
});

test("R19f палети й рядок картки: чисті функції", async () => {
    expect(palletCount([])).toBe(0);
    expect(palletCount([{ qty: 5, package: "A" }, { qty: 3, package: "A" }, { qty: 0, package: "B" }])).toBe(1);
    expect(palletCount([{ qty: 5 }, { qty: 3 }])).toBe(2);              // без пакетів — число рядків
    const deps = { esc: (v) => v, nf: new Intl.NumberFormat("uk-UA"), plural: (n, a, b, c) => (n === 1 ? a : n < 5 ? b : c), name: (c) => "N-" + c, uom: () => "шт" };
    expect(liveLine({ kind: "pallet_cell", quants: [] }, deps)).toBe("Порожньо");
    expect(liveLine({ kind: "pallet_cell", quants: [{ product: "P1", qty: 12, package: "A" }, { product: "P2", qty: 8, package: "B" }] }, deps))
        .toBe("За Odoo: 2 палети · N-P1 12 шт, N-P2 8 шт");
    expect(liveLine({ kind: "stack", quants: [{ product: "P1", qty: 40 }] }, deps)).toBe("За Odoo: N-P1 40 шт");
});

// ------------------------------------------------------------------ вихід зі сторінки під час load() (R-14, збій loadFailed)

/** Відкладена відповідь: resolve/reject після destroy() (запит у польоті в момент виходу зі сторінки). */
const deferred = () => {
    const d = {};
    d.promise = new Promise((res, rej) => {
        d.resolve = res;
        d.reject = rej;
    });
    return d;
};
/** Перехопити console.error на час тесту: після destroy() помилок бути не повинно. */
const spyConsoleErrors = () => {
    const errs = [];
    const orig = console.error;
    console.error = (...a) => errs.push(a);
    after(() => {
        console.error = orig;
    });
    return errs;
};
const waitCall = async (fetch, part) => {
    for (let i = 0; i < 200 && !fetch.calls.some((u) => u.includes(part)); i++) {
        await tick();
    }
};

test("R19g destroy під час load(): відхилений /data не дає ні помилки в консолі, ні сповіщення", async () => {
    const errs = spyConsoleErrors();
    const gate = deferred();
    const { viewer, notes, fetch } = await mountViewer({
        model: "none",
        skipLoad: true,
        routes: { "/data": () => gate.promise },
    });
    const loading = viewer.load();
    await waitCall(fetch, "/data");
    viewer.destroy();
    gate.reject(new TypeError("Failed to fetch"));
    await loading; // не кидає: «Cannot read properties of null (reading 'classList')» був саме тут
    await tick();
    expect(notes).toEqual([]);
    expect(errs).toEqual([]);
});

test("R19h destroy під час load(): /static відхилено, /data успішний — тиша й без підписки на шину", async () => {
    const errs = spyConsoleErrors();
    const gate = deferred();
    const { viewer, notes, client, fetch } = await mountViewer({
        model: "none",
        skipLoad: true,
        routes: { "/static": () => gate.promise },
    });
    const loading = viewer.load();
    await waitCall(fetch, "/static");
    viewer.destroy();
    gate.reject(new Error("/static: 500"));
    await loading;
    await tick();
    expect(notes).toEqual([]);
    expect(errs).toEqual([]);
    expect(fetch.calls.some((u) => u.includes("/data"))).toBe(false); // після destroy наступний запит не йде
    expect(client.cb).toBe(null);
});

test("R19i destroy під час load(): успішні відповіді — DOM не чіпаємо, дані не застосовуємо", async () => {
    const errs = spyConsoleErrors();
    const gate = deferred();
    const { viewer, notes, fetch, fx } = await mountViewer({
        model: "none",
        skipLoad: true,
        routes: { "/data": () => gate.promise },
    });
    const loading = viewer.load();
    await waitCall(fetch, "/data");
    viewer.destroy();
    gate.resolve(json(fx.data));
    await loading;
    await tick();
    expect(notes).toEqual([]);
    expect(errs).toEqual([]);
    expect(viewer.D).toBe(undefined);
});

test("R19j після destroy: зміна стану клієнта й дельта-«full» не торкаються DOM", async () => {
    const errs = spyConsoleErrors();
    const { viewer, client, notes } = await mountViewer({ model: "none" });
    const core = viewer.core;
    viewer.destroy();
    client._setState("offline"); // syncConnState: пігулки вже немає
    core.applyPatch({ full: { bogus: true } }); // loadFailed після destroy мовчить
    await tick();
    expect(notes).toEqual([]);
    expect(errs).toEqual([]);
});

test("R19k без destroy збій /data лишається видимим: повідомлення й «немає даних»", async () => {
    const errs = spyConsoleErrors();
    const { el, notes } = await mountViewer({
        model: "none",
        routes: { "/data": () => new Response("", { status: 500 }) },
    });
    expect(notes.length).toBe(1);
    expect(notes[0][0].startsWith("Не вдалося завантажити дані")).toBe(true);
    expect(txt(el, ".o_f3d_odoo-state")).toBe("немає даних");
    expect(errs.length).toBe(1);
});

test("R19l destroy до завершення mount(): ядро не створюється, load() і applyParams() тихі", async () => {
    const errs = spyConsoleErrors();
    const { viewer, notes } = await mountViewer({ model: "none", skipMount: true });
    const mounting = viewer.mount();
    viewer.destroy();
    await mounting;
    await viewer.load();
    await viewer.applyParams({});
    expect(viewer.core).toBe(null);
    expect(notes).toEqual([]);
    expect(errs).toEqual([]);
});

test("R20 живі дані: прогрес імітується лише при meta.live=false", async () => {
    const sim = await mountViewer({ model: "none" });
    const wo = Object.values(sim.viewer.D.workorders).find((w) => w.state === "progress" && !w.blocked);
    const before = wo.progress;
    await advanceTime(3100);
    expect(wo.progress).toBeGreaterThan(before);
    const live = await mountViewer({
        model: "none",
        mutate: (fx) => {
            fx.data.meta.live = true;
            fx.data.meta.database = "odoo";
        },
    });
    const wo2 = Object.values(live.viewer.D.workorders).find((w) => w.state === "progress" && !w.blocked);
    const before2 = wo2.progress;
    await advanceTime(3100);
    expect(wo2.progress).toBe(before2);
});

test("R21 сценарій пожежної тривоги: 32 маршрути, маркери виходів", async () => {
    const { viewer, fx } = await mountViewer({ model: "core" });
    await viewer.startDrill();
    expect(viewer.getState().panel).toBe("drill");
    expect(viewer.core.drill.curves.length).toBe(Object.keys(fx.data.evacuation.routes).length);
    expect(viewer.core.drill.curves.length).toBe(32);
    expect(viewer.core.drill.marks.length).toBeGreaterThan(fx.data.evacuation.exits.length - 1);
    expect(fx.data.evacuation.exits.length).toBe(12);
    viewer.stopDrill();
    expect(viewer.getState().drill.on).toBe(false);
});

test("R22 вибір: select, Esc скидає, фокус на об'єкті", async () => {
    const { viewer } = await mountViewer({ model: "core" });
    viewer.select("SAW-1");
    viewer.focusOn("SAW-1");
    expect(viewer.getState().selected).toBe("SAW-1");
    key("Escape");
    expect(viewer.getState().selected).toBe(null);
    expect(viewer.getState().panel).toBe("tab");
});

test("R23 маячки верстатів: лампи статусу в моделі", async () => {
    const { viewer } = await mountViewer({ model: "core" });
    expect(viewer.core.lamps.length).toBeGreaterThan(0);
});

// ------------------------------------------------------------------ AC

test("params (AC-02): code/tab/mode і невідомий code", async () => {
    const a = await mountViewer({ model: "core" });
    await a.viewer.applyParams({ code: "SAW-1", tab: "production", mode: "oee" });
    const st = a.viewer.getState();
    expect([st.selected, st.tab, st.mode]).toEqual(["SAW-1", "production", "oee"]);
    const b = await mountViewer({ model: "core" });
    await b.viewer.applyParams({ code: "NOPE" });
    expect(b.viewer.getState().selected).toBe(null);
    expect(b.notes.some(([, t]) => t === "warning")).toBe(true);
    expect(b.viewer.getState().tab).toBe("overview");
    const c = await mountViewer({ model: "none" });
    await c.viewer.applyParams({ mo: "WH/MO/NOPE", layers: "prod" });
    expect(c.notes.some(([, t]) => t === "warning")).toBe(true);
});

test("three_local (AC-03): без запитів поза origin, THREE.REVISION=160", async () => {
    const { viewer, urls } = await mountViewer({ model: "core" });
    const { THREE } = await import(`${BASE}/lib/three/three-bundle.esm.js`);
    expect(THREE.REVISION).toBe("160");
    expect(urls.length).toBeGreaterThan(0);
    for (const u of urls) {
        expect(new URL(u, window.location.href).origin).toBe(window.location.origin);
    }
    expect(viewer.items.has("SAW-1")).toBe(true);
});

test("parts (AC-05): core одразу, engineering у фоні, fire за шаром", async () => {
    const { viewer } = await mountViewer({ model: "core" });
    expect(viewer.items.has("SAW-1")).toBe(true);
    await viewer.loadPart("engineering");
    expect(viewer.items.has("RV-05")).toBe(true);
    expect(viewer.items.has("FACP-1")).toBe(false);
    viewer.setLayer("fire", true);
    await viewer.loadPart("fire");
    expect(viewer.items.has("FACP-1")).toBe(true);
});

test("status_from_payload (AC-07): статус верстата береться з payload, а не з GLB", async () => {
    const { viewer, el } = await mountViewer({
        model: "core",
        mutate: (fx) => {
            fx.data.workcenters["CNC-2"].status = "stop";
        },
    });
    const lab = viewer.core.labels.find((l) => l.obj.userData.code === "CNC-2");
    expect(lab).not.toBe(undefined);
    expect(lab.lbl.element.innerHTML.includes("var(--f3d-bad)")).toBe(true);
    viewer.select("CNC-2");
    expect(txt(el, ".o_f3d_chip")).toBe("Зупинено");
    expect(q(el, ".o_f3d_chip").classList.contains("o_f3d_bad")).toBe(true);
});

test("open_record (AC-08): «Відкрити в Odoo»", async () => {
    const calls = [];
    const r = await mountViewer({
        model: "core",
        routes: {
            "/resolve": (url) => {
                calls.push(url);
                return json(
                    url.includes("code=SAW-1")
                        ? { model: "mrp.workcenter", res_id: 7, display_name: "Розкрій 1", kind: "workcenter" }
                        : { model: null, res_id: null, reason: "not_found" }
                );
            },
        },
    });
    r.viewer.select("SAW-1");
    q(r.el, ".o_f3d_c-open").click();
    await tick();
    await tick();
    expect(r.opened).toEqual([["mrp.workcenter", 7]]);
    r.viewer.select("SAW-2");
    q(r.el, ".o_f3d_c-open").click();
    await tick();
    await tick();
    // запису немає: без повідомлення «немає запису» — кнопка просто зникає (див. docs.test.js, open_group)
    expect(r.notes.some(([m]) => m.includes("SAW-2"))).toBe(false);
    expect(q(r.el, ".o_f3d_c-open")).toBe(null);
});

test("open_record (AC-08): картки документів ведуть через resolve({name})", async () => {
    const r = await mountViewer({
        model: "none",
        routes: {
            "/resolve": (url) =>
                json(url.includes("name=WH%2FMO%2F00231") ? { model: "mrp.production", res_id: 231 } : { model: null, reason: "not_found" }),
        },
    });
    r.viewer.showMO("WH/MO/00231");
    q(r.el, "[data-open]").click();
    await tick();
    await tick();
    expect(r.opened).toEqual([["mrp.production", 231]]);
    r.viewer.showPicking("WH/OUT/00412");
    q(r.el, "[data-open]").click();
    await tick();
    await tick();
    expect(r.notes.some(([m, t]) => m.includes("WH/OUT/00412") && t === "info")).toBe(true);
    // у кіоску кнопок «Відкрити в Odoo» немає
    const k = await mountViewer({ model: "none", kiosk: true, viewerOpts: { onOpenRecord: undefined } });
    k.viewer.showMO("WH/MO/00231");
    expect(k.el.querySelector("[data-open]")).toBe(null);
});

test("theme (AC-09): темна тема змінює фон сцени", async () => {
    const { viewer, el } = await mountViewer({ model: "none" });
    const light = viewer.scene.background.getHexString();
    document.documentElement.dataset.theme = "dark";
    await animationFrame();
    await tick();
    expect(el.dataset.theme).toBe("dark");
    expect(viewer.scene.background.getHexString()).toBe("1a2027");
    expect(light).not.toBe("1a2027");
    delete document.documentElement.dataset.theme;
});

test("lite (AC-30): тіні вимкнені, pixelRatio=1,5 на десктопі (надвибірка замість MSAA), без environment, 1 частинка, лише core+engineering", async () => {
    const { viewer, el } = await mountViewer({ model: "core", lite: 1 });
    expect(viewer.getState().lite).toBe(true);
    expect(viewer.renderer.shadowMap.enabled).toBe(false);
    expect(viewer.renderer.getPixelRatio()).toBe(1.5);
    expect(viewer.scene.environment).toBe(null);
    expect(q(el, ".o_f3d_opt-shadows").closest("label").hidden).toBe(true);
    const sink = [];
    const parts = viewer.core.branchParticles(
        { getLength: () => 10, getPointAt: () => ({ x: 0, y: 0, z: 0 }) },
        0x888888,
        3,
        sink,
        null
    );
    expect(parts.length).toBe(1);
    await viewer.partsReady();
    expect(viewer.items.has("RV-05")).toBe(true);
    expect(viewer.items.has("FACP-1")).toBe(false);
    expect(viewer.items.has("SECURITY-1") || viewer.items.has("KPP-1")).toBe(false);
});

test("lite (AC-31): deviceMemory=4 → lite, localStorage f3d.lite=0 → ні", () => {
    const nav = { deviceMemory: 4 };
    const win = { innerWidth: 1920, matchMedia: () => ({ matches: false }) };
    expect(detectLite({ nav, win })).toBe(true);
    const storage = { getItem: (k) => (k === "f3d.lite" ? "0" : null) };
    expect(detectLite({ nav, win, storage })).toBe(false);
    expect(detectLite({ nav: { deviceMemory: 16 }, win })).toBe(false);
    expect(detectLite({ nav: {}, win: { innerWidth: 1200, matchMedia: () => ({ matches: true }) } })).toBe(true);
    expect(detectLite({ lite: "auto", kiosk: true, params: { lite: "0" }, nav: {}, win })).toBe(false);
    expect(detectLite({ lite: "auto", kiosk: true, nav: {}, win })).toBe(true);
});

test("schema_guard (AC-37): /static зі схемою 2.0 → danger, панель не рендериться", async () => {
    const { el, notes } = await mountViewer({
        model: "none",
        mutate: (fx) => {
            fx.static.meta.schema = "2.0";
        },
    });
    expect(notes.some(([, t]) => t === "danger")).toBe(true);
    expect(qa(el, ".o_f3d_kpi").length).toBe(0);
    expect(() => mergeData({ meta: { schema: "2.0" } }, {})).toThrow(SchemaError);
});

test("merge (AC-47): статика + живі дані, глибоке злиття спільних розділів", async () => {
    const st = {
        meta: { schema: "1.1", built_at: "T0" },
        energy: { consumers: { "SAW-1": { p_inst: 24 } } },
        layout: { W: 150 },
        locations: { A: { x: 1 } },
    };
    const live = { meta: { schema: "1.1", now: "2026-10-12 10:30" }, energy: { consumers: { "SAW-1": { p_now: 13.1 } } }, locations: { B: {} } };
    const D = mergeData(st, live);
    expect(D.energy.consumers["SAW-1"]).toEqual({ p_inst: 24, p_now: 13.1 });
    expect(D.static.layout).toEqual({ W: 150 });
    expect("layout" in D).toBe(false);
    expect(Object.keys(D.locations)).toEqual(["B"]);
    expect(D.meta.built_at).toBe("T0");
    expect(D.meta.now).toBe("2026-10-12 10:30");
    const dst = { a: { b: 1, c: 2 }, l: [1] };
    deepMerge(dst, { a: { b: null, d: 3 }, l: [2] });
    expect(dst).toEqual({ a: { c: 2, d: 3 }, l: [2] });
});

test("null_renderer (AC-51): render=null, 4 KPI, select відкриває картку", async () => {
    const { viewer, el } = await mountViewer({ model: "core" });
    expect(viewer.getState().renderer).toBe("null");
    expect(qa(el, ".o_f3d_kpi").length).toBe(4);
    viewer.select("SAW-1");
    expect(viewer.getState().panel).toBe("object");
});

test("file_client (AC-38): те саме ядро на FileClient, R10 і R11", async () => {
    const fx = await loadFixtures();
    const calls = [];
    const client = new FileClient("/f3d/viewer/odoo_demo.json", {
        fetch: (u, i) => {
            calls.push(u);
            return Promise.resolve(json(fx.data));
        },
    });
    const el = document.createElement("div");
    el.style.cssText = "height:600px;width:1000px";
    document.body.appendChild(el);
    const viewer = new F3dViewer(el, {
        client,
        testMode: true,
        storage: null,
        threeUrl: `${BASE}/lib/three/three-bundle.esm.js`,
        manifest: { dims: fx.manifest.dims, layers: fx.manifest.layers, parts: [] },
    });
    await viewer.mount();
    await viewer.load();
    expect(calls.length).toBe(1);
    expect(qa(el, ".o_f3d_kpi").length).toBe(4);
    viewer.openTab("production");
    expect(qa(el, ".o_f3d_rows li").length).toBe(fx.data.productions.length);
    viewer.destroy();
    el.remove();
});

test("apply_patch_deep_merge (AC-58): глибоке злиття, null прибирає ключ, списки за name", async () => {
    const { viewer } = await mountViewer({ model: "none" });
    const D = viewer.D;
    const cardsBefore = Object.keys(D.infra.cards);
    D.workcenters["SAW-1"].machine_state = "work";
    const mo0 = D.productions[0];
    const n = D.productions.length;
    viewer.applyPatch({
        infra: { cards: { "PV-INV": { rows: [["Зараз", "468 кВт"]] }, "ZZ-DUCK": { rows: [] } }, totals: { pv_now: 468 } },
        workcenters: { "SAW-1": { oee: 0.5 } },
        workorders: { WO00051: { blocked: null } },
        productions: [{ name: mo0.name, progress: 0.77 }],
    });
    for (const c of cardsBefore) {
        expect(c in D.infra.cards).toBe(true);
    }
    expect("PV-INV" in D.infra.cards && "ZZ-DUCK" in D.infra.cards).toBe(true);
    expect(D.infra.totals.pv_now).toBe(468);
    expect(D.workcenters["SAW-1"].machine_state).toBe("work");
    expect(D.workcenters["SAW-1"].oee).toBe(0.5);
    expect("blocked" in D.workorders.WO00051).toBe(false);
    expect(D.productions.length).toBe(n);
    expect(D.productions[0].progress).toBe(0.77);
    expect(D.productions[1].name).toBe(viewer.idx.mo.get(D.productions[1].name).name);
    // видалення й сигнали
    const last = D.productions[n - 1].name;
    viewer.applyPatch({
        removed: { productions: [last] },
        signals: [{ path: "energy/consumers/SAW-1/p_now", value: 99.5 }],
    });
    expect(D.productions.length).toBe(n - 1);
    expect(D.energy.consumers["SAW-1"].p_now).toBe(99.5);
});

test("outdoor_zones (AC-61): контур надвірної зони з polygon, Z-ROOF лише з roofdeck", async () => {
    const { viewer } = await mountViewer({
        model: "none",
        mutate: (fx) => {
            fx.data.zones["Z-YARD-W"] = {
                name: "Двір західний", zone_type: "outdoor", polygon: [[0, 0], [10, 0], [10, 8], [0, 8]],
                locations: [], workcenters: [],
            };
            fx.data.zones["Z-ROOF"] = {
                name: "Покрівля", is_roof: true, polygon: [[10, 10], [30, 10], [30, 30], [10, 30]],
                locations: [], workcenters: [],
            };
        },
    });
    expect("Z-YARD-W" in (viewer.D.static.layout.zones || {})).toBe(false);
    const yard = viewer.items.get("Z-YARD-W");
    expect(yard).not.toBe(undefined);
    expect(yard.userData.kind).toBe("zone");
    const roof = viewer.items.get("Z-ROOF");
    expect(roof.visible).toBe(false);
    viewer.setLayer("roofdeck", true);
    expect(roof.visible).toBe(true);
    viewer.select("Z-YARD-W");
    expect(viewer.getState().panel).toBe("object");
});

test("fire_drill_auto: автостарт і автостоп навчання за drill_active", async () => {
    const { viewer } = await mountViewer({
        model: "core",
        mutate: (fx) => {
            fx.data.evacuation.drill_active = null;
        },
    });
    expect(viewer.getState().drill.on).toBe(false);
    viewer.applyPatch({ evacuation: { drill_active: { name: "DRILL/2026/0003", zone_code: "FA-CNC", elapsed_s: 40 } } });
    await viewer.partsReady();
    for (let i = 0; i < 50 && !viewer.getState().drill.on; i++) {
        await tick();
        await advanceTime(50);
    }
    const st = viewer.getState();
    expect(st.panel).toBe("drill");
    expect(st.drill.t).toBeGreaterThan(39);
    // ручна зупинка не перезапускає навчання з тим самим name
    viewer.stopDrill();
    viewer.applyPatch({ meta: { now: viewer.D.meta.now } });
    await tick();
    expect(viewer.getState().drill.on).toBe(false);
    viewer.applyPatch({ evacuation: { drill_active: null } });
    expect(viewer.getState().drill.on).toBe(false);
});

test("fire_states_devices (AC-62): стани груп, чипи, маркери пристроїв", async () => {
    const { viewer, el } = await mountViewer({ model: "core" });
    const [g1, g2, g3] = Object.keys(viewer.D.fire.groups);
    viewer.applyPatch({
        fire: {
            groups: { [g1]: { state: "alarm" }, [g2]: { state: "prealarm" }, [g3]: { state: "fault" } },
            devices: {
                "2.CNC.05": { type: "smoke", x: 75.0, y: 20.0, z: 8.6, zone: "Z-CNC", state: "alarm", dust: 0.12 },
            },
        },
    });
    await viewer.partsReady();
    viewer.setLayer("fire", true);
    await viewer.loadPart("fire");
    viewer.select(g1);
    expect(kv(el)["Стан"]).toBe("Тривога");
    expect(txt(el, ".o_f3d_pill")).toBe("Тривога");
    expect(q(el, ".o_f3d_pill").classList.contains("o_f3d_bad")).toBe(true);
    viewer.select(g2);
    expect(txt(el, ".o_f3d_pill")).toBe("Передтривога");
    expect(q(el, ".o_f3d_pill").classList.contains("o_f3d_warn")).toBe(true);
    viewer.select(g3);
    expect(txt(el, ".o_f3d_pill")).toBe("Несправність");
    const dev = viewer.items.get("2.CNC.05");
    expect(dev).not.toBe(undefined);
    expect(dev.visible && dev.parent.visible).toBe(true);
    viewer.select("2.CNC.05");
    expect(text(el).includes("smoke")).toBe(true);
    expect(text(el).includes("12%")).toBe(true);
    viewer.select(null);
    viewer.openTab("overview");
    expect(qa(el, ".o_f3d_rows li")[0] !== undefined).toBe(true);
});

test("access_rows (AC-63): рядки СКУД у картках людини й зони", async () => {
    const mut = (fx) => {
        Object.assign(fx.data.employees["OP-SAW-1"], {
            present: true,
            zone: "Z-CUT",
            zone_since: "2026-10-12 07:02",
            last_event: { ts: "2026-10-12 06:58", door: "KPP-IN", direction: "in", type: "pass" },
        });
        fx.data.zones["Z-CUT"].people_now = 6;
    };
    const { viewer, el } = await mountViewer({ model: "core", mutate: mut });
    viewer.select("OP-SAW-1");
    const emp = kv(el);
    expect(emp["На території"]).toBe("так");
    expect(emp["Зона"]).toBe(viewer.D.zones["Z-CUT"].name + " з 07:02");
    expect(emp["Останній прохід"]).toBe("06:58 · KPP-IN · вхід");
    viewer.select("Z-CUT");
    expect(kv(el)["Людей зараз"]).toBe("6");
    // відмова й вихід
    viewer.applyPatch({ employees: { "OP-SAW-1": { last_event: { ts: "2026-10-12 09:00", door: "KPP-IN", direction: "in", type: "deny" } } } });
    viewer.select("OP-SAW-1");
    expect(kv(el)["Останній прохід"]).toBe("09:00 · KPP-IN · відмова");
    // без td_access рядків немає
    const plain = await mountViewer({ model: "core" });
    plain.viewer.select("OP-SAW-1");
    expect("На території" in kv(plain.el)).toBe(false);
    plain.viewer.select("Z-CUT");
    expect("Людей зараз" in kv(plain.el)).toBe(false);
});

test("section_errors (§11): банер недоступного розділу при meta.sections=error", async () => {
    const { viewer, el } = await mountViewer({
        model: "none",
        mutate: (fx) => {
            fx.data.meta.sections = { energy: "error", products: "live" };
            fx.data.meta.errors = [{ provider: "td_energy", error: "KeyError" }];
        },
    });
    const b = q(el, ".o_f3d_sec-banner");
    expect(b).not.toBe(null);
    expect(b.textContent.includes("Розділ energy недоступний")).toBe(true);
    expect(b.textContent.includes("td_energy")).toBe(true);
    viewer.applyPatch({ meta: { errors: [] } });
    expect(q(el, ".o_f3d_sec-banner")).not.toBe(null); // sections лишились
    viewer.D.meta.sections.energy = "live";
    viewer.applyPatch({ meta: { errors: [] } });
    expect(q(el, ".o_f3d_sec-banner")).toBe(null);
});

test("snapshots_tag (R-17): мітка «знімки» при режимі snapshots", async () => {
    const snaps = [1, 2, 3].map((i) => ({ id: i, ts: "2026-10-12 0" + (6 + i) + ":00", kind: "periodic" }));
    const { viewer, el } = await mountViewer({
        model: "none",
        routes: { "/snapshots": () => json({ date: "2026-10-12", snapshots: snaps, mode: "snapshots" }) },
    });
    expect(q(el, ".o_f3d_snap-tag").hidden).toBe(true);
    viewer.setSimTime(600);
    await tick();
    await tick();
    expect(viewer.getState().playbackMode).toBe("snapshots");
    expect(q(el, ".o_f3d_snap-tag").hidden).toBe(false);
    viewer.setPlaybackMode("plan");
    expect(q(el, ".o_f3d_snap-tag").hidden).toBe(true);
});

// ------------------------------------------------------------------ згортання панелей і секцій

const memStorage = (init = {}) => {
    const data = { ...init };
    return { data, getItem: (k) => data[k] ?? null, setItem: (k, v) => { data[k] = String(v); } };
};
const bracket = (code) => window.dispatchEvent(new KeyboardEvent("keydown", { code, key: code === "BracketLeft" ? "х" : "ї", bubbles: true }));

test("ui_panels: краєві кнопки й клавіші [ ] згортають панелі, стан зберігається", async () => {
    const storage = memStorage();
    const { viewer, el } = await mountViewer({ model: "none", viewerOpts: { storage } });
    const side = q(el, ".o_f3d_edge-side");
    const card = q(el, ".o_f3d_edge-card");
    expect(el.classList.contains("o_f3d_side-off")).toBe(false);
    expect(side.getAttribute("aria-expanded")).toBe("true");
    side.click();
    expect(el.classList.contains("o_f3d_side-off")).toBe(true);
    expect(side.getAttribute("aria-expanded")).toBe("false");
    expect(viewer.getState().ui).toEqual({ side: false, card: true, collapsed: [] });
    expect(JSON.parse(storage.data["f3d.ui"])).toEqual({ side: false, card: true, collapsed: [] });
    bracket("BracketRight");
    expect(el.classList.contains("o_f3d_card-off")).toBe(true);
    expect(card.getAttribute("aria-expanded")).toBe("false");
    bracket("BracketLeft");
    expect(el.classList.contains("o_f3d_side-off")).toBe(false);
    // новий екземпляр із тим самим сховищем: права панель лишається згорнутою
    const again = await mountViewer({ model: "none", viewerOpts: { storage } });
    expect(again.el.classList.contains("o_f3d_card-off")).toBe(true);
    expect(again.el.classList.contains("o_f3d_side-off")).toBe(false);
    // явний показ документа розгортає панель, але не змінює збережений стан
    again.viewer.showMO("WH/MO/00231");
    expect(again.el.classList.contains("o_f3d_card-off")).toBe(false);
    expect(JSON.parse(storage.data["f3d.ui"]).card).toBe(false);
});

test("ui_panels: недоступне або пошкоджене сховище не ламає переглядач", async () => {
    const broken = { getItem: () => "{не json", setItem: () => { throw new Error("quota"); } };
    const { viewer, el } = await mountViewer({ model: "none", viewerOpts: { storage: broken } });
    expect(el.classList.contains("o_f3d_side-off")).toBe(false);
    q(el, ".o_f3d_edge-card").click();
    expect(viewer.getState().ui.card).toBe(false);
});

test("ui_folds: секції згортаються кліком по заголовку, стан переживає перемальовування й збереження", async () => {
    const storage = memStorage();
    const { viewer, el } = await mountViewer({ model: "none", viewerOpts: { storage } });
    const toggle = (id) => q(el, `[data-fold="${id}"] .o_f3d_fold-t`).click();
    expect(qa(el, ".o_f3d_side [data-fold]").map((s) => s.dataset.fold)).toEqual(["views", "color", "layers", "show"]);
    expect(qa(el, ".o_f3d_card [data-fold]").map((s) => s.dataset.fold)).toEqual(["kpi", "attn"]);
    toggle("views");
    toggle("attn");
    expect(q(el, '[data-fold="views"]').classList.contains("o_f3d_collapsed")).toBe(true);
    expect(q(el, '[data-fold="views"] .o_f3d_fold-t').getAttribute("aria-expanded")).toBe("false");
    expect(q(el, '[data-fold="color"]').classList.contains("o_f3d_collapsed")).toBe(false);
    viewer.openTab("production");
    viewer.openTab("overview");
    expect(q(el, '[data-fold="attn"]').classList.contains("o_f3d_collapsed")).toBe(true);
    expect(q(el, '[data-fold="kpi"]').classList.contains("o_f3d_collapsed")).toBe(false);
    expect(qa(el, ".o_f3d_kpis .o_f3d_kpi").length).toBe(4);
    expect(JSON.parse(storage.data["f3d.ui"]).collapsed.sort()).toEqual(["attn", "views"]);
    const again = await mountViewer({ model: "none", viewerOpts: { storage } });
    expect(q(again.el, '[data-fold="views"]').classList.contains("o_f3d_collapsed")).toBe(true);
    expect(q(again.el, '[data-fold="attn"]').classList.contains("o_f3d_collapsed")).toBe(true);
    q(again.el, '[data-fold="views"] .o_f3d_fold-t').click();
    expect(q(again.el, '[data-fold="views"]').classList.contains("o_f3d_collapsed")).toBe(false);
});
