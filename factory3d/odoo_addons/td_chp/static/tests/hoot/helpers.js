/** @odoo-module */
// Спільні помічники hoot-набору пульта КГУ: мок API td_chp (маршрути API-01…07), монтування, очікування.
import { advanceTime, animationFrame } from "@odoo/hoot-mock";
import { mockService, mountWithCleanup, onRpc, patchWithCleanup } from "@web/../tests/web_test_helpers";
import { ChpPult } from "@td_chp/pult/pult";
import { STATE } from "./state_fixture";

export const clone = (value) => JSON.parse(JSON.stringify(value));

/** Стан «Резерв»: усі 14 умов пуску виконані, двигун стоїть. */
export function reserveState() {
    const s = clone(STATE);
    Object.assign(s.v, {
        "ctl/state": 0, "ctl/step": 0, "eng/rpm": 0, "gen/p_kw": 0, "gen/load_pct": 0, "ht/q_total": 0, "gas/flow": 0,
        "safe/qf_closed": 0, "gas/yv1": 0, "gas/yv2": 0,
    });
    return s;
}

export function prepareDto(kind, over = {}) {
    const cls = kind === "start" || kind === "stop" ? "B" : "A";
    return Object.assign(
        {
            ref: "chp:12", action_id: 12, token: "tok-" + kind, ttl_s: 120, verify_timeout_s: 30, kind, cls,
            title: { start: "Пуск КГУ-1", stop: "Стоп КГУ-1", estop: "Аварійний стоп КГУ-1", reset: "Скидання аварії КГУ-1" }[kind] || "Команда КГУ-1",
            text: "Текст команди.", sub: cls === "B" ? "Команда класу Б: два підтвердження." : "Клас А: одне підтвердження.",
            checks: clone(STATE.il.list), blocked: false, blocked_reason: "", needs_second: cls === "B",
            confirm_label: cls === "B" ? "Підтвердити (1/2)" : "Виконати", disabled_reason: null,
        },
        over
    );
}

/**
 * Реєструє мок маршрутів `/td_chp/*`. `ctx.state` можна міняти під час тесту; `ctx.cmd(params)` — відповідь `/td_chp/cmd`.
 * Повертає `ctx` з журналом викликів `ctx.calls[route]`.
 */
export function mockChp({ state = null, cmd = null, sim = null, webgl = false, trend = null } = {}) {
    const ctx = { state: state || clone(STATE), cmd, sim, calls: {}, trend };
    const log = (route, params) => {
        (ctx.calls[route] = ctx.calls[route] || []).push(params);
    };
    ctx.bus = { channels: [], handlers: {} };
    mockService("bus_service", {
        addChannel: (name) => ctx.bus.channels.push(name),
        deleteChannel: (name) => ctx.bus.channels.splice(ctx.bus.channels.indexOf(name), 1),
        subscribe: (type, cb) => {
            ctx.bus.handlers[type] = cb;
        },
        unsubscribe: (type) => {
            delete ctx.bus.handlers[type];
        },
    });
    onRpc("/td_chp/state", async (request) => {
        const { params } = await request.json();
        log("state", params);
        return ctx.state;
    });
    onRpc("/td_chp/trend", async (request) => {
        const { params } = await request.json();
        log("trend", params);
        if (ctx.trend) {
            return ctx.trend(params);
        }
        const n = params.range_h === 1 ? 120 : 288;
        const step = params.range_h === 1 ? 30 : 300;
        const series = { pel: [], qth: [], gas: [] };
        for (let i = 0; i < n; i++) {
            series.pel.push(i % 40 === 0 ? null : 500 + (i % 50));
            series.qth.push(i % 40 === 0 ? null : 600 + (i % 50));
            series.gas.push(i % 40 === 0 ? null : 150 + (i % 20));
        }
        return { range_h: params.range_h, step_s: step, t0: new Date(Date.now() - n * step * 1000).toISOString(), series };
    });
    onRpc("/td_chp/journal", async (request) => {
        const { params } = await request.json();
        log("journal", params);
        return { items: clone(ctx.state.jr || []), more: false };
    });
    onRpc("/td_chp/ack", async (request) => {
        const { params } = await request.json();
        log("ack", params);
        return { acked: 1 };
    });
    onRpc("/td_chp/maintenance", async (request) => {
        const { params } = await request.json();
        log("maintenance", params);
        return clone(ctx.state.to || []);
    });
    onRpc("/td_chp/cmd", async (request) => {
        const { params } = await request.json();
        log("cmd", params);
        if (!ctx.cmd) {
            throw new Error("не змоковано /td_chp/cmd");
        }
        return ctx.cmd(params);
    });
    onRpc("/td_chp/sim", async (request) => {
        const { params } = await request.json();
        log("sim", params);
        if (ctx.sim) {
            return ctx.sim(params);
        }
        return { available: false, scenarios: [] };
    });
    if (!webgl) {
        // у headless-браузері WebGL може бути: гасимо, щоб 3D не стартував у кожному тесті (заглушку перевіряє окремий тест)
        const proto = HTMLCanvasElement.prototype;
        const original = proto.getContext;
        patchWithCleanup(proto, {
            getContext(type, ...args) {
                if (typeof type === "string" && type.includes("webgl")) {
                    return null;
                }
                return original.call(this, type, ...args);
            },
        });
    }
    return ctx;
}

/** Дати завершитися запитам і рендеру. */
export async function settle(times = 3) {
    for (let i = 0; i < times; i++) {
        await advanceTime(50);
        await animationFrame();
    }
}

export async function mountPult(context = {}) {
    await mountWithCleanup(ChpPult, { props: { action: { context } } });
    await settle();
}
