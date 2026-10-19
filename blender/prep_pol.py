"""
Готовит плитку фальшпола pol_dlya_servernoi.glb (сгенерированная модель: 6 × 5 плиток, в двух столбцах — решётки,
по краю металлическая рамка с уголками; ~1,5 млн треугольников, текстуры 4096²) для сцены «Серверная»:
    blender/assets/pol_servernoi.glb — кусок пола без рамки: плитки по 0,6 м, 5 вдоль X и 6 вдоль Y (столбцы
                                       решёток идут вдоль X), 3,0 × 3,6 м, верх плиток на z = 0, центр в начале
                                       координат; build_server.py кладёт куски подряд
Модель HD: текстуры не уменьшаются (цвет 4096, карты 2048).

Запуск (из корня проекта), после него — пересобрать сцену build_server.py:
    "C:\\Program Files\\Blender Foundation\\Blender 4.5\\blender.exe" --background --python blender/prep_pol.py
"""

import math
import os
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Matrix

sys.path.insert(0, os.path.dirname(__file__))
from prep_model import export_asset, import_decimated, shrink_textures, vertices  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "pol_dlya_servernoi.glb")
OUT = os.path.join(ROOT, "blender", "assets", "pol_servernoi.glb")

TILE = 0.6
COLS, ROWS = 6, 5   # плиток в файле по X и по Y
DECIMATE = 0.012    # ~18 тыс. треугольников: кусков в комнате ~25, рельеф решёток — в карте нормалей


def tile_area(o):
    """Верх плиток — высота, на которую приходится больше всего площади граней, смотрящих вверх; поле плиток —
    крайние такие грани (рамка по краю и решётки — на другой высоте)"""
    ps = [(p.center.x, p.center.y, p.center.z, p.area) for p in o.data.polygons if p.normal.z > 0.95]
    x, y, z, a = np.array(ps).T
    hist, edges = np.histogram(z, bins=200, weights=a)
    i = hist.argmax()
    level = (edges[i] + edges[i + 1]) / 2
    vs = [(o.data.vertices[v].co.x, o.data.vertices[v].co.y) for p in o.data.polygons
          if p.normal.z > 0.95 and abs(p.center.z - level) < (edges[1] - edges[0]) * 2 for v in p.vertices]
    vx, vy = np.array(vs).T
    return level, (np.percentile(vx, 0.2), np.percentile(vx, 99.8)), (np.percentile(vy, 0.2), np.percentile(vy, 99.8))


def crop(o, xr, yr):
    bm = bmesh.new()
    bm.from_mesh(o.data)
    for co, no in (((xr[0], 0, 0), (-1, 0, 0)), ((xr[1], 0, 0), (1, 0, 0)),
                   ((0, yr[0], 0), (0, -1, 0)), ((0, yr[1], 0), (0, 1, 0))):
        geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
        bmesh.ops.bisect_plane(bm, geom=geom, plane_co=co, plane_no=no, clear_outer=True)
    bm.to_mesh(o.data)
    bm.free()


def build():
    o = import_decimated(SRC, DECIMATE)
    level, xr, yr = tile_area(o)
    print("tiles x", np.round(xr, 4), "y", np.round(yr, 4), "level", round(level, 4))
    crop(o, xr, yr)
    kx, ky = COLS * TILE / (xr[1] - xr[0]), ROWS * TILE / (yr[1] - yr[0])
    o.data.transform(Matrix.Diagonal((kx, ky, (kx + ky) / 2, 1))
                     @ Matrix.Translation((-(xr[0] + xr[1]) / 2, -(yr[0] + yr[1]) / 2, -level)))
    o.data.transform(Matrix.Rotation(math.radians(90), 4, "Z"))  # столбцы решёток — вдоль X
    o.data.update()
    o.name = "pol_servernoi"
    co = vertices(o)
    print("piece size, m:", (co.max(0) - co.min(0)).round(3).tolist(), "z", co[:, 2].min().round(3),
          co[:, 2].max().round(3), "scale", round(kx, 2), round(ky, 2), "tris",
          sum(len(p.vertices) - 2 for p in o.data.polygons))
    shrink_textures(scale=2)
    export_asset(OUT)


build()
