// Мелкие помощники экрана.
export const $ = (s, r = document) => r.querySelector(s);
export const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
export const isMac = () => /Mac|iPhone|iPad/.test(globalThis.navigator?.platform || "");
export const modKey = () => (isMac() ? "⌘" : "Ctrl");
export const reducedMotion = () => globalThis.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;

// подсветка заполненности: класс места по данным Odoo (state/fill) и по признакам «новое / не сохранено»
export const fillCls = (l) => l.state === "out" ? "bad" : l.state === "low" ? "warn" : l.fill == null ? "" : l.fill <= 0.001 ? "bad" : l.fill < 0.3 ? "warn" : "ok";
export const slotCls = (l) => l.pend ? "pend" : l.draft ? "new" : l.fill == null ? `area${l.quants.length ? " has" : ""}` : fillCls(l);
export const isLow = (l) => !!(l.state && l.state !== "ok");
export const pbar = (i18n, v, cls) => `<div class="o_pb ${cls === "ok" ? "" : cls || ""}"><div class="bar"><i style="width:${Math.max(0, Math.min(100, v * 100))}%"></i></div><span>${i18n.pct(v)}</span></div>`;

// функция и атрибуты зоны (W-14) одной строкой для подсказок и подписей: «Приймання · небезпечне, температура +2…+8 °C»; z — результат model.cap.zone(id)
export function zoneHint(i18n, z) {
  if (!z) return "";
  const parts = z.attrs.filter((a) => a !== "temp").map((a) => i18n.t(`fnattr.${a}`));
  if (z.attrs.includes("temp") || z.tmin != null || z.tmax != null) parts.push(`${i18n.t("fnattr.temp")}${z.tmin != null || z.tmax != null ? ` ${z.tmin ?? "…"}…${z.tmax ?? "…"} °C` : ""}`);
  return [z.fn ? i18n.t(`fn.${z.fn}`) : "", parts.join(", ")].filter(Boolean).join(" · ");
}

// на узком экране после выбора прокручиваем к боковой панели
export function scrollToSide(root) {
  if (!globalThis.matchMedia?.("(max-width: 900px)").matches) return;
  root.querySelector(".side")?.scrollIntoView({ behavior: reducedMotion() ? "auto" : "smooth", block: "start" });
}
