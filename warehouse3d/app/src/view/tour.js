// Тур для новичков (W-20, K3): подсветка элемента и подсказка, «Далі / Назад / Пропустити». Грузится лениво (первый вход или кнопка в инструкции).
// Шаги — core/tour.js (невидимые сейчас элементы пропускаются), тексты — i18n/tour.js. Отметка «пройден» — localStorage браузера.
import { pickSteps, TOUR_KEY } from "../core/tour.js";
import TOUR_TEXT from "../i18n/tour.js";

const rd = () => { try { return localStorage.getItem(TOUR_KEY); } catch (e) { return null; } };
const wr = (v) => { try { localStorage.setItem(TOUR_KEY, v); } catch (e) { /* приватный режим: тур покажется снова */ } };
export const tourSeen = () => !!rd();

const visible = (root, sel) => { const el = root.querySelector(sel); if (!el || el.closest("[hidden]")) return false; const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; };

export function startTour({ root, i18n, onEnd }) {
  i18n.extend(TOUR_TEXT);
  const t = i18n.t, steps = pickSteps((s) => visible(root, s));
  if (!steps.length) return null;
  const el = document.createElement("div");
  el.id = "tour"; el.setAttribute("role", "dialog"); el.setAttribute("aria-modal", "true"); el.setAttribute("aria-label", t("tour.title"));
  el.innerHTML = `<div class="tour-shade"></div><div class="tour-hl"></div><div class="tour-card"><div class="tour-n"></div><h2 id="tour-h"></h2><p id="tour-d"></p>
    <div class="tour-act"><button type="button" class="btn btn-link" id="tour-skip"></button><span class="sp"></span><button type="button" class="btn btn-secondary" id="tour-back"></button><button type="button" class="btn btn-primary" id="tour-next"></button></div></div>`;
  document.body.append(el);
  const q = (s) => el.querySelector(s), hl = q(".tour-hl"), card = q(".tour-card");
  let i = 0, ended = false;
  function place() {
    const target = root.querySelector(steps[i].sel); if (!target) return;
    const r = target.getBoundingClientRect(), vw = document.documentElement.clientWidth, vh = window.innerHeight, pad = 4;
    Object.assign(hl.style, { left: `${r.left - pad}px`, top: `${r.top - pad}px`, width: `${r.width + 2 * pad}px`, height: `${r.height + 2 * pad}px` });
    const cw = Math.min(340, vw - 16); card.style.width = `${cw}px`;
    const ch = card.offsetHeight;
    let top = r.bottom + 12;
    if (top + ch > vh - 8) top = r.top - ch - 12; // не помещается снизу — над элементом
    if (top < 8) top = Math.max(8, Math.min(vh - ch - 8, r.bottom - ch - 12)); // огромный элемент (весь план): подсказка внутри него, у нижнего края
    card.style.top = `${top}px`; card.style.left = `${Math.max(8, Math.min(vw - cw - 8, r.left))}px`;
  }
  function show() {
    const s = steps[i], target = root.querySelector(s.sel);
    target?.scrollIntoView?.({ block: "nearest", inline: "nearest" });
    q("#tour-h").textContent = t(`tour.${s.id}.t`); q("#tour-d").textContent = t(`tour.${s.id}.d`);
    q(".tour-n").textContent = t("tour.step", { i: i + 1, n: steps.length });
    q("#tour-skip").textContent = t("tour.skip"); q("#tour-back").textContent = t("tour.back"); q("#tour-back").hidden = i === 0;
    q("#tour-next").textContent = t(i === steps.length - 1 ? "tour.done" : "tour.next");
    el.dataset.step = s.id; el.dataset.i = String(i);
    place(); q("#tour-next").focus({ preventScroll: true });
  }
  function end(done) {
    if (ended) return; ended = true; wr(done ? "done" : "skipped");
    removeEventListener("resize", place); document.removeEventListener("keydown", key, true); el.remove(); onEnd?.(done);
  }
  const next = () => { if (i >= steps.length - 1) end(true); else { i++; show(); } };
  const back = () => { if (i > 0) { i--; show(); } };
  function key(ev) {
    if (ev.key === "Escape") end(false);
    else if (ev.key === "ArrowRight") next(); // Enter нажимает кнопку, на которой стоит фокус
    else if (ev.key === "ArrowLeft") back();
    else if (ev.key !== "Tab") return;
    else { const bs = [...el.querySelectorAll("button:not([hidden])")], a = document.activeElement, k = bs.indexOf(a); ev.preventDefault(); bs[(k + (ev.shiftKey ? bs.length - 1 : 1)) % bs.length].focus(); return; } // фокус остаётся в подсказке
    ev.preventDefault(); ev.stopPropagation();
  }
  q("#tour-next").onclick = next; q("#tour-back").onclick = back; q("#tour-skip").onclick = () => end(false);
  document.addEventListener("keydown", key, true); addEventListener("resize", place);
  show();
  return { end, get steps() { return steps; }, refresh: show };
}
