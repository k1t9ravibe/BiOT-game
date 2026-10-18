"""
Готовит деревья derevya_dlya_fona.glb (сгенерированная модель одним мешем: берёза, тополь и ель в ряд вдоль X,
~0,5 млн треугольников, текстуры 4096², высота ~0,7 м) и сохраняет в blender/assets/derevya.glb тремя объектами
tree_bereza, tree_topol, tree_el (ось Z вверх, как остальные готовые модели). Начало координат каждого дерева —
низ ствола, так что в сцене их удобно клонировать по одному (build_city.py, place_trees).

Запуск (из корня проекта), после него — пересобрать сцену build_city.py:
    "C:\\Program Files\\Blender Foundation\\Blender 4.5\\blender.exe" --background --python blender/prep_trees.py
"""

import os
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Matrix

sys.path.insert(0, os.path.dirname(__file__))
from prep_model import export_asset, import_decimated, shrink_textures, vertices  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "derevya_dlya_fona.glb")
OUT = os.path.join(ROOT, "blender", "assets", "derevya.glb")

NAMES = ("tree_bereza", "tree_topol", "tree_el")  # слева направо по X
HEIGHT = 9.0       # высота самого высокого дерева, м — по ней масштаб всех трёх
DECIMATE = 0.03    # доля треугольников (~5 тыс. на дерево): деревьев в сцене десятки


def split_x(xs, parts):
    """Границы по X между деревьями — самые широкие промежутки без вершин"""
    s = np.sort(xs)
    gaps = np.argsort(np.diff(s))[-(parts - 1):]
    return sorted((s[i] + s[i + 1]) / 2 for i in gaps)


def build():
    o = import_decimated(SRC, DECIMATE)
    co = vertices(o)
    k = HEIGHT / (co[:, 2].max() - co[:, 2].min())
    cuts = split_x(co[:, 0], len(NAMES))
    print("cuts", cuts)
    bounds = [-np.inf, *cuts, np.inf]
    for i, name in enumerate(NAMES):
        t = o.copy()
        t.data = o.data.copy()
        t.name = t.data.name = name
        bpy.context.collection.objects.link(t)
        bm = bmesh.new()
        bm.from_mesh(t.data)
        lo, hi = bounds[i], bounds[i + 1]
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if not lo < f.calc_center_median().x < hi], context="FACES")
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
        bm.to_mesh(t.data)
        bm.free()
        tc = vertices(t)
        low = tc[tc[:, 2] < tc[:, 2].min() + 0.01]  # низ ствола
        base = (low[:, 0].mean(), low[:, 1].mean(), tc[:, 2].min())
        t.data.transform(Matrix.Scale(k, 4) @ Matrix.Translation([-c for c in base]))
        t.location = [c * k for c in base]
        print(name, "size, m:", ((tc.max(0) - tc.min(0)) * k).round(2).tolist())
    bpy.data.objects.remove(o)
    shrink_textures()
    export_asset(OUT)


build()
