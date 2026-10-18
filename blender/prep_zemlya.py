"""
Готовит плитку земли с травой zemlya_trava.glb (сгенерированная модель: квадрат газона с кочками травы
и камнями на слое грунта, ~1,5 млн треугольников, текстуры 4096²) для сцены «Трасса»:
    blender/assets/zemlya_trava.glb — плитка TILE м по X, поверхность газона на z = 0 (грунт — ниже нуля),
                                     центр в начале координат; кладётся рядами вдоль трассы (build_highway.py)
    blender/assets/trava_top.jpg    — вид плитки сверху без краёв: повторяющаяся текстура дальней земли

Запуск (из корня проекта), после него — пересобрать сцену build_highway.py:
    "C:\\Program Files\\Blender Foundation\\Blender 4.5\\blender.exe" --background --python blender/prep_zemlya.py
"""

import os
import sys

import bpy
import numpy as np
from mathutils import Matrix

sys.path.insert(0, os.path.dirname(__file__))
from prep_model import export_asset, import_decimated, shrink_textures, vertices  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "zemlya_trava.glb")
OUT = os.path.join(ROOT, "blender", "assets", "zemlya_trava.glb")
OUT_TOP = os.path.join(ROOT, "blender", "assets", "trava_top.jpg")

TILE = 6.0         # сторона плитки по X, м: кочки травы — по колено, камни — 0,2–0,4 м
DECIMATE = 0.012   # ~18 тыс. треугольников: плиток в сцене десятки
TOP_CROP = 0.8     # доля стороны плитки, которая идёт в текстуру сверху (без кромки и боков грунта)
TOP_RES = 1024


def grass_level(o):
    """Высота поверхности газона: самая частая высота граней, смотрящих вверх"""
    me = o.data
    me.calc_loop_triangles()
    z = np.array([t.center.z for t in me.loop_triangles if t.normal.z > 0.9])
    hist, edges = np.histogram(z, bins=60)
    i = hist.argmax()
    return (edges[i] + edges[i + 1]) / 2


def bake_top(o, size):
    """Ортографический рендер плитки сверху под рассеянным светом — без теней от кочек"""
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_EEVEE_NEXT"
    sc.render.resolution_x = sc.render.resolution_y = TOP_RES
    sc.world = bpy.data.worlds.new("w")
    sc.world.color = (1.0, 1.0, 1.0)
    sc.world.use_nodes = False
    sc.view_settings.view_transform = "Standard"
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = size * TOP_CROP
    cam.location = (0, 0, 20)
    cam.rotation_euler = (0, 0, 0)
    sc.render.image_settings.file_format = "JPEG"
    sc.render.image_settings.quality = 88
    sc.render.filepath = OUT_TOP
    bpy.ops.render.render(write_still=True)
    print("saved", OUT_TOP)


def build():
    o = import_decimated(SRC, DECIMATE)
    co = vertices(o)
    lo, hi = co.min(0), co.max(0)
    k = TILE / (hi[0] - lo[0])
    o.data.transform(Matrix.Scale(k, 4) @ Matrix.Translation((-(lo[0] + hi[0]) / 2, -(lo[1] + hi[1]) / 2, 0)))
    z0 = grass_level(o)
    o.data.transform(Matrix.Translation((0, 0, -z0)))
    o.name = "zemlya_trava"
    co = vertices(o)
    print("tile size, m:", (co.max(0) - co.min(0)).round(2).tolist(), "grass level was", round(z0, 3))
    shrink_textures()
    export_asset(OUT)
    bake_top(o, TILE)


build()
