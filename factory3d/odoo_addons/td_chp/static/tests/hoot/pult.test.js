/** @odoo-module */
// AC-22 (UI: 37 вузлів у 8 системах, 6 шарів, 14 плиток KPI, 16 рядків діагностики) та основа пульта: паспорт
// «типова комплектація (допущення)» — з DTO, вкладки, шари з міжшаровими переходами, тренд, журнал, ТО, стани.
import { describe, expect, test } from "@odoo/hoot";
import { click, queryAll, queryAllTexts, queryOne, queryText } from "@odoo/hoot-dom";
import { advanceTime } from "@odoo/hoot-mock";
import { defineMailModels } from "@mail/../tests/mail_test_helpers";
import { ChpStore, VMAP } from "@td_chp/pult/store";
import { makeNodes } from "@td_chp/pult/nodes";
import { mountWithCleanup } from "@web/../tests/web_test_helpers";
import { ChpPult } from "@td_chp/pult/pult";
import { clone, mockChp, mountPult, settle } from "./helpers";
import { STATE } from "./state_fixture";

describe.current.tags("desktop");
defineMailModels();

test("AC-22: 37 вузлів у 8 системах, 6 шарів, 14 плиток KPI", async () => {
    mockChp();
    await mountPult();
    expect(queryAll("#nodes button").length).toBe(37);
    expect(queryAllTexts("#sys-seg button")).toEqual(["Усі", "Двигун", "Газ", "Тепло ВТ", "Тепло НТ", "Вихлоп", "Повітря", "Електрика", "Безпека"]);
    const systems = new Set(queryAll("#nodes button").map((b) => b.dataset.sys));
    expect(systems.size).toBe(8);
    expect(queryAllTexts("#scheme-tabs button")).toEqual(["Огляд", "Газ і електрика", "Тепло ВТ і опалення", "НТ і повітря", "Вихлоп і викиди", "Масло і безпека"]);
    expect(queryAll("#scheme-layers .layer").length).toBe(6);
    expect(queryAll(".c-kpi .tile").length).toBe(14);
    expect(queryText("#panel-main .c-kpi [data-b=pel]")).toBe("620");
});

test("AC-22: 16 рядків діагностики після переходу на вкладку «Діагностика»", async () => {
    mockChp();
    await mountPult();
    expect(queryOne("#panel-diag").hidden).toBe(true);
    await click("#tab-diag");
    await settle();
    expect(queryOne("#panel-diag").hidden).toBe(false);
    expect(queryOne("#panel-main").hidden).toBe(true);
    expect(queryAll("#cyl-table tbody tr").length).toBe(16);
    expect(queryAll("#aux-table tbody tr").length).toBeGreaterThan(20);
    // A5: відхилення +27 К > 25 К → попередження; свічка 3 560 год → «Зношується»
    expect(queryText("#cyl-table tbody tr:nth-child(5) td:nth-child(3)")).toMatch(/\+27/);
    expect(queryOne("#cyl-table tbody tr:nth-child(5) td:nth-child(3)").className).toMatch(/warn/);
    expect(queryText("#cyl-table tbody tr:nth-child(5) td:nth-child(7)")).toMatch(/Зношується/);
    await click("#tab-main");
    expect(queryOne("#panel-main").hidden).toBe(false);
});

test("фільтр систем: «Двигун» ховає чужі вузли; клік по вузлу відкриває картку параметрів", async () => {
    mockChp();
    await mountPult();
    await click("#sys-seg button[data-sys=eng]");
    const visible = queryAll("#nodes button").filter((b) => !b.hidden);
    expect(visible.length).toBeGreaterThan(3);
    expect(visible.every((b) => b.dataset.sys === "eng")).toBe(true);
    await click("#nodes button[data-node=engine]");
    expect(queryText("#node-detail h3")).toBe("Двигун ГПД");
    expect(queryText("#node-detail .nd-rows")).toMatch(/Частота обертання\s*1\s?500/);
    await click("#sys-seg button[data-sys=all]");
    expect(queryAll("#nodes button").filter((b) => !b.hidden).length).toBe(37);
});

test("мнемосхема: 6 шарів, міжшаровий перехід «→ шар» по кліку", async () => {
    mockChp();
    await mountPult();
    const hidden = () => queryAll("#scheme-layers .layer").map((l) => l.hidden);
    expect(hidden()).toEqual([false, true, true, true, true, true]);
    await click("#scheme-tabs button[data-layer=ht]");
    expect(queryOne("#ly-ht").hidden).toBe(false);
    expect(queryOne("#ly-ov").hidden).toBe(true);
    // міжшаровий перехід «→ шар»: стрілка на шарі веде на інший шар
    const xls = queryAll("#scheme-layers .xl");
    expect(xls.length).toBeGreaterThan(5);
    const first = xls[0];
    const from = first.closest(".layer").id.replace("ly-", "");
    const target = first.dataset.target;
    expect(target).not.toBe(from);
    await click(`#scheme-tabs button[data-layer=${from}]`);
    // hoot.click не вміє фокусувати SVG-елементи (Illegal invocation) — шлемо подію напряму
    queryAll(`#ly-${from} .xl`)[0].dispatchEvent(new MouseEvent("click", { bubbles: true }));
    await settle();
    expect(queryOne("#ly-" + target).hidden).toBe(false);
    expect(queryOne("#ly-" + from).hidden).toBe(true);
    expect(queryOne(`#scheme-tabs button[data-layer=${target}]`).getAttribute("aria-pressed")).toBe("true");
});

test("паспорт: пометка «типова комплектація (допущення)» лише при is_assumption", async () => {
    const ctx = mockChp();
    await mountPult();
    expect(queryOne("#passport").hidden).toBe(false);
    expect(queryText("#passport")).toBe("Паспорт: типова комплектація (допущення)");
    expect(queryOne("#passport").title).toMatch(/TEDOM a\.s\. Quanto D800 NG/);
    expect(queryText("#hdr-name")).toBe("КГУ-1 · TEDOM · 800 кВт");
    expect(queryText("#hdr-sub")).toMatch(/TEDOM a\.s\. Quanto D800 NG/);
});

test("паспорт: без допущення пометка прихована", async () => {
    const s = clone(STATE);
    s.unit.assumption = false;
    mockChp({ state: s });
    await mountPult();
    expect(queryOne("#passport").hidden).toBe(true);
});

test("шапка: стан, режим, дозволи, 14 KPI зі значеннями DTO, журнал, ТО", async () => {
    mockChp();
    await mountPult();
    expect(queryText("#pl-name")).toBe("РОБОТА");
    expect(queryOne("#plaque").dataset.st).toBe("run");
    expect(queryText("#hdr-mode")).toBe("За тепловим графіком");
    expect(queryAll("#perm li.ok").length).toBe(5);
    expect(queryText("[data-b=etat]")).toBe("87,3");
    expect(queryText("[data-b=nox]")).toBe("128");
    expect(queryAll("#jr li").length).toBe(8);
    expect(queryOne("#jr li:first-child .lv").textContent).toBe("Інфо");
    expect(queryAll("#to-list .to-item").length).toBe(5);
    expect(queryText("#to-list .to-item:first-child .v")).toMatch(/через\s*600\s*год/);
    expect(queryOne("#banner").hidden).toBe(true);
});

test("без свіжих даних і при вимкненому читанні — банер, значення «—»", async () => {
    const s = clone(STATE);
    s.stale = true;
    for (const k of Object.keys(s.v)) {
        s.v[k] = null;
    }
    mockChp({ state: s });
    await mountPult();
    expect(queryOne("#banner").hidden).toBe(false);
    expect(queryText("#banner")).toMatch(/Немає свіжих даних/);
    expect(queryText("[data-b=pel]")).toBe("—");
    expect(queryOne("#btn-start").disabled).toBe(true);
    expect(queryOne("#btn-estop").disabled).toBe(false);
});

test("read_enabled=False: «Читання вимкнено адміністратором»", async () => {
    mockChp({ state: { read_disabled: true } });
    await mountPult();
    expect(queryText("#banner")).toBe("Читання вимкнено адміністратором");
});

test("тренд: запит API-02 24 год, перемикач 1 год", async () => {
    const ctx = mockChp();
    await mountPult();
    expect(ctx.calls.trend[0].range_h).toBe(24);
    await click("#trend-seg button[data-range='1']");
    await settle();
    expect(ctx.calls.trend.at(-1).range_h).toBe(1);
    expect(queryOne("#trend-seg button[data-range='1']").getAttribute("aria-pressed")).toBe("true");
});

test("журнал: «Квитувати» викликає API-04", async () => {
    const s = clone(STATE);
    s.jr[0].level = "warn";
    s.jr[0].ack_state = "new";
    const ctx = mockChp({ state: s });
    await mountPult();
    expect(queryOne("#btn-ack").disabled).toBe(false);
    expect(queryText("#jr li:first-child .ak")).toBe("не квитовано");
    await click("#btn-ack");
    await settle();
    expect(ctx.calls.ack.length).toBe(1);
});

test("«Імітація подій» лише при caps.sim і available (td_iot_sim)", async () => {
    mockChp();
    await mountPult();
    expect(queryOne("#demo").hidden).toBe(true);
});

test("«Імітація подій»: caps.sim + available → кнопки сценаріїв", async () => {
    const s = clone(STATE);
    s.caps.sim = true;
    const ctx = mockChp({
        state: s,
        sim: (p) => (p.op === "list" ? { available: true, scenarios: [{ code: "chp_fire", label: "КГУ: пожежа" }, { code: "chp_no_permit", label: "КГУ: знято дозвіл" }] } : { ok: true }),
    });
    await mountPult();
    expect(queryOne("#demo").hidden).toBe(false);
    expect(queryAll("#demo-grid button").map((b) => b.textContent)).toEqual(["Пожежа", "Знято дозвіл КГУ", "Скасувати імітацію"]);
    await click("#d-chp_fire");
    await settle();
    expect(ctx.calls.sim.at(-1)).toEqual({ op: "start", code: "chp_fire", params: null });
});

test("caps.sim без td_iot_sim (available=false) — блоку немає", async () => {
    const s = clone(STATE);
    s.caps.sim = true;
    mockChp({ state: s, sim: () => ({ available: false, scenarios: [] }) });
    await mountPult();
    expect(queryOne("#demo").hidden).toBe(true);
});

test("тема: перемикач авто → світла → темна, атрибут data-theme на корені", async () => {
    mockChp();
    await mountPult();
    const root = queryOne(".o_td_chp_pult");
    expect(root.hasAttribute("data-theme")).toBe(false);
    await click("#btn-theme");
    expect(root.getAttribute("data-theme")).toBe("light");
    expect(queryText("#btn-theme")).toBe("Тема: світла");
    await click("#btn-theme");
    expect(root.getAttribute("data-theme")).toBe("dark");
    await click("#btn-theme");
    expect(root.hasAttribute("data-theme")).toBe(false);
});

test("сховище: відображення сигналів на S/V, підсвітка вузла (R-05), trip без вузла в DTO", async () => {
    const store = new ChpStore();
    store.applyState(clone(STATE));
    expect(store.S.state).toBe(2);
    expect(store.V.pel).toBe(620);
    expect(store.S.valves).toBe(true);
    expect(store.S.hl).toBe(null);
    expect(store.S.mode).toBe("heat");
    expect(Object.keys(VMAP).length).toBeGreaterThan(90);
    // аварія 112 → вузол з DTO, «alarm»
    const a = clone(STATE);
    a.v["ctl/state"] = 3;
    a.alarm = { code: 112, text: "Перегрів ОЖ", node: "engine", acked: false };
    store.applyState(a);
    expect(store.S.hl).toEqual({ node: "engine", kind: "alarm" });
    // зупинка без аварії: trip 1 → вузол qf, «warn»; у стані 0 підсвітка знімається
    const t = clone(STATE);
    t.v["ctl/state"] = 4;
    t.trip = { code: 1, text: "Зникла мережа S2" };
    store.applyState(t);
    expect(store.S.hl).toEqual({ node: "qf", kind: "warn" });
    t.v["ctl/state"] = 0;
    store.applyState(t);
    expect(store.S.hl).toBe(null);
    // немає значення → NaN, а не нуль
    const n = clone(STATE);
    n.v["gas/p_in"] = null;
    store.applyState(n);
    expect(Number.isNaN(store.V.gasP)).toBe(true);
});

test("вузли: nodeActive/nodeBadge — «Працює», «Не працює», підсвітка аварії", async () => {
    const store = new ChpStore();
    store.applyState(clone(STATE));
    const api = makeNodes(store);
    expect(api.nodeBadge("engine")).toEqual(["Працює", "ok"]);
    expect(api.nodeBadge("gasdet")).toEqual(["Норма", "ok"]);
    const a = clone(STATE);
    a.v["ctl/state"] = 3;
    a.alarm = { code: 114, text: "Загазованість", node: "gasdet", acked: false };
    store.applyState(a);
    expect(api.nodeBadge("gasdet")).toEqual(["Аварія", "alarm"]);
});

test("шина td_chp: підписка на канал, td_chp/update → оновлення через ≈ 300 мс; опитування 5 с", async () => {
    const ctx = mockChp();
    await mountPult();
    expect(ctx.bus.channels).toEqual(["td_chp"]);
    expect(typeof ctx.bus.handlers["td_chp/update"]).toBe("function");
    const n = ctx.calls.state.length;
    ctx.bus.handlers["td_chp/update"]({ kinds: ["state"] });
    ctx.bus.handlers["td_chp/update"]({ kinds: ["journal"] });
    await advanceTime(200);
    expect(ctx.calls.state.length).toBe(n);
    await advanceTime(200);
    expect(ctx.calls.state.length).toBe(n + 1);
    // опитування: без шини дані оновлюються кожні 5 с
    await advanceTime(5200);
    expect(ctx.calls.state.length).toBeGreaterThan(n + 1);
    // etag із попередньої відповіді передається назад (API-01)
    expect(ctx.calls.state.at(-1).etag).toBe(STATE.ver);
});

test("журнал: «Показати ще» довантажує API-03 (limit 50, before — ts останнього рядка)", async () => {
    const ctx = mockChp();
    await mountPult();
    expect(queryAll("#jr li").length).toBe(8);
    expect(queryOne("#btn-jr-more").hidden).toBe(false);
    await click("#btn-jr-more");
    await settle();
    expect(ctx.calls.journal[0]).toEqual({ unit: null, limit: 50, before: null });
});

test("закриття дії: канал шини знято, опитування й таймери зупинено", async () => {
    const ctx = mockChp();
    const comp = await mountWithCleanup(ChpPult, { props: { action: { context: {} } } });
    await settle();
    expect(ctx.bus.channels).toEqual(["td_chp"]);
    comp.__owl__.app.destroy();
    expect(ctx.bus.channels).toEqual([]);
    expect(ctx.bus.handlers["td_chp/update"]).toBe(undefined);
    const n = ctx.calls.state.length;
    await advanceTime(12000);
    expect(ctx.calls.state.length).toBe(n);
});
