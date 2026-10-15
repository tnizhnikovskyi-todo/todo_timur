// CSV без зависимостей: разбор (кавычки, переводы строк внутри поля, разделитель , ; или табуляция) и запись (UTF-8, RFC 4180).

// Разделитель определяется по первой строке вне кавычек: чаще всего встречающийся из , ; \t (при равенстве — запятая)
export function detectDelimiter(text) {
  const cnt = { ",": 0, ";": 0, "\t": 0 };
  let q = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (c === '"') q = !q;
    else if (!q && (c === "\n" || c === "\r")) break;
    else if (!q && c in cnt) cnt[c]++;
  }
  return [",", ";", "\t"].reduce((a, b) => (cnt[b] > cnt[a] ? b : a), ",");
}

// text → [[ячейка, …], …]; BOM снимается; пустые строки пропускаются (keepBlank — остаются как [""], чтобы номера строк совпадали с файлом)
export function parseCsv(text, delim = null, keepBlank = false) {
  if (text.charCodeAt(0) === 0xfeff) text = text.slice(1);
  const d = delim || detectDelimiter(text), rows = [];
  let row = [], cell = "", q = false, any = false;
  const endCell = () => { row.push(cell); cell = ""; any = true; };
  const endRow = () => { endCell(); if (keepBlank || row.some((x) => x.trim() !== "")) rows.push(row); row = []; any = false; };
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (q) {
      if (c === '"') { if (text[i + 1] === '"') { cell += '"'; i++; } else q = false; } else cell += c;
    } else if (c === '"' && cell === "") q = true;
    else if (c === d) endCell();
    else if (c === "\n" || c === "\r") { if (c === "\r" && text[i + 1] === "\n") i++; endRow(); }
    else cell += c;
  }
  if (any || cell !== "") endRow();
  return rows;
}

const needsQuote = (s) => /[",\n\r;\t]/.test(s) || /^\s|\s$/.test(s);
export function writeCsv(rows, delim = ",") {
  return rows.map((r) => r.map((v) => { const s = v == null ? "" : String(v); return needsQuote(s) ? `"${s.replace(/"/g, '""')}"` : s; }).join(delim)).join("\r\n") + "\r\n";
}

// байты → текст: UTF-8, при ошибке — windows-1251 (так сохраняет CSV русская и украинская Excel)
export function decodeText(bytes) {
  if (typeof bytes === "string") return bytes;
  const u8 = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes);
  try { return new TextDecoder("utf-8", { fatal: true }).decode(u8); } catch (e) { return new TextDecoder("windows-1251").decode(u8); }
}
