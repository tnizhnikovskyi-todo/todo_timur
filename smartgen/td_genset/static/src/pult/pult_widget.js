/** @odoo-module **/
/**
 * Пульт генератора — OWL-віджет форми td.genset (ТР 2.10, 2.11, А.9). Власник: W3.
 *
 * - Дані: get_pult_state() (формат А.9) при монтуванні, після кожного bus-повідомлення (дебаунс 500 мс)
 *   і після закриття майстра команди; значення приладів null → «немає даних» (AC-06).
 * - Плитки Авто/Пуск/Ручний/Стоп/Тест і кнопки автоматів відкривають майстер підтвердження W2
 *   (action_open_command_wizard, контекст default_command). Без прав або без зв'язку — режим перегляду
 *   з поясненням (AC-24).
 * - Живе оновлення (AC-62): канал "td_genset_<id>" (ir.websocket._build_bus_channel_list), тип
 *   "td_genset.update" → record.load() + get_pult_state; резерв — опитування раз на 30 с, якщо bus
 *   неактивний або websocket не підключений. Відлік стану агрегату і таймера — локально від server_now.
 */
import { Component, onMounted, onWillStart, onWillUnmount, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { formatFloat } from "@web/core/utils/numbers";
import { useService } from "@web/core/utils/hooks";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";

const { DateTime } = luxon;

export const BUS_TYPE = "td_genset.update";
/** Таймінги віджета (об'єкт експортується, щоб тести могли прискорити резервне опитування). */
export const PULT_TIMING = { debounceMs: 500, pollMs: 30000, tickMs: 1000 };

const GAUGE_R = 80;
const GAUGE_CX = 100;
const GAUGE_CY = 100;

function clamp01(value) {
    return Math.min(1, Math.max(0, value));
}

function polar(frac) {
    const angle = Math.PI * (1 - clamp01(frac));
    return [GAUGE_CX + GAUGE_R * Math.cos(angle), GAUGE_CY - GAUGE_R * Math.sin(angle)];
}

/** SVG-дуга півкола приладу від частки f1 до f2 (0 — ліворуч, 1 — праворуч, через верх). */
export function arcPath(f1, f2) {
    const [x1, y1] = polar(f1);
    const [x2, y2] = polar(f2);
    return `M ${x1.toFixed(2)} ${y1.toFixed(2)} A ${GAUGE_R} ${GAUGE_R} 0 0 1 ${x2.toFixed(2)} ${y2.toFixed(2)}`;
}

function fmt(value, digits = 0) {
    if (value === null || value === undefined || Number.isNaN(value)) {
        return "—";
    }
    return formatFloat(value, { digits: [false, digits] });
}

function parseIso(iso) {
    return iso ? DateTime.fromISO(iso, { zone: "utc" }) : null;
}

export class TdGensetPult extends Component {
    static template = "td_genset.PultWidget";
    static props = {
        ...standardWidgetProps,
        compact: { type: Boolean, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.busService = useService("bus_service");
        this.state = useState({ pult: null, refreshCount: 0, now: Date.now(), busy: false });
        this.skewMs = 0;
        this.channel = null;
        this.debounceTimer = null;
        this.pollTimer = null;
        this.tickTimer = null;
        this.onBusUpdate = this.onBusUpdate.bind(this);

        onWillStart(() => this.loadState());
        onMounted(() => {
            if (this.gensetId) {
                this.channel = `td_genset_${this.gensetId}`;
                this.busService.addChannel(this.channel);
                this.busService.subscribe(BUS_TYPE, this.onBusUpdate);
            }
            this.pollTimer = setInterval(() => this.fallbackPoll(), PULT_TIMING.pollMs);
            this.tickTimer = setInterval(() => (this.state.now = Date.now()), PULT_TIMING.tickMs);
        });
        onWillUnmount(() => {
            if (this.channel) {
                this.busService.unsubscribe(BUS_TYPE, this.onBusUpdate);
                this.busService.deleteChannel(this.channel);
            }
            clearTimeout(this.debounceTimer);
            clearInterval(this.pollTimer);
            clearInterval(this.tickTimer);
        });
    }

    // ------------------------------------------------------------------ дані
    get gensetId() {
        return this.props.record.resId || false;
    }

    get pult() {
        return this.state.pult;
    }

    async loadState() {
        if (!this.gensetId) {
            return;
        }
        const pult = await this.orm.call("td.genset", "get_pult_state", [[this.gensetId]]);
        const serverNow = parseIso(pult.server_now);
        this.skewMs = serverNow ? serverNow.toMillis() - Date.now() : 0;
        this.state.pult = pult;
        this.state.now = Date.now();
    }

    async refresh() {
        const record = this.props.record;
        if (!this.gensetId) {
            return;
        }
        if (!record.dirty) {
            await record.load();
        }
        await this.loadState();
        this.state.refreshCount++;
    }

    onBusUpdate(payload) {
        if (!payload || payload.genset_id !== this.gensetId) {
            return;
        }
        clearTimeout(this.debounceTimer);
        this.debounceTimer = setTimeout(() => this.refresh(), PULT_TIMING.debounceMs);
    }

    fallbackPoll() {
        if (!this.gensetId) {
            return;
        }
        if (!this.busService.isActive || this.busService.workerState !== "CONNECTED") {
            this.refresh();
        }
    }

    // ------------------------------------------------------------------ дії
    async openCommand(command) {
        if (this.state.busy || !this.gensetId) {
            return;
        }
        this.state.busy = true;
        try {
            const action = await this.orm.call("td.genset", "action_open_command_wizard", [[this.gensetId]], {
                context: { default_command: command },
            });
            await this.action.doAction(action, { onClose: () => this.refresh() });
        } finally {
            this.state.busy = false;
        }
    }

    onTileClick(tile) {
        if (tile.enabled) {
            this.openCommand(tile.cmd);
        }
    }

    onBreakerClick(breaker) {
        if (breaker.enabled) {
            this.openCommand(breaker.command);
        }
    }

    // ------------------------------------------------------------------ час
    get serverNowMs() {
        return this.state.now + this.skewMs;
    }

    secondsSince(iso) {
        const dt = parseIso(iso);
        return dt ? Math.max(0, Math.floor((this.serverNowMs - dt.toMillis()) / 1000)) : null;
    }

    get ageText() {
        const seconds = this.secondsSince(this.pult?.reading_at);
        if (seconds === null) {
            return _t("немає знімків");
        }
        if (seconds < 60) {
            return _t("%s с тому", seconds);
        }
        if (seconds < 3600) {
            return _t("%s хв тому", Math.floor(seconds / 60));
        }
        return _t("дані на %s", parseIso(this.pult.reading_at).toLocal().toFormat("dd.MM HH:mm"));
    }

    get statusText() {
        const status = this.pult?.status;
        if (!status || !status.label) {
            return this.pult?.has_reading ? _t("невідомо") : _t("немає даних");
        }
        let left = 0;
        if (status.delay) {
            const passed = this.secondsSince(this.pult.reading_at) || 0;
            left = Math.max(0, status.delay - passed);
        }
        return left ? `${status.label} · ${left} с` : status.label;
    }

    get timerInfo() {
        const timer = this.pult?.timer;
        if (!timer || !timer.end) {
            return null;
        }
        const end = parseIso(timer.end).toMillis();
        const start = timer.started_at ? parseIso(timer.started_at).toMillis() : null;
        const left = Math.max(0, Math.floor((end - this.serverNowMs) / 1000));
        const hh = String(Math.floor(left / 3600)).padStart(2, "0");
        const mm = String(Math.floor((left % 3600) / 60)).padStart(2, "0");
        const ss = String(left % 60).padStart(2, "0");
        const progress = start && end > start ? clamp01((this.serverNowMs - start) / (end - start)) : 0;
        return {
            clock: `${hh}:${mm}:${ss}`,
            until: parseIso(timer.end).toLocal().toFormat("HH:mm"),
            by: timer.started_by,
            progress: Math.round(progress * 100),
        };
    }

    get testInfo() {
        const test = this.pult?.test;
        if (!test || !test.end) {
            return null;
        }
        return { until: parseIso(test.end).toLocal().toFormat("HH:mm"), mode: test.mode_label, after: test.after };
    }

    // ------------------------------------------------------------------ плитки, автомати
    get tiles() {
        const buttons = this.pult?.buttons || {};
        const defs = [
            ["auto", _t("Авто"), _t("пуск при зникненні мережі"), "fa-refresh"],
            ["start", _t("Пуск"), _t("запустити двигун"), "fa-play"],
            ["manual", _t("Ручний"), _t("без автопуску"), "fa-hand-paper-o"],
            ["stop", _t("Стоп"), _t("зупинити двигун"), "fa-stop"],
            ["test", _t("Тест"), _t("пуск з навантаженням або без — оберете під час запуску"), "fa-flask"],
        ];
        return defs.map(([cmd, title, sub, icon]) => ({
            cmd,
            title,
            sub,
            icon,
            enabled: Boolean(buttons[cmd]?.enabled) && !this.state.busy,
            active: Boolean(buttons[cmd]?.active),
        }));
    }

    get breakers() {
        const breakers = this.pult?.breakers || {};
        const result = [];
        if (breakers.gen) {
            result.push({
                key: "gen",
                command: "gen_close_open",
                title: _t("Автомат генератора"),
                closed: breakers.gen.closed,
                stateText: breakers.gen.closed ? _t("замкнений") : _t("розімкнений"),
                label: breakers.gen.target_label,
                enabled: breakers.gen.enabled && !this.state.busy,
            });
        }
        if (breakers.mains && breakers.mains.available) {
            result.push({
                key: "mains",
                command: "mains_close_open",
                title: _t("Автомат мережі"),
                closed: breakers.mains.closed,
                stateText: breakers.mains.closed ? _t("замкнений") : _t("розімкнений"),
                label: breakers.mains.target_label,
                enabled: breakers.mains.enabled && !this.state.busy,
            });
        }
        return result;
    }

    get feedNote() {
        const feed = this.pult?.feed;
        if (feed === "genset") {
            return _t("від генератора");
        }
        if (feed === "mains") {
            return _t("від мережі");
        }
        return _t("немає живлення");
    }

    // ------------------------------------------------------------------ прилади і параметри
    get gauges() {
        const g = this.pult?.gauges || {};
        const limits = this.pult?.limits || {};
        const kw = limits.power_kw || 10;
        const powerMax = Math.max(5, Math.ceil((kw * 1.25) / 5) * 5);
        const defs = [
            {
                key: "speed", label: _t("Оберти"), unit: _t("об/хв"), max: 3000, digits: 0,
                zones: [[1400, 1600, "ok"], [2500, 3000, "crit"]],
            },
            {
                key: "active_power", label: _t("Потужність"), unit: "kW", max: powerMax, digits: 1,
                zones: [[0, kw * 0.8, "ok"], [kw * 0.8, kw, "warn"], [kw, powerMax, "crit"]],
            },
            {
                key: "oil_pressure", label: _t("Тиск оливи"), unit: "kPa", max: 800, digits: 0,
                zones: [[0, 100, "warn"], [200, 600, "ok"], [680, 800, "crit"]],
            },
            {
                key: "water_temp", label: _t("Температура ОР"), unit: "°C", max: 120, digits: 0,
                zones: [[0, 40, "low"], [60, 95, "ok"], [98, 120, "crit"]],
            },
        ];
        return defs.map((def) => {
            const value = g[def.key];
            const noData = value === null || value === undefined;
            const frac = noData ? 0 : clamp01(value / def.max);
            const [nx, ny] = polar(frac);
            const needleX = GAUGE_CX + (nx - GAUGE_CX) * 0.78;
            const needleY = GAUGE_CY + (ny - GAUGE_CY) * 0.78;
            return {
                ...def,
                noData,
                display: noData ? "—" : fmt(value, def.digits),
                track: arcPath(0, 1),
                valueArc: noData || frac <= 0 ? null : arcPath(0, frac),
                zones: def.zones
                    .filter(([from, to]) => to > from)
                    .map(([from, to, kind], index) => ({
                        key: `${def.key}_${index}`,
                        kind,
                        path: arcPath(from / def.max, Math.min(to, def.max) / def.max),
                    })),
                needle: { x: needleX.toFixed(2), y: needleY.toFixed(2) },
                maxLabel: fmt(def.max, 0),
            };
        });
    }

    get gaugeNote() {
        const status = this.pult?.status;
        if (!this.pult?.has_reading) {
            return _t("очікуємо перший знімок");
        }
        if (!status || !status.code) {
            return _t("стан невідомий");
        }
        return status.code === "0" ? _t("двигун зупинено") : (status.label || "").toLowerCase();
    }

    get paramGroups() {
        const g = this.pult?.gauges || {};
        const limits = this.pult?.limits || {};
        const amps = limits.current_a ? limits.current_a * 1.2 : 100;
        const tank = limits.tank_l || 100;
        const item = (key, label, value, max, unit, digits, tone = "") => {
            const noData = value === null || value === undefined;
            return {
                key,
                label,
                noData,
                display: noData ? _t("немає даних") : `${fmt(value, digits)}${unit ? " " + unit : ""}`,
                width: noData ? 0 : Math.round(clamp01(Math.abs(value) / max) * 1000) / 10,
                tone,
            };
        };
        const fuelSuffix = this.pult?.fuel_source === "ohm" ? _t("за датчиком") : "";
        return [
            {
                key: "gen",
                title: _t("Генератор"),
                items: [
                    item("ia", "IA", g.current_a, amps, "A", 0),
                    item("ib", "IB", g.current_b, amps, "A", 0),
                    item("ic", "IC", g.current_c, amps, "A", 0),
                    item("guab", "UAB", g.gen_uab, 500, "V", 0),
                    item("gubc", "UBC", g.gen_ubc, 500, "V", 0),
                    item("guca", "UCA", g.gen_uca, 500, "V", 0),
                    item("gf", _t("Частота"), g.gen_freq, 60, "Hz", 1),
                    item("pf", "cos φ", g.power_factor, 1, "", 2, "primary"),
                ],
            },
            {
                key: "engine",
                title: _t("Двигун"),
                items: [
                    item("bat", _t("АКБ"), g.battery_v, 32, "V", 1, "success"),
                    item("dplus", "D+", g.dplus_v, 32, "V", 1, "success"),
                    {
                        ...item("fuel", _t("Паливо"), g.fuel_liters, tank, "L", 0, "success"),
                        hint: fuelSuffix,
                    },
                ],
            },
            {
                key: "mains",
                title: _t("Мережа"),
                items: [
                    item("muab", "UAB", g.mains_uab, 500, "V", 0, "info"),
                    item("mubc", "UBC", g.mains_ubc, 500, "V", 0, "info"),
                    item("muca", "UCA", g.mains_uca, 500, "V", 0, "info"),
                    item("mf", _t("Частота"), g.mains_freq, 60, "Hz", 1, "info"),
                ],
            },
        ];
    }
}

export const tdGensetPult = {
    component: TdGensetPult,
    extractProps: ({ attrs }) => ({ compact: attrs.compact === "1" }),
};

registry.category("view_widgets").add("td_genset_pult", tdGensetPult);
