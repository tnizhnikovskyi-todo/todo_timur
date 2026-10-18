/** @odoo-module **/
// UI-H1…UI-H4: вкладка «Обхід» мобільного екрана `td_energy.mobile` (запис реєстру `td_energy.mobile_tabs`, C-06).
// Чек-лист обходу зі знімком значень сигналів, оптимістична відмітка, «Завершити обхід», «Останні обходи».
// Дані — `td.energy.round.get_mobile` (API-H1); оновлення — після дій, за тиком шини `state` і резервним опитуванням.

import { Component, onMounted, onWillStart, onWillUnmount, useState } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import { registry } from "@web/core/registry";
import { useEnergyActions } from "@td_energy/common/actions";
import { useEnergyBus } from "@td_energy/common/bus";
import { errorMessage } from "@td_energy/common/format";

export const mobileTabs = registry.category("td_energy.mobile_tabs");

const REFRESH_MS = 30000;
export const STATE_LABELS = { done: "Завершено", missed: "Не виконано", cancelled: "Скасовано" };

/** UI-H2: рядок пункту — `<label>` ≥ 44 px, чекбокс 22 px, підказка, «поза нормою» + коментар, «Де це в 3D». */
export class RoundItem extends Component {
    static template = "td_energy_mobile.RoundItem";
    static props = {
        item: { type: Object },
        canEdit: { type: Boolean },
        onToggle: { type: Function },
        onShow3d: { type: Function },
    };

    onChange(ev) {
        this.props.onToggle(this.props.item, ev.target.checked);
    }

    onComment(ev) {
        this.props.onToggle(this.props.item, true, ev.target.value);
    }

    show3d() {
        this.props.onShow3d(this.props.item.node_code);
    }
}

/** UI-H3: «Завершити обхід» ≥ 48 px; при `finish_blocked` — сіра (`aria-disabled`), клік показує тост (D-72). */
export class RoundFinish extends Component {
    static template = "td_energy_mobile.RoundFinish";
    static props = { round: { type: Object }, onFinish: { type: Function } };

    get blocked() {
        return !!this.props.round.finish_blocked;
    }
}

/** UI-H4: «Останні обходи» (≤ `history_limit`): назва, статус, `done/total`, відхилення. */
export class RoundHistory extends Component {
    static template = "td_energy_mobile.RoundHistory";
    static props = { history: { type: Array }, collapsed: { type: Boolean, optional: true } };

    setup() {
        this.stateLabels = STATE_LABELS;
    }
}

/** UI-H1: вкладка «Обхід». */
export class MobileRound extends Component {
    static template = "td_energy_mobile.MobileRound";
    static components = { RoundItem, RoundFinish, RoundHistory };
    static props = ["*"];

    setup() {
        this.actions = useEnergyActions();
        this.state = useState({ data: null, failed: null });
        this.queue = Promise.resolve();
        this.pending = 0;
        onWillStart(() => this.load());
        useEnergyBus(() => this.load(), ["state"]);
        onMounted(() => {
            this.timer = browser.setInterval(() => this.load(), REFRESH_MS);
        });
        onWillUnmount(() => browser.clearInterval(this.timer));
        this.toggle = (item, done, comment) => this.toggleItem(item, done, comment);
        this.show3d = (code) => this.actions.show3d(code);
        this.finish = () => this.finishRound();
    }

    async load() {
        if (this.pending) {
            return; // відмітки в польоті: відповідь дії вже повертає свіжий обхід
        }
        try {
            this.state.data = await this.actions.orm.call("td.energy.round", "get_mobile", []);
            this.state.failed = null;
        } catch (error) {
            if (!this.state.data) {
                this.state.failed = errorMessage(error);
            } else {
                this.actions.fail(error);
            }
        }
    }

    retry() {
        this.state.failed = null;
        return this.load();
    }

    get round() {
        return this.state.data && this.state.data.round;
    }

    get next() {
        return this.state.data && this.state.data.next;
    }

    get history() {
        return (this.state.data && this.state.data.history) || [];
    }

    get banner() {
        const performer = this.round && this.round.performer;
        return performer && !performer.is_me && this.round.state !== "done" ? `Обхід виконує ${performer.name}` : "";
    }

    /** Перерахунок лічильників після оптимістичної відмітки (усі пункти вважаються обов'язковими). */
    recount(round) {
        const total = round.items.length;
        const done = round.items.filter((i) => i.done).length;
        round.done_count = done;
        round.total_count = total;
        round.progress_pct = total ? Math.round((done * 100) / total) : 0;
        round.finish_blocked = total - done ? `залишилось ${total - done}` : null;
        round.can_finish = !round.finish_blocked;
    }

    /** UI-H2: оптимістична відмітка, відкат при помилці; запити йдуть послідовно (блокування виконавця на сервері). */
    toggleItem(item, done, comment) {
        const round = this.round;
        const was = { done: item.done, result: item.result };
        if (comment === undefined) {
            item.done = done;
            if (!done) {
                item.result = "pending";
            }
            this.recount(round);
        }
        this.pending += 1;
        const kwargs = comment === undefined ? {} : { comment };
        this.queue = this.queue
            .then(() => this.actions.orm.call("td.energy.round", "action_toggle_item", [item.id, done], kwargs))
            .then((res) => {
                if (this.pending === 1) {
                    this.state.data.round = res.round;
                }
            })
            .catch((error) => {
                item.done = was.done;
                item.result = was.result;
                this.recount(round);
                this.actions.fail(error);
            })
            .finally(() => {
                this.pending -= 1;
            });
        return this.queue;
    }

    /** UI-H3: завершення; `finish_blocked` → тост (D-72), успіх → тост із серверним часом (D-75) і перезавантаження. */
    async finishRound() {
        const round = this.round;
        if (round.finish_blocked) {
            this.actions.notify(`Позначте всі пункти обходу: ${round.finish_blocked}`, "warning");
            return;
        }
        try {
            const res = await this.actions.orm.call("td.energy.round", "action_finish", [round.id]);
            this.actions.notify(`Обхід завершено й записано в журнал о ${res.finished_at_local}`, "success");
            if (this.props.reload) {
                this.props.reload();
            }
        } catch (error) {
            this.actions.fail(error);
        }
        await this.load();
    }
}

/** Запис реєстру вкладок (C-06): без `badge` (D-78). */
export const ROUND_TAB = {
    id: "round",
    label: "Обхід",
    title: "Обхід",
    sequence: 40,
    component: MobileRound,
    icon: "M9 4h6M9 4a2 2 0 0 0-2 2H5v15h14V6h-2a2 2 0 0 0-2-2M9 12l2 2 4-4",
};

export function registerRoundTab() {
    mobileTabs.add("round", ROUND_TAB, { force: true });
}

/** Сторінка hoot (`/web/tests`) збирає код усіх модулів: вкладку там додають самі тести, тож W1 лишається з трьома.
 * Використовується глобальний `location` (реальна адреса сторінки), а не `browser.location`, який hoot підміняє. */
export function isUnitTestPage() {
    return globalThis.location.pathname.startsWith("/web/tests");
}

if (!isUnitTestPage()) {
    registerRoundTab();
}
