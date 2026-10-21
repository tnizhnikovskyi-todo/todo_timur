/** @odoo-module */
// HOOT: «Показати в 3D» з МО чи переміщення поза живим payload (виконане, скасоване, старе, майбутнє) — API-13: ядро бере маршрут
// із сервера й показує його як showMO / showPicking; без «Об'єкта … немає в даних».
import { describe, expect, test } from "@odoo/hoot";
import { json, mountViewer } from "./helpers";

describe.current.tags("desktop");

const rpc = (result, calls = []) => (url, init) => {
    calls.push(JSON.parse(init.body).params);
    return json({ jsonrpc: "2.0", id: null, result });
};
const roots = (viewer) => [...viewer.core.hl.roots].map((o) => o.userData.code);
const step = (code, state, n) => ({ code, name: "Операція " + n, workcenter: code, state, sequence: n, date_start: "2026-10-06 08:00", date_finished: "2026-10-06 09:00" });
const mo = (extra) => ({
    kind: "mo", name: "WH/MO/09001", reason: null, state: "done", product: "TST", product_name: "Шафа", qty: 1, uom: "шт",
    origin: "S00087", route: "", date: "2026-10-06 12:00", date_start: "2026-10-06 08:00", date_finished: "2026-10-06 12:00", steps: [], ...extra,
});

test("doc_route: виконане МО поза payload — маршрут із сервера, картка й спокійний тост", async () => {
    const calls = [];
    const steps = [step("SAW-1", "done", 1), step("EDGE-2", "done", 2)];
    const { viewer, notes, el } = await mountViewer({
        model: "core",
        routes: { "/doc_route": rpc(mo({ steps }), calls) },
    });
    expect(viewer.D.productions.some((m) => m.name === "WH/MO/09001")).toBe(false);
    await viewer.applyParams({ mo: "WH/MO/09001", tab: "production", so: "S00087" });
    expect(calls).toEqual([{ mo: "WH/MO/09001" }]);
    expect(viewer.getState().panel).toBe("doc");
    expect(viewer.getState().tab).toBe("production");
    expect(roots(viewer)).toEqual(["SAW-1", "EDGE-2"]);
    expect(notes).toEqual([["WH/MO/09001 виконано 06.10 — показано його маршрут", "info"]]);
    const card = el.querySelector(".o_f3d_cardbody").textContent;
    expect(card).toInclude("WH/MO/09001");
    expect(card).toInclude("Виконано");
    expect(card).toInclude("Операція 2");
});

test("doc_route: МО без операцій — картка й info-тост з поясненням, у 3D нічого не підсвічено", async () => {
    const { viewer, notes } = await mountViewer({
        model: "core",
        routes: { "/doc_route": rpc(mo({ state: "draft", reason: "no_workorders", date: null, date_finished: null })) },
    });
    await viewer.applyParams({ mo: "WH/MO/09002", tab: "production" });
    expect(viewer.getState().panel).toBe("doc");
    expect(roots(viewer)).toEqual([]);
    expect(notes.length).toBe(1);
    expect(notes[0][1]).toBe("info");
    expect(notes[0][0]).toInclude("ще без операцій");
});

test("doc_route: скасоване переміщення — комірки звідки/куди, без попередження", async () => {
    const calls = [];
    let res = null;
    const { viewer, notes } = await mountViewer({ model: "core", routes: { "/doc_route": (u, i) => rpc(res, calls)(u, i) } });
    const codes = Object.keys(viewer.D.locations).filter((c) => viewer.items.has(c)).slice(0, 2);
    expect(codes.length).toBe(2);
    res = {
        kind: "picking", name: "WH/INT/00042", reason: null, state: "cancel", type: "internal", picking_type: "Внутрішні", partner: "", origin: "",
        date: "2026-10-06 12:00", locations: [{ code: codes[0], name: "A", role: "from" }, { code: codes[1], name: "B", role: "to" }],
    };
    await viewer.applyParams({ picking: "WH/INT/00042", tab: "logistics" });
    expect(calls).toEqual([{ picking: "WH/INT/00042" }]);
    expect(viewer.getState().panel).toBe("doc");
    expect(roots(viewer)).toEqual(codes);
    expect(notes).toEqual([["WH/INT/00042 скасовано — показано його маршрут", "info"]]);
});

test("doc_route: живе МО показується з payload без запиту; невідомий документ і збій запиту — попередження", async () => {
    const calls = [];
    const live = await mountViewer({ model: "none", routes: { "/doc_route": rpc(mo({}), calls) } });
    await live.viewer.applyParams({ mo: "WH/MO/00231", tab: "production" });
    expect(calls).toEqual([]);
    expect(live.viewer.getState().panel).toBe("mo");
    expect(live.notes).toEqual([]);
    const gone = await mountViewer({ model: "none", routes: { "/doc_route": rpc({ kind: "mo", name: "WH/MO/NOPE", reason: "not_found" }) } });
    await gone.viewer.applyParams({ mo: "WH/MO/NOPE" });
    expect(gone.notes).toEqual([["Документа WH/MO/NOPE немає в базі", "warning"]]);
    const broken = await mountViewer({ model: "none" }); // /doc_route -> 404
    await broken.viewer.applyParams({ picking: "WH/OUT/NOPE" });
    expect(broken.notes.map(([, t]) => t)).toEqual(["warning"]);
    expect(broken.notes[0][0]).not.toInclude("немає в даних");
});
