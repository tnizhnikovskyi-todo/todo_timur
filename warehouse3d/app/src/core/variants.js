// Варианты планировки склада (D-19, I1): у склада несколько слоёв правок — «Як є», «Проєкт A», «Проєкт B»…
// Поля склада: variants [{ id, name, saved, pending }] и variant (id активного). Живой слой активного варианта — wh.saved / wh.pending
// (так работает всё остальное приложение); запись активного варианта в списке пустая (saved: null), слои остальных лежат в своих записях.
// name = null — имя по умолчанию («Як є» у первого, подпись собирает i18n). Чистые функции без DOM; переключение и операции — в model.js.
import { clone, normEdit } from "./types.js";

export const MAX_VARIANTS = 12;
export const MAX_NAME = 60;
export const DEFAULT_VARIANT = "v1";

const normPend = (p) => (Array.isArray(p) ? p.filter((x) => x && x.diff && x.diff.add) : []);
export const cleanName = (s) => String(s == null ? "" : s).replace(/\s+/g, " ").trim().slice(0, MAX_NAME);

// список записей и id активного: пустой или повреждённый список даёт один вариант по умолчанию
export function normVariants(rawList, rawActive) {
  const seen = new Set(), list = [];
  for (const v of Array.isArray(rawList) ? rawList : []) {
    if (!v || v.id == null) continue;
    const id = String(v.id).replace(/[^\w.-]/g, "") || null; if (!id || seen.has(id)) continue;
    seen.add(id);
    list.push({ id, name: cleanName(v.name) || null, saved: v.saved ? normEdit(v.saved) : null, pending: normPend(v.pending) });
    if (list.length >= MAX_VARIANTS) break;
  }
  if (!list.length) list.push({ id: DEFAULT_VARIANT, name: null, saved: null, pending: [] });
  const active = list.some((v) => v.id === rawActive) ? rawActive : list[0].id;
  const a = list.find((v) => v.id === active); a.saved = null; a.pending = [];
  return { variants: list, variant: active };
}

export const entryOf = (wh, id) => wh.variants.find((v) => v.id === id) || null;
export const nextId = (wh) => { let n = wh.variants.length + 1; while (entryOf(wh, `v${n}`)) n++; return `v${n}`; };

// слой варианта: у активного — живой wh.saved, у остальных — свой
export const layerOf = (wh, id) => (id === wh.variant ? wh.saved : (entryOf(wh, id) || {}).saved || null);
export const pendingOf = (wh, id) => (id === wh.variant ? wh.pending : (entryOf(wh, id) || {}).pending || []);

// список для интерфейса: { id, name (null — по умолчанию), active, first }
export const variantList = (wh) => wh.variants.map((v, i) => ({ id: v.id, name: v.name, active: v.id === wh.variant, first: i === 0, pending: pendingOf(wh, v.id).length }));

// новый вариант — копия сохранённого слоя активного (несохранённое не копируется); возвращает id
export function addVariant(wh, name) {
  const id = nextId(wh);
  wh.variants.push({ id, name: cleanName(name) || null, saved: clone(normEdit(wh.saved)), pending: [] });
  return id;
}

// сделать активным id: слой и несохранённое текущего уходят в его запись, слой выбранного становится живым
export function activate(wh, id) {
  const cur = entryOf(wh, wh.variant), tgt = entryOf(wh, id);
  if (!tgt || tgt === cur) return false;
  cur.saved = wh.saved; cur.pending = wh.pending;
  wh.saved = normEdit(tgt.saved); wh.pending = normPend(tgt.pending); wh.variant = id; tgt.saved = null; tgt.pending = [];
  wh.building = wh.saved.building ?? null;
  return true;
}

export function removeVariant(wh, id) {
  if (id === wh.variant || wh.variants.length < 2) return false;
  const i = wh.variants.findIndex((v) => v.id === id); if (i < 0) return false;
  wh.variants.splice(i, 1); return true;
}

export function renameVariant(wh, id, name) {
  const e = entryOf(wh, id); if (!e) return false;
  e.name = cleanName(name) || null; return true;
}
