// Демо-значения для тепловых карт (W-17, D-18): в снимке data.json нет ни движений, ни in_date партий, поэтому хост достраивает их
// детерминированной синтетикой (одинаковый результат при каждой загрузке) и помечает снимок `meta.activity.demo = true`.
// Это только для проверки и демонстрации; ядро этих значений не создаёт. Настоящие данные приходят из Odoo (adapters/odoo-api.js).
export const DEMO_DAYS = 90;

// FNV-1a по строке → неотрицательное целое
const hash = (s) => { let h = 2166136261; for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); } return h >>> 0; };

// Дополняет снимок на месте: у остатков `age` (дней, 0…~420, больше «старых» партий у малой доли мест), у снимка `meta.activity { days, moves: { код: { n, qty } }, demo }`.
// Распределение движений скошенное (немногие места получают большую часть перемещений), чтобы классы ABC различались. Если данные уже есть — не трогает.
export function decorateDemo(base) {
  if (!base || !base.locations || (base.meta && base.meta.activity)) return base;
  const moves = {};
  for (const [code, l] of Object.entries(base.locations)) {
    const h = hash(code), r = (h % 1000) / 1000, r2 = ((h >>> 10) % 1000) / 1000, stocked = (l.quants || []).some((q) => q.qty > 0);
    const n = stocked ? Math.round(48 * r ** 3) : r > 0.7 ? Math.round(6 * r2 ** 2) : 0;
    if (n > 0) moves[code] = { n, qty: n * (2 + ((h >>> 20) % 18)) };
    for (const q of l.quants || []) q.age = Math.floor(420 * ((hash(`${code}|${q.product}|${q.lot || ""}`) % 1000) / 1000) ** 1.6);
  }
  base.meta = { ...(base.meta || {}), activity: { days: DEMO_DAYS, moves, demo: true } };
  return base;
}
