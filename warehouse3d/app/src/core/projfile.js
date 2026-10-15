// Файл проекта .whproj.json (W-10, D-09, A9): проект v2 целиком — склады, слои правок (в том числе здание, адресация, типы), без общей библиотеки.
//   { format: "whproj", v: 1, exported_at, app, project }   v — версия обёртки (миграции файла), project.schema — версия проекта (миграции project.js).
// Снимки складов, которые хост выдаёт по ссылке baseRef (opts.bases), кладутся в файл (base), если ссылка не из числа встроенных — иначе на другом компьютере склад был бы пуст.
// Импорт проверяет схему и приводит проект к текущей; ошибка — { ok: false, error: { key, params } } (ключи словаря). Без DOM.
import { PROJECT_SCHEMA, createProject, migrateProject } from "./project.js";
import { clone } from "./types.js";
import { DEMO_REFS } from "./demo.js";
import { SYNTHETIC_REF } from "./synthetic.js";

export const PROJ_FORMAT = "whproj";
export const PROJ_VERSION = 1;
export const PROJ_EXT = ".whproj.json";
const BUILTIN_REFS = new Set([...Object.values(DEMO_REFS), SYNTHETIC_REF]);

// Проект → объект файла. Встраивает снимки внешних складов (bases: { baseRef: снимок }), если они доступны
export function exportProject(project, { bases = {}, exportedAt = "" } = {}) {
  const p = clone(project);
  for (const w of p.warehouses) if (!w.base && w.baseRef && !BUILTIN_REFS.has(w.baseRef) && bases[w.baseRef]) w.base = clone(bases[w.baseRef]);
  return { format: PROJ_FORMAT, v: PROJ_VERSION, exported_at: exportedAt, app: "warehouse3d", project: p };
}
export const serializeProject = (project, opts) => JSON.stringify(exportProject(project, opts));
// Имя файла только из латиницы (кириллицу некоторые браузеры в имени скачивания заменяют на «download»): украинские и русские буквы транслитерируются
const TR = { а: "a", б: "b", в: "v", г: "h", ґ: "g", д: "d", е: "e", є: "ie", ж: "zh", з: "z", и: "y", і: "i", ї: "i", й: "i", к: "k", л: "l", м: "m", н: "n", о: "o", п: "p", р: "r", с: "s", т: "t", у: "u", ф: "f", х: "kh",
  ц: "ts", ч: "ch", ш: "sh", щ: "shch", ь: "", ю: "iu", я: "ia", ы: "y", э: "e", ъ: "" };
export const asciiName = (s) => String(s ?? "").toLowerCase() === "" ? "" : [...String(s)].map((c) => { const l = c.toLowerCase(), t = TR[l]; return t == null ? c : c === l ? t : t.charAt(0).toUpperCase() + t.slice(1); }).join("").replace(/[^A-Za-z0-9._-]+/g, "_").replace(/^_+|_+$/g, "");
export const projectFileName = (project, ext = PROJ_EXT) => `${asciiName(project.name || project.id) || asciiName(project.id) || "project"}${ext}`;

const bad = (key, params = {}) => ({ ok: false, error: { key, params } });
const obj = (x) => !!x && typeof x === "object" && !Array.isArray(x);
const safeId = (id) => String(id ?? "").replace(/[^\w.-]+/g, "-").replace(/\.broken-/g, "-").slice(0, 80);

// Миграции обёртки файла: версия → функция, поднимающая объект на следующую версию (пока одна версия)
const FILE_MIGRATIONS = {};

// Текст файла → { ok: true, project, migrated } | { ok: false, error }. Принимает и «голый» проект (schema: 2) и проект прежнего формата (v1 правок прототипа)
export function parseProjectFile(text) {
  let raw;
  try { raw = JSON.parse(typeof text === "string" ? text.replace(/^﻿/, "") : text); } catch (e) { return bad("pf.notJson"); }
  if (!obj(raw)) return bad("pf.notProject");
  let proj = raw, migrated = false;
  if (raw.format != null) {
    if (raw.format !== PROJ_FORMAT || !obj(raw.project)) return bad("pf.notProject");
    let v = raw.v == null ? 1 : raw.v;
    if (!Number.isInteger(v) || v < 1) return bad("pf.notProject");
    if (v > PROJ_VERSION) return bad("pf.newer", { v });
    for (; v < PROJ_VERSION; v++) { const f = FILE_MIGRATIONS[v]; if (!f) return bad("pf.notProject"); raw = f(raw); migrated = true; }
    proj = raw.project;
  }
  if (typeof proj.schema === "number" && proj.schema > PROJECT_SCHEMA) return bad("pf.newer", { v: proj.schema });
  if (proj.schema === PROJECT_SCHEMA) {
    if (!Array.isArray(proj.warehouses)) return bad("pf.noWarehouses");
    const ids = new Set();
    for (const w of proj.warehouses) {
      if (!obj(w)) return bad("pf.badWarehouse");
      if (w.saved != null && !obj(w.saved)) return bad("pf.badWarehouse", { code: w.code || "" });
      if (w.pending != null && !Array.isArray(w.pending)) return bad("pf.badWarehouse", { code: w.code || "" });
      if (w.base != null && !(obj(w.base) && obj(w.base.locations))) return bad("pf.badWarehouse", { code: w.code || "" });
      if (w.id != null) { if (ids.has(w.id)) return bad("pf.dupWarehouse", { id: w.id }); ids.add(w.id); }
    }
  } else migrated = true;
  const p = migrateProject(proj);
  if (!p) return bad("pf.notProject");
  if (!p.warehouses.length) return bad("pf.noWarehouses");
  p.id = safeId(p.id) || "project";
  return { ok: true, project: p, migrated };
}

// Копия проекта под новым id (<id>-copy, <id>-copy-2, …, которого нет в existing) и именем с припиской word
export function copyProject(project, existing = [], word = "copy") {
  const base = `${project.id}-copy`; let id = base;
  for (let i = 2; existing.includes(id); i++) id = `${base}-${i}`;
  return createProject({ ...clone(project), id, name: `${project.name || project.id} (${word})` });
}
