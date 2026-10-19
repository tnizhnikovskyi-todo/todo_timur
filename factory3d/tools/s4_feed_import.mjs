#!/usr/bin/env node
// Допоміжний скрипт інтеграційного тесту S4 (tests/test_s4_sync.py): стрічка локацій з Odoo (JSON з API-16) → імпорт у проєкт ядром.
//   node tools/s4_feed_import.mjs <вхід.json>    вхід: {locations, root?, addr?, rules?}; друкує JSON {codes, tray, zones, slots, stats}
// Справжній cellsOf із контекстом адресації площадки (S1) генерує коди комірок; Python звіряє їх із локаціями в БД.
import { readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const CORE = join(resolve(here, ".."), "core/constructor");
const load = (rel) => import(pathToFileURL(join(CORE, rel)).href);
const input = JSON.parse(readFileSync(process.argv[2], "utf8"));

const core = await load("index.js");
const { ArtifactAdapter } = await load("artifact/adapter_artifact.js");
const { runLive } = await load("live.js");
const { reindex } = await load("state.js");
const { cellsOf } = await load("cells.js");
const { normalizeAddr } = await load("addr_core.js");
const { S, E } = core;
const data = new Map();
const env = { localStorage: { getItem: (k) => (data.has(k) ? data.get(k) : null), setItem: (k, v) => data.set(k, String(v)), removeItem: (k) => data.delete(k) } };
const ad = new ArtifactAdapter({ env, getState: () => S, autosaveMs: 5 });
await ad.listSites();
const st = await ad.load("sample");
Object.assign(S, { site: st.site, layers: st.layers, slots: [], placements: [], catalog: st.catalog, settings: st.settings, versions: st.versions, rights: st.rights });
S.app.mode = "edit";
Object.assign(S.site.building, { length: 300, width: 200 });
S.site.addr = input.addr ? normalizeAddr(input.addr) : {};
S.site.parse_rules = {};
E.adapter = ad;
core.setCapabilities(ad.capabilities);
E.commit = () => {
    reindex();
    S.issues = runLive();
};
E.renderLeft = () => {};
const ly = S.layers.find((l) => l.kind === "storage");
for (const t of ["pallet_rack", "floor_spot", "floor_stack", "zone", "shelf", "cantilever"]) {
    if (!ly.slot_types.includes(t)) {
        ly.slot_types.push(t);
    }
}
S.ui.layer = ly.id;
reindex();
const res = E.importLocations(input.locations, { parseRules: input.rules || [] });
const codes = S.slots.flatMap((s) => cellsOf(s).filter((c) => !c.disabled).map((c) => c.code)).sort();
console.log(JSON.stringify({ ok: res.ok, reason: res.reason || null, codes, tray: E.trayItems().map((t) => [t.code, t.reason]), zones: S.slots.filter((s) => s.template === "zone").map((s) => s.params.title), slots: S.slots.length, stats: res.plan?.stats ? { cells: res.plan.stats.cells, racks: res.plan.stats.racks, spots: res.plan.stats.spots, skipped_usage: res.plan.stats.skipped_usage, rules: res.plan.stats.rules } : null }));
