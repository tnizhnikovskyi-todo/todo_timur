// Показатели склада для тепловых карт (W-17, D-18, H2): чистые функции без DOM и без состояния.
// Вход — места `l` снимка (формат data.json: quants [{ product, qty, lot, package, reserved, age }], capacity, fill, state, orderpoint, draft)
// и `activity` снимка: { days, moves: { <код места>: { n, qty } }, demo? } — движения за окно в днях (источник: stock.move.line, у демо — синтетика хоста).
// Показатели: status — прежняя раскраска (заполненность и «ниже минимума» вместе), fill — заполненность, low — ниже минимума, empty — пустые места,
// abc — оборачиваемость (классы ABC по доле перемещений 80 / 15 / 5), age — возраст запаса (самая старая партия места по in_date).
export const HEAT_MODES = ["status", "fill", "low", "empty", "abc", "age"];

// ключи легенды каждого показателя (порядок — порядок в легенде); "none" — нет данных / не применимо
export const HEAT_KEYS = {
  status: [],
  fill: ["f0", "f25", "f50", "f75", "f100", "none"],
  low: ["out", "low", "ok", "none"],
  empty: ["empty", "used"],
  abc: ["A", "B", "C", "none"],
  age: ["d30", "d90", "d180", "d365", "dmax", "none"],
};

export const ABC_SHARE = [80, 15, 5]; // доли перемещений классов A / B / C, %
export const AGE_BOUNDS = [30, 90, 180, 365]; // верхние границы корзин возраста, дней: ≤30, ≤90, ≤180, ≤365, дольше

const EPS = 1e-9;
const qtyOf = (l) => l.quants.reduce((s, q) => s + (q.qty > 0 ? q.qty : 0), 0);

// Классы ABC по числу перемещений: места по убыванию n; класс определяется долей перемещений ДО места (не после), поэтому первое место всегда A,
// а класс B начинается, когда уже набрано 80 %. moves: { код: { n } } → Map код → "A" | "B" | "C" (места без перемещений в карту не попадают).
export function abcClasses(moves, share = ABC_SHARE) {
  const rows = Object.entries(moves || {}).map(([code, m]) => [code, +(m && m.n) || 0]).filter(([, n]) => n > 0).sort((a, b) => b[1] - a[1] || (a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0));
  const total = rows.reduce((s, r) => s + r[1], 0), a = (share[0] / 100) * total, b = ((share[0] + share[1]) / 100) * total, out = new Map();
  let before = 0;
  for (const [code, n] of rows) { out.set(code, before < a - EPS ? "A" : before < b - EPS ? "B" : "C"); before += n; }
  return out;
}

// Корзина возраста запаса (дни → ключ легенды); нет возраста — "none"
export function ageBucket(days) {
  if (days == null || !Number.isFinite(days)) return "none";
  for (let i = 0; i < AGE_BOUNDS.length; i++) if (days <= AGE_BOUNDS[i]) return `d${AGE_BOUNDS[i]}`;
  return "dmax";
}
// Возраст места — возраст самой старой партии с остатком; null, если остатка нет или возраст неизвестен
export function placeAge(l) {
  let m = null;
  for (const q of l.quants) if (q.qty > 0 && Number.isFinite(q.age)) m = m == null ? q.age : Math.max(m, q.age);
  return m;
}

// «Ниже минимума» по правилу пополнения места: out — остатка нет, low — меньше min, ok — не ниже min, none — у места нет правила.
// Берётся state снимка (его считает Odoo-адаптер); без него — по orderpoint и остатку.
export function minState(l) {
  if (l.state === "out" || l.state === "low" || l.state === "ok") return l.state;
  const op = l.orderpoint; if (!op) return "none";
  const have = l.quants.filter((q) => !op.product || q.product === op.product).reduce((s, q) => s + (q.qty > 0 ? q.qty : 0), 0);
  return have <= 0 ? "out" : have < op.min ? "low" : "ok";
}
export const isEmptyPlace = (l) => qtyOf(l) <= 0;

// Корзина заполненности: f0 — пусто, f25 … f100 — до 25 / 50 / 75 / 100 %; нет ёмкости — "none"
export function fillBin(fill) {
  if (fill == null || !Number.isFinite(fill)) return "none";
  return fill <= 0.001 ? "f0" : fill <= 0.25 ? "f25" : fill <= 0.5 ? "f50" : fill <= 0.75 ? "f75" : "f100";
}

// Ключ показателя для места (кроме abc: ему нужны движения всех мест, см. heatMap); null — раскраска по умолчанию (режим status, новые и несохранённые места)
export function heatKey(mode, l) {
  if (!l || l.draft || mode === "status") return null;
  if (mode === "fill") return fillBin(l.fill);
  if (mode === "low") return minState(l);
  if (mode === "empty") return isEmptyPlace(l) ? "empty" : "used";
  if (mode === "age") return ageBucket(placeAge(l));
  return null;
}

// Ключи по всем местам: Map код → ключ; counts — число мест по ключам; data — есть ли данные показателя (ABC без движений, возраст без in_date)
export function heatMap(mode, codes, loc, activity = null) {
  const map = new Map(), counts = {};
  const abc = mode === "abc" ? abcClasses(activity && activity.moves) : null;
  for (const code of codes) {
    const l = loc(code); if (!l || l.draft) continue;
    const k = mode === "abc" ? (abc.get(code) || "none") : heatKey(mode, l);
    if (k == null) continue;
    map.set(code, k); counts[k] = (counts[k] || 0) + 1;
  }
  return { map, counts };
}

// Есть ли у снимка данные для показателя: ABC — движения, возраст — хотя бы одна партия с возрастом
export function heatHasData(mode, activity, locs) {
  if (mode === "abc") return !!activity && Object.values(activity.moves || {}).some((m) => m && m.n > 0);
  if (mode === "age") { for (const l of locs) for (const q of l.quants) if (Number.isFinite(q.age)) return true; return false; }
  return true;
}
