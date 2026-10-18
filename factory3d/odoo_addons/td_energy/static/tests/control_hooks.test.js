/** @odoo-module */
// W2 (§3.4): хуки клієнта «Енергетика» для td_energy_control і td_energy_viewer3d.
// AC-292: `viewerLinks.default` у «Відкрити в 3D» / «Показати в 3D» (без моста — шлях W1, ключ `layers`);
// AC-301: кнопки панелі вузла з реєстру `td_energy.node_actions`; AC-302: баннер «Виконано» Пульту.
import { Component, xml } from "@odoo/owl";
import { describe, expect, test } from "@odoo/hoot";
import { animationFrame } from "@odoo/hoot-mock";
import { click, queryAll, queryAllTexts, queryOne, queryText, waitFor } from "@odoo/hoot-dom";
import { defineMailModels } from "@mail/../tests/mail_test_helpers";
import { mockService, mountWithCleanup, onRpc } from "@web/../tests/web_test_helpers";
import { registry } from "@web/core/registry";
import { viewerLinks, useEnergyActions } from "@td_energy/common/actions";
import { Pult } from "@td_energy/pult/pult";
import { SldCanvas, nodeActions } from "@td_energy/pult/sld";
import { CONTRACTS } from "./fixtures/contracts";

describe.current.tags("desktop");

defineMailModels();

const clone = (value) => JSON.parse(JSON.stringify(value));
const PULT = CONTRACTS["API-05"];
const SLD = PULT.sld;

/** Порожній реєстр: тест не залежить від того, які модулі W2 встановлені (реєстри відновлюються після тесту). */
function clearRegistry(reg) {
    for (const [key] of reg.getEntries()) {
        reg.remove(key);
    }
}

class Probe extends Component {
    static template = xml`<div class="o_probe"/>`;
    static props = ["*"];
    setup() {
        this.actions = useEnergyActions();
    }
}

async function mountProbe() {
    const probe = await mountWithCleanup(Probe);
    return probe.actions;
}

// ------------------------------------------------------------------ AC-292

test("viewerLinks — реєстр td_energy.viewer_links", () => {
    expect(viewerLinks).toBe(registry.category("td_energy.viewer_links"));
});

test("AC-292: «Відкрити в 3D» і «Показати в 3D» ходять через viewerLinks.default", async () => {
    clearRegistry(viewerLinks);
    const opened = [];
    viewerLinks.add("default", { open: async (opts) => opened.push(opts) });
    const rpcs = [];
    onRpc("td.energy.node", "search_read", ({ args }) => rpcs.push(args));
    onRpc("td.energy.node", "action_f3d_show", () => rpcs.push("show"));
    const actions = await mountProbe();
    await actions.openViewer();
    await actions.show3d("QS");
    expect(opened).toEqual([{ code: undefined }, { code: "QS" }]);
    expect(rpcs).toEqual([]); // вузол без equipment_id: пошуку id і action_f3d_show немає
});

test("AC-292: без моста «Показати в 3D» — метод вузла W1 (action_f3d_show)", async () => {
    clearRegistry(viewerLinks);
    const done = [];
    mockService("action", { doAction: (action) => done.push(action) });
    onRpc("td.energy.node", "search_read", () => [{ id: 7 }]);
    onRpc("td.energy.node", "action_f3d_show", ({ args }) => {
        expect(args).toEqual([[7]]);
        return { type: "ir.actions.client", tag: "f3d_viewer.action", params: { select: "T1" } };
    });
    const actions = await mountProbe();
    await actions.show3d("T1");
    expect(done.length).toBe(1);
    expect(done[0].tag).toBe("f3d_viewer.action");
});

test("AC-292: без моста «Відкрити в 3D» — f3d_viewer.action з layers=['energy'] (ключ layer виправлено)", async () => {
    clearRegistry(viewerLinks);
    registry.category("actions").add("f3d_viewer.action", class extends Component {
        static template = xml`<div/>`;
        static props = ["*"];
    });
    const done = [];
    mockService("action", { doAction: (action) => done.push(action) });
    const actions = await mountProbe();
    await actions.openViewer();
    expect(done.length).toBe(1);
    expect(done[0].tag).toBe("f3d_viewer.action");
    expect(done[0].params.layers).toEqual(["energy"]);
    expect("layer" in done[0].params).toBe(false);
});

test("AC-292: без моста й без модуля переглядача — сповіщення, без дії", async () => {
    clearRegistry(viewerLinks);
    registry.category("actions").remove("f3d_viewer.action");
    const notified = [];
    mockService("notification", { add: (message, options) => notified.push([message, options]) });
    mockService("action", { doAction: () => notified.push("doAction") });
    const actions = await mountProbe();
    await actions.openViewer();
    expect(notified.length).toBe(1);
    expect(notified[0][0]).toMatch(/3D-переглядача не встановлено/);
});

test("AC-292: кнопки Пульту (панель вузла, «Відкрити в 3D») використовують viewerLinks.default", async () => {
    clearRegistry(viewerLinks);
    const opened = [];
    viewerLinks.add("default", { open: async (opts) => opened.push(opts) });
    mockService("bus_service", { addChannel() {}, deleteChannel() {}, subscribe() {}, unsubscribe() {} });
    onRpc("td.energy.dashboard", "get_pult", () => clone(PULT));
    await mountWithCleanup(Pult, { props: { action: { context: {} } } });
    await animationFrame();
    await click(".o_td_en_open3d");
    await click("button[data-node-code='BW-2']");
    await animationFrame();
    await click(".o_td_en_sel_3d");
    expect(opened).toEqual([{ code: undefined }, { code: "BW-2" }]);
});

// ------------------------------------------------------------------ AC-301

/** Запис реєстру, що імітує `td_energy_control`: QS — за станом вимикача, BESS — за режимом. */
function stubEntry(calls) {
    return {
        match: (node) => ["QS", "BESS"].includes(node.code),
        actions: async (node, ctx) => {
            calls.push(Object.keys(ctx).sort());
            const closed = node.state === "ok";
            if (node.code === "QS") {
                return [{ code: closed ? "qs_open" : "qs_close", label: closed ? "Вимкнути QS…" : "Увімкнути QS…", cls: "o_td_en_btn--teal", onClick: () => calls.push(node.code) }];
            }
            return [{ code: "bess_charge", label: "Зарядити 50 кВт", cls: "o_td_en_btn--teal", onClick: () => calls.push(node.code) }];
        },
    };
}

test("AC-301: панель вузла QS/BESS містить кнопки з реєстру td_energy.node_actions", async () => {
    clearRegistry(nodeActions);
    const calls = [];
    nodeActions.add("td_energy_control", stubEntry(calls));
    const sld = clone(SLD);
    await mountWithCleanup(SldCanvas, { props: { sld, selected: "QS", onSelect() {} } });
    await animationFrame();
    expect(queryAllTexts(".o_td_en_node_action")).toEqual(["Увімкнути QS…"]);
    expect(queryOne(".o_td_en_node_action").classList.contains("o_td_en_btn--teal")).toBe(true);
    expect(queryOne(".o_td_en_node_action").classList.contains("o_td_en_btn")).toBe(true);
    expect(calls[0]).toEqual(["dialog", "fail", "notify", "orm", "reload"]);
    await click(".o_td_en_node_action");
    expect(calls.at(-1)).toBe("QS");
});

test("AC-301: стан вузла змінює набір кнопок (QS замкнений → «Вимкнути QS…»)", async () => {
    clearRegistry(nodeActions);
    nodeActions.add("td_energy_control", stubEntry([]));
    const sld = clone(SLD);
    sld.nodes.find((n) => n.code === "QS").state = "ok";
    await mountWithCleanup(SldCanvas, { props: { sld, selected: "QS", onSelect() {} } });
    await animationFrame();
    expect(queryAllTexts(".o_td_en_node_action")).toEqual(["Вимкнути QS…"]);
});

test("AC-301: BESS — «Зарядити 50 кВт»; вузол поза match — без додаткових кнопок", async () => {
    clearRegistry(nodeActions);
    nodeActions.add("td_energy_control", stubEntry([]));
    await mountWithCleanup(SldCanvas, { props: { sld: clone(SLD), selected: "BESS", onSelect() {} } });
    await animationFrame();
    expect(queryAllTexts(".o_td_en_node_action")).toEqual(["Зарядити 50 кВт"]);
});

test("AC-301: вузол без збігу в реєстрі — панель як у W1", async () => {
    clearRegistry(nodeActions);
    nodeActions.add("td_energy_control", stubEntry([]));
    await mountWithCleanup(SldCanvas, { props: { sld: clone(SLD), selected: "BW-2", onSelect() {} } });
    await animationFrame();
    expect(queryAll(".o_td_en_sel").length).toBe(1);
    expect(queryAll(".o_td_en_node_action").length).toBe(0);
    expect(queryAll(".o_td_en_sel_card").length).toBe(1);
});

test("AC-301: без реєстру (порожній) панель QS — як у W1", async () => {
    clearRegistry(nodeActions);
    await mountWithCleanup(SldCanvas, { props: { sld: clone(SLD), selected: "QS", onSelect() {} } });
    await animationFrame();
    expect(queryAll(".o_td_en_sel").length).toBe(1);
    expect(queryAll(".o_td_en_node_action").length).toBe(0);
    expect(queryAll(".o_td_en_sel_3d").length).toBe(1);
});

test("AC-301: збій розширення не ламає панель вузла; disabled/title передаються кнопці", async () => {
    clearRegistry(nodeActions);
    nodeActions.add("broken", {
        match: () => true,
        actions: async () => {
            throw new Error("boom");
        },
    });
    nodeActions.add("grey", {
        match: (node) => node.code === "QS",
        actions: async () => [{ code: "x", label: "Недоступно", cls: "", disabled: true, title: "Причина", onClick() {} }],
    });
    await mountWithCleanup(SldCanvas, { props: { sld: clone(SLD), selected: "QS", onSelect() {} } });
    await animationFrame();
    expect(queryAll(".o_td_en_sel").length).toBe(1);
    const btn = queryOne(".o_td_en_node_action");
    expect(btn.disabled).toBe(true);
    expect(btn.getAttribute("title")).toBe("Причина");
});

test("AC-301: після дії Пульт перечитує схему, тривоги й рекомендацію", async () => {
    clearRegistry(nodeActions);
    nodeActions.add("td_energy_control", {
        match: (node) => node.code === "QS",
        actions: async () => [{ code: "qs_close", label: "Увімкнути QS…", cls: "", onClick: async () => {} }],
    });
    mockService("bus_service", { addChannel() {}, deleteChannel() {}, subscribe() {}, unsubscribe() {} });
    const calls = [];
    onRpc("td.energy.dashboard", "get_pult", ({ kwargs }) => {
        calls.push(kwargs.parts);
        return clone(PULT);
    });
    await mountWithCleanup(Pult, { props: { action: { context: {} } } });
    await animationFrame();
    await click("button[data-node-code='QS']");
    await waitFor(".o_td_en_node_action");
    await click(".o_td_en_node_action");
    await animationFrame();
    expect(calls.at(-1)).toEqual(["sld", "alarms", "advice"]);
});

// ------------------------------------------------------------------ AC-302

function mockPult(patch) {
    mockService("bus_service", { addChannel() {}, deleteChannel() {}, subscribe() {}, unsubscribe() {} });
    onRpc("td.energy.dashboard", "get_pult", () => {
        const data = clone(PULT);
        patch(data);
        return data;
    });
}

const DONE_BANNER = {
    id: 7,
    code: "EXPORT-T2",
    state: "done",
    level: "info",
    node_code: "T2",
    title: "Виконано: BESS заряджається 50 кВт",
    text: "Експорт через T2 усунено.",
    actions: [{ code: "undo", label: "Скасувати", kind: "control", class: "A", enabled: true, params: { command_kind: "undo", action_id: 55 } }],
};

test("AC-302: advice.state==='done' — зелений баннер без «Пізніше», із «Скасувати»", async () => {
    clearRegistry(registry.category("td_energy.advice_handlers"));
    const handled = [];
    registry.category("td_energy.advice_handlers").add("control", async (payload) => {
        handled.push(payload.action.code);
        return true;
    });
    mockPult((data) => {
        data.advice = clone(DONE_BANNER);
    });
    await mountWithCleanup(Pult, { props: { action: { context: {} } } });
    await animationFrame();
    const banner = queryOne(".o_td_en_advice");
    expect(banner.classList.contains("o_td_en_advice--done")).toBe(true);
    expect(queryText(".o_td_en_advice_text")).toMatch(/Виконано: BESS заряджається 50 кВт/);
    expect(queryAll(".o_td_en_advice_later").length).toBe(0);
    expect(queryAllTexts(".o_td_en_advice_act")).toEqual(["Скасувати"]);
    await click(".o_td_en_advice_act");
    expect(handled).toEqual(["undo"]);
});

test("AC-302: звичайна рекомендація — без класу --done, «Пізніше» є", async () => {
    mockPult(() => {});
    await mountWithCleanup(Pult, { props: { action: { context: {} } } });
    await animationFrame();
    expect(queryOne(".o_td_en_advice").classList.contains("o_td_en_advice--done")).toBe(false);
    expect(queryAll(".o_td_en_advice_later").length).toBe(1);
});
