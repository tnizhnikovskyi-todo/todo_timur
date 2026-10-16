/** @odoo-module */
// HOOT-тести карток документів (R-23, R-24): бейджі станів, посилання на форми Odoo, QC, історія комірки,
// «Відкрити в Odoo» для стелажів без власного запису (R-16 п. 5).
import { describe, expect, test } from "@odoo/hoot";
import { tick } from "@odoo/hoot-mock";
import { DOC_STATES, docPill } from "@factory3d_viewer/viewer/format";
import { json, mountViewer } from "./helpers";

const q = (el, sel) => el.querySelector(sel);
const qa = (el, sel) => [...el.querySelectorAll(sel)];
const text = (el) => (el.textContent || "").replace(/\s+/g, " ").trim();
const settle = async (n = 4) => {
    for (let i = 0; i < n; i++) {
        await tick();
    }
};
const pillText = (el) => qa(el, ".o_f3d_pill").map(text);
const doc = (name, model, id, kind, state) => ({ name, model, id, kind, state });

describe.current.tags("desktop");

const LOC = {
    code: "RCK-R1-3D",
    complete_name: "WH/Stock/Сировина/Плити/Стелажі/R1/RCK-R1-3D",
    truncated: false,
    products: [
        {
            product: "DSP16-ANT",
            name: "ДСП 16 мм Антрацит 2800×2070",
            uom: "Аркуш",
            qty: 20,
            reserved: 8,
            lots: [
                {
                    lot: "DSP16-ANT-2612-311",
                    qty: 20,
                    reserved: 8,
                    arrived: [
                        {
                            doc: doc("WH/IN/00126", "stock.picking", 5, "picking", "done"),
                            date: "2026-10-12 09:10",
                            qty: 20,
                            from: { code: null, name: "Partners/Vendors" },
                        },
                        { doc: doc("Інвентаризація", null, null, "inventory", null), date: "2026-10-10 08:00", qty: 4, from: null },
                    ],
                    reserve: [
                        {
                            doc: doc("WH/OUT/00412", "stock.picking", 7, "picking", "assigned"),
                            qty: 5,
                            pending: 3,
                            to: { code: null, name: "Partners/Customers" },
                        },
                    ],
                },
            ],
            out: [
                {
                    doc: doc("WH/MO/00231", "mrp.production", 231, "production", "confirmed"),
                    qty: 2,
                    to: { code: "PLT-04C", name: "WH/Виробництво/PLT-04C" },
                    date: "2026-10-12 11:00",
                },
            ],
            incoming: [
                {
                    doc: doc("WH/IN/00130", "stock.picking", 9, "picking", "waiting"),
                    qty: 40,
                    from: { code: null, name: "Partners/Vendors" },
                    date: "2026-10-12 14:00",
                },
            ],
        },
    ],
};

// ------------------------------------------------------------------ словники станів (R-23)
test("doc_states: мітки українською для picking / МО / quality.check", () => {
    const label = (kind, state) => text(new DOMParser().parseFromString(docPill(kind, state), "text/html").body);
    expect(["draft", "waiting", "assigned", "done", "cancel"].map((s) => label("picking", s))).toEqual([
        "Чернетка",
        "Очікує",
        "Готово",
        "Виконано",
        "Скасовано",
    ]);
    expect(["none", "pass", "fail"].map((s) => label("quality", s))).toEqual(["Очікує", "Пройдено", "Брак"]);
    expect(["draft", "confirmed", "progress", "done", "cancel"].map((s) => label("production", s))).toEqual([
        "Чернетка",
        "Підтверджено",
        "У роботі",
        "Виконано",
        "Скасовано",
    ]);
    expect(label("picking", "zzz")).toBe("zzz");
    expect(docPill("picking", null)).toBe("");
    expect(Object.keys(DOC_STATES).sort()).toEqual(["picking", "production", "quality", "scrap"]);
});

// ------------------------------------------------------------------ B: шлях плити в картці МО
test("mo_path_badges: кроки шляху плити — назви документів із посиланнями й станом", async () => {
    const resolveUrls = [];
    const r = await mountViewer({
        model: "none",
        mutate: (fx) => {
            // WH/INT/00061 є в нотатці контролю, але не в pickings payload: стан приходить від провайдера (supply.docs)
            fx.data.productions[0].supply.docs = { "WH/INT/00061": { kind: "picking", state: "assigned" } };
        },
        routes: {
            "/resolve": (url) => {
                resolveUrls.push(url);
                return json(
                    url.includes("name=WH%2FINT%2F00061")
                        ? { model: "stock.picking", res_id: 61 }
                        : { model: null, res_id: null, reason: "not_found" }
                );
            },
        },
    });
    r.viewer.showMO("WH/MO/00231");
    const steps = q(r.el, "ol.o_f3d_steps");
    const link = (name) => q(steps, `[data-open="${name}"]`);
    for (const [name, label] of [["WH/IN/00128", "Готово"], ["QC/00413", "Пройдено"], ["WH/INT/00061", "Готово"]]) {
        expect(link(name) !== null).toBe(true);
        // бейдж стоїть одразу за назвою
        expect(text(link(name).nextElementSibling)).toBe(label);
        expect(link(name).nextElementSibling.classList.contains("o_f3d_pill")).toBe(true);
    }
    // «Відкрити в Odoo» вгорі лишається першим [data-open]
    expect(q(r.el, "[data-open]").classList.contains("o_f3d_doc")).toBe(false);
    link("WH/INT/00061").click();
    await settle();
    expect(r.opened).toEqual([["stock.picking", 61]]);
    // компоненти: приймання з посиланням і бейджем
    const receipt = q(qa(r.el, ".o_f3d_tbl").at(-1), '[data-open="WH/IN/00128"]');
    expect(text(receipt.nextElementSibling)).toBe("Готово");
});

test("mo_path_badges: у кіоску стани є, посилань на Odoo немає", async () => {
    const r = await mountViewer({ model: "none", kiosk: true, viewerOpts: { onOpenRecord: undefined } });
    r.viewer.showMO("WH/MO/00231");
    expect(r.el.querySelector("[data-open]")).toBe(null);
    expect(pillText(q(r.el, "ol.o_f3d_steps")).includes("Готово")).toBe(true);
    expect(text(q(r.el, "ol.o_f3d_steps")).includes("WH/IN/00128")).toBe(true);
});

// ------------------------------------------------------------------ C: QC-посилання
test("qc_links: рядок кванта і червоний блок у комірці карантину ведуть у quality.check", async () => {
    const r = await mountViewer({
        model: "core",
        routes: {
            "/resolve": (url) =>
                json(
                    url.includes("name=QC%2F00412")
                        ? { model: "quality.check", res_id: 412 }
                        : { model: null, res_id: null, reason: "not_found" }
                ),
        },
    });
    r.viewer.select("QC-1");
    const links = qa(r.el, '.o_f3d_cardbody [data-open="QC/00412"]');
    expect(links.length).toBe(2);
    for (const a of links) {
        expect(text(a.nextElementSibling)).toBe("Брак");
    }
    const block = q(r.el, ".o_f3d_note.o_f3d_bad");
    expect(block.contains(links[1])).toBe(true);
    links[1].click();
    await settle();
    expect(r.opened).toEqual([["quality.check", 412]]);
    links[0].click(); // з рядка кванта — той самий запис, а не перехід до картки товару
    await settle();
    expect(r.opened.length).toBe(2);
    expect(r.viewer.getState().selected).toBe("QC-1");
});

test("qc_links: «Потребує уваги» — назва перевірки відкриває форму, решта рядка веде до комірки", async () => {
    const r = await mountViewer({
        model: "none",
        routes: { "/resolve": () => json({ model: "quality.check", res_id: 412 }) },
    });
    const link = q(r.el, '.o_f3d_row [data-open="QC/00412"]');
    expect(link !== null).toBe(true);
    expect(text(link.nextElementSibling)).toBe("Брак");
    link.click();
    await settle();
    expect(r.opened).toEqual([["quality.check", 412]]);
    expect(q(r.el, ".o_f3d_row[data-go^='obj:']") !== null).toBe(true);
});

// ------------------------------------------------------------------ A: історія комірки
test("loc_history: картка комірки — надійшло / резерв / іде з комірки / очікується з посиланнями", async () => {
    let n = 0;
    const r = await mountViewer({
        model: "core",
        routes: {
            "/loc/RCK-R1-3D": () => {
                n++;
                return json(LOC);
            },
        },
    });
    r.viewer.select("RCK-R1-3D");
    await settle();
    expect(n).toBe(1);
    const hist = q(r.el, '.o_f3d_hist[data-hist="RCK-R1-3D"]');
    const t = text(hist);
    for (const word of ["Надійшло", "Резерв", "Іде з комірки", "Очікується", "партія DSP16-ANT-2612-311", "в наявності 20 Аркуш",
        "резерв 8 Аркуш", "5 Аркуш + 3 Аркуш ще не зарезервовано", "сьогодні 09:10", "Інвентаризація"]) {
        expect(t.includes(word)).toBe(true);
    }
    // посилання за model:id і бейджі стану
    const rec = (name) => qa(hist, "[data-rec]").find((a) => text(a) === name);
    expect(rec("WH/IN/00126").dataset.rec).toBe("stock.picking:5");
    expect(text(rec("WH/IN/00126").nextElementSibling)).toBe("Виконано");
    expect(text(rec("WH/OUT/00412").nextElementSibling)).toBe("Готово");
    expect(text(rec("WH/IN/00130").nextElementSibling)).toBe("Очікує");
    expect(rec("WH/MO/00231").dataset.rec).toBe("mrp.production:231");
    expect(text(rec("WH/MO/00231").nextElementSibling)).toBe("Підтверджено");
    expect(rec("Інвентаризація")).toBe(undefined); // без запису Odoo — просто текст
    // порядок груп у лоті: Надійшло перед Резерв; на рівні товару: Іде з комірки перед Очікується
    const labels = qa(hist, ".o_f3d_hlbl").map(text);
    expect(labels).toEqual(["Надійшло", "Резерв", "Іде з комірки", "Очікується"]);
    // призначення з кодом 3D-об'єкта — перехід у сцену
    expect(q(hist, '[data-go="obj:PLT-04C"]') !== null).toBe(true);
    rec("WH/OUT/00412").click();
    await settle();
    expect(r.opened).toEqual([["stock.picking", 7]]);
    // вибір товару в таблиці залишків лишається: рядок веде до картки товару
    expect(q(r.el, '.o_f3d_tbl .o_f3d_click[data-go="prod:DSP16-ANT"]') !== null).toBe(true);
});

test("loc_history: «Раніше в комірці» — вибуло (документ, дата, кількість, куди) і як надійшло, під поточними товарами", async () => {
    const LEFT = {
        ...LOC,
        left_days: 30,
        left: [
            {
                product: "DSP16-WHT",
                name: "ДСП 16 мм Білий 2800×2070",
                uom: "Аркуш",
                lot: "DSP16-WHT-2610-101",
                out: {
                    doc: doc("WH/OUT/00399", "stock.picking", 3, "picking", "done"),
                    qty: 12,
                    to: { code: null, name: "Клієнти" },
                    date: "2026-10-11 15:20",
                },
                arrived: [
                    {
                        doc: doc("WH/IN/00120", "stock.picking", 2, "picking", "done"),
                        date: "2026-10-08 09:00",
                        qty: 12,
                        from: { code: null, name: "Постачальники" },
                    },
                ],
            },
            {
                product: "FUR-HNG",
                name: "Завіса",
                uom: "шт",
                lot: null,
                out: { doc: doc("WH/MO/00231", "mrp.production", 231, "production", "confirmed"), qty: 4, to: { code: "PLT-04C", name: "WH/Виробництво/PLT-04C" }, date: "2026-10-10 08:00" },
                arrived: [],
            },
        ],
    };
    const r = await mountViewer({ model: "core", routes: { "/loc/RCK-R1-3D": () => json(LEFT) } });
    r.viewer.select("RCK-R1-3D");
    await settle();
    const hist = q(r.el, '.o_f3d_hist[data-hist="RCK-R1-3D"]');
    const left = q(hist, ".o_f3d_hleft");
    // блок після поточних товарів, заголовок з вікном
    expect(left !== null && qa(hist, ".o_f3d_hprod").at(-1).closest(".o_f3d_hleft") === left).toBe(true);
    expect(qa(hist, ".o_f3d_hprod:not(.o_f3d_hgone)").every((el) => !left.contains(el))).toBe(true);
    expect(text(q(left, ".o_f3d_hlbl"))).toBe("Раніше в комірці · вибуло за 30 дн.");
    const rows = qa(left, ".o_f3d_hgone");
    expect(rows.length).toBe(2);
    const t0 = text(rows[0]);
    for (const word of ["ДСП 16 мм Білий 2800×2070", "партія DSP16-WHT-2610-101", "Вибуло", "11.10 15:20", "12 Аркуш", "→ Клієнти",
        "Надійшло", "з Постачальники", "08.10 09:00"]) {
        expect(t0.includes(word)).toBe(true);
    }
    expect(qa(rows[0], ".o_f3d_hlbl").map(text)).toEqual(["Вибуло", "Надійшло"]);
    expect(qa(rows[1], ".o_f3d_hlbl").map(text)).toEqual(["Вибуло"]); // без партії і без надходження
    expect(text(rows[1]).includes("партія")).toBe(false);
    // посилання на форму й бейдж стану, як у «Надійшло»/«Резерв»
    const rec = (row, name) => qa(row, "[data-rec]").find((a) => text(a) === name);
    expect(rec(rows[0], "WH/OUT/00399").dataset.rec).toBe("stock.picking:3");
    expect(text(rec(rows[0], "WH/OUT/00399").nextElementSibling)).toBe("Виконано");
    expect(rec(rows[0], "WH/IN/00120").dataset.rec).toBe("stock.picking:2");
    expect(text(rec(rows[1], "WH/MO/00231").nextElementSibling)).toBe("Підтверджено");
    expect(q(rows[1], '[data-go="obj:PLT-04C"]') !== null).toBe(true);
    rec(rows[0], "WH/OUT/00399").click();
    await settle();
    expect(r.opened).toEqual([["stock.picking", 3]]);
    // порожня комірка, з якої щось вибуло, — не «Рухів немає»
    const only = await mountViewer({ model: "core", routes: { "/loc/RCK-R1-3D": () => json({ ...LEFT, products: [], truncated: true }) } });
    only.viewer.select("RCK-R1-3D");
    await settle();
    const t = text(q(only.el, ".o_f3d_hist"));
    expect(t.includes("Рухів по комірці немає")).toBe(false);
    expect(t.includes("Раніше в комірці")).toBe(true);
    expect(t.includes("Показано не всі записи")).toBe(true);
    // без `left` блоку немає (старий сервер)
    const none = await mountViewer({ model: "core", routes: { "/loc/RCK-R1-3D": () => json(LOC) } });
    none.viewer.select("RCK-R1-3D");
    await settle();
    expect(q(none.el, ".o_f3d_hleft")).toBe(null);
});

test("loc_history: жива дельта оновлює відкриту картку, зайва — ні", async () => {
    let n = 0;
    const r = await mountViewer({
        model: "core",
        routes: {
            "/loc/RCK-R1-3D": () => {
                n++;
                const data = structuredClone(LOC);
                if (n > 1) {
                    data.products[0].incoming.push({
                        doc: doc("WH/IN/00131", "stock.picking", 10, "picking", "assigned"),
                        qty: 5,
                        from: null,
                        date: "2026-10-12 15:00",
                    });
                }
                return json(data);
            },
        },
    });
    r.viewer.select("RCK-R1-3D");
    await settle();
    expect(n).toBe(1);
    r.viewer.applyPatch({ maintenance_requests: [] }); // нерелевантна дельта: перемальовування з кешу, без запиту
    await settle();
    expect(n).toBe(1);
    expect(text(q(r.el, ".o_f3d_hist")).includes("WH/IN/00131")).toBe(false);
    r.viewer.applyPatch({ locations: { "RCK-R1-3D": { fill: 0.5 } } });
    await settle();
    expect(n).toBe(2);
    expect(text(q(r.el, ".o_f3d_hist")).includes("WH/IN/00131")).toBe(true);
    r.viewer.applyPatch({ pickings: [] }); // порожній список — нічого не змінилось
    await settle();
    expect(n).toBe(2);
});

test("loc_history: 404 і збій — нейтральне повідомлення; кіоск не питає", async () => {
    const r = await mountViewer({ model: "core" }); // мок за замовчуванням відповідає 404
    r.viewer.select("RCK-R1-3D");
    await settle();
    expect(text(q(r.el, ".o_f3d_hist"))).toBe("Комірки немає в Odoo.");
    const bad = await mountViewer({ model: "core", routes: { "/loc/RCK-R1-3D": () => json({}, {}, 500) } });
    bad.viewer.select("RCK-R1-3D");
    await settle();
    expect(text(q(bad.el, ".o_f3d_hist"))).toBe("Не вдалося завантажити історію комірки.");
    const k = await mountViewer({ model: "core", kiosk: true, viewerOpts: { onOpenRecord: undefined } });
    k.viewer.select("RCK-R1-3D");
    await settle();
    expect(q(k.el, ".o_f3d_hist")).toBe(null);
    expect(k.fetch.calls.some((u) => u.includes("/loc/"))).toBe(false);
});

// ------------------------------------------------------------------ D: «Відкрити в Odoo» для стелажа
test("open_group: стелаж без власного запису відкриває список комірок", async () => {
    const calls = [];
    const lists = [];
    const r = await mountViewer({
        model: "core",
        viewerOpts: { onOpenRecords: (model, ids, name) => lists.push([model, ids, name]) },
        routes: {
            "/resolve": (url) => {
                calls.push(decodeURIComponent(url));
                return json({ model: "stock.location", res_id: null, res_ids: [11, 12, 13], kind: "group", count: 3 });
            },
        },
    });
    r.viewer.select("FG-RACK-R1");
    // рішення без запиту: живі комірки всередині стелажа (за габаритом) вже є в даних
    expect(calls.length).toBe(0);
    const btn = q(r.el, ".o_f3d_c-open");
    expect(btn !== null).toBe(true);
    btn.click();
    await settle();
    expect(calls.length).toBe(1);
    const m = calls[0].match(/code=FG-RACK-R1&codes=(.*)$/);
    const codes = m[1].split(",");
    expect(codes.length).toBe(72);
    expect(codes.every((c) => /^FG-R1-B\d\d-L[1-4]$/.test(c))).toBe(true);
    expect(lists).toEqual([["stock.location", [11, 12, 13], "Палетний стелаж R1"]]);
    expect(r.opened.length).toBe(0);
});

test("open_group: об'єкт без запису й без комірок — кнопки немає (один дешевий resolve), із записом — з'являється", async () => {
    const calls = [];
    const none = await mountViewer({
        model: "core",
        routes: {
            "/resolve": (url) => {
                calls.push(url);
                return json({ model: null, res_id: null, reason: "not_found" });
            },
        },
    });
    none.viewer.select("OFFICE");
    expect(q(none.el, ".o_f3d_c-open")).toBe(null);
    await settle();
    expect(q(none.el, ".o_f3d_c-open")).toBe(null);
    none.viewer.select("OFFICE"); // повторне відкриття не повторює запит
    await settle();
    expect(calls.length).toBe(1);
    expect(calls[0].includes("code=OFFICE")).toBe(true);
    expect(calls[0].includes("codes=")).toBe(false);

    const found = await mountViewer({
        model: "core",
        routes: { "/resolve": () => json({ model: "maintenance.equipment", res_id: 5, kind: "equipment" }) },
    });
    found.viewer.select("SOCIAL");
    expect(q(found.el, ".o_f3d_c-open")).toBe(null);
    await settle();
    expect(q(found.el, ".o_f3d_c-open") !== null).toBe(true);
    q(found.el, ".o_f3d_c-open").click();
    await settle();
    expect(found.opened).toEqual([["maintenance.equipment", 5]]);
});

test("open_group: у кіоску кнопки немає, запитів немає", async () => {
    const r = await mountViewer({ model: "core", kiosk: true, viewerOpts: { onOpenRecord: undefined } });
    r.viewer.select("FG-RACK-R1");
    await settle();
    expect(q(r.el, ".o_f3d_c-open")).toBe(null);
    expect(r.fetch.calls.some((u) => u.includes("/resolve"))).toBe(false);
});

test("open_group: BOARD-RACKS (група обладнання, не «rack») без власного запису, але з комірками всередині — список; один запит на картку", async () => {
    const calls = [];
    const lists = [];
    const r = await mountViewer({
        model: "core",
        viewerOpts: { onOpenRecords: (model, ids, name) => lists.push([model, ids, name]) },
        // у даних є код обладнання (підказка «запис є»), а в Odoo запису немає; діти — комірки RCK-* у габариті групи
        mutate: (fx) => { fx.static.equipment["BOARD-RACKS"] = structuredClone(Object.values(fx.static.equipment)[0]); },
        routes: {
            "/resolve": (url) => {
                calls.push(decodeURIComponent(url));
                return json(
                    url.includes("codes=")
                        ? { model: "stock.location", res_id: null, res_ids: [11, 12, 13], kind: "group", count: 3 }
                        : { model: null, res_id: null, reason: "not_found" }
                );
            },
        },
    });
    expect(r.viewer.items.get("BOARD-RACKS").userData.kind).toBe("equipment");
    r.viewer.select("BOARD-RACKS");
    await settle();
    expect(calls.length).toBe(0); // комірки всередині підказують відповідь без запиту
    q(r.el, ".o_f3d_c-open").click();
    await settle();
    expect(calls.length).toBe(1);
    expect(calls[0].startsWith("/f3d/viewer/resolve?code=BOARD-RACKS&codes=")).toBe(true);
    const codes = calls[0].split("codes=")[1].split(",");
    expect(codes.includes("RCK-R1-1A")).toBe(true);
    expect(codes.length >= 96 && codes.length <= 200).toBe(true);
    expect(lists.length).toBe(1);
    expect(lists[0].slice(0, 2)).toEqual(["stock.location", [11, 12, 13]]);
    // повторний клік — з кешу: нового запиту немає
    q(r.el, ".o_f3d_c-open").click();
    await settle();
    expect(calls.length).toBe(1);
    expect(lists.length).toBe(2);
    expect(r.notes.length).toBe(0);
});

test("open_group: нічого не знайшлося ні за власним кодом, ні в комірках — кнопка зникає без повідомлення, повторно не питаємо", async () => {
    const calls = [];
    const r = await mountViewer({
        model: "core",
        routes: {
            "/resolve": (url) => {
                calls.push(decodeURIComponent(url));
                return json({ model: null, res_id: null, reason: "not_found" });
            },
        },
    });
    // центр із даних (власний запис очікується), але в Odoo його немає, комірок усередині теж
    r.viewer.select("SAW-2");
    expect(calls.length).toBe(0);
    q(r.el, ".o_f3d_c-open").click();
    await settle();
    expect(calls.length).toBe(1);
    expect(q(r.el, ".o_f3d_c-open")).toBe(null);
    expect(r.notes.some(([m]) => m.includes("немає запису"))).toBe(false);
    r.viewer.select("SAW-1");
    r.viewer.select("SAW-2");
    await settle();
    expect(q(r.el, ".o_f3d_c-open")).toBe(null);
    expect(calls.filter((c) => c.includes("code=SAW-2")).length).toBe(1);
    // об'єкт без підказок: один resolve({code}) на картку, кнопки немає
    r.viewer.select("OFFICE");
    await settle();
    r.viewer.select("OFFICE");
    await settle();
    expect(q(r.el, ".o_f3d_c-open")).toBe(null);
    expect(calls.filter((c) => c.includes("code=OFFICE")).length).toBe(1);
    expect(r.notes.length).toBe(0);
});
