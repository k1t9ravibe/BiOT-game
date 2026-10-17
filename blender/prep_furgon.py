"""
Готовит фургон furgonkt.glb (сгенерированная модель: ~1,5 млн треугольников, текстуры 4096², размер ~1 м)
для сцены «Улица у КТПН»: упрощает меш, уменьшает текстуры, ставит в натуральную величину и сохраняет
в blender/assets/furgonkt_van.glb в том же виде, что остальные готовые модели (ось Z вверх, см. place_model
в build_landscape.py): при rz = 0 морда смотрит на −X, низ на нуле, центр в начале координат.

Запуск (из корня проекта), после него — пересобрать сцену build_landscape.py:
    "C:\\Program Files\\Blender Foundation\\Blender 4.5\\blender.exe" --background --python blender/prep_furgon.py
"""

import math
import os

import bpy
from mathutils import Matrix

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "furgonkt.glb")
OUT = os.path.join(ROOT, "blender", "assets", "furgonkt_van.glb")

LENGTH = 5.54     # длина кузова, м — как у прежнего фургона
DECIMATE = 0.03   # доля треугольников, которая остаётся (~45 тыс.)
TEX = {"normal": 1024, "metallic": 1024}  # размер текстур по части имени; остальные (цвет) — 2048
TEX_DEFAULT = 2048


def build():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=SRC)
    o = next(o for o in bpy.data.objects if o.type == "MESH")
    bpy.context.view_layer.objects.active = o
    o.select_set(True)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)  # импорт кладёт поворот Y→Z в объект

    m = o.modifiers.new("decimate", "DECIMATE")
    m.ratio = DECIMATE
    bpy.ops.object.modifier_apply(modifier=m.name)
    bpy.ops.object.shade_smooth_by_angle(angle=math.radians(40))

    # В файле морда смотрит на −Y: поворачиваем на −90° (морда на −X), масштабируем по длине,
    # ставим низом на ноль и центром в начало координат
    o.data.transform(Matrix.Rotation(math.radians(-90), 4, "Z"))
    vs = [v.co for v in o.data.vertices]
    lo = [min(c[i] for c in vs) for i in range(3)]
    hi = [max(c[i] for c in vs) for i in range(3)]
    k = LENGTH / (hi[0] - lo[0])
    o.data.transform(Matrix.Scale(k, 4) @ Matrix.Translation((-(lo[0] + hi[0]) / 2, -(lo[1] + hi[1]) / 2, -lo[2])))
    o.name = "van_body"
    print("van size, m:", [round((hi[i] - lo[i]) * k, 2) for i in range(3)])

    for img in bpy.data.images:
        if img.size[0] == 0:
            continue
        side = next((s for key, s in TEX.items() if key in img.name.lower()), TEX_DEFAULT)
        if img.size[0] > side:
            img.scale(side, side)

    # export_yup=False — как у остальных моделей в blender/assets: place_model ставит их поворотом на −90° по X
    bpy.ops.export_scene.gltf(filepath=OUT, export_format="GLB", export_yup=False, export_image_format="JPEG",
                              export_jpeg_quality=85)
    print("saved", OUT, os.path.getsize(OUT) // 1024, "KB")


build()
