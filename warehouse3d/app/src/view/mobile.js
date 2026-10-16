// Узкий экран (W-20, D-01, K2): телефон и планшет в портрете (≤ 768 px) — режим просмотра и поиска. Верхняя панель сворачивается в меню (☰),
// боковая панель выдвигается снизу, карточка выбранного места — на весь экран; редактирование выключено в модели (setViewOnly), кнопка даёт подсказку.
import { NARROW_Q } from "./util.js";

export function createMobile({ model, root, onChange }) {
  const app = root.querySelector(".app"), top = root.querySelector(".topbar"), menu = root.querySelector("#menu-btn"), grip = root.querySelector("#sheet-grip"), x = root.querySelector("#sheet-x");
  const mq = globalThis.matchMedia?.(NARROW_Q);
  let sheet = "closed"; // closed — только ручка, open — половина экрана, full — карточка места на весь экран
  const setSheet = (s) => { sheet = s; app.dataset.sheet = s; grip.setAttribute("aria-expanded", String(s !== "closed")); };
  const setMenu = (on) => { top.classList.toggle("open", on); menu.setAttribute("aria-expanded", String(on)); };
  const narrow = () => !!mq?.matches;
  function apply() {
    const n = narrow(); app.classList.toggle("mobile", n); model.setViewOnly(n);
    if (!n) { setMenu(false); setSheet("closed"); }
    onChange?.(n);
  }
  mq?.addEventListener("change", apply);
  menu.onclick = () => setMenu(!top.classList.contains("open"));
  grip.onclick = () => setSheet(sheet === "closed" ? "open" : "closed");
  x.onclick = () => setSheet("closed");
  setSheet("closed"); apply();
  return {
    narrow,
    // пользователь выбрал место (нажатие на плане, поиск, переход по коду): карточка на весь экран; выбор зоны или ряда панель не открывает
    card() { if (narrow() && model.ui.sel) setSheet("full"); },
    closeMenu: () => setMenu(false),
  };
}
