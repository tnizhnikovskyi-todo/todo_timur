// Один самодостаточный HTML (W-23): после `vite build --mode single` (один бандл, data.json как data: URL) кладёт CSS и JS прямо в страницу,
// чтобы она открывалась двойным кликом (file://, без сервера). Выход — dist-single/konstruktor-skladu.html.
// Использование: node tools/build-single.mjs  (npm run build:single)
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const APP = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const OUT = path.join(APP, "dist-single");

export function inlineAll(html, read) {
  // </script и <!-- внутри inline-скрипта ломают разбор страницы
  const safe = (js) => js.replace(/<\/(script)/gi, "<\\/$1").replace(/<!--/g, "<\\!--");
  let js = "";
  html = html.replace(/<link\b[^>]*rel="stylesheet"[^>]*>/gi, (t) => `<style>\n${read(/href="([^"]+)"/.exec(t)[1]).replace(/<\/style/gi, "<\\/style")}\n</style>`);
  html = html.replace(/<link\b[^>]*rel="modulepreload"[^>]*>\s*/gi, "");
  html = html.replace(/<script\b[^>]*src="([^"]+)"[^>]*>\s*<\/script>\s*/gi, (t, src) => { js += (js ? "\n" : "") + read(src); return ""; });
  if (!js) throw new Error("в index.html нет скрипта");
  const ext = /(?:src|href)="(?:https?:)?\/\/[^"]+"/i.exec(html);
  if (ext) throw new Error(`внешний адрес: ${ext[0]}`);
  html = html.replace(/<\/body>/i, () => `<script type="module">\n${safe(js)}\n</script>\n</body>`);
  return html;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const read = (p) => fs.readFileSync(path.join(OUT, p), "utf8");
  const html = inlineAll(read("index.html"), read);
  const file = path.join(OUT, "konstruktor-skladu.html");
  fs.writeFileSync(file, html);
  console.log(`${file}: ${(Buffer.byteLength(html) / 1024).toFixed(0)} КБ`);
}
