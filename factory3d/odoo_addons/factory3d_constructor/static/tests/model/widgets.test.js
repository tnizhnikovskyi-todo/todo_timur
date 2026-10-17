/** @odoo-module */
// Віджети форми варіанта: f3d_model_preview (AC-41 у віджеті, AC-42) і f3d_model_upload (AC-34/40 у віджеті, AC-39, R-16).
import { after, describe, expect, test } from "@odoo/hoot";
import { queryAllTexts, queryOne } from "@odoo/hoot-dom";
import { animationFrame, mockFetch } from "@odoo/hoot-mock";
import { Component, useState, xml } from "@odoo/owl";
import { allowTranslations, mountWithCleanup } from "@web/../tests/web_test_helpers";
import { UPLOAD_CONFIG } from "@factory3d_constructor/model/upload";
import { F3dModelPreview } from "@factory3d_constructor/widgets/model_preview";
import { F3dModelUpload } from "@factory3d_constructor/widgets/model_upload";
import { PREVIEW_CONFIG, createNullRenderer } from "@factory3d_constructor/widgets/preview_core";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { boxTris, stlAscii, stlBinary } from "./fixtures";
import { blobBytes, file, glbBox, sizeOf, sphereTris, until } from "./helpers";

describe.current.tags("desktop");

/** Мінімальне оточення без mock-сервера (mail у шаблонній базі тягне RPC discuss.channel): лише сервіси, потрібні віджетам. */
function makeEnv() {
    const calls = { orm: [], dialog: [], notify: [] };
    return {
        calls,
        services: {
            orm: {
                call: async (...a) => (calls.orm.push(a), true),
                write: async (...a) => (calls.orm.push(["write", ...a]), true),
            },
            dialog: { add: (C, props) => calls.dialog.push([C, props]) },
            notification: { add: (msg, opts) => calls.notify.push([msg, opts]) },
        },
    };
}

const mount = (C, props, env = makeEnv()) => {
    allowTranslations(); // _t() у віджетах без mock-середовища
    return mountWithCleanup(C, { props, env, noMainContainer: true });
};

function useNullRenderer() {
    PREVIEW_CONFIG.rendererFactory = createNullRenderer;
    after(() => (PREVIEW_CONFIG.rendererFactory = null));
}

/** Мінімальний двійник `record` форми: `data`, `resId`, `update/save/load` (журнал викликів). */
function fakeRecord(data = {}) {
    return {
        id: "datapoint_1",
        resId: 1,
        isNew: false,
        dirty: false,
        updates: [],
        loads: 0,
        saves: 0,
        data: {
            model_glb_id: false,
            model_original_id: false,
            model_status: "none",
            model_meta: {},
            category: "machine",
            length_mm: 3000,
            width_mm: 1500,
            height_mm: 1800,
            image: false,
            ...data,
        },
        async update(changes) {
            this.updates.push(changes);
            Object.assign(this.data, changes);
        },
        async load() {
            this.loads++;
        },
        async save() {
            this.saves++;
            return true;
        },
    };
}

class PreviewHost extends Component {
    static template = xml`<t t-if="state.show"><F3dModelPreview name="'model_glb_id'" record="props.record"/></t>`;
    static components = { F3dModelPreview };
    static props = ["*"];
    setup() {
        this.state = useState({ show: true });
    }
}

const stage = () => queryOne(".o_f3d_mp_stage");
const caption = () => queryOne(".o_f3d_mp_caption").textContent.trim();
const waitModel = async () => {
    const view = await until(() => document.querySelector(".o_f3d_mp_stage")?.__f3d?.model && document.querySelector(".o_f3d_mp_stage").__f3d);
    await animationFrame(); // підпис і сітка оновлюються після state-зміни
    return view;
};

// ------------------------------------------------------------------ f3d_model_preview

test("AC-41 віджет без файла: умовна модель за категорією з габаритами форми + підпис", async () => {
    useNullRenderer();
    await mount(PreviewHost, { record: fakeRecord({ category: "rack", length_mm: 2700, width_mm: 1100, height_mm: 4500 }) });
    const view = await waitModel();
    expect(view.model.userData.f3dGeneric).toBe("rack");
    const [x, y, z] = await sizeOf(view.model);
    expect(Math.abs(x - 2.7) < 0.03 && Math.abs(y - 4.5) < 0.05 && Math.abs(z - 1.1) < 0.02).toBe(true);
    expect(caption()).toBe("Умовна модель (3D-файлу немає)");
    expect(view.renderer.renders > 0).toBe(true);
    expect(view.labels.length).toBe(3); // підписи габаритів
    expect(view.grid !== null).toBe(true); // підлога-сітка
});

test("AC-41 pending_conversion і error → умовна модель, відповідний підпис", async () => {
    useNullRenderer();
    await mount(PreviewHost, { record: fakeRecord({ model_status: "pending_conversion", model_glb_id: false }) });
    let view = await waitModel();
    expect(view.model.userData.f3dGeneric).toBe("machine");
    expect(caption()).toBe("Очікує перетворення на сервері");
    await mount(PreviewHost, { record: fakeRecord({ model_status: "error", category: "panel" }) });
    const stages = document.querySelectorAll(".o_f3d_mp_stage");
    view = await until(() => stages[1].__f3d?.model && stages[1].__f3d);
    await animationFrame();
    expect(view.model.userData.f3dGeneric).toBe("panel");
    expect(document.querySelectorAll(".o_f3d_mp_caption")[1].textContent.includes("Помилка")).toBe(true);
});

test("AC-42 форма з GLB: рендерер, OrbitControls реагують на перетягування, dispose при закритті", async () => {
    useNullRenderer();
    const bytes = new Uint8Array(await blobBytes(await glbBox(0.8, 2, 0.4)));
    const urls = [];
    mockFetch((input) => {
        const url = typeof input === "object" && input?.url ? input.url : String(input);
        urls.push(url);
        // Response у Hoot — MockResponse (текстовий; двійкові дані псує): віддаємо нативний, його Hoot пропускає як є
        const Native = Response.name === "MockResponse" ? Object.getPrototypeOf(Response) : Response;
        return new Native(bytes, { headers: { "Content-Type": "model/gltf-binary" } });
    });
    const host = await mount(PreviewHost, {
        record: fakeRecord({ model_glb_id: { id: 7, display_name: "model.glb" }, model_status: "ok", model_meta: { file_name: "шафа.glb" } }),
    });
    const el = stage();
    el.style.height = "320px";
    el.style.width = "480px";
    const view = await waitModel();
    expect(urls.some((u) => u.includes("/f3d/constructor/model/1/glb"))).toBe(true);
    expect(view.model.userData.f3dGeneric).toBe(undefined); // завантажено GLB, не умовну модель
    const [x, y, z] = await sizeOf(view.model);
    expect(Math.abs(x - 0.8) < 1e-3 && Math.abs(y - 2) < 1e-3 && Math.abs(z - 0.4) < 1e-3).toBe(true);
    expect(caption()).toBe("3D-модель: шафа.glb");
    expect(view.renderer.isNull).toBe(true);

    // перетягування мишею обертає камеру
    const canvas = view.renderer.domElement;
    const a0 = view.controls.getAzimuthalAngle();
    const ev = (type, x_) =>
        canvas.dispatchEvent(new PointerEvent(type, { pointerId: 1, pointerType: "mouse", button: 0, buttons: 1, clientX: x_, clientY: 100, bubbles: true }));
    ev("pointerdown", 100);
    ev("pointermove", 180);
    ev("pointerup", 180);
    await animationFrame();
    expect(Math.abs(view.controls.getAzimuthalAngle() - a0) > 0.01).toBe(true);
    expect(view.renderer.renders > 1).toBe(true); // рендер на вимогу після 'change'

    // «Автообертання»
    queryOne(".o_f3d_mp_spin").click();
    await animationFrame();
    expect(view.spin).toBe(true);
    expect(view.controls.autoRotate).toBe(true);

    // закриття форми: dispose() рендерера і втрата контексту
    expect(view.renderer.disposed).toBe(0);
    host.state.show = false;
    await animationFrame();
    expect(view.disposed).toBe(true);
    expect(view.renderer.disposed).toBe(1);
    expect(view.renderer.contextLost).toBe(1);
    expect(document.querySelector(".o_f3d_mp_stage")).toBe(null);
});

test("превью: GLB недоступний (404) → умовна модель із поясненням", async () => {
    useNullRenderer();
    mockFetch(() => new Response("", { status: 404 }));
    await mount(PreviewHost, { record: fakeRecord({ model_glb_id: { id: 7, display_name: "x" }, model_status: "ok", category: "conveyor" }) });
    const view = await waitModel();
    expect(view.model.userData.f3dGeneric).toBe("conveyor");
    expect(caption().startsWith("Не вдалося завантажити 3D-файл")).toBe(true);
});

test("§11 WebGL недоступний → «3D недоступне в цьому браузері»", async () => {
    PREVIEW_CONFIG.rendererFactory = () => {
        throw new Error("no webgl");
    };
    after(() => (PREVIEW_CONFIG.rendererFactory = null));
    await mount(PreviewHost, { record: fakeRecord() });
    await until(() => document.querySelector(".o_f3d_mp_nogl"));
    expect(queryOne(".o_f3d_mp_nogl").textContent.trim()).toBe("3D недоступне в цьому браузері");
});

// ------------------------------------------------------------------ f3d_model_upload

async function mountUpload(data = {}, props = {}) {
    const record = fakeRecord(data);
    const env = makeEnv();
    await mount(F3dModelUpload, { record, ...props }, env);
    record.env = env;
    return record;
}

async function pickFiles(files) {
    const input = queryOne(".o_f3d_mu_file");
    Object.defineProperty(input, "files", { value: files, configurable: true });
    input.dispatchEvent(new Event("change", { bubbles: true }));
    await animationFrame();
}

const sizeText = () => queryOne(".o_f3d_mu_size").textContent.replace(/\s+/g, " ").trim();

class FakeXHR {
    static last = null;
    constructor() {
        this.upload = {};
        FakeXHR.last = this;
    }
    open(method, url) {
        this.method = method;
        this.url = url;
    }
    send(body) {
        this.body = body;
        queueMicrotask(() => {
            this.status = 200;
            this.responseText = JSON.stringify({ status: "ok", meta: {}, glb_url: "/g", original_url: "/o", message: "" });
            this.upload.onprogress?.({ lengthComputable: true, loaded: 1, total: 1 });
            this.onload();
        });
    }
}

test("AC-39 «Підставити габарити з моделі»: length=800, width=400, height=2000", async () => {
    const rec = await mountUpload({
        model_status: "ok",
        model_original_id: { id: 1, display_name: "a" },
        model_meta: { status: "ok", format: "stl", file_name: "cab.stl", size_bytes: 2048, triangles: 12, size_mm: { x: 800, y: 2000, z: 400 } },
    });
    expect(sizeText()).toBe("800 × 400 × 2000 мм");
    queryOne(".o_f3d_mu_fill").click();
    await animationFrame();
    expect(rec.updates).toEqual([{ length_mm: 800, width_mm: 400, height_mm: 2000 }]);
    expect(rec.data.length_mm).toBe(800);
    expect(rec.data.width_mm).toBe(400);
    expect(rec.data.height_mm).toBe(2000);
});

test("AC-40 .skp у віджеті → «Формат .skp не підтримується…», нічого не готується до завантаження", async () => {
    await mountUpload();
    await pickFiles([file("room.skp", "x")]);
    expect(queryOne(".o_f3d_mu_error").textContent.startsWith("Формат .skp не підтримується")).toBe(true);
    expect(document.querySelector(".o_f3d_mu_upload")).toBe(null);
    expect(document.querySelector(".o_f3d_mu_result")).toBe(null);
});

test("AC-34 файл 21 МБ у віджеті → «Файл більший за 20 МБ»", async () => {
    await mountUpload();
    await pickFiles([file("big.stl", new ArrayBuffer(21 * 1048576))]);
    expect(queryOne(".o_f3d_mu_error").textContent).toBe("Файл більший за 20 МБ");
    expect(document.querySelector(".o_f3d_mu_upload")).toBe(null);
});

test("завантаження STL: перетворення, перемикач одиниць/осі, збереження (API-09: original + glb + meta)", async () => {
    useNullRenderer();
    UPLOAD_CONFIG.XHR = FakeXHR;
    after(() => (UPLOAD_CONFIG.XHR = null));
    const rec = await mountUpload();
    await pickFiles([file("cab.stl", stlAscii(boxTris(800, 400, 2000)))]);
    await until(() => document.querySelector(".o_f3d_mu_upload"));
    expect(sizeText()).toBe("800 × 400 × 2000 мм");
    expect(queryOne(".o_f3d_mu_unit.active").dataset.unit).toBe("mm");
    expect(queryOne(".o_f3d_mu_axis_chk").checked).toBe(true); // STL: Z вгору визначено автоматично
    expect(queryAllTexts(".o_f3d_mu_tri")).toEqual(["12"]);

    // одиниці «м» → 800 000 мм; повернення до «мм»
    queryOne(".o_f3d_mu_unit[data-unit='m']").click();
    await until(() => sizeText().startsWith("800000 "));
    queryOne(".o_f3d_mu_unit[data-unit='mm']").click();
    await until(() => sizeText().startsWith("800 "));
    // вісь Z вгору → довжина × глибина × висота міняються місцями за y/z
    queryOne(".o_f3d_mu_axis_chk").click();
    await until(() => sizeText() === "800 × 2000 × 400 мм");
    queryOne(".o_f3d_mu_axis_chk").click();
    await until(() => sizeText() === "800 × 400 × 2000 мм");

    queryOne(".o_f3d_mu_upload").click();
    await until(() => rec.loads === 1);
    const xhr = FakeXHR.last;
    expect(xhr.method).toBe("POST");
    expect(xhr.url).toBe("/f3d/constructor/model/upload");
    expect(xhr.body.get("variant_id")).toBe("1");
    expect(xhr.body.get("original").name).toBe("cab.stl");
    expect(xhr.body.get("glb").size > 100).toBe(true);
    const meta = JSON.parse(xhr.body.get("meta"));
    expect(meta.size_mm).toEqual({ x: 800, y: 2000, z: 400 });
    expect(meta.status).toBe("ok");
    expect(meta.converted_by).toBe("browser");
    expect(rec.saves).toBe(0); // запис уже збережений
    expect(document.querySelector(".o_f3d_mu_upload")).toBe(null); // staged скинуто після успіху
});

test("новий запис: перед завантаженням спершу record.save()", async () => {
    useNullRenderer();
    UPLOAD_CONFIG.XHR = FakeXHR;
    after(() => (UPLOAD_CONFIG.XHR = null));
    const rec = await mountUpload();
    rec.isNew = true;
    await pickFiles([file("cab.stl", stlAscii(boxTris(800, 400, 2000)))]);
    await until(() => document.querySelector(".o_f3d_mu_upload"));
    queryOne(".o_f3d_mu_upload").click();
    await until(() => rec.loads === 1);
    expect(rec.saves).toBe(1);
});

test("STEP: лише оригінал, pending_conversion, без GLB у запиті", async () => {
    UPLOAD_CONFIG.XHR = FakeXHR;
    after(() => (UPLOAD_CONFIG.XHR = null));
    useNullRenderer();
    const rec = await mountUpload();
    await pickFiles([file("part.step", "ISO-10303-21;")]);
    await until(() => document.querySelector(".o_f3d_mu_upload"));
    expect(queryOne(".o_f3d_mu_status").textContent.trim()).toBe("Очікує перетворення");
    expect(queryOne(".o_f3d_mu_msg").textContent.includes("перетворення на сервері очікує")).toBe(true);
    queryOne(".o_f3d_mu_upload").click();
    await until(() => rec.loads === 1);
    const body = FakeXHR.last.body;
    expect(body.get("original").name).toBe("part.step");
    expect(body.get("glb")).toBe(null);
    expect(JSON.parse(body.get("meta")).status).toBe("pending_conversion");
});

test("R-16 над лімітом: пропозиція «Спростити» / «Залишити як є»", async () => {
    await mountUpload({}, { maxTriangles: 1000 });
    const data = stlBinary(await sphereTris(40, 20));
    await pickFiles([file("ball.stl", data)]);
    await until(() => document.querySelector(".o_f3d_mu_over"));
    expect(queryOne(".o_f3d_mu_over").textContent.includes("1.5 тис. трикутників (ліміт 1 тис.)") || queryOne(".o_f3d_mu_over").textContent.includes("тис. трикутників (ліміт 1 тис.)")).toBe(true);
    expect(Number(queryOne(".o_f3d_mu_tri").textContent) > 1000).toBe(true);
    queryOne(".o_f3d_mu_simplify").click();
    await until(() => !document.querySelector(".o_f3d_mu_over"));
    expect(Number(queryOne(".o_f3d_mu_tri").textContent) <= 1000).toBe(true);
    expect(queryAllTexts(".o_f3d_mu_warn").some((t) => t.startsWith("Модель спрощено"))).toBe(true);
    // «Залишити як є» ховає пропозицію, файл усе одно можна зберегти
    await pickFiles([file("ball2.stl", data)]);
    await until(() => document.querySelector(".o_f3d_mu_over"));
    queryOne(".o_f3d_mu_keep").click();
    await animationFrame();
    expect(document.querySelector(".o_f3d_mu_over")).toBe(null);
    expect(document.querySelector(".o_f3d_mu_upload") !== null).toBe(true);
});

test("«Видалити модель»: підтвердження → action_clear_model і перезавантаження запису", async () => {
    const rec = await mountUpload({
        model_status: "ok",
        model_original_id: { id: 1, display_name: "a" },
        model_meta: { status: "ok", format: "glb", file_name: "a.glb", size_bytes: 10, size_mm: { x: 1, y: 2, z: 3 } },
    });
    queryOne(".o_f3d_mu_clear").click();
    await animationFrame();
    const [Dialog, props] = rec.env.calls.dialog[0];
    expect(Dialog).toBe(ConfirmationDialog);
    expect(props.title).toBe("Видалити модель");
    await props.confirm();
    expect(rec.env.calls.orm).toEqual([["f3d.equipment.variant", "action_clear_model", [[1]]]]);
    expect(rec.loads).toBe(1);
});

test("pending_conversion: «Повторити перетворення» викликає action_retry_convert", async () => {
    const rec = await mountUpload({
        model_status: "pending_conversion",
        model_original_id: { id: 1, display_name: "a" },
        model_meta: { status: "pending_conversion", format: "step", file_name: "a.step", size_bytes: 10, message: "" },
    });
    expect(queryOne(".o_f3d_mu_status").textContent.trim()).toBe("Очікує перетворення");
    expect(queryOne(".o_f3d_mu_msg").textContent.includes("перетворення на сервері очікує")).toBe(true);
    queryOne(".o_f3d_mu_retry").click();
    await until(() => rec.loads === 1);
    expect(rec.env.calls.orm).toEqual([["f3d.equipment.variant", "action_retry_convert", [[1]]]]);
});
