// Переход по коду места (W-20, K1): поле над планом, подсказки по коду и штрихкоду, Enter (сканер штрихкодов вводит код и Enter),
// горячая клавиша «/» или Ctrl/⌘ + K. Выбор — уровень выше места и выделение (model.find.go), как в поиске «где лежит».
import { esc } from "./util.js";
import { placeEntries, suggestPlaces, resolveEnter } from "../core/goto.js";

export function createGoto({ model, i18n, root, isActive, onGo }) {
  const t = i18n.t, inp = root.querySelector("#go-q"), list = root.querySelector("#go-list"), note = root.querySelector("#go-n");
  let entries = null, sg = { exact: null, items: [] };
  const ents = () => entries || (entries = placeEntries(model.tree.byCode, model.data.locations));
  const sub = (code) => { const q = model.tree.loc(code)?.quants[0]; return q ? (model.data.products[q.product] || {}).name || q.product : ""; };
  const close = () => { list.hidden = true; inp.setAttribute("aria-expanded", "false"); };
  function render() {
    const v = inp.value.trim(); sg = suggestPlaces(ents(), v);
    note.textContent = v && !sg.items.length ? t("go.none") : "";
    list.hidden = !sg.items.length; inp.setAttribute("aria-expanded", String(sg.items.length > 0));
    list.innerHTML = sg.items.map((c) => `<li><button type="button" data-go="${esc(c)}"><span class="t">${esc(c)}</span><span class="m">${esc(sub(c))}</span></button></li>`).join("");
    list.querySelectorAll("[data-go]").forEach((b) => b.onclick = () => go(b.dataset.go));
  }
  function go(code) {
    if (!model.find.go(code)) { note.textContent = t("go.none"); return; }
    inp.value = code; close(); note.textContent = ""; onGo?.(code);
  }
  inp.oninput = render;
  inp.onfocus = () => { if (inp.value.trim()) render(); };
  inp.onkeydown = (ev) => {
    if (ev.key === "Enter") { ev.preventDefault(); render(); const c = resolveEnter(sg); if (c) go(c); else if (sg.items.length) note.textContent = t("go.many", { n: sg.items.length }); }
    else if (ev.key === "Escape") { if (!list.hidden) close(); else { inp.value = ""; note.textContent = ""; inp.blur(); } ev.stopPropagation(); }
    else if (ev.key === "ArrowDown") { list.querySelector("button")?.focus(); ev.preventDefault(); }
  };
  list.onkeydown = (ev) => {
    const bs = [...list.querySelectorAll("button")], i = bs.indexOf(document.activeElement);
    if (ev.key === "ArrowDown" && i < bs.length - 1) { bs[i + 1].focus(); ev.preventDefault(); }
    else if (ev.key === "ArrowUp") { (i > 0 ? bs[i - 1] : inp).focus(); ev.preventDefault(); }
    else if (ev.key === "Escape") { close(); inp.focus(); ev.stopPropagation(); }
  };
  document.addEventListener("click", (ev) => { if (!list.hidden && !ev.target.closest("#go-box")) close(); });
  document.addEventListener("keydown", (ev) => {
    if (!isActive() || ev.altKey) return;
    const typing = /INPUT|SELECT|TEXTAREA/.test(document.activeElement?.tagName || "") || document.activeElement?.isContentEditable;
    if ((ev.key === "/" && !ev.ctrlKey && !ev.metaKey && !typing) || ((ev.ctrlKey || ev.metaKey) && ev.code === "KeyK")) { ev.preventDefault(); inp.focus(); inp.select(); }
  });
  return { reset: () => { entries = null; if (!list.hidden) render(); }, focus: () => inp.focus() };
}
