// Готовит шрифт для PDF (W-19, I-07): DejaVu Sans Mono (Regular и Bold), урезанный до латиницы, кириллицы и нужной пунктуации,
// → src/adapters/pdffont-data.js (base64, грузится ленивым чанком). Запуск: node tools/mkfont.mjs [каталог шрифтов DejaVu]
// Лицензия DejaVu (Bitstream Vera + общественное достояние) разрешает встраивание и подмножества: src/adapters/DejaVu-LICENSE.txt.
import fs from "node:fs";
import { parseTtf, subsetTtf } from "../src/adapters/pdffont.js";

const dir = process.argv[2] || "/usr/share/fonts/truetype/dejavu";
const R = [[0x20, 0x7e], [0xa0, 0xff], [0x400, 0x45f], [0x490, 0x491], [0x2010, 0x2015], [0x2018, 0x201e], [0x2022, 0x2022], [0x2026, 0x2026], [0x2032, 0x2033], [0x20ac, 0x20ac], [0x2116, 0x2116],
  [0x2190, 0x2193], [0x2205, 0x2205], [0x2212, 0x2212], [0x2248, 0x2248], [0x2260, 0x2260], [0x2264, 0x2265], [0x2300, 0x2300], [0x25a0, 0x25a1], [0x25b2, 0x25b2], [0x25bc, 0x25bc]];
const b64 = (file) => {
  const f = parseTtf(new Uint8Array(fs.readFileSync(`${dir}/${file}`))), cmap = new Map();
  for (const [a, b] of R) for (let c = a; c <= b; c++) if (f.cmap.has(c)) cmap.set(c, f.cmap.get(c));
  const out = subsetTtf(f, [...cmap.values()], { renumber: true, cmap });
  console.error(file, cmap.size, "знаков,", out.length, "байт");
  return Buffer.from(out).toString("base64");
};
const out = `// Сгенерировано tools/mkfont.mjs (W-19): DejaVu Sans Mono, подмножество (латиница, кириллица, пунктуация), base64. Лицензия — DejaVu-LICENSE.txt. Не править руками.\n` +
  `export const MONO = "${b64("DejaVuSansMono.ttf")}";\nexport const MONO_BOLD = "${b64("DejaVuSansMono-Bold.ttf")}";\n`;
fs.writeFileSync(new URL("../src/adapters/pdffont-data.js", import.meta.url), out);
