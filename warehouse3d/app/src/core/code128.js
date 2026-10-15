// Code128 (W-09, D-14): кодирование текста в значения символов и в полосы. Без DOM и состояния.
// Наборы: B (ASCII 32–126) и C (пары цифр, для длинных цифровых отрезков). Текст вне ASCII не кодируется (`canCode128`).
const WIDTHS = ("212222 222122 222221 121223 121322 131222 122213 122312 132212 221213 221312 231212 112232 122132 122231 113222 123122 123221 223211 221132 221231 213212 223112 312131 311222 321122 321221 312212 322112 322211 212123 212321 232121 111323 131123 131321 112313 132113 132311 211313 231113 231311 112133 112331 132131 113123 113321 133121 313121 211331 231131 213113 213311 213131 311123 311321 331121 312113 312311 332111 314111 221411 431111 111224 111422 121124 121421 141122 141221 112214 112412 122114 122411 142112 142211 241211 221114 413111 241112 134111 111242 121142 121241 114212 124112 124211 411212 421112 421211 212141 214121 412121 111143 111341 131141 114113 114311 411113 411311 113141 114131 311141 411131 211412 211214 211232 2331112").split(" ");
export const START_B = 104, START_C = 105, CODE_B = 100, CODE_C = 99, STOP = 106;

export const canCode128 = (text) => typeof text === "string" && text.length > 0 && /^[\x20-\x7e]+$/.test(text);

// значения символов без контрольного и стопа: старт, данные (с переключениями наборов)
export function code128Data(text) {
  if (!canCode128(text)) throw new Error("code128: only ASCII 32–126");
  const out = [], digits = (i) => { let n = 0; while (i + n < text.length && text[i + n] >= "0" && text[i + n] <= "9") n++; return n; };
  let set = null, i = 0;
  while (i < text.length) {
    const run = digits(i);
    // набор C — если подряд не меньше 4 цифр (в конце строки — не меньше 4, в начале — тоже); пары цифр, нечётная цифра остаётся набору B
    if (run >= 4 && (set !== "C")) { out.push(set === null ? START_C : CODE_C); set = "C"; }
    else if (set !== "C" && set !== "B") { out.push(START_B); set = "B"; }
    else if (set === "C" && run < 2) { out.push(CODE_B); set = "B"; }
    if (set === "C") { out.push(+text.slice(i, i + 2)); i += 2; }
    else { out.push(text.charCodeAt(i) - 32); i++; }
  }
  return out;
}
export const checksum128 = (data) => data.reduce((s, v, i) => s + (i === 0 ? v : v * i), 0) % 103;

// все значения символов: старт, данные, контрольный, стоп
export function code128Values(text) { const d = code128Data(text); return [...d, checksum128(d), STOP]; }

// ширины полос и пробелов в модулях, начиная с полосы; число модулей (без тихих зон)
export function code128Bars(text) {
  const vals = code128Values(text), widths = vals.flatMap((v) => WIDTHS[v].split("").map(Number));
  return { values: vals, widths, modules: widths.reduce((a, b) => a + b, 0) };
}
// прямоугольники полос в модулях: [{ x, w }]
export function code128Rects(text) {
  const { widths, modules } = code128Bars(text), rects = [];
  let x = 0;
  widths.forEach((w, i) => { if (i % 2 === 0) rects.push({ x, w }); x += w; });
  return { rects, modules };
}
export const code128Modules = (text) => code128Bars(text).modules;
