/** @odoo-module */
// R-22 / API-11: пілюля заявки ТО, посилання на заявку, «Запланувати ТО» в картці обладнання та в «Огляді».
import { expect, test } from "@odoo/hoot";
import { tick } from "@odoo/hoot-mock";
import { json, mountViewer } from "./helpers";

const q = (el, sel) => el.querySelector(sel);
const qa = (el, sel) => [...el.querySelectorAll(sel)];
const text = (el) => (el.textContent || "").replace(/\s+/g, " ").trim();
const settle = async () => {
    for (let i = 0; i < 8; i++) {
        await tick();
    }
};

const PLAN_URL = "/maintenance/plan";
const NEW_REQ = {
    id: "Планове ТО · Розкрій 1", res_id: 777, name: "Планове ТО · Розкрій 1", equipment: "SAW-1", equipment_name: "Розкрій 1",
    maintenance_type: "preventive", stage: "Нова", done: false, priority: "0", schedule_date: "2026-10-09 08:00", overdue_days: 3,
};
const planOk = (init, calls) => {
    calls.push(JSON.parse(init.body));
    return json({
        jsonrpc: "2.0", id: null,
        result: {
            ok: true, created: true, request: NEW_REQ,
            equipment: { "SAW-1": { maintenance_request: NEW_REQ.name, maintenance_request_id: 777, maintenance_due: null, next_maintenance: "2026-10-09" } },
        },
    });
};

/** Дві заявки з однаковою назвою «Планове ТО» (як у демо-базі): правильна — друга за порядком, але остання в списку — чужа. */
const twoSameNamed = (fx) => {
    fx.data.maintenance_requests.push(
        { id: "Планове ТО", res_id: 502, name: "Планове ТО", equipment: "SAW-1", equipment_name: "Розкрій 1", maintenance_type: "preventive",
            stage: "Нова", done: false, priority: "0", schedule_date: "2026-10-10 08:00", overdue_days: 2 },
        { id: "Планове ТО", res_id: 501, name: "Планове ТО", equipment: "FL-1", equipment_name: "Навантажувач ГП 1", maintenance_type: "preventive",
            stage: "Нова", done: false, priority: "0", schedule_date: "2026-10-30 08:00" }
    );
    fx.data.equipment["SAW-1"] = { name: "Розкрій 1", category: "Верстати", maintenance_request: "Планове ТО", maintenance_request_id: 502 };
};

const due = (extra = {}) => (fx) => {
    fx.data.meta.live = true;
    fx.data.meta.database = "odoo";
    fx.data.equipment["SAW-1"] = {
        name: "Розкрій 1", category: "Верстати", next_maintenance: "2026-10-09", maintenance_due: "overdue", ...extra,
    };
};

test("maintenance_pill (R-22): пілюля називає обладнання, стадію, дату й прострочення; заявка — за res_id", async () => {
    const r = await mountViewer({ model: "core", mutate: twoSameNamed });
    r.viewer.select("SAW-1");
    const pill = q(r.el, ".o_f3d_mr");
    expect(text(pill.querySelector("b"))).toBe("Планове ТО · Розкрій 1 · Нова · 10.10, прострочено 2 дн.");
    expect(pill.classList.contains("o_f3d_bad")).toBe(true);
    // назва заявки не повторюється двічі
    expect(text(pill).includes("Планове ТО · Планове ТО")).toBe(false);
    expect(q(r.el, "[data-plan-mr]")).toBe(null);
    // посилання відкриває форму заявки в Odoo
    q(r.el, "[data-open-mr]").click();
    expect(r.opened).toEqual([["maintenance.request", 502]]);
});

test("maintenance_pill (R-22): назва «Планове ТО · <обладнання>» не дублює обладнання, delta зливає за res_id", async () => {
    const r = await mountViewer({ model: "core", mutate: twoSameNamed });
    r.viewer.applyPatch({ maintenance_requests: [{ id: "Планове ТО", res_id: 501, stage: "В роботі" }] });
    const list = r.viewer.D.maintenance_requests.filter((m) => m.id === "Планове ТО");
    expect(list.length).toBe(2);
    expect(list.find((m) => m.res_id === 501).stage).toBe("В роботі");
    expect(list.find((m) => m.res_id === 502).stage).toBe("Нова");
    r.viewer.applyPatch({ maintenance_requests: [NEW_REQ], equipment: { "SAW-1": { maintenance_request: NEW_REQ.name, maintenance_request_id: 777 } } });
    r.viewer.select("SAW-1");
    expect(text(q(r.el, ".o_f3d_mr b"))).toBe("Планове ТО · Розкрій 1 · Нова · 09.10, прострочено 3 дн.");
    // прострочення знято (delta: null) — рядка «прострочено» більше немає
    r.viewer.applyPatch({ maintenance_requests: [{ id: NEW_REQ.id, res_id: 777, overdue_days: null }] });
    r.viewer.select(null);
    r.viewer.select("SAW-1");
    expect(text(q(r.el, ".o_f3d_mr b"))).toBe("Планове ТО · Розкрій 1 · Нова · 09.10");
});

test("maintenance_pill (R-22): статичні дані без res_id — пілюля за назвою, без посилання; в «Огляді» — стадія й дата", async () => {
    const r = await mountViewer({ model: "core" });
    r.viewer.openTab("overview");
    const row = qa(r.el, ".o_f3d_rows li").map(text).find((t) => t.startsWith("CNC-2 —") || t.includes("зупинено"));
    expect(row.includes("зупинено · Помилка шпинделя осі Z, чекаємо сервісного інженера · В роботі · 12.10")).toBe(true);
    r.viewer.select("CNC-2");
    expect(text(q(r.el, ".o_f3d_mr b")).startsWith("Помилка шпинделя осі Z, чекаємо сервісного інженера · ")).toBe(true);
    expect(q(r.el, "[data-open-mr]")).toBe(null);
});

test("maintenance_pill (R-22): у кіоску посилання на заявку немає", async () => {
    const k = await mountViewer({ model: "core", kiosk: true, mutate: twoSameNamed, viewerOpts: { onOpenRecord: undefined } });
    k.viewer.select("SAW-1");
    expect(q(k.el, ".o_f3d_mr")).not.toBe(null);
    expect(q(k.el, "[data-open-mr]")).toBe(null);
    expect(q(k.el, "[data-plan-mr]")).toBe(null);
});

test("maintenance_plan (API-11): «Запланувати ТО» створює заявку, картка й «Огляд» оновлюються", async () => {
    const calls = [];
    const r = await mountViewer({ model: "core", mutate: due(), routes: { [PLAN_URL]: (url, init) => planOk(init, calls) } });
    // «Огляд»: рядок про прострочене ТО без відкритої заявки
    r.viewer.openTab("overview");
    expect(qa(r.el, ".o_f3d_rows li").map(text).some((t) => t.includes("Розкрій 1 — ТО прострочено · 09.10"))).toBe(true);
    r.viewer.select("SAW-1");
    const btn = q(r.el, "[data-plan-mr]");
    expect(text(btn)).toBe("Запланувати ТО");
    expect(text(q(r.el, ".o_f3d_note.o_f3d_bad")).includes("ТО прострочено · 09.10")).toBe(true);
    expect(q(r.el, ".o_f3d_mr")).toBe(null);
    btn.click();
    await settle();
    expect(calls).toEqual([{ jsonrpc: "2.0", method: "call", params: { code: "SAW-1" } }]);
    expect(q(r.el, "[data-plan-mr]")).toBe(null);
    expect(text(q(r.el, ".o_f3d_mr b"))).toBe("Планове ТО · Розкрій 1 · Нова · 09.10, прострочено 3 дн.");
    q(r.el, "[data-open-mr]").click();
    expect(r.opened).toEqual([["maintenance.request", 777]]);
    expect(r.notes.some(([m, t]) => m.includes("Створено заявку") && t === "success")).toBe(true);
    expect(r.viewer.D.equipment["SAW-1"].maintenance_due).toBe(undefined);
    r.viewer.openTab("overview");
    expect(qa(r.el, ".o_f3d_rows li").map(text).some((t) => t.includes("ТО прострочено"))).toBe(false);
});

test("maintenance_plan (API-11): помилка сервера — повідомлення, кнопка лишається; без live і в кіоску кнопки немає", async () => {
    const denied = () => json({ jsonrpc: "2.0", id: null, result: { ok: false, status: 403, error: { code: "forbidden", message: "Немає прав на створення заявок на обслуговування." } } });
    const r = await mountViewer({ model: "core", mutate: due(), routes: { [PLAN_URL]: denied } });
    r.viewer.select("SAW-1");
    q(r.el, "[data-plan-mr]").click();
    await settle();
    expect(r.notes).toEqual([["Немає прав на створення заявок на обслуговування.", "warning"]]);
    expect(q(r.el, "[data-plan-mr]")).not.toBe(null);
    expect(q(r.el, ".o_f3d_mr")).toBe(null);

    const stat = await mountViewer({
        model: "core",
        mutate: (fx) => {
            fx.data.equipment["SAW-1"] = { name: "Розкрій 1", category: "Верстати", maintenance_due: "soon", next_maintenance: "2026-10-14" };
        },
    });
    stat.viewer.select("SAW-1");
    expect(q(stat.el, "[data-plan-mr]")).toBe(null);

    const kiosk = await mountViewer({ model: "core", kiosk: true, mutate: due(), viewerOpts: { onOpenRecord: undefined } });
    kiosk.viewer.select("SAW-1");
    expect(q(kiosk.el, "[data-plan-mr]")).toBe(null);
});

test("maintenance_plan (API-11): ідемпотентна відповідь («заявка вже існує») теж оновлює картку", async () => {
    const calls = [];
    const again = (url, init) => {
        calls.push(init.body);
        return json({ jsonrpc: "2.0", id: null, result: { ok: true, created: false, request: NEW_REQ, equipment: { "SAW-1": { maintenance_request: NEW_REQ.name, maintenance_request_id: 777, maintenance_due: null } } } });
    };
    const r = await mountViewer({ model: "core", mutate: due(), routes: { [PLAN_URL]: again } });
    r.viewer.select("SAW-1");
    q(r.el, "[data-plan-mr]").click();
    await settle();
    expect(calls.length).toBe(1);
    expect(r.notes.some(([m, t]) => m.includes("Заявка вже існує") && t === "success")).toBe(true);
    expect(q(r.el, ".o_f3d_mr")).not.toBe(null);
});
