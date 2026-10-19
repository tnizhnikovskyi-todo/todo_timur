/** @odoo-module */
// Редактор у зборі (нульовий рендерер, мок RPC): AC-10 (шари, сітка, видимість), AC-49 (роль → блокування), AC-63 (перетягування
// у прохід), AC-64 (поворот), AC-65 (лінійка, Delete без нативних діалогів), групи шарів, dynamic у перевірках, code_style 'exact'.
import { advanceTime, after, animationFrame, beforeEach, describe, expect, getFixture, queryAll, queryOne, test } from "@odoo/hoot";
import { E, OdooStore, S, THREE, V, generateCells, mountEditor, runChecks, setupCore, unmountEditor } from "./core";
import { golden, near } from "./helpers";
import { makeLoad, mockRpc } from "./fixtures";

describe.current.tags("desktop");
beforeEach(setupCore);

const SAVE = "/f3d/constructor/save";

/** Монтує редактор у фікстуру з нульовим рендерером. */
async function openEditor(load = makeLoad(), routes = {}) {
    // стелаж фікстури (18 прольотів) перекриває станок у кадрі: скорочуємо його й відсуваємо, щоб промінь вибору дістав станок
    if (load.slots[0]?.uid === "slrack") {
        Object.assign(load.slots[0], { x: 40, y: 5, params: { ...load.slots[0].params, bays: 4 }, cell_count: 16 });
    }
    const fixture = getFixture();
    const style = document.createElement("style");
    style.textContent = ".o_f3d_constructor #vp{position:relative;width:900px;height:600px}.o_f3d_constructor #vp canvas{display:block;width:900px;height:600px}";
    fixture.append(style);
    const root = document.createElement("div");
    root.className = "o_f3d_constructor";
    fixture.append(root);
    const rpc = mockRpc({
        "/f3d/constructor/sites": { ok: true, sites: [{ id: load.site.id, name: load.site.name }] },
        "/f3d/constructor/load": () => structuredClone(load),
        [SAVE]: { ok: true, rev: 4, draft_changes: 1, has_changes: true, id_map: {}, etags: {} },
        ...routes,
    });
    const orm = { create: async () => [77] };
    const store = new OdooStore({ rpc, orm, autosaveMs: 1500 });
    await mountEditor(root, { store, services: { action: {}, notification: {}, orm }, siteId: load.site.id, testMode: true });
    after(() => unmountEditor());
    await animationFrame();
    // setPointerCapture на синтетичні події кидає NotFoundError
    V.canvas.setPointerCapture = () => {};
    V.canvas.releasePointerCapture = () => {};
    return { root, rpc, store };
}

/** Екранні координати точки світу (x, y, z — висота) через камеру сцени. */
function screenOf(x, y, z = 0) {
    const r = V.canvas.getBoundingClientRect();
    const v = new THREE.Vector3(x, z, -y).project(V.camera);
    return { clientX: r.left + ((v.x + 1) / 2) * r.width, clientY: r.top + ((1 - v.y) / 2) * r.height };
}
const ptr = (type, pt) => V.canvas.dispatchEvent(new PointerEvent(type, { bubbles: true, cancelable: true, button: 0, pointerId: 1, pointerType: "mouse", ...pt }));
const key = (code) => document.dispatchEvent(new KeyboardEvent("keydown", { code, key: code, bubbles: true, cancelable: true }));
async function drag(from, to) {
    ptr("pointerdown", screenOf(...from));
    ptr("pointermove", screenOf(...to));
    ptr("pointerup", screenOf(...to));
    await animationFrame();
}
const toastText = () => queryAll("#toast .ftoast").map((t) => t.textContent).join(" | ");
const machineZ = 0.9; // центр корпусу верстата 1,8 м заввишки: цілимося в hit-бокс

test("відкриття: 3 шари, 2 місця, 1 станок; нульовий рендерер; дані з API-01/03", async () => {
    const { rpc, root } = await openEditor();
    expect(root.dataset.ready).toBe("1");
    expect(rpc.of("/f3d/constructor/sites")).toHaveLength(1);
    expect(S.layers).toHaveLength(3);
    expect(S.slots).toHaveLength(2);
    expect(S.placements).toHaveLength(1);
    expect(V.views.size).toBe(3);
    expect(queryAll("#leftBody .layer")).toHaveLength(3);
    expect(root.textContent.includes("імітація")).toBe(false); // публікація справжня
    expect(root.textContent.includes("Конструктор завод")).toBe(false);
});

test("AC-10 сітка активного шару на його відмітці з кроком grid_step; інші шари напівпрозорі; видимість ховає шар", async () => {
    const load = makeLoad();
    load.layers[2].elevation = 4.2;
    load.layers[2].grid_step = 1;
    load.placements[0].layer_id = 3;
    await openEditor(load);
    expect(S.ui.layer).toBe("lyp");
    const dec = V.decor.get("lyp").g;
    const grids = [];
    dec.traverse((o) => {
        if (o.isLineSegments && (o.material === V.mat.gridMinor || o.material === V.mat.gridMajor)) {
            grids.push(o);
        }
    });
    expect(grids.length > 0).toBe(true);
    const xs = new Set();
    for (const g of grids) {
        const p = g.geometry.attributes.position.array;
        for (let i = 0; i < p.length; i += 3) {
            expect(near(p[i + 1], 4.2 + 0.006, 1e-4)).toBe(true); // висота = відмітка шару
            xs.add(Math.round(p[i] * 1000) / 1000);
        }
    }
    const sorted = [...xs].sort((a, b) => a - b);
    expect(sorted.length > 5).toBe(true);
    expect(near(sorted[1] - sorted[0], 1, 1e-6)).toBe(true); // крок сітки
    // сітки неактивних шарів немає, їхні об'єкти — «привиди» (напівпрозорі)
    const other = [];
    V.decor.get("lys").g.traverse((o) => o.isLineSegments && o.material === V.mat.gridMinor && other.push(o));
    expect(other).toHaveLength(0);
    expect(V.views.get("s:slrack").ghost).toBe(true);
    expect(V.views.get("p:plm1").ghost).toBe(false);
    // видимість
    queryOne('#leftBody .layer[data-layer="lys"] .eye').click();
    await animationFrame();
    expect(V.views.has("s:slrack")).toBe(false);
    expect(V.decor.has("lys")).toBe(false);
    queryOne('#leftBody .layer[data-layer="lys"] .eye').click();
    expect(V.views.has("s:slrack")).toBe(true);
});

test("групи шарів: заголовок групи в списку «Шари», згортання", async () => {
    const load = makeLoad();
    load.layers[0].group = "Будівля";
    load.layers[1].group = "Склад";
    load.layers[2].group = "Склад";
    await openEditor(load);
    const heads = queryAll("#leftBody .lgroup");
    expect(heads.map((h) => h.dataset.group)).toEqual(["Будівля", "Склад"]);
    expect(queryAll("#leftBody .layer")).toHaveLength(3);
    queryOne('#leftBody .lgroup[data-group="Склад"]').click(); // активний шар (lyp) лишається видимим навіть у згорнутій групі
    expect(queryAll("#leftBody .layer").length >= 1).toBe(true);
    expect(queryOne('#leftBody .lgroup[data-group="Склад"]').classList.contains("closed")).toBe(false);
});

test("AC-63 block: станок, перетягнутий у прохід, повертається на місце з повідомленням «Прохід перекрито»", async () => {
    await openEditor();
    const pl = S.placements[0];
    expect([pl.x, pl.y]).toEqual([20, 8]);
    await drag([20, 8, machineZ], [20, 21.5, 0]);
    expect([pl.x, pl.y]).toEqual([20, 8]);
    expect(toastText().includes("Прохід перекрито")).toBe(true);
    expect(S.issues.byKey.get("p:plm1")?.level || "normal").toBe("normal");
});

test("AC-63 warn: у режимі «попередження» об'єкт лишається, прив'язка до grid_step, підсвітка помаранчева", async () => {
    const load = makeLoad();
    load.checks.find((c) => c.check === "aisles_free").mode = "warn";
    await openEditor(load);
    const pl = S.placements[0];
    await drag([20, 8, machineZ], [20.3, 21.4, 0]);
    expect(pl.y > 12).toBe(true);
    expect(near(pl.x / 0.5, Math.round(pl.x / 0.5), 1e-9)).toBe(true); // кратно grid_step = 0,5
    expect(near(pl.y / 0.5, Math.round(pl.y / 0.5), 1e-9)).toBe(true);
    expect(S.issues.byKey.get("p:plm1").level).toBe("warn");
    expect(V.views.get("p:plm1").foot.material).toBe(V.mat.dash.warn);
    expect(toastText().includes("Прохід перекрито")).toBe(true);
});

test("AC-64 клавіша R повертає на +90°, footprint перераховується (R-02), перетин із сусідом підсвічується", async () => {
    const load = makeLoad();
    const second = { ...load.placements[0], id: 32, uid: "plm2", code: "M-2", name: "Верстат 2", x: 20, y: 10.2 };
    load.placements.push(second);
    load.checks.find((c) => c.check === "collide").mode = "warn"; // у режимі block поворот із перетином відхиляється
    load.checks.find((c) => c.check === "service_free").enabled = false; // ізолюємо перевірку перетину
    await openEditor(load);
    const pl = S.placements[0];
    E.selectObj({ kind: "placement", id: "plm1" });
    expect(S.issues.byKey.get("p:plm1")?.level || "normal").toBe("normal");
    const before = V.views.get("p:plm1").g.box;
    key("KeyR");
    await animationFrame();
    expect(pl.rotation).toBe(90);
    const after2 = V.views.get("p:plm1").g.box;
    expect(near(before[2] - before[0], 3, 1e-6) && near(before[3] - before[1], 1.5, 1e-6) && near(after2[2] - after2[0], 1.5, 1e-6) && near(after2[3] - after2[1], 3, 1e-6)).toBe(true);
    expect(S.issues.byKey.get("p:plm1").level).toBe("warn"); // 1,5 × 3,0 зачіпає сусіда
    expect(V.views.get("p:plm1").foot.material).toBe(V.mat.dash.warn);
    key("KeyR");
    key("KeyR");
    key("KeyR");
    expect(pl.rotation).toBe(0); // 4 повороти — коло
});

test("AC-65 лінійка: 2 кліки → відстань у метрах; Delete просить підтвердження власним діалогом (alert/confirm/prompt не викликаються)", async () => {
    await openEditor();
    const spies = [];
    const orig = {};
    for (const n of ["alert", "confirm", "prompt"]) {
        orig[n] = window[n];
        window[n] = (...a) => {
            spies.push(n);
            return n === "confirm" ? true : null;
        };
    }
    after(() => Object.assign(window, orig));
    key("KeyM");
    expect(V.ruler.on).toBe(true);
    ptr("pointerdown", screenOf(10, 5));
    ptr("pointerdown", screenOf(13, 9));
    expect(V.ruler.pts).toHaveLength(2);
    expect(near(V.ruler.dist, 5, 0.05)).toBe(true);
    expect(queryOne("#rlabel").hidden).toBe(false);
    expect(queryOne("#rlabel").textContent.includes(" м")).toBe(true);
    key("Escape");
    expect(V.ruler.on).toBe(false);

    E.selectObj({ kind: "placement", id: "plm1" });
    key("Delete");
    await animationFrame();
    const dlg = queryOne("dialog[open]");
    expect(dlg).not.toBe(null);
    expect(dlg.textContent.includes("Видалити")).toBe(true);
    expect(S.placements).toHaveLength(1); // до підтвердження — на місці
    queryOne("#dlgYes").click();
    await animationFrame();
    await animationFrame();
    expect(S.placements).toHaveLength(0);
    expect(spies).toHaveLength(0);
});

test("AC-49 права: шар поза editable_layer_ids — поля вимкнені, перетягування заблоковане, підказка «редагує Комірник»", async () => {
    const load = makeLoad({ rights: { is_manager: false, roles: ["technologist"], editable_layer_ids: [3], can_publish: false, can_edit_catalog: false } });
    await openEditor(load);
    // стелаж (шар «Склади», його редагує комірник) — лише для читання
    E.selectObj({ kind: "slot", id: "slrack" });
    await animationFrame();
    const inputs = queryAll("#rightBody input, #rightBody select");
    expect(inputs.length > 3).toBe(true);
    expect(inputs.every((i) => i.disabled)).toBe(true);
    expect(queryAll("#rightBody .note.lock").some((n) => n.textContent.includes("редагує Комірник"))).toBe(true);
    expect(queryOne("#btnDelete").disabled).toBe(true);
    // перетягування: позиція та черга зберігання не змінюються
    const rack = S.slots.find((s) => s.id === "slrack");
    const x0 = rack.x;
    await drag([rack.x + 1, rack.y + 1, 0.2], [rack.x + 6, rack.y + 3, 0]);
    expect(rack.x).toBe(x0);
    expect(toastText().includes("Комірник")).toBe(true);
    // станок шару 3 редагується
    E.selectObj({ kind: "placement", id: "plm1" });
    await animationFrame();
    expect(queryAll('#rightBody input[data-f="x"]').every((i) => !i.disabled)).toBe(true);
});

test("AC-48 поле x у панелі властивостей двигає об'єкт, а перетягування оновлює поле", async () => {
    const load = makeLoad();
    load.checks.find((c) => c.check === "aisles_free").mode = "warn";
    await openEditor(load);
    E.selectObj({ kind: "placement", id: "plm1" });
    await animationFrame();
    const inp = queryOne('#rightBody input[data-f="x"]');
    inp.value = "24";
    inp.dispatchEvent(new Event("input", { bubbles: true }));
    inp.dispatchEvent(new Event("change", { bubbles: true }));
    expect(S.placements[0].x).toBe(24);
    expect(V.views.get("p:plm1").root.position.x).toBe(24);
    await animationFrame(); // рендер оновлює світові матриці перед наступним вибором променем
    await drag([24, 8, 0], [27, 8, 0]);
    expect(near(S.placements[0].x, 27, 0.01)).toBe(true);
    expect(near(Number(queryOne('#rightBody input[data-f="x"]').value), S.placements[0].x, 1e-9)).toBe(true);
});

test("dynamic: об'єкти з dynamic:true пропускаються в collide/aisles/service/fire", async () => {
    const g = await golden("checks_golden");
    const names = ["collide_overlap_0_3", "aisles_free_blocked", "service_free_neighbor_in_front", "fire_exit_blocked"];
    for (const name of names) {
        const sc = g.scenes.find((s) => s.name === name);
        expect(runChecks(sc.state, sc.configs, g.meta.eps_m).length > 0).toBe(true);
        const st = structuredClone(sc.state);
        for (const p of st.placements) {
            p.dynamic = true;
        }
        const kinds = runChecks(st, sc.configs, g.meta.eps_m).map((i) => i.check);
        for (const k of ["collide", "aisles_free", "service_free", "fire"]) {
            expect(kinds.includes(k)).toBe(false);
        }
    }
});

test("code_style 'exact': одна комірка з кодом = code_prefix; інші стилі не змінюються", () => {
    const exact = generateCells("floor_stack", "PLT-1", 5, 5, 0, { rows: 1, cols: 1, code_style: "exact" }, {}, 0);
    expect(exact).toHaveLength(1);
    expect(exact[0].code).toBe("PLT-1");
    const def = generateCells("floor_stack", "PLT-1", 5, 5, 0, { rows: 1, cols: 1 }, {}, 0);
    expect(def[0].code).not.toBe("PLT-1");
    for (const tpl of ["shelf", "cantilever", "pallet_rack"]) {
        const one = generateCells(tpl, "UNL-1", 0, 0, 0, { code_style: "exact", sections: 1, shelves: 1, arms: 1, levels: 1, bays: 1, positions_per_bay: 1 }, {}, 0);
        expect(one[0].code).toBe(one.length === 1 ? "UNL-1" : one[0].code);
    }
});

test("AC-49/R-11 сервер відхилив автозбережену правку: повідомлення і перечитування стану з API-03", async () => {
    let saves = 0;
    const { rpc } = await openEditor(makeLoad(), {
        [SAVE]: () => {
            saves++;
            return saves === 1
                ? { ok: false, code: "rights", message: "Шар «Виробництво» редагує технолог.", op_index: 0 }
                : { ok: true, rev: 5, draft_changes: 0, has_changes: false, id_map: {}, etags: {} };
        },
    });
    E.selectObj({ kind: "placement", id: "plm1" });
    await animationFrame();
    const inp = queryOne('#rightBody input[data-f="x"]');
    inp.value = "24";
    inp.dispatchEvent(new Event("input", { bubbles: true }));
    inp.dispatchEvent(new Event("change", { bubbles: true }));
    expect(S.placements[0].x).toBe(24);
    await advanceTime(2200); // debounce 150 мс + autosave_ms 1500
    await animationFrame();
    await animationFrame();
    expect(saves).toBe(1);
    expect(rpc.of("/f3d/constructor/load")).toHaveLength(2); // перечитано
    expect(S.placements[0].x).toBe(20); // як на сервері
    expect(toastText().includes("редагує технолог")).toBe(true);
});

/* ===== вибір під курсором (пріоритет шарів) і вид «План» ===== */

/** Місце «напільне штабелювання» один код: габарит l × w, висота стосу h (hit-бокс = h). */
const stackSlot = (id, uid, layer, x, y, l, w, h = 2.4) => ({
    id,
    uid,
    layer_id: layer,
    template: "floor_stack",
    code_prefix: uid.toUpperCase(),
    x,
    y,
    rotation: 0,
    params: { rows: 1, cols: 1, cell_l: l, cell_w: w, max_height: h, code_style: "exact" },
    overrides: {},
    parent_location_id: null,
    cell_count: 1,
    etag: `2026-10-17 10:00:00.0000${id}`,
});
const extraLayer = (load, id, uid, name, kind, over = {}) => {
    load.layers.push({ ...load.layers[2], id, uid, name, kind, slot_types: ["floor_stack", "zone"], edit_groups: [], aisles: [], max_floor_load: 0, ...over });
};
/** Клік (down + up без руху) у точці світу; повертає вибраний об'єкт як «kind:id». */
async function clickAt(x, y, z = 0) {
    const pt = screenOf(x, y, z);
    ptr("pointerdown", pt);
    ptr("pointerup", pt);
    await animationFrame();
    return S.sel ? `${S.sel.kind}:${S.sel.id}` : null;
}

test("вибір: верстат активного шару перемагає штабель іншого шару, що його накриває й стоїть ближче до камери", async () => {
    const load = makeLoad();
    load.slots.push(stackSlot(23, "bigstack", 2, 20, 8, 12, 8)); // шар «Склади», 12 × 8 м, висота 2,4 м проти 1,8 м верстата
    await openEditor(load);
    expect(S.ui.layer).toBe("lyp");
    expect(await clickAt(20, 8, machineZ)).toBe("placement:plm1");
    expect(S.ui.layer).toBe("lyp");
});

test("вибір: інженерні мережі й будівля не перехоплюють клік, поки їхній шар не активний", async () => {
    const load = makeLoad();
    extraLayer(load, 4, "lye", "Інженерні мережі", "engineering", { elevation: 7.5 });
    load.slots.push(stackSlot(24, "duct", 4, 20, 8, 40, 30)); // траса на весь цех на відмітці 7,5 м
    await openEditor(load);
    expect(await clickAt(20, 8, machineZ)).toBe("placement:plm1");
    expect(S.ui.layer).toBe("lyp");
    // шар мереж активний — його об'єкт вибирається (над верстатом, на відмітці 7,5 м)
    S.ui.layer = "lye";
    E.syncScene();
    await animationFrame();
    expect(await clickAt(20, 8, 7.5 + 1.2)).toBe("slot:duct");
});

test("вибір: серед рівних перемагає менший габарит; приховані шари не вибираються", async () => {
    const load = makeLoad();
    // обидва штабелі — на шарі «Склади»; великий вищий, тож перший по променю
    load.slots.push(stackSlot(23, "big", 2, 40, 15, 12, 8, 4), stackSlot(24, "small", 2, 40, 15, 3, 2, 2.4));
    extraLayer(load, 5, "lyh", "Прихований", "storage", { visible: false });
    load.slots.push(stackSlot(25, "ghostbig", 5, 40, 24, 8, 4));
    await openEditor(load);
    expect(V.views.has("s:ghostbig")).toBe(false);
    expect(await clickAt(40, 15, 1.2)).toBe("slot:small");
    S.sel = null;
    expect(await clickAt(40, 24, 1.2)).toBe(null);
});

test("вибір: шар, який можна редагувати, перемагає менший об'єкт шару лише для читання", async () => {
    const load = makeLoad({ rights: { is_manager: false, roles: ["storekeeper"], editable_layer_ids: [2], can_publish: false, can_edit_catalog: false } });
    extraLayer(load, 5, "lyt", "Транспорт", "custom");
    load.slots.push(stackSlot(23, "mine", 2, 40, 15, 12, 8, 1), stackSlot(24, "readonly", 5, 40, 15, 3, 2, 4));
    await openEditor(load);
    expect(S.ui.layer).toBe("lyp"); // активний шар технолога, не редагований цим користувачем
    expect(await clickAt(40, 15, 1.2)).toBe("slot:mine");
});

test("вид «План»: обертання вимкнене, ліва кнопка панорамує, вид лишається вирівняним по осях; 3D обертається", async () => {
    await openEditor();
    E.setView("plan");
    await animationFrame();
    expect(V.controls.enableRotate).toBe(false);
    const q0 = V.camera.quaternion.clone();
    const p0 = V.camera.position.clone();
    const from = screenOf(45, 15, 0); // порожнє місце цеху
    for (let i = 0; i < 3; i++) {
        ptr("pointerdown", from);
        ptr("pointermove", { clientX: from.clientX + 40 * (i + 1), clientY: from.clientY + 25 });
        ptr("pointermove", { clientX: from.clientX + 90 * (i + 1), clientY: from.clientY + 50 });
        ptr("pointerup", { clientX: from.clientX + 90 * (i + 1), clientY: from.clientY + 50 });
        await animationFrame();
    }
    expect(V.camera.quaternion.angleTo(q0) < 1e-6).toBe(true);
    expect(V.camera.position.distanceTo(p0) > 1).toBe(true); // панорамування працює
    expect(near(V.camera.position.y, p0.y, 1e-6)).toBe(true); // висота камери не змінилась
    E.setView("iso");
    await animationFrame();
    expect(V.controls.enableRotate).toBe(true);
    const q1 = V.camera.quaternion.clone();
    const f3 = screenOf(45, 15, 0);
    ptr("pointerdown", f3);
    ptr("pointermove", { clientX: f3.clientX + 60, clientY: f3.clientY + 10 });
    ptr("pointerup", { clientX: f3.clientX + 60, clientY: f3.clientY + 10 });
    await animationFrame();
    expect(V.camera.quaternion.angleTo(q1) > 0.01).toBe(true);
});

test("збереження: відкриття редактора нічого не шле в /save; перетягування одного станка пише лише його запис", async () => {
    const { rpc } = await openEditor();
    await advanceTime(5000);
    await animationFrame();
    expect(rpc.of(SAVE)).toHaveLength(0);
    await drag([20, 8, 0], [22, 8, 0]);
    await advanceTime(2200);
    await animationFrame();
    const saves = rpc.of(SAVE);
    expect(saves).toHaveLength(1);
    const ops = saves[0].params.ops;
    expect(ops).toHaveLength(1);
    expect([ops[0].model, ops[0].op, ops[0].id]).toEqual(["td.placement", "write", 31]);
    expect(ops[0].vals).toEqual({ x_m: 22 });
});
