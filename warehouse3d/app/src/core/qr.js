// QR-код (W-09, D-14): минимальный кодировщик — режим байтов (UTF-8), версии 1–10, уровни коррекции L / M / Q / H, выбор маски по штрафам. Без DOM и состояния.
// qrEncode(text, { ecc }) → { version, size, ecc, mask, rows: [[0|1, …], …] } (1 — тёмный модуль; тихая зона в матрицу не входит).
const ECC_BITS = { L: 1, M: 0, Q: 3, H: 2 };
// версии 1–10: [байт коррекции на блок, блоков в 1-й группе, байт данных в блоке 1-й группы, блоков во 2-й группе, байт данных в блоке 2-й группы]
const BLOCKS = {
  L: [[7, 1, 19], [10, 1, 34], [15, 1, 55], [20, 1, 80], [26, 1, 108], [18, 2, 68], [20, 2, 78], [24, 2, 97], [30, 2, 116], [18, 2, 68, 2, 69]],
  M: [[10, 1, 16], [16, 1, 28], [26, 1, 44], [18, 2, 32], [24, 2, 43], [16, 4, 27], [18, 4, 31], [22, 2, 38, 2, 39], [22, 3, 36, 2, 37], [26, 4, 43, 1, 44]],
  Q: [[13, 1, 13], [22, 1, 22], [18, 2, 17], [26, 2, 24], [18, 2, 15, 2, 16], [24, 4, 19], [18, 2, 14, 4, 15], [22, 4, 18, 2, 19], [20, 4, 16, 4, 17], [24, 6, 19, 2, 20]],
  H: [[17, 1, 9], [28, 1, 16], [22, 2, 13], [16, 4, 9], [22, 2, 11, 2, 12], [28, 4, 15], [26, 4, 13, 1, 14], [26, 4, 14, 2, 15], [24, 4, 12, 4, 13], [28, 6, 15, 2, 16]],
};
const ALIGN = [[], [6, 18], [6, 22], [6, 26], [6, 30], [6, 34], [6, 22, 38], [6, 24, 42], [6, 26, 46], [6, 28, 50]];
export const QR_ECC = Object.keys(ECC_BITS);
export const QR_MAX_VERSION = 10;

const dataBytes = (ecc, v) => { const b = BLOCKS[ecc][v - 1]; return b[1] * b[2] + (b[3] || 0) * (b[4] || 0); };
export const qrCapacity = (ecc, v = QR_MAX_VERSION) => dataBytes(ecc, v) - (v >= 10 ? 3 : 2); // байт текста

// ---------- поле Галуа GF(256), Рид-Соломон
const EXP = new Uint8Array(512), LOG = new Uint8Array(256);
for (let i = 0, x = 1; i < 255; i++) { EXP[i] = x; LOG[x] = i; x <<= 1; if (x & 256) x ^= 0x11d; }
for (let i = 255; i < 512; i++) EXP[i] = EXP[i - 255];
const mul = (a, b) => (a && b ? EXP[LOG[a] + LOG[b]] : 0);
function rsGen(deg) {
  let g = [1];
  for (let i = 0; i < deg; i++) { const n = new Array(g.length + 1).fill(0); g.forEach((c, j) => { n[j] ^= c; n[j + 1] ^= mul(c, EXP[i]); }); g = n; }
  return g;
}
function rsRemainder(data, deg) {
  const g = rsGen(deg), r = new Array(deg).fill(0);
  for (const b of data) {
    const f = b ^ r[0]; r.shift(); r.push(0);
    if (f) for (let i = 0; i < deg; i++) r[i] ^= mul(g[i + 1], f);
  }
  return r;
}

// кодовые слова: данные режима байтов, дополнение, блоки с коррекцией, перемежение
function codewords(bytes, ecc, v) {
  const bits = [], put = (val, n) => { for (let i = n - 1; i >= 0; i--) bits.push((val >>> i) & 1); };
  put(4, 4); put(bytes.length, v >= 10 ? 16 : 8); bytes.forEach((b) => put(b, 8));
  const cap = dataBytes(ecc, v) * 8;
  put(0, Math.min(4, cap - bits.length)); while (bits.length % 8) bits.push(0);
  const data = []; for (let i = 0; i < bits.length; i += 8) data.push(parseInt(bits.slice(i, i + 8).join(""), 2));
  for (let p = 0xec; data.length < dataBytes(ecc, v); p ^= 0xec ^ 0x11) data.push(p);
  const [ec, n1, d1, n2 = 0, d2 = 0] = BLOCKS[ecc][v - 1], blocks = [];
  let k = 0;
  for (let i = 0; i < n1 + n2; i++) { const len = i < n1 ? d1 : d2, d = data.slice(k, k + len); k += len; blocks.push({ d, e: rsRemainder(d, ec) }); }
  const out = [], maxD = Math.max(d1, d2);
  for (let i = 0; i < maxD; i++) for (const b of blocks) if (i < b.d.length) out.push(b.d[i]);
  for (let i = 0; i < ec; i++) for (const b of blocks) out.push(b.e[i]);
  return out;
}

// ---------- матрица
function buildMatrix(v, cw, ecc, maskNo) {
  const size = 17 + 4 * v, m = Array.from({ length: size }, () => new Array(size).fill(0)), fn = Array.from({ length: size }, () => new Array(size).fill(false));
  const set = (x, y, dark) => { if (x >= 0 && y >= 0 && x < size && y < size) { m[y][x] = dark ? 1 : 0; fn[y][x] = true; } };
  for (let i = 0; i < size; i++) { set(6, i, i % 2 === 0); set(i, 6, i % 2 === 0); }
  const finder = (cx, cy) => { for (let dy = -4; dy <= 4; dy++) for (let dx = -4; dx <= 4; dx++) { const d = Math.max(Math.abs(dx), Math.abs(dy)); set(cx + dx, cy + dy, d !== 2 && d !== 4); } };
  finder(3, 3); finder(size - 4, 3); finder(3, size - 4);
  const ap = ALIGN[v - 1], last = ap.length - 1;
  ap.forEach((a, i) => ap.forEach((b, j) => { if ((i === 0 && j === 0) || (i === 0 && j === last) || (i === last && j === 0)) return; for (let dy = -2; dy <= 2; dy++) for (let dx = -2; dx <= 2; dx++) set(a + dx, b + dy, Math.max(Math.abs(dx), Math.abs(dy)) !== 1); }));
  const format = (mask) => {
    const d = (ECC_BITS[ecc] << 3) | mask; let r = d;
    for (let i = 0; i < 10; i++) r = (r << 1) ^ ((r >>> 9) * 0x537);
    const bits = ((d << 10) | r) ^ 0x5412, bit = (i) => ((bits >>> i) & 1) === 1;
    for (let i = 0; i <= 5; i++) set(8, i, bit(i));
    set(8, 7, bit(6)); set(8, 8, bit(7)); set(7, 8, bit(8));
    for (let i = 9; i < 15; i++) set(14 - i, 8, bit(i));
    for (let i = 0; i < 8; i++) set(size - 1 - i, 8, bit(i));
    for (let i = 8; i < 15; i++) set(8, size - 15 + i, bit(i));
    set(8, size - 8, true);
  };
  format(0);
  if (v >= 7) {
    let r = v; for (let i = 0; i < 12; i++) r = (r << 1) ^ ((r >>> 11) * 0x1f25);
    const bits = (v << 12) | r;
    for (let i = 0; i < 18; i++) { const b = ((bits >>> i) & 1) === 1, a = size - 11 + (i % 3), c = Math.floor(i / 3); set(a, c, b); set(c, a, b); }
  }
  // данные зигзагом
  let i = 0;
  for (let right = size - 1; right >= 1; right -= 2) {
    if (right === 6) right = 5;
    for (let vert = 0; vert < size; vert++) for (let j = 0; j < 2; j++) {
      const x = right - j, y = ((right + 1) & 2) === 0 ? size - 1 - vert : vert;
      if (!fn[y][x] && i < cw.length * 8) { m[y][x] = (cw[i >> 3] >>> (7 - (i & 7))) & 1; i++; }
    }
  }
  const MASKS = [(x, y) => (x + y) % 2 === 0, (x, y) => y % 2 === 0, (x) => x % 3 === 0, (x, y) => (x + y) % 3 === 0, (x, y) => (Math.floor(x / 3) + Math.floor(y / 2)) % 2 === 0,
    (x, y) => ((x * y) % 2) + ((x * y) % 3) === 0, (x, y) => (((x * y) % 2) + ((x * y) % 3)) % 2 === 0, (x, y) => ((((x + y) % 2) + ((x * y) % 3)) % 2) === 0];
  const apply = (no) => { for (let y = 0; y < size; y++) for (let x = 0; x < size; x++) if (!fn[y][x] && MASKS[no](x, y)) m[y][x] ^= 1; };
  const penalty = () => {
    let p = 0;
    const lines = [...m, ...Array.from({ length: size }, (_, x) => m.map((row) => row[x]))];
    for (const L of lines) {
      let run = 1;
      for (let k = 1; k <= size; k++) { if (k < size && L[k] === L[k - 1]) run++; else { if (run >= 5) p += 3 + run - 5; run = 1; } }
      const s = L.join("");
      for (const pat of ["10111010000", "00001011101"]) for (let k = s.indexOf(pat); k >= 0; k = s.indexOf(pat, k + 1)) p += 40;
    }
    let dark = 0;
    for (let y = 0; y < size; y++) for (let x = 0; x < size; x++) { dark += m[y][x]; if (x && y && m[y][x] === m[y][x - 1] && m[y][x] === m[y - 1][x] && m[y][x] === m[y - 1][x - 1]) p += 3; }
    return p + 10 * (Math.ceil(Math.abs(dark * 20 - size * size * 10) / (size * size)) - 1);
  };
  let best = -1, bestP = Infinity;
  const pick = maskNo == null ? [0, 1, 2, 3, 4, 5, 6, 7] : [maskNo];
  for (const no of pick) { apply(no); format(no); const p = penalty(); if (p < bestP) { bestP = p; best = no; } apply(no); }
  apply(best); format(best);
  return { size, mask: best, rows: m };
}

// наименьшая версия для текста из len байт (0 — не помещается)
export function qrVersion(len, ecc = "M") { for (let v = 1; v <= QR_MAX_VERSION; v++) if (len <= qrCapacity(ecc, v)) return v; return 0; }

export function qrEncode(text, { ecc = "M", mask = null } = {}) {
  if (!BLOCKS[ecc]) throw new Error("qr: ecc");
  const bytes = [...new TextEncoder().encode(String(text))], v = qrVersion(bytes.length, ecc);
  if (!v) throw new Error("qr: text too long");
  const r = buildMatrix(v, codewords(bytes, ecc, v), ecc, mask);
  return { version: v, size: r.size, ecc, mask: r.mask, rows: r.rows };
}
