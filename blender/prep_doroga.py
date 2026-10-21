"""
Готовит кусок сельской грунтовки selskaya_doroga.glb (сгенерированная модель: песчаное полотно с двумя колеями,
по краям камни и комья земли; ~1,5 млн треугольников, текстуры 4096², дорога в файле идёт по Y) для сцены
«Улица у КТПН»:
    blender/assets/selskaya_doroga.glb — плитка дороги вдоль X шириной WIDTH (с камнями по краям), её полотно
                                         на z = 0, центр в начале координат; кладётся подряд вдоль дороги
                                         (build_landscape.py)

Запуск (из корня проекта), после него — пересобрать сцену build_landscape.py:
    "C:\\Program Files\\Blender Foundation\\Blender 4.5\\blender.exe" --background --python blender/prep_doroga.py
"""

import math
import os
import sys

import numpy as np
from mathutils import Matrix

sys.path.insert(0, os.path.dirname(__file__))
from prep_model import export_asset, import_decimated, shrink_textures, vertices  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "selskaya_doroga.glb")
OUT = os.path.join(ROOT, "blender", "assets", "selskaya_doroga.glb")

WIDTH = 6.0        # ширина плитки поперёк дороги вместе с камнями по краям, м (build_landscape: грунтовка ±3 м)
DECIMATE = 0.015   # ~22 тыс. треугольников: плиток вдоль дороги больше десятка


def road_level(o):
    """Высота полотна — верхняя часть граней, смотрящих вверх (колеи ниже, камни по краям выше)"""
    me = o.data
    me.calc_loop_triangles()
    z = np.array([t.center.z for t in me.loop_triangles if t.normal.z > 0.95 and abs(t.center.y) < WIDTH * 0.3])
    return np.percentile(z, 60)


def build():
    o = import_decimated(SRC, DECIMATE)
    o.data.transform(Matrix.Rotation(math.radians(90), 4, "Z"))  # дорога — вдоль X
    co = vertices(o)
    lo, hi = co.min(0), co.max(0)
    k = WIDTH / (hi[1] - lo[1])
    o.data.transform(Matrix.Scale(k, 4) @ Matrix.Translation((-(lo[0] + hi[0]) / 2, -(lo[1] + hi[1]) / 2, 0)))
    o.data.transform(Matrix.Translation((0, 0, -road_level(o))))
    o.name = "selskaya_doroga"
    co = vertices(o)
    print("tile size, m:", (co.max(0) - co.min(0)).round(2).tolist(), "z:", co[:, 2].min().round(2),
          co[:, 2].max().round(2), "scale", round(k, 2))
    shrink_textures()
    export_asset(OUT)


build()
