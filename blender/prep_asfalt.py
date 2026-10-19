"""
Готовит кусок дороги asfalt.glb (сгенерированная модель: полотно асфальта с белыми краевыми линиями, по бокам
бордюры с травой, снизу слой грунта; ~1,5 млн треугольников, текстуры 4096², дорога в файле идёт по Y) для сцены
«Трасса»:
    blender/assets/asfalt.glb — плитка дороги вдоль X: асфальт от −ROAD до +ROAD по Y, его поверхность на z = 0,
                                центр в начале координат; кладётся подряд вдоль трассы (build_highway.py)

Запуск (из корня проекта), после него — пересобрать сцену build_highway.py:
    "C:\\Program Files\\Blender Foundation\\Blender 4.5\\blender.exe" --background --python blender/prep_asfalt.py
"""

import math
import os
import sys

import bpy
import numpy as np
from mathutils import Matrix

sys.path.insert(0, os.path.dirname(__file__))
from prep_model import export_asset, import_decimated, shrink_textures, vertices  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "asfalt.glb")
OUT = os.path.join(ROOT, "blender", "assets", "asfalt.glb")

ROAD = 3.6         # полуширина асфальта в сцене, м (build_highway.ROAD)
DECIMATE = 0.015   # ~22 тыс. треугольников: полотно плоское, плиток в сцене десятки


def asphalt_level_and_width(o):
    """Высота полотна — самая частая высота граней, смотрящих вверх; полуширина и центр — по крайним таким граням по Y"""
    me = o.data
    me.calc_loop_triangles()
    tri = [(t.center.y, t.center.z) for t in me.loop_triangles if t.normal.z > 0.95]
    y, z = np.array(tri).T
    hist, edges = np.histogram(z, bins=80)
    i = hist.argmax()
    level = (edges[i] + edges[i + 1]) / 2
    on = abs(z - level) < (edges[1] - edges[0]) * 1.5
    y0, y1 = np.percentile(y[on], 0.5), np.percentile(y[on], 99.5)
    return level, (y1 - y0) / 2, (y0 + y1) / 2  # центр — между краями: треугольники после упрощения неравномерны


def build():
    o = import_decimated(SRC, DECIMATE)
    o.data.transform(Matrix.Rotation(math.radians(90), 4, "Z"))  # дорога — вдоль X
    co = vertices(o)
    lo, hi = co.min(0), co.max(0)
    o.data.transform(Matrix.Translation((-(lo[0] + hi[0]) / 2, 0, 0)))
    level, half, mid = asphalt_level_and_width(o)
    k = ROAD / half
    o.data.transform(Matrix.Scale(k, 4) @ Matrix.Translation((0, -mid, -level)))
    o.name = "asfalt"
    co = vertices(o)
    print("tile size, m:", (co.max(0) - co.min(0)).round(2).tolist(), "y:", co[:, 1].min().round(2),
          co[:, 1].max().round(2), "z:", co[:, 2].min().round(2), co[:, 2].max().round(2), "scale", round(k, 2))
    shrink_textures()
    export_asset(OUT)


build()
