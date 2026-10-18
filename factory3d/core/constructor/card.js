// Картка місця (F06-03) й мобільний режим комірника (F06-04) — слайс S3. Клік по комірці: залишки (товар, кількість, резерв, партія, вік),
// категорія, ємність і заповнення, min/max, правила розміщення, рух за 90 днів, «Відкрити в Odoo». На ПК — блок правої панелі, на телефоні
// (≤ 768 px) — картка на весь екран; розмітку мобільного режиму й підказку при наведенні (F06-05) дає s3_chrome.js.
import "./s3_chrome.js";
import { cellsOf } from "./cells.js";
import { can, registries } from "./registry.js";
import { E, S, layerOf } from "./state.js";
import { loadDetail, stockOf } from "./stock_state.js";
import { libraryState } from "./library.js";
import { typeOf } from "./types_data.js";
import { $, fmt, h } from "./util.js";

const pct = (v) => (v == null ? "—" : Math.round(v * 100) + " %");
const day = (iso) => (iso ? String(iso).slice(0, 10) : "—");

/** DOM картки комірки: геометричні дані одразу, залишки — після завантаження (перемальовується на місці). */
export function cardNode(slot, cell) {
    const root = h("div", { class: "s3-card", id: "s3Card", "data-code": cell.code });
    const draw = () => {
        const e = stockOf(cell.code);
        const d = (e && e.detail) || null;
        const ly = layerOf(slot.layer_id);
        const type = typeOf(slot.type_id, libraryState());
        const fill = e ? e.fill : null;
        root.replaceChildren(
            h("div", { class: "frow wrap" }, h("h3", { style: { margin: 0, flex: "1" } }, cell.code), h("span", { class: "tag" }, type ? type.name : slot.template), ly ? h("span", { class: "tag" }, ly.name) : null),
            h(
                "div",
                { class: "kv" },
                h("span", null, "Місць"),
                h("span", null, String(cell.capacity ?? "—")),
                h("span", null, "Макс. навантаження"),
                h("span", null, cell.max_load_kg ? `${fmt(cell.max_load_kg, 0)} кг` : "—"),
                h("span", null, "Категорія"),
                h("span", null, (d && d.category) || slot.storage_category_name || "—"),
                e ? h("span", null, "Запас / резерв") : null,
                e ? h("span", null, `${e.qty ?? 0} / ${e.reserved ?? 0}`) : null,
                e && (e.min != null || e.max != null) ? h("span", null, "Min / max") : null,
                e && (e.min != null || e.max != null) ? h("span", null, `${e.min ?? "—"} / ${e.max ?? "—"}`) : null,
                e && e.age_days != null && e.qty ? h("span", null, "Вік запасу") : null,
                e && e.age_days != null && e.qty ? h("span", null, `${e.age_days} дн.`) : null
            ),
            fill != null ? h("div", null, h("div", { class: "small" }, `Заповненість: ${pct(fill)}`), h("div", { class: "s3-bar" }, h("i", { style: { width: Math.min(100, Math.round(fill * 100)) + "%" } }))) : null,
            !e && can("stock") ? h("div", { class: "small muted" }, S.stock ? "Нова комірка: даних Odoo ще немає." : "Залишки не завантажено (оберіть «Показник» чи «Оновити дані»).") : null,
            e && S.stock && S.stock.demo ? h("div", { class: "small" }, h("span", { class: "tag s3-demo" }, "демо"), " значення синтетичні") : null,
            d && d.rows && d.rows.length
                ? h("div", null, h("h4", { class: "small", style: { margin: "6px 0 2px" } }, "Залишки"), h("table", null, h("thead", null, h("tr", null, ["Товар", "К-сть", "Резерв", "Партія", "Вік"].map((t) => h("th", null, t)))), h("tbody", null, d.rows.map((r) => h("tr", null, h("td", null, r.product || r.ref || "—"), h("td", null, String(r.qty ?? "")), h("td", null, String(r.reserved ?? "")), h("td", null, r.lot || "—"), h("td", null, r.age_days != null ? r.age_days + " дн." : day(r.in_date)))))))
                : null,
            d && d.rules && d.rules.length ? h("div", null, h("h4", { class: "small", style: { margin: "6px 0 2px" } }, "Правила розміщення"), h("ul", { class: "small", style: { margin: 0, paddingLeft: "16px" } }, d.rules.map((r) => h("li", null, typeof r === "string" ? r : r.label || r.name)))) : null,
            d && d.moves && d.moves.length ? h("div", null, h("h4", { class: "small", style: { margin: "6px 0 2px" } }, `Рух за ${(S.stock && S.stock.days) || 90} днів`), h("table", null, h("tbody", null, d.moves.slice(0, 10).map((m) => h("tr", null, h("td", null, day(m.date)), h("td", null, m.product || ""), h("td", null, String(m.qty ?? "")), h("td", { class: "small muted" }, [m.from, m.to].filter(Boolean).join(" → "))))))) : null,
            h(
                "div",
                { class: "frow wrap", style: { marginTop: "6px" } },
                d && d.location_id && registries.dialogs.has("record") ? h("button", { class: "fbtn sm", type: "button", id: "btnOpenOdoo", onclick: () => E.openRecord("stock.location", d.location_id) }, "Відкрити в Odoo") : null,
                h("button", { class: "fbtn sm", type: "button", id: "btnCardLabel", onclick: () => E.runDialog("labels", { spec: { scope: "row", rowId: slot.id } }) }, "Етикетка…")
            )
        );
    };
    draw();
    if (can("stock")) {
        loadDetail(cell.code).then(() => {
            if (root.isConnected || $("#s3CardOv:not([hidden])")) {
                draw();
            }
        });
    }
    return root;
}

/** Права панель: картка вибраної комірки (на ПК); на телефоні картка відкривається на весь екран з `cellPicked`. */
function renderCardBlock(root, { rec }) {
    if (!rec || !S.sel || S.sel.kind !== "slot" || !S.selCell) {
        return;
    }
    const cell = cellsOf(rec).find((c) => c.code === S.selCell);
    if (!cell) {
        return;
    }
    root.append(h("div", { class: "sec", id: "cardBlock" }, h("h3", null, "Картка місця"), cardNode(rec, cell)));
}
registries.panels.add("right:card", { area: "right", render: renderCardBlock }, { sequence: 20, force: true });

/** Клік чи пошук виділив комірку: на телефоні відкриває картку на весь екран. */
export function cellPicked(slotId, code) {
    if (!E.isMobile?.()) {
        E.renderRight?.();
        return;
    }
    const slot = S.sIdx.get(slotId);
    const cell = slot && cellsOf(slot).find((c) => c.code === code);
    if (cell) {
        E.showCard(cardNode(slot, cell), cell.code);
    }
}

Object.assign(E, { cellPicked, cardNode });
