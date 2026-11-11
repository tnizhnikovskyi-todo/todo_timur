// ШАБЛОН десктопного сценарію зрізу (A-21): скриншоти кроків SALES §6 справжніми кліками в Odoo 19, DOM-знімки для check_ui_text.py, facts.json.
// Узагальнено з еталона A-21-real: галузевий зміст (екрани, ролі, кліки) агент пише в `shoot/scenario.steps.mjs` за PLAN.md §6; тут — каркас.
// Запуск з prototype-real/shoot: node scenario.mjs   Env: BASE (порт — у BASE), DB, DEMO_EMAIL_DOMAIN, ONLY=1,2,3 (лише ці кроки; база має бути в потрібному стані), PASS=1|2 (проходи run_all.sh).
// Файл кроків експортує STEPS і PASS1 (номери кроків, що змінюють дані), PASS2 (лише читання: дашборд, звіти).
// Крок = { n, role, url, name, facts?: [{name, sel, re?}] }; дії кроку (кліки, ввід) — у `act(c)`; усе — через press()/typeIn() з rec_lib (не RPC).
import { launch, clip, goto, press, typeIn, settle, dumpDom, fact, ROOT } from './rec_lib.mjs';
import fs from 'fs';
import path from 'path';
const SHOTS = path.join(ROOT, 'screens'); fs.mkdirSync(SHOTS, { recursive: true });
const ONLY = process.env.ONLY ? process.env.ONLY.split(',').map(Number) : null;
const _steps = new URL('./scenario.steps.mjs', import.meta.url);
if (!fs.existsSync(_steps) && process.env.ALLOW_EXAMPLE !== '1') { console.error('FLOW_STOP: немає scenario.steps.mjs (галузевий сценарій за SALES §6); приклад — лише з ALLOW_EXAMPLE=1'); process.exit(2); }
const _mod = await import(fs.existsSync(_steps) ? './scenario.steps.mjs' : './scenario.steps.example.mjs');
const { STEPS } = _mod;
// Проходи зйомки (run_all.sh): PASS=1 — кроки, що ЗМІНЮЮТЬ дані; PASS=2 — лише читання. Списки — експорти PASS1/PASS2 файла кроків; немає обох -> FLOW_STOP.
function passList(mod, label) {
    const p = process.env.PASS; if (!p) return null;
    if (!mod.PASS1 && !mod.PASS2) { console.error(`FLOW_STOP: PASS=${p}, але ${label} не експортує PASS1/PASS2 (PLAN.md §6)`); process.exit(2); }
    return (p === '1' ? mod.PASS1 : mod.PASS2) || [];
}
const PASS_N = ONLY ? null : passList(_mod, 'scenario.steps.mjs');

await launch();
let failed = false;
for (const s of STEPS) {
    if (ONLY && !ONLY.includes(s.n)) continue;
    if (PASS_N && !PASS_N.includes(s.n)) continue;
    const name = `${String(s.n).padStart(2, '0')}-${s.name}`;
    // plain: оверлей відео не потрібен на скриншотах; контекст на крок (record: false — без відео, у video/rec нічого не з'являється) дає console.log із латиницею/діалогами помилок
    const ok = await clip(`shot-${name}`, { role: s.role, mobile: false, url: s.url, plain: true, record: false }, async (c) => {
        await settle(c.page, 900); c.mark();
        if (s.act) await s.act(c, { press, typeIn, goto });
        await settle(c.page, 600);
        await dumpDom(c.page, name, false);
        for (const f of s.facts || []) await fact(c.page, name, f.name, f.sel, { re: f.re });
        await c.page.screenshot({ path: path.join(SHOTS, `${name}.png`) });
    });
    if (!ok) failed = true;
}
process.exit(failed || process.exitCode ? 1 : 0);
