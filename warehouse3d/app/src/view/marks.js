// Значки на плане (W-18): комментарии на объектах (I3) и блокировки зон другими пользователями (I5) — одни и те же подписи в 2D и 3D.
// Данные даёт model.marks(): { node, kind: "comment", open, done, task } | { node, kind: "lock", by, mine, until }.
import { hhmm } from "../core/locks.js";

export const MAX_MARKS = 150; // больше значков план не рисует: остальное — в списке комментариев
export const markText = (m) => (m.kind === "lock" ? `● ${m.by || "?"}` : m.open ? `◆ ${m.open}` : `✓ ${m.done}`);
export const markTitle = (i18n, m) => (m.kind === "lock" ? i18n.t(m.mine ? "mk.lockMine" : "mk.lockBy", { by: m.by || "?", until: hhmm(m.until) }) : i18n.t("mk.comments", { open: m.open, done: m.done }));
export const markClass = (m) => `mk ${m.kind === "lock" ? (m.mine ? "mk-lm" : "mk-l") : m.open ? (m.task ? "mk-t" : "mk-c") : "mk-d"}`;
// значки, которые видны на показанном уровне (внутри фокуса), комментарии раньше блокировок, не больше MAX_MARKS
export function visibleMarks(model, inNode) {
  const F = model.ui.focus, all = model.marks().filter((m) => inNode(m.node, F));
  return [...all.filter((m) => m.kind === "comment"), ...all.filter((m) => m.kind === "lock")].slice(0, MAX_MARKS);
}
