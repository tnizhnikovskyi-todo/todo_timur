/** @odoo-module */
// Формати 3D-моделей (SPEC §8.3, R-15, R-18). Чисті функції без THREE.

/** Перетворення в браузері (DEC-03). */
export const BROWSER_EXT = ["glb", "gltf", "obj", "fbx", "stl", "3mf", "dae"];
/** Зберігається лише оригінал, перетворення на сервері (DEC-04): `pending_conversion`. */
export const SERVER_EXT = ["step", "stp", "iges", "igs", "ifc"];
/** Супутні файли (їх вшиває GLB): матеріали OBJ, буфери glTF, текстури. */
export const COMPANION_EXT = ["mtl", "bin", "png", "jpg", "jpeg", "tga", "bmp", "webp", "gif"];

/** Значення `accept` для `<input type="file" multiple>`. */
export const ACCEPT = [...BROWSER_EXT, "mtl", "bin", "png", "jpg", "jpeg", ...SERVER_EXT].map((e) => `.${e}`).join(",");

/** Ліміти за замовчуванням (параметри `max_model_mb`, `max_triangles` приходять із API-03/`ir.config_parameter`). */
export const DEFAULT_LIMITS = { maxMb: 20, maxTriangles: 50000 };

export const MIME_GLB = "model/gltf-binary";

export function extOf(name) {
    const m = /\.([^.\\/]+)$/.exec(String(name || ""));
    return m ? m[1].toLowerCase() : "";
}

export const baseName = (name) => String(name || "").split(/[\\/]/).pop();

export const rejectMessage = (ext) => `Формат .${ext || "?"} не підтримується. Експортуйте в GLB, OBJ або STEP.`;

/** `detectFormat(file)` → `{ext, kind: 'browser'|'server'|'rejected', companion?: bool}`. `file` — `File` або `{name}`. */
export function detectFormat(file) {
    const ext = extOf(file?.name);
    if (BROWSER_EXT.includes(ext)) {
        return { ext, kind: "browser" };
    }
    if (SERVER_EXT.includes(ext)) {
        return { ext, kind: "server" };
    }
    return { ext, kind: "rejected", companion: COMPANION_EXT.includes(ext) };
}

/**
 * Серед обраних файлів знаходить головний (модель) і супутні.
 * @returns {{main: File|null, kind: string, ext: string, companions: File[], error: string|null}}
 */
export function pickMainFile(files) {
    const list = [...(files || [])];
    const infos = list.map((f) => ({ f, ...detectFormat(f) }));
    const mains = infos.filter((i) => i.kind !== "rejected");
    if (mains.length) {
        const m = mains[0];
        return {
            main: m.f,
            kind: m.kind,
            ext: m.ext,
            companions: infos.filter((i) => i !== m && (i.companion || i.kind !== "rejected")).map((i) => i.f),
            error: null,
        };
    }
    const bad = infos.find((i) => !i.companion) || infos[0];
    return {
        main: null,
        kind: "rejected",
        ext: bad?.ext || "",
        companions: [],
        error: bad ? rejectMessage(bad.ext) : "Оберіть файл моделі.",
    };
}

/** «Файл більший за 20 МБ». */
export const tooLargeMessage = (maxMb) => `Файл більший за ${maxMb} МБ`;

/** «60 тис. трикутників при ліміті 50 тис.» — той самий текст, що `model_warning` на сервері. */
export const trianglesMessage = (tri, max) =>
    `${Math.round(tri / 1000)} тис. трикутників при ліміті ${Math.round(max / 1000)} тис.`;
