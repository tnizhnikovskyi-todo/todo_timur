// Блокировки зон (D-19, W-21). Работают, только если хранилище умеет lock/unlock (модуль Odoo); без него — ничего не делают.
// Правка идёт в «зоне» — ближайшем предке-группе узла (не сам склад). При входе в правку зоны хранилище выдаёт блокировку;
// если зону держит другой пользователь — уведомление, а правки этой зоны запрещены (edit.change спрашивает blocked()).
// Блокировки продлеваются (renew — по таймеру хоста) и снимаются при выходе из правки (release).
// Ответ хранилища: { ok, owner, expires (ISO), mine }. Нет связи — правка не блокируется (но об этом нигде не молчим: ошибка в консоль).
import { refById } from "./tree.js";

const ZONE_TYPES = ["group", "rackset"];
// срок блокировки (ISO, UTC) → «ЧЧ:ММ» по местному времени
export const hhmm = (iso) => { const d = iso ? new Date(iso) : null; return d && !isNaN(d) ? d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : ""; };

export function createLocks(s) {
  const held = new Set(), busy = new Map(), inflight = new Set();
  const api = () => (s.storage && !s.storage.readonly && typeof s.storage.lock === "function" ? s.storage : null);
  const keyOf = (zone) => `${s.wh.id}\n${zone}`;
  const nodeOf = (id) => s.tree.nodes.get(id);
  // зона узла: ближайший предок-группа (включая сам узел); у склада и «types» зоны нет
  function zoneOf(id) {
    for (let n = id && nodeOf(id); n; n = n.parent && nodeOf(n.parent)) if (n.id !== "WH" && ZONE_TYPES.includes(n.type)) return n.id;
    return null;
  }
  const arg = (zone) => ({ project: s.project.id, warehouse: s.wh.id, warehouseCode: s.wh.code, zone });
  const expired = (b) => !b.until || Date.parse(b.until) <= Date.now();
  const say = (kind, key, params) => s.emit({ type: "notify", kind, key, params });
  function markBusy(zone, r) {
    const b = { by: r.owner || "?", until: r.expires || null };
    busy.set(keyOf(zone), b);
    say("bad", "n.zoneLocked", { zone: refById(s.tree, zone), by: b.by, until: hhmm(b.until) });
    s.emit({ type: "locks" });
  }
  async function take(zone) {
    const k = keyOf(zone);
    if (held.has(k) || inflight.has(k)) return;
    const b = busy.get(k);
    if (b && !expired(b)) return;
    busy.delete(k); inflight.add(k);
    try {
      const r = await api().lock(arg(zone));
      if (!r) return;
      if (r.ok) { held.add(k); s.emit({ type: "locks" }); } else if (r.owner) markBusy(zone, r); // отказ без владельца (нет прав) — не «занято»
    } catch (e) { console.error("lock", e); } finally { inflight.delete(k); }
  }
  return {
    zoneOf,
    // что правится сейчас (выделенный узел или текущий фокус) → занятая зона { zone, by, until } или null
    busyInfo(id) {
      const z = zoneOf(id); if (!z) return null;
      const b = busy.get(keyOf(z)); return b && !expired(b) ? { zone: z, ...b } : null;
    },
    // ids правки (узлы, "WH", "types") → первая занятая другим зона или null
    blocked(ids) {
      for (const id of [].concat(ids).filter(Boolean)) { const b = this.busyInfo(id); if (b) return b; }
      return null;
    },
    // вызывается на событиях выбора/фокуса: в режиме правки берёт блокировку зоны текущего узла
    sync() {
      if (!api() || !s.ui.edit) return;
      const z = zoneOf(s.ui.esel || s.ui.focus);
      if (z) take(z);
    },
    held: () => [...held],
    // продлить все свои; потерянные (истекли и заняты другим) становятся чужими
    async renew() {
      if (!api()) return;
      for (const k of [...held]) {
        const i = k.indexOf("\n"), wid = k.slice(0, i), zone = k.slice(i + 1), w = s.project.warehouses.find((x) => x.id === wid);
        try {
          const r = await api().lock({ project: s.project.id, warehouse: wid, warehouseCode: w && w.code, zone });
          if (r && !r.ok && r.owner) { held.delete(k); markBusy(zone, r); }
        } catch (e) { console.error("lock", e); }
      }
    },
    // выход из правки (all — все склады): снять свои и забыть чужие
    async release() {
      busy.clear();
      if (!api()) { held.clear(); return; }
      const mine = [...held]; held.clear();
      for (const k of mine) {
        const i = k.indexOf("\n");
        try { await api().unlock({ project: s.project.id, warehouse: k.slice(0, i), zone: k.slice(i + 1) }); } catch (e) { console.error("unlock", e); }
      }
      s.emit({ type: "locks" });
    },
  };
}
