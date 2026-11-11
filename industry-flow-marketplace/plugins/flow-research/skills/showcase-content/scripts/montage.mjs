// Динамічний монтаж відео з ЖИВИХ записів (video/rec/*.mp4 + .json) за captions.yaml: короткі фрагменти, xfade, тиха ambient-доріжка.
// Титри, плашка ToDo й рамка телефона — прозорі PNG (Open Sans) ПОВЕРХ запису; нічого з інтерфейсу не перефарбовується. Без Odoo, без перезйомки.
// Усі числа в титрах — лише через {{fact:…}} з facts.json; розбіжність/відсутність факту, титр <1,5 с, накладання титрів — помилка (код 1).
// Використання: node montage.mjs --root <prototype-real> [full|reels|all] [--sample]    (--sample: ≈15 с + 1 кадр титра, N-18)
import fs from 'fs'; import path from 'path';
import { ROOT, REC, VIDEO, BRAND, FORMATS, positional, flag, pw, loadCaptions, loadFacts, resolveText, factVal, pieceDur, ff, probe, probeDur, X264, recMeta, tmpdir, d64, esc, rich, fontCss, die } from './lib.mjs';

if (!BRAND) die('немає brand-todo/');
const cap = loadCaptions(); const F = loadFacts(); const cards = cap.cards || {};
const slug = cap.slug || 'show'; const sample = flag('sample');
const which = positional[0] || 'all';
const errs = [], warns = [];
const E = (m) => errs.push(m), W = (m) => warns.push(m);

// ---------------------------------------------------------------- перевірка й підготовка специфікації
function prep(fkey) {
    const f = Object.values(FORMATS).find((x) => x.key === fkey); const spec = (cap.formats || {})[fkey];
    if (!spec || !Array.isArray(spec.pieces) || !spec.pieces.length) { E(`${fkey}: немає pieces`); return null; }
    let pieces = spec.pieces.map((p, i) => ({ ...p, _i: i + 1 }));
    if (sample) { let acc = 0; const out = []; for (const p of pieces) { if (acc >= 15) break; const d = pieceDur(p, cards); if (p.type !== 'card' && acc + d > 15) { const keep = Math.max(1.6, 15 - acc); const to = p.from + keep * (p.speed || 1); out.push({ ...p, to, titles: (p.titles || []).map((t) => { const at = t.at ?? 0.3; const secs = Math.min(t.secs ?? keep, keep - at - 0.3); return { ...t, at, secs }; }).filter((t) => t.secs >= 1.5) }); acc = 15; } else { out.push(p); acc += d; } } pieces = out; }
    for (const p of pieces) {
        const id = `${fkey} #${p._i}`;
        if (!['card', 'desk', 'phone', 'reel'].includes(p.type)) { E(`${id}: невідомий type «${p.type}»`); continue; }
        if (p.type === 'card') { if (!cards[p.card]) E(`${id}: немає картки «${p.card}» у cards`); else if (!fs.existsSync(path.join(REC, `card_${p.card}.mp4`))) E(`${id}: немає video/rec/card_${p.card}.mp4 — запусти rec_cards.mjs`); p.dur = pieceDur(p, cards); continue; }
        if ((p.type === 'reel') !== (fkey === 'reels_9x16')) E(`${id}: type ${p.type} не для формату ${fkey}`);
        let m; try { m = recMeta(p.clip); } catch { E(`${id}: немає запису ${p.clip}`); continue; }
        if (!fs.existsSync(path.join(REC, `${p.clip}.mp4`))) { E(`${id}: немає ${p.clip}.mp4`); continue; }
        p.speed = p.speed || 1; p.scene = p.scene || p.clip; p.m = m;
        if (!(p.to > p.from) || p.from < 0) E(`${id}: from/to некоректні`);
        if (p.to > m.dur + 0.05) E(`${id}: to=${p.to} > тривалості запису ${m.dur} (${p.clip}) — потрібна перезйомка A-21`);
        if (p.speed < 0.5 || p.speed > 3) E(`${id}: speed ${p.speed} поза 0,5–3`);
        p.dur = (p.to - p.from) / p.speed;
        if (p.dur < 1.2) E(`${id}: фрагмент ${p.dur.toFixed(2)} с < 1,2`);
        if (p.type === 'reel' && p.dur > 3.5) W(`${id}: фрагмент Reels ${p.dur.toFixed(1)} с > 3,5 (зміна плану кожні 1,5–3 с)`);
        const ts = (p.titles || []).map((t, j) => ({ ...t, _j: j })).sort((a, b) => a.at - b.at);
        let prevEnd = -1;
        for (const t of ts) {
            const tid = `${id} титр ${t._j + 1}`;
            t.at = t.at ?? 0.3; t.secs = t.secs ?? Math.max(0, p.dur - t.at - 0.3);
            if (t.secs < 1.5) E(`${tid}: ${t.secs.toFixed(2)} с < 1,5`);
            if (t.at + t.secs > p.dur + 0.01) E(`${tid}: виходить за фрагмент (${(t.at + t.secs).toFixed(2)} > ${p.dur.toFixed(2)})`);
            if (t.at < prevEnd - 0.01) E(`${tid}: накладається на попередній титр`);
            prevEnd = t.at + t.secs;
            t.kind = t.kind || 'title'; t.text = resolveText(t.text, F, p.scene); t.kicker = resolveText(t.kicker || '', F, p.scene);
            if (t.big !== undefined) { const m2 = /\{\{fact:([^}]+)\}\}/.exec(String(t.big)); if (m2 && m2[1].includes('.') && m2[1].split('.')[0] !== p.scene) E(`${tid}: цифра «${m2[1]}» не зі сцени фрагмента «${p.scene}» (бічна цифра — з поточної сцени)`); t.big = resolveText(String(t.big), F, p.scene); t.label = resolveText(t.label || '', F, p.scene); }
            if (/\d\s?(%|₴|грн|год|шт)/.test(String(t.text)) && !/\{\{(fact|pl):/.test(String(((p.titles || [])[t._j] || {}).text))) W(`${tid}: число з одиницею без {{fact:…}} — не перевіряється проти facts.json`);
        }
        p.T = ts;
        if (p.side) { p.side = { ...p.side, kicker: resolveText(p.side.kicker || '', F, p.scene), pain: resolveText(p.side.pain || '', F, p.scene) }; }
        if (p.focus) { const [x, y, w, h] = p.focus; if (![x, y, w, h].every((n) => typeof n === 'number') || w <= 0 || h <= 0) E(`${id}: focus має бути [x,y,w,h] у частках в'юпорта`); }
    }
    // гачок (0–3 с)
    const first = pieces[0];
    const isHook = first && first.type === 'card' && ((cards[first.card] || {}).tpl || first.card) === 'hook';
    if (fkey === 'reels_9x16' && first && !isHook && !sample && !(first.T || []).some((t) => t.at <= 1)) E(`${fkey}: перші 0–3 с — не гачок: постав картку tpl: hook або титр проблеми з at ≤ 1`);
    if (!sample) {
        const dir = pieces.filter((p) => p.block === 'director'); const sum = dir.reduce((s, p) => s + p.dur, 0);
        if (!dir.length) E(`${fkey}: немає блоку керівника (block: director, ≈10 с)`); else if (sum < 7 || sum > 13) W(`${fkey}: блок керівника ${sum.toFixed(1)} с (потрібно ≈10)`);
    }
    return { f, pieces };
}

// ---------------------------------------------------------------- прозорі PNG
let browser; const tmp = tmpdir(); const cache = new Map(); let seq = 0;
async function png(html, w, h, file) {
    const pg = await browser.newPage({ viewport: { width: w, height: h } });
    await pg.setContent(`<html><head><style>${fontCss()}html,body{margin:0;background:transparent;font-family:'Open Sans',sans-serif}em{font-style:normal;color:#FE5000}</style></head><body>${html}</body></html>`);
    await pg.evaluate(() => document.fonts.ready); await pg.screenshot({ path: file, omitBackground: true }); await pg.close(); return file;
}
const img = async (key, fn) => { if (!cache.has(key)) cache.set(key, await fn(path.join(tmp, `i${seq++}.png`))); return cache.get(key); };
const LOGO = () => d64(path.join(BRAND, 'todo-logo.png'), 'image/png');
const titleDesk = (k, t, top) => img(`td${k}|${t}|${top}`, (f) => png(`<div style="position:absolute;left:48px;${top ? 'top:40px' : 'bottom:46px'};max-width:1300px;background:rgba(16,24,32,.95);color:#fff;border-left:10px solid #FE5000;border-radius:12px;padding:16px 30px 18px"><div style="font-size:21px;letter-spacing:.07em;text-transform:uppercase;color:#FE5000;font-weight:700;margin-bottom:4px">${esc(k)}</div><div style="font-size:42px;font-weight:700;line-height:1.2">${rich(t)}</div></div>`, 1920, 1080, f));
const painDesk = (k, t) => img(`pd${k}|${t}`, (f) => png(`<div style="position:absolute;inset:0;background:rgba(16,24,32,.9);display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;padding:0 200px"><div style="font-size:30px;letter-spacing:.08em;text-transform:uppercase;color:#FE5000;font-weight:700;margin-bottom:22px">${esc(k)}</div><div style="font-size:70px;font-weight:700;line-height:1.18;color:#fff">${rich(t)}</div></div>`, 1920, 1080, f));
const badge = (h) => img(`bd${h}`, (f) => png(`<div style="display:inline-block;background:#fff;border-radius:${Math.round(h * .3)}px;padding:${Math.round(h * .22)}px ${Math.round(h * .38)}px;box-shadow:0 3px 14px rgba(0,0,0,.35)"><img src="${LOGO()}" style="height:${h}px;display:block"></div>`, Math.round(h * 2.56 + h * .76) + 12, Math.round(h * 1.44) + 12, f));
const titleReel = (k, t) => img(`tr${k}|${t}`, (f) => png(`<div style="position:absolute;left:0;right:0;top:340px;height:142px;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;padding:0 40px;color:#fff"><div style="font-size:32px;letter-spacing:.07em;text-transform:uppercase;color:#FE5000;font-weight:700;margin-bottom:2px">${esc(k)}</div><div style="font-size:46px;font-weight:700;line-height:1.06">${rich(t)}</div></div>`, 1080, 1920, f));
const bgReel = () => img('bgr', (f) => png(`<div style="position:absolute;inset:0;background:radial-gradient(55% 28% at 0% 55%,rgba(254,80,0,.30),transparent 70%),radial-gradient(55% 28% at 100% 80%,rgba(254,80,0,.22),transparent 70%),#101820"></div>`, 1080, 1920, f));
const phoneFrame = (w, h, b) => img(`pf${w}x${h}`, (f) => {
    const R = Math.round(w * .11) + b, r = Math.round(w * .11), Wd = w + 2 * b, H = h + 2 * b;
    const rr = (x, y, ww, hh, q) => `M${x + q},${y}H${x + ww - q}A${q},${q} 0 0 1 ${x + ww},${y + q}V${y + hh - q}A${q},${q} 0 0 1 ${x + ww - q},${y + hh}H${x + q}A${q},${q} 0 0 1 ${x},${y + hh - q}V${y + q}A${q},${q} 0 0 1 ${x + q},${y}Z`;
    return png(`<svg width="${Wd}" height="${H}" viewBox="0 0 ${Wd} ${H}" style="position:absolute;left:0;top:0"><path fill-rule="evenodd" fill="#0b0f14" d="${rr(0, 0, Wd, H, R)} ${rr(b, b, w, h, r)}"/><path fill="none" stroke="#2a333d" stroke-width="3" d="${rr(1.5, 1.5, Wd - 3, H - 3, R)}"/></svg>`, Wd, H, f);
});
const screenMask = (w, h) => img(`mk${w}x${h}`, (f) => { const r = Math.round(w * .11); return png(`<div style="position:absolute;inset:0;background:#000"><div style="position:absolute;inset:0;background:#fff;border-radius:${r}px"></div></div>`, w, h, f); });
const sidePanel = (side, t, first) => img(`sp${side.kicker}|${t.text}|${t.big}|${first}`, (f) => png(`<div style="position:absolute;left:760px;top:130px;width:1030px"><div style="font-size:34px;letter-spacing:.08em;text-transform:uppercase;color:#FE5000;font-weight:700;margin-bottom:18px">${esc(t.kicker || side.kicker || '')}</div><div style="font-size:66px;font-weight:700;line-height:1.15;color:#fff">${rich(t.text)}</div>${first && side.pain ? `<div style="font-size:34px;line-height:1.3;color:#BFBFBF;margin-top:30px">${esc(side.pain)}</div>` : ''}${t.big ? `<div style="margin-top:${first ? 36 : 70}px;display:flex;align-items:baseline;gap:26px;border-top:3px solid #FE5000;padding-top:26px"><div style="font-size:150px;font-weight:700;color:#FE5000;line-height:1">${esc(t.big)}</div><div style="font-size:36px;color:#fff;line-height:1.25;max-width:520px">${esc(t.label || '')}</div></div>` : ''}</div>`, 1920, 1080, f));

// ---------------------------------------------------------------- шматки
const out = (ext = 'mp4') => path.join(tmp, `p${String(seq++).padStart(4, '0')}.${ext}`);
async function overlayItems(p, W, H, kind) { // титри шматка -> [{file,s,e}]
    const items = [];
    for (const t of p.T) {
        let file;
        if (kind === 'reel') file = await titleReel(t.kicker, t.text); else if (kind === 'phone') file = await sidePanel(p.side || {}, t, items.length === 0); else file = t.kind === 'pain' ? await painDesk(t.kicker, t.text) : await titleDesk(t.kicker, t.text, t.top);
        items.push({ file, s: t.at, e: t.at + t.secs });
    }
    return items;
}
function overlayGraph(baseLabel, items, firstIdx) { // повертає {inputs, graph, last}
    const inputs = [], g = []; let last = baseLabel;
    items.forEach((it, i) => {
        const D = Math.max(0.5, it.e - it.s); inputs.push('-loop', '1', '-framerate', '30', '-t', D.toFixed(2), '-i', it.file); const idx = firstIdx + i;
        g.push(`[${idx}:v]format=rgba,fade=t=in:st=0:d=0.2:alpha=1,fade=t=out:st=${Math.max(0.1, D - 0.2).toFixed(2)}:d=0.2:alpha=1,setpts=PTS+${it.s.toFixed(2)}/TB[o${i}]`);
        g.push(`[${last}][o${i}]overlay=0:0:eof_action=pass[l${i}]`); last = `l${i}`;
    });
    return { inputs, graph: g.join(';'), last };
}
let zdir = 0;
async function pieceCard(p) { const o = out(); ff(['-ss', '0', '-t', p.dur.toFixed(2), '-i', path.join(REC, `card_${p.card}.mp4`), '-an', '-vf', 'setpts=PTS-STARTPTS,fps=30,format=yuv420p', ...X264, o]); return o; }
async function pieceDesk(p) {
    const o = out(), L = p.dur.toFixed(2), t = p.dur * p.speed; zdir++;
    const s0 = zdir % 2 ? 0.93 : 1.0, s1 = zdir % 2 ? 1.0 : 0.93;
    const items = await overlayItems(p, 1920, 1080, 'desk'); const b = await badge(40);
    const ov = overlayGraph('a', items, 3); const fb = p.focus && { x: p.focus[0], y: p.focus[1], w: p.focus[2], h: p.focus[3] };
    const Z = fb ? Math.max(1, Math.min(1.75, 0.8 / fb.w, 0.8 / fb.h)) : 1; // ключовий елемент ≤80% кадру: масштаб не обрізає цифри й осі
    const vf = fb ? `[0:v]setpts=(PTS-STARTPTS)/${p.speed},fps=30,scale=w='1920*(1+${(Z - 1).toFixed(3)}*min(1,t/0.7))':h=-2:eval=frame:flags=bicubic,crop=1920:1080:'max(0,min(iw-1920,${(fb.x + fb.w / 2).toFixed(3)}*iw-960))':'max(0,min(ih-1080,${(fb.y + fb.h / 2).toFixed(3)}*ih-540))'[v];`
        : `[0:v]setpts=(PTS-STARTPTS)/${p.speed},fps=30,scale=w='1920*(${s0}+(${s1}-${s0})*t/${L})':h=-2:eval=frame:flags=bicubic[v];`;
    const fc = `color=c=0x101820:s=1920x1080:r=30:d=${L}[bg];${vf}[bg][v]overlay=x='(W-w)/2':y='(H-h)/2':shortest=1[a];` + (ov.graph ? ov.graph + ';' : '') + `[${ov.last}][2:v]overlay=W-w-34:H-h-26,format=yuv420p[out]`;
    ff(['-ss', (p.m.ss + p.from).toFixed(2), '-t', t.toFixed(2), '-i', path.join(REC, `${p.clip}.mp4`), '-f', 'lavfi', '-t', '1', '-i', 'color=c=black:s=16x16', '-loop', '1', '-framerate', '30', '-t', L, '-i', b, ...ov.inputs, '-filter_complex', fc, '-map', '[out]', '-an', '-t', L, ...X264, o]);
    return o;
}
async function piecePhone(p) { // телефон у рамці зліва + бічна панель (титри-кроки) справа
    const o = out(), L = p.dur.toFixed(2), t = p.dur * p.speed; zdir++;
    const PW = 460, PH = 994, B = 22, X = 150, Y = 20;
    const fr = await phoneFrame(PW, PH, B), b = await badge(44), mk = await screenMask(PW, PH);
    const items = await overlayItems(p, 1920, 1080, 'phone'); const ov = overlayGraph('b', items, 4);
    const fc = `color=c=0x101820:s=1920x1080:r=30:d=${L}[bg];[0:v]setpts=(PTS-STARTPTS)/${p.speed},fps=30,scale=w='${PW}*(${zdir % 2 ? `1+0.045*t/${L}` : `1.045-0.045*t/${L}`})':h=-2:eval=frame:flags=bicubic,crop=${PW}:${PH}:'(iw-${PW})/2':0,format=rgba[p0];[3:v]format=gray[mk];[p0][mk]alphamerge[ph];` +
        `[bg][ph]overlay=${X + B}:${Y + B}:shortest=1[a];[a][1:v]overlay=${X}:${Y}[b0];[b0]drawbox=x=0:y=0:w=1920:h=10:color=0xFE5000:t=fill[b];` + (ov.graph ? ov.graph + ';' : '') + `[${ov.last}][2:v]overlay=W-w-34:H-h-26,format=yuv420p[out]`;
    ff(['-ss', (p.m.ss + p.from).toFixed(2), '-t', t.toFixed(2), '-i', path.join(REC, `${p.clip}.mp4`), '-i', fr, '-i', b, '-loop', '1', '-framerate', '30', '-t', L, '-i', mk, ...ov.inputs, '-filter_complex', fc, '-map', '[out]', '-an', '-t', L, ...X264, o]);
    return o;
}
async function pieceReel(p) { // телефон 904×1155 (≈86 % ширини кадру) у безпечній зоні, титр над ним, «камера» всередині екрана
    const o = out(), L = p.dur.toFixed(2), t = p.dur * p.speed; zdir++;
    const PW = 904, PH = 1155, B = 12, X = (1080 - PW - 2 * B) / 2, Y = 485;
    const fr = await phoneFrame(PW, PH, B), b = await badge(52), bg = await bgReel(), mk = await screenMask(PW, PH);
    const items = await overlayItems(p, 1080, 1920, 'reel'); const ov = overlayGraph('c', items, 5); const fb = p.focus && { x: p.focus[0], y: p.focus[1], w: p.focus[2], h: p.focus[3] };
    const Z = fb ? Math.max(1, Math.min(1.8, 0.86 / Math.max(0.05, fb.w))) : 1, cx = fb ? fb.x + fb.w / 2 : 0.5, cy = fb ? fb.y + fb.h / 2 : 0.3;
    const ze = `(1+${(Z - 1).toFixed(3)}*min(1,t/0.7))*(1+0.035*t/${L})`; // повільний дрейф: кадр ніколи не нерухомий
    const fc = `[0:v]setpts=(PTS-STARTPTS)/${p.speed},fps=30,scale=w='${PW}*${ze}':h=-2:eval=frame:flags=bicubic,crop=${PW}:${PH}:'max(0,min(iw-${PW},${cx.toFixed(3)}*iw-${PW / 2}))':'max(0,min(ih-${PH},${cy.toFixed(3)}*ih-${PH / 2}))',format=rgba[p0];[3:v]format=gray[mk];[p0][mk]alphamerge[ph];` +
        `[4:v]format=rgb24[bg];[bg][ph]overlay=${X + B}:${Y + B}:shortest=1[a];[a][1:v]overlay=${X}:${Y}[b];[b]drawbox=x=0:y=0:w=1080:h=10:color=0xFE5000:t=fill[c];` + (ov.graph ? ov.graph + ';' : '') + `[${ov.last}][2:v]overlay=(W-w)/2:262,format=yuv420p[out]`;
    ff(['-ss', (p.m.ss + p.from).toFixed(2), '-t', t.toFixed(2), '-i', path.join(REC, `${p.clip}.mp4`), '-i', fr, '-i', b, '-loop', '1', '-framerate', '30', '-t', L, '-i', mk, '-loop', '1', '-framerate', '30', '-t', L, '-i', bg, ...ov.inputs, '-filter_complex', fc, '-map', '[out]', '-an', '-t', L, ...X264, o]);
    return o;
}
// ---------------------------------------------------------------- склейка xfade + тиха доріжка
const TR = ['fade', 'slideleft', 'smoothleft', 'wipeleft', 'fade', 'circleopen', 'slideright', 'smoothright'];
function chain(files, dd, outFile, mixed) {
    if (files.length === 1) { fs_copy(files[0], outFile); return probeDur(files[0]); }
    const durs = files.map(probeDur); const inp = files.flatMap((f) => ['-i', f]); let fc = '', acc = durs[0], last = '[0:v]';
    for (let i = 1; i < files.length; i++) { const lab = i === files.length - 1 ? '[v]' : `[x${i}]`; fc += `${last}[${i}:v]xfade=transition=${mixed ? TR[i % TR.length] : 'fade'}:duration=${dd}:offset=${(acc - dd).toFixed(3)}${lab};`; acc += durs[i] - dd; last = lab; }
    ff([...inp, '-filter_complex', fc.slice(0, -1), '-map', '[v]', '-c:v', 'libx264', '-crf', '19', '-preset', 'medium', '-pix_fmt', 'yuv420p', '-r', '30', outFile]); return acc;
}
const fs_copy = (a, b) => fs.copyFileSync(a, b);
function finish(silent, target) {
    const dur = probeDur(silent), aud = out('m4a'); const tone = (f, a) => `${a}*sin(2*PI*${f}*t)`;
    ff(['-f', 'lavfi', '-i', `aevalsrc='(0.55+0.45*sin(2*PI*0.08*t))*(${tone(110, 0.5)}+${tone(164.81, 0.35)}+${tone(220, 0.3)}+${tone(261.63, 0.25)}+${tone(329.63, 0.15)})':s=44100:d=${dur.toFixed(2)}`, '-af', `lowpass=f=1800,volume=0.16,afade=t=in:d=1.5,afade=t=out:st=${Math.max(0, dur - 2).toFixed(1)}:d=2`, '-c:a', 'aac', '-b:a', '128k', aud]);
    ff(['-i', silent, '-i', aud, '-c:v', 'copy', '-c:a', 'copy', '-shortest', '-movflags', '+faststart', target]); console.log('готово', path.relative(process.cwd(), target), dur.toFixed(1), 'с');
}

// ---------------------------------------------------------------- запуск
const plans = [];
for (const k of which === 'all' ? ['full', 'reels'] : [which]) { if (!FORMATS[k]) die(`невідомий формат «${k}» (full|reels|all)`); if (!(cap.formats || {})[FORMATS[k].key]) { if (which === 'all') continue; E(`немає formats.${FORMATS[k].key}`); continue; } const r = prep(FORMATS[k].key); if (r) plans.push({ k, ...r }); }
if (warns.length) console.log('ПОПЕРЕДЖЕННЯ:\n' + warns.map((x) => '  ' + x).join('\n'));
if (errs.length) { console.error('ПОМИЛКИ специфікації (відео не збирається):\n' + errs.map((x) => '  ' + x).join('\n')); process.exit(1); }
if (!plans.length) die('нічого збирати: у captions.yaml немає formats.video_16x9 / reels_9x16');
fs.mkdirSync(VIDEO, { recursive: true });
browser = await pw().chromium.launch();
for (const pl of plans) {
    const files = [];
    for (const p of pl.pieces) files.push(p.type === 'card' ? await pieceCard(p) : p.type === 'desk' ? await pieceDesk(p) : p.type === 'phone' ? await piecePhone(p) : await pieceReel(p));
    const silent = path.join(tmp, `${pl.k}_silent.mp4`); chain(files, pl.k === 'reels' ? 0.25 : 0.5, silent, pl.k === 'full');
    const name = `${sample ? 'sample-' : ''}${slug}-${pl.f.suffix}.mp4`; const target = path.join(VIDEO, name); finish(silent, target);
    if (sample) { // 1 кадр титра для приймання зразка
        const first = pl.pieces.map((p, i) => ({ p, i })).find((x) => (x.p.T || []).length); let off = 0; if (first) { for (let j = 0; j < first.i; j++) off += pl.pieces[j].dur - (pl.k === 'reels' ? 0.25 : 0.5); const tt = first.p.T[0]; ff(['-ss', (off + tt.at + 0.8).toFixed(2), '-i', target, '-frames:v', '1', path.join(VIDEO, `sample-title-${pl.f.suffix}.png`)]); console.log('кадр титра ->', `video/sample-title-${pl.f.suffix}.png`); }
    }
}
await browser.close(); fs.rmSync(tmp, { recursive: true, force: true });
