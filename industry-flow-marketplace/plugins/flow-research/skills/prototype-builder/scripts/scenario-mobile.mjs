// ШАБЛОН мобільного сценарію (A-21): справжній мобільний UI Odoo 19 — 390x844, isMobile, hasTouch, DPR 3; ≥4 кроки ролей; скриншоти + DOM-знімки + живий запис.
// Кроки — у `shoot/scenario-mobile.steps.mjs` (ті ж поля, що в scenario.steps.mjs; дотики через press() з c.mobile). Запуск: node scenario-mobile.mjs  (порт — у env BASE)  ONLY=m1,m3.
// Drill-down з дашборда на телефоні — подання з ключовими цифрами (канбан), а не вузький list. Рамку телефона малює scenes.mjs/монтаж (A-21c), не Odoo.
import { launch, clip, settle, press, dumpDom, fact, ROOT } from './rec_lib.mjs';
import fs from 'fs';
import path from 'path';
const OUT = path.join(ROOT, 'screens-mobile'); fs.mkdirSync(OUT, { recursive: true });
const ONLY = process.env.ONLY ? process.env.ONLY.split(',') : null;
const _steps = new URL('./scenario-mobile.steps.mjs', import.meta.url);
if (!fs.existsSync(_steps) && process.env.ALLOW_EXAMPLE !== '1') { console.error('FLOW_STOP: немає scenario-mobile.steps.mjs (галузевий сценарій за SALES §6); приклад — лише з ALLOW_EXAMPLE=1'); process.exit(2); }
const _mod = await import(fs.existsSync(_steps) ? './scenario-mobile.steps.mjs' : './scenario.steps.example.mjs');
const { STEPS } = _mod;
// Проходи зйомки (run_all.sh): PASS=1 — кроки, що ЗМІНЮЮТЬ дані; PASS=2 — лише читання. Списки — експорти PASS1/PASS2 файла кроків; немає обох -> FLOW_STOP.
function passList(mod, label) {
    const p = process.env.PASS; if (!p) return null;
    if (!mod.PASS1 && !mod.PASS2) { console.error(`FLOW_STOP: PASS=${p}, але ${label} не експортує PASS1/PASS2 (PLAN.md §6); мобільні кроки зазвичай лише читають -> PASS2 = ['m1', ...]`); process.exit(2); }
    return (p === '1' ? mod.PASS1 : mod.PASS2) || [];
}
const PASS_K = ONLY ? null : passList(_mod, 'scenario-mobile.steps.mjs');

if (STEPS.length < 4) console.error(`WARN: мобільних кроків ${STEPS.length} < 4 (потрібно ≥4 кроки ролей, SALES §6)`);
await launch();
let failed = false;
for (const s of STEPS) {
    const key = `m${s.n}`; if (ONLY && !ONLY.includes(key)) continue;
    if (PASS_K && !PASS_K.includes(key)) continue;
    const name = `${key}-${s.name}`;
    const ok = await clip(`mshot-${name}`, { role: s.role, mobile: true, url: s.url, plain: true, record: false }, async (c) => {
        await settle(c.page, 1200); c.mark();
        if (s.act) await s.act(c, { press });
        await settle(c.page, 800);
        await dumpDom(c.page, name, true);
        for (const f of s.facts || []) await fact(c.page, name, f.name, f.sel, { re: f.re });
        await c.page.screenshot({ path: path.join(OUT, `${name}.png`) });
    });
    if (!ok) failed = true;
}
process.exit(failed || process.exitCode ? 1 : 0);
