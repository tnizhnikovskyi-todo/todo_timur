// Верхняя панель на компьютере (W-22, I-09): на ширине от 900 px панель в одну строку; когда кнопки не помещаются, самые редкие
// переезжают в меню «Ще» (сами кнопки — те же узлы с теми же обработчиками, ничего не теряется). Порядок переноса — MOVABLE: первая уходит первой.
// До 900 px панель переносится на несколько строк, на телефоне (≤ 768 px) работает меню «☰» (mobile.js) — здесь ничего не делаем.
export const MOVABLE = ["lb-btn", "pa-btn", "hist-btn", "var-btn", "wiz-btn", "tray-btn", "cm-btn", "odoo-new", "odoo-refresh", "plan-btn", "tours-btn"];
export const WIDE_Q = "(min-width: 900px)";

export function createTopFit({ root }) {
  const top = root.querySelector(".topbar"), wrap = root.querySelector("#more-wrap"), btn = root.querySelector("#more-btn"), list = root.querySelector("#more-list");
  const mq = globalThis.matchMedia?.(WIDE_Q);
  const items = MOVABLE.map((id) => root.querySelector(`#${id}`)).filter(Boolean).map((el) => { const ph = document.createComment(el.id); el.before(ph); return { el, ph }; });
  let raf = 0;
  const open = (on) => { list.hidden = !on; btn.setAttribute("aria-expanded", String(on)); };
  const over = () => top.scrollWidth > top.clientWidth + 1;
  const mo = new MutationObserver(() => schedule());
  const watch = () => mo.observe(top, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ["hidden"] });
  function fit() {
    raf = 0;
    mo.disconnect();
    const focus = document.activeElement;
    for (const { el, ph } of items) if (el.parentNode === list) ph.after(el);
    wrap.hidden = false; // меню входит в расчёт ширины
    let moved = 0;
    if (mq?.matches) {
      for (const { el } of items) {
        if (!over()) break;
        if (el.hidden) continue; // скрытая сейчас кнопка (например, только для Odoo) места не занимает
        list.append(el); moved++;
      }
    }
    wrap.hidden = moved === 0;
    if (!moved) open(false);
    mo.takeRecords();
    if (focus && focus !== document.activeElement && document.contains(focus)) focus.focus({ preventScroll: true });
    watch();
  }
  function schedule() { if (!raf) raf = requestAnimationFrame(fit); }
  btn.onclick = (ev) => { ev.stopPropagation(); open(list.hidden); };
  list.addEventListener("click", () => open(false)); // выбор пункта закрывает меню (обработчик самой кнопки уже сработал)
  document.addEventListener("click", (ev) => { if (!list.hidden && !wrap.contains(ev.target)) open(false); });
  document.addEventListener("keydown", (ev) => { if (ev.key === "Escape" && !list.hidden) { open(false); btn.focus(); } });
  globalThis.addEventListener("resize", schedule);
  mq?.addEventListener("change", schedule);
  fit();
  return { fit, schedule, moved: () => items.filter((it) => it.el.parentNode === list).map((it) => it.el.id) };
}
