/** @odoo-module */
// Екран «Керування» (UI-12…UI-16, UI-19, UI-20): AC-295 (сценарії), AC-296 (пріоритети), AC-297 (плитки),
// AC-299 (розклад і журнал); чип зв'язку (AC-294), оновлення з шини, друге підтвердження (D-43).
import { describe, expect, test } from "@odoo/hoot";
import { advanceTime, animationFrame } from "@odoo/hoot-mock";
import { click, edit, queryAll, queryAllTexts, queryFirst, queryOne, queryText, waitFor } from "@odoo/hoot-dom";
import { defineMailModels } from "@mail/../tests/mail_test_helpers";
import { mockService, mountWithCleanup, onRpc } from "@web/../tests/web_test_helpers";
import { MainComponentsContainer } from "@web/core/main_components_container";
import { Control } from "@td_energy_control/control/control";
import { CONTRACTS } from "./fixtures/contracts";
import { clone, controlData, JOURNAL, prepared } from "./fixtures/control_data";

describe.current.tags("desktop");

defineMailModels();

/** Мок `td.energy.control`: журнал викликів у `rec`, підписка шини в `rec.bus`. */
function mockControl(patch = null, { journal = null } = {}) {
    const rec = { loads: 0, prepare: [], confirm: [], cancel: [], second: [], undo: [], journal: [], bus: null };
    mockService("bus_service", {
        addChannel() {},
        deleteChannel() {},
        subscribe: (type, callback) => {
            if (type === "td_energy_control/update") {
                rec.bus = callback;
            }
        },
        unsubscribe() {},
    });
    onRpc("td.energy.control", "get_control", () => {
        rec.loads += 1;
        return controlData(patch);
    });
    onRpc("td.energy.control", "prepare", ({ args, kwargs }) => {
        rec.prepare.push({ args, kwargs });
        return prepared();
    });
    onRpc("td.energy.control", "confirm", ({ args }) => {
        rec.confirm.push(args);
        return clone(CONTRACTS["API-18"]);
    });
    onRpc("td.energy.control", "cancel", ({ args }) => {
        rec.cancel.push(args);
        return { action_id: 55, state: "cancelled" };
    });
    onRpc("td.energy.control", "confirm_second", ({ args }) => {
        rec.second.push(args);
        return { action_id: 55, state: "executing", state_label: "Виконується", needs_second: false, message: "", blocked_reason: null };
    });
    onRpc("td.energy.control", "undo", ({ args }) => {
        rec.undo.push(args);
        return prepared((data) => {
            data.title = "Скасувати: BESS · розряд?";
            data.kind = "bess_stop";
            data.cls = "A";
            data.needs_second = false;
            data.confirm_label = "Виконати";
        });
    });
    onRpc("td.energy.control", "get_action", () => {
        const action = clone(CONTRACTS["API-22"]);
        action.state = "done";
        action.state_label = "Виконано";
        action.finished_at = "2026-10-18T11:20:10Z";
        return action;
    });
    onRpc("td.energy.control", "get_journal", ({ kwargs }) => {
        rec.journal.push(kwargs);
        return journal || { items: [{ ...JOURNAL[4], id: 700, time: "06:30", what: "Вентиляція · денний режим" }], more: false };
    });
    return rec;
}

async function mountControl() {
    await mountWithCleanup(MainComponentsContainer);
    await mountWithCleanup(Control, { props: {} });
    await animationFrame();
}

// ------------------------------------------------------------------ шапка, чип зв'язку (AC-294)

test("UI-12: шапка, інформаційна смуга, секції екрана", async () => {
    mockControl();
    await mountControl();
    expect(queryText(".o_td_en_crumbs")).toBe("Енергетика / Керування");
    expect(queryText(".o_td_en_h1")).toBe("Керування енергетикою заводу");
    expect(queryText(".o_td_en_head .o_td_en_sub")).toBe("Режими, сценарії автоматики, пріоритети навантажень і ручні команди");
    expect(queryText(".o_td_en_info")).toMatch(/Сценарії виконує контролер ГРЩ і збирач сигналів, без затримок Odoo/);
    expect(queryText(".o_td_en_info")).toMatch(/пожежна автоматика працюють окремо й тут не керуються\.$/);
    expect(queryAll(".o_td_en_scenarios, .o_td_en_shed, .o_td_en_cmds, .o_td_en_schedule, .o_td_en_journal").length).toBe(5);
});

test("UI-13: чип зв'язку — на зв'язку (зелений)", async () => {
    mockControl();
    await mountControl();
    expect(queryText(".o_td_en_engine_chip")).toMatch(/Контролер ГРЩ і збирач на зв'язку · 14:20/);
    expect(queryOne(".o_td_en_engine_chip").classList.contains("o_td_en_pill--live")).toBe(true);
});

test("UI-13: hold → янтарний «Автоматику призупинено: …»", async () => {
    mockControl((data) => {
        Object.assign(data.engine, { mode: "hold", reason: "немає даних", level: "warn", label: "Автоматику призупинено: немає даних" });
    });
    await mountControl();
    expect(queryText(".o_td_en_engine_chip")).toBe("Автоматику призупинено: немає даних");
    expect(queryOne(".o_td_en_engine_chip").classList.contains("o_td_en_pill--partial")).toBe(true);
});

test("UI-13: збирач не на зв'язку → червоний", async () => {
    mockControl((data) => {
        Object.assign(data.engine, { connected: false, level: "bad", label: "Збирач не на зв'язку · 5 хв" });
    });
    await mountControl();
    expect(queryText(".o_td_en_engine_chip")).toBe("Збирач не на зв'язку · 5 хв");
    expect(queryOne(".o_td_en_engine_chip").classList.contains("o_td_en_pill--stale")).toBe(true);
});

test("UI-13: запасний текст чипа без label/level", async () => {
    mockControl((data) => {
        data.engine = { connected: true, mode: "off", reason: "вимкнено адміністратором" };
    });
    await mountControl();
    expect(queryText(".o_td_en_engine_chip")).toBe("Автоматику призупинено: вимкнено адміністратором");
    expect(queryOne(".o_td_en_engine_chip").classList.contains("o_td_en_engine_chip--warn")).toBe(true);
});

// ------------------------------------------------------------------ сценарії (AC-295)

test("AC-295: 6 карток, чипи, role=switch + aria-checked, «увімкнено N з 6»", async () => {
    mockControl();
    await mountControl();
    expect(queryAll(".o_td_en_sc").length).toBe(6);
    expect(queryText(".o_td_en_sc_count")).toBe("увімкнено 4 з 6");
    expect(queryAllTexts(".o_td_en_sc h3")[0]).toBe("Зрізання піку");
    expect(queryText("[data-scenario='peak'] .o_td_en_chip--arm")).toBe("Чергування · запас 402 кВт");
    expect(queryText("[data-scenario='pfc'] .o_td_en_chip--warn")).toBe("Збій: PFC-2 ступінь 3");
    expect(queryText("[data-scenario='chp'] .o_td_en_chip--off")).toBe("Вимкнено");
    expect(queryAllTexts("[data-scenario='peak'] .o_td_en_param")).toEqual(["уставка 760 кВт · 95 %", "прогноз 15 хв"]);
    const switches = queryAll(".o_td_en_sc .o_td_en_switch");
    expect(switches.length).toBe(6);
    for (const sw of switches) {
        expect(sw.getAttribute("role")).toBe("switch");
        expect(sw.hasAttribute("aria-checked")).toBe(true);
        expect(sw.getAttribute("aria-label").length > 0).toBe(true);
    }
    expect(switches.map((sw) => sw.getAttribute("aria-checked"))).toEqual(["true", "true", "true", "true", "false", "false"]);
    expect(queryAll(".o_td_en_sc_pending").length).toBe(0);
});

test("AC-295: клік по перемикачу відкриває діалог і не змінює стан без confirm", async () => {
    const rec = mockControl();
    await mountControl();
    const sw = queryOne("[data-scenario='peak'] .o_td_en_switch");
    expect(sw.getAttribute("aria-checked")).toBe("true");
    await click(sw);
    await animationFrame();
    expect(rec.prepare.length).toBe(1);
    expect(rec.prepare[0].args).toEqual(["scenario_toggle", { scenario: "peak", enabled: false }]);
    expect(queryAll(".o_td_en_cd").length).toBe(1);
    expect(rec.confirm.length).toBe(0);
    expect(queryOne("[data-scenario='peak'] .o_td_en_switch").getAttribute("aria-checked")).toBe("true");
    expect(queryText(".o_td_en_sc_count")).toBe("увімкнено 4 з 6");
    // «Скасувати» закриває діалог і скасовує токен; стан не змінився
    await click(".o_td_en_cd_cancel");
    await animationFrame();
    expect(queryAll(".o_td_en_cd").length).toBe(0);
    expect(rec.cancel).toEqual([[CONTRACTS["API-17"].token]]);
    expect(queryOne("[data-scenario='peak'] .o_td_en_switch").getAttribute("aria-checked")).toBe("true");
});

test("AC-295: чип «Очікує застосування» при !applied; «Очікує другого підтвердження» при pending_action_id", async () => {
    mockControl((data) => {
        data.scenarios.items[1].applied = false;
        data.scenarios.items[2].pending_action_id = 61;
    });
    await mountControl();
    expect(queryAll(".o_td_en_sc_pending").length).toBe(1);
    expect(queryText("[data-scenario='self'] .o_td_en_sc_pending")).toBe("Очікує застосування");
    expect(queryText("[data-scenario='pfc'] .o_td_en_sc_second")).toBe("Очікує другого підтвердження");
});

test("AC-295: без прав (can_toggle=false) перемикач disabled з поясненням", async () => {
    mockControl((data) => {
        data.scenarios.items.forEach((item) => (item.can_toggle = false));
        data.meta.can_prepare = false;
        data.meta.role = "viewer";
    });
    await mountControl();
    const sw = queryOne("[data-scenario='peak'] .o_td_en_switch");
    expect(sw.disabled).toBe(true);
    expect(sw.getAttribute("title")).toMatch(/Немає прав/);
});

test("UI-18: «Параметри» → форма за schema → prepare('scenario_params') → діалог", async () => {
    const rec = mockControl();
    await mountControl();
    expect(queryAll("[data-scenario='pfc'] .o_td_en_sc_params_btn").length).toBe(0); // без schema
    await click("[data-scenario='peak'] .o_td_en_sc_params_btn");
    await animationFrame();
    expect(queryText(".o_td_en_pd .modal-title")).toBe("Параметри: Зрізання піку");
    expect(queryText(".o_td_en_pd_hint")).toBe("100…2000 кВт");
    await click(".o_td_en_pd_input");
    await edit("3000");
    await click(".o_td_en_pd_save");
    await animationFrame();
    expect(queryText(".o_td_en_pd_error")).toMatch(/Поза межами 100…2000 кВт/);
    expect(rec.prepare.length).toBe(0);
    await click(".o_td_en_pd_input");
    await edit("900");
    await click(".o_td_en_pd_save");
    await animationFrame();
    expect(rec.prepare[0].args).toEqual(["scenario_params", { scenario: "peak", params: { limit_kw: 900 } }]);
    expect(queryAll(".o_td_en_cd").length).toBe(1);
});

// ------------------------------------------------------------------ пріоритети (AC-296)

test("AC-296: 5 пріоритетів, «Разом можна зняти 174 кВт», «Не відключаються ніколи»", async () => {
    mockControl();
    await mountControl();
    expect(queryAll(".o_td_en_shed_row").length).toBe(5);
    expect(queryText(".o_td_en_shed_sum")).toMatch(/^174\s*кВт$/);
    expect(queryText(".o_td_en_shed_never")).toMatch(/аспірація під час роботи верстатів, ІТ і зв'язок, охорона/);
    expect(queryText(".o_td_en_shed .o_td_en_note")).toMatch(/щоб утримати 760 кВт/);
    expect(queryAllTexts(".o_td_en_shed_row .o_td_en_shed_kw")[0]).toMatch(/^−48\s*кВт$/);
    expect(queryAll(".o_td_en_shed_up").length).toBe(0); // ↑/↓ лише в режимі перестановки
});

test("AC-296: «Змінити порядок» — Вище/Нижче 36 × 36 з aria-label; «Зберегти порядок» → shed_reorder; «Скасувати» повертає порядок", async () => {
    const rec = mockControl();
    await mountControl();
    const first = () => queryAllTexts(".o_td_en_shed_row .o_td_en_shed_title")[0];
    expect(first()).toBe("Зарядна станція навантажувачів");
    await click(".o_td_en_shed_start");
    await animationFrame();
    const ups = queryAll(".o_td_en_shed_up");
    const downs = queryAll(".o_td_en_shed_down");
    expect(ups.length).toBe(5);
    expect(downs.length).toBe(5);
    expect(ups[0].getAttribute("aria-label")).toBe("Вище");
    expect(downs[0].getAttribute("aria-label")).toBe("Нижче");
    expect(ups[0].disabled).toBe(true);
    expect(downs[4].disabled).toBe(true);
    expect(Math.round(ups[1].getBoundingClientRect().width)).toBe(36);
    expect(Math.round(ups[1].getBoundingClientRect().height)).toBe(36);
    // перша нагрузка вниз
    await click(downs[0]);
    await animationFrame();
    expect(first()).toBe("Дахова вентиляція RoofVent");
    expect(queryAllTexts(".o_td_en_shed_n")).toEqual(["1", "2", "3", "4", "5"]);
    // «Скасувати» — порядок як був, режим вимкнено
    await click(".o_td_en_shed_cancel");
    await animationFrame();
    expect(first()).toBe("Зарядна станція навантажувачів");
    expect(queryAll(".o_td_en_shed_up").length).toBe(0);
    expect(rec.prepare.length).toBe(0);
    // знову: змінити й зберегти
    await click(".o_td_en_shed_start");
    await animationFrame();
    await click(queryAll(".o_td_en_shed_down")[0]);
    await animationFrame();
    await click(".o_td_en_shed_save");
    await animationFrame();
    expect(rec.prepare[0].args).toEqual(["shed_reorder", { order: [2, 1, 3, 4, 5] }]);
    expect(queryAll(".o_td_en_cd").length).toBe(1);
});

test("AC-296: без can_reorder кнопки «Змінити порядок» немає", async () => {
    mockControl((data) => {
        data.shed.can_reorder = false;
    });
    await mountControl();
    expect(queryAll(".o_td_en_shed_start").length).toBe(0);
    expect(queryAll(".o_td_en_shed_row").length).toBe(5);
});

// ------------------------------------------------------------------ плитки команд (AC-297)

test("AC-297: 8 плиток у порядку макета, бейдж «B» для класу B", async () => {
    mockControl();
    await mountControl();
    const tiles = queryAll(".o_td_en_cmd");
    expect(tiles.length).toBe(8);
    expect(tiles.map((tile) => tile.dataset.cmd)).toEqual([
        "qs_close",
        "bess_charge",
        "bess_discharge",
        "chp_start",
        "genset_test",
        "light_break",
        "vent_eco",
        "air_setpoint",
    ]);
    expect(queryText("[data-cmd='qs_close'] .o_td_en_cmd_sub")).toBe("секції 1 і 2 разом");
    expect(queryAll(".o_td_en_cls").length).toBe(5); // B: QS, розряд, КГУ, ДГУ, тиск
    expect(queryAll("[data-cmd='bess_charge'] .o_td_en_cls").length).toBe(0);
    expect(queryText("[data-cmd='qs_close'] .o_td_en_cls")).toBe("B");
    expect(tiles.every((tile) => !tile.disabled)).toBe(true);
    expect(Math.round(tiles[0].getBoundingClientRect().height) >= 56).toBe(true);
});

test("AC-297: клік по плитці → prepare(kind) → діалог", async () => {
    const rec = mockControl();
    await mountControl();
    await click("[data-cmd='bess_charge']");
    await animationFrame();
    expect(rec.prepare[0].args).toEqual(["bess_charge", null]);
    expect(queryAll(".o_td_en_cd").length).toBe(1);
});

test("AC-297: disabled + title за причиною (запобіжник, недоступність), підказка D-46", async () => {
    mockControl((data) => {
        data.meta.remote_switching_enabled = false;
        for (const cmd of data.commands) {
            if (["qs_close", "bess_discharge", "chp_start", "genset_test"].includes(cmd.code)) {
                cmd.enabled = false;
                cmd.disabled_reason = "Дистанційне перемикання вимкнено адміністратором";
            }
        }
        data.commands[7].enabled = false;
        data.commands[7].disabled_reason = "Команда недоступна: немає сигналу уставки";
    });
    await mountControl();
    expect(queryAll(".o_td_en_cmd:disabled").length).toBe(5);
    expect(queryOne("[data-cmd='qs_close']").getAttribute("title")).toBe("Дистанційне перемикання вимкнено адміністратором");
    expect(queryText("[data-cmd='qs_close'] .o_td_en_cmd_why")).toBe("Дистанційне перемикання вимкнено адміністратором");
    expect(queryOne("[data-cmd='air_setpoint']").getAttribute("title")).toMatch(/Команда недоступна/);
    expect(queryOne("[data-cmd='bess_charge']").disabled).toBe(false);
    expect(queryText(".o_td_en_cmd_notice")).toMatch(/Дистанційне перемикання вимкнено адміністратором: недоступні команди QS/);
});

test("AC-297: без прав виконувати команди (can_prepare=false) усі плитки disabled", async () => {
    mockControl((data) => {
        data.meta.can_prepare = false;
        data.meta.role = "viewer";
    });
    await mountControl();
    expect(queryAll(".o_td_en_cmd:disabled").length).toBe(8);
    expect(queryOne("[data-cmd='bess_charge']").getAttribute("title")).toBe("Немає прав: потрібна роль «Енергетик»");
});

// ------------------------------------------------------------------ розклад і журнал (AC-299)

test("AC-299: розклад — 6 рядків, left/width смуг, вертикаль «зараз», текстова таблиця", async () => {
    mockControl();
    await mountControl();
    expect(queryAll(".o_td_en_tl_row").length).toBe(6);
    expect(queryText(".o_td_en_tl_now_text")).toBe("зараз 14:20 · план складено з прогнозу навантаження й СЕС");
    expect(queryAllTexts(".o_td_en_tl_scale div span")).toEqual(["00", "03", "06", "09", "12", "15", "18", "21", "24"]);
    const first = queryFirst("[data-resource='bess'] .o_td_en_tl_bar");
    expect(first.getAttribute("style")).toMatch(/left: 31\.25%; width: 14\.58%/);
    expect(first.classList.contains("o_td_en_tl_bar--d")).toBe(true);
    expect(first.getAttribute("title")).toBe("розряд · пік · 07:30–11:00");
    expect(first.textContent).toBe("розряд · пік");
    expect(queryAll("[data-resource='bess'] .o_td_en_tl_bar").length).toBe(3);
    expect(queryAll("[data-resource='chp'] .o_td_en_tl_bar").length).toBe(0);
    const now = queryOne("[data-resource='bess'] .o_td_en_tl_now");
    expect(now.getAttribute("style")).toMatch(/left: 59\.72%/);
    // таблиця для скринридерів
    expect(queryAll(".o_td_en_tl_table.visually-hidden tbody tr").length).toBe(3 + 0 + 3 + 3 + 2 + 1);
    expect(queryAll(".o_td_en_tl[aria-hidden='true']").length).toBe(1);
});

test("AC-299: журнал — рядки з чипами результату, «Скасувати дію», «Підтвердити (2/2)»", async () => {
    mockControl();
    await mountControl();
    expect(queryAll(".o_td_en_j_row").length).toBe(5);
    expect(queryText("[data-journal-id='812'] .o_td_en_j_time")).toBe("14:06");
    expect(queryText("[data-journal-id='812'] .o_td_en_j_what")).toMatch(/Заявка ТО · PFC-2: ступінь 3 не вмикається/);
    expect(queryText("[data-journal-id='812'] .o_td_en_j_who")).toBe("автоматика");
    expect(queryOne("[data-journal-id='812'] .o_td_en_chip").classList.contains("o_td_en_chip--res-info")).toBe(true);
    expect(queryText("[data-journal-id='812'] .o_td_en_chip")).toBe("створено");
    expect(queryOne("[data-journal-id='801'] .o_td_en_chip").classList.contains("o_td_en_chip--res-ok")).toBe(true);
    expect(queryOne("[data-journal-id='799'] .o_td_en_chip").classList.contains("o_td_en_chip--res-bad")).toBe(true);
    expect(queryOne("[data-journal-id='790'] .o_td_en_chip").classList.contains("o_td_en_chip--res-muted")).toBe(true);
    expect(queryAll(".o_td_en_j_undo").length).toBe(1);
    expect(queryAll("[data-journal-id='801'] .o_td_en_j_undo").length).toBe(1);
    expect(queryAll(".o_td_en_j_second").length).toBe(1);
    expect(queryAll("[data-journal-id='55'] .o_td_en_j_second").length).toBe(1);
    expect(queryAll(".o_td_en_j_more_btn").length).toBe(1);
    expect(queryAll(".o_td_en_j_all").length).toBe(1);
});

test("AC-299: «Показати більше» підвантажує 50 записів із before_id", async () => {
    const rec = mockControl();
    await mountControl();
    await click(".o_td_en_j_more_btn");
    await animationFrame();
    expect(rec.journal.length).toBe(1);
    expect(rec.journal[0].limit).toBe(50);
    expect(rec.journal[0].before_id).toBe(790);
    expect(queryAll(".o_td_en_j_row").length).toBe(6);
    expect(queryAll(".o_td_en_j_more_btn").length).toBe(0); // more=false
});

test("AC-299: «Підтвердити (2/2)» лише для іншого енергетика", async () => {
    mockControl((data) => {
        data.pending[0].can_confirm_second = false;
    });
    await mountControl();
    expect(queryAll(".o_td_en_j_second").length).toBe(0);
    expect(queryAll(".o_td_en_pending_ok").length).toBe(0);
    expect(queryText(".o_td_en_pending_row")).toMatch(/Очікує другого підтвердження: Пуск КГУ — Іваненко І\./);
});

test("D-43: «Підтвердити (2/2)» у смузі очікування → confirm_second → блок прогресу", async () => {
    const rec = mockControl();
    await mountControl();
    expect(queryText(".o_td_en_pending_row")).toMatch(/Очікує другого підтвердження: Пуск КГУ — Іваненко І\./);
    await click(".o_td_en_pending_ok");
    await waitFor(".o_td_en_cd_steps");
    expect(rec.second).toEqual([[55]]);
    await animationFrame();
    expect(queryText(".o_td_en_cd_step--done[data-step='done']")).toBe("Виконано");
    await click(".o_td_en_cd_close");
    await animationFrame();
    expect(queryAll(".o_td_en_cd").length).toBe(0);
});

test("AC-299: «Скасувати дію» → undo(action_id) → діалог зворотної дії", async () => {
    const rec = mockControl();
    await mountControl();
    await click("[data-journal-id='801'] .o_td_en_j_undo");
    await animationFrame();
    expect(rec.undo).toEqual([[801]]);
    expect(queryText(".o_td_en_cd .modal-title")).toBe("Скасувати: BESS · розряд?");
});

test("«Усі записи» відкриває журнал (V-41), посилання на заявку ТО — форму запису", async () => {
    mockControl();
    const done = [];
    mockService("action", { doAction: (action) => done.push(action) });
    await mountControl();
    await click(".o_td_en_j_all");
    expect(done.at(-1)).toBe("td_energy_control.action_td_energy_action");
    await click("[data-journal-id='812'] .o_td_en_j_ref");
    expect(done.at(-1).res_model).toBe("maintenance.request");
    expect(done.at(-1).res_id).toBe(48);
});

// ------------------------------------------------------------------ оновлення

test("шина td_energy_control: повідомлення перечитує дані через 2 с (дебаунс)", async () => {
    const rec = mockControl();
    await mountControl();
    const before = rec.loads;
    rec.bus({ kinds: ["scenario"], ts: "2026-10-18T11:20:05Z" });
    rec.bus({ kinds: ["action"], ts: "2026-10-18T11:20:05Z" });
    rec.bus({ kinds: ["other"], ts: "2026-10-18T11:20:05Z" });
    await advanceTime(1000);
    expect(rec.loads).toBe(before);
    await advanceTime(1500);
    await animationFrame();
    expect(rec.loads).toBe(before + 1);
});

test("помилка завантаження: повідомлення про помилку замість екрана", async () => {
    mockService("bus_service", { addChannel() {}, deleteChannel() {}, subscribe() {}, unsubscribe() {} });
    onRpc("td.energy.control", "get_control", () => {
        throw new Error("Немає доступу до Енергетики.");
    });
    await mountControl();
    expect(queryAll(".o_td_en_error").length).toBe(1);
    expect(queryText(".o_td_en_error")).toMatch(/Не вдалося завантажити екран «Керування»/);
    expect(queryAll(".o_td_en_h1").length).toBe(0);
});
