"""Меблеве підприємство — процедурна 3D-сцена.

Запуск (Blender як Python-модуль, pip install bpy):
    python build_scene.py dist/
або у Blender:
    blender -b -P build_scene.py -- dist/
Лише перевбудувати однофайловий переглядач після правок у viewer/index.html:
    python build_scene.py --embed dist/factory.glb dist

Результат: factory.glb, factory.usdz, factory.blend, odoo_demo.json, index.html, factory_viewer.html
(+ parts/*.glb — модель частинами для переглядача, квантована через npx @gltf-transform/cli).

Код розкладено по модулях пакета plant/:
  layout.py    планування: габарити, зони, ворота, верстати, маршрути
  geom.py      матеріали, збирач мешів, спільні меші, типові вузли (палети, пульти, роботи, люди)
  machines.py  процедурні моделі верстатів
  site.py      будівля, склади, інженерія, люди, транспорт, маршрути

Структура сцени:
  FACTORY                 корінь (extras: dims — габарити будівлі)
    LAYER_<key>           порожній об'єкт-шар (у переглядачі — перемикач шару, extras: order)
      <об'єкт>            у кожного клікабельного об'єкта є властивості
                          code / kind / label / desc (у glTF це extras)

Однакові об'єкти (верстати одного типу, стелажі, палети, комірки) посилаються
на спільний меш — у glTF він зберігається один раз, тому файл лишається малим.
"""
import base64
import json
import math
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402,I001 — bpy має імпортуватися раніше за bmesh/mathutils

HERE = os.path.dirname(os.path.abspath(__file__))
VIEWER = os.path.join(HERE, "viewer", "index.html")


def write_odoo(out_dir, live=False):
    """Дані Odoo поруч із моделлю: демо (plant/odoo_demo.py) або, з --live, жива база (plant/odoo_pull.py)."""
    if live:
        from plant.odoo_pull import generate
    else:
        from plant.odoo_demo import generate
    path = os.path.join(out_dir, "odoo_demo.json")
    from plant.cycle_check import check
    data = generate()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    issues = check(data)  # наскрізний цикл: від вивантаження фури до відвантаження клієнту
    print("cycle_check:", "OK" if not issues else f"{len(issues)} проблем\n  " + "\n  ".join(issues))
    return path


# Частини моделі для переглядача: перша вантажиться одразу, решта — у фоні або коли вмикають шар
PARTS = [("core", "Будівля, склади, виробництво, люди",
          ["Будівля", "Склади й логістика", "Виробництво", "Люди й транспорт"]),
         ("engineering", "Інженерні мережі", ["Інженерні мережі"]),
         ("fire", "Пожежна безпека", ["Пожежна безпека"]),
         ("it", "ІТ і Odoo", ["ІТ і Odoo"]),
         ("site", "Територія й охорона", ["Територія й охорона"])]


def quantize(src, dst):
    """KHR_mesh_quantization: three.js читає без декодера, файл ~40 % менший."""
    try:
        subprocess.run(["npx", "--yes", "@gltf-transform/cli@4.1.1", "quantize", src, dst],
                       check=True, capture_output=True, timeout=600)
    except (OSError, subprocess.SubprocessError):
        print(f"gltf-transform недоступний — {os.path.basename(dst)} без квантування")
        with open(src, "rb") as a, open(dst, "wb") as b:
            b.write(a.read())


def export_parts(out_dir):
    """Кожна група шарів — окремий GLB у parts/ + manifest.json (шари, коди об'єктів, розміри)."""
    from plant.geom import LAYER_COLL
    from plant.layout import D, H, LAYERS, W
    pdir = os.path.join(out_dir, "parts")
    os.makedirs(pdir, exist_ok=True)
    manifest = dict(dims=f"{W:.0f} × {D:.0f} м · h {H:.0f} м",
                    layers=[dict(key=k, label=lb, group=g, order=i) for i, (k, lb, g) in enumerate(LAYERS)], parts=[])
    for key, title, groups in PARTS:
        keys = [k for k, _, g in LAYERS if g in groups]
        bpy.ops.object.select_all(action="DESELECT")
        codes = set()
        for k in keys:
            for ob in LAYER_COLL[k].all_objects:
                ob.select_set(True)
                if "code" in ob:
                    codes.add(str(ob["code"]))
        raw, out = os.path.join(pdir, key + ".raw.glb"), os.path.join(pdir, key + ".glb")
        bpy.ops.export_scene.gltf(filepath=raw, export_format="GLB", use_selection=True, export_extras=True,
                                  export_yup=True, export_apply=True, export_cameras=False, export_lights=False)
        quantize(raw, out)
        os.remove(raw)
        manifest["parts"].append(dict(key=key, title=title, file=f"parts/{key}.glb", layers=keys,
                                      codes=sorted(codes), bytes=os.path.getsize(out)))
    with open(os.path.join(pdir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, separators=(",", ":"))
    return manifest


def _viewer_html(out_dir, parts=False, odoo=False, b64_files=False):
    """Сторінка переглядача: маніфест частин завжди; за потреби — частини (base64) і дані Odoo всередині.
    b64_files — частини як текстові файли base64 (для хостингу, що не віддає .glb)."""
    with open(VIEWER, encoding="utf-8") as f:
        html = f.read()
    with open(os.path.join(out_dir, "parts", "manifest.json"), encoding="utf-8") as f:
        manifest = json.load(f)
    if b64_files:
        for p in manifest["parts"]:
            p["file"] += ".txt"
    html = html.replace("<!-- PARTS_MANIFEST -->", '<script type="application/json" id="parts-manifest">'
                        + json.dumps(manifest, ensure_ascii=False).replace("</", "<\\/") + "</script>")
    if parts:
        blobs = []
        for p in manifest["parts"]:
            with open(os.path.join(out_dir, p["file"]), "rb") as f:
                data = base64.b64encode(f.read()).decode()
            blobs.append(f'<script type="application/octet-stream" id="part-{p["key"]}">{data}</script>')
        html = html.replace("<!-- MODEL_DATA -->", "\n".join(blobs))
    if odoo:
        with open(os.path.join(out_dir, "odoo_demo.json"), encoding="utf-8") as f:
            data = f.read().replace("</", "<\\/")
        html = html.replace("<!-- ODOO_DATA -->", f'<script type="application/json" id="odoo-data">{data}</script>')
    return html


def embed_viewer(out_dir):
    """index.html (частини з parts/) і factory_viewer.html (усе всередині, відкривається подвійним кліком).
    Окремо, не в git: artifact/ — сторінка з даними всередині й частинами як base64-текст поруч (для
    хостингу з обмеженням розміру сторінки й типів файлів)."""
    for name, kw in (("index.html", {}), ("factory_viewer.html", dict(parts=True, odoo=True))):
        with open(os.path.join(out_dir, name), "w", encoding="utf-8") as f:
            f.write(standalone(_viewer_html(out_dir, **kw)))
    adir = os.path.join(out_dir, "artifact")
    os.makedirs(os.path.join(adir, "parts"), exist_ok=True)
    with open(os.path.join(adir, "index.html"), "w", encoding="utf-8") as f:
        f.write(_viewer_html(out_dir, odoo=True, b64_files=True))
    for name in os.listdir(os.path.join(out_dir, "parts")):
        if name.endswith(".glb"):
            with open(os.path.join(out_dir, "parts", name), "rb") as src, \
                    open(os.path.join(adir, "parts", name + ".txt"), "w") as dst:
                dst.write(base64.b64encode(src.read()).decode())


def standalone(html):
    """Повний HTML-документ навколо сторінки переглядача (сам viewer/index.html — без «скелета»)."""
    return ('<!doctype html>\n<html lang="uk"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">'
            '</head><body>\n' + html + "\n</body></html>\n")


def main(out_dir, live=False):
    from plant.geom import make_layers, make_materials
    from plant.site import build_all

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.unit_settings.system = "METRIC"
    make_materials()
    make_layers()
    build_all()

    # камера і світло — для тих, хто відкриє .blend
    cam = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
    bpy.context.scene.collection.objects.link(cam)
    cam.location = (25, -80, 95)
    cam.rotation_euler = (math.radians(52), 0, math.radians(-22))
    bpy.context.scene.camera = cam
    sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN"))
    sun.data.energy = 3
    sun.rotation_euler = (math.radians(40), math.radians(15), math.radians(30))
    bpy.context.scene.collection.objects.link(sun)

    os.makedirs(out_dir, exist_ok=True)
    glb = os.path.join(out_dir, "factory.glb")
    bpy.ops.export_scene.gltf(filepath=glb, export_format="GLB", export_extras=True,
                              export_yup=True, export_apply=True, export_cameras=False,
                              export_lights=False)
    bpy.ops.wm.usd_export(filepath=os.path.join(out_dir, "factory.usdz"),
                          export_materials=True, generate_preview_surface=True,
                          convert_orientation=True, export_global_forward_selection="NEGATIVE_Z",
                          export_global_up_selection="Y", export_lights=False,
                          export_cameras=False)
    bpy.context.preferences.filepaths.save_version = 0  # без factory.blend1
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(os.path.join(out_dir, "factory.blend")))
    write_odoo(out_dir, live)
    export_parts(out_dir)
    embed_viewer(out_dir)
    objs = [o for o in bpy.data.objects if o.type == "MESH"]
    tris = sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in objs)
    print(f"objects={len(objs)} unique_meshes={len(bpy.data.meshes)} rendered_tris={tris}")


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    live = "--live" in argv  # дані з Odoo (ODOO_URL, ODOO_DB, ODOO_USER, ODOO_PASSWORD), а не демо
    argv = [a for a in argv if a != "--live"]
    if argv and argv[0] == "--embed":  # лише переглядач і дані, частини моделі вже є в <dist>/parts
        write_odoo(argv[-1], live)
        embed_viewer(argv[-1])
    else:
        main(argv[0] if argv else "dist", live)
