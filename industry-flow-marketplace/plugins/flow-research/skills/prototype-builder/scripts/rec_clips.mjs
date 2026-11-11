// ШАБЛОН живих записів: безперервний запис сценарію (CDP-screencast) з кліками, набором, прокруткою, zoom/count-up; титри НЕ малюються (їх накладає A-21c).
// Результат: video/rec/<кліп>.mp4 + <кліп>.json {ss, dur, ok, events:[title|off|pain|focus]} -> handoff-a21c.md. Запуск: node rec_clips.mjs D_dash M_dash ...
// Кліпи — у `shoot/clips.mjs` (export const CLIPS = { async D_dash() { return clip('D_dash', {role, url}, async (c) => {...}); } }); приклад патерну — clips.example.mjs.
// Проходи (run_all.sh, PASS=1|2): clips.mjs експортує PASS1 (кліпи, що змінюють дані) і PASS2 (лише читання; кліпи дашборда — першими в списку, після fix_dates), щоб цифри
// збігались зі скриншотами й facts.json; перед повною зйомкою — build_db.sh (перестворення бази).
import { launch } from './rec_lib.mjs';
import fs from 'fs';
const _steps = new URL('./clips.mjs', import.meta.url);
if (!fs.existsSync(_steps) && process.env.ALLOW_EXAMPLE !== '1') { console.error('FLOW_STOP: немає clips.mjs (галузевий сценарій за SALES §6); приклад — лише з ALLOW_EXAMPLE=1'); process.exit(2); }
const _mod = await import(fs.existsSync(_steps) ? './clips.mjs' : './clips.example.mjs');
const { CLIPS } = _mod;
// Проходи зйомки (run_all.sh): PASS=1 — кліпи, що ЗМІНЮЮТЬ дані; PASS=2 — лише читання. Списки — експорти PASS1/PASS2 файла кроків; немає обох -> FLOW_STOP.
function passList(mod, label) {
    const p = process.env.PASS; if (!p) return null;
    if (!mod.PASS1 && !mod.PASS2) { console.error(`FLOW_STOP: PASS=${p}, але ${label} не експортує PASS1/PASS2 (PLAN.md §6)`); process.exit(2); }
    return (p === '1' ? mod.PASS1 : mod.PASS2) || [];
}
const names = process.argv.slice(2).length ? process.argv.slice(2) : (passList(_mod, 'clips.mjs') ?? Object.keys(CLIPS));
await launch();
let bad = 0;
for (const n of names) {
    if (!CLIPS[n]) { console.error('немає кліпа', n); bad++; continue; }
    if (!(await CLIPS[n]())) bad++;
}
process.exit(bad || process.exitCode ? 1 : 0);
