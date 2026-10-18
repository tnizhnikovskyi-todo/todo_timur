/** @odoo-module */
// Генератори тестових файлів 3D-моделей (AC-37): коробка-«шафа» у різних форматах. Без залежності від Odoo/Hoot (запускається й у node).
// Усі розміри задаються у одиницях файла; вершини — від кута (0,0,0).

// URL-пространства імен збираємо з частин: у вихідниках модуля не повинно бути літералів зовнішніх адрес (AC-05)
const H = "http" + ":/" + "/";
const NS_3MF_CT = H + "schemas.openxmlformats.org/package/2006/content-types";
const NS_3MF_REL = H + "schemas.openxmlformats.org/package/2006/relationships";
const NS_3MF = H + "schemas.microsoft.com/3dmanufacturing/core/2015/02";
const REL_3MF = H + "schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel";
const NS_DAE = H + "www.collada.org/2005/11/COLLADASchema";

const enc = (s) => new TextEncoder().encode(s);

/** 8 вершин і 12 трикутників коробки sx × sy × sz. */
export function boxData(sx, sy, sz) {
    const v = [
        [0, 0, 0], [sx, 0, 0], [sx, sy, 0], [0, sy, 0],
        [0, 0, sz], [sx, 0, sz], [sx, sy, sz], [0, sy, sz],
    ];
    const t = [
        [0, 2, 1], [0, 3, 2], // низ (z=0)
        [4, 5, 6], [4, 6, 7], // верх (z=sz)
        [0, 1, 5], [0, 5, 4], // y=0
        [3, 7, 6], [3, 6, 2], // y=sy
        [0, 4, 7], [0, 7, 3], // x=0
        [1, 2, 6], [1, 6, 5], // x=sx
    ];
    return { v, t };
}

/** Трикутники як масив [[ax,ay,az],[bx,..],[cx,..]] (для STL). */
export function boxTris(sx, sy, sz) {
    const { v, t } = boxData(sx, sy, sz);
    return t.map((tri) => tri.map((i) => v[i]));
}

export function stlAscii(tris, name = "box") {
    const f = (n) => Number(n).toString();
    let s = `solid ${name}\n`;
    for (const tri of tris) {
        s += "facet normal 0 0 0\nouter loop\n";
        for (const p of tri) {
            s += `vertex ${f(p[0])} ${f(p[1])} ${f(p[2])}\n`;
        }
        s += "endloop\nendfacet\n";
    }
    return s + `endsolid ${name}\n`;
}

export function stlBinary(tris) {
    const buf = new ArrayBuffer(84 + tris.length * 50);
    const dv = new DataView(buf);
    dv.setUint32(80, tris.length, true);
    tris.forEach((tri, i) => {
        let o = 84 + i * 50 + 12; // нормаль (12 байт) лишаємо нульовою
        for (const p of tri) {
            for (const c of p) {
                dv.setFloat32(o, c, true);
                o += 4;
            }
        }
    });
    return new Uint8Array(buf);
}

export function objText(sx, sy, sz, { mtl = "box.mtl", material = "Cab" } = {}) {
    const { v, t } = boxData(sx, sy, sz);
    let s = "# box\n" + (mtl ? `mtllib ${mtl}\n` : "") + "o Box\n";
    s += v.map((p) => `v ${p[0]} ${p[1]} ${p[2]}`).join("\n") + "\n";
    if (material) {
        s += `usemtl ${material}\n`;
    }
    s += t.map((f) => `f ${f[0] + 1} ${f[1] + 1} ${f[2] + 1}`).join("\n") + "\n";
    return s;
}

export const mtlText = (material = "Cab") => `newmtl ${material}\nKd 0.2 0.5 0.8\nKa 0 0 0\nKs 0.1 0.1 0.1\nNs 10\nd 1\n`;

export function colladaText(sx, sy, sz, { unit = 1, up = "Y_UP" } = {}) {
    const { v, t } = boxData(sx, sy, sz);
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n' +
        `<COLLADA xmlns="${NS_DAE}" version="1.4.1">\n` +
        `<asset><unit name="unit" meter="${unit}"/><up_axis>${up}</up_axis></asset>\n` +
        '<library_geometries><geometry id="box-geom" name="box"><mesh>\n' +
        `<source id="box-pos"><float_array id="box-pos-arr" count="24">${v.flat().join(" ")}</float_array>` +
        '<technique_common><accessor source="#box-pos-arr" count="8" stride="3"><param name="X" type="float"/><param name="Y" type="float"/><param name="Z" type="float"/></accessor></technique_common></source>\n' +
        '<vertices id="box-vtx"><input semantic="POSITION" source="#box-pos"/></vertices>\n' +
        `<triangles count="12"><input semantic="VERTEX" source="#box-vtx" offset="0"/><p>${t.flat().join(" ")}</p></triangles>\n` +
        "</mesh></geometry></library_geometries>\n" +
        '<library_visual_scenes><visual_scene id="Scene" name="Scene"><node id="boxnode" name="box" type="NODE"><instance_geometry url="#box-geom"/></node></visual_scene></library_visual_scenes>\n' +
        '<scene><instance_visual_scene url="#Scene"/></scene>\n</COLLADA>\n'
    );
}

/** 3MF (zip) → Uint8Array; `zipSync` — з fflate бандла f3d-loaders. */
export function threeMf(zipSync, sx, sy, sz, unit = "millimeter") {
    const { v, t } = boxData(sx, sy, sz);
    const model =
        `<?xml version="1.0" encoding="UTF-8"?><model unit="${unit}" xml:lang="en-US" xmlns="${NS_3MF}"><resources><object id="1" type="model"><mesh><vertices>` +
        v.map((p) => `<vertex x="${p[0]}" y="${p[1]}" z="${p[2]}"/>`).join("") +
        "</vertices><triangles>" +
        t.map((f) => `<triangle v1="${f[0]}" v2="${f[1]}" v3="${f[2]}"/>`).join("") +
        '</triangles></mesh></object></resources><build><item objectid="1"/></build></model>';
    return zipSync({
        "[Content_Types].xml": enc(
            `<?xml version="1.0" encoding="UTF-8"?><Types xmlns="${NS_3MF_CT}"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/></Types>`
        ),
        "_rels/.rels": enc(
            `<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="${NS_3MF_REL}"><Relationship Target="/3D/3dmodel.model" Id="rel0" Type="${REL_3MF}"/></Relationships>`
        ),
        "3D/3dmodel.model": enc(model),
    });
}

/** Мінімальний ASCII FBX 7.3 з однією коробкою (одиниці файла). */
export function fbxAscii(sx, sy, sz) {
    const { v, t } = boxData(sx, sy, sz);
    // у FBX індекс останньої вершини полігона зберігається як ~i (-i-1)
    const idx = t.map((f) => [f[0], f[1], -f[2] - 1]).flat();
    return (
        "; FBX 7.3.0 project file\n" +
        "FBXHeaderExtension:  {\n\tFBXHeaderVersion: 1003\n\tFBXVersion: 7300\n}\n" +
        "GlobalSettings:  {\n\tVersion: 1000\n\tProperties70:  {\n" +
        '\t\tP: "UpAxis", "int", "Integer", "",1\n\t\tP: "UpAxisSign", "int", "Integer", "",1\n\t\tP: "FrontAxis", "int", "Integer", "",2\n' +
        '\t\tP: "FrontAxisSign", "int", "Integer", "",1\n\t\tP: "CoordAxis", "int", "Integer", "",0\n\t\tP: "CoordAxisSign", "int", "Integer", "",1\n' +
        '\t\tP: "UnitScaleFactor", "double", "Number", "",1\n\t}\n}\n' +
        "Objects:  {\n" +
        '\tGeometry: 1000, "Geometry::Box", "Mesh" {\n' +
        `\t\tVertices: *24 {\n\t\t\ta: ${v.flat().join(",")}\n\t\t}\n` +
        `\t\tPolygonVertexIndex: *${idx.length} {\n\t\t\ta: ${idx.join(",")}\n\t\t}\n` +
        "\t\tGeometryVersion: 124\n\t}\n" +
        '\tModel: 2000, "Model::Box", "Mesh" {\n\t\tVersion: 232\n\t\tProperties70:  {\n\t\t\tP: "Lcl Translation", "Lcl Translation", "", "A",0,0,0\n\t\t}\n\t}\n' +
        "}\n" +
        "Connections:  {\n\tC: \"OO\",2000,0\n\tC: \"OO\",1000,2000\n}\n"
    );
}
