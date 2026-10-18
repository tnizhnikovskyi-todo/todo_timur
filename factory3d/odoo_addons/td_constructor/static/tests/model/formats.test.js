/** @odoo-module */
// AC-40 (JS): формати, відмова .skp; AC-34 (JS): ліміт 20 МБ.
import { describe, expect, test } from "@odoo/hoot";
import { ACCEPT, detectFormat, pickMainFile, rejectMessage } from "@factory3d_constructor/model/formats";
import { ModelImportError } from "@factory3d_constructor/model/normalize";
import { importModelFiles } from "@factory3d_constructor/model/import";
import { file } from "./helpers";

describe.current.tags("desktop");

test("detectFormat: браузер / сервер / відхилено", () => {
    for (const e of ["glb", "gltf", "obj", "fbx", "stl", "3mf", "dae"]) {
        expect(detectFormat({ name: `A.${e.toUpperCase()}` })).toEqual({ ext: e, kind: "browser" });
    }
    for (const e of ["step", "stp", "iges", "igs", "ifc"]) {
        expect(detectFormat({ name: `a.${e}` }).kind).toBe("server");
    }
    expect(detectFormat({ name: "a.skp" }).kind).toBe("rejected");
    expect(detectFormat({ name: "a.mtl" })).toEqual({ ext: "mtl", kind: "rejected", companion: true });
    expect(detectFormat({ name: "noext" }).kind).toBe("rejected");
    expect(ACCEPT.includes(".glb") && ACCEPT.includes(".step") && ACCEPT.includes(".mtl")).toBe(true);
});

test("AC-40 .skp відхиляється з текстом «Формат .skp не підтримується…»", async () => {
    expect(rejectMessage("skp")).toBe("Формат .skp не підтримується. Експортуйте в GLB, OBJ або STEP.");
    const sel = pickMainFile([file("room.skp", "x")]);
    expect(sel.main).toBe(null);
    expect(sel.error.startsWith("Формат .skp не підтримується")).toBe(true);
    let err = null;
    try {
        await importModelFiles([file("room.skp", "x")]);
    } catch (e) {
        err = e;
    }
    expect(err instanceof ModelImportError).toBe(true);
    expect(err.code).toBe("unsupported_format");
    expect(err.message.startsWith("Формат .skp не підтримується")).toBe(true);
});

test("pickMainFile: модель + .mtl + текстура", () => {
    const sel = pickMainFile([file("tex.png", "x"), file("a.mtl", "x"), file("a.obj", "x")]);
    expect(sel.main.name).toBe("a.obj");
    expect(sel.kind).toBe("browser");
    expect(sel.companions.map((f) => f.name).sort()).toEqual(["a.mtl", "tex.png"]);
    expect(pickMainFile([file("a.mtl", "x")]).main).toBe(null);
});

test("AC-34 файл 21 МБ → too_large «Файл більший за 20 МБ», нічого не читається", async () => {
    const big = file("big.stl", new ArrayBuffer(21 * 1048576));
    let err = null;
    try {
        await importModelFiles([big]);
    } catch (e) {
        err = e;
    }
    expect(err.code).toBe("too_large");
    expect(err.message).toBe("Файл більший за 20 МБ");
    // ліміт з параметра
    err = null;
    try {
        await importModelFiles([file("a.stl", new ArrayBuffer(3 * 1048576))], { maxMb: 2 });
    } catch (e) {
        err = e;
    }
    expect(err.message).toBe("Файл більший за 2 МБ");
});

test("STEP/IGES/IFC: лише оригінал, pending_conversion, без GLB", async () => {
    for (const name of ["a.step", "b.stp", "c.iges", "d.igs", "e.ifc"]) {
        const r = await importModelFiles([file(name, "ISO-10303-21;")]);
        expect(r.glb).toBe(null);
        expect(r.meta.status).toBe("pending_conversion");
        expect(r.meta.format).toBe(name.split(".")[1]);
        expect(r.meta.file_name).toBe(name);
        expect(r.meta.converted_by).toBe(null);
        expect(r.meta.message.includes("перетворення на сервері очікує")).toBe(true);
    }
});
