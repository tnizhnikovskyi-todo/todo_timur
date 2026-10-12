"""Меблеве підприємство — процедурна 3D-сцена.

Запуск (Blender як Python-модуль, pip install bpy):
    python build_scene.py dist/
або у Blender:
    blender -b -P build_scene.py -- dist/
Лише перевбудувати однофайловий переглядач після правок у viewer/index.html:
    python build_scene.py --embed dist/factory.glb dist

Результат: factory.glb, factory.usdz, factory.blend, odoo_demo.json, index.html, factory_viewer.html
(+ factory_web.glb — квантована копія для переглядача, потрібен Node.js для npx).

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
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402,I001 — bpy має імпортуватися раніше за bmesh/mathutils

HERE = os.path.dirname(os.path.abspath(__file__))
VIEWER = os.path.join(HERE, "viewer", "index.html")


def write_odoo(out_dir):
    """Демо-дані «як із Odoo» (plant/odoo_demo.py) поруч із моделлю."""
    from plant.odoo_demo import generate
    path = os.path.join(out_dir, "odoo_demo.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(generate(), f, ensure_ascii=False, separators=(",", ":"))
    return path


def embed_viewer(out_dir, glb, odoo_json=None):
    """Однофайловий переглядач: модель (base64) і дані Odoo вбудовані, відкривається без веб-сервера."""
    with open(glb, "rb") as f:
        data = base64.b64encode(f.read()).decode()
    with open(VIEWER, encoding="utf-8") as f:
        html = f.read()
    html = html.replace("<!-- MODEL_DATA -->",
                        f'<script type="application/octet-stream" id="model-data">{data}</script>')
    odoo_json = odoo_json or os.path.join(out_dir, "odoo_demo.json")
    if os.path.exists(odoo_json):
        with open(odoo_json, encoding="utf-8") as f:
            odoo = f.read().replace("</", "<\\/")
        html = html.replace("<!-- ODOO_DATA -->",
                            f'<script type="application/json" id="odoo-data">{odoo}</script>')
    standalone = ('<!doctype html>\n<html lang="uk"><head><meta charset="utf-8">'
                  '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">'
                  '</head><body>\n' + html + "\n</body></html>\n")
    with open(os.path.join(out_dir, "factory_viewer.html"), "w", encoding="utf-8") as f:
        f.write(standalone)


def main(out_dir):
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
    shutil.copy(VIEWER, os.path.join(out_dir, "index.html"))
    write_odoo(out_dir)
    # для однофайлового переглядача — квантована копія (KHR_mesh_quantization, three.js читає
    # без декодера): ~40 % менше, щоб сторінка вмістилася в ліміт хостингу
    web = os.path.join(out_dir, "factory_web.glb")
    try:
        subprocess.run(["npx", "--yes", "@gltf-transform/cli@4.1.1", "quantize", glb, web],
                       check=True, capture_output=True, timeout=600)
    except (OSError, subprocess.SubprocessError):
        print("gltf-transform недоступний — вбудовую повний GLB")
        web = glb
    embed_viewer(out_dir, web)
    objs = [o for o in bpy.data.objects if o.type == "MESH"]
    tris = sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in objs)
    print(f"objects={len(objs)} unique_meshes={len(bpy.data.meshes)} rendered_tris={tris}")


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    if argv and argv[0] == "--embed":
        write_odoo(argv[2])
        shutil.copy(VIEWER, os.path.join(argv[2], "index.html"))
        embed_viewer(argv[2], argv[1])
    else:
        main(argv[0] if argv else "dist")
