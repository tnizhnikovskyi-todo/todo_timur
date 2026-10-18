/** @odoo-module **/
// UI-01 Resources (`td_energy_resources.resources`, V-01): екран «Енергоресурси заводу». Вкладки ресурсів, KPI, графік
// доби + список споживачів, резерви економії. Дані — `td.energy.res.dashboard.get_resources(code)` (API-01);
// оновлення: шина `td_energy` (kpi, дебаунс 2 с) і резервне опитування `meta.refresh_s`.

import { Component, onMounted, onWillStart, onWillUnmount, useState } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import { registry } from "@web/core/registry";
import { useEnergyActions } from "@td_energy/common/actions";
import { useEnergyBus } from "@td_energy/common/bus";
import { errorMessage, staleText } from "@td_energy/common/format";
import { ResChart } from "./chart";
import { useResourceDay } from "./day";
import { ResKpis } from "./kpis";
import { ResList } from "./list";
import { ResNotes } from "./notes";
import { ResTabs } from "./tabs";

export const MODEL = "td.energy.res.dashboard";
const DEFAULT_REFRESH_S = 30;

/** Частина відповіді може прийти як `{"error": …}` (збій однієї частини не ламає решту, SPEC розд. 11). */
export function partError(part) {
    return part && !Array.isArray(part) && typeof part === "object" && "error" in part ? String(part.error) : null;
}

export class Resources extends Component {
    static template = "td_energy_resources.Resources";
    static components = { ResTabs, ResKpis, ResChart, ResList, ResNotes };
    static props = ["*"];

    setup() {
        this.actions = useEnergyActions();
        const context = (this.props.action && this.props.action.context) || {};
        this.state = useState({ code: context.td_energy_resource || null, data: null, failed: null, loading: false });
        this.day = useResourceDay(() => (this.state.data && this.state.data.meta) || null);
        this.lastLoad = 0;
        this.timer = null;

        useEnergyBus(() => this.load(), ["kpi"]);
        onWillStart(() => this.load());
        onMounted(() => {
            const seconds = (this.meta && this.meta.refresh_s) || DEFAULT_REFRESH_S;
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

    async load() {
        const requested = this.state.code;
        let res;
        try {
            res = await this.actions.orm.call(MODEL, "get_resources", [], { code: requested });
        } catch (error) {
            if (requested !== this.state.code) {
                return;
            }
            this.state.loading = false;
            if (requested && !this.state.data) {
                // невідомий/прихований ресурс із контексту дії → перша вкладка
                this.state.code = null;
                return this.load();
            }
            if (!this.state.data) {
                this.state.failed = errorMessage(error);
            } else {
                this.state.code = this.state.data.resource ? this.state.data.resource.code : null;
                this.actions.fail(error);
            }
            return;
        }
        this.lastLoad = Date.now();
        if (requested !== this.state.code) {
            return; // відповідь на застарілу вкладку
        }
        const tabs = res.tabs || [];
        if (requested && tabs.length && !tabs.some((tab) => tab.code === requested)) {
            this.state.code = tabs[0].code; // вкладку приховано (D-48) → перша
            return this.load();
        }
        this.state.failed = null;
        this.state.loading = false;
        this.state.data = res;
        this.state.code = res.resource ? res.resource.code : requested;
    }

    async selectTab(code) {
        if (code === this.state.code) {
            return;
        }
        this.state.code = code;
        this.state.loading = true;
        await this.load();
    }

    // ------------------------------------------------------------------ відповідь

    get meta() {
        return (this.state.data && this.state.data.meta) || {};
    }

    get capabilities() {
        return this.meta.capabilities || {};
    }

    get tabs() {
        return (this.state.data && this.state.data.tabs) || [];
    }

    get resource() {
        return (this.state.data && this.state.data.resource) || null;
    }

    /** Колір ресурсу (`resource.color`, інакше акцент Енергетики). */
    get color() {
        return (this.resource && this.resource.color) || "#714B67";
    }

    get totalText() {
        const total = this.meta.total;
        return (total && total.text) || "";
    }

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

    part(name) {
        const resource = this.resource;
        const value = resource ? resource[name] : null;
        return { error: partError(value), value: partError(value) ? null : value };
    }

    get kpis() {
        const { error, value } = this.part("kpis");
        return { error, items: Array.isArray(value) ? value : [] };
    }

    get chart() {
        return this.part("chart");
    }

    get list() {
        return this.part("list");
    }

    get notes() {
        const { error, value } = this.part("notes");
        return { error, items: Array.isArray(value) ? value : [] };
    }

    // ------------------------------------------------------------------ дії

    /** «Вивантажити в Excel» (D-41, API-07): завантаження xlsx за добу екрана. */
    exportXlsx() {
        browser.open(this.day.exportUrl, "_self");
    }
}

registry.category("actions").add("td_energy_resources.resources", Resources);
