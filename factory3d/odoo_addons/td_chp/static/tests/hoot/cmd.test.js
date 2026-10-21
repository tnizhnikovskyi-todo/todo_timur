/** @odoo-module */
// AC-23: «Пуск» при невиконаних умовах — `#il` без діалогу; при виконаних — 1/2, після `confirm` «Очікує другого
// підтвердження»; зміна режиму/уставок відкриває діалог класу А, до `confirm` значення не змінюється. Також: аварійний
// стоп, картка «Очікує другого підтвердження» для іншого користувача, права, «Скинути аварію».
import { describe, expect, test } from "@odoo/hoot";
import { click, queryAll, queryOne, queryText, select } from "@odoo/hoot-dom";
import { advanceTime } from "@odoo/hoot-mock";
import { defineMailModels } from "@mail/../tests/mail_test_helpers";
import { clone, mockChp, mountPult, prepareDto, reserveState, settle } from "./helpers";
import { STATE } from "./state_fixture";

describe.current.tags("desktop");
defineMailModels();

const cmdMock = (handlers) => (params) => {
    const h = handlers[params.op];
    if (!h) {
        throw new Error("не змоковано op=" + params.op);
    }
    return h(params);
};

test("«Пуск» при невиконаних умовах: #il без діалогу, перевірки з prepare", async () => {
    const blocked = prepareDto("start", {
        blocked: true,
        blocked_reason: "тиск газу 1,15 бар < 1,5 бар",
        token: null,
        checks: clone(STATE.il.list).map((c) => (c.code === "gas_pressure" ? { ...c, state: "fail", detail: "тиск газу 1,15 бар < 1,5 бар" } : c)),
    });
    const state = reserveState();
    state.il.ok = false;
    state.il.list = blocked.checks;
    const ctx = mockChp({ state, cmd: cmdMock({ prepare: () => blocked }) });
    await mountPult();
    expect(queryOne("#btn-start").disabled).toBe(false);
    expect(queryOne("#il").hidden).toBe(true);
    await click("#btn-start");
    await settle();
    expect(ctx.calls.cmd[0]).toEqual({ op: "prepare", unit: null, kind: "start" });
    expect(queryOne("#il").hidden).toBe(false);
    expect(queryOne("#clsb").hidden).toBe(true);
    expect(queryText("#il-head")).toBe("Пуск заблоковано: тиск газу 1,15 бар < 1,5 бар");
    expect(queryAll("#il-list li").length).toBe(14);
    expect(queryAll("#il-list li.bad").length).toBe(1);
    expect(queryText("#cmd-msg")).toMatch(/Пуск заблоковано/);
});

test("«Пуск» при виконаних умовах: діалог 1/2, після confirm — «Очікує другого підтвердження»", async () => {
    const ctx = mockChp({
        state: reserveState(),
        cmd: cmdMock({
            prepare: () => prepareDto("start"),
            confirm: () => ({ ref: "chp:12", state: "awaiting_second", state_label: "Очікує другого підтвердження", needs_second: true, message: "", blocked_reason: "" }),
            cancel: () => ({ ref: "chp:12", state: "cancelled", state_label: "Скасовано" }),
        }),
    });
    await mountPult();
    await click("#btn-start");
    await settle();
    expect(queryOne("#il").hidden).toBe(true);
    expect(queryOne("#clsb").hidden).toBe(false);
    expect(queryText("#clsb-t")).toBe("Команда класу Б: «Пуск КГУ-1»");
    expect(queryText("#cb-c1")).toBe("1/2 · енергетик");
    expect(queryText("#cb-c2")).toBe("2/2 · головний енергетик");
    expect(queryText("#btn-cb1")).toBe("Підтвердити (1/2)");
    expect(queryOne("#cb-c1").classList.contains("done")).toBe(false);
    // поки діалог відкритий, «Пуск» недоступний
    expect(queryOne("#btn-start").disabled).toBe(true);
    // бекенд після 1/2 віддає команду в `pending` (для інших користувачів і для стеження ініціатором)
    ctx.state.pending = [{ ref: "chp:12", kind: "start", title: "Пуск КГУ-1", prepared_by: "Я", can_second: false, second_expires_at: "2026-10-20T10:05:00Z" }];
    await click("#btn-cb1");
    await settle();
    expect(ctx.calls.cmd.find((c) => c.op === "confirm")).toEqual({ op: "confirm", unit: null, ref: "chp:12", token: "tok-start" });
    expect(queryText("#clsb-p")).toMatch(/Очікує другого підтвердження/);
    expect(queryOne("#cb-c1").classList.contains("done")).toBe(true);
    expect(queryOne("#btn-cb1").hidden).toBe(true);
    // ініціатору кнопки 2/2 немає
    expect(queryAll("#clsb button").filter((b) => !b.hidden).map((b) => b.textContent.trim())).toEqual(["Скасувати"]);
    // власна команда ініціатора не дублюється карткою «Очікує другого підтвердження» (її бачать інші користувачі)
    expect(queryAll("#pend-list .panel").length).toBe(0);
    await click("#btn-cbx");
    await settle();
    expect(ctx.calls.cmd.at(-1)).toEqual({ op: "cancel", unit: null, ref: "chp:12", token: "tok-start" });
    expect(queryOne("#clsb").hidden).toBe(true);
});

test("оператор-chief: клас Б без 2/2 — «Виконати», стеження за станом команди до done", async () => {
    let polls = 0;
    const ctx = mockChp({
        state: reserveState(),
        cmd: cmdMock({
            prepare: () => prepareDto("start", { needs_second: false, confirm_label: "Виконати" }),
            confirm: () => ({ ref: "chp:12", state: "queued", state_label: "У черзі", needs_second: false, message: "Команду прийнято", blocked_reason: "" }),
            get: () => {
                polls++;
                return { ref: "chp:12", state: polls < 2 ? "executing" : "done", state_label: polls < 2 ? "Виконується" : "Виконано", error: "", result_text: "" };
            },
        }),
    });
    await mountPult();
    await click("#btn-start");
    await settle();
    expect(queryText("#btn-cb1")).toBe("Виконати");
    expect(queryOne("#cb-c2").hidden).toBe(true);
    await click("#btn-cb1");
    await settle();
    expect(queryOne("#clsb").hidden).toBe(true);
    await settle(30);
    expect(ctx.calls.cmd.filter((c) => c.op === "get").length).toBeGreaterThan(0);
    await (async () => {
        for (let i = 0; i < 6 && !/виконано/.test(queryText("#cmd-msg")); i++) {
            await settle(10);
        }
    })();
    expect(queryText("#cmd-msg")).toMatch(/Пуск КГУ-1: виконано/);
});

test("зміна режиму відкриває діалог класу А; до confirm значення не змінюється", async () => {
    const ctx = mockChp({
        cmd: cmdMock({
            prepare: (p) => prepareDto("set_mode", { ref: "chp:20", token: "tok-mode", title: "Режим роботи КГУ-1", text: "Режим роботи: Ручний.", sub: "Клас А: значення зміниться лише після підтвердження.", params: p.params }),
            confirm: () => ({ ref: "chp:20", state: "queued", state_label: "У черзі", needs_second: false, message: "", blocked_reason: "" }),
            get: () => ({ ref: "chp:20", state: "queued", state_label: "У черзі" }),
        }),
    });
    await mountPult();
    expect(queryText("#hdr-mode")).toBe("За тепловим графіком");
    expect(queryOne("#sel-mode").value).toBe("heat");
    await select("manual", { target: "#sel-mode" });
    await settle();
    expect(ctx.calls.cmd.at(-1)).toEqual({ op: "prepare", unit: null, kind: "set_mode", params: { mode: "manual" } });
    expect(queryOne("#cla").hidden).toBe(false);
    expect(queryOne("#clsb").hidden).toBe(true);
    expect(queryText("#cla-p")).toMatch(/Режим роботи: Ручний\./);
    expect(queryText("#btn-ca-yes")).toBe("Виконати");
    // до confirm значення пульта не змінилось, а елемент показує обране значення, а не скидається опитуванням
    expect(queryText("#hdr-mode")).toBe("За тепловим графіком");
    await advanceTime(1500);
    expect(queryOne("#sel-mode").value).toBe("manual");
    expect(queryOne("#rng-sp").disabled).toBe(true);
    expect(ctx.calls.cmd.filter((c) => c.op === "confirm").length).toBe(0);
    await click("#btn-ca-yes");
    await settle();
    expect(ctx.calls.cmd.find((c) => c.op === "confirm")).toEqual({ op: "confirm", unit: null, ref: "chp:20", token: "tok-mode" });
    expect(queryOne("#cla").hidden).toBe(true);
    expect(queryText("#hdr-mode")).toBe("За тепловим графіком");
    // поки команда виконується, елемент керування лишається з обраним значенням (до оновлення DTO)
    await advanceTime(1500);
    expect(queryOne("#sel-mode").value).toBe("manual");
});

test("«Скасувати» діалог класу А: команда скасована, елемент повертається до значення зі сховища", async () => {
    const ctx = mockChp({
        cmd: cmdMock({
            prepare: () => prepareDto("set_heat_dir", { ref: "chp:21", token: "tok-heat" }),
            cancel: () => ({ ref: "chp:21", state: "cancelled", state_label: "Скасовано" }),
        }),
    });
    await mountPult();
    await select("boiler", { target: "#sel-heat" });
    await settle();
    expect(queryOne("#cla").hidden).toBe(false);
    await click("#btn-ca-no");
    await settle();
    expect(ctx.calls.cmd.at(-1)).toEqual({ op: "cancel", unit: null, ref: "chp:21", token: "tok-heat" });
    expect(queryOne("#cla").hidden).toBe(true);
    expect(queryOne("#sel-heat").value).toBe("auto");
});

test("уставка потужності і cos φ: діалог класу А з параметрами", async () => {
    const s = clone(STATE);
    s.v["ctl/mode"] = 3;
    const ctx = mockChp({ state: s, cmd: cmdMock({ prepare: (p) => prepareDto(p.kind, { ref: "chp:22", token: "tok-" + p.kind }) }) });
    await mountPult();
    expect(queryOne("#rng-sp").disabled).toBe(false);
    const sp = queryOne("#rng-sp");
    sp.value = "90";
    sp.dispatchEvent(new Event("input", { bubbles: true }));
    expect(queryText("#out-sp")).toMatch(/90\s*%/);
    sp.dispatchEvent(new Event("change", { bubbles: true }));
    await settle();
    expect(ctx.calls.cmd.at(-1)).toEqual({ op: "prepare", unit: null, kind: "set_setpoint", params: { sp_pct: 90 } });
    expect(queryOne("#cla").hidden).toBe(false);
    await click("#btn-ca-no");
    await settle();
    const cs = queryOne("#rng-cos");
    cs.value = "0.95";
    cs.dispatchEvent(new Event("change", { bubbles: true }));
    await settle();
    expect(ctx.calls.cmd.at(-1)).toEqual({ op: "prepare", unit: null, kind: "set_cos", params: { cos: 0.95 } });
});

test("аварійний стоп: #es-confirm, підтвердження — confirm", async () => {
    const ctx = mockChp({
        cmd: cmdMock({
            prepare: () => prepareDto("estop", { ref: "chp:30", token: "tok-es" }),
            confirm: () => ({ ref: "chp:30", state: "queued", state_label: "У черзі", needs_second: false, message: "", blocked_reason: "" }),
            get: () => ({ ref: "chp:30", state: "queued", state_label: "У черзі" }),
        }),
    });
    await mountPult();
    expect(queryOne("#es-confirm").hidden).toBe(true);
    await click("#btn-estop");
    await settle();
    expect(queryOne("#es-confirm").hidden).toBe(false);
    expect(queryText("#es-t")).toBe("Аварійний стоп КГУ-1");
    await click("#btn-es-yes");
    await settle();
    expect(ctx.calls.cmd.find((c) => c.op === "confirm")).toEqual({ op: "confirm", unit: null, ref: "chp:30", token: "tok-es" });
    expect(queryOne("#es-confirm").hidden).toBe(true);
});

test("картка «Очікує другого підтвердження» для іншого користувача: кнопка 2/2 лише з can_second", async () => {
    const s = reserveState();
    s.pending = [
        { ref: "chp:40", kind: "start", title: "Пуск КГУ-1", prepared_by: "Іван Енергетик", can_second: true, second_expires_at: "2026-10-20T10:05:00Z" },
        { ref: "chp:41", kind: "stop", title: "Стоп КГУ-1", prepared_by: "Я", can_second: false, second_expires_at: "2026-10-20T10:05:00Z" },
    ];
    const ctx = mockChp({
        state: s,
        cmd: cmdMock({
            confirm_second: () => ({ ref: "chp:40", state: "queued", state_label: "У черзі", needs_second: true, message: "Підтверджено (2/2)", blocked_reason: "" }),
            get: () => ({ ref: "chp:40", state: "queued", state_label: "У черзі" }),
        }),
    });
    await mountPult();
    expect(queryAll("#pend-list .panel").length).toBe(2);
    expect(queryText("#pend-list .panel:first-child .t")).toBe("Очікує другого підтвердження");
    expect(queryText("#pend-list .panel:first-child .note")).toMatch(/Іван Енергетик/);
    expect(queryAll("#pend-list .btn").length).toBe(1);
    await click("#pend-list .btn");
    await settle();
    expect(ctx.calls.cmd.find((c) => c.op === "confirm_second")).toEqual({ op: "confirm_second", unit: null, ref: "chp:40" });
});

test("права: без operator команди вимкнені, лише перегляд; без запису — підказка", async () => {
    const s = reserveState();
    s.caps.operate = false;
    mockChp({ state: s });
    await mountPult();
    expect(queryOne("#btn-start").disabled).toBe(true);
    expect(queryOne("#btn-estop").disabled).toBe(true);
    expect(queryOne("#sel-mode").disabled).toBe(true);
    expect(queryText("#ctl-hint")).toMatch(/Лише перегляд/);
});

test("write_enabled=False (без мосту): команди вимкнені з поясненням", async () => {
    const s = reserveState();
    s.caps.write = false;
    mockChp({ state: s });
    await mountPult();
    expect(queryOne("#btn-start").disabled).toBe(true);
    expect(queryText("#ctl-hint")).toMatch(/write_enabled/);
});

test("стан «Аварія»: «Скинути аварію» — діалог класу А; «Пуск» дозволений для перевірки умов", async () => {
    const s = clone(STATE);
    s.v["ctl/state"] = 3;
    s.v["alarm/code"] = 112;
    s.alarm = { code: 112, text: "Перегрів ОЖ: 97,5 °C ≥ 97 °C", node: "engine", acked: false };
    const ctx = mockChp({ state: s, cmd: cmdMock({ prepare: () => prepareDto("reset", { ref: "chp:50", token: "tok-reset" }) }) });
    await mountPult();
    expect(queryOne("#plaque").dataset.st).toBe("alarm");
    expect(queryOne("#plaque").classList.contains("unack")).toBe(true);
    expect(queryText("#pl-sub")).toMatch(/Перегрів ОЖ/);
    expect(queryOne("#tab-dot").hidden).toBe(false);
    expect(queryOne("#btn-reset").hidden).toBe(false);
    expect(queryOne("#btn-estop").disabled).toBe(true);
    expect(queryOne("#nodes button[data-node=engine]").classList.contains("hl-alarm")).toBe(true);
    await click("#btn-reset");
    await settle();
    expect(ctx.calls.cmd.at(-1)).toEqual({ op: "prepare", unit: null, kind: "reset" });
    expect(queryOne("#cla").hidden).toBe(false);
});

test("пуск із стану: 9 кроків, поточний крок і синхроноскоп", async () => {
    const s = clone(STATE);
    Object.assign(s.v, { "ctl/state": 1, "ctl/step": 8, "ctl/step_left": 4.5, "eng/rpm": 1500, "ctl/sync_ok": 0, "ctl/sync_dphi": 6 });
    mockChp({ state: s });
    await mountPult();
    expect(queryOne("#seq").hidden).toBe(false);
    expect(queryAll("#seq-steps li").length).toBe(9);
    expect(queryAll("#seq-steps li.done").length).toBe(7);
    expect(queryOne("#seq-steps li.cur").textContent).toMatch(/8\. Синхронізація з мережею/);
    expect(queryOne("#sync-st").textContent).toBe("Підгонка");
    expect(queryText("#pl-sub")).toBe("Крок 8/9: Синхронізація з мережею");
});

test("охолодження: #cool-box з залишком часу", async () => {
    const s = clone(STATE);
    Object.assign(s.v, { "ctl/state": 4, "ctl/cool_left": 38 });
    mockChp({ state: s });
    await mountPult();
    expect(queryOne("#cool-box").hidden).toBe(false);
    expect(queryText("#cool-t")).toBe("38 с");
});
