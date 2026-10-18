/** @odoo-module **/
// UI-05 NodeCard (`td_energy.node_card`, V-23) і UI-06 CurrentChart: картка вузла (R-30, API-07).
// Блоки (KPI, графік струму, відгалуження, облік, захист, події, обслуговування, відключення) показуються,
// лише якщо їх повернув сервер для виду вузла.

import { Component, onMounted, onWillStart, onWillUnmount, useState } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { useEnergyActions } from "../common/actions";
import { useEnergyBus } from "../common/bus";
import {
    CHART,
    areaPath,
    chartX,
    chartY,
    factSegments,
    linePath,
    markerPos,
    scaleMax,
    xTicks,
    yTicks,
} from "../common/chart";
import { DASH, errorMessage, fmtAuto, fmtDate, fmtDec, fmtInt, hourToHm, kyivNowHour } from "../common/format";
import { OutageDialog, openTicketWizard, plural } from "./dialogs";

const REFRESH_S = 30;
const TAP_STATES = { run: "Працює", idle: "Простій", mnt: "На ТО" };
const MAINT_TAGS = { "Нова": "new", "У роботі": "plan", "План": "muted", "Заплановано": "plan" };
const CHIP_CLASS = { ok: "ok", warn: "warn", alarm: "alarm", off: "muted", info: "muted" };

const r1 = (n) => Math.round(n * 10) / 10;

/** UI-06: струм (А) за добу 15 хв, лінії «увага 80 %» і «номінал», маркер максимуму, «зараз». */
export class CurrentChart extends Component {
    static template = "td_energy.CurrentChart";
    static props = { chart: { type: Object }, ratingA: { type: Number, optional: true } };

    get chart() {
        return this.props.chart;
    }

    get nowSlot() {
        return this.chart.now_slot ?? 0;
    }

    get nowHour() {
        const hour = kyivNowHour();
        return Math.floor(hour * 4) === this.nowSlot ? hour : this.nowSlot / 4 + 0.1;
    }

    get rating() {
        return this.chart.rating_a || this.props.ratingA || 0;
    }

    get vmax() {
        return scaleMax(this.rating, this.chart.a, [this.chart.peak && this.chart.peak.a]);
    }

    get paths() {
        const segments = factSegments(this.chart.a || [], this.nowSlot, this.nowHour);
        return {
            line: segments.map((seg) => linePath(seg, this.vmax)).join(" "),
            area: segments.map((seg) => areaPath(seg, this.vmax)).join(" "),
        };
    }

    get gridLines() {
        return yTicks(this.vmax);
    }

    get hourTicks() {
        return xTicks();
    }

    lineY(value) {
        return r1(chartY(value, this.vmax));
    }

    get nowX() {
        return r1(chartX(this.nowHour));
    }

    get peak() {
        const peak = this.chart.peak;
        if (!peak || peak.a === null || peak.a === undefined) {
            return null;
        }
        const pos = markerPos(peak.slot, peak.a, this.vmax);
        const flip = pos.x > CHART.right - 90;
        return { ...pos, a: peak.a, tx: flip ? pos.x - 8 : pos.x + 8, ty: pos.y - 8, anchor: flip ? "end" : "start" };
    }

    get warnPct() {
        return this.rating ? Math.round((this.chart.warn_a / this.rating) * 100) : 80;
    }

    fmtInt(value) {
        return fmtInt(value);
    }
}

export class NodeCard extends Component {
    static template = "td_energy.NodeCard";
    static components = { CurrentChart };
    static props = ["*"];

    setup() {
        this.actions = useEnergyActions();
        this.dialog = useService("dialog");
        const action = this.props.action || {};
        const params = action.params || {};
        const context = action.context || {};
        this.code = params.code || context.active_code || null;
        this.state = useState({ data: null, failed: null, filter: "all" });
        this.tapStates = TAP_STATES;
        this.fmtInt = fmtInt;
        this.fmtDec = fmtDec;
        this.fmtAuto = fmtAuto;
        this.fmtDate = fmtDate;
        this.dash = DASH;

        useEnergyBus(() => this.load(), ["kpi", "alarm", "state", "profile"]);
        onWillStart(() => this.load());
        onMounted(() => {
            this.timer = browser.setInterval(() => this.load(), REFRESH_S * 1000);
        });
        onWillUnmount(() => browser.clearInterval(this.timer));
    }

    async load() {
        if (!this.code) {
            this.state.failed = "Не вказано код вузла.";
            return;
        }
        try {
            this.state.data = await this.actions.orm.call("td.energy.dashboard", "get_node_card", [], {
                code: this.code,
                period: "day",
            });
            this.state.failed = null;
        } catch (error) {
            if (!this.state.data) {
                this.state.failed = errorMessage(error);
            } else {
                this.actions.fail(error);
            }
        }
    }

    get node() {
        return this.state.data.node;
    }

    get data() {
        return this.state.data;
    }

    /** Шлях: назви предків; останній елемент — поточний вузол. */
    get path() {
        return this.node.path || [];
    }

    chipClass(chip, index) {
        if (index === 0 && chip.state === "ok") {
            return "teal"; // «Під напругою» — колір схеми
        }
        return CHIP_CLASS[chip.state] || "muted";
    }

    // ------------------------------------------------------------------ KPI

    get kpiCards() {
        const k = this.data.kpis || {};
        const cards = [];
        if (k.current) {
            const c = k.current;
            const pct = c.pct;
            cards.push({
                id: "current",
                label: "Струм зараз",
                text: fmtInt(c.a),
                unit: c.a === null || c.a === undefined ? "" : "А",
                bar: pct === null || pct === undefined ? null : { pct: Math.min(100, pct), cls: pct >= 100 ? "alarm" : pct >= 80 ? "warn" : "" },
                note:
                    pct === null || pct === undefined
                        ? ""
                        : `${fmtInt(pct)} % від ${fmtInt(c.rating_a)} А` + ((c.phases || []).length ? ` · фази ${c.phases.map((v) => fmtInt(v)).join(" / ")} А` : ""),
            });
        }
        if (k.power) {
            const p = k.power;
            cards.push({
                id: "power",
                label: "Потужність",
                text: fmtAuto(p.kw),
                unit: p.kw === null || p.kw === undefined ? "" : "кВт",
                note: [
                    p.p_inst_kw === null || p.p_inst_kw === undefined ? null : `встановлена ${fmtAuto(p.p_inst_kw)} кВт`,
                    p.cos_phi === null || p.cos_phi === undefined ? null : `cos φ ${fmtDec(p.cos_phi, 2)}`,
                ]
                    .filter(Boolean)
                    .join(" · "),
            });
        }
        if (k.energy) {
            const e = k.energy;
            const orders = e.orders === null || e.orders === undefined ? null : `${fmtInt(e.orders)} ${plural(e.orders, "замовлення", "замовлення", "замовлень")} на виробництво`;
            cards.push({
                id: "energy",
                label: "Енергія сьогодні",
                text: fmtInt(e.kwh),
                unit: e.kwh === null || e.kwh === undefined ? "" : "кВт·год",
                note: [e.cost_uah === undefined ? null : `${fmtInt(e.cost_uah)} ₴`, orders].filter(Boolean).join(" · "),
            });
        }
        if (k.peak) {
            const p = k.peak;
            cards.push({
                id: "peak",
                label: "Максимум доби",
                text: fmtInt(p.a),
                unit: p.a === null || p.a === undefined ? "" : "А",
                note: p.time ? `о ${p.time} · поріг уваги ${fmtInt(p.warn_a)} А (80 %)` : "",
            });
        }
        if (k.idle) {
            const names = k.idle.names || [];
            cards.push({
                id: "idle",
                label: "Простій під напругою",
                text: fmtDec(k.idle.kw, 1),
                unit: k.idle.kw === null || k.idle.kw === undefined ? "" : "кВт",
                note: names.length ? `${names.join(" і ")} ${names.length > 1 ? "не працюють" : "не працює"}` : "Простоїв немає",
            });
        }
        return cards;
    }

    // ------------------------------------------------------------------ відгалуження

    get taps() {
        return this.data.taps || null;
    }

    get tapRows() {
        const rows = (this.taps && this.taps.rows) || [];
        const filter = this.state.filter;
        return rows.filter((row) => filter === "all" || (filter === "run" ? row.state === "run" : row.state !== "run"));
    }

    setFilter(filter) {
        this.state.filter = filter;
    }

    // ------------------------------------------------------------------ допоміжні блоки

    get meter() {
        const m = this.data.meter;
        if (!m) {
            return null;
        }
        const rows = [
            ["Лічильник", [m.code, m.model].filter(Boolean).join(" · ")],
            ["Трансформатори струму", m.ct_ratio || DASH],
            ["Останнє показання", m.last_ts ? `${m.last_ts} · ${fmtInt(m.last_kwh)} кВт·год` : DASH],
            ["Наступна повірка", fmtDate(m.next_verification)],
            ["Баланс з відгалуженнями", m.balance_pct === null || m.balance_pct === undefined ? DASH : `${fmtDec(m.balance_pct, 1)} % за годину`],
        ];
        return rows;
    }

    get protection() {
        const p = this.data.protection;
        if (!p) {
            return null;
        }
        const ir = p.ir && p.ir.ratio ? `${fmtDec(p.ir.ratio, 1)} × In = ${fmtInt(p.ir.a)} А` : DASH;
        const thermo = p.thermography && p.thermography.date ? `${fmtDate(p.thermography.date, true)} · ${(p.thermography.state || "").toLowerCase()}` : DASH;
        return {
            title: `Захист ${p.breaker || ""}`.trim(),
            rows: [
                ["Автомат", `${fmtInt(p.rating_a)} А${p.trip_unit ? ` · розчіплювач ${p.trip_unit}` : ""}`],
                ["Уставка Ir", ir],
                ["Спрацювань за рік", fmtInt(p.trips_year)],
                ["Тепловізійний огляд", thermo],
            ],
        };
    }

    maintTag(state) {
        return MAINT_TAGS[state] || "muted";
    }

    get outage() {
        const o = this.data.outage;
        if (!o) {
            return null;
        }
        const count = this.taps ? this.taps.count : null;
        const parts = [];
        if (count !== null && count !== undefined) {
            parts.push(`${fmtInt(count)} ${plural(count, "відгалуження", "відгалуження", "відгалужень")}`);
        }
        parts.push(`${fmtInt(o.orders)} ${plural(o.orders, "замовлення", "замовлення", "замовлень")}`);
        return { ...o, affects: `Зачіпає ${parts.join(" і ")} · статус: ${o.state_label}` };
    }

    get genset() {
        const extra = this.data.extra || {};
        return extra.genset && extra.genset.open_action ? extra.genset : null;
    }

    // ------------------------------------------------------------------ дії

    openPult() {
        return this.actions.openPult();
    }

    openNode(code) {
        if (code && code !== this.code) {
            return this.actions.openCard(code);
        }
    }

    planOutage() {
        const node = this.node;
        const last = this.path.length ? this.path[this.path.length - 1].name : node.name;
        this.dialog.add(OutageDialog, { nodeCode: node.code, nodeName: last, onCreated: () => this.load() });
    }

    createTicket() {
        return openTicketWizard(this.actions, this.node.code);
    }

    async openMaint(item) {
        if (item.id) {
            await this.actions.openRecord("maintenance.request", item.id);
        }
    }

    async openOutagePlan() {
        const outage = this.data.outage;
        if (outage && outage.plan_id) {
            await this.actions.openRecord("td.energy.outage.plan", outage.plan_id);
        }
    }

    async openGenset() {
        try {
            await this.actions.action.doAction(this.genset.open_action);
        } catch (error) {
            this.actions.fail(error);
        }
    }

    hourLabel(slot) {
        return hourToHm(slot / 4);
    }
}

registry.category("actions").add("td_energy.node_card", NodeCard);
