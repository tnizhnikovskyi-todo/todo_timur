// Тепловые карты (W-17, H2): палитры показателей и легенда над планом. Расчёт показателей — core/metrics.js; здесь только цвета и разметка.
// Цвета одинаковы в 2D (fill элемента) и в 3D (атрибут экземпляра, plan3d.js); от темы не зависят — читаются на светлом и тёмном фоне.
import { esc } from "./util.js";

const NONE = "#8f969e";
export const PALETTE = {
  fill: { f0: "#dde3ea", f25: "#a8cfe8", f50: "#6aaede", f75: "#2f82c4", f100: "#16508f", none: NONE },
  low: { out: "#d44c59", low: "#e99d00", ok: "#28a745", none: NONE },
  empty: { empty: "#e8b923", used: "#8c9bab" },
  abc: { A: "#d44c59", B: "#e99d00", C: "#28a745", none: NONE },
  age: { d30: "#28a745", d90: "#9bc53d", d180: "#e8c11a", dmax: "#d44c59", d365: "#e98a15", none: NONE },
};
export const heatColor = (mode, key) => (PALETTE[mode] && PALETTE[mode][key]) || NONE;

const sw = (bg) => `<i class="sw" style="${bg}"></i>`;
const STATUS = [["--ok", "legend.ok"], ["--warn", "legend.warn"], ["--bad", "legend.bad"], ["--idle", "legend.idle", 1], ["--new", "legend.new"], ["--pend", "legend.pend"]];

// Разметка легенды: status — прежняя (цвета тем), иначе ключи показателя с числом мест и пометки новое / не сохранено; note — пояснения («демо», нет данных)
export function legendHtml({ mode, keys, counts, t, demo, hasData, days }) {
  const item = (bg, text, n) => `<span>${sw(bg)}<em>${esc(text)}${n != null ? ` <b class="n">${n}</b>` : ""}</em></span>`;
  const st = (id) => STATUS.filter((x) => id.includes(x[0])).map(([v, k, border]) => item(border ? `border:1.5px solid var(${v})` : `background:var(${v})`, t(k)));
  if (mode === "status") return STATUS.map(([v, k, border]) => item(border ? `border:1.5px solid var(${v})` : `background:var(${v})`, t(k))).join("");
  let h = keys.map((k) => item(`background:${heatColor(mode, k)}`, t(`heat.${mode}.${k}`), counts[k] || 0)).join("") + st(["--new", "--pend"]).join("");
  const notes = [];
  if (mode === "abc" && days) notes.push(t("heat.days", { n: days }));
  if (demo && (mode === "abc" || mode === "age")) notes.push(t("heat.demo"));
  if (!hasData) notes.push(t("heat.noData"));
  if (notes.length) h += `<span class="note mut" data-heat-note>${esc(notes.join(" · "))}</span>`;
  return h;
}
