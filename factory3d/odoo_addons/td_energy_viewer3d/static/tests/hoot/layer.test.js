/** @odoo-module */
// HOOT: розширення «Енергетика в 3D» (SPEC 8.4.3): UI-23 EnergyLayerExtension, UI-24 StateColors (AC-288), UI-26 NodeBlock (AC-290).
import { describe, expect, test } from "@odoo/hoot";
import { energyLayer } from "@td_energy_viewer3d/layer/energy_layer";
import { MODE_KEY, chipHtml, sceneStates, stateColor, worstState } from "@td_energy_viewer3d/layer/colors";
import { firstMesh, makeLayer, mountEnergy } from "./helpers";

describe.current.tags("desktop");

const q = (el, sel) => el.querySelector(sel);
const qa = (el, sel) => [...el.querySelectorAll(sel)];
const text = (el) => (el.textContent || "").replace(/\s+/g, " ").trim();
const hex = (viewer, code) => firstMesh(viewer.items.get(code)).material.emissive.getHexString();

test("UI23 EnergyLayerExtension: режим «Електромережа: стан вузлів» з'являється лише коли в D є energy.layer", async () => {
    const withLayer = await mountEnergy({ engineering: false });
    const radio = q(withLayer.el, '.o_f3d_radio input[value="td_energy"]');
    expect(radio.closest("label").hidden).toBe(false);
    expect(radio.closest("label").textContent.trim()).toBe("Електромережа: стан вузлів");
    withLayer.viewer.destroy();
    const old = await mountEnergy({ layer: null, engineering: false }); // старий сервер: без шару розширення неактивне
    expect(q(old.el, '.o_f3d_radio input[value="td_energy"]').closest("label").hidden).toBe(true);
    expect(energyLayer.cardBlocks("BW-2", old.viewer.D, null)).toEqual([]);
});

test("UI23 applyData оновлює стан лише коли змінилась секція energy; дельта замінює вузли й тривоги цілком", async () => {
    const { viewer } = await mountEnergy({ engineering: false });
    const st = energyLayer.states.get(viewer.scene);
    const v0 = st.version;
    viewer.applyPatch({ locations: {} }); // не energy: стан не перебудовується
    expect(st.version).toBe(v0);
    const layer = makeLayer();
    layer.nodes = layer.nodes.slice(0, 2);
    layer.alarms = [];
    viewer.applyPatch({ energy: { layer } });
    expect(st.version).toBe(v0 + 1);
    expect(viewer.D.energy.layer.nodes.length).toBe(2); // списки замінюються, а не склеюються
    expect(viewer.D.energy.layer.alarms.length).toBe(0);
    expect(viewer.D.energy.layer.thresholds.warn_pct).toBe(80);
});

test("AC-288 StateColors: ok/warn/alarm/gen/off → зелений/жовтий/червоний/бурштиновий/сірий; невідомий scene → null", async () => {
    const { viewer, el } = await mountEnergy();
    const T = energyLayer.THREE;
    const col = (h) => new T.Color(h).getHexString();
    await viewer.applyParams({ mode: "td_energy" });
    expect(viewer.getState().mode).toBe(MODE_KEY);
    expect(hex(viewer, "BW-2")).toBe(col("#27ae60"));
    expect(hex(viewer, "PFC-2")).toBe(col("#f39c12"));
    expect(hex(viewer, "CABLES")).toBe(col("#e74c3c")); // C1 ok + C2 alarm → найгірший
    expect(hex(viewer, "PV-INV")).toBe(col("#b45309"));
    expect(hex(viewer, "CHP")).toBe(col("#9ca3af"));
    expect(firstMesh(viewer.items.get("SAW-1")).material.emissive.getHex()).toBe(0); // немає в шарі
    const fake = { userData: { code: "NO-SUCH-SCENE" } };
    expect(energyLayer.modeColor("td_energy", fake, viewer.D)).toBe(null);
    expect(energyLayer.modeColor("power", viewer.items.get("BW-2"), viewer.D)).toBe(null);
    expect(energyLayer.modeColor("td_energy", viewer.items.get("BW-2"), { energy: {} })).toBe(null);
    // легенда з порогами
    const legend = text(q(el, ".o_f3d_cardbody .o_f3d_legend"));
    expect(legend.includes("норма")).toBe(true);
    expect(legend.includes("увага ≥ 80 %")).toBe(true);
    expect(legend.includes("тривога ≥ 100 % / немає даних")).toBe(true);
    expect(legend.includes("генерує/працює")).toBe(true);
    expect(legend.includes("вимкнено/резерв")).toBe(true);
    // пороги змінились у дельті → легенда оновилась
    viewer.applyPatch({ energy: { layer: { thresholds: { warn_pct: 70, alarm_pct: 95 } } } });
    expect(text(q(el, ".o_f3d_cardbody .o_f3d_legend")).includes("увага ≥ 70 %")).toBe(true);
    // стан змінився → колір оновився без перемикання режиму
    const layer = makeLayer();
    layer.nodes.find((n) => n.code === "BW-2").state = "alarm";
    viewer.applyPatch({ energy: { layer } });
    expect(hex(viewer, "BW-2")).toBe(col("#e74c3c"));
});

test("AC-288 чисті функції: worstState, sceneStates, stateColor, чип стану — текст, а не лише колір", () => {
    expect(worstState(["ok", "off"])).toBe("ok");
    expect(worstState(["ok", "gen", "warn"])).toBe("warn");
    expect(worstState(["warn", "alarm", "ok"])).toBe("alarm");
    expect(worstState([])).toBe("ok");
    const states = sceneStates(makeLayer());
    expect(states.get("CABLES")).toBe("alarm");
    expect(states.has("NOSCENE-1")).toBe(false);
    expect(stateColor({ ok: 1 }, makeLayer(), "BW-2")).toBe(1);
    expect(stateColor({ ok: 1 }, makeLayer(), "NO")).toBe(null);
    expect(stateColor({}, null, "BW-2")).toBe(null);
    const chips = { ok: "Норма", warn: "Увага", alarm: "Тривога", gen: "Генерує", off: "Вимкнено" };
    for (const [state, label] of Object.entries(chips)) {
        const div = document.createElement("div");
        div.innerHTML = chipHtml(state);
        expect(div.textContent).toBe(label);
        expect(div.firstElementChild.classList.contains("o_f3d_chip")).toBe(true);
    }
});

test("AC-290 NodeBlock: чип, P, струм/%, ≤ 3 тривоги, кнопка лише за card і openAction; клік → td_energy.node_card", async () => {
    const actions = [];
    const layer = makeLayer();
    for (let i = 0; i < 5; i++) {
        layer.alarms.push({ id: 300 + i, node: "BW-2", scene: "BW-2", level: "warn", title: "Тривога " + i, time: "13:0" + i, state: "active" });
    }
    layer.nodes[0].alarms = 5;
    const { viewer, el } = await mountEnergy({ layer, viewerOpts: { onOpenAction: (a) => actions.push(a) } });
    viewer.select("BW-2");
    const blk = q(el, '.o_f3d_cardbody .o_td_en_node[data-node="BW-2"]');
    expect(text(blk.querySelector(".o_f3d_chip"))).toBe("Норма");
    const body = text(blk);
    expect(body.includes("P 124 кВт")).toBe(true);
    expect(body.includes("192 А · 30 %")).toBe(true);
    expect(qa(blk, ".o_td_en_alarms li").length).toBe(3);
    expect(text(q(blk, ".o_td_en_alarms li")).includes("Тривога 0")).toBe(true); // порядок як у шарі
    const btn = q(blk, "button[data-ext]");
    expect(btn.dataset.ext).toBe("td_energy:open_card:BW-2");
    expect(text(btn)).toBe("Відкрити картку вузла");
    btn.click();
    expect(actions).toEqual([{ type: "ir.actions.client", tag: "td_energy.node_card", name: "BW-2", params: { code: "BW-2" } }]);
    // сцена з двома вузлами (CABLES) — по блоку на вузол; стан кожного свій
    viewer.select("CABLES");
    expect(qa(el, ".o_td_en_node").map((b) => b.dataset.node)).toEqual(["C1", "C2"]);
    expect(text(q(el, '.o_td_en_node[data-node="C2"] .o_f3d_chip'))).toBe("Тривога");
    expect(text(q(el, '.o_td_en_node[data-node="C2"]')).includes("P 128 кВт")).toBe(true);
    // вузол з card=false — без кнопки
    viewer.select("QS");
    expect(text(q(el, '.o_td_en_node[data-node="QS"] .o_f3d_chip'))).toBe("Вимкнено");
    expect(q(el, '.o_td_en_node[data-node="QS"] button')).toBe(null);
    // об'єкт, якого немає в шарі, — блоку немає
    viewer.select("SAW-1");
    expect(qa(el, ".o_td_en_node").length).toBe(0);
});

test("AC-290 без openAction (киоск) кнопки «Відкрити картку вузла» немає, чип і показники є", async () => {
    const { viewer, el } = await mountEnergy({ kiosk: true });
    viewer.select("BW-2");
    const blk = q(el, '.o_td_en_node[data-node="BW-2"]');
    expect(text(blk.querySelector(".o_f3d_chip"))).toBe("Норма");
    expect(q(blk, "button")).toBe(null);
});
