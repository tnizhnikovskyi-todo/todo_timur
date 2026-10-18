/** @odoo-module */
// AC-106 (edgePath) і AC-121 (схема: вибір вузла, «Відкрити картку вузла» лише для card=true).
import { describe, expect, test } from "@odoo/hoot";
import { queryAll, queryOne, queryText } from "@odoo/hoot-dom";
import { animationFrame } from "@odoo/hoot-mock";
import { defineMailModels } from "@mail/../tests/mail_test_helpers";
import { mountWithCleanup } from "@web/../tests/web_test_helpers";
import { SldCanvas, edgePath } from "@td_energy/pult/sld";
import { CONTRACTS } from "./fixtures/contracts";

describe.current.tags("desktop");

defineMailModels();

const SLD = CONTRACTS["API-05"].sld;
const node = (shape, x, y, w, h) => ({ shape, x, y, w, h });

test("edgePath: блок → блок з y_mid (AC-106, RM6-1 → T1)", () => {
    expect(edgePath(node("box", 580, 100, 160, 44), node("box", 230, 192, 200, 64))).toBe("M660 144 V168 H330 V192");
});

test("edgePath: збіг центрів — прямий відрізок", () => {
    expect(edgePath(node("box", 580, 24, 160, 44), node("box", 580, 100, 160, 44))).toBe("M660 68 V100");
});

test("edgePath: шина над вузлом — від низу шини до верху вузла в x центру вузла (AC-106)", () => {
    // SEC-1 (bar, y 298..304) → BW-2 (y 336)
    expect(edgePath(node("bar", 40, 298, 590, 6), node("box", 330, 336, 120, 84))).toBe("M390 304 V336");
});

test("edgePath: x центру вузла затискається в межі шини", () => {
    // центр вузла (x=1250+45=1295) правіше шини 690..1280 → 1280
    expect(edgePath(node("bar", 690, 298, 590, 6), node("box", 1250, 336, 90, 84))).toBe("M1280 304 V336");
    // центр лівіше шини → x шини
    expect(edgePath(node("bar", 690, 298, 590, 6), node("box", 600, 336, 40, 84))).toBe("M690 304 V336");
});

test("edgePath: шина нижче вузла (СЕС над секцією 2)", () => {
    expect(edgePath(node("bar", 690, 298, 590, 6), node("box", 1110, 192, 88, 64))).toBe("M1154 256 V298");
});

test("edgePath: дитина — шина (T1 → секція 1)", () => {
    expect(edgePath(node("box", 230, 192, 200, 64), node("bar", 40, 298, 590, 6))).toBe("M330 256 V298");
});

test("SldCanvas малює блоки, шини, ребра й підпис QS", async () => {
    await mountWithCleanup(SldCanvas, { props: { sld: SLD, selected: null, onSelect() {} } });
    await animationFrame();
    // 21 вузол: 2 шини, 2 підписи, 17 кнопок (блоки й вимикач QS)
    expect(queryAll("button.o_td_en_node").length).toBe(17);
    expect(queryAll(".o_td_en_sld_bar:not(.o_td_en_qs_bridge)").length).toBe(2);
    expect(queryAll(".o_td_en_sld_edges path").length).toBe(SLD.edges.length);
    expect(queryText(".o_td_en_qs_label")).toBe("QS вимкнено");
    expect(queryAll(".o_td_en_qs_bridge").length).toBe(0);
    expect(queryOne("button[data-node-code='C2']").classList.contains("o_td_en_node--alarm")).toBe(true);
});

test("QS увімкнено: перемичка між секціями й підпис", async () => {
    const sld = JSON.parse(JSON.stringify(SLD));
    sld.nodes.find((n) => n.code === "QS").state = "ok";
    await mountWithCleanup(SldCanvas, { props: { sld, selected: null, onSelect() {} } });
    await animationFrame();
    expect(queryText(".o_td_en_qs_label")).toBe("QS увімкнено");
    expect(queryAll(".o_td_en_qs_bridge").length).toBe(1);
});

test("вибраний вузол: факти й «Відкрити картку вузла» лише для card=true", async () => {
    await mountWithCleanup(SldCanvas, { props: { sld: SLD, selected: "BW-2", onSelect() {} } });
    await animationFrame();
    expect(queryAll(".o_td_en_sel").length).toBe(1);
    expect(queryAll(".o_td_en_sel li").length).toBe(2);
    expect(queryAll(".o_td_en_sel_card").length).toBe(1);
    expect(queryAll(".o_td_en_sel_3d").length).toBe(1);
    expect(queryOne("button[data-node-code='BW-2']").classList.contains("is-selected")).toBe(true);
});

test("вузол без картки (card=false): кнопки картки немає", async () => {
    await mountWithCleanup(SldCanvas, { props: { sld: SLD, selected: "PV-INV", onSelect() {} } });
    await animationFrame();
    expect(queryAll(".o_td_en_sel").length).toBe(1);
    expect(queryAll(".o_td_en_sel_card").length).toBe(0);
    expect(queryAll(".o_td_en_sel_3d").length).toBe(1);
});
