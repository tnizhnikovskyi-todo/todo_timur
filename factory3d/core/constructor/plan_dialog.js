// Діалог плану публікації (F02-01…05, 10) і журнал публікацій з відкатом (F02-08): одне ядро для прототипа й модуля.
//
// План віддає адаптер (`adapter.planPreview()` → {lines, issues, unchanged, first, scopes, copyReminder}); застосовує його
// `adapter.planApply({lines, note, copyAck})`. У модулі «Публікація» відкриває майстер Odoo (API-06), а журнал і відкат —
// цей діалог через `adapter.planLog()` / `planOps()` / `rollback()` (API-18). Діалоги в реєстрі: `plan`, `planLog`.
import { openDialog } from "./dialogs.js";
import { can, registries } from "./registry.js";
import { canManage } from "./roles.js";
import { E, S } from "./state.js";
import { fld, selectEl } from "./fields.js";
import { FLAG_LABEL, KIND_LABEL, OP_LABEL, RES_LABEL, VIEWS, closure, filterLines, flagLabels, lineKey, lineText, planSummary, planTable, selectAll, selectScope, toCsv, viewCounts } from "./plan_core.js";
import { K, fmtDate, fmtInt, h, toast } from "./util.js";

const MAX_ROWS = 300;
const ex = (list, f) => (list.length ? list.slice(0, 3).map(f).join(", ") + (list.length > 3 ? " … " + f(list[list.length - 1]) : "") : "—");
const KIND_CLS = { create: "ok", move: "w", rename: "w", attrs: "w", update: "w", archive: "b" };

function download(name, text, mime) {
    const url = URL.createObjectURL(new Blob([text], { type: mime }));
    const a = h("a", { href: url, download: name });
    document.body.append(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** Діалог плану: види, область, позначки, залежності, файл для імпорту, підтвердження. Повертає проміс, що завершується закриттям. */
export async function openPlanDialog({ adapter, onClose } = {}) {
    adapter ||= E.adapter;
    let plan;
    try {
        plan = await adapter.planPreview();
    } catch (e) {
        toast(e.message || "Не вдалося побудувати план публікації.", "err");
        return undefined;
    }
    const { lines } = plan;
    const st = { view: "all", scope: "" };
    const first = plan.first;
    const blocks = plan.issues.filter((i) => i.severity === "block");
    const warns = plan.issues.filter((i) => i.severity === "warn");
    const note = h("textarea", { placeholder: "Що змінено в цій версії (необов’язково)", "aria-label": "Нотатка" });
    const copyAck = h("input", { type: "checkbox", "aria-label": "Більше не нагадувати" });
    const chips = h("div", { class: "frow", style: { flexWrap: "wrap", gap: "6px" } });
    const table = h("div", { class: "plan-lines", style: { maxHeight: "42vh", overflow: "auto", border: "1px solid var(--line, #ccd)", borderRadius: "6px" } });
    const sum = h("div", { class: "small muted", "data-role": "plan-sum" });
    const summaryBox = h("div", { class: "fcol" });
    let confirmBtn = null;

    const countOf = (test) => lines.filter(test);
    const renderSummary = () => {
        const created = countOf((l) => l.kind === "create" && l.res === "location");
        const eq = countOf((l) => l.kind === "create" && (l.res === "equipment" || l.res === "workcenter"));
        const changed = countOf((l) => ["move", "rename", "attrs", "update"].includes(l.kind) && l.res !== "replenish" && l.res !== "putaway");
        const removed = countOf((l) => l.kind === "archive" && l.res !== "replenish" && l.res !== "putaway");
        const rules = countOf((l) => l.res === "replenish" || l.res === "putaway");
        const row = (n, t, x) => h("div", { class: "sumrow" }, h("div", { class: "n" }, fmtInt(n)), h("div", null, h("div", null, t), h("div", { class: "x" }, x)));
        summaryBox.replaceChildren(
            ...K(
                h("div", { class: "lbl" }, "Буде створено в Odoo" + (first ? " (перша публікація площадки)" : "")),
                row(created.length, "місць зберігання (td_code, штрихкод, місткість, категорія)", ex(created, (l) => l.code)),
                row(eq.length, "одиниць обладнання / робочих центрів", ex(eq, (l) => l.code || l.name)),
                row(changed.length, "змінено", `перенесень ${countOf((l) => l.kind === "move").length} · перейменувань ${countOf((l) => l.kind === "rename").length} · атрибутів і обладнання ${countOf((l) => l.kind === "attrs" || (l.kind === "update" && l.res !== "putaway" && l.res !== "replenish")).length}`),
                row(removed.length, "видалено в чернетці (пропозиції архівації; нічого не видаляється)", `місць ${removed.filter((l) => l.res === "location").length} · обладнання ${removed.filter((l) => l.res !== "location").length}`),
                rules.length ? row(rules.length, "правил поповнення й розміщення", ex(rules, (l) => l.name)) : null
            )
        );
    };

    const renderChips = () => {
        const counts = viewCounts(lines);
        chips.replaceChildren(
            ...VIEWS.filter((v) => v.id === "all" || counts[v.id]).map((v) =>
                h("button", { class: "fbtn sm" + (st.view === v.id ? " primary" : ""), type: "button", "data-view": v.id, "aria-pressed": String(st.view === v.id), onclick: () => { st.view = v.id; refresh(); } }, `${v.label} · ${fmtInt(counts[v.id])}`)
            )
        );
    };

    const lineRow = (l) =>
        h(
            "div",
            { class: "plan-row", "data-code": l.code, style: { display: "grid", gridTemplateColumns: "28px 110px 150px 1fr 1.4fr", gap: "8px", padding: "3px 8px", alignItems: "center", borderBottom: "1px solid var(--line, #e3e6ee)", opacity: l.blocked ? 0.65 : 1 } },
            h("input", {
                type: "checkbox",
                checked: !!l.selected && !l.blocked,
                disabled: !!l.blocked,
                "aria-label": `Застосувати ${l.code}`,
                onchange: (e) => {
                    l.selected = e.target.checked;
                    refreshSummary();
                },
            }),
            h("span", { class: "fbadge " + (KIND_CLS[l.kind] || "") }, KIND_LABEL[l.kind] || l.kind),
            h("span", { class: "small" }, RES_LABEL[l.res] || l.res),
            h("span", { style: { fontFamily: "monospace", overflowWrap: "anywhere" } }, l.code, l.depends_code ? h("span", { class: "small muted" }, ` ← ${l.depends_code}`) : null),
            h("span", { class: "small" }, lineText(l), l.blocked ? h("span", { class: "fbadge b", style: { marginLeft: "6px" } }, l.blocked_reason || "застосувати не можна") : flagLabels(l).map((f) => h("span", { class: "fbadge w", style: { marginLeft: "6px" } }, f)))
        );

    const renderTable = () => {
        const shown = filterLines(lines, st.view, st.scope);
        table.replaceChildren(
            ...K(
                shown.length ? shown.slice(0, MAX_ROWS).map(lineRow) : h("div", { class: "note", style: { margin: "8px" } }, "У цьому виді немає рядків."),
                shown.length > MAX_ROWS ? h("div", { class: "small muted", style: { padding: "6px 8px" } }, `… ще ${shown.length - MAX_ROWS} (фільтр за зоною чи видом звузить список)`) : null
            )
        );
    };

    const refreshSummary = () => {
        const s = planSummary(lines);
        const { added, skipped } = closure(lines);
        sum.textContent =
            `Буде застосовано: ${fmtInt(s.selected)} (створити ${fmtInt(s.create)}, перенести ${fmtInt(s.move)}, перейменувати ${fmtInt(s.rename)}, атрибути ${fmtInt(s.attrs)}, архів ${fmtInt(s.archive)}, правила ${fmtInt(s.rules)})` +
            (added.length ? ` · батьки додано автоматично: ${added.map((l) => l.code).join(", ")}` : "") +
            (skipped.length ? ` · пропущено через заблоковану залежність: ${skipped.map((x) => x.code).join(", ")}` : "") +
            (s.blocked ? ` · застосувати не можна: ${s.blocked}` : "");
        if (confirmBtn) {
            confirmBtn.disabled = !!blocks.length || (!s.selected && !(plan.draftChanges > 0));
        }
    };
    const refresh = () => {
        renderChips();
        renderTable();
        refreshSummary();
    };

    const scopeSel = plan.scopes && plan.scopes.length ? selectEl([["", "Усі зони й ряди"], ...plan.scopes.map((s) => [s.uid, `${s.name} (${s.n})`])], st.scope, (v) => { st.scope = v; refresh(); }, false, "Зона або ряд") : null;
    const toolbar = h(
        "div",
        { class: "frow", style: { gap: "6px", flexWrap: "wrap", alignItems: "center" } },
        scopeSel ? fld("Зона або ряд", scopeSel) : null,
        scopeSel ? h("button", { class: "fbtn sm", type: "button", id: "planScopeOnly", onclick: () => { if (st.scope) { selectScope(lines, st.scope); refresh(); } } }, "Лише обране") : null,
        h("button", { class: "fbtn sm", type: "button", id: "planSelectAll", onclick: () => { selectAll(lines, true); refresh(); } }, "Вибрати все"),
        h("button", { class: "fbtn sm", type: "button", id: "planSelectNone", onclick: () => { selectAll(lines, false); refresh(); } }, "Зняти все")
    );

    renderSummary();
    refresh();
    const nextN = S.versions.reduce((a, v) => Math.max(a, v.n), 0) + 1;
    const imitation = adapter.kind !== "odoo";
    return await new Promise((resolve) => {
        const dlg = openDialog({
            title: "Публікація версії " + nextN,
            cls: "wide",
            body: h(
                "div",
                { class: "fcol" },
                imitation ? h("div", { class: "note" }, "Це імітація: записи в Odoo не створюються. Підтвердження зберігає нову версію макета й оновлює «стан Odoo» прототипу (журнал і відкат — «Журнал публікацій»).") : null,
                summaryBox,
                blocks.length ? h("div", { class: "note lock", "data-role": "plan-blocks" }, `Публікацію заборонено: зауваження зі статусом «Заборона» (${blocks.length}): ${blocks.slice(0, 3).map((i) => i.message).join("; ")}${blocks.length > 3 ? " …" : ""}`) : null,
                warns.length ? h("div", { class: "small muted" }, `Попередження перевірок: ${warns.length}. Публікацію дозволено.`) : null,
                plan.copyReminder ? h("label", { class: "note", style: { display: "flex", gap: "8px", alignItems: "center" } }, copyAck, "Перше застосування: спершу виконайте його на копії бази Odoo. Більше не нагадувати.") : null,
                chips,
                toolbar,
                table,
                sum,
                total0(plan) ? h("div", { class: "note lock" }, "З моменту останньої версії змін немає.") : null,
                fld("Нотатка до версії", note)
            ),
            actions: [
                { label: "Файл для імпорту (CSV)", id: "planCsv", onClick: () => { download("plan_import.csv", toCsv(planTable(lines, { onlyChanged: true })), "text/csv;charset=utf-8"); return false; } },
                { label: "Скасувати" },
                {
                    label: "Підтвердити й опублікувати",
                    cls: "primary",
                    id: "planConfirm",
                    onClick: async () => {
                        try {
                            const res = await adapter.planApply({ lines, note: note.value.trim(), copyAck: copyAck.checked });
                            toast(`Версію ${res.version.n} опубліковано` + (imitation ? " (імітація: записи Odoo не створено)." : "."));
                            if (res.skipped && res.skipped.length) {
                                toast(`Пропущено рядків із заблокованою залежністю: ${res.skipped.length}`, "warn");
                            }
                        } catch (e) {
                            toast(e.message || "Публікація не вдалася.", "err");
                            return false;
                        }
                        return undefined;
                    },
                },
            ],
            onClose: async () => {
                if (onClose) {
                    await onClose();
                }
                resolve();
            },
        });
        confirmBtn = dlg.querySelector("#planConfirm");
        refreshSummary();
    });
}

/** Нема що публікувати: ні рядків, ні правок чернетки (кнопка «Підтвердити» вимкнена). */
const total0 = (plan) => !plan.first && !plan.lines.length && !(plan.draftChanges > 0);

// ---- журнал публікацій і відкат (F02-08) ------------------------------------------------------------------------------------------

const countText = (c) => ["create", "move", "rename", "attrs", "archive"].filter((k) => c[k]).map((k) => `${OP_LABEL[k]} ${c[k]}`).join(" · ") || "без змін";

function fmtVal(v) {
    if (v == null) {
        return "—";
    }
    return typeof v === "object" ? JSON.stringify(v) : String(v);
}

/** Журнал: версії з операціями за видами, «Відкотити» (менеджер), перегляд операцій. */
export async function openJournal({ adapter } = {}) {
    adapter ||= E.adapter;
    const box = h("div", { class: "fcol", "data-role": "journal" });
    const opened = new Set();
    const load = async () => {
        let res;
        try {
            res = await adapter.planLog();
        } catch (e) {
            box.replaceChildren(h("div", { class: "note lock" }, e.message || "Журнал недоступний."));
            return;
        }
        const rows = [];
        for (const v of res.versions) {
            const ops = opened.has(v.n) ? await adapter.planOps(v.id) : null;
            rows.push(
                h(
                    "div",
                    { class: "jrow", "data-version": v.n, style: { padding: "8px 0", borderBottom: "1px solid var(--line, #e3e6ee)" } },
                    h(
                        "div",
                        { class: "frow", style: { gap: "8px", alignItems: "center", flexWrap: "wrap" } },
                        h("b", null, "v" + v.n),
                        h("span", { class: "small muted" }, `${fmtDate(v.published_at)} · ${v.by || "—"}`),
                        v.rolled_back ? h("span", { class: "fbadge b" }, "відкочено") : v.ops ? h("span", { class: "fbadge ok" }, `${v.ops} операцій`) : h("span", { class: "fbadge" }, "без операцій в Odoo"),
                        h("span", { style: { flex: 1 } }),
                        v.ops ? h("button", { class: "fbtn sm", type: "button", "data-act": "ops", onclick: async () => { opened.has(v.n) ? opened.delete(v.n) : opened.add(v.n); await load(); } }, opened.has(v.n) ? "Сховати операції" : "Операції") : null,
                        canManage() && can("rollback") && !v.rolled_back && v.ops
                            ? h("button", { class: "fbtn sm", type: "button", "data-act": "rollback", disabled: !v.can_rollback, title: v.can_rollback ? "Повернути Odoo до стану перед цією публікацією" : v.reason, onclick: () => rollbackAsk(v) }, "Відкотити")
                            : null
                    ),
                    v.note ? h("div", { class: "small" }, v.note) : null,
                    h("div", { class: "small muted" }, countText(v.counts)),
                    !v.can_rollback && !v.rolled_back && v.ops && v.reason ? h("div", { class: "small", style: { color: "var(--warn, #b45309)" } }, "Відкат недоступний: " + v.reason) : null,
                    v.rolled_back ? h("div", { class: "small muted" }, `Відкотив ${v.rolled_back_by || "—"} · ${fmtDate(v.rolled_back_at)}`) : null,
                    ops
                        ? h(
                              "div",
                              { class: "small", style: { maxHeight: "28vh", overflow: "auto", marginTop: "6px", fontFamily: "monospace" } },
                              ops.slice(0, 300).map((o) => h("div", { style: { opacity: o.rolled_back ? 0.55 : 1 } }, `${o.seq}. ${OP_LABEL[o.op] || o.op} · ${RES_LABEL[o.res] || o.res} · ${o.code}`, o.op !== "create" ? h("span", { class: "muted" }, `  ${fmtVal(o.before)} → ${fmtVal(o.after)}`) : null)),
                              ops.length > 300 ? h("div", { class: "muted" }, `… ще ${ops.length - 300}`) : null
                          )
                        : null
                )
            );
        }
        box.replaceChildren(...K(rows.length ? rows : h("div", { class: "note" }, "Публікацій ще не було.")));
    };
    const rollbackAsk = async (v) => {
        const ok = await E.confirmBox({
            title: "Відкотити публікацію v" + v.n + "?",
            text: "В Odoo буде повернуто стан до цієї публікації: створене піде в архів, значення полів повернуться, архівне відновиться. Чернетка не змінюється — наступний план знову запропонує зміни.",
            ok: "Відкотити",
        });
        if (!ok) {
            return;
        }
        try {
            const res = await adapter.rollback(v.id);
            toast(`Відкочено операцій: ${res.reverted}. Чернетка не змінена.`);
            await load();
            if (E.reload) {
                await E.reload();
            }
        } catch (e) {
            toast(e.message || "Відкат не вдався.", "err");
        }
    };
    await load();
    return await new Promise((resolve) =>
        openDialog({ title: "Журнал публікацій", cls: "wide", body: box, actions: [{ label: "Закрити" }], onClose: resolve })
    );
}

registries.dialogs.add("plan", (args, ctx) => openPlanDialog({ adapter: ctx?.adapter, ...(args || {}) }), { force: true });
registries.dialogs.add("planLog", (args, ctx) => openJournal({ adapter: ctx?.adapter }), { force: true });
registries.menu.add("planLog", { area: "more", label: "Журнал публікацій", icon: "hist", capability: "rollback", sequence: 60, run: () => E.runDialog("planLog") }, { sequence: 60, force: true });
