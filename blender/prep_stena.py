"""
Готовит стены серверной (сгенерированные модели: панель стены в рамке из балок, сверху трубы и лотки, синяя полоса;
~1,5 млн треугольников, текстуры 4096²):
    stena_s_dveryi.glb  → blender/assets/stena_dver.glb — стена с дверью, электрощитами и вентрешёткой (вход)
    stena_bez_dveri.glb → blender/assets/stena.glb      — стена без двери (остальные стороны)
В обоих файлах после подготовки: стена вдоль X, центр по X в нуле, лицевая сторона (трубы, щиты) смотрит на −Y,
задняя грань на y = 0, низ на z = 0, высота WALL_H. build_server.py растягивает стены по длине под размер комнаты.
Модели HD: текстуры не уменьшаются (цвет 4096, карты 2048). Печатает длину, толщину и глубину панели от лицевой
стороны (по ней ставятся шкаф и логотип) — их берёт build_server.py.

Запуск (из корня проекта), после него — пересобрать сцену build_server.py:
    "C:\\Program Files\\Blender Foundation\\Blender 4.5\\blender.exe" --background --python blender/prep_stena.py
"""

import os
import sys

import bpy
import numpy as np
from mathutils import Matrix

sys.path.insert(0, os.path.dirname(__file__))
from prep_model import export_asset, import_decimated, shrink_textures, vertices  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODELS = [("stena_s_dveryi.glb", "stena_dver.glb"), ("stena_bez_dveri.glb", "stena.glb")]
WALL_H = 4.0       # высота стены, м: дверь в модели — 47 % высоты, так она ~1,9 м
DECIMATE = 0.03    # ~45 тыс. треугольников


def panel_depth(o, front):
    """Глубина плоскости панели от лицевой стороны: больше всего площади граней, смотрящих на −Y"""
    ps = [(p.center.y, p.area) for p in o.data.polygons if p.normal.y < -0.95]
    y, a = np.array(ps).T
    hist, edges = np.histogram(y, bins=200, weights=a)
    i = hist.argmax()
    return (edges[i] + edges[i + 1]) / 2 - front


def build(src, out):
    o = import_decimated(os.path.join(ROOT, src), DECIMATE)
    co = vertices(o)
    lo, hi = co.min(0), co.max(0)
    k = WALL_H / (hi[2] - lo[2])
    o.data.transform(Matrix.Scale(k, 4) @ Matrix.Translation((-(lo[0] + hi[0]) / 2, -hi[1], -lo[2])))
    o.data.update()
    o.name = os.path.splitext(out)[0]
    co = vertices(o)
    front = co[:, 1].min()
    print("WALL", out, "length", round(co[:, 0].max() - co[:, 0].min(), 3), "thick", round(-front, 3),
          "panel from front", round(panel_depth(o, front), 3), "tris", sum(len(p.vertices) - 2 for p in o.data.polygons))
    shrink_textures(scale=2)
    export_asset(os.path.join(ROOT, "blender", "assets", out))


for src, out in MODELS:
    build(src, out)
