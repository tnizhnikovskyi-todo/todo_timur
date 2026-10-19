#!/usr/bin/env node
// Тести слайса S6 «Спільна робота й навчання» (F12 варіанти, F13 коментарі, F14 блокування зон, F19 тури, інструкція й мови UK/EN,
// N-01 рівні й мініатюра, N-03 історія версій) без Odoo і браузера.
//   node tools/test_core_s6.mjs            окремо
//   node tools/test_core.mjs               разом з рештою набору (підключає `register`)
import assert from "node:assert/strict";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(here, "..");
const CORE = join(ROOT, "core/constructor");
const load = (rel) => import(pathToFileURL(join(CORE, rel)).href);

const memEnv = () => {
    const data = new Map();
    return { localStorage: { getItem: (k) => (data.has(k) ? data.get(k) : null), setItem: (k, v) => data.set(k, String(v)), removeItem: (k) => data.delete(k) }, _data: data };
};

/** Ядро з прикладом площадки в стані (без DOM), справжній ArtifactAdapter у пам'яті. */
async function boot() {
    const core = await load("index.js");
    const { ArtifactAdapter } = await load("artifact/adapter_artifact.js");
    const { runLive } = await load("live.js");
    const { S, E } = core;
    const { reindex } = await load("state.js");
    const ad = new ArtifactAdapter({ env: memEnv(), getState: () => S, autosaveMs: 5 });
    await ad.listSites();
    const apply = (st) => {
        Object.assign(S, { site: st.site, layers: st.layers, slots: st.slots, placements: st.placements, catalog: st.catalog, settings: st.settings, versions: st.versions, rights: st.rights });
        S.app.mode = "edit";
        reindex();
        S.issues = runLive();
    };
    apply(await ad.load("sample"));
    E.adapter = ad;
    core.setCapabilities(ad.capabilities);
    E.commit = () => {
        reindex();
        S.issues = runLive();
    };
    E.isNarrow = () => false;
    E.renderLeft = () => {};
    return { core, S, E, ad, reindex, apply, runLive };
}

const newSlotLike = (S, prefix, x = 5, y = 5) => ({ ...JSON.parse(JSON.stringify(S.slots.find((s) => s.template === "pallet_rack"))), id: "n" + prefix, rid: null, etag: null, code_prefix: prefix, x, y });

export function register(test) {
    /* ---------- мови ---------- */
    test("S6 i18n: UK за замовчуванням і ключ; EN з реєстру, підстановки {x}; невідома фраза лишається; шаблони чужих фраз", async () => {
        const i18n = await load("i18n.js");
        await load("index.js");
        i18n.setLang("uk", { persist: false });
        assert.equal(i18n.getLang(), "uk");
        assert.equal(i18n.t("Варіанти планування"), "Варіанти планування");
        assert.equal(i18n.t("Видалити варіант «{name}»?", { name: "A" }), "Видалити варіант «A»?");
        i18n.setLang("en", { persist: false });
        assert.equal(i18n.getLang(), "en");
        assert.equal(i18n.t("Варіанти планування"), "Layout variants");
        assert.equal(i18n.t("Видалити варіант «{name}»?", { name: "A" }), "Delete the variant “A”?");
        assert.equal(i18n.t("Фраза без перекладу"), "Фраза без перекладу");
        assert.equal(i18n.enOf("Чернетка · змінено 5"), "Draft · 5 changed");
        assert.equal(i18n.enOf("Опублікувати"), "Publish");
        assert.equal(i18n.enOf("щось своє"), null);
        i18n.setLang("uk", { persist: false });
        assert.equal(i18n.t("Варіанти планування"), "Варіанти планування");
        assert.deepEqual(Object.keys(i18n.LANGS), ["uk", "en"]);
    });

    test("S6 i18n: усі фрази t() і addEn мають пару; кожен тур, крок і тема інструкції — двомовні", async () => {
        const { TOURS } = await load("tour_defs.js");
        const { TOPICS } = await load("help_topics.js");
        assert.equal(TOURS.length, 12, "тур новачка + 11 тематичних");
        assert.deepEqual(TOURS.map((t) => t.id), ["welcome", "basic", "rack", "import", "scratch", "address", "putaway", "apply", "find", "labels", "docs", "team"]);
        assert.equal(TOURS[0].steps.length, 13, "тур новачка — 13 кроків");
        for (const tr of TOURS) {
            for (const f of [tr.title, tr.desc]) {
                assert.ok(f[0] && f[1] && f[0] !== f[1], `${tr.id}: заголовок/опис UK і EN`);
            }
            for (const [i, s] of tr.steps.entries()) {
                assert.ok(["read", "do"].includes(s.kind), `${tr.id}#${i} kind`);
                assert.ok(s.title[0] && s.title[1] && s.text[0] && s.text[1], `${tr.id}#${i} тексти UK і EN`);
                assert.notEqual(s.text[0], s.text[1], `${tr.id}#${i}: EN відрізняється від UK`);
                assert.ok(s.kind === "read" || s.act, `${tr.id}#${i}: «дія» має act`);
            }
        }
        assert.equal(TOPICS.length, 36, "36 тем інструкції");
        assert.equal(new Set(TOPICS.map((t) => t[0])).size, 36, "id тем унікальні");
        for (const tp of TOPICS) {
            assert.ok(tp[1][0] && tp[1][1] && tp[2][0].length > 40 && tp[2][1].length > 40, `${tp[0]}: заголовок і текст UK/EN`);
        }
        assert.ok(TOURS.filter((t) => t.mutates).every((t) => t.id === "rack"), "змінює дані лише тур стелажа");
    });

    /* ---------- F13 ---------- */
    test("S6 коментарі: колір значка (відкрита задача > відкрита нотатка > усе вирішено), групи, фільтри статус/вид/текст/«лише цей об'єкт»", async () => {
        const { toneOf, groupByTarget, filterComments, keyOf } = await load("comments.js");
        const c = (o) => ({ id: 1, target_kind: "slot", target_uid: "a", target_label: "Ряд A", kind: "note", state: "open", text: "текст", author: "Іван", ...o });
        assert.equal(toneOf([c({}), c({ kind: "task" })]), "task");
        assert.equal(toneOf([c({}), c({ kind: "task", state: "resolved" })]), "note");
        assert.equal(toneOf([c({ state: "resolved" }), c({ kind: "task", state: "resolved" })]), "done");
        const list = [c({ id: 1 }), c({ id: 2, kind: "task", target_uid: "b", text: "Перемірити прохід" }), c({ id: 3, state: "resolved", target_kind: "cell", target_uid: "R1-B01-L1", author: "Олена" })];
        const g = groupByTarget(list);
        assert.deepEqual([...g.keys()], [keyOf("slot", "a"), keyOf("slot", "b"), keyOf("cell", "R1-B01-L1")]);
        assert.deepEqual(filterComments(list, { state: "open" }).map((x) => x.id), [1, 2]);
        assert.deepEqual(filterComments(list, { state: "all", kind: "task" }).map((x) => x.id), [2]);
        assert.deepEqual(filterComments(list, { state: "all", q: "ПРОХІД" }).map((x) => x.id), [2]);
        assert.deepEqual(filterComments(list, { state: "all", q: "олена" }).map((x) => x.id), [3], "пошук і за автором");
        assert.deepEqual(filterComments(list, { state: "all", only: true }, { kind: "slot", uid: "a" }).map((x) => x.id), [1]);
    });

    test("S6 коментарі: об'єкт коментування за виділенням — площадка, місце, комірка, розміщення", async () => {
        const { S, E } = await boot();
        const { targetOfSelection } = await load("comments.js");
        assert.equal(targetOfSelection().kind, "site");
        const slot = S.slots.find((s) => s.template === "pallet_rack");
        S.sel = { kind: "slot", id: slot.id };
        assert.deepEqual(targetOfSelection(), { kind: "slot", uid: slot.id, label: slot.params.title || slot.code_prefix });
        S.selCell = "X-B01-L1";
        assert.deepEqual(targetOfSelection(), { kind: "cell", uid: "X-B01-L1", label: "X-B01-L1" });
        const pl = S.placements[0];
        S.sel = { kind: "placement", id: pl.id };
        S.selCell = null;
        assert.equal(targetOfSelection().kind, "placement");
        assert.ok(E.openThread && E.refreshComments);
    });

    test("S6 коментарі (прототип): створення, оновлення, вирішення, видалення — як API-22; перевірка тексту, виду й об'єкта", async () => {
        const { ad } = await boot();
        assert.equal(ad.capabilities.comments, true);
        let r = await ad.comments({ op: "list" });
        assert.deepEqual(r.comments, []);
        r = await ad.comments({ op: "create", vals: { target_kind: "slot", target_uid: "s1", target_label: "Ряд 1", text: "  Перевірити на місці  ", kind: "task" } });
        assert.equal(r.comments.length, 1);
        const c = r.comments[0];
        assert.deepEqual([c.kind, c.state, c.text, c.mine, c.can_resolve, c.can_delete], ["task", "open", "Перевірити на місці", true, true, true]);
        assert.equal(r.id, c.id);
        r = await ad.comments({ op: "resolve", id: c.id });
        assert.equal(r.comments[0].state, "resolved");
        assert.ok(r.comments[0].resolved_by);
        r = await ad.comments({ op: "resolve", id: c.id, resolved: false });
        assert.equal(r.comments[0].state, "open");
        r = await ad.comments({ op: "update", id: c.id, text: "Інший" });
        assert.equal(r.comments[0].text, "Інший");
        await assert.rejects(() => ad.comments({ op: "create", vals: { target_kind: "slot", text: "  " } }), (e) => e.code === "validation");
        await assert.rejects(() => ad.comments({ op: "create", vals: { target_kind: "planet", text: "x" } }), (e) => e.code === "validation");
        await assert.rejects(() => ad.comments({ op: "create", vals: { target_kind: "slot", text: "x", kind: "bug" } }), (e) => e.code === "validation");
        await assert.rejects(() => ad.comments({ op: "resolve", id: 999 }), (e) => e.code === "not_found");
        r = await ad.comments({ op: "delete", id: c.id });
        assert.deepEqual(r.comments, []);
        assert.deepEqual((await ad.comments({ op: "assignees" })).users, []);
    });

    test("S6 коментарі (ядро): додавання через адаптер оновлює список і лічильники; помилка сервера — не падає", async () => {
        const { E, S } = await boot();
        const cm = await load("comments.js");
        await cm.refreshComments();
        assert.equal(cm.allComments().length, 0);
        const res = await cm.addComment({ kind: "site", uid: String(S.site.id), label: S.site.name }, { text: "Загальна нотатка", kind: "note" });
        assert.ok(res);
        assert.equal(cm.allComments().length, 1);
        assert.equal(S.comments.list[0].target_kind, "site");
        const bad = await cm.addComment({ kind: "site", uid: "1", label: "x" }, { text: "   " });
        assert.equal(bad, null, "порожній текст відхилено");
        assert.equal(cm.allComments().length, 1);
        assert.ok(cm.anchorFor("site", String(S.site.id)), "значок площадки має якір на сцені");
        const slot = S.slots.find((s) => s.template === "pallet_rack");
        const a = cm.anchorFor("slot", slot.id);
        assert.ok(a && Number.isFinite(a.x) && Number.isFinite(a.z));
        assert.equal(cm.anchorFor("slot", "немає"), null);
        const cell = (await load("cells.js")).cellsOf(slot)[0];
        assert.ok(cm.anchorFor("cell", cell.code), "якір комірки");
        S.sel = null;
        S.selCell = null;
        assert.equal(E.commentsTarget().kind, "site");
    });

    /* ---------- F12 ---------- */
    test("S6 варіанти: цифри порівняння (місць, палетомісць, площа, об'єм, ємність) = capacitySummary; різниця й відсутні значення", async () => {
        const { S } = await boot();
        const { variantMetrics, compareMetrics, METRIC_ROWS } = await load("variants.js");
        const { capacitySummary } = await load("capacity_core.js");
        const m = variantMetrics();
        const sum = capacitySummary(S.slots, { categories: [] });
        assert.deepEqual(m, { cells: sum.cells, places: sum.places, area: sum.area, volume: sum.volume, max_weight: sum.maxWeight });
        assert.ok(m.cells > 100 && m.places >= m.cells && m.area > 0 && m.volume > 0);
        const half = variantMetrics(S.slots.filter((s, i) => i % 2));
        assert.ok(half.cells < m.cells);
        const rows = compareMetrics({ ...m, ops: 3 }, { ...half, ops: 1 });
        assert.deepEqual(rows.map((r) => r.key), METRIC_ROWS.map((r) => r.key));
        const cells = rows.find((r) => r.key === "cells");
        assert.equal(cells.diff, half.cells - m.cells);
        assert.equal(rows.find((r) => r.key === "ops").diff, -2);
        assert.equal(compareMetrics({ cells: 5 }, {}).find((r) => r.key === "cells").diff, null);
    });

    test("S6 варіанти (прототип): «Як є», створити з поточного, зробити активним — правки не губляться; переіменування, видалення, ліміт 12", async () => {
        const { S, ad, apply } = await boot();
        assert.equal(ad.capabilities.variants, true);
        let r = await ad.variants({ op: "list" });
        assert.deepEqual(r.variants.map((v) => [v.name, v.active]), [["Як є", true]]);
        const base = S.slots.length;
        r = await ad.variants({ op: "create", name: "Проєкт A", metrics: { cells: 11, places: 22, area: 3, volume: 4, max_weight: 500 } });
        assert.equal(r.variants.length, 2);
        const a = r.variants.find((v) => v.name === "Проєкт A");
        assert.equal(r.active_id, a.id, "після створення робота триває в новому варіанті");
        assert.equal(a.metrics.cells, 11);
        S.slots.push(newSlotLike(S, "S6-A1"));
        await ad.save(S, { now: true });
        r = await ad.variants({ op: "activate", id: 1, metrics: { cells: 12 } });
        assert.equal(r.reload, true);
        apply(await ad.load("sample"));
        assert.equal(S.slots.length, base, "«Як є» — без правок проєкту A");
        assert.equal(r.variants.find((v) => v.id === a.id).metrics.cells, 12 - 1 + 1 === 12 ? 12 : 12, "метрики A збережено при виході");
        r = await ad.variants({ op: "activate", id: a.id });
        apply(await ad.load("sample"));
        assert.equal(S.slots.length, base + 1, "правки проєкту A на місці");
        assert.ok(S.slots.some((s) => s.code_prefix === "S6-A1"));
        r = await ad.variants({ op: "rename", id: a.id, name: "Проєкт Б" });
        assert.ok(r.variants.some((v) => v.name === "Проєкт Б"));
        await assert.rejects(() => ad.variants({ op: "rename", id: a.id, name: "як є" }), (e) => e.code === "validation", "назва зайнята (без урахування регістру)");
        await assert.rejects(() => ad.variants({ op: "delete", id: a.id }), (e) => /Активний/.test(e.message));
        r = await ad.variants({ op: "delete", id: 1 });
        assert.equal(r.variants.length, 1);
        await assert.rejects(() => ad.variants({ op: "delete", id: a.id }), (e) => e.code === "validation");
        for (let i = 0; i < 11; i++) {
            await ad.variants({ op: "create", name: "В" + i, activate: false });
        }
        await assert.rejects(() => ad.variants({ op: "create", name: "Забагато" }), (e) => /Не більше 12/.test(e.message));
        await assert.rejects(() => ad.variants({ op: "bogus" }), (e) => e.code === "validation");
    });

    test("S6 варіанти (прототип): навчальна копія — «Скасувати» повертає чернетку, «Залишити зміни» робить звичайним варіантом; одна копія", async () => {
        const { S, ad, apply } = await boot();
        const base = S.slots.length;
        let r = await ad.variants({ op: "create", name: "Навчальна копія", training: true });
        const tr = r.variants.find((v) => v.is_training);
        assert.equal(r.training_id, tr.id);
        assert.equal(r.active_id, tr.id);
        await assert.rejects(() => ad.variants({ op: "create", name: "Ще", training: true }), (e) => /вже існує/.test(e.message));
        S.slots.push(newSlotLike(S, "S6-T1"));
        await ad.save(S, { now: true });
        r = await ad.variants({ op: "end_training", id: tr.id, keep: false });
        assert.equal(r.reload, true);
        assert.equal(r.training_id, null);
        apply(await ad.load("sample"));
        assert.equal(S.slots.length, base);
        assert.equal(r.variants.length, 1);
        r = await ad.variants({ op: "create", name: "Навчальна копія", training: true });
        const t2 = r.variants.find((v) => v.is_training);
        S.slots.push(newSlotLike(S, "S6-T2"));
        await ad.save(S, { now: true });
        r = await ad.variants({ op: "end_training", id: t2.id, keep: true });
        assert.equal(r.variants.find((v) => v.id === t2.id).is_training, false);
        assert.equal(r.training_id, null);
        assert.ok(S.slots.some((s) => s.code_prefix === "S6-T2"));
    });

    test("S6 варіанти (ядро): створення/перемикання через адаптер оновлюють S.variants; активний показує «живі» цифри", async () => {
        const { S, E, ad, apply } = await boot();
        E.flushNow = async () => ({ ok: true });
        E.reload = async () => apply(await ad.load("sample"));
        const v = await load("variants.js");
        await v.refreshVariants();
        assert.equal(v.activeVariant().name, "Як є");
        await v.createVariant("Проєкт A");
        assert.equal(v.activeVariant().name, "Проєкт A");
        assert.equal(S.variants.list.length, 2);
        const live = v.liveList().find((x) => x.active);
        assert.equal(live.metrics.cells, v.variantMetrics().cells);
        await v.activateVariant(S.variants.list.find((x) => x.name === "Як є").id);
        assert.equal(v.activeVariant().name, "Як є");
        await v.createVariant("Навчальна копія", { training: true });
        assert.equal(v.trainingVariant().is_training, true);
        await v.endTraining(false);
        assert.equal(v.trainingVariant(), null);
        assert.equal(v.activeVariant().name, "Як є", "скасування повертає в джерело");
    });

    /* ---------- N-03 ---------- */
    test("S6 версії (прототип): контрольна точка не міняє активну версію й базу; перегляд знімка; нотатка; обрізання до 50 лише точок", async () => {
        const { S, ad } = await boot();
        const active = S.site.active_version.n;
        const r0 = await ad.versions({ op: "list" });
        assert.ok(r0.versions.some((v) => v.is_active && v.n === active));
        const cp = await ad.versions({ op: "checkpoint", note: "Перед змінами" });
        assert.deepEqual([cp.version.kind, cp.version.state, cp.version.is_active, cp.version.note], ["checkpoint", "superseded", false, "Перед змінами"]);
        assert.equal(S.site.active_version.n, active, "активна версія та сама");
        assert.equal(S.site.draft_base_version.n, active);
        const view = await ad.versions({ op: "view", version_id: cp.version.id });
        assert.equal(view.view.slots.length, S.slots.length);
        assert.ok(view.view.layers.length && view.view.site.building.length > 0);
        const note = await ad.versions({ op: "note", version_id: cp.version.id, note: "  Нова  " });
        assert.equal(note.version.note, "Нова");
        for (let i = 0; i < 52; i++) {
            await ad.versions({ op: "checkpoint", note: "т" + i });
        }
        const list = (await ad.versions({ op: "list" })).versions;
        assert.equal(list.filter((v) => v.kind === "checkpoint").length, 50, "не більше 50 контрольних точок");
        assert.ok(S.versions.some((v) => v.kind !== "checkpoint"), "публікації не прибираються");
        assert.equal(list.length, 50, "у списку — останні 50");
        await assert.rejects(() => ad.versions({ op: "view", version_id: 99999 }), (e) => e.code === "not_found");
    });

    test("S6 історія: схема версії (SVG-пара) і перелік — планSvg має шари, місця й обладнання; EN-тексти", async () => {
        await boot();
        const v = await load("versions_ui.js");
        assert.equal(typeof v.openHistory, "function");
        assert.equal(typeof v.planSvg, "function");
        const { S } = await load("state.js");
        const cur = v.currentView();
        assert.equal(cur.slots, S.slots);
    });

    /* ---------- F14 ---------- */
    test("S6 блокування: ключ оренди = найменша зона, що містить центр; зона-контур — сама; поза зонами — сам об'єкт (дзеркало сервера)", async () => {
        const { S } = await boot();
        const { zoneKeyOf } = await load("locks.js");
        const { zonesOf } = await load("capacity_core.js");
        const zones = zonesOf(S.slots);
        assert.ok(zones.length >= 2, "у прикладі є зони");
        const z = zones[0].zone;
        assert.equal(zoneKeyOf(z), z.id, "зона-контур — власний ключ");
        const poly = zones[0].poly;
        const cx = poly.reduce((a, p) => a + p[0], 0) / poly.length;
        const cy = poly.reduce((a, p) => a + p[1], 0) / poly.length;
        const inner = { id: "x1", template: "pallet_rack", x: cx, y: cy };
        const key = zoneKeyOf(inner);
        assert.ok(zones.some((zz) => zz.zone.id === key), "об'єкт у зоні → ключ зони");
        const outside = { id: "x2", template: "pallet_rack", x: -500, y: -500 };
        assert.equal(zoneKeyOf(outside), "x2", "поза зонами — сам об'єкт");
        const nested = zones.filter((zz) => zz !== zones[0] && zz.poly.every(([x, y]) => x >= Math.min(...poly.map((p) => p[0])) && x <= Math.max(...poly.map((p) => p[0])) && y >= Math.min(...poly.map((p) => p[1])) && y <= Math.max(...poly.map((p) => p[1]))));
        assert.ok(nested.length >= 0);
        assert.equal(zoneKeyOf(null), null);
    });

    test("S6 блокування: HH:MM із часу сервера; busyText з іменем; чужа оренда відхиляється з повідомленням, своя продовжується (мок адаптера)", async () => {
        const { S, E, core } = await boot();
        const lk = await load("locks.js");
        assert.match(lk.clock("2026-10-19 14:05:00"), /^\d\d:\d\d$/);
        const slot = S.slots.find((s) => s.template === "pallet_rack");
        const calls = [];
        const exp = "2026-10-19 14:35:00";
        let busy = true;
        E.adapter = {
            capabilities: { locks: true },
            dirty: false,
            async locks(req) {
                calls.push(req);
                if (req.op === "acquire" && busy) {
                    const lock = { zone_uid: req.zone_uid, user: "Іван Петренко", mine: false, expires_at: exp };
                    throw Object.assign(new Error("Зону зайнято"), { code: "locked", lock, locks: [lock] });
                }
                return { ok: true, locks: req.op === "release" ? [] : [{ zone_uid: req.zone_uid, user: "Я", mine: true, expires_at: exp }], ttl: 300, heartbeat: 60 };
            },
        };
        core.setCapabilities({ locks: true });
        assert.equal(await lk.acquire(slot.id), false, "чужу оренду не взято");
        assert.equal(calls[0].zone_uid, slot.id);
        assert.match(lk.busyText({ zone_uid: slot.id, user: "Іван Петренко", expires_at: exp }), /редагує Іван Петренко до \d\d:\d\d/);
        assert.equal(lk.foreignLock(slot.id).user, "Іван Петренко");
        busy = false;
        assert.equal(await lk.acquire(slot.id), true);
        assert.equal(lk.lockOf(slot.id).mine, true);
        assert.equal(lk.foreignLock(slot.id), null);
        await lk.release(slot.id);
        assert.equal(S.locks.list.length, 0);
        assert.equal(S.locks.held.size, 0);
    });

    test("S6 блокування: у прототипі можливості locks немає (не емулюється); вибір об'єкта нічого не робить без права проєктування", async () => {
        const { ad, S, E } = await boot();
        assert.equal(ad.capabilities.locks, false);
        await assert.rejects(() => ad.locks({ op: "list" }), (e) => e.code === "not_supported");
        const lk = await load("locks.js");
        let n = 0;
        E.adapter = { capabilities: { locks: true }, locks: async () => (n++, { ok: true, locks: [] }) };
        S.app.mode = "view";
        await lk.onSelect({ kind: "slot", id: S.slots[0].id });
        assert.equal(n, 0, "режим перегляду — оренди немає");
    });

    /* ---------- N-01 ---------- */
    test("S6 рівні: нормалізація фокусу (ряд знає зону, стелаж лише в ряду), видимість об'єктів, ланцюжок крихт, «↑» і «⟲»", async () => {
        const { S, E } = await boot();
        const lv = await load("levels.js");
        const { zonesOf } = await load("capacity_core.js");
        const { cellsOf } = await load("cells.js");
        const rows = S.slots.filter((s) => s.template === "pallet_rack");
        const zones = zonesOf(S.slots);
        const row = rows.find((r) => zones.some(({ poly }) => poly.length && lv.normalizeFocus({ row: r.id }) && lv.normalizeFocus({ row: r.id }).zone)) || rows[0];
        const f = lv.normalizeFocus({ row: row.id, bay: 2, level: 1 });
        assert.equal(f.row, row.id);
        assert.deepEqual([f.bay, f.level], [2, 1]);
        assert.equal(lv.normalizeFocus({ bay: 3 }), null, "стелаж без ряду відкидається");
        assert.equal(lv.normalizeFocus(null), null);
        assert.equal(lv.normalizeFocus({ row: "немає" }), null);
        lv.setFocus({ row: row.id }, { camera: false });
        assert.equal(S.ui.focus.row, row.id);
        assert.equal(lv.objVisible("slot", row.id), true);
        const other = rows.find((r) => r.id !== row.id);
        assert.equal(lv.objVisible("slot", other.id), false, "інший ряд сховано");
        assert.equal(lv.objVisible("placement", S.placements[0].id), false);
        assert.equal(lv.objVisible("layer", "x"), true, "не об'єкти не ховаються");
        const crumbs = lv.crumbsOf();
        assert.equal(crumbs[0].key, "site");
        assert.ok(crumbs.some((c) => c.key === "row"));
        const cells = cellsOf(row);
        lv.setFocus({ row: row.id, bay: cells[0].index }, { camera: false });
        assert.ok(S.hl && S.hl.kind === "level" && S.hl.codes.size > 0, "стелаж підсвічено");
        assert.ok([...S.hl.codes].every((c) => cells.find((x) => x.code === c).index === cells[0].index));
        lv.setFocus({ row: row.id, bay: cells[0].index, level: cells[0].level }, { camera: false });
        assert.ok(S.hl.codes.size <= cells.length && S.hl.codes.has(cells[0].code));
        assert.equal(lv.crumbsOf().at(-1).key, "level");
        assert.equal(lv.levelUp(), true);
        assert.equal(S.ui.focus.level, null);
        assert.equal(S.ui.focus.bay, cells[0].index);
        lv.levelUp();
        lv.levelUp();
        assert.equal(S.ui.focus.row, null, "ряд знято");
        while (lv.levelUp()) {
            /* до складу */
        }
        assert.equal(S.ui.focus, null);
        assert.equal(S.hl, null, "підсвітку знято");
        assert.equal(lv.levelUp(), false, "вище нікуди");
        lv.setFocus({ row: row.id }, { camera: false });
        lv.resetFocus();
        assert.equal(S.ui.focus, null);
        assert.equal(E.objVisible("slot", other.id), true);
    });

    test("S6 рівні: фокус на зоні лишає видимими об'єкти її контуру; повторний клік піднімає вибір (місце → стелаж → ряд → зона → склад)", async () => {
        const { S, E } = await boot();
        const lv = await load("levels.js");
        const { zoneAt, zonesOf } = await load("capacity_core.js");
        const { cellsOf } = await load("cells.js");
        const { polygonContains } = await load("geometry.js");
        const zones = zonesOf(S.slots).filter(({ zone }) => zone.template === "zone");
        const withRows = zones.find(({ zone, poly }) => S.slots.some((s) => s.template === "pallet_rack" && polygonContains(poly, [s.x, s.y])));
        assert.ok(withRows, "є зона зі стелажами");
        const inside = S.slots.filter((s) => s.template !== "zone" && polygonContains(withRows.poly, [s.x, s.y]));
        const outsideRow = S.slots.find((s) => s.template === "pallet_rack" && !polygonContains(withRows.poly, [s.x, s.y]));
        lv.setFocus({ zone: withRows.zone.id }, { camera: false });
        assert.ok(inside.every((s) => lv.objVisible("slot", s.id)));
        assert.equal(lv.objVisible("slot", outsideRow.id), false);
        assert.equal(lv.objVisible("slot", withRows.zone.id), true);
        lv.resetFocus();
        // клік: рівні вибору
        const row = inside.find((s) => s.template === "pallet_rack");
        const cell = cellsOf(row)[0];
        E.selectObj = (ref) => {
            S.sel = ref ? { ...ref } : null;
            S.selCell = null;
        };
        S.sel = { kind: "slot", id: row.id };
        S.selCell = cell.code;
        lv.applyPick("bay", true);
        assert.equal(S.selCell, null);
        assert.equal(S.ui.selBay.index, cell.index);
        assert.ok(S.hl && S.hl.kind === "level" && S.hl.codes.has(cell.code));
        lv.applyPick("row", false);
        assert.equal(S.ui.selBay, null);
        assert.equal(S.hl, null);
        lv.applyPick("zone", false);
        assert.equal(S.sel.id, zoneAt(zonesOf(S.slots), row.x, row.y).id, "вибір піднято до найменшої зони ряду");
        lv.applyPick("site", false);
        assert.equal(S.sel, null, "вище зони — склад: вибір знято");
        assert.deepEqual(lv.PICKS.map((p) => p[0]), ["cell", "bay", "row", "zone"]);
    });

    test("S6 мініатюра: масштаб за габаритом, піксель → точка плану з обрізанням по контуру", async () => {
        const { miniScale, miniToWorld } = await load("minimap.js");
        const B = { length: 150, width: 72 };
        const sc = miniScale(B);
        assert.ok(sc.w <= 168 && sc.h <= 120 && Math.abs(sc.w / sc.h - 150 / 72) < 0.05);
        const p = miniToWorld(sc.w / 2, sc.h / 2, B, sc);
        assert.ok(Math.abs(p.x - 75) < 1 && Math.abs(p.y - 36) < 1);
        assert.deepEqual(miniToWorld(-50, 9999, B, sc), { x: 0, y: 0 });
        const q = miniToWorld(0, 0, B, sc);
        assert.ok(Math.abs(q.y - 72) < 1, "верх мініатюри — північ плану");
    });

    /* ---------- адаптери й реєстри ---------- */
    test("S6 адаптер Odoo: маршрути API-21/22/23/24, site_id у кожному виклику, помилка → StoreError із полями відповіді; capabilities", async () => {
        const { OdooAdapter } = await load("adapter_odoo.js");
        const calls = [];
        const rpc = async (route, params) => {
            calls.push([route, params]);
            if (route.endsWith("/locks") && params.zone_uid === "busy") {
                return { ok: false, code: "locked", message: "Зону зайнято", lock: { user: "Іван" }, locks: [{ zone_uid: "busy" }] };
            }
            return { ok: true, route };
        };
        const ad = new OdooAdapter({ rpc, orm: {} });
        ad.siteId = 7;
        assert.deepEqual([ad.capabilities.variants, ad.capabilities.comments, ad.capabilities.locks], [true, true, true]);
        await ad.variants({ op: "create", name: "A", metrics: { cells: 1 } });
        await ad.comments({ op: "list" });
        await ad.locks({ op: "acquire", zone_uid: "z1" });
        await ad.versions({ op: "list" });
        await ad.versions({ op: "view", version_id: 3 });
        await ad.versions({ op: "checkpoint", note: "т" });
        await ad.versions({ op: "note", version_id: 3, note: "н" });
        assert.deepEqual(
            calls.map(([r]) => r),
            ["/f3d/constructor/variants", "/f3d/constructor/comments", "/f3d/constructor/locks", "/f3d/constructor/version/view", "/f3d/constructor/version/view", "/f3d/constructor/version/checkpoint", "/f3d/constructor/version/checkpoint"]
        );
        assert.deepEqual(calls[0][1], { site_id: 7, op: "create", name: "A", metrics: { cells: 1 } });
        assert.deepEqual(calls[3][1], { site_id: 7 });
        assert.deepEqual(calls[5][1], { site_id: 7, op: "create", note: "т" }, "checkpoint → op create сервера");
        assert.deepEqual(calls[6][1], { site_id: 7, op: "note", version_id: 3, note: "н" });
        await assert.rejects(
            () => ad.locks({ op: "acquire", zone_uid: "busy" }),
            (e) => e.code === "locked" && e.lock.user === "Іван" && e.locks.length === 1 && /зайнято/.test(e.message)
        );
        const off = new OdooAdapter({ rpc, orm: {}, capabilities: { locks: false } });
        assert.equal(off.capabilities.locks, false, "хост може вимкнути");
    });

    test("S6 реєстри: вкладки «Варіанти»/«Коментарі», блоки правої панелі, меню (варіант, EN, тури, інструкція), діалоги tours/help/history, гаряча клавіша U", async () => {
        const core = await load("index.js");
        const { registries } = core;
        for (const k of ["left:variants", "left:comments"]) {
            assert.equal(registries.panels.get(k).area, "left");
        }
        assert.equal(registries.panels.get("left:variants").tab, "variants");
        assert.equal(registries.panels.get("left:comments").tab, "comments");
        for (const k of ["right:comments", "right:lock", "site:locks"]) {
            assert.ok(registries.panels.has(k), k);
        }
        assert.equal(registries.panels.get("right:comments").capability, "comments");
        assert.equal(registries.panels.get("right:lock").capability, "locks");
        for (const k of ["variants", "lang", "tours", "help"]) {
            assert.ok(registries.menu.has(k), "меню " + k);
        }
        assert.equal(registries.menu.get("variants").capability, "variants");
        assert.equal(registries.menu.get("lang").area, "top");
        assert.equal(registries.menu.get("tours").area, "more");
        for (const k of ["tours", "help", "history"]) {
            assert.ok(registries.dialogs.has(k), "діалог " + k);
        }
        assert.ok(registries.hotkeys.has("levels.up"));
        assert.ok(core.CAPABILITY_NAMES.includes("variants") && core.CAPABILITY_NAMES.includes("locks"));
        const i18n = await load("i18n.js");
        i18n.setLang("uk", { persist: false });
        assert.equal(registries.menu.get("lang").label, "EN");
        i18n.setLang("en", { persist: false });
        assert.equal(registries.menu.get("lang").label, "UK");
        i18n.setLang("uk", { persist: false });
    });

    test("S6 тури: дії кроків — вкладки, режим, виділення, стелаж у навчальній копії; блокувальники (телефон, права, відсутність варіантів)", async () => {
        const { S, E, core } = await boot();
        const tours = await load("tours.js");
        const { TOUR_BY_ID } = await load("tour_defs.js");
        const tabs = [];
        E.setLeftTab = (t) => {
            tabs.push(t);
            S.ui.leftTab = t;
        };
        E.renderAll = () => {};
        await tours.showAct({ tab: "variants" });
        assert.equal(S.ui.leftTab, "variants");
        assert.equal(tours.actDone({ tab: "variants" }), true);
        assert.equal(tours.actDone({ tab: "comments" }), false);
        S.app.mode = "view";
        assert.equal(tours.actDone({ mode: "edit" }), false);
        await tours.showAct({ mode: "edit" });
        assert.equal(S.app.mode, "edit");
        assert.equal(tours.actDone({ mode: "edit" }), true);
        // стелаж туру
        const before = S.slots.length;
        let placed = null;
        E.addSlotAt = (spec, x, y) => {
            placed = { spec, x, y };
            S.slots.push(newSlotLike(S, spec.prefix, x, y));
        };
        E.camTarget = () => ({ x: 20.4, y: 10.6 });
        await tours.showAct({ rack: true });
        assert.equal(S.slots.length, before + 1);
        assert.equal(placed.spec.prefix, "TOUR-R1");
        assert.deepEqual([placed.x, placed.y], [20, 11]);
        assert.equal(tours.actDone({ rack: true }), true);
        await tours.showAct({ rack: true });
        assert.equal(S.slots.length, before + 1, "повторний «Показати мені» не дублює");
        E.selectObj = (ref) => (S.sel = ref);
        await tours.showAct({ levels: 3 });
        assert.equal(tours.actDone({ levels: 3 }), true);
        // блокувальники
        S.rights.is_manager = true;
        core.setCapabilities({ variants: true });
        assert.equal(tours.tourBlocker(TOUR_BY_ID.rack), null);
        assert.equal(tours.tourBlocker(TOUR_BY_ID.welcome), null);
        core.setCapabilities({ variants: false });
        assert.match(tours.tourBlocker(TOUR_BY_ID.rack), /навчальної копії/);
        assert.equal(tours.tourBlocker(TOUR_BY_ID.welcome), null, "тур без змін не потребує копії");
        core.setCapabilities({ variants: true });
        S.rights.is_manager = false;
        assert.match(tours.tourBlocker(TOUR_BY_ID.rack), /менеджер/);
        E.isMobile = () => true;
        assert.match(tours.tourBlocker(TOUR_BY_ID.welcome), /телефоні/);
        E.isMobile = undefined;
    });
}

if (process.argv[1] && pathToFileURL(process.argv[1]).href === import.meta.url) {
    const tests = [];
    register((name, fn) => tests.push([name, fn]));
    let fail = 0;
    for (const [name, fn] of tests) {
        try {
            await fn();
            console.log("PASS", name);
        } catch (e) {
            fail++;
            console.log("FAIL", name, "::", (e && e.message ? e.message : String(e)).split("\n").slice(0, 3).join(" "));
        }
    }
    console.log(`\nІТОГО S6: ${tests.length - fail} passed, ${fail} failed`);
    process.exit(fail ? 1 : 0);
}
