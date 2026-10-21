/** @odoo-module **/
// UI-02 `store.js`: сховище пульта КГУ. Замінює модель величин мокапу (`b_sim.js`) адаптером даних на API:
// `store={S,V,K,cyl,jr,to,caps,il,pending}`. Оновлення — шина `td_chp` (дебаунс 300 мс, див. `pult.js`) + опитування
// 5 с (2 с при відкритій команді); числа згладжуються `approach` (`b_sim.js:7`). Немає значення — NaN, на екрані «—».
// Пульт нічого не вирішує: стани, пороги, перевірки й тексти приходять із бекенду (R-01…R-13).

import { rpc } from "@web/core/network/rpc";
import { browser } from "@web/core/browser/browser";
import { approach, num } from "./util";

export const POLL_MS = 5000;
export const POLL_FAST_MS = 2000;
export const TAU = 0.8;
export const ST = { RESERVE: 0, START: 1, RUN: 2, ALARM: 3, COOL: 4 };
export const ST_KEY = ["reserve", "start", "run", "alarm", "cool"];
export const ST_NAME = ["Резерв", "Пуск", "Робота", "Аварія", "Охолодження"];
export const MODES = { heat: "За тепловим графіком", el: "За електричним графіком", peak: "Зрізання піку", manual: "Ручний" };
export const MODE_KEYS = ["heat", "el", "peak", "manual"];
export const HEAT_KEYS = ["auto", "boiler", "cooler"];
export const BYPASS_KEYS = ["auto", "ht", "bypass"];
/** R-05: вузол підсвітки для `alarm/trip` (у DTO `trip` вузла немає). */
export const TRIP_NODE = { 1: "qf", 2: "qf", 3: "cabinet" };
/** R-13: кроки пуску (назви й тривалість у емуляторі, с). */
export const STEPS = [
    { id: "vent", name: "Вентиляція контейнера", dur: 5 },
    { id: "warm", name: "Попередній підігрів ОЖ", dur: 6 },
    { id: "lube", name: "Попереднє змащення", dur: 5 },
    { id: "proving", name: "Перевірка герметичності клапанів", dur: 7 },
    { id: "crank", name: "Прокрутка стартером", dur: 6 },
    { id: "ign", name: "Запалювання", dur: 5 },
    { id: "idle", name: "Холостий хід", dur: 5 },
    { id: "sync", name: "Синхронізація з мережею", dur: 9 },
    { id: "load", name: "Набір навантаження", dur: 12 },
];
export const CYL = ["A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8", "B1", "B2", "B3", "B4", "B5", "B6", "B7", "B8"];

/** Ключ `V.*` мокапу → код сигналу без `chp/` (SPEC §5.2, колонка «мокап») або [код, множник]. */
export const VMAP = {
    rpm: "eng/rpm", pel: "gen/p_kw", pShaft: "eng/shaft_kw", qth: "ht/q_total", gas: "gas/flow",
    cos: "gen/cos", Q: "gen/q_kvar", U: "gen/u_v", f: "gen/f_hz", I: "gen/i_a", Ipct: "gen/i_pct",
    excI: "gen/exc_a", excU: "gen/exc_v",
    pOil: "eng/p_oil", tJo: "eng/t_jacket_out", tJi: "eng/t_jacket_in", tOil: "eng/t_oil", tOilOut: "oil/t_out",
    dpOilF: "oil/dp_filter", oilLvl: "oil/level", oilFresh: "oil/fresh", oilWaste: "oil/waste", oilCons: "oil/cons",
    torque: "eng/torque", tBrg: "eng/t_bearing", vib: "eng/vib",
    gasP: "gas/p_in", gasReg: "gas/p_reg", dpFilter: "gas/dp_filter", vpLeak: "gas/vp_leak",
    thr: "eng/throttle", lambda: "eng/lambda", pMix: "eng/p_mix", tcRpm: "eng/tc_rpm", pBoost: "eng/p_boost",
    tAirIn: "eng/t_air_in", tAirOut: "eng/t_air_out", tTurb: "eng/t_turb_in",
    qPhe: "ht/q_phe", qExh: "ht/q_exh", qBoiler: "ht/q_boiler", qCooler: "ht/q_cooler", demand: "ctl/heat_demand",
    flow: "ht/flow", tRetRaw: "ht/t_ret_raw", tRet: "ht/t_ret", mixPos: "ht/mix_pos", cap: ["ht/cap_pct", 0.01],
    tMid: "ht/t_mid", tSup: "ht/t_sup", flowC: "ht/flow_cool", tCoolOut: "ht/t_cool_out", fan: "ht/cooler_fan",
    pLoop: "ht/p_loop", pExpHT: "ht/p_exp_ht", pExpLT: "ht/p_exp_lt", pExpH: "ht/p_exp_h",
    pDisHT: "ht/p_dis_ht", hmTot: "ht/heat_total",
    qLT: "lt/q_kw", flowLT: "lt/flow", tLTin: "lt/t_in", tLTout: "lt/t_out", fanLT: "lt/fan", pDisLT: "lt/p_dis",
    tE1: "exh/t_e1", tCatOut: "exh/t_cat_out", tE2: "exh/t_e2", tStack: "exh/t_stack", dpCat: "exh/dp_cat",
    nox: "exh/nox", coRaw: "exh/co_raw", co: "exh/co", o2: "exh/o2", bypass: ["exh/bypass_pct", 0.01], backP: "exh/back_p",
    airDp: "air/dp_filter", tCont: "air/t_cont", fanSup: "air/fan_sup", fanExh: "air/fan_exh", louver: "air/louver",
    lel: "safe/lel", ctrlV: "safe/ctrl_v", uGrid: "safe/u_grid", dfdt: "safe/rocof_dfdt", dphi: "safe/rocof_dphi",
    batV: "eng/bat_v", starterI: "eng/starter_a", batI: "eng/bat_a",
    eTot: "em/kwh", eRe: "em/kvarh",
};
/** Насоси: `V.pHT={run,f,I}` — прапор + частота + струм. */
const PUMPS = {
    pHT: ["ht/pump_ht_run", "ht/pump_ht_f", "ht/pump_ht_a"],
    pHe: ["ht/pump_he_run", "ht/pump_he_f", "ht/pump_he_a"],
    pLT: ["lt/pump_run", "lt/pump_f", "lt/pump_a"],
};
/** Показники `k` DTO (R-02) → `V.*`. */
const KMAP = { etaE: "eta_e", etaH: "eta_h", etaT: "eta_t", co2: "co2_kgh", dT: "dT" };
/** Лічильники не згладжуються: вони монотонні й великі. */
const RAW_KEYS = new Set(["eTot", "eRe", "hmTot"]);

const flag = (x) => x === 1;
const nvl = (x, d) => (Number.isFinite(x) ? x : d);

export function errorText(err) {
    const d = err && err.data;
    if (d && d.message) {
        return String(d.message);
    }
    if (err && err.message && !/^RPC_ERROR|^Odoo/.test(err.message)) {
        return String(err.message);
    }
    return "Помилка запиту до Odoo.";
}

export class ChpStore {
    /** @param {{unitCode?: string|null}} opts */
    constructor({ unitCode = null } = {}) {
        this._seen = false;
        this.unitCode = unitCode || null;
        this.S = {
            state: -1, mode: "heat", setpoint: NaN, cosSet: NaN, heatDir: "auto", bypassMode: "auto", load: NaN,
            rpm: NaN, qf: false, valves: false, valvesTest: false, stepI: -1, coolLeft: 0, warmSkip: false,
            permit: false, remote: false, rsw: false, grid: false, fire: false, rocofFlag: false, estopLoop: false,
            vp: { st: "none", time: null }, ext: "ready", extLevel: NaN, topup: false, starter: false, starts: NaN,
            hours: NaN, tAmb: NaN, psl: false, psh: false, inletValve: false, esCab: false, esDoor: false, esExt: false,
            eDay: NaN, qDay: NaN, gDay: NaN, cDay: NaN, runDay: NaN, gasTotal: NaN,
            sync: { du: NaN, df: NaN, dp: NaN, ok: false },
            alarm: null, trip: null, hl: null, stale: true, gasP: NaN, pOil: NaN, fan: NaN, fanLT: NaN, fanSup: NaN,
            fanExh: NaN, louver: NaN, lel: NaN, mixPos: NaN, bypass: NaN, cap: NaN,
        };
        this.V = {};
        this.T = {}; // цілі згладжування
        Object.keys(VMAP).forEach((k) => {
            this.V[k] = NaN;
            this.T[k] = NaN;
        });
        Object.keys(KMAP).forEach((k) => {
            this.V[k] = NaN;
            this.T[k] = NaN;
        });
        Object.keys(PUMPS).forEach((k) => {
            this.V[k] = { run: false, f: NaN, I: NaN };
            this.T[k] = { f: NaN, I: NaN };
        });
        this.V.hmP = NaN;
        this.V.hmFlow = NaN;
        this.V.cylAvg = NaN;
        this.K = {};
        this.cyl = CYL.map((id) => ({ id, t: NaN, dev: NaN, knock: NaN, kv: NaN, ms: NaN, plug: NaN }));
        this.jr = [];
        this.jrMore = false;
        this.jrExpanded = false;
        this.to = [];
        this.caps = { operate: false, chief: false, sim: false, write: false, rsw: false, bridge: false };
        this.il = { ok: false, list: [] };
        this.pending = [];
        this.unit = { code: "", name: "КГУ", p_nom_kw: 800, cylinders: 16, passport: {}, assumption: false };
        this.th = {
            gas_min_bar: 1.5, gas_warn_bar: 1.7, ret_set_c: 70, jacket_warn_c: 92, jacket_max_c: 95, bat_min_v: 23.5,
            oil_min_pct: 40, lel_warn_pct: 10, lel_alarm_pct: 20, nox_limit: 250, co_limit: 300, cyl_dev_warn_k: 25,
            cyl_dev_alarm_k: 40, knock_warn: 35, knock_alarm: 60, plug_interval_h: 4000, lhv_kwh_m3: 9.5, co2_kg_m3: 1.98,
        };
        this.raw = {};
        this.units = {};
        this.stateOf = {};
        this.age = null;
        this.ts = null;
        this.etag = null;
        this.loaded = false;
        this.offline = false;
        this.readDisabled = false;
        this.error = "";
        this.rev = 0; // збільшується при кожній зміні DTO: за ним оновлюють журнал, ТО, діалоги
        this.fast = false;
        this.listeners = new Set();
        this._timer = null;
        this._busy = null;
        this._again = false;
        this._stopped = true;
        this.trend = { range: 24, t0: null, step: 300, series: { pel: [], qth: [], gas: [] }, live: [], loadedAt: 0 };
    }

    /* ------------------------------ запити ------------------------------ */
    async call(route, params = {}) {
        return rpc(route, params);
    }

    /** API-01. Повертає true, якщо DTO змінився. */
    async refresh() {
        if (this._busy) {
            this._again = true;
            return this._busy;
        }
        this._busy = this._refresh();
        try {
            return await this._busy;
        } finally {
            this._busy = null;
            if (this._again && !this._stopped) {
                this._again = false;
                this.refresh();
            }
        }
    }

    async _refresh() {
        let dto;
        try {
            dto = await this.call("/td_chp/state", { unit: this.unitCode, etag: this.etag });
        } catch (err) {
            this.offline = !(err && err.data && err.data.message);
            this.error = errorText(err);
            this._emit();
            return false;
        }
        const was = this.offline;
        this.offline = false;
        this.error = "";
        if (dto && dto.not_modified) {
            this.lastOk = Date.now();
            if (was) {
                this._emit();
            }
            return false;
        }
        try {
            this.applyState(dto || {});
        } catch (err) {
            this.error = "Невірна відповідь сервера: " + (err && err.message ? err.message : err);
            this._emit();
            return false;
        }
        if (this.jrExpanded) {
            await this.loadJournal({ limit: Math.min(200, Math.max(50, this.jr.length)) });
        }
        this._emit();
        return true;
    }

    /** Розібрати DTO API-01 у S/V/K/… (без мережі: його викликають і тести). */
    applyState(dto) {
        this.lastOk = Date.now();
        if (dto.read_disabled) {
            this.readDisabled = true;
            this.loaded = true;
            this.etag = null;
            this.S.stale = true;
            this.rev++;
            return;
        }
        this.readDisabled = false;
        this.loaded = true;
        this.etag = dto.ver || null;
        this.ts = dto.ts || null;
        this.age = dto.age_s ?? null;
        this.unit = Object.assign({}, this.unit, dto.unit || {});
        if (dto.unit && dto.unit.th) {
            this.th = Object.assign({}, this.th, dto.unit.th);
        }
        this.caps = Object.assign({}, this.caps, dto.caps || {});
        this.raw = dto.v || {};
        this.units = dto.u || {};
        this.stateOf = dto.st || {};
        this.K = dto.k || {};
        this.il = dto.il || { ok: false, list: [] };
        this.pending = dto.pending || [];
        this.to = dto.to || [];
        if (!this.jrExpanded) {
            this.jr = dto.jr || [];
        }
        this.S.stale = !!dto.stale;
        const first = !this._seen;
        this._seen = true;
        this._targets();
        this._derive(dto);
        this._smoothAll(0, first); // перший DTO показуємо одразу, далі — плавно (`tick`)
        this.rev++;
        this._pushLive();
    }

    _targets() {
        const r = (code) => num(this.raw[code]);
        Object.keys(VMAP).forEach((k) => {
            const m = VMAP[k];
            const [code, mul] = Array.isArray(m) ? m : [m, 1];
            this.T[k] = r(code) * mul;
        });
        Object.keys(KMAP).forEach((k) => {
            this.T[k] = num(this.K[KMAP[k]]);
        });
        Object.keys(PUMPS).forEach((k) => {
            const [run, f, i] = PUMPS[k];
            this.V[k].run = flag(r(run));
            this.T[k].f = r(f);
            this.T[k].I = r(i);
        });
    }

    _derive(dto) {
        const S = this.S;
        const r = (code) => num(this.raw[code]);
        const st = r("ctl/state");
        S.state = Number.isFinite(st) ? st : -1;
        const mode = r("ctl/mode");
        S.mode = MODE_KEYS[mode] || (mode === 4 ? "profile" : "heat");
        S.modeUnknown = !MODE_KEYS[mode];
        S.setpoint = r("ctl/sp_pct");
        S.cosSet = r("ctl/cos_set");
        S.heatDir = HEAT_KEYS[r("ctl/heat_dir")] || "auto";
        S.bypassMode = BYPASS_KEYS[r("ctl/bypass_mode")] || "auto";
        S.load = r("gen/load_pct") / 100;
        S.qf = flag(r("safe/qf_closed"));
        const yv1 = r("gas/yv1");
        const yv2 = r("gas/yv2");
        S.valves = yv1 === 1 && yv2 === 1;
        S.valvesTest = yv1 === 2 || yv2 === 2;
        const step = r("ctl/step");
        S.stepI = step >= 1 && step <= STEPS.length ? step - 1 : -1;
        S.stepLeft = r("ctl/step_left");
        S.coolLeft = nvl(r("ctl/cool_left"), 0);
        S.warmSkip = flag(r("ctl/warm_skip"));
        S.permit = flag(r("ctl/permit"));
        S.remote = flag(r("ctl/remote"));
        S.rsw = !!this.caps.rsw;
        S.grid = flag(r("safe/grid_ok"));
        S.fire = flag(r("safe/fire"));
        S.rocofFlag = flag(r("safe/rocof"));
        S.estopLoop = flag(r("safe/estop_loop"));
        const vp = r("gas/vp_state");
        const ts = r("gas/vp_ts");
        S.vp = { st: { 1: "run", 2: "ok", 3: "leak" }[vp] || "none", time: ts > 0 ? new Date(ts * 1000) : null };
        S.ext = { 1: "release", 2: "fired" }[r("safe/ext_state")] || "ready";
        S.extLevel = r("safe/ext_level");
        S.topup = flag(r("oil/topup"));
        S.starter = flag(r("eng/starter_on"));
        S.starts = r("eng/starts");
        S.hours = r("eng/hours");
        S.tAmb = r("air/t_amb");
        S.psl = flag(r("gas/psl"));
        S.psh = flag(r("gas/psh"));
        S.inletValve = flag(r("gas/inlet_valve"));
        S.esCab = flag(r("safe/es_cab"));
        S.esDoor = flag(r("safe/es_door"));
        S.esExt = flag(r("safe/es_ext"));
        S.eDay = r("em/kwh_day");
        S.qDay = r("ht/heat_day");
        S.gDay = r("gas/day");
        S.cDay = num(this.K.co2_day_t) * 1000;
        S.runDay = r("em/runh_day");
        S.gasTotal = r("gas/total");
        S.sync = { du: r("ctl/sync_du"), df: r("ctl/sync_df"), dp: r("ctl/sync_dphi"), ok: flag(r("ctl/sync_ok")) };
        S.alarm = dto.alarm ? { code: dto.alarm.code, text: dto.alarm.text, node: dto.alarm.node, acked: !!dto.alarm.acked } : null;
        S.trip = dto.trip ? { code: dto.trip.code, text: dto.trip.text, node: TRIP_NODE[dto.trip.code] || "cabinet" } : null;
        // R-05: аварія → вузол «alarm»; зупинка без аварії → вузол «warn», знімається при коді 0 і стані 0
        S.hl = S.alarm
            ? { node: S.alarm.node, kind: "alarm" }
            : S.trip && S.state !== ST.RESERVE
              ? { node: S.trip.node, kind: "warn" }
              : null;
        // циліндри
        (dto.cyl || []).forEach((c, i) => {
            const row = this.cyl[i];
            if (!row) {
                return;
            }
            row.id = c.id;
            row.t = num(c.t);
            row.dev = num(c.dev);
            row.knock = num(c.knock);
            row.kv = num(c.kv);
            row.ms = num(c.ms);
            row.plug = num(c.plug_h);
        });
        const ts_ = this.cyl.map((c) => c.t).filter(Number.isFinite);
        this.V.cylAvg = ts_.length ? ts_.reduce((a, b) => a + b, 0) / ts_.length : NaN;
    }

    /** Згладжування чисел до цілей. `snap` — без плавності (перший DTO або тест). */
    _smoothAll(dt, snap = false) {
        const V = this.V;
        const T = this.T;
        const go = (cur, tgt, keep) => {
            if (!Number.isFinite(tgt)) {
                return NaN;
            }
            if (keep || snap || !Number.isFinite(cur)) {
                return tgt;
            }
            return approach(cur, tgt, dt, TAU);
        };
        Object.keys(VMAP).forEach((k) => {
            V[k] = go(V[k], T[k], RAW_KEYS.has(k));
        });
        Object.keys(KMAP).forEach((k) => {
            V[k] = go(V[k], T[k]);
        });
        Object.keys(PUMPS).forEach((k) => {
            V[k].f = go(V[k].f, T[k].f);
            V[k].I = go(V[k].I, T[k].I);
        });
        V.hmP = V.qBoiler;
        V.hmFlow = V.flow;
        const S = this.S;
        S.rpm = V.rpm;
        S.gasP = V.gasP;
        S.pOil = V.pOil;
        S.fan = V.fan;
        S.fanLT = V.fanLT;
        S.fanSup = V.fanSup;
        S.fanExh = V.fanExh;
        S.louver = V.louver;
        S.lel = V.lel;
        S.mixPos = V.mixPos;
        S.bypass = V.bypass;
        S.cap = V.cap;
    }

    /** Крок згладжування (250 мс у `pult.js`). */
    tick(dt) {
        this._smoothAll(Math.min(dt, 1));
    }

    /* ------------------------------ ТО ------------------------------ */
    _toItem(frag) {
        const f = String(frag).toLowerCase();
        return this.to.find((x) => String(x.name || "").toLowerCase().includes(f));
    }
    toLeft(frag) {
        const x = this._toItem(frag);
        return x ? num(x.left_h) : NaN;
    }
    toSince(frag) {
        const x = this._toItem(frag);
        return x ? num(this.S.hours) - num(x.last_h) : NaN;
    }

    /* ------------------------------ тренд (UI-06) ------------------------------ */
    async loadTrend(range) {
        const tr = this.trend;
        try {
            const d = await this.call("/td_chp/trend", { unit: this.unitCode, range_h: range });
            tr.range = d.range_h;
            tr.step = d.step_s;
            tr.t0 = new Date(d.t0).getTime();
            tr.series = d.series || { pel: [], qth: [], gas: [] };
            tr.loadedAt = Date.now();
            tr.live = [];
            tr.error = "";
        } catch (err) {
            tr.error = errorText(err);
        }
        this._emit();
    }
    /** Точки тренда: API-02 (відрізки `step_s`) + «живі» точки зі сховища (після кінця ряду). */
    trendPoints() {
        const tr = this.trend;
        const pts = [];
        if (tr.t0 !== null) {
            const n = tr.series.pel.length;
            for (let i = 0; i < n; i++) {
                const pe = tr.series.pel[i];
                const pt = tr.series.qth[i];
                const g = tr.series.gas[i];
                if (pe === null && pt === null && g === null) {
                    continue;
                }
                pts.push({ t: tr.t0 + (i + 0.5) * tr.step * 1000, pe, pt, g });
            }
        }
        const last = pts.length ? pts[pts.length - 1].t : 0;
        tr.live.forEach((p) => {
            if (p.t > last) {
                pts.push(p);
            }
        });
        return pts;
    }
    _pushLive() {
        const tr = this.trend;
        const now = Date.now();
        const last = tr.live[tr.live.length - 1];
        const gap = tr.range === 1 ? 5000 : 30000;
        if (last && now - last.t < gap) {
            return;
        }
        if (!Number.isFinite(this.T.pel) && !Number.isFinite(this.T.qth) && !Number.isFinite(this.T.gas)) {
            return;
        }
        const nn = (x) => (Number.isFinite(x) ? x : null);
        tr.live.push({ t: now, pe: nn(this.T.pel), pt: nn(this.T.qth), g: nn(this.T.gas) });
        if (tr.live.length > 400) {
            tr.live.shift();
        }
    }

    /* ------------------------------ журнал ------------------------------ */
    async loadJournal({ more = false, limit = 50 } = {}) {
        const before = more && this.jr.length ? this.jr[this.jr.length - 1].ts : null;
        try {
            const d = await this.call("/td_chp/journal", { unit: this.unitCode, limit, before });
            this.jr = more ? this.jr.concat(d.items || []) : d.items || [];
            this.jrMore = !!d.more;
            this.jrExpanded = true;
            this.rev++;
        } catch (err) {
            this.error = errorText(err);
        }
        this._emit();
    }
    async ack(ids = null) {
        const res = await this.call("/td_chp/ack", { unit: this.unitCode, ids });
        await this.refresh();
        return res;
    }

    /* ------------------------------ ТО, команди, імітація ------------------------------ */
    async maintenanceDone(ruleId) {
        const list = await this.call("/td_chp/maintenance", { unit: this.unitCode, rule_id: ruleId });
        this.to = list || this.to;
        this.rev++;
        this._emit();
        await this.refresh();
        return list;
    }
    command(op, kw = {}) {
        return this.call("/td_chp/cmd", Object.assign({ op, unit: this.unitCode }, kw));
    }
    sim(op, code = null, params = null) {
        return this.call("/td_chp/sim", { op, code, params });
    }

    /* ------------------------------ цикл оновлення ------------------------------ */
    onChange(fn) {
        this.listeners.add(fn);
        return () => this.listeners.delete(fn);
    }
    _emit() {
        this.listeners.forEach((fn) => fn(this));
    }
    start() {
        this._stopped = false;
        const loop = async () => {
            if (this._stopped) {
                return;
            }
            await this.refresh();
            if (!this._stopped) {
                this._timer = browser.setTimeout(loop, this.fast ? POLL_FAST_MS : POLL_MS);
            }
        };
        return loop();
    }
    /** Дострокове оновлення (шина, дія користувача). */
    poke() {
        if (!this._stopped) {
            this.refresh();
        }
    }
    stop() {
        this._stopped = true;
        browser.clearTimeout(this._timer);
        this._timer = null;
        this.listeners.clear();
    }
}
