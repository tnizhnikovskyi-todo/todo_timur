/** @odoo-module **/
// UI-01 Pult (`td_energy.pult`, V-22): «Пульт енергетика». KPI й перемикач періоду, рекомендація, однолінійна схема,
// профіль доби з прогнозом, тривоги, побічні блоки. Оновлення: шина `td_energy` (дебаунс 2 с, лише потрібні частини)
// і резервне опитування `meta.refresh_s` (30 с).

import { Component, onMounted, onWillStart, onWillUnmount, useState } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { useEnergyActions } from "../common/actions";
import { partsForKinds, useEnergyBus } from "../common/bus";
import { DASH, PERIODS, chpText, errorMessage, fmtDec, fmtInt, staleText } from "../common/format";
import { runAdviceAction, snoozeAdvice, visibleAdviceActions } from "../common/advice";
import { OutageDialog, openTicketWizard } from "../node_card/dialogs";
import { AlarmList } from "./alarms";
import { ProfileChart } from "./profile";
import { SldCanvas } from "./sld";

export const PARTS = ["kpis", "sld", "profile", "alarms", "side", "advice"];
const PART_KEYS = {
    kpis: ["kpis"],
    sld: ["sld"],
    profile: ["profile", "foot"],
    alarms: ["alarms"],
    side: ["top", "mo", "maint"],
    advice: ["advice"],
};

const MAINT_TAGS = {
    "Нова": "new",
    "Заплановано": "plan",
    "План": "plan",
    "Узгоджено": "ok",
    "У роботі": "plan",
    "На узгодженні": "new",
};

export class Pult extends Component {
    static template = "td_energy.Pult";
    static components = { SldCanvas, ProfileChart, AlarmList };
    static props = ["*"];

    setup() {
        this.actions = useEnergyActions();
        this.dialog = useService("dialog");
        this.periods = PERIODS;
        const context = (this.props.action && this.props.action.context) || {};
        const period = PERIODS.some(([key]) => key === context.td_energy_period) ? context.td_energy_period : "now";
        this.state = useState({ period, data: null, errors: {}, failed: null, selNode: null });
        this.lastLoad = 0;
        this.timer = null;
        this.fmtInt = fmtInt;
        this.fmtDec = fmtDec;
        this.dash = DASH;

        useEnergyBus((kinds) => this.load(partsForKinds(kinds)));
        onWillStart(() => this.load());
        onMounted(() => {
            const seconds = (this.state.data && this.state.data.meta && this.state.data.meta.refresh_s) || 30;
            this.timer = browser.setInterval(() => {
                // резервне опитування: лише якщо шина давно мовчить
                if (Date.now() - this.lastLoad >= seconds * 1000 - 1000) {
                    this.load();
                }
            }, seconds * 1000);
        });
        onWillUnmount(() => browser.clearInterval(this.timer));
    }

    // ------------------------------------------------------------------ дані

    /** Завантаження всіх частин (parts=null) або лише названих; відповідь зливається в `state.data`. */
    async load(parts = null) {
        const period = this.state.period;
        let res;
        try {
            res = await this.actions.orm.call("td.energy.dashboard", "get_pult", [], { period, parts });
        } catch (error) {
            if (!this.state.data) {
                this.state.failed = errorMessage(error);
            } else {
                this.actions.fail(error);
            }
            return;
        }
        this.lastLoad = Date.now();
        if (period !== this.state.period) {
            return; // відповідь на застарілий період
        }
        this.state.failed = null;
        const data = { ...(this.state.data || {}), meta: res.meta || (this.state.data || {}).meta };
        const errors = { ...this.state.errors };
        for (const part of parts || PARTS) {
            const keys = PART_KEYS[part];
            const first = res[keys[0]];
            if (first && typeof first === "object" && !Array.isArray(first) && "error" in first && Object.keys(first).length === 1) {
                errors[part] = first.error;
                continue;
            }
            delete errors[part];
            for (const key of keys) {
                if (key in res) {
                    data[key] = res[key];
                }
            }
        }
        this.state.errors = errors;
        this.state.data = data;
        const sld = data.sld;
        if (this.state.selNode && sld && !(sld.nodes || []).some((n) => n.code === this.state.selNode)) {
            this.state.selNode = null;
        }
    }

    async setPeriod(period) {
        if (period === this.state.period) {
            return;
        }
        this.state.period = period;
        await this.load(["kpis", "profile"]);
    }

    get meta() {
        return this.state.data.meta || {};
    }

    get capabilities() {
        return this.meta.capabilities || {};
    }

    get stale() {
        return this.meta.data_state === "stale";
    }

    // ------------------------------------------------------------------ шапка

    /** Індикатор даних: «Живі дані · HH:MM» / «Частково · HH:MM» / «Немає даних · {вік}». */
    get dataChip() {
        const meta = this.meta;
        if (meta.data_state === "stale") {
            return { cls: "stale", text: staleText(meta.age_s) };
        }
        if (meta.data_state === "partial") {
            return { cls: "partial", text: `Частково · ${meta.now_local || ""}` };
        }
        return { cls: "live", text: `Живі дані · ${meta.now_local || ""}` };
    }

    // ------------------------------------------------------------------ KPI

    /** Шість карток KPI (R-27). Живі показники при `stale` — «—». */
    get kpiCards() {
        const k = this.state.data.kpis;
        if (!k) {
            return [];
        }
        const stale = this.stale;
        const live = (value) => (stale ? null : value);
        const unit = (text, u) => (text === DASH ? { text, unit: "" } : { text, unit: u });
        const cards = [];

        const grid = k.grid || {};
        const gridPct = live(grid.pct);
        cards.push({
            id: "grid",
            label: "З мережі зараз",
            ...unit(fmtInt(live(grid.kw)), "кВт"),
            bar: gridPct === null || gridPct === undefined ? null : { pct: Math.min(100, Math.max(0, gridPct)), cls: gridPct > 100 ? "alarm" : "" },
            note: stale || gridPct === null || gridPct === undefined
                ? ""
                : `${fmtInt(gridPct)} % договірної · запас ${fmtInt(grid.reserve_kw)} кВт` +
                  (grid.export_kw > 0 ? ` · експорт ${fmtInt(grid.export_kw)} кВт` : ""),
        });

        const load = k.load || {};
        cards.push({
            id: "load",
            label: "Споживання заводу",
            ...unit(fmtInt(live(load.kw)), "кВт"),
            note: stale
                ? ""
                : [load.pv_share_pct === null || load.pv_share_pct === undefined ? null : `СЕС покриває ${fmtInt(load.pv_share_pct)} %`, chpText(load.chp_state)]
                      .filter(Boolean)
                      .join(" · "),
        });

        const energy = k.energy || {};
        cards.push({
            id: "energy",
            label: energy.label || "З мережі сьогодні",
            ...unit(fmtInt(energy.kwh), "кВт·год"),
            note:
                energy.cost_uah === undefined
                    ? ""
                    : [
                          energy.cost_uah === null ? null : `${fmtInt(energy.cost_uah)} ₴`,
                          energy.price_uah === null || energy.price_uah === undefined ? null : `тариф ${fmtDec(energy.price_uah, 2)} ₴/кВт·год`,
                      ]
                          .filter(Boolean)
                          .join(" · "),
        });

        const peak = k.peak || {};
        cards.push({
            id: "peak",
            label: peak.label || "Пік доби (15 хв)",
            ...unit(fmtInt(peak.kw), "кВт"),
            note: peak.note || "",
        });

        const gen = k.generation || {};
        const bessMode = gen.bess_kw >= 1 ? " · заряд" : gen.bess_kw <= -1 ? " · розряд" : "";
        cards.push({
            id: "generation",
            label: "Власна генерація",
            ...unit(fmtInt(live(gen.pv_kw)), "кВт"),
            note: stale
                ? ""
                : [
                      gen.pv_pct_kwp === null || gen.pv_pct_kwp === undefined ? null : `СЕС ${fmtInt(gen.pv_pct_kwp)} % піку`,
                      gen.bess_soc_pct === null || gen.bess_soc_pct === undefined ? null : `BESS ${fmtInt(gen.bess_soc_pct)} %${bessMode}`,
                      gen.genset ? `ДГУ ${gen.genset.label}` : null,
                  ]
                      .filter(Boolean)
                      .join(" · "),
        });

        const cos = k.cos_phi || {};
        const low = (cos.low_sections || []).map(
            (n) => `Секція ${n}: ${fmtDec((cos.sections || [])[n - 1], 2)} — нижче ${fmtDec(cos.warn, 2)}`
        );
        const below = cos.plant !== null && cos.plant !== undefined && cos.plant < cos.alarm;
        cards.push({
            id: "cos_phi",
            label: "cos φ заводу",
            text: fmtDec(live(cos.plant), 2),
            unit: "",
            note: stale
                ? ""
                : low.length
                ? low.join("; ")
                : (cos.sections || []).length
                ? `Секції: ${cos.sections.map((v) => fmtDec(v, 2)).join(" · ")}`
                : "",
            noteCls: stale ? "" : low.length ? (below ? "alarm" : "warn") : "",
        });
        return cards;
    }

    // ------------------------------------------------------------------ рекомендація

    /** Кнопки рекомендації: `enabled=false` і `control` без обробника (W2) не малюються (D-02). */
    get adviceActions() {
        return visibleAdviceActions(this.state.data.advice);
    }

    /** UI-28: баннер «Виконано» (`advice.state === 'done'`): зелений, без «Пізніше», кнопка «Скасувати». */
    get adviceDone() {
        const advice = this.state.data.advice;
        return !!advice && advice.state === "done";
    }

    async runAdvice(act) {
        const changed = await runAdviceAction(this.actions, this.state.data.advice, act, this);
        if (changed) {
            await this.load(["advice", "alarms"]);
        }
    }

    async snooze() {
        if (await snoozeAdvice(this.actions, this.state.data.advice)) {
            this.state.data.advice = null;
        }
    }

    // ------------------------------------------------------------------ схема

    selectNode(code) {
        this.state.selNode = code;
    }

    get selectedCard() {
        const sld = this.state.data.sld;
        const code = this.state.selNode;
        const node = code && sld ? (sld.nodes || []).find((n) => n.code === code) : null;
        return node && node.card ? node : null;
    }

    // ------------------------------------------------------------------ побічні блоки

    get topMax() {
        const top = this.state.data.top || [];
        return top.length ? Math.max(...top.map((t) => t.kw || 0), 1) : 1;
    }

    topWidth(row) {
        return Math.round(((row.kw || 0) / this.topMax) * 100);
    }

    maintTag(state) {
        return MAINT_TAGS[state] || "muted";
    }

    async openMaint(item) {
        if (item.kind === "request") {
            await this.actions.openRecord("maintenance.request", item.id);
        } else if (item.kind === "outage") {
            await this.actions.openRecord("td.energy.outage.plan", item.id);
        }
    }

    async openProduction(name) {
        const rows = await this.actions.orm.searchRead("mrp.production", [["name", "=", name]], ["id"], { limit: 1 });
        if (rows.length) {
            await this.actions.openRecord("mrp.production", rows[0].id);
        }
    }

    planOutage() {
        const node = this.selectedCard;
        if (node) {
            this.dialog.add(OutageDialog, {
                nodeCode: node.code,
                nodeName: node.label,
                onCreated: () => this.load(["side", "alarms"]),
            });
            return;
        }
        return this.actions.action.doAction({
            type: "ir.actions.act_window",
            res_model: "td.energy.outage.plan",
            views: [[false, "form"]],
            target: "current",
        });
    }

    createTicket() {
        const node = this.selectedCard;
        return openTicketWizard(this.actions, node ? node.code : null);
    }

    openAlloc() {
        return this.actions.openXml("td_energy.action_td_energy_alloc_pivot");
    }

    openMaintenance() {
        return this.actions.openXml("maintenance.hr_equipment_request_action");
    }

    /** C-02: дію «Звіт за зміну» задає модуль аналітики (`meta.report_action`); без неї кнопки немає. */
    get reportAction() {
        return this.capabilities.report ? this.meta.report_action || null : null;
    }

    openReport() {
        const xmlid = this.reportAction;
        return xmlid ? this.actions.openXml(xmlid) : undefined;
    }
}

registry.category("actions").add("td_energy.pult", Pult);
