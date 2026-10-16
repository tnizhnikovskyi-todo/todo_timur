/** @odoo-module */
// HOOT-тести ядра переглядача на demo_payload.json + model_static.json (мок /static і /data), testMode=true.
// Сценарії R1…R23 — по одному test() на рядок реєстру (AC-06), далі AC-02/03/05/07/08/09/30/31/37/38/47/51/58/61/62/63.
import { describe, expect, test } from "@odoo/hoot";
import { advanceTime, animationFrame, tick } from "@odoo/hoot-mock";
import { FileClient, SchemaError, deepMerge, mergeData } from "@factory3d_viewer/viewer/data_client";
import { detectLite } from "@factory3d_viewer/viewer/lite";
import { F3dViewer } from "@factory3d_viewer/viewer/core";
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
    expect(r.notes.some(([m, t]) => m.includes("SAW-2") && t === "info")).toBe(true);
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

test("lite (AC-30): тіні вимкнені, pixelRatio=1, без environment, 1 частинка, лише core+engineering", async () => {
    const { viewer, el } = await mountViewer({ model: "core", lite: 1 });
    expect(viewer.getState().lite).toBe(true);
    expect(viewer.renderer.shadowMap.enabled).toBe(false);
    expect(viewer.renderer.getPixelRatio()).toBe(1);
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
    // без factory3d_access рядків немає
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
            fx.data.meta.errors = [{ provider: "factory3d_energy", error: "KeyError" }];
        },
    });
    const b = q(el, ".o_f3d_sec-banner");
    expect(b).not.toBe(null);
    expect(b.textContent.includes("Розділ energy недоступний")).toBe(true);
    expect(b.textContent.includes("factory3d_energy")).toBe(true);
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
