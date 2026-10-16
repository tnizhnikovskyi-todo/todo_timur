// Туры (W-20, K3; W-24): подсветка элемента и подсказка. Грузится лениво (первый вход, меню «Тури», инструкция, ссылка #tour-<id>).
// Данные туров — core/tours.js (шаги «прочитать» и «действие» с проверкой и «Показати мені»), тексты — i18n/tour.js, учебная копия — core/tourcopy.js.
// T-basic (тур W-20) идёт по-прежнему: шаги, чьих элементов нет на экране, отбрасываются сразу (pickSteps); у остальных туров шаг без элемента пропускается
// с пояснением. Отметки «пройдено»: T-basic — TOUR_KEY (done / skipped), остальные — TOURS_KEY (JSON) в localStorage браузера.
import { pickSteps, TOUR_KEY } from "../core/tour.js";
import { TOURS, tourById, stepsFor, pickSel, readMarks, markTour, needsDesktop, SAMPLE_CSV, SAMPLE_NAME } from "../core/tours.js";
import { beginCopy, cancelCopy, keepCopy, copyRec, copyAlive, copyDenied, COPY_KEY } from "../core/tourcopy.js";
import TOUR_TEXT from "../i18n/tour.js";
import { esc } from "./util.js";

const kv = { get: (k) => { try { return localStorage.getItem(k); } catch (e) { return null; } }, set: (k, v) => { try { localStorage.setItem(k, v); } catch (e) { /* приватный режим: тур покажется снова */ } } };
const rd = () => kv.get(TOUR_KEY), wr = (v) => kv.set(TOUR_KEY, v);
export const tourSeen = () => !!rd();

const qs = (s) => document.querySelector(s);
const rectOk = (el) => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
// элемент, который подсвечивается: кнопка из меню «Ще» показывается кнопкой «Ще»; null — элемента сейчас нет на экране
function target(sel) {
  const el = qs(sel); if (!el) return null;
  if (el.closest("#more-list")) { const b = qs("#more-btn"); return !el.hidden && b && !b.closest("[hidden]") && rectOk(b) ? b : null; }
  return el.closest("[hidden]") || !rectOk(el) ? null : el;
}
const isNarrow = () => !!qs(".app.mobile");
const marksOf = () => ({ ...readMarks(kv), "T-basic": rd() === "done" ? "done" : undefined });
const whoText = (t, tour) => tour.who.map((w) => t(`tour.who.${w}`)).join(", ");
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
async function waitFor(fn, ms) { const t0 = Date.now(); for (;;) { let v = false; try { v = await fn(); } catch (e) { /* ещё не готово */ } if (v) return true; if (Date.now() - t0 > ms) return false; await wait(80); } }

// ---------- список туров (меню «Тури» и инструкция)
export function fillTourList(el, { i18n, start }) {
  i18n.extend(TOUR_TEXT);
  const t = i18n.t, marks = marksOf(), narrow = isNarrow();
  el.innerHTML = `<ul class="tour-list">${TOURS.map((x) => {
    const off = narrow && needsDesktop(x);
    return `<li data-tour-id="${x.id}"><div class="tl-main"><b>${esc(t(`tour.${x.short}.name`))}</b>
      <span class="mut">${esc(t("tour.who", { who: whoText(t, x) }))} · ${esc(t("tour.min", { n: x.min }))}${x.mutates ? ` · ${esc(t("tour.copyTag"))}` : ""}${off ? ` · ${esc(t("tour.desktop"))}` : ""}</span>
      ${marks[x.id] ? `<span class="tl-done" data-done>✓ ${esc(t("tour.doneMark"))}</span>` : ""}</div>
      <button type="button" class="btn btn-secondary" data-start="${x.id}"${off ? " disabled" : ""}>${esc(t("tour.start"))}</button></li>`;
  }).join("")}</ul>`;
  el.querySelectorAll("[data-start]").forEach((b) => b.onclick = () => start(b.dataset.start));
}

// меню «Тури» в верхней панели: всплывающий список под кнопкой (или под «Ще», если кнопка спрятана в меню)
export function toursMenu({ i18n, start, anchor }) {
  i18n.extend(TOUR_TEXT);
  const old = qs("#tours-pop"); if (old) { old.remove(); return; }
  const pop = document.createElement("div"); pop.id = "tours-pop"; pop.className = "o_menu tours-pop"; pop.setAttribute("role", "dialog"); pop.setAttribute("aria-label", i18n.t("tour.menuTitle"));
  pop.innerHTML = `<div class="tp-h">${esc(i18n.t("tour.menuTitle"))}</div><div data-list></div>`;
  document.body.append(pop);
  fillTourList(pop.querySelector("[data-list]"), { i18n, start: (id) => { close(); start(id); } });
  const a = anchor && rectOk(anchor) ? anchor : qs("#more-btn") || anchor, r = a.getBoundingClientRect();
  pop.style.left = "auto"; pop.style.top = `${Math.round(r.bottom + 4)}px`; pop.style.right = `${Math.max(8, Math.round(innerWidth - r.right))}px`;
  function close() { pop.remove(); document.removeEventListener("click", out, true); document.removeEventListener("keydown", esc2, true); }
  const out = (ev) => { if (!pop.contains(ev.target) && !(anchor && anchor.contains(ev.target))) close(); };
  const esc2 = (ev) => { if (ev.key === "Escape") { ev.stopPropagation(); close(); } };
  setTimeout(() => { document.addEventListener("click", out, true); document.addEventListener("keydown", esc2, true); });
}

// ---------- конец тура с учебной копией
function endPanel({ i18n, model, rec, orphan, el: host, done }) {
  const t = i18n.t, el = host || document.createElement("div");
  if (!host) { el.id = "tour"; el.setAttribute("role", "dialog"); el.setAttribute("aria-modal", "true"); document.body.append(el); }
  const name = (model.variants.list().find((v) => v.id === rec.copy) || {}).name || "";
  el.className = "tour-final"; el.innerHTML = `<div class="tour-shade"></div><div class="tour-card tour-end" id="tour-end"><h2>${esc(t("tour.end.title"))}</h2>
    <p>${esc(t(orphan ? "tour.end.orphan" : "tour.end.intro", { name }))}</p>
    <label class="chk"><input type="radio" name="tc-how" value="variant" checked> ${esc(t("tour.end.asVariant"))}</label>
    <label class="chk"><input type="radio" name="tc-how" value="merge"> ${esc(t("tour.end.asMerge"))}</label>
    <div class="tour-act"><button type="button" class="btn btn-secondary" id="tc-cancel">${esc(t("tour.end.cancel"))}</button><span class="sp"></span><button type="button" class="btn btn-primary" id="tc-keep">${esc(t("tour.end.keep"))}</button></div></div>`;
  const card = el.querySelector(".tour-card"); card.style.cssText = "left:50%;top:50%;transform:translate(-50%,-50%);width:min(380px,calc(100vw - 16px))";
  const fin = async (fn) => { el.querySelectorAll("button").forEach((b) => { b.disabled = true; }); try { await fn(); } catch (e) { console.error(e); } el.remove(); done?.(); };
  el.querySelector("#tc-cancel").onclick = () => fin(async () => { await cancelCopy(model, rec); model.notify("ok", "tour.end.cancelled"); });
  el.querySelector("#tc-keep").onclick = () => fin(async () => {
    const how = el.querySelector('input[name="tc-how"]:checked').value, r = await keepCopy(model, rec, how);
    model.notify(r === "merge" ? "ok" : "info", r === "merge" ? "tour.end.keptMerge" : how === "merge" ? "tour.end.mergeNo" : "tour.end.keptVariant");
  });
  el.querySelector("#tc-cancel").focus();
}

// прерванный тур (страница закрыта посреди тура): предложить убрать учебную копию
export function offerCleanup({ i18n, model }) {
  i18n.extend(TOUR_TEXT);
  const rec = copyRec(model); if (!rec || rec.proj !== model.project.id || qs("#tour")) return false;
  if (!copyAlive(model, rec)) { model.pref.write(COPY_KEY, ""); return false; }
  endPanel({ i18n, model, rec, orphan: true });
  return true;
}

// ---------- тур
export function startTour({ root, i18n, model, host = {}, id = "T-basic", onEnd }) {
  i18n.extend(TOUR_TEXT);
  const tour = tourById(id), t = i18n.t;
  if (!tour || qs("#tour")) return null;
  const narrow = isNarrow(), odoo = !!host.odoo;
  if (narrow && needsDesktop(tour)) { model.notify("info", "tour.desktop"); return null; }
  let steps;
  if (tour.legacy) { const by = new Map(tour.steps.map((s) => [s.id, s])); steps = pickSteps((s) => !!target(s)).map((p) => ({ ...by.get(p.id), sel: [p.sel] })); }
  else steps = stepsFor(tour, { narrow, odoo });
  if (!steps.length) return null;
  let rec = null;
  if (tour.mutates) {
    const denied = copyDenied(model); if (denied) { model.notify("bad", denied); return null; }
    rec = beginCopy(model, { tour: id, name: t("tour.copyName", { name: t(`tour.${tour.short}.name`) }) });
    if (!rec) { model.notify("bad", "tour.copyFail"); return null; }
  }
  const mem = { saved0: JSON.stringify(model.saved), ids0: new Set(model.tree.nodes.keys()), done: {}, zone: null };
  const state0 = { edit: model.ui.edit, probs: !!target("#problems") };
  const c = {
    model, mem, t, odoo, narrow, host,
    has: (s) => !!qs(s), vis: (s) => !!target(s), click: (s) => { qs(s)?.click(); },
    type: (s, v) => { const e = qs(s); if (e) { e.value = v; e.dispatchEvent(new Event("input", { bubbles: true })); } },
    sample: () => { const e = qs("#imp-dlg [data-file]"); if (!e) return; const dt = new DataTransfer(); dt.items.add(new File([SAMPLE_CSV], SAMPLE_NAME, { type: "text/csv" })); e.files = dt.files; e.dispatchEvent(new Event("change", { bubbles: true })); },
    closeDlg: () => document.querySelectorAll(".o_modal_bg").forEach((m) => { const b = m.querySelector("[data-close]"); if (b) b.click(); else m.remove(); }),
    openWhere: () => import("./putaway.js").then((m) => m.openPutaway({ model, i18n, tab: "where" })),
  };
  const el = document.createElement("div");
  el.id = "tour"; el.setAttribute("role", "dialog"); el.setAttribute("aria-modal", "true"); el.setAttribute("aria-label", t("tour.title"));
  el.innerHTML = `<div class="tour-shade"></div><div class="tour-hl"></div><div class="tour-card"><div class="tour-n"></div><h2 id="tour-h"></h2><p id="tour-d"></p><p class="tour-note" id="tour-note" hidden></p><p class="tour-st" id="tour-st" role="status" hidden></p>
    <div class="tour-act"><button type="button" class="btn btn-link" id="tour-skip"></button><button type="button" class="btn btn-link" id="tour-pass" hidden></button><span class="sp"></span><button type="button" class="btn btn-secondary" id="tour-back"></button><button type="button" class="btn btn-secondary" id="tour-show" hidden></button><button type="button" class="btn btn-primary" id="tour-next"></button></div></div>`;
  document.body.append(el);
  const q = (s) => el.querySelector(s), hl = q(".tour-hl"), card = q(".tour-card");
  let i = 0, ended = false, ok = false, timer = 0, poll = 0, notes = [], cur = null, busy = false;
  const hist = [];
  const title = (s) => t(`${s.k}.t`);
  const latched = (s) => !!mem.done[s.id];

  function place() {
    const tg = cur && cur.pick ? target(cur.pick) : null, vw = document.documentElement.clientWidth, vh = window.innerHeight, cw = Math.min(cur && cur.kind === "act" ? 400 : 340, vw - 16);
    card.style.width = `${cw}px`;
    if (!tg) { Object.assign(hl.style, { left: "50%", top: "50%", width: "0px", height: "0px" }); const ch = card.offsetHeight; card.style.top = `${Math.max(8, (vh - ch) / 2)}px`; card.style.left = `${Math.max(8, (vw - cw) / 2)}px`; return; }
    const r = tg.getBoundingClientRect(), pad = 4;
    Object.assign(hl.style, { left: `${r.left - pad}px`, top: `${r.top - pad}px`, width: `${r.width + 2 * pad}px`, height: `${r.height + 2 * pad}px` });
    const ch = card.offsetHeight;
    let top = r.bottom + 12;
    if (top + ch > vh - 8) top = r.top - ch - 12; // не помещается снизу — над элементом
    if (top < 8) top = Math.max(8, Math.min(vh - ch - 8, r.bottom - ch - 12)); // огромный элемент (весь план): подсказка внутри него, у нижнего края
    card.style.top = `${top}px`; card.style.left = `${Math.max(8, Math.min(vw - cw - 8, r.left))}px`;
  }
  const paintOk = () => {
    const act = cur.kind === "act", st = q("#tour-st");
    el.classList.toggle("act", act); q("#tour-show").hidden = !act || ok; q("#tour-pass").hidden = !act || ok;
    q("#tour-next").disabled = act && !ok;
    st.textContent = [act ? t(ok ? "tour.ok" : "tour.wait") : "", ...notes].filter(Boolean).join(" "); st.hidden = !st.textContent;
  };
  function setOk(v) { ok = v; if (v) mem.done[cur.id] = true; paintOk(); place(); }
  function tick() {
    if (ended || !cur) return;
    if (cur.kind === "act" && !ok) { let v = false; try { v = !!cur.check(c); } catch (e) { /* модель ещё не готова */ } if (v) { setOk(true); if (!timer) timer = setTimeout(() => { timer = 0; if (!ended && ok) next(); }, 700); } }
    place();
  }
  function show(idx, skipped) {
    clearTimeout(timer); timer = 0;
    i = idx; cur = steps[i]; busy = false;
    if (!cur.dlg) c.closeDlg();
    cur.pick = cur.noEl ? null : pickSel(cur, (s) => !!target(s));
    try { cur.init?.(c); } catch (e) { /* без базовой точки проверка просто не сработает */ }
    notes = skipped || [];
    ok = cur.kind === "act" && (latched(cur) || (() => { try { return !!cur.check(c); } catch (e) { return false; } })());
    if (ok) mem.done[cur.id] = true;
    q("#tour-h").textContent = title(cur); q("#tour-d").textContent = t(`${cur.k}.d`);
    q(".tour-n").textContent = t("tour.step", { i: i + 1, n: steps.length });
    q("#tour-skip").textContent = t("tour.skip"); q("#tour-pass").textContent = t("tour.pass"); q("#tour-show").textContent = t("tour.show"); q("#tour-back").textContent = t("tour.back");
    q("#tour-back").hidden = !hist.length;
    q("#tour-next").textContent = t(i === steps.length - 1 ? "tour.done" : "tour.next");
    const nt = q("#tour-note"); nt.hidden = !(rec && !hist.length); nt.textContent = nt.hidden ? "" : t("tour.copyNote");
    el.dataset.step = cur.id; el.dataset.i = String(i); el.dataset.kind = cur.kind;
    if (cur.pick) qs(cur.pick)?.scrollIntoView?.({ block: "nearest", inline: "nearest" });
    paintOk(); place();
    if (cur.kind === "read") q("#tour-next").focus({ preventScroll: true });
    if (cur.kind === "act" && !ok) q("#tour-show").focus({ preventScroll: true });
  }
  // следующий показываемый шаг начиная с idx: шаг, чьего элемента нет на экране, пропускается с пояснением
  function go(idx, pushFrom) {
    const skipped = [];
    for (; idx < steps.length; idx++) {
      const s = steps[idx];
      if (s.noEl || pickSel(s, (x) => !!target(x))) { if (pushFrom != null) hist.push(pushFrom); show(idx, skipped); return; }
      skipped.push(t("tour.skipped", { title: title(s) }));
    }
    end(true);
  }
  const next = () => { if (ended || busy) return; if (i >= steps.length - 1) { end(true); return; } go(i + 1, i); };
  const back = () => { if (ended || !hist.length) return; show(hist.pop()); };
  const pass = () => { if (i >= steps.length - 1) end(true); else go(i + 1, i); };
  async function showMe() {
    if (busy || ended || cur.kind !== "act") return;
    busy = true; q("#tour-show").disabled = true;
    try { await cur.run(c); } catch (e) { console.error(e); }
    const done = await waitFor(() => cur.check(c), 2500);
    busy = false; q("#tour-show").disabled = false;
    if (ended) return;
    if (done) { setOk(true); clearTimeout(timer); timer = setTimeout(() => { timer = 0; if (!ended) next(); }, 350); }
    else { const st = q("#tour-st"); st.hidden = false; st.textContent = t("tour.showFail"); place(); }
  }
  function cleanup() {
    c.closeDlg();
    if (target("#problems") && !state0.probs) qs("#pr-btn")?.click();
    if (model.ui.edit && !state0.edit) model.setEdit(false);
  }
  function end(done) {
    if (ended) return; ended = true;
    clearTimeout(timer); clearInterval(poll);
    if (tour.legacy) wr(done ? "done" : "skipped"); else if (done) markTour(kv, id, "done");
    removeEventListener("resize", place); document.removeEventListener("keydown", key, true);
    cleanup();
    if (rec) { endPanel({ i18n, model, rec, orphan: false, el, done: () => onEnd?.(done) }); }
    else { el.remove(); onEnd?.(done); }
  }
  function key(ev) {
    if (ev.key === "Escape") end(false);
    else if ((ev.key === "ArrowRight" || ev.key === "ArrowLeft") && (!/INPUT|SELECT|TEXTAREA/.test(document.activeElement?.tagName || ""))) { if (ev.key === "ArrowRight") { if (cur.kind === "read" || ok) next(); } else back(); } // Enter нажимает кнопку, на которой стоит фокус
    else if (ev.key !== "Tab" || cur.kind === "act") return;
    else { const bs = [...el.querySelectorAll("button:not([hidden]):not([disabled])")], a = document.activeElement, k = bs.indexOf(a); ev.preventDefault(); bs[(k + (ev.shiftKey ? bs.length - 1 : 1)) % bs.length].focus(); return; } // на шаге «прочитать» фокус остаётся в подсказке
    ev.preventDefault(); ev.stopPropagation();
  }
  q("#tour-next").onclick = next; q("#tour-back").onclick = back; q("#tour-skip").onclick = () => end(false); q("#tour-pass").onclick = pass; q("#tour-show").onclick = showMe;
  document.addEventListener("keydown", key, true); addEventListener("resize", place);
  poll = setInterval(tick, 250);
  go(0, null);
  return { end, get steps() { return steps; }, get rec() { return rec; }, refresh: () => show(i) };
}
