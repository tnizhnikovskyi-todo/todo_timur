// Минимальные чтение и запись XLSX (без зависимостей, грузится лениво): ZIP + SpreadsheetML одного листа.
// Запись: один лист, строки — inlineStr, числа — n; ZIP со сжатием deflate (CompressionStream), если оно есть, иначе без сжатия.
// Чтение: первый лист книги; общие строки, inlineStr, числа, логические; сжатие — DecompressionStream("deflate-raw").

const te = new TextEncoder(), td = new TextDecoder();
const CRC = (() => { const t = new Uint32Array(256); for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1; t[n] = c >>> 0; } return t; })();
const crc32 = (u8) => { let c = 0xffffffff; for (let i = 0; i < u8.length; i++) c = CRC[(c ^ u8[i]) & 255] ^ (c >>> 8); return (c ^ 0xffffffff) >>> 0; };
const concat = (parts) => { const out = new Uint8Array(parts.reduce((a, p) => a + p.length, 0)); let o = 0; for (const p of parts) { out.set(p, o); o += p.length; } return out; };

async function pipe(u8, stream) {
  const w = stream.writable.getWriter(), parts = [], r = stream.readable.getReader();
  w.write(u8).catch(() => {}); w.close().catch(() => {});
  for (;;) { const { done, value } = await r.read(); if (done) break; parts.push(value); }
  return concat(parts);
}

// ---------- ZIP
export async function zipWrite(files) { // files: [[имя, Uint8Array]]
  const chunks = [], central = []; let off = 0;
  const canZ = typeof CompressionStream === "function";
  for (const [name, data] of files) {
    const nm = te.encode(name), crc = crc32(data);
    let body = data, method = 0;
    if (canZ && data.length > 64) { const z = await pipe(data, new CompressionStream("deflate-raw")); if (z.length < data.length) { body = z; method = 8; } }
    const lh = new DataView(new ArrayBuffer(30));
    lh.setUint32(0, 0x04034b50, true); lh.setUint16(4, 20, true); lh.setUint16(6, 0x0800, true); lh.setUint16(8, method, true); lh.setUint16(12, 0x21, true);
    lh.setUint32(14, crc, true); lh.setUint32(18, body.length, true); lh.setUint32(22, data.length, true); lh.setUint16(26, nm.length, true);
    chunks.push(new Uint8Array(lh.buffer), nm, body);
    const ch = new DataView(new ArrayBuffer(46));
    ch.setUint32(0, 0x02014b50, true); ch.setUint16(4, 20, true); ch.setUint16(6, 20, true); ch.setUint16(8, 0x0800, true); ch.setUint16(10, method, true); ch.setUint16(14, 0x21, true);
    ch.setUint32(16, crc, true); ch.setUint32(20, body.length, true); ch.setUint32(24, data.length, true); ch.setUint16(28, nm.length, true); ch.setUint32(42, off, true);
    central.push(new Uint8Array(ch.buffer), nm);
    off += 30 + nm.length + body.length;
  }
  const csize = central.reduce((a, p) => a + p.length, 0), end = new DataView(new ArrayBuffer(22));
  end.setUint32(0, 0x06054b50, true); end.setUint16(8, files.length, true); end.setUint16(10, files.length, true); end.setUint32(12, csize, true); end.setUint32(16, off, true);
  return concat([...chunks, ...central, new Uint8Array(end.buffer)]);
}

export async function zipRead(u8) { // → Map имя → Uint8Array
  const dv = new DataView(u8.buffer, u8.byteOffset, u8.byteLength);
  let e = u8.length - 22; while (e >= 0 && dv.getUint32(e, true) !== 0x06054b50) e--;
  if (e < 0) throw new Error("not a zip");
  const n = dv.getUint16(e + 10, true), out = new Map(); let p = dv.getUint32(e + 16, true);
  for (let i = 0; i < n; i++) {
    if (dv.getUint32(p, true) !== 0x02014b50) throw new Error("bad zip");
    const method = dv.getUint16(p + 10, true), csz = dv.getUint32(p + 20, true), nl = dv.getUint16(p + 28, true), xl = dv.getUint16(p + 30, true), cl = dv.getUint16(p + 32, true), lo = dv.getUint32(p + 42, true);
    const name = td.decode(u8.subarray(p + 46, p + 46 + nl));
    const ds = lo + 30 + dv.getUint16(lo + 26, true) + dv.getUint16(lo + 28, true), raw = u8.subarray(ds, ds + csz);
    if (!name.endsWith("/")) {
      if (method !== 0 && method !== 8) throw new Error("zip method");
      out.set(name, method === 0 ? raw : await pipe(raw, new DecompressionStream("deflate-raw")));
    }
    p += 46 + nl + xl + cl;
  }
  return out;
}

// ---------- XML
const xesc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]).replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f]/g, "");
const xun = (s) => s.replace(/&(#x[0-9a-fA-F]+|#\d+|lt|gt|amp|quot|apos);/g, (m, k) => (k[0] === "#" ? String.fromCodePoint(k[1] === "x" ? parseInt(k.slice(2), 16) : +k.slice(1)) : { lt: "<", gt: ">", amp: "&", quot: '"', apos: "'" }[k]));
const colName = (i) => { let s = ""; for (let n = i + 1; n > 0; n = Math.floor((n - 1) / 26)) s = String.fromCharCode(65 + ((n - 1) % 26)) + s; return s; };
const colIndex = (ref) => { let n = 0; for (const c of /^[A-Z]+/i.exec(ref)[0].toUpperCase()) n = n * 26 + c.charCodeAt(0) - 64; return n - 1; };
const textOf = (x) => [...x.matchAll(/<t\b[^>]*>([\s\S]*?)<\/t>/g)].map((m) => xun(m[1])).join("");

// rows: [[значение, …]]; число (typeof number) пишется как n, остальное — строка
export async function writeXlsx(rows, sheet = "Sheet1") {
  const cell = (v, r, c) => v === "" || v == null ? "" : typeof v === "number" && Number.isFinite(v) ? `<c r="${colName(c)}${r + 1}"><v>${v}</v></c>` : `<c r="${colName(c)}${r + 1}" t="inlineStr"><is><t xml:space="preserve">${xesc(v)}</t></is></c>`;
  const data = rows.map((row, r) => `<row r="${r + 1}">${row.map((v, c) => cell(v, r, c)).join("")}</row>`).join("");
  const X = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n', NS = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"', R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships";
  const files = {
    "[Content_Types].xml": `${X}<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/></Types>`,
    "_rels/.rels": `${X}<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="${R}/officeDocument" Target="xl/workbook.xml"/></Relationships>`,
    "xl/workbook.xml": `${X}<workbook ${NS} xmlns:r="${R}"><sheets><sheet name="${xesc(sheet.slice(0, 31))}" sheetId="1" r:id="rId1"/></sheets></workbook>`,
    "xl/_rels/workbook.xml.rels": `${X}<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="${R}/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="${R}/styles" Target="styles.xml"/></Relationships>`,
    "xl/styles.xml": `${X}<styleSheet ${NS}><fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts><fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills><borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/></cellXfs></styleSheet>`,
    "xl/worksheets/sheet1.xml": `${X}<worksheet ${NS}><sheetData>${data}</sheetData></worksheet>`,
  };
  return zipWrite(Object.entries(files).map(([k, v]) => [k, te.encode(v)]));
}

// → [[строка, …], …]: первый лист; пропущенные ячейки — "", пустые строки пропускаются (keepBlank — остаются пустыми массивами по номеру строки r)
export async function readXlsx(bytes, keepBlank = false) {
  const z = await zipRead(bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes));
  const get = (n) => (z.has(n) ? td.decode(z.get(n)) : null);
  let path = "xl/worksheets/sheet1.xml";
  const wb = get("xl/workbook.xml"), rels = get("xl/_rels/workbook.xml.rels");
  if (wb && rels) {
    const rid = /<sheet\b[^>]*\br:id="([^"]+)"/.exec(wb)?.[1], tag = rid && [...rels.matchAll(/<Relationship\b[^>]*>/g)].map((m) => m[0]).find((x) => new RegExp(`\\bId="${rid}"`).test(x));
    const tg = tag && /\bTarget="([^"]+)"/.exec(tag)?.[1];
    if (tg) path = tg.startsWith("/") ? tg.slice(1) : `xl/${tg.replace(/^\.\//, "")}`;
  }
  const xml = get(path) ?? get([...z.keys()].find((k) => /^xl\/worksheets\/[^/]+\.xml$/.test(k)) || "");
  if (xml == null) throw new Error("no sheet");
  const ss = get("xl/sharedStrings.xml"), shared = ss ? [...ss.matchAll(/<si\b[^>]*>([\s\S]*?)<\/si>/g)].map((m) => textOf(m[1])) : [];
  const rows = [];
  for (const rm of xml.matchAll(/<row\b([^>]*?)(?:\/>|>([\s\S]*?)<\/row>)/g)) {
    const row = []; let next = 0, rn = /\br="(\d+)"/.exec(rm[1])?.[1];
    if (keepBlank && rn) while (rows.length < +rn - 1) rows.push([]);
    for (const cm of (rm[2] || "").matchAll(/<c\b([^>]*?)(?:\/>|>([\s\S]*?)<\/c>)/g)) {
      const at = cm[1], ref = /\br="([A-Z]+\d+)"/i.exec(at), t = /\bt="(\w+)"/.exec(at)?.[1], body = cm[2] || "";
      const idx = ref ? colIndex(ref[1]) : next; while (row.length < idx) row.push("");
      const v = /<v>([\s\S]*?)<\/v>/.exec(body)?.[1];
      row[idx] = t === "s" ? shared[+v] ?? "" : t === "inlineStr" ? textOf(body) : v == null ? "" : t === "b" ? (v === "1" ? "TRUE" : "FALSE") : xun(v);
      next = idx + 1;
    }
    if (keepBlank || row.some((x) => String(x).trim() !== "")) rows.push(row);
  }
  return rows;
}
