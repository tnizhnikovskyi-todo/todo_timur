/** @odoo-module */
// AC-37, AC-38, AC-35 (JS): конвеєр R-15/R-16 на згенерованих у тесті файлах (GLB, OBJ+MTL, STL, FBX, 3MF, DAE).
import { describe, expect, test } from "@odoo/hoot";
import { importModelFiles } from "@factory3d_constructor/model/import";
import { countTriangles, normalizeObject, sizeToVariantDims } from "@factory3d_constructor/model/normalize";
import { simplifyToTriangles } from "@factory3d_constructor/model/simplify";
import {
    boxTris, colladaText, fbxAscii, mtlText, objText, stlAscii, stlBinary, threeMf,
} from "./fixtures";
import { blobBytes, file, glbBox, loadLoaders, loadThree, sizeOf, sphereTris } from "./helpers";

describe.current.tags("desktop");

const near = (a, b, eps = 1) => Math.abs(a - b) <= eps;
const sizeIs = (s, x, y, z) => near(s.x, x) && near(s.y, y) && near(s.z, z);

/** GLB-Blob → розбір GLTFLoader-ом → габарит у метрах (перевірка кругового проходу). */
async function reparse(glb) {
    const three = await loadThree();
    const buf = await blobBytes(glb);
    const head = new TextDecoder().decode(new Uint8Array(buf, 0, 4));
    const gltf = await new Promise((res, rej) => new three.GLTFLoader().parse(buf, "", res, rej));
    return { head, scene: gltf.scene, size: await sizeOf(gltf.scene) };
}

test("AC-37 GLB (згенерований GLTFExporter-ом) → GLB-Blob, triangles>0, size_mm ±1 мм", async () => {
    const src = await glbBox(0.8, 2, 0.4);
    const r = await importModelFiles([file("шафа.glb", src)]);
    expect(r.glb instanceof Blob).toBe(true);
    expect(r.meta.format).toBe("glb");
    expect(r.meta.triangles).toBe(12);
    expect(r.meta.units).toBe("m");
    expect(r.meta.status).toBe("ok");
    expect(r.meta.converted_by).toBe("browser");
    expect(sizeIs(r.meta.size_mm, 800, 2000, 400)).toBe(true);
    expect(r.meta.glb_size_bytes).toBe(r.glb.size);
    const back = await reparse(r.glb);
    expect(back.head).toBe("glTF");
    expect(near(back.size[0] * 1000, 800) && near(back.size[1] * 1000, 2000) && near(back.size[2] * 1000, 400)).toBe(true);
});

test("AC-37 OBJ+MTL → GLB; кольорове MTL-матеріал зберігається", async () => {
    const r = await importModelFiles([file("box.obj", objText(800, 2000, 400)), file("box.mtl", mtlText())]);
    expect(r.meta.triangles).toBe(12);
    expect(r.meta.units).toBe("mm"); // 2000 > 50
    expect(sizeIs(r.meta.size_mm, 800, 2000, 400)).toBe(true);
    let color = null;
    r.object.traverse((o) => {
        if (o.isMesh) {
            color = o.material.color.getHex();
        }
    });
    expect(color !== 0xb0b7c0).toBe(true); // не «сірий за замовчуванням»
    expect((await reparse(r.glb)).head).toBe("glTF");
});

test("AC-37 OBJ без MTL → GLB із матеріалом за замовчуванням", async () => {
    const r = await importModelFiles([file("box.obj", objText(0.8, 2, 0.4, { mtl: null, material: null }))]);
    expect(r.meta.units).toBe("m");
    expect(sizeIs(r.meta.size_mm, 800, 2000, 400)).toBe(true);
});

test("AC-37 STL (ASCII і бінарний) → GLB", async () => {
    for (const data of [stlAscii(boxTris(800, 400, 2000)), stlBinary(boxTris(800, 400, 2000))]) {
        const r = await importModelFiles([file("box.stl", data)]);
        expect(r.meta.triangles).toBe(12);
        expect(sizeIs(r.meta.size_mm, 800, 2000, 400)).toBe(true);
        expect(r.glb.size > 100).toBe(true);
    }
});

test("AC-37 FBX → GLB", async () => {
    const r = await importModelFiles([file("box.fbx", fbxAscii(800, 2000, 400))]);
    expect(r.meta.format).toBe("fbx");
    expect(r.meta.triangles).toBe(12);
    expect(r.meta.units).toBe("mm");
    expect(sizeIs(r.meta.size_mm, 800, 2000, 400)).toBe(true);
});

test("AC-37 3MF → GLB (Z-up за замовчуванням)", async () => {
    const L = await loadLoaders();
    const r = await importModelFiles([file("box.3mf", threeMf(L.fflate.zipSync, 800, 400, 2000))]);
    expect(r.meta.format).toBe("3mf");
    expect(r.meta.up_axis).toBe("z");
    expect(r.meta.triangles).toBe(12);
    expect(sizeIs(r.meta.size_mm, 800, 2000, 400)).toBe(true);
});

test("AC-37 DAE → GLB", async () => {
    const r = await importModelFiles([file("box.dae", colladaText(0.8, 2, 0.4))]);
    expect(r.meta.format).toBe("dae");
    expect(r.meta.triangles).toBe(12);
    expect(sizeIs(r.meta.size_mm, 800, 2000, 400)).toBe(true);
});

test("AC-38 STL шафи 800×400×2000 мм Z-up: auto → mm, size_mm {x:800,y:2000,z:400}; units m → x=800000", async () => {
    const f = () => [file("cab.stl", stlAscii(boxTris(800, 400, 2000)))];
    const a = await importModelFiles(f(), { units: "auto", upAxis: "auto" });
    expect(a.meta.units).toBe("mm");
    expect(a.meta.up_axis).toBe("z");
    expect(a.meta.size_mm).toEqual({ x: 800, y: 2000, z: 400 });
    expect(a.meta.bbox_m).toEqual([0.8, 2, 0.4]);
    expect(sizeToVariantDims(a.meta.size_mm)).toEqual({ length_mm: 800, width_mm: 400, height_mm: 2000 });
    const m = await importModelFiles(f(), { units: "m" });
    expect(m.meta.units).toBe("m");
    expect(m.meta.size_mm.x).toBe(800000);
    const cm = await importModelFiles(f(), { units: "cm" });
    expect(cm.meta.size_mm).toEqual({ x: 8000, y: 20000, z: 4000 });
    const inch = await importModelFiles(f(), { units: "in" });
    expect(inch.meta.size_mm.x).toBe(20320);
    // перемикач «Вісь Z вгору»: y ↔ z
    const y = await importModelFiles(f(), { upAxis: "y" });
    expect(y.meta.up_axis).toBe("y");
    expect(y.meta.size_mm).toEqual({ x: 800, y: 400, z: 2000 });
});

test("R-15 нормалізація: центр X/Z у 0, min.y = 0, масштаб у метри", async () => {
    const { THREE } = await loadThree();
    const r = await importModelFiles([file("cab.stl", stlAscii(boxTris(800, 400, 2000)))]);
    r.object.updateMatrixWorld(true);
    const b = new THREE.Box3().setFromObject(r.object, true);
    expect(near(b.min.y, 0, 1e-6)).toBe(true);
    expect(near((b.min.x + b.max.x) / 2, 0, 1e-6)).toBe(true);
    expect(near((b.min.z + b.max.z) / 2, 0, 1e-6)).toBe(true);
    expect(near(b.max.y, 2, 1e-6)).toBe(true);
});

test("R-15 glTF: одиниці «m», але при max>50 — попередження «Схоже, одиниці — мм»", async () => {
    const { THREE } = await loadThree();
    const mesh = new THREE.Mesh(new THREE.BoxGeometry(800, 2000, 400), new THREE.MeshStandardMaterial());
    const out = normalizeObject(mesh, { ext: "glb" }, THREE);
    expect(out.units).toBe("m");
    expect(out.warnings.some((w) => w.startsWith("Схоже, одиниці — мм"))).toBe(true);
    expect(normalizeObject(mesh.clone(), { ext: "glb", units: "mm" }, THREE).warnings.length).toBe(0);
});

test("порожній файл без геометрії → empty", async () => {
    let err = null;
    try {
        await importModelFiles([file("e.obj", "# empty\n")]);
    } catch (e) {
        err = e;
    }
    expect(err.code).toBe("empty");
});

test("AC-35 simplifyToTriangles(sphere100k, 50000) → triangles ≤ 50000", async () => {
    const { THREE } = await loadThree();
    const mesh = new THREE.Mesh(new THREE.SphereGeometry(1, 316, 158), new THREE.MeshStandardMaterial({ color: 0x884422 }));
    const obj = new THREE.Group();
    obj.add(mesh);
    const before = countTriangles(obj);
    expect(before > 90000).toBe(true);
    const r = simplifyToTriangles(obj, 50000, THREE);
    expect(r.triangles <= 50000).toBe(true);
    expect(r.triangles > 25000).toBe(true); // найбільше N, що задовольняє умову (не «до нуля»)
    expect(r.warning).toBe(null);
    expect(countTriangles(obj)).toBe(before); // вхідний об'єкт не змінено
    // матеріал і кольори зберігаються
    expect(r.object3d.children[0].material.color.getHex()).toBe(0x884422);
    expect(r.object3d.children[0].geometry.attributes.normal.count).toBe(r.object3d.children[0].geometry.attributes.position.count);
    // менша ціль → менше трикутників
    expect(simplifyToTriangles(obj, 8000, THREE).triangles <= 8000).toBe(true);
});

test("R-16: недосяжна ціль → найкращий результат + попередження", async () => {
    const { THREE } = await loadThree();
    const obj = new THREE.Group();
    obj.add(new THREE.Mesh(new THREE.SphereGeometry(1, 64, 32), new THREE.MeshStandardMaterial()));
    const r = simplifyToTriangles(obj, 10, THREE);
    expect(r.warning !== null).toBe(true);
    expect(r.triangles > 10).toBe(true);
});

test("AC-35 STL 60 000 трикутників: попередження «60 тис. трикутників при ліміті 50 тис.»; спрощення → ≤ 50000", async () => {
    const tris = await sphereTris(300, 101);
    expect(tris.length).toBe(60000);
    const data = stlBinary(tris);
    const r = await importModelFiles([file("sphere.stl", data)]);
    expect(r.meta.triangles).toBe(60000);
    expect(r.warnings.includes("60 тис. трикутників при ліміті 50 тис.")).toBe(true);
    const s = await importModelFiles([file("sphere.stl", data)], { simplify: true });
    expect(s.meta.triangles <= 50000).toBe(true);
    expect(s.warnings.some((w) => w.startsWith("Модель спрощено"))).toBe(true);
    expect(s.meta.glb_size_bytes > 0).toBe(true);
});

test("STL із нульовими нормалями «facet normal 0 0 0» → нормалі перераховано (модель не чорна)", async () => {
    const r = await importModelFiles([file("cab.stl", stlAscii(boxTris(800, 400, 2000)))]);
    let checked = 0;
    r.object.traverse((o) => {
        if (o.isMesh) {
            const n = o.geometry.attributes.normal;
            for (let i = 0; i < n.count; i++) {
                expect(Math.abs(n.getX(i)) + Math.abs(n.getY(i)) + Math.abs(n.getZ(i)) > 0.5).toBe(true);
                checked++;
            }
        }
    });
    expect(checked).toBe(36);
});

test("OBJ+MTL з текстурою: map_Kd береться з обраних файлів, зображення вшивається в GLB", async () => {
    const canvas = document.createElement("canvas");
    canvas.width = canvas.height = 4;
    const ctx = canvas.getContext("2d");
    ctx.fillStyle = "#ff0000";
    ctx.fillRect(0, 0, 4, 4);
    const png = await new Promise((res) => canvas.toBlob(res, "image/png"));
    const obj =
        "mtllib t.mtl\nv 0 0 0\nv 1 0 0\nv 1 1 0\nv 0 1 0\nvt 0 0\nvt 1 0\nvt 1 1\nvt 0 1\nusemtl M\nf 1/1 2/2 3/3\nf 1/1 3/3 4/4\n";
    const mtl = "newmtl M\nKd 1 1 1\nmap_Kd tex.png\n";
    const withTex = await importModelFiles([file("quad.obj", obj), file("t.mtl", mtl), file("tex.png", png)]);
    let map = null;
    withTex.object.traverse((o) => {
        if (o.isMesh && o.material.map) {
            map = o.material.map;
        }
    });
    expect(map !== null).toBe(true);
    expect(!!map.image).toBe(true);
    expect(withTex.meta.triangles).toBe(2);
    const noTex = await importModelFiles([file("quad.obj", obj), file("t.mtl", "newmtl M\nKd 1 1 1\n")]);
    expect(withTex.glb.size > noTex.glb.size).toBe(true); // зображення всередині GLB
});
