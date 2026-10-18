/** @odoo-module **/
// UI-17 ConfirmDialog: prepare → диалог (проверки блокувань, TTL токена) → confirm → прогресс «Надіслано → Виконується →
// Виконано / Не виконано» (опрос get_action каждые 2 с). Хелперы `runCommand/runUndo/runSecond` открывают диалог из
// экрана «Керування», обработчика рекомендаций и панели вузла (ctx = `{orm, dialog, notify, fail}`).

import { Component, onMounted, onWillUnmount, useEffect, useState } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import { Dialog } from "@web/core/dialog/dialog";
import { useChildRef, useService } from "@web/core/utils/hooks";
import { errorMessage } from "@td_energy/common/format";

export const MODEL = "td.energy.control";
export const POLL_MS = 2000;
export const DEFAULT_VERIFY_S = 60;
export const FINAL_STATES = ["done", "failed", "blocked", "expired", "cancelled"];
export const CHECK_TEXT = { ok: "гаразд", fail: "не виконано", unknown: "немає даних" };

const sleep = (ms) => new Promise((resolve) => browser.setTimeout(resolve, ms));

/** Крок прогресу за станом дії: 1 «Надіслано», 2 «Виконується», 3 — завершено. */
export function stepOf(state) {
    if (state === "executing") {
        return 2;
    }
    if (FINAL_STATES.includes(state)) {
        return 3;
    }
    return 1;
}

/** Причина невдачі для рядка «Не виконано: {причина}». */
export function failureText(action) {
    return action.error || action.blocked_reason || action.result_text || action.state_label || "невідома причина";
}

/**
 * Опитування `get_action` до `finished_at`/кінцевого стану, не довше `timeoutMs`.
 * @returns {Promise<object|null>} остання відповідь (null — зупинено)
 */
export async function pollAction(orm, actionId, { onUpdate, isStopped, timeoutMs, intervalMs = POLL_MS }) {
    const started = Date.now();
    while (!isStopped()) {
        const action = await orm.call(MODEL, "get_action", [actionId]);
        if (isStopped()) {
            return null;
        }
        onUpdate(action);
        if (action.finished_at || FINAL_STATES.includes(action.state)) {
            return action;
        }
        if (Date.now() - started >= timeoutMs) {
            return action;
        }
        await sleep(intervalMs);
    }
    return null;
}

export class ConfirmDialog extends Component {
    static template = "td_energy_control.ConfirmDialog";
    static components = { Dialog };
    static props = {
        prepared: { type: Object, optional: true },
        started: { type: Object, optional: true },
        onResult: { type: Function, optional: true },
        verifyTimeoutS: { type: Number, optional: true },
        close: { type: Function },
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.modalRef = useChildRef();
        const prepared = this.props.prepared;
        this.checkText = CHECK_TEXT;
        this.state = useState({
            phase: prepared ? "ask" : "progress", // ask | progress | second | final
            remaining: prepared ? prepared.ttl_s || 0 : 0,
            expired: false,
            busy: false,
            error: null,
            action: null,
            step: 1,
            tracked: false,
            outcome: null, // {ok, text} — итог для phase final/second
        });
        this.actionId = prepared ? prepared.action_id : this.props.started.action_id;
        this.mustCancel = !!prepared; // Esc / «Скасувати» / закриття до confirm → cancel(token)
        this.confirming = false; // захист від подвійного кліку: confirm відправляється один раз
        this.stopped = false;
        this.finished = false;
        this.timer = null;
        this.previousFocus = document.activeElement;

        onMounted(() => {
            const el = this.modalRef.el;
            if (el) {
                el.setAttribute("aria-modal", "true");
                el.setAttribute("aria-label", this.titleText);
            }
            if (prepared) {
                this.timer = browser.setInterval(() => this.tick(), 1000);
            } else {
                this.track(this.props.started);
            }
            this.focusPrimary();
        });
        useEffect(
            () => {
                this.focusPrimary();
            },
            () => [this.state.phase, this.state.expired]
        );
        onWillUnmount(() => this.teardown());
    }

    // ------------------------------------------------------------------ вид

    get titleText() {
        if (this.props.prepared) {
            const title = this.props.prepared.title || "Підтвердити дію";
            return title.endsWith("?") ? title : `${title}?`;
        }
        return this.props.started.title || "Виконання команди";
    }

    get blockedReason() {
        const prepared = this.props.prepared;
        return prepared && prepared.blocked ? prepared.blocked_reason || "Дію заблоковано" : null;
    }

    get canConfirm() {
        const prepared = this.props.prepared;
        return (
            !!prepared &&
            !this.blockedReason &&
            !prepared.disabled_reason &&
            !this.state.expired &&
            !this.state.busy &&
            !this.confirming &&
            this.state.phase === "ask"
        );
    }

    get confirmLabel() {
        const prepared = this.props.prepared;
        return (prepared && prepared.confirm_label) || "Виконати";
    }

    /** Три рядки прогресу; останній — «Виконано» або «Не виконано: {причина}». */
    get steps() {
        const { step, outcome } = this.state;
        const failed = !!outcome && !outcome.ok;
        const cls = (index) => (index < step ? "done" : index === step ? "current" : "todo");
        return [
            { key: "sent", text: "Надіслано", cls: cls(1) },
            { key: "executing", text: "Виконується", cls: failed && step < 2 ? "todo" : cls(2) },
            {
                key: failed ? "failed" : "done",
                text: outcome ? outcome.text : "Виконано",
                cls: outcome ? (failed ? "fail" : "done") : "todo",
            },
        ];
    }

    // ------------------------------------------------------------------ життєвий цикл

    focusPrimary() {
        const root = this.modalRef.el;
        if (!root) {
            return;
        }
        const target =
            root.querySelector(".o_td_en_cd_ok:not([disabled])") ||
            root.querySelector(".o_td_en_cd_close") ||
            root.querySelector(".o_td_en_cd_cancel");
        if (target) {
            target.focus();
        }
    }

    tick() {
        if (this.state.remaining > 0) {
            this.state.remaining -= 1;
        }
        if (this.state.remaining <= 0 && this.state.phase === "ask") {
            this.state.expired = true;
            this.mustCancel = false;
            browser.clearInterval(this.timer);
            this.timer = null;
        }
    }

    teardown() {
        this.stopped = true;
        if (this.timer !== null) {
            browser.clearInterval(this.timer);
            this.timer = null;
        }
        if (this.mustCancel && this.props.prepared) {
            // сервіси компонента після знищення недоступні — беремо глобальні з env
            this.env.services.orm.call(MODEL, "cancel", [this.props.prepared.token]).catch(() => {});
        }
        if (this.actionId && this.state.phase === "progress" && !this.finished) {
            this.detach(); // закрито під час виконання: підсумок покаже тост (D-31)
        }
        const previous = this.previousFocus;
        if (previous && previous.isConnected && previous.focus) {
            previous.focus();
        }
    }

    /** Фоновий облік дії після закриття діалогу: тост «Надіслано», потім «Виконано» / «Не виконано: …». */
    detach() {
        const { orm, notification } = this.env.services;
        const title = this.titleText.replace(/\?$/, "");
        const timeoutMs = ((this.props.verifyTimeoutS || DEFAULT_VERIFY_S) + 30) * 1000;
        notification.add(`Надіслано: ${title}`, { type: "info" });
        pollAction(orm, this.actionId, { onUpdate() {}, isStopped: () => false, timeoutMs })
            .then((action) => {
                if (!action || !(action.finished_at || FINAL_STATES.includes(action.state))) {
                    return;
                }
                if (action.state === "done") {
                    notification.add(`Виконано: ${title}`, { type: "success" });
                } else {
                    notification.add(`Не виконано: ${failureText(action)}`, { type: "danger" });
                }
            })
            .catch(() => {});
    }

    report(result) {
        if (this.props.onResult) {
            this.props.onResult(result);
        }
    }

    // ------------------------------------------------------------------ дії

    async confirm() {
        if (!this.canConfirm) {
            return;
        }
        this.confirming = true;
        this.state.busy = true;
        this.state.error = null;
        this.mustCancel = false;
        let res;
        try {
            res = await this.orm.call(MODEL, "confirm", [this.props.prepared.token]);
        } catch (error) {
            this.confirming = false;
            this.state.busy = false;
            this.state.error = errorMessage(error);
            this.mustCancel = !this.state.expired;
            return;
        }
        this.state.busy = false;
        if (this.timer !== null) {
            browser.clearInterval(this.timer);
            this.timer = null;
        }
        this.actionId = res.action_id || this.actionId;
        if (res.blocked_reason || res.state === "blocked") {
            this.state.phase = "final";
            this.state.outcome = { ok: false, text: `Не виконано: ${res.blocked_reason || res.message || "заблоковано"}` };
            this.notification.add(this.state.outcome.text, { type: "danger" });
            this.report({ action_id: this.actionId, state: "blocked", ok: false });
            return;
        }
        if (res.state === "awaiting_second") {
            this.state.phase = "second";
            this.state.outcome = { ok: true, text: res.message || "Очікуємо друге підтвердження іншим енергетиком." };
            this.report({ action_id: this.actionId, state: "awaiting_second", ok: true });
            return;
        }
        this.state.phase = "progress";
        this.track(res);
    }

    /** Опитування прогресу виконаної дії (`get_action` кожні 2 с, не довше `verify_timeout_s + 30`). */
    async track(initial) {
        this.state.tracked = true;
        this.state.step = stepOf(initial.state);
        const timeoutMs = ((this.props.verifyTimeoutS || DEFAULT_VERIFY_S) + 30) * 1000;
        let action;
        try {
            action = await pollAction(this.orm, this.actionId, {
                isStopped: () => this.stopped,
                timeoutMs,
                onUpdate: (update) => {
                    this.state.action = update;
                    this.state.step = stepOf(update.state);
                },
            });
        } catch (error) {
            if (!this.stopped) {
                this.state.phase = "final";
                this.state.outcome = { ok: false, text: `Не виконано: ${errorMessage(error)}` };
                this.report({ action_id: this.actionId, state: "failed", ok: false });
            }
            return;
        }
        if (!action || this.stopped) {
            return;
        }
        const isFinal = action.finished_at || FINAL_STATES.includes(action.state);
        this.state.phase = "final";
        if (!isFinal) {
            this.state.outcome = { ok: true, text: "Виконується довше, ніж зазвичай. Стан дивіться в журналі." };
            this.report({ action_id: this.actionId, state: action.state, ok: false });
            return;
        }
        this.finished = true;
        const ok = action.state === "done";
        this.state.outcome = ok
            ? { ok: true, text: action.result_text ? `Виконано · ${action.result_text}` : "Виконано" }
            : { ok: false, text: `Не виконано: ${failureText(action)}` };
        const title = this.titleText.replace(/\?$/, "");
        this.notification.add(ok ? `Виконано: ${title}` : this.state.outcome.text, { type: ok ? "success" : "danger" });
        this.report({ action_id: this.actionId, state: action.state, ok });
    }
}

// ------------------------------------------------------------------ відкриття діалогу

/**
 * Виклик `prepareFn()` (prepare/undo) і показ диалога. Промис завершується при закритті диалога:
 * `{action_id, state, ok}` — підсумок або `null` (скасовано / помилка prepare).
 * @param {{dialog, fail}} ctx
 */
export async function openConfirm(ctx, prepareFn, { onOpen, ...options } = {}) {
    let prepared;
    try {
        prepared = await prepareFn();
    } catch (error) {
        if (onOpen) {
            onOpen();
        }
        ctx.fail(error);
        return null;
    }
    if (onOpen) {
        onOpen(); // диалог показан: экран снова доступен (фокус вернётся на элемент-инициатор)
    }
    return showDialog(ctx, { prepared, ...options });
}

function showDialog(ctx, props) {
    return new Promise((resolve) => {
        const box = { result: null };
        ctx.dialog.add(
            ConfirmDialog,
            { ...props, onResult: (result) => (box.result = result) },
            { onClose: () => resolve(box.result) }
        );
    });
}

/** Ручна команда або дія рекомендації: `prepare(kind, params, advice_id)` → диалог. */
export function runCommand(ctx, kind, params = null, { adviceId = null, verifyTimeoutS, onOpen } = {}) {
    const kwargs = adviceId ? { advice_id: adviceId } : {};
    return openConfirm(ctx, () => ctx.orm.call(MODEL, "prepare", [kind, params], kwargs), { verifyTimeoutS, onOpen });
}

/** Скасування виконаної дії: `undo(action_id)` → диалог зворотної дії. */
export function runUndo(ctx, actionId, { verifyTimeoutS, onOpen } = {}) {
    return openConfirm(ctx, () => ctx.orm.call(MODEL, "undo", [actionId]), { verifyTimeoutS, onOpen });
}

/** Друге підтвердження (D-43): `confirm_second(action_id)` → блок прогресу. */
export async function runSecond(ctx, actionId, title, { verifyTimeoutS, onOpen } = {}) {
    let res;
    try {
        res = await ctx.orm.call(MODEL, "confirm_second", [actionId]);
    } catch (error) {
        if (onOpen) {
            onOpen();
        }
        ctx.fail(error);
        return null;
    }
    if (onOpen) {
        onOpen();
    }
    if (res.blocked_reason || res.state === "blocked") {
        ctx.notify(`Не виконано: ${res.blocked_reason || res.message || "заблоковано"}`, "danger");
        return { action_id: actionId, state: "blocked", ok: false };
    }
    return showDialog(ctx, {
        started: { action_id: res.action_id || actionId, state: res.state, title: title || "Виконання команди" },
        verifyTimeoutS,
    });
}
