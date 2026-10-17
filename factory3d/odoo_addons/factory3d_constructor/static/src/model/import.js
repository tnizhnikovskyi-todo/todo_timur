/** @odoo-module */
// Конвеєр імпорту моделі в браузері (R-15, DEC-03): файл(и) → завантажувач за розширенням → нормалізація → (спрощення) → GLB.
import { loadLoaders, loadThree, getThree } from "./three";
import {
    DEFAULT_LIMITS, MIME_GLB, baseName, extOf, pickMainFile, tooLargeMessage, trianglesMessage,
} from "./formats";
import { ModelImportError, normalizeMaterials, normalizeObject } from "./normalize";
import { simplifyToTriangles } from "./simplify";

export const MB = 1048576;
export const PENDING_MESSAGE = "Збережено оригінал; перетворення на сервері очікує.";

/** LoadingManager, що відстежує незавершені підзавантаження (текстури) і мапить імена файлів на blob-URL супутніх файлів. */
function makeManager(T, companions) {
    const urls = new Map();
    for (const f of companions) {
        urls.set(baseName(f.name).toLowerCase(), URL.createObjectURL(f));
    }
    const manager = new T.LoadingManager();
    manager.setURLModifier((url) => {
        if (/^(data|blob):/i.test(url)) {
            return url;
        }
        const clean = decodeURIComponent(String(url).split(/[?#]/)[0]);
        return urls.get(baseName(clean).toLowerCase()) || url;
    });
    let pending = 0;
    let waiters = [];
    const settle = () => {
        if (!pending) {
            waiters.splice(0).forEach((r) => r());
        }
    };
    const start = manager.itemStart;
    const end = manager.itemEnd;
    const fail = manager.itemError;
    manager.itemStart = (u) => {
        pending++;
        start(u);
    };
    manager.itemEnd = (u) => {
        pending--;
        end(u);
        settle();
    };
    manager.itemError = (u) => {
        pending--;
        fail(u);
        settle();
    };
    manager.idle = () => new Promise((r) => (pending ? waiters.push(r) : r()));
    manager.dispose = () => {
        waiters = [];
        urls.forEach((u) => URL.revokeObjectURL(u));
    };
    return manager;
}

/** Читає файл моделі в об'єкт three.js (у одиницях файла). */
export async function loadModelObject(files, { T, L, three } = {}) {
    T ||= getThree();
    const sel = pickMainFile(files);
    if (!sel.main) {
        throw new ModelImportError("unsupported_format", sel.error);
    }
    if (sel.kind === "server") {
        throw new ModelImportError("unsupported_format", "Цей формат перетворюється на сервері.");
    }
    L ||= await loadLoaders();
    three ||= await loadThree();
    const { main, ext } = sel;
    const manager = makeManager(T, sel.companions);
    try {
        let obj;
        if (ext === "glb" || ext === "gltf") {
            const loader = new three.GLTFLoader(manager);
            const data = ext === "glb" ? await main.arrayBuffer() : await main.text();
            const gltf = await new Promise((res, rej) => loader.parse(data, "", res, rej));
            obj = gltf.scene || gltf.scenes?.[0];
        } else if (ext === "obj") {
            const text = await main.text();
            const loader = new L.OBJLoader(manager);
            const mtlName = (/^\s*mtllib\s+(.+?)\s*$/m.exec(text) || [])[1];
            const mtlFile =
                sel.companions.find((f) => mtlName && baseName(f.name).toLowerCase() === baseName(mtlName).toLowerCase()) ||
                sel.companions.find((f) => extOf(f.name) === "mtl");
            if (mtlFile) {
                const mats = new L.MTLLoader(manager).parse(await mtlFile.text(), "");
                mats.preload();
                loader.setMaterials(mats);
            }
            obj = loader.parse(text);
        } else if (ext === "stl") {
            const geo = new L.STLLoader(manager).parse(await main.arrayBuffer());
            obj = new T.Mesh(
                geo,
                new T.MeshStandardMaterial({ color: 0xb0b7c0, metalness: 0.2, roughness: 0.6, vertexColors: !!geo.hasColors })
            );
            obj.name = baseName(main.name);
        } else if (ext === "fbx") {
            obj = new L.FBXLoader(manager).parse(await main.arrayBuffer(), "");
        } else if (ext === "3mf") {
            obj = new L.ThreeMFLoader(manager).parse(await main.arrayBuffer());
        } else if (ext === "dae") {
            obj = new L.ColladaLoader(manager).parse(await main.text(), "").scene;
        }
        if (!obj) {
            throw new Error("порожній результат");
        }
        await manager.idle(); // текстури OBJ/MTL, DAE
        return { object: obj, ext, main, companions: sel.companions };
    } catch (e) {
        if (e instanceof ModelImportError) {
            throw e;
        }
        throw new ModelImportError("parse_error", `Не вдалося прочитати файл .${ext}: ${e?.message || e}`);
    } finally {
        manager.dispose();
    }
}

/** `GLTFExporter` → GLB-Blob (R-15 п. 8): binary, embedImages, maxTextureSize 1024, onlyVisible. */
export async function exportGlb(object, { L, maxTextureSize = 1024 } = {}) {
    L ||= await loadLoaders();
    try {
        const buf = await new Promise((res, rej) =>
            new L.GLTFExporter().parse(object, res, rej, {
                binary: true,
                embedImages: true,
                maxTextureSize,
                onlyVisible: true,
            })
        );
        return new Blob([buf], { type: MIME_GLB });
    } catch (e) {
        throw new ModelImportError("export_failed", `Не вдалося перетворити модель у GLB: ${e?.message || e}`);
    }
}

/**
 * `importModelFiles(files, opts)` → `{glb: Blob|null, meta, warnings, object, original, ext, loaded}` (R-15, SPEC §8.3).
 * `opts = {units: 'auto'|'mm'|'cm'|'m'|'in', upAxis: 'auto'|'y'|'z', maxMb, maxTriangles, simplify, loaded}`;
 * `simplify: true` спрощує до `maxTriangles` (R-16), `loaded` — результат попереднього `loadModelObject` (без повторного читання).
 * STEP/IGES/IFC: `glb=null`, `meta.status='pending_conversion'` (DEC-04). Помилки — `ModelImportError` (`code`, український `message`).
 */
export async function importModelFiles(files, opts = {}) {
    const { units = "auto", upAxis = "auto", simplify = false } = opts;
    const maxMb = opts.maxMb || DEFAULT_LIMITS.maxMb;
    const maxTriangles = opts.maxTriangles || DEFAULT_LIMITS.maxTriangles;
    const sel = pickMainFile(files);
    if (!sel.main) {
        throw new ModelImportError("unsupported_format", sel.error);
    }
    const { main, ext } = sel;
    if (main.size > maxMb * MB) {
        throw new ModelImportError("too_large", tooLargeMessage(maxMb));
    }
    const base = { format: ext, file_name: main.name, size_bytes: main.size };
    if (sel.kind === "server") {
        return {
            glb: null,
            object: null,
            original: main,
            ext,
            warnings: [],
            meta: {
                ...base, glb_size_bytes: 0, triangles: 0, bbox_m: null, size_mm: null, units: null, up_axis: null,
                status: "pending_conversion", warnings: [], message: PENDING_MESSAGE, converted_by: null,
            },
        };
    }
    const T = opts.T || (await loadThree()).THREE;
    const loaded = opts.loaded || (await loadModelObject(files, { T }));
    normalizeMaterials(loaded.object, T);
    let n = normalizeObject(loaded.object, { ext, units, upAxis }, T);
    let object = n.object;
    const warnings = [...n.warnings];
    let triangles = n.triangles;
    if (triangles > maxTriangles) {
        if (simplify) {
            const s = simplifyToTriangles(object, maxTriangles, T);
            object = s.object3d;
            warnings.push(
                s.warning || `Модель спрощено: було ${Math.round(triangles / 1000)} тис. трикутників, стало ${Math.round(s.triangles / 1000)} тис.`
            );
            triangles = s.triangles;
        }
        if (triangles > maxTriangles) {
            warnings.push(trianglesMessage(triangles, maxTriangles));
        }
    }
    const glb = await exportGlb(object, { maxTextureSize: opts.maxTextureSize });
    if (glb.size > maxMb * MB) {
        throw new ModelImportError("too_large", `Після перетворення модель більша за ${maxMb} МБ. Спростіть її або зменште текстури.`);
    }
    return {
        glb,
        object,
        original: main,
        ext,
        loaded,
        warnings,
        meta: {
            ...base,
            glb_size_bytes: glb.size,
            triangles,
            bbox_m: n.bboxM,
            size_mm: n.sizeMm,
            units: n.units,
            up_axis: n.upAxis,
            status: "ok",
            warnings: n.warnings,
            message: "",
            converted_by: "browser",
        },
    };
}
