// Згенеровано tools/build_core.mjs з factory3d/core/constructor/*. НЕ правити вручну: правте core/ і запустіть збірку.
var __defProp = Object.defineProperty;
var __export = (target, all) => {
  for (var name in all)
    __defProp(target, name, { get: all[name], enumerable: true });
};

// core/constructor/registry.js
var Registry = class {
  constructor(name) {
    this.name = name;
    this._map = /* @__PURE__ */ new Map();
    this._n = 0;
    this._subs = /* @__PURE__ */ new Set();
  }
  /**
   * @param {string} key
   * @param {*} value
   * @param {{sequence?: number, force?: boolean}} [opts] sequence — порядок (менше = раніше, за замовчуванням 50);
   *   без `force` повторна реєстрація ключа — помилка (щоб два слайси не затирали один одного мовчки)
   */
  add(key, value, { sequence = 50, force = false } = {}) {
    if (this._map.has(key) && !force) {
      throw new Error(`Реєстр «${this.name}»: ключ «${key}» уже зайнятий`);
    }
    this._map.set(key, { value, sequence, n: this._n++ });
    this._notify();
    return this;
  }
  get(key, fallback) {
    const e = this._map.get(key);
    if (e) {
      return e.value;
    }
    if (arguments.length > 1) {
      return fallback;
    }
    throw new Error(`Реєстр «${this.name}»: немає ключа «${key}»`);
  }
  has(key) {
    return this._map.has(key);
  }
  remove(key) {
    const had = this._map.delete(key);
    if (had) {
      this._notify();
    }
    return had;
  }
  clear() {
    this._map.clear();
    this._notify();
  }
  /** [[key, value], …] у порядку sequence, далі — у порядку додавання. */
  getEntries() {
    return [...this._map.entries()].sort((a, b) => a[1].sequence - b[1].sequence || a[1].n - b[1].n).map(([k, e]) => [k, e.value]);
  }
  getAll() {
    return this.getEntries().map(([, v]) => v);
  }
  keys() {
    return this.getEntries().map(([k]) => k);
  }
  /** Підписка на зміни (повертає функцію відписки). */
  subscribe(fn) {
    this._subs.add(fn);
    return () => this._subs.delete(fn);
  }
  _notify() {
    for (const fn of this._subs) {
      fn(this);
    }
  }
};
var REGISTRY_NAMES = ["panels", "dialogs", "checks", "shapes", "metrics", "menu", "hotkeys", "capabilities"];
var registries = Object.fromEntries(REGISTRY_NAMES.map((n) => [n, new Registry(n)]));
var CAPABILITY_NAMES = [
  "publish",
  "check",
  "library",
  "storage",
  "stock",
  "putaway",
  "odoo_import",
  "rollback",
  "render",
  "files",
  "variants",
  "comments",
  "locks"
];
var can = (name) => registries.capabilities.get(name, false) === true;
function setCapabilities(caps = {}) {
  registries.capabilities.clear();
  for (const [name, on] of Object.entries(caps)) {
    registries.capabilities.add(name, !!on, { force: true });
  }
}
function forEachEntry(registry, fn, ctx2) {
  for (const [key, value] of registry.getEntries()) {
    if (value && typeof value.when === "function" && !value.when(ctx2)) {
      continue;
    }
    if (value && value.capability && !can(value.capability)) {
      continue;
    }
    try {
      fn(key, value);
    } catch (e) {
      console.error(`Реєстр «${registry.name}», ключ «${key}»:`, e);
    }
  }
}

// core/constructor/adapter.js
var REQUIRED_METHODS = [
  "listSites",
  "createSite",
  "load",
  "save",
  "flush",
  "saveSite",
  "saveCheck",
  "check",
  "publish",
  "restoreVersion",
  "uploadModel",
  "loadModel",
  "attachUnderlay",
  "detachUnderlay",
  "loadUnderlay",
  "ensureGroupIds"
];
var StoreError = class extends Error {
  constructor(code, message, extra = {}) {
    super(message || code);
    this.code = code;
    Object.assign(this, extra);
  }
};
function newUid() {
  const b = new Uint8Array(16);
  (globalThis.crypto || window.crypto).getRandomValues(b);
  return Array.from(b, (x) => x.toString(16).padStart(2, "0")).join("");
}
function assertAdapter(adapter) {
  const missing = REQUIRED_METHODS.filter((m) => typeof adapter?.[m] !== "function");
  if (missing.length) {
    throw new Error(`Адаптер даних не відповідає контракту: немає ${missing.join(", ")}`);
  }
  const caps = adapter.capabilities;
  if (!caps || typeof caps !== "object") {
    throw new Error("Адаптер даних не оголосив capabilities");
  }
  for (const name of Object.keys(caps)) {
    if (!CAPABILITY_NAMES.includes(name)) {
      throw new Error(`Адаптер оголосив невідому можливість «${name}»`);
    }
  }
  return adapter;
}
var noop = () => {
};
var BaseAdapter = class {
  constructor(o = {}) {
    this.kind = "base";
    this.capabilities = {};
    this.autosaveMs = o.autosaveMs ?? 1500;
    this.status = "saved";
    this.onStatus = o.onStatus || noop;
    this.onSaved = o.onSaved || noop;
    this.onConflict = o.onConflict || (() => "theirs");
    this.onReject = o.onReject || noop;
    this.onReload = o.onReload || noop;
  }
  get dirty() {
    return false;
  }
  _setStatus(status, info) {
    this.status = status;
    this.onStatus(status, info);
  }
  async ensureGroupIds() {
    return {};
  }
  async loadModel() {
    return null;
  }
  async loadUnderlay() {
    return null;
  }
};

// core/constructor/body.js
var BODY_HTML = `<svg width="0" height="0" style="position:absolute" aria-hidden="true" focusable="false"><defs>
<symbol id="i-eye" viewBox="0 0 24 24"><path d="M2 12s3.6-6.5 10-6.5S22 12 22 12s-3.6 6.5-10 6.5S2 12 2 12z"/><circle cx="12" cy="12" r="3"/></symbol>
<symbol id="i-eyeoff" viewBox="0 0 24 24"><path d="M3 3l18 18"/><path d="M10.6 5.7A10 10 0 0 1 12 5.5C18.4 5.5 22 12 22 12a17 17 0 0 1-3.2 3.9M6.3 6.8A17 17 0 0 0 2 12s3.6 6.5 10 6.5c1.5 0 2.8-.3 4-.9"/><path d="M9.9 9.9a3 3 0 0 0 4.2 4.2"/></symbol>
<symbol id="i-lock" viewBox="0 0 24 24"><rect x="5" y="11" width="14" height="9" rx="1"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/></symbol>
<symbol id="i-plus" viewBox="0 0 24 24"><path d="M12 5v14M5 12h14"/></symbol>
<symbol id="i-x" viewBox="0 0 24 24"><path d="M6 6l12 12M18 6L6 18"/></symbol>
<symbol id="i-rot" viewBox="0 0 24 24"><path d="M20 12a8 8 0 1 1-2.5-5.8"/><path d="M20 4v5h-5"/></symbol>
<symbol id="i-trash" viewBox="0 0 24 24"><path d="M4 7h16M10 7V4h4v3M6 7l1 13h10l1-13M10 11v6M14 11v6"/></symbol>
<symbol id="i-ruler" viewBox="0 0 24 24"><path d="M3 17L17 3l4 4L7 21z"/><path d="M7 13l2 2M10 10l2 2M13 7l2 2"/></symbol>
<symbol id="i-cube" viewBox="0 0 24 24"><path d="M12 3l8 4.5v9L12 21l-8-4.5v-9z"/><path d="M4 7.5L12 12l8-4.5M12 12v9"/></symbol>
<symbol id="i-plan" viewBox="0 0 24 24"><rect x="3" y="3" width="18" height="18"/><path d="M3 12h9V3M12 12v9M16 12h5"/></symbol>
<symbol id="i-fit" viewBox="0 0 24 24"><path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"/></symbol>
<symbol id="i-sun" viewBox="0 0 24 24"><circle cx="12" cy="12" r="4"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M19 5l-2 2M7 17l-2 2"/></symbol>
<symbol id="i-moon" viewBox="0 0 24 24"><path d="M20 14.5A8 8 0 0 1 9.5 4 8 8 0 1 0 20 14.5z"/></symbol>
<symbol id="i-upload" viewBox="0 0 24 24"><path d="M12 16V4M7 9l5-5 5 5M4 16v4h16v-4"/></symbol>
<symbol id="i-hist" viewBox="0 0 24 24"><path d="M3 12a9 9 0 1 0 3-6.7"/><path d="M3 4v5h5M12 7v5l3 2"/></symbol>
<symbol id="i-check" viewBox="0 0 24 24"><path d="M4 12.5l5 5L20 6.5"/></symbol>
<symbol id="i-tag" viewBox="0 0 24 24"><path d="M4 5h16M9 5v14M15 5v14M7 19h4M13 19h4"/></symbol>
<symbol id="i-up" viewBox="0 0 24 24"><path d="M6 15l6-6 6 6"/></symbol>
<symbol id="i-down" viewBox="0 0 24 24"><path d="M6 9l6 6 6-6"/></symbol>
<symbol id="i-copy" viewBox="0 0 24 24"><rect x="8" y="8" width="12" height="12"/><path d="M4 16V4h12"/></symbol>
</defs></svg>
<div id="app" data-mtab="layers">
  <header class="top">
    <div class="brand">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="square" aria-hidden="true"><path d="M3 21V3h18"/><path d="M7 21V9h6v12M13 15h8v6"/><path d="M3 21h18" stroke-dasharray="2 2"/></svg>
      <span>Конструктор</span>
    </div>
    <div class="grp" id="siteGrp"><label for="siteSel">Площадка</label><select id="siteSel" aria-label="Площадка"></select><button class="fbtn sm" id="btnNewSite" type="button">+<span class="lg"> Нова площадка</span></button></div>
    <div class="grp"><label for="roleSel">Роль</label><select id="roleSel" aria-label="Роль"></select></div>
    <div class="seg" id="modeSeg" role="group" aria-label="Режим"><button type="button" data-mode="view" aria-pressed="false">Перегляд</button><button type="button" data-mode="edit" aria-pressed="true">Редагування</button></div>
    <div class="grow"></div>
    <span class="chip" id="draftChip">Чернетка · без змін</span>
    <span class="store" id="storeTag"></span>
    <div class="grp" id="menuExtra" hidden></div>
    <button class="fbtn primary" id="btnPublish" type="button">Опублікувати</button>
    <button class="fbtn" id="btnHistory" type="button">Історія<span class="lg"> версій</span></button>
    <button class="fbtn icon" id="btnTheme" type="button" aria-label="Тема"></button>
  </header>
  <div class="main">
    <aside class="left" id="left" aria-label="Ліва панель">
      <nav class="ltabs" role="tablist" id="ltabs">
        <button type="button" role="tab" data-tab="layers">Шари</button>
        <button type="button" role="tab" data-tab="slots">Місця</button>
        <button type="button" role="tab" data-tab="catalog">Каталог</button>
      </nav>
      <div class="pane" id="leftBody"></div>
    </aside>
    <section class="center" aria-label="3D-сцена">
      <div id="vp"></div>
      <div class="vtools" id="vtools"></div>
      <div class="vnotice" id="vnotice"></div>
      <div class="legend" id="legend"><div><kbd>R</kbd> поворот · <kbd>Del</kbd> видалити · <kbd>Esc</kbd> скасувати · <kbd>Alt</kbd> без прив’язки · <kbd>←↑↓→</kbd> крок сітки · <kbd>M</kbd> лінійка · ПКМ — панорама (у «Плані» й ЛКМ на порожньому) · колесо — масштаб</div>
        <div class="lgd"><span><i class="sq e"></i>електрика</span><span><i class="ci a"></i>повітря</span><span><i class="tr d"></i>аспірація</span><span><i class="bx ai"></i>прохід</span><span><i class="bx fp"></i>пожежна зона</span><span><i class="ds w"></i>попередження</span><span><i class="ds b"></i>заборона</span></div></div>
      <div class="stamp" id="stamp"></div>
      <div class="rlabel" id="rlabel" hidden></div>
      <div class="float" id="dxfPanel" hidden></div>
    </section>
    <aside class="right" id="right" aria-label="Властивості">
      <div class="pane" id="rightBody"></div>
    </aside>
  </div>
  <nav class="mtabs" id="mtabs" role="tablist">
    <button type="button" role="tab" data-mtab="layers">Шари</button>
    <button type="button" role="tab" data-mtab="slots">Місця</button>
    <button type="button" role="tab" data-mtab="catalog">Каталог</button>
    <button type="button" role="tab" data-mtab="props">Об’єкт</button>
  </nav>
  <div id="toast" role="status" aria-live="polite"></div>
</div>
`;

// core/constructor/data.js
var data_exports = {};
__export(data_exports, {
  CATEGORIES: () => CATEGORIES,
  CHECKS: () => CHECKS,
  FRONT_ANGLE: () => FRONT_ANGLE,
  FRONT_SIDES: () => FRONT_SIDES,
  LAYER_KINDS: () => LAYER_KINDS,
  LAYER_UTIL_KINDS: () => LAYER_UTIL_KINDS,
  ROLES: () => ROLES,
  SOLID_SLOTS: () => SOLID_SLOTS,
  TPL: () => TPL,
  UTIL_KINDS: () => UTIL_KINDS,
  defaultParams: () => defaultParams,
  newLayerDefaults: () => newLayerDefaults,
  roleName: () => roleName,
  rotationsList: () => rotationsList,
  slotHeight: () => slotHeight
});

// core/constructor/cells.js
var cells_exports = {};
__export(cells_exports, {
  CODE_MAX_LEN: () => CODE_MAX_LEN,
  OVERRIDE_KEYS: () => OVERRIDE_KEYS,
  PREFIX_MAX_LEN: () => PREFIX_MAX_LEN,
  SERVICE_SIDES: () => SERVICE_SIDES,
  SLOT_TEMPLATES: () => SLOT_TEMPLATES,
  cellCount: () => cellCount,
  cellsOf: () => cellsOf,
  clearCellsCache: () => clearCellsCache,
  countCells: () => countCells,
  footprint: () => footprint,
  generateCells: () => generateCells,
  normalizeParams: () => normalizeParams,
  rawCells: () => rawCells,
  slotObb: () => slotObb
});

// core/constructor/geometry.js
var geometry_exports = {};
__export(geometry_exports, {
  FRONT_VECTORS: () => FRONT_VECTORS,
  aabbOverlap: () => aabbOverlap,
  anchorOffset: () => anchorOffset,
  makeObb: () => makeObb,
  obbAabb: () => obbAabb,
  obbAxes: () => obbAxes,
  obbCorners: () => obbCorners,
  obbInsidePolygon: () => obbInsidePolygon,
  placementObb: () => placementObb,
  polygonContains: () => polygonContains,
  rectObb: () => rectObb,
  rectPolygon: () => rectPolygon,
  rotate: () => rotate,
  satPenetration: () => satPenetration,
  segmentsCross: () => segmentsCross,
  serviceObb: () => serviceObb,
  serviceTotal: () => serviceTotal,
  utilityPoints: () => utilityPoints
});
var FRONT_VECTORS = { s: [0, -1], n: [0, 1], e: [1, 0], w: [-1, 0] };
var makeObb = (cx, cy, a, b, rot = 0) => ({ cx: +cx, cy: +cy, a: +a, b: +b, rot: +rot });
function rotate(x, y, deg) {
  if (!deg) {
    return [x, y];
  }
  const r = deg * Math.PI / 180;
  const c = Math.cos(r);
  const s = Math.sin(r);
  return [x * c - y * s, x * s + y * c];
}
function obbAxes(obb) {
  const r = obb.rot * Math.PI / 180;
  const c = Math.cos(r);
  const s = Math.sin(r);
  return [
    [c, s],
    [-s, c]
  ];
}
function obbCorners(obb) {
  const [[ux, uy], [vx, vy]] = obbAxes(obb);
  const { cx, cy, a, b } = obb;
  return [
    [cx - a * ux - b * vx, cy - a * uy - b * vy],
    [cx + a * ux - b * vx, cy + a * uy - b * vy],
    [cx + a * ux + b * vx, cy + a * uy + b * vy],
    [cx - a * ux + b * vx, cy - a * uy + b * vy]
  ];
}
function obbAabb(obb) {
  const cs = obbCorners(obb);
  const xs = cs.map((p) => p[0]);
  const ys = cs.map((p) => p[1]);
  return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
}
var rectObb = (x0, y0, x1, y1) => makeObb((x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2, (y1 - y0) / 2, 0);
var aabbOverlap = (A, B, eps = 0) => !(A[2] < B[0] - eps || B[2] < A[0] - eps || A[3] < B[1] - eps || B[3] < A[1] - eps);
function satPenetration(A, B) {
  const [[a1x, a1y], [a2x, a2y]] = obbAxes(A);
  const [[b1x, b1y], [b2x, b2y]] = obbAxes(B);
  const dx = B.cx - A.cx;
  const dy = B.cy - A.cy;
  let best = Infinity;
  for (const [ux, uy] of [
    [a1x, a1y],
    [a2x, a2y],
    [b1x, b1y],
    [b2x, b2y]
  ]) {
    const rA = A.a * Math.abs(ux * a1x + uy * a1y) + A.b * Math.abs(ux * a2x + uy * a2y);
    const rB = B.a * Math.abs(ux * b1x + uy * b1y) + B.b * Math.abs(ux * b2x + uy * b2y);
    const depth = rA + rB - Math.abs(dx * ux + dy * uy);
    if (depth < best) {
      best = depth;
    }
  }
  return best;
}
function distPointSegment(px, py, p1, p2) {
  const [x1, y1] = p1;
  const [x2, y2] = p2;
  const vx = x2 - x1;
  const vy = y2 - y1;
  const l2 = vx * vx + vy * vy;
  if (l2 === 0) {
    return Math.hypot(px - x1, py - y1);
  }
  const t = Math.max(0, Math.min(1, ((px - x1) * vx + (py - y1) * vy) / l2));
  return Math.hypot(px - (x1 + t * vx), py - (y1 + t * vy));
}
function polygonContains(poly, point, eps = 1e-3) {
  const [px, py] = point;
  const n = poly.length;
  for (let i = 0; i < n; i++) {
    if (distPointSegment(px, py, poly[i], poly[(i + 1) % n]) <= eps) {
      return true;
    }
  }
  let inside = false;
  let j = n - 1;
  for (let i = 0; i < n; i++) {
    const [xi, yi] = poly[i];
    const [xj, yj] = poly[j];
    if (yi > py !== yj > py && px < (xj - xi) * (py - yi) / (yj - yi) + xi) {
      inside = !inside;
    }
    j = i;
  }
  return inside;
}
function side(p, q1, q2) {
  const vx = q2[0] - q1[0];
  const vy = q2[1] - q1[1];
  const len = Math.hypot(vx, vy);
  return len === 0 ? 0 : (vx * (p[1] - q1[1]) - vy * (p[0] - q1[0])) / len;
}
function segmentsCross(p1, p2, q1, q2, eps = 1e-3) {
  const d1 = side(p1, q1, q2);
  const d2 = side(p2, q1, q2);
  const e1 = side(q1, p1, p2);
  const e2 = side(q2, p1, p2);
  if (Math.min(Math.abs(d1), Math.abs(d2), Math.abs(e1), Math.abs(e2)) <= eps) {
    return false;
  }
  return d1 * d2 < 0 && e1 * e2 < 0;
}
function obbInsidePolygon(obb, poly, eps = 1e-3) {
  const cs = obbCorners(obb);
  if (!cs.every((c) => polygonContains(poly, c, eps))) {
    return false;
  }
  const n = poly.length;
  for (let i = 0; i < 4; i++) {
    const c1 = cs[i];
    const c2 = cs[(i + 1) % 4];
    for (let j = 0; j < n; j++) {
      if (segmentsCross(c1, c2, poly[j], poly[(j + 1) % n], eps)) {
        return false;
      }
    }
  }
  return true;
}
var rectPolygon = (length, width2) => [
  [0, 0],
  [length, 0],
  [length, width2],
  [0, width2]
];
function frontFrame(v) {
  const a = v.length / 2e3;
  const b = v.width / 2e3;
  const [fx, fy] = FRONT_VECTORS[v.front_side || "s"] || FRONT_VECTORS.s;
  const rx = -fy;
  const ry = fx;
  const [hf, hl] = fx === 0 ? [b, a] : [a, b];
  return { f: [fx, fy], r: [rx, ry], hf, hl, a, b };
}
function anchorOffset(v) {
  const { f, r, hf, hl } = frontFrame(v);
  const anchor = v.anchor || "center";
  if (anchor === "front") {
    return [-f[0] * hf, -f[1] * hf];
  }
  if (anchor === "back") {
    return [f[0] * hf, f[1] * hf];
  }
  if (anchor === "corner") {
    return [-f[0] * hf + r[0] * hl, -f[1] * hf + r[1] * hl];
  }
  return [0, 0];
}
function placementObb(v, x, y, rotation) {
  const [ox, oy] = anchorOffset(v);
  const [wx, wy] = rotate(ox, oy, rotation);
  return makeObb(x + wx, y + wy, v.length / 2e3, v.width / 2e3, rotation);
}
function serviceTotal(v) {
  const s = v.service || {};
  return ["front", "back", "left", "right"].reduce((acc, k) => acc + Math.max(0, s[k] || 0), 0);
}
function serviceObb(v, x, y, rotation) {
  if (serviceTotal(v) <= 0) {
    return null;
  }
  const s = v.service || {};
  const { f, r, a, b } = frontFrame(v);
  const ext = { "+x": 0, "-x": 0, "+y": 0, "-y": 0 };
  const add = ([vx, vy], value) => {
    if (vx > 0) {
      ext["+x"] += value;
    } else if (vx < 0) {
      ext["-x"] += value;
    } else if (vy > 0) {
      ext["+y"] += value;
    } else {
      ext["-y"] += value;
    }
  };
  add(f, (s.front || 0) / 1e3);
  add([-f[0], -f[1]], (s.back || 0) / 1e3);
  add(r, (s.right || 0) / 1e3);
  add([-r[0], -r[1]], (s.left || 0) / 1e3);
  const body = placementObb(v, x, y, rotation);
  const lx = (ext["+x"] - ext["-x"]) / 2;
  const ly = (ext["+y"] - ext["-y"]) / 2;
  const [wx, wy] = rotate(lx, ly, rotation);
  return makeObb(
    body.cx + wx,
    body.cy + wy,
    a + (ext["+x"] + ext["-x"]) / 2,
    b + (ext["+y"] + ext["-y"]) / 2,
    rotation
  );
}
function utilityPoints(v, x, y, rotation) {
  const body = placementObb(v, x, y, rotation);
  return (v.utilities || []).map((u) => {
    const [wx, wy] = rotate((u.x_mm || 0) / 1e3, (u.y_mm || 0) / 1e3, rotation);
    return [u.kind, body.cx + wx, body.cy + wy];
  });
}

// core/constructor/cells.js
var CODE_MAX_LEN = 32;
var PREFIX_MAX_LEN = 22;
var I = "int";
var F = "float";
var SLOT_TEMPLATES = {
  pallet_rack: {
    label: "Палетний стелаж",
    cells: true,
    params: {
      bays: [1, 200, 6, I],
      levels: [1, 12, 4, I],
      bay_width: [0.3, 6, 2.7, F],
      depth: [0.2, 3, 1.1, F],
      level_height: [0.1, 3, 1.5, F],
      positions_per_bay: [1, 8, 3, I],
      max_load_kg: [0, null, 1e3, F],
      index_digits: [1, 4, 2, I]
    },
    choices: { code_style: [["default", "bay_letter", "exact"], "default"] }
  },
  cantilever: {
    label: "Консольний стелаж",
    cells: true,
    params: {
      arms: [1, 100, 4, I],
      levels: [1, 12, 3, I],
      arm_length: [0.3, 2, 1, F],
      length: [0.5, 60, 6, F],
      level_height: [0.1, 3, 1.2, F],
      max_load_kg: [0, null, 500, F],
      index_digits: [1, 4, 2, I]
    },
    choices: { code_style: [["default", "exact"], "default"] }
  },
  shelf: {
    label: "Полицевий стелаж / комірки",
    cells: true,
    params: {
      sections: [1, 100, 4, I],
      shelves: [1, 20, 5, I],
      cell_w: [0.1, 8, 0.9, F],
      cell_d: [0.1, 2, 0.4, F],
      cell_h: [0.05, 2, 0.4, F],
      index_digits: [1, 4, 2, I]
    },
    choices: { loc_kind: [["bin", "shelf"], "bin"], code_style: [["default", "exact"], "default"] }
  },
  floor_stack: {
    label: "Напільне штабелювання",
    cells: true,
    params: {
      rows: [1, 50, 2, I],
      cols: [1, 26, 4, I],
      cell_l: [0.3, 6, 1.2, F],
      cell_w: [0.3, 4, 0.8, F],
      max_height: [0.1, 6, 1.5, F],
      index_digits: [1, 4, 2, I]
    },
    choices: { code_style: [["default", "exact"], "default"] }
  },
  machine_spot: {
    label: "Місце під верстат",
    cells: false,
    params: { length: [0.3, 30, 3, F], width: [0.3, 30, 1.5, F] },
    service: true
  },
  zone: { label: "Зона-контур", cells: false, params: {}, polygon: true }
};
var SERVICE_SIDES = ["front", "back", "left", "right"];
var OVERRIDE_KEYS = ["disabled", "max_load_kg", "capacity", "name"];
function normalizeParams(template, params) {
  const spec = SLOT_TEMPLATES[template];
  const src = params || {};
  const out = {};
  if (!spec) {
    return out;
  }
  for (const [key, [, , def]] of Object.entries(spec.params)) {
    out[key] = src[key] ?? def;
  }
  for (const [key, [, def]] of Object.entries(spec.choices || {})) {
    out[key] = src[key] ?? def;
  }
  if (spec.service) {
    out.service = {};
    for (const s of SERVICE_SIDES) {
      out.service[s] = (src.service || {})[s] ?? 0;
    }
  }
  if (spec.polygon) {
    out.polygon = (src.polygon || []).map((p) => [Number(p[0]), Number(p[1])]);
  }
  return out;
}
function footprint(template, params) {
  const p = normalizeParams(template, params);
  switch (template) {
    case "pallet_rack":
      return { l: p.bays * p.bay_width, w: p.depth };
    case "cantilever":
      return { l: p.length, w: p.arm_length };
    case "shelf":
      return { l: p.sections * p.cell_w, w: p.cell_d };
    case "floor_stack":
      return { l: p.cols * p.cell_l, w: p.rows * p.cell_w };
    case "machine_spot":
      return { l: p.length, w: p.width };
    default: {
      const xs = p.polygon.map((q) => q[0]);
      const ys = p.polygon.map((q) => q[1]);
      return xs.length ? { l: Math.max(...xs) - Math.min(...xs), w: Math.max(...ys) - Math.min(...ys) } : { l: 0, w: 0 };
    }
  }
}
function slotObb(template, params, x, y, rot) {
  const { l, w } = footprint(template, params);
  if (template === "zone") {
    const poly = normalizeParams(template, params).polygon;
    const xs = poly.map((q) => q[0]);
    const ys = poly.map((q) => q[1]);
    return makeObb((Math.max(...xs) + Math.min(...xs)) / 2, (Math.max(...ys) + Math.min(...ys)) / 2, l / 2, w / 2, 0);
  }
  return makeObb(x, y, l / 2, w / 2, rot);
}
var width = (count, digits = 2) => Math.max(digits, String(count).length);
var zpad = (n, w) => String(n).padStart(w, "0");
var letter = (n) => String.fromCharCode(64 + n);
function rawCells(template, p, prefix) {
  const cells = rawCellsStyled(template, p, prefix);
  if (p.code_style === "exact" && cells.length === 1) {
    cells[0].code = prefix;
  }
  return cells;
}
function rawCellsStyled(template, p, prefix) {
  const cells = [];
  if (template === "pallet_rack") {
    const length = p.bays * p.bay_width;
    const wn = width(p.bays, p.index_digits);
    for (let bay = 1; bay <= p.bays; bay++) {
      for (let lvl = 1; lvl <= p.levels; lvl++) {
        cells.push({
          code: p.code_style === "bay_letter" ? `${prefix}-${zpad(bay, wn)}${letter(lvl)}` : `${prefix}-B${zpad(bay, wn)}-L${lvl}`,
          level: lvl,
          index: bay,
          lx: -length / 2 + (bay - 0.5) * p.bay_width,
          ly: 0,
          dz: (lvl - 1) * p.level_height,
          l: p.bay_width,
          w: p.depth,
          h: p.level_height,
          capacity: Number(p.positions_per_bay),
          max_load_kg: p.max_load_kg,
          kind: "pallet_cell"
        });
      }
    }
  } else if (template === "cantilever") {
    const length = p.length;
    const armL = length / p.arms;
    const wn = width(p.arms, p.index_digits);
    for (let arm = 1; arm <= p.arms; arm++) {
      for (let lvl = 1; lvl <= p.levels; lvl++) {
        cells.push({
          code: `${prefix}-A${zpad(arm, wn)}-L${lvl}`,
          level: lvl,
          index: arm,
          lx: -length / 2 + (arm - 0.5) * armL,
          ly: 0,
          dz: (lvl - 1) * p.level_height,
          l: armL,
          w: p.arm_length,
          h: p.level_height,
          capacity: 0,
          max_load_kg: p.max_load_kg,
          kind: "shelf"
        });
      }
    }
  } else if (template === "shelf") {
    const length = p.sections * p.cell_w;
    const wn = width(p.sections, p.index_digits);
    for (let sec = 1; sec <= p.sections; sec++) {
      for (let lvl = 1; lvl <= p.shelves; lvl++) {
        cells.push({
          code: `${prefix}-S${zpad(sec, wn)}-L${lvl}`,
          level: lvl,
          index: sec,
          lx: -length / 2 + (sec - 0.5) * p.cell_w,
          ly: 0,
          dz: (lvl - 1) * p.cell_h,
          l: p.cell_w,
          w: p.cell_d,
          h: p.cell_h,
          capacity: 0,
          max_load_kg: 0,
          kind: p.loc_kind
        });
      }
    }
  } else if (template === "floor_stack") {
    const length = p.cols * p.cell_l;
    const wid = p.rows * p.cell_w;
    const wn = width(p.rows, p.index_digits);
    for (let row = 1; row <= p.rows; row++) {
      for (let col = 1; col <= p.cols; col++) {
        cells.push({
          code: `${prefix}-${zpad(row, wn)}${letter(col)}`,
          level: 1,
          index: (row - 1) * p.cols + col,
          lx: -length / 2 + (col - 0.5) * p.cell_l,
          ly: -wid / 2 + (row - 0.5) * p.cell_w,
          dz: 0,
          l: p.cell_l,
          w: p.cell_w,
          h: p.max_height,
          capacity: 0,
          max_load_kg: 0,
          kind: "stack"
        });
      }
    }
  }
  return cells;
}
function generateCells(template, prefix, x, y, rot, params, overrides, elevation = 0) {
  const spec = SLOT_TEMPLATES[template];
  if (!spec || !spec.cells) {
    return [];
  }
  const p = normalizeParams(template, params);
  const ovs = overrides || {};
  const out = [];
  for (const raw of rawCells(template, p, prefix)) {
    const ov = ovs[raw.code] || {};
    if (ov.disabled) {
      continue;
    }
    const [wx, wy] = rotate(raw.lx, raw.ly, rot);
    out.push({
      code: raw.code,
      name: ov.name || raw.code,
      template,
      level: raw.level,
      index: raw.index,
      x: x + wx,
      y: y + wy,
      z0: elevation + raw.dz,
      l: raw.l,
      w: raw.w,
      h: raw.h,
      rot: Number(rot),
      capacity: ov.capacity ?? raw.capacity,
      max_load_kg: ov.max_load_kg ?? raw.max_load_kg,
      kind: raw.kind
    });
  }
  return out;
}
var countCells = (template, prefix, params, overrides) => generateCells(template, prefix, 0, 0, 0, params, overrides, 0).length;
var cache = /* @__PURE__ */ new Map();
function cellsOf(s) {
  const sig = [s.template, s.code_prefix, JSON.stringify(s.params), JSON.stringify(s.overrides || {})].join("|");
  const hit = cache.get(s.id);
  if (hit && hit.sig === sig) {
    return hit.cells;
  }
  const spec = SLOT_TEMPLATES[s.template];
  let cells = [];
  if (spec && spec.cells) {
    const ovs = s.overrides || {};
    cells = rawCells(s.template, normalizeParams(s.template, s.params), s.code_prefix || "").map((c) => {
      const ov = ovs[c.code];
      const r = { ...c };
      if (ov) {
        r.ov = true;
        r.disabled = !!ov.disabled;
        if (ov.capacity != null) {
          r.capacity = ov.capacity;
        }
        if (ov.max_load_kg != null) {
          r.max_load_kg = ov.max_load_kg;
        }
        if (ov.name) {
          r.name = ov.name;
        }
      }
      return r;
    });
  }
  if (cache.size > 400) {
    cache.clear();
  }
  cache.set(s.id, { sig, cells });
  return cells;
}
var cellCount = (s) => cellsOf(s).filter((c) => !c.disabled).length;
var clearCellsCache = () => cache.clear();

// core/constructor/data.js
var ROLES = [
  { id: "manager", name: "Менеджер" },
  { id: "technologist", name: "Технолог" },
  { id: "storekeeper", name: "Комірник" },
  { id: "engineer", name: "Інженер" }
];
var roleName = (id) => (ROLES.find((r) => r.id === id) || { name: id }).name;
var LAYER_KINDS = {
  building: "Будівля",
  storage: "Склади",
  production: "Виробництво",
  engineering: "Інженерні мережі",
  yard: "Двір",
  custom: "Свій шар"
};
var CATEGORIES = {
  machine: "Верстат",
  rack: "Стелаж",
  forklift: "Навантажувач",
  conveyor: "Конвеєр",
  panel: "Шафа / щит",
  robot: "Робот",
  other: "Інше"
};
var UTIL_KINDS = { electric: "Електрика", air: "Стиснене повітря", dust: "Аспірація" };
var LAYER_UTIL_KINDS = { ...UTIL_KINDS, panel: "Щит" };
var FRONT_SIDES = { s: "Низ креслення (−Y)", e: "Праворуч (+X)", n: "Верх креслення (+Y)", w: "Ліворуч (−X)" };
var FRONT_ANGLE = { s: 0, e: 90, n: 180, w: 270 };
var range = (tpl, k) => {
  const [min, max, def, type] = SLOT_TEMPLATES[tpl].params[k];
  return { min, max: max ?? 1e5, def, int: type === "int" ? 1 : 0 };
};
var num = (tpl, k, l, u, step) => ({ k, l, u, step, ...range(tpl, k) });
var TPL = {
  pallet_rack: {
    name: "Палетний стелаж",
    prefix: "R1",
    info: "Прольоти × яруси → комірки ПРЕФІКС-B01-L1",
    params: [
      num("pallet_rack", "bays", "Прольотів", null, 1),
      num("pallet_rack", "levels", "Ярусів", null, 1),
      num("pallet_rack", "bay_width", "Ширина прольоту", "м", 0.05),
      num("pallet_rack", "depth", "Глибина", "м", 0.05),
      num("pallet_rack", "level_height", "Висота ярусу", "м", 0.05),
      num("pallet_rack", "positions_per_bay", "Місць у прольоті", null, 1),
      num("pallet_rack", "max_load_kg", "Макс. навантаження на ярус", "кг", 50),
      num("pallet_rack", "index_digits", "Розрядів у номері", null, 1),
      { k: "code_style", l: "Стиль кодів", type: "select", options: [["default", "B01-L1"], ["bay_letter", "1A (проліт+ярус)"], ["exact", "Один код = префікс"]], def: "default" }
    ]
  },
  cantilever: {
    name: "Консольний стелаж",
    prefix: "CL1",
    info: "Секції × яруси консолей",
    params: [
      num("cantilever", "arms", "Секцій консолей", null, 1),
      num("cantilever", "levels", "Ярусів", null, 1),
      num("cantilever", "arm_length", "Виліт консолі", "м", 0.05),
      num("cantilever", "length", "Довжина", "м", 0.1),
      num("cantilever", "level_height", "Висота ярусу", "м", 0.05),
      num("cantilever", "max_load_kg", "Макс. навантаження на ярус", "кг", 50),
      num("cantilever", "index_digits", "Розрядів у номері", null, 1)
    ]
  },
  shelf: {
    name: "Полицевий стелаж / комірки",
    prefix: "SH1",
    info: "Секції × полиці → комірки PREFIX-S01-L1",
    params: [
      num("shelf", "sections", "Секцій", null, 1),
      num("shelf", "shelves", "Полиць", null, 1),
      num("shelf", "cell_w", "Ширина комірки", "м", 0.05),
      num("shelf", "cell_d", "Глибина комірки", "м", 0.05),
      num("shelf", "cell_h", "Висота комірки", "м", 0.05),
      num("shelf", "index_digits", "Розрядів у номері", null, 1),
      { k: "loc_kind", l: "Вид локацій", type: "select", options: [["bin", "Комірка (bin)"], ["shelf", "Полиця (shelf)"]], def: "bin" }
    ]
  },
  floor_stack: {
    name: "Напільне штабелювання",
    prefix: "ST1",
    info: "Рядки × колонки → місця під стос (PREFIX-01A)",
    params: [
      num("floor_stack", "rows", "Рядів", null, 1),
      num("floor_stack", "cols", "Колонок", null, 1),
      num("floor_stack", "cell_l", "Довжина місця", "м", 0.05),
      num("floor_stack", "cell_w", "Ширина місця", "м", 0.05),
      num("floor_stack", "max_height", "Макс. висота стосу", "м", 0.1),
      num("floor_stack", "index_digits", "Розрядів у номері", null, 1),
      { k: "code_style", l: "Стиль кодів", type: "select", options: [["default", "PREFIX-01A"], ["exact", "Один код = префікс"]], def: "default" }
    ]
  },
  machine_spot: {
    name: "Місце під верстат",
    prefix: "MS1",
    info: "Габарит місця й зона обслуговування",
    params: [
      num("machine_spot", "length", "Довжина", "м", 0.1),
      num("machine_spot", "width", "Ширина", "м", 0.1),
      { k: "service.front", l: "Обслуговування спереду", u: "м", min: 0, max: 8, step: 0.1 },
      { k: "service.back", l: "Ззаду", u: "м", min: 0, max: 8, step: 0.1 },
      { k: "service.left", l: "Зліва", u: "м", min: 0, max: 8, step: 0.1 },
      { k: "service.right", l: "Справа", u: "м", min: 0, max: 8, step: 0.1 }
    ]
  },
  zone: {
    name: "Зона-контур",
    prefix: "Z1",
    info: "Прямокутний контур-розмітка зони",
    params: [
      { k: "length", l: "Довжина", u: "м", min: 0.5, max: 150, step: 0.1 },
      { k: "width", l: "Ширина", u: "м", min: 0.5, max: 150, step: 0.1 },
      { k: "title", l: "Назва зони", type: "text" },
      { k: "color", l: "Колір", type: "color" }
    ]
  }
};
function defaultParams(template) {
  if (template === "zone") {
    return { length: 10, width: 8, title: "Нова зона", color: "#9fb7c9" };
  }
  if (template === "machine_spot") {
    return { length: 6, width: 4, service: { front: 1.5, back: 0.5, left: 0.5, right: 0.5 } };
  }
  const out = {};
  for (const p of TPL[template].params) {
    out[p.k] = p.def;
  }
  return out;
}
var SOLID_SLOTS = ["pallet_rack", "cantilever", "shelf", "floor_stack"];
var CHECKS = [
  { id: "fits", name: "Вміщується в місце", hint: "У межах місця, будівлі чи контуру шару; дозволені шар і поворот" },
  { id: "collide", name: "Немає перетинів", hint: "Габарит не перетинає інші об’єкти шару (OBB, SAT)" },
  { id: "service_free", name: "Зона обслуговування вільна", hint: "Розширений зоною обслуговування прямокутник не зачіпає чужі габарити" },
  { id: "aisles_free", name: "Проходи не перекриті", hint: "Габарит не перетинає проходи шару" },
  { id: "load", name: "Навантаження в нормі", hint: "Вага на площу ≤ ліміту шару; для комірки стелажа ≤ max_load_kg" },
  { id: "utility_reach", name: "Підключення досяжне", hint: "До найближчої точки потрібного виду не далі N м" },
  { id: "fire", name: "Пожежні проходи й виходи", hint: "Не перекриті пожежні проходи та зони перед виходами" }
];
function slotHeight(s) {
  const p = s.params || {};
  switch (s.template) {
    case "pallet_rack":
    case "cantilever":
      return (p.levels || 1) * (p.level_height || 1.5) + 0.25;
    case "shelf":
      return (p.shelves || 1) * (p.cell_h || 0.4) + 0.1;
    case "floor_stack":
      return p.max_height || 1.5;
    case "machine_spot":
      return 0.05;
    default:
      return 0.02;
  }
}
function rotationsList(v) {
  switch (v && v.rotations) {
    case "q":
      return [0, 90, 180, 270];
    case "h":
      return [0, 180];
    case "z":
      return [0];
    default:
      return null;
  }
}
var newLayerDefaults = () => ({
  name: "Новий шар",
  kind: "custom",
  elevation: 3,
  grid_step: 0.5,
  aisle_width: 3,
  max_floor_load: 10,
  bounds: null,
  slot_types: Object.keys(TPL),
  edit_roles: ["manager"],
  edit_groups: [],
  color: "#9a6bb3",
  opacity: 0.6,
  style: "solid",
  visible: true,
  aisles: [],
  fire_paths: [],
  utilities: [],
  underlay: null
});

// core/constructor/dialogs.js
var dialogs_exports = {};
__export(dialogs_exports, {
  askConflict: () => askConflict,
  confirmBox: () => confirmBox,
  openDialog: () => openDialog,
  openHistory: () => openHistory,
  openNewSite: () => openNewSite,
  openServerIssues: () => openServerIssues
});

// core/constructor/roles.js
var roles_exports = {};
__export(roles_exports, {
  ROLES: () => ROLES,
  canCatalog: () => canCatalog,
  canEditLayer: () => canEditLayer,
  canManage: () => canManage,
  canPublish: () => canPublish,
  layerRoleNames: () => layerRoleNames,
  lockHint: () => lockHint,
  myRoleNames: () => myRoleNames,
  toastLock: () => toastLock,
  viewAs: () => viewAs
});

// core/constructor/state.js
var state_exports = {};
__export(state_exports, {
  E: () => E,
  S: () => S,
  V: () => V,
  elevOf: () => elevOf,
  isLayerVisible: () => isLayerVisible,
  layerOf: () => layerOf,
  objKey: () => objKey,
  passportOf: () => passportOf,
  recOfRef: () => recOfRef,
  reindex: () => reindex,
  resetState: () => resetState,
  snapStep: () => snapStep,
  snapV: () => snapV,
  variantOf: () => variantOf
});

// core/constructor/util.js
var util_exports = {};
__export(util_exports, {
  $: () => $,
  $$: () => $$,
  K: () => K,
  ROOT: () => ROOT,
  clamp: () => clamp,
  clone: () => clone,
  debounce: () => debounce,
  fmt: () => fmt,
  fmtDate: () => fmtDate,
  fmtInt: () => fmtInt,
  fmtSize: () => fmtSize,
  getp: () => getp,
  h: () => h,
  ic: () => ic,
  normDeg: () => normDeg,
  pad2: () => pad2,
  rad: () => rad,
  rnd: () => rnd,
  setp: () => setp,
  sleep: () => sleep,
  toast: () => toast,
  uid: () => uid
});
var ROOT = { el: null };
var $ = (s, r) => (r || ROOT.el)?.querySelector(s) || null;
var $$ = (s, r) => Array.from((r || ROOT.el)?.querySelectorAll(s) || []);
var K = (...a) => a.flat(Infinity).filter((x) => x != null && x !== false);
function h(tag, attrs, ...kids) {
  const el = document.createElement(tag);
  let val;
  if (attrs) {
    for (const k in attrs) {
      const v = attrs[k];
      if (v == null || v === false) {
        continue;
      }
      if (k === "class") {
        el.className = v;
      } else if (k === "style" && typeof v === "object") {
        Object.assign(el.style, v);
      } else if (k.startsWith("on") && typeof v === "function") {
        el.addEventListener(k.slice(2), v);
      } else if (k === "value") {
        val = v;
      } else if (k === "checked" || k === "disabled" || k === "selected" || k === "hidden" || k === "indeterminate") {
        el[k] = !!v;
      } else if (k === "html") {
        el.innerHTML = v;
      } else {
        el.setAttribute(k, v === true ? "" : v);
      }
    }
  }
  for (const c of K(kids)) {
    el.append(c.nodeType ? c : document.createTextNode(String(c)));
  }
  if (val !== void 0) {
    el.value = val;
  }
  return el;
}
var ic = (n) => h("span", { class: "ic", "aria-hidden": "true", html: `<svg><use href="#i-${n}"/></svg>` });
var uid = (p) => p + Math.random().toString(36).slice(2, 7) + Date.now().toString(36).slice(-3);
var clone = (o) => JSON.parse(JSON.stringify(o));
var rnd = (v, d = 3) => {
  const k = Math.pow(10, d);
  const r = Math.round(v * k) / k;
  return r === 0 ? 0 : r;
};
var fmt = (n, d = 1) => {
  if (n == null || !isFinite(n)) {
    return "—";
  }
  const s = Number(n).toFixed(d);
  return (s === "-0" || /^-0\.0+$/.test(s) ? s.slice(1) : s).replace(".", ",");
};
var fmtInt = (n) => Math.round(n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, " ");
var rad = (a) => a * Math.PI / 180;
var pad2 = (n) => String(n).padStart(2, "0");
var clamp = (v, a, b) => Math.min(b, Math.max(a, v));
var debounce = (fn, ms) => {
  let t;
  const f = (...a) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...a), ms);
  };
  f.cancel = () => clearTimeout(t);
  return f;
};
var sleep = (ms) => new Promise((r) => setTimeout(r, ms));
var getp = (o, path) => path.split(".").reduce((a, k) => a == null ? a : a[k], o);
var setp = (o, path, v) => {
  const ks = path.split(".");
  let a = o;
  while (ks.length > 1) {
    const k = ks.shift();
    a = a[k] = a[k] || {};
  }
  a[ks[0]] = v;
};
var normDeg = (a) => (a % 360 + 360) % 360;
var fmtDate = (iso) => {
  try {
    const d = new Date(String(iso).includes("T") ? iso : String(iso).replace(" ", "T") + "Z");
    return d.toLocaleString("uk-UA", { dateStyle: "short", timeStyle: "short" });
  } catch {
    return iso;
  }
};
var fmtSize = (b) => b >= 1048576 ? fmt(b / 1048576, 1) + " МБ" : b >= 1024 ? fmt(b / 1024, 0) + " КБ" : b + " Б";
function toast(msg, kind) {
  const box = $("#toast");
  if (!box) {
    return null;
  }
  const t = h("div", { class: "ftoast" + (kind ? " " + kind : "") }, msg);
  box.append(t);
  while (box.children.length > 3) {
    box.firstChild.remove();
  }
  setTimeout(() => t.remove(), kind === "err" || kind === "warn" ? 5200 : 3200);
  return t;
}

// core/constructor/state.js
var E = {};
var initialS = () => ({
  app: { sites: [], active: null, mode: "edit", viewAs: null },
  site: null,
  layers: [],
  slots: [],
  placements: [],
  catalog: [],
  settings: { checks: {}, reach_n: 15, labels: true },
  versions: [],
  rights: { is_manager: false, roles: [], editable_layer_ids: [], can_publish: false, can_edit_catalog: false },
  sel: null,
  selCell: null,
  edit: null,
  issues: { list: [], byKey: /* @__PURE__ */ new Map() },
  ui: { leftTab: "layers", layer: null },
  vIdx: /* @__PURE__ */ new Map(),
  lIdx: /* @__PURE__ */ new Map(),
  sIdx: /* @__PURE__ */ new Map(),
  pIdx: /* @__PURE__ */ new Map(),
  changed: 0,
  saveState: "saved"
  // saved | saving | error
});
var S = initialS();
var initialV = () => ({
  ok: false,
  testMode: false,
  renderer: null,
  scene: null,
  camera: null,
  controls: null,
  canvas: null,
  raf: 0,
  world: null,
  views: /* @__PURE__ */ new Map(),
  decor: /* @__PURE__ */ new Map(),
  underlays: /* @__PURE__ */ new Map(),
  uldata: /* @__PURE__ */ new Map(),
  pick: [],
  labels: [],
  theme: "light",
  col: {},
  mat: {},
  geo: {},
  bodyMats: /* @__PURE__ */ new Map(),
  labelCache: /* @__PURE__ */ new Map(),
  ruler: { on: false, pts: [], objs: [] },
  placing: null,
  drag: null,
  models: /* @__PURE__ */ new Map(),
  staticSig: "",
  pickMode: null,
  hoverKey: null,
  cursor: { x: 0, y: 0 },
  buildingG: null,
  hidden: /* @__PURE__ */ new Set()
  // шари, приховані в цьому сеансі (видимість — клієнтська, на сервер не пишеться)
});
var V = initialV();
function resetState() {
  for (const o of [S, V]) {
    for (const k of Object.keys(o)) {
      delete o[k];
    }
  }
  Object.assign(S, initialS());
  Object.assign(V, initialV());
}
function reindex() {
  S.vIdx.clear();
  S.lIdx.clear();
  S.sIdx.clear();
  S.pIdx.clear();
  for (const p of S.catalog) {
    for (const v of p.variants) {
      S.vIdx.set(v.id, { v, p });
    }
  }
  for (const l of S.layers) {
    S.lIdx.set(l.id, l);
  }
  for (const s of S.slots) {
    S.sIdx.set(s.id, s);
  }
  for (const p of S.placements) {
    S.pIdx.set(p.id, p);
  }
}
var layerOf = (id) => S.lIdx.get(id);
var variantOf = (id) => (S.vIdx.get(id) || {}).v;
var passportOf = (id) => (S.vIdx.get(id) || {}).p;
var elevOf = (layerId) => (layerOf(layerId) || { elevation: 0 }).elevation;
var objKey = (kind, id) => (kind === "placement" ? "p:" : "s:") + id;
var recOfRef = (ref2) => ref2.kind === "placement" ? S.pIdx.get(ref2.id) : S.sIdx.get(ref2.id);
var snapStep = (rec) => (layerOf(rec.layer_id) || { grid_step: 0.5 }).grid_step || 0.5;
var snapV = (v, st) => rnd(Math.round(v / st) * st, 4);
var isLayerVisible = (ly) => !V.hidden.has(ly.id);

// core/constructor/roles.js
var viewAs = () => S.rights.is_manager && S.app.viewAs && S.app.viewAs !== "manager" ? S.app.viewAs : null;
function canEditLayer(ly) {
  if (!ly || S.app.mode !== "edit") {
    return false;
  }
  const va = viewAs();
  if (va) {
    return (ly.edit_roles || []).includes(va);
  }
  if (S.rights.is_manager) {
    return true;
  }
  return ly.rid != null && (S.rights.editable_layer_ids || []).includes(ly.rid);
}
var canManage = () => S.app.mode === "edit" && S.rights.is_manager && !viewAs();
var canCatalog = () => {
  if (S.app.mode !== "edit") {
    return false;
  }
  const va = viewAs();
  return va ? va === "technologist" : !!(S.rights.is_manager || S.rights.can_edit_catalog);
};
var canPublish = () => canManage() && !!S.rights.can_publish;
var layerRoleNames = (ly) => (ly.edit_roles || []).filter((r) => r !== "manager").map(roleName);
function lockHint(ly) {
  if (S.app.mode !== "edit") {
    return "Режим перегляду: правка вимкнена. Увімкніть «Редагування».";
  }
  const rs = layerRoleNames(ly);
  return `Шар «${ly.name}» редагує ${rs.length ? rs.join(", ") + " і Менеджер" : "Менеджер"}`;
}
var toastLock = (ly) => toast(lockHint(ly), "warn");
var myRoleNames = () => {
  const rs = S.rights.roles || [];
  return rs.length ? rs.map(roleName).join(", ") : "Без ролі";
};

// core/constructor/dialogs.js
function openDialog(o) {
  const dlg = h("dialog", { class: o.cls || "" });
  const close = (r) => {
    dlg.returnValue = r || "";
    dlg.close();
  };
  dlg.append(
    ...K(
      h("div", { class: "dh" }, h("h2", null, o.title), h("button", { class: "xbtn", type: "button", "aria-label": "Закрити", onclick: () => close("") }, ic("x"))),
      h("div", { class: "db" }, o.body),
      o.actions && o.actions.length ? h(
        "div",
        { class: "df" },
        o.actions.map(
          (a) => h(
            "button",
            {
              class: "fbtn " + (a.cls || ""),
              type: "button",
              disabled: a.disabled,
              id: a.id,
              onclick: async () => {
                const r = a.onClick ? await a.onClick(dlg) : void 0;
                if (r !== false) {
                  close(a.value || "ok");
                }
              }
            },
            a.label
          )
        )
      ) : null
    )
  );
  dlg.addEventListener("close", () => {
    if (o.onClose) {
      o.onClose(dlg.returnValue);
    }
    dlg.remove();
  });
  dlg.addEventListener("click", (e) => {
    if (e.target === dlg && o.light) {
      close("");
    }
  });
  ($("#app") || document.body).append(dlg);
  dlg.showModal();
  dlg.close2 = close;
  return dlg;
}
function confirmBox(o) {
  return new Promise((res) => {
    let done = false;
    openDialog({
      title: o.title,
      cls: "narrow",
      body: h("p", { style: { margin: 0 } }, o.text),
      actions: [
        { label: o.cancel || "Скасувати", value: "no" },
        { label: o.ok || "Так", cls: o.danger ? "danger" : "primary", value: "yes", id: "dlgYes", onClick: () => {
          done = true;
        } }
      ],
      onClose: () => res(done)
    });
  });
}
function openNewSite() {
  const name = h("input", { type: "text", value: "Нова площадка", "aria-label": "Назва", id: "newSiteName" });
  const code = h("input", { type: "text", value: "", maxlength: 16, "aria-label": "Код", id: "newSiteCode", placeholder: "напр. MAIN" });
  code.addEventListener("input", () => {
    code.value = code.value.toUpperCase().replace(/[^A-Z0-9]/g, "");
  });
  const dim = (v, label, id) => h("input", { type: "number", value: v, min: 5, step: 1, "aria-label": label, id });
  const l = dim(60, "Довжина", "newSiteL");
  const w = dim(30, "Ширина", "newSiteW");
  const hh = dim(8, "Висота", "newSiteH");
  const lab = (t, el) => h("label", { class: "fld" }, h("span", null, t), el);
  openDialog({
    title: "Нова площадка",
    cls: "narrow",
    body: h(
      "div",
      { class: "fcol" },
      lab("Назва", name),
      lab("Код (великі латинські літери й цифри, до 16)", code),
      h("div", { class: "grid3" }, lab("Довжина, м", l), lab("Ширина, м", w), lab("Висота, м", hh)),
      h("div", { class: "small muted" }, "Створюється порожня площадка: п’ять базових шарів і каталог типових варіантів.")
    ),
    actions: [
      { label: "Скасувати" },
      {
        label: "Створити",
        cls: "primary",
        id: "dlgCreateSite",
        onClick: async () => {
          if (!name.value.trim() || !code.value) {
            toast("Вкажіть назву й код площадки.", "warn");
            return false;
          }
          const ok = await E.createSite({ name: name.value.trim(), code: code.value, building: { l: +l.value, w: +w.value, h: +hh.value } });
          return ok ? void 0 : false;
        }
      }
    ]
  });
}
function openHistory() {
  const body = h("div");
  const dlg = openDialog({ title: "Історія версій", cls: "narrow", body, actions: [{ label: "Закрити" }] });
  const render2 = () => {
    const vs = [...S.versions].sort((a, b) => b.n - a.n);
    const act = S.site.active_version ? S.site.active_version.n : null;
    body.replaceChildren(
      ...K(
        h("div", { class: "small muted", style: { marginBottom: "6px" } }, "Повернення змінює чернетку; записи Odoo (локації, обладнання) не змінюються, доки ви не опублікуєте нову версію."),
        vs.length ? vs.map(
          (v) => h(
            "div",
            { class: "ver" },
            h("div", { class: "vn" }, "v" + v.n),
            h(
              "div",
              { class: "vi" },
              h("div", null, fmtDate(v.published_at) + " · " + v.by, v.n === act ? h("span", { class: "fbadge ok", style: { marginLeft: "8px" } }, "активна") : null),
              h("div", { class: "small" }, v.note || "без нотатки"),
              v.counts ? h("div", { class: "small muted mono" }, `${v.counts.layers} шарів · ${v.counts.slots} місць · ${v.counts.cells} комірок · ${v.counts.placements} обл.`) : null
            ),
            h(
              "button",
              {
                class: "fbtn sm",
                type: "button",
                "data-version": v.id,
                disabled: !canManage(),
                title: canManage() ? "" : "Повертає Менеджер у режимі редагування",
                onclick: async () => {
                  const ok = await confirmBox({ title: `Повернути чернетку до v${v.n}?`, text: "Поточна чернетка буде замінена знімком версії. Незбережені зміни пропадуть.", ok: "Повернути", danger: true });
                  if (!ok) {
                    return;
                  }
                  await E.restoreVersion(v.id, v.n);
                  dlg.close2("");
                }
              },
              "Повернути чернетку"
            )
          )
        ) : h("div", { class: "empty" }, "Версій ще немає. Натисніть «Опублікувати».")
      )
    );
  };
  render2();
}
function openServerIssues(res) {
  const issues = res.issues || [];
  const name = (c) => (CHECKS.find((x) => x.id === c) || {}).name || c;
  openDialog({
    title: "Перевірка на сервері",
    cls: "narrow",
    body: h(
      "div",
      { class: "fcol" },
      h("div", { class: "frow" }, res.summary.block ? h("span", { class: "fbadge b" }, res.summary.block + " заборон") : null, res.summary.warn ? h("span", { class: "fbadge w" }, res.summary.warn + " попер.") : null, !issues.length ? h("span", { class: "fbadge ok" }, "усе гаразд") : null),
      h(
        "div",
        { class: "issues", id: "serverIssues" },
        issues.map((i) => h("div", { class: "issue " + i.severity }, h("div", { class: "im" }, i.message, h("div", { class: "io" }, (i.severity === "block" ? "ЗАБОРОНА" : "ПОПЕРЕДЖЕННЯ") + " · " + name(i.check)))))
      )
    ),
    actions: [{ label: "Закрити" }]
  });
}
function askConflict() {
  return new Promise((res) => {
    let choice = "theirs";
    openDialog({
      title: "Запис змінив інший користувач",
      cls: "narrow",
      body: h("p", { style: { margin: 0 } }, "Об’єкт на сервері новіший за ваш. Залишити вашу версію чи взяти серверну (ваші зміни цього об’єкта буде втрачено)?"),
      actions: [
        { label: "Взяти серверне", value: "theirs", id: "dlgTheirs" },
        { label: "Залишити моє", cls: "primary", value: "mine", id: "dlgMine", onClick: () => {
          choice = "mine";
        } }
      ],
      onClose: () => res(choice)
    });
  });
}
Object.assign(E, { openDialog, confirmBox, openNewSite, openHistory, openServerIssues, askConflict });
registries.dialogs.add("confirm", (o) => confirmBox(o), { force: true });
registries.dialogs.add("newSite", () => openNewSite(), { force: true });
registries.dialogs.add("history", () => openHistory(), { force: true });
registries.dialogs.add("serverIssues", ({ res }) => openServerIssues(res), { force: true });
registries.dialogs.add("conflict", () => askConflict(), { force: true });

// core/constructor/dxf.js
var dxf_exports = {};
__export(dxf_exports, {
  DWG_MESSAGE: () => DWG_MESSAGE,
  DXF_MAX_BYTES: () => DXF_MAX_BYTES,
  DXF_MAX_SEGMENTS: () => DXF_MAX_SEGMENTS,
  DXF_PARSER_URL: () => DXF_PARSER_URL,
  defaultUnderlayParams: () => defaultUnderlayParams,
  importUnderlayFile: () => importUnderlayFile,
  loadDxfParser: () => loadDxfParser,
  loadUnderlays: () => loadUnderlays,
  openDxfPanel: () => openDxfPanel,
  parseDxf: () => parseDxf,
  renderDxfPanel: () => renderDxfPanel
});

// core/constructor/fields.js
function numInput(o) {
  const el = h("input", {
    type: "number",
    step: o.step == null ? "any" : o.step,
    min: o.min,
    max: o.max,
    value: o.value == null ? "" : String(rnd(o.value, 4)),
    disabled: o.dis,
    "data-f": o.f,
    inputmode: "decimal",
    "aria-label": o.label
  });
  if (!o.dis) {
    el.addEventListener("focus", () => o.begin && o.begin());
    el.addEventListener("input", () => {
      if (el.value === "" || el.validity.badInput) {
        return;
      }
      let v = parseFloat(el.value);
      if (!isFinite(v)) {
        return;
      }
      if (o.int) {
        v = Math.round(v);
      }
      if (o.min != null && v < o.min - 1e-9) {
        return;
      }
      if (o.max != null && v > o.max + 1e-9) {
        return;
      }
      o.set(v);
    });
    el.addEventListener("change", () => o.end && o.end());
  }
  return el;
}
var fld = (label, el, unit, cls) => h("label", { class: "fld" + (cls ? " " + cls : "") }, h("span", null, label, unit ? h("i", null, " · " + unit) : null), el);
function textInput(o) {
  const el = h("input", { type: "text", value: o.value == null ? "" : o.value, disabled: o.dis, "aria-label": o.label, "data-f": o.f });
  if (!o.dis) {
    el.addEventListener("focus", () => o.begin && o.begin());
    el.addEventListener("input", () => o.set(el.value));
    el.addEventListener("change", () => o.end && o.end());
  }
  return el;
}
function selectEl(opts, value, onChange, dis, label) {
  const el = h(
    "select",
    { disabled: dis, "aria-label": label },
    opts.map(([v, t]) => h("option", { value: v, selected: String(v) === String(value) }, t))
  );
  el.addEventListener("change", () => onChange(el.value));
  return el;
}
function checkGroup(opts, vals, onChange, dis) {
  return h(
    "div",
    { class: "checks" },
    opts.map(([v, t]) => {
      const cb = h("input", { type: "checkbox", checked: vals.includes(v), disabled: dis });
      cb.addEventListener("change", () => {
        const cur = new Set(vals);
        if (cb.checked) {
          cur.add(v);
        } else {
          cur.delete(v);
        }
        onChange([...cur]);
      });
      return h("label", null, cb, t);
    })
  );
}
function paramFields(tpl, params, o) {
  const spec = TPL[tpl];
  return h(
    "div",
    { class: "grid2" },
    spec.params.map((p) => {
      const val = getp(params, p.k) ?? p.def;
      const common = { dis: o.dis, label: p.l, begin: o.begin, end: o.end };
      if (p.type === "text") {
        return fld(p.l, textInput({ ...common, value: val, set: (v) => {
          setp(params, p.k, v);
          o.onChange();
        } }), null, "span2");
      }
      if (p.type === "select") {
        return fld(p.l, selectEl(p.options, val, (v) => {
          o.begin && o.begin();
          setp(params, p.k, v);
          o.onChange();
          o.end && o.end();
        }, o.dis, p.l), p.u);
      }
      if (p.type === "color") {
        const c = h("input", { type: "color", value: val || "#9fb7c9", disabled: o.dis, "aria-label": p.l });
        c.addEventListener("focus", () => o.begin && o.begin());
        c.addEventListener("input", () => {
          setp(params, p.k, c.value);
          o.onChange();
        });
        c.addEventListener("change", () => o.end && o.end());
        return fld(p.l, c);
      }
      return fld(
        p.l,
        numInput({ ...common, value: val, min: p.min, max: p.max, step: p.step, int: p.int, f: "p." + p.k, set: (v) => {
          setp(params, p.k, v);
          o.onChange();
        } }),
        p.u
      );
    })
  );
}

// core/constructor/host.js
var host = {
  loadThree: null,
  buildGenericModel: null,
  loadLoaders: null,
  themeTarget: null,
  themeKey: "f3d_constructor_theme",
  themeAuto: false,
  onTheme: null,
  siteKey: "f3d_constructor_site",
  dxfParserUrl: null,
  services: {}
};
function setHost(h2 = {}) {
  Object.assign(host, {
    loadThree: null,
    buildGenericModel: null,
    loadLoaders: null,
    themeTarget: null,
    themeKey: "f3d_constructor_theme",
    themeAuto: false,
    onTheme: null,
    siteKey: "f3d_constructor_site",
    dxfParserUrl: null,
    services: {}
  });
  Object.assign(host, h2);
  return host;
}

// core/constructor/dxf.js
var DXF_PARSER_URL = "/td_constructor/static/lib/dxf-parser/dxf-parser.min.js";
var DXF_MAX_BYTES = 5 * 1024 * 1024;
var DXF_MAX_SEGMENTS = 2e5;
var DWG_MESSAGE = "Конвертуйте в DXF; DWG буде на сервері.";
var parserPromise = null;
function loadDxfParser() {
  if (window.DxfParser) {
    return Promise.resolve(window.DxfParser);
  }
  if (!parserPromise) {
    parserPromise = new Promise((resolve, reject) => {
      const el = document.createElement("script");
      el.src = host.dxfParserUrl || DXF_PARSER_URL;
      el.onload = () => resolve(window.DxfParser);
      el.onerror = () => {
        parserPromise = null;
        reject(new Error("Не вдалося завантажити розбирач DXF."));
      };
      document.head.append(el);
    });
  }
  return parserPromise;
}
function parseDxf(text, Parser = window.DxfParser) {
  const dxf = new Parser().parseSync(text);
  const segs = [];
  const line = (x12, y12, x2, y2) => segs.push(x12, y12, x2, y2);
  const arc = (c, r, a0, a1, T) => {
    if (a1 <= a0) {
      a1 += Math.PI * 2;
    }
    const n = Math.max(8, Math.ceil((a1 - a0) / (Math.PI / 24)));
    let px = null;
    let py = null;
    for (let i = 0; i <= n; i++) {
      const a = a0 + (a1 - a0) * i / n;
      const p = T(c.x + r * Math.cos(a), c.y + r * Math.sin(a));
      if (px != null) {
        line(px, py, p[0], p[1]);
      }
      px = p[0];
      py = p[1];
    }
  };
  const bulgeArc = (p, q, b, T) => {
    const dx = q.x - p.x;
    const dy = q.y - p.y;
    const d = Math.hypot(dx, dy);
    if (d < 1e-9) {
      return;
    }
    const th = 4 * Math.atan(b);
    const r = d / (2 * Math.sin(th / 2));
    const off = r * Math.cos(th / 2);
    const cx = (p.x + q.x) / 2 - dy / d * off;
    const cy = (p.y + q.y) / 2 + dx / d * off;
    const a0 = Math.atan2(p.y - cy, p.x - cx);
    const n = Math.max(6, Math.ceil(Math.abs(th) / (Math.PI / 24)));
    let px = null;
    let py = null;
    for (let i = 0; i <= n; i++) {
      const a = a0 + th * i / n;
      const pt = T(cx + Math.abs(r) * Math.cos(a), cy + Math.abs(r) * Math.sin(a));
      if (px != null) {
        line(px, py, pt[0], pt[1]);
      }
      px = pt[0];
      py = pt[1];
    }
  };
  const ent = (e, T, depth) => {
    const pt = (v) => T(v.x, v.y);
    switch (e.type) {
      case "LINE": {
        const a = pt(e.vertices[0]);
        const b = pt(e.vertices[1]);
        line(a[0], a[1], b[0], b[1]);
        break;
      }
      case "LWPOLYLINE":
      case "POLYLINE": {
        const vs = e.vertices || [];
        const n = vs.length;
        for (let i = 0; i < n - 1 + (e.shape ? 1 : 0); i++) {
          const p = vs[i];
          const q = vs[(i + 1) % n];
          if (p.bulge) {
            bulgeArc(p, q, p.bulge, T);
          } else {
            const a = pt(p);
            const b = pt(q);
            line(a[0], a[1], b[0], b[1]);
          }
        }
        break;
      }
      case "CIRCLE":
        arc(e.center, e.radius, 0, Math.PI * 2, T);
        break;
      case "ARC":
        arc(e.center, e.radius, e.startAngle, e.endAngle, T);
        break;
      case "INSERT": {
        const b = dxf.blocks && dxf.blocks[e.name];
        if (!b || !b.entities || depth > 3) {
          break;
        }
        const sx = e.xScale == null ? 1 : e.xScale;
        const sy = e.yScale == null ? 1 : e.yScale;
        const rot = rad(e.rotation || 0);
        const c = Math.cos(rot);
        const s = Math.sin(rot);
        const bp = b.position || { x: 0, y: 0 };
        const p0 = e.position || { x: 0, y: 0 };
        const T2 = (x, y) => {
          const lx = (x - bp.x) * sx;
          const ly = (y - bp.y) * sy;
          return T(p0.x + lx * c - ly * s, p0.y + lx * s + ly * c);
        };
        for (const be of b.entities) {
          ent(be, T2, depth + 1);
        }
        break;
      }
      default:
        break;
    }
  };
  const ident = (x, y) => [x, y];
  for (const e of dxf.entities || []) {
    ent(e, ident, 0);
    if (segs.length >= DXF_MAX_SEGMENTS * 4) {
      break;
    }
  }
  const cap = Math.min(segs.length, DXF_MAX_SEGMENTS * 4);
  const arr = new Float32Array(cap);
  for (let i = 0; i < cap; i++) {
    arr[i] = segs[i];
  }
  let x0 = 1e30;
  let y0 = 1e30;
  let x1 = -1e30;
  let y1 = -1e30;
  for (let i = 0; i < arr.length; i += 2) {
    const x = arr[i];
    const y = arr[i + 1];
    x0 = Math.min(x0, x);
    x1 = Math.max(x1, x);
    y0 = Math.min(y0, y);
    y1 = Math.max(y1, y);
  }
  return { segs: arr, n: arr.length / 4, bbox: [x0, y0, x1, y1], truncated: segs.length > arr.length };
}
var defaultUnderlayParams = (bbox) => ({
  unit: Math.max(bbox[2] - bbox[0], bbox[3] - bbox[1]) > 500 ? "mm" : "m",
  dx: 0,
  dy: 0,
  rot_deg: 0,
  scale: 1,
  opacity: 0.75
});
async function loadUnderlays() {
  V.uldata.clear();
  let Parser = null;
  for (const ly of S.layers) {
    const u = ly.underlay;
    if (!u || u.format !== "dxf" || u.status !== "ready") {
      continue;
    }
    try {
      const src = await E.adapter.loadUnderlay(ly);
      if (!src) {
        continue;
      }
      if (src.segs) {
        V.uldata.set(ly.id, { segs: src.segs, n: src.segs.length / 4 });
        continue;
      }
      Parser = Parser || await loadDxfParser();
      const res = parseDxf(src.text, Parser);
      u.bbox = res.bbox;
      V.uldata.set(ly.id, { segs: res.segs, n: res.n });
    } catch (e) {
      console.warn("underlay", ly.name, e);
    }
  }
  E.syncUnderlays();
}
function openDxfPanel() {
  S.ui.dxfOpen = true;
  renderDxfPanel();
}
function closeDxfPanel() {
  S.ui.dxfOpen = false;
  if (V.pickMode) {
    V.pickMode = null;
    E.rulerClear();
  }
  renderDxfPanel();
}
async function importUnderlayFile(ly, file, store, msg) {
  const note = (cls, text) => msg && msg.replaceChildren(...K(h("div", { class: "note " + cls, style: { margin: "6px 0" } }, text)));
  msg && msg.replaceChildren();
  const isDwg = /\.dwg$/i.test(file.name);
  if (!isDwg && !/\.dxf$/i.test(file.name)) {
    note("err", "Потрібен файл .dxf.");
    return false;
  }
  if (isDwg) {
    note("lock", DWG_MESSAGE);
  } else if (file.size > DXF_MAX_BYTES) {
    toast("Файл завеликий (> 5 МБ): буде прочитано лише перші 200 тис. відрізків.", "warn");
  }
  let res = null;
  if (!isDwg) {
    try {
      const Parser = await loadDxfParser();
      res = parseDxf(await file.text(), Parser);
    } catch (e) {
      console.warn(e);
      note("err", "Не вдалося прочитати DXF: " + (e && e.message ? e.message : e));
      return false;
    }
    if (!res.n) {
      note("err", "У файлі не знайдено підтримуваних ліній.");
      return false;
    }
  }
  if (ly.rid == null) {
    await E.flushNow();
  }
  const att = await store.attachUnderlay(ly, file);
  ly.underlay = {
    url: att.url,
    name: file.name,
    format: isDwg ? "dwg" : "dxf",
    status: isDwg ? "pending_conversion" : "ready",
    params: res ? defaultUnderlayParams(res.bbox) : { unit: "mm", dx: 0, dy: 0, rot_deg: 0, scale: 1, opacity: 0.75 },
    bbox: res ? res.bbox : null
  };
  if (res) {
    V.uldata.set(ly.id, { segs: res.segs, n: res.n });
    toast(`Підкладку завантажено: ${fmtInt(res.n)} відрізків.` + (res.truncated ? " Файл обрізано до ліміту." : ""));
  } else {
    V.uldata.delete(ly.id);
  }
  E.liveEdit();
  return true;
}
function renderDxfPanel() {
  const box = $("#dxfPanel");
  if (!box) {
    return;
  }
  if (!S.ui.dxfOpen) {
    box.hidden = true;
    return;
  }
  const ly = layerOf(S.ui.layer);
  if (!ly) {
    return;
  }
  box.hidden = false;
  box.replaceChildren();
  const u = ly.underlay;
  const dis = !canEditLayer(ly);
  const upd = () => {
    E.liveEdit();
  };
  box.append(
    ...K(
      h("h4", null, "Підкладка DXF", h("button", { class: "xbtn", type: "button", "aria-label": "Закрити", onclick: closeDxfPanel }, ic("x"))),
      h("div", { class: "small muted", style: { marginBottom: "6px" } }, `Шар «${ly.name}», відмітка ${fmt(ly.elevation, 1)} м. LINE, LWPOLYLINE, POLYLINE, CIRCLE, ARC, INSERT.`),
      dis ? h("div", { class: "note lock" }, lockHint(ly)) : null
    )
  );
  const fi = h("input", { type: "file", accept: ".dxf,.dwg", hidden: true, id: "dxfFile", "aria-label": "Файл DXF" });
  const msg = h("div", { id: "dxfMsg" });
  fi.addEventListener("change", async () => {
    const f = fi.files[0];
    if (!f) {
      return;
    }
    const ok = await importUnderlayFile(ly, f, E.adapter, msg);
    if (ok) {
      renderDxfPanel();
    }
  });
  box.append(...K(h("button", { class: "fbtn", type: "button", disabled: dis, onclick: () => fi.click() }, ic("upload"), u ? "Замінити файл" : "Обрати файл DXF"), fi, msg));
  if (!u) {
    box.append(h("div", { class: "small muted", style: { marginTop: "8px" } }, "Файл не завантажено. Підкладка малюється лініями на підлозі активного шару для обведення в масштабі."));
    return;
  }
  if (u.format === "dwg" || u.status === "pending_conversion") {
    box.append(h("div", { class: "note lock", id: "dwgNote", style: { margin: "8px 0" } }, DWG_MESSAGE), h("div", { class: "small" }, u.name));
    box.append(removeBtn(ly, dis));
    return;
  }
  const m = u.params;
  const real = V.underlays.get(ly.id) ? "" : h("div", { class: "note lock", style: { margin: "6px 0" } }, "Дані підкладки ще завантажуються або недоступні. Спробуйте замінити файл.");
  box.append(
    ...K(
      h("div", { class: "small", style: { margin: "8px 0 4px" } }, `${u.name}${V.uldata.get(ly.id) ? " · " + fmtInt(V.uldata.get(ly.id).n) + " відрізків" : ""}`),
      real,
      h(
        "div",
        { class: "fcol" },
        h("div", { class: "frow" }, h("span", { class: "lbl" }, "Одиниці"), h("span", { class: "seg" }, ["mm", "m"].map((x) => h("button", { type: "button", disabled: dis, "aria-pressed": String(m.unit === x), onclick: () => {
          m.unit = x;
          upd();
          renderDxfPanel();
        } }, x === "mm" ? "мм" : "м")))),
        h(
          "div",
          { class: "grid3" },
          fld("Зсув X", numInput({ value: m.dx, dis, step: 0.5, label: "Зсув X", f: "dxf-dx", set: (v) => {
            m.dx = v;
            upd();
          } }), "м"),
          fld("Зсув Y", numInput({ value: m.dy, dis, step: 0.5, label: "Зсув Y", f: "dxf-dy", set: (v) => {
            m.dy = v;
            upd();
          } }), "м"),
          fld("Поворот", numInput({ value: m.rot_deg, dis, step: 1, label: "Поворот", f: "dxf-rot", set: (v) => {
            m.rot_deg = v;
            upd();
          } }), "°")
        ),
        fld("Прозорість", h("input", { type: "range", min: 0.1, max: 1, step: 0.05, value: m.opacity, disabled: dis, "aria-label": "Прозорість", oninput: (e) => {
          m.opacity = parseFloat(e.target.value);
          upd();
        } }), "лінії"),
        h("div", { class: "small muted" }, `Масштаб ×${fmt(m.scale || 1, 4)}`),
        h(
          "div",
          { class: "frow wrap" },
          h("button", { class: "fbtn sm", type: "button", disabled: dis || !u.bbox, onclick: () => {
            const k = (m.unit === "m" ? 1 : 1e-3) * (m.scale || 1), b = u.bbox;
            m.dx = rnd(S.site.building.length / 2 - (b[0] + b[2]) / 2 * k, 2);
            m.dy = rnd(S.site.building.width / 2 - (b[1] + b[3]) / 2 * k, 2);
            m.rot_deg = 0;
            upd();
            renderDxfPanel();
          } }, "До центру будівлі"),
          h("button", { class: "fbtn sm", type: "button", disabled: dis, "aria-pressed": String(!!V.pickMode), onclick: () => {
            E.cancelModes();
            V.pickMode = "dxfscale";
            V.pickPts = [];
            S.ui.dxfScale = null;
            toast("Клацніть дві точки на підкладці, потім введіть реальну відстань.");
            renderDxfPanel();
          } }, ic("ruler"), "Прив’язати масштаб по двох точках")
        ),
        S.ui.dxfScale ? h(
          "div",
          { class: "note" },
          `Відстань між точками на кресленні: ${fmt(S.ui.dxfScale.d, 3)} м`,
          h(
            "div",
            { class: "frow", style: { marginTop: "6px" } },
            numInput({ value: null, dis, min: 1e-3, step: 0.01, label: "Реальна відстань, м", f: "ulreal", set: (v) => {
              S.ui.dxfScale.real = v;
            } }),
            h("button", { class: "fbtn sm primary", type: "button", onclick: () => {
              const sc = S.ui.dxfScale;
              if (!sc.real) {
                toast("Введіть реальну відстань у метрах.", "warn");
                return;
              }
              m.scale = rnd((m.scale || 1) * sc.real / sc.d, 6);
              S.ui.dxfScale = null;
              E.rulerClear();
              upd();
              renderDxfPanel();
              toast("Масштаб підкладки уточнено.");
            } }, "Застосувати")
          )
        ) : null,
        removeBtn(ly, dis)
      )
    )
  );
}
function removeBtn(ly, dis) {
  return h(
    "button",
    {
      class: "fbtn sm danger",
      type: "button",
      id: "btnRemoveUnderlay",
      disabled: dis,
      onclick: () => {
        ly.underlay = null;
        V.uldata.delete(ly.id);
        E.adapter.detachUnderlay(ly);
        E.liveEdit();
        renderDxfPanel();
      }
    },
    ic("trash"),
    "Прибрати підкладку"
  );
}
function pickModeClick(pt) {
  if (V.pickMode !== "dxfscale") {
    return;
  }
  const v = E.underlayVertex(S.ui.layer, pt.x, pt.y, 0.6);
  if (v) {
    pt.x = v.x;
    pt.y = v.y;
  }
  V.pickPts = V.pickPts || [];
  V.pickPts.push(pt);
  E.rulerPoint(pt);
  if (V.pickPts.length === 2) {
    const [a, b] = V.pickPts;
    V.pickMode = null;
    V.pickPts = [];
    S.ui.dxfScale = { d: Math.hypot(b.x - a.x, b.y - a.y), real: null };
    $("#rlabel").hidden = true;
    renderDxfPanel();
  }
}
Object.assign(E, { openDxfPanel, renderDxfPanel, pickModeClick, loadUnderlays });

// core/constructor/live.js
var live_exports = {};
__export(live_exports, {
  checkConfigs: () => checkConfigs,
  newBlocks: () => newBlocks,
  pGeom: () => pGeom,
  runLive: () => runLive,
  sGeom: () => sGeom,
  slotDims: () => slotDims,
  toCheckState: () => toCheckState
});

// core/constructor/checks.js
var checks_exports = {};
__export(checks_exports, {
  CHECK_KEYS: () => CHECK_KEYS,
  DEFAULT_EPS_M: () => DEFAULT_EPS_M,
  DEFAULT_REACH_M: () => DEFAULT_REACH_M,
  Scene: () => Scene,
  issue: () => issue,
  runChecks: () => runChecks,
  signature: () => signature,
  summarize: () => summarize
});
var CHECK_KEYS = ["fits", "collide", "service_free", "aisles_free", "load", "utility_reach", "fire"];
var DEFAULT_EPS_M = 1e-3;
var DEFAULT_REACH_M = 15;
var ROTATION_TOLERANCE_DEG = 0.01;
var fmtAngle = (v) => String(parseFloat(v.toFixed(2)));
var fix = (v, d) => v.toFixed(d);
var g = (v) => String(parseFloat(Number(v).toPrecision(6)));
function rotationOk(mode, rotation) {
  const period = { q: 90, h: 180, z: 360 }[mode];
  if (period === void 0) {
    return true;
  }
  const rem = (rotation % period + period) % period;
  return Math.min(rem, period - rem) <= ROTATION_TOLERANCE_DEG;
}
var objKey2 = (kind, id) => (kind === "placement" ? "p:" : "s:") + id;
var Scene = class {
  constructor(state) {
    this.building = (state.site || {}).building || {};
    this.layers = new Map((state.layers || []).map((l) => [l.id, l]));
    this.variants = new Map((state.variants || []).map((v) => [v.id, v]));
    this.slots = new Map((state.slots || []).map((s) => [s.id, s]));
    this.placements = (state.placements || []).filter((p) => this.variants.has(p.variant_id));
    this._slotObb = /* @__PURE__ */ new Map();
    this._slotCells = /* @__PURE__ */ new Map();
    this._body = /* @__PURE__ */ new Map();
    this._service = /* @__PURE__ */ new Map();
  }
  slotObb(slot) {
    if (!this._slotObb.has(slot.id)) {
      this._slotObb.set(
        slot.id,
        slotObb(slot.template, slot.params || {}, slot.x || 0, slot.y || 0, slot.rotation || 0)
      );
    }
    return this._slotObb.get(slot.id);
  }
  slotCells(slot) {
    if (!this._slotCells.has(slot.id)) {
      const elevation = (this.layers.get(slot.layer_id) || {}).elevation || 0;
      const cells = generateCells(
        slot.template,
        slot.code_prefix || "",
        slot.x || 0,
        slot.y || 0,
        slot.rotation || 0,
        slot.params || {},
        slot.overrides || {},
        elevation
      );
      this._slotCells.set(slot.id, new Map(cells.map((c) => [c.code, c])));
    }
    return this._slotCells.get(slot.id);
  }
  body(p) {
    if (!this._body.has(p.id)) {
      this._body.set(p.id, placementObb(this.variants.get(p.variant_id), p.x || 0, p.y || 0, p.rotation || 0));
    }
    return this._body.get(p.id);
  }
  service(p) {
    if (!this._service.has(p.id)) {
      this._service.set(p.id, serviceObb(this.variants.get(p.variant_id), p.x || 0, p.y || 0, p.rotation || 0));
    }
    return this._service.get(p.id);
  }
  /** F = розміщення ∪ місця (крім zone). */
  objects() {
    const out = [];
    for (const p of this.placements) {
      if (p.dynamic) {
        continue;
      }
      out.push({ kind: "placement", id: p.id, code: p.code, layer_id: p.layer_id, obb: this.body(p), slot_id: p.slot_id });
    }
    for (const s of this.slots.values()) {
      if (s.template !== "zone") {
        out.push({ kind: "slot", id: s.id, code: s.code_prefix, layer_id: s.layer_id, obb: this.slotObb(s), slot_id: null });
      }
    }
    return out;
  }
  containerPolygon(layer) {
    const bounds = layer ? layer.bounds : null;
    if (bounds && bounds.length >= 3) {
      return [bounds.map((p) => [p[0], p[1]]), "контуру шару"];
    }
    return [rectPolygon(this.building.length || 0, this.building.width || 0), "будівлі"];
  }
};
var issue = (check, severity, layer_id, codes, message, keys, sub) => ({
  check,
  severity,
  layer_id,
  codes: [...codes],
  message,
  keys: [...keys],
  id: [check, ...[...keys].sort(), sub || ""].join("|")
});
function epsOf(config, eps) {
  const tol = (config.params || {}).tolerance_mm;
  return typeof tol === "number" ? tol / 1e3 : eps;
}
function checkFits(scene, config, eps) {
  const sev = config.mode;
  const issues = [];
  for (const p of scene.placements) {
    const variant = scene.variants.get(p.variant_id);
    const layer = scene.layers.get(p.layer_id) || {};
    const { code } = p;
    const lid = p.layer_id;
    const k = [objKey2("placement", p.id)];
    const kinds = variant.layer_kinds || [];
    if (kinds.length && !kinds.includes(layer.kind)) {
      issues.push(issue("fits", sev, lid, [code], `${code}: варіант не допускається на шарі «${layer.name || ""}»`, k, "layer"));
    }
    const slot = p.slot_id != null ? scene.slots.get(p.slot_id) : null;
    const types = variant.slot_types || [];
    if (slot && types.length && !types.includes(slot.template)) {
      issues.push(issue("fits", sev, lid, [code], `${code}: варіант не допускається в місці типу ${slot.template}`, k, "tpl"));
    }
    const rotation = p.rotation || 0;
    if (!rotationOk(variant.rotations, rotation)) {
      issues.push(issue("fits", sev, lid, [code], `${code}: поворот ${fmtAngle(rotation)}° недозволений`, k, "rot"));
    }
    const cellCode = p.cell_code;
    let container;
    let what;
    if (cellCode && slot) {
      const cell = scene.slotCells(slot).get(cellCode);
      if (!cell) {
        issues.push(issue("fits", sev, lid, [code], `${code}: комірки ${cellCode} немає в місці ${slot.code_prefix}`, k, "cell"));
        continue;
      }
      container = obbCorners(makeObb(cell.x, cell.y, cell.l / 2, cell.w / 2, cell.rot));
      what = "комірки";
    } else if (slot) {
      container = obbCorners(scene.slotObb(slot));
      what = "місця";
    } else {
      [container, what] = scene.containerPolygon(layer);
    }
    if (!obbInsidePolygon(scene.body(p), container, eps)) {
      issues.push(issue("fits", sev, lid, [code], `${code}: виходить за межі ${what}`, k, "bounds"));
    }
  }
  for (const slot of scene.slots.values()) {
    if (slot.template === "zone") {
      continue;
    }
    const [container, what] = scene.containerPolygon(scene.layers.get(slot.layer_id) || {});
    if (!obbInsidePolygon(scene.slotObb(slot), container, eps)) {
      issues.push(
        issue("fits", sev, slot.layer_id, [slot.code_prefix], `${slot.code_prefix}: виходить за межі ${what}`, [objKey2("slot", slot.id)], "bounds")
      );
    }
  }
  return issues;
}
function byLayer(objects) {
  const groups = /* @__PURE__ */ new Map();
  for (const o of objects) {
    if (!groups.has(o.layer_id)) {
      groups.set(o.layer_id, []);
    }
    groups.get(o.layer_id).push(o);
  }
  return groups;
}
var sameSlot = (a, b) => {
  if (a.kind === "placement" && b.kind === "slot") {
    return a.slot_id === b.id;
  }
  if (a.kind === "slot" && b.kind === "placement") {
    return b.slot_id === a.id;
  }
  return false;
};
function checkCollide(scene, config, eps) {
  const sev = config.mode;
  const issues = [];
  for (const [layerId, group] of byLayer(scene.objects())) {
    const boxes = group.map((o) => obbAabb(o.obb));
    for (let i = 0; i < group.length; i++) {
      for (let j = i + 1; j < group.length; j++) {
        const a = group[i];
        const b = group[j];
        if (sameSlot(a, b) || !aabbOverlap(boxes[i], boxes[j], eps)) {
          continue;
        }
        const depth = satPenetration(a.obb, b.obb);
        if (depth > eps) {
          const [x, y] = a.code <= b.code ? [a, b] : [b, a];
          issues.push(
            issue("collide", sev, layerId, [x.code, y.code], `${x.code} перетинається з ${y.code} на ${fix(depth, 2)} м`, [objKey2(x.kind, x.id), objKey2(y.kind, y.id)])
          );
        }
      }
    }
  }
  return issues;
}
function checkServiceFree(scene, config, eps) {
  const sev = config.mode;
  const issues = [];
  const groups = byLayer(scene.objects());
  for (const p of scene.placements) {
    const service = p.dynamic ? null : scene.service(p);
    if (!service) {
      continue;
    }
    const box = obbAabb(service);
    for (const other of groups.get(p.layer_id) || []) {
      if (other.kind === "placement" && other.id === p.id) {
        continue;
      }
      if (other.kind === "slot" && other.id === p.slot_id) {
        continue;
      }
      if (!aabbOverlap(box, obbAabb(other.obb), eps)) {
        continue;
      }
      if (satPenetration(service, other.obb) > eps) {
        issues.push(
          issue("service_free", sev, p.layer_id, [p.code, other.code], `Зона обслуговування ${p.code} зачіпає ${other.code}`, [objKey2("placement", p.id), objKey2(other.kind, other.id)])
        );
      }
    }
  }
  return issues;
}
function checkRects(scene, config, eps, check, key) {
  const sev = config.mode;
  const issues = [];
  for (const [layerId, group] of byLayer(scene.objects())) {
    const rects = (scene.layers.get(layerId) || {})[key] || [];
    for (const obj of group) {
      for (const rect of rects) {
        if (satPenetration(obj.obb, rectObb(rect.x0, rect.y0, rect.x1, rect.y1)) <= eps) {
          continue;
        }
        const name = rect.name || "";
        let message;
        if (check === "aisles_free") {
          message = `Прохід перекрито: ${obj.code} × ${name}`;
        } else if (rect.kind === "exit") {
          message = `Вихід перекрито: ${obj.code} × ${name}`;
        } else {
          message = `Пожежний прохід перекрито: ${obj.code} × ${name}`;
        }
        issues.push(issue(check, sev, layerId, [obj.code], message, [objKey2(obj.kind, obj.id)], String(rect.id ?? name)));
      }
    }
  }
  return issues;
}
var checkAislesFree = (scene, config, eps) => checkRects(scene, config, eps, "aisles_free", "aisles");
var checkFire = (scene, config, eps) => checkRects(scene, config, eps, "fire", "fire_paths");
function checkLoad(scene, config) {
  const sev = config.mode;
  const issues = [];
  for (const p of scene.placements) {
    const variant = scene.variants.get(p.variant_id);
    const layer = scene.layers.get(p.layer_id) || {};
    const limit = layer.max_floor_load || 0;
    const load = variant.floor_load || 0;
    const k = [objKey2("placement", p.id)];
    if (limit > 0 && load > limit) {
      issues.push(issue("load", sev, p.layer_id, [p.code], `${p.code}: навантаження ${fix(load, 1)} кН/м² перевищує ${fix(limit, 1)}`, k, "floor"));
    }
    const slot = p.slot_id != null ? scene.slots.get(p.slot_id) : null;
    if (p.cell_code && slot) {
      const cell = scene.slotCells(slot).get(p.cell_code);
      const weight = variant.weight_kg || 0;
      if (cell && cell.max_load_kg > 0 && weight > cell.max_load_kg) {
        issues.push(issue("load", sev, p.layer_id, [p.code], `${p.code}: маса ${g(weight)} кг перевищує ${g(cell.max_load_kg)} кг комірки ${p.cell_code}`, k, "cell"));
      }
    }
  }
  return issues;
}
function checkUtilityReach(scene, config) {
  const sev = config.mode;
  let maxM = (config.params || {}).max_m;
  if (typeof maxM !== "number" || !(maxM > 0)) {
    maxM = DEFAULT_REACH_M;
  }
  const points = /* @__PURE__ */ new Map();
  for (const layer of scene.layers.values()) {
    for (const u of layer.utilities || []) {
      const kind = u.kind === "panel" ? "electric" : u.kind;
      if (!points.has(kind)) {
        points.set(kind, []);
      }
      points.get(kind).push([u.x, u.y]);
    }
  }
  const issues = [];
  for (const p of scene.placements) {
    const variant = scene.variants.get(p.variant_id);
    const k = [objKey2("placement", p.id)];
    for (const [kind, ux, uy] of utilityPoints(variant, p.x || 0, p.y || 0, p.rotation || 0)) {
      const cands = points.get(kind) || [];
      if (!cands.length) {
        issues.push(issue("utility_reach", sev, p.layer_id, [p.code], `${p.code}: на площадці немає точки «${kind}»`, k, kind));
        continue;
      }
      const dist = Math.min(...cands.map(([cx, cy]) => Math.hypot(ux - cx, uy - cy)));
      if (dist > maxM) {
        issues.push(issue("utility_reach", sev, p.layer_id, [p.code], `${p.code}: до найближчої точки «${kind}» ${fix(dist, 1)} м (ліміт ${g(maxM)} м)`, k, kind));
      }
    }
  }
  return issues;
}
var CHECKERS = {
  fits: checkFits,
  collide: checkCollide,
  service_free: checkServiceFree,
  aisles_free: checkAislesFree,
  load: checkLoad,
  utility_reach: checkUtilityReach,
  fire: checkFire
};
CHECK_KEYS.forEach((key, i) => registries.checks.add(key, { run: CHECKERS[key] }, { sequence: (i + 1) * 10, force: true }));
function runChecks(state, configs, eps = DEFAULT_EPS_M) {
  const scene = new Scene(state);
  const byKey = new Map((configs || []).filter((c) => c.enabled).map((c) => [c.check, c]));
  const issues = [];
  for (const [key, chk] of registries.checks.getEntries()) {
    const config = byKey.get(chk.config || key);
    if (config) {
      issues.push(...chk.run(scene, config, epsOf(config, eps)));
    }
  }
  return issues;
}
var summarize = (issues) => ({
  block: issues.filter((i) => i.severity === "block").length,
  warn: issues.filter((i) => i.severity === "warn").length
});
var signature = (issues) => issues.map((i) => `${i.check}|${i.severity}|${i.codes.join(",")}`).sort();

// core/constructor/live.js
function slotDims(s) {
  const H = slotHeight({ ...s, params: normalizeParams(s.template, s.params) });
  if (s.template === "zone") {
    return { L: s.params.length || 1, W: s.params.width || 1, H };
  }
  const f = footprint(s.template, s.params);
  return { L: f.l, W: f.w, H };
}
function pGeom(pl, v) {
  const rot = pl.rotation || 0;
  const body = placementObb(v, pl.x, pl.y, rot);
  const svc = serviceObb(v, pl.x, pl.y, rot);
  const g3 = { cx: body.cx, cy: body.cy, L: v.length / 1e3, W: v.width / 1e3, a: rot, body, svc: null };
  g3.poly = obbCorners(body);
  g3.box = obbAabb(body);
  if (svc) {
    const [ox, oy] = rotate(svc.cx - body.cx, svc.cy - body.cy, -rot);
    Object.assign(g3, { shx: svc.a, shy: svc.b, sox: ox, soy: oy, svc: obbCorners(svc) });
  }
  return g3;
}
function sGeom(s) {
  const d = slotDims(s);
  const a = s.rotation || 0;
  const g3 = { cx: s.x, cy: s.y, L: d.L, W: d.W, H: d.H, a };
  g3.body = makeObb(s.x, s.y, d.L / 2, d.W / 2, a);
  g3.poly = obbCorners(g3.body);
  g3.box = obbAabb(g3.body);
  if (s.template === "machine_spot") {
    const sv = (s.params || {}).service || {};
    const e = { yn: sv.front || 0, yp: sv.back || 0, xn: sv.left || 0, xp: sv.right || 0 };
    g3.shx = d.L / 2 + (e.xn + e.xp) / 2;
    g3.shy = d.W / 2 + (e.yn + e.yp) / 2;
    g3.sox = (e.xp - e.xn) / 2;
    g3.soy = (e.yp - e.yn) / 2;
  }
  return g3;
}
function slotForChecks(s) {
  if (s.template !== "zone") {
    return s;
  }
  const g3 = sGeom(s);
  return { ...s, x: 0, y: 0, rotation: 0, params: { polygon: g3.poly } };
}
function toCheckState() {
  return {
    site: { building: S.site.building },
    layers: S.layers,
    slots: S.slots.map(slotForChecks),
    placements: S.placements,
    variants: S.catalog.flatMap((p) => p.variants)
  };
}
var checkConfigs = () => Object.entries(S.settings.checks).map(([check, c]) => ({
  check,
  enabled: c.enabled,
  mode: c.mode,
  params: check === "utility_reach" ? { ...c.params, max_m: S.settings.reach_n } : c.params || {}
}));
var epsM = () => (S.site && S.site.settings && S.site.settings.eps_mm || 1) / 1e3;
function runLive() {
  const list = runChecks(toCheckState(), checkConfigs(), epsM()).map((i) => ({
    ...i,
    level: i.severity,
    msg: i.message,
    layerId: i.layer_id
  }));
  const byKey = /* @__PURE__ */ new Map();
  for (const it of list) {
    for (const k of it.keys) {
      const e = byKey.get(k) || { level: "warn", items: [] };
      e.items.push(it);
      if (it.level === "block") {
        e.level = "block";
      }
      byKey.set(k, e);
    }
  }
  return { list, byKey, summary: summarize(list) };
}
function newBlocks(before, after, key) {
  const ids = new Set(before.list.filter((i) => i.level === "block" && i.keys.includes(key)).map((i) => i.id));
  return after.list.filter((i) => i.level === "block" && i.keys.includes(key) && !ids.has(i.id));
}

// core/constructor/panels_left.js
var isNarrow = () => window.matchMedia("(max-width: 900px)").matches;
function renderTop() {
  const ss = $("#siteSel");
  ss.replaceChildren(...K(S.app.sites.map((s) => h("option", { value: s.id, selected: s.id === S.app.active }, s.name))));
  const rs = $("#roleSel");
  if (S.rights.is_manager) {
    rs.disabled = false;
    rs.setAttribute("aria-label", "Переглянути як роль");
    rs.replaceChildren(
      ...K(ROLES.map((r) => h("option", { value: r.id, selected: r.id === (S.app.viewAs || "manager") }, r.id === "manager" ? "Менеджер (своя роль)" : "Переглянути як: " + r.name)))
    );
  } else {
    rs.disabled = true;
    rs.setAttribute("aria-label", "Ваша роль");
    rs.replaceChildren(h("option", { value: "me" }, myRoleNames()));
  }
  $$("#modeSeg button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.mode === S.app.mode)));
  const pub = $("#btnPublish");
  pub.hidden = !can("publish");
  pub.disabled = !canPublish();
  pub.title = pub.disabled ? S.rights.is_manager && !S.rights.can_publish ? "Публікацію вимкнено (параметр td.constructor.publish_enabled)" : "Публікує Менеджер у режимі редагування" : "";
  $("#btnNewSite").disabled = !canManage();
  renderMenu();
  renderChips();
  const tt = $("#btnTheme");
  tt.replaceChildren(ic(curTheme() === "dark" ? "sun" : "moon"));
  renderSaveState();
}
function renderMenu() {
  const box = $("#menuExtra");
  if (!box) {
    return;
  }
  const ctx2 = { E, S, V };
  const top = [];
  const more = [];
  forEachEntry(registries.menu, (key, m) => (m.area === "more" ? more : top).push([key, m]), ctx2);
  const btn = ([key, m], cls) => h("button", { class: cls + (m.cls ? " " + m.cls : ""), type: "button", id: "menu-" + key, disabled: m.disabled ? m.disabled(ctx2) : false, onclick: () => m.run(ctx2) }, m.icon ? ic(m.icon) : null, m.label);
  box.replaceChildren(
    ...K(
      top.map((e) => btn(e, "fbtn")),
      more.length ? h("details", { class: "more", id: "menuMore" }, h("summary", { class: "fbtn" }, "Ще ▾"), h("div", { class: "morelist" }, more.map((e) => btn(e, "fbtn")))) : null
    )
  );
  box.hidden = !top.length && !more.length;
}
var SAVE_LABELS = { saved: "Збережено", saving: "Зберігаємо…", error: "Помилка збереження" };
function renderSaveState() {
  const el = $("#storeTag");
  if (!el) {
    return;
  }
  el.textContent = SAVE_LABELS[S.saveState] || "";
  el.dataset.state = S.saveState;
  renderNotice();
}
var curTheme = () => {
  const t = (host.themeTarget || ROOT.el)?.dataset.theme;
  if (t === "dark" || t === "light") {
    return t;
  }
  return host.themeAuto && window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
};
function renderChips() {
  const chip = $("#draftChip");
  if (!chip || !S.site) {
    return;
  }
  const n = S.site.draft_changes || 0;
  chip.textContent = isNarrow() ? `Чернетка · ${n}` : n ? `Чернетка · змінено ${n}` : "Чернетка · без змін";
  chip.classList.toggle("dirty", n > 0);
  const v = S.site.active_version ? "v" + S.site.active_version.n : "не опубліковано";
  chip.title = "Активна версія: " + v;
}
function updateTabs() {
  $$("#ltabs button").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.tab === S.ui.leftTab)));
  const m = $("#app").dataset.mtab;
  $$("#mtabs button").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.mtab === m)));
}
function setLeftTab(t) {
  S.ui.leftTab = t;
  $("#app").dataset.mtab = t;
  renderLeft();
  updateTabs();
}
function setMTab(t) {
  if (t === "props") {
    $("#app").dataset.mtab = "props";
    updateTabs();
    E.renderRight();
  } else {
    setLeftTab(t);
  }
}
var leftPanels = () => registries.panels.getEntries().filter(([, p]) => p.area === "left");
function renderLeft() {
  const root = $("#leftBody");
  root.replaceChildren();
  const found = leftPanels().find(([, p]) => p.tab === S.ui.leftTab) || leftPanels()[0];
  if (found) {
    found[1].render(root);
  }
}
function ensureTabs() {
  for (const [, p] of leftPanels()) {
    if (!p.tab || $(`#ltabs button[data-tab="${p.tab}"]`)) {
      continue;
    }
    const mk = (mobile) => h("button", { type: "button", role: "tab", [mobile ? "data-mtab" : "data-tab"]: p.tab, onclick: () => mobile ? E.setMTab(p.tab) : E.setLeftTab(p.tab) }, p.label || p.tab);
    $("#ltabs").append(mk(false));
    const props = $('#mtabs button[data-mtab="props"]');
    if (props) {
      props.before(mk(true));
    }
  }
}
function renderAll() {
  ensureTabs();
  renderTop();
  renderLeft();
  E.renderRight();
  renderVTools();
  renderStamp();
  renderNotice();
  E.renderDxfPanel();
  updateTabs();
}
function setActiveLayer(id) {
  if (S.ui.layer === id) {
    return;
  }
  V.hidden.delete(id);
  S.ui.layer = id;
  S.issues = runLive();
  E.syncScene();
  renderLayerList();
  renderLayerForm();
  renderStamp();
  E.renderDxfPanel();
  if (S.ui.leftTab === "slots") {
    renderLeft();
  }
  E.requestRender();
}
function renderLayersTab(root) {
  const add = h("button", { class: "fbtn sm", type: "button", disabled: !canManage(), onclick: addLayer, title: canManage() ? "" : "Шари додає Менеджер" }, ic("plus"), "Шар");
  root.append(...K(h("div", { class: "sec" }, h("h3", null, "Шари", add), h("div", { id: "layerList" })), h("div", { class: "sec", id: "layerForm" })));
  renderLayerList();
  renderLayerForm();
}
function renderLayerList() {
  const box = $("#layerList");
  if (!box) {
    return;
  }
  const lys = [...S.layers].sort((a, b) => a.sequence - b.sequence);
  const groups = [];
  for (const ly of lys) {
    const name = ly.group || "";
    let g3 = groups.find((x) => x.name === name);
    if (!g3) {
      g3 = { name, layers: [] };
      groups.push(g3);
    }
    g3.layers.push(ly);
  }
  const collapsed = S.ui.collapsed = S.ui.collapsed || /* @__PURE__ */ new Set();
  const row = (ly) => {
    const n = S.slots.filter((s) => s.layer_id === ly.id).length + S.placements.filter((p) => p.layer_id === ly.id).length;
    const vis = isLayerVisible(ly);
    return h(
      "div",
      {
        class: "layer" + (ly.id === S.ui.layer ? " active" : "") + (vis ? "" : " hidden"),
        role: "button",
        tabindex: 0,
        "data-layer": ly.id,
        onclick: () => setActiveLayer(ly.id),
        onkeydown: (e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            setActiveLayer(ly.id);
          }
        }
      },
      h(
        "button",
        {
          class: "eye",
          type: "button",
          "aria-label": vis ? "Сховати шар" : "Показати шар",
          onclick: (e) => {
            e.stopPropagation();
            if (vis) {
              V.hidden.add(ly.id);
            } else {
              V.hidden.delete(ly.id);
            }
            E.syncScene();
            renderLayerList();
          }
        },
        ic(vis ? "eye" : "eyeoff")
      ),
      h("span", { class: "sw", style: { background: ly.color } }),
      h("span", { class: "nm", title: ly.name }, ly.name),
      canEditLayer(ly) ? null : h("span", { class: "ic", title: lockHint(ly) }, ic("lock")),
      h("span", { class: "meta" }, (ly.elevation >= 0 ? "+" : "") + fmt(ly.elevation, 1) + " м · " + n)
    );
  };
  const items = [];
  for (const g3 of groups) {
    const closed = !!g3.name && collapsed.has(g3.name) && !g3.layers.some((l) => l.id === S.ui.layer);
    if (g3.name) {
      items.push(
        h(
          "div",
          {
            class: "lgroup" + (closed ? " closed" : ""),
            role: "button",
            tabindex: 0,
            "data-group": g3.name,
            onclick: () => {
              if (collapsed.has(g3.name)) {
                collapsed.delete(g3.name);
              } else {
                collapsed.add(g3.name);
              }
              renderLayerList();
            }
          },
          ic(closed ? "down" : "up"),
          h("span", { class: "nm" }, g3.name),
          h("span", { class: "meta" }, String(g3.layers.length))
        )
      );
    }
    if (!closed) {
      items.push(...g3.layers.map(row));
    }
  }
  box.replaceChildren(...K(h("div", { class: "layers" }, items)));
}
function addLayer() {
  const ly = { ...newLayerDefaults(), id: newUid(), rid: null, etag: null, sequence: Math.max(0, ...S.layers.map((l) => l.sequence)) + 10 };
  S.layers.push(ly);
  S.ui.layer = ly.id;
  E.commit({});
}
function layerEdit(fn) {
  fn();
  E.liveEdit();
}
function boundsRect(b) {
  if (!b || b.length !== 4) {
    return null;
  }
  const xs = [...new Set(b.map((p) => p[0]))];
  const ys = [...new Set(b.map((p) => p[1]))];
  return xs.length === 2 && ys.length === 2 ? { x0: Math.min(...xs), x1: Math.max(...xs), y0: Math.min(...ys), y1: Math.max(...ys) } : null;
}
var rectBounds = (r) => [
  [r.x0, r.y0],
  [r.x1, r.y0],
  [r.x1, r.y1],
  [r.x0, r.y1]
];
function renderLayerForm() {
  const box = $("#layerForm");
  if (!box) {
    return;
  }
  const ly = layerOf(S.ui.layer);
  box.replaceChildren();
  if (!ly) {
    return;
  }
  const dis = !canManage();
  const disC = !canEditLayer(ly);
  const num3 = (label, key, unit, o) => fld(label, numInput(Object.assign({ value: ly[key], dis, label, set: (v) => layerEdit(() => {
    ly[key] = v;
  }) }, o)), unit);
  const frag = [];
  frag.push(h("h3", null, "Параметри шару"));
  if (dis) {
    frag.push(h("div", { class: "note lock" }, S.app.mode === "edit" ? "Параметри шарів змінює Менеджер." : lockHint(ly)));
  }
  const rect = boundsRect(ly.bounds);
  frag.push(
    h(
      "div",
      { class: "fcol" },
      fld("Назва", textInput({ value: ly.name, dis, label: "Назва", f: "layer-name", set: (v) => layerEdit(() => {
        ly.name = v;
      }) })),
      h(
        "div",
        { class: "grid2" },
        fld("Тип", selectEl(Object.entries(LAYER_KINDS), ly.kind, (v) => layerEdit(() => {
          ly.kind = v;
        }), dis, "Тип")),
        num3("Відмітка", "elevation", "м", { step: 0.1 })
      ),
      h("div", { class: "grid3" }, num3("Крок сітки", "grid_step", "м", { step: 0.05, min: 0.05 }), num3("Ширина проходів", "aisle_width", "м", { step: 0.1, min: 0 }), num3("Навант. на підлогу", "max_floor_load", "кН/м²", { step: 1, min: 0 })),
      h(
        "div",
        { class: "frow" },
        fld("Колір", h("input", { type: "color", value: ly.color, disabled: dis, onchange: (e) => layerEdit(() => {
          ly.color = e.target.value;
        }) })),
        fld("Непрозорість", h("input", { type: "range", min: 0.1, max: 1, step: 0.05, value: ly.opacity, disabled: dis, oninput: (e) => layerEdit(() => {
          ly.opacity = parseFloat(e.target.value);
        }) }))
      ),
      fld(
        "Контур шару",
        h(
          "div",
          { class: "fcol" },
          h(
            "label",
            { class: "frow" },
            h("input", {
              type: "checkbox",
              checked: !!ly.bounds,
              disabled: dis,
              onchange: (e) => {
                layerEdit(() => {
                  ly.bounds = e.target.checked ? rectBounds({ x0: 0, y0: 0, x1: S.site.building.length, y1: S.site.building.width }) : null;
                });
                renderLayerForm();
              }
            }),
            "Задати контур (інакше — межі будівлі)"
          ),
          ly.bounds && rect ? h("div", { class: "grid4" }, ["x0", "y0", "x1", "y1"].map((k) => numInput({ value: rect[k], dis, label: k, step: 0.5, set: (v) => layerEdit(() => {
            ly.bounds = rectBounds({ ...boundsRect(ly.bounds), [k]: v });
          }) }))) : ly.bounds ? h("div", { class: "small muted" }, `Контур із ${ly.bounds.length} точок: редагується у формі Odoo.`) : null
        ),
        "м"
      ),
      fld("Допустимі типи місць", checkGroup(Object.entries(TPL).map(([k, t]) => [k, t.name]), ly.slot_types, (v) => layerEdit(() => {
        ly.slot_types = v;
      }), dis)),
      fld(
        "Редагують ролі",
        checkGroup(
          ROLES.map((r) => [r.id, r.name]),
          ly.edit_roles,
          async (v) => {
            const roles = v.includes("manager") ? v : ["manager", ...v];
            await E.adapter.ensureGroupIds(roles);
            layerEdit(() => {
              ly.edit_roles = roles;
            });
          },
          dis
        )
      )
    )
  );
  frag.push(h("hr"), h("div", { class: "h3" }, "Підкладка"), h("button", { class: "fbtn sm", type: "button", onclick: () => E.openDxfPanel() }, ic("upload"), ly.underlay ? "Підкладка: " + ly.underlay.name : "Підкладка DXF"));
  const rectRows = (arr, container) => arr.map(
    (a, i) => h(
      "div",
      { class: "mini fp" },
      textInput({ value: a.name || "", dis: disC, label: "Назва", set: (v) => layerEdit(() => {
        a.name = v;
      }) }),
      ...["x0", "y0", "x1", "y1"].map((k) => numInput({ value: a[k], dis: disC, label: k, step: 0.1, set: (v) => layerEdit(() => {
        a[k] = v;
      }) })),
      h("button", { class: "xbtn", type: "button", disabled: disC, "aria-label": "Видалити", onclick: () => {
        layerEdit(() => {
          const j = container.indexOf(a);
          container.splice(j >= 0 ? j : i, 1);
        });
        renderLayerForm();
      } }, ic("x"))
    )
  );
  const fireAll = ly.fire_paths;
  const paths = fireAll.filter((f) => f.kind !== "exit");
  const exits = fireAll.filter((f) => f.kind === "exit");
  frag.push(
    h("hr"),
    h("div", { class: "h3" }, "Проходи шару"),
    h("div", null, rectRows(ly.aisles, ly.aisles)),
    h("button", { class: "fbtn sm", type: "button", disabled: disC, onclick: () => {
      const t = E.camTarget(), w = ly.aisle_width || 2.5;
      layerEdit(() => ly.aisles.push({ id: uid("ai_"), name: "Прохід " + (ly.aisles.length + 1), x0: rnd(t.x - 6), y0: rnd(t.y - w / 2), x1: rnd(t.x + 6), y1: rnd(t.y + w / 2) }));
      renderLayerForm();
    } }, ic("plus"), "Прохід")
  );
  frag.push(
    h("hr"),
    h("div", { class: "h3" }, "Пожежні проходи й виходи"),
    h("div", null, rectRows(paths, fireAll)),
    exits.length ? h("details", null, h("summary", { class: "small muted" }, `Виходи: ${exits.length}`), rectRows(exits, fireAll)) : null,
    h(
      "div",
      { class: "frow wrap" },
      h("button", { class: "fbtn sm", type: "button", disabled: disC, onclick: () => {
        const t = E.camTarget();
        layerEdit(() => fireAll.push({ id: uid("fp_"), kind: "path", name: "Пожежний прохід " + (paths.length + 1), x0: rnd(t.x - 6), y0: rnd(t.y - 0.6), x1: rnd(t.x + 6), y1: rnd(t.y + 0.6) }));
        renderLayerForm();
      } }, ic("plus"), "Прохід"),
      h("button", { class: "fbtn sm", type: "button", disabled: disC, onclick: () => {
        const t = E.camTarget();
        layerEdit(() => fireAll.push({ id: uid("fp_"), kind: "exit", name: "Вихід " + (exits.length + 1), x0: rnd(t.x - 1), y0: 0, x1: rnd(t.x + 1), y1: 2.5 }));
        renderLayerForm();
      } }, ic("plus"), "Вихід")
    )
  );
  const ut = ly.utilities;
  frag.push(
    h("hr"),
    h("div", { class: "h3" }, "Точки щитів і магістралей"),
    ut.length ? h(
      "details",
      null,
      h("summary", { class: "small muted" }, `Точок: ${ut.length}`),
      ut.map(
        (a) => h(
          "div",
          { class: "mini u" },
          selectEl(Object.entries(LAYER_UTIL_KINDS), a.kind, (v) => layerEdit(() => {
            a.kind = v;
          }), disC, "Вид"),
          numInput({ value: a.x, dis: disC, label: "x", step: 0.5, set: (v) => layerEdit(() => {
            a.x = v;
          }) }),
          numInput({ value: a.y, dis: disC, label: "y", step: 0.5, set: (v) => layerEdit(() => {
            a.y = v;
          }) }),
          h("button", { class: "xbtn", type: "button", disabled: disC, "aria-label": "Видалити", onclick: () => {
            layerEdit(() => ut.splice(ut.indexOf(a), 1));
            renderLayerForm();
          } }, ic("x"))
        )
      )
    ) : h("div", { class: "small muted" }, "Точок немає."),
    h("button", { class: "fbtn sm", type: "button", disabled: disC, onclick: () => {
      const t = E.camTarget();
      layerEdit(() => ut.push({ id: uid("u"), kind: "electric", name: "", x: rnd(t.x, 1), y: rnd(t.y, 1) }));
      renderLayerForm();
    } }, ic("plus"), "Точка")
  );
  const sorted = [...S.layers].sort((a, b) => a.sequence - b.sequence);
  const idx = sorted.indexOf(ly);
  const move = (d) => {
    const o = sorted[idx + d];
    if (!o) {
      return;
    }
    layerEdit(() => {
      const t = ly.sequence;
      ly.sequence = o.sequence;
      o.sequence = t;
      if (ly.sequence === o.sequence) {
        ly.sequence += d;
      }
    });
    renderLayerForm();
  };
  frag.push(
    h("hr"),
    h(
      "div",
      { class: "frow wrap" },
      h("button", { class: "fbtn sm icon", type: "button", disabled: dis || idx <= 0, "aria-label": "Вище", onclick: () => move(-1) }, ic("up")),
      h("button", { class: "fbtn sm icon", type: "button", disabled: dis || idx >= sorted.length - 1, "aria-label": "Нижче", onclick: () => move(1) }, ic("down")),
      h("span", { class: "grow" }),
      h("button", { class: "fbtn sm danger", type: "button", disabled: dis || S.layers.length < 2, onclick: () => deleteLayer(ly) }, ic("trash"), "Видалити шар")
    )
  );
  box.append(...K(frag));
}
async function deleteLayer(ly) {
  const n = S.slots.filter((s) => s.layer_id === ly.id).length + S.placements.filter((p) => p.layer_id === ly.id).length;
  const ok = await E.confirmBox({ title: "Видалити шар?", text: `Шар «${ly.name}»${n ? ` містить ${n} об’єктів — вони теж будуть видалені.` : "."}`, ok: "Видалити", danger: true });
  if (!ok) {
    return;
  }
  S.slots = S.slots.filter((s) => s.layer_id !== ly.id);
  S.placements = S.placements.filter((p) => p.layer_id !== ly.id);
  S.layers = S.layers.filter((l) => l.id !== ly.id);
  V.uldata.delete(ly.id);
  reindex();
  if (S.sel && !S.sIdx.has(S.sel.id) && !S.pIdx.has(S.sel.id)) {
    S.sel = null;
  }
  S.ui.layer = (S.layers.find((l) => l.kind === "production") || S.layers[0]).id;
  E.commit({});
}
function renderSlotsTab(root) {
  const ly = layerOf(S.ui.layer);
  if (!ly) {
    return;
  }
  const dis = !canEditLayer(ly);
  const T = S.ui.tpl = S.ui.tpl || { template: "pallet_rack", prefix: "R1", params: defaultParams("pallet_rack") };
  const spec = TPL[T.template];
  const sec = h("div", { class: "sec" }, h("h3", null, "Новий шаблон"));
  if (dis) {
    sec.append(h("div", { class: "note lock" }, lockHint(ly)));
  }
  const allowed = ly.slot_types.includes(T.template);
  sec.append(
    h(
      "div",
      { class: "fcol" },
      fld("Шаблон", selectEl(Object.entries(TPL).map(([k, t]) => [k, t.name]), T.template, (v) => {
        T.template = v;
        T.params = defaultParams(v);
        T.prefix = TPL[v].prefix;
        renderLeft();
      }, false, "Шаблон")),
      h("div", { class: "small muted" }, spec.info),
      fld("Префікс коду", textInput({ value: T.prefix, label: "Префікс", f: "tpl-prefix", set: (v) => {
        T.prefix = v;
      } }), "напр. PR-1; до 22 символів"),
      paramFields(T.template, T.params, { dis: false, onChange: () => {
      } }),
      !allowed ? h("div", { class: "note err" }, `Шар «${ly.name}» не допускає цей шаблон. Змініть «Допустимі типи місць» у параметрах шару.`) : null,
      h("button", { class: "fbtn primary", type: "button", id: "btnPlaceSlot", disabled: dis || !allowed, onclick: () => E.startPlacing({ kind: "slot", template: T.template, prefix: (T.prefix || spec.prefix).slice(0, 22), params: clone(T.params) }) }, "Поставити на сцену")
    )
  );
  root.append(...K(sec));
  const slots = S.slots.filter((s) => s.layer_id === ly.id);
  const total = slots.reduce((a, s) => a + cellCount(s), 0);
  root.append(
    ...K(
      h(
        "div",
        { class: "sec" },
        h("h3", null, `Місця шару · ${slots.length}`),
        slots.length ? h(
          "div",
          { class: "rowlist" },
          slots.map(
            (s) => h(
              "div",
              {
                class: "it" + (S.sel && S.sel.id === s.id ? " sel" : ""),
                role: "button",
                tabindex: 0,
                onclick: () => {
                  E.selectObj({ kind: "slot", id: s.id });
                  E.focusOn(s.x, s.y);
                },
                onkeydown: (e) => {
                  if (e.key === "Enter") {
                    E.selectObj({ kind: "slot", id: s.id });
                    E.focusOn(s.x, s.y);
                  }
                }
              },
              h("span", { class: "t" }, (s.template === "zone" && s.params.title && s.params.title !== s.code_prefix ? s.params.title + " · " : "") + s.code_prefix),
              h("span", { class: "tag" }, TPL[s.template].name.split(" ")[0]),
              h("span", { class: "m" }, SOLID_SLOTS.includes(s.template) ? cellCount(s) + " ком." : "—")
            )
          )
        ) : h("div", { class: "empty" }, "На цьому шарі місць ще немає."),
        h("div", { class: "small muted", style: { marginTop: "6px" } }, `Комірок на шарі: ${fmtInt(total)}`)
      )
    )
  );
}
function renderCatalogTab(root) {
  const q = (S.ui.catQ || "").toLowerCase();
  const canCat = canCatalog();
  root.append(
    ...K(
      h(
        "div",
        { class: "sec" },
        h("h3", null, "Каталог обладнання", h("button", { class: "fbtn sm", type: "button", disabled: !canCat, onclick: () => E.openPassportForm(null) }, ic("plus"), "Тип")),
        h("input", {
          type: "text",
          placeholder: "Пошук: тип, виробник, модель",
          value: S.ui.catQ || "",
          "aria-label": "Пошук",
          style: { width: "100%" },
          oninput: (e) => {
            S.ui.catQ = e.target.value;
            const pos = e.target.selectionStart;
            renderLeft();
            const ni = $("#leftBody input[type=text]");
            if (ni) {
              ni.focus();
              ni.setSelectionRange(pos, pos);
            }
          }
        })
      )
    )
  );
  if (!canCat) {
    root.append(h("div", { class: "note lock", style: { marginBottom: "8px" } }, S.app.mode === "edit" ? "Каталог редагують Менеджер і Технолог." : "Режим перегляду."));
  }
  for (const [ck, cn] of Object.entries(CATEGORIES)) {
    const pps = S.catalog.filter((p) => p.category === ck && (!q || (p.name + " " + p.manufacturer + " " + p.model + " " + p.variants.map((v) => v.name).join(" ")).toLowerCase().includes(q)));
    if (!pps.length) {
      continue;
    }
    root.append(
      ...K(
        h(
          "details",
          { class: "cat", open: true },
          h("summary", null, cn, h("span", { class: "c" }, pps.reduce((a, p) => a + p.variants.length, 0))),
          pps.map(
            (p) => h(
              "div",
              { class: "pp" },
              h("div", { class: "ph" }, h("b", null, p.name), h("button", { class: "fbtn sm", type: "button", title: "Тип: виробник, модель, категорія", onclick: () => E.openPassportForm(p) }, "Тип")),
              h("div", { class: "mf" }, [p.manufacturer, p.model].filter((x) => x && x !== "—").join(" · ") || "без виробника"),
              p.variants.map(
                (v) => h(
                  "div",
                  {
                    class: "var",
                    draggable: "true",
                    "data-variant": v.id,
                    title: "Перетягніть на сцену",
                    ondragstart: (e) => {
                      e.dataTransfer.setData("text/f3d-variant", v.id);
                      e.dataTransfer.setData("text/plain", v.name);
                      e.dataTransfer.effectAllowed = "copy";
                    }
                  },
                  h("span", { class: "vn" }, v.name),
                  h("span", { class: "vm" }, `${fmt(v.length / 1e3, 1)}×${fmt(v.width / 1e3, 1)}×${fmt(v.height / 1e3, 1)} м`, v.model && v.model.status === "ok" ? h("span", { class: "tag", title: "Є 3D-модель" }, "3D") : v.model && v.model.status === "pending_conversion" ? h("span", { class: "tag", title: "Очікує перетворення на сервері" }, "3D…") : null),
                  h("button", { class: "fbtn sm icon", type: "button", title: "Поставити на сцену", "aria-label": "Поставити на сцену", onclick: () => E.startPlacing({ kind: "placement", variantId: v.id }) }, ic("plus")),
                  h("button", { class: "fbtn sm", type: "button", title: "Картка варіанта: габарити, сервіс, 3D-модель", onclick: () => E.openVariantForm(v, p) }, "Змінити")
                )
              ),
              h("button", { class: "fbtn sm", type: "button", disabled: !canCat, onclick: () => E.openVariantForm(null, p) }, ic("plus"), "Варіант")
            )
          )
        )
      )
    );
  }
  root.append(
    ...K(
      h(
        "div",
        { class: "sec", style: { marginTop: "12px" } },
        h("h3", null, "Підкладка"),
        h("button", { class: "fbtn", type: "button", onclick: () => E.openDxfPanel() }, ic("upload"), "Підкладка DXF"),
        h("div", { class: "small muted", style: { marginTop: "4px" } }, "DXF для обведення в масштабі; DWG — на сервері.")
      )
    )
  );
}
function renderVTools() {
  const box = $("#vtools");
  if (!box) {
    return;
  }
  const b = (icon, label, fn, pressed) => h("button", { class: "fbtn", type: "button", onclick: fn, "aria-pressed": pressed == null ? null : String(!!pressed), title: label, "aria-label": label }, ic(icon), h("span", { class: "lg" }, label));
  box.replaceChildren(
    ...K(
      b("cube", "3D", () => E.setView("iso")),
      b("plan", "План", () => E.setView("plan")),
      b("fit", "Вписати", () => E.setView(V.camMode || "iso")),
      b("ruler", "Лінійка", () => {
        const on = !V.ruler.on;
        E.cancelModes();
        V.ruler.on = on;
        if (on) {
          toast("Лінійка: клацніть дві точки на підлозі активного шару.");
        }
        renderVTools();
      }, V.ruler.on),
      b("tag", "Підписи", () => {
        S.settings.labels = !S.settings.labels;
        E.requestRender();
        renderVTools();
      }, S.settings.labels),
      V.placing ? h("button", { class: "fbtn danger", type: "button", onclick: E.cancelModes }, ic("x"), h("span", null, "Скасувати")) : null
    )
  );
}
function renderStamp() {
  const st = $("#stamp");
  if (!st || !S.site) {
    return;
  }
  const ly = layerOf(S.ui.layer);
  st.replaceChildren(
    ...K(
      h("div", null, "Площадка"),
      h("div", { class: "mono" }, S.site.name.length > 22 ? S.site.name.slice(0, 21) + "…" : S.site.name),
      h("div", null, "Шар"),
      h("div", { class: "mono" }, ly ? ly.name : "—"),
      h("div", null, "Відмітка"),
      h("div", { class: "mono" }, ly ? (ly.elevation >= 0 ? "+" : "") + fmt(ly.elevation, 1) + " м" : "—"),
      h("div", null, "Сітка"),
      h("div", { class: "mono" }, ly ? fmt(ly.grid_step, 2) + " м" : "—"),
      h("div", null, "Курсор"),
      h("div", { class: "mono", id: "curPos" }, "—"),
      h("div", null, "Об’єкт"),
      h("div", { class: "mono", id: "hoverName", style: { overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: "190px" } }, "—")
    )
  );
}
function updateStamp() {
  const el = $("#curPos");
  if (el) {
    el.textContent = `x ${fmt(V.cursor.x, 1)} · y ${fmt(V.cursor.y, 1)}`;
  }
}
function renderNotice() {
  const box = $("#vnotice");
  if (!box) {
    return;
  }
  box.replaceChildren();
  if (S.saveState === "error") {
    box.append(h("div", { class: "note err" }, "Не вдалося зберегти зміни на сервері. Чернетка лишається в пам’яті, повтор виконується автоматично."));
  }
}
Object.assign(E, {
  renderTop,
  renderMenu,
  renderSaveState,
  renderChips,
  renderLeft,
  renderAll,
  renderLayerList,
  renderLayerForm,
  renderVTools,
  renderStamp,
  updateStamp,
  renderNotice,
  setActiveLayer,
  setLeftTab,
  setMTab,
  updateTabs,
  isNarrow,
  curTheme
});
registries.panels.add("left:layers", { area: "left", tab: "layers", label: "Шари", render: renderLayersTab }, { sequence: 10, force: true });
registries.panels.add("left:slots", { area: "left", tab: "slots", label: "Місця", render: renderSlotsTab }, { sequence: 20, force: true });
registries.panels.add("left:catalog", { area: "left", tab: "catalog", label: "Каталог", render: renderCatalogTab }, { sequence: 30, force: true });

// core/constructor/panels_right.js
function selectObj(ref2) {
  S.sel = ref2 ? { kind: ref2.kind, id: ref2.id } : null;
  S.selCell = null;
  S.edit = null;
  if (ref2) {
    const rec = recOfRef(ref2);
    if (rec && rec.layer_id !== S.ui.layer) {
      S.ui.layer = rec.layer_id;
      S.issues = runLive();
      E.syncScene();
      E.renderLayerList();
      E.renderLayerForm();
      E.renderStamp();
    }
  }
  renderRight();
  E.updateVisual();
  const rb = $("#rightBody");
  if (rb) {
    rb.scrollTop = 0;
  }
  if (S.ui.leftTab === "slots") {
    E.renderLeft();
  }
  if (ref2 && E.isNarrow() && $("#app").dataset.mtab !== "props") {
    $("#app").dataset.mtab = "props";
    E.updateTabs();
  }
}
function beginEdit(kind, rec) {
  if (!S.edit || S.edit.rec !== rec) {
    S.edit = { kind, rec, snap: clone(rec), before: S.issues };
  }
}
function liveEdit() {
  S.issues = runLive();
  E.syncScene();
  renderChecksBlock();
  E.renderChips();
  E.renderLayerList();
  renderDerived();
  renderCellsBox();
  E.scheduleSave();
}
function restoreRec(rec, snap) {
  for (const k of Object.keys(rec)) {
    if (!(k in snap)) {
      delete rec[k];
    }
  }
  for (const k of Object.keys(snap)) {
    rec[k] = clone(snap[k]);
  }
}
function endEdit() {
  const e = S.edit;
  if (!e) {
    return;
  }
  S.edit = null;
  const after = runLive();
  const key = objKey(e.kind, e.rec.id);
  const nb = newBlocks(e.before, after, key);
  if (nb.length) {
    restoreRec(e.rec, e.snap);
    S.issues = runLive();
    E.syncScene();
    toast("Заблоковано: " + nb[0].msg + ". Значення повернуто.", "err");
    renderRight();
    E.renderChips();
    E.renderLayerList();
    E.scheduleSave();
    return;
  }
  S.issues = after;
  E.updateVisual();
  renderChecksBlock();
}
function syncPropsValues() {
  const rec = S.sel && recOfRef(S.sel);
  if (!rec) {
    return;
  }
  $$("#rightBody [data-f]").forEach((el) => {
    if (document.activeElement === el) {
      return;
    }
    const f = el.dataset.f;
    const v = f.startsWith("p.") ? getp(rec.params, f.slice(2)) : rec[f];
    if (v != null && el.type === "number") {
      el.value = String(rnd(v, 4));
    }
  });
  renderDerived();
}
function renderRight() {
  const root = $("#rightBody");
  if (!root) {
    return;
  }
  root.replaceChildren();
  const rec = S.sel && recOfRef(S.sel);
  if (!rec) {
    S.sel = null;
    renderSiteProps(root);
  } else if (S.sel.kind === "placement") {
    renderPlacementProps(root, rec);
  } else {
    renderSlotProps(root, rec);
  }
  renderPanelBlocks("right", root, { rec });
}
function renderPanelBlocks(area, root, ctx2) {
  forEachEntry(registries.panels, (_key, p) => p.area === area && p.render(root, ctx2), ctx2);
}
registries.panels.add(
  "right:checks",
  {
    area: "right",
    render(root) {
      root.append(h("div", { class: "sec", id: "checksBlock" }));
      renderChecksBlock();
    }
  },
  { sequence: 90, force: true }
);
function renderSiteProps(root) {
  const dis = !canManage();
  const b = S.site.building;
  const cg = S.site.column_grid;
  const upd = () => {
    S.issues = runLive();
    E.syncScene(true);
    E.setView(V.camMode || "iso");
    E.renderChips();
    E.saveSiteProps();
  };
  root.append(
    ...K(
      h(
        "div",
        { class: "sec" },
        h("h3", null, "Площадка"),
        dis ? h("div", { class: "note lock", style: { marginBottom: "8px" } }, S.app.mode === "edit" ? "Параметри площадки змінює Менеджер." : lockHint(layerOf(S.ui.layer))) : null,
        h(
          "div",
          { class: "fcol" },
          fld("Назва", textInput({ value: S.site.name, dis, label: "Назва", set: (v) => {
            S.site.name = v;
            const e = S.app.sites.find((s) => s.id === S.site.id);
            if (e) {
              e.name = v;
            }
            E.renderTop();
            E.renderStamp();
            E.saveSiteProps();
          } })),
          h(
            "div",
            { class: "grid3" },
            fld("Довжина", numInput({ value: b.length, dis, min: 5, max: 1e3, step: 1, label: "Довжина", set: (v) => {
              b.length = v;
              upd();
            } }), "м"),
            fld("Ширина", numInput({ value: b.width, dis, min: 5, max: 1e3, step: 1, label: "Ширина", set: (v) => {
              b.width = v;
              upd();
            } }), "м"),
            fld("Висота", numInput({ value: b.height, dis, min: 2, max: 60, step: 0.5, label: "Висота", set: (v) => {
              b.height = v;
              upd();
            } }), "м")
          ),
          h(
            "div",
            { class: "grid2" },
            fld("Крок колон X", numInput({ value: cg.step_x, dis, min: 0, max: 100, step: 1, label: "Крок колон X", set: (v) => {
              cg.step_x = v;
              upd();
            } }), "м"),
            fld("Крок колон Y", numInput({ value: cg.step_y, dis, min: 0, max: 100, step: 1, label: "Крок колон Y", set: (v) => {
              cg.step_y = v;
              upd();
            } }), "м")
          ),
          h("div", { class: "small muted" }, `Активна версія: ${S.site.active_version ? "v" + S.site.active_version.n : "не опубліковано"}. Об’єктів: ${S.slots.length} місць, ${S.placements.length} одиниць обладнання.`),
          h("div", { class: "note" }, "Клацніть об’єкт на сцені або в списках, щоб побачити точні параметри. Перетягування працює з прив’язкою до сітки активного шару.")
        )
      )
    )
  );
  renderPanelBlocks("site", root, { rec: null });
}
var lockNote = (ly) => canEditLayer(ly) ? null : h("div", { class: "note lock", style: { marginBottom: "8px" } }, ic("lock"), " ", lockHint(ly));
function renderPlacementProps(root, pl) {
  const ly = layerOf(pl.layer_id);
  const dis = !canEditLayer(ly);
  const v = variantOf(pl.variant_id);
  const kind = "placement";
  const ed = { begin: () => beginEdit(kind, pl), end: endEdit };
  const set = (fn) => (val) => {
    fn(val);
    liveEdit();
  };
  const opts = [];
  for (const p of S.catalog) {
    for (const x of p.variants) {
      opts.push([x.id, `${p.name} — ${x.name}`]);
    }
  }
  const rots = rotationsList(v);
  const eq = pl.equipment;
  root.append(
    ...K(
      h(
        "div",
        { class: "sec" },
        h("h3", null, "Обладнання"),
        lockNote(ly),
        pl.dynamic ? h("div", { class: "note", id: "dynamicNote" }, "Динамічний об’єкт (люди, транспорт): не враховується в перевірках перетинів, проходів, обслуговування й пожежних шляхів.") : null,
        h(
          "div",
          { class: "fcol" },
          h(
            "div",
            { class: "grid2" },
            fld("Код", textInput({ value: pl.code, dis, label: "Код", f: "code", set: set((x) => {
              pl.code = x;
            }), ...ed })),
            fld("Назва", textInput({ value: pl.name, dis, label: "Назва", f: "name", set: set((x) => {
              pl.name = x;
            }), ...ed }))
          ),
          fld("Варіант (тип обладнання)", selectEl(opts, pl.variant_id, (x) => {
            beginEdit(kind, pl);
            pl.variant_id = x;
            liveEdit();
            endEdit();
            renderRight();
          }, dis, "Варіант")),
          h(
            "div",
            { class: "grid3" },
            fld("x", numInput({ value: pl.x, dis, step: snapStep(pl), f: "x", label: "x", set: set((x) => {
              pl.x = x;
            }), ...ed }), "м"),
            fld("y", numInput({ value: pl.y, dis, step: snapStep(pl), f: "y", label: "y", set: set((x) => {
              pl.y = x;
            }), ...ed }), "м"),
            fld(
              "Поворот",
              rots ? selectEl(rots.map((r) => [r, r + "°"]), normDeg(Math.round(pl.rotation || 0)), (x) => {
                beginEdit(kind, pl);
                pl.rotation = Number(x);
                liveEdit();
                endEdit();
              }, dis, "Поворот") : numInput({ value: pl.rotation || 0, dis, step: 15, f: "rotation", label: "Поворот", set: set((x) => {
                pl.rotation = normDeg(x);
              }), ...ed }),
              rots ? null : "°"
            )
          ),
          h("div", { id: "derived" }),
          eq ? h("div", { class: "small" }, "Запис в Odoo: ", h("a", { href: "#", onclick: (e) => {
            e.preventDefault();
            E.openRecord("maintenance.equipment", eq.id);
          } }, eq.name)) : null,
          h(
            "div",
            { class: "frow wrap" },
            h("button", { class: "fbtn sm", type: "button", id: "btnRotate", disabled: dis, onclick: () => rotateSel(1) }, ic("rot"), "Повернути 90°"),
            h("button", { class: "fbtn sm", type: "button", onclick: () => {
              const x = variantOf(pl.variant_id);
              if (x) {
                E.openVariantForm(x, passportOf(x.id));
              }
            } }, "Картка варіанта"),
            h("span", { class: "grow" }),
            h("button", { class: "fbtn sm danger", type: "button", id: "btnDelete", disabled: dis, onclick: askDelete }, ic("trash"), "Видалити")
          )
        )
      )
    )
  );
  renderPanelBlocks("placement", root, { rec: pl });
  renderDerived();
}
function renderDerived() {
  const box = $("#derived");
  if (!box || !S.sel) {
    return;
  }
  const rec = recOfRef(S.sel);
  if (!rec) {
    return;
  }
  if (S.sel.kind === "placement") {
    const v = variantOf(rec.variant_id);
    const p = passportOf(rec.variant_id);
    if (!v) {
      return;
    }
    const g3 = pGeom(rec, v);
    const host2 = rec.slot_id ? S.sIdx.get(rec.slot_id) : null;
    const q = v.floor_load != null && v.floor_load !== "" ? Number(v.floor_load) : v.weight_kg * 9.81 / 1e3 / Math.max(g3.L * g3.W, 0.01);
    box.replaceChildren(
      ...K(
        h(
          "dl",
          { class: "kv" },
          h("dt", null, "Тип"),
          h("dd", null, p.name),
          h("dt", null, "Виробник"),
          h("dd", null, p.manufacturer || "—"),
          h("dt", null, "Габарит"),
          h("dd", null, `${fmt(g3.L, 2)} × ${fmt(g3.W, 2)} м · ${normDeg(Math.round(rec.rotation || 0))}°`),
          h("dt", null, "Охоплення AABB"),
          h("dd", null, `${fmt(g3.box[2] - g3.box[0], 2)} × ${fmt(g3.box[3] - g3.box[1], 2)} м`),
          h("dt", null, "Центр"),
          h("dd", null, `${fmt(g3.cx, 2)} ; ${fmt(g3.cy, 2)}`),
          h("dt", null, "Потужність"),
          h("dd", null, v.power_kw ? fmt(v.power_kw, 1) + " кВт" : "—"),
          h("dt", null, "Маса · на підлогу"),
          h("dd", null, `${fmtInt(v.weight_kg)} кг · ${fmt(q, 1)} кН/м²`),
          h("dt", null, "Місце"),
          h("dd", null, host2 ? host2.code_prefix : "—")
        )
      )
    );
  } else {
    const d = slotDims(rec);
    const n = cellCount(rec);
    const cap = cellsOf(rec).reduce((a, c) => a + (c.disabled ? 0 : c.capacity || 0), 0);
    box.replaceChildren(
      ...K(
        h(
          "dl",
          { class: "kv" },
          h("dt", null, "Шаблон"),
          h("dd", null, TPL[rec.template].name),
          h("dt", null, "Габарит"),
          h("dd", null, `${fmt(d.L, 2)} × ${fmt(d.W, 2)} м`),
          SOLID_SLOTS.includes(rec.template) ? [h("dt", null, "Комірок"), h("dd", { id: "cellCount" }, fmtInt(n)), h("dt", null, "Місткість"), h("dd", null, fmtInt(cap))] : null
        )
      )
    );
  }
}
function renderSlotProps(root, s) {
  const ly = layerOf(s.layer_id);
  const dis = !canEditLayer(ly) || !!s.locked;
  const kind = "slot";
  const ed = { begin: () => beginEdit(kind, s), end: endEdit };
  const set = (fn) => (val) => {
    fn(val);
    liveEdit();
  };
  const spec = TPL[s.template];
  root.append(
    ...K(
      h(
        "div",
        { class: "sec" },
        h("h3", null, spec.name),
        lockNote(ly),
        s.locked ? h("div", { class: "note lock" }, "Складний контур зони редагується у формі Odoo.") : null,
        h(
          "div",
          { class: "fcol" },
          h(
            "div",
            { class: "grid2" },
            fld("Код / префікс", textInput({ value: s.code_prefix, dis, label: "Префікс", f: "code_prefix", set: set((x) => {
              s.code_prefix = x.slice(0, 22);
            }), ...ed })),
            fld("Шар", h("input", { type: "text", value: ly.name, disabled: true }))
          ),
          h(
            "div",
            { class: "grid3" },
            fld("x", numInput({ value: s.x, dis, step: snapStep(s), f: "x", label: "x", set: set((x) => {
              s.x = x;
            }), ...ed }), "м"),
            fld("y", numInput({ value: s.y, dis, step: snapStep(s), f: "y", label: "y", set: set((x) => {
              s.y = x;
            }), ...ed }), "м"),
            fld("Поворот", numInput({ value: s.rotation || 0, dis, step: 15, f: "rotation", label: "Поворот", set: set((x) => {
              s.rotation = normDeg(x);
            }), ...ed }), "°")
          ),
          paramFields(s.template, s.params, { dis, begin: ed.begin, end: ed.end, onChange: () => liveEdit() }),
          h("div", { id: "derived" }),
          h(
            "div",
            { class: "frow wrap" },
            h("button", { class: "fbtn sm", type: "button", id: "btnRotate", disabled: dis, onclick: () => rotateSel(1) }, ic("rot"), "Повернути 90°"),
            h("span", { class: "grow" }),
            h("button", { class: "fbtn sm danger", type: "button", id: "btnDelete", disabled: dis, onclick: askDelete }, ic("trash"), "Видалити")
          )
        )
      )
    )
  );
  if (SOLID_SLOTS.includes(s.template)) {
    root.append(h("div", { class: "sec", id: "cellsBox" }));
  }
  renderPanelBlocks("slot", root, { rec: s });
  renderDerived();
  renderCellsBox();
}
function renderCellsBox() {
  const box = $("#cellsBox");
  if (!box || !S.sel || S.sel.kind !== "slot") {
    return;
  }
  const s = S.sIdx.get(S.sel.id);
  if (!s) {
    return;
  }
  const ly = layerOf(s.layer_id);
  const dis = !canEditLayer(ly);
  const cells = cellsOf(s);
  const lim = S.ui.cellsAll ? cells.length : 120;
  const nOv = Object.keys(s.overrides || {}).length;
  const rows = cells.slice(0, lim).map(
    (c) => h(
      "tr",
      {
        class: (S.selCell === c.code ? "sel " : "") + (c.ov ? "ov " : "") + (c.disabled ? "blk" : ""),
        "data-code": c.code,
        onclick: () => {
          S.selCell = S.selCell === c.code ? null : c.code;
          E.updateVisual();
          renderCellsBox();
        }
      },
      h("td", null, c.code),
      h("td", null, c.capacity == null ? "—" : c.capacity),
      h("td", null, c.max_load_kg == null ? "—" : fmtInt(c.max_load_kg))
    )
  );
  box.replaceChildren(
    ...K(
      h("h3", { class: "h3" }, `Комірки · ${fmtInt(cells.filter((c) => !c.disabled).length)}`),
      h("div", { class: "scroll" }, h("table", { class: "cells" }, h("thead", null, h("tr", null, h("th", null, "Код"), h("th", null, "Місць"), h("th", null, "Макс. кг"))), h("tbody", null, rows))),
      cells.length > lim ? h("button", { class: "fbtn sm", type: "button", style: { marginTop: "6px" }, onclick: () => {
        S.ui.cellsAll = true;
        renderCellsBox();
      } }, `Показати всі (${cells.length})`) : null,
      h("div", { class: "small muted", style: { marginTop: "4px" } }, "Це майбутні stock.location із td_code, barcode і місткістю (створюються при публікації). Позначені рядки — ручна правка комірки.")
    )
  );
  const sc = S.selCell && cells.find((c) => c.code === S.selCell);
  if (sc) {
    const setOv = (key, val) => {
      s.overrides = s.overrides || {};
      const o = s.overrides[sc.code] = s.overrides[sc.code] || {};
      if (val === false || val == null) {
        delete o[key];
      } else {
        o[key] = val;
      }
      if (!Object.keys(o).length) {
        delete s.overrides[sc.code];
      }
      liveEdit();
    };
    box.append(
      ...K(
        h(
          "div",
          { class: "note", style: { marginTop: "8px" } },
          h("div", { class: "h3" }, "Комірка " + sc.code),
          h(
            "div",
            { class: "grid2" },
            fld("Місткість", numInput({ value: sc.capacity, dis, min: 0, step: 1, label: "Місткість", set: (v) => setOv("capacity", v) })),
            fld("Макс. навантаження", numInput({ value: sc.max_load_kg, dis, min: 0, step: 50, label: "Макс. навантаження", set: (v) => setOv("max_load_kg", v) }), "кг")
          ),
          h("label", { class: "frow", style: { marginTop: "6px" } }, h("input", { type: "checkbox", checked: !!sc.disabled, disabled: dis, onchange: (e) => setOv("disabled", e.target.checked) }), "Не використовувати (вимкнена)"),
          h("button", { class: "fbtn sm", type: "button", style: { marginTop: "6px" }, disabled: dis || !sc.ov, onclick: () => {
            delete s.overrides[sc.code];
            liveEdit();
          } }, "Скинути ручні правки")
        )
      )
    );
  }
  if (nOv) {
    box.append(h("div", { class: "small muted", style: { marginTop: "6px" } }, `Ручних правок: ${nOv}`));
  }
}
var MODE_OPTS = [["warn", "Попередження"], ["block", "Заборона"]];
function issueRow(it, selKey) {
  return h(
    "div",
    { class: "issue " + it.level, role: "button", tabindex: 0, onclick: () => gotoIssue(it, selKey), onkeydown: (e) => {
      if (e.key === "Enter") {
        gotoIssue(it, selKey);
      }
    } },
    h("div", { class: "im" }, it.msg, h("div", { class: "io" }, (it.level === "block" ? "ЗАБОРОНА" : "ПОПЕРЕДЖЕННЯ") + " · " + (CHECKS.find((c) => c.id === it.check) || {}).name))
  );
}
function gotoIssue(it, selKey) {
  const key = it.keys.find((k) => k !== selKey) || it.keys[0];
  const ref2 = { kind: key.startsWith("p:") ? "placement" : "slot", id: key.slice(2) };
  const rec = recOfRef(ref2);
  if (!rec) {
    return;
  }
  selectObj(ref2);
  E.focusOn(rec.x, rec.y);
}
function renderChecksBlock() {
  const box = $("#checksBlock");
  if (!box) {
    return;
  }
  const selKey = S.sel ? objKey(S.sel.kind, S.sel.id) : null;
  const ly = layerOf(S.ui.layer);
  const all = S.issues.list;
  const mine = selKey ? all.filter((i) => i.keys.includes(selKey)) : [];
  const layerList = all.filter((i) => i.layerId === S.ui.layer && !mine.includes(i));
  const nb = all.filter((i) => i.level === "block").length;
  const nw = all.length - nb;
  const frag = [
    h(
      "h3",
      null,
      "Перевірки",
      h("span", { class: "frow" }, nb ? h("span", { class: "fbadge b" }, nb + " заборон") : null, nw ? h("span", { class: "fbadge w" }, nw + " попер.") : null, !all.length ? h("span", { class: "fbadge ok" }, "усе гаразд") : null)
    )
  ];
  if (selKey) {
    frag.push(h("div", { class: "lbl", style: { margin: "4px 0" } }, "Вибраний об’єкт"), mine.length ? h("div", { class: "issues" }, mine.map((i) => issueRow(i, selKey))) : h("div", { class: "small muted" }, "Зауважень немає."));
  }
  frag.push(h("div", { class: "lbl", style: { margin: "8px 0 4px" } }, `Шар «${ly ? ly.name : ""}»`), layerList.length ? h("div", { class: "issues" }, layerList.slice(0, 40).map((i) => issueRow(i, selKey))) : h("div", { class: "small muted" }, "Зауважень немає."));
  if (layerList.length > 40) {
    frag.push(h("div", { class: "small muted" }, `… ще ${layerList.length - 40}`));
  }
  if (can("check")) {
    frag.push(h("button", { class: "fbtn sm", type: "button", id: "btnValidate", style: { marginTop: "8px" }, onclick: () => E.validateOnServer() }, ic("check"), "Перевірити на сервері"));
  }
  const dis = !canManage();
  const cfg = S.settings.checks;
  frag.push(
    h(
      "details",
      { style: { marginTop: "10px" }, open: S.ui.cfgOpen, ontoggle: (e) => {
        S.ui.cfgOpen = e.target.open;
      } },
      h("summary", { class: "lbl", style: { cursor: "pointer" } }, "Налаштування перевірок"),
      dis ? h("div", { class: "note lock", style: { margin: "6px 0" } }, "Налаштування змінює Менеджер.") : null,
      CHECKS.filter((c) => cfg[c.id]).map(
        (c) => h(
          "div",
          { class: "frow", style: { margin: "5px 0" }, title: c.hint },
          h("input", { type: "checkbox", checked: cfg[c.id].enabled, disabled: dis, "aria-label": c.name, onchange: (e) => {
            cfg[c.id].enabled = e.target.checked;
            liveCfg(c.id);
          } }),
          h("span", { style: { flex: 1, minWidth: 0 } }, c.name),
          selectEl(MODE_OPTS, cfg[c.id].mode, (v) => {
            cfg[c.id].mode = v;
            liveCfg(c.id);
          }, dis, c.name)
        )
      ),
      cfg.utility_reach ? h("div", { class: "frow", style: { marginTop: "6px" } }, h("span", { style: { flex: 1 } }, "Макс. відстань до точки мережі, N"), numInput({ value: S.settings.reach_n, dis, min: 1, max: 200, step: 1, label: "N", set: (v) => {
        S.settings.reach_n = v;
        cfg.utility_reach.params = { ...cfg.utility_reach.params, max_m: v };
        liveCfg("utility_reach");
      } }), "м") : null
    )
  );
  box.replaceChildren(...K(frag));
}
function liveCfg(check) {
  S.issues = runLive();
  E.updateVisual();
  E.renderChips();
  renderChecksBlock();
  const c = S.settings.checks[check];
  E.adapter.saveCheck(check, { enabled: c.enabled, mode: c.mode, params: c.params || {} });
}
function rotateSel(dir) {
  if (!S.sel) {
    return;
  }
  const rec = recOfRef(S.sel);
  const ly = layerOf(rec.layer_id);
  if (!canEditLayer(ly)) {
    toastLock(ly);
    return;
  }
  if (rec.locked) {
    return;
  }
  const kind = S.sel.kind;
  beginEdit(kind, rec);
  let next = normDeg((rec.rotation || 0) + 90 * dir);
  if (kind === "placement") {
    const al = rotationsList(variantOf(rec.variant_id));
    if (al) {
      let c = rec.rotation || 0;
      let ok = null;
      for (let i = 0; i < 4; i++) {
        c = normDeg(c + 90 * dir);
        if (al.includes(c)) {
          ok = c;
          break;
        }
      }
      if (ok == null) {
        toast("Для цього варіанта поворот не дозволено", "warn");
        S.edit = null;
        return;
      }
      next = ok;
    }
  }
  rec.rotation = next;
  liveEdit();
  endEdit();
  renderRight();
  const ne = S.issues.byKey.get(objKey(kind, rec.id));
  if (ne && ne.level === "warn") {
    toast(ne.items[0].msg, "warn");
  }
}
async function askDelete() {
  if (!S.sel) {
    return;
  }
  const rec = recOfRef(S.sel);
  const ly = layerOf(rec.layer_id);
  if (!canEditLayer(ly)) {
    toastLock(ly);
    return;
  }
  const nm = rec.code || rec.code_prefix || rec.name;
  const extra = S.sel.kind === "slot" && cellCount(rec) ? ` Буде видалено ${cellCount(rec)} комірок.` : "";
  const ok = await E.confirmBox({ title: "Видалити об’єкт?", text: `«${nm}» буде видалено з чернетки.${extra}`, ok: "Видалити", danger: true });
  if (!ok) {
    return;
  }
  if (S.sel.kind === "placement") {
    S.placements = S.placements.filter((p) => p.id !== rec.id);
  } else {
    S.slots = S.slots.filter((s) => s.id !== rec.id);
    for (const p of S.placements) {
      if (p.slot_id === rec.id) {
        p.slot_id = null;
      }
    }
  }
  S.sel = null;
  S.selCell = null;
  E.commit({});
}
var CODE_PREFIX = { machine: "M", rack: "RK", forklift: "FL", conveyor: "CV", panel: "SW", robot: "RB" };
function addPlacementAt(variantId, x, y, snap) {
  const ly = layerOf(S.ui.layer);
  const v = variantOf(variantId);
  if (!ly || !v) {
    return;
  }
  if (!canEditLayer(ly)) {
    toastLock(ly);
    return;
  }
  const st = ly.grid_step || 0.5;
  const cat = (passportOf(variantId) || {}).category;
  const pre = CODE_PREFIX[cat] || "EQ";
  let n = 1;
  while (S.placements.some((p) => p.code === pre + "-" + pad2(n))) {
    n++;
  }
  const pl = {
    id: newUid(),
    rid: null,
    etag: null,
    layer_id: ly.id,
    variant_id: v.id,
    slot_id: null,
    cell_code: null,
    x: snap ? snapV(x, st) : x,
    y: snap ? snapV(y, st) : y,
    rotation: 0,
    code: pre + "-" + pad2(n),
    name: v.name,
    equipment: null
  };
  const before = S.issues;
  S.placements.push(pl);
  S.pIdx.set(pl.id, pl);
  E.assignSlot(pl);
  const after = runLive();
  const nb = newBlocks(before, after, "p:" + pl.id);
  if (nb.length) {
    S.placements.pop();
    S.pIdx.delete(pl.id);
    toast("Заблоковано: " + nb[0].msg, "err");
    return;
  }
  S.sel = { kind: "placement", id: pl.id };
  E.commit({});
  const st2 = S.issues.byKey.get("p:" + pl.id);
  if (st2) {
    toast(st2.items[0].msg, "warn");
  }
}
function addSlotAt(spec, x, y) {
  const ly = layerOf(S.ui.layer);
  if (!ly) {
    return;
  }
  const s = { id: newUid(), rid: null, etag: null, layer_id: ly.id, template: spec.template, code_prefix: spec.prefix, x, y, rotation: 0, params: clone(spec.params), overrides: {}, parent_location_id: null };
  const before = S.issues;
  S.slots.push(s);
  S.sIdx.set(s.id, s);
  const after = runLive();
  const nb = newBlocks(before, after, "s:" + s.id);
  if (nb.length) {
    S.slots.pop();
    S.sIdx.delete(s.id);
    toast("Заблоковано: " + nb[0].msg, "err");
    return;
  }
  S.sel = { kind: "slot", id: s.id };
  E.commit({});
  const n = cellCount(s);
  toast(n ? `Створено місце «${s.code_prefix}»: ${fmtInt(n)} комірок.` : `Створено місце «${s.code_prefix}».`);
}
function nudge(dx, dy) {
  if (!S.sel) {
    return;
  }
  const rec = recOfRef(S.sel);
  const ly = layerOf(rec.layer_id);
  if (!canEditLayer(ly)) {
    toastLock(ly);
    return;
  }
  if (rec.locked) {
    return;
  }
  const kind = S.sel.kind;
  const st = ly.grid_step || 0.5;
  beginEdit(kind, rec);
  rec.x = rnd(rec.x + dx * st, 4);
  rec.y = rnd(rec.y + dy * st, 4);
  liveEdit();
  endEdit();
  syncPropsValues();
}
Object.assign(E, {
  selectObj,
  beginEdit,
  liveEdit,
  endEdit,
  syncPropsValues,
  renderRight,
  renderDerived,
  renderCellsBox,
  renderChecksBlock,
  rotateSel,
  askDelete,
  addPlacementAt,
  addSlotAt,
  nudge,
  recOf: recOfRef
});

// core/constructor/scene.js
var scene_exports = {};
__export(scene_exports, {
  assignSlot: () => assignSlot,
  buildPlacementView: () => buildPlacementView,
  buildSlotView: () => buildSlotView,
  camTarget: () => camTarget,
  cancelModes: () => cancelModes,
  dashRect: () => dashRect,
  disposeScene: () => disposeScene,
  floorPoint: () => floorPoint,
  focusOn: () => focusOn,
  initScene: () => initScene,
  lineGeo: () => lineGeo,
  pickCandidates: () => pickCandidates,
  poseView: () => poseView,
  recolorMats: () => recolorMats,
  requestRender: () => requestRender,
  resizeScene: () => resizeScene,
  rulerClear: () => rulerClear,
  rulerPoint: () => rulerPoint,
  setView: () => setView,
  startPlacing: () => startPlacing,
  syncScene: () => syncScene,
  syncUnderlays: () => syncUnderlays,
  underlayVertex: () => underlayVertex,
  updateVisual: () => updateVisual,
  variantBody: () => variantBody
});

// core/constructor/three.js
var THREE = {};
var promise = null;
function loadThree() {
  if (!promise) {
    if (typeof host.loadThree !== "function") {
      return Promise.reject(new Error("Хост не передав host.loadThree()"));
    }
    promise = Promise.resolve(host.loadThree()).then((m) => {
      Object.assign(THREE, m);
      return THREE;
    }).catch((e) => {
      promise = null;
      throw e;
    });
  }
  return promise;
}
function getThree() {
  if (!THREE.Vector3) {
    throw new Error("three.js ще не завантажено: спершу await loadThree()");
  }
  return THREE;
}
function webglAvailable() {
  try {
    const c = document.createElement("canvas");
    return !!(c.getContext("webgl2") || c.getContext("webgl"));
  } catch {
    return false;
  }
}

// core/constructor/scene.js
var BODY = { other: "#9ba6b1" };
var UCOL = { electric: "#e0a030", air: "#3a8fd0", dust: "#6aa04a" };
function readColors() {
  const cs = getComputedStyle($("#app") || document.documentElement);
  const g3 = (n) => cs.getPropertyValue(n).trim() || "#888888";
  return {
    scene: g3("--scene"),
    grid: g3("--grid"),
    grid2: g3("--grid2"),
    floor: g3("--floor"),
    stroke: g3("--stroke"),
    accent: g3("--accent"),
    warn: g3("--warn"),
    block: g3("--block"),
    ink: g3("--ink")
  };
}
function initMats() {
  const C = V.col;
  const M = V.mat = {};
  const T = V.themed = [];
  const th = (m, k) => {
    T.push([m, k]);
    return m;
  };
  M.edge = th(new THREE.LineBasicMaterial({ color: C.stroke, transparent: true, opacity: 0.85 }), "stroke");
  M.edgeGhost = th(new THREE.LineBasicMaterial({ color: C.stroke, transparent: true, opacity: 0.22 }), "stroke");
  const dash = (k, o, ds, gs) => th(new THREE.LineDashedMaterial({ color: C[k], dashSize: ds || 0.4, gapSize: gs || 0.22, transparent: true, opacity: o || 0.95 }), k);
  M.dash = { normal: dash("stroke", 0.85), sel: dash("accent"), warn: dash("warn"), block: dash("block") };
  M.dashGhost = dash("stroke", 0.28);
  M.svc = dash("accent", 0.7, 0.18, 0.16);
  M.sel = th(new THREE.LineBasicMaterial({ color: C.accent }), "accent");
  const fl = (k, o) => th(new THREE.MeshBasicMaterial({ color: C[k], transparent: true, opacity: o, depthWrite: false, side: THREE.DoubleSide }), k);
  M.fill = { sel: fl("accent", 0.2), warn: fl("warn", 0.34), block: fl("block", 0.38) };
  M.hit = new THREE.MeshBasicMaterial({ visible: false });
  M.gridMinor = th(new THREE.LineBasicMaterial({ color: C.grid, transparent: true, opacity: 0.75 }), "grid");
  M.gridMajor = th(new THREE.LineBasicMaterial({ color: C.grid2, transparent: true, opacity: 0.9 }), "grid2");
  M.floor = th(new THREE.MeshBasicMaterial({ color: C.floor }), "floor");
  M.bld = th(new THREE.LineBasicMaterial({ color: C.stroke }), "stroke");
  M.col = new THREE.MeshLambertMaterial({ color: "#8a96a3", transparent: true, opacity: 0.5 });
  M.ruler = th(new THREE.LineBasicMaterial({ color: C.accent, depthTest: false }), "accent");
  M.rulerPt = th(new THREE.MeshBasicMaterial({ color: C.accent, depthTest: false }), "accent");
  M.cell = new THREE.MeshLambertMaterial({ color: "#ffffff", transparent: true, opacity: 0.62, depthWrite: false });
  M.cellGhost = new THREE.MeshLambertMaterial({ color: "#ffffff", transparent: true, opacity: 0.16, depthWrite: false });
  M.pt = {};
  for (const k in UCOL) {
    M.pt[k] = new THREE.MeshLambertMaterial({ color: UCOL[k] });
  }
  M.under = th(new THREE.LineBasicMaterial({ color: C.accent, transparent: true, opacity: 0.8 }), "accent");
}
function recolorMats() {
  V.col = readColors();
  for (const [m, k] of V.themed) {
    m.color.set(V.col[k]);
  }
  V.scene.background = new THREE.Color(V.col.scene);
}
function bodyMat(name, ghost) {
  const k = name + (ghost ? "_g" : "");
  let m = V.bodyMats.get(k);
  if (!m) {
    m = new THREE.MeshLambertMaterial({ color: BODY[name] || "#999999", transparent: !!ghost, opacity: ghost ? 0.3 : 1, depthWrite: !ghost });
    V.bodyMats.set(k, m);
  }
  return m;
}
function nullRenderer() {
  return {
    domElement: document.createElement("canvas"),
    setSize() {
    },
    setPixelRatio() {
    },
    // як справжній рендерер: оновлює світові матриці (від них залежать промені вибору й перетягування)
    render(scene, camera) {
      scene.updateMatrixWorld();
      if (camera.parent === null) {
        camera.updateMatrixWorld();
      }
    },
    dispose() {
    },
    forceContextLoss() {
    }
  };
}
function initScene() {
  const host2 = $("#vp");
  let renderer = null;
  if (V.testMode) {
    renderer = nullRenderer();
  } else {
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    } catch {
      host2.append(h("div", { class: "nogl" }, "3D недоступне в цьому браузері. Форми й перевірки працюють, 3D-вид — ні."));
      return false;
    }
  }
  V.renderer = renderer;
  V.ok = true;
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  V.canvas = renderer.domElement;
  V.canvas.tabIndex = 0;
  V.canvas.setAttribute("aria-label", "3D-сцена площадки");
  host2.append(V.canvas);
  V.scene = new THREE.Scene();
  V.col = readColors();
  V.scene.background = new THREE.Color(V.col.scene);
  initMats();
  const G = V.geo;
  G.box = new THREE.BoxGeometry(1, 1, 1);
  G.boxEdges = new THREE.EdgesGeometry(G.box);
  G.cyl = new THREE.CylinderGeometry(1, 1, 1, 18);
  G.plane = new THREE.PlaneGeometry(1, 1).rotateX(-Math.PI / 2);
  G.octa = new THREE.OctahedronGeometry(0.45);
  G.cone = new THREE.ConeGeometry(0.4, 0.9, 10);
  G.sph = new THREE.SphereGeometry(0.4, 12, 8);
  V.camera = new THREE.PerspectiveCamera(42, 1, 0.5, 4e3);
  const lk = Number(THREE.REVISION) >= 155 ? Math.PI : 1;
  V.scene.add(new THREE.AmbientLight(16777215, 0.78 * lk));
  const dl = new THREE.DirectionalLight(16777215, 0.55 * lk);
  dl.position.set(40, 100, 60);
  V.scene.add(dl);
  V.world = new THREE.Group();
  V.scene.add(V.world);
  V.raycaster = new THREE.Raycaster();
  initPointer();
  V.controls = new THREE.OrbitControls(V.camera, V.canvas);
  V.controls.enableDamping = false;
  V.controls.screenSpacePanning = false;
  V.controls.maxPolarAngle = Math.PI * 0.495;
  V.controls.minDistance = 2;
  V.controls.maxDistance = 900;
  V.controls.addEventListener("change", requestRender);
  V.ro = new ResizeObserver(() => resizeScene());
  V.ro.observe(host2);
  resizeScene();
  return true;
}
function disposeScene() {
  cancelAnimationFrame(V.raf);
  cancelAnimationFrame(V.hoverRaf);
  V.raf = 0;
  V.hoverRaf = 0;
  V.ro?.disconnect();
  V.controls?.dispose();
  for (const v of V.views.values()) {
    dispose(v.root);
  }
  for (const d of V.decor.values()) {
    disposeDecor(d.g);
  }
  for (const u of V.underlays.values()) {
    u.o.geometry.dispose();
    u.o.material.dispose();
  }
  if (V.buildingG) {
    const shared = Object.values(V.geo);
    V.buildingG.traverse((o) => {
      if (o.geometry && !shared.includes(o.geometry)) {
        o.geometry.dispose();
      }
    });
  }
  for (const c of V.labelCache.values()) {
    c.tex.dispose();
  }
  for (const m of V.bodyMats.values()) {
    m.dispose();
  }
  for (const g3 of Object.values(V.geo)) {
    g3.dispose?.();
  }
  for (const m of Object.values(V.mat)) {
    if (m && m.dispose) {
      m.dispose();
    } else if (m && typeof m === "object") {
      Object.values(m).forEach((x) => x.dispose?.());
    }
  }
  V.renderer?.dispose();
  V.renderer?.forceContextLoss?.();
  V.ok = false;
}
function resizeScene() {
  if (!V.ok) {
    return;
  }
  const host2 = $("#vp");
  const w = host2.clientWidth;
  const hh = host2.clientHeight;
  if (w < 2 || hh < 2) {
    return;
  }
  V.renderer.setSize(w, hh, false);
  V.camera.aspect = w / hh;
  V.camera.updateProjectionMatrix();
  requestRender();
}
function requestRender() {
  if (V.ok && !V.raf) {
    V.raf = requestAnimationFrame(() => {
      V.raf = 0;
      render();
    });
  }
}
function render() {
  if (!V.ok) {
    return;
  }
  const dist = V.camera.position.distanceTo(V.controls.target);
  const on = S.settings.labels;
  for (const l of V.labels) {
    l.s.visible = on && dist < l.max;
  }
  V.renderer.render(V.scene, V.camera);
  updateRulerLabel();
}
var P3 = (x, y, z) => new THREE.Vector3(x, z || 0, -y);
function setView(kind) {
  if (!V.ok) {
    return;
  }
  V.camMode = kind;
  const b = S.site.building;
  const cx = b.length / 2;
  const cz = -b.width / 2;
  const tgt = new THREE.Vector3(cx, 0, cz);
  const dir = kind === "plan" ? new THREE.Vector3(0, 1, 1e-4) : new THREE.Vector3(-0.42, 0.72, 0.7).normalize();
  const pts = [];
  for (const x of [0, b.length]) {
    for (const y of [0, b.width]) {
      for (const z of [0, b.height]) {
        pts.push(new THREE.Vector3(x, z, -y));
      }
    }
  }
  V.camera.aspect = Math.max(0.2, ($("#vp").clientWidth || 800) / Math.max(1, $("#vp").clientHeight || 600));
  V.camera.updateProjectionMatrix();
  let d = Math.hypot(b.length, b.width) * 0.25;
  for (let i = 0; i < 80; i++) {
    V.camera.position.copy(tgt).addScaledVector(dir, d);
    V.camera.lookAt(tgt);
    V.camera.updateMatrixWorld();
    let ok = true;
    for (const p of pts) {
      const q = p.clone().project(V.camera);
      if (Math.abs(q.x) > 0.97 || Math.abs(q.y) > 0.92 || q.z > 1) {
        ok = false;
        break;
      }
    }
    if (ok) {
      break;
    }
    d *= 1.05;
  }
  const plan = kind === "plan";
  V.controls.enableRotate = !plan;
  V.controls.mouseButtons.LEFT = plan ? THREE.MOUSE.PAN : THREE.MOUSE.ROTATE;
  V.controls.touches.ONE = plan ? THREE.TOUCH.PAN : THREE.TOUCH.ROTATE;
  V.controls.target.copy(tgt);
  V.controls.update();
  requestRender();
}
function focusOn(x, y, dist) {
  if (!V.ok) {
    return;
  }
  const el = V.controls.target.clone();
  const off = V.camera.position.clone().sub(el);
  const nt = P3(x, y, 0);
  if (dist) {
    off.setLength(dist);
  }
  V.controls.target.copy(nt);
  V.camera.position.copy(nt).add(off);
  V.controls.update();
  requestRender();
}
function camTarget() {
  if (!V.ok) {
    return { x: S.site.building.length / 2, y: S.site.building.width / 2 };
  }
  const t = V.controls.target;
  return { x: t.x, y: -t.z };
}
var FONT = '"Arial Narrow", "Roboto Condensed", system-ui, sans-serif';
function makeLabel(text, h0, max, color, flatW) {
  const col = color || V.col.stroke;
  const key = text + "|" + col + "|" + V.theme;
  let c = V.labelCache.get(key);
  if (!c) {
    const cv = document.createElement("canvas");
    const ctx2 = cv.getContext("2d");
    const fs = 34;
    ctx2.font = `500 ${fs}px ${FONT}`;
    const w = Math.ceil(ctx2.measureText(text).width) + 20;
    cv.width = w;
    cv.height = 50;
    ctx2.font = `500 ${fs}px ${FONT}`;
    ctx2.textBaseline = "middle";
    ctx2.lineWidth = 6;
    ctx2.strokeStyle = V.col.scene;
    ctx2.lineJoin = "round";
    ctx2.strokeText(text, 10, 27);
    ctx2.fillStyle = col;
    ctx2.fillText(text, 10, 27);
    const tex = new THREE.CanvasTexture(cv);
    if (THREE.SRGBColorSpace) {
      tex.colorSpace = THREE.SRGBColorSpace;
    }
    tex.minFilter = THREE.LinearFilter;
    tex.generateMipmaps = false;
    c = { tex, aspect: w / 50 };
    V.labelCache.set(key, c);
  }
  let sp;
  if (flatW) {
    if (h0 * c.aspect > flatW) {
      h0 = flatW / c.aspect;
    }
    sp = new THREE.Mesh(V.geo.plane, new THREE.MeshBasicMaterial({ map: c.tex, transparent: true, depthWrite: false }));
    sp.scale.set(h0 * c.aspect, 1, h0);
    sp.renderOrder = 1;
  } else {
    sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: c.tex, transparent: true, depthWrite: false }));
    sp.scale.set(h0 * c.aspect, h0, 1);
  }
  sp.userData.label = true;
  const rec = { s: sp, max: max || 120 };
  V.labels.push(rec);
  sp.userData.rec = rec;
  return sp;
}
function dropLabels(root) {
  root.traverse((o) => {
    if (o.userData.rec) {
      const i = V.labels.indexOf(o.userData.rec);
      if (i >= 0) {
        V.labels.splice(i, 1);
      }
      if (o.material) {
        o.material.dispose();
      }
    }
  });
}
function boxMesh(w, hh, d, x, y, z, mat) {
  const m = new THREE.Mesh(V.geo.box, mat);
  m.scale.set(w, hh, d);
  m.position.set(x, y, z);
  return m;
}
function boxEdge(w, hh, d, x, y, z, mat) {
  const e = new THREE.LineSegments(V.geo.boxEdges, mat);
  e.scale.set(w, hh, d);
  e.position.set(x, y, z);
  return e;
}
function lineGeo(pts) {
  const g3 = new THREE.BufferGeometry();
  g3.setAttribute("position", new THREE.Float32BufferAttribute(pts, 3));
  return g3;
}
function dashRect(hx, hy, ox, oy, mat, y) {
  const g3 = lineGeo([-hx + ox, y, -(-hy + oy), hx + ox, y, -(-hy + oy), hx + ox, y, -(hy + oy), -hx + ox, y, -(hy + oy)]);
  const l = new THREE.LineLoop(g3, mat);
  l.computeLineDistances();
  return l;
}
function planeMesh(w, d, x, y, z, mat) {
  const m = new THREE.Mesh(V.geo.plane, mat);
  m.scale.set(w, 1, d);
  m.position.set(x, y, z);
  return m;
}
function dispose(root) {
  root.traverse((o) => {
    if (o.userData.own && o.geometry) {
      o.geometry.dispose();
    }
    if (o.userData.inst) {
      o.dispose();
    }
  });
  (root.userData.mats || []).forEach((m) => m.dispose());
  dropLabels(root);
}
var genericCategory = (cat) => cat === "cabinet" ? "panel" : cat || "other";
function variantBody(cat, v, norm, ghost) {
  const L = v.length / 1e3;
  const W = v.width / 1e3;
  const H = v.height / 1e3;
  if (norm) {
    return modelBody(norm, L, H, W, ghost);
  }
  const ang = FRONT_ANGLE[v.front_side || "s"];
  const swap = ang === 90 || ang === 270;
  const g3 = new THREE.Group();
  const b = host.buildGenericModel(genericCategory(cat), { l: swap ? W : L, w: swap ? L : W, h: H }, THREE);
  if (ghost) {
    b.traverse((c) => {
      if (c.isMesh) {
        c.material = bodyMat("other", true);
      }
    });
  }
  b.rotation.y = rad(ang);
  g3.add(b);
  g3.add(boxEdge(L, H, W, 0, H / 2, 0, ghost ? V.mat.edgeGhost : V.mat.edge));
  return g3;
}
function modelBody(m, L, H, W, ghost) {
  const g3 = new THREE.Group();
  const o = m.obj.clone(true);
  const sz = m.size;
  o.scale.set(L / Math.max(sz.x, 1e-6), H / Math.max(sz.y, 1e-6), W / Math.max(sz.z, 1e-6));
  if (ghost) {
    o.traverse((c) => {
      if (c.isMesh) {
        c.material = bodyMat("other", true);
      }
    });
  }
  g3.add(o);
  return g3;
}
var isGhost = (ly) => ly.id !== S.ui.layer;
function variantSig(v, p) {
  return [v.length, v.width, v.height, v.service, v.front_side, v.anchor, p && p.category];
}
function buildPlacementView(pl, opts) {
  opts = opts || {};
  const v = variantOf(pl.variant_id);
  const ly = layerOf(pl.layer_id);
  if (!v || !ly) {
    return null;
  }
  const p = passportOf(pl.variant_id);
  const g3 = pGeom(pl, v);
  const ghost = opts.ghost != null ? opts.ghost : isGhost(ly);
  const H = v.height / 1e3;
  const root = new THREE.Group();
  root.userData.ref = { kind: "placement", id: pl.id };
  root.add(variantBody(p && p.category || "other", v, V.models.get(v.id), ghost));
  const view = { key: "p:" + pl.id, root, kind: "placement", id: pl.id, g: g3, H, ghost, layerId: ly.id };
  view.foot = dashRect(g3.L / 2 + 0.06, g3.W / 2 + 0.06, 0, 0, ghost ? V.mat.dashGhost : V.mat.dash.normal, 0.03);
  root.add(view.foot);
  if (g3.svc && !ghost) {
    view.svc = dashRect(g3.shx, g3.shy, g3.sox, g3.soy, V.mat.svc, 0.025);
    root.add(view.svc);
  }
  view.fill = planeMesh(g3.L + 0.7, g3.W + 0.7, 0, 0.02, 0, V.mat.fill.sel);
  view.fill.visible = false;
  root.add(view.fill);
  view.sel = boxEdge(g3.L * 1.03, H * 1.02, g3.W * 1.03, 0, H / 2, 0, V.mat.sel);
  view.sel.visible = false;
  root.add(view.sel);
  const hit = boxMesh(g3.L, Math.max(H, 0.4), g3.W, 0, Math.max(H, 0.4) / 2, 0, V.mat.hit);
  hit.userData.ref = root.userData.ref;
  hit.userData.view = view;
  root.add(hit);
  view.hit = hit;
  if (!opts.noLabel) {
    const lb = makeLabel(pl.code || pl.name || "", 0.9, 70);
    lb.position.set(0, H + 0.7, 0);
    root.add(lb);
    view.label = lb;
  }
  poseView(view, pl, v);
  return view;
}
function poseView(view, rec, v) {
  if (view.kind === "placement") {
    v = v || variantOf(rec.variant_id);
    const g3 = pGeom(rec, v);
    view.g = g3;
    view.root.position.set(g3.cx, elevOf(rec.layer_id), -g3.cy);
  } else {
    view.root.position.set(rec.x, elevOf(rec.layer_id), -rec.y);
  }
  view.root.rotation.y = rad(rec.rotation || 0);
}
var frameOf = {
  pallet_rack(p, d, sg) {
    for (let b = 0; b <= p.bays; b++) {
      const x = -d.L / 2 + b * p.bay_width;
      for (const sy of [-d.W / 2, d.W / 2]) {
        sg([x, sy, 0], [x, sy, d.H]);
      }
      sg([x, -d.W / 2, d.H], [x, d.W / 2, d.H]);
    }
    for (let l = 1; l <= p.levels; l++) {
      for (const sy of [-d.W / 2, d.W / 2]) {
        sg([-d.L / 2, sy, l * p.level_height], [d.L / 2, sy, l * p.level_height]);
      }
    }
  },
  shelf(p, d, sg) {
    for (let b = 0; b <= p.sections; b++) {
      const x = -d.L / 2 + b * p.cell_w;
      for (const sy of [-d.W / 2, d.W / 2]) {
        sg([x, sy, 0], [x, sy, d.H]);
      }
    }
    for (let l = 0; l <= p.shelves; l++) {
      const z = l * p.cell_h + 0.05;
      for (const sy of [-d.W / 2, d.W / 2]) {
        sg([-d.L / 2, sy, z], [d.L / 2, sy, z]);
      }
    }
  },
  cantilever(p, d, sg) {
    const y0 = -d.W / 2 + 0.075;
    for (let b = 0; b <= p.arms; b++) {
      const x = -d.L / 2 + b * d.L / p.arms;
      sg([x, y0, 0], [x, y0, d.H]);
      for (let l = 1; l <= p.levels; l++) {
        sg([x, y0, l * p.level_height], [x, d.W / 2, l * p.level_height]);
      }
    }
  }
};
for (const [tpl, fn] of Object.entries(frameOf)) {
  registries.shapes.add(
    tpl,
    {
      frame(p, d) {
        const pts = [];
        fn(p, d, (a, b) => pts.push(a[0], a[2], -a[1], b[0], b[2], -b[1]));
        return pts;
      }
    },
    { force: true }
  );
}
function frameLines(s, d) {
  const shape = registries.shapes.get(s.template, null);
  return shape && shape.frame ? shape.frame(normalizeParams(s.template, s.params), d) : [];
}
function cellColor(c, s, ly, sel) {
  if (sel) {
    return new THREE.Color(V.col.accent);
  }
  const metric = S.ui.metric ? registries.metrics.get(S.ui.metric, null) : null;
  const mc = metric && metric.color ? metric.color(c, s, ly) : null;
  if (mc) {
    return new THREE.Color(mc);
  }
  if (c.disabled) {
    return new THREE.Color("#8b8b8b");
  }
  const col = new THREE.Color(ly.color);
  if (c.ov) {
    col.lerp(new THREE.Color(V.col.warn), 0.5);
  }
  return col;
}
var ZONE_HUGE = 0.1;
function buildSlotView(s, opts) {
  opts = opts || {};
  const ly = layerOf(s.layer_id);
  if (!ly) {
    return null;
  }
  const ghost = opts.ghost != null ? opts.ghost : isGhost(ly);
  const d = slotDims(s);
  const g3 = sGeom(s);
  const root = new THREE.Group();
  root.userData.ref = { kind: "slot", id: s.id };
  const view = { key: "s:" + s.id, root, kind: "slot", id: s.id, g: g3, H: d.H, ghost, layerId: ly.id, tpl: s.template };
  const edgeMat = ghost ? V.mat.edgeGhost : V.mat.edge;
  const mkHit = (hh) => {
    const hit = boxMesh(d.L, hh, d.W, 0, hh / 2, 0, V.mat.hit);
    hit.userData.ref = root.userData.ref;
    hit.userData.view = view;
    root.add(hit);
    view.hit = hit;
  };
  if (s.template === "zone") {
    const col = new THREE.Color(s.params.color || ly.color);
    const B = S.site.building;
    const huge = d.L * d.W > ZONE_HUGE * B.length * B.width;
    const fm = new THREE.MeshBasicMaterial({
      color: col,
      transparent: true,
      opacity: ghost ? huge ? 0 : 0.06 : huge ? 0.06 : clamp(ly.opacity * 0.55, 0.1, 0.5),
      depthWrite: false,
      side: THREE.DoubleSide
    });
    root.userData.mats = [fm];
    if (fm.opacity > 0) {
      root.add(planeMesh(d.L, d.W, 0, 0.012, 0, fm));
    }
    const ol = new THREE.LineLoop(
      lineGeo([-d.L / 2, 0.016, d.W / 2, d.L / 2, 0.016, d.W / 2, d.L / 2, 0.016, -d.W / 2, -d.L / 2, 0.016, -d.W / 2]),
      new THREE.LineBasicMaterial({ color: col.clone().multiplyScalar(0.55), transparent: true, opacity: ghost ? 0.25 : 0.9 })
    );
    ol.userData.own = 1;
    root.userData.mats.push(ol.material);
    root.add(ol);
    mkHit(0.05);
    view.fillSel = planeMesh(d.L, d.W, 0, 0.02, 0, V.mat.fill.sel);
    view.fillSel.visible = false;
    root.add(view.fillSel);
    view.fill = view.fillSel;
    view.foot = null;
    const t = s.params.title || s.code_prefix;
    const lb = makeLabel(t, clamp(Math.min(d.W * 0.3, d.L * 0.2), 0.8, 2.4), 420, null, d.L * 0.92);
    lb.position.set(0, 0.03, 0);
    root.add(lb);
    view.label = lb;
  } else if (s.template === "machine_spot") {
    view.foot = dashRect(d.L / 2, d.W / 2, 0, 0, ghost ? V.mat.dashGhost : V.mat.dash.normal, 0.03);
    root.add(view.foot);
    if (g3.shx != null && !ghost) {
      root.add(dashRect(g3.shx, g3.shy, g3.sox, g3.soy, V.mat.svc, 0.025));
    }
    view.fill = planeMesh(d.L, d.W, 0, 0.02, 0, V.mat.fill.sel);
    view.fill.visible = false;
    root.add(view.fill);
    mkHit(0.3);
    const lb = makeLabel(s.code_prefix, 0.8, 90);
    lb.position.set(0, 0.25, 0);
    root.add(lb);
    view.label = lb;
    view.sel = boxEdge(d.L, 0.3, d.W, 0, 0.15, 0, V.mat.sel);
    view.sel.visible = false;
    root.add(view.sel);
  } else {
    const cells = cellsOf(s);
    const im = new THREE.InstancedMesh(V.geo.box, ghost ? V.mat.cellGhost : V.mat.cell, Math.max(cells.length, 1));
    im.userData.inst = 1;
    im.count = cells.length;
    const m4 = new THREE.Matrix4();
    const q = new THREE.Quaternion();
    const sc = new THREE.Vector3();
    const ps = new THREE.Vector3();
    const stack = s.template === "floor_stack";
    cells.forEach((c, i) => {
      const hh = stack ? Math.min(c.h, 0.5) : c.h * 0.78;
      sc.set(c.l * 0.92, hh, c.w * 0.9);
      ps.set(c.lx, c.dz + (s.template === "shelf" ? 0.05 : 0) + hh / 2 + (stack ? 0.02 : 0.1), -c.ly);
      m4.compose(ps, q, sc);
      im.setMatrixAt(i, m4);
      im.setColorAt(i, cellColor(c, s, ly, false));
    });
    im.instanceMatrix.needsUpdate = true;
    if (im.instanceColor) {
      im.instanceColor.needsUpdate = true;
    }
    root.add(im);
    view.cells = im;
    view.cellList = cells;
    view.ly = ly;
    const fl = frameLines(s, d);
    if (fl.length) {
      const ls = new THREE.LineSegments(lineGeo(fl), edgeMat);
      ls.userData.own = 1;
      root.add(ls);
    }
    view.foot = dashRect(d.L / 2 + 0.06, d.W / 2 + 0.06, 0, 0, ghost ? V.mat.dashGhost : V.mat.dash.normal, 0.03);
    root.add(view.foot);
    view.fill = planeMesh(d.L + 0.7, d.W + 0.7, 0, 0.02, 0, V.mat.fill.sel);
    view.fill.visible = false;
    root.add(view.fill);
    mkHit(Math.max(d.H, 0.3));
    view.sel = boxEdge(d.L * 1.02, d.H * 1.02, d.W * 1.02, 0, d.H / 2, 0, V.mat.sel);
    view.sel.visible = false;
    root.add(view.sel);
    const lb = makeLabel(s.code_prefix, 1.1, 130);
    lb.position.set(0, d.H + 0.8, 0);
    root.add(lb);
    view.label = lb;
  }
  poseView(view, s);
  return view;
}
function colorCells(view, selCode) {
  if (!view.cells) {
    return;
  }
  const s = S.sIdx.get(view.id);
  if (!s) {
    return;
  }
  view.cellList.forEach((c, i) => view.cells.setColorAt(i, cellColor(c, s, view.ly, c.code === selCode)));
  if (view.cells.instanceColor) {
    view.cells.instanceColor.needsUpdate = true;
  }
  view.selCode = selCode;
}
function gridStepDisplay(step, span) {
  let d = step;
  if (span / d > 160) {
    for (const k of [1, 2, 5, 10, 20]) {
      if (k <= d) {
        continue;
      }
      d = k;
      if (span / d <= 160) {
        break;
      }
    }
  }
  while (span / d > 160) {
    d *= 2;
  }
  return Math.max(d, step);
}
function boundsBox(ly) {
  const B = S.site.building;
  if (!ly.bounds || ly.bounds.length < 3) {
    return { x0: 0, y0: 0, x1: B.length, y1: B.width };
  }
  const xs = ly.bounds.map((p) => p[0]);
  const ys = ly.bounds.map((p) => p[1]);
  return { x0: Math.min(...xs), y0: Math.min(...ys), x1: Math.max(...xs), y1: Math.max(...ys) };
}
function buildDecor(ly) {
  const g3 = new THREE.Group();
  const own = [];
  const active = ly.id === S.ui.layer;
  const el = ly.elevation;
  const bp = boundsBox(ly);
  const add = (o, ownGeo) => {
    g3.add(o);
    if (ownGeo) {
      o.userData.own = 1;
    }
    return o;
  };
  const col = new THREE.Color(ly.color);
  if (active) {
    const ds = gridStepDisplay(ly.grid_step || 1, Math.max(bp.x1 - bp.x0, bp.y1 - bp.y0));
    const mj = [];
    const mn = [];
    const y = el + 6e-3;
    const nx = Math.floor((bp.x1 - bp.x0) / ds + 1e-6);
    const ny = Math.floor((bp.y1 - bp.y0) / ds + 1e-6);
    for (let i = 0; i <= nx; i++) {
      const x = bp.x0 + i * ds;
      (i % 5 === 0 ? mj : mn).push(x, y, -bp.y0, x, y, -(bp.y0 + ny * ds));
    }
    for (let j = 0; j <= ny; j++) {
      const yy = bp.y0 + j * ds;
      (j % 5 === 0 ? mj : mn).push(bp.x0, y, -yy, bp.x0 + nx * ds, y, -yy);
    }
    if (mn.length) {
      add(new THREE.LineSegments(lineGeo(mn), V.mat.gridMinor), 1);
    }
    if (mj.length) {
      add(new THREE.LineSegments(lineGeo(mj), V.mat.gridMajor), 1);
    }
  }
  const outline = (yv) => {
    const poly = ly.bounds && ly.bounds.length >= 3 ? ly.bounds : [
      [bp.x0, bp.y0],
      [bp.x1, bp.y0],
      [bp.x1, bp.y1],
      [bp.x0, bp.y1]
    ];
    return lineGeo(poly.flatMap(([x, y]) => [x, yv, -y]));
  };
  if (el > 0.01) {
    const vm = new THREE.MeshBasicMaterial({ color: col, transparent: true, opacity: active ? 0.06 : 0.015, depthWrite: false, side: THREE.DoubleSide });
    own.push(vm);
    g3.add(planeMesh(bp.x1 - bp.x0, bp.y1 - bp.y0, (bp.x0 + bp.x1) / 2, el, -(bp.y0 + bp.y1) / 2, vm));
    const lm = new THREE.LineBasicMaterial({ color: col, transparent: true, opacity: active ? 0.9 : 0.45 });
    own.push(lm);
    add(new THREE.LineLoop(outline(el), lm), 1);
    const vl = [];
    for (const [x, y] of [
      [bp.x0, bp.y0],
      [bp.x1, bp.y0],
      [bp.x1, bp.y1],
      [bp.x0, bp.y1]
    ]) {
      vl.push(x, 0, -y, x, el, -y);
    }
    add(new THREE.LineSegments(lineGeo(vl), lm), 1);
  } else if (ly.bounds) {
    const lm = new THREE.LineDashedMaterial({ color: col, dashSize: 1, gapSize: 0.6 });
    own.push(lm);
    const ol = new THREE.LineLoop(outline(0.02), lm);
    ol.computeLineDistances();
    add(ol, 1);
  }
  const zone = (x0, y0, x1, y1, color, op, lab) => {
    const fm = new THREE.MeshBasicMaterial({ color, transparent: true, opacity: active ? op : op * 0.4, depthWrite: false, side: THREE.DoubleSide });
    own.push(fm);
    g3.add(planeMesh(Math.abs(x1 - x0), Math.abs(y1 - y0), (x0 + x1) / 2, el + 0.018, -(y0 + y1) / 2, fm));
    const lm = new THREE.LineDashedMaterial({ color, dashSize: 0.4, gapSize: 0.25, transparent: true, opacity: active ? 0.9 : 0.35 });
    own.push(lm);
    const ol = new THREE.LineLoop(lineGeo([x0, el + 0.02, -y0, x1, el + 0.02, -y0, x1, el + 0.02, -y1, x0, el + 0.02, -y1]), lm);
    ol.computeLineDistances();
    add(ol, 1);
    if (lab && active) {
      const lb = makeLabel(lab, 0.7, 70, color);
      lb.position.set((x0 + x1) / 2, el + 0.4, -(y0 + y1) / 2);
      g3.add(lb);
    }
  };
  for (const a of ly.aisles || []) {
    zone(a.x0, a.y0, a.x1, a.y1, "#2e9d8f", 0.16, a.name);
  }
  for (const f of ly.fire_paths || []) {
    zone(f.x0, f.y0, f.x1, f.y1, "#d6453d", f.kind === "exit" ? 0.2 : 0.18, f.name);
  }
  if ((ly.utilities || []).length) {
    const stems = [];
    for (const u of ly.utilities) {
      const geo = u.kind === "electric" || u.kind === "panel" ? V.geo.octa : u.kind === "air" ? V.geo.sph : V.geo.cone;
      const m = new THREE.Mesh(geo, V.mat.pt[u.kind] || V.mat.pt.electric);
      m.position.set(u.x, el + 0.1, -u.y);
      g3.add(m);
      if (el > 0.5) {
        stems.push(u.x, 0, -u.y, u.x, el, -u.y);
      }
    }
    if (stems.length) {
      const sm = new THREE.LineBasicMaterial({ color: col, transparent: true, opacity: 0.25 });
      own.push(sm);
      add(new THREE.LineSegments(lineGeo(stems), sm), 1);
    }
  }
  g3.userData.ownMats = own;
  return g3;
}
function disposeDecor(g3) {
  g3.traverse((o) => {
    if (o.userData.own && o.geometry) {
      o.geometry.dispose();
    }
  });
  (g3.userData.ownMats || []).forEach((m) => m.dispose());
  dropLabels(g3);
}
function buildBuilding() {
  const B = S.site.building;
  const g3 = new THREE.Group();
  g3.add(planeMesh(B.length, B.width, B.length / 2, -0.01, -B.width / 2, V.mat.floor));
  const e = new THREE.LineSegments(V.geo.boxEdges, V.mat.bld);
  e.scale.set(B.length, B.height, B.width);
  e.position.set(B.length / 2, B.height / 2, -B.width / 2);
  g3.add(e);
  const sx = S.site.column_grid.step_x;
  const sy = S.site.column_grid.step_y;
  if (sx > 1 && sy > 1) {
    const xs = [];
    const ys = [];
    for (let x = sx; x < B.length - 0.01; x += sx) {
      xs.push(x);
    }
    for (let y = sy; y < B.width - 0.01; y += sy) {
      ys.push(y);
    }
    const n = xs.length * ys.length;
    if (n > 0 && n < 2e3) {
      const im = new THREE.InstancedMesh(V.geo.box, V.mat.col, n);
      const m4 = new THREE.Matrix4();
      let i = 0;
      for (const x of xs) {
        for (const y of ys) {
          m4.compose(new THREE.Vector3(x, B.height / 2, -y), new THREE.Quaternion(), new THREE.Vector3(0.4, B.height, 0.4));
          im.setMatrixAt(i++, m4);
        }
      }
      g3.add(im);
    }
  }
  return g3;
}
function syncStatic() {
  const B = S.site.building;
  const sig = JSON.stringify([B, S.site.column_grid, V.theme, S.site.id]);
  if (sig === V.staticSig) {
    return;
  }
  V.staticSig = sig;
  if (V.buildingG) {
    V.world.remove(V.buildingG);
    const shared = Object.values(V.geo);
    V.buildingG.traverse((o) => {
      if (o.geometry && !shared.includes(o.geometry)) {
        o.geometry.dispose();
      }
      if (o.isInstancedMesh) {
        o.dispose();
      }
    });
  }
  V.buildingG = buildBuilding();
  V.world.add(V.buildingG);
}
function syncScene(force) {
  if (!V.ok) {
    return;
  }
  syncStatic();
  const lseen = /* @__PURE__ */ new Set();
  for (const ly of S.layers) {
    lseen.add(ly.id);
    const sig = JSON.stringify([ly.elevation, ly.grid_step, ly.bounds, ly.color, !isLayerVisible(ly), ly.aisles, ly.fire_paths, ly.utilities, ly.id === S.ui.layer, S.site.building, V.theme]);
    const cur = V.decor.get(ly.id);
    if (cur && cur.sig === sig && !force) {
      continue;
    }
    if (cur) {
      V.world.remove(cur.g);
      disposeDecor(cur.g);
    }
    if (!isLayerVisible(ly)) {
      V.decor.delete(ly.id);
      continue;
    }
    const g3 = buildDecor(ly);
    V.world.add(g3);
    V.decor.set(ly.id, { g: g3, sig });
  }
  for (const [id, d] of V.decor) {
    if (!lseen.has(id)) {
      V.world.remove(d.g);
      disposeDecor(d.g);
      V.decor.delete(id);
    }
  }
  const seen = /* @__PURE__ */ new Set();
  for (const pl of S.placements) {
    const ly = layerOf(pl.layer_id);
    const v = variantOf(pl.variant_id);
    if (!ly || !v || !isLayerVisible(ly)) {
      continue;
    }
    const key = "p:" + pl.id;
    seen.add(key);
    const sig = JSON.stringify([pl.x, pl.y, pl.rotation, pl.variant_id, pl.layer_id, pl.code, variantSig(v, passportOf(pl.variant_id)), ly.elevation, isGhost(ly), V.theme, V.models.has(v.id)]);
    const cur = V.views.get(key);
    if (cur && cur.sig === sig && !force) {
      continue;
    }
    if (cur) {
      V.world.remove(cur.root);
      dispose(cur.root);
    }
    const view = buildPlacementView(pl);
    if (!view) {
      continue;
    }
    view.sig = sig;
    V.world.add(view.root);
    V.views.set(key, view);
  }
  for (const s of S.slots) {
    const ly = layerOf(s.layer_id);
    if (!ly || !isLayerVisible(ly)) {
      continue;
    }
    const key = "s:" + s.id;
    seen.add(key);
    const sig = JSON.stringify([s, ly.elevation, ly.color, ly.opacity, isGhost(ly), V.theme]);
    const cur = V.views.get(key);
    if (cur && cur.sig === sig && !force) {
      continue;
    }
    if (cur) {
      V.world.remove(cur.root);
      dispose(cur.root);
    }
    const view = buildSlotView(s);
    if (!view) {
      continue;
    }
    view.sig = sig;
    V.world.add(view.root);
    V.views.set(key, view);
  }
  for (const [k, v] of V.views) {
    if (!seen.has(k)) {
      V.world.remove(v.root);
      dispose(v.root);
      V.views.delete(k);
    }
  }
  V.pick = [];
  for (const v of V.views.values()) {
    if (v.hit) {
      V.pick.push(v.hit);
    }
  }
  syncUnderlays();
  updateVisual();
}
function updateVisual() {
  if (!V.ok) {
    return;
  }
  const selKey = S.sel ? objKey(S.sel.kind, S.sel.id) : null;
  for (const [key, v] of V.views) {
    const st = S.issues.byKey.get(key);
    const lvl = st ? st.level : "normal";
    const isSel = key === selKey;
    if (v.foot) {
      v.foot.material = v.ghost ? V.mat.dashGhost : V.mat.dash[lvl] || V.mat.dash.normal;
    }
    if (v.fill) {
      v.fill.visible = !v.ghost && (lvl !== "normal" || isSel);
      v.fill.material = lvl === "normal" ? V.mat.fill.sel : V.mat.fill[lvl];
    }
    if (v.sel) {
      v.sel.visible = isSel;
    }
    if (v.cells) {
      const want = isSel ? S.selCell || "" : "";
      if ((v.selCode || "") !== want) {
        colorCells(v, want || null);
      }
    }
  }
  requestRender();
}
function rulerClear() {
  for (const o of V.ruler.objs) {
    V.world.remove(o);
    if (o.geometry && o.geometry !== V.geo.sph) {
      o.geometry.dispose();
    }
  }
  V.ruler.objs = [];
  V.ruler.pts = [];
  const rl = $("#rlabel");
  if (rl) {
    rl.hidden = true;
  }
  requestRender();
}
function rulerPoint(pt) {
  const R = V.ruler;
  if (R.pts.length >= 2) {
    rulerClear();
  }
  R.pts.push(pt);
  const m = new THREE.Mesh(V.geo.sph, V.mat.rulerPt);
  m.position.set(pt.x, pt.z + 0.05, -pt.y);
  m.scale.setScalar(0.6);
  m.renderOrder = 10;
  V.world.add(m);
  R.objs.push(m);
  if (R.pts.length === 2) {
    const [a, b] = R.pts;
    const l = new THREE.Line(lineGeo([a.x, a.z + 0.06, -a.y, b.x, b.z + 0.06, -b.y]), V.mat.ruler);
    l.renderOrder = 10;
    V.world.add(l);
    R.objs.push(l);
    R.dist = Math.hypot(b.x - a.x, b.y - a.y);
    const rl = $("#rlabel");
    rl.textContent = fmt(R.dist, 2) + " м · Δx " + fmt(Math.abs(b.x - a.x), 2) + " · Δy " + fmt(Math.abs(b.y - a.y), 2);
    rl.hidden = false;
  }
  requestRender();
}
function updateRulerLabel() {
  const R = V.ruler;
  if (R.pts.length < 2) {
    return;
  }
  const a = R.pts[0];
  const b = R.pts[1];
  const mid = new THREE.Vector3((a.x + b.x) / 2, (a.z + b.z) / 2, -(a.y + b.y) / 2).project(V.camera);
  const w = V.canvas.clientWidth;
  const hh = V.canvas.clientHeight;
  const el = $("#rlabel");
  el.style.left = (mid.x + 1) / 2 * w + "px";
  el.style.top = (1 - mid.y) / 2 * hh + "px";
}
function syncUnderlays() {
  for (const [id, cur] of V.underlays) {
    if (!layerOf(id)) {
      V.world.remove(cur.o);
      cur.o.geometry.dispose();
      cur.o.material.dispose();
      V.underlays.delete(id);
    }
  }
  for (const ly of S.layers) {
    const u = ly.underlay;
    const data = V.uldata.get(ly.id);
    const sig = u && data && u.status === "ready" ? JSON.stringify([u.params, ly.elevation, !isLayerVisible(ly), V.theme, data.n]) : "";
    const cur = V.underlays.get(ly.id);
    if (cur && cur.sig === sig) {
      continue;
    }
    if (cur) {
      V.world.remove(cur.o);
      cur.o.geometry.dispose();
      cur.o.material.dispose();
      V.underlays.delete(ly.id);
    }
    if (!sig || !isLayerVisible(ly)) {
      continue;
    }
    const p = u.params;
    const segs = data.segs;
    const k = (p.unit === "m" ? 1 : 1e-3) * (p.scale || 1);
    const a = rad(p.rot_deg || 0);
    const c = Math.cos(a);
    const s = Math.sin(a);
    const pos = new Float32Array(segs.length / 2 * 3);
    const y0 = ly.elevation + 0.04;
    for (let i = 0, j = 0; i < segs.length; i += 2, j += 3) {
      const px = segs[i] * k;
      const py = segs[i + 1] * k;
      pos[j] = px * c - py * s + p.dx;
      pos[j + 1] = y0;
      pos[j + 2] = -(px * s + py * c + p.dy);
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    const mat = V.mat.under.clone();
    mat.opacity = clamp(p.opacity == null ? 0.7 : p.opacity, 0.05, 1);
    const o = new THREE.LineSegments(geo, mat);
    o.renderOrder = 2;
    V.world.add(o);
    V.underlays.set(ly.id, { o, sig });
  }
  requestRender();
}
function underlayVertex(layerId, wx, wy, maxD) {
  const cur = V.underlays.get(layerId);
  if (!cur) {
    return null;
  }
  const p = cur.o.geometry.attributes.position.array;
  let best = null;
  let bd = maxD;
  for (let i = 0; i < p.length; i += 3) {
    const d = Math.hypot(p[i] - wx, -p[i + 2] - wy);
    if (d < bd) {
      bd = d;
      best = { x: p[i], y: -p[i + 2] };
    }
  }
  return best;
}
function ndc(e) {
  const r = V.canvas.getBoundingClientRect();
  return new THREE.Vector2((e.clientX - r.left) / r.width * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
}
function floorPoint(e, elev) {
  V.raycaster.setFromCamera(ndc(e), V.camera);
  const out = new THREE.Vector3();
  if (!V.raycaster.ray.intersectPlane(new THREE.Plane(new THREE.Vector3(0, 1, 0), -(elev || 0)), out)) {
    return null;
  }
  return { x: out.x, y: -out.z, z: elev || 0 };
}
var OVERLAY_KINDS = ["building", "engineering"];
function pickCandidates(e) {
  V.world.updateMatrixWorld(true);
  V.raycaster.setFromCamera(ndc(e), V.camera);
  const hits = V.raycaster.intersectObjects(V.pick, false);
  const seen = /* @__PURE__ */ new Set();
  const out = [];
  for (const h0 of hits) {
    const ref2 = h0.object.userData.ref;
    const view = h0.object.userData.view;
    if (!ref2 || !view || seen.has(view.key)) {
      continue;
    }
    seen.add(view.key);
    const ly = layerOf(view.layerId);
    if (!ly || !isLayerVisible(ly)) {
      continue;
    }
    const active = view.layerId === S.ui.layer;
    if (!active && (view.tpl === "zone" || OVERLAY_KINDS.includes(ly.kind))) {
      continue;
    }
    const tier = active ? 0 : canEditLayer(ly) ? 1 : 2;
    out.push({ ref: ref2, view, hit: h0, tier, area: view.g.L * view.g.W, kind: view.kind === "placement" ? 0 : 1 });
  }
  out.sort((a, b) => a.tier - b.tier || a.area - b.area || a.kind - b.kind || a.hit.distance - b.hit.distance);
  return out;
}
function pickAt(e) {
  const best = pickCandidates(e)[0];
  return best ? { ref: best.ref, view: best.view, hit: best.hit } : null;
}
var rafLive = /* @__PURE__ */ (() => {
  let f = 0;
  return () => {
    if (f) {
      return;
    }
    f = requestAnimationFrame(() => {
      f = 0;
      liveCheck();
    });
  };
})();
function initPointer() {
  const cv = V.canvas;
  const listeners = {
    pointerdown: onDown,
    pointermove: onMove,
    pointerup: onUp,
    pointercancel: onUp,
    contextmenu: (e) => e.preventDefault(),
    dragover: (e) => {
      if ([...e.dataTransfer.types].includes("text/f3d-variant")) {
        e.preventDefault();
        e.dataTransfer.dropEffect = "copy";
      }
    },
    drop: (e) => {
      const id = e.dataTransfer.getData("text/f3d-variant");
      if (!id) {
        return;
      }
      e.preventDefault();
      const ly = layerOf(S.ui.layer);
      const pt = floorPoint(e, ly ? ly.elevation : 0);
      if (pt) {
        E.addPlacementAt(id, pt.x, pt.y, true);
      }
    }
  };
  for (const [t, fn] of Object.entries(listeners)) {
    cv.addEventListener(t, fn);
  }
}
function onDown(e) {
  V.canvas.focus({ preventScroll: true });
  if (e.pointerType === "mouse" && e.button !== 0) {
    return;
  }
  const ly = layerOf(S.ui.layer);
  const elev = ly ? ly.elevation : 0;
  if (V.pickMode) {
    const pt2 = floorPoint(e, elev);
    if (pt2) {
      E.pickModeClick(pt2);
    }
    e.preventDefault();
    return;
  }
  if (V.ruler.on) {
    const pt2 = floorPoint(e, elev);
    if (pt2) {
      pt2.x = rnd(pt2.x, 2);
      pt2.y = rnd(pt2.y, 2);
      rulerPoint(pt2);
    }
    return;
  }
  if (V.placing) {
    V.placing.down = { x: e.clientX, y: e.clientY };
    V.controls.enabled = true;
    return;
  }
  const hit = pickAt(e);
  V.bg = null;
  if (!hit) {
    V.bg = { x: e.clientX, y: e.clientY };
    return;
  }
  E.selectObj(hit.ref);
  if (hit.view.cells) {
    const ci = V.raycaster.intersectObject(hit.view.cells, false)[0];
    if (ci && ci.instanceId != null && hit.view.cellList[ci.instanceId]) {
      S.selCell = hit.view.cellList[ci.instanceId].code;
      updateVisual();
      E.renderCellsBox();
      const tr = $("#cellsBox tr.sel");
      if (tr) {
        tr.scrollIntoView({ block: "nearest" });
      }
    }
  }
  const rec = recOfRef(hit.ref);
  if (!rec) {
    return;
  }
  const lyr = layerOf(rec.layer_id);
  if (!canEditLayer(lyr)) {
    if (S.app.mode === "edit") {
      toastLock(lyr);
    }
    return;
  }
  if (rec.locked) {
    toast("Складний контур зони редагується у формі Odoo.", "warn");
    return;
  }
  const pt = floorPoint(e, lyr.elevation);
  if (!pt) {
    return;
  }
  V.controls.enabled = false;
  try {
    V.canvas.setPointerCapture(e.pointerId);
  } catch {
  }
  V.drag = { ref: hit.ref, rec, key: objKey(hit.ref.kind, hit.ref.id), start: { x: rec.x, y: rec.y }, pt0: pt, moved: false, sx: e.clientX, sy: e.clientY, before: S.issues, elev: lyr.elevation };
}
function onMove(e) {
  const ly = layerOf(S.ui.layer);
  const elev = ly ? ly.elevation : 0;
  const pp = floorPoint(e, V.drag ? V.drag.elev : elev);
  if (pp) {
    V.cursor = pp;
    E.updateStamp();
  }
  if (V.placing) {
    movePlacing(e);
    return;
  }
  if (!V.drag && !V.hoverRaf) {
    const ex2 = { clientX: e.clientX, clientY: e.clientY };
    V.hoverRaf = requestAnimationFrame(() => {
      V.hoverRaf = 0;
      hoverAt(ex2);
    });
  }
  const d = V.drag;
  if (!d) {
    return;
  }
  if (!d.moved && Math.hypot(e.clientX - d.sx, e.clientY - d.sy) < 4) {
    return;
  }
  d.moved = true;
  if (!pp) {
    return;
  }
  const st = e.altKey ? 0.01 : snapStep(d.rec);
  d.rec.x = snapV(d.start.x + (pp.x - d.pt0.x), st);
  d.rec.y = snapV(d.start.y + (pp.y - d.pt0.y), st);
  const view = V.views.get(d.key);
  if (view) {
    poseView(view, d.rec);
  }
  rafLive();
}
function hoverAt(e) {
  if (!V.canvas || V.drag || V.placing || V.ruler.on || V.pickMode) {
    return;
  }
  const hit = pickAt(e);
  const key = hit ? objKey(hit.ref.kind, hit.ref.id) : null;
  if (key === V.hoverKey) {
    return;
  }
  V.hoverKey = key;
  const rec = hit && recOfRef(hit.ref);
  V.canvas.style.cursor = hit ? canEditLayer(layerOf(rec.layer_id)) ? "move" : "pointer" : "";
  const el = $("#hoverName");
  if (el) {
    el.textContent = rec ? (rec.code || rec.code_prefix) + (rec.name ? " · " + rec.name : rec.params && rec.params.title ? " · " + rec.params.title : "") : "—";
  }
}
function onUp(e) {
  try {
    V.canvas.releasePointerCapture(e.pointerId);
  } catch {
  }
  if (V.placing && V.placing.down) {
    const d0 = V.placing.down;
    V.placing.down = null;
    if (Math.hypot(e.clientX - d0.x, e.clientY - d0.y) < 5) {
      movePlacing(e);
      placeClick(e.shiftKey);
    }
    return;
  }
  const d = V.drag;
  V.drag = null;
  V.controls.enabled = true;
  if (V.bg) {
    const b = V.bg;
    V.bg = null;
    if (Math.hypot(e.clientX - b.x, e.clientY - b.y) < 4) {
      E.selectObj(null);
    }
    return;
  }
  if (!d || !d.moved) {
    return;
  }
  finishMove(d);
}
function liveCheck() {
  S.issues = runLive();
  updateVisual();
  E.syncPropsValues();
  E.renderChecksBlock();
}
function finishMove(d) {
  const after = runLive();
  const nb = newBlocks(d.before, after, d.key);
  if (nb.length) {
    d.rec.x = d.start.x;
    d.rec.y = d.start.y;
    const view = V.views.get(d.key);
    if (view) {
      poseView(view, d.rec);
    }
    S.issues = runLive();
    updateVisual();
    E.syncPropsValues();
    E.renderChecksBlock();
    toast("Заблоковано: " + nb[0].msg + ". Об’єкт повернуто на місце.", "err");
    return;
  }
  if (d.ref.kind === "placement") {
    assignSlot(d.rec);
  }
  const st0 = d.start;
  if (st0.x !== d.rec.x || st0.y !== d.rec.y) {
    E.commit({});
  } else {
    S.issues = after;
    updateVisual();
  }
  const first = S.issues.byKey.get(d.key);
  if (first && first.level !== "block") {
    toast(first.items[0].msg, "warn");
  }
}
function assignSlot(pl) {
  const v = variantOf(pl.variant_id);
  if (!v) {
    return;
  }
  const g3 = pGeom(pl, v);
  let found = null;
  for (const s of S.slots) {
    if (s.template === "machine_spot" && s.layer_id === pl.layer_id && polygonContains(sGeom(s).poly, [g3.cx, g3.cy], 1e-6)) {
      found = s;
    }
  }
  pl.slot_id = found ? found.id : null;
}
function startPlacing(spec) {
  cancelModes();
  const ly = layerOf(S.ui.layer);
  if (!ly) {
    return;
  }
  if (!canEditLayer(ly)) {
    toastLock(ly);
    return;
  }
  const c = camTarget();
  let rec;
  if (spec.kind === "placement") {
    const v = variantOf(spec.variantId);
    if (!v) {
      return;
    }
    rec = { id: "tmp", layer_id: ly.id, variant_id: v.id, slot_id: null, cell_code: null, x: snapV(c.x, ly.grid_step), y: snapV(c.y, ly.grid_step), rotation: 0, code: "", name: v.name };
  } else {
    if (!ly.slot_types.includes(spec.template)) {
      toast(`Шар «${ly.name}» не допускає шаблон «${TPL[spec.template].name}»`, "warn");
      return;
    }
    rec = { id: "tmp", layer_id: ly.id, template: spec.template, code_prefix: spec.prefix, x: snapV(c.x, ly.grid_step), y: snapV(c.y, ly.grid_step), rotation: 0, params: clone(spec.params), overrides: {} };
  }
  const view = rec.template ? buildSlotView(rec, { ghost: false }) : buildPlacementView(rec, { ghost: false, noLabel: true });
  if (!view) {
    return;
  }
  V.world.add(view.root);
  V.placing = { spec, rec, view, kind: spec.kind };
  V.canvas.style.cursor = "copy";
  V.placing.hint = toast("Клацніть на сцені, щоб поставити. Shift — поставити кілька, Esc — скасувати.");
  liveGhost();
  requestRender();
  E.renderVTools();
}
function movePlacing(e) {
  const P = V.placing;
  if (!P) {
    return;
  }
  const ly = layerOf(P.rec.layer_id);
  const pt = floorPoint(e, ly.elevation);
  if (!pt) {
    return;
  }
  const st = e.altKey ? 0.01 : ly.grid_step || 0.5;
  P.rec.x = snapV(pt.x, st);
  P.rec.y = snapV(pt.y, st);
  poseView(P.view, P.rec);
  liveGhost();
}
function liveGhost() {
  const P = V.placing;
  if (!P) {
    return;
  }
  const isSlot = !!P.rec.template;
  const arr = isSlot ? S.slots : S.placements;
  const idx = isSlot ? S.sIdx : S.pIdx;
  arr.push(P.rec);
  idx.set("tmp", P.rec);
  const res = runLive();
  arr.pop();
  idx.delete("tmp");
  const key = (isSlot ? "s:" : "p:") + "tmp";
  const st = res.byKey.get(key);
  const lvl = st ? st.level : "normal";
  P.lvl = lvl;
  P.issues = st ? st.items : [];
  const v = P.view;
  if (v.foot) {
    v.foot.material = V.mat.dash[lvl] || V.mat.dash.normal;
  }
  if (v.fill) {
    v.fill.visible = true;
    v.fill.material = lvl === "normal" ? V.mat.fill.sel : V.mat.fill[lvl];
  }
  requestRender();
}
function placeClick(keep) {
  const P = V.placing;
  if (!P) {
    return;
  }
  if (P.lvl === "block") {
    toast("Заблоковано: " + P.issues.find((i) => i.level === "block").msg, "err");
    return;
  }
  if (P.kind === "placement") {
    E.addPlacementAt(P.spec.variantId, P.rec.x, P.rec.y, false);
  } else {
    E.addSlotAt(P.spec, P.rec.x, P.rec.y);
  }
  if (!keep) {
    cancelModes();
  }
}
function cancelModes() {
  if (V.placing) {
    if (V.placing.hint) {
      V.placing.hint.remove();
    }
    V.world.remove(V.placing.view.root);
    dispose(V.placing.view.root);
    V.placing = null;
    if (V.canvas) {
      V.canvas.style.cursor = "";
    }
  }
  if (V.ruler.on) {
    V.ruler.on = false;
    rulerClear();
  }
  if (V.pickMode) {
    V.pickMode = null;
  }
  requestRender();
  E.renderVTools?.();
}
Object.assign(E, {
  requestRender,
  setView,
  focusOn,
  camTarget,
  syncScene,
  updateVisual,
  rulerClear,
  rulerPoint,
  syncUnderlays,
  underlayVertex,
  startPlacing,
  cancelModes,
  assignSlot,
  initScene,
  disposeScene,
  resizeScene,
  recolorMats,
  floorPoint,
  poseView,
  buildPlacementView,
  buildSlotView
});

// core/constructor/app.js
var ctx = null;
var lsGet = (k) => {
  try {
    return window.localStorage.getItem(k);
  } catch {
    return null;
  }
};
var lsSet = (k, v) => {
  try {
    window.localStorage.setItem(k, v);
  } catch {
  }
};
var syncNow = () => {
  if (!ctx || !S.site) {
    return;
  }
  ctx.adapter.save(S);
};
var scheduleSave = debounce(syncNow, 150);
async function flushNow() {
  if (!ctx) {
    return { ok: true };
  }
  scheduleSave.cancel();
  syncNow();
  const r = await ctx.adapter.flush();
  if (r.reload && r.ok !== false) {
    await reload();
  }
  return r;
}
var saveSiteProps = debounce(async () => {
  if (!ctx || !S.site) {
    return;
  }
  const b = S.site.building;
  const cg = S.site.column_grid;
  try {
    await ctx.adapter.saveSite({
      name: S.site.name,
      building: { length: b.length, width: b.width, height: b.height },
      column_grid: { step_x: cg.step_x, step_y: cg.step_y }
    });
  } catch (e) {
    toast("Не вдалося зберегти параметри площадки: " + (e.data?.message || e.message || e), "err");
  }
}, 700);
function commit() {
  reindex();
  S.issues = runLive();
  E.syncScene();
  E.renderAll();
  scheduleSave();
}
function applyLoaded(st, keep) {
  S.site = st.site;
  S.layers = st.layers;
  S.slots = st.slots;
  S.placements = st.placements;
  S.catalog = st.catalog;
  S.settings = st.settings;
  S.versions = st.versions;
  S.rights = st.rights;
  S.app.active = st.site.id;
  const entry = S.app.sites.find((s) => s.id === st.site.id);
  if (entry) {
    entry.name = st.site.name;
  }
  ctx.adapter.autosaveMs = st.site.settings?.autosave_ms ?? 1500;
  reindex();
  S.sel = keep?.sel && (keep.sel.kind === "slot" ? S.sIdx : S.pIdx).has(keep.sel.id) ? keep.sel : null;
  S.selCell = null;
  S.edit = null;
  if (!keep) {
    V.hidden = new Set(S.layers.filter((l) => !l.visible).map((l) => l.id));
  }
  const first = S.layers.find((l) => l.kind === "production") || S.layers.find((l) => l.kind !== "building") || S.layers[0];
  S.ui.layer = keep?.layer && layerOf(keep.layer) ? keep.layer : first.id;
  S.ui.dxfScale = null;
  V.models.clear();
  S.issues = runLive();
}
async function afterSiteLoad(keep) {
  E.renderAll();
  E.syncScene(true);
  if (!keep) {
    E.setView("iso");
  }
  await Promise.all([loadVariantModels(), E.loadUnderlays()]);
}
async function openSite(id, keep) {
  const st = await ctx.adapter.load(id);
  if (!ctx) {
    return;
  }
  applyLoaded(st, keep);
  lsSet(host.siteKey, String(id));
  await afterSiteLoad(keep);
}
async function switchSite(id) {
  if (id === S.app.active) {
    return;
  }
  const r = await flushNow();
  if (r.ok === false) {
    toast("Не вдалося зберегти зміни: площадку не перемкнено.", "err");
    E.renderTop();
    return;
  }
  try {
    E.cancelModes();
    await openSite(id);
  } catch (e) {
    toast("Не вдалося відкрити площадку: " + (e.message || e), "err");
    E.renderTop();
  }
}
async function reload() {
  if (!ctx || !S.site) {
    return;
  }
  const keep = { sel: S.sel, layer: S.ui.layer };
  await openSite(S.site.id, keep);
}
async function createSite(o) {
  try {
    const id = await ctx.adapter.createSite(o);
    S.app.sites = await ctx.adapter.listSites();
    await flushNow();
    await openSite(id);
    toast("Створено порожню площадку.");
    return true;
  } catch (e) {
    toast(e.message || "Не вдалося створити площадку.", "err");
    return false;
  }
}
async function restoreVersion(versionId, n) {
  try {
    const res = await ctx.adapter.restoreVersion(versionId);
    await openSite(res.site_id || S.site.id, { sel: null, layer: S.ui.layer });
    toast(`Чернетку повернуто до версії ${n}.`);
  } catch (e) {
    toast(e.message || "Не вдалося повернути чернетку.", "err");
  }
}
async function publish() {
  try {
    await ctx.adapter.publish({ onClose: () => reload(), state: S });
  } catch (e) {
    toast(e.message || "Не вдалося підготувати публікацію.", "err");
  }
}
async function validateOnServer() {
  try {
    await flushNow();
    E.openServerIssues(await ctx.adapter.check());
  } catch (e) {
    toast(e.message || "Не вдалося виконати перевірку.", "err");
  }
}
var dialogCtx = () => ({ E, S, V, adapter: ctx?.adapter, host, reload });
async function runDialog(name, args) {
  if (!registries.dialogs.has(name)) {
    toast(`Діалог «${name}» недоступний у цьому хості.`, "warn");
    return void 0;
  }
  return await registries.dialogs.get(name)(args || {}, dialogCtx());
}
var openVariantForm = (variant, passport) => runDialog("variantForm", { variant: variant || null, passport });
var openPassportForm = (passport) => runDialog("passportForm", { passport: passport || null });
var openRecord = (model, id) => runDialog("record", { model, id });
function normalizeModel(obj) {
  const wrap = new THREE.Group();
  const inner = obj.clone(true);
  wrap.add(inner);
  wrap.updateMatrixWorld(true);
  const box = new THREE.Box3().setFromObject(wrap);
  const c = box.getCenter(new THREE.Vector3());
  const size = box.getSize(new THREE.Vector3());
  inner.position.set(-c.x, -box.min.y, -c.z);
  wrap.updateMatrixWorld(true);
  return { obj: wrap, size };
}
async function loadVariantModels() {
  if (V.testMode) {
    return;
  }
  let any = false;
  for (const p of S.catalog) {
    for (const v of p.variants) {
      if (!v.model || V.models.has(v.id)) {
        continue;
      }
      try {
        const obj = await ctx.adapter.loadModel(v, THREE);
        if (!obj) {
          continue;
        }
        if (!ctx) {
          return;
        }
        V.models.set(v.id, normalizeModel(obj));
        any = true;
      } catch (e) {
        console.warn("model", v.id, e);
      }
    }
  }
  if (any && ctx) {
    E.syncScene();
  }
}
var themeEl = () => host.themeTarget || ROOT.el;
function applyTheme(t) {
  themeEl().dataset.theme = t;
  lsSet(host.themeKey, t);
  host.onTheme?.(t);
  V.theme = t;
  if (V.ok) {
    E.recolorMats();
    E.syncScene(true);
  }
  E.renderTop();
  E.renderStamp();
}
function listen(target, type, fn) {
  target.addEventListener(type, fn);
  ctx.listeners.push([target, type, fn]);
}
function bindEvents() {
  listen($("#siteSel"), "change", (e) => switchSite(S.app.sites.find((s) => String(s.id) === e.target.value)?.id));
  listen($("#roleSel"), "change", (e) => {
    if (!S.rights.is_manager) {
      return;
    }
    S.app.viewAs = e.target.value === "manager" ? null : e.target.value;
    S.edit = null;
    S.issues = runLive();
    E.renderAll();
    const ly = layerOf(S.ui.layer);
    if (ly && S.app.mode === "edit" && !canEditLayer(ly)) {
      toast(lockHint(ly), "warn");
    }
  });
  $$("#modeSeg button").forEach(
    (b) => listen(b, "click", () => {
      S.app.mode = b.dataset.mode;
      S.edit = null;
      E.cancelModes();
      E.renderAll();
    })
  );
  listen($("#btnNewSite"), "click", () => runDialog("newSite"));
  listen($("#btnPublish"), "click", publish);
  listen($("#btnHistory"), "click", () => E.openHistory());
  listen($("#btnTheme"), "click", () => applyTheme(E.curTheme() === "dark" ? "light" : "dark"));
  $$("#ltabs button").forEach((b) => listen(b, "click", () => E.setLeftTab(b.dataset.tab)));
  $$("#mtabs button").forEach((b) => listen(b, "click", () => E.setMTab(b.dataset.mtab)));
  listen(document, "keydown", onKey);
  if (host.themeAuto && window.matchMedia) {
    listen(window.matchMedia("(prefers-color-scheme: dark)"), "change", () => {
      if (!themeEl().dataset.theme) {
        applyTheme(E.curTheme());
      }
    });
  }
  listen(window, "beforeunload", (e) => {
    if (ctx && (ctx.adapter.dirty || S.saveState === "error")) {
      e.preventDefault();
      e.returnValue = "";
    }
  });
}
function onKey(e) {
  if (!ctx || !ROOT.el || !ROOT.el.isConnected) {
    return;
  }
  const t = e.target;
  const typing = t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.tagName === "SELECT");
  if ($("dialog[open]") || document.querySelector(".modal.show, .o_dialog")) {
    return;
  }
  for (const [key, hk] of registries.hotkeys.getEntries()) {
    if (typing && !hk.typing) {
      continue;
    }
    if ((e.ctrlKey || e.metaKey) && !hk.ctrl) {
      continue;
    }
    if (e.altKey && !hk.alt) {
      continue;
    }
    if (hk.ctrl && !(e.ctrlKey || e.metaKey)) {
      continue;
    }
    const hit = hk.match ? hk.match(e) : (hk.code ? e.code === hk.code : e.key === hk.key) && (hk.shift == null || hk.shift === e.shiftKey);
    if (!hit || hk.when && !hk.when(e)) {
      continue;
    }
    try {
      if (hk.run(e) !== false) {
        return;
      }
    } catch (err) {
      console.error(`Гаряча клавіша «${key}»:`, err);
    }
  }
}
function registerBuiltinHotkeys() {
  const add = (key, hk, sequence) => registries.hotkeys.add(key, hk, { sequence, force: true });
  add(
    "escape",
    {
      key: "Escape",
      typing: true,
      run() {
        if (V.placing || V.ruler.on || V.pickMode) {
          E.cancelModes();
        } else if (S.sel) {
          E.selectObj(null);
        }
      }
    },
    10
  );
  add("rotate", { code: "KeyR", alt: true, run: (e) => (e.preventDefault(), E.rotateSel(e.shiftKey ? -1 : 1)) }, 20);
  add(
    "delete",
    {
      match: (e) => e.code === "Delete" || e.code === "Backspace",
      when: () => !!S.sel,
      run: (e) => (e.preventDefault(), E.askDelete())
    },
    30
  );
  add(
    "ruler",
    {
      code: "KeyM",
      run() {
        const on = !V.ruler.on;
        E.cancelModes();
        V.ruler.on = on;
        E.renderVTools();
      }
    },
    40
  );
  add(
    "nudge",
    {
      match: (e) => e.code.startsWith("Arrow"),
      when: () => !!S.sel,
      run(e) {
        e.preventDefault();
        const k = e.shiftKey ? 10 : 1;
        E.nudge(e.code === "ArrowRight" ? k : e.code === "ArrowLeft" ? -k : 0, e.code === "ArrowUp" ? k : e.code === "ArrowDown" ? -k : 0);
      }
    },
    50
  );
}
registerBuiltinHotkeys();
function wireAdapter(store) {
  store.onStatus = (status) => {
    if (!ctx) {
      return;
    }
    S.saveState = status;
    E.renderSaveState();
  };
  store.onSaved = (r) => {
    if (!ctx || !S.site) {
      return;
    }
    Object.assign(S.site, { draft_rev: r.rev, draft_changes: r.draft_changes, has_changes: r.has_changes });
    const pools = { "td.layer": S.layers, "td.slot": S.slots, "td.placement": S.placements };
    for (const u of r.updates) {
      const rec = (pools[u.model] || []).find((x) => x.id === u.uid);
      if (rec) {
        rec.rid = u.rid ?? rec.rid;
        if (u.etag) {
          rec.etag = u.etag;
        }
      }
    }
    E.renderChips();
  };
  store.onConflict = () => E.askConflict();
  store.onReject = (r) => toast(r.message || "Сервер відхилив зміну.", "err");
  store.onReload = () => {
    if (ctx && S.site) {
      syncNow();
      ctx.adapter.flush().then(() => ctx && reload());
    }
  };
}
async function mountEditor(rootEl, { adapter, store, host: hostSvc, services, siteId, testMode } = {}) {
  adapter = assertAdapter(adapter || store);
  resetState();
  setHost({ ...hostSvc || {}, services: { ...hostSvc?.services || {}, ...services || {} } });
  setCapabilities(adapter.capabilities);
  ROOT.el = rootEl;
  ctx = { adapter, listeners: [] };
  E.adapter = adapter;
  E.store = adapter;
  E.host = host;
  rootEl.innerHTML = BODY_HTML;
  const th = lsGet(host.themeKey);
  if (th === "dark" || th === "light") {
    themeEl().dataset.theme = th;
    host.onTheme?.(th);
  } else if (!host.themeAuto) {
    themeEl().dataset.theme = "light";
  }
  V.theme = E.curTheme();
  V.testMode = !!testMode;
  wireAdapter(adapter);
  if (host.debug) {
    window.__f3dEditor = { S, V, E, THREE, adapter, store: adapter };
  }
  try {
    await loadThree();
  } catch (e) {
    $("#vp").append(Object.assign(document.createElement("div"), { className: "nogl", textContent: "Не вдалося завантажити 3D-бібліотеку: " + (e.message || e) }));
    throw e;
  }
  if (!ctx) {
    return;
  }
  bindEvents();
  S.app.sites = await adapter.listSites();
  if (!ctx) {
    return;
  }
  if (!S.app.sites.length) {
    $("#vp").append(Object.assign(document.createElement("div"), { className: "nogl", textContent: "Площадок немає. Створіть площадку в меню «Планування → Площадки»." }));
    return;
  }
  const stored = lsGet(host.siteKey);
  const want = siteId ?? stored;
  const entry = S.app.sites.find((s) => String(s.id) === String(want)) || S.app.sites[0];
  E.initScene();
  await openSite(entry.id);
  rootEl.dataset.ready = "1";
}
function unmountEditor() {
  if (!ctx) {
    return;
  }
  const c = ctx;
  try {
    scheduleSave.cancel();
    saveSiteProps.cancel();
    if (S.site) {
      c.adapter.save(S);
    }
    c.adapter.flush();
  } catch {
  }
  for (const [target, type, fn] of c.listeners) {
    target.removeEventListener(type, fn);
  }
  E.cancelModes?.();
  E.disposeScene?.();
  ctx = null;
  if (ROOT.el) {
    ROOT.el.innerHTML = "";
    delete ROOT.el.dataset.ready;
  }
  ROOT.el = null;
  resetState();
}
Object.assign(E, { commit, scheduleSave, flushNow, reload, switchSite, createSite, restoreVersion, publish, validateOnServer, saveSiteProps, runDialog, openVariantForm, openPassportForm, openRecord, normalizeModel, loadVariantModels });

// core/constructor/adapter_odoo.js
var adapter_odoo_exports = {};
__export(adapter_odoo_exports, {
  OdooAdapter: () => OdooAdapter,
  OdooStore: () => OdooStore,
  StoreError: () => StoreError,
  attachRules: () => attachRules,
  layerFromApi: () => layerFromApi,
  layerToApi: () => layerToApi,
  newUid: () => newUid,
  normalizeLoaded: () => normalizeLoaded,
  passportFromApi: () => passportFromApi,
  placementFromApi: () => placementFromApi,
  placementToApi: () => placementToApi,
  polygonToRect: () => polygonToRect,
  putawayFromApi: () => putawayFromApi,
  putawayToApi: () => putawayToApi,
  rectToPolygon: () => rectToPolygon,
  replenishFromApi: () => replenishFromApi,
  replenishToApi: () => replenishToApi,
  slotFromApi: () => slotFromApi,
  slotToApi: () => slotToApi,
  variantFromApi: () => variantFromApi
});
var MODEL_ORDER = { "td.check.config": 0, "td.layer": 1, "td.slot": 2, "td.placement": 3, "td.putaway.rule": 4, "td.replenish.rule": 5 };
var REF_MODELS = { layer_id: "td.layer", slot_id: "td.slot" };
var RES_OF_MODEL = { "stock.location": "location", "maintenance.equipment": "equipment", "mrp.workcenter": "workcenter", "stock.warehouse.orderpoint": "replenish", "stock.putaway.rule": "putaway" };
var BATCH = 400;
var rectOf = (a) => ({
  ...a,
  x0: Math.min(a.x0, a.x1),
  x1: Math.max(a.x0, a.x1),
  y0: Math.min(a.y0, a.y1),
  y1: Math.max(a.y0, a.y1)
});
function polygonToRect(poly) {
  if (!poly || poly.length !== 4) {
    return null;
  }
  const [p0, p1, p2, p3] = poly;
  const ex2 = p1[0] - p0[0];
  const ey = p1[1] - p0[1];
  const fx = p2[0] - p1[0];
  const fy = p2[1] - p1[1];
  const l = Math.hypot(ex2, ey);
  const w = Math.hypot(fx, fy);
  const tol = 1e-6 * Math.max(1, l, w);
  if (l < tol || w < tol || Math.abs(ex2 * fx + ey * fy) > tol * Math.max(l, w) * 1e3) {
    return null;
  }
  if (Math.abs(p0[0] + fx - p3[0]) > tol * 1e3 || Math.abs(p0[1] + fy - p3[1]) > tol * 1e3) {
    return null;
  }
  return {
    cx: (p0[0] + p2[0]) / 2,
    cy: (p0[1] + p2[1]) / 2,
    l,
    w,
    rot: (Math.atan2(ey, ex2) * 180 / Math.PI + 360) % 360
  };
}
function rectToPolygon(cx, cy, l, w, rot) {
  const r = rot * Math.PI / 180;
  const c = Math.cos(r);
  const s = Math.sin(r);
  return [
    [-l / 2, -w / 2],
    [l / 2, -w / 2],
    [l / 2, w / 2],
    [-l / 2, w / 2]
  ].map(([x, y]) => [rnd(cx + x * c - y * s, 6), rnd(cy + x * s + y * c, 6)]);
}
function underlayFromApi(u) {
  if (!u) {
    return null;
  }
  const p = u.params || {};
  return {
    url: u.url,
    name: u.name || "",
    format: u.format,
    status: u.status,
    params: {
      unit: p.unit || "mm",
      dx: p.dx ?? 0,
      dy: p.dy ?? 0,
      rot_deg: p.rot_deg ?? 0,
      scale: p.scale ?? 1,
      opacity: p.opacity ?? 0.75
    }
  };
}
function layerFromApi(l) {
  const groups = l.edit_groups || [];
  return {
    id: l.uid,
    rid: l.id,
    etag: l.etag,
    name: l.name,
    kind: l.kind,
    sequence: l.sequence,
    elevation: l.elevation,
    grid_step: l.grid_step,
    aisle_width: l.aisle_width,
    max_floor_load: l.max_floor_load,
    bounds: l.bounds || null,
    slot_types: [...l.slot_types || []],
    group: l.group || "",
    edit_groups: clone(groups),
    edit_roles: ["manager", ...groups.map((g3) => g3.role).filter((r) => r && r !== "manager")],
    color: l.color,
    opacity: l.opacity,
    style: l.style,
    visible: l.visible !== false,
    aisles: (l.aisles || []).map(rectOf),
    fire_paths: (l.fire_paths || []).map(rectOf),
    utilities: clone(l.utilities || []),
    underlay: underlayFromApi(l.underlay)
  };
}
function putawayFromApi(r) {
  return {
    id: r.uid,
    rid: r.id,
    etag: r.etag,
    product_id: r.product_id ?? null,
    product: r.product || "",
    category_id: r.category_id ?? null,
    package_type_ids: [...r.package_type_ids || []],
    in_location_id: r.in_location_id ?? null,
    out_code: r.out_code || "",
    out_location_id: r.out_location_id ?? null,
    sublocation: r.sublocation || "no",
    storage_category_id: r.storage_category_id ?? null,
    sequence: r.sequence ?? 10,
    odoo_rule_id: r.odoo_rule_id ?? null,
    deleted: !!r.deleted
  };
}
var putawayToApi = (r) => ({
  uid: r.id,
  product_id: r.product_id ?? null,
  category_id: r.category_id ?? null,
  package_type_ids: [...r.package_type_ids || []],
  in_location_id: r.in_location_id ?? null,
  out_code: r.out_code || null,
  out_location_id: r.out_location_id ?? null,
  sublocation: r.sublocation || "no",
  storage_category_id: r.sublocation === "closest_location" ? r.storage_category_id ?? null : null,
  sequence: r.sequence ?? 10,
  deleted: !!r.deleted
});
function replenishFromApi(r) {
  return {
    id: r.uid,
    rid: r.id,
    etag: r.etag,
    product_id: r.product_id ?? null,
    product: r.product || "",
    cell_code: r.cell_code || "",
    location_id: r.location_id ?? null,
    min_qty: r.min_qty || 0,
    max_qty: r.max_qty || 0,
    odoo_orderpoint_id: r.odoo_orderpoint_id ?? null,
    deleted: !!r.deleted
  };
}
var replenishToApi = (r) => ({
  uid: r.id,
  product_id: r.product_id ?? null,
  cell_code: r.cell_code || null,
  location_id: r.location_id ?? null,
  min_qty: r.min_qty || 0,
  max_qty: r.max_qty || 0,
  deleted: !!r.deleted
});
function attachRules(st, rules) {
  const r = rules || {};
  Object.defineProperty(st.site, "rules", { value: { putaway: (r.putaway || []).map(putawayFromApi), replenish: (r.replenish || []).map(replenishFromApi) }, writable: true, configurable: true, enumerable: false });
  return st;
}
function slotFromApi(s, layerUid) {
  const rec = {
    id: s.uid,
    rid: s.id,
    etag: s.etag,
    layer_id: layerUid.get(s.layer_id),
    template: s.template,
    code_prefix: s.code_prefix,
    x: s.x,
    y: s.y,
    rotation: s.rotation || 0,
    // S2 (MERGE §3.3): категорія зберігання, стратегія списання, функція й атрибути зони, температурний режим (null — успадкувати)
    storage_category_id: s.storage_category_id ?? null,
    removal_strategy_id: s.removal_strategy_id ?? null,
    function_id: s.function_id ?? null,
    attr_ids: [...s.attr_ids || []],
    temp_min_c: s.temp_min_c || 0,
    temp_max_c: s.temp_max_c || 0,
    params: clone(s.params || {}),
    overrides: clone(s.overrides || {}),
    parent_location_id: s.parent_location_id || null,
    note: s.note || ""
  };
  if (s.template === "zone") {
    const poly = rec.params.polygon || [];
    const rc = polygonToRect(poly);
    const old = rec.params;
    const xs = poly.map((p) => p[0]);
    const ys = poly.map((p) => p[1]);
    if (rc) {
      rec.x = rnd(rc.cx, 6);
      rec.y = rnd(rc.cy, 6);
      rec.rotation = rnd(rc.rot, 6);
      rec.params = { length: rnd(rc.l, 6), width: rnd(rc.w, 6) };
    } else {
      rec.x = (Math.min(...xs) + Math.max(...xs)) / 2;
      rec.y = (Math.min(...ys) + Math.max(...ys)) / 2;
      rec.rotation = 0;
      rec.params = { length: Math.max(...xs) - Math.min(...xs), width: Math.max(...ys) - Math.min(...ys) };
      rec.locked = true;
      rec.polygon = clone(poly);
    }
    rec.params.title = s.note || old.title || s.code_prefix;
    rec.params.color = old.color || null;
  }
  return rec;
}
function placementFromApi(p, layerUid, slotUid) {
  return {
    id: p.uid,
    rid: p.id,
    etag: p.etag,
    layer_id: layerUid.get(p.layer_id),
    variant_id: String(p.variant_id),
    slot_id: p.slot_id ? slotUid.get(p.slot_id) || null : null,
    cell_code: p.cell_code || null,
    x: p.x,
    y: p.y,
    rotation: p.rotation || 0,
    code: p.code,
    name: p.name,
    equipment: p.equipment || null,
    dynamic: !!p.dynamic
  };
}
function variantFromApi(v) {
  return { ...clone(v), id: String(v.id), rid: v.id };
}
function passportFromApi(p) {
  return {
    id: String(p.passport_id),
    pid: p.passport_id,
    name: p.name,
    role: p.role,
    manufacturer: p.manufacturer,
    model: p.model,
    category: p.category || "other",
    variants: (p.variants || []).map(variantFromApi)
  };
}
function normalizeLoaded(data) {
  const settings = data.site.settings || {};
  const layers = (data.layers || []).map(layerFromApi);
  const layerUid = new Map((data.layers || []).map((l) => [l.id, l.uid]));
  const slots = (data.slots || []).map((s) => slotFromApi(s, layerUid));
  const slotUid = new Map((data.slots || []).map((s) => [s.id, s.uid]));
  const placements = (data.placements || []).map((p) => placementFromApi(p, layerUid, slotUid));
  const checks = {};
  for (const c of data.checks || []) {
    checks[c.check] = { enabled: !!c.enabled, mode: c.mode, params: clone(c.params || {}), id: c.id ?? null };
  }
  const reach = checks.utility_reach?.params?.max_m ?? settings.reach_default_m ?? 15;
  const site = data.site;
  return {
    site: {
      id: site.id,
      name: site.name,
      code: site.code,
      building: { ...site.building },
      column_grid: { ...site.column_grid },
      default_parent_location: site.default_parent_location || null,
      active_version: site.active_version || null,
      draft_base_version: site.draft_base_version || null,
      draft_rev: site.draft_rev,
      draft_changes: site.draft_changes,
      has_changes: site.has_changes,
      settings
    },
    layers,
    slots,
    placements,
    catalog: (data.catalog || []).map(passportFromApi),
    settings: { checks, reach_n: reach, labels: true },
    versions: clone(data.versions || []),
    rights: {
      is_manager: !!data.rights?.is_manager,
      roles: [...data.rights?.roles || []],
      editable_layer_ids: [...data.rights?.editable_layer_ids || []],
      can_publish: !!data.rights?.can_publish,
      can_edit_catalog: !!data.rights?.can_edit_catalog
    }
  };
}
var ref = (uid2) => uid2 ? "@" + uid2 : null;
var num2 = (v) => v == null || v === "" ? 0 : Number(v);
function rectToApi(a, i, prefix) {
  const r = rectOf(a);
  const out = {
    id: String(a.id || `${prefix}${i + 1}`).slice(0, 32),
    name: String(a.name || "").slice(0, 64),
    x0: rnd(r.x0, 4),
    y0: rnd(r.y0, 4),
    x1: rnd(r.x1, 4),
    y1: rnd(r.y1, 4)
  };
  if (a.kind) {
    out.kind = a.kind;
  }
  return out;
}
function layerToApi(l, groupIds = {}) {
  const vals = {
    uid: l.id,
    name: l.name,
    kind: l.kind,
    sequence: Math.round(l.sequence),
    elevation_m: num2(l.elevation),
    grid_step_m: num2(l.grid_step),
    aisle_width_m: num2(l.aisle_width),
    max_floor_load_kn_m2: num2(l.max_floor_load),
    bounds: l.bounds && l.bounds.length >= 3 ? l.bounds.map((p) => [rnd(p[0], 4), rnd(p[1], 4)]) : null,
    color: l.color,
    opacity: num2(l.opacity),
    style: l.style || "solid",
    aisles: (l.aisles || []).map((a, i) => rectToApi(a, i, "ai")),
    fire_paths: (l.fire_paths || []).map((a, i) => rectToApi({ kind: "path", ...a }, i, "fp")),
    utilities: (l.utilities || []).map((u, i) => ({
      id: String(u.id || `u${i + 1}`).slice(0, 32),
      kind: u.kind,
      name: String(u.name || "").slice(0, 64),
      x: rnd(u.x, 4),
      y: rnd(u.y, 4),
      z: rnd(u.z || 0, 4)
    })),
    allowed_slot_types: [...l.slot_types || []]
  };
  if (l.underlay) {
    vals.underlay_params = { ...l.underlay.params };
  }
  const roles = (l.edit_roles || []).filter((r) => r !== "manager");
  if (roles.every((r) => groupIds[r] != null)) {
    vals.edit_group_ids = roles.map((r) => groupIds[r]).sort((a, b) => a - b);
  }
  return vals;
}
function slotToApi(s) {
  const vals = {
    uid: s.id,
    layer_id: ref(s.layer_id),
    template: s.template,
    code_prefix: s.code_prefix,
    x_m: rnd(s.x, 4),
    y_m: rnd(s.y, 4),
    rotation: rnd(s.rotation || 0, 4),
    storage_category_id: s.storage_category_id ?? null,
    removal_strategy_id: s.removal_strategy_id ?? null,
    function_id: s.function_id ?? null,
    attr_ids: [...s.attr_ids || []],
    temp_min_c: s.temp_min_c || 0,
    temp_max_c: s.temp_max_c || 0,
    params: clone(s.params),
    overrides: clone(s.overrides || {})
  };
  if (s.template === "zone") {
    const title = s.params.title;
    vals.x_m = 0;
    vals.y_m = 0;
    vals.rotation = 0;
    vals.params = {
      polygon: s.locked ? clone(s.polygon) : rectToPolygon(s.x, s.y, s.params.length, s.params.width, s.rotation || 0)
    };
    if (title != null && title !== s.code_prefix) {
      vals.note = String(title).slice(0, 255);
    }
  }
  return vals;
}
function placementToApi(p) {
  return {
    uid: p.id,
    layer_id: ref(p.layer_id),
    variant_id: Number(p.variant_id),
    slot_id: ref(p.slot_id),
    cell_code: p.cell_code || null,
    code: p.code,
    name: p.name || p.code,
    x_m: rnd(p.x, 4),
    y_m: rnd(p.y, 4),
    rotation: rnd(p.rotation || 0, 4)
  };
}
var same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
var OdooAdapter = class extends BaseAdapter {
  /**
   * @param {object} o
   * @param {Function} o.rpc          `rpc(route, params)` — JSON-RPC Odoo
   * @param {object}   [o.orm]        сервіс orm (створення вкладень підкладки, запис полів площадки, id налаштувань перевірок)
   * @param {object}   [o.action]     сервіс action (майстер публікації)
   * @param {Function} [o.uploadModel] завантаження 3D-моделі варіанта (API-09): `(variantId, {original, glb, meta}, opts) => Promise`
   * @param {number}   [o.autosaveMs] затримка автозбереження (settings.autosave_ms)
   * @param {number[]} [o.retryDelays] повтори при мережевій помилці: 2, 5, 15 с
   * @param {Function} [o.onStatus]   (status: 'saved'|'saving'|'error', info)
   * @param {Function} [o.onSaved]    ({rev, draft_changes, has_changes, updates: [{model, uid, rid, etag}]})
   * @param {Function} [o.onConflict] ({model, uid, current, message}) → 'mine' | 'theirs' (або проміс)
   * @param {Function} [o.onReject]   ({code, message, model, uid, kind})
   * @param {Function} [o.onReload]   () — автозбереження: сервер відхилив/змінив запис, стан слід перечитати (API-03)
   */
  constructor(o) {
    super(o);
    this.kind = "odoo";
    this.capabilities = { publish: true, check: true, ...o.capabilities || {} };
    this.rpc = o.rpc;
    this.orm = o.orm;
    this.action = o.action;
    this._uploadModel = o.uploadModel;
    this.retryDelays = o.retryDelays || [2e3, 5e3, 15e3];
    this.siteId = null;
    Object.assign(this.capabilities, { storage: true, putaway: true, rollback: true });
    this.groupIds = {};
    this._seq = 0;
    this._resetTracking();
  }
  _resetTracking() {
    clearTimeout(this._timer);
    this._timer = null;
    this._retryN = 0;
    this.pending = /* @__PURE__ */ new Map();
    this.rids = /* @__PURE__ */ new Map();
    this.etags = /* @__PURE__ */ new Map();
    this.byId = /* @__PURE__ */ new Map();
    this.shadow = /* @__PURE__ */ new Map();
  }
  get pendingCount() {
    return this.pending.size;
  }
  /** Є незбережені зміни (черга або запит у польоті) — для `beforeunload`. */
  get dirty() {
    return this.pending.size > 0 || !!this.flushing;
  }
  // --- читання -------------------------------------------------------------------------------------------
  async _call(route, params) {
    return await this.rpc(route, params);
  }
  /** API-01 */
  async listSites() {
    const res = await this._call("/f3d/constructor/sites", {});
    if (!res.ok) {
      throw new StoreError(res.code, res.message);
    }
    return res.sites;
  }
  /** API-02: повертає id нової площадки. */
  async createSite({ name, code, building }) {
    const res = await this._call("/f3d/constructor/site/create", { name, code, ...building ? { building } : {} });
    if (!res.ok) {
      throw new StoreError(res.code, res.message);
    }
    return res.site_id;
  }
  /** API-03: завантажує площадку й скидає відстеження змін (чергу слід скинути на сервер перед цим: `flush()`). */
  async load(id) {
    const res = await this._call("/f3d/constructor/load", { site_id: id });
    if (!res.ok) {
      throw new StoreError(res.code, res.message);
    }
    const st = attachRules(normalizeLoaded(res), res.rules);
    this.reset(id, st);
    return st;
  }
  /** Запам'ятовує серверні id/etag і «тіньовий» знімок сутностей стану. */
  reset(siteId, st) {
    this._resetTracking();
    this.siteId = siteId;
    const groupIds = {};
    for (const l of st.layers) {
      this._bind("td.layer", l.id, l.rid, l.etag);
      for (const g3 of l.edit_groups || []) {
        if (g3.role) {
          groupIds[g3.role] = g3.id;
        }
      }
    }
    this.groupIds = { ...this.groupIds, ...groupIds };
    for (const s of st.slots) {
      this._bind("td.slot", s.id, s.rid, s.etag);
    }
    for (const p of st.placements) {
      this._bind("td.placement", p.id, p.rid, p.etag);
    }
    for (const [check, c] of Object.entries(st.settings.checks)) {
      if (c.id != null) {
        this._bind("td.check.config", check, c.id, null);
      }
    }
    for (const r of st.site.rules?.putaway || []) {
      this._bind("td.putaway.rule", r.id, r.rid, r.etag);
    }
    for (const r of st.site.rules?.replenish || []) {
      this._bind("td.replenish.rule", r.id, r.rid, r.etag);
    }
    this._snapshot(st);
    this._setStatus("saved");
  }
  _bind(model, uid2, rid, etag) {
    const key = `${model}:${uid2}`;
    if (rid != null) {
      this.rids.set(key, rid);
      this.byId.set(`${model}:${rid}`, key);
    }
    if (etag) {
      this.etags.set(key, etag);
    }
  }
  _snapshot(st) {
    this.shadow.clear();
    for (const e of this._entities(st)) {
      this.shadow.set(e.key, JSON.stringify(e.vals));
    }
  }
  _entities(st) {
    const out = [];
    for (const l of st.layers) {
      out.push({ model: "td.layer", uid: l.id, key: "td.layer:" + l.id, vals: layerToApi(l, this.groupIds) });
    }
    for (const s of st.slots) {
      out.push({ model: "td.slot", uid: s.id, key: "td.slot:" + s.id, vals: slotToApi(s) });
    }
    for (const p of st.placements) {
      out.push({ model: "td.placement", uid: p.id, key: "td.placement:" + p.id, vals: placementToApi(p) });
    }
    for (const r of st.site?.rules?.putaway || []) {
      out.push({ model: "td.putaway.rule", uid: r.id, key: "td.putaway.rule:" + r.id, vals: putawayToApi(r) });
    }
    for (const r of st.site?.rules?.replenish || []) {
      out.push({ model: "td.replenish.rule", uid: r.id, key: "td.replenish.rule:" + r.id, vals: replenishToApi(r) });
    }
    return out;
  }
  // --- запис: черга операцій -----------------------------------------------------------------------------
  /**
   * Додає операцію API-04 у чергу; операції над тим самим записом зливаються:
   * create+write → create; write+write → один write; create+unlink → нічого; write+unlink → unlink.
   * Автозбереження спрацьовує через `autosaveMs`.
   * @param {{model: string, op: 'create'|'write'|'unlink', uid?: string, id?: number, etag?: string, vals?: object}} op
   */
  queue(op) {
    const { model } = op;
    const uid2 = op.uid ?? op.tmp;
    const key = `${model}:${uid2 ?? "#" + op.id}`;
    if (op.id != null && uid2 == null) {
      this._bind(model, `#${op.id}`, op.id, op.etag);
    }
    const cur = this.pending.get(key);
    if (op.op === "create") {
      this.pending.set(key, { model, kind: "create", uid: uid2, vals: { ...op.vals }, seq: this._seq++ });
    } else if (op.op === "write") {
      if (cur && (cur.kind === "create" || cur.kind === "write")) {
        Object.assign(cur.vals, op.vals);
      } else if (!cur) {
        this.pending.set(key, { model, kind: "write", uid: uid2, id: op.id, etag: op.etag, vals: { ...op.vals }, seq: this._seq++ });
      }
    } else if (op.op === "unlink") {
      if (cur && cur.kind === "create") {
        this.pending.delete(key);
      } else {
        this.pending.set(key, { model, kind: "unlink", uid: uid2, id: op.id, etag: cur?.etag ?? op.etag, seq: this._seq++ });
      }
    }
    if (this.pending.size) {
      this._setStatus("saving");
      this._schedule(this.autosaveMs);
    }
  }
  /** Контракт: порівнює стан із відомим серверу й ставить зміни в чергу; `now` — відправити негайно. */
  save(st, { now = false } = {}) {
    this.sync(st);
    return now ? this.flush() : void 0;
  }
  /**
   * Порівнює стан редактора (шари, місця, розміщення) з тим, що вже знає сервер, і ставить у чергу create/write/unlink
   * (write — лише змінені поля). Повертає кількість поставлених операцій.
   */
  sync(st) {
    let n = 0;
    const seen = /* @__PURE__ */ new Set();
    for (const e of this._entities(st)) {
      seen.add(e.key);
      const before = this.shadow.get(e.key);
      if (before === void 0) {
        this.queue({ model: e.model, op: "create", uid: e.uid, vals: e.vals });
        n++;
      } else if (before !== JSON.stringify(e.vals)) {
        const prev = JSON.parse(before);
        const diff = {};
        for (const k of Object.keys(e.vals)) {
          if (!same(e.vals[k], prev[k])) {
            diff[k] = e.vals[k];
          }
        }
        this.queue({ model: e.model, op: "write", uid: e.uid, vals: diff });
        n++;
      } else {
        continue;
      }
      this.shadow.set(e.key, JSON.stringify(e.vals));
    }
    for (const key of [...this.shadow.keys()]) {
      if (!seen.has(key)) {
        const [model, uid2] = [key.slice(0, key.indexOf(":")), key.slice(key.indexOf(":") + 1)];
        this.shadow.delete(key);
        this.queue({ model, op: "unlink", uid: uid2 });
        n++;
      }
    }
    return n;
  }
  _schedule(delay) {
    if (this._timer) {
      return;
    }
    this._timer = setTimeout(async () => {
      this._timer = null;
      const r = await this.flush();
      if (r && r.reload && r.ok !== false) {
        this.onReload();
      }
    }, delay);
  }
  _scheduleRetry() {
    const delays = this.retryDelays;
    const d = delays[Math.min(this._retryN, delays.length - 1)];
    this._retryN++;
    clearTimeout(this._timer);
    this._timer = null;
    this._schedule(d);
  }
  _resolve(vals) {
    const out = { ...vals };
    for (const [field, model] of Object.entries(REF_MODELS)) {
      const v = out[field];
      if (typeof v === "string" && v.startsWith("@")) {
        const rid = this.rids.get(`${model}:${v.slice(1)}`);
        if (rid != null) {
          out[field] = rid;
        }
      }
    }
    return out;
  }
  /** Бере з черги пакет операцій (create → write → unlink; за порядком моделей); записи, що чекають на create, лишаються. */
  _takeBatch() {
    const entries = [...this.pending.entries()];
    const rank = (e) => {
      const o = MODEL_ORDER[e.model] ?? 9;
      return e.kind === "create" ? o : e.kind === "write" ? 10 + o : 20 + (9 - o);
    };
    entries.sort((a, b) => rank(a[1]) - rank(b[1]) || a[1].seq - b[1].seq);
    const batch = [];
    for (const [key, e] of entries) {
      if (batch.length >= BATCH) {
        break;
      }
      const id = this.rids.get(key) ?? e.id;
      if (e.kind !== "create" && id == null) {
        continue;
      }
      const etag = this.etags.get(key) ?? e.etag;
      let op;
      if (e.kind === "create") {
        op = { model: e.model, op: "create", tmp: e.uid, vals: this._resolve(e.vals) };
      } else if (e.kind === "write") {
        op = { model: e.model, op: "write", id, ...etag ? { etag } : {}, vals: this._resolve(e.vals) };
      } else {
        op = { model: e.model, op: "unlink", id, ...etag ? { etag } : {} };
      }
      batch.push({ key, entry: e, op });
    }
    for (const b of batch) {
      this.pending.delete(b.key);
    }
    return batch;
  }
  /** Повертає записи в чергу (з урахуванням змін, поставлених, поки запит був у польоті). */
  _requeue(items) {
    for (const { key, entry } of items) {
      const cur = this.pending.get(key);
      if (!cur) {
        this.pending.set(key, entry);
      } else if (entry.kind === "create" && cur.kind === "write") {
        cur.kind = "create";
        cur.vals = { ...entry.vals, ...cur.vals };
      } else if (entry.kind === "write" && cur.kind === "write") {
        cur.vals = { ...entry.vals, ...cur.vals };
        cur.etag = entry.etag ?? cur.etag;
      }
    }
  }
  /** Надсилає чергу (API-04); повертає {ok, rejected, reload}. Паралельні виклики стають у чергу. */
  flush() {
    if (this.flushing) {
      this._again = true;
      return this.flushing;
    }
    clearTimeout(this._timer);
    this._timer = null;
    this.flushing = this._flushLoop().finally(() => {
      this.flushing = null;
      if (this._again) {
        this._again = false;
        if (this.pending.size) {
          this._schedule(0);
        }
      }
    });
    return this.flushing;
  }
  async _flushLoop() {
    const result = { ok: true, rejected: [], reload: false };
    for (let guard = 0; guard < 100 && this.pending.size; guard++) {
      const batch = this._takeBatch();
      if (!batch.length) {
        break;
      }
      this._setStatus("saving");
      let res;
      try {
        res = await this._call("/f3d/constructor/save", { site_id: this.siteId, ops: batch.map((b) => b.op) });
      } catch (e) {
        this._requeue(batch);
        this._setStatus("error", e);
        this._scheduleRetry();
        return { ...result, ok: false, error: e };
      }
      if (res.ok) {
        this._applyOk(batch, res);
        this._retryN = 0;
        continue;
      }
      const bad = res.op_index != null ? batch[res.op_index] : null;
      const rest = batch.filter((b) => b !== bad);
      if (res.code === "conflict" && bad) {
        const choice = await this.onConflict({
          model: bad.entry.model,
          uid: bad.entry.uid,
          current: res.current,
          message: res.message
        });
        if (choice === "mine") {
          if (res.current?.etag) {
            this.etags.set(bad.key, res.current.etag);
          }
          this._requeue(batch);
        } else {
          this._requeue(rest);
          result.reload = true;
          result.rejected.push({ code: "conflict", message: res.message, model: bad.entry.model, uid: bad.entry.uid, kind: bad.entry.kind });
        }
        continue;
      }
      const dropped = bad ? [bad] : batch;
      if (bad) {
        this._requeue(rest);
      }
      for (const b of dropped) {
        const rej = { code: res.code, message: res.message, model: b.entry.model, uid: b.entry.uid, kind: b.entry.kind };
        result.rejected.push(rej);
        this.onReject(rej);
      }
      result.reload = true;
    }
    this._setStatus(this.pending.size ? "saving" : "saved");
    return result;
  }
  _applyOk(batch, res) {
    const idMap = res.id_map || {};
    const updates = [];
    for (const { key, entry } of batch) {
      if (entry.kind === "create") {
        const rid = idMap[entry.uid];
        if (rid != null) {
          this._bind(entry.model, entry.uid, rid, null);
          updates.push({ model: entry.model, uid: entry.uid, rid, etag: null });
        }
      } else if (entry.kind === "unlink") {
        const rid = this.rids.get(key);
        this.rids.delete(key);
        this.etags.delete(key);
        this.byId.delete(`${entry.model}:${rid}`);
      }
    }
    for (const [mid, etag] of Object.entries(res.etags || {})) {
      const key = this.byId.get(mid);
      if (key) {
        this.etags.set(key, etag);
        const model = mid.slice(0, mid.indexOf(":"));
        const upd = updates.find((u) => u.model === model && `${u.model}:${u.rid}` === mid);
        if (upd) {
          upd.etag = etag;
        } else {
          updates.push({ model, uid: key.slice(model.length + 1), rid: this.rids.get(key), etag });
        }
      }
    }
    this.onSaved({ rev: res.rev, draft_changes: res.draft_changes, has_changes: res.has_changes, id_map: idMap, updates });
  }
  // --- інші виклики --------------------------------------------------------------------------------------
  /** API-05: перевірка на сервері (спершу зберігає чергу). */
  async check(layerId) {
    await this.flush();
    const res = await this._call("/f3d/constructor/validate", { site_id: this.siteId, ...layerId ? { layer_id: layerId } : {} });
    if (!res.ok) {
      throw new StoreError(res.code, res.message);
    }
    return res;
  }
  /**
   * API-06: зберігає чергу, створює майстер публікації й відкриває його діалогом (попередній перегляд «буде створено /
   * оновлено / пропонуємо архівувати» і підтвердження). Повертає відповідь API; `onClose` — після закриття майстра.
   */
  async publish({ onClose } = {}) {
    const fl = await this.flush();
    if (!fl.ok || this.pending.size) {
      throw new StoreError("save_failed", "Не вдалося зберегти чернетку перед публікацією.");
    }
    const res = await this._call("/f3d/constructor/publish/preview", { site_id: this.siteId });
    if (!res.ok) {
      throw new StoreError(res.code, res.message);
    }
    const act = { ...res.action };
    if (act.type === "ir.actions.act_window" && !act.views) {
      act.views = String(act.view_mode || "form").split(",").map((m) => [false, m.trim()]);
    }
    await this.action.doAction(act, { onClose });
    return res;
  }
  /** API-08: повертає чернетку до знімка версії. */
  async restoreVersion(versionId) {
    await this.flush();
    const res = await this._call("/f3d/constructor/version/restore", { version_id: versionId });
    if (!res.ok) {
      throw new StoreError(res.code, res.message);
    }
    return res;
  }
  /** Налаштування перевірки (API-04 для td.check.config; id записів — з API-03 або з ORM). */
  async saveCheck(check, vals) {
    const key = `td.check.config:${check}`;
    if (!this.rids.has(key) && this.orm) {
      const rows = await this.orm.searchRead("td.check.config", [["site_id", "=", this.siteId]], ["check_key"]);
      for (const r of rows) {
        this._bind("td.check.config", r.check_key, r.id, null);
      }
    }
    this.queue({ model: "td.check.config", op: "write", uid: check, id: this.rids.get(key), vals });
  }
  /**
   * Поля площадки (назва, габарити будівлі, крок колон) — стандартний ORM: API-04 їх не охоплює.
   * Нейтральний вигляд контракту: {name, building: {length, width, height}, column_grid: {step_x, step_y}} (метри);
   * поля Odoo (`building_length_m`…) проходять без змін.
   */
  async saveSite(vals) {
    const out = { ...vals };
    if (out.building) {
      const { length, width: width2, height } = out.building;
      Object.assign(out, { building_length_m: length, building_width_m: width2, building_height_m: height });
      delete out.building;
    }
    if (out.column_grid) {
      Object.assign(out, { column_step_x_m: out.column_grid.step_x, column_step_y_m: out.column_grid.step_y });
      delete out.column_grid;
    }
    await this.orm.write("td.site", [this.siteId], out);
  }
  /** id груп ролей конструктора (для «Хто редагує» шару): з уже завантажених шарів або з res.groups. */
  async ensureGroupIds(roles) {
    if (roles.every((r) => r === "manager" || this.groupIds[r] != null) || !this.orm) {
      return this.groupIds;
    }
    const rows = await this.orm.searchRead("res.groups", [["privilege_id.name", "=", "Конструктор"]], ["name"]);
    const map = { технолог: "technologist", комірник: "storekeeper", інженер: "engineer", менеджер: "manager" };
    for (const r of rows) {
      const role = map[String(r.name).split(":").pop().trim().toLowerCase()];
      if (role) {
        this.groupIds[role] = r.id;
      }
    }
    return this.groupIds;
  }
  /** Підкладка: файл → вкладення шару (ORM), далі — операція write у чергу (`underlay_attachment_id`). Повертає {id, url}. */
  async attachUnderlay(layer, file) {
    const data = await new Promise((res, rej) => {
      const r = new FileReader();
      r.onload = () => res(String(r.result).split(",").pop());
      r.onerror = () => rej(r.error);
      r.readAsDataURL(file);
    });
    const ids = await this.orm.create("ir.attachment", [
      { name: file.name, datas: data, res_model: "td.layer", res_id: layer.rid }
    ]);
    const id = Array.isArray(ids) ? ids[0] : ids;
    this.queue({ model: "td.layer", op: "write", uid: layer.id, vals: { underlay_attachment_id: id } });
    return { id, url: `/web/content/${id}` };
  }
  /** Знімає підкладку з шару (операція write у чергу). */
  async detachUnderlay(layer) {
    this.queue({ model: "td.layer", op: "write", uid: layer.id, vals: { underlay_attachment_id: false } });
  }
  /** 3D-модель варіанта (API-09): завантаження виконує хост (`o.uploadModel` — multipart + csrf, model/upload.js). */
  async uploadModel(variantId, payload, opts = {}) {
    if (!this._uploadModel) {
      throw new StoreError("not_supported", "Завантаження моделей у цьому хості не налаштоване.");
    }
    return await this._uploadModel(variantId, payload, opts);
  }
  /** Модель варіанта: GLB із вкладення (API-10; `?v=` — etag для скидання кешу) → Object3D або null. */
  async loadModel(variant, T) {
    const m = variant?.model;
    if (!m || m.status !== "ok" || !m.glb_url || !T?.GLTFLoader) {
      return null;
    }
    const gltf = await new T.GLTFLoader().loadAsync(m.glb_url + "?v=" + encodeURIComponent(variant.etag || ""));
    return gltf.scene;
  }
  /** Підкладка DXF: текст файла з вкладення шару (`underlay.url`) або null. */
  async loadUnderlay(layer) {
    const u = layer?.underlay;
    if (!u || u.format !== "dxf" || u.status !== "ready" || !u.url) {
      return null;
    }
    const r = await fetch(u.url, { credentials: "same-origin" });
    return r.ok ? { text: await r.text() } : null;
  }
  // --- S2: категорії зберігання, залишки, правила розміщення, журнал публікацій і відкат (API-12, API-15, API-17, API-18) ---
  /** API-12: `{op: "list"}` → {categories, strategies, functions, attrs}; `{op: "save", id?, vals, confirm}` → {category}; `{op: "delete", id, confirm}`. */
  async categories(req = { op: "list" }) {
    const res = await this._call("/f3d/constructor/storage_categories", req);
    if (!res.ok) {
      throw new StoreError(res.code, res.message);
    }
    return res;
  }
  /** Залишки й вага запасу за кодами комірок + макс. вага комірки: {loads: {код: {qty, weight_kg}}, limits}. */
  async stockLoads(codes) {
    const res = await this._call("/f3d/constructor/storage/loads", { site_id: this.siteId, ...codes ? { codes } : {} });
    if (!res.ok) {
      throw new StoreError(res.code, res.message);
    }
    return res;
  }
  /** API-17: зайнятість кодів у зовнішній системі → {codes: {код: {state: free|own|match|busy, reason}}}. */
  async codesCheck(codes) {
    const res = await this._call("/f3d/constructor/codes/check", { site_id: this.siteId, codes });
    if (!res.ok) {
      throw new StoreError(res.code, res.message);
    }
    return res;
  }
  /** API-15 `fit`: «чи вміститься» для правил розміщення чернетки → {rules: {uid: [{code, reason}]}}. */
  async putawayFit() {
    await this.flush();
    const res = await this._call("/f3d/constructor/putaway/fit", { site_id: this.siteId });
    if (!res.ok) {
      throw new StoreError(res.code, res.message);
    }
    return res;
  }
  /** API-15 `where`: куди Odoo покладе товар → {location: {id, code, name}, moved, estimate: false}. */
  async putawayWhere(q) {
    const res = await this._call("/f3d/constructor/putaway/where", { site_id: this.siteId, product_id: q.product_id, quantity: q.quantity, package_type_id: q.package_type_id || null, ...q.location_code ? { location_code: q.location_code } : {} });
    if (!res.ok) {
      throw new StoreError(res.code, res.message);
    }
    return res;
  }
  /** Пошук записів для форм правил: kind ∈ product | category | package_type | location; `ids` — назви за id. */
  async lookup(kind, term = "", ids = null) {
    const res = await this._call("/f3d/constructor/putaway/lookup", { site_id: this.siteId, kind, term, ...ids ? { ids } : {} });
    if (!res.ok) {
      throw new StoreError(res.code, res.message);
    }
    return res.rows;
  }
  /** API-18: журнал публікацій → {versions: [{id, n, counts, ops, rolled_back, can_rollback, reason}], can_rollback}. */
  async planLog() {
    const res = await this._call("/f3d/constructor/publish/log", { site_id: this.siteId });
    if (!res.ok) {
      throw new StoreError(res.code, res.message);
    }
    return res;
  }
  /** API-18: операції версії журналу. */
  async planOps(versionId) {
    const res = await this._call("/f3d/constructor/publish/log", { site_id: this.siteId, version_id: versionId });
    if (!res.ok) {
      throw new StoreError(res.code, res.message);
    }
    return res.ops.map((o) => ({ ...o, res: RES_OF_MODEL[o.res_model] || o.res_model }));
  }
  /** API-18: відкат публікації (лише записи Odoo; чернетка не змінюється). */
  async rollback(versionId) {
    const res = await this._call("/f3d/constructor/publish/rollback", { site_id: this.siteId, version_id: versionId, confirm: true });
    if (!res.ok) {
      throw new StoreError(res.code, res.message, { issues: res.issues });
    }
    return res;
  }
  // --- старі назви методів (HOOT-тести W2 і зовнішній код) ---
  loadSite(id) {
    return this.load(id);
  }
  validate(layerId) {
    return this.check(layerId);
  }
  publishPreview(o) {
    return this.publish(o);
  }
};
var OdooStore = OdooAdapter;

// core/constructor/capacity_core.js
var ZONE_FUNCTIONS = [
  { key: "receiving", name: "Приймання", color: "#3b82f6" },
  { key: "quality", name: "Контроль якості", color: "#8b5cf6" },
  { key: "quarantine", name: "Карантин", color: "#f59e0b" },
  { key: "storage", name: "Зберігання", color: "#10b981" },
  { key: "picking", name: "Комплектація", color: "#06b6d4" },
  { key: "packing", name: "Пакування", color: "#ec4899" },
  { key: "shipping", name: "Відвантаження", color: "#ef4444" },
  { key: "scrap", name: "Брак", color: "#6b7280" },
  { key: "returns", name: "Повернення", color: "#a855f7" },
  { key: "wip", name: "Буфер виробництва", color: "#84cc16" }
];
var ZONE_ATTRS = [
  { key: "temp", name: "Температурний режим" },
  { key: "hazmat", name: "Небезпечні вантажі" },
  { key: "valuable", name: "Цінне" },
  { key: "long", name: "Довгомірне" }
];
var ALLOW_NEW = [
  ["mixed", "Змішане зберігання"],
  ["same", "Лише той самий товар"],
  ["empty", "Лише порожнє місце"]
];
var SUBLOCATION = [
  ["no", "Ні"],
  ["closest_location", "Місце з категорією зберігання"],
  ["last_used", "Остання використана"]
];
var SUBLOCATION_LABEL = Object.fromEntries(SUBLOCATION);
var POLICY_LABEL = Object.fromEntries(ALLOW_NEW);
var cache2 = { loads: {}, limits: {}, fit: {}, codes: {}, demo: false };
var nameCache = /* @__PURE__ */ new Map();
var rememberName = (kind, id, name) => id != null && name && nameCache.set(`${kind}:${id}`, name);
function nameOf(kind, id) {
  const hit = nameCache.get(`${kind}:${id}`);
  if (hit) {
    return hit;
  }
  if (kind === "product" && S.site && S.site.rules) {
    const r = [...S.site.rules.putaway || [], ...S.site.rules.replenish || []].find((x) => x.product_id === id && x.product);
    if (r) {
      return r.product;
    }
  }
  return id != null ? `#${id}` : "—";
}
function rulesState() {
  if (!S.site) {
    return { putaway: [], replenish: [] };
  }
  if (!S.site.rules) {
    S.site.rules = { putaway: [], replenish: [] };
  }
  S.site.rules.putaway ||= [];
  S.site.rules.replenish ||= [];
  return S.site.rules;
}
var newPutawayRule = (o = {}) => ({
  id: newUid(),
  product_id: null,
  category_id: null,
  package_type_ids: [],
  in_location_id: null,
  out_code: "",
  out_location_id: null,
  sublocation: "no",
  storage_category_id: null,
  sequence: 10,
  odoo_rule_id: null,
  deleted: false,
  ...o
});
var newReplenishRule = (o = {}) => ({
  id: newUid(),
  product_id: null,
  cell_code: "",
  location_id: null,
  min_qty: 0,
  max_qty: 0,
  odoo_orderpoint_id: null,
  deleted: false,
  ...o
});
function ruleStatus(rule, base2, linkKey) {
  if (rule.deleted) {
    return "deleted";
  }
  if (!rule[linkKey]) {
    return "new";
  }
  const was = base2 && base2.get(rule.id);
  return was && was !== ruleSig(rule) ? "changed" : "";
}
var STATUS_LABEL = { new: "нове", changed: "змінене", deleted: "буде видалено" };
var SIG_FIELDS = ["product_id", "category_id", "package_type_ids", "in_location_id", "out_code", "out_location_id", "sublocation", "storage_category_id", "sequence", "cell_code", "location_id", "min_qty", "max_qty"];
var ruleSig = (r) => JSON.stringify(SIG_FIELDS.map((k) => r[k] === void 0 ? null : r[k]));
var rulesBase = (list) => new Map(list.map((r) => [r.id, ruleSig(r)]));
function zonePoly(z) {
  const l = z.params.length || 1;
  const w = z.params.width || 1;
  const a = (z.rotation || 0) * Math.PI / 180;
  const c = Math.cos(a);
  const s = Math.sin(a);
  return [[-l / 2, -w / 2], [l / 2, -w / 2], [l / 2, w / 2], [-l / 2, w / 2]].map(([x, y]) => [z.x + x * c - y * s, z.y + x * s + y * c]);
}
function zonesOf(slots = S.slots) {
  return slots.filter((s) => s.template === "zone").map((zone) => ({ zone, poly: zone.params.polygon || zonePoly(zone) }));
}
var polyArea = (poly) => Math.abs(poly.reduce((a, [x1, y1], i) => a + (x1 * poly[(i + 1) % poly.length][1] - poly[(i + 1) % poly.length][0] * y1), 0)) / 2;
function zoneChainAt(zones, x, y) {
  return zones.filter(({ poly }) => polygonContains(poly, [x, y])).sort((a, b) => polyArea(a.poly) - polyArea(b.poly)).map(({ zone }) => zone);
}
function inheritedField(slot, field, zone) {
  const has = (v) => v != null && v !== "" && !(Array.isArray(v) && !v.length);
  if (has(slot[field])) {
    return { value: slot[field], from: "own" };
  }
  for (const z of Array.isArray(zone) ? zone : zone ? [zone] : []) {
    if (has(z[field])) {
      return { value: z[field], from: "zone" };
    }
  }
  return { value: null, from: null };
}
function cellsAbs(slot, elevation = 0) {
  if (!SLOT_TEMPLATES[slot.template] || !SLOT_TEMPLATES[slot.template].cells) {
    return [];
  }
  return generateCells(slot.template, slot.code_prefix || "", slot.x, slot.y, slot.rotation || 0, slot.params, slot.overrides || {}, elevation);
}
function cellLimit(slot, cell, category) {
  const ov = (slot.overrides || {})[cell.code] || {};
  if (ov.max_load_kg != null && ov.max_load_kg > 0) {
    return { kg: ov.max_load_kg, source: "місце" };
  }
  if (cell.max_load_kg > 0) {
    return { kg: cell.max_load_kg, source: "тип місця" };
  }
  if (category && category.max_weight > 0) {
    return { kg: category.max_weight, source: "категорія" };
  }
  return { kg: 0, source: "" };
}
function capacitySummary(slots, { loads = null, categories = [], zone = null, allSlots = S.slots } = {}) {
  const zones = zonesOf(allSlots);
  const cats = new Map(categories.map((c) => [c.id, c]));
  const out = { cells: 0, places: 0, area: 0, volume: 0, maxWeight: 0, withCategory: 0, occupied: 0, free: 0, fill: null };
  for (const slot of slots) {
    for (const cell of cellsAbs(slot)) {
      const home = zoneChainAt(zones, cell.x, cell.y);
      if (zone && !home.includes(zone)) {
        continue;
      }
      const cat = cats.get(inheritedField(slot, "storage_category_id", home).value);
      out.cells++;
      out.places += cell.capacity || 0;
      if ((cell.level || 1) === 1) {
        out.area += cell.l * cell.w;
      }
      out.volume += cell.l * cell.w * cell.h;
      out.maxWeight += cellLimit(slot, cell, cat).kg;
      out.withCategory += inheritedField(slot, "storage_category_id", home).value ? 1 : 0;
      if (loads) {
        if ((loads[cell.code] || {}).qty > 0) {
          out.occupied++;
        } else {
          out.free++;
        }
      }
    }
  }
  if (loads && out.cells) {
    out.fill = out.occupied / out.cells;
  }
  return out;
}
var g2 = (v) => String(parseFloat(Number(v).toPrecision(6)));
var issue2 = (check, severity, layerId, codes, message, slotId) => ({ check, severity, layer_id: layerId, codes, message, keys: slotId ? [`s:${slotId}`] : [], id: `${check}|${codes.join(",")}|${message}` });
function cellLoadIssues(scene, config, eps = 1e-3, data = cache2) {
  const out = [];
  for (const slot of scene.slots.values()) {
    for (const [code, cell] of scene.slotCells(slot)) {
      const load = data.loads[code];
      const limit = data.limits[code] || cell.max_load_kg || 0;
      if (load && limit > 0 && load.weight_kg > limit + eps) {
        out.push(issue2("cell_load", config.mode, slot.layer_id, [code], `${code}: вага запасу ${g2(Math.round(load.weight_kg * 100) / 100)} кг перевищує допустимі ${g2(limit)} кг`, slot.id));
      }
    }
  }
  return out;
}
function putawayFitIssues(scene, config, eps = 1e-3, data = cache2, rules = rulesState().putaway) {
  const out = [];
  const bySlot = /* @__PURE__ */ new Map();
  for (const slot of scene.slots.values()) {
    for (const [code] of scene.slotCells(slot)) {
      bySlot.set(code, slot);
    }
  }
  for (const rule of rules) {
    if (rule.deleted) {
      continue;
    }
    for (const { code, reason } of data.fit[rule.id] || []) {
      const slot = bySlot.get(code);
      if (slot) {
        out.push(issue2("putaway_fit", config.mode, slot.layer_id, [code], `Правило «${ruleLabel(rule)}»: не вміститься в ${code} — ${reason}`, slot.id));
      }
    }
  }
  return out;
}
function codeConflictIssues(scene, config, eps = 1e-3, data = cache2) {
  const out = [];
  const owner = /* @__PURE__ */ new Map();
  for (const slot of scene.slots.values()) {
    for (const [code] of scene.slotCells(slot)) {
      const st = data.codes[code];
      if (st && st.state === "busy") {
        out.push(issue2("code_conflict", config.mode, slot.layer_id, [code], `${code}: ${st.reason}`, slot.id));
      }
      if (owner.has(code) && owner.get(code) !== slot.id) {
        const first = scene.slots.get(owner.get(code));
        out.push(issue2("code_conflict", config.mode, slot.layer_id, [code], `Код ${code} дублюється в місцях ${first.code_prefix} і ${slot.code_prefix}`, slot.id));
      }
      owner.set(code, slot.id);
    }
  }
  return out;
}
var ruleLabel = (rule) => rule.product_id ? rule.product || nameOf("product", rule.product_id) : rule.category_id ? rule.category || nameOf("category", rule.category_id) : "усі товари";
function rulesInto(code, slot, rules = rulesState().putaway, zone = null) {
  const cat = inheritedField(slot, "storage_category_id", zone).value;
  return rules.filter((r) => !r.deleted && (r.out_code === code || r.sublocation === "closest_location" && r.storage_category_id && r.storage_category_id === cat));
}
function rulesIntoSlot(slot, rules = rulesState().putaway, zone = null) {
  const out = [];
  for (const rule of rules) {
    if (rule.deleted) {
      continue;
    }
    const codes = cellsAbs(slot).map((c) => c.code).filter((code) => rulesInto(code, slot, [rule], zone).length);
    if (codes.length) {
      out.push({ rule, codes });
    }
  }
  return out;
}
registries.checks.add("cell_load", { run: (scene, config, eps) => cellLoadIssues(scene, config, eps), label: "Вага запасу в комірці" }, { sequence: 80, force: true });
registries.checks.add("putaway_fit", { run: (scene, config, eps) => putawayFitIssues(scene, config, eps), label: "Правило розміщення: вміститься" }, { sequence: 90, force: true });
registries.checks.add("code_conflict", { run: (scene, config, eps) => codeConflictIssues(scene, config, eps), label: "Конфлікт кодів і штрихкодів" }, { sequence: 95, force: true });
var EXTRA_CHECKS = [
  { id: "cell_load", name: "Вага запасу в комірці", hint: "Вага залишків із зовнішньої системи проти макс. ваги комірки чи категорії зберігання", mode: "warn" },
  { id: "putaway_fit", name: "Правило розміщення: вміститься", hint: "Вага/об'єм товару й габарити упаковки проти габаритів і макс. ваги комірки-цілі", mode: "warn" },
  { id: "code_conflict", name: "Конфлікт кодів і штрихкодів", hint: "Код зайнятий у зовнішній системі (інший склад, архів, інша компанія) або дублюється в чернетці", mode: "warn" }
];
var HIGHLIGHT = { target: "#2563eb", match: "#f59e0b" };
function highlightCodes(rule) {
  const targets = /* @__PURE__ */ new Set();
  const matches = /* @__PURE__ */ new Set();
  if (!rule) {
    return { targets, matches };
  }
  if (rule.out_code) {
    targets.add(rule.out_code);
  }
  for (const slot of S.slots) {
    for (const cell of cellsAbs(slot)) {
      if (rule.sublocation === "closest_location" && rule.storage_category_id && inheritedField(slot, "storage_category_id", null).value === rule.storage_category_id) {
        targets.add(cell.code);
      }
      const stock = cache2.loads[cell.code];
      if (rule.product_id && stock && (stock.product_ids || []).includes(rule.product_id)) {
        matches.add(cell.code);
      }
    }
  }
  return { targets, matches };
}
registries.metrics.add(
  "rule_target",
  {
    label: "Правило розміщення",
    color(cell) {
      const rule = rulesState().putaway.find((r) => r.id === S.ui.ruleHighlight);
      const { targets, matches } = highlightCodes(rule);
      return targets.has(cell.code) ? HIGHLIGHT.target : matches.has(cell.code) ? HIGHLIGHT.match : null;
    },
    legend: [["Куди веде правило", HIGHLIGHT.target], ["Є відповідний товар", HIGHLIGHT.match]]
  },
  { sequence: 80, force: true }
);

// core/constructor/plan_core.js
var KIND_LABEL = {
  create: "Створити",
  move: "Перенести",
  rename: "Перейменувати",
  attrs: "Атрибути",
  update: "Оновити",
  archive: "Архівувати"
};
var RES_LABEL = {
  location: "Місце зберігання",
  equipment: "Обладнання",
  workcenter: "Робочий центр",
  replenish: "Правило поповнення",
  putaway: "Правило розміщення"
};
var FLAG_LABEL = {
  stock: "є залишок",
  barcode_busy: "штрихкод уже зайнятий",
  moves: "є незавершені переміщення",
  requests: "є відкриті заявки",
  workorders: "є незавершені завдання",
  target: "ціль не знайдено",
  warehouse: "поза складом"
};
var OP_LABEL = { create: "створено", move: "переміщено", rename: "перейменовано", attrs: "змінено атрибути", archive: "архівовано" };
var VIEWS = [
  { id: "all", label: "Усе", test: () => true },
  { id: "create", label: "Створити", test: (l) => l.kind === "create" && !isRule(l) },
  { id: "move", label: "Перенести", test: (l) => l.kind === "move" },
  { id: "rename", label: "Перейменувати", test: (l) => l.kind === "rename" },
  { id: "attrs", label: "Атрибути", test: (l) => (l.kind === "attrs" || l.kind === "update") && !isRule(l) },
  { id: "archive", label: "Архів", test: (l) => l.kind === "archive" && !isRule(l) },
  { id: "rules", label: "Правила", test: (l) => isRule(l) },
  { id: "blocked", label: "Застосувати не можна", test: (l) => !!l.blocked }
];
var isRule = (l) => l.res === "replenish" || l.res === "putaway";
function viewCounts(lines) {
  return Object.fromEntries(VIEWS.map((v) => [v.id, lines.filter((l) => v.test(l)).length]));
}
function filterLines(lines, viewId, scopeUid = "") {
  const view = VIEWS.find((v) => v.id === viewId) || VIEWS[0];
  return lines.filter((l) => view.test(l) && (!scopeUid || inScope(l, scopeUid)));
}
var inScope = (l, uid2) => l.scope_uid === uid2 || l.zone_uid === uid2;
function selectAll(lines, on) {
  for (const l of lines) {
    if (l.kind !== "archive" || l.explicit) {
      l.selected = on && !l.blocked;
    }
  }
}
function selectScope(lines, uid2) {
  for (const l of lines) {
    if (l.kind !== "archive" || l.explicit) {
      l.selected = !l.blocked && inScope(l, uid2);
    }
  }
}
function closure(lines) {
  const parents = new Map(lines.filter((l) => l.kind === "create" || l.kind === "attrs" && l.vals && l.vals.active).map((l) => [`${l.res}|${l.code}`, l]));
  const skipped = [];
  const dead = (line) => {
    let dep = line.depends_code;
    for (let guard = 0; dep && guard < 20; guard++) {
      const parent = parents.get(`location|${dep}`);
      if (!parent) {
        return null;
      }
      if (parent.blocked) {
        return dep;
      }
      dep = parent.depends_code;
    }
    return null;
  };
  const chosen = [];
  for (const l of lines) {
    if (!l.selected || l.blocked) {
      continue;
    }
    const bad = dead(l);
    if (bad) {
      skipped.push({ code: l.code, reason: `Залежність ${bad} заблокована` });
    } else {
      chosen.push(l);
    }
  }
  const have = new Set(chosen);
  const added = [];
  for (const line of [...chosen]) {
    let dep = line.depends_code;
    for (let guard = 0; dep && guard < 20; guard++) {
      const parent = parents.get(`location|${dep}`);
      if (!parent) {
        break;
      }
      if (!have.has(parent)) {
        have.add(parent);
        chosen.push(parent);
        added.push(parent);
      }
      dep = parent.depends_code;
    }
  }
  return { chosen, added, skipped };
}
function planSummary(lines) {
  const { chosen } = closure(lines);
  const n = (test) => chosen.filter(test).length;
  return {
    create: n((l) => l.kind === "create" && !isRule(l)),
    move: n((l) => l.kind === "move"),
    rename: n((l) => l.kind === "rename"),
    attrs: n((l) => (l.kind === "attrs" || l.kind === "update") && !isRule(l)),
    archive: n((l) => l.kind === "archive" && !isRule(l)),
    rules: n(isRule),
    blocked: lines.filter((l) => l.blocked).length,
    selected: chosen.length
  };
}
var IMPORT_HEADER = ["Назва", "Батьківська локація", "Штрихкод", "Код сцени", "Вид", "Місткість", "Категорія зберігання"];
function planTable(lines, { onlyChanged = false } = {}) {
  const rows = lines.filter((l) => l.res === "location" && ["create", "rename", "attrs"].includes(l.kind) && (!onlyChanged || l.selected) && !l.blocked).map((l) => [l.vals.name ?? l.name ?? l.code, l.vals.parent_name ?? "", l.vals.barcode ?? l.code, l.vals.td_code ?? l.code, l.vals.td_loc_kind ?? "", l.vals.td_capacity ?? "", l.vals.storage_category_name ?? ""]);
  return { header: IMPORT_HEADER, rows };
}
var csvCell = (v) => {
  const s = v == null ? "" : String(v);
  return /[",;\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
};
var toCsv = ({ header, rows }) => [header, ...rows].map((r) => r.map(csvCell).join(",")).join("\n");
var flagLabels = (l) => (l.flags || []).map((f) => FLAG_LABEL[f] || f);
function lineText(l) {
  if (l.changes) {
    return l.changes;
  }
  return Object.entries(l.vals || {}).map(([k, v]) => `${k}: ${l.before && k in l.before ? l.before[k] : "—"} → ${v}`).join("; ");
}

// core/constructor/plan_dialog.js
var MAX_ROWS = 300;
var ex = (list, f) => list.length ? list.slice(0, 3).map(f).join(", ") + (list.length > 3 ? " … " + f(list[list.length - 1]) : "") : "—";
var KIND_CLS = { create: "ok", move: "w", rename: "w", attrs: "w", update: "w", archive: "b" };
function download(name, text, mime) {
  const url = URL.createObjectURL(new Blob([text], { type: mime }));
  const a = h("a", { href: url, download: name });
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1e3);
}
async function openPlanDialog({ adapter, onClose } = {}) {
  adapter ||= E.adapter;
  let plan;
  try {
    plan = await adapter.planPreview();
  } catch (e) {
    toast(e.message || "Не вдалося побудувати план публікації.", "err");
    return void 0;
  }
  const { lines } = plan;
  const st = { view: "all", scope: "" };
  const first = plan.first;
  const blocks = plan.issues.filter((i) => i.severity === "block");
  const warns = plan.issues.filter((i) => i.severity === "warn");
  const note = h("textarea", { placeholder: "Що змінено в цій версії (необов’язково)", "aria-label": "Нотатка" });
  const copyAck = h("input", { type: "checkbox", "aria-label": "Більше не нагадувати" });
  const chips = h("div", { class: "frow", style: { flexWrap: "wrap", gap: "6px" } });
  const table = h("div", { class: "plan-lines", style: { maxHeight: "42vh", overflow: "auto", border: "1px solid var(--line, #ccd)", borderRadius: "6px" } });
  const sum = h("div", { class: "small muted", "data-role": "plan-sum" });
  const summaryBox = h("div", { class: "fcol" });
  let confirmBtn = null;
  const countOf = (test) => lines.filter(test);
  const renderSummary = () => {
    const created = countOf((l) => l.kind === "create" && l.res === "location");
    const eq = countOf((l) => l.kind === "create" && (l.res === "equipment" || l.res === "workcenter"));
    const changed = countOf((l) => ["move", "rename", "attrs", "update"].includes(l.kind) && l.res !== "replenish" && l.res !== "putaway");
    const removed = countOf((l) => l.kind === "archive" && l.res !== "replenish" && l.res !== "putaway");
    const rules = countOf((l) => l.res === "replenish" || l.res === "putaway");
    const row = (n, t, x) => h("div", { class: "sumrow" }, h("div", { class: "n" }, fmtInt(n)), h("div", null, h("div", null, t), h("div", { class: "x" }, x)));
    summaryBox.replaceChildren(
      ...K(
        h("div", { class: "lbl" }, "Буде створено в Odoo" + (first ? " (перша публікація площадки)" : "")),
        row(created.length, "місць зберігання (td_code, штрихкод, місткість, категорія)", ex(created, (l) => l.code)),
        row(eq.length, "одиниць обладнання / робочих центрів", ex(eq, (l) => l.code || l.name)),
        row(changed.length, "змінено", `перенесень ${countOf((l) => l.kind === "move").length} · перейменувань ${countOf((l) => l.kind === "rename").length} · атрибутів і обладнання ${countOf((l) => l.kind === "attrs" || l.kind === "update" && l.res !== "putaway" && l.res !== "replenish").length}`),
        row(removed.length, "видалено в чернетці (пропозиції архівації; нічого не видаляється)", `місць ${removed.filter((l) => l.res === "location").length} · обладнання ${removed.filter((l) => l.res !== "location").length}`),
        rules.length ? row(rules.length, "правил поповнення й розміщення", ex(rules, (l) => l.name)) : null
      )
    );
  };
  const renderChips2 = () => {
    const counts = viewCounts(lines);
    chips.replaceChildren(
      ...VIEWS.filter((v) => v.id === "all" || counts[v.id]).map(
        (v) => h("button", { class: "fbtn sm" + (st.view === v.id ? " primary" : ""), type: "button", "data-view": v.id, "aria-pressed": String(st.view === v.id), onclick: () => {
          st.view = v.id;
          refresh();
        } }, `${v.label} · ${fmtInt(counts[v.id])}`)
      )
    );
  };
  const lineRow = (l) => h(
    "div",
    { class: "plan-row", "data-code": l.code, style: { display: "grid", gridTemplateColumns: "28px 110px 150px 1fr 1.4fr", gap: "8px", padding: "3px 8px", alignItems: "center", borderBottom: "1px solid var(--line, #e3e6ee)", opacity: l.blocked ? 0.65 : 1 } },
    h("input", {
      type: "checkbox",
      checked: !!l.selected && !l.blocked,
      disabled: !!l.blocked,
      "aria-label": `Застосувати ${l.code}`,
      onchange: (e) => {
        l.selected = e.target.checked;
        refreshSummary();
      }
    }),
    h("span", { class: "fbadge " + (KIND_CLS[l.kind] || "") }, KIND_LABEL[l.kind] || l.kind),
    h("span", { class: "small" }, RES_LABEL[l.res] || l.res),
    h("span", { style: { fontFamily: "monospace", overflowWrap: "anywhere" } }, l.code, l.depends_code ? h("span", { class: "small muted" }, ` ← ${l.depends_code}`) : null),
    h("span", { class: "small" }, lineText(l), l.blocked ? h("span", { class: "fbadge b", style: { marginLeft: "6px" } }, l.blocked_reason || "застосувати не можна") : flagLabels(l).map((f) => h("span", { class: "fbadge w", style: { marginLeft: "6px" } }, f)))
  );
  const renderTable = () => {
    const shown = filterLines(lines, st.view, st.scope);
    table.replaceChildren(
      ...K(
        shown.length ? shown.slice(0, MAX_ROWS).map(lineRow) : h("div", { class: "note", style: { margin: "8px" } }, "У цьому виді немає рядків."),
        shown.length > MAX_ROWS ? h("div", { class: "small muted", style: { padding: "6px 8px" } }, `… ще ${shown.length - MAX_ROWS} (фільтр за зоною чи видом звузить список)`) : null
      )
    );
  };
  const refreshSummary = () => {
    const s = planSummary(lines);
    const { added, skipped } = closure(lines);
    sum.textContent = `Буде застосовано: ${fmtInt(s.selected)} (створити ${fmtInt(s.create)}, перенести ${fmtInt(s.move)}, перейменувати ${fmtInt(s.rename)}, атрибути ${fmtInt(s.attrs)}, архів ${fmtInt(s.archive)}, правила ${fmtInt(s.rules)})` + (added.length ? ` · батьки додано автоматично: ${added.map((l) => l.code).join(", ")}` : "") + (skipped.length ? ` · пропущено через заблоковану залежність: ${skipped.map((x) => x.code).join(", ")}` : "") + (s.blocked ? ` · застосувати не можна: ${s.blocked}` : "");
    if (confirmBtn) {
      confirmBtn.disabled = !!blocks.length || !s.selected && !(plan.draftChanges > 0);
    }
  };
  const refresh = () => {
    renderChips2();
    renderTable();
    refreshSummary();
  };
  const scopeSel = plan.scopes && plan.scopes.length ? selectEl([["", "Усі зони й ряди"], ...plan.scopes.map((s) => [s.uid, `${s.name} (${s.n})`])], st.scope, (v) => {
    st.scope = v;
    refresh();
  }, false, "Зона або ряд") : null;
  const toolbar = h(
    "div",
    { class: "frow", style: { gap: "6px", flexWrap: "wrap", alignItems: "center" } },
    scopeSel ? fld("Зона або ряд", scopeSel) : null,
    scopeSel ? h("button", { class: "fbtn sm", type: "button", id: "planScopeOnly", onclick: () => {
      if (st.scope) {
        selectScope(lines, st.scope);
        refresh();
      }
    } }, "Лише обране") : null,
    h("button", { class: "fbtn sm", type: "button", id: "planSelectAll", onclick: () => {
      selectAll(lines, true);
      refresh();
    } }, "Вибрати все"),
    h("button", { class: "fbtn sm", type: "button", id: "planSelectNone", onclick: () => {
      selectAll(lines, false);
      refresh();
    } }, "Зняти все")
  );
  renderSummary();
  refresh();
  const nextN = S.versions.reduce((a, v) => Math.max(a, v.n), 0) + 1;
  const imitation = adapter.kind !== "odoo";
  return await new Promise((resolve) => {
    const dlg = openDialog({
      title: "Публікація версії " + nextN,
      cls: "wide",
      body: h(
        "div",
        { class: "fcol" },
        imitation ? h("div", { class: "note" }, "Це імітація: записи в Odoo не створюються. Підтвердження зберігає нову версію макета й оновлює «стан Odoo» прототипу (журнал і відкат — «Журнал публікацій»).") : null,
        summaryBox,
        blocks.length ? h("div", { class: "note lock", "data-role": "plan-blocks" }, `Публікацію заборонено: зауваження зі статусом «Заборона» (${blocks.length}): ${blocks.slice(0, 3).map((i) => i.message).join("; ")}${blocks.length > 3 ? " …" : ""}`) : null,
        warns.length ? h("div", { class: "small muted" }, `Попередження перевірок: ${warns.length}. Публікацію дозволено.`) : null,
        plan.copyReminder ? h("label", { class: "note", style: { display: "flex", gap: "8px", alignItems: "center" } }, copyAck, "Перше застосування: спершу виконайте його на копії бази Odoo. Більше не нагадувати.") : null,
        chips,
        toolbar,
        table,
        sum,
        total0(plan) ? h("div", { class: "note lock" }, "З моменту останньої версії змін немає.") : null,
        fld("Нотатка до версії", note)
      ),
      actions: [
        { label: "Файл для імпорту (CSV)", id: "planCsv", onClick: () => {
          download("plan_import.csv", toCsv(planTable(lines, { onlyChanged: true })), "text/csv;charset=utf-8");
          return false;
        } },
        { label: "Скасувати" },
        {
          label: "Підтвердити й опублікувати",
          cls: "primary",
          id: "planConfirm",
          onClick: async () => {
            try {
              const res = await adapter.planApply({ lines, note: note.value.trim(), copyAck: copyAck.checked });
              toast(`Версію ${res.version.n} опубліковано` + (imitation ? " (імітація: записи Odoo не створено)." : "."));
              if (res.skipped && res.skipped.length) {
                toast(`Пропущено рядків із заблокованою залежністю: ${res.skipped.length}`, "warn");
              }
            } catch (e) {
              toast(e.message || "Публікація не вдалася.", "err");
              return false;
            }
            return void 0;
          }
        }
      ],
      onClose: async () => {
        if (onClose) {
          await onClose();
        }
        resolve();
      }
    });
    confirmBtn = dlg.querySelector("#planConfirm");
    refreshSummary();
  });
}
var total0 = (plan) => !plan.first && !plan.lines.length && !(plan.draftChanges > 0);
var countText = (c) => ["create", "move", "rename", "attrs", "archive"].filter((k) => c[k]).map((k) => `${OP_LABEL[k]} ${c[k]}`).join(" · ") || "без змін";
function fmtVal(v) {
  if (v == null) {
    return "—";
  }
  return typeof v === "object" ? JSON.stringify(v) : String(v);
}
async function openJournal({ adapter } = {}) {
  adapter ||= E.adapter;
  const box = h("div", { class: "fcol", "data-role": "journal" });
  const opened = /* @__PURE__ */ new Set();
  const load = async () => {
    let res;
    try {
      res = await adapter.planLog();
    } catch (e) {
      box.replaceChildren(h("div", { class: "note lock" }, e.message || "Журнал недоступний."));
      return;
    }
    const rows = [];
    for (const v of res.versions) {
      const ops = opened.has(v.n) ? await adapter.planOps(v.id) : null;
      rows.push(
        h(
          "div",
          { class: "jrow", "data-version": v.n, style: { padding: "8px 0", borderBottom: "1px solid var(--line, #e3e6ee)" } },
          h(
            "div",
            { class: "frow", style: { gap: "8px", alignItems: "center", flexWrap: "wrap" } },
            h("b", null, "v" + v.n),
            h("span", { class: "small muted" }, `${fmtDate(v.published_at)} · ${v.by || "—"}`),
            v.rolled_back ? h("span", { class: "fbadge b" }, "відкочено") : v.ops ? h("span", { class: "fbadge ok" }, `${v.ops} операцій`) : h("span", { class: "fbadge" }, "без операцій в Odoo"),
            h("span", { style: { flex: 1 } }),
            v.ops ? h("button", { class: "fbtn sm", type: "button", "data-act": "ops", onclick: async () => {
              opened.has(v.n) ? opened.delete(v.n) : opened.add(v.n);
              await load();
            } }, opened.has(v.n) ? "Сховати операції" : "Операції") : null,
            canManage() && can("rollback") && !v.rolled_back && v.ops ? h("button", { class: "fbtn sm", type: "button", "data-act": "rollback", disabled: !v.can_rollback, title: v.can_rollback ? "Повернути Odoo до стану перед цією публікацією" : v.reason, onclick: () => rollbackAsk(v) }, "Відкотити") : null
          ),
          v.note ? h("div", { class: "small" }, v.note) : null,
          h("div", { class: "small muted" }, countText(v.counts)),
          !v.can_rollback && !v.rolled_back && v.ops && v.reason ? h("div", { class: "small", style: { color: "var(--warn, #b45309)" } }, "Відкат недоступний: " + v.reason) : null,
          v.rolled_back ? h("div", { class: "small muted" }, `Відкотив ${v.rolled_back_by || "—"} · ${fmtDate(v.rolled_back_at)}`) : null,
          ops ? h(
            "div",
            { class: "small", style: { maxHeight: "28vh", overflow: "auto", marginTop: "6px", fontFamily: "monospace" } },
            ops.slice(0, 300).map((o) => h("div", { style: { opacity: o.rolled_back ? 0.55 : 1 } }, `${o.seq}. ${OP_LABEL[o.op] || o.op} · ${RES_LABEL[o.res] || o.res} · ${o.code}`, o.op !== "create" ? h("span", { class: "muted" }, `  ${fmtVal(o.before)} → ${fmtVal(o.after)}`) : null)),
            ops.length > 300 ? h("div", { class: "muted" }, `… ще ${ops.length - 300}`) : null
          ) : null
        )
      );
    }
    box.replaceChildren(...K(rows.length ? rows : h("div", { class: "note" }, "Публікацій ще не було.")));
  };
  const rollbackAsk = async (v) => {
    const ok = await E.confirmBox({
      title: "Відкотити публікацію v" + v.n + "?",
      text: "В Odoo буде повернуто стан до цієї публікації: створене піде в архів, значення полів повернуться, архівне відновиться. Чернетка не змінюється — наступний план знову запропонує зміни.",
      ok: "Відкотити"
    });
    if (!ok) {
      return;
    }
    try {
      const res = await adapter.rollback(v.id);
      toast(`Відкочено операцій: ${res.reverted}. Чернетка не змінена.`);
      await load();
      if (E.reload) {
        await E.reload();
      }
    } catch (e) {
      toast(e.message || "Відкат не вдався.", "err");
    }
  };
  await load();
  return await new Promise(
    (resolve) => openDialog({ title: "Журнал публікацій", cls: "wide", body: box, actions: [{ label: "Закрити" }], onClose: resolve })
  );
}
registries.dialogs.add("plan", (args, ctx2) => openPlanDialog({ adapter: ctx2?.adapter, ...args || {} }), { force: true });
registries.dialogs.add("planLog", (args, ctx2) => openJournal({ adapter: ctx2?.adapter }), { force: true });
registries.menu.add("planLog", { area: "more", label: "Журнал публікацій", icon: "hist", capability: "rollback", sequence: 60, run: () => E.runDialog("planLog") }, { sequence: 60, force: true });

// core/constructor/capacity_ui.js
var MODE_OPTS2 = [["warn", "Попередження"], ["block", "Заборона"]];
var lib = { loaded: false, loading: null, categories: [], strategies: [], functions: ZONE_FUNCTIONS.map((f) => ({ id: f.key, ...f })), attrs: ZONE_ATTRS.map((a) => ({ id: a.key, ...a })) };
async function loadLib(force = false) {
  const adapter = E.adapter;
  if (!adapter || typeof adapter.categories !== "function" || !can("storage")) {
    lib.loaded = true;
    return lib;
  }
  if (lib.loaded && !force) {
    return lib;
  }
  lib.loading ||= adapter.categories({ op: "list" }).then((res) => {
    Object.assign(lib, { categories: res.categories || [], strategies: res.strategies || [], functions: (res.functions || lib.functions).map((f) => ({ ...f })), attrs: (res.attrs || lib.attrs).map((a) => ({ ...a })) });
  }).catch((e) => console.warn("Категорії зберігання недоступні:", e.message || e)).finally(() => {
    lib.loaded = true;
    lib.loading = null;
  });
  await lib.loading;
  return lib;
}
function ensureLib() {
  if (!lib.loaded && !lib.loading) {
    loadLib().then(() => E.renderRight && E.renderRight());
  }
}
var categoryOf = (id) => lib.categories.find((c) => String(c.id) === String(id)) || null;
var strategyName = (id) => (lib.strategies.find((s) => String(s.id) === String(id)) || {}).name || "";
var functionOf = (id) => lib.functions.find((f) => String(f.id) === String(id)) || null;
function rerunLive() {
  if (!S.site) {
    return;
  }
  S.issues = runLive();
  E.renderChips && E.renderChips();
  E.updateVisual && E.updateVisual();
  E.renderChecksBlock && E.renderChecksBlock();
}
var allCodes = () => S.slots.flatMap((s) => cellsAbs(s).map((c) => c.code));
var sigCodes = "";
async function refreshCaches(what = ["loads", "fit", "codes"]) {
  const a = E.adapter;
  if (!a || !S.site) {
    return;
  }
  try {
    if (what.includes("loads") && typeof a.stockLoads === "function" && can("storage")) {
      const r = await a.stockLoads();
      cache2.loads = r.loads || {};
      cache2.limits = r.limits || {};
      cache2.demo = !!r.demo;
    }
    if (what.includes("fit") && typeof a.putawayFit === "function" && can("putaway")) {
      cache2.fit = rulesState().putaway.length ? (await a.putawayFit()).rules || {} : {};
    }
    if (what.includes("codes") && typeof a.codesCheck === "function") {
      const codes = allCodes();
      const sig = codes.length + ":" + codes.slice(0, 50).join(",") + ":" + codes.slice(-50).join(",");
      if (sig !== sigCodes) {
        sigCodes = sig;
        cache2.codes = {};
        for (let i = 0; i < codes.length; i += 4e3) {
          Object.assign(cache2.codes, (await a.codesCheck(codes.slice(i, i + 4e3))).codes || {});
        }
      }
    }
  } catch (e) {
    console.warn("Кеш перевірок ємності:", e);
    return;
  }
  rerunLive();
}
var scheduleCaches = debounce((what) => refreshCaches(what), 900);
function lazyRefresh() {
  const on = (k) => !!(S.settings.checks[k] && S.settings.checks[k].enabled);
  const what = [on("cell_load") ? "loads" : null, on("putaway_fit") ? "fit" : null, on("code_conflict") ? "codes" : null].filter(Boolean);
  if (S.site && what.length) {
    scheduleCaches(what);
  }
}
function lookupField({ kind, id, label, placeholder, onPick, dis }) {
  const adapter = E.adapter;
  const input = h("input", { type: "text", value: id != null ? nameOf(kind, id) : "", placeholder: placeholder || "Почніть вводити назву", "aria-label": label, disabled: dis, "data-lookup": kind, autocomplete: "off" });
  const list = h("div", { class: "lookup", style: { display: "flex", flexDirection: "column", gap: "2px", maxHeight: "160px", overflow: "auto" } });
  const search = async () => {
    if (typeof adapter.lookup !== "function") {
      return;
    }
    const rows = await adapter.lookup(kind, input.value);
    list.replaceChildren(
      ...rows.map(
        (r) => h("button", { class: "fbtn sm", type: "button", style: { textAlign: "left" }, onclick: () => {
          rememberName(kind, r.id, r.name);
          input.value = r.name;
          list.replaceChildren();
          onPick(r);
        } }, r.name)
      )
    );
  };
  const delayed = debounce(search, 250);
  input.addEventListener("input", () => {
    if (!input.value.trim()) {
      list.replaceChildren();
      onPick(null);
      return;
    }
    delayed();
  });
  input.addEventListener("focus", () => !input.value && search());
  return h("div", { class: "fcol" }, input, list);
}
function renderSlotBlock(root, { rec }) {
  if (!rec || rec.template === "machine_spot") {
    return;
  }
  const isZone = rec.template === "zone";
  const cells = isZone ? [] : cellsAbs(rec, (layerOf(rec.layer_id) || {}).elevation || 0);
  if (!isZone && !cells.length) {
    return;
  }
  ensureLib();
  lazyRefresh();
  const ly = layerOf(rec.layer_id);
  const dis = !canEditLayer(ly) || !!rec.locked;
  const zones = zonesOf();
  const home = isZone ? zoneChainAt(zones, rec.x, rec.y).filter((z) => z !== rec) : zoneChainAt(zones, rec.x, rec.y);
  const cat = inheritedField(rec, "storage_category_id", home);
  const strat = inheritedField(rec, "removal_strategy_id", home);
  const edit = (fn2) => (v) => {
    E.beginEdit("slot", rec);
    fn2(v);
    E.liveEdit();
    E.endEdit();
  };
  const catOpts = [["", cat.from === "zone" ? `— як у зони: ${(categoryOf(cat.value) || {}).name || "…"} —` : "— без категорії —"], ...lib.categories.map((c) => [c.id, c.name])];
  const stratOpts = [["", strat.from === "zone" ? `— як у зони: ${strategyName(strat.value) || "…"} —` : "— як в Odoo —"], ...lib.strategies.map((s) => [s.id, s.name])];
  const conv = (v) => v === "" ? null : isNaN(Number(v)) ? v : Number(v);
  const fn = functionOf(rec.function_id);
  const first = cells[0];
  const info = first ? cellLimit(rec, first, categoryOf(cat.value)) : null;
  const sumScope = isZone ? capacitySummary(S.slots.filter((s) => s !== rec), { loads: Object.keys(cache2.loads).length || cache2.demo ? cache2.loads : null, categories: lib.categories, zone: rec }) : capacitySummary([rec], { loads: Object.keys(cache2.loads).length || cache2.demo ? cache2.loads : null, categories: lib.categories });
  root.append(
    ...K(
      h(
        "div",
        { class: "sec", id: "capacityBlock" },
        h("h3", null, "Зберігання й ємність"),
        h(
          "div",
          { class: "fcol" },
          isZone ? [
            fld("Функція зони", selectEl([["", "— не задано —"], ...lib.functions.map((f) => [f.id, f.name])], rec.function_id ?? "", (v) => {
              edit((x) => {
                rec.function_id = conv(x);
                const f = functionOf(rec.function_id);
                if (f && f.color) {
                  rec.params.color = f.color;
                }
              })(v);
              E.renderRight();
            }, dis, "Функція зони")),
            // колір рамки зони — колір функції
            fn && fn.color ? h("div", { class: "small", style: { display: "flex", alignItems: "center", gap: "6px" } }, h("span", { style: { width: "14px", height: "14px", background: fn.color, display: "inline-block", borderRadius: "3px" } }), "Колір рамки й підпису зони: " + fn.name) : null,
            h("div", { class: "lbl" }, "Атрибути зони (лише в проєкті)"),
            h("div", { class: "checks" }, lib.attrs.map((a) => {
              const on = (rec.attr_ids || []).some((x) => String(x) === String(a.id));
              const cb = h("input", { type: "checkbox", checked: on, disabled: dis, "aria-label": a.name, "data-attr": a.key || a.id });
              cb.addEventListener("change", () => {
                edit(() => {
                  const cur = new Set(rec.attr_ids || []);
                  cb.checked ? cur.add(a.id) : cur.delete(a.id);
                  rec.attr_ids = [...cur];
                })();
                E.renderRight();
              });
              return h("label", null, cb, a.name);
            })),
            (rec.attr_ids || []).some((x) => (lib.attrs.find((a) => String(a.id) === String(x)) || {}).key === "temp" || x === "temp") ? h("div", { class: "grid2" }, fld("Температура від", numInput({ value: rec.temp_min_c ?? 0, dis, step: 1, label: "Температура від", set: (v) => {
              E.beginEdit("slot", rec);
              rec.temp_min_c = v;
              E.liveEdit();
              E.endEdit();
            } }), "°C"), fld("до", numInput({ value: rec.temp_max_c ?? 0, dis, step: 1, label: "Температура до", set: (v) => {
              E.beginEdit("slot", rec);
              rec.temp_max_c = v;
              E.liveEdit();
              E.endEdit();
            } }), "°C")) : null
          ] : null,
          fld("Категорія зберігання", selectEl(catOpts, rec.storage_category_id ?? "", edit((v) => {
            rec.storage_category_id = conv(v);
          }), dis || !can("storage"), "Категорія зберігання")),
          cat.value ? h("div", { class: "small muted" }, categoryLine(categoryOf(cat.value))) : null,
          fld("Стратегія списання", selectEl(stratOpts, rec.removal_strategy_id ?? "", edit((v) => {
            rec.removal_strategy_id = conv(v);
          }), dis || !can("storage"), "Стратегія списання")),
          info ? h("div", { class: "small", "data-role": "cell-limit" }, `Комірка ${first.code}: ${fmt(first.l, 2)}×${fmt(first.w, 2)}×${fmt(first.h, 2)} м · місткість ${fmtInt(first.capacity || 0)} · макс. вага ${info.kg ? fmtInt(info.kg) + " кг (" + info.source + ")" : "не задано"}`) : null,
          h(
            "div",
            { class: "small muted", "data-role": "slot-summary" },
            `${isZone ? "Усередині зони" : "У місці"}: комірок ${fmtInt(sumScope.cells)} · палетомісць ${fmtInt(sumScope.places)} · площа ${fmt(sumScope.area, 1)} м² · об'єм ${fmt(sumScope.volume, 1)} м³ · сума макс. ваги ${fmtInt(sumScope.maxWeight)} кг · з категорією ${fmtInt(sumScope.withCategory)}` + (sumScope.fill != null ? ` · зайнято ${fmtInt(sumScope.occupied)} / вільно ${fmtInt(sumScope.free)} (${fmt(sumScope.fill * 100, 0)}%)${cache2.demo ? " · демо" : ""}` : "")
          ),
          !can("storage") ? h("div", { class: "small muted" }, "Категорії й стратегії в цьому хості недоступні.") : null
        )
      )
    )
  );
}
var categoryLine = (c) => c ? `${c.name}: макс. вага ${c.max_weight ? fmtInt(c.max_weight) + " кг" : "без обмеження"}, ${POLICY_LABEL[c.allow_new_product] || c.allow_new_product}` : "";
registries.panels.add("slot:capacity", { area: "slot", render: renderSlotBlock }, { sequence: 35, force: true });
function renderSiteBlock(root) {
  ensureLib();
  lazyRefresh();
  const loads = Object.keys(cache2.loads).length || cache2.demo ? cache2.loads : null;
  const sum = capacitySummary(S.slots, { loads, categories: lib.categories });
  const rules = rulesState();
  root.append(
    ...K(
      h(
        "div",
        { class: "sec", id: "siteCapacity" },
        h("h3", null, "Ємність площадки"),
        h(
          "div",
          { class: "small", "data-role": "site-summary" },
          `Комірок ${fmtInt(sum.cells)} · палетомісць ${fmtInt(sum.places)} · площа ${fmt(sum.area, 1)} м² · об'єм ${fmt(sum.volume, 1)} м³ · сума макс. ваги ${fmtInt(sum.maxWeight)} кг · з категорією ${fmtInt(sum.withCategory)}` + (sum.fill != null ? ` · зайнято ${fmtInt(sum.occupied)}, вільно ${fmtInt(sum.free)} · заповнення ${fmt(sum.fill * 100, 0)}%${cache2.demo ? " (демо)" : ""}` : "")
        ),
        h(
          "div",
          { class: "frow", style: { flexWrap: "wrap", gap: "6px", marginTop: "6px" } },
          can("storage") ? h("button", { class: "fbtn sm", type: "button", id: "btnCategories", onclick: () => E.runDialog("categories") }, "Категорії зберігання…") : null,
          can("putaway") ? h("button", { class: "fbtn sm", type: "button", id: "btnRules", onclick: () => E.runDialog("rules") }, `Правила розміщення й поповнення (${rules.putaway.filter((r) => !r.deleted).length}/${rules.replenish.filter((r) => !r.deleted).length})…`) : null,
          E.adapter && E.adapter.kind === "artifact" && typeof E.adapter.stockLoads === "function" ? h("button", { class: "fbtn sm", type: "button", id: "btnDemoStock", onclick: async () => {
            E.adapter.demoStock = !E.adapter.demoStock;
            await refreshCaches(["loads"]);
            E.renderRight();
          } }, E.adapter.demoStock ? "Сховати демо-залишки" : "Показати демо-залишки") : null,
          typeof (E.adapter || {}).codesCheck === "function" ? h("button", { class: "fbtn sm", type: "button", id: "btnCheckCodes", title: "Перевірити зайнятість кодів у зовнішній системі", onclick: async () => {
            sigCodes = "";
            await refreshCaches(["codes"]);
            toast("Зайнятість кодів перевірено.");
          } }, "Перевірити коди") : null
        )
      )
    )
  );
}
registries.panels.add("site:capacity", { area: "site", render: renderSiteBlock }, { sequence: 50, force: true });
function renderChecksConfig(root) {
  const dis = !canManage();
  const cfg = S.settings.checks;
  const save2 = (id) => {
    const c = cfg[id];
    const a = E.adapter;
    if (a.kind === "odoo" && c.id == null && typeof a.queue === "function") {
      a.queue({ model: "td.check.config", op: "create", uid: id, vals: { check_key: id, enabled: c.enabled, mode: c.mode, params: c.params || {} } });
      c.id = -1;
    } else {
      a.saveCheck(id, { enabled: c.enabled, mode: c.mode, params: c.params || {} });
    }
    rerunLive();
    if (c.enabled) {
      refreshCaches([{ cell_load: "loads", putaway_fit: "fit", code_conflict: "codes" }[id]]);
    }
  };
  const items = EXTRA_CHECKS.filter((c) => c.id !== "cell_load" || can("storage")).filter((c) => c.id !== "putaway_fit" || can("putaway"));
  if (!items.length) {
    return;
  }
  root.append(
    h(
      "div",
      { class: "sec", id: "capChecks" },
      h("div", { class: "lbl", style: { margin: "6px 0" } }, "Перевірки ємності й правил"),
      dis ? h("div", { class: "note lock" }, "Налаштування змінює Менеджер.") : null,
      items.map((c) => {
        const cur = cfg[c.id] || { enabled: false, mode: c.mode, params: {}, id: null };
        return h(
          "div",
          { class: "frow", style: { margin: "5px 0" }, title: c.hint },
          h("input", { type: "checkbox", checked: !!cur.enabled && !!cfg[c.id], disabled: dis, "aria-label": c.name, "data-check": c.id, onchange: (e) => {
            cfg[c.id] ||= { enabled: false, mode: c.mode, params: {}, id: null };
            cfg[c.id].enabled = e.target.checked;
            save2(c.id);
          } }),
          h("span", { style: { flex: 1, minWidth: 0 } }, c.name),
          selectEl(MODE_OPTS2, cur.mode, (v) => {
            cfg[c.id] ||= { enabled: false, mode: c.mode, params: {}, id: null };
            cfg[c.id].mode = v;
            save2(c.id);
          }, dis, c.name)
        );
      })
    )
  );
}
registries.panels.add("right:capchecks", { area: "right", render: renderChecksConfig }, { sequence: 92, force: true });
async function openCategories() {
  const adapter = E.adapter;
  await loadLib(true);
  const dis = !canManage();
  const body = h("div", { class: "fcol", "data-role": "categories" });
  const draft = { id: null, name: "", max_weight: 0, allow_new_product: "mixed", capacity: [] };
  const form = h("div", { class: "fcol", style: { borderTop: "1px solid var(--line, #e3e6ee)", paddingTop: "8px", marginTop: "8px" } });
  const refresh = async () => {
    await loadLib(true);
    render2();
  };
  const edit = (c) => {
    Object.assign(draft, c ? { id: c.id, name: c.name, max_weight: c.max_weight, allow_new_product: c.allow_new_product, capacity: (c.capacity || []).map((x) => ({ ...x })) } : { id: null, name: "", max_weight: 0, allow_new_product: "mixed", capacity: [] });
    renderForm();
  };
  const save2 = async () => {
    try {
      await adapter.categories({ op: "save", id: draft.id, confirm: true, vals: { name: draft.name, max_weight: draft.max_weight, allow_new_product: draft.allow_new_product, capacity: draft.capacity.map((r) => ({ product_id: r.product_id || null, package_type_id: r.package_type_id || null, quantity: r.quantity })) } });
      toast("Категорію збережено.");
      edit(null);
      await refresh();
      E.renderRight();
    } catch (e) {
      toast(e.message || "Не вдалося зберегти категорію.", "err");
    }
  };
  const del = async (c) => {
    try {
      await adapter.categories({ op: "delete", id: c.id, confirm: true });
      toast("Категорію видалено.");
      await refresh();
    } catch (e) {
      toast(e.message || "Не вдалося видалити.", "err");
    }
  };
  function render2() {
    body.replaceChildren(
      ...K(
        h("div", { class: "note" }, "Категорії зберігання (в Odoo — `stock.storage.category`) змінюються одразу, поза планом публікації. Призначення місцям, рядам і зонам — у блоці «Зберігання й ємність»; діє вниз."),
        lib.categories.length ? lib.categories.map(
          (c) => h(
            "div",
            { class: "frow", "data-cat": c.id, style: { gap: "8px", padding: "4px 0", borderBottom: "1px solid var(--line, #e3e6ee)", alignItems: "center" } },
            h("b", { style: { flex: 1 } }, c.name),
            h("span", { class: "small muted" }, `${c.max_weight ? fmtInt(c.max_weight) + " кг" : "без ліміту"} · ${POLICY_LABEL[c.allow_new_product]} · ємність: ${c.capacity.length} · місць: ${c.locations}`),
            h("button", { class: "fbtn sm", type: "button", disabled: dis, "data-act": "edit", onclick: () => edit(c) }, "Змінити"),
            h("button", { class: "fbtn sm", type: "button", disabled: dis || c.in_use, title: c.in_use ? "Категорію вже використано" : "", "data-act": "delete", onclick: () => del(c) }, "Видалити")
          )
        ) : h("div", { class: "note" }, "Категорій ще немає."),
        dis ? h("div", { class: "note lock" }, "Категорії зберігання змінює Менеджер.") : h("button", { class: "fbtn sm", type: "button", id: "btnNewCategory", onclick: () => edit(null) }, "Нова категорія"),
        form
      )
    );
    renderForm();
  }
  function renderForm() {
    if (dis) {
      form.replaceChildren();
      return;
    }
    form.replaceChildren(
      h("div", { class: "lbl" }, draft.id ? "Зміна категорії" : "Нова категорія"),
      fld("Назва", textInput({ value: draft.name, label: "Назва категорії", set: (v) => {
        draft.name = v;
      } })),
      h(
        "div",
        { class: "grid2" },
        fld("Макс. вага", numInput({ value: draft.max_weight, min: 0, step: 10, label: "Макс. вага", set: (v) => {
          draft.max_weight = v;
        } }), "кг"),
        fld("Політика", selectEl(ALLOW_NEW, draft.allow_new_product, (v) => {
          draft.allow_new_product = v;
        }, false, "Політика"))
      ),
      h("div", { class: "lbl" }, "Ємність за товаром або упаковкою"),
      draft.capacity.map(
        (r, i) => h(
          "div",
          { class: "frow", style: { gap: "6px", alignItems: "flex-start" } },
          r.package_type_id != null || r.kind === "package" ? lookupField({ kind: "package_type", id: r.package_type_id, label: "Упаковка", onPick: (x) => {
            r.package_type_id = x ? x.id : null;
          } }) : lookupField({ kind: "product", id: r.product_id, label: "Товар", onPick: (x) => {
            r.product_id = x ? x.id : null;
          } }),
          numInput({ value: r.quantity, min: 0, step: 1, label: "Кількість", set: (v) => {
            r.quantity = v;
          } }),
          h("button", { class: "fbtn sm", type: "button", "aria-label": "Прибрати рядок ємності", onclick: () => {
            draft.capacity.splice(i, 1);
            renderForm();
          } }, "×")
        )
      ),
      h(
        "div",
        { class: "frow", style: { gap: "6px" } },
        h("button", { class: "fbtn sm", type: "button", onclick: () => {
          draft.capacity.push({ product_id: null, package_type_id: null, quantity: 1 });
          renderForm();
        } }, "+ Товар"),
        h("button", { class: "fbtn sm", type: "button", onclick: () => {
          draft.capacity.push({ product_id: null, package_type_id: -1, kind: "package", quantity: 1 });
          renderForm();
        } }, "+ Упаковка")
      ),
      h("div", { class: "frow", style: { gap: "6px" } }, h("button", { class: "fbtn primary", type: "button", id: "btnSaveCategory", onclick: save2 }, "Зберегти категорію"), draft.id ? h("button", { class: "fbtn", type: "button", onclick: () => edit(null) }, "Скасувати правку") : null)
    );
  }
  render2();
  return await new Promise((resolve) => openDialog({ title: "Категорії зберігання", cls: "wide", body, actions: [{ label: "Закрити" }], onClose: resolve }));
}
registries.dialogs.add("categories", () => openCategories(), { force: true });
registries.menu.add("categories", { area: "more", label: "Категорії зберігання", icon: "tag", capability: "storage", sequence: 55, run: () => E.runDialog("categories") }, { sequence: 55, force: true });

// core/constructor/rules_dialog.js
var canEditRules = () => S.app.mode === "edit" && (S.rights.is_manager || (S.rights.roles || []).length > 0);
var base = { site: null, putaway: /* @__PURE__ */ new Map(), replenish: /* @__PURE__ */ new Map() };
function ensureBase() {
  const r = rulesState();
  if (base.site !== (S.site && S.site.id)) {
    base = { site: S.site && S.site.id, putaway: rulesBase(r.putaway), replenish: rulesBase(r.replenish) };
  }
  return base;
}
var save = () => {
  rerunLive();
  E.scheduleSave && E.scheduleSave();
  refreshCaches(["fit"]);
};
function highlightRule(rule) {
  S.ui.metric = "rule_target";
  S.ui.ruleHighlight = rule ? rule.id : null;
  S.ui.whereCode = null;
  E.syncScene && E.syncScene(true);
  E.requestRender && E.requestRender();
  const codes = rule && rule.out_code ? [rule.out_code] : [];
  const slot = S.slots.find((s) => cellsAbs(s).some((c) => codes.includes(c.code)));
  if (slot && E.focusOn) {
    E.focusOn(slot.x, slot.y);
  }
}
function clearHighlight() {
  if (S.ui.metric === "rule_target") {
    S.ui.metric = null;
  }
  S.ui.ruleHighlight = null;
  S.ui.whereCode = null;
  E.syncScene && E.syncScene(true);
  E.requestRender && E.requestRender();
}
var allCells = () => S.slots.flatMap((s) => cellsAbs(s).map((c) => ({ code: c.code, slot: s })));
function codeField({ value, label, onPick, dis }) {
  const input = h("input", { type: "text", value: value || "", "aria-label": label, disabled: dis, "data-code-input": "1", autocomplete: "off", placeholder: "Код комірки, напр. AA-R1-B01-L1" });
  const list = h("div", { class: "lookup", style: { display: "flex", flexDirection: "column", gap: "2px", maxHeight: "140px", overflow: "auto" } });
  const find = () => {
    const t = input.value.trim().toLowerCase();
    const rows = t ? allCells().filter((c) => c.code.toLowerCase().includes(t)).slice(0, 30) : [];
    list.replaceChildren(...rows.map((c) => h("button", { class: "fbtn sm", type: "button", style: { textAlign: "left" }, onclick: () => {
      input.value = c.code;
      list.replaceChildren();
      onPick(c.code);
    } }, c.code)));
    onPick(input.value.trim());
  };
  input.addEventListener("input", find);
  return h("div", { class: "fcol" }, input, list);
}
async function openPutawayForm(rule, isNew) {
  const adapter = E.adapter;
  await loadLib();
  const d = { ...rule, package_type_ids: [...rule.package_type_ids] };
  const mode = { by: d.category_id && !d.product_id ? "category" : "product" };
  const body = h("div", { class: "fcol", "data-role": "putaway-form" });
  const render2 = () => {
    body.replaceChildren(
      ...K(
        h(
          "div",
          { class: "frow", style: { gap: "10px" } },
          ["product", "category"].map((m) => h("label", null, h("input", { type: "radio", name: "pwby", checked: mode.by === m, onchange: () => {
            mode.by = m;
            if (m === "product") {
              d.category_id = null;
            } else {
              d.product_id = null;
            }
            render2();
          } }), m === "product" ? " Товар" : " Категорія товару"))
        ),
        mode.by === "product" ? fld("Товар", lookupField({ kind: "product", id: d.product_id, label: "Товар", onPick: (r) => {
          d.product_id = r ? r.id : null;
          d.product = r ? r.name : "";
        } })) : fld("Категорія товару", lookupField({ kind: "category", id: d.category_id, label: "Категорія товару", onPick: (r) => {
          d.category_id = r ? r.id : null;
          d.category = r ? r.name : "";
        } })),
        fld("Типи упаковки (необов'язково)", h("div", { class: "fcol" }, d.package_type_ids.length ? h("div", { class: "small" }, d.package_type_ids.map((id) => nameOf("package_type", id)).join(", ")) : null, lookupField({ kind: "package_type", id: null, label: "Тип упаковки", placeholder: "Додати тип упаковки", onPick: (r) => {
          if (r && !d.package_type_ids.includes(r.id)) {
            d.package_type_ids.push(r.id);
            render2();
          }
        } }), d.package_type_ids.length ? h("button", { class: "fbtn sm", type: "button", onclick: () => {
          d.package_type_ids = [];
          render2();
        } }, "Прибрати упаковки") : null)),
        fld("Коли надходить у (необов'язково)", lookupField({ kind: "location", id: d.in_location_id, label: "Коли надходить у", placeholder: "За замовчуванням — склад площадки", onPick: (r) => {
          d.in_location_id = r ? r.id : null;
        } })),
        fld("Покласти в комірку", codeField({ value: d.out_code, label: "Куди покласти", onPick: (code) => {
          d.out_code = code;
        } })),
        h(
          "div",
          { class: "grid2" },
          fld("Шукати всередині", selectEl(SUBLOCATION, d.sublocation, (v) => {
            d.sublocation = v;
            render2();
          }, false, "Шукати всередині")),
          fld("Пріоритет", numInput({ value: d.sequence, step: 1, int: true, label: "Пріоритет", set: (v) => {
            d.sequence = v;
          } }))
        ),
        d.sublocation === "closest_location" ? fld("Категорія зберігання місця", selectEl([["", "— оберіть —"], ...lib.categories.map((c) => [c.id, c.name])], d.storage_category_id ?? "", (v) => {
          d.storage_category_id = v === "" ? null : isNaN(Number(v)) ? v : Number(v);
        }, false, "Категорія зберігання")) : null
      )
    );
  };
  render2();
  return await new Promise(
    (resolve) => openDialog({
      title: isNew ? "Нове правило розміщення" : "Правило розміщення",
      body,
      actions: [
        { label: "Скасувати" },
        {
          label: "Зберегти",
          cls: "primary",
          id: "btnSaveRule",
          onClick: () => {
            if (!d.product_id && !d.category_id) {
              toast("Вкажіть товар або категорію товару.", "warn");
              return false;
            }
            if (!d.out_code) {
              toast("Вкажіть комірку призначення.", "warn");
              return false;
            }
            if (d.sublocation === "closest_location" && !d.storage_category_id) {
              toast("Для «місце з категорією зберігання» оберіть категорію.", "warn");
              return false;
            }
            if (d.sublocation !== "closest_location") {
              d.storage_category_id = null;
            }
            Object.assign(rule, d);
            if (isNew) {
              rulesState().putaway.push(rule);
            }
            save();
            resolve(true);
            return void 0;
          }
        }
      ],
      onClose: () => resolve(false)
    })
  );
}
async function openReplenishForm(rule, isNew) {
  const d = { ...rule };
  const body = h(
    "div",
    { class: "fcol", "data-role": "replenish-form" },
    fld("Товар", lookupField({ kind: "product", id: d.product_id, label: "Товар", onPick: (r) => {
      d.product_id = r ? r.id : null;
      d.product = r ? r.name : "";
    } })),
    fld("Комірка", codeField({ value: d.cell_code, label: "Комірка", onPick: (code) => {
      d.cell_code = code;
    } })),
    h("div", { class: "grid2" }, fld("Мінімум", numInput({ value: d.min_qty, min: 0, step: 1, label: "Мінімум", set: (v) => {
      d.min_qty = v;
    } })), fld("Максимум", numInput({ value: d.max_qty, min: 0, step: 1, label: "Максимум", set: (v) => {
      d.max_qty = v;
    } }))),
    h("div", { class: "small muted" }, "Правило можливе для комірки із залишком або з уже наявним правилом; у Odoo воно потрапить публікацією.")
  );
  return await new Promise(
    (resolve) => openDialog({
      title: isNew ? "Нове правило поповнення" : "Правило поповнення",
      body,
      actions: [
        { label: "Скасувати" },
        {
          label: "Зберегти",
          cls: "primary",
          id: "btnSaveRule",
          onClick: () => {
            if (!d.product_id || !d.cell_code) {
              toast("Вкажіть товар і комірку.", "warn");
              return false;
            }
            if (d.max_qty < d.min_qty) {
              toast("Максимум не може бути меншим за мінімум.", "warn");
              return false;
            }
            Object.assign(rule, d);
            if (isNew) {
              rulesState().replenish.push(rule);
            }
            save();
            resolve(true);
            return void 0;
          }
        }
      ],
      onClose: () => resolve(false)
    })
  );
}
async function prefetchNames(adapter) {
  const rules = rulesState();
  const need = { category: /* @__PURE__ */ new Set(), package_type: /* @__PURE__ */ new Set(), location: /* @__PURE__ */ new Set(), product: /* @__PURE__ */ new Set() };
  for (const r of rules.putaway) {
    r.category_id != null && need.category.add(r.category_id);
    r.package_type_ids.forEach((id) => need.package_type.add(id));
    [r.in_location_id, r.out_location_id].forEach((id) => id != null && need.location.add(id));
  }
  for (const r of rules.replenish) {
    r.location_id != null && need.location.add(r.location_id);
  }
  if (typeof adapter.lookup !== "function") {
    return;
  }
  for (const [kind, ids] of Object.entries(need)) {
    const missing = [...ids].filter((id) => nameOf(kind, id).startsWith("#"));
    if (missing.length) {
      try {
        (await adapter.lookup(kind, "", missing)).forEach((r) => rememberName(kind, r.id, r.name));
      } catch (e) {
        console.warn("Назви правил недоступні:", e.message || e);
      }
    }
  }
}
async function openRules({ tab = "putaway" } = {}) {
  const adapter = E.adapter;
  await loadLib();
  await prefetchNames(adapter);
  await refreshCaches(["fit"]);
  const st = { tab };
  const body = h("div", { class: "fcol", "data-role": "rules" });
  const dis = !canEditRules();
  const rules = rulesState();
  const bs = ensureBase();
  const chip = (status) => status ? h("span", { class: "fbadge " + (status === "deleted" ? "b" : status === "changed" ? "w" : "ok"), "data-status": status }, STATUS_LABEL[status]) : null;
  const remove = (list, rule) => {
    if (rule[list === rules.putaway ? "odoo_rule_id" : "odoo_orderpoint_id"]) {
      rule.deleted = true;
    } else {
      list.splice(list.indexOf(rule), 1);
    }
    save();
    render2();
  };
  const restore = (rule) => {
    rule.deleted = false;
    save();
    render2();
  };
  const putawayRows = () => {
    const sorted = [...rules.putaway].sort((a, b) => a.sequence - b.sequence);
    if (!sorted.length) {
      return h("div", { class: "note" }, "Правил розміщення ще немає.");
    }
    return sorted.map((r) => {
      const status = ruleStatus(r, bs.putaway, "odoo_rule_id");
      const fit = cache2.fit[r.id] || [];
      return h(
        "div",
        { class: "rule-row", "data-rule": r.id, style: { display: "grid", gridTemplateColumns: "1fr 1fr auto", gap: "8px", padding: "6px 0", borderBottom: "1px solid var(--line, #e3e6ee)", opacity: r.deleted ? 0.6 : 1, alignItems: "center" } },
        h("div", null, h("b", null, ruleLabel(r)), " ", chip(status), r.package_type_ids.length ? h("div", { class: "small muted" }, "упаковка: " + r.package_type_ids.map((id) => nameOf("package_type", id)).join(", ")) : null, h("div", { class: "small muted" }, `пріоритет ${r.sequence} · коли надходить у: ${r.in_location_id ? nameOf("location", r.in_location_id) : "склад площадки"}`)),
        h("div", { class: "small" }, "→ ", h("b", null, r.out_code || "—"), r.sublocation !== "no" ? h("span", { class: "muted" }, ` · шукати: ${SUBLOCATION_LABEL[r.sublocation]}${r.storage_category_id ? " (" + ((categoryOf(r.storage_category_id) || {}).name || "категорія") + ")" : ""}`) : null, fit.length ? h("div", { class: "small", style: { color: "var(--warn, #b45309)" }, "data-role": "fit-warn" }, "Правило: не вміститься — " + fit.map((f) => f.reason).join("; ")) : null),
        h(
          "div",
          { class: "frow", style: { gap: "4px" } },
          h("button", { class: "fbtn sm", type: "button", "data-act": "highlight", onclick: () => {
            highlightRule(r);
            toast("Ціль правила підсвічено.");
            render2();
          }, disabled: !r.out_code }, "Підсвітити"),
          r.deleted ? h("button", { class: "fbtn sm", type: "button", "data-act": "restore", disabled: dis, onclick: () => restore(r) }, "Повернути") : [h("button", { class: "fbtn sm", type: "button", "data-act": "edit", disabled: dis, onclick: async () => {
            if (await openPutawayForm(r, false)) {
              render2();
            }
          } }, "Змінити"), h("button", { class: "fbtn sm", type: "button", "data-act": "delete", disabled: dis, onclick: () => remove(rules.putaway, r) }, "Видалити")]
        )
      );
    });
  };
  const replenishRows = () => {
    if (!rules.replenish.length) {
      return h("div", { class: "note" }, "Правил поповнення ще немає.");
    }
    return rules.replenish.map((r) => {
      const status = ruleStatus(r, bs.replenish, "odoo_orderpoint_id");
      return h(
        "div",
        { class: "rule-row", "data-rule": r.id, style: { display: "grid", gridTemplateColumns: "1fr 1fr auto", gap: "8px", padding: "6px 0", borderBottom: "1px solid var(--line, #e3e6ee)", opacity: r.deleted ? 0.6 : 1, alignItems: "center" } },
        h("div", null, h("b", null, r.product || nameOf("product", r.product_id)), " ", chip(status)),
        h("div", { class: "small" }, `${r.cell_code || "—"} · мін ${fmt(r.min_qty, 0)} / макс ${fmt(r.max_qty, 0)}`),
        h(
          "div",
          { class: "frow", style: { gap: "4px" } },
          r.deleted ? h("button", { class: "fbtn sm", type: "button", "data-act": "restore", disabled: dis, onclick: () => restore(r) }, "Повернути") : [h("button", { class: "fbtn sm", type: "button", "data-act": "edit", disabled: dis, onclick: async () => {
            if (await openReplenishForm(r, false)) {
              render2();
            }
          } }, "Змінити"), h("button", { class: "fbtn sm", type: "button", "data-act": "delete", disabled: dis, onclick: () => remove(rules.replenish, r) }, "Видалити")]
        )
      );
    });
  };
  function render2() {
    body.replaceChildren(
      ...K(
        h("div", { class: "note" }, "Правила змінюються в чернетці й потрапляють у зовнішню систему лише публікацією (вид «Правила» у плані); видалення — архів, відкат повертає."),
        h(
          "div",
          { class: "frow", style: { gap: "6px" } },
          h("button", { class: "fbtn sm" + (st.tab === "putaway" ? " primary" : ""), type: "button", "data-tab": "putaway", onclick: () => {
            st.tab = "putaway";
            render2();
          } }, `Розміщення · ${rules.putaway.filter((r) => !r.deleted).length}`),
          h("button", { class: "fbtn sm" + (st.tab === "replenish" ? " primary" : ""), type: "button", "data-tab": "replenish", onclick: () => {
            st.tab = "replenish";
            render2();
          } }, `Поповнення min/max · ${rules.replenish.filter((r) => !r.deleted).length}`),
          h("span", { style: { flex: 1 } }),
          S.ui.metric === "rule_target" ? h("button", { class: "fbtn sm", type: "button", id: "btnClearHighlight", onclick: () => {
            clearHighlight();
            render2();
          } }, "Зняти підсвітку") : null
        ),
        st.tab === "putaway" ? putawayRows() : replenishRows(),
        dis ? h("div", { class: "note lock" }, "Правила пише проєктувальник або менеджер у режимі редагування.") : h("button", { class: "fbtn sm", type: "button", id: "btnNewRule", onclick: async () => {
          const ok = st.tab === "putaway" ? await openPutawayForm(newPutawayRule(), true) : await openReplenishForm(newReplenishRule(), true);
          if (ok) {
            render2();
          }
        } }, st.tab === "putaway" ? "Нове правило розміщення" : "Нове правило поповнення"),
        st.tab === "putaway" && can("putaway") ? whereBox() : null
      )
    );
  }
  function whereBox() {
    const q = { product_id: null, package_type_id: null, quantity: 1 };
    const out = h("div", { class: "small", "data-role": "where-result" });
    return h(
      "div",
      { class: "fcol", style: { borderTop: "1px solid var(--line, #e3e6ee)", paddingTop: "8px", marginTop: "8px" } },
      h("div", { class: "lbl" }, "Куди покладе Odoo?"),
      h("div", { class: "grid2" }, fld("Товар", lookupField({ kind: "product", id: null, label: "Товар для підбору місця", onPick: (r) => {
        q.product_id = r ? r.id : null;
      } })), fld("Кількість", numInput({ value: 1, min: 0, step: 1, label: "Кількість", set: (v) => {
        q.quantity = v;
      } }))),
      fld("Упаковка (необов'язково)", lookupField({ kind: "package_type", id: null, label: "Упаковка", onPick: (r) => {
        q.package_type_id = r ? r.id : null;
      } })),
      h("button", { class: "fbtn sm", type: "button", id: "btnWhere", onclick: async () => {
        if (!q.product_id) {
          toast("Оберіть товар.", "warn");
          return;
        }
        try {
          const res = await adapter.putawayWhere({ ...q });
          const code = res.location && res.location.code || "";
          out.textContent = res.moved ? `Odoo покладе в ${code || res.location.name}${res.estimate ? " (оцінка за застосованими правилами)" : ""}.` : `Застосованих правил немає: товар лишається на місці приймання${res.estimate ? " (оцінка)" : ""}.`;
          if (code) {
            S.ui.metric = "rule_target";
            S.ui.ruleHighlight = null;
            S.ui.whereCode = code;
            E.syncScene && E.syncScene(true);
          }
        } catch (e) {
          toast(e.message || "Не вдалося визначити місце.", "err");
        }
      } }, "Показати місце"),
      out
    );
  }
  render2();
  return await new Promise((resolve) => openDialog({ title: "Правила розміщення й поповнення", cls: "wide", body, actions: [{ label: "Закрити" }], onClose: resolve }));
}
registries.dialogs.add("rules", (args) => openRules(args || {}), { force: true });
registries.menu.add("rules", { area: "more", label: "Правила розміщення", icon: "tag", capability: "putaway", sequence: 54, run: () => E.runDialog("rules") }, { sequence: 54, force: true });
function renderRulesInto(root, { rec }) {
  if (!rec || rec.template === "machine_spot" || !can("putaway")) {
    return;
  }
  const rules = rulesState();
  const zones = zonesOf();
  let hits;
  let own;
  if (rec.template === "zone") {
    const poly = (zones.find((z) => z.zone === rec) || {}).poly;
    const inside = new Set(poly ? S.slots.flatMap((s) => cellsAbs(s)).filter((c) => polygonContains(poly, [c.x, c.y])).map((c) => c.code) : []);
    hits = rules.putaway.filter((r) => !r.deleted && inside.has(r.out_code)).map((rule) => ({ rule, codes: [rule.out_code] }));
    own = [...inside];
  } else {
    hits = rulesIntoSlot(rec, rules.putaway, zoneChainAt(zones, rec.x, rec.y));
    own = cellsAbs(rec).map((c) => c.code);
  }
  const replenish = rec.template === "zone" ? [] : rules.replenish.filter((r) => !r.deleted && own.includes(r.cell_code));
  if (!hits.length && !replenish.length && !(rec.template !== "zone" && own.length && canEditRules())) {
    return;
  }
  root.append(
    ...K(
      h(
        "div",
        { class: "sec", id: "rulesInto" },
        h("h3", null, "Правила розміщення сюди"),
        hits.length ? null : h("div", { class: "small muted" }, "Правил, що ведуть сюди, немає."),
        hits.map(
          ({ rule, codes }) => h("div", { class: "frow", "data-rule": rule.id, style: { gap: "6px", alignItems: "center" } }, h("span", { style: { flex: 1 }, class: "small" }, `${ruleLabel(rule)} → ${codes.length > 3 ? codes.slice(0, 3).join(", ") + " …" : codes.join(", ")}`), h("button", { class: "fbtn sm", type: "button", "data-act": "highlight", onclick: () => highlightRule(rule) }, "Підсвітити"))
        ),
        replenish.length ? h("div", { class: "lbl", style: { margin: "6px 0 2px" } }, "Поповнення (min/max)") : null,
        replenish.map((r) => h("div", { class: "small", "data-replenish": r.id }, `${r.product || nameOf("product", r.product_id)} · ${r.cell_code}: мін ${fmt(r.min_qty, 0)} / макс ${fmt(r.max_qty, 0)}`)),
        h(
          "div",
          { class: "frow", style: { gap: "6px", marginTop: "4px", flexWrap: "wrap" } },
          S.ui.metric === "rule_target" ? h("button", { class: "fbtn sm", type: "button", onclick: () => {
            clearHighlight();
            E.renderRight();
          } }, "Зняти підсвітку") : null,
          rec.template !== "zone" && own.length && canEditRules() ? h("button", { class: "fbtn sm", type: "button", id: "btnNewMinMax", onclick: async () => {
            if (await openReplenishForm(newReplenishRule({ cell_code: own[0] }), true)) {
              E.renderRight();
            }
          } }, "Нове правило min/max…") : null
        )
      )
    )
  );
}
registries.panels.add("slot:rules", { area: "slot", render: renderRulesInto }, { sequence: 36, force: true });
export {
  BaseAdapter,
  CAPABILITY_NAMES,
  E,
  OdooAdapter,
  OdooStore,
  REGISTRY_NAMES,
  REQUIRED_METHODS,
  Registry,
  S,
  StoreError,
  THREE,
  V,
  adapter_odoo_exports as adapter_odoo,
  assertAdapter,
  can,
  cells_exports as cells,
  checks_exports as checks,
  data_exports as data,
  dialogs_exports as dialogs,
  dxf_exports as dxf,
  forEachEntry,
  geometry_exports as geometry,
  getThree,
  host,
  live_exports as live,
  loadThree,
  mountEditor,
  newUid,
  registries,
  roles_exports as roles,
  scene_exports as scene,
  setCapabilities,
  setHost,
  state_exports as state,
  unmountEditor,
  util_exports as util,
  webglAvailable
};
