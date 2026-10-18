/** @odoo-module */
// UI-22 NodeActions (D-38, C-46): запис `td_energy_control` у `td_energy.node_actions`; кнопки панелі вузла QS/BESS
// за відповіддю API-27 (стан рахує сервер), клік → prepare → ConfirmDialog.
import { describe, expect, test } from "@odoo/hoot";
import { animationFrame } from "@odoo/hoot-mock";
import { click, queryAll, queryAllTexts, queryOne, queryText } from "@odoo/hoot-dom";
import { defineMailModels } from "@mail/../tests/mail_test_helpers";
import { mockService, mountWithCleanup, onRpc } from "@web/../tests/web_test_helpers";
import { MainComponentsContainer } from "@web/core/main_components_container";
import { registry } from "@web/core/registry";
import { SldCanvas } from "@td_energy/pult/sld";
import { CONTRACTS as W1 } from "@td_energy/../tests/fixtures/contracts";
import { nodeActionsEntry } from "@td_energy_control/handlers/node_actions";
import { clone, prepared } from "./fixtures/control_data";

describe.current.tags("desktop");

defineMailModels();

const SLD = W1["API-05"].sld;

const ROWS = {
    QS: {
        off: { code: "qs_close", label: "Увімкнути QS…", kind: "qs_close", cls: "B", enabled: true, disabled_reason: null },
        ok: { code: "qs_open", label: "Вимкнути QS…", kind: "qs_open", cls: "B", enabled: true, disabled_reason: null },
    },
    BESS: {
        idle: { code: "bess_charge", label: "Зарядити 50 кВт", kind: "bess_charge", cls: "A", enabled: true, disabled_reason: null },
        charging: { code: "bess_stop", label: "Зупинити заряд", kind: "bess_stop", cls: "A", enabled: true, disabled_reason: null },
    },
};

function mockNodes({ rows = null, prepareError = null } = {}) {
    const rec = { asked: [], prepare: [], toasts: [] };
    mockService("notification", {
        add: (message, options) => {
            rec.toasts.push([message, options && options.type]);
            return () => {};
        },
    });
    onRpc("td.energy.control", "get_node_actions", ({ args }) => {
        rec.asked.push(args[0]);
        if (rows) {
            return clone(rows);
        }
        return [args[0] === "QS" ? ROWS.QS.off : ROWS.BESS.idle];
    });
    onRpc("td.energy.control", "prepare", ({ args }) => {
        rec.prepare.push(args);
        if (prepareError) {
            throw new Error(prepareError);
        }
        return prepared();
    });
    onRpc("td.energy.control", "cancel", () => ({ action_id: 55, state: "cancelled" }));
    return rec;
}

async function mountSld(selected, { sld = SLD, onChanged = () => {} } = {}) {
    await mountWithCleanup(MainComponentsContainer);
    await mountWithCleanup(SldCanvas, { props: { sld: clone(sld), selected, onSelect() {}, onChanged } });
    await animationFrame();
}

test("UI-22: запис td_energy_control зареєстрований; match — лише QS і BESS", () => {
    const reg = registry.category("td_energy.node_actions");
    expect(reg.contains("td_energy_control")).toBe(true);
    expect(reg.get("td_energy_control")).toBe(nodeActionsEntry);
    expect(nodeActionsEntry.match({ code: "QS" })).toBe(true);
    expect(nodeActionsEntry.match({ code: "BESS" })).toBe(true);
    expect(nodeActionsEntry.match({ code: "BW-2" })).toBe(false);
});

test("AC-301/D-38: QS (вимкнений) — «Увімкнути QS…», стиль teal; клік → prepare(qs_close) → діалог", async () => {
    const rec = mockNodes();
    await mountSld("QS");
    expect(rec.asked).toEqual(["QS"]);
    expect(queryAllTexts(".o_td_en_node_action")).toEqual(["Увімкнути QS…"]);
    expect(queryOne(".o_td_en_node_action").classList.contains("o_td_en_btn--teal")).toBe(true);
    await click(".o_td_en_node_action");
    await animationFrame();
    expect(rec.prepare).toEqual([["qs_close", null]]);
    expect(queryAll(".o_td_en_cd").length).toBe(1);
});

test("AC-301/D-38: QS замкнений — «Вимкнути QS…» (qs_open)", async () => {
    const rec = mockNodes({ rows: [ROWS.QS.ok] });
    const sld = clone(SLD);
    sld.nodes.find((node) => node.code === "QS").state = "ok";
    await mountSld("QS", { sld });
    expect(queryAllTexts(".o_td_en_node_action")).toEqual(["Вимкнути QS…"]);
    await click(".o_td_en_node_action");
    await animationFrame();
    expect(rec.prepare).toEqual([["qs_open", null]]);
});

test("AC-301/D-38: BESS — «Зарядити 50 кВт» і «Зупинити заряд» за станом", async () => {
    mockNodes();
    await mountSld("BESS");
    expect(queryAllTexts(".o_td_en_node_action")).toEqual(["Зарядити 50 кВт"]);
    expect(queryOne(".o_td_en_node_action").dataset.actionCode).toBe("bess_charge");
});

test("AC-301/D-38: BESS заряджається — «Зупинити заряд» (bess_stop)", async () => {
    const rec = mockNodes({ rows: [ROWS.BESS.charging] });
    await mountSld("BESS");
    expect(queryAllTexts(".o_td_en_node_action")).toEqual(["Зупинити заряд"]);
    await click(".o_td_en_node_action");
    await animationFrame();
    expect(rec.prepare).toEqual([["bess_stop", null]]);
});

test("D-46: дистанційне перемикання вимкнено — кнопка disabled із причиною", async () => {
    mockNodes({
        rows: [{ ...ROWS.QS.off, enabled: false, disabled_reason: "Дистанційне перемикання вимкнено адміністратором" }],
    });
    await mountSld("QS");
    const btn = queryOne(".o_td_en_node_action");
    expect(btn.disabled).toBe(true);
    expect(btn.getAttribute("title")).toBe("Дистанційне перемикання вимкнено адміністратором");
});

test("вузол поза QS/BESS — RPC get_node_actions не викликається, кнопок немає", async () => {
    const rec = mockNodes();
    await mountSld("BW-2");
    expect(rec.asked).toEqual([]);
    expect(queryAll(".o_td_en_node_action").length).toBe(0);
    expect(queryAll(".o_td_en_sel_card").length).toBe(1);
});

test("після закриття діалогу панель повідомляє про зміну (onChanged → Пульт перечитає схему)", async () => {
    mockNodes();
    const changes = [];
    await mountSld("QS", { onChanged: () => changes.push(1) });
    await click(".o_td_en_node_action");
    await animationFrame();
    await click(".o_td_en_cd_cancel");
    await animationFrame();
    expect(changes.length).toBe(1);
});

test("помилка prepare (UserError) — сповіщення, діалог не відкривається", async () => {
    const rec = mockNodes({
        prepareError: "Дистанційне перемикання вимкнено: td.energy_control.remote_switching_enabled. Зверніться до адміністратора.",
    });
    await mountSld("QS");
    await click(".o_td_en_node_action");
    await animationFrame();
    expect(queryAll(".o_td_en_cd").length).toBe(0);
    expect(rec.toasts.at(-1)[0]).toMatch(/Дистанційне перемикання вимкнено/);
    expect(queryText(".o_td_en_sel_title")).toBe("QS");
});
