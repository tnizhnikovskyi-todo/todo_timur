// Карточка места (W-17, H4): то, что боковая панель показывает о выбранном месте сверх остатков и заполненности — категория хранения,
// правила размещения, ведущие сюда, ёмкость, движения за окно, возраст запаса и ссылка «Відкрити в Odoo». Данные — model.place(code) (core/stock.js).
import { esc } from "./util.js";

export function cardHtml({ card, i18n, url }) {
  if (!card) return "";
  const t = (k, p) => esc(i18n.t(k, p)), mut = (s) => `<span class="mut">${esc(s)}</span>`;
  const rows = [];
  rows.push(`<tr><th>${t("card.category")}</th><td data-card="category">${card.category ? `${esc(card.category.name)}${card.category.maxWeight ? ` · ${t("card.maxWeight", { n: i18n.int(card.category.maxWeight) })}` : ""}` : mut(i18n.t("card.none"))}</td></tr>`);
  rows.push(`<tr><th>${t("card.capacity")}</th><td data-card="capacity">${card.capacity ? `${esc(i18n.int(card.capacity))} ${t(card.kind === "pallet_cell" ? "card.unitPkg" : "card.unitQty")}${card.fill != null ? ` · ${esc(i18n.pct(card.fill))}` : ""}` : mut(i18n.t("card.none"))}</td></tr>`);
  if (card.orderpoint) rows.push(`<tr><th>${t("card.minmax")}</th><td data-card="minmax">${t("side.minmax", { min: card.orderpoint.min, max: card.orderpoint.max })}</td></tr>`);
  if (card.age != null) rows.push(`<tr><th>${t("card.age")}</th><td data-card="age">${t("card.days", { n: card.age })}${card.moves && card.moves.demo ? ` <span class="badge">${t("heat.demoShort")}</span>` : ""}</td></tr>`);
  if (card.moves) rows.push(`<tr><th>${t("card.moves")}</th><td data-card="moves">${t("card.movesVal", { n: card.moves.n, days: card.moves.days || "—" })}${card.moves.qty ? ` · ${esc(i18n.int(card.moves.qty))}` : ""}${card.moves.demo ? ` <span class="badge">${t("heat.demoShort")}</span>` : ""}</td></tr>`);
  const rules = card.rules.length
    ? `<ul class="o_rules" data-card="rules">${card.rules.map((r) => `<li>${esc(r.productName || r.category || i18n.t("card.ruleAny"))}${r.storageCategory ? ` · ${esc(r.storageCategory)}` : ""}${r.from ? ` <span class="mut">← ${esc(r.from)}</span>` : ""}${r.direct ? "" : ` <span class="mut">(${t("card.ruleCat")})</span>`}</li>`).join("")}</ul>`
    : `<p class="mut" data-card="rules">${t("card.noRules")}</p>`;
  return `<div class="sec">${t("card.title")}</div><table class="o_card"><tbody>${rows.join("")}</tbody></table>
    <div class="sec">${t("card.rules")}</div>${rules}
    ${url ? `<div class="acts"><a class="btn btn-secondary" data-odoo-link href="${esc(url)}" target="_blank" rel="noopener">${t("card.openOdoo")}</a></div>` : ""}`;
}
