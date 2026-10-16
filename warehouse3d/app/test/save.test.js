import test from "node:test";
import assert from "node:assert/strict";
import { saveFile } from "../src/view/save.js";
import { toArtifactHtml } from "../tools/build-artifact.mjs";

// фейковая среда: window.claude (с downloads или без) и document для запасного пути через ссылку
function env(claude) {
  const clicks = [];
  globalThis.window = claude === undefined ? {} : { claude };
  globalThis.document = {
    createElement: () => { const a = { click: () => clicks.push(a.download), remove() {} }; return a; },
    body: { append() {} },
  };
  return clicks;
}
const err = (code) => Object.assign(new Error(code), { code });
test.afterEach(() => { delete globalThis.window; delete globalThis.document; });

test("saveFile: downloads доступен — файл уходит через save, ссылка не используется", async () => {
  const calls = [], clicks = env({ use: async (n) => (n === "downloads" ? { save: async (r) => { calls.push(r); return { status: "saved" }; } } : null) });
  assert.equal(await saveFile("a.csv", "x;y", "text/csv"), "saved");
  assert.equal(calls.length, 1); assert.equal(calls[0].filename, "a.csv"); assert.ok(calls[0].data instanceof Blob);
  assert.equal(clicks.length, 0);
});

test("saveFile: нет window.claude или use вернул null — запасной путь через ссылку", async () => {
  let clicks = env(undefined);
  assert.equal(await saveFile("a.csv", "x", "text/csv"), "saved"); assert.deepEqual(clicks, ["a.csv"]);
  clicks = env({ use: async () => null });
  assert.equal(await saveFile("b.pdf", "x", "application/pdf"), "saved"); assert.deepEqual(clicks, ["b.pdf"]);
  clicks = env({ use: async () => { throw err("unavailable"); } });
  assert.equal(await saveFile("c.json", "{}", "application/json"), "saved"); assert.deepEqual(clicks, ["c.json"]);
});

test("saveFile: отказ пользователя — тихо, без ссылки; unavailable при save — запасной путь; прочие ошибки — исключение", async () => {
  let clicks = env({ use: async () => ({ save: async () => { throw err("declined"); } }) });
  assert.equal(await saveFile("a.csv", "x", "text/csv"), "declined"); assert.equal(clicks.length, 0);
  clicks = env({ use: async () => ({ save: async () => { throw err("unavailable"); } }) });
  assert.equal(await saveFile("a.csv", "x", "text/csv"), "saved"); assert.deepEqual(clicks, ["a.csv"]);
  clicks = env({ use: async () => ({ save: async () => { throw err("too_large"); } }) });
  await assert.rejects(saveFile("a.csv", "x", "text/csv"), { code: "too_large" }); assert.equal(clicks.length, 0);
});

test("saveFile: расширение вне списка платформы (.zpl) — повтор как .txt", async () => {
  const names = [];
  env({ use: async () => ({ save: async (r) => { names.push(r.filename); if (r.filename.endsWith(".zpl")) throw err("rejected_extension"); return { status: "saved" }; } }) });
  assert.equal(await saveFile("labels.zpl", "^XA", "text/plain"), "saved");
  assert.deepEqual(names, ["labels.zpl", "labels.zpl.txt"]);
});

test("toArtifactHtml: без doctype / html / head / body, title и относительные пути сохранены", () => {
  const src = `<!doctype html><html lang="uk"><head><meta charset="utf-8"><meta name="viewport" content="x"><title>Warehouse 3D</title>
<script type="module" crossorigin src="./assets/i.js"></script><link rel="modulepreload" href="./assets/a.js"><link rel="stylesheet" href="./assets/i.css"></head>
<body><div id="app"></div></body></html>`;
  const out = toArtifactHtml(src);
  assert.ok(out.startsWith("<title>Конструктор складу</title>\n<link rel=\"stylesheet\""));
  assert.ok(out.includes('<div id="app"></div>') && out.includes('src="./assets/i.js"') && out.includes('href="./assets/a.js"'));
  assert.doesNotMatch(out, /<\/?(?:!doctype|html|head|body|meta)\b/i);
  assert.throws(() => toArtifactHtml(src.replace("./assets/i.css", "https://cdn.x/i.css")), /сторонний/);
});
