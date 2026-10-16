// Мини-карта (W-20, K1): схема склада целиком в углу плана (2D и 3D) и рамка текущего вида. Нажатие или перетаскивание по карте сдвигает вид;
// нажатие вне показанного уровня переводит фокус на зону под точкой. Кнопка «▦» сворачивает карту (выбор запоминается). Не закрывает панели: см. place().
import { PANEL_SEL } from "./util.js";

const NS = "http://www.w3.org/2000/svg";

// view() → { x, y, w, h } видимая область в метрах склада или null; panTo(x, y) — центр вида в точку
export function createMinimap({ model, i18n, vp, view, panTo, narrow }) {
  const t = i18n.t, box = document.createElement("div");
  box.id = "minimap"; box.className = "minimap";
  box.innerHTML = `<button type="button" class="mm-tg" id="mm-tg"></button><svg role="img" preserveAspectRatio="xMidYMid meet"><path class="mm-z"/><path class="mm-r"/><rect class="mm-fr"/></svg>`;
  const host = vp.parentElement; host.append(box); // рядом с планом, а не внутри: `#vp svg` / `#vp canvas` остаются единственными (тесты, стили)
  const svg = box.querySelector("svg"), tg = box.querySelector("#mm-tg"), pz = svg.querySelector(".mm-z"), pr = svg.querySelector(".mm-r"), fr = svg.querySelector(".mm-fr");
  let on = model.pref.read("minimap") ? model.pref.read("minimap") === "1" : !narrow(), world = null, down = false;
  const rect = (n) => `M${n.x} ${n.y}h${n.w}v${n.d}h${-n.w}z`;

  // схема: зоны — контуры, ряды и места на полу — заливка; здание — контур
  function build() {
    const tr = model.tree, r = tr.root, b = model.building?.contour || [];
    let x0 = r.x, y0 = r.y, x1 = r.x + r.w, y1 = r.y + r.d, z = "", k = "";
    for (const p of b) { x0 = Math.min(x0, p[0]); y0 = Math.min(y0, p[1]); x1 = Math.max(x1, p[0]); y1 = Math.max(y1, p[1]); }
    for (const n of tr.nodes.values()) {
      if (!(n.w > 0 && n.d > 0)) continue;
      if (n.type === "rack") k += rect(n);
      else if ((n.type === "group" || n.type === "rackset") && n.kids.length && n !== r) z += rect(n);
      else if (n.loc && !n.kids.length && (n.type === "group" || n.type === "bayleaf")) k += rect(n);
    }
    if (b.length) z += `M${b.map((p) => p.join(" ")).join("L")}z`;
    const m = Math.max(x1 - x0, y1 - y0) * 0.03 + 0.5;
    world = { x: x0 - m, y: y0 - m, w: x1 - x0 + 2 * m, h: y1 - y0 + 2 * m };
    svg.setAttribute("viewBox", `${world.x} ${world.y} ${world.w} ${world.h}`);
    svg.style.aspectRatio = `${world.w} / ${world.h}`;
    pz.setAttribute("d", z); pr.setAttribute("d", k);
    svg.setAttribute("aria-label", t("mm.title"));
    frame();
  }
  function frame() {
    const v = on && !box.hidden ? view() : null;
    fr.style.display = v && world ? "" : "none";
    if (v && world) { fr.setAttribute("x", v.x); fr.setAttribute("y", v.y); fr.setAttribute("width", v.w); fr.setAttribute("height", v.h); }
  }
  const at = (e) => { const p = svg.createSVGPoint(); p.x = e.clientX; p.y = e.clientY; return p.matrixTransform(svg.getScreenCTM().inverse()); };
  // зона под точкой, не лежащая в показанном уровне (focus) — на неё переводится фокус
  function zoneAt(x, y) {
    const tr = model.tree, F = tr.nodes.get(model.ui.focus), has = (n) => x >= n.x && x <= n.x + n.w && y >= n.y && y <= n.y + n.d;
    if (F && has(F)) return null;
    let best = null;
    for (const n of tr.nodes.values()) if ((n.type === "group" || n.type === "rackset") && n.kids.length && n.id !== "WH" && has(n) && (!best || n.depth > best.depth)) best = n;
    return best;
  }
  svg.addEventListener("pointerdown", (e) => {
    down = true; svg.setPointerCapture(e.pointerId); e.preventDefault();
    const p = at(e), z = zoneAt(p.x, p.y);
    if (z) { down = false; model.focusTo(z.id); } else panTo(p.x, p.y);
  });
  svg.addEventListener("pointermove", (e) => { if (down) { const p = at(e); panTo(p.x, p.y); } });
  const up = () => { down = false; };
  svg.addEventListener("pointerup", up); svg.addEventListener("pointercancel", up);

  // кнопка: свернуть / показать
  function paint() {
    box.classList.toggle("off", !on); tg.textContent = on ? "−" : "▦";
    tg.title = t(on ? "mm.hide" : "mm.show"); tg.setAttribute("aria-label", tg.title); tg.setAttribute("aria-expanded", String(on));
    frame();
  }
  tg.onclick = () => { on = !on; model.pref.write("minimap", on ? "1" : "0"); paint(); place(); };

  // положение — в правом нижнем углу плана; панели (проблемы, комментарии, мастер) не закрываются: карта сдвигается левее панели, а если места не остаётся, прячется
  function place() {
    box.hidden = false;
    const m = host.getBoundingClientRect(), r = vp.getBoundingClientRect(), bw = box.offsetWidth, base = m.right - r.right + 8;
    let right = base;
    box.style.bottom = `${m.bottom - r.bottom + 8}px`;
    for (const p of document.querySelectorAll(PANEL_SEL)) {
      const c = p.getBoundingClientRect();
      if (!c.width || c.left >= r.right || c.bottom <= r.top || c.top >= r.bottom) continue;
      right = Math.max(right, m.right - c.left + 8);
    }
    if (r.width - (right - base + 8) - bw < 24) box.hidden = true; else box.style.right = `${right}px`;
    frame();
  }
  new ResizeObserver(place).observe(vp);
  paint(); build();
  return { build, frame, place, refreshText: paint };
}
