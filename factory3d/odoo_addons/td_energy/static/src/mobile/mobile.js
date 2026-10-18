/** @odoo-module **/
// UI-09 Mobile (`td_energy.mobile`, V-24): екран чергового енергетика (≥ 360 px): вкладки «Стан», «Тривоги · N», «Схема».
// Вкладки беруться з реєстру `td_energy.mobile_tabs` (C-33): W4 додає «Обхід» власним записом
// `{id, label, sequence, component, [title], [badge(mobile)]}`; компонент вкладки отримує props
// `{mobile, meta, capabilities, reload, goTab}`. Кнопки не менші за 48 px.

import { Component, onMounted, onWillStart, onWillUnmount, useState } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";
import { useEnergyActions } from "../common/actions";
import { runAdviceAction, snoozeAdvice, visibleAdviceActions } from "../common/advice";
import { useEnergyBus } from "../common/bus";
import {
    LEVEL_LABELS,
    STATE_LABELS,
    alarmLevel,
    errorMessage,
    fmtAge,
    fmtDec,
    fmtInt,
} from "../common/format";

export const mobileTabs = registry.category("td_energy.mobile_tabs");

/** Картка активної тривоги: «Беру в роботу» → «У роботі · ви» → «Закрити»; «Де це в 3D»; «Призначити на себе». */
export class MobileAlarmCard extends Component {
    static template = "td_energy.MobileAlarmCard";
    static props = {
        item: { type: Object },
        capabilities: { type: Object, optional: true },
        onChanged: { type: Function, optional: true },
    };

    setup() {
        this.actions = useEnergyActions();
        this.state = useState({ busy: false });
        this.levelLabels = LEVEL_LABELS;
    }

    get item() {
        return this.props.item;
    }

    get level() {
        return alarmLevel(this.item);
    }

    get isOpen() {
        return this.item.state === "active" || this.item.state === "acked";
    }

    /** Тег рівня: у моїй роботі — «У роботі · ви». */
    get tag() {
        if (this.item.taken_by_me && this.isOpen) {
            return { text: "У роботі · ви", cls: "work" };
        }
        return { text: LEVEL_LABELS[this.level], cls: this.level };
    }

    get canTake() {
        const caps = this.props.capabilities || {};
        return !!caps.take && this.isOpen && !this.item.taken_by_me && !this.item.assigned;
    }

    get canResolve() {
        const caps = this.props.capabilities || {};
        return !!caps.take && this.isOpen && this.item.taken_by_me;
    }

    get assignedElse() {
        return this.isOpen && this.item.assigned && !this.item.taken_by_me ? `У роботі: ${this.item.assigned}` : "";
    }

    get canAssignRequest() {
        return !!this.item.request_id && !!this.item.request_assignable;
    }

    async run(method, message) {
        if (this.state.busy) {
            return;
        }
        this.state.busy = true;
        try {
            await this.actions.orm.call("td.energy.event", method, [[this.item.id]]);
            this.actions.notify(`${message}: ${this.item.title}`, "success");
            if (this.props.onChanged) {
                await this.props.onChanged();
            }
        } catch (error) {
            this.actions.fail(error);
        } finally {
            this.state.busy = false;
        }
    }

    take() {
        return this.run("action_take", "Взято в роботу");
    }

    resolve() {
        return this.run("action_resolve", "Закрито");
    }

    async assignRequest() {
        if (this.state.busy) {
            return;
        }
        this.state.busy = true;
        try {
            await this.actions.orm.write("maintenance.request", [this.item.request_id], { user_id: user.userId });
            this.actions.notify("Заявку ТО призначено на вас.", "success");
            if (this.props.onChanged) {
                await this.props.onChanged();
            }
        } catch (error) {
            this.actions.fail(error);
        } finally {
            this.state.busy = false;
        }
    }

    where3d() {
        return this.actions.show3d(this.item.node_code);
    }
}

/** Рекомендація (слот): дії link/ticket і «Відкласти». */
export class MobileAdvice extends Component {
    static template = "td_energy.MobileAdvice";
    static props = {
        advice: { type: Object },
        onChanged: { type: Function, optional: true },
    };

    setup() {
        this.actions = useEnergyActions();
    }

    get acts() {
        return visibleAdviceActions(this.props.advice);
    }

    async run(act) {
        if (await runAdviceAction(this.actions, this.props.advice, act, this)) {
            await this.refresh();
        }
    }

    async snooze() {
        if (await snoozeAdvice(this.actions, this.props.advice)) {
            await this.refresh();
        }
    }

    async refresh() {
        if (this.props.onChanged) {
            await this.props.onChanged();
        }
    }
}

/** Секція «Активні · N» з картками тривог і рекомендацією; на вкладці «Стан» — з кнопкою «Усі тривоги». */
export class MobileActive extends Component {
    static template = "td_energy.MobileActive";
    static components = { MobileAlarmCard, MobileAdvice };
    static props = {
        mobile: { type: Object },
        capabilities: { type: Object, optional: true },
        reload: { type: Function },
        goTab: { type: Function, optional: true },
    };

    get alarms() {
        return this.props.mobile.alarms || { active_count: 0, active: [], info_today: [], advice: null };
    }
}

export class MobileState extends Component {
    static template = "td_energy.MobileState";
    static components = { MobileActive };
    static props = ["*"];

    get state() {
        return this.props.mobile.state || {};
    }

    /** Тексти плиток стану (макет Mobile): мережа, СЕС, BESS, ДГУ · АВР, cos φ. */
    get tiles() {
        const s = this.state;
        const bess = s.bess || {};
        const kw = bess.kw;
        const bessKw = kw >= 1 ? `заряд ${fmtInt(kw)} кВт` : kw <= -1 ? `розряд ${fmtInt(-kw)} кВт` : "0 кВт";
        const ats = ((s.genset_ats && s.genset_ats.text) || "").replace(/^ДГУ · АВР:\s*/, "");
        const cos = s.cos_phi || {};
        const low = (cos.low_sections || []).map((n) => `с${n}`);
        return [
            { id: "pv", label: "СЕС", value: `${fmtInt(s.pv_kw)} кВт`, cls: "gen" },
            { id: "bess", label: "BESS", value: `${fmtInt(bess.soc_pct)} % · ${bessKw}`, cls: "" },
            { id: "ats", label: "ДГУ · АВР", value: ats || "—", cls: "" },
            {
                id: "cos",
                label: "cos φ",
                value: `${fmtDec(cos.plant, 2)}${low.length ? ` · ${low.join(", ")} нижче норми` : ""}`,
                cls: low.length ? "warn" : "",
            },
        ];
    }

    get gridBar() {
        const pct = this.state.pct;
        return pct === null || pct === undefined ? 0 : Math.min(100, Math.max(0, pct));
    }

    fmt(value) {
        return fmtInt(value);
    }
}

export class MobileAlarms extends Component {
    static template = "td_energy.MobileAlarms";
    static components = { MobileActive };
    static props = ["*"];

    get info() {
        return (this.props.mobile.alarms || {}).info_today || [];
    }
}

export class MobileScheme extends Component {
    static template = "td_energy.MobileScheme";
    static props = ["*"];

    setup() {
        this.stateLabels = STATE_LABELS;
    }

    get nodes() {
        return this.props.mobile.scheme || [];
    }
}

mobileTabs.add("state", { id: "state", label: "Стан", title: "Меблеве підприємство", sequence: 10, component: MobileState, icon: "M13 2 4 14h7l-1 8 9-12h-7z" });
mobileTabs.add("alarms", {
    id: "alarms",
    label: "Тривоги",
    title: "Тривоги",
    sequence: 20,
    component: MobileAlarms,
    badge: (mobile) => (mobile.alarms ? mobile.alarms.active_count : null),
    icon: "M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9M10 21h4",
});
mobileTabs.add("scheme", {
    id: "scheme",
    label: "Схема",
    title: "Схема мережі",
    sequence: 30,
    component: MobileScheme,
    icon: "M12 3v6M5 9h14M5 9v6M12 9v6M19 9v6M3 15h4M10 15h4M17 15h4",
});

export class Mobile extends Component {
    static template = "td_energy.Mobile";
    static props = ["*"];

    setup() {
        this.actions = useEnergyActions();
        this.state = useState({ tab: null, data: null, failed: null });
        useEnergyBus(() => this.load(), ["kpi", "alarm", "state", "advice"]);
        onWillStart(() => this.load());
        onMounted(() => {
            const seconds = (this.state.data && this.state.data.meta && this.state.data.meta.refresh_s) || 30;
            this.timer = browser.setInterval(() => this.load(), seconds * 1000);
        });
        onWillUnmount(() => browser.clearInterval(this.timer));
        this.reload = () => this.load();
        this.goTab = (id) => {
            this.state.tab = id;
        };
    }

    async load() {
        try {
            // усі три вкладки одним запитом (≤ 20 КБ): лічильник «Тривоги · N» потрібен на кожній
            this.state.data = await this.actions.orm.call("td.energy.dashboard", "get_mobile", [], { tab: null });
            this.state.failed = null;
        } catch (error) {
            if (!this.state.data) {
                this.state.failed = errorMessage(error);
            } else {
                this.actions.fail(error);
            }
        }
    }

    get tabs() {
        return mobileTabs
            .getAll()
            .slice()
            .sort((a, b) => (a.sequence ?? 100) - (b.sequence ?? 100));
    }

    get current() {
        const tabs = this.tabs;
        return tabs.find((tab) => tab.id === this.state.tab) || tabs[0];
    }

    get meta() {
        return this.state.data.meta || {};
    }

    get capabilities() {
        return this.meta.capabilities || {};
    }

    get chip() {
        const meta = this.meta;
        if (meta.data_state === "stale") {
            return { cls: "stale", text: `Немає даних · ${fmtAge(meta.age_s)}` };
        }
        return { cls: meta.data_state === "partial" ? "partial" : "live", text: meta.now_local || "" };
    }

    tabLabel(tab) {
        const badge = tab.badge ? tab.badge(this.state.data) : null;
        return badge === null || badge === undefined ? tab.label : `${tab.label} · ${badge}`;
    }

    get tabProps() {
        return {
            mobile: this.state.data,
            meta: this.meta,
            capabilities: this.capabilities,
            reload: this.reload,
            goTab: this.goTab,
        };
    }
}

registry.category("actions").add("td_energy.mobile", Mobile);
