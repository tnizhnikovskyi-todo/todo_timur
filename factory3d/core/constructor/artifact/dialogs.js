// Діалоги артефакта (прототип): нова площадка (порожня / приклад), тип обладнання (паспорт), картка варіанта з 3D-моделлю,
// публікація-імітація. В Odoo ці форми — штатні форми записів (діалоги variantForm/passportForm/record там реєструє odoo_host.js),
// тут — вбудовані. Усі діалоги — власні, без alert/confirm/prompt. Реєстрація: `registerArtifactDialogs(adapter)`.
import { CATEGORIES, FRONT_SIDES, LAYER_KINDS, SOLID_SLOTS, TPL, UTIL_KINDS } from "../data.js";
import { cellsOf } from "../cells.js";
import { confirmBox, openDialog } from "../dialogs.js";
import { checkGroup, fld, numInput, selectEl, textInput } from "../fields.js";
import { registries } from "../registry.js";
import { canCatalog } from "../roles.js";
import { E, S, V } from "../state.js";
import { THREE } from "../three.js";
import { $$, clone, fmt, fmtInt, fmtSize, h, ic, rnd, toast, uid } from "../util.js";
import { openPlanDialog } from "../plan_dialog.js";
import { createVariantPreview } from "./preview.js";
import { installOdooSim } from "./odoo_sim.js";

const MODEL_EXT = /\.(glb|gltf|obj|fbx|stl|3mf|dae|step|stp|iges|igs|ifc)$/i;
const MAX_MODEL_MB = 20;
const MAX_TRIANGLES = 50000;
const ROT_MODES = [
    ["q", "Кожні 90°"],
    ["h", "0° і 180°"],
    ["z", "Без повороту"],
    ["any", "Будь-який кут"],
];

function countTris(obj) {
    let n = 0;
    obj.traverse((o) => {
        if (o.isMesh && o.geometry) {
            const g = o.geometry;
            n += g.index ? g.index.count / 3 : g.attributes.position ? g.attributes.position.count / 3 : 0;
        }
    });
    return Math.round(n);
}

/* ===== нова площадка (CD-22, CD-24) ===== */
export function openNewSite() {
    const hasSample = S.app.sites.some((s) => s.id === "sample");
    let kind = "empty";
    const name = h("input", { type: "text", value: "Нова площадка", "aria-label": "Назва" });
    const radio = (v, t, sub, dis) =>
        h(
            "label",
            { class: "frow", style: { alignItems: "flex-start", margin: "6px 0" } },
            h("input", {
                type: "radio",
                name: "sk",
                value: v,
                checked: v === kind,
                disabled: dis,
                onchange: () => {
                    kind = v;
                    name.value = v === "sample" ? "Меблеве підприємство (приклад)" : "Нова площадка";
                },
            }),
            h("div", null, h("div", null, t), h("div", { class: "small muted" }, sub))
        );
    openDialog({
        title: "Нова площадка",
        cls: "narrow",
        body: h(
            "div",
            { class: "fcol" },
            fld("Назва", name),
            radio("empty", "Порожня площадка", "Будівля 60×30×8 м, п’ять базових шарів, каталог із типовими варіантами."),
            radio("sample", "Меблеве підприємство (приклад)", hasSample ? "Приклад уже є в списку площадок." : "Наш завод: будівля 150×72×9 м, стелажі, верстати, проходи, виходи.", hasSample)
        ),
        actions: [
            { label: "Скасувати" },
            {
                label: "Створити",
                cls: "primary",
                id: "dlgCreateSite",
                onClick: async () => {
                    const ok = await E.createSite({ kind, name: name.value.trim() || "Нова площадка" });
                    return ok ? undefined : false;
                },
            },
        ],
    });
}

/* ===== паспорт (тип обладнання) ===== */
export function openPassportDialog({ passport }) {
    const isNew = !passport;
    const pp = isNew ? { id: uid("pp_"), category: "machine", role: "", name: "Новий тип", manufacturer: "", model: "", variants: [] } : passport;
    const d = clone(pp);
    const dis = !canCatalog();
    const used = pp.variants.some((v) => S.placements.some((pl) => pl.variant_id === v.id));
    openDialog({
        title: isNew ? "Новий тип обладнання" : "Тип обладнання (паспорт)",
        cls: "narrow",
        body: h(
            "div",
            { class: "fcol" },
            fld("Назва типу", textInput({ value: d.name, dis, label: "Назва", set: (v) => { d.name = v; } })),
            fld("Категорія (від неї залежить умовна модель)", selectEl(Object.entries(CATEGORIES), d.category, (v) => { d.category = v; }, dis, "Категорія")),
            h(
                "div",
                { class: "grid2" },
                fld("Виробник", textInput({ value: d.manufacturer, dis, label: "Виробник", set: (v) => { d.manufacturer = v; } })),
                fld("Модель", textInput({ value: d.model, dis, label: "Модель", set: (v) => { d.model = v; } }))
            ),
            fld("Роль (код)", textInput({ value: d.role, dis, label: "Роль", set: (v) => { d.role = v; } })),
            !isNew && used ? h("div", { class: "note" }, "Тип використовується на сцені: видалення вимкнено.") : null
        ),
        actions: [
            !isNew
                ? {
                      label: "Видалити тип",
                      cls: "danger",
                      disabled: dis || used,
                      onClick: async () => {
                          const ok = await confirmBox({ title: "Видалити тип?", text: `«${pp.name}» і його варіанти (${pp.variants.length}) буде видалено з каталогу.`, ok: "Видалити", danger: true });
                          if (!ok) {
                              return false;
                          }
                          S.catalog = S.catalog.filter((x) => x !== pp);
                          E.commit();
                      },
                  }
                : null,
            { label: "Скасувати" },
            {
                label: "Зберегти",
                cls: "primary",
                disabled: dis,
                onClick: () => {
                    Object.assign(pp, { name: d.name, category: d.category, manufacturer: d.manufacturer, model: d.model, role: d.role });
                    if (isNew) {
                        S.catalog.push(pp);
                    }
                    E.commit();
                },
            },
        ].filter(Boolean),
    });
}

/* ===== картка варіанта (CD-11, CD-12, CD-15…19) ===== */
export function openVariantCard({ variant, passport }, { adapter }) {
    const pp = passport;
    if (!pp) {
        return;
    }
    const isNew = !variant;
    const orig = variant || {
        id: uid("v_"),
        name: "Варіант",
        length: 2000,
        width: 1000,
        height: 1800,
        service: { front: 1000, back: 300, left: 300, right: 300 },
        rotations: "q",
        layer_kinds: ["production"],
        slot_types: ["machine_spot"],
        utilities: [],
        power_kw: 0,
        panel: "",
        weight_kg: 500,
        floor_load: null,
        anchor: "center",
        front_side: "s",
        model: null,
    };
    const dis = !canCatalog();
    const vd = clone(orig);
    vd.service = vd.service || { front: 0, back: 0, left: 0, right: 0 };
    vd.utilities = vd.utilities || [];
    const M = { meta: vd.model ? clone(vd.model) : null, parsed: null, files: null, units: "mm", zup: false, norm: null, removed: false, msg: null };
    if (vd.model) {
        M.units = vd.model.units || "mm";
        M.zup = vd.model.up_axis === "z";
        M.norm = V.models.get(vd.id) || null;
    }
    let preview = null;
    const refreshPreview = () => {
        if (preview) {
            preview.show(pp.category, vd, M.norm);
        }
    };
    const set = (fn) => (v) => {
        fn(v);
        refreshPreview();
    };
    const pvBox = h("div", { class: "pv" }, h("div", { class: "ph" }, "Перегляд: обертання мишею / пальцем"));
    const infoBox = h("div");
    const msgBox = h("div");
    const dimsEl = (k, l) => fld(l, numInput({ value: vd[k], dis, min: 10, max: 60000, step: 10, int: 1, label: l, f: k, set: set((v) => { vd[k] = v; }) }), "мм");
    const utilBox = h("div");
    const renderUtil = () => {
        utilBox.replaceChildren(
            ...vd.utilities.map((u, i) =>
                h(
                    "div",
                    { class: "mini u", style: { gridTemplateColumns: "minmax(0,1fr) 62px 62px 62px 24px" } },
                    selectEl(Object.entries(UTIL_KINDS), u.kind, (v) => { u.kind = v; }, dis, "Вид"),
                    ...["x", "y", "z"].map((k) => numInput({ value: u[k + "_mm"], dis, step: 50, label: k, set: (v) => { u[k + "_mm"] = v; } })),
                    h("button", { class: "xbtn", type: "button", disabled: dis, "aria-label": "Видалити", onclick: () => { vd.utilities.splice(i, 1); renderUtil(); } }, ic("x"))
                )
            ),
            h("button", { class: "fbtn sm", type: "button", disabled: dis, onclick: () => { vd.utilities.push({ kind: "electric", x_mm: 0, y_mm: 0, z_mm: 1500 }); renderUtil(); } }, ic("plus"), "Точка підключення")
        );
    };
    renderUtil();
    const q = vd.floor_load != null && vd.floor_load !== "" ? vd.floor_load : "";
    const left = h(
        "div",
        { class: "fcol" },
        h("div", { class: "small muted" }, `Тип: ${pp.name} · ${CATEGORIES[pp.category] || pp.category}${pp.manufacturer && pp.manufacturer !== "—" ? " · " + pp.manufacturer : ""}`),
        dis ? h("div", { class: "note lock" }, S.app.mode === "edit" ? "Каталог редагують Менеджер і Технолог." : "Режим перегляду.") : null,
        fld("Назва варіанта", textInput({ value: vd.name, dis, label: "Назва", set: (v) => { vd.name = v; } })),
        h("div", { class: "grid3" }, dimsEl("length", "Довжина"), dimsEl("width", "Ширина"), dimsEl("height", "Висота")),
        h("div", { class: "lbl" }, "Зона обслуговування, мм"),
        h(
            "div",
            { class: "grid4" },
            [["front", "спереду"], ["back", "ззаду"], ["left", "зліва"], ["right", "справа"]].map(([k, l]) =>
                fld(l, numInput({ value: vd.service[k], dis, min: 0, step: 50, int: 1, label: l, set: set((v) => { vd.service[k] = v; }) }))
            )
        ),
        fld("Дозволені повороти", selectEl(ROT_MODES, vd.rotations || "q", (v) => { vd.rotations = v; }, dis, "Повороти")),
        fld("Де можна ставити: шари", checkGroup(Object.entries(LAYER_KINDS), vd.layer_kinds, (v) => { vd.layer_kinds = v; }, dis)),
        fld("Де можна ставити: типи місць", checkGroup(Object.entries(TPL).map(([k, t]) => [k, t.name]), vd.slot_types, (v) => { vd.slot_types = v; }, dis)),
        h("div", { class: "lbl" }, "Точки підключення (від центру, мм)"),
        utilBox,
        h(
            "div",
            { class: "grid3" },
            fld("Потужність", numInput({ value: vd.power_kw, dis, min: 0, step: 0.5, label: "Потужність", set: (v) => { vd.power_kw = v; } }), "кВт"),
            fld("Щит", textInput({ value: vd.panel, dis, label: "Щит", set: (v) => { vd.panel = v; } })),
            fld("Маса", numInput({ value: vd.weight_kg, dis, min: 0, step: 50, int: 1, label: "Маса", set: (v) => { vd.weight_kg = v; } }), "кг")
        ),
        h(
            "div",
            { class: "grid3" },
            fld("Навантаження на підлогу", numInput({ value: q, dis, min: 0, step: 0.5, label: "Навантаження", set: (v) => { vd.floor_load = v > 0 ? v : null; } }), "кН/м², 0 = з маси"),
            fld("Точка прив’язки", selectEl([["center", "Центр"], ["corner", "Кут (лівий-нижній)"]], vd.anchor, (v) => { vd.anchor = v; }, dis, "Прив’язка")),
            fld("Передня сторона", selectEl(Object.entries(FRONT_SIDES), vd.front_side, (v) => { vd.front_side = v; refreshPreview(); }, dis, "Передня сторона"))
        )
    );

    /* --- блок моделі --- */
    const fileIn = h("input", { type: "file", multiple: true, accept: ".glb,.gltf,.obj,.mtl,.fbx,.stl,.3mf,.dae,.step,.stp,.iges,.igs,.ifc", hidden: true, id: "modelFile", "aria-label": "Файл моделі" });
    const dropEl = h(
        "div",
        { class: "drop", tabindex: 0, role: "button", onclick: () => !dis && fileIn.click(), onkeydown: (e) => { if ((e.key === "Enter" || e.key === " ") && !dis) { fileIn.click(); } } },
        "Оберіть або перетягніть файл моделі",
        h("div", { class: "small" }, "GLB/glTF, OBJ(+MTL), FBX, STL, 3MF, DAE; STEP/IGES/IFC — на сервері")
    );
    ["dragover", "dragenter"].forEach((t) => dropEl.addEventListener(t, (e) => { e.preventDefault(); dropEl.classList.add("over"); }));
    ["dragleave", "drop"].forEach((t) => dropEl.addEventListener(t, () => dropEl.classList.remove("over")));
    dropEl.addEventListener("drop", (e) => {
        e.preventDefault();
        if (!dis) {
            onFiles(e.dataTransfer.files);
        }
    });
    fileIn.addEventListener("change", () => onFiles(fileIn.files));
    const say = (kind, text) => {
        M.msg = text ? { kind, text } : null;
        msgBox.replaceChildren(...(M.msg ? [h("div", { class: "note " + (kind === "err" ? "err" : kind === "warn" ? "lock" : ""), style: { marginTop: "6px" }, role: "status" }, text)] : []));
    };
    const renormalize = () => {
        if (M.parsed) {
            M.norm = E.normalizeModel(adapter.orient(M.parsed.obj, M.units, M.zup, THREE));
        }
    };
    const renderInfo = () => {
        const mt = M.removed ? null : M.parsed ? M.parsed.meta : M.meta;
        if (!mt) {
            infoBox.replaceChildren(h("div", { class: "small muted", style: { marginTop: "6px" } }, "Моделі немає: у 3D показується умовна модель за категорією «" + (CATEGORIES[pp.category] || pp.category) + "»."));
            return;
        }
        const sz = M.norm ? M.norm.size : null;
        infoBox.replaceChildren(
            h(
                "dl",
                { class: "kv", style: { marginTop: "8px" } },
                h("dt", null, "Файл"),
                h("dd", null, mt.file_name),
                h("dt", null, "Формат"),
                h("dd", null, String(mt.format).toUpperCase()),
                h("dt", null, "Розмір файлу"),
                h("dd", null, fmtSize(mt.size_bytes)),
                h("dt", null, "Трикутників"),
                h("dd", null, fmtInt(mt.triangles)),
                h("dt", null, "Габарити моделі"),
                h("dd", null, sz ? `${fmtInt(sz.x * 1000)} × ${fmtInt(sz.z * 1000)} × ${fmtInt(sz.y * 1000)} мм` : "—")
            ),
            h(
                "div",
                { class: "frow wrap", style: { marginTop: "8px" } },
                h("span", { class: "lbl" }, "Одиниці"),
                h("span", { class: "seg" }, ["mm", "m"].map((u) => h("button", { type: "button", "aria-pressed": String(M.units === u), disabled: dis, onclick: () => { M.units = u; renormalize(); renderInfo(); refreshPreview(); } }, u === "mm" ? "мм" : "м"))),
                h("label", { class: "frow" }, h("input", { type: "checkbox", checked: M.zup, disabled: dis, onchange: (e) => { M.zup = e.target.checked; renormalize(); renderInfo(); refreshPreview(); } }), "вісь Z вгору")
            ),
            h(
                "div",
                { class: "frow wrap", style: { marginTop: "8px" } },
                h(
                    "button",
                    {
                        class: "fbtn sm",
                        type: "button",
                        disabled: dis || !sz,
                        onclick: () => {
                            vd.length = Math.max(10, Math.round(sz.x * 1000));
                            vd.width = Math.max(10, Math.round(sz.z * 1000));
                            vd.height = Math.max(10, Math.round(sz.y * 1000));
                            $$("[data-f=length],[data-f=width],[data-f=height]", dlg).forEach((el) => {
                                el.value = String(vd[el.dataset.f]);
                            });
                            refreshPreview();
                        },
                    },
                    "Підставити габарити з моделі"
                ),
                h("button", { class: "fbtn sm danger", type: "button", disabled: dis, onclick: () => { M.removed = true; M.parsed = null; M.files = null; M.norm = null; say(null); renderInfo(); refreshPreview(); } }, "Прибрати модель")
            )
        );
    };
    async function onFiles(list) {
        const arr = [...list];
        if (!arr.length) {
            return;
        }
        say(null);
        const main = arr.find((f) => MODEL_EXT.test(f.name));
        if (!main) {
            say("err", "Невідомий формат. Підтримуються: GLB/glTF, OBJ(+MTL), FBX, STL, 3MF, DAE.");
            return;
        }
        const ext = main.name.split(".").pop().toLowerCase();
        if (["step", "stp", "iges", "igs", "ifc"].includes(ext)) {
            say("warn", `Формат .${ext.toUpperCase()}: перетворення на сервері (Odoo). У прототипі браузер його не читає — збережемо оригінал і зробимо облегчений GLB на сервері.`);
            return;
        }
        const total = arr.reduce((a, f) => a + f.size, 0);
        if (total > MAX_MODEL_MB * 1048576) {
            say("err", `Файл завеликий: ${fmt(total / 1048576, 1)} МБ. Ліміт — ${MAX_MODEL_MB} МБ. Зменште модель або передайте оригінал на сервер для перетворення.`);
            return;
        }
        say("", "Читаю модель…");
        try {
            const list2 = await Promise.all(arr.map(async (f) => ({ name: f.name, buf: await f.arrayBuffer() })));
            const keep = list2.filter((f) => f.name === main.name || /\.mtl$/i.test(f.name));
            const obj = await adapter.parseModel(keep, ext, THREE);
            const tris = countTris(obj);
            const raw = new THREE.Box3().setFromObject(obj).getSize(new THREE.Vector3());
            M.parsed = { obj, meta: { file_name: main.name, format: ext, size_bytes: total, triangles: tris } };
            M.files = keep;
            M.removed = false;
            M.units = Math.max(raw.x, raw.y, raw.z) > 50 ? "mm" : "m";
            M.zup = ["stl", "3mf"].includes(ext);
            renormalize();
            renderInfo();
            refreshPreview();
            if (tris > MAX_TRIANGLES) {
                say("warn", `Трикутників: ${fmtInt(tris)} (> 50 000). Рекомендуємо спростити модель — на сервері (Odoo) буде облегчений GLB. У прототипі модель усе одно показана.`);
            } else {
                say("ok", `Модель прочитано: ${fmtInt(tris)} трикутників.`);
            }
        } catch (e) {
            console.warn(e);
            M.parsed = null;
            say("err", "Не вдалося прочитати модель: " + (e && e.message ? e.message : e));
        }
    }
    const right = h(
        "div",
        { class: "fcol" },
        h("div", { class: "lbl" }, "3D-модель"),
        pvBox,
        dropEl,
        fileIn,
        msgBox,
        infoBox,
        h("div", { class: "small muted" }, "STEP / IGES / IFC — перетворення на сервері (Odoo): зберігаємо оригінал і облегчений GLB, габарити й превʼю з моделі. Ліміт: 20 МБ і 50 тис. трикутників.")
    );
    renderInfo();
    const dlg = openDialog({
        title: isNew ? "Новий варіант" : "Варіант: " + orig.name,
        cls: "wide",
        body: h("div", { class: "vcard" }, left, right),
        onClose: () => {
            if (preview) {
                preview.dispose();
            }
        },
        actions: [
            !isNew
                ? {
                      label: "Видалити варіант",
                      cls: "danger",
                      disabled: dis,
                      onClick: async () => {
                          if (S.placements.some((p) => p.variant_id === orig.id)) {
                              toast("Варіант використовується на сцені — спершу приберіть об’єкти.", "warn");
                              return false;
                          }
                          const ok = await confirmBox({ title: "Видалити варіант?", text: `«${orig.name}» буде видалено з каталогу.`, ok: "Видалити", danger: true });
                          if (!ok) {
                              return false;
                          }
                          pp.variants = pp.variants.filter((x) => x.id !== orig.id);
                          await adapter.deleteModel(orig.id);
                          V.models.delete(orig.id);
                          E.commit();
                      },
                  }
                : null,
            { label: "Скасувати" },
            {
                label: "Зберегти",
                cls: "primary",
                disabled: dis,
                onClick: async () => {
                    if (!vd.name.trim()) {
                        toast("Вкажіть назву варіанта.", "warn");
                        return false;
                    }
                    if (M.removed) {
                        vd.model = null;
                        await adapter.deleteModel(vd.id);
                        V.models.delete(vd.id);
                    } else if (M.parsed) {
                        const sz = M.norm.size;
                        vd.model = {
                            status: "ok",
                            format: M.parsed.meta.format,
                            file_name: M.parsed.meta.file_name,
                            size_bytes: M.parsed.meta.size_bytes,
                            triangles: M.parsed.meta.triangles,
                            units: M.units,
                            up_axis: M.zup ? "z" : "y",
                            size_mm: [Math.round(sz.x * 1000), Math.round(sz.z * 1000), Math.round(sz.y * 1000)],
                            converted_by: "browser",
                        };
                        await adapter.uploadModel(vd.id, { ext: M.parsed.meta.format, files: M.files });
                        V.models.set(vd.id, M.norm);
                    } else if (vd.model && M.meta) {
                        vd.model.units = M.units;
                        vd.model.up_axis = M.zup ? "z" : "y";
                        if (M.norm) {
                            const sz = M.norm.size;
                            vd.model.size_mm = [Math.round(sz.x * 1000), Math.round(sz.z * 1000), Math.round(sz.y * 1000)];
                            V.models.delete(vd.id); // одиниці й вісь змінилися: модель перебудується з файлів
                        }
                    }
                    vd.rotations = vd.rotations || "q";
                    if (isNew) {
                        pp.variants.push(vd);
                    } else {
                        Object.assign(orig, vd);
                    }
                    E.commit();
                    if (!V.models.has(vd.id) && vd.model) {
                        await E.loadVariantModels();
                    }
                },
            },
        ].filter(Boolean),
    });
    preview = createVariantPreview(pvBox);
    refreshPreview();
}

/* ===== публікація-імітація (CD-20, CD-21) ===== */
function cellMap(slots) {
    const m = new Map();
    for (const s of slots) {
        if (SOLID_SLOTS.includes(s.template)) {
            for (const c of cellsOf(s)) {
                m.set(c.code, [c.capacity, c.max_load_kg, c.disabled ? 1 : 0, rnd(c.x, 2), rnd(c.y, 2), rnd(s.rotation || 0, 0)].join("|"));
            }
        }
    }
    return m;
}

/** Зведення змін чернетки відносно активної версії. */
export function computeDiff(St, base) {
    const b = !St.site.active_version || !base ? { slots: [], placements: [], catalog: [], layers: [] } : base;
    const bc = cellMap(b.slots);
    const cc = cellMap(St.slots);
    const created = [];
    const changed = [];
    const removed = [];
    for (const [k, v] of cc) {
        if (!bc.has(k)) {
            created.push(k);
        } else if (bc.get(k) !== v) {
            changed.push(k);
        }
    }
    for (const k of bc.keys()) {
        if (!cc.has(k)) {
            removed.push(k);
        }
    }
    const bp = new Map(b.placements.map((p) => [p.id, JSON.stringify(p)]));
    const pc = [];
    const pch = [];
    const prm = [];
    for (const p of St.placements) {
        if (!bp.has(p.id)) {
            pc.push(p);
        } else if (bp.get(p.id) !== JSON.stringify(p)) {
            pch.push(p);
        }
    }
    const cur = new Set(St.placements.map((p) => p.id));
    for (const p of b.placements) {
        if (!cur.has(p.id)) {
            prm.push(p);
        }
    }
    const bv = new Map();
    for (const p of b.catalog) {
        for (const v of p.variants) {
            bv.set(v.id, JSON.stringify(v));
        }
    }
    let vch = 0;
    for (const p of St.catalog) {
        for (const v of p.variants) {
            if (bv.has(v.id) && bv.get(v.id) !== JSON.stringify(v)) {
                vch++;
            }
        }
    }
    return { cellsNew: created, cellsChanged: changed, cellsRemoved: removed, plNew: pc, plChanged: pch, plRemoved: prm, variantsChanged: vch };
}

/** Публікація (імітація): діалог плану ядра (`plan_dialog.js`) — види рядків, область, залежності, журнал і відкат (F02). */
export function openPublish({ adapter, onClose }) {
    return openPlanDialog({ adapter, onClose });
}

/** Підключає діалоги артефакта (замість форм Odoo): викликає хост прототипу перед монтуванням. */
export function registerArtifactDialogs(adapter) {
    const reg = registries.dialogs;
    reg.add("newSite", () => openNewSite(), { force: true });
    reg.add("passportForm", (args) => openPassportDialog(args), { force: true });
    reg.add("variantForm", (args) => openVariantCard(args, { adapter }), { force: true });
    reg.add("record", () => toast("Записів Odoo в прототипі немає.", "warn"), { force: true });
    adapter.openPublish = openPublish;
    installOdooSim(adapter); // стан «Odoo» прототипа: план, журнал, відкат, категорії, правила (artifact/odoo_sim.js)
}

