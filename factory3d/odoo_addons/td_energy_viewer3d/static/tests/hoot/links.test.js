/** @odoo-module */
// HOOT: UI-27 ViewerLinks (C-45): реєстр `td_energy.viewer_links`, ключ `default`, `open({code})`.
import { after, describe, expect, test } from "@odoo/hoot";
import { registry } from "@web/core/registry";
import { makeViewerLink, viewerLinksService } from "@td_energy_viewer3d/layer/links";

describe.current.tags("desktop");

const links = () => registry.category("td_energy.viewer_links");

test("UI27 сервіс-реєстратор: старт додає запис default; open({code}) → action_td_open_3d → doAction", async () => {
    expect(registry.category("services").contains("td_energy_viewer_links")).toBe(true);
    expect(viewerLinksService.dependencies).toEqual(["orm", "action"]);
    const calls = [];
    const orm = { call: async (...a) => { calls.push(["orm", ...a]); return { type: "ir.actions.client", tag: "f3d_viewer.action", params: { code: "BW-2" } }; } };
    const action = { doAction: async (a) => { calls.push(["action", a]); } };
    const had = links().contains("default");
    const prev = had ? links().get("default") : null;
    after(() => {
        links().remove("default");
        if (prev) {
            links().add("default", prev);
        }
    });
    viewerLinksService.start({}, { orm, action });
    expect(links().contains("default")).toBe(true);
    const link = links().get("default");
    const result = await link.open({ code: "BW-2" });
    expect(calls).toEqual([
        ["orm", "td.energy.node", "action_td_open_3d", ["BW-2"]],
        ["action", { type: "ir.actions.client", tag: "f3d_viewer.action", params: { code: "BW-2" } }],
    ]);
    expect(result.tag).toBe("f3d_viewer.action");
    // без вузла — лише шар (code = null); повторний старт не падає
    calls.length = 0;
    await link.open({});
    await link.open();
    expect(calls.filter((c) => c[0] === "orm").map((c) => c[3])).toEqual([[null], [null]]);
    viewerLinksService.start({}, { orm, action });
});

test("UI27 помилка сервера (UserError «Вузол … не знайдено») піднімається до викликача, doAction не викликається", async () => {
    const calls = [];
    const orm = { call: async () => { throw new Error("Вузол X не знайдено."); } };
    const action = { doAction: async () => { calls.push("action"); } };
    const link = makeViewerLink({ orm, action });
    let error = null;
    try {
        await link.open({ code: "X" });
    } catch (e) {
        error = e;
    }
    expect(error?.message).toBe("Вузол X не знайдено.");
    expect(calls.length).toBe(0);
    // порожня відповідь — нічого не відкриваємо
    const none = makeViewerLink({ orm: { call: async () => false }, action });
    await none.open({ code: "BW-2" });
    expect(calls.length).toBe(0);
});
