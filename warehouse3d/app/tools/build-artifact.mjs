// Публикация в артефакт claude.ai (W-23): после `vite build` делает из dist/index.html страницу без doctype / html / head / body
// (dist/artifact.html) и список файлов для публикации (dist/artifact-files.json: путь на странице → путь от каталога app/).
// Использование: node tools/build-artifact.mjs  (npm run build:artifact)
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const APP = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const DIST = path.join(APP, "dist");
const TITLE = "Конструктор складу";

export function toArtifactHtml(html) {
  const head = /<head[^>]*>([\s\S]*?)<\/head>/i.exec(html)?.[1] ?? "";
  const body = /<body[^>]*>([\s\S]*?)<\/body>/i.exec(html)?.[1] ?? "";
  const keep = [];
  for (const m of head.matchAll(/<(link|script)\b[^>]*>(?:\s*<\/script>)?/gi)) {
    const t = m[0];
    if (/\b(?:href|src)="(?:https?:)?\/\//i.test(t)) throw new Error(`сторонний адрес запрещён: ${t}`);
    if (/<link\b[^>]*rel="modulepreload"/i.test(t) || /<link\b[^>]*rel="stylesheet"/i.test(t) || /<script\b/i.test(t)) keep.push(t);
  }
  const styles = keep.filter((t) => /^<link/i.test(t) && /stylesheet/i.test(t));
  const rest = keep.filter((t) => !styles.includes(t));
  // порядок: title, стили, затем содержимое страницы; скрипты и preload — после
  const bodyScripts = [...body.matchAll(/<script\b[^>]*>(?:\s*<\/script>)?/gi)].map((m) => m[0]);
  const bodyHtml = body.replace(/<script\b[^>]*>(?:\s*<\/script>)?/gi, "").trim();
  const out = [`<title>${TITLE}</title>`, ...styles, ...rest.filter((t) => /^<link/i.test(t)), bodyHtml, ...rest.filter((t) => /^<script/i.test(t)), ...bodyScripts]
    .filter(Boolean).join("\n") + "\n";
  return out;
}

function walk(dir) {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((e) => (e.isDirectory() ? walk(path.join(dir, e.name)) : [path.join(dir, e.name)]));
}

export function filesList() {
  const files = {};
  for (const f of walk(path.join(DIST, "assets")).sort()) {
    const rel = path.relative(DIST, f).split(path.sep).join("/");
    files[`./${rel}`] = `dist/${rel}`;
  }
  return files;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const html = toArtifactHtml(fs.readFileSync(path.join(DIST, "index.html"), "utf8"));
  if (/<\/?(?:!doctype|html|head|body)\b/i.test(html)) throw new Error("в artifact.html остались doctype / html / head / body");
  fs.writeFileSync(path.join(DIST, "artifact.html"), html);
  const files = filesList();
  fs.writeFileSync(path.join(DIST, "artifact-files.json"), JSON.stringify(files, null, 2) + "\n");
  const total = Object.values(files).reduce((s, p) => s + fs.statSync(path.join(APP, p)).size, 0);
  console.log(`artifact.html ${html.length} Б; artifact-files.json: ${Object.keys(files).length} файлов, ${(total / 1024).toFixed(0)} КБ`);
}
