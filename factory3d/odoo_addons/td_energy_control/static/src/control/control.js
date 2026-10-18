/** @odoo-module **/
// UI-12 Control (`td_energy_control.control`, V-35): экран «Керування енергетикою заводу». Данные — `get_control()`
// (API-16); обновление: шина `td_energy_control` (дебаунс 2 с) и резервный таймер `meta.refresh_s` (30 с).
// Состояние: `data`, `reorder` (локальный порядок сброса), `busy`; диалоги — ConfirmDialog/ParamsDialog (UI-17, UI-18).

import { Component, onMounted, onWillStart, onWillUnmount, useState } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { useEnergyActions } from "@td_energy/common/actions";
import { errorMessage } from "@td_energy/common/format";
import { useControlBus } from "./bus";
import { MODEL, runCommand, runSecond, runUndo } from "./confirm_dialog";
import { CommandTiles } from "./commands";
import { Journal } from "./journal";
import { ParamsDialog } from "./params_dialog";
import { ScenarioGrid } from "./scenarios";
import { ScheduleTimeline } from "./schedule";
import { ShedList } from "./shed";

export const JOURNAL_STEP = 50;
export const ENGINE_KINDS = ["action", "scenario", "engine", "schedule", "shed"];
export const INFO_TEXT =
    "Сценарії виконує контролер ГРЩ і збирач сигналів, без затримок Odoo. Тут задаються режими, уставки й розклад. " +
    "Кожна ручна команда проходить блокування й підтвердження і пишеться в журнал. " +
    "Захист людей і пожежна автоматика працюють окремо й тут не керуються.";

/** UI-13 EngineChip: `level` ok/warn/bad (D-28); текст — з API, запасний — за `connected/mode`. */
export class EngineChip extends Component {
    static template = "td_energy_control.EngineChip";
    static props = { engine: { type: Object } };

    get level() {
        const engine = this.props.engine;
        if (engine.level) {
            return engine.level;
        }
        if (!engine.connected) {
            return "bad";
        }
        return engine.mode === "auto" ? "ok" : "warn";
    }

    get text() {
        const engine = this.props.engine;
        if (engine.label) {
            return engine.label;
        }
        if (!engine.connected) {
            return "Збирач не на зв'язку";
        }
        if (engine.mode !== "auto") {
            const reason = engine.reason ? `: ${engine.reason}` : "";
            return `Автоматику призупинено${reason}`;
        }
        return "Контролер ГРЩ і збирач на зв'язку";
    }

    get pillClass() {
        const cls = { ok: "live", warn: "partial", bad: "stale" }[this.level] || "stale";
        return `o_td_en_pill o_td_en_pill--${cls} o_td_en_engine_chip o_td_en_engine_chip--${this.level}`;
    }
}

export class Control extends Component {
    static template = "td_energy_control.Control";
    static components = { EngineChip, ScenarioGrid, ShedList, CommandTiles, ScheduleTimeline, Journal };
    static props = ["*"];

    setup() {
        this.actions = useEnergyActions();
        this.dialog = useService("dialog");
        this.infoText = INFO_TEXT;
        this.state = useState({
            data: null,
            failed: null,
            busy: false,
            reorder: null, // null или список id приоритетов в локальном порядке
            extra: [], // записи журнала, подгруженные «Показати більше»
            extraMore: null,
            loadingMore: false,
        });
        this.timer = null;
        this.lastLoad = 0;

        useControlBus(() => this.load(), ENGINE_KINDS);
        onWillStart(() => this.load());
        onMounted(() => {
            const seconds = (this.state.data && this.state.data.meta && this.state.data.meta.refresh_s) || 30;
            this.timer = browser.setInterval(() => {
                if (Date.now() - this.lastLoad >= seconds * 1000 - 1000) {
                    this.load();
                }
            }, seconds * 1000);
        });
        onWillUnmount(() => browser.clearInterval(this.timer));
    }

    get ctx() {
        const { orm, notify, fail } = this.actions;
        return { orm, dialog: this.dialog, notify, fail };
    }

    get meta() {
        return this.state.data.meta || {};
    }

    // ------------------------------------------------------------------ данные

    async load() {
        try {
            const data = await this.actions.orm.call(MODEL, "get_control", []);
            this.lastLoad = Date.now();
            this.state.failed = null;
            this.state.data = data;
        } catch (error) {
            if (!this.state.data) {
                this.state.failed = errorMessage(error);
            } else {
                this.actions.fail(error);
            }
        }
    }

    get journalItems() {
        const data = this.state.data;
        const seen = new Set();
        const items = [];
        for (const item of [...(data.journal || []), ...this.state.extra]) {
            if (!seen.has(item.id)) {
                seen.add(item.id);
                items.push(item);
            }
        }
        return items;
    }

    get journalMore() {
        return this.state.extraMore !== null ? this.state.extraMore : !!this.state.data.journal_more;
    }

    async loadMore() {
        const items = this.journalItems;
        if (!items.length || this.state.loadingMore) {
            return;
        }
        this.state.loadingMore = true;
        try {
            const res = await this.actions.orm.call(MODEL, "get_journal", [], {
                limit: JOURNAL_STEP,
                before_id: items[items.length - 1].id,
            });
            this.state.extra = [...this.state.extra, ...(res.items || [])];
            this.state.extraMore = !!res.more;
        } catch (error) {
            this.actions.fail(error);
        } finally {
            this.state.loadingMore = false;
        }
    }

    // ------------------------------------------------------------------ команды

    /** Общий путь: prepare → диалог → перечитать данные. Возвращает итог `{action_id, state, ok}` или null. */
    async run(kind, params = null) {
        if (this.state.busy) {
            return null;
        }
        this.state.busy = true;
        const release = () => (this.state.busy = false);
        let result = null;
        try {
            result = await runCommand(this.ctx, kind, params, { onOpen: release });
        } finally {
            release();
        }
        await this.load();
        return result;
    }

    runTile(cmd) {
        return this.run(cmd.code);
    }

    toggleScenario(item) {
        return this.run("scenario_toggle", { scenario: item.code, enabled: !item.enabled });
    }

    editParams(item) {
        this.dialog.add(ParamsDialog, {
            scenario: item,
            onSave: (params) => this.run("scenario_params", { scenario: item.code, params }),
        });
    }

    // ------------------------------------------------------------------ порядок сброса (D-24)

    startReorder() {
        this.state.reorder = (this.state.data.shed.items || []).map((item) => item.id);
    }

    moveShed(index, delta) {
        const order = [...this.state.reorder];
        const target = index + delta;
        if (target < 0 || target >= order.length) {
            return;
        }
        [order[index], order[target]] = [order[target], order[index]];
        this.state.reorder = order;
    }

    cancelReorder() {
        this.state.reorder = null;
    }

    async saveReorder() {
        const result = await this.run("shed_reorder", { order: this.state.reorder });
        if (result && result.ok) {
            this.state.reorder = null;
        }
    }

    // ------------------------------------------------------------------ журнал и второе подтверждение

    canSecond(item) {
        const pending = (this.state.data.pending || []).find((p) => p.id === item.id);
        return !!pending && !!pending.can_confirm_second;
    }

    async confirmSecond(id, title) {
        if (this.state.busy) {
            return;
        }
        this.state.busy = true;
        const release = () => (this.state.busy = false);
        try {
            await runSecond(this.ctx, id, title, { onOpen: release });
        } finally {
            release();
        }
        await this.load();
    }

    async undo(item) {
        if (this.state.busy) {
            return;
        }
        this.state.busy = true;
        const release = () => (this.state.busy = false);
        try {
            await runUndo(this.ctx, item.id, { onOpen: release });
        } finally {
            release();
        }
        await this.load();
    }

    openRef(ref) {
        return this.actions.openRecord(ref.model, ref.id);
    }

    openAll() {
        return this.actions.openXml("td_energy_control.action_td_energy_action");
    }
}

registry.category("actions").add("td_energy_control.control", Control);
