// Превью формы типа места: схематичный SVG (строка) по параметрам типа — вид спереди (стеллажи, стосы, ёмкости, носители, ворота)
// или сверху (ограждения, зоны). Без DOM и тем: цвета задают классы pv-* в style.css.
import { groundOff, levelBase, levelsTop, shapeOf } from "../core/params.js";

const W = 240, H = 150, G = 138; // размер, линия пола
const n1 = (x) => Math.round(x * 10) / 10;
const r = (x, y, w, h, c = "pv-s") => `<rect class="${c}" x="${n1(x)}" y="${n1(y)}" width="${n1(Math.max(0.5, w))}" height="${n1(Math.max(0.5, h))}"/>`;
const ln = (x1, y1, x2, y2, c = "pv-s") => `<line class="${c}" x1="${n1(x1)}" y1="${n1(y1)}" x2="${n1(x2)}" y2="${n1(y2)}"/>`;
const circ = (x, y, rad, c = "pv-s") => `<circle class="${c}" cx="${n1(x)}" cy="${n1(y)}" r="${n1(Math.max(0.5, rad))}"/>`;

export function previewSvg(t) {
  const sh = shapeOf(t), w = t.w || 1, d = t.d || 1;
  let body = "";
  if (sh === "rack" || sh === "rolls" || sh === "cabinet") {
    const lv = Math.max(1, t.lv || 1), top = levelsTop(t, lv), s = Math.min(112 / (top + 0.15), 200 / w), x0 = (W - w * s) / 2, bt = Math.max(1.5, (t.bt || 0.08) * s), v = t.v;
    body += ln(10, G, W - 10, G, "pv-g");
    if (sh === "cabinet") body += r(x0, G - (top + 0.1) * s, w * s, (top + 0.1) * s, "pv-f");
    else if (v === "aframe") { const a = ((t.ang || 75) * Math.PI) / 180, ex = Math.min(d / 2, top / Math.tan(a)); body += ln(x0, G, x0 + w * s, G, "pv-s") + `<path class="pv-s" d="M${n1(W / 2 - ex * s)} ${G} L${n1(W / 2)} ${n1(G - top * s)} L${n1(W / 2 + ex * s)} ${G}"/>`; }
    else if (v === "honey") { const c = Math.max(1, t.pos || 1); for (let i = 0; i <= c; i++) body += r(x0 + (w * s * i) / c - 1, G - (top + 0.1) * s, 2, (top + 0.1) * s); }
    else for (const u of [0, w * s]) body += r(x0 + u - 1.5, G - (top + 0.15) * s, 3, (top + 0.15) * s);
    for (let l = 0; l < lv; l++) {
      const y = G - levelBase(t, l) * s;
      if (v === "hang") continue;
      if (v === "rod") body += circ(x0 + w * s * 0.5, y - 4, 3) + ln(x0, y, x0 + w * s, y);
      else if (v === "cant") body += ln(x0, y, x0 + w * s, y, "pv-s pv-d");
      else body += r(x0, y - bt / 2, w * s, bt, sh === "cabinet" ? "pv-t" : "pv-b");
    }
    if (v === "hang") body += ln(x0, G - top * s, x0 + w * s, G - top * s) + [0.2, 0.4, 0.6, 0.8].map((k) => ln(x0 + w * s * k, G - top * s, x0 + w * s * k, G - top * s * 0.6, "pv-d")).join("");
    if (groundOff(t)) body += ln(x0, G - groundOff(t) * s, x0 + 8, G - groundOff(t) * s, "pv-d");
    body += `<text class="pv-t" x="${W / 2}" y="12" text-anchor="middle">${n1(w)} × ${n1(d)} × ${n1(top)}</text>`;
  } else if (sh === "stack") {
    const h = t.h || 1.2, gx = Math.max(1, t.gx || 1), tiers = Math.max(1, t.tiers || 1), s = Math.min(112 / h, 200 / w), bw = (w * s) / gx, bh = (h * s) / tiers, x0 = (W - w * s) / 2;
    body += ln(10, G, W - 10, G, "pv-g");
    for (let i = 0; i < gx; i++) for (let k = 0; k < tiers; k++) body += r(x0 + i * bw + 0.5, G - (k + 1) * bh, bw - 1, bh - 0.5, "pv-f");
    body += `<text class="pv-t" x="${W / 2}" y="12" text-anchor="middle">${n1(w)} × ${n1(d)} × ${n1(h)}</text>`;
  } else if (sh === "cylinder") {
    const h = t.h || 2, dia = Math.min(w, d), s = Math.min(100 / h, 100 / dia), cw = dia * s, ch = h * s, x0 = (W - cw) / 2, cone = t.cone ? Math.min(ch * 0.3, cw * 0.6) : 0;
    body += ln(10, G, W - 10, G, "pv-g");
    body += `<path class="pv-f" d="M${n1(x0)} ${n1(G - ch)} L${n1(x0)} ${n1(G - cone)} L${n1(W / 2)} ${G} L${n1(x0 + cw)} ${n1(G - cone)} L${n1(x0 + cw)} ${n1(G - ch)} Z"/>`;
    body += `<ellipse class="pv-s" cx="${n1(W / 2)}" cy="${n1(G - ch)}" rx="${n1(cw / 2)}" ry="${n1(Math.max(2, cw / 8))}"/>`;
    body += `<text class="pv-t" x="${W / 2}" y="12" text-anchor="middle">∅ ${n1(dia)} × ${n1(h)}</text>`;
  } else if (sh === "mobile") {
    const h = t.h || 1.2, s = Math.min(100 / h, 200 / w), pw = w * s, x0 = (W - pw) / 2, ph = h * s, yb = G - 14;
    body += ln(10, G, W - 10, G, "pv-g") + r(x0, yb - 4, pw, 4, "pv-f");
    if (t.wheels) for (const u of [0.12, 0.88]) body += circ(x0 + pw * u, G - 5, 5);
    for (let i = 0; i < (t.shelves || 0); i++) body += ln(x0, yb - 4 - ((ph - 18) * (i + 1)) / ((t.shelves || 0) + 1), x0 + pw, yb - 4 - ((ph - 18) * (i + 1)) / ((t.shelves || 0) + 1), "pv-b");
    if ((t.walls || 0) > 0) body += r(x0, yb - ph + 14, pw, ph - 18, "pv-d");
    for (let i = 0; i < (t.slots || 0); i++) body += ln(x0 + ((i + 0.5) * pw) / t.slots, yb - 4, x0 + ((i + 0.5) * pw) / t.slots, yb - ph + 14, "pv-d");
    body += `<text class="pv-t" x="${W / 2}" y="12" text-anchor="middle">${n1(w)} × ${n1(d)} × ${n1(h)}</text>`;
  } else if (sh === "gate") {
    const h = t.h || 3, s = Math.min(110 / h, 200 / w), gw = w * s, x0 = (W - gw) / 2, jw = Math.max(5, gw / 8);
    body += ln(10, G, W - 10, G, "pv-g") + r(x0, G - h * s, jw, h * s, "pv-f") + r(x0 + gw - jw, G - h * s, jw, h * s, "pv-f") + r(x0 + jw, G - h * s, gw - 2 * jw, 10, "pv-f");
    body += `<text class="pv-t" x="${W / 2}" y="12" text-anchor="middle">${n1(w)} × ${n1(h)}</text>`;
  } else { // зона и ограждение: вид сверху
    const s = Math.min(110 / d, 200 / w), pw = w * s, pd = d * s, x0 = (W - pw) / 2, y0 = (H - pd) / 2 + 4, enc = sh === "enclosure";
    body += r(x0, y0, pw, pd, enc ? "pv-z" : "pv-h");
    if (enc) {
      const th = Math.max(2, (t.th || 0.1) * s * 2), wl = typeof t.wl === "string" ? t.wl : "NESW", door = t.door || "S";
      for (const k of wl) {
        const horiz = k === "N" || k === "S", len = horiz ? pw : pd, g = k === door ? len * 0.35 : 0, a = (len - g) / 2;
        const seg = (u, l) => (horiz ? r(x0 + u, k === "N" ? y0 : y0 + pd - th, l, th, "pv-f") : r(k === "W" ? x0 : x0 + pw - th, y0 + u, th, l, "pv-f"));
        if (g) { seg(0, a); seg(a + g, a); } else seg(0, len);
      }
    }
    body += `<text class="pv-t" x="${W / 2}" y="12" text-anchor="middle">${n1(w)} × ${n1(d)}${t.h > 0 && enc ? ` × ${n1(t.h)}` : ""}</text>`;
  }
  return `<svg class="pv" viewBox="0 0 ${W} ${H}" role="img" aria-hidden="true" focusable="false"><defs><pattern id="pvh" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="6" class="pv-hl"/></pattern></defs>${body}</svg>`;
}
