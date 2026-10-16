// Шрифт для PDF (W-19, I-07): разбор TrueType, подмножество (только используемые знаки) и объекты шрифта для PDF. Без зависимостей и без DOM.
// Сам шрифт — DejaVu Sans Mono (свободная лицензия), заранее урезанный до латиницы и кириллицы (`pdffont-data.js`, чанк грузится при первой записи PDF с кириллицей
// или документа). Моноширинный: ширина знака везде 0,602 em, поэтому раскладка этикеток (core/labels.js, CH = 0,6) остаётся верной.
// В PDF шрифт встраивается как CIDFontType2 (Identity-H, номера глифов): в файл попадают только глифы текста документа, плюс ToUnicode — текст извлекается и ищется.

const dvOf = (u8) => new DataView(u8.buffer, u8.byteOffset, u8.byteLength);
const concat = (parts) => { const out = new Uint8Array(parts.reduce((a, p) => a + p.length, 0)); let o = 0; for (const p of parts) { out.set(p, o); o += p.length; } return out; };
const pad4 = (n) => (n + 3) & ~3;

// ---------- разбор
export function parseTtf(bytes) {
  const dv = dvOf(bytes), n = dv.getUint16(4), tab = {};
  for (let i = 0; i < n; i++) { const o = 12 + 16 * i; tab[String.fromCharCode(bytes[o], bytes[o + 1], bytes[o + 2], bytes[o + 3])] = { off: dv.getUint32(o + 8), len: dv.getUint32(o + 12) }; }
  const T = (t) => (tab[t] ? bytes.subarray(tab[t].off, tab[t].off + tab[t].len) : null);
  const head = T("head"), maxp = T("maxp"), hhea = T("hhea"), hmtx = T("hmtx"), loca = T("loca"), glyf = T("glyf");
  if (!head || !maxp || !hhea || !hmtx || !loca || !glyf) throw new Error("ttf: missing tables");
  const hd = dvOf(head), upem = hd.getUint16(18), long = hd.getInt16(50) === 1, numGlyphs = dvOf(maxp).getUint16(4), hh = dvOf(hhea), nHM = hh.getUint16(34), ld = dvOf(loca), hm = dvOf(hmtx);
  const off = (g) => (long ? ld.getUint32(g * 4) : ld.getUint16(g * 2) * 2);
  const glyph = (g) => glyf.subarray(off(g), off(g + 1));
  const metric = (g) => (g < nHM ? { aw: hm.getUint16(g * 4), lsb: hm.getInt16(g * 4 + 2) } : { aw: hm.getUint16((nHM - 1) * 4), lsb: hm.getInt16(nHM * 4 + (g - nHM) * 2) });
  // cmap: формат 12, иначе 4
  const cmap = new Map(), ct = T("cmap");
  if (ct) {
    const cd = dvOf(ct), subs = [];
    for (let i = 0; i < cd.getUint16(2); i++) { const pid = cd.getUint16(4 + 8 * i), eid = cd.getUint16(6 + 8 * i), o = cd.getUint32(8 + 8 * i); subs.push({ pid, eid, o, fmt: cd.getUint16(o) }); }
    const s = subs.find((x) => x.fmt === 12 && (x.pid === 3 || x.pid === 0)) || subs.find((x) => x.fmt === 4 && x.pid === 3 && x.eid === 1) || subs.find((x) => x.fmt === 4);
    if (s && s.fmt === 12) {
      for (let i = 0, ng = cd.getUint32(s.o + 12); i < ng; i++) { const p = s.o + 16 + 12 * i, a = cd.getUint32(p), b = cd.getUint32(p + 4), g0 = cd.getUint32(p + 8); for (let c = a; c <= b; c++) cmap.set(c, g0 + c - a); }
    } else if (s) {
      const seg = cd.getUint16(s.o + 6) / 2, endO = s.o + 14, startO = endO + seg * 2 + 2, deltaO = startO + seg * 2, rangeO = deltaO + seg * 2;
      for (let i = 0; i < seg; i++) {
        const end = cd.getUint16(endO + 2 * i), start = cd.getUint16(startO + 2 * i), delta = cd.getUint16(deltaO + 2 * i), ro = cd.getUint16(rangeO + 2 * i);
        for (let c = start; c <= end && c < 0xffff; c++) {
          let g = ro === 0 ? (c + delta) & 0xffff : cd.getUint16(rangeO + 2 * i + ro + 2 * (c - start));
          if (ro !== 0 && g) g = (g + delta) & 0xffff;
          if (g) cmap.set(c, g);
        }
      }
    }
  }
  const os2 = T("OS/2");
  return { bytes, tab, T, upem, numGlyphs, nHM, glyph, metric, cmap, bbox: [hd.getInt16(36), hd.getInt16(38), hd.getInt16(40), hd.getInt16(42)],
    ascent: hh.getInt16(4), descent: hh.getInt16(6), capHeight: os2 && os2.length >= 90 ? dvOf(os2).getInt16(88) : hh.getInt16(4) };
}

// составной глифу нужны глифы-компоненты: [позиция поля, номер]
function components(g) {
  const out = [];
  if (g.length < 10) return out;
  const d = dvOf(g);
  if (d.getInt16(0) >= 0) return out;
  let p = 10;
  for (;;) {
    const flags = d.getUint16(p); out.push([p + 2, d.getUint16(p + 2)]); p += 4 + (flags & 1 ? 4 : 2);
    if (flags & 8) p += 2; else if (flags & 0x40) p += 4; else if (flags & 0x80) p += 8;
    if (!(flags & 0x20)) break;
  }
  return out;
}

// ---------- подмножество
// gids — нужные номера глифов (0 добавляется сам). renumber: false — номера прежние, лишние глифы пустые (для PDF: номера из cmap исходного шрифта);
// true — глифы идут подряд (файл шрифта в репозитории); cmap — Map(код знака → прежний номер) для таблицы cmap подмножества (нужна только при renumber).
export function subsetTtf(font, gids, { renumber = false, cmap = null } = {}) {
  const keep = new Set([0]);
  const add = (g) => { if (keep.has(g) || g >= font.numGlyphs) return; keep.add(g); for (const [, c] of components(font.glyph(g))) add(c); };
  for (const g of gids) add(g);
  const list = renumber ? [...keep].sort((a, b) => a - b) : Array.from({ length: font.numGlyphs }, (_, i) => i), map = new Map(list.map((g, i) => [g, i])), N = list.length;
  const glyf = [], loca = new Uint8Array(4 * (N + 1)), ldv = dvOf(loca), hmtx = new Uint8Array(4 * N), hdv = dvOf(hmtx);
  let o = 0;
  list.forEach((g, i) => {
    ldv.setUint32(i * 4, o);
    let data = keep.has(g) ? font.glyph(g) : new Uint8Array(0);
    if (renumber && data.length) { data = data.slice(); const dd = dvOf(data); for (const [p, c] of components(data)) dd.setUint16(p, map.get(c)); }
    const m = keep.has(g) ? font.metric(g) : { aw: 0, lsb: 0 };
    hdv.setUint16(i * 4, m.aw); hdv.setInt16(i * 4 + 2, m.lsb);
    const padded = new Uint8Array(pad4(data.length)); padded.set(data); glyf.push(padded); o += padded.length;
  });
  ldv.setUint32(N * 4, o);
  const copy = (t) => font.T(t).slice(), head = copy("head"), hhea = copy("hhea"), maxp = copy("maxp");
  dvOf(head).setUint32(8, 0); dvOf(head).setInt16(50, 1); dvOf(hhea).setUint16(34, N); dvOf(maxp).setUint16(4, N);
  const tables = { glyf: concat(glyf), loca, hmtx, head, hhea, maxp };
  for (const t of ["cvt ", "fpgm", "prep"]) if (font.T(t)) tables[t] = font.T(t);
  if (cmap) tables.cmap = buildCmap([...cmap].filter(([c, g]) => c < 0xffff && map.has(g)).map(([c, g]) => [c, map.get(g)]).sort((a, b) => a[0] - b[0]));
  return assemble(tables);
}

function buildCmap(pairs) {
  const segs = [];
  for (const [c, g] of pairs) { const s = segs[segs.length - 1]; if (s && c === s.end + 1 && g === s.g0 + (c - s.start)) s.end = c; else segs.push({ start: c, end: c, g0: g }); }
  segs.push({ start: 0xffff, end: 0xffff, g0: 0, last: true });
  const n = segs.length, len = 16 + 8 * n, out = new Uint8Array(12 + len), d = dvOf(out);
  d.setUint16(2, 1); d.setUint16(4, 3); d.setUint16(6, 1); d.setUint32(8, 12);
  const base = 12, e = Math.floor(Math.log2(n)), sr = 2 * 2 ** e;
  d.setUint16(base, 4); d.setUint16(base + 2, len); d.setUint16(base + 6, 2 * n); d.setUint16(base + 8, sr); d.setUint16(base + 10, e); d.setUint16(base + 12, 2 * n - sr);
  segs.forEach((s, i) => {
    d.setUint16(base + 14 + 2 * i, s.end); d.setUint16(base + 16 + 2 * n + 2 * i, s.start);
    d.setUint16(base + 16 + 4 * n + 2 * i, s.last ? 1 : (s.g0 - s.start) & 0xffff);
  });
  return out;
}

const sum32 = (u8) => { const d = dvOf(u8.length % 4 ? concat([u8, new Uint8Array(4 - (u8.length % 4))]) : u8); let s = 0; for (let i = 0; i < d.byteLength; i += 4) s = (s + d.getUint32(i)) >>> 0; return s; };
function assemble(tables) {
  const tags = Object.keys(tables).sort(), n = tags.length, e = Math.floor(Math.log2(n)), dirLen = 12 + 16 * n;
  let off = dirLen; const dir = new Uint8Array(dirLen), dd = dvOf(dir), body = [];
  dd.setUint32(0, 0x00010000); dd.setUint16(4, n); dd.setUint16(6, 16 * 2 ** e); dd.setUint16(8, e); dd.setUint16(10, 16 * n - 16 * 2 ** e);
  let headOff = 0;
  tags.forEach((t, i) => {
    const u = tables[t], p = 12 + 16 * i;
    for (let k = 0; k < 4; k++) dir[p + k] = t.charCodeAt(k);
    dd.setUint32(p + 4, sum32(u)); dd.setUint32(p + 8, off); dd.setUint32(p + 12, u.length);
    if (t === "head") headOff = off;
    const pd = new Uint8Array(pad4(u.length)); pd.set(u); body.push(pd); off += pd.length;
  });
  const out = concat([dir, ...body]);
  dvOf(out).setUint32(headOff + 8, (0xb1b0afba - sum32(out)) >>> 0);
  return out;
}

// ---------- шрифт документа
// createFont(байты шрифта) → состояние одного шрифта в одном PDF: enc() переводит текст в 16-битные номера глифов (hex-строка PDF) и запоминает использованные знаки.
export function createFont(bytes, { name = "DejaVuSansMono", tag = "AAAAAA", bold = false } = {}) {
  const f = parseTtf(bytes), used = new Map(), q = f.cmap.get(63) ?? 0, k = 1000 / f.upem;
  const gidOf = (cp) => { const g = f.cmap.get(cp); return g == null ? (cp === 0xa0 ? f.cmap.get(32) ?? q : cp === 0x2026 || cp === 0x2011 ? f.cmap.get(cp === 0x2011 ? 45 : 46) ?? q : q) : g; };
  const cps = (s) => [...String(s ?? "")].map((c) => c.codePointAt(0)).filter((c) => c >= 32 && c !== 127);
  const api = {
    embedded: true, bold, name, tag, face: `${tag}+${name}`,
    has: (cp) => f.cmap.has(cp),
    // hex-строка текста: <0041…>
    enc(s) {
      let h = "";
      for (const c of cps(s)) { const g = gidOf(c); if (!used.has(g)) used.set(g, c); h += g.toString(16).padStart(4, "0"); }
      return `<${h}>`;
    },
    // ширина строки при кегле size (в единицах size)
    width(s, size) { let w = 0; for (const c of cps(s)) w += f.metric(gidOf(c)).aw * k; return (w * size) / 1000; },
    // содержимое для PDF: подмножество шрифта, ширины глифов, ToUnicode
    build() {
      const gids = [...used.keys()].sort((a, b) => a - b), ttf = subsetTtf(f, gids, { renumber: false });
      const W = gids.map((g) => `${g} [${Math.round(f.metric(g).aw * k)}]`).join(" ");
      const hex4 = (c) => (c > 0xffff ? String.fromCharCode(0xd800 + ((c - 0x10000) >> 10), 0xdc00 + ((c - 0x10000) & 0x3ff)).split("").map((x) => x.charCodeAt(0).toString(16).padStart(4, "0")).join("") : c.toString(16).padStart(4, "0"));
      const entries = gids.filter((g) => g !== 0).map((g) => `<${g.toString(16).padStart(4, "0")}> <${hex4(used.get(g))}>`), chunks = [];
      for (let i = 0; i < entries.length; i += 100) chunks.push(`${Math.min(100, entries.length - i)} beginbfchar\n${entries.slice(i, i + 100).join("\n")}\nendbfchar`);
      const toUni = `/CIDInit /ProcSet findresource begin\n12 dict begin\nbegincmap\n/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def\n/CMapName /Adobe-Identity-UCS def\n/CMapType 2 def\n1 begincodespacerange\n<0000> <FFFF>\nendcodespacerange\n${chunks.join("\n")}\nendcmap\nCMapName currentdict /CMap defineresource pop\nend\nend`;
      const bb = f.bbox.map((v) => Math.round(v * k));
      return { ttf, W, toUni, dw: Math.round(f.metric(f.cmap.get(65) ?? 0).aw * k), bbox: bb, ascent: Math.round(f.ascent * k), descent: Math.round(f.descent * k), cap: Math.round(f.capHeight * k) };
    },
  };
  return api;
}

// Шрифты документа: { regular, bold } — свежее состояние на каждый PDF (какие знаки использованы). Данные шрифта — отдельный чанк.
export async function loadFonts() {
  const d = await import("./pdffont-data.js"), raw = (b64) => Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
  return { regular: createFont(raw(d.MONO), { name: "DejaVuSansMono", tag: "AAAAAA" }), bold: createFont(raw(d.MONO_BOLD), { name: "DejaVuSansMono-Bold", tag: "AAAAAB", bold: true }) };
}
