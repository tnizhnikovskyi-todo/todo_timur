// Инструкция пользователя: оглавление и разделы. Тексты — в словарях (help.<раздел>.title / help.<раздел>.html).
// Правило проекта: любое изменение поведения приложения обновляет эти тексты в том же коммите.
import { esc, reducedMotion } from "./util.js";

export const HELP_SECTIONS = ["start", "view", "select", "edit", "move", "multi", "tools", "addr", "copy", "catalog", "templates", "save", "project", "building", "odoo", "keys"];

export function renderHelp(root, { i18n, model, onBack }) {
  const t = (k, p) => i18n.t(k, p), now = model.data.meta?.now || "";
  const date = now ? `${now.slice(8, 10)}.${now.slice(5, 7)}.${now.slice(0, 4)}` : "";
  const sw = (v, border) => `<i class="sw" style="${border ? `border:1.5px solid var(${v})` : `background:var(${v})`}"></i>`;
  const legend = `<div class="hl-legend"><span>${sw("--ok")}${esc(t("legend.ok"))}</span><span>${sw("--warn")}${esc(t("legend.warn"))}</span><span>${sw("--bad")}${esc(t("legend.bad"))}</span><span>${sw("--idle", 1)}${esc(t("legend.idle"))}</span><span>${sw("--new")}${esc(t("legend.new"))}</span><span>${sw("--pend")}${esc(t("legend.pend"))}</span></div>`;
  const body = (id) => t(`help.${id}.html`, { date }) + (id === "view" ? legend : "");
  root.innerHTML = `<div class="o_help"><nav class="toc" aria-label="${esc(t("help.toc"))}"><div class="h">${esc(t("help.toc"))}</div>${HELP_SECTIONS.map((id) => `<a href="#h-${id}" data-toc="${id}">${esc(t(`help.${id}.title`))}</a>`).join("")}</nav>
    <article class="hl-sheet"><h1>${esc(t("help.title"))}</h1>${HELP_SECTIONS.map((id) => `<section id="h-${id}"><h2>${esc(t(`help.${id}.title`))}</h2>${body(id)}</section>`).join("")}
    <p><button class="btn btn-primary" data-back>${esc(t("help.back"))}</button></p></article></div>`;
  root.querySelectorAll("[data-toc]").forEach((a) => a.onclick = (ev) => {
    ev.preventDefault();
    root.querySelectorAll("[data-toc]").forEach((x) => x.removeAttribute("aria-current")); a.setAttribute("aria-current", "true");
    root.querySelector(`#h-${a.dataset.toc}`).scrollIntoView({ behavior: reducedMotion() ? "auto" : "smooth", block: "start" });
  });
  root.querySelector("[data-back]").onclick = onBack;
}
