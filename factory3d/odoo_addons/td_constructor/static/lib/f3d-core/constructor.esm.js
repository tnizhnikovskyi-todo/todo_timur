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
  LOC_KIND_LABELS: () => LOC_KIND_LABELS,
  ROLES: () => ROLES,
  SHAPE_LABELS: () => SHAPE_LABELS,
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
  BOTTOM_LIFT: () => BOTTOM_LIFT,
  CODE_MAX_LEN: () => CODE_MAX_LEN2,
  LEVEL_KEYS: () => LEVEL_KEYS,
  LOC_KINDS: () => LOC_KINDS,
  OVERRIDE_KEYS: () => OVERRIDE_KEYS,
  PREFIX_MAX_LEN: () => PREFIX_MAX_LEN,
  SERVICE_SIDES: () => SERVICE_SIDES,
  SHAPE_KEYS: () => SHAPE_KEYS,
  SLOT_TEMPLATES: () => SLOT_TEMPLATES,
  addressedCells: () => addressedCells,
  cellCount: () => cellCount,
  cellsOf: () => cellsOf,
  clearCellsCache: () => clearCellsCache,
  countCells: () => countCells,
  footprint: () => footprint,
  generateCells: () => generateCells,
  normalizeParams: () => normalizeParams,
  rawCells: () => rawCells,
  setContextResolver: () => setContextResolver,
  slotObb: () => slotObb,
  templateCodes: () => templateCodes
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
var makeObb = (cx, cy, a, b, rot2 = 0) => ({ cx: +cx, cy: +cy, a: +a, b: +b, rot: +rot2 });
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
var aabbOverlap = (A, B2, eps = 0) => !(A[2] < B2[0] - eps || B2[2] < A[0] - eps || A[3] < B2[1] - eps || B2[3] < A[1] - eps);
function satPenetration(A, B2) {
  const [[a1x, a1y], [a2x, a2y]] = obbAxes(A);
  const [[b1x, b1y], [b2x, b2y]] = obbAxes(B2);
  const dx = B2.cx - A.cx;
  const dy = B2.cy - A.cy;
  let best = Infinity;
  for (const [ux, uy] of [
    [a1x, a1y],
    [a2x, a2y],
    [b1x, b1y],
    [b2x, b2y]
  ]) {
    const rA = A.a * Math.abs(ux * a1x + uy * a1y) + A.b * Math.abs(ux * a2x + uy * a2y);
    const rB = B2.a * Math.abs(ux * b1x + uy * b1y) + B2.b * Math.abs(ux * b2x + uy * b2y);
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

// core/constructor/addr_core.js
var SEGMENT_KEYS = ["zone", "row", "bay", "level", "pos"];
var SEGMENT_KINDS = ["num", "alpha"];
var ROW_FROM = ["up", "down", "left", "right"];
var ROW_MODES = ["seq", "snake"];
var BAY_DIRS = ["ltr", "rtl", "odd_even"];
var LEVEL_DIRS = ["up", "down"];
var DEPTH_MODES = ["level", "cell"];
var LOC_TREES = ["flat", "row", "section"];
var ROW_TEMPLATES = ["pallet_rack", "cantilever", "shelf", "floor_stack"];
var SPOT_TEMPLATES = ["floor_spot"];
var SPOT_SEGMENT_ORDER = ["pos", "row", "bay", "level"];
var CODE_MAX_LEN = 32;
var TPL_MAX_LEN = 64;
var ZONE_CODE_MAX_LEN = 8;
var MAX_ROW_NO = 9999;
var ALIASES = {
  prefix: "prefix",
  "префікс": "prefix",
  zone: "zone",
  "зона": "zone",
  row: "row",
  aisle: "row",
  "ряд": "row",
  bay: "bay",
  section: "bay",
  "секція": "bay",
  level: "level",
  tier: "level",
  "ярус": "level",
  pos: "pos",
  position: "pos",
  "позиція": "pos"
};
var DEFAULT_TPL = "{zone} {row} {bay} {level} {pos}";
var DEFAULT_SEP = "-";
var DEFAULT_SEG = {
  zone: { kind: "alpha", width: 1, start: 1 },
  row: { kind: "num", width: 2, start: 1 },
  bay: { kind: "num", width: 2, start: 1 },
  level: { kind: "num", width: 1, start: 1 },
  pos: { kind: "num", width: 1, start: 1 }
};
var PRESETS = {
  legacy: {},
  zone_row_bay_level: { tpl: DEFAULT_TPL },
  prefix_bay_level: { tpl: "{prefix} B{bay} L{level} {pos}" },
  prefix_bay_letter: { tpl: "{prefix} {bay}{level} {pos}", seg: { level: { kind: "alpha" } } },
  row_odd_even: { tpl: DEFAULT_TPL, bay_dir: "odd_even" }
};
var PRESET_LABELS = {
  legacy: "Як зараз (ПРЕФІКС-B01-L1)",
  zone_row_bay_level: "Зона-ряд-секція-ярус",
  prefix_bay_level: "Префікс B01 L1",
  prefix_bay_letter: "Префікс 01A (ярус буквою)",
  row_odd_even: "Зона-ряд-секція (чет/непарні)"
};
var SEP_RE = /^[A-Za-z0-9._/#:-]{0,3}$/;
var LITERAL_RE = /^[A-Za-z0-9._/#:-]*$/;
var AddrError = class extends Error {
};
var tplCache = /* @__PURE__ */ new Map();
function parseTpl(tpl) {
  if (tplCache.has(tpl)) {
    return tplCache.get(tpl);
  }
  if (typeof tpl !== "string" || !tpl.trim()) {
    throw new AddrError("Шаблон коду порожній.");
  }
  if (tpl.length > TPL_MAX_LEN) {
    throw new AddrError(`Шаблон коду довший за ${TPL_MAX_LEN} символів.`);
  }
  const words = [];
  const seen = /* @__PURE__ */ new Set();
  for (const raw of tpl.trim().split(/\s+/)) {
    const tokens = [];
    let pos = 0;
    for (const m of raw.matchAll(/\{([^{}]*)\}/g)) {
      addLiteral(tokens, raw.slice(pos, m.index));
      const name = ALIASES[m[1].trim().toLowerCase()];
      if (!name) {
        throw new AddrError(`Невідомий сегмент {${m[1]}} у шаблоні.`);
      }
      if (seen.has(name)) {
        throw new AddrError(`Сегмент {${m[1]}} повторюється в шаблоні.`);
      }
      seen.add(name);
      tokens.push(["seg", name]);
      pos = m.index + m[0].length;
    }
    addLiteral(tokens, raw.slice(pos));
    words.push(tokens);
  }
  if (!seen.size) {
    throw new AddrError("У шаблоні немає жодного сегмента ({ряд}, {секція}, {ярус} …).");
  }
  if (tplCache.size > 256) {
    tplCache.clear();
  }
  tplCache.set(tpl, words);
  return words;
}
function addLiteral(tokens, text) {
  if (!text) {
    return;
  }
  if (text.includes("{") || text.includes("}")) {
    throw new AddrError("Шаблон: дужки { } мають обрамляти назву сегмента.");
  }
  if (!LITERAL_RE.test(text)) {
    throw new AddrError("Шаблон: літери слова — латиниця, цифри та . _ / # : -");
  }
  tokens.push(["lit", text]);
}
function tplSegments(addr) {
  const out = /* @__PURE__ */ new Set();
  for (const word of parseTpl(addr.tpl)) {
    for (const [kind, name] of word) {
      if (kind === "seg") {
        out.add(name);
      }
    }
  }
  return out;
}
function toAlpha(n) {
  if (!Number.isInteger(n) || n < 1) {
    throw new AddrError("Буквений сегмент: номер має бути ≥ 1.");
  }
  let out = "";
  while (n) {
    const rem = (n - 1) % 26;
    out = String.fromCharCode(65 + rem) + out;
    n = Math.floor((n - 1) / 26);
  }
  return out;
}
function fromAlpha(text) {
  if (!text || !/^[A-Z]+$/.test(text)) {
    return null;
  }
  let n = 0;
  for (const ch of text) {
    n = n * 26 + ch.charCodeAt(0) - 64;
  }
  return n;
}
function formatValue(spec, n) {
  if (typeof n === "string") {
    return n;
  }
  const value = spec.start + n - 1;
  if (spec.kind === "alpha") {
    return toAlpha(value);
  }
  if (value < 0) {
    throw new AddrError("Номер сегмента менший за нуль.");
  }
  return String(value).padStart(spec.width, "0");
}
function wordValues(addr, vals) {
  return parseTpl(addr.tpl).map((word) => {
    let out = "";
    for (const [kind, item] of word) {
      if (kind === "lit") {
        out += item;
        continue;
      }
      const value = vals[item];
      if (value == null || value === "") {
        return null;
      }
      out += item === "prefix" ? String(value) : formatValue(addr.seg[item], value);
    }
    return out;
  });
}
var renderCode = (addr, vals) => wordValues(addr, vals).filter((w) => w !== null).join(addr.sep);
function intIn(value, lo, hi, label) {
  if (typeof value !== "number" || !Number.isFinite(value) || !Number.isInteger(value)) {
    throw new AddrError(`${label}: очікується ціле число.`);
  }
  if (value < lo || value > hi) {
    throw new AddrError(`${label}: допустимо від ${lo} до ${hi}.`);
  }
  return value;
}
function choice(value, allowed, label) {
  if (!allowed.includes(value)) {
    throw new AddrError(`${label}: допустимо ${allowed.join(", ")}.`);
  }
  return value;
}
var empty = (v) => v == null || v === false || v === "";
function normalizeAddr(value) {
  if (empty(value) || value === "legacy") {
    return {};
  }
  if (typeof value !== "object" || Array.isArray(value)) {
    throw new AddrError("Адресація має бути об'єктом.");
  }
  const out = {};
  if (!empty(value.row_no)) {
    out.row_no = intIn(value.row_no, 1, MAX_ROW_NO, "Номер ряду");
  }
  if (!empty(value.zone_code)) {
    const z = value.zone_code;
    if (typeof z !== "string" || z.length > ZONE_CODE_MAX_LEN || !LITERAL_RE.test(z)) {
      throw new AddrError(`Код зони: до ${ZONE_CODE_MAX_LEN} символів, латиниця, цифри та . _ / # : -`);
    }
    out.zone_code = z;
  }
  if (empty(value.tpl)) {
    if (value.legacy === true) {
      out.legacy = true;
    }
    return out;
  }
  parseTpl(value.tpl);
  const sep = value.sep ?? DEFAULT_SEP;
  if (typeof sep !== "string" || !SEP_RE.test(sep)) {
    throw new AddrError("Роздільник: до 3 символів (латиниця, цифри та . _ / # : -).");
  }
  const segs2 = value.seg || {};
  if (typeof segs2 !== "object" || Array.isArray(segs2)) {
    throw new AddrError("Сегменти мають бути об'єктом.");
  }
  const segOut = {};
  for (const key of SEGMENT_KEYS) {
    const raw = segs2[key] || {};
    if (typeof raw !== "object" || Array.isArray(raw)) {
      throw new AddrError(`Сегмент «${key}»: очікується об'єкт.`);
    }
    const base2 = DEFAULT_SEG[key];
    const label = `Сегмент «${key}»`;
    const kind = choice(raw.kind ?? base2.kind, SEGMENT_KINDS, label + ": вид");
    segOut[key] = {
      kind,
      width: intIn(raw.width ?? base2.width, 1, 8, label + ": ширина"),
      start: intIn(raw.start ?? base2.start, kind === "alpha" ? 1 : 0, 999, label + ": початок")
    };
  }
  return Object.assign(out, {
    tpl: value.tpl.trim(),
    sep,
    seg: segOut,
    row_from: choice(value.row_from ?? "up", ROW_FROM, "Напрям рядів"),
    row_mode: choice(value.row_mode ?? "seq", ROW_MODES, "Режим рядів"),
    bay_dir: choice(value.bay_dir ?? "ltr", BAY_DIRS, "Напрям секцій"),
    level_dir: choice(value.level_dir ?? "up", LEVEL_DIRS, "Напрям ярусів")
  });
}
function safeNormalize(value) {
  try {
    return normalizeAddr(value);
  } catch (e) {
    if (e instanceof AddrError) {
      return {};
    }
    throw e;
  }
}
var isOwn = (addr) => !!addr && ("tpl" in addr || addr.legacy === true);
function effectiveAddr(...levels) {
  const own = levels.find((a) => isOwn(a));
  return own && !own.legacy ? own : null;
}
function slotPolygon(slot) {
  const params = slot.params || {};
  const poly = params.polygon || slot.polygon;
  if (poly && poly.length >= 3) {
    return poly.map((p) => [Number(p[0]), Number(p[1])]);
  }
  const { length, width: width2 } = params;
  if (!length || !width2) {
    return null;
  }
  const rot2 = (slot.rotation || 0) * Math.PI / 180;
  const cos = Math.cos(rot2);
  const sin = Math.sin(rot2);
  const cx = slot.x || 0;
  const cy = slot.y || 0;
  return [
    [-length / 2, -width2 / 2],
    [length / 2, -width2 / 2],
    [length / 2, width2 / 2],
    [-length / 2, width2 / 2]
  ].map(([px, py]) => [cx + px * cos - py * sin, cy + px * sin + py * cos]);
}
function polyArea(poly) {
  let total = 0;
  poly.forEach(([x1, y1], i) => {
    const [x2, y2] = poly[(i + 1) % poly.length];
    total += x1 * y2 - x2 * y1;
  });
  return Math.abs(total) / 2;
}
function center(slot, poly) {
  if (poly) {
    return [poly.reduce((a, p) => a + p[0], 0) / poly.length, poly.reduce((a, p) => a + p[1], 0) / poly.length];
  }
  return [slot.x || 0, slot.y || 0];
}
function orderKey(rowFrom, point, uid2) {
  const x = Math.floor(point[0] * 100 + 0.5);
  const y = Math.floor(point[1] * 100 + 0.5);
  const main = { up: y, down: -y, right: x, left: -x }[rowFrom];
  const side2 = rowFrom === "up" || rowFrom === "down" ? x : y;
  return [main, side2, String(uid2)];
}
function cmpKeys(a, b) {
  for (let i = 0; i < a.length; i++) {
    if (a[i] < b[i]) {
      return -1;
    }
    if (a[i] > b[i]) {
      return 1;
    }
  }
  return 0;
}
var uidOf = (slot) => slot.uid || slot.id;
function* freeNumbers(used) {
  let n = 0;
  for (; ; ) {
    n++;
    if (!used.has(n)) {
      yield n;
    }
  }
}
function addressContext(slots, siteAddr = null, siteDepthMode = "level") {
  const site = safeNormalize(siteAddr);
  const out = /* @__PURE__ */ new Map();
  const byLayer2 = /* @__PURE__ */ new Map();
  for (const s of slots) {
    if (!byLayer2.has(s.layer_id)) {
      byLayer2.set(s.layer_id, []);
    }
    byLayer2.get(s.layer_id).push(s);
  }
  for (const layerSlots of byLayer2.values()) {
    const zones = [];
    for (const s of layerSlots) {
      const poly = s.template === "zone" ? slotPolygon(s) : null;
      if (poly) {
        zones.push({ slot: s, poly, area: polyArea(poly) });
      }
    }
    const zoneFrom = site.row_from || "up";
    const ordered = [...zones].sort((a, b) => cmpKeys(orderKey(zoneFrom, center(a.slot, a.poly), uidOf(a.slot)), orderKey(zoneFrom, center(b.slot, b.poly), uidOf(b.slot))));
    const zoneNo = new Map(ordered.map((z, i) => [uidOf(z.slot), i + 1]));
    const scopes = /* @__PURE__ */ new Map();
    for (const s of layerSlots) {
      if (s.template === "zone") {
        continue;
      }
      const point = center(s);
      let host2 = null;
      for (const z of zones) {
        if (polygonContains(z.poly, point) && (!host2 || z.area < host2.area)) {
          host2 = z;
        }
      }
      const zone2 = host2 ? host2.slot : null;
      const key = zone2 ? uidOf(zone2) : null;
      if (!scopes.has(key)) {
        scopes.set(key, { zone: zone2, members: [] });
      }
      scopes.get(key).members.push(s);
    }
    for (const { zone: zone2, members } of scopes.values()) {
      const zoneAddr = zone2 ? safeNormalize(zone2.addr) : {};
      const scopeAddr = effectiveAddr(zoneAddr, site) || {};
      const rowFrom = scopeAddr.row_from || "up";
      const zoneValue = zone2 ? zoneAddr.zone_code || zoneNo.get(uidOf(zone2)) || null : null;
      const depthMode = zone2 && zone2.depth_mode || siteDepthMode || "level";
      const numbers = /* @__PURE__ */ new Map();
      for (const templates of [ROW_TEMPLATES, SPOT_TEMPLATES]) {
        const group = members.filter((s) => templates.includes(s.template));
        const pinned = new Map(group.map((s) => [uidOf(s), safeNormalize(s.addr).row_no]));
        const free = freeNumbers(new Set([...pinned.values()].filter((n) => n)));
        const sorted = [...group].sort((a, b) => cmpKeys(orderKey(rowFrom, center(a), uidOf(a)), orderKey(rowFrom, center(b), uidOf(b))));
        for (const s of sorted) {
          numbers.set(uidOf(s), pinned.get(uidOf(s)) || free.next().value);
        }
      }
      for (const s of members) {
        const uid2 = uidOf(s);
        const isRow = ROW_TEMPLATES.includes(s.template);
        out.set(uid2, {
          addr: effectiveAddr(safeNormalize(s.addr), zoneAddr, site),
          zone: zoneValue,
          row: isRow ? numbers.get(uid2) ?? null : null,
          spot: isRow ? null : numbers.get(uid2) ?? null,
          depth_mode: s.depth_mode || depthMode
        });
      }
    }
    for (const s of layerSlots) {
      if (s.template === "zone") {
        out.set(uidOf(s), {
          addr: effectiveAddr(safeNormalize(s.addr), site),
          zone: null,
          row: null,
          spot: null,
          depth_mode: s.depth_mode || siteDepthMode || "level"
        });
      }
    }
  }
  return out;
}
var usableContext = (ctx2) => ctx2 && (ctx2.addr || ctx2.depth_mode === "cell") ? ctx2 : null;
function stateContexts(state) {
  const site = state.site || {};
  return addressContext((state.slots || []).map((s) => ({ ...s, uid: s.uid || s.id })), site.addr, site.depth_mode || "level");
}
function bayForward(rot2) {
  const r = (rot2 || 0) * Math.PI / 180;
  const cos = Math.cos(r);
  const sin = Math.sin(r);
  return Math.abs(cos) >= Math.abs(sin) ? cos > 0 : sin < 0;
}
function cellVals(ctx2, prefix, rot2, raw, sizes) {
  const addr = ctx2.addr;
  const row = ctx2.row;
  const leftRight = bayForward(rot2);
  let forward = leftRight;
  if (addr.row_mode === "snake" && row && row % 2 === 0) {
    forward = !forward;
  }
  if (addr.bay_dir === "rtl") {
    forward = !forward;
  }
  const k = forward ? raw.k : sizes.bays - raw.k + 1;
  const side2 = raw.side || 1;
  let bay;
  if (addr.bay_dir === "odd_even") {
    const sideNo = (sizes.sides || 1) > 1 ? side2 : (row || 1) % 2 ? 1 : 2;
    bay = sideNo === 1 ? 2 * k - 1 : 2 * k;
  } else {
    bay = k + (side2 - 1) * sizes.bays;
  }
  let level = raw.level ?? null;
  if (level !== null && addr.level_dir === "down") {
    level = sizes.levels - level + 1;
  }
  let pos = raw.pos ?? null;
  if (pos !== null && raw.pos_x && !leftRight) {
    pos = raw.pos_n - pos + 1;
  }
  return { prefix, zone: ctx2.zone ?? null, row: row ?? null, bay, level, pos };
}
function spotVals(ctx2, prefix) {
  const have = tplSegments(ctx2.addr);
  const vals = { prefix, zone: ctx2.zone ?? null, row: null, bay: null, level: null, pos: null };
  for (const key of SPOT_SEGMENT_ORDER) {
    if (have.has(key)) {
      vals[key] = ctx2.spot || 1;
      break;
    }
  }
  return vals;
}
function findDuplicates(codes) {
  const seen = /* @__PURE__ */ new Set();
  const dup = [];
  for (const c of codes) {
    if (seen.has(c) && !dup.includes(c)) {
      dup.push(c);
    }
    seen.add(c);
  }
  return dup;
}
function preview(codes, oldCodes = null, limit = 10) {
  let changed = 0;
  if (oldCodes) {
    changed = codes.filter((c, i) => i >= oldCodes.length || oldCodes[i] !== c).length;
  }
  return {
    first: codes.slice(0, limit),
    last: codes.length ? codes[codes.length - 1] : null,
    total: codes.length,
    changed,
    duplicates: findDuplicates(codes),
    too_long: codes.filter((c) => c.length > CODE_MAX_LEN)
  };
}
function conflicts(codesBySlot, occupied = []) {
  const owners = /* @__PURE__ */ new Map();
  for (const [uid2, codes] of codesBySlot) {
    for (const c of codes) {
      if (!owners.has(c)) {
        owners.set(c, []);
      }
      owners.get(c).push(uid2);
    }
  }
  const taken = new Set(occupied);
  const out = {};
  for (const [code, uids] of owners) {
    if (uids.length > 1 || taken.has(code)) {
      out[code] = uids;
    }
  }
  return out;
}

// core/constructor/cells.js
var CODE_MAX_LEN2 = 32;
var PREFIX_MAX_LEN = 22;
var BOTTOM_LIFT = 0.15;
var I = "int";
var F = "float";
var B = "bool";
var L = "list";
var LOC_KINDS = ["stack", "area", "kit", "bin", "shelf", "pallet_cell"];
var SHAPE_KEYS = ["", "rack", "roll_rack", "stack", "zone", "fence", "cylinder", "cabinet", "mobile", "gate"];
var OPT_RACK = {
  bottom_on_floor: [null, null, true, B],
  double_sided: [null, null, false, B],
  gap_x: [0, 2, 0, F],
  gap_y: [0, 2, 0, F],
  beam_th: [0, 0.3, 0, F],
  slope: [0, 20, 0, F],
  cells_per_level: [1, 12, 1, I],
  level_heights: [0.1, 3, null, L]
};
var { gap_x: _gx, ...OPT_CANTILEVER } = OPT_RACK;
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
    opt: { ...OPT_RACK, deep: [1, 6, 1, I] },
    choices: { code_style: [["default", "bay_letter", "exact"], "default"] },
    optChoices: { shape: [SHAPE_KEYS, ""] }
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
    opt: OPT_CANTILEVER,
    choices: { code_style: [["default", "exact"], "default"] },
    optChoices: { shape: [SHAPE_KEYS, ""] }
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
    opt: { ...OPT_RACK },
    choices: { loc_kind: [["bin", "shelf"], "bin"], code_style: [["default", "exact"], "default"] },
    optChoices: { shape: [SHAPE_KEYS, ""] }
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
    opt: { gap_x: [0, 2, 0, F], gap_y: [0, 2, 0, F] },
    choices: { code_style: [["default", "exact"], "default"], loc_kind: [LOC_KINDS, "stack"] },
    optChoices: { shape: [SHAPE_KEYS, ""] }
  },
  // прямокутник на підлозі = ОДНА локація (MERGE.md §2.3): буферні й спеціальні зони, мобільні носії, зона на підлозі
  floor_spot: {
    label: "Місце на підлозі (одна локація)",
    cells: true,
    params: {
      length: [0.1, 200, 1.2, F],
      width: [0.1, 200, 0.8, F],
      height: [0, 30, 1.5, F],
      max_load_kg: [0, null, 0, F],
      capacity: [0, null, 0, F]
    },
    choices: { loc_kind: [LOC_KINDS, "area"], shape: [SHAPE_KEYS, "zone"] }
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
var OVERRIDE_KEYS = ["disabled", "max_load_kg", "capacity", "name", "usage", "replenish_location"];
var LEVEL_KEYS = { pallet_rack: ["levels", "level_height"], cantilever: ["levels", "level_height"], shelf: ["shelves", "cell_h"] };
var BAY_KEYS = { pallet_rack: "bays", cantilever: "arms", shelf: "sections", floor_stack: "cols" };
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
  for (const [key, [, , , type]] of Object.entries(spec.opt || {})) {
    if (src[key] == null) {
      continue;
    }
    if (type === L) {
      const [countKey, heightKey] = LEVEL_KEYS[template];
      const list = Array.isArray(src[key]) ? src[key].map(Number) : [];
      if (list.length) {
        const pad = Array(out[countKey]).fill(out[heightKey]);
        out[key] = [...list, ...pad].slice(0, out[countKey]);
      }
    } else {
      out[key] = type === B ? !!src[key] : src[key];
    }
  }
  for (const key of Object.keys(spec.optChoices || {})) {
    if (src[key]) {
      out[key] = src[key];
    }
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
var sidesOf = (p) => p.double_sided ? 2 : 1;
function footprint(template, params) {
  const p = normalizeParams(template, params);
  const gx = p.gap_x ?? 0;
  const gy = p.gap_y ?? 0;
  const sd = sidesOf(p);
  switch (template) {
    case "pallet_rack":
      return { l: p.bays * p.bay_width + (p.bays - 1) * gx, w: sd * p.depth * (p.deep ?? 1) + (sd - 1) * gy };
    case "cantilever":
      return { l: p.length, w: sd * p.arm_length + (sd - 1) * gy };
    case "shelf":
      return { l: p.sections * p.cell_w + (p.sections - 1) * gx, w: sd * p.cell_d + (sd - 1) * gy };
    case "floor_stack":
      return { l: p.cols * p.cell_l + (p.cols - 1) * gx, w: p.rows * p.cell_w + (p.rows - 1) * gy };
    case "machine_spot":
    case "floor_spot":
      return { l: p.length, w: p.width };
    default: {
      const xs = p.polygon.map((q) => q[0]);
      const ys = p.polygon.map((q) => q[1]);
      return xs.length ? { l: Math.max(...xs) - Math.min(...xs), w: Math.max(...ys) - Math.min(...ys) } : { l: 0, w: 0 };
    }
  }
}
function slotObb(template, params, x, y, rot2) {
  const { l, w } = footprint(template, params);
  if (template === "zone") {
    const poly = normalizeParams(template, params).polygon;
    const xs = poly.map((q) => q[0]);
    const ys = poly.map((q) => q[1]);
    return makeObb((Math.max(...xs) + Math.min(...xs)) / 2, (Math.max(...ys) + Math.min(...ys)) / 2, l / 2, w / 2, 0);
  }
  return makeObb(x, y, l / 2, w / 2, rot2);
}
var width = (count, digits = 2) => Math.max(digits, String(count).length);
var zpad = (n, w) => String(n).padStart(w, "0");
var letter = (n) => String.fromCharCode(64 + n);
function levelsOf(p, n, baseH2) {
  const heights = p.level_heights;
  const lift = p.bottom_on_floor === false ? BOTTOM_LIFT : 0;
  const beam = p.beam_th || 0;
  const out = [];
  let z = lift;
  for (let i = 0; i < n; i++) {
    const h2 = heights ? heights[i] : baseH2;
    out.push({ dz: heights ? z : lift + i * baseH2, h: beam ? Math.max(h2 - beam, 0.05) : h2 });
    z += h2;
  }
  return out;
}
function rawCells(template, p, prefix) {
  const cells = rawCellsStyled(template, p, prefix);
  if (p.code_style === "exact" && cells.length === 1) {
    cells[0].code = prefix;
  }
  return cells;
}
function rawCellsStyled(template, p, prefix) {
  const cells = [];
  const gx = p.gap_x ?? 0;
  const gy = p.gap_y ?? 0;
  const sides = sidesOf(p);
  const sideY = (side2, full, d) => sides === 1 ? 0 : side2 === 1 ? -(full - d) / 2 : (full - d) / 2;
  if (template === "pallet_rack") {
    const deep = p.deep ?? 1;
    const d = p.depth * deep;
    const length = p.bays * p.bay_width + (p.bays - 1) * gx;
    const full = sides * d + (sides - 1) * gy;
    const wn = width(p.bays * sides, p.index_digits);
    const lv = levelsOf(p, p.levels, p.level_height);
    for (let side2 = 1; side2 <= sides; side2++) {
      for (let bay = 1; bay <= p.bays; bay++) {
        const bayNo = bay + (side2 - 1) * p.bays;
        for (let lvl = 1; lvl <= p.levels; lvl++) {
          cells.push({
            code: p.code_style === "bay_letter" ? `${prefix}-${zpad(bayNo, wn)}${letter(lvl)}` : `${prefix}-B${zpad(bayNo, wn)}-L${lvl}`,
            level: lvl,
            index: bayNo,
            lx: -length / 2 + (bay - 0.5) * p.bay_width + (bay - 1) * gx,
            ly: sideY(side2, full, d),
            dz: lv[lvl - 1].dz,
            l: p.bay_width,
            w: d,
            h: lv[lvl - 1].h,
            capacity: Number(p.positions_per_bay) * deep,
            max_load_kg: p.max_load_kg,
            kind: "pallet_cell",
            k: bay,
            side: side2
          });
        }
      }
    }
  } else if (template === "cantilever") {
    const length = p.length;
    const armL = length / p.arms;
    const full = sides * p.arm_length + (sides - 1) * gy;
    const wn = width(p.arms * sides, p.index_digits);
    const lv = levelsOf(p, p.levels, p.level_height);
    for (let side2 = 1; side2 <= sides; side2++) {
      for (let arm = 1; arm <= p.arms; arm++) {
        const armNo = arm + (side2 - 1) * p.arms;
        for (let lvl = 1; lvl <= p.levels; lvl++) {
          cells.push({
            code: `${prefix}-A${zpad(armNo, wn)}-L${lvl}`,
            level: lvl,
            index: armNo,
            lx: -length / 2 + (arm - 0.5) * armL,
            ly: sideY(side2, full, p.arm_length),
            dz: lv[lvl - 1].dz,
            l: armL,
            w: p.arm_length,
            h: lv[lvl - 1].h,
            capacity: 0,
            max_load_kg: p.max_load_kg,
            kind: "shelf",
            k: arm,
            side: side2
          });
        }
      }
    }
  } else if (template === "shelf") {
    const length = p.sections * p.cell_w + (p.sections - 1) * gx;
    const full = sides * p.cell_d + (sides - 1) * gy;
    const wn = width(p.sections * sides, p.index_digits);
    const lv = levelsOf(p, p.shelves, p.cell_h);
    for (let side2 = 1; side2 <= sides; side2++) {
      for (let sec = 1; sec <= p.sections; sec++) {
        const secNo = sec + (side2 - 1) * p.sections;
        for (let lvl = 1; lvl <= p.shelves; lvl++) {
          cells.push({
            code: `${prefix}-S${zpad(secNo, wn)}-L${lvl}`,
            level: lvl,
            index: secNo,
            lx: -length / 2 + (sec - 0.5) * p.cell_w + (sec - 1) * gx,
            ly: sideY(side2, full, p.cell_d),
            dz: lv[lvl - 1].dz,
            l: p.cell_w,
            w: p.cell_d,
            h: lv[lvl - 1].h,
            capacity: 0,
            max_load_kg: 0,
            kind: p.loc_kind,
            k: sec,
            side: side2
          });
        }
      }
    }
  } else if (template === "floor_stack") {
    const length = p.cols * p.cell_l + (p.cols - 1) * gx;
    const wid = p.rows * p.cell_w + (p.rows - 1) * gy;
    const wn = width(p.rows, p.index_digits);
    for (let row = 1; row <= p.rows; row++) {
      for (let col = 1; col <= p.cols; col++) {
        cells.push({
          code: `${prefix}-${zpad(row, wn)}${letter(col)}`,
          level: 1,
          index: (row - 1) * p.cols + col,
          lx: -length / 2 + (col - 0.5) * p.cell_l + (col - 1) * gx,
          ly: -wid / 2 + (row - 0.5) * p.cell_w + (row - 1) * gy,
          dz: 0,
          l: p.cell_l,
          w: p.cell_w,
          h: p.max_height,
          capacity: 0,
          max_load_kg: 0,
          kind: p.loc_kind,
          k: col,
          side: 1,
          pos: row,
          pos_n: p.rows
        });
      }
    }
  } else if (template === "floor_spot") {
    cells.push({
      code: prefix,
      level: 1,
      index: 1,
      lx: 0,
      ly: 0,
      dz: 0,
      l: p.length,
      w: p.width,
      h: p.height,
      capacity: p.capacity,
      max_load_kg: p.max_load_kg,
      kind: p.loc_kind,
      k: 1,
      side: 1
    });
  }
  return cells;
}
function splitCells(cells, n) {
  const out = [];
  for (const c of cells) {
    for (let j = 1; j <= n; j++) {
      out.push({
        ...c,
        code: `${c.code}-${j}`,
        lx: c.lx - c.l / 2 + (j - 0.5) * c.l / n,
        l: c.l / n,
        capacity: c.capacity / n,
        max_load_kg: c.max_load_kg / n,
        pos: j,
        pos_n: n,
        pos_x: true
      });
    }
  }
  return out;
}
function addressedCells(template, p, prefix, rot2, ctx2) {
  let cells = rawCells(template, p, prefix);
  if (!ctx2) {
    return cells;
  }
  if (ctx2.depth_mode === "cell" && LEVEL_KEYS[template]) {
    cells = splitCells(cells, p.cells_per_level ?? 1);
  }
  const addr = ctx2.addr;
  if (!addr || p.code_style === "exact") {
    return cells;
  }
  if (template === "floor_spot") {
    for (const c of cells) {
      c.code = renderCode(addr, spotVals(ctx2, prefix));
    }
    return cells;
  }
  const sizes = { sides: sidesOf(p), levels: LEVEL_KEYS[template] ? p[LEVEL_KEYS[template][0]] : 1, bays: p[BAY_KEYS[template]] };
  for (const c of cells) {
    c.code = renderCode(addr, cellVals(ctx2, prefix, rot2, { ...c, level: LEVEL_KEYS[template] ? c.level : null }, sizes));
  }
  return cells;
}
function generateCells(template, prefix, x, y, rot2, params, overrides, elevation = 0, ctx2 = null) {
  const spec = SLOT_TEMPLATES[template];
  if (!spec || !spec.cells) {
    return [];
  }
  const p = normalizeParams(template, params);
  const ovs = overrides || {};
  const out = [];
  for (const raw of addressedCells(template, p, prefix, rot2, ctx2)) {
    const ov = ovs[raw.code] || {};
    if (ov.disabled) {
      continue;
    }
    const [wx, wy] = rotate(raw.lx, raw.ly, rot2);
    const cell = {
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
      rot: Number(rot2),
      capacity: ov.capacity ?? raw.capacity,
      max_load_kg: ov.max_load_kg ?? raw.max_load_kg,
      kind: raw.kind
    };
    for (const k of ["usage", "replenish_location"]) {
      if (k in ov) {
        cell[k] = ov[k];
      }
    }
    out.push(cell);
  }
  return out;
}
var templateCodes = (template, params, prefix, ctx2 = null) => {
  const spec = SLOT_TEMPLATES[template];
  return spec && spec.cells ? addressedCells(template, normalizeParams(template, params), prefix, 0, ctx2).map((c) => c.code) : [];
};
var countCells = (template, prefix, params, overrides, ctx2 = null) => generateCells(template, prefix, 0, 0, 0, params, overrides, 0, ctx2).length;
var cache = /* @__PURE__ */ new Map();
var resolver = null;
function setContextResolver(fn) {
  resolver = fn;
  cache.clear();
}
function cellsOf(s) {
  const ctx2 = resolver ? resolver(s) : null;
  const sig = [s.template, s.code_prefix, JSON.stringify(s.params), JSON.stringify(s.overrides || {}), s.rotation || 0, ctx2 ? JSON.stringify(ctx2) : ""].join("|");
  const hit = cache.get(s.id);
  if (hit && hit.sig === sig) {
    return hit.cells;
  }
  const spec = SLOT_TEMPLATES[s.template];
  let cells = [];
  if (spec && spec.cells) {
    const ovs = s.overrides || {};
    cells = addressedCells(s.template, normalizeParams(s.template, s.params), s.code_prefix || "", s.rotation || 0, ctx2).map((c) => {
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
        for (const k of ["usage", "replenish_location"]) {
          if (k in ov) {
            r[k] = ov[k];
          }
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
  const [min, max, def, type] = SLOT_TEMPLATES[tpl].params[k] || SLOT_TEMPLATES[tpl].opt[k];
  return { min, max: max ?? 1e5, def, int: type === "int" ? 1 : 0 };
};
var num = (tpl, k, l, u, step) => ({ k, l, u, step, ...range(tpl, k) });
var LOC_KIND_LABELS = {
  stack: "Стос",
  area: "Майданчик",
  kit: "Візок / етажерка",
  bin: "Комірка (bin)",
  shelf: "Полиця",
  pallet_cell: "Комірка палети"
};
var SHAPE_LABELS = {
  "": "За генератором",
  rack: "Стійка",
  roll_rack: "Рулонний стелаж",
  stack: "Штабель",
  zone: "Зона",
  fence: "Огорожа / камера",
  cylinder: "Циліндр / бункер",
  cabinet: "Шафа-машина",
  mobile: "Мобільний носій",
  gate: "Ворота / док"
};
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
  floor_spot: {
    name: "Місце на підлозі",
    prefix: "FS1",
    info: "Прямокутник на підлозі = одна локація (буферна чи спеціальна зона, візок, ворота-зона)",
    params: [
      num("floor_spot", "length", "Довжина", "м", 0.1),
      num("floor_spot", "width", "Ширина", "м", 0.1),
      num("floor_spot", "height", "Висота", "м", 0.1),
      num("floor_spot", "max_load_kg", "Макс. навантаження", "кг", 50),
      num("floor_spot", "capacity", "Місткість", "місць", 1),
      { k: "loc_kind", l: "Вид локації", type: "select", options: LOC_KINDS.map((v) => [v, LOC_KIND_LABELS[v]]), def: "area" },
      { k: "shape", l: "Форма 3D", type: "select", options: SHAPE_KEYS.filter(Boolean).map((v) => [v, SHAPE_LABELS[v]]), def: "zone" }
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
var SOLID_SLOTS = ["pallet_rack", "cantilever", "shelf", "floor_stack", "floor_spot"];
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
  const lift = p.bottom_on_floor === false ? 0.15 : 0;
  switch (s.template) {
    case "pallet_rack":
    case "cantilever":
      return (p.level_heights ? p.level_heights.reduce((a, x) => a + x, 0) : (p.levels || 1) * (p.level_height || 1.5)) + lift + 0.25;
    case "shelf":
      return (p.level_heights ? p.level_heights.reduce((a, x) => a + x, 0) : (p.shelves || 1) * (p.cell_h || 0.4)) + lift + 0.1;
    case "floor_stack":
      return p.max_height || 1.5;
    case "floor_spot":
      return p.height ?? 1.5;
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
  selKeys: () => selKeys,
  selRefs: () => selRefs,
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
var E = { lifecycle: { mount: /* @__PURE__ */ new Set(), unmount: /* @__PURE__ */ new Set() } };
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
  multi: [],
  // мультивиділення (S3, F09-02): [{kind, id}] з ≥ 2 об'єктів; S.sel — основний (останній) серед них
  selCell: null,
  edit: null,
  issues: { list: [], byKey: /* @__PURE__ */ new Map() },
  ui: { leftTab: "layers", layer: null },
  vIdx: /* @__PURE__ */ new Map(),
  lIdx: /* @__PURE__ */ new Map(),
  sIdx: /* @__PURE__ */ new Map(),
  pIdx: /* @__PURE__ */ new Map(),
  changed: 0,
  saveState: "saved",
  // saved | saving | error
  hist: { stack: [], idx: -1, cur: "", label: null, busy: false },
  // скасування/повтор (S3, undo.js)
  unsaved: /* @__PURE__ */ new Set(),
  // ключі об'єктів, змінених після останнього збереження (N-05, «не збережено»)
  stock: null,
  // залишки по кодах для карти й картки (S3, stock_state.js): {at, demo, days, byCode: Map}
  hl: null
  // підсвічені комірки пошуку (S3): {kind, codes: Set}
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
  if (S.multi.length) {
    S.multi = S.multi.filter((r) => (r.kind === "placement" ? S.pIdx : S.sIdx).has(r.id));
    if (S.multi.length < 2) {
      if (S.multi.length === 1 && !S.sel) {
        S.sel = { ...S.multi[0] };
      }
      S.multi = [];
    } else if (!S.sel) {
      S.sel = { ...S.multi[S.multi.length - 1] };
    } else if (!S.multi.some((r) => r.kind === S.sel.kind && r.id === S.sel.id)) {
      S.multi = [];
    }
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
var selRefs = () => S.multi.length > 1 ? S.multi : S.sel ? [S.sel] : [];
var selKeys = () => new Set(selRefs().map((r) => objKey(r.kind, r.id)));

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
    let choice2 = "theirs";
    openDialog({
      title: "Запис змінив інший користувач",
      cls: "narrow",
      body: h("p", { style: { margin: 0 } }, "Об’єкт на сервері новіший за ваш. Залишити вашу версію чи взяти серверну (ваші зміни цього об’єкта буде втрачено)?"),
      actions: [
        { label: "Взяти серверне", value: "theirs", id: "dlgTheirs" },
        { label: "Залишити моє", cls: "primary", value: "mine", id: "dlgMine", onClick: () => {
          choice2 = "mine";
        } }
      ],
      onClose: () => res(choice2)
    });
  });
}
Object.assign(E, { openDialog, confirmBox, openNewSite, openHistory, openServerIssues, askConflict });
registries.dialogs.add("confirm", (o) => confirmBox(o), { force: true });
registries.dialogs.add("newSite", () => openNewSite(), { force: true });
registries.dialogs.add("history", () => openHistory(), { force: true });
registries.dialogs.add("serverIssues", ({ res }) => openServerIssues(res), { force: true });
registries.dialogs.add("conflict", () => askConflict(), { force: true });

// core/constructor/draft.js
var DESIGN_ROLES = ["technologist", "storekeeper", "engineer"];
var ACCESS_NAMES = { view: "Перегляд", design: "Проєктування", apply: "Застосування" };
function access() {
  const va = viewAs();
  const mobile2 = !!E.isMobile?.();
  const edit = S.app.mode === "edit" && !mobile2;
  const isDesigner = va ? DESIGN_ROLES.includes(va) : !!S.rights.is_manager || (S.rights.roles || []).some((r) => DESIGN_ROLES.includes(r));
  const design2 = edit && isDesigner;
  const apply = !mobile2 && canPublish();
  return { view: true, design: design2, apply, level: apply ? "apply" : design2 ? "design" : "view", name: ACCESS_NAMES[apply ? "apply" : design2 ? "design" : "view"] };
}
function accessHint(need) {
  if (E.isMobile?.()) {
    return "У мобільному режимі доступні перегляд і пошук; правка вимкнена.";
  }
  if (S.app.mode !== "edit") {
    return "Режим перегляду: увімкніть «Редагування».";
  }
  if (need === "apply") {
    return "Застосування в Odoo доступне менеджеру в режимі редагування (група «Застосування»).";
  }
  return "Потрібен рівень «Проєктування»: технолог, комірник, інженер або менеджер.";
}
var strip = (k, v) => k === "rid" || k === "etag" ? void 0 : v;
var recJson = (r) => JSON.stringify(r, strip);
var keyed = () => [...S.layers.map((l) => ["l:" + l.id, l]), ...S.slots.map((s) => ["s:" + s.id, s]), ...S.placements.map((p) => ["p:" + p.id, p])];
var saved = /* @__PURE__ */ new Map();
function syncSaveAll() {
  const b = $("#menu-saveAll");
  if (b) {
    b.disabled = !S.unsaved.size && S.saveState === "saved";
  }
}
function markSaved() {
  saved = new Map(keyed().map(([k, r]) => [k, recJson(r)]));
  if (S.unsaved.size) {
    S.unsaved = /* @__PURE__ */ new Set();
    E.updateVisual?.();
  }
  syncSaveAll();
}
function refreshUnsaved() {
  const next = /* @__PURE__ */ new Set();
  for (const [k, r] of keyed()) {
    if (saved.get(k) !== recJson(r)) {
      next.add(k);
    }
  }
  const old = S.unsaved;
  if (next.size !== old.size || [...next].some((k) => !old.has(k))) {
    S.unsaved = next;
    E.updateVisual?.();
    syncSaveAll();
  }
}
function objStatus(kind, rec) {
  const key = objKey(kind, rec.id);
  if (S.unsaved.has(key)) {
    return "unsaved";
  }
  if (rec.rid != null || E.adapter?.baseMap?.has?.(key)) {
    return "odoo";
  }
  return "new";
}
var STATUS_LABELS = { unsaved: "не збережено", new: "нове · лише в моделі", odoo: "з Odoo" };
async function saveAll() {
  const r = await E.flushNow();
  toast(r && r.ok === false ? "Не вдалося зберегти зміни." : "Усе збережено.", r && r.ok === false ? "err" : void 0);
  markSaved();
}
async function resetToOdoo() {
  const av = S.site?.active_version;
  const ver = av && S.versions.find((v) => v.n === av.n);
  if (!ver) {
    toast("Немає опублікованої версії: нічого скидати.", "warn");
    return;
  }
  const ok = await E.confirmBox({ title: "Скинути до даних Odoo?", text: `Чернетку буде повернуто до опублікованої версії v${ver.n}; усі незастосовані зміни втрачено.`, ok: "Скинути", danger: true });
  if (ok) {
    E.undoReset();
    await E.restoreVersion(ver.id, ver.n);
  }
}
registries.menu.add(
  "saveAll",
  { area: "top", label: "Зберегти все", icon: "check", sequence: 5, run: saveAll, disabled: () => !S.unsaved.size && S.saveState === "saved" },
  { sequence: 5, force: true }
);
registries.menu.add(
  "resetToOdoo",
  { area: "more", label: "Скинути до даних Odoo", icon: "hist", sequence: 20, run: resetToOdoo, disabled: () => !access().design || !S.site?.active_version },
  { sequence: 20, force: true }
);
function renderStatusBlock(root, { rec }) {
  if (!rec || !S.sel) {
    return;
  }
  const st = objStatus(S.sel.kind, rec);
  const acc = access();
  const btn = h("button", { class: "fbtn sm", type: "button", id: "btnSaveObj", "data-title": "Записати чергу змін у чернетку негайно", onclick: saveAll }, "Зберегти");
  btn.disabled = st !== "unsaved" || !acc.design;
  btn.title = !acc.design ? accessHint("design") : st === "unsaved" ? "Записати чергу змін у чернетку негайно" : "Усе вже збережено";
  root.append(h("div", { class: "sec", id: "statusBlock" }, h("h3", null, "Статус"), h("div", { class: "frow wrap" }, h("span", { class: "tag s3-status", "data-status": st }, STATUS_LABELS[st]), h("span", { class: "tag", title: "Рівень доступу" }, acc.name), btn)));
}
registries.panels.add("right:status", { area: "right", render: renderStatusBlock }, { sequence: 80, force: true });
function openHotkeys() {
  const rows = registries.hotkeys.getEntries().filter(([, hk2]) => hk2.label);
  const base2 = [
    ["Esc", "скасувати режим / зняти вибір"],
    ["R", "поворот на 90° (Shift — у інший бік)"],
    ["Del", "видалити виділене"],
    ["←↑↓→", "зсунути на крок сітки (Shift — на 10)"],
    ["M", "лінійка"],
    ["Alt", "без прив’язки до сітки при перетягуванні"]
  ];
  const extra = rows.map(([, hk2]) => {
    const [k, ...rest] = hk2.label.split(" — ");
    return [k, rest.join(" — ")];
  });
  openDialog({
    title: "Гарячі клавіші",
    cls: "narrow",
    body: h("table", { class: "tbl", id: "hotkeysTable" }, h("tbody", null, K([...base2, ...extra].map(([k, d]) => h("tr", null, h("td", null, h("kbd", null, k)), h("td", null, d)))))),
    actions: [{ label: "Закрити" }]
  });
}
registries.dialogs.add("hotkeys", () => openHotkeys(), { force: true });
registries.menu.add("hotkeys", { area: "more", label: "Гарячі клавіші", icon: "tag", sequence: 90, run: () => E.runDialog("hotkeys") }, { sequence: 90, force: true });
Object.assign(E, { access, accessHint, markSaved, refreshUnsaved, objStatus, syncSaveAll });

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
function selectEl(opts2, value, onChange, dis, label) {
  const el = h(
    "select",
    { disabled: dis, "aria-label": label },
    opts2.map(([v, t]) => h("option", { value: v, selected: String(v) === String(value) }, t))
  );
  el.addEventListener("change", () => onChange(el.value));
  return el;
}
function checkGroup(opts2, vals, onChange, dis) {
  return h(
    "div",
    { class: "checks" },
    opts2.map(([v, t]) => {
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
  const segs2 = [];
  const line = (x12, y12, x2, y2) => segs2.push(x12, y12, x2, y2);
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
        const rot2 = rad(e.rotation || 0);
        const c = Math.cos(rot2);
        const s = Math.sin(rot2);
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
    if (segs2.length >= DXF_MAX_SEGMENTS * 4) {
      break;
    }
  }
  const cap = Math.min(segs2.length, DXF_MAX_SEGMENTS * 4);
  const arr = new Float32Array(cap);
  for (let i = 0; i < cap; i++) {
    arr[i] = segs2[i];
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
  return { segs: arr, n: arr.length / 4, bbox: [x0, y0, x1, y1], truncated: segs2.length > arr.length };
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
function hasAddr(state) {
  const site = state.site || {};
  const filled = (a) => !!a && Object.keys(a).length > 0;
  return filled(site.addr) || site.depth_mode === "cell" || (state.slots || []).some((s) => filled(s.addr) || !!s.depth_mode);
}
var Scene = class {
  constructor(state) {
    this._state = state;
    this._contexts = null;
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
  /** Контекст адресації місця (F01): коди комірок як у розкладці з адресацією; без адресації — null (legacy-коди). */
  slotCtx(slot) {
    if (this._contexts === null) {
      this._contexts = hasAddr(this._state) ? stateContexts(this._state) : /* @__PURE__ */ new Map();
    }
    return usableContext(this._contexts.get(slot.uid || slot.id));
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
        elevation,
        this.slotCtx(slot)
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
    const types2 = variant.slot_types || [];
    if (slot && types2.length && !types2.includes(slot.template)) {
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
      for (const rect2 of rects) {
        if (satPenetration(obj.obb, rectObb(rect2.x0, rect2.y0, rect2.x1, rect2.y1)) <= eps) {
          continue;
        }
        const name = rect2.name || "";
        let message;
        if (check === "aisles_free") {
          message = `Прохід перекрито: ${obj.code} × ${name}`;
        } else if (rect2.kind === "exit") {
          message = `Вихід перекрито: ${obj.code} × ${name}`;
        } else {
          message = `Пожежний прохід перекрито: ${obj.code} × ${name}`;
        }
        issues.push(issue(check, sev, layerId, [obj.code], message, [objKey2(obj.kind, obj.id)], String(rect2.id ?? name)));
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
  const rot2 = pl.rotation || 0;
  const body = placementObb(v, pl.x, pl.y, rot2);
  const svc = serviceObb(v, pl.x, pl.y, rot2);
  const g3 = { cx: body.cx, cy: body.cy, L: v.length / 1e3, W: v.width / 1e3, a: rot2, body, svc: null };
  g3.poly = obbCorners(body);
  g3.box = obbAabb(body);
  if (svc) {
    const [ox, oy] = rotate(svc.cx - body.cx, svc.cy - body.cy, -rot2);
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
    site: { building: S.site.building, addr: S.site.addr || null, depth_mode: S.site.depth_mode || "level" },
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
    const mk = (mobile2) => h("button", { type: "button", role: "tab", [mobile2 ? "data-mtab" : "data-tab"]: p.tab, onclick: () => mobile2 ? E.setMTab(p.tab) : E.setLeftTab(p.tab) }, p.label || p.tab);
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
  const num4 = (label, key, unit, o) => fld(label, numInput(Object.assign({ value: ly[key], dis, label, set: (v) => layerEdit(() => {
    ly[key] = v;
  }) }, o)), unit);
  const frag = [];
  frag.push(h("h3", null, "Параметри шару"));
  if (dis) {
    frag.push(h("div", { class: "note lock" }, S.app.mode === "edit" ? "Параметри шарів змінює Менеджер." : lockHint(ly)));
  }
  const rect2 = boundsRect(ly.bounds);
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
        num4("Відмітка", "elevation", "м", { step: 0.1 })
      ),
      h("div", { class: "grid3" }, num4("Крок сітки", "grid_step", "м", { step: 0.05, min: 0.05 }), num4("Ширина проходів", "aisle_width", "м", { step: 0.1, min: 0 }), num4("Навант. на підлогу", "max_floor_load", "кН/м²", { step: 1, min: 0 })),
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
          ly.bounds && rect2 ? h("div", { class: "grid4" }, ["x0", "y0", "x1", "y1"].map((k) => numInput({ value: rect2[k], dis, label: k, step: 0.5, set: (v) => layerEdit(() => {
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
  const opts2 = [];
  for (const p of S.catalog) {
    for (const x of p.variants) {
      opts2.push([x.id, `${p.name} — ${x.name}`]);
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
          fld("Варіант (тип обладнання)", selectEl(opts2, pl.variant_id, (x) => {
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
  recolorCells: () => recolorCells,
  recolorMats: () => recolorMats,
  refsInRect: () => refsInRect,
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
    ink: g3("--ink"),
    unsaved: "#12a5a0",
    // бірюзовий «не збережено» (N-05)
    hl: "#f2c200"
    // підсвітка результатів пошуку (F06-02)
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
  M.dash = { normal: dash("stroke", 0.85), sel: dash("accent"), warn: dash("warn"), block: dash("block"), unsaved: dash("unsaved") };
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
  const L2 = v.length / 1e3;
  const W = v.width / 1e3;
  const H = v.height / 1e3;
  if (norm) {
    return modelBody(norm, L2, H, W, ghost);
  }
  const ang = FRONT_ANGLE[v.front_side || "s"];
  const swap = ang === 90 || ang === 270;
  const g3 = new THREE.Group();
  const b = host.buildGenericModel(genericCategory(cat), { l: swap ? W : L2, w: swap ? L2 : W, h: H }, THREE);
  if (ghost) {
    b.traverse((c) => {
      if (c.isMesh) {
        c.material = bodyMat("other", true);
      }
    });
  }
  b.rotation.y = rad(ang);
  g3.add(b);
  g3.add(boxEdge(L2, H, W, 0, H / 2, 0, ghost ? V.mat.edgeGhost : V.mat.edge));
  return g3;
}
function modelBody(m, L2, H, W, ghost) {
  const g3 = new THREE.Group();
  const o = m.obj.clone(true);
  const sz = m.size;
  o.scale.set(L2 / Math.max(sz.x, 1e-6), H / Math.max(sz.y, 1e-6), W / Math.max(sz.z, 1e-6));
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
function buildPlacementView(pl, opts2) {
  opts2 = opts2 || {};
  const v = variantOf(pl.variant_id);
  const ly = layerOf(pl.layer_id);
  if (!v || !ly) {
    return null;
  }
  const p = passportOf(pl.variant_id);
  const g3 = pGeom(pl, v);
  const ghost = opts2.ghost != null ? opts2.ghost : isGhost(ly);
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
  if (!opts2.noLabel) {
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
  if (S.hl && S.hl.codes.has(c.code)) {
    return new THREE.Color(V.col.hl);
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
function buildSlotView(s, opts2) {
  opts2 = opts2 || {};
  const ly = layerOf(s.layer_id);
  if (!ly) {
    return null;
  }
  const ghost = opts2.ghost != null ? opts2.ghost : isGhost(ly);
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
    const B2 = S.site.building;
    const huge = d.L * d.W > ZONE_HUGE * B2.length * B2.width;
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
    const stack3 = s.template === "floor_stack";
    cells.forEach((c, i) => {
      const hh = stack3 ? Math.min(c.h, 0.5) : c.h * 0.78;
      sc.set(c.l * 0.92, hh, c.w * 0.9);
      ps.set(c.lx, c.dz + (s.template === "shelf" ? 0.05 : 0) + hh / 2 + (stack3 ? 0.02 : 0.1), -c.ly);
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
  const B2 = S.site.building;
  if (!ly.bounds || ly.bounds.length < 3) {
    return { x0: 0, y0: 0, x1: B2.length, y1: B2.width };
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
  const zone2 = (x0, y0, x1, y1, color, op, lab) => {
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
    zone2(a.x0, a.y0, a.x1, a.y1, "#2e9d8f", 0.16, a.name);
  }
  for (const f of ly.fire_paths || []) {
    zone2(f.x0, f.y0, f.x1, f.y1, "#d6453d", f.kind === "exit" ? 0.2 : 0.18, f.name);
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
  const B2 = S.site.building;
  const g3 = new THREE.Group();
  g3.add(planeMesh(B2.length, B2.width, B2.length / 2, -0.01, -B2.width / 2, V.mat.floor));
  const e = new THREE.LineSegments(V.geo.boxEdges, V.mat.bld);
  e.scale.set(B2.length, B2.height, B2.width);
  e.position.set(B2.length / 2, B2.height / 2, -B2.width / 2);
  g3.add(e);
  const sx = S.site.column_grid.step_x;
  const sy = S.site.column_grid.step_y;
  if (sx > 1 && sy > 1) {
    const xs = [];
    const ys = [];
    for (let x = sx; x < B2.length - 0.01; x += sx) {
      xs.push(x);
    }
    for (let y = sy; y < B2.width - 0.01; y += sy) {
      ys.push(y);
    }
    const n = xs.length * ys.length;
    if (n > 0 && n < 2e3) {
      const im = new THREE.InstancedMesh(V.geo.box, V.mat.col, n);
      const m4 = new THREE.Matrix4();
      let i = 0;
      for (const x of xs) {
        for (const y of ys) {
          m4.compose(new THREE.Vector3(x, B2.height / 2, -y), new THREE.Quaternion(), new THREE.Vector3(0.4, B2.height, 0.4));
          im.setMatrixAt(i++, m4);
        }
      }
      g3.add(im);
    }
  }
  return g3;
}
function syncStatic() {
  const B2 = S.site.building;
  const sig = JSON.stringify([B2, S.site.column_grid, V.theme, S.site.id]);
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
var colorSig = () => `${S.ui.metric || ""}|${S.hl ? S.hl.rev || S.hl.codes.size : 0}|${S.stock ? S.stock.rev || 0 : 0}`;
function recolorCells() {
  V.colorSig = null;
  updateVisual();
}
function updateVisual() {
  if (!V.ok) {
    return;
  }
  const keys = selKeys();
  const selKey = S.sel ? objKey(S.sel.kind, S.sel.id) : null;
  const sig = colorSig();
  const recolor = V.colorSig !== sig;
  V.colorSig = sig;
  for (const [key, v] of V.views) {
    const st = S.issues.byKey.get(key);
    const lvl = st ? st.level : "normal";
    const isSel = keys.has(key);
    const unsaved = S.unsaved.has(key);
    if (v.foot) {
      v.foot.material = v.ghost ? V.mat.dashGhost : lvl === "normal" && unsaved ? V.mat.dash.unsaved : V.mat.dash[lvl] || V.mat.dash.normal;
    }
    if (v.fill) {
      v.fill.visible = !v.ghost && (lvl !== "normal" || isSel);
      v.fill.material = lvl === "normal" ? V.mat.fill.sel : V.mat.fill[lvl];
    }
    if (v.sel) {
      v.sel.visible = isSel;
    }
    if (v.cells) {
      const want = key === selKey ? S.selCell || "" : "";
      if (recolor || (v.selCode || "") !== want) {
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
    const segs2 = data.segs;
    const k = (p.unit === "m" ? 1 : 1e-3) * (p.scale || 1);
    const a = rad(p.rot_deg || 0);
    const c = Math.cos(a);
    const s = Math.sin(a);
    const pos = new Float32Array(segs2.length / 2 * 3);
    const y0 = ly.elevation + 0.04;
    for (let i = 0, j = 0; i < segs2.length; i += 2, j += 3) {
      const px = segs2[i] * k;
      const py = segs2[i + 1] * k;
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
    pointerleave: () => E.hideTip?.(),
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
  const additive = e.ctrlKey || e.metaKey;
  if (e.shiftKey && V.camMode === "plan" && e.pointerType !== "touch") {
    startBox(e, hit, additive);
    return;
  }
  if (!hit) {
    V.bg = { x: e.clientX, y: e.clientY };
    return;
  }
  if (additive) {
    E.toggleMulti(hit.ref);
    return;
  }
  const inMulti = S.multi.length > 1 && S.multi.some((r) => r.kind === hit.ref.kind && r.id === hit.ref.id);
  if (inMulti) {
    S.sel = { kind: hit.ref.kind, id: hit.ref.id };
  } else {
    E.selectObj(hit.ref);
  }
  if (hit.view.cells && !inMulti) {
    const ci = V.raycaster.intersectObject(hit.view.cells, false)[0];
    if (ci && ci.instanceId != null && hit.view.cellList[ci.instanceId]) {
      S.selCell = hit.view.cellList[ci.instanceId].code;
      updateVisual();
      E.renderCellsBox();
      const tr = $("#cellsBox tr.sel");
      if (tr) {
        tr.scrollIntoView({ block: "nearest" });
      }
      E.cellPicked?.(hit.ref.id, S.selCell, e);
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
  let group = null;
  if (inMulti) {
    group = [];
    for (const r of S.multi) {
      const rr = recOfRef(r);
      if (!rr || !canEditLayer(layerOf(rr.layer_id)) || rr.locked) {
        toast(rr && !canEditLayer(layerOf(rr.layer_id)) ? lockHint(layerOf(rr.layer_id)) : "Складний контур зони редагується у формі Odoo.", "warn");
        return;
      }
      group.push({ ref: r, rec: rr, key: objKey(r.kind, r.id), start: { x: rr.x, y: rr.y } });
    }
  }
  V.controls.enabled = false;
  try {
    V.canvas.setPointerCapture(e.pointerId);
  } catch {
  }
  V.drag = { ref: hit.ref, rec, key: objKey(hit.ref.kind, hit.ref.id), start: { x: rec.x, y: rec.y }, pt0: pt, moved: false, sx: e.clientX, sy: e.clientY, before: S.issues, elev: lyr.elevation, group };
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
  if (V.box) {
    moveBox(e);
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
  if (d.group) {
    const ddx = d.rec.x - d.start.x;
    const ddy = d.rec.y - d.start.y;
    for (const it of d.group) {
      if (it.rec === d.rec) {
        continue;
      }
      it.rec.x = rnd(it.start.x + ddx, 4);
      it.rec.y = rnd(it.start.y + ddy, 4);
      const v2 = V.views.get(it.key);
      if (v2) {
        poseView(v2, it.rec);
      }
    }
  }
  rafLive();
}
function hoverAt(e) {
  if (!V.canvas || V.drag || V.box || V.placing || V.ruler.on || V.pickMode) {
    return;
  }
  const hit = pickAt(e);
  let cell = null;
  if (hit && hit.view.cells) {
    const ci = V.raycaster.intersectObject(hit.view.cells, false)[0];
    cell = ci && ci.instanceId != null ? hit.view.cellList[ci.instanceId] || null : null;
  }
  const key = hit ? objKey(hit.ref.kind, hit.ref.id) : null;
  const hk2 = key ? key + "|" + (cell ? cell.code : "") : null;
  if (hk2 === V.hoverKey) {
    return;
  }
  V.hoverKey = hk2;
  const rec = hit && recOfRef(hit.ref);
  V.canvas.style.cursor = hit ? canEditLayer(layerOf(rec.layer_id)) ? "move" : "pointer" : "";
  const el = $("#hoverName");
  if (el) {
    el.textContent = rec ? (rec.code || rec.code_prefix) + (rec.name ? " · " + rec.name : rec.params && rec.params.title ? " · " + rec.params.title : "") : "—";
  }
  if (rec) {
    E.showTip?.({ x: e.clientX, y: e.clientY, rec, kind: hit.ref.kind, cell });
  } else {
    E.hideTip?.();
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
  if (V.box) {
    finishBox(e);
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
  const items = d.group || [d];
  const after = runLive();
  const nb = items.flatMap((it) => newBlocks(d.before, after, it.key));
  if (nb.length) {
    for (const it of items) {
      it.rec.x = it.start.x;
      it.rec.y = it.start.y;
      const view = V.views.get(it.key);
      if (view) {
        poseView(view, it.rec);
      }
    }
    S.issues = runLive();
    updateVisual();
    E.syncPropsValues();
    E.renderChecksBlock();
    toast("Заблоковано: " + nb[0].msg + (items.length > 1 ? ". Групу повернуто на місце." : ". Об’єкт повернуто на місце."), "err");
    return;
  }
  for (const it of items) {
    if (it.ref.kind === "placement") {
      assignSlot(it.rec);
    }
  }
  if (items.some((it) => it.start.x !== it.rec.x || it.start.y !== it.rec.y)) {
    E.commit({});
  } else {
    S.issues = after;
    updateVisual();
  }
  const first = items.map((it) => S.issues.byKey.get(it.key)).find((st) => st && st.level !== "block");
  if (first) {
    toast(first.items[0].msg, "warn");
  }
}
function startBox(e, hit, add) {
  V.box = { x0: e.clientX, y0: e.clientY, x1: e.clientX, y1: e.clientY, add, moved: false, hit };
  V.controls.enabled = false;
  try {
    V.canvas.setPointerCapture(e.pointerId);
  } catch {
  }
}
function moveBox(e) {
  const b = V.box;
  b.x1 = e.clientX;
  b.y1 = e.clientY;
  if (!b.moved && Math.hypot(b.x1 - b.x0, b.y1 - b.y0) < 5) {
    return;
  }
  b.moved = true;
  if (!b.el) {
    b.el = h("div", { class: "s3-box", style: { position: "absolute", pointerEvents: "none", border: "1px dashed var(--accent)", background: "color-mix(in srgb, var(--accent) 14%, transparent)", zIndex: "3" } });
    $("#vp").append(b.el);
  }
  const r = $("#vp").getBoundingClientRect();
  Object.assign(b.el.style, { left: Math.min(b.x0, b.x1) - r.left + "px", top: Math.min(b.y0, b.y1) - r.top + "px", width: Math.abs(b.x1 - b.x0) + "px", height: Math.abs(b.y1 - b.y0) + "px" });
}
function refsInRect(rect2) {
  const cv = V.canvas.getBoundingClientRect();
  const out = [];
  const q = new THREE.Vector3();
  for (const v of V.views.values()) {
    if (v.layerId !== S.ui.layer || !v.g || !v.g.poly) {
      continue;
    }
    const ly = layerOf(v.layerId);
    if (!ly || !isLayerVisible(ly) || OVERLAY_KINDS.includes(ly.kind) || v.tpl === "building") {
      continue;
    }
    const el = ly.elevation || 0;
    const inside = v.g.poly.every(([px, py]) => {
      q.set(px, el, -py).project(V.camera);
      const cx = cv.left + (q.x + 1) / 2 * cv.width;
      const cy = cv.top + (1 - q.y) / 2 * cv.height;
      return cx >= rect2.x0 && cx <= rect2.x1 && cy >= rect2.y0 && cy <= rect2.y1;
    });
    if (inside) {
      out.push({ kind: v.kind, id: v.id });
    }
  }
  return out;
}
function finishBox(e) {
  const b = V.box;
  V.box = null;
  V.controls.enabled = true;
  if (b.el) {
    b.el.remove();
  }
  if (!b.moved) {
    if (b.hit) {
      if (b.add) {
        E.toggleMulti(b.hit.ref);
      } else {
        E.selectObj(b.hit.ref);
      }
    } else if (!b.add) {
      E.selectObj(null);
    }
    return;
  }
  const rect2 = { x0: Math.min(b.x0, b.x1), y0: Math.min(b.y0, b.y1), x1: Math.max(b.x0, b.x1), y1: Math.max(b.y0, b.y1) };
  E.boxSelect(refsInRect(rect2), b.add);
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
  recolorCells,
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
  E.undoRecord?.();
  E.refreshUnsaved?.();
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
function commit(o) {
  if (o && o.label) {
    E.undoLabel?.(o.label);
  }
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
  S.multi = [];
  S.hl = null;
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
  if (!keep) {
    S.stock = null;
  }
  if (keep) {
    E.undoRebase?.();
  } else {
    E.undoReset?.();
  }
  E.markSaved?.();
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
    E.undoReset?.();
    toast(`Чернетку повернуто до версії ${n}.`);
  } catch (e) {
    toast(e.message || "Не вдалося повернути чернетку.", "err");
  }
}
async function publish() {
  try {
    await ctx.adapter.publish({
      onClose: () => {
        E.undoReset?.();
        return reload();
      },
      state: S
    });
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
  for (const [key, hk2] of registries.hotkeys.getEntries()) {
    if (typing && !hk2.typing) {
      continue;
    }
    if ((e.ctrlKey || e.metaKey) && !hk2.ctrl) {
      continue;
    }
    if (e.altKey && !hk2.alt) {
      continue;
    }
    if (hk2.ctrl && !(e.ctrlKey || e.metaKey)) {
      continue;
    }
    const hit = hk2.match ? hk2.match(e) : (hk2.code ? e.code === hk2.code : e.key === hk2.key) && (hk2.shift == null || hk2.shift === e.shiftKey);
    if (!hit || hk2.when && !hk2.when(e)) {
      continue;
    }
    try {
      if (hk2.run(e) !== false) {
        return;
      }
    } catch (err) {
      console.error(`Гаряча клавіша «${key}»:`, err);
    }
  }
}
function registerBuiltinHotkeys() {
  const add = (key, hk2, sequence) => registries.hotkeys.add(key, hk2, { sequence, force: true });
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
    if (status === "saved") {
      E.markSaved?.();
    }
    E.renderSaveState();
    E.syncSaveAll?.();
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
      E.undoReset?.();
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
  for (const fn of E.lifecycle.mount) {
    try {
      fn();
    } catch (e) {
      console.error("mount hook:", e);
    }
  }
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
  for (const fn of E.lifecycle.unmount) {
    try {
      fn();
    } catch (e) {
      console.error("unmount hook:", e);
    }
  }
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
function rectToPolygon(cx, cy, l, w, rot2) {
  const r = rot2 * Math.PI / 180;
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
    note: s.note || "",
    // S1 (MERGE §3.3): тип місця, власна адресація й глибина локацій; порожні значення — «успадкувати» (null)
    type_id: s.type_id ?? null,
    addr: s.addr && Object.keys(s.addr).length ? clone(s.addr) : null,
    depth_mode: s.depth_mode || null
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
  const out = {
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
      settings,
      // S1: адресація площадки (R-22), ієрархія й глибина локацій; бібліотека типів і пресетів (API-03 `types`, `presets`)
      addr: clone(site.addr || {}),
      loc_tree: site.loc_tree || "flat",
      depth_mode: site.depth_mode || "level",
      parse_rules: clone(site.parse_rules || {})
      // S4: правила розбору кодів і лоток «Не розміщено» (F10)
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
  Object.defineProperty(out.site, "library", { value: { types: clone(data.types || []), presets: clone(data.presets || []) }, writable: true, configurable: true, enumerable: false });
  return out;
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
    overrides: clone(s.overrides || {}),
    type_id: s.type_id ?? null,
    addr: s.addr && Object.keys(s.addr).length ? clone(s.addr) : {},
    depth_mode: s.depth_mode || null
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
    this.capabilities = { publish: true, check: true, library: true, ...o.capabilities || {} };
    Object.assign(this.capabilities, { stock: true, render: true, ...o.capabilities || {} });
    this.serverRenumber = true;
    this.rpc = o.rpc;
    this.orm = o.orm;
    this.action = o.action;
    this._uploadModel = o.uploadModel;
    this.retryDelays = o.retryDelays || [2e3, 5e3, 15e3];
    this.siteId = null;
    Object.assign(this.capabilities, { storage: true, putaway: true, rollback: true });
    Object.assign(this.capabilities, { odoo_import: true, files: true });
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
    for (let guard3 = 0; guard3 < 100 && this.pending.size; guard3++) {
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
        const choice2 = await this.onConflict({
          model: bad.entry.model,
          uid: bad.entry.uid,
          current: res.current,
          message: res.message
        });
        if (choice2 === "mine") {
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
  /**
   * Адресація площадки (S1): addr, depth_mode, loc_tree — свій маршрут `/site/addr` (API-04 і ORM площадку не пишуть для проєктувальника);
   * `opts.renumber`: "new" — закріпити номери вже опублікованих, "all" — перенумерувати все (лише менеджер).
   */
  async saveAddr(vals, { renumber = "new" } = {}) {
    const res = await this._call("/f3d/constructor/site/addr", { site_id: this.siteId, renumber, ...vals });
    if (!res.ok) {
      throw new StoreError(res.code, res.message);
    }
    return { pinned: res.pinned, reload: true };
  }
  /**
   * Бібліотека типів і пресетів (API-11): `{op: "list"}` → {types, presets}; `{op: "save", kind, id?, vals}` → {record};
   * `{op: "delete", kind, id}` → {id}.
   */
  async library(req) {
    const res = await this._call("/f3d/constructor/library", req);
    if (!res.ok) {
      throw new StoreError(res.code, res.message);
    }
    return res;
  }
  /**
   * Залишки по кодах (API-13 `/stock/state`, S3): `{codes?, days?, detail?}` → {at, days, demo: false, truncated, codes: {код: {qty, reserved, fill,
   * in_date, age_days, moves, min, max, capacity, top_product, location_id?, detail?}}}; `detail` — рядки залишків, рух, правила для картки;
   * великий склад віддається пачками: `truncated` + `next` → наступний виклик з `offset: next`.
   */
  async stock({ codes = null, days = null, detail = false, offset = 0 } = {}) {
    const res = await this._call("/f3d/constructor/stock/state", { site_id: this.siteId, codes, days, detail, ...offset ? { offset } : {} });
    if (!res.ok) {
      throw new StoreError(res.code, res.message);
    }
    return res;
  }
  /** Пошук «де лежить» (API-14 `/stock/find`): `{q, mode}` → {hits: [{code, items: [{product, ref, qty, lot, package}]}]}. */
  async find({ q, mode = "any" } = {}) {
    const res = await this._call("/f3d/constructor/stock/find", { site_id: this.siteId, q, mode });
    if (!res.ok) {
      throw new StoreError(res.code, res.message);
    }
    return res;
  }
  /** Файл від сервера (API-19): `kind` — labels_pdf | table_xlsx | plan_pdf | spec_pdf → {filename, mimetype, content (base64)}. */
  async render(kind, payload) {
    const res = await this._call(`/f3d/constructor/render/${kind}`, { site_id: this.siteId, ...payload });
    if (!res.ok) {
      throw new StoreError(res.code, res.message);
    }
    return res;
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
  async uploadModel(variantId, payload, opts2 = {}) {
    if (!this._uploadModel) {
      throw new StoreError("not_supported", "Завантаження моделей у цьому хості не налаштоване.");
    }
    return await this._uploadModel(variantId, payload, opts2);
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
  // --- S4: структура з Odoo й файли (API-16, API-20; F10, F11, F02-09/12) ---
  /**
   * Стрічка локацій складу (API-16 `/odoo/locations`): `{op: "feed"}` (за замовчуванням) → {feed: {root, warehouse, locations: [{id, code, name,
   * parent, parent_id, usage, barcode, qty, active}], truncated, next}}; `{op: "sync"}` → те саме + {diff: {appeared, disappeared, renamed, moved},
   * baseline: "created"|"existing"}; `{op: "baseline"}` — база порівняння (`site.odoo_baseline_id`) стає нинішньою стрічкою.
   */
  async locations({ op = "feed", ...rest } = {}) {
    const res = await this._call("/f3d/constructor/odoo/locations", { site_id: this.siteId, op, ...rest });
    if (!res.ok) {
      throw new StoreError(res.code, res.message);
    }
    return res;
  }
  /** Правила розбору кодів і лоток «Не розміщено» площадки (`site.parse_rules`): окремий маршрут, бо ORM площадку проєктувальнику не пише. */
  async saveParseRules(rules) {
    const res = await this._call("/f3d/constructor/odoo/rules", { site_id: this.siteId, parse_rules: rules });
    if (!res.ok) {
      throw new StoreError(res.code, res.message);
    }
    return res;
  }
  /** Розбір таблиці на сервері (API-20 `/parse/table`): `{filename, bytes (Uint8Array), sheet?}` → {format, sheets?, rows}. */
  async parseTable({ filename, bytes, sheet = 0 }) {
    let bin = "";
    for (let i = 0; i < bytes.length; i += 32768) {
      bin += String.fromCharCode.apply(null, bytes.subarray(i, i + 32768));
    }
    const res = await this._call("/f3d/constructor/parse/table", { site_id: this.siteId, filename, content: btoa(bin), sheet });
    if (!res.ok) {
      throw new StoreError(res.code, res.message);
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

// core/constructor/shape_forms.js
var levelCount = (p, tpl) => tpl === "shelf" ? p.shelves : p.levels;
var bayCount = (p, tpl) => tpl === "pallet_rack" ? p.bays : tpl === "cantilever" ? p.arms : p.sections;
var baseH = (p, tpl) => tpl === "shelf" ? p.cell_h : p.level_height;
function levelTops(p, tpl) {
  const n = levelCount(p, tpl);
  const heights = p.level_heights || Array(n).fill(baseH(p, tpl));
  const out = [];
  let z = p.bottom_on_floor === false ? 0.15 : 0;
  for (const h2 of heights) {
    z += h2;
    out.push(z);
  }
  return out;
}
function sideBlocks(p, d, tpl) {
  if (!p.double_sided) {
    return [{ y0: -d.W / 2, y1: d.W / 2 }];
  }
  const one = tpl === "pallet_rack" ? p.depth * (p.deep ?? 1) : tpl === "cantilever" ? p.arm_length : p.cell_d;
  return [
    { y0: -d.W / 2, y1: -d.W / 2 + one },
    { y0: d.W / 2 - one, y1: d.W / 2 }
  ];
}
function rack(p, d, sg, tpl) {
  const n = bayCount(p, tpl);
  const pitch = tpl === "pallet_rack" ? p.bay_width : tpl === "cantilever" ? d.L / n : p.cell_w;
  const gx = p.gap_x ?? 0;
  const tops = levelTops(p, tpl);
  for (const { y0, y1 } of sideBlocks(p, d, tpl)) {
    for (let i = 0; i < n; i++) {
      const xa = -d.L / 2 + i * (pitch + gx);
      const xb = xa + pitch;
      for (const x of [xa, xb]) {
        for (const y of [y0, y1]) {
          sg([x, y, 0], [x, y, d.H]);
        }
        sg([x, y0, d.H], [x, y1, d.H]);
      }
      for (const z of tops) {
        for (const y of [y0, y1]) {
          sg([xa, y, z], [xb, y, z]);
        }
      }
    }
  }
}
function rollRack(p, d, sg, tpl) {
  const n = bayCount(p, tpl);
  const pitch = d.L / n;
  const tops = levelTops(p, tpl);
  for (const { y0, y1 } of sideBlocks(p, d, tpl)) {
    const back = p.double_sided && y0 > -d.W / 2 ? y1 : y0;
    const front = back === y0 ? y1 : y0;
    for (let i = 0; i <= n; i++) {
      const x = -d.L / 2 + i * pitch;
      sg([x, back, 0], [x, back, d.H]);
      for (const z of tops) {
        sg([x, back, z], [x, front, z]);
        sg([x, front, z], [x, front, z + 0.15]);
      }
    }
  }
}
function stack(p, d, sg) {
  const rows = p.rows || 1;
  const cols = p.cols || 1;
  const gx = p.gap_x ?? 0;
  const gy = p.gap_y ?? 0;
  const cl = p.cell_l ?? d.L;
  const cw = p.cell_w ?? d.W;
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const x0 = -d.L / 2 + c * (cl + gx);
      const y0 = -d.W / 2 + r * (cw + gy);
      rect(sg, x0, y0, x0 + cl, y0 + cw, 0.02);
      rect(sg, x0, y0, x0 + cl, y0 + cw, d.H);
      for (const [x, y] of [[x0, y0], [x0 + cl, y0], [x0 + cl, y0 + cw], [x0, y0 + cw]]) {
        sg([x, y, 0.02], [x, y, d.H]);
      }
    }
  }
}
var rect = (sg, x0, y0, x1, y1, z) => {
  sg([x0, y0, z], [x1, y0, z]);
  sg([x1, y0, z], [x1, y1, z]);
  sg([x1, y1, z], [x0, y1, z]);
  sg([x0, y1, z], [x0, y0, z]);
};
function zone(p, d, sg) {
  const z = 0.03;
  rect(sg, -d.L / 2, -d.W / 2, d.L / 2, d.W / 2, z);
  const k = Math.min(d.L, d.W) * 0.12;
  for (const [sx, sy] of [[-1, -1], [1, -1], [1, 1], [-1, 1]]) {
    const x = sx * d.L / 2;
    const y = sy * d.W / 2;
    sg([x, y, z], [x - sx * k, y, z + 0]);
    sg([x, y, z], [x, y - sy * k, z]);
  }
  sg([-d.L / 2, -d.W / 2, z], [d.L / 2, d.W / 2, z]);
  sg([-d.L / 2, d.W / 2, z], [d.L / 2, -d.W / 2, z]);
}
function fence(p, d, sg) {
  const hx = d.L / 2;
  const hy = d.W / 2;
  rect(sg, -hx, -hy, hx, hy, 0.02);
  rect(sg, -hx, -hy, hx, hy, d.H);
  rect(sg, -hx, -hy, hx, hy, d.H / 2);
  const nx = Math.max(1, Math.round(d.L));
  const ny = Math.max(1, Math.round(d.W));
  for (let i = 0; i <= nx; i++) {
    const x = -hx + i * d.L / nx;
    for (const y of [-hy, hy]) {
      sg([x, y, 0.02], [x, y, d.H]);
    }
  }
  for (let j = 1; j < ny; j++) {
    const y = -hy + j * d.W / ny;
    for (const x of [-hx, hx]) {
      sg([x, y, 0.02], [x, y, d.H]);
    }
  }
}
var ellipse = (sg, rx, ry, z, steps = 24) => {
  for (let i = 0; i < steps; i++) {
    const a = i / steps * Math.PI * 2;
    const b = (i + 1) / steps * Math.PI * 2;
    sg([Math.cos(a) * rx, Math.sin(a) * ry, z], [Math.cos(b) * rx, Math.sin(b) * ry, z]);
  }
};
function cylinder(p, d, sg) {
  const rx = d.L / 2;
  const ry = d.W / 2;
  ellipse(sg, rx, ry, 0.02);
  ellipse(sg, rx, ry, d.H);
  for (const [x, y] of [[rx, 0], [-rx, 0], [0, ry], [0, -ry]]) {
    sg([x, y, 0.02], [x, y, d.H]);
  }
  ellipse(sg, rx, ry, d.H * 0.5, 16);
}
function cabinet(p, d, sg) {
  const hx = d.L / 2;
  const hy = d.W / 2;
  rect(sg, -hx, -hy, hx, hy, 0.02);
  rect(sg, -hx, -hy, hx, hy, d.H);
  for (const [x, y] of [[-hx, -hy], [hx, -hy], [hx, hy], [-hx, hy]]) {
    sg([x, y, 0.02], [x, y, d.H]);
  }
  sg([0, -hy, 0.02], [0, -hy, d.H]);
  for (let i = 1; i <= 4; i++) {
    const z = d.H - i * d.H / 12;
    sg([-hx * 0.8, -hy, z], [hx * 0.8, -hy, z]);
  }
}
function mobile(p, d, sg) {
  const hx = d.L / 2;
  const hy = d.W / 2;
  const base2 = Math.min(0.12, d.H * 0.2);
  rect(sg, -hx, -hy, hx, hy, base2);
  rect(sg, -hx, -hy, hx, hy, d.H);
  for (const [x, y] of [[-hx, -hy], [hx, -hy], [hx, hy], [-hx, hy]]) {
    sg([x, y, base2], [x, y, d.H]);
    sg([x, y, 0], [x, y, base2]);
  }
  sg([-hx, 0, d.H * 0.5], [hx, 0, d.H * 0.5]);
}
function gate(p, d, sg) {
  const hx = d.L / 2;
  sg([-hx, 0, 0], [-hx, 0, d.H]);
  sg([hx, 0, 0], [hx, 0, d.H]);
  sg([-hx, 0, d.H], [hx, 0, d.H]);
  sg([-hx, -d.W / 2, 0.02], [hx, -d.W / 2, 0.02]);
  sg([-hx, d.W / 2, 0.02], [hx, d.W / 2, 0.02]);
  sg([-hx, -d.W / 2, 0.02], [-hx, d.W / 2, 0.02]);
  sg([hx, -d.W / 2, 0.02], [hx, d.W / 2, 0.02]);
}
var FORMS = { rack, roll_rack: rollRack, stack, zone, fence, cylinder, cabinet, mobile, gate };
var FORM_KEYS = Object.keys(FORMS);
var DEFAULT_FORM = { pallet_rack: "rack", shelf: "rack", cantilever: "roll_rack", floor_stack: "stack", floor_spot: "zone" };
var NEW_PARAMS = ["deep", "gap_x", "gap_y", "double_sided", "level_heights", "bottom_on_floor", "beam_th"];
function runForm(form, tpl, p, d, out) {
  const fn = FORMS[form];
  if (!fn) {
    return false;
  }
  fn(p, d, (a, b) => out.push(a[0], a[2], -a[1], b[0], b[2], -b[1]), tpl);
  return true;
}
function frameFor(tpl, p, d, base2) {
  const out = [];
  const form = p.shape || (NEW_PARAMS.some((k) => p[k] != null) ? DEFAULT_FORM[tpl] : "");
  if (form && runForm(form, tpl, p, d, out)) {
    return out;
  }
  return base2 ? base2.frame(p, d) : [];
}
for (const tpl of ["pallet_rack", "shelf", "cantilever", "floor_stack", "floor_spot"]) {
  const base2 = registries.shapes.get(tpl, null);
  registries.shapes.add(tpl, { frame: (p, d) => frameFor(tpl, p, d, base2) }, { force: true });
}
for (const key of FORM_KEYS) {
  registries.shapes.add("form:" + key, { frame: (p, d) => {
    const out = [];
    runForm(key, "floor_spot", p, d, out);
    return out;
  } }, { force: true });
}
function typeSegments(type) {
  const tpl = type.template || "floor_spot";
  const params = type.template ? { ...type.params || {}, ...type.shape ? { shape: type.shape } : {} } : { length: type.params?.width || 3.5, width: 0.3, height: type.params?.height || 4, shape: "gate" };
  const p = normalizeParams(tpl, params);
  const fp = footprint(tpl, params);
  const d = { L: fp.l, W: fp.w, H: slotHeight({ template: tpl, params: p }) };
  const form = p.shape || DEFAULT_FORM[tpl];
  const segs2 = [];
  const fn = FORMS[form];
  if (fn) {
    fn(p, d, (a, b) => segs2.push([a, b]), tpl);
  }
  if (!segs2.length && SLOT_TEMPLATES[tpl]) {
    FORMS.rack(p, d, (a, b) => segs2.push([a, b]), tpl);
  }
  return { segs: segs2, d };
}
function typeSvg(type, w = 160, h2 = 110) {
  const { segs: segs2, d } = typeSegments(type);
  const proj = ([x, y, z]) => [x + 0.5 * y, z + 0.5 * y];
  const pts = segs2.flatMap(([a, b]) => [proj(a), proj(b)]);
  if (!pts.length) {
    return "";
  }
  const xs = pts.map((q) => q[0]);
  const ys = pts.map((q) => q[1]);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const k = Math.min((w - 12) / Math.max(maxX - minX, 0.1), (h2 - 12) / Math.max(maxY - minY, 0.1));
  const f = (q) => [6 + (q[0] - minX) * k, h2 - 6 - (q[1] - minY) * k];
  const lines = segs2.map(([a, b]) => {
    const [x1, y1] = f(proj(a));
    const [x2, y2] = f(proj(b));
    return `<line x1="${x1.toFixed(1)}" y1="${y1.toFixed(1)}" x2="${x2.toFixed(1)}" y2="${y2.toFixed(1)}"/>`;
  }).join("");
  return `<svg viewBox="0 0 ${w} ${h2}" width="${w}" height="${h2}" role="img" aria-label="${type.name}" fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="round" data-dims="${d.L.toFixed(2)}x${d.W.toFixed(2)}x${d.H.toFixed(2)}">${lines}</svg>`;
}

// core/constructor/addr.js
var SEG_LABELS = { zone: "Зона", row: "Ряд", bay: "Секція", level: "Ярус", pos: "Позиція" };
var SEG_KINDS = [
  ["num", "Цифри"],
  ["alpha", "Букви"]
];
var DIR_LABELS = {
  row_from: { up: "Вгору (+Y)", down: "Вниз (−Y)", right: "Праворуч (+X)", left: "Ліворуч (−X)" },
  row_mode: { seq: "Підряд", snake: "Змійкою" },
  bay_dir: { ltr: "Зліва направо", rtl: "Справа наліво", odd_even: "Чет/непарні по сторонах проходу" },
  level_dir: { up: "Знизу вгору", down: "Зверху вниз" },
  depth_mode: { level: "Ярус", cell: "Комірка (ярус ділиться)" },
  loc_tree: { flat: "Плоско (ім'я = код)", row: "Ряд (віртуальна локація)", section: "Секція (віртуальна локація)" }
};
var opts = (keys, labels) => keys.map((k) => [k, labels[k]]);
var ROW_SLOTS = ["pallet_rack", "cantilever", "shelf", "floor_stack", "floor_spot"];
var isRowSlot = (s) => ROW_SLOTS.includes(s.template);
var hasKeys = (a) => !!a && Object.keys(a).length > 0;
var slotDict = (s) => ({
  uid: s.id,
  id: s.id,
  layer_id: s.layer_id,
  template: s.template,
  code_prefix: s.code_prefix,
  x: s.x,
  y: s.y,
  rotation: s.rotation || 0,
  params: s.params,
  polygon: s.locked ? s.polygon : null,
  addr: s.addr || null,
  depth_mode: s.depth_mode || null
});
var memo = { sig: "", ctx: null };
function anyAddressing() {
  const site = S.site || {};
  const own = safeNormalize(site.addr);
  if ("tpl" in own || site.depth_mode === "cell") {
    return true;
  }
  return S.slots.some((x) => hasKeys(x.addr) || x.depth_mode);
}
function contextsOf(slots, siteAddr, siteDepth) {
  const sig = JSON.stringify([
    siteAddr || null,
    siteDepth || null,
    slots.map((s) => [s.id, s.layer_id, s.template, s.x, s.y, s.rotation || 0, s.addr || null, s.depth_mode || null, s.template === "zone" ? [s.params.length, s.params.width, s.polygon || null] : 0])
  ]);
  if (memo.sig !== sig) {
    memo = { sig, ctx: addressContext(slots.map(slotDict), siteAddr, siteDepth || "level") };
  }
  return memo.ctx;
}
function contextOf(s) {
  if (!S.site || !S.sIdx || !S.sIdx.has(s.id) || !anyAddressing()) {
    return null;
  }
  const ctx2 = contextsOf(S.slots, S.site.addr, S.site.depth_mode).get(s.id);
  return ctx2 && (ctx2.addr || ctx2.depth_mode === "cell") ? ctx2 : null;
}
setContextResolver(contextOf);
function sceneCodes({ siteAddr = S.site?.addr, siteDepth = S.site?.depth_mode, patch = null } = {}) {
  const slots = patch ? S.slots.map((s) => patch(s) || s) : S.slots;
  const ctxs = addressContext(slots.map(slotDict), siteAddr, siteDepth || "level");
  const out = /* @__PURE__ */ new Map();
  for (const s of slots) {
    if (s.template === "zone") {
      continue;
    }
    const ctx2 = ctxs.get(s.id);
    const useCtx = ctx2 && (ctx2.addr || ctx2.depth_mode === "cell") ? ctx2 : null;
    try {
      out.set(s.id, generateCells(s.template, s.code_prefix || "", s.x, s.y, s.rotation || 0, s.params, null, 0, useCtx).map((c) => c.code));
    } catch {
      out.set(s.id, []);
    }
  }
  return out;
}
var labelOfSlot = (id) => (S.sIdx.get(id) || {}).code_prefix || id;
function previewScene(o = {}) {
  const now = sceneCodes();
  const next = sceneCodes(o);
  const ids = [...next.keys()];
  const pv = preview(
    ids.flatMap((id) => next.get(id)),
    ids.flatMap((id) => now.get(id) || [])
  );
  pv.conflicts = conflicts(next);
  pv.slots = ids.length;
  return pv;
}
function rowNumberOf(s) {
  if (!S.sIdx || !S.sIdx.has(s.id)) {
    return null;
  }
  const ctx2 = contextsOf(S.slots, S.site?.addr, S.site?.depth_mode).get(s.id);
  return ctx2 ? ctx2.row ?? ctx2.spot ?? null : null;
}
function fromAddr(addr, depthMode) {
  const { zone_code: zoneCode, row_no: rowNo, legacy, ...rest } = safeNormalize(addr);
  return {
    mode: legacy ? "legacy" : "tpl" in rest ? "own" : "inherit",
    addr: "tpl" in rest ? clone(rest) : normalizeAddr({ tpl: PRESETS.zone_row_bay_level.tpl }),
    zone_code: zoneCode || "",
    row_no: rowNo || null,
    depth_mode: depthMode || ""
  };
}
function toAddr(st, { site = false, zone: zone2 = false, row = false } = {}) {
  let out = {};
  if (st.mode === "own") {
    out = { ...st.addr };
  } else if (st.mode === "legacy" && !site) {
    out = { legacy: true };
  }
  if (zone2 && st.zone_code) {
    out.zone_code = st.zone_code;
  }
  if (row && st.row_no) {
    out.row_no = st.row_no;
  }
  return normalizeAddr(out);
}
function addrEditor(o) {
  const { st, dis } = o;
  const box = h("div", { class: "fcol", "data-role": "addr-editor" });
  const change = () => {
    let err = null;
    try {
      if (st.mode === "own") {
        normalizeAddr(st.addr);
      }
    } catch (e) {
      if (!(e instanceof AddrError)) {
        throw e;
      }
      err = e.message;
    }
    o.onChange(err);
  };
  const draw = () => {
    const modes = [
      ...o.mode === "site" ? [] : [["inherit", "Успадкувати"]],
      ["legacy", "Як зараз (ПРЕФІКС-B01-L1)"],
      ["own", "Власний шаблон"]
    ];
    const kids = [
      fld(
        o.mode === "site" ? "Адресація кодів" : "Власні налаштування",
        selectEl(modes, st.mode, (v) => {
          st.mode = v;
          draw();
          change();
        }, dis, "Режим адресації")
      )
    ];
    if (st.mode === "own") {
      const a = st.addr;
      const presetKeys = Object.keys(PRESETS).filter((k) => k !== "legacy");
      kids.push(
        fld(
          "Пресет шаблону",
          selectEl([["", "—"], ...presetKeys.map((k) => [k, PRESET_LABELS[k]])], "", (v) => {
            if (v) {
              st.addr = normalizeAddr(PRESETS[v]);
              draw();
              change();
            }
          }, dis, "Пресет шаблону")
        ),
        fld("Шаблон: слова через пробіл, сегменти {prefix} {zone} {row} {bay} {level} {pos}", textInput({ value: a.tpl, dis, label: "Шаблон", f: "addr-tpl", set: (v) => {
          a.tpl = v;
          change();
        } })),
        h(
          "div",
          { class: "grid2" },
          fld("Роздільник (до 3 символів)", textInput({ value: a.sep, dis, label: "Роздільник", f: "addr-sep", set: (v) => {
            a.sep = v;
            change();
          } })),
          fld("Ряди від входу", selectEl(opts(ROW_FROM, DIR_LABELS.row_from), a.row_from, (v) => {
            a.row_from = v;
            change();
          }, dis, "Напрям рядів"))
        ),
        h(
          "div",
          { class: "grid2" },
          fld("Секції", selectEl(opts(BAY_DIRS, DIR_LABELS.bay_dir), a.bay_dir, (v) => {
            a.bay_dir = v;
            change();
          }, dis, "Напрям секцій")),
          fld("Ряди", selectEl(opts(ROW_MODES, DIR_LABELS.row_mode), a.row_mode, (v) => {
            a.row_mode = v;
            change();
          }, dis, "Режим рядів"))
        ),
        fld("Яруси", selectEl(opts(LEVEL_DIRS, DIR_LABELS.level_dir), a.level_dir, (v) => {
          a.level_dir = v;
          change();
        }, dis, "Напрям ярусів")),
        h("div", { class: "small muted" }, "Сегмент: вид · ширина (ведучі нулі) · початкове значення"),
        ...SEGMENT_KEYS.map(
          (k) => h(
            "div",
            { class: "grid3", "data-seg": k },
            fld(SEG_LABELS[k], selectEl(SEG_KINDS, a.seg[k].kind, (v) => {
              a.seg[k].kind = v;
              if (v === "alpha" && a.seg[k].start < 1) {
                a.seg[k].start = 1;
              }
              draw();
              change();
            }, dis, SEG_LABELS[k] + ": вид")),
            fld("Ширина", numInput({ value: a.seg[k].width, dis, min: 1, max: 8, step: 1, int: true, label: SEG_LABELS[k] + ": ширина", set: (v) => {
              a.seg[k].width = v;
              change();
            } })),
            fld("Початок", numInput({ value: a.seg[k].start, dis, min: a.seg[k].kind === "alpha" ? 1 : 0, max: 999, step: 1, int: true, label: SEG_LABELS[k] + ": початок", set: (v) => {
              a.seg[k].start = v;
              change();
            } }))
          )
        )
      );
    }
    if (o.mode === "zone") {
      kids.push(fld("Код зони замість номера", textInput({ value: st.zone_code, dis, label: "Код зони", f: "addr-zone-code", set: (v) => {
        st.zone_code = v.trim();
        change();
      } }), "до 8 символів"));
    }
    if (o.mode === "slot" && o.row) {
      kids.push(fld("Закріплений номер", numInput({ value: st.row_no, dis, min: 1, max: 9999, step: 1, int: true, label: "Номер ряду", set: (v) => {
        st.row_no = v;
        change();
      } }), "порожньо — за геометрією"));
    }
    kids.push(
      fld(
        "Остання локація в Odoo",
        selectEl([["", o.mode === "site" ? "Ярус" : "Як у зони / площадки"], ...opts(DEPTH_MODES, DIR_LABELS.depth_mode).filter(([k]) => o.mode !== "site" || k !== "level")], st.depth_mode || "", (v) => {
          st.depth_mode = v;
          change();
        }, dis, "Глибина локацій")
      )
    );
    box.replaceChildren(...K(kids));
  };
  draw();
  return box;
}
var hasConflicts = (pv) => Object.keys(pv.conflicts).length > 0 || pv.too_long.length > 0;
function previewBlock(compute) {
  const box = h("div", { class: "note", "data-role": "addr-preview" });
  const render2 = (err) => {
    let pv = null;
    let msg = err;
    if (!msg) {
      try {
        pv = compute();
      } catch (e) {
        msg = e.message || String(e);
      }
    }
    if (msg) {
      box.className = "note err";
      box.replaceChildren(msg);
      return false;
    }
    const dups = Object.entries(pv.conflicts);
    box.className = "note" + (hasConflicts(pv) ? " err" : "");
    box.replaceChildren(
      ...K(
        h("div", { class: "h3" }, "Попередній перегляд"),
        h("div", { class: "small", "data-role": "addr-first" }, pv.first.length ? pv.first.join(" · ") : "Кодів немає"),
        pv.last ? h("div", { class: "small muted", "data-role": "addr-last" }, `Останній: ${pv.last} · усього ${fmtInt(pv.total)} кодів у ${fmtInt(pv.slots)} місцях`) : null,
        h("div", { class: "small", "data-role": "addr-changed" }, pv.changed ? `Зміниться кодів: ${fmtInt(pv.changed)} (потрібні нові етикетки)` : "Коди не змінюються"),
        pv.too_long.length ? h("div", { class: "small", style: { color: "var(--block)" } }, `Код довший за 32 символи: ${pv.too_long[0]}`) : null,
        dups.length ? h(
          "div",
          { class: "small", "data-role": "addr-dups" },
          h("div", { style: { color: "var(--block)" } }, `Повтори кодів: ${dups.length} — зберегти не можна`),
          dups.slice(0, 5).map(
            ([code, ids]) => h("div", null, code + " — ", ids.map((id, i) => h("a", { href: "#", style: { marginRight: "6px" }, onclick: (e) => {
              e.preventDefault();
              E.selectObj({ kind: "slot", id });
            } }, labelOfSlot(id) + (i < ids.length - 1 ? "," : ""))))
          )
        ) : null
      )
    );
    return !hasConflicts(pv);
  };
  return { box, render: render2 };
}
function renderSiteBlock(root) {
  const dis = !(S.app.mode === "edit" && (S.rights.is_manager || (S.rights.roles || []).length));
  const st = fromAddr(S.site.addr, S.site.depth_mode);
  if (st.mode === "inherit") {
    st.mode = "legacy";
  }
  let tree = S.site.loc_tree || "flat";
  let renumber = "new";
  const hypo = () => ({ siteAddr: toAddr(st, { site: true }), siteDepth: st.depth_mode || "level" });
  const pvBox = previewBlock(() => previewScene(hypo()));
  const apply = h("button", { class: "fbtn primary", type: "button", id: "btnAddrApply", disabled: dis, onclick: () => applySite() }, "Застосувати");
  const upd = (err) => {
    apply.disabled = dis || !pvBox.render(err);
  };
  async function applySite() {
    const vals = { addr: toAddr(st, { site: true }), depth_mode: st.depth_mode || "level", loc_tree: tree };
    const res = await E.runDialog("addr.applySite", { vals, renumber });
    if (res && res.ok) {
      toast(res.pinned ? `Адресацію застосовано; закріплено номерів: ${res.pinned}.` : "Адресацію застосовано.");
    }
  }
  root.append(
    ...K(
      h(
        "div",
        { class: "sec", id: "addrSite" },
        h("h3", null, "Адресація"),
        dis ? h("div", { class: "note lock" }, "Адресацію змінює проєктувальник чи менеджер.") : null,
        h(
          "div",
          { class: "fcol" },
          addrEditor({ st, mode: "site", dis, onChange: upd }),
          fld("Ієрархія локацій в Odoo", selectEl(opts(LOC_TREES, DIR_LABELS.loc_tree), tree, (v) => {
            tree = v;
          }, dis || !canManage(), "Ієрархія локацій")),
          fld("Перенумерація наявних", selectEl([["new", "Нумерувати тільки нові"], ["all", "Перенумерувати все (лише менеджер)"]], renumber, (v) => {
            renumber = v;
          }, dis, "Перенумерація")),
          h("div", { class: "small muted" }, "Імена й штрихкоди опублікованих локацій змінює лише публікація; для змінених кодів потрібні нові етикетки."),
          pvBox.box,
          h("div", { class: "frow" }, apply)
        )
      )
    )
  );
  upd(null);
}
function renderSlotBlock(root, { rec }) {
  if (!rec || !rec.template || rec.template === "machine_spot") {
    return;
  }
  const ly = layerOf(rec.layer_id);
  const dis = !canEditLayer(ly) || !!rec.locked;
  const zone2 = rec.template === "zone";
  const st = fromAddr(rec.addr, rec.depth_mode);
  const draftAddr = () => toAddr(st, { zone: zone2, row: !zone2 });
  const patch = (s) => s.id === rec.id ? { ...s, addr: draftAddr(), depth_mode: st.depth_mode || null } : null;
  const pvBox = previewBlock(() => previewScene({ patch }));
  const apply = h("button", { class: "fbtn primary", type: "button", id: "btnAddrSlotApply", disabled: dis, onclick: () => applySlot() }, "Застосувати");
  const upd = (err) => {
    apply.disabled = dis || !pvBox.render(err);
  };
  async function applySlot() {
    const res = await E.runDialog("addr.applySlot", { id: rec.id, addr: draftAddr(), depth_mode: st.depth_mode || null });
    if (res && res.ok) {
      toast("Адресацію місця застосовано.");
    }
  }
  const addressed = !!contextOf(rec);
  const num4 = addressed && !zone2 ? rowNumberOf(rec) : null;
  const codes = zone2 ? [] : cellsOf(rec).map((c) => c.code);
  root.append(
    ...K(
      h(
        "div",
        { class: "sec", id: "addrSlot" },
        h("h3", null, "Адресація"),
        num4 != null ? h("div", { class: "small muted", "data-role": "addr-row-no" }, `Номер ${rec.template === "floor_spot" ? "місця" : "ряду"}: ${num4}`) : null,
        codes.length ? h("div", { class: "small", "data-role": "addr-slot-codes" }, `Коди: ${codes.slice(0, 3).join(", ")}${codes.length > 3 ? ` … ${codes[codes.length - 1]}` : ""}`) : null,
        h(
          "div",
          { class: "fcol" },
          addrEditor({ st, mode: zone2 ? "zone" : "slot", row: !zone2 && isRowSlot(rec), dis, onChange: upd }),
          pvBox.box,
          h(
            "div",
            { class: "frow wrap" },
            apply,
            zone2 || !isRowSlot(rec) ? null : h("button", { class: "fbtn sm", type: "button", id: "btnRowPin", disabled: dis || !addressed, onclick: () => pinNumbers([rec]) }, "Закріпити номер")
          )
        )
      )
    )
  );
  upd(null);
}
registries.panels.add("site:addr", { area: "site", render: renderSiteBlock }, { sequence: 40, force: true });
registries.panels.add("slot:addr", { area: "slot", render: renderSlotBlock }, { sequence: 40, force: true });
function pinNumbers(slots) {
  const ctxs = contextsOf(S.slots, S.site?.addr, S.site?.depth_mode);
  let n = 0;
  for (const s of slots) {
    const ctx2 = ctxs.get(s.id);
    const number = ctx2 && (ctx2.row ?? ctx2.spot);
    if (number && safeNormalize(s.addr).row_no !== number) {
      s.addr = { ...safeNormalize(s.addr), row_no: number };
      n++;
    }
  }
  if (n) {
    E.commit({});
    toast(`Закріплено номерів: ${n}.`);
  }
  return n;
}
function remapCodes(oldCodes, newCodes) {
  for (const s of S.slots) {
    const old = oldCodes.get(s.id) || [];
    const next = newCodes.get(s.id) || [];
    if (!old.length || old.join() === next.join()) {
      continue;
    }
    const map = old.length === next.length ? new Map(old.map((c, i) => [c, next[i]])) : /* @__PURE__ */ new Map();
    if (s.overrides && Object.keys(s.overrides).length) {
      const keep = new Set(next);
      const out = {};
      for (const [k, v] of Object.entries(s.overrides)) {
        const nk = map.get(k) ?? k;
        if (keep.has(nk)) {
          out[nk] = v;
        }
      }
      s.overrides = out;
    }
    for (const p of S.placements) {
      if (p.slot_id === s.id && p.cell_code && map.has(p.cell_code)) {
        p.cell_code = map.get(p.cell_code);
      }
    }
  }
}
registries.dialogs.add(
  "addr.applySite",
  async ({ vals, renumber }, { adapter }) => {
    const prev = { addr: S.site.addr, depth_mode: S.site.depth_mode, loc_tree: S.site.loc_tree };
    try {
      const old = sceneCodes();
      Object.assign(S.site, vals);
      const res = (adapter.saveAddr ? await adapter.saveAddr(vals, { renumber }) : await adapter.saveSite(vals)) || {};
      if (adapter.serverRenumber || res.reload) {
        await E.flushNow();
        await E.reload();
      } else {
        remapCodes(old, sceneCodes());
        E.commit({});
      }
      return { ok: true, pinned: res.pinned || 0 };
    } catch (e) {
      Object.assign(S.site, prev);
      toast(e.message || "Не вдалося застосувати адресацію.", "err");
      return { ok: false };
    }
  },
  { force: true }
);
registries.dialogs.add(
  "addr.applySlot",
  async ({ id, addr, depth_mode: depthMode }, { adapter }) => {
    const rec = S.sIdx.get(id);
    if (!rec) {
      return { ok: false };
    }
    const old = sceneCodes();
    rec.addr = hasKeys(addr) ? addr : null;
    rec.depth_mode = depthMode || null;
    if (adapter.serverRenumber) {
      E.commit({});
      await E.flushNow();
      await E.reload();
    } else {
      remapCodes(old, sceneCodes());
      E.commit({});
      E.renderRight();
    }
    return { ok: true };
  },
  { force: true }
);
var origAddSlotAt = E.addSlotAt;
if (origAddSlotAt && !origAddSlotAt.s1) {
  E.addSlotAt = function addSlotAtPinned(spec, x, y) {
    const before = new Set(S.slots.map((s) => s.id));
    origAddSlotAt.call(this, spec, x, y);
    let changed = false;
    for (const s of S.slots.filter((x2) => !before.has(x2.id))) {
      if (spec.type_id != null) {
        s.type_id = spec.type_id;
        changed = true;
      }
      if (anyAddressing() && isRowSlot(s) && !safeNormalize(s.addr).row_no) {
        const number = rowNumberOf(s);
        if (number) {
          s.addr = { ...safeNormalize(s.addr), row_no: number };
          changed = true;
        }
      }
    }
    if (changed) {
      E.commit({});
    }
  };
  E.addSlotAt.s1 = true;
}

// core/constructor/library.js
var EMPTY = () => ({ types: [], presets: [] });
function libraryState() {
  if (!S.site) {
    return EMPTY();
  }
  if (!S.site.library) {
    Object.defineProperty(S.site, "library", { value: EMPTY(), writable: true, configurable: true, enumerable: false });
  }
  return S.site.library;
}
var canWriteLibrary = () => S.app.mode === "edit" && (S.rights.is_manager || (S.rights.roles || []).length > 0);
var canDeleteLibrary = () => S.app.mode === "edit" && !!S.rights.is_manager;
async function call(adapter, req) {
  if (adapter && typeof adapter.library === "function") {
    return await adapter.library(req);
  }
  return null;
}
var upsert = (list, rec) => {
  const i = list.findIndex((x) => String(x.id) === String(rec.id));
  if (i >= 0) {
    list[i] = rec;
  } else {
    list.push(rec);
  }
};
async function refreshLibrary(adapter) {
  const res = await call(adapter, { op: "list" });
  const lib4 = libraryState();
  if (res) {
    lib4.types = res.types || [];
    lib4.presets = res.presets || [];
  }
  return lib4;
}
async function saveRecord(adapter, kind, vals, id = null) {
  const lib4 = libraryState();
  const key = kind === "type" ? "types" : "presets";
  const res = await call(adapter, { op: "save", kind, id, vals });
  const rec = res ? res.record : { ...vals, id: id ?? "l_" + Math.random().toString(36).slice(2, 10) };
  upsert(lib4[key], rec);
  return rec;
}
async function deleteRecord(adapter, kind, id) {
  const lib4 = libraryState();
  const key = kind === "type" ? "types" : "presets";
  await call(adapter, { op: "delete", kind, id });
  lib4[key] = lib4[key].filter((x) => String(x.id) !== String(id));
}

// core/constructor/types_data.js
var GROUPS = {
  rack: "Стелажні",
  floor: "Напільні",
  special: "Спеціальні",
  zone: "Буферні та технологічні зони",
  mobile: "Мобільні носії"
};
var RELEVANCE_MARK = { 2: "●", 1: "○", 0: "—" };
var RELEVANCE_LABEL = { 2: "є на меблевій фабриці", 1: "буває", 0: "немає" };
var rack2 = (over = {}) => ({ bays: 6, levels: 4, bay_width: 2.7, depth: 1.1, level_height: 1.5, positions_per_bay: 3, max_load_kg: 1e3, ...over });
var shelf = (over = {}) => ({ sections: 4, shelves: 5, cell_w: 0.9, cell_d: 0.4, cell_h: 0.4, ...over });
var cant = (over = {}) => ({ arms: 4, levels: 3, arm_length: 1, length: 6, level_height: 1.2, max_load_kg: 500, ...over });
var stack2 = (over = {}) => ({ rows: 2, cols: 4, cell_l: 1.2, cell_w: 0.8, max_height: 1.5, ...over });
var spot = (over = {}) => ({ length: 4, width: 3, height: 0.1, ...over });
var ROWS = [
  ["R01", "Фронтальний палетний стелаж", "rack", "pallet_rack", "", 2, "pallet_cell", rack2(), "Класичний палетний стелаж: кожен проліт × ярус — комірка на кілька палет."],
  ["R02", "Стелаж подвійної глибини (double-deep)", "rack", "pallet_rack", "", 1, "pallet_cell", rack2({ deep: 2 }), "Палети ставляться у два ряди в глибину; доступ лише до крайнього."],
  ["R03", "Стелаж для вузьких проходів (VNA)", "rack", "pallet_rack", "", 1, "pallet_cell", rack2({ levels: 8, level_height: 1.6 }), "Високий стелаж із вузьким проходом для висотного штабелера."],
  ["R04", "Заїзний стелаж (drive-in)", "rack", "pallet_rack", "", 0, "pallet_cell", rack2({ deep: 4, levels: 3, positions_per_bay: 1 }), "Навантажувач заїжджає всередину; багато палет в глибину."],
  ["R05", "Гравітаційний стелаж", "rack", "pallet_rack", "", 0, "pallet_cell", rack2({ deep: 5, levels: 3, slope: 3 }), "Палети котяться по похилих роликах до виходу (FIFO)."],
  ["R06", "Flow-стелаж (роликовий)", "rack", "shelf", "", 1, "bin", shelf({ sections: 4, shelves: 4, cell_w: 1, cell_d: 2, cell_h: 0.5, slope: 4 }), "Короби котяться по похилих роликах до зони комплектації."],
  ["R07", "Стелаж push-back", "rack", "pallet_rack", "", 1, "pallet_cell", rack2({ deep: 3, levels: 4, slope: 5 }), "Палети штовхають одна одну по похилих візках (LIFO)."],
  ["R08", "Мобільний стелаж (на рейках)", "rack", "pallet_rack", "", 0, "pallet_cell", rack2({ double_sided: true, gap_y: 0 }), "Блоки стелажів розсуваються по рейках; один проход на всі."],
  ["R09", "Шаттл-стелаж", "rack", "pallet_rack", "", 0, "pallet_cell", rack2({ deep: 6, levels: 5, positions_per_bay: 1 }), "Глибокі канали, у яких палети возить шаттл."],
  ["R10", "Консольний стелаж", "rack", "cantilever", "", 2, "shelf", cant(), "Довгомірні вантажі (плити, профіль, труби) на консолях."],
  ["R11", "Полицевий стелаж", "rack", "shelf", "", 2, "shelf", shelf({ cell_w: 1, cell_d: 0.5, cell_h: 0.5, loc_kind: "shelf" }), "Вантажі без палет на полицях."],
  ["R12", "Мезонін (антресоль)", "rack", "shelf", "", 1, "shelf", shelf({ shelves: 3, cell_w: 1.2, cell_d: 0.6, cell_h: 0.6, loc_kind: "shelf" }), "Другий поверх; відмітку задає шар (CD-04)."],
  ["R13", "Комірковий стелаж / біни (фурнітура)", "rack", "shelf", "", 2, "bin", shelf({ sections: 6, shelves: 6, cell_w: 0.4, cell_d: 0.4, cell_h: 0.25 }), "Дрібні складові (фурнітура, кріплення) у комірках."],
  ["R14", "Вертикальна карусель", "rack", "shelf", "cylinder", 0, "bin", shelf({ sections: 1, shelves: 12, cell_w: 1.6, cell_d: 1, cell_h: 0.3 }), "Автоматична карусель; параметри автоматики не моделюються."],
  ["R15", "Вертикальний ліфтовий модуль (VLM)", "rack", "shelf", "cabinet", 0, "bin", shelf({ sections: 1, shelves: 20, cell_w: 1.5, cell_d: 0.8, cell_h: 0.2 }), "Автоматична шафа з лотками; параметри автоматики не моделюються."],
  ["R16", "Горизонтальна карусель", "rack", "shelf", "cylinder", 0, "bin", shelf({ sections: 6, shelves: 3, cell_w: 0.8, cell_d: 0.6, cell_h: 0.5 }), "Горизонтальна карусель; параметри автоматики не моделюються."],
  ["R17", "Стільниковий стелаж", "rack", "shelf", "", 0, "shelf", shelf({ sections: 4, shelves: 6, cell_w: 0.8, cell_d: 2, cell_h: 0.4 }), "Глибокі осередки для довгомірних (труби, прути, профіль)."],
  ["R18", "A-frame", "rack", "shelf", "", 0, "bin", shelf({ sections: 10, shelves: 2, cell_w: 0.3, cell_d: 0.6, cell_h: 0.8 }), "Модуль швидкого комплектування малих складових."],
  ["R19", "Консольний стелаж для рулонів", "rack", "cantilever", "roll_rack", 1, "shelf", cant({ arms: 6, levels: 2, arm_length: 1.2, level_height: 1.4 }), "Рулони (тканина, плівка, шпон) на консолях-жолобах."],
  ["R20", "Вішалки (підвісне зберігання)", "rack", "shelf", "", 0, "shelf", shelf({ sections: 4, shelves: 2, cell_w: 1.2, cell_d: 0.6, cell_h: 1.6, loc_kind: "shelf" }), "Штанги для підвісних виробів."],
  ["FL1", "Штабель", "floor", "floor_stack", "stack", 2, "stack", stack2(), "Плити й піддони штабелем на підлозі."],
  ["FL2", "Зона на підлозі", "floor", "floor_spot", "zone", 2, "area", spot({ length: 4, width: 3 }), "Розмічений прямокутник на підлозі — одна локація."],
  ["FL3", "Блочне зберігання", "floor", "floor_stack", "stack", 1, "stack", stack2({ rows: 3, cols: 5, max_height: 3 }), "Щільні блоки штабелів без проходів між ними."],
  ["FL4", "Розмітка палетомісць", "floor", "floor_stack", "zone", 1, "area", stack2({ rows: 2, cols: 6, max_height: 1.8, loc_kind: "area" }), "Палетомісця, розмічені на підлозі."],
  ["FL5", "Штабель у стоякових піддонах", "floor", "floor_stack", "stack", 0, "stack", stack2({ rows: 2, cols: 4, max_height: 4 }), "Високий штабель у піддонах зі стійками."],
  ["SP1", "Клітка", "special", "floor_spot", "fence", 1, "area", spot({ length: 3, width: 3, height: 2.4 }), "Огороджена зона для цінних і режимних вантажів."],
  ["SP2", "Холодильна камера", "special", "floor_spot", "fence", 0, "area", spot({ length: 4, width: 3, height: 2.6 }), "Охолоджуване приміщення (температуру задає зона)."],
  ["SP3", "Морозильна камера", "special", "floor_spot", "fence", 0, "area", spot({ length: 4, width: 3, height: 2.6 }), "Приміщення для глибокого заморожування."],
  ["SP4", "Склад ЛФМ (лакофарбових матеріалів)", "special", "floor_spot", "fence", 2, "area", spot({ length: 4, width: 3, height: 2.6 }), "Пожежонебезпечні матеріали: лаки, фарби, розчинники, клеї."],
  ["SP5", "Склад газових балонів", "special", "floor_spot", "fence", 0, "area", spot({ length: 3, width: 2, height: 2.2 }), "Огороджена зона для балонів зі стиснутим газом."],
  ["SP6", "Бункер", "special", "floor_spot", "cylinder", 1, "area", spot({ length: 2.5, width: 2.5, height: 4 }), "Сипкі матеріали (тирса, стружка, гранули)."],
  ["SP7", "Ємність (резервуар)", "special", "floor_spot", "cylinder", 1, "area", spot({ length: 2, width: 2, height: 3 }), "Рідини: клей, розчинники, пально-мастильні матеріали."],
  ["SP8", "Інструментальна", "special", "floor_spot", "cabinet", 2, "area", spot({ length: 4, width: 3, height: 2.4 }), "Зберігання й видача інструменту та оснастки."],
  ["BF01", "Зона приймання", "zone", "floor_spot", "zone", 2, "area", spot({ length: 6, width: 4 }), "Буфер розвантаження й первинного розбору."],
  ["BF02", "Зона відвантаження", "zone", "floor_spot", "zone", 2, "area", spot({ length: 6, width: 4 }), "Буфер готових до відвантаження вантажів."],
  ["BF03", "Ворота / док", "zone", null, "gate", 2, null, { width: 3.5, height: 4 }, "Об'єкт будівлі (layer.items), пов'язаний із локацією виду «док»."],
  ["BF04", "Буфер перед виробництвом", "zone", "floor_spot", "zone", 2, "area", spot({ length: 5, width: 3 }), "Матеріали, подані до дільниці."],
  ["BF05", "Зона комплектації", "zone", "floor_spot", "zone", 2, "area", spot({ length: 5, width: 3 }), "Збір комплектів і замовлень."],
  ["BF06", "Зона вхідного контролю (QC)", "zone", "floor_spot", "zone", 2, "area", spot({ length: 4, width: 3 }), "Перевірка якості до розміщення."],
  ["BF07", "Карантин", "zone", "floor_spot", "zone", 1, "area", spot({ length: 3, width: 3 }), "Вантажі до рішення щодо якості."],
  ["BF08", "Зона браку", "zone", "floor_spot", "zone", 1, "area", spot({ length: 3, width: 2 }), "Забракована продукція й матеріали."],
  ["BF09", "Зона повернень", "zone", "floor_spot", "zone", 1, "area", spot({ length: 3, width: 2 }), "Повернення від клієнтів і з виробництва."],
  ["BF10", "Зона пакування", "zone", "floor_spot", "zone", 1, "area", spot({ length: 5, width: 3 }), "Пакування готових виробів."],
  ["BF11", "Зона розпакування / сортування", "zone", "floor_spot", "zone", 1, "area", spot({ length: 4, width: 3 }), "Розпакування й сортування вхідних поставок."],
  ["BF12", "Транзитна зона (cross-docking)", "zone", "floor_spot", "zone", 0, "area", spot({ length: 6, width: 3 }), "Вантаж проходить без розміщення на зберігання."],
  ["MB1", "Візок", "mobile", "floor_spot", "mobile", 2, "kit", spot({ length: 1.2, width: 0.8, height: 1 }), "Візок для комплектів і напівфабрикатів."],
  ["MB2", "Роллконтейнер", "mobile", "floor_spot", "mobile", 1, "kit", spot({ length: 0.8, width: 0.7, height: 1.7 }), "Сітчастий контейнер на колесах."],
  ["MB3", "Касета", "mobile", "floor_spot", "mobile", 1, "kit", spot({ length: 1.2, width: 0.6, height: 1.2 }), "Касета для плит і деталей на колесах."],
  ["MB4", "Gitterbox", "mobile", "floor_spot", "mobile", 1, "kit", spot({ length: 1.2, width: 0.8, height: 0.97 }), "Сітчастий ящик-піддон, що штабелюється."],
  ["MB5", "Етажерка комплекту", "mobile", "floor_spot", "mobile", 2, "kit", spot({ length: 0.8, width: 0.6, height: 1.6 }), "Багатополична етажерка для комплекту деталей."]
];
var CATALOG = ROWS.map(([ref2, name, group, template, shape, relevance, locKind, params, description], i) => ({
  id: ref2.toLowerCase(),
  code: ref2.toLowerCase(),
  ref: ref2,
  name,
  description,
  group,
  template,
  shape,
  params,
  relevance,
  loc_kind: locKind,
  is_custom: false,
  company_id: null,
  sequence: (i + 1) * 10
}));
function allTypes(lib4) {
  const server = lib4 && lib4.types || [];
  const codes = new Set(server.map((t) => t.code));
  return [...server, ...CATALOG.filter((t) => !codes.has(t.code))];
}
function typeOf(typeId, lib4) {
  if (typeId == null || typeId === "") {
    return null;
  }
  return allTypes(lib4).find((t) => String(t.id) === String(typeId) || t.code === typeId) || null;
}
function startParams(type) {
  const p = { ...type.params || {} };
  if (type.shape && type.template && SLOT_TEMPLATES[type.template]) {
    p.shape = type.shape;
  }
  if (type.loc_kind && SLOT_TEMPLATES[type.template]?.choices?.loc_kind && LOC_KINDS.includes(type.loc_kind)) {
    const allowed = SLOT_TEMPLATES[type.template].choices.loc_kind[0];
    if (allowed.includes(type.loc_kind) && p.loc_kind == null) {
      p.loc_kind = type.loc_kind;
    }
  }
  return p;
}
function filterTypes(types2, { q = "", group = "", minRelevance = 0 } = {}) {
  const needle = q.trim().toLowerCase();
  return types2.filter(
    (t) => (!group || t.group === group) && t.relevance >= minRelevance && (!needle || [t.name, t.ref, t.code, t.description].some((x) => (x || "").toLowerCase().includes(needle)))
  );
}
function customCopy(type, name) {
  const code = "c_" + newUid().slice(0, 10);
  return { ...JSON.parse(JSON.stringify(type)), id: code, code, ref: null, name: name || `${type.name} (копія)`, is_custom: true, relevance: type.relevance };
}
var isBuildingType = (t) => !t.template;

// core/constructor/types_ui.js
var KINDS_LABEL = { stack: "Стос", area: "Майданчик", kit: "Візок / етажерка", bin: "Комірка (bin)", shelf: "Полиця", pallet_cell: "Комірка палети" };
var PLACEABLE = ["pallet_rack", "cantilever", "shelf", "floor_stack", "floor_spot"];
var SIZE_KEYS = {
  pallet_rack: ["bay_width", "depth", "level_height"],
  shelf: ["cell_w", "cell_d", "cell_h"],
  cantilever: ["arm_length", "level_height"],
  floor_stack: ["cell_l", "cell_w", "max_height"],
  floor_spot: ["length", "width", "height"]
};
var PARAM_UI = {
  bay_width: "Ширина секції",
  depth: "Глибина секції",
  level_height: "Висота ярусу",
  cell_w: "Ширина комірки",
  cell_d: "Глибина комірки",
  cell_h: "Висота комірки",
  arm_length: "Виліт консолі",
  cell_l: "Довжина місця",
  max_height: "Макс. висота",
  length: "Довжина",
  width: "Ширина",
  height: "Висота",
  deep: "Глибина в палетах",
  bottom_on_floor: "Нижній ярус на підлозі",
  double_sided: "Двосторонній ряд",
  gap_x: "Зазор між секціями",
  gap_y: "Зазор між сторонами",
  beam_th: "Товщина балки",
  slope: "Ухил, °",
  cells_per_level: "Комірок на ярусі",
  level_heights: "Висоти ярусів",
  shape: "Форма 3D"
};
var lib = () => libraryState();
var types = () => allTypes(lib());
var layerAllows = (tpl) => {
  const ly = layerOf(S.ui.layer);
  return !!ly && (ly.slot_types || []).includes(tpl);
};
function optFields(tpl, params, o) {
  const spec = SLOT_TEMPLATES[tpl];
  if (!spec) {
    return null;
  }
  const wrap = (k, el) => h("div", { "data-opt": k }, el);
  const cells = [];
  for (const [key, [min, max, def, type]] of Object.entries(spec.opt || {})) {
    const label = PARAM_UI[key] || key;
    const commit2 = () => o.onChange && o.onChange();
    if (type === "bool") {
      const val = params[key] ?? def;
      cells.push(wrap(key, h("label", { class: "frow", style: { gap: "6px" } }, h("input", { type: "checkbox", checked: !!val, disabled: o.dis, "data-f": "p." + key, onchange: (e) => {
        o.begin && o.begin();
        params[key] = e.target.checked;
        commit2();
        o.end && o.end();
      } }), label)));
    } else if (type === "list") {
      const val = params[key] ? params[key].join(", ") : "";
      cells.push(wrap(key, fld(label + ", м", textInput({ value: val, dis: o.dis, label, f: "p." + key, begin: o.begin, end: o.end, set: (v) => {
        const nums = v.split(/[;,\s]+/).map(Number).filter((x) => Number.isFinite(x) && x >= min && x <= max);
        if (nums.length) {
          params[key] = nums;
        } else {
          delete params[key];
        }
        commit2();
      } }), null, "span2")));
    } else {
      cells.push(wrap(key, fld(label, numInput({ value: params[key] ?? def, dis: o.dis, min, max, step: type === "int" ? 1 : 0.05, int: type === "int", f: "p." + key, label, begin: o.begin, end: o.end, set: (v) => {
        params[key] = v;
        commit2();
      } }))));
    }
  }
  if (spec.optChoices && spec.optChoices.shape) {
    cells.push(wrap("shape", fld("Форма 3D", selectEl(Object.entries(SHAPE_LABELS), params.shape || "", (v) => {
      o.begin && o.begin();
      if (v) {
        params.shape = v;
      } else {
        delete params.shape;
      }
      o.onChange && o.onChange();
      o.end && o.end();
    }, o.dis, "Форма 3D"))));
  }
  return h("div", { class: "grid2", "data-role": "opt-fields" }, cells);
}
function nextPrefix(type, usedSet = null) {
  const base2 = ((type.ref || type.code || "T").replace(/[^A-Za-z0-9]/g, "").toUpperCase() || "T").slice(0, 16);
  const used = usedSet || new Set(S.slots.map((s) => s.code_prefix));
  let n = 1;
  while (used.has(`${base2}-${n}`)) {
    n++;
  }
  return `${base2}-${n}`;
}
var paramsForType = (type) => ({ ...defaultParams(type.template), ...clone(startParams(type)) });
function placeTypeOnScene(type, params) {
  if (isBuildingType(type) || !PLACEABLE.includes(type.template)) {
    toast("Цей тип — об'єкт будівлі: його додають у режимі «Будівля».", "warn");
    return false;
  }
  if (!layerAllows(type.template)) {
    toast(`Шар «${(layerOf(S.ui.layer) || {}).name}» не допускає цей тип місця. Змініть «Допустимі типи місць» шару.`, "warn");
    return false;
  }
  (S.ui.projectTypes = S.ui.projectTypes || /* @__PURE__ */ new Set()).add(type.code);
  E.startPlacing({ kind: "slot", template: type.template, prefix: nextPrefix(type), params: clone(params || paramsForType(type)), type_id: type.id });
  return true;
}
function regionOf(zoneId) {
  const zone2 = zoneId ? S.sIdx.get(zoneId) : null;
  const b = S.site.building || { length: 60, width: 30 };
  return zone2 ? { cx: zone2.x, cy: zone2.y, l: zone2.params.length, w: zone2.params.width, rot: zone2.rotation || 0 } : { cx: b.length / 2, cy: b.width / 2, l: b.length, w: b.width, rot: 0 };
}
function layoutInRegion(fp, region, n, { aisle = 0.5, gap = 0.5, step = 0.5 } = {}) {
  const cos = Math.cos(region.rot * Math.PI / 180);
  const sin = Math.sin(region.rot * Math.PI / 180);
  const out = [];
  let u = -region.l / 2 + 0.5 + fp.l / 2;
  let v = -region.w / 2 + 0.5 + fp.w / 2;
  while (out.length < n) {
    if (u + fp.l / 2 > region.l / 2 - 0.5 + 1e-6) {
      u = -region.l / 2 + 0.5 + fp.l / 2;
      v += fp.w + aisle;
    }
    if (v + fp.w / 2 > region.w / 2 - 0.5 + 1e-6) {
      break;
    }
    out.push({ x: snapV(region.cx + u * cos - v * sin, step), y: snapV(region.cy + u * sin + v * cos, step), rotation: region.rot });
    u += fp.l + gap;
  }
  return out;
}
function addSlots(list) {
  const ly = layerOf(S.ui.layer);
  const made = [];
  for (const spec of list) {
    const s = {
      id: newUid(),
      rid: null,
      etag: null,
      layer_id: ly.id,
      template: spec.template,
      code_prefix: spec.prefix,
      x: spec.x,
      y: spec.y,
      rotation: spec.rotation || 0,
      params: clone(spec.params),
      overrides: {},
      parent_location_id: null
    };
    if (spec.type_id != null) {
      s.type_id = spec.type_id;
    }
    if (spec.addr && Object.keys(spec.addr).length) {
      s.addr = clone(spec.addr);
    }
    const before = S.issues;
    S.slots.push(s);
    S.sIdx.set(s.id, s);
    if (newBlocks(before, runLive(), "s:" + s.id).length) {
      S.slots.pop();
      S.sIdx.delete(s.id);
    } else {
      made.push(s);
    }
  }
  if (made.length) {
    S.sel = { kind: "slot", id: made[made.length - 1].id };
    E.commit({});
    pinNumbers(made.filter((s) => contextOf(s)));
  }
  return made;
}
function placeTypeOnPlan(type, params, zoneId, count) {
  const ly = layerOf(S.ui.layer);
  if (!ly || !canEditLayer(ly)) {
    toast("Шар не редагується вами.", "warn");
    return 0;
  }
  if (!layerAllows(type.template)) {
    toast("Шар не допускає цей тип місця.", "warn");
    return 0;
  }
  const floor = ["floor_spot", "floor_stack"].includes(type.template);
  const slots = layoutInRegion(footprint(type.template, params), regionOf(zoneId), count, { aisle: floor ? 0.5 : ly.aisle_width || 3, gap: type.template === "floor_spot" ? 0.3 : 0.5, step: ly.grid_step || 0.5 });
  const used = new Set(S.slots.map((s) => s.code_prefix));
  const list = slots.map((pos) => {
    const prefix = nextPrefix(type, used);
    used.add(prefix);
    return { ...pos, template: type.template, params, prefix, type_id: type.id };
  });
  const made = addSlots(list);
  const left = count - made.length;
  toast(made.length ? `Додано місць: ${made.length}${left ? `; не вмістилось або заблоковано: ${left}` : ""}.` : "Не вдалося додати: у зоні немає вільного місця.", made.length ? "ok" : "warn");
  return made.length;
}
async function openCatalog(adapter, args = {}) {
  try {
    await refreshLibrary(adapter);
  } catch {
  }
  const st = { q: "", group: "", minRel: 1, sel: args.code || null, params: null, plan: false, zone: "", count: 4 };
  const body = h("div", { class: "fcol", id: "catalogBody" });
  const grid = h("div", { id: "catalogGrid", style: { display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))", gap: "8px", alignContent: "start", overflow: "auto", maxHeight: "60vh", flex: "1 1 60%" } });
  const detail = h("div", { id: "catalogDetail", class: "fcol", style: { flex: "1 1 40%", minWidth: "260px", overflow: "auto", maxHeight: "60vh" } });
  const dlg = openDialog({ title: "Каталог типів місць", cls: "wide", body, actions: [{ label: "Закрити", value: "close" }] });
  const choose = (t) => {
    st.sel = t.code;
    st.params = isBuildingType(t) ? {} : paramsForType(t);
    st.plan = false;
    draw();
  };
  const draw = () => {
    const all = types();
    const list = filterTypes(all, { q: st.q, group: st.group, minRelevance: st.minRel });
    grid.replaceChildren(
      ...K(
        list.length ? null : h("div", { class: "empty", style: { gridColumn: "1 / -1" } }, "Типів за цим фільтром немає."),
        list.map(
          (t2) => h(
            "div",
            { class: "it" + (t2.code === st.sel ? " sel" : ""), role: "button", tabindex: 0, "data-type": t2.code, style: { border: "1px solid var(--line)", padding: "6px", cursor: "pointer", display: "flex", flexDirection: "column", gap: "4px", background: t2.code === st.sel ? "var(--accent-soft)" : "" }, onclick: () => choose(t2), onkeydown: (e) => {
              if (e.key === "Enter") {
                choose(t2);
              }
            } },
            h("div", { html: typeSvg(t2, 160, 90), style: { color: "var(--ink2)" } }),
            h("div", { class: "frow" }, h("b", null, t2.ref || "★"), h("span", { class: "grow" }), h("span", { title: RELEVANCE_LABEL[t2.relevance] }, RELEVANCE_MARK[t2.relevance])),
            h("div", { class: "small" }, t2.name)
          )
        )
      )
    );
    const t = st.sel && all.find((x) => x.code === st.sel);
    detail.replaceChildren(...K(t ? detailOf(t) : h("div", { class: "empty" }, "Оберіть тип: праворуч з'являться опис, параметри й дії.")));
  };
  function detailOf(t) {
    const building = isBuildingType(t);
    const dis = false;
    const fp = !building ? footprint(t.template, st.params) : null;
    const zones = S.slots.filter((s) => s.template === "zone" && s.layer_id === S.ui.layer);
    const canWrite = canWriteLibrary();
    return [
      h("div", { html: typeSvg(t, 280, 150), style: { color: "var(--ink2)", alignSelf: "center" } }),
      h("h3", { class: "h3" }, `${t.ref || "Власний"} · ${t.name}`),
      h("div", { class: "frow wrap" }, h("span", { class: "tag" }, GROUPS[t.group] || t.group), h("span", { class: "tag" }, building ? "об'єкт будівлі" : SLOT_TEMPLATES[t.template].label), h("span", { class: "tag" }, `${RELEVANCE_MARK[t.relevance]} ${RELEVANCE_LABEL[t.relevance]}`), t.loc_kind ? h("span", { class: "tag" }, KINDS_LABEL[t.loc_kind] || t.loc_kind) : null),
      h("div", { class: "small", "data-role": "type-desc" }, t.description || ""),
      building ? h("div", { class: "note" }, "Ворота й доки — об'єкти будівлі (layer.items): їх додають у режимі «Будівля»; тут — лише довідка.") : K(
        h("div", { class: "small muted" }, `Габарит: ${fmt(fp.l, 2)} × ${fmt(fp.w, 2)} м`),
        paramFields(t.template, st.params, { dis, onChange: () => {
          draw2();
        } }),
        optFields(t.template, st.params, { dis, onChange: () => {
          draw2();
        } }),
        st.plan ? h(
          "div",
          { class: "note", id: "planBox" },
          h(
            "div",
            { class: "grid2" },
            fld("Зона", selectEl([["", "Вільна частина шару"], ...zones.map((z) => [z.id, z.params.title || z.code_prefix])], st.zone, (v) => {
              st.zone = v;
            }, false, "Зона")),
            fld("Кількість", numInput({ value: st.count, min: 1, max: 200, step: 1, int: true, label: "Кількість", f: "plan-count", set: (v) => {
              st.count = v;
            } }))
          ),
          h(
            "div",
            { class: "frow", style: { marginTop: "6px" } },
            h("button", { class: "fbtn primary", type: "button", id: "btnPlanGo", onclick: () => {
              if (placeTypeOnPlan(t, st.params, st.zone, st.count)) {
                dlg.close2("ok");
              }
            } }, "Додати"),
            h("button", { class: "fbtn", type: "button", onclick: () => {
              st.plan = false;
              draw();
            } }, "Скасувати")
          )
        ) : h(
          "div",
          { class: "frow wrap" },
          h("button", { class: "fbtn primary", type: "button", id: "btnAddToProject", onclick: () => {
            if (placeTypeOnScene(t, st.params)) {
              dlg.close2("ok");
            }
          } }, "Додати в проєкт"),
          h("button", { class: "fbtn", type: "button", id: "btnAddToPlan", onclick: () => {
            st.plan = true;
            draw();
          } }, "Додати на план")
        )
      ),
      h(
        "div",
        { class: "frow wrap" },
        !building && !t.is_custom ? h("button", { class: "fbtn sm", type: "button", id: "btnToLibrary", disabled: !canWrite, title: canWrite ? "Власна копія типу в бібліотеці (каталог не змінюється)" : "Бібліотеку пише проєктувальник", onclick: () => saveCopy(t) }, "У бібліотеку") : null,
        t.is_custom ? h("button", { class: "fbtn sm danger", type: "button", id: "btnTypeDelete", disabled: !canDeleteLibrary(), title: canDeleteLibrary() ? "" : "Видаляє менеджер", onclick: () => removeType(t) }, ic("trash"), "Видалити з бібліотеки") : null
      )
    ];
  }
  const draw2 = () => {
    const t = types().find((x) => x.code === st.sel);
    if (t) {
      detail.replaceChildren(...K(detailOf(t)));
    }
  };
  async function saveCopy(t) {
    try {
      const cp = customCopy(t, st.params && t.template ? `${t.name} (мій)` : null);
      cp.params = { ...clone(t.params || {}), ...clone(st.params || {}) };
      const rec = await saveRecord(adapter, "type", { code: cp.code, name: cp.name, description: cp.description, group: cp.group, template: cp.template, shape: cp.shape, params: cp.params, relevance: cp.relevance, loc_kind: cp.loc_kind, is_custom: true });
      toast(`Тип «${rec.name}» збережено в бібліотеці.`);
      st.sel = rec.code;
      draw();
    } catch (e) {
      toast(e.message || "Не вдалося зберегти тип у бібліотеці.", "err");
    }
  }
  async function removeType(t) {
    try {
      await deleteRecord(adapter, "type", t.id);
      st.sel = null;
      draw();
      toast("Тип видалено з бібліотеки.");
    } catch (e) {
      toast(e.message || "Не вдалося видалити тип.", "err");
    }
  }
  body.append(
    ...K(
      h(
        "div",
        { class: "frow wrap" },
        h("input", { type: "search", placeholder: "Пошук типу…", "aria-label": "Пошук типу", id: "catalogSearch", style: { flex: "1 1 200px" }, oninput: (e) => {
          st.q = e.target.value;
          drawGrid();
        } }),
        selectEl([["", "Усі групи"], ...Object.entries(GROUPS)], st.group, (v) => {
          st.group = v;
          drawGrid();
        }, false, "Група"),
        h("label", { class: "frow", style: { gap: "6px" } }, h("input", { type: "checkbox", id: "catalogRel", checked: st.minRel > 0, onchange: (e) => {
          st.minRel = e.target.checked ? 1 : 0;
          drawGrid();
        } }), "Лише ті, що є на меблевій фабриці (● ○)")
      ),
      h("div", { class: "frow", style: { alignItems: "flex-start", gap: "12px", flexWrap: "wrap" } }, grid, detail)
    )
  );
  const drawGrid = () => {
    const list = filterTypes(types(), { q: st.q, group: st.group, minRelevance: st.minRel });
    if (st.sel && !list.find((t) => t.code === st.sel)) {
      st.sel = null;
    }
    draw();
  };
  const first = args.code && types().find((t) => t.code === args.code);
  if (first) {
    choose(first);
  } else {
    draw();
  }
  return await new Promise((res) => dlg.addEventListener("close", () => res(dlg.returnValue)));
}
registries.dialogs.add("catalog", (args, { adapter }) => openCatalog(adapter, args || {}), { force: true });
registries.menu.add("catalog", { area: "more", label: "Каталог типів", icon: "plus", sequence: 30, run: () => E.runDialog("catalog") }, { sequence: 30, force: true });
function renderTypeBlock(root, { rec }) {
  if (!rec || ["zone", "machine_spot"].includes(rec.template) || !SLOT_TEMPLATES[rec.template]) {
    return;
  }
  const ly = layerOf(rec.layer_id);
  const dis = !canEditLayer(ly) || !!rec.locked;
  const opts2 = types().filter((t) => t.template === rec.template);
  const cur = typeOf(rec.type_id, lib());
  const ed = { begin: () => E.beginEdit("slot", rec), end: () => E.endEdit() };
  const note = h("div", { class: "small muted", "data-role": "type-note" });
  const asTypeBtn = h("button", { class: "fbtn sm", type: "button", id: "btnAsType", onclick: () => asType() }, "Як у типу");
  const refresh = () => {
    const cur2 = typeOf(rec.type_id, lib());
    const diff = cur2 ? Object.entries(startParams(cur2)).filter(([k, v]) => JSON.stringify(rec.params[k] ?? null) !== JSON.stringify(v)).length : 0;
    note.textContent = cur2 ? `${cur2.description || ""}${diff ? ` · змінено параметрів відносно типу: ${diff}` : " · як у типу"}` : "";
    asTypeBtn.disabled = dis || !cur2 || !diff;
  };
  const live = () => {
    E.liveEdit();
    refresh();
  };
  const asType = () => {
    if (!cur) {
      return;
    }
    E.beginEdit("slot", rec);
    rec.params = { ...defaultParams(rec.template), ...clone(startParams(cur)) };
    E.liveEdit();
    E.endEdit();
    E.renderRight();
  };
  refresh();
  root.append(
    ...K(
      h(
        "div",
        { class: "sec", id: "typeBlock" },
        h("h3", null, "Тип"),
        h(
          "div",
          { class: "fcol" },
          fld("Тип місця", selectEl([["", "— не задано —"], ...opts2.map((t) => [t.id, `${t.ref ? t.ref + " · " : ""}${t.name}`])], rec.type_id ?? "", (v) => {
            E.beginEdit("slot", rec);
            const picked = opts2.find((t) => String(t.id) === v);
            rec.type_id = picked ? picked.id : null;
            E.liveEdit();
            E.endEdit();
            E.renderRight();
          }, dis, "Тип місця")),
          cur ? note : null,
          cur ? asTypeBtn : null,
          h("div", { class: "small muted" }, "Конструкція ряду: переозначення параметрів типу для цього ряду"),
          optFields(rec.template, rec.params, { dis, begin: ed.begin, end: ed.end, onChange: live })
        )
      )
    )
  );
}
registries.panels.add("slot:type", { area: "slot", render: renderTypeBlock }, { sequence: 30, force: true });
function usedTypes() {
  const rows = /* @__PURE__ */ new Map();
  for (const s of S.slots) {
    if (s.type_id == null) {
      continue;
    }
    const t = typeOf(s.type_id, lib());
    if (t) {
      rows.set(t.code, { type: t, slots: [...rows.get(t.code)?.slots || [], s] });
    }
  }
  for (const code of S.ui.projectTypes || []) {
    const t = types().find((x) => x.code === code);
    if (t && !rows.has(code)) {
      rows.set(code, { type: t, slots: [] });
    }
  }
  for (const t of lib().types.filter((x) => x.is_custom)) {
    if (!rows.has(t.code)) {
      rows.set(t.code, { type: t, slots: [] });
    }
  }
  return [...rows.values()];
}
function openResize(row) {
  const t = row.type;
  const keys = SIZE_KEYS[t.template] || [];
  const base2 = row.slots[0] ? row.slots[0].params : paramsForType(t);
  const vals = Object.fromEntries(keys.map((k) => [k, getp(base2, k) ?? getp(defaultParams(t.template), k)]));
  const body = h(
    "div",
    { class: "fcol" },
    h("div", { class: "small muted" }, `Нові розміри застосуються до всіх місць типу «${t.name}» (${fmtInt(row.slots.length)}); комірки перебудуються.`),
    h("div", { class: "grid2" }, keys.map((k) => {
      const [min, max, , kind] = SLOT_TEMPLATES[t.template].params[k];
      return fld(PARAM_UI[k] || k, numInput({ value: vals[k], min, max: max ?? 1e3, step: kind === "int" ? 1 : 0.05, label: PARAM_UI[k] || k, f: "size-" + k, set: (v) => {
        vals[k] = v;
      } }), "м");
    }))
  );
  openDialog({
    title: `Розмір типу: ${t.ref || t.name}`,
    cls: "narrow",
    body,
    actions: [
      { label: "Скасувати", value: "no" },
      {
        label: "Застосувати до всіх місць",
        cls: "primary",
        id: "btnResizeGo",
        onClick: () => {
          for (const s of row.slots) {
            for (const k of keys) {
              setp(s.params, k, vals[k]);
            }
          }
          if (!row.slots.length) {
            t.params = { ...t.params || {}, ...vals };
          }
          E.commit({});
          toast(`Перебудовано місць: ${row.slots.length}.`);
        }
      }
    ]
  });
}
function openNewType(adapter) {
  const draft = { name: "", group: "rack", template: "pallet_rack", shape: "", loc_kind: "", description: "", params: defaultParams("pallet_rack") };
  const form = h("div", { class: "fcol" });
  const dlgRef = {};
  const redraw = () => {
    form.replaceChildren(
      ...K(
        fld("Назва типу", textInput({ value: draft.name, label: "Назва типу", f: "type-name", set: (v) => {
          draft.name = v;
        } })),
        h(
          "div",
          { class: "grid2" },
          fld("Група", selectEl(Object.entries(GROUPS), draft.group, (v) => {
            draft.group = v;
          }, false, "Група")),
          fld("Генератор", selectEl(PLACEABLE.map((k) => [k, TPL[k].name]), draft.template, (v) => {
            draft.template = v;
            draft.params = defaultParams(v);
            redraw();
          }, false, "Генератор"))
        ),
        paramFields(draft.template, draft.params, { dis: false, onChange: () => {
        } }),
        optFields(draft.template, draft.params, { dis: false, onChange: () => {
        } }),
        fld("Опис", textInput({ value: draft.description, label: "Опис", f: "type-desc", set: (v) => {
          draft.description = v;
        } }))
      )
    );
  };
  redraw();
  dlgRef.dlg = openDialog({
    title: "Новий тип місця",
    cls: "narrow",
    body: form,
    actions: [
      { label: "Скасувати", value: "no" },
      {
        label: "Зберегти тип",
        cls: "primary",
        id: "btnTypeSave",
        onClick: async () => {
          if (!draft.name.trim()) {
            toast("Вкажіть назву типу.", "warn");
            return false;
          }
          try {
            const rec = await saveRecord(adapter, "type", { code: "c_" + newUid().slice(0, 10), name: draft.name.trim(), description: draft.description, group: draft.group, template: draft.template, shape: draft.params.shape || "", params: clone(draft.params), relevance: 1, loc_kind: draft.loc_kind || null, is_custom: true });
            toast(`Тип «${rec.name}» збережено.`);
            E.renderLeft();
            return true;
          } catch (e) {
            toast(e.message || "Не вдалося зберегти тип.", "err");
            return false;
          }
        }
      }
    ]
  });
}
registries.dialogs.add("typeNew", (_a, { adapter }) => openNewType(adapter), { force: true });
registries.dialogs.add("typeResize", ({ code }) => {
  const row = usedTypes().find((r) => r.type.code === code);
  if (row) {
    openResize(row);
  }
}, { force: true });
function renderTypesTab(root) {
  const rows = usedTypes();
  const canWrite = canWriteLibrary();
  root.append(
    ...K(
      h(
        "div",
        { class: "sec" },
        h("h3", null, "Типи місць"),
        h(
          "div",
          { class: "frow wrap" },
          h("button", { class: "fbtn primary", type: "button", id: "btnOpenCatalog", onclick: () => E.runDialog("catalog") }, "Каталог типів…"),
          h("button", { class: "fbtn", type: "button", id: "btnNewType", disabled: !canWrite, title: canWrite ? "" : "Типи створює проєктувальник", onclick: () => E.runDialog("typeNew") }, ic("plus"), "Новий тип")
        ),
        h("div", { class: "small muted", style: { marginTop: "6px" } }, "Каталог не змінюється: «Додати в проєкт» ставить тип на сцену, «У бібліотеку» робить власну копію.")
      ),
      h(
        "div",
        { class: "sec", id: "projectTypes" },
        h("h3", null, `У проєкті · ${rows.length}`),
        rows.length ? h(
          "div",
          { class: "rowlist" },
          rows.map((r) => h(
            "div",
            { class: "it", "data-type": r.type.code },
            h("span", { class: "t", title: r.type.name }, `${r.type.ref ? r.type.ref + " · " : "★ "}${r.type.name}`),
            h("span", { class: "tag" }, r.type.is_custom ? "свій" : "каталог"),
            h("span", { class: "m" }, `${fmtInt(r.slots.length)} міс.`),
            h("button", { class: "fbtn sm icon", type: "button", title: "Змінити розмір для всіх місць типу", "aria-label": "Змінити розмір типу", disabled: !SIZE_KEYS[r.type.template], onclick: () => E.runDialog("typeResize", { code: r.type.code }) }, "↔")
          ))
        ) : h("div", { class: "empty" }, "У проєкті ще немає місць із типом.")
      )
    )
  );
}
registries.panels.add("left:types", { area: "left", tab: "types", label: "Типи", render: renderTypesTab }, { sequence: 25, force: true });

// core/constructor/presets.js
var PRESET_KINDS = { row: "Ряд", section: "Секція", group: "Виділене" };
var MAX_GROUP = 200;
var PLACEABLE2 = ["pallet_rack", "cantilever", "shelf", "floor_stack", "floor_spot", "machine_spot"];
var COUNT_KEY = { pallet_rack: "bays", cantilever: "arms", shelf: "sections", floor_stack: "cols" };
function specOf(slot, origin = null, lib4 = libraryState()) {
  const spec = { template: slot.template, params: clone(slot.params || {}), rotation: Math.round(slot.rotation || 0) };
  const type = typeOf(slot.type_id, lib4);
  if (type) {
    spec.type_code = type.code;
  }
  if (slot.addr && Object.keys(slot.addr).length) {
    const { row_no: _pin, ...addr } = slot.addr;
    if (Object.keys(addr).length) {
      spec.addr = clone(addr);
    }
  }
  if (origin) {
    spec.dx = Math.round((slot.x - origin.x) * 1e4) / 1e4;
    spec.dy = Math.round((slot.y - origin.y) * 1e4) / 1e4;
    spec.prefix = slot.code_prefix;
  }
  return spec;
}
function normalizePresetData(kind, data) {
  if (!PRESET_KINDS[kind]) {
    throw new Error(`Невідомий вид пресету «${kind}».`);
  }
  const one = (spec2) => {
    if (!spec2 || typeof spec2 !== "object" || !PLACEABLE2.includes(spec2.template)) {
      throw new Error("Пресет: невідомий або непридатний генератор місця.");
    }
    const out = { template: spec2.template, params: normalizeParams(spec2.template, spec2.params), rotation: (Math.round(Number(spec2.rotation) || 0) % 360 + 360) % 360 };
    for (const k of ["type_code", "prefix"]) {
      if (spec2[k]) {
        out[k] = String(spec2[k]).slice(0, 32);
      }
    }
    for (const k of ["dx", "dy"]) {
      if (spec2[k] != null) {
        if (!Number.isFinite(Number(spec2[k]))) {
          throw new Error("Пресет: зсув має бути числом.");
        }
        out[k] = Number(spec2[k]);
      }
    }
    if (spec2.addr && typeof spec2.addr === "object") {
      out.addr = clone(spec2.addr);
    }
    return out;
  };
  if (kind === "group") {
    const list = data && data.slots;
    if (!Array.isArray(list) || !list.length || list.length > MAX_GROUP) {
      throw new Error(`Пресет «Виділене»: від 1 до ${MAX_GROUP} місць.`);
    }
    return { slots: list.map(one) };
  }
  const spec = one(data && data.slot);
  if (kind === "section" && !COUNT_KEY[spec.template]) {
    throw new Error("Секцією може бути лише стелаж чи штабель.");
  }
  return { slot: spec };
}
function presetFromSlot(slot, kind, name, lib4 = libraryState()) {
  const spec = specOf(slot, null, lib4);
  if (kind === "section") {
    const key = COUNT_KEY[slot.template];
    if (!key) {
      throw new Error("Секцію можна зберегти лише зі стелажа чи штабеля.");
    }
    spec.params[key] = 1;
  }
  const type = typeOf(slot.type_id, lib4);
  return { name, kind, type_id: type && typeof type.id === "number" ? type.id : null, data: normalizePresetData(kind, { slot: spec }) };
}
function presetFromSlots(slots, name, lib4 = libraryState()) {
  if (!slots.length) {
    throw new Error("Немає що зберігати.");
  }
  const origin = { x: slots[0].x, y: slots[0].y };
  return { name, kind: "group", type_id: null, data: normalizePresetData("group", { slots: slots.map((s) => specOf(s, origin, lib4)) }) };
}
var typeIdOf = (spec, lib4) => {
  const t = spec.type_code && allTypes(lib4).find((x) => x.code === spec.type_code);
  return t ? t.id : null;
};
function insertSection(preset, row, n = 1) {
  const spec = preset.data.slot;
  if (spec.template !== row.template || !COUNT_KEY[row.template]) {
    throw new Error("Секція пресету не підходить до цього ряду: інший генератор.");
  }
  const key = COUNT_KEY[row.template];
  const add = (spec.params[key] || 1) * n;
  const next = (row.params[key] ?? normalizeParams(row.template, {})[key]) + add;
  const max = SLOT_TEMPLATES[row.template].params[key][1];
  if (next > max) {
    throw new Error(`Забагато секцій: допустимо до ${max}.`);
  }
  for (const [k, v] of Object.entries(spec.params)) {
    if (k !== key && !["index_digits", "max_load_kg"].includes(k)) {
      row.params[k] = clone(v);
    }
  }
  row.params[key] = next;
  return next;
}
function plansFromPreset(preset, { zoneId = "", count = 1, lib: lib4 = libraryState(), at = null } = {}) {
  const ly = layerOf(S.ui.layer);
  const used = new Set(S.slots.map((s) => s.code_prefix));
  const makePrefix = (spec2) => {
    const type = spec2.type_code && allTypes(lib4).find((t) => t.code === spec2.type_code);
    const base2 = spec2.prefix && !used.has(spec2.prefix) ? spec2.prefix : nextPrefix(type || { ref: spec2.template === "pallet_rack" ? "R" : spec2.template.slice(0, 3) }, used);
    used.add(base2);
    return base2;
  };
  const common = (spec2) => ({ template: spec2.template, params: clone(spec2.params), rotation: spec2.rotation, prefix: makePrefix(spec2), type_id: typeIdOf(spec2, lib4), addr: spec2.addr });
  if (preset.kind === "group") {
    const region = regionOf(zoneId);
    const origin = at || { x: region.cx, y: region.cy };
    return preset.data.slots.map((spec2) => ({ ...common(spec2), x: origin.x + (spec2.dx || 0), y: origin.y + (spec2.dy || 0) }));
  }
  const spec = preset.data.slot;
  const spots = layoutInRegion(footprint(spec.template, spec.params), regionOf(zoneId), count, { aisle: ly.aisle_width || 3, gap: 0.5, step: ly.grid_step || 0.5 });
  return spots.map((pos) => ({ ...common(spec), ...pos, rotation: pos.rotation + spec.rotation }));
}
var lib2 = () => libraryState();
function inZone(z, s) {
  const a = (z.rotation || 0) * Math.PI / 180;
  const dx = s.x - z.x;
  const dy = s.y - z.y;
  const u = dx * Math.cos(a) + dy * Math.sin(a);
  const v = -dx * Math.sin(a) + dy * Math.cos(a);
  return Math.abs(u) <= z.params.length / 2 && Math.abs(v) <= z.params.width / 2;
}
function openSave(adapter, { id }) {
  const slot = S.sIdx.get(id);
  if (!slot) {
    return void 0;
  }
  const isZone = slot.template === "zone";
  const draft = { name: slot.code_prefix, kind: isZone ? "group" : "row" };
  const kinds = isZone ? [["group", "Виділене: зона з вмістом"]] : [["row", "Ряд"], ...COUNT_KEY[slot.template] ? [["section", "Секція"]] : []];
  const dlg = openDialog({
    title: "Зберегти як шаблон",
    cls: "narrow",
    body: h(
      "div",
      { class: "fcol" },
      fld("Назва шаблону", textInput({ value: draft.name, label: "Назва шаблону", f: "preset-name", set: (v) => {
        draft.name = v;
      } })),
      fld("Що зберегти", selectEl(kinds, draft.kind, (v) => {
        draft.kind = v;
      }, false, "Вид шаблону")),
      h("div", { class: "small muted" }, "Шаблон потрапляє в бібліотеку: його видно в інших проєктах. Тип, яруси, комірки, параметри й поворот зберігаються разом.")
    ),
    actions: [
      { label: "Скасувати", value: "no" },
      {
        label: "Зберегти",
        cls: "primary",
        id: "btnPresetSaveGo",
        onClick: async () => {
          if (!draft.name.trim()) {
            toast("Вкажіть назву шаблону.", "warn");
            return false;
          }
          try {
            const inside = isZone ? S.slots.filter((s) => s.id !== slot.id && s.layer_id === slot.layer_id && s.template !== "zone" && inZone(slot, s)) : [];
            const vals = isZone ? presetFromSlots(inside, draft.name.trim()) : presetFromSlot(slot, draft.kind, draft.name.trim());
            const rec = await saveRecord(adapter, "preset", vals);
            toast(`Шаблон «${rec.name}» збережено в бібліотеці.`);
            return true;
          } catch (e) {
            toast(e.message || "Не вдалося зберегти шаблон.", "err");
            return false;
          }
        }
      }
    ]
  });
  return new Promise((res) => dlg.addEventListener("close", () => res(dlg.returnValue)));
}
async function openInsert(adapter, { id }) {
  try {
    await refreshLibrary(adapter);
  } catch {
  }
  const target = S.sIdx.get(id);
  const ly = target ? layerOf(target.layer_id) : layerOf(S.ui.layer);
  if (!ly || !canEditLayer(ly)) {
    toast("Шар не редагується вами.", "warn");
    return void 0;
  }
  const isZone = !!target && target.template === "zone";
  const fits = (p) => isZone ? p.kind === "row" || p.kind === "group" : !!target && p.kind === "section" && p.data.slot.template === target.template;
  const list = lib2().presets.filter(fits);
  const draft = { id: list[0] ? list[0].id : null, count: 1 };
  const listBox = h("div", { class: "rowlist", id: "presetList" });
  const draw = () => {
    listBox.replaceChildren(
      ...K(
        list.length ? list.map((p) => h("div", { class: "it" + (String(p.id) === String(draft.id) ? " sel" : ""), role: "button", tabindex: 0, "data-preset": p.id, onclick: () => {
          draft.id = p.id;
          draw();
        } }, h("span", { class: "t" }, p.name), h("span", { class: "tag" }, PRESET_KINDS[p.kind] || p.kind))) : h("div", { class: "empty" }, "Підходящих шаблонів у бібліотеці немає.")
      )
    );
  };
  draw();
  const dlg = openDialog({
    title: "Вставити з шаблону",
    cls: "narrow",
    body: h(
      "div",
      { class: "fcol" },
      h("div", { class: "small muted" }, isZone ? "Ряд вставляється ×N у зону; «Виділене» — одним блоком у зону." : "Секція додається в кінець вибраного ряду."),
      listBox,
      fld("Кількість (рядів чи секцій)", numInput({ value: draft.count, min: 1, max: 100, step: 1, int: true, label: "Кількість", f: "preset-count", set: (v) => {
        draft.count = v;
      } }))
    ),
    actions: [
      { label: "Скасувати", value: "no" },
      {
        label: "Вставити",
        cls: "primary",
        id: "btnPresetInsertGo",
        onClick: () => {
          const preset = list.find((p) => String(p.id) === String(draft.id));
          if (!preset) {
            toast("Оберіть шаблон.", "warn");
            return false;
          }
          try {
            applyPreset(preset, target, draft.count);
            return true;
          } catch (e) {
            toast(e.message || "Не вдалося вставити шаблон.", "err");
            return false;
          }
        }
      }
    ]
  });
  return new Promise((res) => dlg.addEventListener("close", () => res(dlg.returnValue)));
}
function applyPreset(preset, target, count = 1) {
  const data = { ...preset, data: normalizePresetData(preset.kind, preset.data) };
  if (preset.kind === "section") {
    E.beginEdit("slot", target);
    const n = insertSection(data, target, count);
    E.liveEdit();
    E.endEdit();
    E.renderRight();
    toast(`Додано секції: тепер ${n}.`);
    return n;
  }
  const made = addSlots(plansFromPreset(data, { zoneId: target && target.template === "zone" ? target.id : "", count }));
  toast(made.length ? `Вставлено місць: ${fmtInt(made.length)}.` : "Не вдалося вставити: немає вільного місця або заблоковано перевірками.", made.length ? "ok" : "warn");
  return made.length;
}
registries.dialogs.add("presetSave", (args, { adapter }) => openSave(adapter, args), { force: true });
registries.dialogs.add("presetInsert", (args, { adapter }) => openInsert(adapter, args), { force: true });
async function openLibrary(adapter) {
  try {
    await refreshLibrary(adapter);
  } catch (e) {
    toast(e.message || "Не вдалося прочитати бібліотеку.", "warn");
  }
  const body = h("div", { class: "fcol", id: "libraryBody" });
  const guard3 = async (fn) => {
    try {
      await fn();
    } catch (e) {
      toast(e.message || "Не вдалося виконати дію.", "err");
    }
    draw();
  };
  function rename(p) {
    const draft = { name: p.name };
    openDialog({
      title: "Перейменувати шаблон",
      cls: "narrow",
      body: fld("Назва", textInput({ value: draft.name, label: "Назва", f: "preset-rename", set: (v) => {
        draft.name = v;
      } })),
      actions: [
        { label: "Скасувати", value: "no" },
        { label: "Зберегти", cls: "primary", id: "btnPresetRename", onClick: async () => {
          if (!draft.name.trim()) {
            return false;
          }
          await guard3(() => saveRecord(adapter, "preset", { name: draft.name.trim() }, p.id));
          return true;
        } }
      ]
    });
  }
  function draw() {
    const l = lib2();
    const canW = canWriteLibrary();
    const canD = canDeleteLibrary();
    const customTypes = l.types.filter((t) => t.is_custom);
    body.replaceChildren(
      ...K(
        h("h3", { class: "h3" }, `Шаблони · ${l.presets.length}`),
        l.presets.length ? h(
          "div",
          { class: "rowlist", id: "libPresets" },
          l.presets.map((p) => h(
            "div",
            { class: "it", "data-preset": p.id },
            h("span", { class: "t" }, p.name),
            h("span", { class: "tag" }, PRESET_KINDS[p.kind] || p.kind),
            h("button", { class: "fbtn sm icon", type: "button", title: "Перейменувати", "aria-label": "Перейменувати шаблон", disabled: !canW, onclick: () => rename(p) }, "✎"),
            h("button", { class: "fbtn sm icon danger", type: "button", title: canD ? "Видалити з бібліотеки" : "Видаляє менеджер", "aria-label": "Видалити шаблон", disabled: !canD, onclick: () => guard3(() => deleteRecord(adapter, "preset", p.id)) }, ic("trash"))
          ))
        ) : h("div", { class: "empty" }, "Шаблонів ще немає: збережіть ряд чи секцію («Зберегти як шаблон» у властивостях місця)."),
        h("h3", { class: "h3" }, `Власні типи · ${customTypes.length}`),
        customTypes.length ? h(
          "div",
          { class: "rowlist", id: "libTypes" },
          customTypes.map((t) => h(
            "div",
            { class: "it", "data-type": t.code },
            h("span", { class: "t" }, t.name),
            h("span", { class: "tag" }, SLOT_TEMPLATES[t.template] ? SLOT_TEMPLATES[t.template].label.split(" ")[0] : "тип"),
            h("button", { class: "fbtn sm icon", type: "button", title: "Відкрити в каталозі", "aria-label": "Відкрити в каталозі", onclick: () => E.runDialog("catalog", { code: t.code }) }, ic("plus")),
            h("button", { class: "fbtn sm icon danger", type: "button", title: canD ? "Видалити з бібліотеки" : "Видаляє менеджер", "aria-label": "Видалити тип", disabled: !canD, onclick: () => guard3(() => deleteRecord(adapter, "type", t.id)) }, ic("trash"))
          ))
        ) : h("div", { class: "empty" }, "Власних типів немає: «У бібліотеку» в каталозі типів робить копію типу."),
        h("div", { class: "small muted" }, "Бібліотека спільна для всіх проєктів компанії; правка типу чи шаблону в проєкті бібліотеку не змінює.")
      )
    );
  }
  draw();
  const dlg = openDialog({ title: "Бібліотека", cls: "wide", body, actions: [{ label: "Закрити", value: "close" }] });
  return new Promise((res) => dlg.addEventListener("close", () => res(dlg.returnValue)));
}
registries.dialogs.add("library", (_a, { adapter }) => openLibrary(adapter), { force: true });
registries.menu.add("library", { area: "more", label: "Бібліотека", icon: "tag", sequence: 31, run: () => E.runDialog("library") }, { sequence: 31, force: true });
function renderPresetBlock(root, { rec }) {
  const zone2 = !!rec && rec.template === "zone";
  if (!rec || !(zone2 || PLACEABLE2.includes(rec.template)) || rec.template === "machine_spot") {
    return;
  }
  const ly = layerOf(rec.layer_id);
  const dis = !canEditLayer(ly) || !!rec.locked;
  const canSave = canWriteLibrary();
  root.append(
    ...K(
      h(
        "div",
        { class: "sec", id: "presetBlock" },
        h("h3", null, "Шаблони"),
        h(
          "div",
          { class: "frow wrap" },
          h("button", { class: "fbtn sm", type: "button", id: "btnPresetSave", disabled: !canSave, title: canSave ? "" : "Бібліотеку пише проєктувальник", onclick: () => E.runDialog("presetSave", { id: rec.id }) }, zone2 ? "Зберегти вміст зони" : "Зберегти як шаблон"),
          h("button", { class: "fbtn sm", type: "button", id: "btnPresetInsert", disabled: dis || !zone2 && !COUNT_KEY[rec.template], onclick: () => E.runDialog("presetInsert", { id: rec.id }) }, "Вставити з шаблону…")
        )
      )
    )
  );
}
registries.panels.add("slot:presets", { area: "slot", render: renderPresetBlock }, { sequence: 35, force: true });

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
  return slots.filter((s) => s.template === "zone").map((zone2) => ({ zone: zone2, poly: zone2.params.polygon || zonePoly(zone2) }));
}
var polyArea2 = (poly) => Math.abs(poly.reduce((a, [x1, y1], i) => a + (x1 * poly[(i + 1) % poly.length][1] - poly[(i + 1) % poly.length][0] * y1), 0)) / 2;
function zoneChainAt(zones, x, y) {
  return zones.filter(({ poly }) => polygonContains(poly, [x, y])).sort((a, b) => polyArea2(a.poly) - polyArea2(b.poly)).map(({ zone: zone2 }) => zone2);
}
function inheritedField(slot, field, zone2) {
  const has = (v) => v != null && v !== "" && !(Array.isArray(v) && !v.length);
  if (has(slot[field])) {
    return { value: slot[field], from: "own" };
  }
  for (const z of Array.isArray(zone2) ? zone2 : zone2 ? [zone2] : []) {
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
function capacitySummary(slots, { loads = null, categories = [], zone: zone2 = null, allSlots = S.slots } = {}) {
  const zones = zonesOf(allSlots);
  const cats = new Map(categories.map((c) => [c.id, c]));
  const out = { cells: 0, places: 0, area: 0, volume: 0, maxWeight: 0, withCategory: 0, occupied: 0, free: 0, fill: null };
  for (const slot of slots) {
    for (const cell of cellsAbs(slot)) {
      const home = zoneChainAt(zones, cell.x, cell.y);
      if (zone2 && !home.includes(zone2)) {
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
function rulesInto(code, slot, rules = rulesState().putaway, zone2 = null) {
  const cat = inheritedField(slot, "storage_category_id", zone2).value;
  return rules.filter((r) => !r.deleted && (r.out_code === code || r.sublocation === "closest_location" && r.storage_category_id && r.storage_category_id === cat));
}
function rulesIntoSlot(slot, rules = rulesState().putaway, zone2 = null) {
  const out = [];
  for (const rule of rules) {
    if (rule.deleted) {
      continue;
    }
    const codes = cellsAbs(slot).map((c) => c.code).filter((code) => rulesInto(code, slot, [rule], zone2).length);
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
    for (let guard3 = 0; dep && guard3 < 20; guard3++) {
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
    for (let guard3 = 0; dep && guard3 < 20; guard3++) {
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
var lib3 = { loaded: false, loading: null, categories: [], strategies: [], functions: ZONE_FUNCTIONS.map((f) => ({ id: f.key, ...f })), attrs: ZONE_ATTRS.map((a) => ({ id: a.key, ...a })) };
async function loadLib(force = false) {
  const adapter = E.adapter;
  if (!adapter || typeof adapter.categories !== "function" || !can("storage")) {
    lib3.loaded = true;
    return lib3;
  }
  if (lib3.loaded && !force) {
    return lib3;
  }
  lib3.loading ||= adapter.categories({ op: "list" }).then((res) => {
    Object.assign(lib3, { categories: res.categories || [], strategies: res.strategies || [], functions: (res.functions || lib3.functions).map((f) => ({ ...f })), attrs: (res.attrs || lib3.attrs).map((a) => ({ ...a })) });
  }).catch((e) => console.warn("Категорії зберігання недоступні:", e.message || e)).finally(() => {
    lib3.loaded = true;
    lib3.loading = null;
  });
  await lib3.loading;
  return lib3;
}
function ensureLib() {
  if (!lib3.loaded && !lib3.loading) {
    loadLib().then(() => E.renderRight && E.renderRight());
  }
}
var categoryOf = (id) => lib3.categories.find((c) => String(c.id) === String(id)) || null;
var strategyName = (id) => (lib3.strategies.find((s) => String(s.id) === String(id)) || {}).name || "";
var functionOf = (id) => lib3.functions.find((f) => String(f.id) === String(id)) || null;
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
var USAGE_OPTS = [["", "— як в Odoo —"], ["internal", "Внутрішня (зберігання)"], ["view", "Віртуальна (група, без залишків)"]];
var REPLENISH_OPTS = [["", "— як в Odoo —"], ["1", "Так"], ["0", "Ні"]];
var flagText = (key, v) => key === "replenish_location" ? v ? "1" : "0" : String(v);
function flagValue(rec, cells, key) {
  const seen = new Set(cells.map((c) => {
    const v = ((rec.overrides || {})[c.code] || {})[key];
    return v == null ? "" : flagText(key, v);
  }));
  return seen.size > 1 ? "~" : [...seen][0] ?? "";
}
function setFlag(rec, cells, key, value) {
  rec.overrides = rec.overrides || {};
  for (const c of cells) {
    const o = rec.overrides[c.code] = rec.overrides[c.code] || {};
    if (value == null) {
      delete o[key];
    } else {
      o[key] = value;
    }
    if (!Object.keys(o).length) {
      delete rec.overrides[c.code];
    }
  }
}
function renderSlotBlock2(root, { rec }) {
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
  const catOpts = [["", cat.from === "zone" ? `— як у зони: ${(categoryOf(cat.value) || {}).name || "…"} —` : "— без категорії —"], ...lib3.categories.map((c) => [c.id, c.name])];
  const stratOpts = [["", strat.from === "zone" ? `— як у зони: ${strategyName(strat.value) || "…"} —` : "— як в Odoo —"], ...lib3.strategies.map((s) => [s.id, s.name])];
  const conv = (v) => v === "" ? null : isNaN(Number(v)) ? v : Number(v);
  const fn = functionOf(rec.function_id);
  const first = cells[0];
  const info = first ? cellLimit(rec, first, categoryOf(cat.value)) : null;
  const sumScope = isZone ? capacitySummary(S.slots.filter((s) => s !== rec), { loads: Object.keys(cache2.loads).length || cache2.demo ? cache2.loads : null, categories: lib3.categories, zone: rec }) : capacitySummary([rec], { loads: Object.keys(cache2.loads).length || cache2.demo ? cache2.loads : null, categories: lib3.categories });
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
            fld("Функція зони", selectEl([["", "— не задано —"], ...lib3.functions.map((f) => [f.id, f.name])], rec.function_id ?? "", (v) => {
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
            h("div", { class: "checks" }, lib3.attrs.map((a) => {
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
            (rec.attr_ids || []).some((x) => (lib3.attrs.find((a) => String(a.id) === String(x)) || {}).key === "temp" || x === "temp") ? h("div", { class: "grid2" }, fld("Температура від", numInput({ value: rec.temp_min_c ?? 0, dis, step: 1, label: "Температура від", set: (v) => {
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
          isZone ? null : flagField("Тип локацій комірок", USAGE_OPTS, flagValue(rec, cells, "usage"), edit((v) => {
            if (v !== "~") {
              setFlag(rec, cells, "usage", v || null);
            }
          }), dis, "usage"),
          isZone ? null : flagField("Місце поповнення", REPLENISH_OPTS, flagValue(rec, cells, "replenish_location"), edit((v) => {
            if (v !== "~") {
              setFlag(rec, cells, "replenish_location", v === "" ? null : v === "1");
            }
          }), dis, "replenish_location"),
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
var flagField = (label, opts2, value, onChange, dis, key) => {
  const el = selectEl(value === "~" ? [["~", "— різні —"], ...opts2] : opts2, value, onChange, dis, label);
  el.dataset.flag = key;
  return fld(label, el);
};
var categoryLine = (c) => c ? `${c.name}: макс. вага ${c.max_weight ? fmtInt(c.max_weight) + " кг" : "без обмеження"}, ${POLICY_LABEL[c.allow_new_product] || c.allow_new_product}` : "";
registries.panels.add("slot:capacity", { area: "slot", render: renderSlotBlock2 }, { sequence: 35, force: true });
function renderSiteBlock2(root) {
  ensureLib();
  lazyRefresh();
  const loads = Object.keys(cache2.loads).length || cache2.demo ? cache2.loads : null;
  const sum = capacitySummary(S.slots, { loads, categories: lib3.categories });
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
registries.panels.add("site:capacity", { area: "site", render: renderSiteBlock2 }, { sequence: 50, force: true });
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
        lib3.categories.length ? lib3.categories.map(
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
        d.sublocation === "closest_location" ? fld("Категорія зберігання місця", selectEl([["", "— оберіть —"], ...lib3.categories.map((c) => [c.id, c.name])], d.storage_category_id ?? "", (v) => {
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
  const restore2 = (rule) => {
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
          r.deleted ? h("button", { class: "fbtn sm", type: "button", "data-act": "restore", disabled: dis, onclick: () => restore2(r) }, "Повернути") : [h("button", { class: "fbtn sm", type: "button", "data-act": "edit", disabled: dis, onclick: async () => {
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
          r.deleted ? h("button", { class: "fbtn sm", type: "button", "data-act": "restore", disabled: dis, onclick: () => restore2(r) }, "Повернути") : [h("button", { class: "fbtn sm", type: "button", "data-act": "edit", disabled: dis, onclick: async () => {
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

// core/constructor/undo.js
var KINDS = ["layers", "slots", "placements", "putaway", "replenish"];
var MAX_STEPS = 100;
var MAX_CHARS = 3e7;
var COALESCE_MS = 1200;
var strip2 = (k, v) => k === "rid" || k === "etag" ? void 0 : v;
var siteVals = () => ({ addr: S.site?.addr ?? null, depth_mode: S.site?.depth_mode ?? null, loc_tree: S.site?.loc_tree ?? null });
var rulesOf = () => S.site && S.site.rules || {};
var snapshot = () => JSON.stringify({ layers: S.layers, slots: S.slots, placements: S.placements, putaway: rulesOf().putaway || [], replenish: rulesOf().replenish || [], site: siteVals() }, strip2);
var same2 = (a, b) => JSON.stringify(a) === JSON.stringify(b);
function changedFields(a, b) {
  const out = [];
  for (const k of /* @__PURE__ */ new Set([...Object.keys(a), ...Object.keys(b)])) {
    if (same2(a[k], b[k])) {
      continue;
    }
    if ((k === "params" || k === "overrides") && a[k] && b[k] && typeof a[k] === "object" && typeof b[k] === "object") {
      for (const kk of /* @__PURE__ */ new Set([...Object.keys(a[k]), ...Object.keys(b[k])])) {
        if (!same2(a[k][kk], b[k][kk])) {
          out.push(`${k}.${kk}`);
        }
      }
    } else {
      out.push(k);
    }
  }
  return out;
}
function diffSnapshots(a, b) {
  const out = { added: [], removed: [], changed: [], site: !same2(a.site, b.site) };
  for (const kind of KINDS) {
    const ma = new Map((a[kind] || []).map((r) => [r.id, r]));
    const mb = new Map((b[kind] || []).map((r) => [r.id, r]));
    for (const [id, r] of mb) {
      if (!ma.has(id)) {
        out.added.push({ kind, id, rec: r });
      } else {
        const fields = changedFields(ma.get(id), r);
        if (fields.length) {
          out.changed.push({ kind, id, rec: r, fields });
        }
      }
    }
    for (const [id, r] of ma) {
      if (!mb.has(id)) {
        out.removed.push({ kind, id, rec: r });
      }
    }
  }
  return out;
}
var nameOf2 = (e) => {
  if (e.kind === "putaway" || e.kind === "replenish") {
    return `${e.kind === "putaway" ? "правило розміщення" : "правило поповнення"} ${e.rec.product?.name || e.rec.out_code || e.rec.cell_code || ""}`.trim();
  }
  return (e.kind === "layers" ? e.rec.name : e.kind === "slots" ? e.rec.params?.title || e.rec.code_prefix : e.rec.code || e.rec.name) || "об’єкт";
};
var MOVE = ["x", "y"];
function labelOf(d) {
  const n = d.added.length + d.removed.length + d.changed.length;
  if (!n && d.site) {
    return "Адресація площадки";
  }
  if (d.added.length && !d.removed.length && !d.changed.length) {
    return d.added.length === 1 ? `Додано: ${nameOf2(d.added[0])}` : `Додано об’єктів: ${d.added.length}`;
  }
  if (d.removed.length && !d.added.length && !d.changed.length) {
    return d.removed.length === 1 ? `Видалено: ${nameOf2(d.removed[0])}` : `Видалено об’єктів: ${d.removed.length}`;
  }
  if (d.changed.length && !d.added.length && !d.removed.length) {
    const all = (set) => d.changed.every((c) => c.fields.every((f) => set.includes(f)));
    const one = d.changed.length === 1;
    const nm = one ? nameOf2(d.changed[0]) : "";
    if (all(MOVE)) {
      return one ? `Переміщено: ${nm}` : `Переміщено об’єктів: ${d.changed.length}`;
    }
    if (all(["rotation"]) || all(["x", "y", "rotation"])) {
      return one ? `Повернуто: ${nm}` : `Повернуто об’єктів: ${d.changed.length}`;
    }
    if (one && d.changed[0].fields.every((f) => f.startsWith("params.") || f.startsWith("overrides."))) {
      return `Параметри: ${nm}`;
    }
    if (one && d.changed[0].fields.every((f) => f === "addr" || f === "depth_mode")) {
      return `Адресація: ${nm}`;
    }
    if (one && (d.changed[0].kind === "putaway" || d.changed[0].kind === "replenish")) {
      return `Правило: ${nm}`;
    }
    return one ? `Зміна: ${nm}` : `Зміна об’єктів: ${d.changed.length}`;
  }
  return `Зміна: ${n} дій`;
}
function undoLabel(text) {
  S.hist.label = text || null;
}
var trim = (H) => {
  let total = H.stack.reduce((s, e) => s + e.data.length, 0);
  while (H.stack.length > 1 && (H.stack.length > MAX_STEPS || total > MAX_CHARS)) {
    total -= H.stack.shift().data.length;
    H.idx--;
  }
};
var notify = () => E.renderUndoButtons?.();
function undoReset() {
  const H = S.hist;
  const data = S.site ? snapshot() : "";
  H.stack = [{ data, label: "", at: 0, key: null }];
  H.idx = 0;
  H.cur = data;
  H.label = null;
  H.busy = false;
  notify();
}
function undoRebase() {
  const H = S.hist;
  if (!H.stack.length || !S.site) {
    return undoReset();
  }
  const data = snapshot();
  H.stack.length = H.idx + 1;
  H.stack[H.idx] = { ...H.stack[H.idx], data };
  H.cur = data;
  H.label = null;
  notify();
}
function undoRecord() {
  const H = S.hist;
  if (!S.site || H.busy) {
    return false;
  }
  const data = snapshot();
  if (!H.stack.length) {
    undoReset();
    return false;
  }
  if (data === H.cur) {
    return false;
  }
  const diff = diffSnapshots(JSON.parse(H.cur), JSON.parse(data));
  const label = H.label || labelOf(diff);
  H.label = null;
  const one = diff.changed.length === 1 && !diff.added.length && !diff.removed.length && !diff.site ? diff.changed[0] : null;
  const key = one ? `${one.kind}:${one.id}:${one.fields.join(",")}` : null;
  H.stack.length = H.idx + 1;
  const top = H.stack[H.idx];
  const now = Date.now();
  if (key && top && top.key === key && now - top.at < COALESCE_MS && H.idx > 0) {
    top.data = data;
    top.at = now;
  } else {
    H.stack.push({ data, label, at: now, key });
    H.idx = H.stack.length - 1;
    trim(H);
  }
  H.cur = data;
  notify();
  return true;
}
function undoState() {
  const H = S.hist;
  const hasRedo = H.idx >= 0 && H.idx < H.stack.length - 1;
  return {
    canUndo: H.idx > 0,
    canRedo: hasRedo,
    undoLabel: H.idx > 0 ? H.stack[H.idx].label : "",
    redoLabel: hasRedo ? H.stack[H.idx + 1].label : ""
  };
}
function restore(data, prevData) {
  const next = JSON.parse(data);
  const prev = JSON.parse(prevData);
  const d = diffSnapshots(prev, next);
  const carry = (list, fresh) => {
    const cur = new Map(list.map((r) => [r.id, r]));
    return fresh.map((r) => {
      const c = cur.get(r.id);
      r.rid = c ? c.rid ?? null : null;
      r.etag = c ? c.etag ?? null : null;
      return r;
    });
  };
  for (const kind of ["layers", "slots", "placements"]) {
    S[kind] = carry(S[kind], next[kind] || []);
  }
  if (S.site && (S.site.rules || (next.putaway || []).length || (next.replenish || []).length)) {
    const rules = S.site.rules || { putaway: [], replenish: [] };
    S.site.rules = { ...rules, putaway: carry(rules.putaway || [], next.putaway || []), replenish: carry(rules.replenish || [], next.replenish || []) };
  }
  if (d.site && S.site) {
    Object.assign(S.site, next.site);
  }
  S.multi = [];
  S.selCell = null;
  S.edit = null;
  reindex();
  const touched = [...d.changed, ...d.added].filter((e) => e.kind === "slots" || e.kind === "placements");
  const keep = S.sel && (S.sel.kind === "slot" ? S.sIdx : S.pIdx).has(S.sel.id) ? S.sel : null;
  S.sel = touched.length ? { kind: touched[0].kind === "slots" ? "slot" : "placement", id: touched[0].id } : keep;
  return { changedSite: d.site, site: next.site };
}
async function goto(i, verb) {
  const H = S.hist;
  const from = H.stack[H.idx];
  const to = H.stack[i];
  const label = i < H.idx ? from.label : to.label;
  H.busy = true;
  try {
    if (E.adapter?.dirty) {
      await E.flushNow();
    }
    const { changedSite, site } = restore(to.data, from.data);
    H.idx = i;
    E.commit({});
    to.data = H.cur = snapshot();
    if (changedSite && E.adapter?.saveAddr) {
      await E.adapter.saveAddr(site, { renumber: "new" });
      if (E.adapter.serverRenumber) {
        await E.flushNow();
        await E.reload();
      }
    }
    toast(`${verb}: ${label}`);
  } catch (e) {
    toast(e.message || "Не вдалося виконати дію.", "err");
  } finally {
    H.busy = false;
    notify();
  }
}
var guard = () => {
  const acc = E.access?.();
  if (acc && !acc.design) {
    toast(E.accessHint?.("design") || "Правка недоступна.", "warn");
    return false;
  }
  return true;
};
async function undo() {
  undoRecord();
  const H = S.hist;
  if (H.idx <= 0) {
    toast("Немає що скасувати.");
    return false;
  }
  if (!guard()) {
    return false;
  }
  await goto(H.idx - 1, "Скасовано");
  return true;
}
async function redo() {
  undoRecord();
  const H = S.hist;
  if (H.idx < 0 || H.idx >= H.stack.length - 1) {
    toast("Немає що повторити.");
    return false;
  }
  if (!guard()) {
    return false;
  }
  await goto(H.idx + 1, "Повторено");
  return true;
}
Object.assign(E, { undo, redo, undoLabel, undoRecord, undoReset, undoRebase, undoState });
var isZ = (e) => e.code === "KeyZ";
registries.hotkeys.add("undo", { ctrl: true, label: "Ctrl+Z — скасувати", match: (e) => isZ(e) && !e.shiftKey && !e.altKey, run: (e) => (e.preventDefault(), void undo()) }, { sequence: 5, force: true });
registries.hotkeys.add(
  "redo",
  { ctrl: true, label: "Ctrl+Shift+Z / Ctrl+Y — повторити", match: (e) => isZ(e) && e.shiftKey || e.code === "KeyY", run: (e) => (e.preventDefault(), void redo()) },
  { sequence: 6, force: true }
);

// core/constructor/edit_tools.js
var PREFIX_MAX = 22;
var kindOf = (ref2) => ref2.kind === "placement" ? "placement" : "slot";
var arrOf = (kind) => kind === "placement" ? S.placements : S.slots;
var idxOf = (kind) => kind === "placement" ? S.pIdx : S.sIdx;
function selectedItems() {
  return selRefs().map((ref2) => ({ ref: ref2, kind: kindOf(ref2), rec: recOfRef(ref2) })).filter((it) => it.rec);
}
function canEditAll(items) {
  const acc = E.access?.();
  if (acc && !acc.design) {
    toast(E.accessHint?.("design") || "Правка недоступна.", "warn");
    return false;
  }
  for (const it of items) {
    const ly = layerOf(it.rec.layer_id);
    if (!canEditLayer(ly)) {
      toastLock(ly);
      return false;
    }
    if (it.rec.locked) {
      toast("Складний контур зони редагується у формі Odoo.", "warn");
      return false;
    }
  }
  return true;
}
function boxOf(it) {
  if (it.kind === "placement") {
    const v = variantOf(it.rec.variant_id);
    return v ? pGeom(it.rec, v).box : [it.rec.x, it.rec.y, it.rec.x, it.rec.y];
  }
  return sGeom(it.rec).box;
}
function groupBox(items) {
  const bs = items.map(boxOf);
  return [Math.min(...bs.map((b) => b[0])), Math.min(...bs.map((b) => b[1])), Math.max(...bs.map((b) => b[2])), Math.max(...bs.map((b) => b[3]))];
}
function nextCodeLike(code, used, max = PREFIX_MAX) {
  const m = /^(.*?)(\d+)(\D*)$/.exec(code || "");
  const [stem, num4, tail] = m ? [m[1], m[2], m[3]] : [(code || "X") + "-", "1", ""];
  for (let n = Number(num4) + 1; n < 1e5; n++) {
    const cand = stem + String(n).padStart(num4.length, "0") + tail;
    if (!used.has(cand) && cand.length <= max) {
      used.add(cand);
      return cand;
    }
  }
  return code;
}
var cleanAddr = (addr) => {
  if (!addr) {
    return null;
  }
  const { row_no: _pin, ...rest } = addr;
  return Object.keys(rest).length ? rest : null;
};
function copyRec(kind, rec, { dx = 0, dy = 0, layerId = null, used }) {
  const c = clone(rec);
  c.id = newUid();
  c.rid = null;
  c.etag = null;
  c.x = rnd(rec.x + dx, 4);
  c.y = rnd(rec.y + dy, 4);
  if (layerId) {
    c.layer_id = layerId;
  }
  if (kind === "slot") {
    c.overrides = {};
    c.parent_location_id = null;
    c.code_prefix = nextCodeLike(rec.code_prefix, used.prefixes);
    c.addr = cleanAddr(c.addr);
    if (!c.addr) {
      delete c.addr;
    }
    if (c.template === "zone") {
      c.params = { ...c.params, title: `${rec.params?.title || rec.code_prefix} (копія)` };
    }
  } else {
    c.code = nextCodeLike(rec.code || "EQ-00", used.codes, 32);
    c.slot_id = null;
    c.cell_code = null;
    c.equipment = null;
  }
  return c;
}
var usedCodes = () => ({ prefixes: new Set(S.slots.map((s) => s.code_prefix)), codes: new Set(S.placements.map((p) => p.code)) });
function attempt(copies) {
  const before = S.issues;
  for (const c of copies) {
    arrOf(c.kind).push(c.rec);
    idxOf(c.kind).set(c.rec.id, c.rec);
  }
  for (const c of copies) {
    if (c.kind === "placement") {
      E.assignSlot(c.rec);
    }
  }
  const after = runLive();
  const nb = copies.flatMap((c) => newBlocks(before, after, objKey(c.kind, c.rec.id)));
  if (nb.length) {
    for (const c of copies) {
      const a = arrOf(c.kind);
      a.splice(a.indexOf(c.rec), 1);
      idxOf(c.kind).delete(c.rec.id);
    }
    return nb[0].msg;
  }
  return null;
}
var rot = (x, y, deg) => {
  const a = deg * Math.PI / 180;
  return [x * Math.cos(a) - y * Math.sin(a), x * Math.sin(a) + y * Math.cos(a)];
};
function offsetCandidates(items, { prefer = "length", gap = 0.5, aisle = 0 } = {}) {
  const first = items[0].rec;
  const b = groupBox(items);
  const spanX = b[2] - b[0];
  const spanY = b[3] - b[1];
  const single = items.length === 1;
  const g3 = single ? sGeomOrP(items[0]) : { L: spanX, W: spanY, a: 0 };
  const along = [g3.L + gap, 0];
  const across = [0, g3.W + gap + aisle];
  const a = single ? first.rotation || 0 : 0;
  const dirs = prefer === "across" ? [across, along] : [along, across];
  const out = [];
  for (const k of [1, 2, 3]) {
    for (const [ux, uy] of dirs) {
      for (const sgn of [1, -1]) {
        out.push(rot(ux * k * sgn, uy * k * sgn, a));
      }
    }
  }
  return out.map(([dx, dy]) => [rnd(dx, 4), rnd(dy, 4)]);
}
var sGeomOrP = (it) => it.kind === "placement" ? pGeom(it.rec, variantOf(it.rec.variant_id) || { length: 1e3, width: 1e3 }) : sGeom(it.rec);
function afterCopies(made, label) {
  if (!made.length) {
    return;
  }
  S.multi = [];
  S.selCell = null;
  S.sel = { kind: made[made.length - 1].kind, id: made[made.length - 1].rec.id };
  if (made.length > 1) {
    S.multi = made.map((c) => ({ kind: c.kind, id: c.rec.id }));
  }
  E.undoLabel?.(label);
  E.commit({});
  pinNumbers(made.filter((c) => c.kind === "slot" && contextOf(c.rec)).map((c) => c.rec));
}
function duplicateSel(mode = null) {
  const items = selectedItems();
  if (!items.length || !canEditAll(items)) {
    return false;
  }
  const one = items.length === 1 ? items[0] : null;
  if (one && one.kind === "slot" && (mode === "tier" || mode == null && S.selCell && LEVEL_KEYS[one.rec.template])) {
    return addTier(one.rec);
  }
  if (one && one.kind === "slot" && mode === "bay") {
    return addBay(one.rec);
  }
  const ly = layerOf(one ? one.rec.layer_id : items[0].rec.layer_id);
  const rack3 = one && one.kind === "slot" && COUNT_KEY[one.rec.template] && one.rec.template !== "floor_stack";
  const used = usedCodes();
  for (const [dx, dy] of offsetCandidates(items, { prefer: rack3 ? "across" : "length", gap: one && one.kind === "slot" && one.rec.template === "floor_spot" ? 0.3 : 0.5, aisle: rack3 ? ly?.aisle_width || 3 : 0 })) {
    const u = { prefixes: new Set(used.prefixes), codes: new Set(used.codes) };
    const copies = items.map((it) => ({ kind: it.kind, rec: copyRec(it.kind, it.rec, { dx, dy, used: u }) }));
    if (!attempt(copies)) {
      afterCopies(copies, items.length > 1 ? `Дублювання: ${items.length} об’єктів` : `Дублювання: ${items[0].rec.code_prefix || items[0].rec.code}`);
      return true;
    }
  }
  toast("Немає вільного місця поруч для копії.", "warn");
  return false;
}
function addTier(s) {
  const [key] = LEVEL_KEYS[s.template] || [];
  if (!key) {
    toast("У цього місця немає ярусів.", "warn");
    return false;
  }
  return bump(s, key, "Ярус зверху");
}
function addBay(s) {
  const key = COUNT_KEY[s.template];
  if (!key) {
    toast("У цього місця немає секцій.", "warn");
    return false;
  }
  return bump(s, key, "Секція в кінці ряду");
}
function bump(s, key, label) {
  const max = (SLOT_TEMPLATES[s.template].params[key] || SLOT_TEMPLATES[s.template].opt[key] || [])[1] ?? 1e3;
  const cur = Number(s.params[key] ?? ((SLOT_TEMPLATES[s.template].params[key] || [])[2] || 1));
  if (cur + 1 > max) {
    toast(`Досягнуто межу: ${max}.`, "warn");
    return false;
  }
  const before = S.issues;
  s.params[key] = cur + 1;
  S.selCell = null;
  const nb = newBlocks(before, runLive(), objKey("slot", s.id));
  if (nb.length) {
    s.params[key] = cur;
    S.issues = runLive();
    toast("Заблоковано: " + nb[0].msg, "err");
    return false;
  }
  E.undoLabel?.(`${label}: ${s.code_prefix}`);
  E.commit({});
  return true;
}
var clip = null;
function copySel() {
  const items = selectedItems().filter((it) => !it.rec.locked);
  if (!items.length) {
    toast("Немає що копіювати: виділіть об’єкт.", "warn");
    return false;
  }
  const b = groupBox(items);
  clip = { items: items.map((it) => ({ kind: it.kind, rec: clone(it.rec) })), cx: (b[0] + b[2]) / 2, cy: (b[1] + b[3]) / 2, layerId: items[0].rec.layer_id, w: b[2] - b[0], h: b[3] - b[1] };
  toast(items.length > 1 ? `Скопійовано: ${items.length} об’єктів.` : `Скопійовано: ${items[0].rec.code_prefix || items[0].rec.code}.`);
  return true;
}
function targetLayer() {
  const accepts = (ly) => ly && canEditLayer(ly) && clip.items.every((it) => it.kind === "slot" ? ly.slot_types.includes(it.rec.template) : ly.kind !== "building");
  const active = layerOf(S.ui.layer);
  if (accepts(active)) {
    return active;
  }
  const base2 = active ? active.elevation : 0;
  return S.layers.filter(accepts).sort((a, b) => Math.abs(a.elevation - base2) - Math.abs(b.elevation - base2))[0] || null;
}
function pasteClip() {
  if (!clip) {
    toast("Буфер порожній: спершу скопіюйте (Ctrl+C).", "warn");
    return false;
  }
  const acc = E.access?.();
  if (acc && !acc.design) {
    toast(E.accessHint?.("design") || "Правка недоступна.", "warn");
    return false;
  }
  const sel = selectedItems();
  const zone2 = sel.length === 1 && sel[0].kind === "slot" && sel[0].rec.template === "zone" && canEditLayer(layerOf(sel[0].rec.layer_id)) ? sel[0].rec : null;
  const ly = zone2 ? layerOf(zone2.layer_id) : targetLayer();
  if (!ly) {
    toast("Немає шару, що допускає ці об’єкти й дозволяє правку.", "warn");
    return false;
  }
  if (zone2 && !clip.items.every((it) => it.kind === "slot" ? ly.slot_types.includes(it.rec.template) : true)) {
    toast("Зона не підходить: її шар не допускає ці типи місць.", "warn");
    return false;
  }
  const sameLayer = ly.id === clip.layerId;
  const c = E.camTarget ? E.camTarget() : { x: S.site.building.length / 2, y: S.site.building.width / 2 };
  const home = zone2 ? { x: zone2.x, y: zone2.y } : sameLayer ? { x: clip.cx, y: clip.cy } : c;
  const tries = [];
  if (zone2) {
    const zl = zone2.params.length;
    const zw = zone2.params.width;
    for (let k = 0; k < 40; k++) {
      const u = -zl / 2 + 0.5 + clip.w / 2 + k % 6 * (clip.w + 0.5);
      const v = -zw / 2 + 0.5 + clip.h / 2 + Math.floor(k / 6) * (clip.h + 0.5);
      if (Math.abs(u) + clip.w / 2 <= zl / 2 && Math.abs(v) + clip.h / 2 <= zw / 2) {
        const [wx, wy] = rot(u, v, zone2.rotation || 0);
        tries.push([zone2.x + wx - clip.cx, zone2.y + wy - clip.cy]);
      }
    }
  } else {
    const step = Math.max(clip.w, clip.h) + 0.5;
    const first = sameLayer ? [step, 0] : [0, 0];
    tries.push([home.x - clip.cx + first[0], home.y - clip.cy + first[1]]);
    for (const k of [1, 2, 3]) {
      for (const [ux, uy] of [[1, 0], [0, -1], [-1, 0], [0, 1]]) {
        tries.push([home.x - clip.cx + ux * step * k, home.y - clip.cy + uy * step * k]);
      }
    }
  }
  const used = usedCodes();
  for (const [dx, dy] of tries) {
    const u = { prefixes: new Set(used.prefixes), codes: new Set(used.codes) };
    const copies = clip.items.map((it) => ({ kind: it.kind, rec: copyRec(it.kind, it.rec, { dx, dy, layerId: ly.id, used: u }) }));
    if (!attempt(copies)) {
      afterCopies(copies, `Вставлення: ${copies.length > 1 ? copies.length + " об’єктів" : copies[0].rec.code_prefix || copies[0].rec.code}`);
      return true;
    }
  }
  toast(zone2 ? "У зоні немає вільного місця для вставлення." : "Немає вільного місця для вставлення.", "warn");
  return false;
}
function arrayCopies({ nx = 2, ny = 1, dx, dy }) {
  const items = selectedItems();
  if (!items.length || !canEditAll(items)) {
    return 0;
  }
  const b = groupBox(items);
  const stepX = dx ?? rnd(b[2] - b[0] + 0.3, 3);
  const stepY = dy ?? rnd(b[3] - b[1] + 0.3, 3);
  const used = usedCodes();
  const made = [];
  let skipped = 0;
  for (let j = 0; j < ny; j++) {
    for (let i = 0; i < nx; i++) {
      if (!i && !j) {
        continue;
      }
      const copies = items.map((it) => ({ kind: it.kind, rec: copyRec(it.kind, it.rec, { dx: i * stepX, dy: j * stepY, used }) }));
      if (attempt(copies)) {
        skipped++;
        for (const c of copies) {
          (c.kind === "slot" ? used.prefixes : used.codes).delete(c.kind === "slot" ? c.rec.code_prefix : c.rec.code);
        }
      } else {
        made.push(...copies);
      }
    }
  }
  if (made.length) {
    afterCopies(made, `Масив ${nx}×${ny}: ${made.length} копій`);
  }
  toast(made.length ? `Масив: створено ${made.length}${skipped ? `, не вмістилось або заблоковано: ${skipped}` : ""}.` : "Масив: жодної копії не вдалося розмістити.", made.length ? void 0 : "warn");
  return made.length;
}
function applyMoves(items, mutate, label) {
  const before = S.issues;
  const snaps = items.map((it) => ({ it, x: it.rec.x, y: it.rec.y, rotation: it.rec.rotation }));
  mutate();
  const after = runLive();
  const nb = items.flatMap((it) => newBlocks(before, after, objKey(it.ref.kind, it.ref.id)));
  if (nb.length) {
    for (const s of snaps) {
      Object.assign(s.it.rec, { x: s.x, y: s.y, rotation: s.rotation });
    }
    S.issues = runLive();
    toast("Заблоковано: " + nb[0].msg + ". Зміну скасовано.", "err");
    return false;
  }
  for (const it of items) {
    if (it.kind === "placement") {
      E.assignSlot(it.rec);
    }
  }
  E.undoLabel?.(label);
  E.commit({});
  return true;
}
var ALIGN = {
  left: (b, g3) => [g3[0] - b[0], 0],
  right: (b, g3) => [g3[2] - b[2], 0],
  top: (b, g3) => [0, g3[3] - b[3]],
  bottom: (b, g3) => [0, g3[1] - b[1]],
  cx: (b, g3) => [(g3[0] + g3[2]) / 2 - (b[0] + b[2]) / 2, 0],
  cy: (b, g3) => [0, (g3[1] + g3[3]) / 2 - (b[1] + b[3]) / 2]
};
var ALIGN_LABELS = { left: "Ліворуч", right: "Праворуч", top: "Угору", bottom: "Донизу", cx: "Центр X", cy: "Центр Y" };
function alignSel(mode) {
  const items = selectedItems();
  if (items.length < 2 || !ALIGN[mode] || !canEditAll(items)) {
    return false;
  }
  const g3 = groupBox(items);
  return applyMoves(
    items,
    () => {
      for (const it of items) {
        const [dx, dy] = ALIGN[mode](boxOf(it), g3);
        it.rec.x = rnd(it.rec.x + dx, 4);
        it.rec.y = rnd(it.rec.y + dy, 4);
      }
    },
    `Вирівнювання: ${ALIGN_LABELS[mode]}`
  );
}
function distributeSel(axis) {
  const items = selectedItems();
  if (items.length < 3 || !canEditAll(items)) {
    if (items.length < 3) {
      toast("Розподіл потребує щонайменше трьох об’єктів.", "warn");
    }
    return false;
  }
  const lo = axis === "x" ? 0 : 1;
  const hi = lo + 2;
  const rows = items.map((it) => ({ it, b: boxOf(it) })).sort((a, b) => a.b[lo] + a.b[hi] - (b.b[lo] + b.b[hi]));
  const span = rows[rows.length - 1].b[hi] - rows[0].b[lo];
  const total = rows.reduce((s, r) => s + (r.b[hi] - r.b[lo]), 0);
  const gap = (span - total) / (rows.length - 1);
  return applyMoves(
    items,
    () => {
      let pos = rows[0].b[hi] + gap;
      for (let i = 1; i < rows.length - 1; i++) {
        const d = pos - rows[i].b[lo];
        rows[i].it.rec[axis] = rnd(rows[i].it.rec[axis] + d, 4);
        pos += rows[i].b[hi] - rows[i].b[lo] + gap;
      }
    },
    `Розподіл по ${axis === "x" ? "X" : "Y"}`
  );
}
function rotateGroup(dir = 1) {
  const items = selectedItems();
  if (!items.length || !canEditAll(items)) {
    return false;
  }
  const g3 = groupBox(items);
  const cx = (g3[0] + g3[2]) / 2;
  const cy = (g3[1] + g3[3]) / 2;
  for (const it of items) {
    if (it.kind === "placement") {
      const al = rotationsList(variantOf(it.rec.variant_id));
      if (al && !al.includes(normDeg((it.rec.rotation || 0) + 90 * dir))) {
        toast(`Для «${it.rec.code}» поворот не дозволено.`, "warn");
        return false;
      }
    }
  }
  return applyMoves(
    items,
    () => {
      for (const it of items) {
        const [dx, dy] = [it.rec.x - cx, it.rec.y - cy];
        const [nx, ny] = dir > 0 ? [-dy, dx] : [dy, -dx];
        it.rec.x = rnd(cx + nx, 4);
        it.rec.y = rnd(cy + ny, 4);
        it.rec.rotation = normDeg((it.rec.rotation || 0) + 90 * dir);
      }
    },
    items.length > 1 ? "Поворот рядів" : `Поворот: ${items[0].rec.code_prefix || items[0].rec.code}`
  );
}
async function removeAll() {
  const items = selectedItems();
  if (!items.length || !canEditAll(items)) {
    return false;
  }
  const ok = await E.confirmBox({ title: "Прибрати виділене?", text: `Буде видалено ${items.length} об’єктів із чернетки.`, ok: "Прибрати", danger: true });
  if (!ok) {
    return false;
  }
  const ids = new Set(items.map((it) => it.ref.kind + ":" + it.ref.id));
  S.slots = S.slots.filter((s) => !ids.has("slot:" + s.id));
  S.placements = S.placements.filter((p) => !ids.has("placement:" + p.id));
  for (const p of S.placements) {
    if (p.slot_id && !S.slots.some((s) => s.id === p.slot_id)) {
      p.slot_id = null;
    }
  }
  S.sel = null;
  S.multi = [];
  S.selCell = null;
  E.undoLabel?.(`Видалення: ${items.length} об’єктів`);
  E.commit({});
  return true;
}
function groupToZone() {
  const items = selectedItems().filter((it) => it.rec.template !== "zone");
  if (items.length < 2 || !canEditAll(items)) {
    if (items.length < 2) {
      toast("Для групування виділіть щонайменше два об’єкти (не зони).", "warn");
    }
    return false;
  }
  const lids = new Set(items.map((it) => it.rec.layer_id));
  if (lids.size > 1) {
    toast("Групувати можна об’єкти одного шару.", "warn");
    return false;
  }
  const ly = layerOf([...lids][0]);
  if (!ly.slot_types.includes("zone")) {
    toast(`Шар «${ly.name}» не допускає зони.`, "warn");
    return false;
  }
  const slots = items.filter((it) => it.kind === "slot").map((it) => it.rec);
  const zones = new Set(slots.map((s) => (contextOf(s) || {}).zone ?? null));
  const prevZone = zones.size === 1 ? [...zones][0] : null;
  pinNumbers(slots.filter((s) => contextOf(s)));
  const g3 = groupBox(items);
  const m = 1;
  const prefix = nextPrefix({ ref: "ZN", code: "ZN" });
  const zone2 = {
    id: newUid(),
    rid: null,
    etag: null,
    layer_id: ly.id,
    template: "zone",
    code_prefix: prefix,
    x: rnd((g3[0] + g3[2]) / 2, 4),
    y: rnd((g3[1] + g3[3]) / 2, 4),
    rotation: 0,
    params: { length: rnd(g3[2] - g3[0] + 2 * m, 3), width: rnd(g3[3] - g3[1] + 2 * m, 3), title: `Група ${prefix}`, color: ly.color },
    overrides: {},
    parent_location_id: null
  };
  if (prevZone != null) {
    zone2.addr = { zone_code: String(prevZone) };
  }
  const copies = [{ kind: "slot", rec: zone2 }];
  const why = attempt(copies);
  if (why) {
    toast("Заблоковано: " + why, "err");
    return false;
  }
  S.multi = [];
  S.sel = { kind: "slot", id: zone2.id };
  E.undoLabel?.(`Групування в зону: ${items.length} об’єктів`);
  E.commit({});
  toast(`Створено зону «${zone2.params.title}».`);
  return true;
}
async function ungroupZone() {
  const items = selectedItems();
  const zone2 = items.length === 1 && items[0].kind === "slot" && items[0].rec.template === "zone" ? items[0].rec : null;
  if (!zone2) {
    toast("Виділіть зону, яку треба розгрупувати.", "warn");
    return false;
  }
  if (!canEditAll(items)) {
    return false;
  }
  const inside = S.slots.filter((s) => s.id !== zone2.id && s.template !== "zone" && s.layer_id === zone2.layer_id && (contextOf(s) || {}).zone != null);
  const ok = await E.confirmBox({ title: "Розгрупувати зону?", text: `Зону «${zone2.params.title || zone2.code_prefix}» буде видалено; об’єкти всередині лишаться, їхні коди не змінюються.`, ok: "Розгрупувати" });
  if (!ok) {
    return false;
  }
  pinNumbers(inside);
  S.slots = S.slots.filter((s) => s.id !== zone2.id);
  S.sel = null;
  S.multi = [];
  E.undoLabel?.(`Розгрупування: ${zone2.params.title || zone2.code_prefix}`);
  E.commit({});
  return true;
}
function applyProps({ rotation, dx, dy }) {
  const items = selectedItems();
  if (!items.length || !canEditAll(items)) {
    return false;
  }
  const hasRot = rotation != null && rotation !== "";
  const mx = Number(dx) || 0;
  const my = Number(dy) || 0;
  if (!hasRot && !mx && !my) {
    toast("Немає змін: вкажіть поворот чи зсув.", "warn");
    return false;
  }
  return applyMoves(
    items,
    () => {
      for (const it of items) {
        if (hasRot) {
          it.rec.rotation = Number(rotation);
        }
        it.rec.x = rnd(it.rec.x + mx, 4);
        it.rec.y = rnd(it.rec.y + my, 4);
      }
    },
    `Властивості: ${items.length} об’єктів`
  );
}
var BULK_TEMPLATES = ["pallet_rack", "shelf", "cantilever", "floor_stack", "floor_spot"];
var SECT_KEY = { pallet_rack: "bays", shelf: "sections", cantilever: "arms", floor_stack: "cols", floor_spot: null };
var LVL_KEY = { pallet_rack: "levels", shelf: "shelves", cantilever: "levels", floor_stack: null, floor_spot: null };
function bulkLayout({ template, rows, sections, levels, aisle, vertical, zoneId }) {
  const params = {};
  if (SECT_KEY[template]) {
    params[SECT_KEY[template]] = sections;
  }
  if (LVL_KEY[template]) {
    params[LVL_KEY[template]] = levels;
  }
  const full = { ...Object.fromEntries(Object.entries(SLOT_TEMPLATES[template].params).map(([k, v]) => [k, v[2]])), ...params };
  const fp = footprint(template, full);
  const zone2 = zoneId ? S.sIdx.get(zoneId) : null;
  const b = S.site.building;
  const region = zone2 ? { cx: zone2.x, cy: zone2.y, l: zone2.params.length, w: zone2.params.width, rot: zone2.rotation || 0 } : { cx: b.length / 2, cy: b.width / 2, l: b.length, w: b.width, rot: 0 };
  const step = (layerOf(S.ui.layer) || {}).grid_step || 0.5;
  const [fl, fw] = vertical ? [fp.w, fp.l] : [fp.l, fp.w];
  const out = [];
  const cos = Math.cos(region.rot * Math.PI / 180);
  const sin = Math.sin(region.rot * Math.PI / 180);
  for (let i = 0; i < rows; i++) {
    const u = -region.l / 2 + 0.5 + fl / 2;
    const v = -region.w / 2 + 0.5 + fw / 2 + i * (fw + aisle);
    if (u + fl / 2 > region.l / 2 - 0.5 + 1e-6 || v + fw / 2 > region.w / 2 - 0.5 + 1e-6) {
      break;
    }
    out.push({ x: rnd(Math.round((region.cx + u * cos - v * sin) / step) * step, 4), y: rnd(Math.round((region.cy + u * sin + v * cos) / step) * step, 4), rotation: normDeg(region.rot + (vertical ? 90 : 0)), params: { ...full } });
  }
  return { rows: out, fp: { l: fl, w: fw }, region, cells: out.length * sections * (levels || 1) };
}
function bulkCreate(o) {
  const ly = layerOf(S.ui.layer);
  if (!ly || !canEditLayer(ly)) {
    toast(ly ? lockHint(ly) : "Немає активного шару.", "warn");
    return 0;
  }
  if (!ly.slot_types.includes(o.template)) {
    toast(`Шар «${ly.name}» не допускає цей тип місця.`, "warn");
    return 0;
  }
  const lay = bulkLayout(o);
  const used = new Set(S.slots.map((s) => s.code_prefix));
  const list = lay.rows.map((r) => {
    const prefix = nextPrefix({ ref: TPL[o.template].prefix, code: o.template }, used);
    used.add(prefix);
    return { ...r, template: o.template, prefix };
  });
  E.undoLabel?.(`Масове створення: ${list.length} рядів`);
  const made = addSlots(list);
  toast(made.length ? `Створено рядів: ${made.length}${made.length < o.rows ? `; не вмістилось або заблоковано: ${o.rows - made.length}` : ""}.` : "У зоні немає вільного місця.", made.length ? void 0 : "warn");
  return made.length;
}
function previewSvg(lay) {
  const r = lay.region;
  const W = 320;
  const k = W / Math.max(r.l, 1);
  const Hh = Math.max(40, r.w * k);
  const rects = lay.rows.map((row) => {
    const u = ((row.x - r.cx) * Math.cos(-r.rot * Math.PI / 180) - (row.y - r.cy) * Math.sin(-r.rot * Math.PI / 180)) * k;
    const v = ((row.x - r.cx) * Math.sin(-r.rot * Math.PI / 180) + (row.y - r.cy) * Math.cos(-r.rot * Math.PI / 180)) * k;
    return `<rect x="${(W / 2 + u - lay.fp.l * k / 2).toFixed(1)}" y="${(Hh / 2 - v - lay.fp.w * k / 2).toFixed(1)}" width="${(lay.fp.l * k).toFixed(1)}" height="${(lay.fp.w * k).toFixed(1)}" fill="var(--accent-soft)" stroke="var(--accent)"/>`;
  }).join("");
  return `<svg viewBox="0 0 ${W} ${Hh.toFixed(0)}" width="100%" style="max-height:200px;border:1px solid var(--line);background:var(--surface2)"><rect x="0.5" y="0.5" width="${W - 1}" height="${(Hh - 1).toFixed(0)}" fill="none" stroke="var(--ink3)" stroke-dasharray="4 3"/>${rects}</svg>`;
}
function openBulk() {
  const ly = layerOf(S.ui.layer);
  const zones = S.slots.filter((s) => s.template === "zone" && s.layer_id === S.ui.layer);
  const sel = selectedItems();
  const st = { template: BULK_TEMPLATES.find((t) => ly && ly.slot_types.includes(t)) || "pallet_rack", rows: 4, sections: 6, levels: 3, aisle: ly && ly.aisle_width || 3, orient: "h", zoneId: sel.length === 1 && sel[0].rec.template === "zone" ? sel[0].rec.id : zones[0]?.id || "" };
  const prev = h("div", { id: "bulkPreview" });
  const info = h("div", { class: "small muted", id: "bulkInfo" });
  const draw = () => {
    const lay = bulkLayout({ ...st, vertical: st.orient === "v" });
    prev.innerHTML = previewSvg(lay);
    info.textContent = `Рядів: ${lay.rows.length} із ${st.rows} · комірок: ${lay.cells} · габарит ряду ${fmt(lay.fp.l, 1)}×${fmt(lay.fp.w, 1)} м`;
  };
  const num4 = (key, label, min, max, step = 1) => {
    const el = h("input", { type: "number", min, max, step, value: st[key], "aria-label": label, "data-s3": key });
    el.addEventListener("input", () => {
      const v = parseFloat(el.value);
      if (isFinite(v) && v >= min && v <= max) {
        st[key] = v;
        draw();
      }
    });
    return fld(label, el);
  };
  const body = h(
    "div",
    { class: "fcol", id: "bulkBody" },
    h("div", { class: "grid2" }, fld("Тип місця", selectEl(BULK_TEMPLATES.filter((t) => ly && ly.slot_types.includes(t)).map((t) => [t, SLOT_TEMPLATES[t].label || t]), st.template, (v) => {
      st.template = v;
      draw();
    }, false, "Тип місця")), fld("Зона", selectEl([["", "Вся будівля"], ...zones.map((z) => [z.id, z.params.title || z.code_prefix])], st.zoneId, (v) => {
      st.zoneId = v;
      draw();
    }, false, "Зона"))),
    h("div", { class: "grid3" }, num4("rows", "Рядів", 1, 60), num4("sections", "Секцій у ряду", 1, 60), num4("levels", "Ярусів", 1, 12)),
    h("div", { class: "grid2" }, num4("aisle", "Прохід між рядами, м", 0, 12, 0.1), fld("Орієнтація", selectEl([["h", "Уздовж зони"], ["v", "Упоперек"]], st.orient, (v) => {
      st.orient = v;
      draw();
    }, false, "Орієнтація"))),
    prev,
    info
  );
  draw();
  openDialog({
    title: "Масове створення",
    cls: "narrow",
    body,
    actions: [
      { label: "Скасувати", value: "no" },
      {
        label: "Створити",
        cls: "primary",
        id: "btnBulkGo",
        onClick: () => {
          const n = bulkCreate({ ...st, vertical: st.orient === "v" });
          return n ? void 0 : false;
        }
      }
    ]
  });
}
function openArray() {
  const items = selectedItems();
  if (!items.length) {
    toast("Виділіть об’єкт для масиву.", "warn");
    return;
  }
  const b = groupBox(items);
  const st = { nx: 3, ny: 2, dx: rnd(b[2] - b[0] + 0.3, 2), dy: rnd(b[3] - b[1] + 0.3, 2) };
  const num4 = (key, label, min, max, step = 1) => {
    const el = h("input", { type: "number", min, max, step, value: st[key], "aria-label": label, "data-s3": key });
    el.addEventListener("input", () => {
      const v = parseFloat(el.value);
      if (isFinite(v)) {
        st[key] = v;
      }
    });
    return fld(label, el);
  };
  openDialog({
    title: "Масив копій",
    cls: "narrow",
    body: h("div", { class: "fcol", id: "arrayBody" }, h("div", { class: "grid2" }, num4("nx", "Копій по X (N)", 1, 50), num4("ny", "Копій по Y (M)", 1, 50)), h("div", { class: "grid2" }, num4("dx", "Крок X, м", -500, 500, 0.05), num4("dy", "Крок Y, м", -500, 500, 0.05)), h("div", { class: "small muted" }, "Копії — того ж типу, з наступними кодами; заблоковані перевірками пропускаються.")),
    actions: [
      { label: "Скасувати", value: "no" },
      { label: "Створити", cls: "primary", id: "btnArrayGo", onClick: () => arrayCopies({ nx: Math.round(st.nx), ny: Math.round(st.ny), dx: st.dx, dy: st.dy }) ? void 0 : false }
    ]
  });
}
registries.dialogs.add("bulk", () => openBulk(), { force: true });
registries.dialogs.add("array", () => openArray(), { force: true });
var designOnly = () => !E.access?.().design;
registries.menu.add("bulk", { area: "more", label: "Масове створення…", icon: "plus", sequence: 40, run: () => E.runDialog("bulk"), disabled: designOnly }, { sequence: 40, force: true });
registries.menu.add("array", { area: "more", label: "Масив копій…", icon: "copy", sequence: 41, run: () => E.runDialog("array"), disabled: () => designOnly() || !selRefs().length }, { sequence: 41, force: true });
var hk = (key, def, seq) => registries.hotkeys.add(key, { ctrl: true, ...def }, { sequence: seq, force: true });
hk("duplicate", { label: "Ctrl+D — дублювати", match: (e) => e.code === "KeyD" && !e.shiftKey, when: () => selRefs().length > 0, run: (e) => (e.preventDefault(), void duplicateSel()) }, 12);
hk("copy", { label: "Ctrl+C — копіювати", match: (e) => e.code === "KeyC" && !e.shiftKey, when: () => selRefs().length > 0, run: (e) => (e.preventDefault(), void copySel()) }, 13);
hk("paste", { label: "Ctrl+V — вставити", match: (e) => e.code === "KeyV" && !e.shiftKey, when: () => !!clip, run: (e) => (e.preventDefault(), void pasteClip()) }, 14);
registries.hotkeys.add("multi.rotate", { alt: true, label: "R — повернути виділені ряди", code: "KeyR", when: () => S.multi.length > 1, run: (e) => (e.preventDefault(), void rotateGroup(e.shiftKey ? -1 : 1)) }, { sequence: 15, force: true });
registries.hotkeys.add(
  "multi.delete",
  { match: (e) => e.code === "Delete" || e.code === "Backspace", when: () => S.multi.length > 1, run: (e) => (e.preventDefault(), void removeAll()) },
  { sequence: 25, force: true }
);
hk(
  "selectAll",
  {
    label: "Ctrl+A — виділити все на шарі",
    match: (e) => e.code === "KeyA" && !e.shiftKey,
    run(e) {
      e.preventDefault();
      const refs = [
        ...S.slots.filter((s) => s.layer_id === S.ui.layer && !(layerOf(s.layer_id) || {}).kind?.match(/building|engineering/)).map((s) => ({ kind: "slot", id: s.id })),
        ...S.placements.filter((p) => p.layer_id === S.ui.layer).map((p) => ({ kind: "placement", id: p.id }))
      ];
      E.boxSelect(refs, false);
    }
  },
  16
);
Object.assign(E, { duplicateSel, copySel, pasteClip, arrayCopies, alignSel, distributeSel, rotateGroup, removeAll, groupToZone, ungroupZone, applyProps, bulkCreate });

// core/constructor/selection.js
var same3 = (a, b) => a.kind === b.kind && a.id === b.id;
function setMulti(refs, primary = null) {
  const uniq = [];
  for (const r of refs) {
    if (!uniq.some((u) => same3(u, r))) {
      uniq.push({ kind: r.kind, id: r.id });
    }
  }
  S.selCell = null;
  S.edit = null;
  if (uniq.length >= 2) {
    S.multi = uniq;
    S.sel = primary && uniq.some((u) => same3(u, primary)) ? { kind: primary.kind, id: primary.id } : { ...uniq[uniq.length - 1] };
  } else {
    S.multi = [];
    S.sel = uniq[0] || null;
  }
  E.renderRight();
  E.updateVisual();
  if (S.ui.leftTab === "slots") {
    E.renderLeft();
  }
}
function toggleMulti(ref2) {
  const cur = selRefs();
  const has = cur.some((r) => same3(r, ref2));
  setMulti(has ? cur.filter((r) => !same3(r, ref2)) : [...cur, ref2], has ? null : ref2);
}
function boxSelect(refs, add = false) {
  setMulti([...add ? selRefs() : [], ...refs]);
  if (refs.length) {
    toast(`Виділено: ${selRefs().length}.`);
  }
}
var origSelect = E.selectObj;
E.selectObj = function selectObjMulti(ref2, ...rest) {
  S.multi = [];
  return origSelect.call(this, ref2, ...rest);
};
var origRight = E.renderRight;
E.renderRight = function renderRightMulti(...args) {
  if (S.multi.length > 1) {
    return renderMultiPanel();
  }
  return origRight.apply(this, args);
};
var nameOf3 = (it) => it.kind === "slot" ? it.rec.params?.title || it.rec.code_prefix : it.rec.code || it.rec.name;
function renderMultiPanel() {
  const root = $("#rightBody");
  if (!root) {
    return;
  }
  root.replaceChildren();
  const items = selectedItems();
  const acc = E.access();
  const btn = (label, fn, o = {}) => {
    const b = h("button", { class: "fbtn sm" + (o.cls ? " " + o.cls : ""), type: "button", id: o.id, "data-title": o.title || "", onclick: fn }, o.icon ? ic(o.icon) : null, label);
    b.disabled = !acc.design || !!o.dis;
    b.title = !acc.design ? E.accessHint("design") : o.title || "";
    return b;
  };
  const list = h(
    "div",
    { class: "mlist", id: "multiList", style: { maxHeight: "180px", overflow: "auto", border: "1px solid var(--line)" } },
    items.map(
      (it) => h(
        "div",
        { class: "frow", "data-key": it.ref.kind + ":" + it.ref.id, style: { padding: "2px 6px", borderBottom: "1px solid var(--line2)" } },
        h("button", { class: "linkbtn", type: "button", style: { flex: "1", textAlign: "left", border: 0, background: "none", cursor: "pointer", fontWeight: S.sel && same3(S.sel, it.ref) ? "600" : "400" }, onclick: () => setMulti(items.map((x) => x.ref), it.ref) }, nameOf3(it)),
        h("span", { class: "small muted" }, it.kind === "slot" ? it.rec.template : "обладнання"),
        h("button", { class: "xbtn", type: "button", "aria-label": "Прибрати з виділення", onclick: () => toggleMulti(it.ref) }, ic("x"))
      )
    )
  );
  const slots = items.filter((it) => it.kind === "slot").map((it) => it.rec);
  const props = { rotation: "", dx: 0, dy: 0 };
  const num4 = (key, label) => {
    const el = h("input", { type: "number", step: 0.5, value: props[key], "aria-label": label, "data-s3": key });
    el.addEventListener("input", () => props[key] = parseFloat(el.value) || 0);
    return fld(label, el);
  };
  root.append(
    h("div", { class: "sec", id: "multiPanel" }, h("h3", null, `Виділено ${items.length}`), list),
    h(
      "div",
      { class: "sec" },
      h("h3", null, "Дії"),
      h(
        "div",
        { class: "frow wrap" },
        btn("Дублювати всі", () => duplicateSel(), { id: "btnMultiDup", icon: "copy", title: "Ctrl+D" }),
        btn("Копіювати", () => copySel(), { id: "btnMultiCopy", title: "Ctrl+C" }),
        btn("Повернути ряди", () => rotateGroup(1), { id: "btnMultiRot", icon: "rot", title: "R" }),
        btn("Прибрати всі", () => removeAll(), { id: "btnMultiDel", icon: "trash", cls: "danger", title: "Del" }),
        btn("Зберегти виділене", () => saveGroupPreset(slots), { id: "btnMultiPreset", dis: !slots.length || !canWriteLibrary(), title: canWriteLibrary() ? "Пресет «виділене» в бібліотеку" : "Бібліотеку пише проєктувальник" })
      )
    ),
    h(
      "div",
      { class: "sec" },
      h("h3", null, "Вирівнювання"),
      h("div", { class: "frow wrap", id: "alignBox" }, Object.entries(ALIGN_LABELS).map(([k, t]) => btn(t, () => alignSel(k), { id: "btnAlign-" + k }))),
      h("div", { class: "frow wrap" }, btn("Розподілити по X", () => distributeSel("x"), { id: "btnDistX", dis: items.length < 3 }), btn("Розподілити по Y", () => distributeSel("y"), { id: "btnDistY", dis: items.length < 3 }))
    ),
    h(
      "div",
      { class: "sec" },
      h("h3", null, "Групи"),
      h("div", { class: "frow wrap" }, btn("Згрупувати в нову зону", () => groupToZone(), { id: "btnGroupZone" }), btn("Розгрупувати зону", () => ungroupZone(), { id: "btnUngroup", dis: !(items.length === 1 && items[0].rec.template === "zone") }))
    ),
    h(
      "div",
      { class: "sec" },
      h("h3", null, "Властивості"),
      h("div", { class: "grid3" }, fld("Поворот", selectEl([["", "—"], ["0", "0°"], ["90", "90°"], ["180", "180°"], ["270", "270°"]], "", (v) => props.rotation = v, !acc.design, "Поворот")), num4("dx", "Зсув X, м"), num4("dy", "Зсув Y, м")),
      h("div", { class: "small muted" }, "Застосовуються лише змінені поля."),
      btn("Застосувати", () => applyProps(props), { id: "btnMultiApply" })
    )
  );
}
async function saveGroupPreset(slots) {
  const draft = { name: `Виділене (${slots.length})` };
  openDialog({
    title: "Зберегти виділене",
    cls: "narrow",
    body: h("div", { class: "fcol" }, fld("Назва шаблону", textInput({ value: draft.name, label: "Назва шаблону", f: "multi-preset-name", set: (v) => draft.name = v })), h("div", { class: "small muted" }, "Місця зберігаються з взаємним розташуванням; шаблон потрапляє в бібліотеку.")),
    actions: [
      { label: "Скасувати", value: "no" },
      {
        label: "Зберегти",
        cls: "primary",
        id: "btnMultiPresetGo",
        onClick: async () => {
          try {
            const rec = await saveRecord(E.adapter, "preset", presetFromSlots(slots, draft.name.trim() || "Виділене"));
            toast(`Шаблон «${rec.name}» збережено в бібліотеці.`);
            return true;
          } catch (e) {
            toast(e.message || "Не вдалося зберегти шаблон.", "err");
            return false;
          }
        }
      }
    ]
  });
}
function renderToolsBlock(root, { rec }) {
  if (!rec || !S.sel || S.multi.length > 1) {
    return;
  }
  const acc = E.access();
  const slot = S.sel.kind === "slot" ? rec : null;
  const b = (label, fn, id, title) => {
    const el = h("button", { class: "fbtn sm", type: "button", id, onclick: fn }, label);
    el.disabled = !acc.design;
    el.title = !acc.design ? E.accessHint("design") : title || "";
    return el;
  };
  const tier = slot && LEVEL_KEYS[slot.template];
  const bay = slot && COUNT_KEY[slot.template];
  root.append(
    h(
      "div",
      { class: "sec", id: "toolsBlock" },
      h("h3", null, "Дублювання й копії"),
      h(
        "div",
        { class: "frow wrap" },
        b(slot && slot.template === "zone" ? "Копія зони" : slot && tier ? "Ряд із наступним номером" : "Дублювати", () => duplicateSel(slot && tier ? "row" : null), "btnDup", "Ctrl+D"),
        tier ? b("Ярус зверху", () => duplicateSel("tier"), "btnDupTier", "Додати ярус над останнім") : null,
        bay ? b("Секція в кінець ряду", () => duplicateSel("bay"), "btnDupBay", "Додати секцію в кінці ряду") : null,
        b("Копіювати", () => copySel(), "btnCopy", "Ctrl+C; вставлення — Ctrl+V"),
        slot && slot.template === "zone" ? b("Розгрупувати", () => ungroupZone(), "btnUngroup", "Прибрати зону; об’єкти всередині лишаються") : null,
        b("Масив…", () => E.runDialog("array"), "btnArray", "N×M копій із кроком")
      )
    )
  );
}
registries.panels.add("right:tools", { area: "right", render: renderToolsBlock }, { sequence: 60, force: true });
Object.assign(E, { setMulti, toggleMulti, boxSelect });

// core/constructor/barcode.js
var C128 = "212222 222122 222221 121223 121322 131222 122213 122312 132212 221213 221312 231212 112232 122132 122231 113222 123122 123221 223211 221132 221231 213212 223112 312131 311222 321122 321221 312212 322112 322211 212123 212321 232121 111323 131123 131321 112313 132113 132311 211313 231113 231311 112133 112331 132131 113123 113321 133121 313121 211331 231131 213113 213311 213131 311123 311321 331121 312113 312311 332111 314111 221411 431111 111224 111422 121124 121421 141122 141221 112214 112412 122114 122411 142112 142211 241211 221114 413111 241112 134111 111242 121142 121241 114212 124112 124211 411212 421112 421211 212141 214121 412121 111143 111341 131141 114113 114311 411113 411311 113141 114131 311141 411131 211412 211214 211232 2331112".split(
  " "
);
var START_B = 104;
var START_C = 105;
var CODE_B = 100;
var CODE_C = 99;
var STOP = 106;
var isPrintableAscii = (text) => /^[\x20-\x7e]*$/.test(text);
var digitRun = (text, i) => {
  let n = 0;
  while (i + n < text.length && text.charCodeAt(i + n) >= 48 && text.charCodeAt(i + n) <= 57) {
    n++;
  }
  return n;
};
function code128Values(text) {
  const s = String(text);
  if (!s.length) {
    throw new Error("Code128: порожній рядок.");
  }
  if (!isPrintableAscii(s)) {
    throw new Error("Code128: лише друкований ASCII (для інших символів — QR).");
  }
  const out = [];
  let set = null;
  let i = 0;
  const run0 = digitRun(s, 0);
  if (run0 >= 4 || run0 === s.length && run0 >= 2) {
    out.push(START_C);
    set = "C";
  } else {
    out.push(START_B);
    set = "B";
  }
  while (i < s.length) {
    const run = digitRun(s, i);
    if (set === "B") {
      if (run >= 6 || run >= 4 && i + run === s.length) {
        if (run % 2) {
          out.push(s.charCodeAt(i) - 32);
          i++;
        }
        out.push(CODE_C);
        set = "C";
        continue;
      }
      out.push(s.charCodeAt(i) - 32);
      i++;
    } else {
      if (run >= 2) {
        out.push(Number(s.slice(i, i + 2)));
        i += 2;
      } else {
        out.push(CODE_B);
        set = "B";
      }
    }
  }
  let sum = out[0];
  for (let k = 1; k < out.length; k++) {
    sum += out[k] * k;
  }
  out.push(sum % 103, STOP);
  return out;
}
function code128(text) {
  const values = code128Values(text);
  let bits = "";
  for (const v of values) {
    const pat = C128[v];
    let bar = true;
    for (const ch of pat) {
      bits += (bar ? "1" : "0").repeat(Number(ch));
      bar = !bar;
    }
  }
  return { values, modules: bits, width: bits.length };
}
var RS = [
  [[1, 26, 19], [1, 26, 16], [1, 26, 13], [1, 26, 9]],
  [[1, 44, 34], [1, 44, 28], [1, 44, 22], [1, 44, 16]],
  [[1, 70, 55], [1, 70, 44], [2, 35, 17], [2, 35, 13]],
  [[1, 100, 80], [2, 50, 32], [2, 50, 24], [4, 25, 9]],
  [[1, 134, 108], [2, 67, 43], [2, 33, 15, 2, 34, 16], [2, 33, 11, 2, 34, 12]],
  [[2, 86, 68], [4, 43, 27], [4, 43, 19], [4, 43, 15]],
  [[2, 98, 78], [4, 49, 31], [2, 32, 14, 4, 33, 15], [4, 39, 13, 1, 40, 14]],
  [[2, 121, 97], [2, 60, 38, 2, 61, 39], [4, 40, 18, 2, 41, 19], [4, 40, 14, 2, 41, 15]],
  [[2, 146, 116], [3, 58, 36, 2, 59, 37], [4, 36, 16, 4, 37, 17], [4, 36, 12, 4, 37, 13]],
  [[2, 86, 68, 2, 87, 69], [4, 69, 43, 1, 70, 44], [6, 43, 19, 2, 44, 20], [6, 43, 15, 2, 44, 16]],
  [[4, 101, 81], [1, 80, 50, 4, 81, 51], [4, 50, 22, 4, 51, 23], [3, 36, 12, 8, 37, 13]],
  [[2, 116, 92, 2, 117, 93], [6, 58, 36, 2, 59, 37], [4, 46, 20, 6, 47, 21], [7, 42, 14, 4, 43, 15]],
  [[4, 133, 107], [8, 59, 37, 1, 60, 38], [8, 44, 20, 4, 45, 21], [12, 33, 11, 4, 34, 12]],
  [[3, 145, 115, 1, 146, 116], [4, 64, 40, 5, 65, 41], [11, 36, 16, 5, 37, 17], [11, 36, 12, 5, 37, 13]],
  [[5, 109, 87, 1, 110, 88], [5, 65, 41, 5, 66, 42], [5, 54, 24, 7, 55, 25], [11, 36, 12, 7, 37, 13]]
];
var ALIGN2 = [[], [6, 18], [6, 22], [6, 26], [6, 30], [6, 34], [6, 22, 38], [6, 24, 42], [6, 26, 46], [6, 28, 50], [6, 30, 54], [6, 32, 58], [6, 34, 62], [6, 26, 46, 66], [6, 26, 48, 70]];
var ECC_INDEX = { L: 0, M: 1, Q: 2, H: 3 };
var ECC_FORMAT = { L: 1, M: 0, Q: 3, H: 2 };
var QR_MAX_VERSION = RS.length;
var blocksOf = (version, ecc) => {
  const e = RS[version - 1][ECC_INDEX[ecc]];
  const out = [];
  for (let i = 0; i < e.length; i += 3) {
    for (let k = 0; k < e[i]; k++) {
      out.push({ total: e[i + 1], data: e[i + 2] });
    }
  }
  return out;
};
var dataCodewords = (version, ecc) => blocksOf(version, ecc).reduce((n, b) => n + b.data, 0);
var EXP = new Array(512);
var LOG = new Array(256);
for (let i = 0, x = 1; i < 255; i++) {
  EXP[i] = x;
  LOG[x] = i;
  x <<= 1;
  if (x & 256) {
    x ^= 285;
  }
}
for (let i = 255; i < 512; i++) {
  EXP[i] = EXP[i - 255];
}
var gmul = (a, b) => a && b ? EXP[LOG[a] + LOG[b]] : 0;
function rsGenerator(deg) {
  let g3 = [1];
  for (let i = 0; i < deg; i++) {
    const next = new Array(g3.length + 1).fill(0);
    for (let j = 0; j < g3.length; j++) {
      next[j] ^= g3[j];
      next[j + 1] ^= gmul(g3[j], EXP[i]);
    }
    g3 = next;
  }
  return g3;
}
function rsRemainder(data, deg) {
  const gen = rsGenerator(deg);
  const rem = new Array(deg).fill(0);
  for (const b of data) {
    const f = b ^ rem.shift();
    rem.push(0);
    if (f) {
      for (let i = 0; i < deg; i++) {
        rem[i] ^= gmul(gen[i + 1], f);
      }
    }
  }
  return rem;
}
var utf8 = (text) => Array.from(new TextEncoder().encode(text));
function buildCodewords(bytes, version, ecc) {
  const cap = dataCodewords(version, ecc) * 8;
  const bits = [];
  const put = (val, n) => {
    for (let i = n - 1; i >= 0; i--) {
      bits.push(val >>> i & 1);
    }
  };
  put(4, 4);
  put(bytes.length, version <= 9 ? 8 : 16);
  for (const b of bytes) {
    put(b, 8);
  }
  put(0, Math.min(4, cap - bits.length));
  while (bits.length % 8) {
    bits.push(0);
  }
  for (let pad = 236; bits.length < cap; pad ^= 236 ^ 17) {
    put(pad, 8);
  }
  const data = [];
  for (let i = 0; i < bits.length; i += 8) {
    data.push(parseInt(bits.slice(i, i + 8).join(""), 2));
  }
  const blocks = blocksOf(version, ecc);
  let pos = 0;
  const parts = blocks.map((b) => {
    const d = data.slice(pos, pos + b.data);
    pos += b.data;
    return { d, e: rsRemainder(d, b.total - b.data) };
  });
  const out = [];
  for (let i = 0; i < Math.max(...parts.map((p) => p.d.length)); i++) {
    for (const p of parts) {
      if (i < p.d.length) {
        out.push(p.d[i]);
      }
    }
  }
  for (let i = 0; i < parts[0].e.length; i++) {
    for (const p of parts) {
      out.push(p.e[i]);
    }
  }
  return out;
}
var MASKS = [
  (x, y) => (x + y) % 2 === 0,
  (x, y) => y % 2 === 0,
  (x, y) => x % 3 === 0,
  (x, y) => (x + y) % 3 === 0,
  (x, y) => ((y / 2 | 0) + (x / 3 | 0)) % 2 === 0,
  (x, y) => x * y % 2 + x * y % 3 === 0,
  (x, y) => (x * y % 2 + x * y % 3) % 2 === 0,
  (x, y) => ((x + y) % 2 + x * y % 3) % 2 === 0
];
var Matrix = class {
  constructor(version) {
    this.version = version;
    this.size = 17 + 4 * version;
    this.m = Array.from({ length: this.size }, () => new Array(this.size).fill(false));
    this.fn = Array.from({ length: this.size }, () => new Array(this.size).fill(false));
  }
  set(x, y, dark, isFn = true) {
    this.m[y][x] = dark;
    if (isFn) {
      this.fn[y][x] = true;
    }
  }
  drawFunctionPatterns() {
    const n = this.size;
    for (let i = 0; i < n; i++) {
      this.set(6, i, i % 2 === 0);
      this.set(i, 6, i % 2 === 0);
    }
    for (const [cx, cy] of [[3, 3], [n - 4, 3], [3, n - 4]]) {
      for (let dy = -4; dy <= 4; dy++) {
        for (let dx = -4; dx <= 4; dx++) {
          const x = cx + dx;
          const y = cy + dy;
          if (x >= 0 && x < n && y >= 0 && y < n) {
            const d = Math.max(Math.abs(dx), Math.abs(dy));
            this.set(x, y, d !== 2 && d !== 4);
          }
        }
      }
    }
    const pos = ALIGN2[this.version - 1];
    for (let a = 0; a < pos.length; a++) {
      for (let b = 0; b < pos.length; b++) {
        if (a === 0 && b === 0 || a === 0 && b === pos.length - 1 || a === pos.length - 1 && b === 0) {
          continue;
        }
        for (let dy = -2; dy <= 2; dy++) {
          for (let dx = -2; dx <= 2; dx++) {
            this.set(pos[a] + dx, pos[b] + dy, Math.max(Math.abs(dx), Math.abs(dy)) !== 1);
          }
        }
      }
    }
    this.drawFormat("M", 0);
    this.drawVersion();
  }
  drawFormat(ecc, mask) {
    const n = this.size;
    const data = ECC_FORMAT[ecc] << 3 | mask;
    let rem = data;
    for (let i = 0; i < 10; i++) {
      rem = rem << 1 ^ (rem >>> 9) * 1335;
    }
    const bits = (data << 10 | rem) ^ 21522;
    const bit = (i) => (bits >>> i & 1) !== 0;
    for (let i = 0; i <= 5; i++) {
      this.set(8, i, bit(i));
    }
    this.set(8, 7, bit(6));
    this.set(8, 8, bit(7));
    this.set(7, 8, bit(8));
    for (let i = 9; i < 15; i++) {
      this.set(14 - i, 8, bit(i));
    }
    for (let i = 0; i < 8; i++) {
      this.set(n - 1 - i, 8, bit(i));
    }
    for (let i = 8; i < 15; i++) {
      this.set(8, n - 15 + i, bit(i));
    }
    this.set(8, n - 8, true);
  }
  drawVersion() {
    if (this.version < 7) {
      return;
    }
    let rem = this.version;
    for (let i = 0; i < 12; i++) {
      rem = rem << 1 ^ (rem >>> 11) * 7973;
    }
    const bits = this.version << 12 | rem;
    for (let i = 0; i < 18; i++) {
      const dark = (bits >>> i & 1) !== 0;
      const a = this.size - 11 + i % 3;
      const b = Math.floor(i / 3);
      this.set(a, b, dark);
      this.set(b, a, dark);
    }
  }
  drawCodewords(words) {
    const n = this.size;
    let i = 0;
    for (let right = n - 1; right >= 1; right -= 2) {
      if (right === 6) {
        right = 5;
      }
      for (let vert = 0; vert < n; vert++) {
        for (let j = 0; j < 2; j++) {
          const x = right - j;
          const upward = (right + 1 & 2) === 0;
          const y = upward ? n - 1 - vert : vert;
          if (!this.fn[y][x] && i < words.length * 8) {
            this.m[y][x] = (words[i >>> 3] >>> 7 - (i & 7) & 1) !== 0;
            i++;
          }
        }
      }
    }
  }
  applyMask(mask) {
    const f = MASKS[mask];
    for (let y = 0; y < this.size; y++) {
      for (let x = 0; x < this.size; x++) {
        if (!this.fn[y][x] && f(x, y)) {
          this.m[y][x] = !this.m[y][x];
        }
      }
    }
  }
  penalty() {
    const n = this.size;
    let result = 0;
    const runs = (line) => {
      let p = 0;
      let run = 1;
      for (let i = 1; i <= line.length; i++) {
        if (i < line.length && line[i] === line[i - 1]) {
          run++;
        } else {
          if (run >= 5) {
            p += 3 + (run - 5);
          }
          run = 1;
        }
      }
      return p;
    };
    const finder = (line) => {
      const pat = [true, false, true, true, true, false, true];
      let p = 0;
      for (let i = 0; i + 7 <= line.length; i++) {
        if (pat.every((v, k2) => line[i + k2] === v)) {
          const before = i >= 4 && [1, 2, 3, 4].every((k2) => !line[i - k2]);
          const after = i + 11 <= line.length && [7, 8, 9, 10].every((k2) => !line[i + k2]);
          if (before || after) {
            p += 40;
          }
        }
      }
      return p;
    };
    for (let y = 0; y < n; y++) {
      result += runs(this.m[y]) + finder(this.m[y]);
    }
    for (let x = 0; x < n; x++) {
      const col = this.m.map((r) => r[x]);
      result += runs(col) + finder(col);
    }
    for (let y = 0; y < n - 1; y++) {
      for (let x = 0; x < n - 1; x++) {
        const c = this.m[y][x];
        if (c === this.m[y][x + 1] && c === this.m[y + 1][x] && c === this.m[y + 1][x + 1]) {
          result += 3;
        }
      }
    }
    const dark = this.m.reduce((s, r) => s + r.filter(Boolean).length, 0);
    const k = Math.ceil(Math.abs(dark * 20 - n * n * 10) / (n * n)) - 1;
    return result + Math.max(0, k) * 10;
  }
};
function qr(text, { ecc = "M", mask = null, minVersion = 1 } = {}) {
  if (!(ecc in ECC_INDEX)) {
    throw new Error(`QR: невідомий рівень «${ecc}».`);
  }
  const bytes = utf8(String(text));
  let version = minVersion;
  for (; version <= QR_MAX_VERSION; version++) {
    if (4 + (version <= 9 ? 8 : 16) + bytes.length * 8 <= dataCodewords(version, ecc) * 8) {
      break;
    }
  }
  if (version > QR_MAX_VERSION) {
    throw new Error("QR: текст задовгий (до 400 байт).");
  }
  const mx = new Matrix(version);
  mx.drawFunctionPatterns();
  mx.drawCodewords(buildCodewords(bytes, version, ecc));
  let best = mask;
  if (best == null) {
    let min = Infinity;
    for (let m = 0; m < 8; m++) {
      mx.applyMask(m);
      mx.drawFormat(ecc, m);
      const p = mx.penalty();
      if (p < min) {
        min = p;
        best = m;
      }
      mx.applyMask(m);
    }
  }
  mx.applyMask(best);
  mx.drawFormat(ecc, best);
  const rows = mx.m.map((r) => r.map((d) => d ? "1" : "0").join(""));
  return { version, size: mx.size, ecc, mask: best, rows, get: (x, y) => rows[y][x] === "1" };
}

// core/constructor/labels.js
var LABELS_MAX = 5e3;
var LAYOUTS = {
  "70x36": { name: "70×36 мм (3×8)", w: 70, h: 36, page: { w: 210, h: 297 } },
  "105x48": { name: "105×48 мм (2×6)", w: 105, h: 48, page: { w: 210, h: 297 } },
  "100x150": { name: "100×150 мм (рулон, 1 на аркуш)", w: 100, h: 150, page: { w: 100, h: 150 } },
  custom: { name: "Свій розмір", w: 70, h: 36, page: { w: 210, h: 297 } }
};
var SCOPES = { selected: "Виділене (все всередині)", zone: "Зона", row: "Ряд", tier: "Ярус знизу", all: "Усі місця" };
var defaultSpec = () => ({
  scope: "selected",
  zoneId: "",
  rowId: "",
  tier: 1,
  onlyNew: false,
  onlyApplied: false,
  kind: "code128",
  show: { zone: false, row: false, bay: false, level: false, type: false },
  arrows: "none",
  scanLevel: 2,
  layout: "70x36",
  custom: { w: 70, h: 36 },
  pageSize: "A4",
  margin: null,
  // {l, t, r, b} мм; null — по центру
  gap: { x: 0, y: 0 },
  skip: 0,
  font: "cyr",
  dpi: 203
});
var slotsInside = (zone2) => {
  const poly = sGeom(zone2).poly;
  return S.slots.filter((s) => s.id !== zone2.id && s.template !== "zone" && s.layer_id === zone2.layer_id && polygonContains(poly, [s.x, s.y]));
};
var isApplied = (s) => s.rid != null || !!E.adapter?.baseMap?.has?.("s:" + s.id);
var isNewOrRenumbered = (s) => {
  const st = E.objStatus ? E.objStatus("slot", s) : "new";
  return st === "new" || st === "unsaved";
};
function scopeSlots(spec) {
  const sel = selRefs().filter((r) => r.kind === "slot").map((r) => S.sIdx.get(r.id)).filter(Boolean);
  const expand = (list) => list.flatMap((s) => s.template === "zone" ? slotsInside(s) : [s]);
  switch (spec.scope) {
    case "zone": {
      const z = S.sIdx.get(spec.zoneId) || sel.find((s) => s.template === "zone");
      return z ? slotsInside(z) : [];
    }
    case "row": {
      const s = S.sIdx.get(spec.rowId) || sel.find((x) => x.template !== "zone");
      return s ? [s] : [];
    }
    case "tier":
      return sel.length ? expand(sel) : S.slots.filter((s) => s.template !== "zone");
    case "all":
      return S.slots.filter((s) => s.template !== "zone");
    default:
      return expand(sel);
  }
}
function collectCells(spec) {
  let slots = scopeSlots(spec);
  if (spec.onlyNew) {
    slots = slots.filter(isNewOrRenumbered);
  }
  if (spec.onlyApplied) {
    slots = slots.filter(isApplied);
  }
  const seen = /* @__PURE__ */ new Set();
  const out = [];
  for (const s of slots) {
    for (const c of cellsOf(s)) {
      if (c.disabled || seen.has(c.code)) {
        continue;
      }
      if (spec.scope === "tier" && c.level !== Number(spec.tier)) {
        continue;
      }
      seen.add(c.code);
      out.push({ code: c.code, slot: s, cell: c });
    }
  }
  return out;
}
var TR = { а: "a", б: "b", в: "v", г: "h", ґ: "g", д: "d", е: "e", є: "ie", ж: "zh", з: "z", и: "y", і: "i", ї: "i", й: "i", к: "k", л: "l", м: "m", н: "n", о: "o", п: "p", р: "r", с: "s", т: "t", у: "u", ф: "f", х: "kh", ц: "ts", ч: "ch", ш: "sh", щ: "shch", ь: "", ю: "iu", я: "ia", ы: "y", э: "e", ё: "io", ъ: "" };
var translit = (t) => String(t).split("").map((ch) => {
  const lo = ch.toLowerCase();
  if (!(lo in TR)) {
    return ch;
  }
  const r = TR[lo];
  return ch === lo ? r : r.charAt(0).toUpperCase() + r.slice(1);
}).join("");
function buildItems(cells, spec) {
  const fix2 = spec.font === "latin" ? translit : (x) => x;
  return cells.map(({ code, slot, cell }) => {
    const ctx2 = contextOf(slot) || {};
    const lines = [];
    const parts = [];
    if (spec.show.zone && ctx2.zone != null) {
      parts.push(`Зона ${ctx2.zone}`);
    }
    if (spec.show.row) {
      const r = rowNumberOf(slot);
      parts.push(`Ряд ${r ?? slot.code_prefix}`);
    }
    if (spec.show.bay && cell.index != null && slot.template !== "floor_spot") {
      parts.push(`Секція ${cell.index}`);
    }
    if (spec.show.level && cell.level != null && slot.template !== "floor_spot") {
      parts.push(`Ярус ${cell.level}`);
    }
    if (parts.length) {
      lines.push(fix2(parts.join(" · ")));
    }
    if (spec.show.type) {
      const t = typeOf(slot.type_id, libraryState());
      lines.push(fix2(t ? t.name : slot.template));
    }
    let arrow = null;
    if (spec.arrows !== "none" && cell.level != null) {
      if (cell.level > Number(spec.scanLevel)) {
        arrow = "up";
      } else if (spec.arrows === "updown" && cell.level < Number(spec.scanLevel)) {
        arrow = "down";
      }
    }
    return { code, lines, arrow };
  });
}
function pageGeometry(spec) {
  const L2 = LAYOUTS[spec.layout] || LAYOUTS.custom;
  const lab = spec.layout === "custom" ? { w: Number(spec.custom.w) || 70, h: Number(spec.custom.h) || 36 } : { w: L2.w, h: L2.h };
  const page = spec.layout === "100x150" ? { w: 100, h: 150 } : { w: 210, h: 297 };
  const gx = Number(spec.gap.x) || 0;
  const gy = Number(spec.gap.y) || 0;
  const m = spec.margin;
  const avW = page.w - (m ? m.l + m.r : 0);
  const avH = page.h - (m ? m.t + m.b : 0);
  const cols = Math.max(1, Math.floor((avW + gx + 1e-6) / (lab.w + gx)));
  const rows = Math.max(1, Math.floor((avH + gy + 1e-6) / (lab.h + gy)));
  const usedW = cols * lab.w + (cols - 1) * gx;
  const usedH = rows * lab.h + (rows - 1) * gy;
  return { page, label: lab, cols, rows, perPage: cols * rows, x0: m ? m.l : (page.w - usedW) / 2, y0: m ? m.t : (page.h - usedH) / 2, gx, gy };
}
function paginate(items, spec) {
  const g3 = pageGeometry(spec);
  const skip = Math.max(0, Math.floor(Number(spec.skip) || 0)) % g3.perPage;
  const pages = [];
  let slot = skip;
  for (const item of items) {
    const pi = Math.floor(slot / g3.perPage);
    const k = slot % g3.perPage;
    (pages[pi] = pages[pi] || []).push({ item, x: g3.x0 + k % g3.cols * (g3.label.w + g3.gx), y: g3.y0 + Math.floor(k / g3.cols) * (g3.label.h + g3.gy) });
    slot++;
  }
  return pages.map((p) => p || []);
}
var esc = (t) => String(t).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
var num3 = (v) => Number(v.toFixed(3));
function barsSvg(code, x, y, w, hh) {
  const c = code128(code);
  const mod = w / (c.width + 20);
  let d = "";
  let i = 0;
  while (i < c.width) {
    if (c.modules[i] === "1") {
      let j = i;
      while (j < c.width && c.modules[j] === "1") {
        j++;
      }
      d += `M${num3(x + (10 + i) * mod)} ${num3(y)}h${num3((j - i) * mod)}v${num3(hh)}h${num3(-(j - i) * mod)}z`;
      i = j;
    } else {
      i++;
    }
  }
  return `<path d="${d}" fill="#000"/>`;
}
function qrSvg(code, x, y, side2) {
  const q = qr(code, { ecc: "M" });
  const mod = side2 / (q.size + 8);
  let d = "";
  for (let r = 0; r < q.size; r++) {
    let c = 0;
    while (c < q.size) {
      if (q.rows[r][c] === "1") {
        let e = c;
        while (e < q.size && q.rows[r][e] === "1") {
          e++;
        }
        d += `M${num3(x + (4 + c) * mod)} ${num3(y + (4 + r) * mod)}h${num3((e - c) * mod)}v${num3(mod)}h${num3(-(e - c) * mod)}z`;
        c = e;
      } else {
        c++;
      }
    }
  }
  return `<path d="${d}" fill="#000"/>`;
}
var arrowSvg = (dir, x, y, s) => `<path d="${dir === "up" ? `M${num3(x + s / 2)} ${num3(y)}L${num3(x + s)} ${num3(y + s * 0.6)}H${num3(x + s * 0.7)}V${num3(y + s)}H${num3(x + s * 0.3)}V${num3(y + s * 0.6)}H${num3(x)}z` : `M${num3(x + s / 2)} ${num3(y + s)}L${num3(x)} ${num3(y + s * 0.4)}H${num3(x + s * 0.3)}V${num3(y)}H${num3(x + s * 0.7)}V${num3(y + s * 0.4)}H${num3(x + s)}z`}" fill="#000"/>`;
var kindFor = (code, spec) => spec.kind === "qr" || !isPrintableAscii(code) ? "qr" : "code128";
function labelSvg(item, spec, w, hh) {
  const m = Math.min(2.2, w * 0.04, hh * 0.06);
  const kind = kindFor(item.code, spec);
  const lineH = Math.min(3.6, hh * 0.1);
  let out = "";
  const extra = item.lines.length;
  if (kind === "qr") {
    const side2 = Math.min(hh - 2 * m, w * 0.46);
    out += qrSvg(item.code, m, (hh - side2) / 2, side2);
    const tx = m + side2 + m * 0.8;
    const tw = w - tx - m;
    const fs = Math.min(hh * 0.24, tw / (item.code.length * 0.56));
    out += `<text x="${num3(tx)}" y="${num3(hh / 2 - (extra ? lineH * 0.2 : 0) + fs * 0.35)}" font-family="DejaVu Sans, Arial, sans-serif" font-weight="700" font-size="${num3(fs)}" textLength="${num3(Math.min(tw, item.code.length * fs * 0.62))}" lengthAdjust="spacingAndGlyphs">${esc(item.code)}</text>`;
    item.lines.forEach((t, i) => {
      out += `<text x="${num3(tx)}" y="${num3(hh / 2 + fs * 0.35 + lineH * (i + 1) * 0.95)}" font-family="DejaVu Sans, Arial, sans-serif" font-size="${num3(lineH * 0.8)}">${esc(t)}</text>`;
    });
  } else {
    const top = m + extra * lineH;
    item.lines.forEach((t, i) => {
      out += `<text x="${num3(m)}" y="${num3(m + lineH * (i + 0.8))}" font-family="DejaVu Sans, Arial, sans-serif" font-size="${num3(lineH * 0.8)}">${esc(t)}</text>`;
    });
    const fs = Math.min(hh * 0.26, (w - 2 * m) / (item.code.length * 0.6));
    const bh = Math.max(4, hh - top - fs * 1.25 - m);
    out += barsSvg(item.code, m, top, w - 2 * m, bh);
    out += `<text x="${num3(w / 2)}" y="${num3(top + bh + fs * 0.95)}" text-anchor="middle" font-family="DejaVu Sans, Arial, sans-serif" font-weight="700" font-size="${num3(fs)}" textLength="${num3(Math.min(item.code.length * fs * 0.62, w - 2 * m))}" lengthAdjust="spacingAndGlyphs">${esc(item.code)}</text>`;
  }
  if (item.arrow) {
    const s = Math.min(hh * 0.28, w * 0.14);
    out += arrowSvg(item.arrow, w - s - m, m, s);
  }
  return out;
}
function sheetSvg(pages, spec, index = 0, { frame = true } = {}) {
  const g3 = pageGeometry(spec);
  const inner = (pages[index] || []).map(({ item, x, y }) => `<g transform="translate(${num3(x)} ${num3(y)})">${frame ? `<rect width="${g3.label.w}" height="${g3.label.h}" fill="none" stroke="#c6c6c6" stroke-width="0.2"/>` : ""}${labelSvg(item, spec, g3.label.w, g3.label.h)}</g>`).join("");
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${g3.page.w} ${g3.page.h}" width="${g3.page.w}mm" height="${g3.page.h}mm"><rect width="${g3.page.w}" height="${g3.page.h}" fill="#fff"/>${inner}</svg>`;
}
async function sheetPng(svg, spec, dpi = 200) {
  const g3 = pageGeometry(spec);
  const w = Math.round(g3.page.w / 25.4 * dpi);
  const hh = Math.round(g3.page.h / 25.4 * dpi);
  const img = new Image();
  img.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(svg.replace(/width="[\d.]+mm" height="[\d.]+mm"/, `width="${w}" height="${hh}"`));
  await new Promise((res, rej) => {
    img.onload = res;
    img.onerror = () => rej(new Error("Не вдалося намалювати етикетки."));
  });
  const cv = document.createElement("canvas");
  cv.width = w;
  cv.height = hh;
  const ctx2 = cv.getContext("2d");
  ctx2.fillStyle = "#fff";
  ctx2.fillRect(0, 0, w, hh);
  ctx2.drawImage(img, 0, 0, w, hh);
  return await new Promise((res) => cv.toBlob(res, "image/png"));
}
var dots = (mm, dpi) => Math.round(mm * dpi / 25.4);
function toZpl(items, spec) {
  const dpi = Number(spec.dpi) === 300 ? 300 : 203;
  const g3 = pageGeometry(spec);
  const W = dots(g3.label.w, dpi);
  const H = dots(g3.label.h, dpi);
  const m = dots(Math.min(2.2, g3.label.w * 0.04), dpi);
  const warnings = /* @__PURE__ */ new Set();
  const out = [];
  for (const item of items) {
    const kind = kindFor(item.code, spec);
    if (kind === "qr" && spec.kind !== "qr") {
      warnings.add(`Код «${item.code}» містить не-ASCII: Code128 не підходить, використано QR.`);
    }
    const lineDots = dots(3.2, dpi);
    let z = `^XA^CI28^PW${W}^LL${H}^LH0,0
`;
    const textFs = Math.min(Math.round(H * 0.22), Math.round((W - 2 * m) / (item.code.length * 0.62)));
    if (kind === "qr") {
      const q = qr(item.code, { ecc: "M" });
      const side2 = Math.min(H - 2 * m, Math.round(W * 0.46));
      const mag = Math.max(1, Math.min(10, Math.floor(side2 / (q.size + 8))));
      if (mag < 2) {
        warnings.add(`Дрібний QR: модуль ${mag} точк. при ${dpi} dpi (треба ≥ 2) — збільшіть етикетку.`);
      }
      const qx = m;
      z += `^FO${qx},${m}^BQN,2,${mag}^FDMA,${item.code}^FS
`;
      const tx = m + (q.size + 8) * mag;
      z += `^FO${tx},${Math.round(H / 2 - textFs / 2)}^A0N,${textFs},${textFs}^FD${item.code}^FS
`;
      item.lines.forEach((t, i) => {
        z += `^FO${tx},${Math.round(H / 2 + textFs / 2 + lineDots * i)}^A0N,${lineDots},${lineDots}^FD${t}^FS
`;
      });
    } else {
      const c = code128(item.code);
      const modW = Math.max(1, Math.floor((W - 2 * m) / (c.width + 20)));
      if (modW < 2) {
        warnings.add(`Дрібний штрихкод «${item.code}»: модуль ${modW} точк. при ${dpi} dpi (треба ≥ 2) — збільште етикетку чи оберіть QR.`);
      }
      const top = m + item.lines.length * lineDots;
      item.lines.forEach((t, i) => {
        z += `^FO${m},${m + lineDots * i}^A0N,${lineDots},${lineDots}^FD${t}^FS
`;
      });
      const bh = Math.max(20, H - top - textFs - 2 * m);
      z += `^BY${modW},3,${bh}^FO${Math.round((W - c.width * modW) / 2)},${top}^BCN,${bh},N,N,N,A^FD${item.code}^FS
`;
      z += `^FO${m},${top + bh + Math.round(m / 2)}^A0N,${textFs},${textFs}^FB${W - 2 * m},1,0,C^FD${item.code}^FS
`;
    }
    if (item.arrow) {
      const s = Math.round(H * 0.26);
      const ax = W - m - s;
      z += `^FO${ax + Math.round(s * 0.35)},${m + Math.round(s * 0.4)}^GB${Math.round(s * 0.3)},${Math.round(s * 0.6)},${Math.round(s * 0.3)}^FS
`;
      z += `^FO${ax},${m}^GD${s},${Math.round(s * 0.5)},3,B,${item.arrow === "up" ? "R" : "L"}^FS
`;
    }
    out.push(z + "^PQ1^XZ");
  }
  return { zpl: out.join("\n"), warnings: [...warnings] };
}
function pdfPayload(items, spec, format = "pdf") {
  const g3 = pageGeometry(spec);
  return {
    format,
    font: spec.font,
    kind: spec.kind,
    page: g3.page,
    grid: { cols: g3.cols, rows: g3.rows, x0: g3.x0, y0: g3.y0, w: g3.label.w, h: g3.label.h, gx: g3.gx, gy: g3.gy },
    skip: Math.max(0, Math.floor(Number(spec.skip) || 0)),
    labels: items.map((i) => ({ code: i.code, lines: i.lines, arrow: i.arrow }))
  };
}
function download2(name, mime, data, isB64 = false) {
  const bin = isB64 ? Uint8Array.from(atob(data), (c) => c.charCodeAt(0)) : data;
  const url = URL.createObjectURL(bin instanceof Blob ? bin : new Blob([bin], { type: mime }));
  const a = h("a", { href: url, download: name });
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1500);
}
async function openLabels(adapter, args = {}) {
  const spec = { ...defaultSpec(), ...args.spec || {} };
  const zones = S.slots.filter((s) => s.template === "zone");
  const racks = S.slots.filter((s) => s.template !== "zone");
  if (!args.spec) {
    const sel = selRefs().filter((r) => r.kind === "slot");
    spec.scope = sel.length ? "selected" : "all";
  }
  const body = h("div", { class: "fcol", id: "labelsBody" });
  const prev = h("div", { id: "labelsPreview", style: { background: "var(--surface2)", border: "1px solid var(--line)", padding: "6px", overflow: "auto", maxHeight: "50vh", textAlign: "center" } });
  const info = h("div", { class: "small", id: "labelsInfo" });
  const warn = h("div", { class: "note warn", id: "labelsWarn", hidden: true });
  let model = { items: [], pages: [], cells: [] };
  const recompute = () => {
    model.cells = collectCells(spec);
    model.items = buildItems(model.cells, spec);
    model.pages = paginate(model.items, spec);
    const over = model.items.length > LABELS_MAX;
    info.textContent = `Етикеток: ${model.items.length}${over ? ` (ліміт ${LABELS_MAX})` : ""} · аркушів: ${model.pages.length}`;
    prev.innerHTML = model.items.length ? sheetSvg(model.pages, spec, 0).replace(/width="[\d.]+mm" height="[\d.]+mm"/, 'width="100%" style="max-width:360px;height:auto"') : "";
    if (!model.items.length) {
      prev.textContent = "Немає комірок за цим вибором.";
    }
    const z = model.items.length ? toZpl(model.items.slice(0, 50), spec).warnings : [];
    warn.hidden = !z.length;
    warn.textContent = z.join(" ");
    for (const id of ["btnLabelsPdf", "btnLabelsPng", "btnLabelsZpl"]) {
      const b = document.getElementById(id);
      if (b) {
        b.disabled = !model.items.length || over || id === "btnLabelsPdf" && !can("render");
      }
    }
  };
  const set = (path, v) => {
    const ks = path.split(".");
    let o = spec;
    while (ks.length > 1) {
      o = o[ks.shift()];
    }
    o[ks[0]] = v;
    recompute();
  };
  const check = (label, path, get) => {
    const cb = h("input", { type: "checkbox", checked: !!get(), "data-s3": path });
    cb.addEventListener("change", () => set(path, cb.checked));
    return h("label", { class: "frow", style: { gap: "4px" } }, cb, label);
  };
  const numF = (label, path, get, min, max, step = 1) => {
    const el = h("input", { type: "number", value: get(), min, max, step, "aria-label": label, "data-s3": path });
    el.addEventListener("input", () => {
      const v = parseFloat(el.value);
      if (isFinite(v)) {
        set(path, v);
      }
    });
    return fld(label, el);
  };
  const mg = () => spec.margin || { l: 0, t: 0, r: 0, b: 0 };
  const draw = () => {
    const custom = spec.layout === "custom";
    body.replaceChildren(
      ...K([
        h(
          "div",
          { class: "grid2" },
          fld("Що друкувати", selectEl(Object.entries(SCOPES), spec.scope, (v) => {
            spec.scope = v;
            recompute();
            draw();
          }, false, "Що друкувати")),
          spec.scope === "zone" ? fld("Зона", selectEl([["", "—"], ...zones.map((z) => [z.id, z.params.title || z.code_prefix])], spec.zoneId, (v) => set("zoneId", v), false, "Зона")) : spec.scope === "row" ? fld("Ряд", selectEl([["", "—"], ...racks.map((z) => [z.id, z.code_prefix])], spec.rowId, (v) => set("rowId", v), false, "Ряд")) : spec.scope === "tier" ? numF("Ярус знизу", "tier", () => spec.tier, 1, 12) : h("div")
        ),
        h("div", { class: "frow wrap" }, check("Лише нові та перенумеровані", "onlyNew", () => spec.onlyNew), check("Лише застосовані в Odoo", "onlyApplied", () => spec.onlyApplied)),
        h(
          "div",
          { class: "grid2" },
          fld("Штрихкод", selectEl([["code128", "Code128"], ["qr", "QR"]], spec.kind, (v) => set("kind", v), false, "Штрихкод")),
          fld("Шрифт", selectEl([["cyr", "З кирилицею"], ["latin", "Лише латиниця"]], spec.font, (v) => set("font", v), false, "Шрифт"))
        ),
        h("div", { class: "frow wrap" }, check("Зона", "show.zone", () => spec.show.zone), check("Ряд", "show.row", () => spec.show.row), check("Секція", "show.bay", () => spec.show.bay), check("Ярус", "show.level", () => spec.show.level), check("Тип", "show.type", () => spec.show.type)),
        h(
          "div",
          { class: "grid2" },
          fld("Стрілка ярусів", selectEl([["none", "Немає"], ["up", "Вгору (вище точки)"], ["updown", "Вгору й вниз"]], spec.arrows, (v) => set("arrows", v), false, "Стрілка")),
          numF("Точка сканування: ярус", "scanLevel", () => spec.scanLevel, 1, 12)
        ),
        h("div", { class: "grid2" }, fld("Розкладка", selectEl(Object.entries(LAYOUTS).map(([k, v]) => [k, v.name]), spec.layout, (v) => {
          spec.layout = v;
          recompute();
          draw();
        }, false, "Розкладка")), numF("Пропустити перші", "skip", () => spec.skip, 0, 500)),
        custom ? h("div", { class: "grid2" }, numF("Ширина, мм", "custom.w", () => spec.custom.w, 10, 300), numF("Висота, мм", "custom.h", () => spec.custom.h, 10, 300)) : null,
        h(
          "div",
          { class: "grid3" },
          numF("Проміжок X, мм", "gap.x", () => spec.gap.x, 0, 30, 0.5),
          numF("Проміжок Y, мм", "gap.y", () => spec.gap.y, 0, 30, 0.5),
          fld("Поля", selectEl([["auto", "По центру"], ["zero", "0 мм"], ["5", "5 мм"], ["10", "10 мм"]], spec.margin ? mg().l === 0 ? "zero" : String(mg().l) : "auto", (v) => {
            spec.margin = v === "auto" ? null : { l: v === "zero" ? 0 : +v, t: v === "zero" ? 0 : +v, r: v === "zero" ? 0 : +v, b: v === "zero" ? 0 : +v };
            recompute();
          }, false, "Поля"))
        ),
        fld("ZPL: роздільна здатність", selectEl([["203", "203 dpi"], ["300", "300 dpi"]], String(spec.dpi), (v) => set("dpi", +v), false, "dpi")),
        info,
        warn,
        prev
      ])
    );
    recompute();
  };
  openDialog({
    title: "Етикетки",
    cls: "wide",
    body,
    actions: [
      { label: "Закрити", value: "close" },
      {
        label: "ZPL",
        id: "btnLabelsZpl",
        onClick: () => {
          const { zpl, warnings } = toZpl(model.items, spec);
          download2(`labels_${spec.dpi}dpi.zpl`, "text/plain", zpl);
          toast(warnings.length ? `ZPL збережено. Попередження: ${warnings[0]}` : "ZPL збережено.", warnings.length ? "warn" : void 0);
          return false;
        }
      },
      {
        label: "PNG",
        id: "btnLabelsPng",
        onClick: async () => {
          const blob = await sheetPng(sheetSvg(model.pages, spec, 0, { frame: false }), spec);
          download2("labels.png", "image/png", blob);
          toast("PNG (аркуш 1) збережено.");
          return false;
        }
      },
      {
        label: "PDF",
        cls: "primary",
        id: "btnLabelsPdf",
        onClick: async () => {
          try {
            const res = await adapter.render("labels_pdf", pdfPayload(model.items, spec));
            download2(res.filename || "labels.pdf", res.mimetype || "application/pdf", res.content, true);
            toast("PDF сформовано на сервері.");
          } catch (e) {
            toast(e.message || "Не вдалося сформувати PDF.", "err");
          }
          return false;
        }
      }
    ]
  });
  draw();
  const pdf = document.getElementById("btnLabelsPdf");
  if (pdf && !can("render")) {
    pdf.title = "PDF формує сервер Odoo («на сервері»); у цьому режимі доступні ZPL і PNG.";
  }
}
registries.dialogs.add("labels", (a, { adapter }) => openLabels(adapter, a), { force: true });
registries.menu.add("labels", { area: "more", label: "Етикетки…", icon: "tag", sequence: 32, run: () => E.runDialog("labels") }, { sequence: 32, force: true });
function renderLabelsBlock(root, { rec }) {
  if (!rec || !S.sel || S.sel.kind !== "slot" || rec.template !== "zone" && !cellsOf(rec).length) {
    return;
  }
  root.append(
    h("div", { class: "sec", id: "labelsBlock" }, h("h3", null, "Етикетки"), h("button", { class: "fbtn sm", type: "button", id: "btnLabels", onclick: () => E.runDialog("labels", rec.template === "zone" ? { spec: { scope: "zone", zoneId: rec.id } } : { spec: { scope: "row", rowId: rec.id } }) }, "Друк етикеток…"))
  );
}
registries.panels.add("right:labels", { area: "right", render: renderLabelsBlock }, { sequence: 70, force: true });
Object.assign(E, { openLabels: (a) => E.runDialog("labels", a) });

// core/constructor/stock_state.js
var revN = 0;
function applyStock(res, { merge = false } = {}) {
  const prev = merge && S.stock ? S.stock.byCode : /* @__PURE__ */ new Map();
  const byCode = new Map(prev);
  for (const [code, v] of Object.entries(res.codes || {})) {
    byCode.set(code, { ...byCode.get(code) || {}, ...v });
  }
  S.stock = { at: res.at || (/* @__PURE__ */ new Date()).toISOString(), demo: !!res.demo, days: res.days || 90, rev: ++revN, byCode, abc: abcClasses(byCode), truncated: !!res.truncated };
  return S.stock;
}
function abcClasses(byCode) {
  const rows = [...byCode].map(([code, v]) => [code, Number(v.moves) || 0]).sort((a, b) => b[1] - a[1] || (a[0] < b[0] ? -1 : 1));
  const total = rows.reduce((s, r) => s + r[1], 0);
  const out = /* @__PURE__ */ new Map();
  let cum = 0;
  for (const [code, m] of rows) {
    if (!m) {
      out.set(code, "0");
      continue;
    }
    out.set(code, cum < total * 0.8 - 1e-9 ? "A" : cum < total * 0.95 - 1e-9 ? "B" : "C");
    cum += m;
  }
  return out;
}
async function loadStock({ force = false, codes = null, quiet = false } = {}) {
  if (!can("stock") || !E.adapter?.stock) {
    return null;
  }
  if (S.stock && !force && !codes) {
    return S.stock;
  }
  try {
    let res = await E.adapter.stock({ codes, days: S.stock?.days || null });
    const all = { ...res, codes: { ...res.codes } };
    for (let i = 0; i < 50 && !codes && res.truncated && res.next; i++) {
      res = await E.adapter.stock({ codes, days: all.days, offset: res.next });
      Object.assign(all.codes, res.codes);
      all.truncated = res.truncated;
    }
    const st = applyStock(all, { merge: !!codes });
    E.recolorCells?.();
    E.renderHeat?.();
    return st;
  } catch (e) {
    if (!quiet) {
      toast(e.message || "Не вдалося прочитати залишки.", "err");
    }
    return null;
  }
}
async function loadDetail(code) {
  const cur = S.stock?.byCode.get(code);
  if (cur && cur.detail) {
    return cur.detail;
  }
  if (!can("stock") || !E.adapter?.stock) {
    return null;
  }
  try {
    const res = await E.adapter.stock({ codes: [code], detail: true });
    const v = (res.codes || {})[code];
    if (!v) {
      return null;
    }
    if (!S.stock) {
      applyStock({ ...res, codes: {} });
    }
    const entry = S.stock.byCode.get(code) || {};
    S.stock.byCode.set(code, { ...entry, ...v });
    return v.detail || null;
  } catch {
    return null;
  }
}
async function findStock(q, mode = "any") {
  if (!can("stock") || !E.adapter?.find) {
    return null;
  }
  const res = await E.adapter.find({ q, mode });
  return { hits: res.hits || [], demo: !!res.demo };
}
var stockOf = (code) => S.stock ? S.stock.byCode.get(code) : void 0;
var fmtAt = (at) => {
  try {
    const d = new Date(String(at).includes("T") ? at : String(at).replace(" ", "T") + "Z");
    return d.toLocaleTimeString("uk-UA", { hour: "2-digit", minute: "2-digit" });
  } catch {
    return String(at);
  }
};
Object.assign(E, { loadStock, loadDetail, findStock, stockOf });

// core/constructor/heat.js
var GRAY = "#a9adb3";
var FILL = [
  ["empty", "Порожньо", "#d9e3e8"],
  ["q1", "до 25 %", "#b5dcc3"],
  ["q2", "25–50 %", "#7cc49a"],
  ["q3", "50–75 %", "#3e9e6a"],
  ["q4", "понад 75 %", "#1e6b47"],
  ["nocap", "без ємності", GRAY]
];
var BELOW = [
  ["none", "Запасу немає", "#c32d2d"],
  ["below", "Нижче мінімуму", "#e08a00"],
  ["ok", "Не нижче мінімуму", "#2c9a5b"],
  ["norule", "Без правила", GRAY]
];
var EMPTY2 = [
  ["empty", "Порожнє (можна класти)", "#2c9a5b"],
  ["busy", "Зайняте", "#c9ccd1"]
];
var ABC = [
  ["A", "A — 80 % руху", "#c32d2d"],
  ["B", "B — наступні 15 %", "#e0a030"],
  ["C", "C — останні 5 %", "#4f8fcf"],
  ["0", "Без руху", GRAY]
];
var AGE = [
  ["a30", "до 30 днів", "#2c9a5b"],
  ["a90", "31–90 днів", "#8ac24a"],
  ["a180", "91–180 днів", "#e0c030"],
  ["a365", "181–365 днів", "#e08a00"],
  ["a999", "понад 365 днів", "#c32d2d"],
  ["none", "Порожньо", "#d9e3e8"]
];
var CLASSIFY = {
  fill(e) {
    if (e.fill == null) {
      return "nocap";
    }
    return e.fill <= 0 ? "empty" : e.fill <= 0.25 ? "q1" : e.fill <= 0.5 ? "q2" : e.fill <= 0.75 ? "q3" : "q4";
  },
  below_min(e) {
    if (e.min == null) {
      return "norule";
    }
    return !e.qty ? "none" : e.qty < e.min ? "below" : "ok";
  },
  empty: (e) => e.qty ? "busy" : "empty",
  abc: (e, code) => S.stock.abc.get(code) || "0",
  age(e) {
    if (!e.qty) {
      return "none";
    }
    const d = e.age_days ?? 0;
    return d <= 30 ? "a30" : d <= 90 ? "a90" : d <= 180 ? "a180" : d <= 365 ? "a365" : "a999";
  }
};
var DEFS = { fill: FILL, below_min: BELOW, empty: EMPTY2, abc: ABC, age: AGE };
var METRIC_LABELS = { fill: "Заповненість", below_min: "Нижче мінімуму", empty: "Порожні місця", abc: "Оборотність ABC", age: "Вік запасу" };
var colorOf = (key, cls) => (DEFS[key].find((c) => c[0] === cls) || [])[2] || null;
for (const key of Object.keys(DEFS)) {
  registries.metrics.add(
    key,
    {
      label: METRIC_LABELS[key],
      color(cell) {
        const e = stockOf(cell.code);
        if (!e) {
          return null;
        }
        return colorOf(key, CLASSIFY[key](e, cell.code));
      }
    },
    { sequence: 10 + Object.keys(DEFS).indexOf(key), force: true }
  );
}
function legendOf(key) {
  const counts = new Map(DEFS[key].map((c) => [c[0], 0]));
  let fresh = 0;
  for (const s of S.slots) {
    for (const c of cellsOf(s)) {
      if (c.disabled) {
        continue;
      }
      const e = stockOf(c.code);
      if (!e) {
        fresh++;
        continue;
      }
      const k = CLASSIFY[key](e, c.code);
      counts.set(k, (counts.get(k) || 0) + 1);
    }
  }
  const rows = DEFS[key].map(([k, label, color]) => ({ key: k, label, color, count: counts.get(k) || 0 }));
  if (fresh) {
    rows.push({ key: "new", label: "Нові / без даних", color: "var(--ink3)", count: fresh });
  }
  return rows;
}
var LS_KEY = "f3d_constructor_metric";
var lsGet2 = () => {
  try {
    return window.localStorage.getItem(LS_KEY);
  } catch {
    return null;
  }
};
var lsSet2 = (v) => {
  try {
    window.localStorage.setItem(LS_KEY, v || "");
  } catch {
  }
};
async function setMetric(key) {
  if (key && !registries.metrics.has(key)) {
    return;
  }
  S.ui.metric = key || "";
  lsSet2(S.ui.metric);
  if (key && !S.stock) {
    await loadStock({ quiet: false });
  }
  E.recolorCells?.();
  renderHeat();
}
async function restoreMetric() {
  const k = lsGet2();
  if (k && registries.metrics.has(k) && can("stock")) {
    S.ui.metric = k;
    await loadStock({ quiet: true });
    E.recolorCells?.();
    renderHeat();
  }
}
async function refreshStock() {
  const st = await loadStock({ force: true });
  if (st) {
    E.recolorCells?.();
    renderHeat();
  }
  return st;
}
function renderHeat() {
  const sel = $("#s3Metric");
  const box = $("#s3Heat");
  if (!sel || !box) {
    return;
  }
  const avail = can("stock");
  sel.replaceChildren(h("option", { value: "" }, "Показник: звичайний"), ...Object.entries(METRIC_LABELS).map(([k, t]) => h("option", { value: k, selected: S.ui.metric === k }, t)));
  const key = DEFS[S.ui.metric] ? S.ui.metric : "";
  sel.value = key;
  sel.disabled = !avail;
  sel.title = avail ? "Забарвлення комірок за залишками" : "Адаптер не віддає залишки";
  const rf = $("#s3Refresh");
  if (rf) {
    rf.disabled = !avail || !key;
  }
  if (!key || !S.stock) {
    box.hidden = true;
    box.replaceChildren();
    return;
  }
  box.hidden = false;
  box.replaceChildren(
    h("div", { class: "s3-heat-h" }, h("b", null, METRIC_LABELS[key]), S.stock.demo ? h("span", { class: "tag s3-demo", title: "У демо-знімку немає рухів і дат: значення синтетичні" }, "демо") : null, h("span", { class: "small muted" }, "станом на " + fmtAt(S.stock.at))),
    ...legendOf(key).map((r) => h("div", { class: "s3-heat-row", "data-class": r.key }, h("i", { class: "sq", style: { background: r.color } }), h("span", null, r.label), h("span", { class: "num" }, String(r.count))))
  );
}
registries.menu.add(
  "refreshStock",
  { area: "more", label: "Оновити дані", icon: "hist", capability: "stock", sequence: 33, run: () => refreshStock() },
  { sequence: 33, force: true }
);
Object.assign(E, { setMetric, restoreMetric, refreshStock, renderHeat, legendOf });

// core/constructor/search.js
var normCode = (s) => String(s ?? "").toUpperCase().replace(/[^0-9A-ZА-ЯІЇЄҐ]/g, "");
function findCodes(q, limit = 40) {
  const n = normCode(q);
  if (!n) {
    return { hits: [], total: 0 };
  }
  const hits = [];
  const push = (kind, code, rec, extra) => {
    const c = normCode(code);
    const at = c.indexOf(n);
    if (at >= 0) {
      hits.push({ kind, code, rec, rank: c === n ? 0 : at === 0 ? 1 : 2, ...extra });
    }
  };
  for (const s of S.slots) {
    if (s.template === "zone") {
      push("slot", s.params?.title || s.code_prefix, s, { slot: s, zoneName: true });
      continue;
    }
    for (const c of cellsOf(s)) {
      if (!c.disabled) {
        push("cell", c.code, s, { slot: s, cell: c });
      }
    }
  }
  for (const p of S.placements) {
    push("placement", p.code || p.name || "", p, {});
  }
  hits.sort((a, b) => a.rank - b.rank || a.code.length - b.code.length || (a.code < b.code ? -1 : 1));
  return { hits: hits.slice(0, limit), total: hits.length };
}
function worldOf(slot, cell) {
  const [wx, wy] = rotate(cell.lx, cell.ly, slot.rotation || 0);
  return { x: slot.x + wx, y: slot.y + wy, z: (layerOf(slot.layer_id) || { elevation: 0 }).elevation + (cell.dz || 0) };
}
function gotoCode(code) {
  const { hits } = findCodes(code, 5);
  const hit = hits.find((x) => x.rank === 0) || hits[0];
  if (!hit) {
    toast(`Код «${code}» не знайдено.`, "warn");
    return false;
  }
  return gotoHit(hit);
}
function gotoHit(hit) {
  const rec = hit.rec;
  const ly = layerOf(rec.layer_id);
  if (ly && V.hidden.has(ly.id)) {
    V.hidden.delete(ly.id);
    E.syncScene();
  }
  E.selectObj({ kind: hit.kind === "placement" ? "placement" : "slot", id: rec.id });
  let pos = { x: rec.x, y: rec.y };
  if (hit.kind === "cell") {
    S.selCell = hit.cell.code;
    pos = worldOf(hit.slot, hit.cell);
    E.updateVisual();
    E.renderCellsBox?.();
  }
  E.focusOn?.(pos.x, pos.y, hit.kind === "cell" ? 14 : 24);
  if (hit.kind === "cell") {
    E.cellPicked?.(rec.id, hit.cell.code);
  }
  return true;
}
var hlN = 0;
function setHighlight(codes, kind = "find") {
  S.hl = codes && codes.size ? { kind, codes, rev: ++hlN } : null;
  E.recolorCells?.();
}
var findState = { q: "", hits: null, demo: false };
function itemText(it) {
  const parts = [it.product || it.ref || "", it.qty != null ? `${it.qty}` : "", it.lot ? `партія ${it.lot}` : "", it.package ? `уп. ${it.package}` : ""];
  return parts.filter(Boolean).join(" · ");
}
function renderSearchTab(root) {
  const gotoIn = h("input", { type: "search", id: "s3Goto", placeholder: "Код або штрихкод, напр. PLT-01A", autocomplete: "off", "aria-label": "Перейти до місця", enterkeyhint: "go" });
  const gotoList = h("div", { class: "s3-list", id: "s3GotoList", role: "listbox" });
  const findIn = h("input", { type: "search", id: "s3Find", placeholder: "Товар, артикул, партія, упаковка", autocomplete: "off", "aria-label": "Де лежить", value: findState.q, enterkeyhint: "search" });
  const findInfo = h("div", { class: "small", id: "s3FindInfo" });
  const findList = h("div", { class: "s3-list", id: "s3FindList" });
  const drawGoto = () => {
    const { hits, total } = findCodes(gotoIn.value, 8);
    gotoList.replaceChildren(
      ...gotoIn.value && !hits.length ? [h("div", { class: "small muted" }, "Нічого не знайдено")] : [],
      ...hits.map(
        (x) => h("button", { class: "s3-item", type: "button", "data-code": x.code, role: "option", onclick: () => gotoHit(x) }, h("b", null, x.code), h("span", { class: "small muted" }, x.kind === "cell" ? "комірка" : x.kind === "placement" ? "обладнання" : x.slot?.template === "zone" ? "зона" : "місце"))
      ),
      ...total > hits.length ? [h("div", { class: "small muted" }, `…ще ${total - hits.length}: уточніть код`)] : []
    );
  };
  gotoIn.addEventListener("input", drawGoto);
  gotoIn.addEventListener("keydown", (e) => {
    if (e.key !== "Enter") {
      return;
    }
    e.preventDefault();
    const { hits } = findCodes(gotoIn.value, 5);
    const exact = hits.find((x) => x.rank === 0);
    if (exact || hits.length === 1) {
      gotoHit(exact || hits[0]);
      gotoIn.select();
    } else if (hits.length) {
      drawGoto();
      toast(`Збігів: ${hits.length}. Оберіть зі списку.`);
    } else {
      toast(`Код «${gotoIn.value}» не знайдено.`, "warn");
    }
  });
  const drawFind = () => {
    if (findState.hits == null) {
      findInfo.textContent = can("stock") ? "" : "Пошук за товаром недоступний: адаптер не віддає залишки.";
      findList.replaceChildren();
      return;
    }
    const n = findState.hits.length;
    findInfo.replaceChildren(`Знайдено місць: ${n}`, findState.demo ? h("span", { class: "tag s3-demo" }, "демо") : "", n ? h("button", { class: "fbtn sm", type: "button", id: "s3FindClear", onclick: () => {
      findState = { q: "", hits: null, demo: false };
      setHighlight(null);
      renderSearchTab(root.replaceChildren() || root);
    } }, "Скинути підсвітку") : "");
    findList.replaceChildren(
      ...findState.hits.slice(0, 100).map(
        (x) => h("button", { class: "s3-item", type: "button", "data-code": x.code, onclick: () => gotoCode(x.code) }, h("b", null, x.code), h("span", { class: "small" }, (x.items || []).map(itemText).join("; ")))
      )
    );
  };
  const runFind = async () => {
    const q = findIn.value.trim();
    findState.q = q;
    if (!q) {
      return;
    }
    if (!can("stock")) {
      toast("Пошук за товаром недоступний: адаптер не віддає залишки.", "warn");
      return;
    }
    try {
      const r = await findStock(q);
      findState = { q, hits: r ? r.hits : [], demo: !!r?.demo };
      setHighlight(new Set(findState.hits.map((x) => x.code)));
      drawFind();
      if (!findState.hits.length) {
        toast("Нічого не знайдено.", "warn");
      }
    } catch (e) {
      toast(e.message || "Не вдалося виконати пошук.", "err");
    }
  };
  findIn.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      runFind();
    }
  });
  root.append(
    h("div", { class: "sec", id: "s3GotoBox" }, h("h3", null, "Перейти до місця"), gotoIn, gotoList, h("div", { class: "small muted" }, "Регістр і розділювачі не важливі: plt01a → PLT-01A. Сканер: код + Enter.")),
    h("div", { class: "sec", id: "s3FindBox" }, h("h3", null, "Де лежить"), h("div", { class: "frow" }, findIn, h("button", { class: "fbtn sm", type: "button", id: "s3FindGo", onclick: runFind }, "Знайти")), findInfo, findList, h("div", { class: "small muted" }, "Кілька слів шукаються в одному залишку."))
  );
  drawGoto();
  drawFind();
}
registries.panels.add("left:search", { area: "left", tab: "search", label: "Пошук", render: renderSearchTab }, { sequence: 15, force: true });
function openSearch(mode = "goto") {
  E.setLeftTab("search");
  E.mobilePanel?.("left");
  setTimeout(() => {
    const el = $(mode === "find" ? "#s3Find" : "#s3Goto");
    if (el) {
      el.focus();
      el.select?.();
    }
  }, 30);
}
registries.hotkeys.add("search.slash", { key: "/", label: "/ — перейти до місця", run: (e) => (e.preventDefault(), openSearch("goto")) }, { sequence: 8, force: true });
registries.hotkeys.add("search.ctrlk", { ctrl: true, code: "KeyK", typing: true, label: "Ctrl+K — пошук", match: (e) => e.code === "KeyK" && !e.shiftKey, run: (e) => (e.preventDefault(), openSearch("goto")) }, { sequence: 9, force: true });
registries.menu.add("search", { area: "top", label: "Пошук", icon: "fit", sequence: 4, run: () => openSearch("goto") }, { sequence: 4, force: true });
Object.assign(E, { openSearch, gotoCode, gotoHit, gotoCell: gotoCode, findCodes, setHighlight });

// core/constructor/s3_chrome.js
var MOBILE_QUERY = "(max-width: 768px)";
var STYLE_ID = "f3d-s3-style";
var CSS = `
.f3d-s3 .s3-burger,.f3d-s3 .s3-mbar,.f3d-s3 .s3-objbtn,.f3d-s3 .s3-card-ov{display:none}
.f3d-s3 .s3-tools{position:absolute;right:8px;top:8px;display:flex;gap:4px;flex-wrap:wrap;justify-content:flex-end;max-width:calc(100% - 16px);z-index:2;align-items:center}
.f3d-s3 .s3-tools select{max-width:190px;min-height:30px}
.f3d-s3 .s3-heat{position:absolute;right:8px;bottom:8px;z-index:2;background:var(--surface);border:1px solid var(--line);padding:6px 8px;font-size:12px;line-height:1.5;max-width:230px}
.f3d-s3 .s3-heat-h{display:flex;gap:6px;align-items:center;flex-wrap:wrap;margin-bottom:2px}
.f3d-s3 .s3-heat-row{display:flex;gap:6px;align-items:center}
.f3d-s3 .s3-heat-row .num{margin-left:auto;color:var(--ink2)}
.f3d-s3 .s3-heat .sq{display:inline-block;width:12px;height:12px;border:1px solid var(--line);flex:none}
.f3d-s3 .s3-demo{background:var(--warn-soft);color:var(--warn);border:1px solid var(--warn);padding:0 4px;font-size:11px}
.f3d-s3 .s3-tip{position:absolute;z-index:6;pointer-events:none;background:var(--ink);color:var(--surface);padding:5px 8px;font-size:12px;line-height:1.4;max-width:260px;box-shadow:0 4px 14px rgba(0,0,0,.3)}
.f3d-s3 .s3-list{display:flex;flex-direction:column;max-height:260px;overflow:auto;border:1px solid var(--line2);margin-top:4px}
.f3d-s3 .s3-list:empty{display:none}
.f3d-s3 .s3-item{display:flex;gap:8px;align-items:baseline;justify-content:space-between;border:0;border-bottom:1px solid var(--line2);background:var(--surface);padding:6px 8px;text-align:left;cursor:pointer;min-height:34px}
.f3d-s3 .s3-item:hover{background:var(--accent-soft)}
.f3d-s3 .s3-card table{width:100%;border-collapse:collapse;font-size:12px}
.f3d-s3 .s3-card td,.f3d-s3 .s3-card th{padding:2px 4px;border-bottom:1px solid var(--line2);text-align:left}
.f3d-s3 .s3-card .kv{display:grid;grid-template-columns:auto 1fr;gap:2px 10px;margin:4px 0}
.f3d-s3 .s3-card .kv span:nth-child(odd){color:var(--ink2)}
.f3d-s3 .s3-bar{height:8px;background:var(--surface3);border:1px solid var(--line);margin:2px 0 6px}
.f3d-s3 .s3-bar i{display:block;height:100%;background:var(--accent)}
.f3d-s3 .s3-status{background:var(--accent-soft)}
.f3d-s3 .s3-status[data-status="unsaved"]{background:#bfeceb;color:#064e4c}
.f3d-s3 .s3-status[data-status="new"]{background:var(--warn-soft)}
@media (max-width: 768px){
  .f3d-s3 .top{gap:4px 6px;padding:4px 6px}
  .f3d-s3 .top .brand,.f3d-s3 .top .grow,.f3d-s3 .top .grp:not(#siteGrp),.f3d-s3 #modeSeg,.f3d-s3 #draftChip,.f3d-s3 #storeTag,.f3d-s3 #s3Access,.f3d-s3 #btnPublish,.f3d-s3 #btnHistory,.f3d-s3 #menuExtra,.f3d-s3 #btnNewSite,.f3d-s3 .s3-undo{display:none!important}
  .f3d-s3 .s3-burger{display:inline-flex}
  .f3d-s3 #siteGrp{flex:1 1 0;min-width:0}
  .f3d-s3 #siteSel{max-width:none;width:100%}
  .f3d-s3 .main{grid-template-columns:minmax(0,1fr)!important;grid-template-rows:minmax(0,1fr)!important}
  .f3d-s3 .center{grid-column:1!important;grid-row:1!important;min-width:0}
  .f3d-s3 .mtabs,.f3d-s3 .stamp,.f3d-s3 .legend,.f3d-s3 .vnotice{display:none!important}
  .f3d-s3 .left,.f3d-s3 .right{display:none!important;position:absolute;top:0;bottom:0;z-index:30;width:min(88vw,360px);max-width:100%;grid-column:auto!important;grid-row:auto!important;background:var(--surface);box-shadow:0 0 24px rgba(0,0,0,.35);border:0}
  .f3d-s3.m-left .left{display:flex!important;left:0}
  .f3d-s3.m-right .right{display:flex!important;right:0}
  .f3d-s3 .ltabs{display:flex!important;flex-wrap:wrap}
  .f3d-s3 .s3-mbar{display:flex;position:absolute;left:6px;right:6px;top:6px;z-index:4;gap:4px}
  .f3d-s3 .s3-mbar input{flex:1;min-width:0;min-height:36px;font-size:16px}
  .f3d-s3 .s3-mlist{position:absolute;left:0;right:0;top:40px;background:var(--surface);border:1px solid var(--line);max-height:50vh;overflow:auto}
  .f3d-s3 .vtools{top:50px!important;left:6px!important}
  .f3d-s3 .vtools .fbtn{min-height:34px}
  .f3d-s3 .s3-tools{top:auto;bottom:56px;right:6px;left:6px;justify-content:flex-start}
  .f3d-s3 .s3-tools select{max-width:60vw}
  .f3d-s3 .s3-heat{right:6px;bottom:96px;max-width:46vw;font-size:11px}
  .f3d-s3 .s3-objbtn{display:inline-flex;position:absolute;right:6px;bottom:8px;z-index:40}
  .f3d-s3.m-left .s3-burger{position:absolute;left:calc(min(88vw,360px) + 4px);top:6px;z-index:40}
  .f3d-s3.m-left .s3-objbtn{display:none}
  .f3d-s3 .s3-card-ov{display:flex;flex-direction:column;position:fixed;inset:0;z-index:60;background:var(--surface)}
  .f3d-s3 .s3-card-ov[hidden]{display:none}
  .f3d-s3 .s3-card-ov .s3-card-h{display:flex;align-items:center;gap:8px;padding:8px 10px;border-bottom:1px solid var(--line)}
  .f3d-s3 .s3-card-ov .s3-card-b{flex:1;overflow:auto;padding:10px}
  .f3d-s3 dialog{max-width:100vw;width:100%}
  .f3d-s3 .fbtn,.f3d-s3 .s3-item{min-height:36px}
}
`;
var isMobile = () => typeof window !== "undefined" && !!window.matchMedia && window.matchMedia(MOBILE_QUERY).matches;
function ensureStyle() {
  const root = ROOT.el;
  if (!root || root.querySelector("#" + STYLE_ID)) {
    return;
  }
  const st = document.createElement("style");
  st.id = STYLE_ID;
  st.textContent = CSS;
  root.prepend(st);
}
function applyMobile() {
  const app = $("#app");
  if (!app) {
    return;
  }
  const mob = isMobile();
  app.classList.toggle("m", mob);
  if (mob) {
    if (S.app.mode !== "view") {
      S.ui.modeBefore = S.app.mode;
      S.app.mode = "view";
      S.edit = null;
      E.cancelModes?.();
      E.renderAll?.();
    }
  } else {
    app.classList.remove("m-left", "m-right");
    hideCard();
    if (S.ui.modeBefore) {
      S.app.mode = S.ui.modeBefore;
      S.ui.modeBefore = null;
      E.renderAll?.();
    }
  }
}
function mobilePanel(side2, open = null) {
  const app = $("#app");
  if (!app || !isMobile()) {
    return;
  }
  const cls = side2 === "left" ? "m-left" : "m-right";
  const other = side2 === "left" ? "m-right" : "m-left";
  const on = open == null ? !app.classList.contains(cls) : open;
  app.classList.remove(other);
  app.classList.toggle(cls, on);
  decorate();
}
function tipHtml({ rec, kind, cell }) {
  const code = cell ? cell.code : kind === "placement" ? rec.code : rec.params?.title || rec.code_prefix;
  const lines = [h("b", null, code || "—")];
  const e = cell && E.stockOf?.(cell.code);
  if (cell) {
    if (e) {
      const top = e.top_product || e.detail && e.detail.rows && e.detail.rows[0] && e.detail.rows[0].product;
      lines.push(h("div", null, top ? `Товар: ${top}` : e.qty ? `Кількість: ${e.qty}` : "Порожньо"));
      lines.push(h("div", null, e.fill != null ? `Заповненість: ${Math.round(e.fill * 100)} %` : "Заповненість: —"));
    } else if (can("stock")) {
      lines.push(h("div", { style: { opacity: 0.8 } }, S.stock ? "нова комірка · без даних Odoo" : "залишки не завантажено"));
    }
  } else if (kind === "placement") {
    lines.push(h("div", null, rec.name || ""));
  }
  return lines;
}
function showTip(info) {
  const tip = $("#s3Tip");
  const cv = $("#vp");
  if (!tip || !cv || isMobile()) {
    return;
  }
  const r = cv.getBoundingClientRect();
  tip.replaceChildren(...tipHtml(info));
  tip.hidden = false;
  tip.style.left = Math.min(info.x - r.left + 14, r.width - 200) + "px";
  tip.style.top = Math.max(4, info.y - r.top + 14) + "px";
}
function hideTip() {
  const tip = $("#s3Tip");
  if (tip) {
    tip.hidden = true;
  }
}
function showCard(node, title) {
  const ov = $("#s3CardOv");
  if (!ov) {
    return;
  }
  $("#s3CardTitle").textContent = title || "";
  $("#s3CardBody").replaceChildren(node);
  ov.hidden = false;
}
function hideCard() {
  const ov = $("#s3CardOv");
  if (ov) {
    ov.hidden = true;
  }
}
function ensureDom() {
  const app = $("#app");
  if (!app) {
    return false;
  }
  app.classList.add("f3d-s3");
  const center2 = $(".center");
  if (!$("#s3Tools")) {
    const tools = h(
      "div",
      { class: "s3-tools", id: "s3Tools" },
      h("button", { class: "fbtn icon s3-undo", type: "button", id: "s3Undo", "aria-label": "Скасувати", onclick: () => E.undo() }, ic("rot")),
      h("button", { class: "fbtn icon s3-undo", type: "button", id: "s3Redo", "aria-label": "Повторити", style: { transform: "scaleX(-1)" }, onclick: () => E.redo() }, ic("rot")),
      h("select", { id: "s3Metric", "aria-label": "Показник", onchange: (e) => E.setMetric(e.target.value) }),
      h("button", { class: "fbtn icon", type: "button", id: "s3Refresh", "aria-label": "Оновити дані", title: "Оновити дані", onclick: () => E.refreshStock() }, ic("hist"))
    );
    center2.append(tools, h("div", { class: "s3-heat", id: "s3Heat", hidden: true }), h("div", { class: "s3-tip", id: "s3Tip", hidden: true }));
  }
  if (!$("#s3Burger")) {
    $(".top").prepend(h("button", { class: "fbtn icon s3-burger", type: "button", id: "s3Burger", "aria-label": "Панель", onclick: () => mobilePanel("left") }, h("span", { "aria-hidden": "true" }, "☰")));
  }
  const legend = $("#legend");
  if (legend && !$("#s3Keys")) {
    const k = (t) => h("kbd", null, t);
    legend.prepend(h("div", { id: "s3Keys" }, k("Ctrl+Z"), "/", k("Y"), " скасувати · ", k("Ctrl+D"), " дублювати · ", k("Ctrl+C"), "/", k("V"), " копіювати · ", k("Ctrl+клік"), " виділення · ", k("Shift+рамка"), " у «Плані» · ", k("/"), " пошук"));
  }
  if (!$("#s3Access")) {
    $("#storeTag").after(h("span", { class: "chip", id: "s3Access" }));
  }
  if (!$("#s3Mbar")) {
    const inp = h("input", { type: "search", id: "s3mSearch", placeholder: "Код місця, напр. PLT-01A", "aria-label": "Пошук місця", autocomplete: "off", enterkeyhint: "go" });
    const list = h("div", { class: "s3-mlist", id: "s3mList", hidden: true });
    const draw = () => {
      const { hits } = E.findCodes(inp.value, 8);
      list.hidden = !inp.value;
      list.replaceChildren(...hits.map((x) => h("button", { class: "s3-item", type: "button", onclick: () => (E.gotoHit(x), list.hidden = true, inp.blur()) }, h("b", null, x.code), h("span", { class: "small muted" }, x.kind === "cell" ? "комірка" : x.kind === "placement" ? "обладнання" : "місце"))));
    };
    inp.addEventListener("input", draw);
    inp.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        const { hits } = E.findCodes(inp.value, 5);
        const hit = hits.find((x) => x.rank === 0) || (hits.length === 1 ? hits[0] : null);
        if (hit) {
          E.gotoHit(hit);
          list.hidden = true;
          inp.blur();
        } else {
          draw();
        }
      }
    });
    center2.append(h("div", { class: "s3-mbar", id: "s3Mbar" }, inp, h("button", { class: "fbtn", type: "button", id: "s3mFind", onclick: () => E.openSearch("find"), "aria-label": "Де лежить" }, "Де?"), list));
    center2.append(h("button", { class: "fbtn primary s3-objbtn", type: "button", id: "s3ObjBtn", onclick: () => mobilePanel("right") }, "Панель об’єкта"));
    app.append(
      h(
        "div",
        { class: "s3-card-ov", id: "s3CardOv", hidden: true },
        h("div", { class: "s3-card-h" }, h("b", { id: "s3CardTitle", style: { flex: "1" } }), h("button", { class: "fbtn", type: "button", id: "s3CardClose", onclick: hideCard }, "Закрити")),
        h("div", { class: "s3-card-b", id: "s3CardBody" })
      )
    );
  }
  return true;
}
function decorate() {
  ensureStyle();
  if (!ensureDom()) {
    return;
  }
  renderUndoButtons();
  E.renderHeat?.();
  const acc = E.access?.();
  const tag = $("#s3Access");
  if (tag && acc) {
    tag.textContent = acc.name;
    tag.title = "Рівень доступу: " + acc.name + (acc.design ? "" : ". " + E.accessHint("design"));
  }
  $("#modeSeg")?.querySelectorAll("button").forEach((b) => {
    b.disabled = isMobile();
    b.title = isMobile() ? "У мобільному режимі правка вимкнена" : "";
  });
  const br = $("#s3Burger");
  if (br) {
    const open = $("#app").classList.contains("m-left");
    br.setAttribute("aria-expanded", String(open));
    br.firstChild.textContent = open ? "✕" : "☰";
  }
  const ob = $("#s3ObjBtn");
  if (ob) {
    ob.textContent = $("#app").classList.contains("m-right") ? "Закрити панель" : "Панель об’єкта";
  }
}
function renderUndoButtons() {
  const u = $("#s3Undo");
  if (!u) {
    return;
  }
  const st = E.undoState();
  const acc = E.access?.() || { design: true };
  const r = $("#s3Redo");
  u.disabled = !st.canUndo || !acc.design;
  r.disabled = !st.canRedo || !acc.design;
  u.title = !acc.design ? E.accessHint("design") : st.canUndo ? `Скасувати: ${st.undoLabel} (Ctrl+Z)` : "Немає що скасувати";
  r.title = !acc.design ? E.accessHint("design") : st.canRedo ? `Повторити: ${st.redoLabel} (Ctrl+Shift+Z)` : "Немає що повторити";
}
var onRootClick = (e) => {
  const more = $("#menuMore");
  if (more && more.open && (!more.contains(e.target) || e.target.closest(".morelist button"))) {
    more.open = false;
  }
};
var mql = null;
var onMql = () => {
  applyMobile();
  decorate();
};
function onMount() {
  decorate();
  applyMobile();
  mql = window.matchMedia ? window.matchMedia(MOBILE_QUERY) : null;
  mql?.addEventListener("change", onMql);
  ROOT.el?.addEventListener("click", onRootClick, true);
  rootWithClick = ROOT.el;
  E.restoreMetric?.();
}
var rootWithClick = null;
function onUnmount() {
  mql?.removeEventListener("change", onMql);
  mql = null;
  rootWithClick?.removeEventListener("click", onRootClick, true);
  rootWithClick = null;
}
E.lifecycle.mount.add(onMount);
E.lifecycle.unmount.add(onUnmount);
var origRenderAll = E.renderAll;
E.renderAll = function renderAllS3(...a) {
  const r = origRenderAll.apply(this, a);
  try {
    decorate();
    if (isMobile() && S.app.mode !== "view") {
      applyMobile();
    }
  } catch (e) {
    console.error("S3 chrome:", e);
  }
  return r;
};
Object.assign(E, { isMobile, mobilePanel, showTip, hideTip, showCard, hideCard, renderUndoButtons, decorateS3: decorate });

// core/constructor/card.js
var pct = (v) => v == null ? "—" : Math.round(v * 100) + " %";
var day = (iso) => iso ? String(iso).slice(0, 10) : "—";
function cardNode(slot, cell) {
  const root = h("div", { class: "s3-card", id: "s3Card", "data-code": cell.code });
  const draw = () => {
    const e = stockOf(cell.code);
    const d = e && e.detail || null;
    const ly = layerOf(slot.layer_id);
    const type = typeOf(slot.type_id, libraryState());
    const fill = e ? e.fill : null;
    root.replaceChildren(
      ...K(
        h("div", { class: "frow wrap" }, h("h3", { style: { margin: 0, flex: "1" } }, cell.code), h("span", { class: "tag" }, type ? type.name : (SLOT_TEMPLATES[slot.template] || {}).label || slot.template), ly ? h("span", { class: "tag" }, ly.name) : null),
        h(
          "div",
          { class: "kv" },
          h("span", null, "Місць"),
          h("span", null, String(cell.capacity ?? "—")),
          h("span", null, "Макс. навантаження"),
          h("span", null, cell.max_load_kg ? `${fmt(cell.max_load_kg, 0)} кг` : "—"),
          h("span", null, "Категорія"),
          h("span", null, d && d.category || slot.storage_category_name || "—"),
          e ? h("span", null, "Запас / резерв") : null,
          e ? h("span", null, `${e.qty ?? 0} / ${e.reserved ?? 0}`) : null,
          e && (e.min != null || e.max != null) ? h("span", null, "Min / max") : null,
          e && (e.min != null || e.max != null) ? h("span", null, `${e.min ?? "—"} / ${e.max ?? "—"}`) : null,
          e && e.age_days != null && e.qty ? h("span", null, "Вік запасу") : null,
          e && e.age_days != null && e.qty ? h("span", null, `${e.age_days} дн.`) : null
        ),
        fill != null ? h("div", null, h("div", { class: "small" }, `Заповненість: ${pct(fill)}`), h("div", { class: "s3-bar" }, h("i", { style: { width: Math.min(100, Math.round(fill * 100)) + "%" } }))) : null,
        !e && can("stock") ? h("div", { class: "small muted" }, S.stock ? "Нова комірка: даних Odoo ще немає." : "Залишки не завантажено (оберіть «Показник» чи «Оновити дані»).") : null,
        e && S.stock && S.stock.demo ? h("div", { class: "small" }, h("span", { class: "tag s3-demo" }, "демо"), " значення синтетичні") : null,
        d && d.rows && d.rows.length ? h("div", null, h("h4", { class: "small", style: { margin: "6px 0 2px" } }, "Залишки"), h("table", null, h("thead", null, h("tr", null, ["Товар", "К-сть", "Резерв", "Партія", "Вік"].map((t) => h("th", null, t)))), h("tbody", null, d.rows.map((r) => h("tr", null, h("td", null, r.product || r.ref || "—"), h("td", null, String(r.qty ?? "")), h("td", null, String(r.reserved ?? "")), h("td", null, r.lot || "—"), h("td", null, r.age_days != null ? r.age_days + " дн." : day(r.in_date))))))) : null,
        d && d.rules && d.rules.length ? h("div", null, h("h4", { class: "small", style: { margin: "6px 0 2px" } }, "Правила розміщення"), h("ul", { class: "small", style: { margin: 0, paddingLeft: "16px" } }, d.rules.map((r) => h("li", null, typeof r === "string" ? r : r.label || r.name)))) : null,
        d && d.moves && d.moves.length ? h("div", null, h("h4", { class: "small", style: { margin: "6px 0 2px" } }, `Рух за ${S.stock && S.stock.days || 90} днів`), h("table", null, h("tbody", null, d.moves.slice(0, 10).map((m) => h("tr", null, h("td", null, day(m.date)), h("td", null, m.product || ""), h("td", null, String(m.qty ?? "")), h("td", { class: "small muted" }, [m.from, m.to].filter(Boolean).join(" → "))))))) : null,
        h(
          "div",
          { class: "frow wrap", style: { marginTop: "6px" } },
          d && d.record && registries.dialogs.has("record") ? h("button", { class: "fbtn sm", type: "button", id: "btnOpenOdoo", onclick: () => E.openRecord(d.record.model, d.record.id) }, "Відкрити в Odoo") : null,
          h("button", { class: "fbtn sm", type: "button", id: "btnCardLabel", onclick: () => E.runDialog("labels", { spec: { scope: "row", rowId: slot.id } }) }, "Етикетка…")
        )
      )
    );
  };
  draw();
  if (can("stock")) {
    loadDetail(cell.code).then(() => {
      if (root.isConnected || $("#s3CardOv:not([hidden])")) {
        draw();
      }
    });
  }
  return root;
}
function renderCardBlock(root, { rec }) {
  if (!rec || !S.sel || S.sel.kind !== "slot" || !S.selCell) {
    return;
  }
  const cell = cellsOf(rec).find((c) => c.code === S.selCell);
  if (!cell) {
    return;
  }
  root.append(h("div", { class: "sec", id: "cardBlock" }, h("h3", null, "Картка місця"), cardNode(rec, cell)));
}
registries.panels.add("right:card", { area: "right", render: renderCardBlock }, { sequence: 20, force: true });
function cellPicked(slotId, code) {
  if (!E.isMobile?.()) {
    E.renderRight?.();
    return;
  }
  const slot = S.sIdx.get(slotId);
  const cell = slot && cellsOf(slot).find((c) => c.code === code);
  if (cell) {
    E.showCard(cardNode(slot, cell), cell.code);
  }
}
Object.assign(E, { cellPicked, cardNode });

// core/constructor/parse_codes.js
var PART_KEYS = ["zone", "row", "bay", "level", "pos", "prefix"];
var PART_LABELS = { zone: "зона", row: "ряд", bay: "секція", level: "ярус", pos: "позиція", prefix: "префікс" };
var NAMES = {
  zone: ["зона", "zone"],
  row: ["ряд", "row", "aisle"],
  bay: ["секція", "секция", "bay", "section"],
  level: ["ярус", "level", "tier"],
  pos: ["позиція", "позиция", "pos", "position"],
  prefix: ["префікс", "префикс", "prefix"]
};
var ALIAS = Object.fromEntries(Object.entries(NAMES).flatMap(([k, a]) => a.map((x) => [x, k])));
var RULE_TYPES = ["auto", "pallet_rack", "shelf", "cantilever", "floor_stack", "floor_spot"];
var TYPE_LABELS = { auto: "Тип: за частинами", pallet_rack: "Палетний стелаж", shelf: "Полицевий", cantilever: "Консольний", floor_stack: "Штабелі", floor_spot: "Місце на підлозі" };
var RULES_MAX = 30;
var TEXT_MAX = 160;
var esc2 = (s) => s.replace(/[.*+?^${}()|[\]\\/-]/g, "\\$&");
function tokenizeMask(mask) {
  if (typeof mask !== "string" || !mask.trim()) {
    throw new Error("Маска порожня.");
  }
  const toks = [];
  let lit = "";
  const flush = () => {
    if (lit) {
      toks.push({ t: "lit", text: lit });
      lit = "";
    }
  };
  for (let i = 0; i < mask.length; i++) {
    const ch = mask[i];
    if (ch === "{") {
      const j = mask.indexOf("}", i);
      if (j < 0) {
        throw new Error("У масці немає закриваючої дужки }.");
      }
      flush();
      const body = mask.slice(i + 1, j);
      const colon = body.indexOf(":");
      const key = ALIAS[(colon < 0 ? body : body.slice(0, colon)).trim().toLowerCase()];
      if (!key) {
        throw new Error(`Невідома частина {${body.trim()}}. Доступні: ряд, секція, ярус, зона, позиція, префікс.`);
      }
      toks.push({ t: "part", key, mod: colon < 0 ? "" : body.slice(colon + 1).trim() });
      i = j;
    } else if (ch === "*") {
      flush();
      toks.push({ t: "any" });
    } else {
      lit += ch;
    }
  }
  flush();
  if (!toks.some((x) => x.t === "part")) {
    throw new Error("У масці немає жодної частини ({ряд}, {секція}, {ярус} …).");
  }
  const seen = /* @__PURE__ */ new Set();
  for (const t of toks) {
    if (t.t === "part") {
      if (seen.has(t.key)) {
        throw new Error(`Частина {${PART_LABELS[t.key]}} повторюється в масці.`);
      }
      seen.add(t.key);
    }
  }
  return toks;
}
function partSpec(key, mod) {
  if (!mod) {
    return key === "zone" ? { kind: "text", src: "[A-Za-z0-9]+" } : key === "prefix" ? { kind: "text", src: "[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*?" } : { kind: "num", src: "[0-9]+" };
  }
  if (mod === "a" || mod === "A") {
    return { kind: "alpha", src: "[A-Za-z]+" };
  }
  if (mod === "n" || mod === "d" || mod === "#") {
    return { kind: "num", src: "[0-9]+" };
  }
  let m = /^([A-Za-z])\s*-\s*([A-Za-z])$/.exec(mod);
  if (m) {
    const [lo, hi] = [m[1].toUpperCase().charCodeAt(0) - 64, m[2].toUpperCase().charCodeAt(0) - 64];
    if (lo > hi) {
      throw new Error(`Діапазон літер {${PART_LABELS[key]}:${mod}}: початок більший за кінець.`);
    }
    return { kind: "alpha", lo, hi, src: "[A-Za-z]" };
  }
  m = /^(\d+)\s*-\s*(\d+)$/.exec(mod);
  if (m) {
    if (+m[1] > +m[2]) {
      throw new Error(`Діапазон чисел {${PART_LABELS[key]}:${mod}}: початок більший за кінець.`);
    }
    return { kind: "num", lo: +m[1], hi: +m[2], src: "[0-9]+" };
  }
  throw new Error(`Невідомий модифікатор «${mod}» у {${PART_LABELS[key]}:${mod}}: a (літери), A-D, 1-5.`);
}
function compileRule(rule) {
  const out = { ok: false, id: rule.id || "", type: rule.type || "auto", enabled: rule.enabled !== false, mode: rule.mode === "regex" ? "regex" : "mask", re: null, kinds: {}, tokens: null, spec: rule };
  try {
    if (out.mode === "regex") {
      const src = String(rule.regex || "");
      if (!src.trim() || src.length > TEXT_MAX) {
        throw new Error(`Регулярний вираз: 1…${TEXT_MAX} символів.`);
      }
      out.re = new RegExp(src, "i");
      const known = [...src.matchAll(/\(\?<([A-Za-z_]\w*)>/g)].map((m) => m[1]).filter((n) => PART_KEYS.includes(n));
      if (!known.length) {
        throw new Error("Регулярний вираз має містити групи (?<row>…), (?<bay>…), (?<level>…) (також zone, pos, prefix).");
      }
      for (const k of known) {
        out.kinds[k] = { kind: k === "zone" || k === "prefix" ? "text" : "num" };
      }
    } else {
      out.tokens = tokenizeMask(rule.mask);
      let src = "";
      for (const t of out.tokens) {
        if (t.t === "lit") {
          src += esc2(t.text);
        } else if (t.t === "any") {
          src += ".*?";
        } else {
          const sp = partSpec(t.key, t.mod);
          out.kinds[t.key] = sp;
          src += `(?<${t.key}>${sp.src})`;
        }
      }
      out.re = new RegExp(`^${src}$`, "i");
    }
    out.ok = true;
  } catch (e) {
    out.error = e.message || String(e);
  }
  return out;
}
function partValue(kind, text) {
  if (kind.kind === "text") {
    return text;
  }
  const n = kind.kind === "num" ? parseInt(text, 10) : fromAlpha(text.toUpperCase());
  return n == null || Number.isNaN(n) || kind.lo != null && (n < kind.lo || n > kind.hi) ? void 0 : n;
}
function matchRule(cr, code) {
  if (!cr.ok || !cr.enabled) {
    return null;
  }
  const m = cr.re.exec(code);
  if (!m) {
    return null;
  }
  const parts = {};
  const raw = {};
  for (const [key, text] of Object.entries(m.groups || {})) {
    if (text == null || !PART_KEYS.includes(key)) {
      continue;
    }
    const v = partValue(cr.kinds[key] || { kind: "num" }, text);
    if (v === void 0) {
      return null;
    }
    parts[key] = key === "zone" ? text : v;
    raw[key] = text;
  }
  return Object.keys(parts).length ? { parts, raw } : null;
}
var NUM_KEYS = ["row", "bay", "level", "pos"];
var segRe = (addr, key) => key === "prefix" ? "(?<prefix>[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*?)" : addr.seg[key].kind === "alpha" ? `(?<${key}>[A-Z]+)` : `(?<${key}>[0-9]+)`;
function addrMatchers(addrValue) {
  const addr = safeNormalize(addrValue);
  if (!addr.tpl) {
    return [];
  }
  const words = parseTpl(addr.tpl);
  const n = words.length;
  const subsets = [];
  for (let mask = 1; mask < 2 ** n; mask++) {
    const idx = [];
    for (let i = 0; i < n; i++) {
      if (mask >> i & 1) {
        idx.push(i);
      }
    }
    const keys = idx.flatMap((i) => words[i].filter(([k]) => k === "seg").map(([, name]) => name));
    if (keys.some((k) => NUM_KEYS.includes(k) || k === "prefix")) {
      subsets.push({ idx, keys });
    }
  }
  subsets.sort((a, b) => b.idx.length - a.idx.length || a.idx.join().localeCompare(b.idx.join(), "en", { numeric: true }));
  return subsets.map(({ idx, keys }) => {
    const body = idx.map((i) => words[i].map(([kind, item]) => kind === "lit" ? esc2(item) : segRe(addr, item)).join("")).join(esc2(addr.sep));
    return { addr, idx, keys, re: new RegExp(`^${body}$`) };
  });
}
function matchAddr(matchers, code) {
  for (const mt of matchers) {
    const m = mt.re.exec(code);
    if (!m) {
      continue;
    }
    const parts = {};
    const raw = {};
    let ok = true;
    for (const [key, text] of Object.entries(m.groups || {})) {
      raw[key] = text;
      if (key === "prefix" || key === "zone") {
        parts[key] = text;
        continue;
      }
      const spec = mt.addr.seg[key];
      const v = (spec.kind === "alpha" ? fromAlpha(text) : parseInt(text, 10)) - spec.start + 1;
      if (!(v >= 1)) {
        ok = false;
        break;
      }
      parts[key] = v;
    }
    if (ok) {
      return { parts, raw, matcher: mt };
    }
  }
  return null;
}
var LEGACY_RULES = [
  { id: "legacy:pallet_rack", mask: "{prefix}-B{bay}-L{level}", type: "pallet_rack" },
  { id: "legacy:cantilever", mask: "{prefix}-A{bay}-L{level}", type: "cantilever" },
  { id: "legacy:shelf", mask: "{prefix}-S{bay}-L{level}", type: "shelf" }
];
function makeParser({ rules = [], addr = null, legacy = true } = {}) {
  const custom = rules.map(compileRule);
  const matchers = addrMatchers(addr);
  const builtin = legacy ? LEGACY_RULES.map(compileRule) : [];
  const parse = (code) => {
    for (const cr of custom) {
      const r = matchRule(cr, code);
      if (r) {
        return { kind: "custom", rule: cr.id, type: cr.type, cr, ...r };
      }
    }
    const a = matchAddr(matchers, code);
    if (a) {
      return { kind: "addr", rule: "addr", type: "auto", ...a };
    }
    for (const cr of builtin) {
      const r = matchRule(cr, code);
      if (r) {
        return { kind: "legacy", rule: cr.id, type: cr.type, cr, ...r };
      }
    }
    return null;
  };
  return { parse, custom, matchers, errors: custom.filter((c) => !c.ok).map((c) => ({ id: c.id, error: c.error })) };
}
function levelKind(parts) {
  const hasBay = parts.bay != null;
  const hasLevel = parts.level != null;
  return hasBay && hasLevel ? "rack" : hasBay || hasLevel ? "stack" : "spot";
}
var LETTER = "A-Za-zА-Яа-яІіЇїЄєҐґ";
var lex = (code) => [...code.matchAll(new RegExp(`[${LETTER}]+|[0-9]+|[^${LETTER}0-9]+`, "g"))].map((m) => ({ t: /^[0-9]/.test(m[0]) ? "num" : new RegExp(`^[${LETTER}]`).test(m[0]) ? "alpha" : "sep", text: m[0] }));
var NUM_ORDER = { 1: ["bay"], 2: ["bay", "level"], 3: ["row", "bay", "level"], 4: ["zone", "row", "bay", "level"] };
function maskCandidates(code) {
  const toks = lex(code);
  const nums = toks.filter((t) => t.t === "num");
  const names = NUM_ORDER[Math.min(nums.length, 4)];
  if (!names) {
    return [];
  }
  const build = (keys, firstAlpha) => {
    let i = 0;
    let seenAlpha = 0;
    return toks.map((t) => {
      if (t.t === "sep") {
        return t.text;
      }
      if (t.t === "num") {
        const key = keys[i++];
        return key ? `{${PART_LABELS[key]}}` : "*";
      }
      if (seenAlpha++ === 0 && firstAlpha) {
        return firstAlpha;
      }
      return /^[A-Za-z]$/.test(t.text) ? t.text : "*";
    }).join("");
  };
  const out = [];
  if (toks[0].t === "alpha") {
    const lead = [build(names, "{префікс}"), build(names, "{зона:a}")];
    out.push(...toks[0].text.length === 1 ? lead.reverse() : lead);
    if (nums.length >= 3) {
      out.push(build(NUM_ORDER[nums.length - 1], "{префікс}"));
    }
  }
  out.push(build(names, null));
  return [...new Set(out)].filter((m) => m.includes("{"));
}
function guessMasks(codes, { limit = 5, sample = 40 } = {}) {
  const cands = /* @__PURE__ */ new Set();
  for (const code of codes.slice(0, sample)) {
    maskCandidates(code).forEach((m) => cands.add(m));
  }
  const rows = [];
  for (const mask of cands) {
    const cr = compileRule({ mask });
    if (cr.ok) {
      rows.push({ mask, matched: codes.reduce((n, c) => n + (matchRule(cr, c) ? 1 : 0), 0), total: codes.length, parts: cr.tokens.filter((t) => t.t === "part").length, order: rows.length });
    }
  }
  rows.sort((a, b) => b.matched - a.matched || b.parts - a.parts || a.order - b.order);
  return rows.filter((r) => r.matched > 0).slice(0, limit).map(({ mask, matched, total }) => ({ mask, matched, total }));
}
function normalizeRules(value) {
  const src = value && typeof value === "object" ? value : {};
  const rules = (Array.isArray(src.rules) ? src.rules : []).slice(0, RULES_MAX).map((r, i) => {
    const mode = r.mode === "regex" ? "regex" : "mask";
    const out2 = { id: String(r.id || `r${i + 1}`).slice(0, 24), mode, type: RULE_TYPES.includes(r.type) ? r.type : "auto", enabled: r.enabled !== false };
    out2[mode] = String(r[mode] || "").slice(0, TEXT_MAX);
    return out2;
  });
  const out = { v: 1, rules };
  if (Array.isArray(src.tray) && src.tray.length) {
    out.tray = src.tray;
  }
  if (src.tray_more) {
    out.tray_more = src.tray_more;
  }
  return out;
}
var siteRules = () => normalizeRules(S.site?.parse_rules);
var siteParser = (rules = siteRules().rules) => makeParser({ rules, addr: S.site?.addr || null });
function analyzeCodes(items, parser) {
  const out = { total: items.length, parsed: 0, unparsed: [], byRule: {} };
  for (const it of items) {
    const code = typeof it === "string" ? it : it.code;
    const r = parser.parse(code);
    if (!r) {
      out.unparsed.push({ code, loc: it });
    } else {
      out.parsed++;
      out.byRule[r.rule] = (out.byRule[r.rule] || 0) + 1;
    }
  }
  return out;
}
async function saveRules(next) {
  if (!S.site) {
    return;
  }
  S.site.parse_rules = next;
  if (E.adapter && typeof E.adapter.saveParseRules === "function") {
    await E.adapter.saveParseRules(next);
  }
  E.renderLeft?.();
}
var ruleSeq = 0;
var newRule = (mask = "") => ({ id: `r${Date.now().toString(36)}${ruleSeq++}`, mode: "mask", mask, type: "auto", enabled: true });
var codeOf = (i) => typeof i === "string" ? i : i.code;
function openParseCodes({ items = null } = {}) {
  const st = { rules: siteRules().rules.map((r) => ({ ...r })), items: items || (E.trayCodes ? E.trayCodes() : []) };
  const stats = h("div", { class: "small", id: "pcStats" });
  const bad = h("div", { class: "small", id: "pcUnparsed" });
  const rowsBox = h("div", { class: "fcol", id: "pcRules" });
  const guessBox = h("div", { class: "small", id: "pcGuess" });
  const parser = () => makeParser({ rules: st.rules, addr: S.site?.addr || null });
  const refresh = () => {
    const p = parser();
    const a = analyzeCodes(st.items, p);
    stats.textContent = `З ${a.total} місць розібрано ${a.parsed}` + (p.errors.length ? ` · правил із помилкою: ${p.errors.length}` : "");
    const ex2 = a.unparsed.slice(0, 8).map((u) => u.code);
    bad.replaceChildren(h("b", null, `Не розпізнано: ${a.unparsed.length}`), ex2.length ? h("div", { class: "mono small", id: "pcExamples" }, ex2.join(" · ") + (a.unparsed.length > ex2.length ? " …" : "")) : h("span", null, " — усе розібрано"));
    return p;
  };
  const render2 = () => {
    const p = refresh();
    rowsBox.replaceChildren(
      ...st.rules.map((r, i) => {
        const key = r.mode === "regex" ? "regex" : "mask";
        const input = h("input", { type: "text", value: r[key] || "", placeholder: key === "regex" ? "^(?<row>\\d+)-(?<bay>\\d+)-(?<level>\\d+)$" : "{ряд}-{секція}-{ярус}", "aria-label": "Маска", class: "pc-mask" });
        input.addEventListener("input", () => {
          r[key] = input.value;
          refresh();
        });
        const sel = (opts2, val, on, label) => {
          const s = h("select", { "aria-label": label }, opts2.map(([v, t]) => h("option", { value: v, selected: v === val }, t)));
          s.addEventListener("change", () => on(s.value));
          return s;
        };
        const move = (d) => {
          if (st.rules[i + d]) {
            [st.rules[i], st.rules[i + d]] = [st.rules[i + d], st.rules[i]];
            render2();
          }
        };
        const cr = p.custom[i];
        return h(
          "div",
          { class: "frow wrap pc-rule", "data-rule": r.id },
          h("input", { type: "checkbox", checked: r.enabled !== false, "aria-label": "Увімкнено", onchange: (e) => {
            r.enabled = e.target.checked;
            refresh();
          } }),
          sel([["mask", "Маска"], ["regex", "Регулярний вираз"]], r.mode, (v) => {
            r.mode = v;
            render2();
          }, "Режим"),
          input,
          sel(RULE_TYPES.map((t) => [t, TYPE_LABELS[t]]), r.type || "auto", (v) => {
            r.type = v;
          }, "Тип місця"),
          h("button", { class: "fbtn sm", type: "button", title: "Вище", "aria-label": "Вище", onclick: () => move(-1) }, "↑"),
          h("button", { class: "fbtn sm", type: "button", title: "Нижче", "aria-label": "Нижче", onclick: () => move(1) }, "↓"),
          h("button", { class: "fbtn sm danger", type: "button", title: "Видалити правило", "aria-label": "Видалити правило", onclick: () => {
            st.rules.splice(i, 1);
            render2();
          } }, "×"),
          cr && !cr.ok ? h("div", { class: "small err", style: { flexBasis: "100%" } }, cr.error) : null
        );
      })
    );
  };
  const guess = () => {
    const rest = analyzeCodes(st.items, parser()).unparsed.map((u) => u.code);
    const rows = guessMasks(rest.length ? rest : st.items.map(codeOf));
    guessBox.replaceChildren(
      ...rows.length ? rows.map((g3) => h("div", { class: "frow" }, h("span", { class: "mono" }, g3.mask), h("span", { class: "muted" }, `${g3.matched} із ${g3.total}`), h("button", { class: "fbtn sm", type: "button", "data-mask": g3.mask, onclick: () => {
        st.rules.push(newRule(g3.mask));
        render2();
      } }, "Додати"))) : [h("span", { class: "muted" }, "Не вдалося підібрати маску за зразками.")]
    );
  };
  const body = h(
    "div",
    { class: "fcol", id: "pcBody" },
    h("div", { class: "small muted" }, "Частини: {ряд} {секція} {ярус} {зона} {позиція} {префікс}; {x:a} — літери, {x:A-D} — діапазон літер, {x:1-5} — діапазон чисел, * — будь-який текст. Порядок = пріоритет; далі діє адресація площадки й «ПРЕФІКС-B01-L1»."),
    rowsBox,
    h("div", { class: "frow" }, h("button", { class: "fbtn sm", type: "button", id: "pcAdd", onclick: () => {
      st.rules.push(newRule());
      render2();
    } }, "+ Правило"), h("button", { class: "fbtn sm", type: "button", id: "pcGuessBtn", onclick: guess }, "Підібрати маску за зразками")),
    guessBox,
    stats,
    bad
  );
  render2();
  return new Promise((resolve) => {
    let saved2 = null;
    E.openDialog({
      title: "Розбір кодів",
      body,
      onClose: () => resolve(saved2),
      actions: [
        { label: "Закрити", value: "no" },
        {
          label: "Зберегти правила",
          cls: "primary",
          id: "pcSave",
          onClick: async () => {
            if (parser().errors.length) {
              toast("Виправте правила з помилкою.", "warn");
              return false;
            }
            try {
              saved2 = normalizeRules({ ...S.site?.parse_rules || {}, rules: st.rules });
              await saveRules(saved2);
            } catch (e) {
              saved2 = null;
              toast(e.message || "Не вдалося зберегти правила.", "err");
              return false;
            }
            toast("Правила розбору збережено.");
          }
        }
      ]
    });
  });
}
registries.dialogs.add("parseCodes", (args) => openParseCodes(args || {}), { force: true });
registries.menu.add("parseCodes", { area: "more", label: "Розбір кодів…", icon: "tag", sequence: 62, run: () => E.runDialog("parseCodes"), disabled: () => !S.site }, { sequence: 62, force: true });
Object.assign(E, { siteParser, normalizeParseRules: normalizeRules, saveParseRules: saveRules });

// core/constructor/autolayout.js
var EPS = 1e-6;
var CELL_TEMPLATES = Object.keys(SLOT_TEMPLATES).filter((t) => SLOT_TEMPLATES[t].cells);
var isBlockSlot = (s) => CELL_TEMPLATES.includes(s.template);
var natural = (a, b) => String(a).localeCompare(String(b), "uk", { numeric: true });
var ceilTo = (v, step) => Math.ceil(v / step - EPS) * step;
function layoutLines(blocks, { aisle = 3, gap = 0.5, margin = 0.5, maxL = Infinity, maxW = Infinity } = {}) {
  const limL = maxL - 2 * margin;
  const limW = maxW - 2 * margin;
  const lines = [];
  const byKey = /* @__PURE__ */ new Map();
  const push = (ln, b) => {
    ln.blocks.push(b);
    ln.len += b.l + (ln.blocks.length > 1 ? gap : 0);
    ln.depth = Math.max(ln.depth, b.w);
  };
  const newLine = (spot2) => ({ blocks: [], len: 0, depth: 0, spot: spot2 });
  for (const b of blocks.filter((x) => !x.spot)) {
    const key = b.line ?? b.id;
    let ln = byKey.get(key);
    if (!ln) {
      ln = newLine(false);
      byKey.set(key, ln);
      lines.push(ln);
    }
    push(ln, b);
  }
  const flat = [];
  for (const ln of lines) {
    if (ln.len <= limL + EPS) {
      flat.push(ln);
      continue;
    }
    let cur2 = newLine(false);
    for (const b of ln.blocks) {
      if (cur2.blocks.length && cur2.len + gap + b.l > limL + EPS) {
        flat.push(cur2);
        cur2 = newLine(false);
      }
      push(cur2, b);
    }
    flat.push(cur2);
  }
  const target = Number.isFinite(limL) ? limL : Math.max(20, ...flat.map((l) => l.len));
  let cur = null;
  for (const b of blocks.filter((x) => x.spot)) {
    if (!cur || cur.len + gap + b.l > target + EPS) {
      cur = newLine(true);
      flat.push(cur);
    }
    push(cur, b);
  }
  const tooLong = flat.find((ln) => ln.len > limL + EPS);
  if (tooLong) {
    return { ok: false, need: { l: tooLong.len + 2 * margin, w: 0 }, reason: `ряд довжиною ${fmt(tooLong.len, 1)} м не вміщається в зону` };
  }
  const cols = [];
  let col = null;
  for (const ln of flat) {
    const add = (col && col.lines.length ? aisle : 0) + ln.depth;
    if (!col || col.lines.length && col.depth + add > limW + EPS) {
      col = { lines: [], depth: 0, len: 0 };
      cols.push(col);
    }
    col.depth += (col.lines.length ? aisle : 0) + ln.depth;
    col.lines.push(ln);
    col.len = Math.max(col.len, ln.len);
  }
  const L2 = cols.reduce((s, c) => s + c.len, 0) + Math.max(0, cols.length - 1) * aisle + 2 * margin;
  const W = Math.max(0, ...cols.map((c) => c.depth)) + 2 * margin;
  if (L2 > maxL + EPS || W > maxW + EPS) {
    return { ok: false, need: { l: L2, w: W }, reason: `потрібно ${fmt(L2, 1)}×${fmt(W, 1)} м` };
  }
  const pos = /* @__PURE__ */ new Map();
  let u0 = margin;
  for (const c of cols) {
    let v0 = margin;
    for (const ln of c.lines) {
      let u = u0;
      for (const b of ln.blocks) {
        pos.set(b.id, { u: u + b.l / 2 - L2 / 2, v: v0 + ln.depth / 2 - W / 2 });
        u += b.l + gap;
      }
      v0 += ln.depth + aisle;
    }
    u0 += c.len + aisle;
  }
  return { ok: true, l: L2, w: W, pos };
}
var overlap = (a, b) => a[0] < b[2] - EPS && b[0] < a[2] - EPS && a[1] < b[3] - EPS && b[1] < a[3] - EPS;
function packRects(items, region, obstacles = [], { gap = 1, margin = 0.5 } = {}) {
  const x0 = region ? region.x0 + margin : margin;
  const x1 = region ? region.x1 - margin : Infinity;
  const y0 = region ? region.y0 + margin : margin;
  const y1 = region ? region.y1 - margin : Infinity;
  const pos = /* @__PURE__ */ new Map();
  let x = x0;
  let y = y0;
  let shelfH = 0;
  for (const it of items) {
    let guard3 = 0;
    for (; ; ) {
      if (++guard3 > 5e3) {
        return { ok: false, reason: "не вдалося знайти місце для зон", need: null };
      }
      if (x + it.l > x1 + EPS) {
        if (shelfH === 0) {
          return { ok: false, reason: `зона «${it.title || it.id}» ${fmt(it.l, 1)}×${fmt(it.w, 1)} м ширша за контур`, need: { l: it.l + 2 * margin, w: it.w } };
        }
        x = x0;
        y += shelfH + gap;
        shelfH = 0;
        continue;
      }
      if (y + it.w > y1 + EPS) {
        return { ok: false, reason: `зона «${it.title || it.id}» не вміщається в контур (бракує глибини)`, need: { l: it.l + 2 * margin, w: y + it.w - y0 + margin } };
      }
      const box = [x, y, x + it.l, y + it.w];
      const hit = obstacles.find((o) => overlap(box, o));
      if (hit) {
        x = hit[2] + gap;
        continue;
      }
      pos.set(it.id, { x: x + it.l / 2, y: y + it.w / 2 });
      x += it.l + gap;
      shelfH = Math.max(shelfH, it.w);
      break;
    }
  }
  return { ok: true, pos };
}
function layoutPlan({ zones, orphans = [], region = null, obstacles = [], aisle = 3, gap = 0.5, margin = 0.5, step = 0.5, zoneGap = 1 }) {
  const lim = region ? { maxL: region.x1 - region.x0, maxW: region.y1 - region.y0 } : {};
  const items = [];
  const lays = /* @__PURE__ */ new Map();
  const all = [...zones, ...orphans.length ? [{ id: "__orphans", title: "Поза зонами", blocks: orphans }] : []];
  for (const z of all) {
    const fixed = z.fixed || null;
    const r = layoutLines(z.blocks, { aisle, gap, margin, maxL: fixed ? fixed.l : lim.maxL ?? Infinity, maxW: fixed ? fixed.w : lim.maxW ?? Infinity });
    if (!r.ok) {
      return { ok: false, reason: `Зона «${z.title || z.id}»: ${r.reason}`, need: r.need };
    }
    const even = 2 * step;
    const size = fixed ? { l: fixed.l, w: fixed.w } : { l: Math.max(even * 2, ceilTo(r.l, even)), w: Math.max(even * 2, ceilTo(r.w, even)) };
    lays.set(z.id, { lay: r, size });
    items.push({ id: z.id, title: z.title, l: size.l, w: size.w });
  }
  const packed = packRects(items, region, obstacles, { gap: zoneGap, margin });
  if (!packed.ok) {
    return { ok: false, reason: packed.reason, need: packed.need };
  }
  const out = { ok: true, zones: /* @__PURE__ */ new Map(), blocks: /* @__PURE__ */ new Map(), orphans: null };
  for (const z of all) {
    const { lay, size } = lays.get(z.id);
    const c = packed.pos.get(z.id);
    const rect2 = { x: rnd(c.x, 3), y: rnd(c.y, 3), l: size.l, w: size.w };
    z.id === "__orphans" ? out.orphans = rect2 : out.zones.set(z.id, rect2);
    for (const [bid, p] of lay.pos) {
      out.blocks.set(bid, { x: rnd(c.x + p.u, 3), y: rnd(c.y + p.v, 3) });
    }
  }
  return out;
}
var slotOfZone = (zones, s) => {
  let host2 = null;
  for (const z of zones) {
    if (polygonContains(z.poly, [s.x, s.y]) && (!host2 || z.area < host2.area)) {
      host2 = z;
    }
  }
  return host2;
};
var polyArea3 = (p) => Math.abs(p.reduce((a, [x1, y1], i) => a + x1 * p[(i + 1) % p.length][1] - p[(i + 1) % p.length][0] * y1, 0)) / 2;
function blockOf(s) {
  const fp = footprint(s.template, s.params);
  return { id: s.id, l: fp.l, w: fp.w, spot: s.template === "floor_spot" };
}
var rectOfItem = (it) => {
  if ([it.x0, it.y0, it.x1, it.y1].every(Number.isFinite)) {
    return [it.x0, it.y0, it.x1, it.y1];
  }
  const w = it.w ?? it.length ?? it.l;
  const d = it.d ?? it.depth ?? it.width;
  if ([it.x, it.y, w, d].every(Number.isFinite)) {
    return [it.x - w / 2, it.y - d / 2, it.x + w / 2, it.y + d / 2];
  }
  return null;
};
function layerObstacles(ly) {
  const out = [];
  for (const r of [...ly.aisles || [], ...ly.fire_paths || [], ...ly.items || []]) {
    const b = rectOfItem(r);
    if (b) {
      out.push(b);
    }
  }
  for (const p of S.placements) {
    const v = p.layer_id === ly.id ? variantOf(p.variant_id) : null;
    if (v) {
      out.push(pGeom(p, v).box);
    }
  }
  for (const s of S.slots) {
    if (s.layer_id === ly.id && s.template === "machine_spot") {
      out.push(sGeom(s).box);
    }
  }
  return out;
}
function regionOf2(ly) {
  const b = ly && ly.bounds && [ly.bounds.x0, ly.bounds.y0, ly.bounds.x1, ly.bounds.y1].every(Number.isFinite) ? ly.bounds : null;
  if (b) {
    return { x0: b.x0, y0: b.y0, x1: b.x1, y1: b.y1 };
  }
  const bl = S.site && S.site.building;
  return bl && bl.length > 0 && bl.width > 0 ? { x0: 0, y0: 0, x1: bl.length, y1: bl.width } : null;
}
function pinBeforeMove(slots) {
  const zones = /* @__PURE__ */ new Map();
  for (const s of slots) {
    const ctx2 = contextOf(s);
    if (!ctx2) {
      continue;
    }
    const n = ctx2.row ?? ctx2.spot;
    if (n && safeNormalize(s.addr).row_no !== n) {
      s.addr = { ...safeNormalize(s.addr), row_no: n };
    }
    if (ctx2.zone != null && ctx2.addr && ctx2.addr.seg && /\{zone\}/.test(ctx2.addr.tpl || "")) {
      zones.set(s.id, { zone: ctx2.zone, spec: ctx2.addr.seg.zone });
    }
  }
  for (const z of S.slots.filter((x) => x.template === "zone" && !safeNormalize(x.addr).zone_code)) {
    const poly = slotPolygon(z);
    const hit = poly && slots.find((s) => zones.has(s.id) && polygonContains(poly, [s.x, s.y]));
    if (hit) {
      const { zone: zone2, spec } = zones.get(hit.id);
      const code = typeof zone2 === "string" ? zone2 : formatValue(spec, zone2);
      if (/^[A-Za-z0-9._/#:-]{1,8}$/.test(code)) {
        z.addr = { ...safeNormalize(z.addr), zone_code: code };
      }
    }
  }
}
var rotOf = (z) => z.rotation || 0;
var toWorld = (zone2, u, v) => {
  const a = rotOf(zone2) * Math.PI / 180;
  return { x: rnd(zone2.x + u * Math.cos(a) - v * Math.sin(a), 3), y: rnd(zone2.y + u * Math.sin(a) + v * Math.cos(a), 3) };
};
var orderBlocks = (list) => [...list].sort((a, b) => (a.template === "floor_spot") - (b.template === "floor_spot") || (rowNumberOf(a) ?? 1e9) - (rowNumberOf(b) ?? 1e9) || natural(a.code_prefix, b.code_prefix));
function guard2(ly) {
  const acc = E.access?.();
  if (acc && !acc.design) {
    toast(E.accessHint?.("design") || "Правка недоступна.", "warn");
    return false;
  }
  if (!ly || !canEditLayer(ly)) {
    if (ly) {
      toastLock(ly);
    }
    return false;
  }
  return true;
}
var zonesOf2 = (ly) => S.slots.filter((s) => s.template === "zone" && s.layer_id === ly.id).map((s) => ({ slot: s, poly: slotPolygon(s), area: 0 })).filter((z) => z.poly).map((z) => ({ ...z, area: polyArea3(z.poly) }));
function autoLayoutZone(zoneId, { quiet = false } = {}) {
  const zone2 = S.sIdx.get(zoneId);
  const ly = zone2 && layerOf(zone2.layer_id);
  if (!zone2 || zone2.template !== "zone") {
    return { ok: false, reason: "Зону не знайдено." };
  }
  if (!quiet && !guard2(ly)) {
    return { ok: false, reason: "Немає прав." };
  }
  if (zone2.locked) {
    const reason = "Складний контур зони редагується у формі Odoo.";
    quiet || toast(reason, "warn");
    return { ok: false, reason };
  }
  const zones = zonesOf2(ly);
  const mine = orderBlocks(S.slots.filter((s) => s.layer_id === ly.id && isBlockSlot(s) && slotOfZone(zones, s)?.slot.id === zone2.id));
  if (!mine.length) {
    quiet || toast("У зоні немає рядів для розкладки.", "warn");
    return { ok: false, reason: "У зоні немає рядів." };
  }
  const rot2 = rotOf(zone2);
  const plan = layoutPlan({
    zones: [{ id: zone2.id, title: zone2.params.title || zone2.code_prefix, blocks: mine.map((s) => ({ ...blockOf(s), line: s.addr?.row_no ? `r${s.addr.row_no}` : s.id })), fixed: { l: zone2.params.length, w: zone2.params.width } }],
    aisle: ly.aisle_width || 3,
    region: null,
    step: ly.grid_step || 0.5
  });
  if (!plan.ok) {
    const reason = `Ряди не вміщаються в зону: ${plan.reason}. Нічого не змінено.`;
    quiet || toast(reason, "warn");
    return { ok: false, reason };
  }
  E.undoRecord?.();
  pinBeforeMove(mine);
  const c = plan.zones.get(zone2.id);
  for (const s of mine) {
    const p = plan.blocks.get(s.id);
    Object.assign(s, { ...toWorld(zone2, p.x - c.x, p.y - c.y), rotation: rot2 });
  }
  E.undoLabel?.(`Авторозкладка: ${zone2.params.title || zone2.code_prefix}`);
  E.commit({});
  quiet || toast(`Розкладено рядів: ${mine.length}.`);
  return { ok: true, moved: mine.length };
}
function autoLayoutSite({ layerId = S.ui.layer, quiet = false, fixedSizes = false } = {}) {
  const ly = layerOf(layerId);
  if (!quiet && !guard2(ly)) {
    return { ok: false, reason: "Немає прав." };
  }
  if (!ly) {
    return { ok: false, reason: "Немає активного шару." };
  }
  const zs = zonesOf2(ly);
  const free = zs.filter((z) => !z.slot.locked);
  const lockedBoxes = zs.filter((z) => z.slot.locked).map((z) => [Math.min(...z.poly.map((p) => p[0])), Math.min(...z.poly.map((p) => p[1])), Math.max(...z.poly.map((p) => p[0])), Math.max(...z.poly.map((p) => p[1]))]);
  const blocks = S.slots.filter((s) => s.layer_id === ly.id && isBlockSlot(s));
  const own = new Map(free.map((z) => [z.slot.id, []]));
  const orphans = [];
  for (const s of blocks) {
    const host2 = slotOfZone(zs, s);
    if (host2 && host2.slot.locked) {
      continue;
    }
    (host2 ? own.get(host2.slot.id) : orphans).push(s);
  }
  if (!free.length && !orphans.length) {
    quiet || toast("Немає що розкладати: на шарі немає зон і рядів.", "warn");
    return { ok: false, reason: "Немає що розкладати." };
  }
  const sorted = [...free].sort((a, b) => a.slot.x - b.slot.x || a.slot.y - b.slot.y || natural(a.slot.code_prefix, b.slot.code_prefix));
  const lineOf = (s) => s.addr?.row_no ? `r${s.addr.row_no}` : s.id;
  const plan = layoutPlan({
    zones: sorted.map((z) => ({ id: z.slot.id, title: z.slot.params.title || z.slot.code_prefix, blocks: orderBlocks(own.get(z.slot.id)).map((s) => ({ ...blockOf(s), line: lineOf(s) })), fixed: fixedSizes || !own.get(z.slot.id).length ? { l: z.slot.params.length, w: z.slot.params.width } : null })),
    orphans: orderBlocks(orphans).map((s) => ({ ...blockOf(s), line: lineOf(s) })),
    region: regionOf2(ly),
    obstacles: [...layerObstacles(ly), ...lockedBoxes],
    aisle: ly.aisle_width || 3,
    step: ly.grid_step || 0.5
  });
  if (!plan.ok) {
    const reason = `Не вміщається: ${plan.reason}. Нічого не змінено.`;
    quiet || toast(reason, "warn");
    return { ok: false, reason, need: plan.need };
  }
  E.undoRecord?.();
  pinBeforeMove(blocks);
  for (const z of free) {
    const r = plan.zones.get(z.slot.id);
    Object.assign(z.slot, { x: r.x, y: r.y, rotation: 0 });
    z.slot.params = { ...z.slot.params, length: r.l, width: r.w };
  }
  for (const s of blocks) {
    const p = plan.blocks.get(s.id);
    if (p) {
      Object.assign(s, { x: p.x, y: p.y, rotation: 0 });
    }
  }
  E.undoLabel?.("Авторозкладка площадки");
  E.commit({});
  quiet || toast(`Розкладено: зон ${free.length}, рядів ${plan.blocks.size}.`);
  return { ok: true, zones: free.length, blocks: plan.blocks.size };
}
function renderZoneBlock(root, { rec }) {
  if (!rec || rec.template !== "zone") {
    return;
  }
  const dis = !canEditLayer(layerOf(rec.layer_id)) || !!rec.locked;
  root.append(
    h(
      "div",
      { class: "sec", id: "autoZone" },
      h("h3", null, "Авторозкладка"),
      h("div", { class: "small muted" }, "Ряди вглиб у межах зони; ручні положення й повороти всередині знімаються. Скасовується одним Ctrl+Z."),
      h("div", { class: "frow" }, h("button", { class: "fbtn", type: "button", id: "btnAutoZone", disabled: dis, onclick: () => autoLayoutZone(rec.id) }, "Розкласти автоматично"))
    )
  );
}
function renderSiteBlock3(root) {
  const ly = layerOf(S.ui.layer);
  root.append(
    h(
      "div",
      { class: "sec", id: "autoSite" },
      h("h3", null, "Авторозкладка"),
      h("div", { class: "small muted" }, "Зони по горизонталі в контурі шару (обходячи проходи, пожежні шляхи й об'єкти), ряди — вглиб. Скасовується одним Ctrl+Z."),
      h("div", { class: "frow" }, h("button", { class: "fbtn", type: "button", id: "btnAutoSite", disabled: !ly || !canEditLayer(ly), onclick: () => autoLayoutSite() }, "Розкласти автоматично"))
    )
  );
}
registries.panels.add("slot:autolayout", { area: "slot", render: renderZoneBlock }, { sequence: 45, force: true });
registries.panels.add("site:autolayout", { area: "site", render: renderSiteBlock3 }, { sequence: 45, force: true });
registries.menu.add("autolayout", { area: "more", label: "Авторозкладка площадки", icon: "fit", sequence: 64, run: () => autoLayoutSite(), disabled: () => !S.site || !canEditLayer(layerOf(S.ui.layer)) }, { sequence: 64, force: true });
Object.assign(E, { autoLayoutZone, autoLayoutSite });

// core/constructor/structure.js
var REASONS = {
  no_rule: "Код не збігається з жодним правилом розбору й немає зони-родителя",
  bad_code: "Код не підходить для місця: великі латинські літери, цифри й дефіси, до 22 символів",
  dup: "Код повторюється",
  size: "Секцій більше 200 або ярусів більше 12",
  not_reproduced: "Адресація не відтворює цей код",
  mask: "Маска не відтворюється адресацією (розділювач чи літерали)",
  bad_part: "Номер частини коду менший за початок нумерації",
  new_in_odoo: "З'явилося в Odoo після останнього оновлення"
};
var PREFIX_RE = /^[A-Z0-9]+(-[A-Z0-9]+)*$/;
var PREFIX_MAX2 = 22;
var LITERAL_RE2 = /^[A-Za-z0-9._/#:-]*$/;
var RACKS = ["pallet_rack", "shelf", "cantilever"];
var BAY_PARAM = { pallet_rack: ["bays", "levels"], shelf: ["sections", "shelves"], cantilever: ["arms", "levels"], floor_stack: ["cols", null] };
var SPOT_DEFAULT = { length: 1.2, width: 0.8, height: 1.5, capacity: 1, loc_kind: "area", shape: "zone" };
var ZONE_COLORS = ["#9fb7c9", "#c9b79f", "#a9c99f", "#c99fb7", "#9fc9c4", "#c9c49f"];
var fullName = (l) => l.parent ? `${l.parent}/${l.name}` : l.name;
var segs = (path) => path ? path.split("/") : [];
var natural2 = (a, b) => String(a).localeCompare(String(b), "uk", { numeric: true });
var validPrefix = (code) => PREFIX_RE.test(code) && code.length <= PREFIX_MAX2;
var trayItem = (loc, reason) => ({ code: loc.code, name: loc.name, parent: loc.parent || "", usage: loc.usage || "internal", reason });
function commonRoot(locs) {
  let root = null;
  for (const l of locs) {
    if (!l.parent) {
      continue;
    }
    const s = segs(l.parent);
    if (root === null) {
      root = s;
    } else {
      let i = 0;
      while (i < root.length && root[i] === s[i]) {
        i++;
      }
      root = root.slice(0, i);
    }
  }
  return root || [];
}
function deriveRoot(usable, cells) {
  const root = commonRoot(cells);
  const same4 = cells.length && cells.every((c) => c.parent === cells[0].parent);
  if (same4 && root.length >= 2 && usable.some((l) => l.usage === "view" && fullName(l) === root.join("/"))) {
    return root.slice(0, -1);
  }
  return root;
}
var tailNumber = (name) => {
  const m = /(\d+)\s*$/.exec(name || "");
  return m ? parseInt(m[1], 10) : null;
};
var ownAddr = (siteAddr) => !!(siteAddr && siteAddr.tpl);
function deriveAddr(cr, rawByKey, { levelAsBay = false } = {}) {
  if (!cr || !cr.tokens || cr.tokens.some((t) => t.t === "any")) {
    return null;
  }
  const keyOf = (k) => levelAsBay && k === "level" ? "bay" : k;
  const lits = cr.tokens.filter((t) => t.t === "lit").map((t) => t.text);
  const counts = {};
  for (const ch of lits.join("")) {
    if ("-._/#:".includes(ch)) {
      counts[ch] = (counts[ch] || 0) + 1;
    }
  }
  const sep = Object.keys(counts).sort((a, b) => counts[b] - counts[a])[0] || "-";
  const words = [""];
  for (const t of cr.tokens) {
    if (t.t === "part") {
      words[words.length - 1] += `{${keyOf(t.key)}}`;
      continue;
    }
    t.text.split(sep).forEach((piece, i) => {
      if (i) {
        words.push("");
      }
      words[words.length - 1] += piece;
    });
  }
  if (words.some((w) => !w) || words.some((w) => !LITERAL_RE2.test(w.replace(/\{[a-z]+\}/g, "")))) {
    return null;
  }
  const seg = {};
  for (const [key0, spec] of Object.entries(cr.kinds)) {
    const key = keyOf(key0);
    if (key === "prefix") {
      continue;
    }
    const raws = rawByKey[key0] || [];
    const padded = raws.some((r) => r.length > 1 && r.startsWith("0"));
    seg[key] = {
      kind: spec.kind === "alpha" ? "alpha" : "num",
      width: spec.kind === "alpha" ? 1 : padded ? Math.min(8, Math.max(...raws.map((r) => r.length))) : 1,
      start: spec.kind === "alpha" ? 1 : raws.some((r) => parseInt(r, 10) === 0) ? 0 : 1
    };
  }
  try {
    const out = normalizeAddr({ tpl: words.join(" "), sep, seg });
    parseTpl(out.tpl);
    return out;
  } catch {
    return null;
  }
}
function subsetAddr(siteAddr, matcher) {
  const words = siteAddr.tpl.trim().split(/\s+/);
  if (matcher.idx.length === words.length) {
    return null;
  }
  return normalizeAddr({ ...siteAddr, tpl: matcher.idx.map((i) => words[i]).join(" ") });
}
function emulate(spec, zone2, siteAddr, depthMode) {
  const addr = safeNormalize(spec.addr);
  const zoneAddr = zone2 && zone2.code ? { zone_code: zone2.code } : {};
  const eff = effectiveAddr(addr, zoneAddr, siteAddr);
  const ctx2 = { addr: eff, zone: zone2?.code ?? null, row: spec.template === "floor_spot" ? null : addr.row_no ?? null, spot: null, depth_mode: depthMode };
  return addressedCells(spec.template, normalizeParams(spec.template, spec.params), spec.code_prefix, 0, usableContext(ctx2) || { addr: null, depth_mode: depthMode }).map((c) => c.code);
}
function planStructure(locs, o = {}) {
  const { parser = makeParser({ rules: [], addr: null }), siteAddr = {}, depthMode = "level", existingCodes = /* @__PURE__ */ new Set(), existingPrefixes = /* @__PURE__ */ new Set() } = o;
  const stats = { total: locs.length, unparsedCodes: [], structure: 0, skipped_usage: 0, cells: 0, known: 0, parsed: 0, unparsed: 0, racks: 0, spots: 0, stock_qty: 0, warehouses: [], rules: {} };
  const tray = [];
  const usable = locs.filter((l) => {
    if (l.usage && !["internal", "view"].includes(l.usage)) {
      stats.skipped_usage++;
      return false;
    }
    return true;
  });
  const parents = new Set(usable.map((l) => l.parent).filter(Boolean));
  stats.warehouses = [...new Set(usable.map((l) => segs(fullName(l))[0]).filter(Boolean))];
  const cells = usable.filter((l) => {
    const isCell = l.usage !== "view" && !parents.has(fullName(l));
    if (!isCell) {
      stats.structure++;
    }
    return isCell;
  });
  const rootSegs = o.root || deriveRoot(usable, cells);
  stats.cells = cells.length;
  const zones = /* @__PURE__ */ new Map();
  const groups = /* @__PURE__ */ new Map();
  const spots = [];
  const seen = /* @__PURE__ */ new Set();
  const zoneRef = (key, title, code = null) => {
    if (!zones.has(key)) {
      zones.set(key, { key, title, code, order: zones.size });
    }
    return zones.get(key);
  };
  const byId = new Map(usable.filter((l) => l.id != null).map((l) => [l.id, l]));
  const below = (l) => {
    if (l.parent_id != null && byId.has(l.parent_id)) {
      const names = [];
      let cur = byId.get(l.parent_id);
      while (cur && cur.parent_id != null && byId.has(cur.parent_id)) {
        names.unshift(cur.name);
        cur = byId.get(cur.parent_id);
      }
      return names;
    }
    const p = segs(l.parent);
    return rootSegs.length && rootSegs.every((s, i) => p[i] === s) ? p.slice(rootSegs.length) : p.slice(Math.min(1, p.length));
  };
  for (const loc of [...cells].sort((a, b) => natural2(a.code, b.code))) {
    if (existingCodes.has(loc.code)) {
      stats.known++;
      continue;
    }
    if (seen.has(loc.code)) {
      tray.push(trayItem(loc, "dup"));
      continue;
    }
    seen.add(loc.code);
    stats.stock_qty += Number(loc.qty) > 0 ? 1 : 0;
    const ch = below(loc);
    const r = parser.parse(loc.code);
    if (!r) {
      stats.unparsedCodes.push(loc.code);
      if (!ch.length) {
        tray.push(trayItem(loc, "no_rule"));
      } else if (validPrefix(loc.code)) {
        spots.push({ loc, zone: zoneRef(`p:${ch[0]}`, ch[0]) });
      } else {
        tray.push(trayItem(loc, "bad_code"));
      }
      continue;
    }
    stats.parsed++;
    stats.rules[r.rule] = (stats.rules[r.rule] || 0) + 1;
    const parts = r.parts;
    let kind = r.type === "floor_spot" ? "spot" : levelKind(parts);
    let zone2 = null;
    let zoneFromPath = false;
    if (parts.zone != null) {
      const raw = r.raw.zone ?? String(parts.zone);
      zone2 = zoneRef(`z:${raw.toUpperCase()}`, `Зона ${raw}`, /^[A-Za-z0-9._/#:-]{1,8}$/.test(raw) ? raw : null);
    } else if (ch.length >= 2 || ch.length === 1 && parts.row != null) {
      zone2 = zoneRef(`p:${ch[0]}`, ch[0]);
      zoneFromPath = true;
    }
    if (kind === "spot") {
      if (!validPrefix(loc.code)) {
        tray.push(trayItem(loc, "bad_code"));
        continue;
      }
      spots.push({ loc, zone: zone2, rule: r });
      continue;
    }
    const rest = zoneFromPath ? ch.slice(1) : ch;
    const holder = rest.length ? rest[rest.length - 1] : null;
    let rowKey;
    let rowVal = null;
    if (parts.row != null) {
      rowKey = `r:${parts.row}`;
      rowVal = parts.row;
    } else if (parts.prefix != null) {
      rowKey = `x:${String(parts.prefix).toUpperCase()}`;
    } else if (holder) {
      rowKey = `c:${loc.parent_id ?? segs(loc.parent).join("/")}`;
      rowVal = tailNumber(holder);
    } else {
      rowKey = "none";
    }
    const keys = Object.keys(parts).sort().join(",");
    const gkey = [zone2 ? zone2.key : "", rowKey, r.kind, r.rule, kind, keys].join("|");
    if (!groups.has(gkey)) {
      groups.set(gkey, { key: gkey, zone: zone2, rowKey, rowVal, kind, rule: r, items: [], holder, subsetOf: r.matcher || null });
    }
    const bay = parts.bay ?? parts.level;
    groups.get(gkey).items.push({ loc, bay, level: parts.bay != null ? parts.level ?? null : null, raw: r.raw, parts });
  }
  const used = new Set(existingPrefixes);
  const mkPrefix = (base2) => {
    let b = base2.toUpperCase().replace(/[^A-Z0-9-]+/g, "-").replace(/^-+|-+$/g, "").replace(/-{2,}/g, "-").slice(0, PREFIX_MAX2 - 4) || "R";
    let p = b;
    for (let n = 2; used.has(p); n++) {
      p = `${b}-${n}`;
    }
    used.add(p);
    return p;
  };
  const slots = [];
  const siteN = safeNormalize(siteAddr);
  const demote = (g3, reason) => g3.items.forEach((it) => tray.push(trayItem(it.loc, reason)));
  for (const g3 of [...groups.values()].sort((a, b) => natural2(a.zone?.key || "", b.zone?.key || "") || natural2(a.rowKey, b.rowKey))) {
    const rule = g3.rule;
    let startBay = 1;
    let startLevel = 1;
    let startRow = 1;
    let deriv = null;
    if (rule.kind === "custom") {
      const raws = {};
      for (const it of g3.items) {
        for (const [k, v] of Object.entries(it.raw)) {
          (raws[k] ||= []).push(v);
        }
      }
      deriv = deriveAddr(rule.cr, raws, { levelAsBay: g3.kind === "stack" && g3.items[0].parts.bay == null });
      if (!deriv) {
        demote(g3, "mask");
        continue;
      }
      startBay = deriv.seg.bay ? deriv.seg.bay.start : 1;
      startLevel = deriv.seg.level ? deriv.seg.level.start : 1;
      startRow = deriv.seg.row ? deriv.seg.row.start : 1;
    }
    const bays = Math.max(...g3.items.map((it) => it.bay - startBay + 1));
    const levels = g3.kind === "rack" ? Math.max(...g3.items.map((it) => it.level - startLevel + 1)) : 1;
    if (Math.min(...g3.items.map((it) => it.bay - startBay + 1)) < 1 || g3.kind === "rack" && Math.min(...g3.items.map((it) => it.level - startLevel + 1)) < 1) {
      demote(g3, "bad_part");
      continue;
    }
    if (bays > 200 || levels > 12) {
      demote(g3, "size");
      continue;
    }
    const template = g3.kind === "rack" ? RACKS.includes(rule.type) ? rule.type : "pallet_rack" : "floor_stack";
    const [bk, lk] = BAY_PARAM[template];
    const params = { [bk]: bays };
    if (lk) {
      params[lk] = levels;
    } else {
      params.rows = 1;
    }
    if (rule.kind === "legacy") {
      const w = g3.items.map((it) => it.raw.bay || "");
      params.index_digits = Math.min(4, Math.max(1, w.some((x) => x.length > 1 && x.startsWith("0")) ? Math.max(...w.map((x) => x.length)) : 1));
    }
    let addr = null;
    if (rule.kind === "custom") {
      addr = deriv;
    } else if (rule.kind === "addr") {
      addr = subsetAddr(siteN, rule.matcher);
    } else if (ownAddr(siteN)) {
      addr = { legacy: true };
    }
    let rowNo = null;
    if (g3.rowVal != null && rule.kind !== "legacy") {
      rowNo = g3.rowVal - (rule.kind === "custom" ? startRow : 1) + 1;
      if (rowNo >= 1 && rowNo <= 9999 && g3.rowKey.startsWith("r:")) {
        addr = { ...addr || {}, row_no: rowNo };
      } else {
        rowNo = null;
      }
    }
    const prefix0 = rule.kind === "legacy" ? String(g3.items[0].raw.prefix || "") : [g3.zone ? g3.zone.code || `Z${g3.zone.order + 1}` : "", g3.rowKey.startsWith("r:") ? `R${String(g3.rowVal).padStart(2, "0")}` : g3.holder ? g3.holder : "R"].filter(Boolean).join("-");
    if (rule.kind === "legacy" && (!validPrefix(prefix0) || used.has(prefix0))) {
      demote(g3, used.has(prefix0) ? "dup" : "bad_code");
      continue;
    }
    const spec = { id: newUid(), template, code_prefix: rule.kind === "legacy" ? (used.add(prefix0), prefix0) : mkPrefix(prefix0), params, addr: addr && Object.keys(addr).length ? addr : null, overrides: {}, zoneKey: g3.zone ? g3.zone.key : null, lineKey: g3.rowKey, items: g3.items.map((it) => it.loc), group: g3.key };
    const want = new Set(g3.items.map((it) => it.loc.code));
    const got = emulate(spec, g3.zone, siteN, depthMode);
    if ([...want].some((c) => !got.includes(c))) {
      used.delete(spec.code_prefix);
      demote(g3, "not_reproduced");
      continue;
    }
    for (const c of got) {
      if (!want.has(c)) {
        spec.overrides[c] = { disabled: true };
      }
    }
    for (const it of g3.items) {
      if (it.loc.name && it.loc.name !== it.loc.code) {
        spec.overrides[it.loc.code] = { ...spec.overrides[it.loc.code] || {}, name: it.loc.name };
      }
    }
    slots.push(spec);
    stats.racks++;
  }
  const owner = /* @__PURE__ */ new Map();
  for (const sp of [...slots]) {
    const codes = sp.items.map((l) => l.code);
    const clash = codes.find((c) => owner.has(c));
    if (clash) {
      slots.splice(slots.indexOf(sp), 1);
      sp.items.forEach((l) => tray.push(trayItem(l, "dup")));
      used.delete(sp.code_prefix);
      stats.racks--;
    } else {
      codes.forEach((c) => owner.set(c, sp.id));
    }
  }
  for (const { loc, zone: zone2, rule } of spots) {
    if (existingPrefixes.has(loc.code) || used.has(loc.code)) {
      tray.push(trayItem(loc, "dup"));
      continue;
    }
    used.add(loc.code);
    const spec = { id: newUid(), template: "floor_spot", code_prefix: loc.code, params: { ...SPOT_DEFAULT }, addr: ownAddr(siteN) ? { legacy: true } : null, overrides: {}, zoneKey: zone2 ? zone2.key : null, lineKey: `s:${zone2 ? zone2.key : ""}`, items: [loc], group: `s:${loc.code}` };
    if (loc.name && loc.name !== loc.code) {
      spec.overrides[loc.code] = { name: loc.name };
    }
    slots.push(spec);
    stats.spots++;
  }
  const usedZones = new Set(slots.map((s) => s.zoneKey).filter(Boolean));
  for (const key of [...zones.keys()]) {
    if (!usedZones.has(key)) {
      zones.delete(key);
    }
  }
  stats.unparsed = tray.length;
  return { zones, slots, tray, stats };
}
var slotDict2 = (s) => ({ uid: s.id, id: s.id, layer_id: s.layer_id, template: s.template, code_prefix: s.code_prefix, x: s.x, y: s.y, rotation: s.rotation || 0, params: s.params, polygon: null, addr: s.addr || null, depth_mode: s.depth_mode || null });
function realCodes(slots, others = S.slots) {
  const ids = new Set(slots.map((s) => s.id));
  const all = [...others.filter((s) => !ids.has(s.id)), ...slots];
  const ctxs = addressContext(all.map(slotDict2), S.site?.addr, S.site?.depth_mode || "level");
  const out = /* @__PURE__ */ new Map();
  for (const s of slots) {
    if (s.template !== "zone") {
      const ov = s.overrides || {};
      const cells = addressedCells(s.template, normalizeParams(s.template, s.params), s.code_prefix, s.rotation || 0, usableContext(ctxs.get(s.id)));
      out.set(s.id, cells.map((c) => c.code).filter((c) => !(ov[c] && ov[c].disabled)));
    }
  }
  return out;
}
var importLayer = () => {
  const cur = layerOf(S.ui.layer);
  return cur && cur.kind === "storage" ? cur : S.layers.find((l) => l.kind === "storage") || cur;
};
var blockOfSlot = (r, spec) => {
  const fp = footprint(r.template, r.params);
  return { id: r.id, line: spec.lineKey, spot: r.template === "floor_spot", l: fp.l, w: fp.w };
};
var projectCodes = () => new Set(S.slots.flatMap((s) => cellsOf(s).filter((c) => !c.disabled).map((c) => c.code)));
function commitStructure(plan, { label = "Імпорт структури", layout = true, growBuilding = false, keepTray = true } = {}) {
  const ly = importLayer();
  if (!ly || !canEditLayer(ly)) {
    return { ok: false, reason: ly ? lockHint(ly) : "Немає шару для місць." };
  }
  const need = [...new Set(plan.slots.map((s) => s.template).concat(plan.zones.size ? ["zone"] : []))];
  const miss = need.filter((t) => !ly.slot_types.includes(t));
  if (miss.length && !canManage()) {
    return { ok: false, reason: `Шар «${ly.name}» не допускає типи місць: ${miss.join(", ")}. Дозвіл змінює менеджер.` };
  }
  const used = new Set(S.slots.map((s) => s.code_prefix));
  const zoneSlots = /* @__PURE__ */ new Map();
  let zi = 0;
  for (const z of [...plan.zones.values()].sort((a, b) => a.order - b.order)) {
    let prefix = `Z-${(z.code || String(++zi)).toUpperCase().replace(/[^A-Z0-9]/g, "") || zi}`.slice(0, 12);
    for (let n = 2; used.has(prefix); n++) {
      prefix = `${prefix.replace(/-\d+$/, "")}-${n}`;
    }
    used.add(prefix);
    const rec = { id: newUid(), rid: null, etag: null, layer_id: ly.id, template: "zone", code_prefix: prefix, x: 0, y: 0, rotation: 0, params: { length: 10, width: 8, title: z.title, color: ZONE_COLORS[z.order % ZONE_COLORS.length] }, overrides: {}, parent_location_id: null };
    if (z.code) {
      rec.addr = { zone_code: z.code };
    }
    zoneSlots.set(z.key, rec);
  }
  const racks = plan.slots.map((sp) => {
    const rec = { id: sp.id, rid: null, etag: null, layer_id: ly.id, template: sp.template, code_prefix: sp.code_prefix, x: 0, y: 0, rotation: 0, params: clone(sp.params), overrides: clone(sp.overrides), parent_location_id: null };
    if (sp.addr) {
      rec.addr = clone(sp.addr);
    }
    return { rec, spec: sp };
  });
  const step = ly.grid_step || 0.5;
  let rects = [];
  if (layout) {
    const zoneSpecs = [...zoneSlots].map(([key, z]) => ({ id: z.id, title: z.params.title, blocks: racks.filter((r) => r.spec.zoneKey === key).map((r) => blockOfSlot(r.rec, r.spec)) }));
    const orphans = racks.filter((r) => !r.spec.zoneKey).map((r) => blockOfSlot(r.rec, r.spec));
    const existing = S.slots.filter((s) => s.layer_id === ly.id).map((s) => sGeom(s).box);
    const base2 = { zones: zoneSpecs, orphans, aisle: ly.aisle_width || 3, step };
    let lp = growBuilding ? { ok: false } : layoutPlan({ ...base2, region: regionOf2(ly), obstacles: [...layerObstacles(ly), ...existing] });
    let outside = false;
    if (!lp.ok) {
      const right = Math.max(0, ...existing.map((b) => b[2]));
      lp = layoutPlan({ ...base2, region: { x0: right ? right + 1 : 0, y0: 0, x1: Infinity, y1: Infinity }, obstacles: [] });
      outside = !growBuilding && !!regionOf2(ly);
      if (!lp.ok) {
        return { ok: false, reason: lp.reason };
      }
    }
    for (const [, z] of zoneSlots) {
      const r = lp.zones.get(z.id);
      Object.assign(z, { x: r.x, y: r.y });
      Object.assign(z.params, { length: r.l, width: r.w });
    }
    for (const { rec } of racks) {
      Object.assign(rec, lp.blocks.get(rec.id));
    }
    rects = [...lp.zones.values(), ...lp.orphans ? [lp.orphans] : []];
    plan = { ...plan, outside };
  }
  const codes = realCodes(racks.map((r) => r.rec), [...S.slots, ...zoneSlots.values()]);
  const tray = [...plan.tray];
  const kept = [];
  for (const { rec, spec } of racks) {
    const want = new Set(spec.items.map((l) => l.code));
    const got = new Set(codes.get(rec.id) || []);
    if (want.size === got.size && [...want].every((c) => got.has(c))) {
      kept.push({ rec, spec });
    } else {
      spec.items.forEach((l) => tray.push(trayItem(l, "not_reproduced")));
    }
  }
  const keptZones = [...zoneSlots].filter(([key]) => kept.some((k) => k.spec.zoneKey === key)).map(([, z]) => z);
  E.undoRecord?.();
  S.ui.layer = ly.id;
  if (miss.length) {
    ly.slot_types.push(...miss);
  }
  if (growBuilding && rects.length && S.site.building) {
    const L2 = Math.ceil(Math.max(...rects.map((r) => r.x + r.l / 2)) + 2);
    const W = Math.ceil(Math.max(...rects.map((r) => r.y + r.w / 2)) + 2);
    const b = S.site.building;
    if (L2 > b.length || W > b.width) {
      Object.assign(b, { length: Math.max(L2, b.length), width: Math.max(W, b.width) });
      E.saveSiteProps?.();
    }
  }
  keptZones.forEach((z) => S.slots.push(z));
  kept.forEach((k) => S.slots.push(k.rec));
  const have = new Set((keepTray ? S.site.parse_rules?.tray || [] : []).map((t) => t.code));
  E.setTray?.([...keepTray ? S.site.parse_rules?.tray || [] : [], ...tray.filter((t) => !have.has(t.code))]);
  const cellsN = kept.reduce((n, k) => n + k.spec.items.length, 0);
  E.undoLabel?.(`${label}: ${fmtInt(cellsN)} місць`);
  E.commit({});
  return { ok: true, created: kept.length + keptZones.length, zones: keptZones.length, slots: kept.length, cells: cellsN, tray: tray.length, outside: !!plan.outside };
}
function importLocations(locs, { label, layout = true, growBuilding = false, parseRules = null } = {}) {
  const parser = makeParser({ rules: parseRules || siteRules().rules, addr: S.site?.addr || null });
  const plan = planStructure(locs, { parser, siteAddr: safeNormalize(S.site?.addr), depthMode: S.site?.depth_mode || "level", existingCodes: projectCodes(), existingPrefixes: new Set(S.slots.map((s) => s.code_prefix)) });
  const keep = S.site.parse_rules;
  if (parseRules) {
    S.site.parse_rules = normalizeRules({ ...keep || {}, rules: parseRules });
  }
  const res = commitStructure(plan, { label, layout, growBuilding });
  if (!res.ok) {
    S.site.parse_rules = keep;
  }
  return { ...res, plan };
}
Object.assign(E, { importLocations, planStructure, commitStructure });

// core/constructor/tray.js
var TRAY_MAX = 5e3;
var PREFIX_RE2 = /^[A-Z0-9]+(-[A-Z0-9]+)*$/;
var SPOT = { length: 1.2, width: 0.8, height: 1.5, capacity: 1, loc_kind: "area", shape: "zone" };
var SHOWN = 120;
var filterText = "";
function trayItems() {
  const stored = S.site && S.site.parse_rules && S.site.parse_rules.tray || [];
  if (!stored.length) {
    return [];
  }
  const have = projectCodes();
  return stored.filter((t) => !have.has(t.code));
}
function setTray(list, { persist = true } = {}) {
  if (!S.site) {
    return;
  }
  const keep = list.slice(0, TRAY_MAX);
  const next = normalizeRules({ ...S.site.parse_rules || {}, tray: keep, tray_more: Math.max(0, list.length - keep.length) });
  if (!keep.length) {
    delete next.tray;
    delete next.tray_more;
  }
  S.site.parse_rules = next;
  if (persist) {
    Promise.resolve(saveRules(next)).catch((e) => toast(e.message || "Не вдалося зберегти лоток.", "err"));
  }
  updateTabLabel();
}
function trayCodes() {
  return [.../* @__PURE__ */ new Set([...trayItems().map((t) => t.code), ...projectCodes()])];
}
var zonesOnLayer = (layerId) => S.slots.filter((s) => s.template === "zone" && s.layer_id === layerId && slotPolygon(s));
var zoneAt = (layerId, x, y) => {
  let best = null;
  for (const z of zonesOnLayer(layerId)) {
    const poly = slotPolygon(z);
    const area = (z.params.length || 1) * (z.params.width || 1);
    if (polygonContains(poly, [x, y]) && (!best || area < best.area)) {
      best = { z, area };
    }
  }
  return best ? best.z : null;
};
var overlaps = (a, b) => a[0] < b[2] - 1e-6 && b[0] < a[2] - 1e-6 && a[1] < b[3] - 1e-6 && b[1] < a[3] - 1e-6;
function freePositions(layerId, n, { zone: zone2 = null, point = null } = {}) {
  const [fl, fw] = [SPOT.length, SPOT.width];
  const gap = 0.3;
  const taken = S.slots.filter((s) => s.layer_id === layerId && s.template !== "zone").map((s) => sGeom(s).box);
  const out = [];
  const free = (x2, y2) => {
    const box = [x2 - fl / 2, y2 - fw / 2, x2 + fl / 2, y2 + fw / 2];
    return !taken.some((t) => overlaps(box, t)) && !out.some((o) => overlaps(box, [o.x - fl / 2, o.y - fw / 2, o.x + fl / 2, o.y + fw / 2]));
  };
  if (zone2) {
    const rot2 = (zone2.rotation || 0) * Math.PI / 180;
    const [L2, W] = [zone2.params.length, zone2.params.width];
    for (let v = -W / 2 + 0.5 + fw / 2; v <= W / 2 - 0.5 - fw / 2 + 1e-6 && out.length < n; v += fw + gap) {
      for (let u = -L2 / 2 + 0.5 + fl / 2; u <= L2 / 2 - 0.5 - fl / 2 + 1e-6 && out.length < n; u += fl + gap) {
        const x2 = zone2.x + u * Math.cos(rot2) - v * Math.sin(rot2);
        const y2 = zone2.y + u * Math.sin(rot2) + v * Math.cos(rot2);
        if (free(x2, y2)) {
          out.push({ x: Math.round(x2 * 100) / 100, y: Math.round(y2 * 100) / 100, rotation: zone2.rotation || 0 });
        }
      }
    }
    return out;
  }
  const b = S.site.building || { length: 60, width: 30 };
  let x = point ? point.x : 1;
  let y = point ? point.y : 1;
  const x0 = x;
  for (let guard3 = 0; guard3 < 4e3 && out.length < n; guard3++) {
    if (free(x, y)) {
      out.push({ x: Math.round(x * 100) / 100, y: Math.round(y * 100) / 100, rotation: 0 });
    }
    x += fl + gap;
    if (x > Math.max(b.length, x0 + 30) - 1) {
      x = x0;
      y += fw + gap;
    }
  }
  return out;
}
function placeFromTray(items, { zoneId = null, point = null } = {}) {
  const ly = layerOf(S.ui.layer);
  const acc = E.access?.();
  if (acc && !acc.design) {
    toast(E.accessHint?.("design") || "Правка недоступна.", "warn");
    return { ok: false, placed: 0, reason: "Немає прав." };
  }
  if (!ly || !canEditLayer(ly)) {
    if (ly) {
      toastLock(ly);
    }
    return { ok: false, placed: 0, reason: "Шар не редагується вами." };
  }
  if (!ly.slot_types.includes("floor_spot")) {
    toast(`Шар «${ly.name}» не допускає місця на підлозі.`, "warn");
    return { ok: false, placed: 0, reason: "Шар не допускає місця на підлозі." };
  }
  const used = new Set(S.slots.map((s) => s.code_prefix));
  const ok = items.filter((t) => PREFIX_RE2.test(t.code) && t.code.length <= 22 && !used.has(t.code));
  const bad = items.length - ok.length;
  if (!ok.length) {
    const why = items.length === 1 ? REASONS[items[0].reason === "dup" ? "dup" : "bad_code"] : "Коди не підходять для місць: великі латинські літери, цифри й дефіси, до 22 символів.";
    toast(why, "warn");
    return { ok: false, placed: 0, reason: why };
  }
  const zone2 = zoneId ? S.sIdx.get(zoneId) : null;
  const pos = freePositions(ly.id, ok.length, { zone: zone2, point });
  const n = Math.min(pos.length, ok.length);
  if (!n) {
    toast(zone2 ? "У зоні немає вільного місця." : "Немає вільного місця.", "warn");
    return { ok: false, placed: 0, reason: "Немає вільного місця." };
  }
  const siteOwn = !!safeNormalize(S.site.addr).tpl;
  E.undoRecord?.();
  ok.slice(0, n).forEach((t, i) => {
    const s = { id: newUid(), rid: null, etag: null, layer_id: ly.id, template: "floor_spot", code_prefix: t.code, x: pos[i].x, y: pos[i].y, rotation: pos[i].rotation, params: { ...SPOT }, overrides: {}, parent_location_id: null };
    if (t.name && t.name !== t.code) {
      s.overrides[t.code] = { name: t.name };
    }
    if (siteOwn) {
      s.addr = { legacy: true };
    }
    S.slots.push(s);
  });
  E.undoLabel?.(`Розміщено з лотка: ${n}`);
  E.commit({});
  updateTabLabel();
  toast(`Розміщено з лотка: ${n}${bad || n < ok.length ? `; не розміщено: ${items.length - n}` : ""}.`, bad || n < ok.length ? "warn" : void 0);
  return { ok: true, placed: n };
}
function openPlaceDialog(items) {
  const ly = layerOf(S.ui.layer);
  const zones = ly ? zonesOnLayer(ly.id) : [];
  let zoneId = zones.find((z) => S.sel && S.sel.id === z.id)?.id || "";
  const opts2 = [["", "Вільне місце шару (поза зонами)"], ...zones.map((z) => [z.id, z.params.title || z.code_prefix])];
  openDialog({
    title: "Розмістити в…",
    cls: "narrow",
    body: h("div", { class: "fcol", id: "trayPlaceBody" }, h("div", { class: "small" }, items.length === 1 ? `Код ${items[0].code}` : `Записів: ${items.length}`), fld("Куди", selectEl(opts2, zoneId, (v) => {
      zoneId = v;
    }, false, "Зона"))),
    actions: [
      { label: "Скасувати", value: "no" },
      { label: "Розмістити", cls: "primary", id: "trayPlaceGo", onClick: () => placeFromTray(items, { zoneId: zoneId || null }).ok ? void 0 : false }
    ]
  });
}
function renderTrayTab(root) {
  const all = trayItems();
  const q = filterText.trim().toLowerCase();
  const list = q ? all.filter((t) => `${t.code} ${t.name} ${t.parent}`.toLowerCase().includes(q)) : all;
  const more = (S.site?.parse_rules || {}).tray_more || 0;
  const input = h("input", { type: "search", value: filterText, placeholder: "Фільтр за кодом чи назвою", "aria-label": "Фільтр лотка", id: "trayFilter" });
  input.addEventListener("input", () => {
    filterText = input.value;
    E.renderLeft();
    $("#trayFilter")?.focus();
  });
  const rows = list.slice(0, SHOWN).map(
    (t) => h(
      "div",
      { class: "tray-row", draggable: "true", "data-code": t.code, title: REASONS[t.reason] || "" },
      h("div", { class: "tray-main" }, h("span", { class: "mono tray-code" }, t.code), t.name && t.name !== t.code ? h("span", { class: "small muted" }, ` ${t.name}`) : null),
      h("div", { class: "small muted" }, REASONS[t.reason] || t.reason || ""),
      h("button", { class: "fbtn sm", type: "button", "data-act": "place", onclick: () => openPlaceDialog([t]) }, "Розмістити в…")
    )
  );
  for (const r of rows) {
    r.addEventListener("dragstart", (e) => {
      e.dataTransfer.setData("text/plain", `f3d-tray:${r.dataset.code}`);
      e.dataTransfer.effectAllowed = "copy";
    });
  }
  root.append(
    h(
      "div",
      { class: "sec", id: "trayBlock" },
      h("h3", null, "Не розміщено"),
      h("div", { class: "small", id: "trayCount" }, all.length ? `Без правила й зони-родителя: ${fmtInt(all.length)}${more ? ` (+${fmtInt(more)} не збережено)` : ""}` : "Усе розміщено."),
      h("div", { class: "small muted" }, "Перетягніть запис на зону чи вільне місце сцени або натисніть «Розмістити в…». Ctrl+Z повертає запис у лоток."),
      h(
        "div",
        { class: "frow wrap" },
        h("button", { class: "fbtn sm", type: "button", id: "trayParse", onclick: () => E.runDialog("parseCodes") }, "Розбір кодів…"),
        h("button", { class: "fbtn sm", type: "button", id: "trayAll", disabled: !list.length, onclick: () => openPlaceDialog(list) }, q ? "Розмістити знайдені…" : "Розмістити всі…"),
        h("button", { class: "fbtn sm danger", type: "button", id: "trayClear", disabled: !all.length, onclick: clearTray }, "Очистити лоток")
      ),
      all.length ? input : null,
      h("div", { class: "tray-list", id: "trayList" }, rows),
      list.length > SHOWN ? h("div", { class: "small muted" }, `Показано ${SHOWN} із ${fmtInt(list.length)}; уточніть фільтр.`) : null
    )
  );
}
async function clearTray() {
  const ok = await E.confirmBox({ title: "Очистити лоток?", text: "Записи лотка буде видалено з проєкту. Локації в Odoo не змінюються; їх можна імпортувати знову.", ok: "Очистити", danger: true });
  if (ok) {
    setTray([]);
    E.renderLeft();
  }
}
registries.panels.add("left:tray", { area: "left", tab: "tray", label: "Лоток", render: renderTrayTab }, { sequence: 22, force: true });
function updateTabLabel() {
  if (typeof document === "undefined") {
    return;
  }
  const n = trayItems().length;
  for (const b of document.querySelectorAll('#ltabs button[data-tab="tray"], #mtabs button[data-mtab="tray"]')) {
    b.textContent = n ? `Лоток (${n > 999 ? "999+" : n})` : "Лоток";
  }
}
var origRenderAll2 = E.renderAll;
if (typeof origRenderAll2 === "function") {
  E.renderAll = function renderAllTray(...a) {
    const r = origRenderAll2.apply(this, a);
    try {
      updateTabLabel();
    } catch (e) {
      console.error("tray label:", e);
    }
    return r;
  };
}
var bound = null;
function onMount2() {
  const cv = V.canvas;
  if (!cv) {
    return;
  }
  const over = (e) => {
    if ([...e.dataTransfer?.types || []].includes("text/plain")) {
      e.preventDefault();
      e.dataTransfer.dropEffect = "copy";
    }
  };
  const drop = (e) => {
    const text = e.dataTransfer?.getData("text/plain") || "";
    if (!text.startsWith("f3d-tray:")) {
      return;
    }
    e.preventDefault();
    const item = trayItems().find((t) => t.code === text.slice(9));
    const p = E.floorPoint?.(e, elevOf(S.ui.layer));
    if (item && p) {
      const z = zoneAt(S.ui.layer, p.x, p.y);
      placeFromTray([item], z ? { zoneId: z.id } : { point: p });
    }
  };
  cv.addEventListener("dragover", over);
  cv.addEventListener("drop", drop);
  bound = () => {
    cv.removeEventListener("dragover", over);
    cv.removeEventListener("drop", drop);
  };
}
E.lifecycle.mount.add(onMount2);
E.lifecycle.unmount.add(() => {
  if (bound) {
    bound();
    bound = null;
  }
});
Object.assign(E, { trayItems, setTray, trayCodes, placeFromTray });

// core/constructor/tabular_core.js
var enc = new TextEncoder();
var u8 = (x) => x instanceof Uint8Array ? x : new Uint8Array(x);
var xmlEsc = (s) => String(s).replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F]/g, "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
var xmlUnesc = (s) => s.replace(/&(#x[0-9a-fA-F]+|#\d+|amp|lt|gt|quot|apos);/g, (_m, e) => {
  if (e[0] === "#") {
    return String.fromCodePoint(e[1] === "x" ? parseInt(e.slice(2), 16) : parseInt(e.slice(1), 10));
  }
  return { amp: "&", lt: "<", gt: ">", quot: '"', apos: "'" }[e];
});
var crcTable = null;
function crc32(bytes) {
  if (!crcTable) {
    crcTable = new Uint32Array(256);
    for (let n = 0; n < 256; n++) {
      let c2 = n;
      for (let k = 0; k < 8; k++) {
        c2 = c2 & 1 ? 3988292384 ^ c2 >>> 1 : c2 >>> 1;
      }
      crcTable[n] = c2 >>> 0;
    }
  }
  let c = 4294967295;
  for (let i = 0; i < bytes.length; i++) {
    c = crcTable[(c ^ bytes[i]) & 255] ^ c >>> 8;
  }
  return (c ^ 4294967295) >>> 0;
}
async function pipe(bytes, stream) {
  const w = stream.writable.getWriter();
  w.write(bytes);
  w.close();
  const chunks = [];
  const r = stream.readable.getReader();
  for (; ; ) {
    const { done, value } = await r.read();
    if (done) {
      break;
    }
    chunks.push(value);
  }
  const out = new Uint8Array(chunks.reduce((n, c) => n + c.length, 0));
  let o = 0;
  for (const c of chunks) {
    out.set(c, o);
    o += c.length;
  }
  return out;
}
var deflateRaw = (b) => pipe(b, new CompressionStream("deflate-raw"));
var inflateRaw = (b) => pipe(b, new DecompressionStream("deflate-raw"));
async function zipFiles(files) {
  const parts = [];
  const central = [];
  let offset = 0;
  const compress = typeof CompressionStream === "function";
  for (const f of files) {
    const name = enc.encode(f.name);
    const data = u8(f.data);
    const crc = crc32(data);
    const body = compress && data.length > 64 ? await deflateRaw(data) : data;
    const method = body === data ? 0 : 8;
    const lh = new DataView(new ArrayBuffer(30));
    lh.setUint32(0, 67324752, true);
    lh.setUint16(4, 20, true);
    lh.setUint16(6, 2048, true);
    lh.setUint16(8, method, true);
    lh.setUint16(10, 0, true);
    lh.setUint16(12, 33, true);
    lh.setUint32(14, crc, true);
    lh.setUint32(18, body.length, true);
    lh.setUint32(22, data.length, true);
    lh.setUint16(26, name.length, true);
    lh.setUint16(28, 0, true);
    parts.push(new Uint8Array(lh.buffer), name, body);
    const ch = new DataView(new ArrayBuffer(46));
    ch.setUint32(0, 33639248, true);
    ch.setUint16(4, 20, true);
    ch.setUint16(6, 20, true);
    ch.setUint16(8, 2048, true);
    ch.setUint16(10, method, true);
    ch.setUint16(12, 0, true);
    ch.setUint16(14, 33, true);
    ch.setUint32(16, crc, true);
    ch.setUint32(20, body.length, true);
    ch.setUint32(24, data.length, true);
    ch.setUint16(28, name.length, true);
    ch.setUint32(42, offset, true);
    central.push(new Uint8Array(ch.buffer), name);
    offset += 30 + name.length + body.length;
  }
  const cdSize = central.reduce((n, c) => n + c.length, 0);
  const end = new DataView(new ArrayBuffer(22));
  end.setUint32(0, 101010256, true);
  end.setUint16(8, files.length, true);
  end.setUint16(10, files.length, true);
  end.setUint32(12, cdSize, true);
  end.setUint32(16, offset, true);
  const all = [...parts, ...central, new Uint8Array(end.buffer)];
  const out = new Uint8Array(all.reduce((n, c) => n + c.length, 0));
  let o = 0;
  for (const c of all) {
    out.set(c, o);
    o += c.length;
  }
  return out;
}
async function unzip(bytes) {
  const b = u8(bytes);
  const dv = new DataView(b.buffer, b.byteOffset, b.byteLength);
  let eocd = -1;
  for (let i = b.length - 22; i >= Math.max(0, b.length - 7e4); i--) {
    if (dv.getUint32(i, true) === 101010256) {
      eocd = i;
      break;
    }
  }
  if (eocd < 0) {
    throw new Error("Файл не схожий на XLSX (немає zip-каталогу).");
  }
  const n = dv.getUint16(eocd + 10, true);
  let p = dv.getUint32(eocd + 16, true);
  const out = /* @__PURE__ */ new Map();
  const dec = new TextDecoder();
  for (let i = 0; i < n; i++) {
    if (dv.getUint32(p, true) !== 33639248) {
      throw new Error("Пошкоджений zip-каталог.");
    }
    const method = dv.getUint16(p + 10, true);
    const csize = dv.getUint32(p + 20, true);
    const nlen = dv.getUint16(p + 28, true);
    const xlen = dv.getUint16(p + 30, true);
    const clen = dv.getUint16(p + 32, true);
    const lho = dv.getUint32(p + 42, true);
    const name = dec.decode(b.subarray(p + 46, p + 46 + nlen));
    p += 46 + nlen + xlen + clen;
    const start = lho + 30 + dv.getUint16(lho + 26, true) + dv.getUint16(lho + 28, true);
    const raw = b.subarray(start, start + csize);
    if (name.endsWith("/")) {
      continue;
    }
    if (method === 0) {
      out.set(name, raw);
    } else if (method === 8) {
      out.set(name, await inflateRaw(raw));
    } else {
      throw new Error(`Непідтримуваний метод стиснення zip: ${method}.`);
    }
  }
  return out;
}
var colName = (i) => {
  let s = "";
  for (let n = i + 1; n > 0; n = Math.floor((n - 1) / 26)) {
    s = String.fromCharCode(65 + (n - 1) % 26) + s;
  }
  return s;
};
var colIndex = (ref2) => {
  let n = 0;
  for (const ch of /^[A-Z]+/.exec(ref2)[0]) {
    n = n * 26 + ch.charCodeAt(0) - 64;
  }
  return n - 1;
};
async function writeXlsx(rows, { sheet = "Локації" } = {}) {
  const name = xmlEsc(String(sheet).replace(/[\\/?*[\]:]/g, " ").slice(0, 31) || "Лист1");
  const body = rows.map((row, r) => {
    const cells = row.map((v, c) => {
      if (v === "" || v == null) {
        return "";
      }
      const ref2 = `${colName(c)}${r + 1}`;
      if (typeof v === "number" && Number.isFinite(v)) {
        return `<c r="${ref2}"><v>${v}</v></c>`;
      }
      if (typeof v === "boolean") {
        return `<c r="${ref2}" t="b"><v>${v ? 1 : 0}</v></c>`;
      }
      return `<c r="${ref2}" t="inlineStr"><is><t xml:space="preserve">${xmlEsc(v)}</t></is></c>`;
    }).join("");
    return `<row r="${r + 1}">${cells}</row>`;
  }).join("");
  const head = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n';
  const files = [
    { name: "[Content_Types].xml", data: enc.encode(`${head}<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>`) },
    { name: "_rels/.rels", data: enc.encode(`${head}<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>`) },
    { name: "xl/workbook.xml", data: enc.encode(`${head}<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="${name}" sheetId="1" r:id="rId1"/></sheets></workbook>`) },
    { name: "xl/_rels/workbook.xml.rels", data: enc.encode(`${head}<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>`) },
    { name: "xl/worksheets/sheet1.xml", data: enc.encode(`${head}<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>${body}</sheetData></worksheet>`) }
  ];
  return await zipFiles(files);
}
var attr = (tag, name) => {
  const m = new RegExp(`\\b${name}="([^"]*)"`).exec(tag);
  return m ? xmlUnesc(m[1]) : null;
};
var textOf = (xml) => [...xml.matchAll(/<t(?:\s[^>]*)?>([\s\S]*?)<\/t>/g)].map((m) => xmlUnesc(m[1])).join("");
async function readXlsx(bytes, { sheet = 0 } = {}) {
  const files = await unzip(bytes);
  const dec = new TextDecoder();
  const get = (n) => files.has(n) ? dec.decode(files.get(n)) : null;
  const wb = get("xl/workbook.xml");
  if (!wb) {
    throw new Error("Файл не схожий на XLSX (немає xl/workbook.xml).");
  }
  const rels = new Map([...(get("xl/_rels/workbook.xml.rels") || "").matchAll(/<Relationship\b[^>]*>/g)].map((m) => [attr(m[0], "Id"), attr(m[0], "Target")]));
  const sheets = [...wb.matchAll(/<sheet\b[^>]*>/g)].map((m) => ({ name: attr(m[0], "name"), rid: attr(m[0], "r:id") }));
  if (!sheets.length) {
    throw new Error("У книзі немає жодного аркуша.");
  }
  const pick = typeof sheet === "number" ? sheets[sheet] : sheets.find((s) => s.name === sheet);
  if (!pick) {
    throw new Error(`Аркуша «${sheet}» немає в книзі.`);
  }
  let target = rels.get(pick.rid) || "worksheets/sheet1.xml";
  target = target.startsWith("/") ? target.slice(1) : `xl/${target}`;
  const xml = get(target);
  if (xml == null) {
    throw new Error(`Немає даних аркуша (${target}).`);
  }
  const sst = (get("xl/sharedStrings.xml") || "").split(/<si\b[^>]*>/).slice(1).map((si) => textOf(si.split("</si>")[0].replace(/<rPh\b[\s\S]*?<\/rPh>/g, "")));
  const rows = [];
  for (const rm of xml.matchAll(/<row\b([^>]*?)(?:\/>|>([\s\S]*?)<\/row>)/g)) {
    const r = parseInt(attr(rm[1], "r") || rows.length + 1, 10) - 1;
    const row = [];
    for (const cm of (rm[2] || "").matchAll(/<c\b([^>]*?)(?:\/>|>([\s\S]*?)<\/c>)/g)) {
      const ref2 = attr(cm[1], "r");
      const idx = ref2 ? colIndex(ref2) : row.length;
      const t = attr(cm[1], "t");
      const inner = cm[2] || "";
      const v = /<v>([\s\S]*?)<\/v>/.exec(inner);
      let val = "";
      if (t === "inlineStr") {
        val = textOf(inner);
      } else if (v) {
        const raw = xmlUnesc(v[1]);
        val = t === "s" ? sst[parseInt(raw, 10)] ?? "" : t === "b" ? raw === "1" : t === "str" || t === "e" ? raw : raw.trim() === "" ? "" : Number(raw);
        if (typeof val === "number" && Number.isNaN(val)) {
          val = raw;
        }
      }
      while (row.length < idx) {
        row.push("");
      }
      row[idx] = val;
    }
    while (rows.length < r) {
      rows.push([]);
    }
    rows[r] = row;
  }
  return { sheets: sheets.map((s) => s.name), sheet: pick.name, rows: trimRows(rows) };
}
function trimRows(rows) {
  const out = rows.map((r) => {
    const a = [...r];
    while (a.length && (a[a.length - 1] === "" || a[a.length - 1] == null)) {
      a.pop();
    }
    return a.map((v) => v == null ? "" : v);
  });
  while (out.length && !out[out.length - 1].length) {
    out.pop();
  }
  const w = Math.max(0, ...out.map((r) => r.length));
  return out.map((r) => [...r, ...Array(w - r.length).fill("")]);
}
function decodeText(bytes) {
  const b = u8(bytes);
  try {
    return { text: new TextDecoder("utf-8", { fatal: true }).decode(b).replace(/^﻿/, ""), encoding: "utf-8" };
  } catch {
    return { text: new TextDecoder("windows-1251").decode(b), encoding: "windows-1251" };
  }
}
function detectDelimiter(text) {
  const first = text.split(/\r\n|\n|\r/, 1)[0] || "";
  let best = ",";
  let max = -1;
  for (const d of [",", ";", "	"]) {
    let n = 0;
    let q = false;
    for (const ch of first) {
      if (ch === '"') {
        q = !q;
      } else if (ch === d && !q) {
        n++;
      }
    }
    if (n > max) {
      max = n;
      best = d;
    }
  }
  return best;
}
function parseCsv(text, delim = detectDelimiter(text)) {
  const rows = [];
  let row = [];
  let cell = "";
  let q = false;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (q) {
      if (ch === '"') {
        if (text[i + 1] === '"') {
          cell += '"';
          i++;
        } else {
          q = false;
        }
      } else {
        cell += ch;
      }
    } else if (ch === '"' && cell === "") {
      q = true;
    } else if (ch === delim) {
      row.push(cell);
      cell = "";
    } else if (ch === "\n" || ch === "\r") {
      if (ch === "\r" && text[i + 1] === "\n") {
        i++;
      }
      row.push(cell);
      rows.push(row);
      row = [];
      cell = "";
    } else {
      cell += ch;
    }
  }
  if (cell !== "" || row.length) {
    row.push(cell);
    rows.push(row);
  }
  return trimRows(rows);
}
function toCsv2(rows, { delim = ",", bom = true } = {}) {
  const cell = (v) => {
    const s = v == null ? "" : String(v);
    return s.includes('"') || s.includes(delim) || /[\r\n]/.test(s) || /^\s|\s$/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  return (bom ? "\uFEFF" : "") + rows.map((r) => r.map(cell).join(delim)).join("\r\n") + "\r\n";
}
async function readTable(bytes, filename = "", { delimiter = null, sheet = 0 } = {}) {
  const b = u8(bytes);
  if (b.length > 3 && b[0] === 80 && b[1] === 75) {
    const x = await readXlsx(b, { sheet });
    return { format: "xlsx", sheets: x.sheets, sheet: x.sheet, rows: x.rows };
  }
  const { text, encoding } = decodeText(b);
  const d = delimiter || detectDelimiter(text);
  return { format: "csv", encoding, delimiter: d, rows: parseCsv(text, d) };
}
var FIELDS = [
  { key: "complete_name", label: "Повна назва локації", aliases: ["full location name", "complete name", "complete_name", "повна назва локації", "повне ім'я локації", "повна назва", "полное название местоположения", "полное имя локации", "полное название"] },
  { key: "name", label: "Назва", aliases: ["location name", "name", "назва локації", "назва", "ім'я", "название местоположения", "название локации", "название", "имя"] },
  { key: "parent", label: "Батьківська локація", aliases: ["parent location", "location_id", "parent", "батьківська локація", "батьківська", "родительское местоположение", "родительская локация", "родитель"] },
  { key: "usage", label: "Тип локації", aliases: ["location type", "usage", "type", "тип локації", "тип", "тип местоположения", "тип локации"] },
  { key: "barcode", label: "Штрихкод", aliases: ["barcode", "штрихкод", "штрих-код", "штрих код"] },
  { key: "posx", label: "Коридор (X)", aliases: ["corridor (x)", "corridor", "posx", "коридор (x)", "коридор"] },
  { key: "posy", label: "Стелажі (Y)", aliases: ["shelves (y)", "shelves", "posy", "стелажі (y)", "стелажі", "стеллажи (y)", "стеллажи"] },
  { key: "posz", label: "Висота (Z)", aliases: ["height (z)", "height", "posz", "висота (z)", "висота", "высота (z)", "высота"] },
  { key: "product", label: "Товар", aliases: ["product", "product/name", "товар", "продукт", "номенклатура"] },
  { key: "qty", label: "Кількість", aliases: ["quantity", "on hand quantity", "qty", "кількість", "залишок", "количество", "остаток"] },
  { key: "lot", label: "Партія", aliases: ["lot/serial number", "lot", "lot/serial", "партія", "серійний номер", "партія/серійний номер", "партия", "серийный номер"] }
];
var normHeader = (s) => String(s ?? "").toLowerCase().replace(/[’`ʼ]/g, "'").replace(/\s+/g, " ").trim();
var ALIAS_OF = new Map(FIELDS.flatMap((f) => f.aliases.map((a) => [a, f.key])));
function autoMap(header) {
  const map = {};
  header.forEach((h2, i) => {
    const key = ALIAS_OF.get(normHeader(h2));
    if (key && !(key in map)) {
      map[key] = i;
    }
  });
  return map;
}
var USAGE_PATTERNS = [
  [/internal|внутр/i, "internal"],
  [/view|вигляд|вид\b|представ|віртуал|виртуал/i, "view"],
  [/customer|клієнт|покупц|клиент|покупат/i, "customer"],
  [/supplier|vendor|постач|поставщ/i, "supplier"],
  [/inventory|інвентар|инвентар/i, "inventory"],
  [/production|виробн|производ/i, "production"],
  [/transit|транзит/i, "transit"]
];
var usageOf = (v) => {
  const s = String(v ?? "").trim();
  if (!s) {
    return "internal";
  }
  const hit = USAGE_PATTERNS.find(([re]) => re.test(s));
  return hit ? hit[1] : s.toLowerCase();
};
var str = (v) => (v == null ? "" : String(v)).trim();
function rowsToLocations(rows, map) {
  const get = (row, key) => key in map ? row[map[key]] : "";
  const byFull = /* @__PURE__ */ new Map();
  const stats = { rows: rows.length, locations: 0, stockRows: 0, skippedEmpty: 0 };
  for (const row of rows) {
    let name = str(get(row, "name"));
    let parent = str(get(row, "parent"));
    const full = str(get(row, "complete_name"));
    if (full) {
      const i = full.lastIndexOf("/");
      name = i < 0 ? full : full.slice(i + 1).trim();
      parent = i < 0 ? parent : full.slice(0, i).trim();
    }
    if (!name) {
      stats.skippedEmpty++;
      continue;
    }
    const key = parent ? `${parent}/${name}` : name;
    let loc = byFull.get(key);
    if (!loc) {
      const barcode = str(get(row, "barcode"));
      loc = { code: barcode || name, name, parent, usage: usageOf(get(row, "usage")), barcode, qty: 0 };
      for (const k of ["posx", "posy", "posz"]) {
        const v = get(row, k);
        if (v !== "" && v != null && !Number.isNaN(Number(v))) {
          loc[k] = Number(v);
        }
      }
      byFull.set(key, loc);
    }
    const q = Number(get(row, "qty"));
    if (str(get(row, "product")) && q > 0) {
      loc.qty += q;
      stats.stockRows++;
    }
  }
  const locs = [...byFull.values()];
  stats.locations = locs.length;
  return { locs, stats };
}
var EXPORT_HEADER = ["name", "location_id", "usage", "barcode", "posx", "posy", "posz"];
function locationsToRows(locs) {
  return [EXPORT_HEADER, ...locs.map((l) => [l.name ?? l.code, l.parent || "", l.usage || "internal", l.barcode || l.code || "", l.posx ?? "", l.posy ?? "", l.posz ?? ""])];
}
function withParents(locs, known = /* @__PURE__ */ new Set()) {
  const have = /* @__PURE__ */ new Set([...known, ...locs.map((l) => l.parent ? `${l.parent}/${l.name}` : l.name)]);
  const out = [];
  const add = (path) => {
    if (!path || have.has(path)) {
      return;
    }
    const i = path.lastIndexOf("/");
    add(i < 0 ? "" : path.slice(0, i));
    have.add(path);
    out.push({ code: "", name: i < 0 ? path : path.slice(i + 1), parent: i < 0 ? "" : path.slice(0, i), usage: "view", barcode: "" });
  };
  for (const l of locs) {
    add(l.parent);
  }
  return [...out, ...locs];
}
var fileName = (base2, ext) => `${String(base2 || "locations").replace(/[^\w.-]+/g, "_")}.${ext}`;

// core/constructor/files_ui.js
var isXlsx = (b) => b.length > 3 && b[0] === 80 && b[1] === 75;
function saveBlob(name, data, mime) {
  const url = URL.createObjectURL(new Blob([data], { type: mime }));
  const a = h("a", { href: url, download: name });
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1500);
}
async function readFileTable(bytes, filename, opts2 = {}) {
  const ad = E.adapter;
  if (isXlsx(bytes) && can("files") && ad && typeof ad.parseTable === "function") {
    try {
      return await ad.parseTable({ filename, bytes, sheet: opts2.sheet ?? 0 });
    } catch (e) {
      console.warn("parseTable (сервер) не вдався, читаю локально:", e);
    }
  }
  return await readTable(bytes, filename, opts2);
}
var feedLoc = (r) => ({ id: r.id ?? null, code: r.code || r.barcode || r.name, name: r.name, parent: r.parent || "", parent_id: r.parent_id ?? null, usage: r.usage || "internal", barcode: r.barcode || "", qty: Number(r.qty) || 0, active: r.active !== false });
function openImport({ file = null } = {}) {
  if (!S.site) {
    return void 0;
  }
  const st = { source: null, label: "", table: null, map: {}, locs: [], stats: null, plan: null, mode: canManage() ? "new" : "current", projName: "", layout: true, extra: [], busy: false, error: "", suggestions: [] };
  const box = h("div", { class: "fcol", id: "impBody" });
  const mapBox = h("div", { class: "fcol", id: "impMap" });
  const sumBox = h("div", { class: "fcol", id: "impSummary" });
  const optBox = h("div", { class: "fcol", id: "impOpts" });
  let goBtn = null;
  const rulesNow = () => [...siteRules().rules, ...st.extra];
  const recompute = () => {
    st.suggestions = [];
    if (st.table) {
      const body = st.table.rows.slice(1);
      const r = rowsToLocations(body, st.map);
      st.locs = r.locs;
      st.stats = r.stats;
    }
    if (!st.locs.length) {
      st.plan = null;
      return;
    }
    const parser = makeParser({ rules: rulesNow(), addr: S.site.addr || null });
    if (st.source !== "odoo") {
      st.warehouses = null;
    }
    st.plan = planStructure(st.locs, { parser, siteAddr: safeNormalize(S.site.addr), depthMode: S.site.depth_mode || "level", existingCodes: projectCodes(), existingPrefixes: new Set(S.slots.map((s) => s.code_prefix)) });
    const un = st.plan.stats.unparsedCodes;
    if (un.length && un.length >= 0.3 * Math.max(1, st.plan.stats.cells)) {
      st.suggestions = guessMasks(un, { limit: 3 });
    }
  };
  const setTable = async (table, label) => {
    st.source = "file";
    st.table = table;
    st.label = label;
    st.map = autoMap(table.rows[0] || []);
    st.projName = st.projName || label.replace(/\.[^.]+$/, "");
    recompute();
    render2();
  };
  const loadFile = async (f) => {
    try {
      const bytes = new Uint8Array(await f.arrayBuffer());
      const table = await readFileTable(bytes, f.name);
      if (!table.rows.length) {
        throw new Error("Файл порожній.");
      }
      st.error = "";
      await setTable(table, f.name);
    } catch (e) {
      st.error = e.message || String(e);
      render2();
    }
  };
  const loadOdoo = async () => {
    try {
      const r = await E.adapter.locations({ op: "feed" });
      st.source = "odoo";
      st.table = null;
      st.label = `Odoo: ${r.feed.warehouse?.name || r.feed.root || "склад"}${r.demo || r.feed.demo ? " (приклад)" : ""}`;
      st.locs = r.feed.locations.map(feedLoc);
      st.stats = { rows: st.locs.length, locations: st.locs.length, stockRows: st.locs.filter((l) => l.qty > 0).length, skippedEmpty: 0 };
      st.projName = st.projName || r.feed.warehouse?.name || "Склад з Odoo";
      st.error = r.feed.truncated ? "Стрічка обрізана: перші " + fmtInt(st.locs.length) + " локацій." : "";
      st.warehouses = r.feed.warehouse ? [r.feed.warehouse.code || r.feed.warehouse.name] : null;
      recompute();
      render2();
    } catch (e) {
      st.error = e.message || String(e);
      render2();
    }
  };
  const render2 = () => {
    const fileIn = h("input", { type: "file", accept: ".csv,.txt,.xlsx,.xls,text/csv", id: "impFile", "aria-label": "Файл імпорту" });
    fileIn.addEventListener("change", () => fileIn.files[0] && loadFile(fileIn.files[0]));
    const drop = h("div", { class: "frow wrap", id: "impSource" }, fileIn, can("odoo_import") ? h("button", { class: "fbtn", type: "button", id: "impOdoo", onclick: loadOdoo }, "Прочитати структуру з Odoo") : null);
    drop.addEventListener("dragover", (e) => e.preventDefault());
    drop.addEventListener("drop", (e) => {
      e.preventDefault();
      e.dataTransfer.files[0] && loadFile(e.dataTransfer.files[0]);
    });
    const header = st.table ? st.table.rows[0] || [] : [];
    mapBox.replaceChildren(
      ...st.table ? [
        h("div", { class: "small muted" }, `Файл: ${st.label} · ${st.table.format === "xlsx" ? `аркуш «${st.table.sheet}»` : `${st.table.encoding}, роздільник ${st.table.delimiter === "	" ? "табуляція" : st.table.delimiter}`} · рядків: ${fmtInt(st.table.rows.length - 1)}`),
        h(
          "div",
          { class: "grid3", id: "impMapGrid" },
          FIELDS.map(
            (f) => fld(f.label, selectEl([["", "— немає —"], ...header.map((x, i) => [String(i), String(x || `Колонка ${i + 1}`)])], f.key in st.map ? String(st.map[f.key]) : "", (v) => {
              v === "" ? delete st.map[f.key] : st.map[f.key] = Number(v);
              recompute();
              renderSummary();
            }, false, f.label))
          )
        )
      ] : []
    );
    box.replaceChildren(drop, st.error ? h("div", { class: "note lock", id: "impError" }, st.error) : null, mapBox, sumBox, optBox);
    renderSummary();
    renderOpts();
  };
  const renderSummary = () => {
    const p = st.plan;
    const need = st.table && !("name" in st.map) && !("complete_name" in st.map);
    sumBox.replaceChildren(
      ...need ? [h("div", { class: "note lock" }, "Вкажіть колонку з назвою локації («Назва» або «Повна назва локації»).")] : p ? [
        h("div", { class: "sumrow" }, h("div", { class: "n", id: "impCells" }, fmtInt(p.stats.cells)), h("div", null, "місць (локацій без вкладених)", h("div", { class: "x" }, `рядків структури: ${fmtInt(p.stats.structure)} · залишків: ${fmtInt(st.stats.stockRows || p.stats.stock_qty)} · складів: ${fmtInt((st.warehouses || p.stats.warehouses).length)}${(st.warehouses || p.stats.warehouses).length ? ` (${(st.warehouses || p.stats.warehouses).slice(0, 4).join(", ")})` : ""}`))),
        p.stats.skipped_usage ? h("div", { class: "small muted" }, `Нескладські типи пропущено: ${fmtInt(p.stats.skipped_usage)}`) : null,
        h("div", { class: "small", id: "impParsed" }, `Буде створено: зон ${fmtInt(p.zones.size)}, рядів ${fmtInt(p.stats.racks)}, місць на підлозі ${fmtInt(p.stats.spots)} · У лоток «Не розміщено»: ${fmtInt(p.tray.length)}${p.stats.known ? ` · уже в проєкті: ${fmtInt(p.stats.known)}` : ""}`),
        ...reasonRows(p),
        ...st.suggestions.map((g3) => h("div", { class: "frow", "data-role": "suggest" }, h("span", { class: "small" }, "Підібрано маску:"), h("span", { class: "mono" }, g3.mask), h("span", { class: "muted small" }, `${g3.matched} із ${g3.total} нерозібраних`), h("button", { class: "fbtn sm", type: "button", "data-mask": g3.mask, onclick: () => {
          st.extra.push({ id: `s${st.extra.length + 1}`, mode: "mask", mask: g3.mask, type: "auto", enabled: true });
          recompute();
          renderSummary();
        } }, "Застосувати"))),
        st.extra.length ? h("div", { class: "small muted" }, `Додані правила (збережуться з імпортом): ${st.extra.map((r) => r.mask).join(" · ")}`) : null
      ] : [h("div", { class: "small muted" }, "Оберіть файл CSV чи XLSX або прочитайте структуру складу з Odoo.")]
    );
    if (goBtn) {
      goBtn.disabled = !p || st.busy || need || !(p.slots.length || p.tray.length);
    }
  };
  const reasonRows = (p) => {
    const by = {};
    for (const t of p.tray) {
      (by[t.reason] ||= []).push(t.code);
    }
    return Object.entries(by).map(([k, codes]) => h("div", { class: "small muted", "data-role": "reason", "data-reason": k }, `${fmtInt(codes.length)} — ${REASONS[k] || k}: ${codes.slice(0, 3).join(", ")}${codes.length > 3 ? " …" : ""}`));
  };
  const renderOpts = () => {
    const mgr = canManage();
    optBox.replaceChildren(
      h(
        "div",
        { class: "fcol" },
        h("label", { class: "frow" }, h("input", { type: "radio", name: "impMode", id: "impNew", checked: st.mode === "new", disabled: !mgr, onchange: () => {
          st.mode = "new";
          renderOpts();
        } }), "Створити новий проєкт «з файлу»", mgr ? null : h("span", { class: "small muted" }, " (лише менеджер)")),
        st.mode === "new" ? fld("Назва проєкту", h("input", { type: "text", id: "impName", value: st.projName, "aria-label": "Назва проєкту", oninput: (e) => {
          st.projName = e.target.value;
        } })) : null,
        h("label", { class: "frow" }, h("input", { type: "radio", name: "impMode", id: "impCurrent", checked: st.mode === "current", onchange: () => {
          st.mode = "current";
          renderOpts();
        } }), `Додати в поточний проєкт «${S.site.name}»`),
        h("label", { class: "frow" }, h("input", { type: "checkbox", id: "impLayout", checked: st.layout, onchange: (e) => {
          st.layout = e.target.checked;
        } }), "Розкласти автоматично (зони по горизонталі, ряди вглиб)"),
        h("div", { class: "frow" }, h("button", { class: "fbtn sm", type: "button", id: "impRules", onclick: () => E.runDialog("parseCodes", { items: st.locs.map((l) => l.code) }) }, "Правила розбору…"))
      )
    );
  };
  const apply = async () => {
    if (!st.plan || st.busy) {
      return false;
    }
    st.busy = true;
    goBtn.disabled = true;
    try {
      const rules = normalizeRules({ rules: rulesNow() }).rules;
      let res;
      if (st.mode === "new") {
        const code = `IMP${Date.now().toString(36).toUpperCase().slice(-9)}`;
        if (!await E.createSite({ name: st.projName.trim() || "Імпорт", code })) {
          return false;
        }
        S.site.parse_rules = normalizeRules({ rules });
        res = E.importLocations(st.locs, { label: "Імпорт структури", layout: st.layout, growBuilding: true, parseRules: rules });
        await saveRules(S.site.parse_rules);
      } else {
        if (st.extra.length) {
          await saveRules(normalizeRules({ ...S.site.parse_rules || {}, rules }));
        }
        res = E.importLocations(st.locs, { label: "Імпорт структури", layout: st.layout, parseRules: rules });
      }
      if (!res.ok) {
        toast(res.reason || "Імпорт не виконано.", "warn");
        return false;
      }
      toast(`Імпортовано: зон ${res.zones}, рядів і місць ${res.slots}, комірок ${fmtInt(res.cells)}${res.tray ? `; у лоток «Не розміщено»: ${fmtInt(res.tray)}` : ""}.`);
      E.setLeftTab?.(res.tray && !res.slots ? "tray" : S.ui.leftTab);
      return true;
    } catch (e) {
      toast(e.message || "Не вдалося імпортувати.", "err");
      return false;
    } finally {
      st.busy = false;
    }
  };
  render2();
  const dlg = openDialog({
    title: "Імпорт локацій",
    cls: "wide",
    body: box,
    actions: [
      { label: "Скасувати", value: "no" },
      { label: "Імпортувати", cls: "primary", id: "impGo", disabled: true, onClick: async () => await apply() ? void 0 : false }
    ]
  });
  goBtn = dlg.querySelector("#impGo");
  renderSummary();
  if (file) {
    loadFile(file);
  }
  return dlg;
}
var projectRoot = () => S.site.default_parent_location?.name || E.adapter?.defaultParent || "Склад";
function projectLocations({ zones = false } = {}) {
  const root = projectRoot();
  const parser = makeParser({ rules: siteRules().rules, addr: S.site.addr || null });
  const zs = zones ? S.slots.filter((s) => s.template === "zone" && slotPolygon(s)).map((z) => ({ title: z.params.title || z.code_prefix, poly: slotPolygon(z), area: (z.params.length || 1) * (z.params.width || 1), layer: z.layer_id })) : [];
  const out = [];
  for (const s of S.slots) {
    const host2 = zs.filter((z) => z.layer === s.layer_id && polygonContains(z.poly, [s.x, s.y])).sort((a, b) => a.area - b.area)[0];
    for (const c of cellsOf(s)) {
      if (c.disabled) {
        continue;
      }
      const r = parser.parse(c.code);
      const loc = { code: c.code, name: c.name || c.code, parent: host2 ? `${root}/${host2.title}` : root, usage: c.usage && c.usage !== "internal" ? c.usage : "internal", barcode: c.code };
      if (r) {
        Object.assign(loc, typeof r.parts.row === "number" ? { posx: r.parts.row } : {}, r.parts.bay != null ? { posy: r.parts.bay } : {}, r.parts.level != null ? { posz: r.parts.level } : {});
      }
      out.push(loc);
    }
  }
  return out;
}
function changedLocations(all, feed) {
  const byCode = new Map(feed.map((l) => [l.code, l]));
  const changed = all.filter((l) => {
    const f = byCode.get(l.code);
    return !f || f.name !== l.name;
  });
  return withParents(changed, new Set(feed.map(fullName)));
}
function openExport() {
  if (!S.site) {
    return void 0;
  }
  const st = { scope: "all", format: "xlsx", zones: false };
  const info = h("div", { class: "small muted", id: "expInfo" });
  info.textContent = `Місць у проєкті: ${fmtInt(S.slots.reduce((n, sl) => n + cellsOf(sl).filter((c) => !c.disabled).length, 0))}.`;
  const body = h(
    "div",
    { class: "fcol", id: "expBody" },
    fld("Що експортувати", selectEl([["all", "Усі місця"], ...can("odoo_import") ? [["changed", "Нові й змінені відносно Odoo (з недостаючими батьками)"]] : []], st.scope, (v) => {
      st.scope = v;
    }, false, "Що експортувати")),
    fld("Формат", selectEl([["xlsx", "XLSX"], ["csv", "CSV (UTF-8, кома)"]], st.format, (v) => {
      st.format = v;
    }, false, "Формат")),
    h("label", { class: "frow" }, h("input", { type: "checkbox", id: "expZones", onchange: (e) => {
      st.zones = e.target.checked;
    } }), "Зони як батьківські локації (для перенесення структури в інший проєкт)"),
    info,
    h("div", { class: "small muted" }, "Формат імпорту Odoo: name, location_id (повне ім'я батька), usage, barcode, posx/posy/posz. Файл створюється в браузері й нікуди не надсилається.")
  );
  openDialog({
    title: "Експорт локацій",
    cls: "narrow",
    body,
    actions: [
      { label: "Скасувати", value: "no" },
      {
        label: "Завантажити",
        cls: "primary",
        id: "expGo",
        onClick: async () => {
          try {
            let locs = projectLocations({ zones: st.zones });
            if (st.scope === "changed") {
              const r = await E.adapter.locations({ op: "feed" });
              locs = changedLocations(locs, r.feed.locations.map(feedLoc));
            } else if (st.zones) {
              locs = withParents(locs, /* @__PURE__ */ new Set([projectRoot()]));
            }
            const rows = locationsToRows(locs);
            const base2 = S.site.code || S.site.name;
            if (st.format === "csv") {
              saveBlob(fileName(base2, "csv"), toCsv2(rows), "text/csv;charset=utf-8");
            } else {
              saveBlob(fileName(base2, "xlsx"), await writeXlsx(rows, { sheet: "Локації" }), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet");
            }
            toast(`Файл створено: ${fmtInt(rows.length - 1)} рядків.`);
          } catch (e) {
            toast(e.message || "Не вдалося створити файл.", "err");
            return false;
          }
        }
      }
    ]
  });
}
registries.dialogs.add("importLocations", (args) => openImport(args || {}), { force: true });
registries.dialogs.add("exportLocations", () => openExport(), { force: true });
var design = () => !S.site || (E.access ? !E.access().design : false);
registries.menu.add("importLocations", { area: "more", label: "Імпорт локацій…", icon: "plus", sequence: 56, run: () => E.runDialog("importLocations"), disabled: design }, { sequence: 56, force: true });
registries.menu.add("exportLocations", { area: "more", label: "Експорт локацій…", icon: "tag", sequence: 57, run: () => E.runDialog("exportLocations"), disabled: () => !S.site }, { sequence: 57, force: true });
Object.assign(E, { openImport, openExport, readFileTable });

// core/constructor/sync_ui.js
var GROUPS2 = [
  ["appeared", "З'явилося в Odoo", "піде в лоток «Не розміщено»"],
  ["disappeared", "Зникло в Odoo (архів чи видалення)", "комірку вимкнено в моделі"],
  ["renamed", "Перейменовано в Odoo", "назва комірки оновиться"],
  ["moved", "Інший батько в Odoo", "батька запам'ятовано для місця на підлозі"]
];
var ownerOf = (code) => S.slots.find((s) => s.template !== "zone" && cellsOf(s).some((c) => c.code === code));
function relevantDiff(diff, have = projectCodes(), trayCodes2 = new Set(E.trayItems?.().map((t) => t.code) || [])) {
  const known = (c) => have.has(c) || trayCodes2.has(c);
  return {
    appeared: (diff.appeared || []).map(feedLoc).filter((l) => l.usage === "internal" && !known(l.code)),
    disappeared: (diff.disappeared || []).filter((l) => known(l.code || l.name)).map((l) => ({ ...feedLoc(l) })),
    renamed: (diff.renamed || []).filter((r) => known(r.code)),
    moved: (diff.moved || []).filter((r) => known(r.code))
  };
}
function applyAccepted(items) {
  const tray = [...S.site.parse_rules?.tray || []];
  const stored = new Set(tray.map((t) => t.code));
  let changed = 0;
  E.undoRecord?.();
  const drop = /* @__PURE__ */ new Set();
  for (const { group, item } of items) {
    if (group === "appeared") {
      if (!stored.has(item.code)) {
        tray.push({ code: item.code, name: item.name, parent: item.parent, usage: item.usage, reason: "new_in_odoo" });
        stored.add(item.code);
      }
    } else if (group === "disappeared") {
      const code = item.code;
      const s = ownerOf(code);
      drop.add(code);
      if (s) {
        if (s.template === "floor_spot" || cellsOf(s).filter((c) => !c.disabled).length <= 1) {
          S.slots.splice(S.slots.indexOf(s), 1);
        } else {
          s.overrides = { ...s.overrides || {}, [code]: { ...(s.overrides || {})[code] || {}, disabled: true } };
        }
        changed++;
      }
    } else if (group === "renamed") {
      const s = ownerOf(item.code);
      if (s) {
        s.overrides = { ...s.overrides || {}, [item.code]: { ...(s.overrides || {})[item.code] || {}, name: item.new } };
        changed++;
      }
      const t = tray.find((x) => x.code === item.code);
      if (t) {
        t.name = item.new;
      }
    } else if (group === "moved") {
      const s = ownerOf(item.code);
      if (s && s.template === "floor_spot" && item.new_parent_id) {
        s.parent_location_id = item.new_parent_id;
        changed++;
      }
    }
  }
  E.setTray?.(tray.filter((t) => !drop.has(t.code)));
  if (changed) {
    E.undoLabel?.("Оновлення з Odoo");
    E.commit({});
  } else {
    E.renderLeft?.();
  }
  return { slots: changed, tray: tray.length };
}
async function openSync() {
  const ad = E.adapter;
  if (!S.site || !ad || typeof ad.locations !== "function") {
    return void 0;
  }
  let r;
  try {
    r = await ad.locations({ op: "sync" });
  } catch (e) {
    toast(e.message || "Не вдалося прочитати структуру з Odoo.", "err");
    return void 0;
  }
  const diff = relevantDiff(r.diff || {});
  const total = GROUPS2.reduce((n, [k]) => n + diff[k].length, 0);
  if (!total) {
    await ad.locations({ op: "baseline" });
    toast(r.baseline === "created" ? "Базу порівняння з Odoo створено." : "Розбіжностей з Odoo немає.");
    return void 0;
  }
  const pick = /* @__PURE__ */ new Map();
  const keyOf = (g3, i) => `${g3}:${i}`;
  for (const [g3] of GROUPS2) {
    diff[g3].forEach((_x, i) => pick.set(keyOf(g3, i), "odoo"));
  }
  const list = h("div", { class: "fcol", id: "syncList" });
  const sum = h("div", { class: "small muted", id: "syncSum" });
  const draw = () => {
    sum.textContent = `Прийняти з Odoo: ${[...pick.values()].filter((v) => v === "odoo").length} із ${total}`;
    list.replaceChildren(
      ...GROUPS2.filter(([g3]) => diff[g3].length).flatMap(([g3, title, hint]) => [
        h("h4", { style: { margin: "8px 0 2px" } }, `${title}: ${fmtInt(diff[g3].length)}`, h("span", { class: "small muted" }, ` — ${hint}`)),
        ...diff[g3].slice(0, 200).map((it, i) => {
          const k = keyOf(g3, i);
          const text = g3 === "renamed" ? `${it.code}: «${it.old}» → «${it.new}»` : g3 === "moved" ? `${it.code}: ${it.old_parent} → ${it.new_parent}` : `${it.code}${it.name && it.name !== it.code ? ` — ${it.name}` : ""}`;
          const sel = h("select", { "aria-label": text, "data-key": k }, h("option", { value: "odoo", selected: pick.get(k) === "odoo" }, "Прийняти з Odoo"), h("option", { value: "mine", selected: pick.get(k) === "mine" }, "Залишити моє"));
          sel.addEventListener("change", () => {
            pick.set(k, sel.value);
            sum.textContent = `Прийняти з Odoo: ${[...pick.values()].filter((v) => v === "odoo").length} із ${total}`;
          });
          return h("div", { class: "frow", "data-group": g3 }, h("span", { class: "mono small", style: { flex: 1 } }, text), sel);
        }),
        diff[g3].length > 200 ? h("div", { class: "small muted" }, `Показано 200 із ${diff[g3].length}; «Прийняти все» діє на всі.`) : null
      ])
    );
  };
  draw();
  const setAll = (v) => {
    for (const k of pick.keys()) {
      pick.set(k, v);
    }
    draw();
  };
  return new Promise((resolve) => {
    openDialog({
      title: "Розбіжності з Odoo",
      cls: "wide",
      body: h("div", { class: "fcol", id: "syncBody" }, h("div", { class: "small" }, "Після «Оновити з Odoo» знайдено зміни, зроблені в Odoo поза конструктором. Ваші правки моделі не зачіпаються, доки не вибрано «Прийняти з Odoo»."), h("div", { class: "frow" }, h("button", { class: "fbtn sm", type: "button", id: "syncAllOdoo", onclick: () => setAll("odoo") }, "Прийняти все з Odoo"), h("button", { class: "fbtn sm", type: "button", id: "syncAllMine", onclick: () => setAll("mine") }, "Залишити все моє")), list, sum),
      onClose: () => resolve(null),
      actions: [
        { label: "Пізніше", value: "no" },
        {
          label: "Застосувати вибір",
          cls: "primary",
          id: "syncApply",
          onClick: async () => {
            const items = [];
            for (const [g3] of GROUPS2) {
              diff[g3].forEach((item, i) => pick.get(keyOf(g3, i)) === "odoo" && items.push({ group: g3, item }));
            }
            try {
              const res = applyAccepted(items);
              await ad.locations({ op: "baseline" });
              toast(`Прийнято з Odoo: ${items.length}; змінено місць: ${res.slots}.`);
              resolve(res);
            } catch (e) {
              toast(e.message || "Не вдалося застосувати.", "err");
              return false;
            }
          }
        }
      ]
    });
  });
}
registries.dialogs.add("syncOdoo", () => openSync(), { force: true });
registries.menu.add("syncOdoo", { area: "more", label: "Оновити з Odoo", icon: "hist", capability: "odoo_import", sequence: 58, run: () => E.runDialog("syncOdoo"), disabled: () => !S.site || !can("odoo_import") }, { sequence: 58, force: true });
Object.assign(E, { openSync, applySyncChoices: applyAccepted });
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
