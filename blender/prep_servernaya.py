"""
Готовит основу серверной servernaya.glb (сгенерированная модель: угол помещения — пол с решётками и две стены
с кабельными лотками, — и рядом два плоских обломка; ~1,5 млн треугольников, текстуры 4096²) для сцены «Серверная»:
    blender/assets/servernaya_ugol.glb — только угол: стены на +X и +Y, наружный угол стен в начале координат,
                                         верх пола на z = 0, высота стен WALL_H. Из четырёх зеркальных копий
                                         build_server.py собирает замкнутую комнату.
Модель HD: упрощение мягкое, текстуры не уменьшаются (цвет 4096, карты 2048) — в комнате стены видны вблизи.

Запуск (из корня проекта), после него — пересобрать сцену build_server.py:
    "C:\\Program Files\\Blender Foundation\\Blender 4.5\\blender.exe" --background --python blender/prep_servernaya.py
"""

import math
import os
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Matrix

sys.path.insert(0, os.path.dirname(__file__))
from prep_model import export_asset, shrink_textures, vertices  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "servernaya.glb")
OUT = os.path.join(ROOT, "blender", "assets", "servernaya_ugol.glb")

WALL_H = 3.6       # высота стен над полом, м — как потолок в build_server.py
DECIMATE = 0.3     # от угла (~265 тыс. треугольников) остаётся ~80 тыс.
# Угол обрезается по x > CROP[0], y > CROP[1] (без бортика по открытым краям). Внутренние грани стен после
# масштаба (измерено лучами): x = −0,26, y = −0,18 — build_server.INNER
CROP = (-6.45, -5.85)


def keep_corner():
    """Импорт, склейка вершин, разбиение на куски; остаётся самый высокий — угол комнаты со стенами
    (обломки рядом плоские). Склейка с допуском 1 мм: иначе стены и пол угла — отдельные куски"""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=SRC)
    o = next(o for o in bpy.data.objects if o.type == "MESH")
    bpy.context.view_layer.objects.active = o
    o.select_set(True)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.remove_doubles(threshold=0.001)
    bpy.ops.mesh.separate(type="LOOSE")
    bpy.ops.object.mode_set(mode="OBJECT")
    parts = sorted((p for p in bpy.data.objects if p.type == "MESH"), key=lambda p: -vertices(p)[:, 2].max())
    for p in parts[1:]:
        bpy.data.objects.remove(p)
    o = parts[0]
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = o
    o.select_set(True)
    # Швы развёртки — по краям островков UV, чтобы упрощение не утянуло их в тёмные щели атласа
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.seams_from_islands()
    bpy.ops.object.mode_set(mode="OBJECT")
    m = o.modifiers.new("decimate", "DECIMATE")
    m.ratio = DECIMATE
    bpy.ops.object.modifier_apply(modifier=m.name)
    bpy.ops.object.shade_smooth_by_angle(angle=math.radians(30))
    return o


def floor_level(o):
    """Верх пола — высота, на которую приходится больше всего площади граней, смотрящих вверх"""
    up = [(p.center.z, p.area) for p in o.data.polygons if p.normal.z > 0.95]
    z, a = np.array(up).T
    hist, edges = np.histogram(z, bins=200, weights=a)
    i = hist.argmax()
    return (edges[i] + edges[i + 1]) / 2


def build():
    o = keep_corner()
    co = vertices(o)
    lo, hi = co.min(0), co.max(0)
    # Стены — там, где много вершин выше половины высоты; разворачиваем зеркально, чтобы они были на +X и +Y
    top = co[co[:, 2] > lo[2] + 0.6 * (hi[2] - lo[2])]
    sx = 1 if np.sum(top[:, 0] > (lo[0] + hi[0]) / 2) > len(top) / 2 else -1
    sy = 1 if np.sum(top[:, 1] > (lo[1] + hi[1]) / 2) > len(top) / 2 else -1
    if sx * sy < 0:  # одно отражение вывернет грани — вместо этого поворот на 90° с отражением осей
        o.data.transform(Matrix(((0, 1, 0, 0), (1, 0, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1))))
        o.data.flip_normals()
        co = vertices(o)
        lo, hi = co.min(0), co.max(0)
        top = co[co[:, 2] > lo[2] + 0.6 * (hi[2] - lo[2])]
        sx = 1 if np.sum(top[:, 0] > (lo[0] + hi[0]) / 2) > len(top) / 2 else -1
        sy = sx
    if sx < 0:  # обе стены на минусах — поворот на 180°
        o.data.transform(Matrix.Rotation(math.pi, 4, "Z"))
    co = vertices(o)
    lo, hi = co.min(0), co.max(0)
    o.data.update()
    z0 = floor_level(o)
    k = WALL_H / (hi[2] - z0)
    o.data.transform(Matrix.Scale(k, 4) @ Matrix.Translation((-hi[0], -hi[1], -z0)))
    o.data.update()
    o.name = "servernaya_ugol"

    # По открытым краям у модели бортик ~0,3 м (край диорамы): в собранной комнате он лёг бы порогом посередине
    bm = bmesh.new()
    bm.from_mesh(o.data)
    for co_, no in (((CROP[0], 0, 0), (-1, 0, 0)), ((0, CROP[1], 0), (0, -1, 0))):
        geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
        bmesh.ops.bisect_plane(bm, geom=geom, plane_co=co_, plane_no=no, clear_outer=True)
    bm.to_mesh(o.data)
    bm.free()
    co = vertices(o)
    print("corner size, m:", (co.max(0) - co.min(0)).round(2).tolist(), "scale", round(k, 2), "tris",
          sum(len(p.vertices) - 2 for p in o.data.polygons))
    shrink_textures(scale=2)
    export_asset(OUT)


build()
