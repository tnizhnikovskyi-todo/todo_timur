'use strict';
/* ===== утиліти ===== */
for (const m of ['replaceChildren', 'append', 'prepend']) {
  const orig = Element.prototype[m];
  Element.prototype[m] = function (...k) { return orig.apply(this, k.flat(Infinity).filter((x) => x != null && x !== false)); };
}
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
function h(tag, attrs, ...kids) {
  const el = document.createElement(tag);
  let val;
  if (attrs) for (const k in attrs) {
    const v = attrs[k];
    if (v == null || v === false) continue;
    if (k === 'class') el.className = v;
    else if (k === 'style' && typeof v === 'object') Object.assign(el.style, v);
    else if (k.startsWith('on') && typeof v === 'function') el.addEventListener(k.slice(2), v);
    else if (k === 'value') val = v;
    else if (k === 'checked' || k === 'disabled' || k === 'selected' || k === 'hidden' || k === 'indeterminate') el[k] = !!v;
    else if (k === 'html') el.innerHTML = v;
    else el.setAttribute(k, v === true ? '' : v);
  }
  for (const c of kids.flat(Infinity)) {
    if (c == null || c === false) continue;
    el.append(c.nodeType ? c : document.createTextNode(String(c)));
  }
  if (val !== undefined) el.value = val;
  return el;
}
const ic = (n) => h('span', { class: 'ic', 'aria-hidden': 'true', html: `<svg><use href="#i-${n}"/></svg>` });
const uid = (p) => p + Math.random().toString(36).slice(2, 7) + Date.now().toString(36).slice(-3);
const clone = (o) => JSON.parse(JSON.stringify(o));
const rnd = (v, d = 3) => { const k = Math.pow(10, d); const r = Math.round(v * k) / k; return r === 0 ? 0 : r; };
const fmt = (n, d = 1) => { if (n == null || !isFinite(n)) return '—'; const s = Number(n).toFixed(d); return (s === '-0' || /^-0\.0+$/.test(s) ? s.slice(1) : s).replace('.', ','); };
const fmtInt = (n) => Math.round(n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
const rad = (a) => a * Math.PI / 180;
const pad2 = (n) => String(n).padStart(2, '0');
const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
const debounce = (fn, ms) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const getp = (o, path) => path.split('.').reduce((a, k) => (a == null ? a : a[k]), o);
const setp = (o, path, v) => { const ks = path.split('.'); let a = o; while (ks.length > 1) { const k = ks.shift(); a = a[k] = a[k] || {}; } a[ks[0]] = v; };
const normDeg = (a) => ((a % 360) + 360) % 360;
const fmtDate = (iso) => { try { return new Date(iso).toLocaleString('uk-UA', { dateStyle: 'short', timeStyle: 'short' }); } catch (e) { return iso; } };
const fmtSize = (b) => (b >= 1048576 ? fmt(b / 1048576, 1) + ' МБ' : b >= 1024 ? fmt(b / 1024, 0) + ' КБ' : b + ' Б');
function toast(msg, kind) {
  const box = $('#toast');
  const t = h('div', { class: 'toast' + (kind ? ' ' + kind : '') }, msg);
  box.append(t);
  while (box.children.length > 3) box.firstChild.remove();
  setTimeout(() => t.remove(), kind === 'err' || kind === 'warn' ? 5200 : 3200);
  return t;
}
