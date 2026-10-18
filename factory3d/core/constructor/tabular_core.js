// Таблиці CSV/XLSX без залежностей (F11, слайс S4): розбір і запис у браузері й у Node. XLSX — власний мінімальний читач і письменник
// (zip зі стисненням deflate-raw через DecompressionStream/CompressionStream; без CDN і бібліотек). Рядки — масиви значень
// (string | number | boolean); порожня клітинка — "". Читач розуміє файли Excel/LibreOffice/openpyxl/xlsxwriter (спільні рядки, inlineStr,
// числа, логічні); письменник дає inlineStr і числа, які читають Excel, LibreOffice і openpyxl. Далі — відповідність заголовків колонок
// формату імпорту stock.location (EN/UK/RU) і перетворення рядків у локації та назад.

/* ---------- байти й XML ---------- */
const enc = new TextEncoder();
const u8 = (x) => (x instanceof Uint8Array ? x : new Uint8Array(x));
const xmlEsc = (s) => String(s).replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F]/g, "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
const xmlUnesc = (s) =>
    s.replace(/&(#x[0-9a-fA-F]+|#\d+|amp|lt|gt|quot|apos);/g, (_m, e) => {
        if (e[0] === "#") {
            return String.fromCodePoint(e[1] === "x" ? parseInt(e.slice(2), 16) : parseInt(e.slice(1), 10));
        }
        return { amp: "&", lt: "<", gt: ">", quot: '"', apos: "'" }[e];
    });

let crcTable = null;
export function crc32(bytes) {
    if (!crcTable) {
        crcTable = new Uint32Array(256);
        for (let n = 0; n < 256; n++) {
            let c = n;
            for (let k = 0; k < 8; k++) {
                c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
            }
            crcTable[n] = c >>> 0;
        }
    }
    let c = 0xffffffff;
    for (let i = 0; i < bytes.length; i++) {
        c = crcTable[(c ^ bytes[i]) & 0xff] ^ (c >>> 8);
    }
    return (c ^ 0xffffffff) >>> 0;
}

async function pipe(bytes, stream) {
    const w = stream.writable.getWriter();
    w.write(bytes);
    w.close();
    const chunks = [];
    const r = stream.readable.getReader();
    for (;;) {
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
const deflateRaw = (b) => pipe(b, new CompressionStream("deflate-raw"));
const inflateRaw = (b) => pipe(b, new DecompressionStream("deflate-raw"));

/* ---------- zip ---------- */
/** Файли [{name, data}] → zip (deflate, якщо є CompressionStream; інакше stored). */
export async function zipFiles(files) {
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
        lh.setUint32(0, 0x04034b50, true);
        lh.setUint16(4, 20, true);
        lh.setUint16(6, 0x0800, true); // UTF-8 імена
        lh.setUint16(8, method, true);
        lh.setUint16(10, 0, true);
        lh.setUint16(12, 0x21, true); // 1980-01-01
        lh.setUint32(14, crc, true);
        lh.setUint32(18, body.length, true);
        lh.setUint32(22, data.length, true);
        lh.setUint16(26, name.length, true);
        lh.setUint16(28, 0, true);
        parts.push(new Uint8Array(lh.buffer), name, body);
        const ch = new DataView(new ArrayBuffer(46));
        ch.setUint32(0, 0x02014b50, true);
        ch.setUint16(4, 20, true);
        ch.setUint16(6, 20, true);
        ch.setUint16(8, 0x0800, true);
        ch.setUint16(10, method, true);
        ch.setUint16(12, 0, true);
        ch.setUint16(14, 0x21, true);
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
    end.setUint32(0, 0x06054b50, true);
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

/** zip → Map(ім'я → Uint8Array); читає центральний каталог, розпаковує stored і deflate. */
export async function unzip(bytes) {
    const b = u8(bytes);
    const dv = new DataView(b.buffer, b.byteOffset, b.byteLength);
    let eocd = -1;
    for (let i = b.length - 22; i >= Math.max(0, b.length - 70000); i--) {
        if (dv.getUint32(i, true) === 0x06054b50) {
            eocd = i;
            break;
        }
    }
    if (eocd < 0) {
        throw new Error("Файл не схожий на XLSX (немає zip-каталогу).");
    }
    const n = dv.getUint16(eocd + 10, true);
    let p = dv.getUint32(eocd + 16, true);
    const out = new Map();
    const dec = new TextDecoder();
    for (let i = 0; i < n; i++) {
        if (dv.getUint32(p, true) !== 0x02014b50) {
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

/* ---------- XLSX ---------- */
export const colName = (i) => {
    let s = "";
    for (let n = i + 1; n > 0; n = Math.floor((n - 1) / 26)) {
        s = String.fromCharCode(65 + ((n - 1) % 26)) + s;
    }
    return s;
};
const colIndex = (ref) => {
    let n = 0;
    for (const ch of /^[A-Z]+/.exec(ref)[0]) {
        n = n * 26 + ch.charCodeAt(0) - 64;
    }
    return n - 1;
};

/** Рядки → XLSX (Uint8Array). Рядки — inlineStr (нулі на початку зберігаються), числа — числа, "" — порожня клітинка. */
export async function writeXlsx(rows, { sheet = "Локації" } = {}) {
    const name = xmlEsc(String(sheet).replace(/[\\/?*[\]:]/g, " ").slice(0, 31) || "Лист1");
    const body = rows
        .map((row, r) => {
            const cells = row
                .map((v, c) => {
                    if (v === "" || v == null) {
                        return "";
                    }
                    const ref = `${colName(c)}${r + 1}`;
                    if (typeof v === "number" && Number.isFinite(v)) {
                        return `<c r="${ref}"><v>${v}</v></c>`;
                    }
                    if (typeof v === "boolean") {
                        return `<c r="${ref}" t="b"><v>${v ? 1 : 0}</v></c>`;
                    }
                    return `<c r="${ref}" t="inlineStr"><is><t xml:space="preserve">${xmlEsc(v)}</t></is></c>`;
                })
                .join("");
            return `<row r="${r + 1}">${cells}</row>`;
        })
        .join("");
    const head = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n';
    const files = [
        { name: "[Content_Types].xml", data: enc.encode(`${head}<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>`) },
        { name: "_rels/.rels", data: enc.encode(`${head}<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>`) },
        { name: "xl/workbook.xml", data: enc.encode(`${head}<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="${name}" sheetId="1" r:id="rId1"/></sheets></workbook>`) },
        { name: "xl/_rels/workbook.xml.rels", data: enc.encode(`${head}<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>`) },
        { name: "xl/worksheets/sheet1.xml", data: enc.encode(`${head}<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>${body}</sheetData></worksheet>`) },
    ];
    return await zipFiles(files);
}

const attr = (tag, name) => {
    const m = new RegExp(`\\b${name}="([^"]*)"`).exec(tag);
    return m ? xmlUnesc(m[1]) : null;
};
const textOf = (xml) => [...xml.matchAll(/<t(?:\s[^>]*)?>([\s\S]*?)<\/t>/g)].map((m) => xmlUnesc(m[1])).join("");

/** XLSX → {sheets: [назви], sheet, rows}; `sheet` — назва або номер листа (за замовчуванням перший). */
export async function readXlsx(bytes, { sheet = 0 } = {}) {
    const files = await unzip(bytes);
    const dec = new TextDecoder();
    const get = (n) => (files.has(n) ? dec.decode(files.get(n)) : null);
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
            const ref = attr(cm[1], "r");
            const idx = ref ? colIndex(ref) : row.length;
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

/** Прибирає хвостові порожні клітинки/рядки й вирівнює ширину рядків (прямокутна таблиця). */
export function trimRows(rows) {
    const out = rows.map((r) => {
        const a = [...r];
        while (a.length && (a[a.length - 1] === "" || a[a.length - 1] == null)) {
            a.pop();
        }
        return a.map((v) => (v == null ? "" : v));
    });
    while (out.length && !out[out.length - 1].length) {
        out.pop();
    }
    const w = Math.max(0, ...out.map((r) => r.length));
    return out.map((r) => [...r, ...Array(w - r.length).fill("")]);
}

/* ---------- CSV ---------- */
/** Байти → {text, encoding}: UTF-8 (BOM знімається) або Windows-1251, якщо байти не є UTF-8. */
export function decodeText(bytes) {
    const b = u8(bytes);
    try {
        return { text: new TextDecoder("utf-8", { fatal: true }).decode(b).replace(/^﻿/, ""), encoding: "utf-8" };
    } catch {
        return { text: new TextDecoder("windows-1251").decode(b), encoding: "windows-1251" };
    }
}

/** Роздільник за першим рядком (поза лапками): кома, крапка з комою або табуляція. */
export function detectDelimiter(text) {
    const first = text.split(/\r\n|\n|\r/, 1)[0] || "";
    let best = ",";
    let max = -1;
    for (const d of [",", ";", "\t"]) {
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

/** Текст CSV → рядки (лапки, подвоєні лапки, перенесення в клітинках). */
export function parseCsv(text, delim = detectDelimiter(text)) {
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

/** Рядки → CSV (UTF-8; BOM для Excel; лапки лише де потрібно). */
export function toCsv(rows, { delim = ",", bom = true } = {}) {
    const cell = (v) => {
        const s = v == null ? "" : String(v);
        return s.includes('"') || s.includes(delim) || /[\r\n]/.test(s) || /^\s|\s$/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
    };
    return (bom ? "﻿" : "") + rows.map((r) => r.map(cell).join(delim)).join("\r\n") + "\r\n";
}

/** Файл (байти + ім'я) → {format, encoding?, delimiter?, sheets?, rows}. XLSX розпізнається за zip-сигнатурою, а не за розширенням. */
export async function readTable(bytes, filename = "", { delimiter = null, sheet = 0 } = {}) {
    const b = u8(bytes);
    if (b.length > 3 && b[0] === 0x50 && b[1] === 0x4b) {
        const x = await readXlsx(b, { sheet });
        return { format: "xlsx", sheets: x.sheets, sheet: x.sheet, rows: x.rows };
    }
    const { text, encoding } = decodeText(b);
    const d = delimiter || detectDelimiter(text);
    return { format: "csv", encoding, delimiter: d, rows: parseCsv(text, d) };
}

/* ---------- колонки формату імпорту stock.location ---------- */
export const FIELDS = [
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
    { key: "lot", label: "Партія", aliases: ["lot/serial number", "lot", "lot/serial", "партія", "серійний номер", "партія/серійний номер", "партия", "серийный номер"] },
];
const normHeader = (s) => String(s ?? "").toLowerCase().replace(/[’`ʼ]/g, "'").replace(/\s+/g, " ").trim();
const ALIAS_OF = new Map(FIELDS.flatMap((f) => f.aliases.map((a) => [a, f.key])));

/** Заголовок → {поле: індекс колонки} за відомими назвами (EN/UK/RU, технічні імена Odoo). */
export function autoMap(header) {
    const map = {};
    header.forEach((h, i) => {
        const key = ALIAS_OF.get(normHeader(h));
        if (key && !(key in map)) {
            map[key] = i;
        }
    });
    return map;
}

const USAGE_PATTERNS = [
    [/internal|внутр/i, "internal"],
    [/view|вигляд|вид\b|представ|віртуал|виртуал/i, "view"],
    [/customer|клієнт|покупц|клиент|покупат/i, "customer"],
    [/supplier|vendor|постач|поставщ/i, "supplier"],
    [/inventory|інвентар|инвентар/i, "inventory"],
    [/production|виробн|производ/i, "production"],
    [/transit|транзит/i, "transit"],
];
/** Значення «Тип локації» (ключ чи підпис Odoo, будь-якою мовою) → ключ usage; порожнє — internal. */
export const usageOf = (v) => {
    const s = String(v ?? "").trim();
    if (!s) {
        return "internal";
    }
    const hit = USAGE_PATTERNS.find(([re]) => re.test(s));
    return hit ? hit[1] : s.toLowerCase();
};
const str = (v) => (v == null ? "" : String(v)).trim();

/**
 * Таблиця → локації {code, name, parent, usage, barcode, qty, posx, posy, posz}: код = штрихкод, інакше ім'я (F11-02). Рядки з товаром
 * і кількістю додають залишок до локації (за повним іменем). Порожні рядки пропускаються.
 * @returns {{locs: Array, stats: {rows, locations, stockRows, skippedEmpty}}}
 */
export function rowsToLocations(rows, map) {
    const get = (row, key) => (key in map ? row[map[key]] : "");
    const byFull = new Map();
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

/** Заголовок формату імпорту Odoo (технічні імена полів stock.location). */
export const EXPORT_HEADER = ["name", "location_id", "usage", "barcode", "posx", "posy", "posz"];

/** Локації → рядки таблиці формату імпорту Odoo (заголовок + дані); `parent` — повне ім'я батька. */
export function locationsToRows(locs) {
    return [EXPORT_HEADER, ...locs.map((l) => [l.name ?? l.code, l.parent || "", l.usage || "internal", l.barcode || l.code || "", l.posx ?? "", l.posy ?? "", l.posz ?? ""])];
}

/** Додає недостаючих батьків (усі проміжні шляхи) як локації типу view; порядок — батьки раніше дітей. */
export function withParents(locs, known = new Set()) {
    const have = new Set([...known, ...locs.map((l) => (l.parent ? `${l.parent}/${l.name}` : l.name))]);
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

/** Ім'я файлу з розширенням для скачування. */
export const fileName = (base, ext) => `${String(base || "locations").replace(/[^\w.-]+/g, "_")}.${ext}`;
