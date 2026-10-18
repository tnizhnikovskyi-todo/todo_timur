// Штрихкоди без залежностей (F05-02, F05-04; MERGE.md §4.2): Code128 (набори A/B/C, контрольна сума) і QR (режим byte, версії 1–15,
// рівні L/M/Q/H, вибір маски за штрафами). Один код у модулі й прототипі; сервер малює ті самі коди через reportlab/qrcode (services/labels.py),
// еталон Python↔JS — tools/test_core_s3.mjs. Без DOM і без CDN (JsBarcode/qrcode-generator не потрібні).

/* ---------- Code128 ---------- */
// 107 шаблонів: 0–105 — символи, 106 — стоп (7 елементів); цифри — ширини смуг і пробілів по черзі, сума кожного символа — 11 модулів.
const C128 =
    "212222 222122 222221 121223 121322 131222 122213 122312 132212 221213 221312 231212 112232 122132 122231 113222 123122 123221 223211 221132 221231 213212 223112 312131 311222 321122 321221 312212 322112 322211 212123 212321 232121 111323 131123 131321 112313 132113 132311 211313 231113 231311 112133 112331 132131 113123 113321 133121 313121 211331 231131 213113 213311 213131 311123 311321 331121 312113 312311 332111 314111 221411 431111 111224 111422 121124 121421 141122 141221 112214 112412 122114 122411 142112 142211 241211 221114 413111 241112 134111 111242 121142 121241 114212 124112 124211 411212 421112 421211 212141 214121 412121 111143 111341 131141 114113 114311 411113 411311 113141 114131 311141 411131 211412 211214 211232 2331112".split(
        " "
    );
const START_B = 104;
const START_C = 105;
const CODE_B = 100;
const CODE_C = 99;
const STOP = 106;

/** Чи рядок складається лише з друкованих ASCII (32–126) — інакше Code128 не підходить (використайте QR). */
export const isPrintableAscii = (text) => /^[\x20-\x7e]*$/.test(text);

const digitRun = (text, i) => {
    let n = 0;
    while (i + n < text.length && text.charCodeAt(i + n) >= 48 && text.charCodeAt(i + n) <= 57) {
        n++;
    }
    return n;
};

/** Значення Code128 (старт, дані, контрольна сума, стоп) для друкованого ASCII; цифрові серії ≥ 4 кодуються набором C. */
export function code128Values(text) {
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
    if (run0 >= 4 || (run0 === s.length && run0 >= 2)) {
        out.push(START_C);
        set = "C";
    } else {
        out.push(START_B);
        set = "B";
    }
    while (i < s.length) {
        const run = digitRun(s, i);
        if (set === "B") {
            // у наборі B серія з ≥ 6 цифр (чи ≥ 4 в кінці) переходить у C; непарна серія віддає першу цифру набору B
            if (run >= 6 || (run >= 4 && i + run === s.length)) {
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

/** Модулі Code128 рядком «1» (смуга) / «0» (пробіл) без тихих зон; ширина = 11 × (символів) + 13. */
export function code128(text) {
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

/** Розбір модулів Code128 назад у значення (для перевірок): повертає {values, text, ok}. */
export function code128Decode(modules) {
    const values = [];
    let i = 0;
    const read = (pat) => {
        let p = 0;
        let bar = modules[i] === "1";
        let j = i;
        for (const ch of pat) {
            const want = bar ? "1" : "0";
            for (let k = 0; k < Number(ch); k++) {
                if (modules[j++] !== want) {
                    return false;
                }
            }
            bar = !bar;
            p++;
        }
        return p === pat.length ? j : false;
    };
    while (i < modules.length) {
        let hit = -1;
        for (let v = 0; v < C128.length; v++) {
            const end = read(C128[v]);
            if (end !== false) {
                hit = v;
                i = end;
                break;
            }
        }
        if (hit < 0) {
            return { values, text: "", ok: false };
        }
        values.push(hit);
    }
    const sum = values.slice(1, -2).reduce((a, v, k) => a + v * (k + 1), values[0]) % 103;
    let text = "";
    let set = values[0] === START_C ? "C" : "B";
    for (const v of values.slice(1, -2)) {
        if (v === CODE_B) {
            set = "B";
        } else if (v === CODE_C) {
            set = "C";
        } else if (set === "C") {
            text += String(v).padStart(2, "0");
        } else {
            text += String.fromCharCode(v + 32);
        }
    }
    return { values, text, ok: values[values.length - 1] === STOP && values[values.length - 2] === sum };
}

/* ---------- QR ---------- */
// Блоки виправлення помилок: версії 1–15, рівні L, M, Q, H; запис [кількість блоків, всього кодових слів у блоці, даних у блоці (, …друга група)].
const RS = [
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
    [[5, 109, 87, 1, 110, 88], [5, 65, 41, 5, 66, 42], [5, 54, 24, 7, 55, 25], [11, 36, 12, 7, 37, 13]],
];
const ALIGN = [[], [6, 18], [6, 22], [6, 26], [6, 30], [6, 34], [6, 22, 38], [6, 24, 42], [6, 26, 46], [6, 28, 50], [6, 30, 54], [6, 32, 58], [6, 34, 62], [6, 26, 46, 66], [6, 26, 48, 70]];
const ECC_INDEX = { L: 0, M: 1, Q: 2, H: 3 };
const ECC_FORMAT = { L: 1, M: 0, Q: 3, H: 2 };
export const QR_MAX_VERSION = RS.length;

const blocksOf = (version, ecc) => {
    const e = RS[version - 1][ECC_INDEX[ecc]];
    const out = [];
    for (let i = 0; i < e.length; i += 3) {
        for (let k = 0; k < e[i]; k++) {
            out.push({ total: e[i + 1], data: e[i + 2] });
        }
    }
    return out;
};
const dataCodewords = (version, ecc) => blocksOf(version, ecc).reduce((n, b) => n + b.data, 0);

// поле Галуа 256 (поліном 0x11D)
const EXP = new Array(512);
const LOG = new Array(256);
for (let i = 0, x = 1; i < 255; i++) {
    EXP[i] = x;
    LOG[x] = i;
    x <<= 1;
    if (x & 0x100) {
        x ^= 0x11d;
    }
}
for (let i = 255; i < 512; i++) {
    EXP[i] = EXP[i - 255];
}
const gmul = (a, b) => (a && b ? EXP[LOG[a] + LOG[b]] : 0);

function rsGenerator(deg) {
    let g = [1];
    for (let i = 0; i < deg; i++) {
        const next = new Array(g.length + 1).fill(0);
        for (let j = 0; j < g.length; j++) {
            next[j] ^= g[j];
            next[j + 1] ^= gmul(g[j], EXP[i]);
        }
        g = next;
    }
    return g;
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

const utf8 = (text) => Array.from(new TextEncoder().encode(text));

/** Бітовий потік даних (режим byte) і кодові слова з виправленням помилок у порядку розкладання. */
function buildCodewords(bytes, version, ecc) {
    const cap = dataCodewords(version, ecc) * 8;
    const bits = [];
    const put = (val, n) => {
        for (let i = n - 1; i >= 0; i--) {
            bits.push((val >>> i) & 1);
        }
    };
    put(0b0100, 4);
    put(bytes.length, version <= 9 ? 8 : 16);
    for (const b of bytes) {
        put(b, 8);
    }
    put(0, Math.min(4, cap - bits.length));
    while (bits.length % 8) {
        bits.push(0);
    }
    for (let pad = 0xec; bits.length < cap; pad ^= 0xec ^ 0x11) {
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

const MASKS = [
    (x, y) => (x + y) % 2 === 0,
    (x, y) => y % 2 === 0,
    (x, y) => x % 3 === 0,
    (x, y) => (x + y) % 3 === 0,
    (x, y) => (((y / 2) | 0) + ((x / 3) | 0)) % 2 === 0,
    (x, y) => ((x * y) % 2) + ((x * y) % 3) === 0,
    (x, y) => (((x * y) % 2) + ((x * y) % 3)) % 2 === 0,
    (x, y) => (((x + y) % 2) + ((x * y) % 3)) % 2 === 0,
];

class Matrix {
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
        const pos = ALIGN[this.version - 1];
        for (let a = 0; a < pos.length; a++) {
            for (let b = 0; b < pos.length; b++) {
                if ((a === 0 && b === 0) || (a === 0 && b === pos.length - 1) || (a === pos.length - 1 && b === 0)) {
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
        const data = (ECC_FORMAT[ecc] << 3) | mask;
        let rem = data;
        for (let i = 0; i < 10; i++) {
            rem = (rem << 1) ^ ((rem >>> 9) * 0x537);
        }
        const bits = ((data << 10) | rem) ^ 0x5412;
        const bit = (i) => ((bits >>> i) & 1) !== 0;
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
            rem = (rem << 1) ^ ((rem >>> 11) * 0x1f25);
        }
        const bits = (this.version << 12) | rem;
        for (let i = 0; i < 18; i++) {
            const dark = ((bits >>> i) & 1) !== 0;
            const a = this.size - 11 + (i % 3);
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
                    const upward = ((right + 1) & 2) === 0;
                    const y = upward ? n - 1 - vert : vert;
                    if (!this.fn[y][x] && i < words.length * 8) {
                        this.m[y][x] = ((words[i >>> 3] >>> (7 - (i & 7))) & 1) !== 0;
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
                if (pat.every((v, k) => line[i + k] === v)) {
                    const before = i >= 4 && [1, 2, 3, 4].every((k) => !line[i - k]);
                    const after = i + 11 <= line.length && [7, 8, 9, 10].every((k) => !line[i + k]);
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
}

/**
 * QR-код тексту (UTF-8, режим byte). opts: {ecc: "L"|"M"|"Q"|"H" (M), mask: 0–7 (за замовчуванням — найкраща за штрафами), minVersion}.
 * Повертає {version, size, ecc, mask, rows: ["1010…", …] (1 — темний модуль), get(x, y)}; занадто довгий текст — помилка.
 */
export function qr(text, { ecc = "M", mask = null, minVersion = 1 } = {}) {
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
    const rows = mx.m.map((r) => r.map((d) => (d ? "1" : "0")).join(""));
    return { version, size: mx.size, ecc, mask: best, rows, get: (x, y) => rows[y][x] === "1" };
}
